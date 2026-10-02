"""Verified registration: challenge -> email -> password confirmation -> User."""
from datetime import timedelta
from smtplib import SMTPException

import requests
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from allauth.account.models import EmailAddress

from .models import PendingSignup, TeacherProfile
from .security import client_ip


def signup_ready():
    return bool(settings.EMAIL_HOST and settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def create_username_account(data):
    if not settings.ALLOW_USERNAME_SIGNUP:
        raise ValidationError('Đăng ký bằng tên tài khoản hiện chưa mở.')
    parts = data['full_name'].split()
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=data['username'], password=data['password'],
                email=data.get('email', ''),
                first_name=' '.join(parts[:-1]) if len(parts) > 1 else parts[0],
                last_name=parts[-1] if len(parts) > 1 else '')
            TeacherProfile.objects.get_or_create(user=user)
            if user.email:
                EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    except IntegrityError as exc:
        raise ValidationError('Tên tài khoản đã được sử dụng. Vui lòng chọn tên khác.') from exc
    return user


def password_login_username(identity):
    """Resolve exactly one username/email without affecting Google linking."""
    query = {'email__iexact': identity} if '@' in identity else {'username__iexact': identity}
    try:
        return User.objects.get(**query).username
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        return identity


def verify_challenge(request, token):
    if not signup_ready():
        raise ValidationError('Đăng ký email tạm chưa mở. Vui lòng đăng ký bằng Google hoặc liên hệ quản trị viên.')
    if not isinstance(token, str) or not token or len(token) > 2048:
        raise ValidationError('Vui lòng hoàn thành bước xác minh chống spam.')
    try:
        result = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={'secret': settings.TURNSTILE_SECRET_KEY, 'response': token, 'remoteip': client_ip(request)},
            timeout=8)
        result.raise_for_status()
        data = result.json()
        valid = (isinstance(data, dict) and data.get('success') is True
                 and data.get('hostname') in settings.TURNSTILE_HOSTNAMES
                 and data.get('action') == 'signup')
    except (requests.RequestException, ValueError):
        valid = False
    if not valid:
        raise ValidationError('Xác minh chống spam chưa thành công. Vui lòng thử lại.')


def start_signup(request, data, token):
    verify_challenge(request, token)
    # Identical result for existing and pending email addresses.
    if User.objects.filter(email__iexact=data['email']).exists():
        return
    import uuid
    pending, _ = PendingSignup.objects.update_or_create(email=data['email'], defaults={
        'token': uuid.uuid4(), 'password_hash': make_password(data['password']),
        'first_name': data.get('first_name', ''), 'last_name': data.get('last_name', ''),
        'expires_at': timezone.now() + timedelta(hours=1),
    })
    url = settings.PUBLIC_SITE_URL + reverse('accounts:verify_signup', args=[pending.token])
    try:
        sent = send_mail('Xác minh đăng ký GradeFlow',
            f'Để hoàn tất đăng ký, mở liên kết và nhập lại mật khẩu anh/chị vừa chọn:\n{url}\n'
            'Liên kết hết hạn sau 1 giờ. Nếu không yêu cầu đăng ký, hãy bỏ qua email này.',
            settings.DEFAULT_FROM_EMAIL, [pending.email])
        if sent != 1:
            raise OSError('Mail not accepted')
    except (SMTPException, OSError):
        raise ValidationError('Chưa gửi được email xác minh. Vui lòng thử lại sau.')
    PendingSignup.objects.filter(expires_at__lt=timezone.now()).delete()


@require_http_methods(['GET', 'POST'])
def verify_signup(request, token):
    pending = PendingSignup.objects.filter(token=token, expires_at__gt=timezone.now()).first()
    error = ''
    if pending is None:
        error = 'Liên kết đã hết hạn hoặc đã sử dụng. Vui lòng đăng ký lại.'
    elif request.method == 'POST':
        if not check_password(request.POST.get('password', ''), pending.password_hash):
            error = 'Mật khẩu chưa đúng. Nhập mật khẩu đã chọn khi đăng ký.'
        else:
            with transaction.atomic():
                # Delete is the atomic claim: only one confirmation may create a User.
                claimed, _ = PendingSignup.objects.filter(pk=pending.pk, token=token,
                    expires_at__gt=timezone.now()).delete()
                if claimed and not User.objects.filter(email__iexact=pending.email).exists():
                    user = User.objects.create(username=pending.email, email=pending.email,
                        password=pending.password_hash, first_name=pending.first_name,
                        last_name=pending.last_name)
                    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
                    TeacherProfile.objects.get_or_create(user=user)
                    messages.success(request, 'Đăng ký thành công. Anh/chị được tặng 100 điểm tín dụng. Vui lòng đăng nhập.')
                    return redirect('accounts:login')
            error = 'Liên kết đã sử dụng hoặc tài khoản đã tồn tại. Vui lòng đăng nhập.'
    response = render(request, 'accounts/verify_signup.html', {'valid': pending is not None, 'error': error},
                      status=400 if error else 200)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response
