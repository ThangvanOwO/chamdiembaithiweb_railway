"""Persistent limits for every public authentication entry point."""
import hashlib
import ipaddress
import json
import logging
import time
from datetime import datetime, timezone

from django.conf import settings
from django.db import DatabaseError, OperationalError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils.cache import patch_cache_control

from .models import SecurityRateBucket

logger = logging.getLogger(__name__)


def client_ip(request):
    # Enabled only behind our loopback-only Nginx, which overwrites this header.
    raw = request.META.get('REMOTE_ADDR', '')
    if settings.TRUST_PROXY_CLIENT_IP:
        raw = request.META.get('HTTP_X_GRADEFLOW_CLIENT_IP', raw)
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return 'unknown'


def take_limit(scope, identity, limit, seconds):
    current = int(time.time())
    window = current // seconds
    key = hashlib.sha256(f'{scope}:{identity}:{window}'.encode()).hexdigest()
    expires = datetime.fromtimestamp((window + 1) * seconds, timezone.utc)
    for attempt in range(5):
        try:
            with transaction.atomic():
                bucket, created = SecurityRateBucket.objects.get_or_create(
                    key=key, defaults={'expires_at': expires})
                if created:
                    SecurityRateBucket.objects.filter(
                        expires_at__lt=datetime.fromtimestamp(current, timezone.utc)).delete()
                return bool(SecurityRateBucket.objects.filter(pk=key, hits__lt=limit).update(hits=F('hits') + 1))
        except OperationalError as exc:
            if 'locked' not in str(exc).lower() or attempt == 4:
                raise
            time.sleep(0.02 * (attempt + 1))


class AuthenticationSafetyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.rstrip('/')
        group = None
        if path in ('/accounts/login', '/api/login', '/api/v1/auth/login', '/admin/login'):
            group, limit, period = 'login', 30, 600
        elif path in ('/accounts/register', '/accounts/signup', '/api/v1/auth/register'):
            group, limit, period = 'signup', 5, 3600
        elif path in ('/accounts/password-reset', '/accounts/password/reset'):
            group, limit, period = 'reset', 5, 3600
        elif path.startswith('/accounts/verify-signup/') or path.startswith('/accounts/reset/'):
            group, limit, period = 'confirm', 15, 600

        if group and request.method == 'POST':
            try:
                content_length = int(request.META.get('CONTENT_LENGTH') or 0)
            except ValueError:
                return JsonResponse({'error': 'Yêu cầu không hợp lệ.'}, status=400)
            if content_length > 16 * 1024 or len(request.body) > 16 * 1024:
                return JsonResponse({'error': 'Yêu cầu quá lớn.'}, status=413)
            try:
                allowed = take_limit(group, client_ip(request), limit, period)
                if group == 'login':
                    try:
                        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
                        identity = str(data.get('email') or data.get('username') or '').strip().casefold()[:254]
                    except (ValueError, AttributeError, UnicodeDecodeError):
                        identity = ''
                    if identity:
                        allowed = take_limit('login-account', identity, 12, 600) and allowed
            except DatabaseError:
                logger.exception('Authentication rate limit storage unavailable')
                return JsonResponse({'error': 'Tạm thời chưa thể xác thực. Vui lòng thử lại sau.'}, status=503)
            if not allowed:
                response = JsonResponse({'error': 'Quá nhiều yêu cầu. Vui lòng thử lại sau.'}, status=429)
                response['Retry-After'] = str(period)
                response['Cache-Control'] = 'no-store'
                return response

        response = self.get_response(request)
        if request.path.startswith(('/api/', '/accounts/', '/admin/', '/dashboard/', '/grading/', '/media/')):
            patch_cache_control(response, private=True, no_store=True, max_age=0)
            response.setdefault('Referrer-Policy', 'same-origin')
        return response
