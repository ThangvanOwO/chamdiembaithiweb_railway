"""
Custom allauth adapters.
- Allow email/password signup via custom register view.
- Allow social login (Google) to auto-create users.
"""
import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.http import HttpResponse
from django.db import DatabaseError
from .security import client_ip, take_limit

logger = logging.getLogger('allauth')


class CustomAccountAdapter(DefaultAccountAdapter):
    """Allow signup (used by both custom register view and allauth internally)."""
    def is_open_for_signup(self, request):
        # Email registration must go through our Turnstile + email confirmation.
        return False


class GoogleSocialAdapter(DefaultSocialAccountAdapter):
    """Allow Google OAuth signup — auto-create user on first Google login."""
    def is_open_for_signup(self, request, sociallogin):
        return True

    def can_authenticate_by_email(self, login, email):
        """A contact email entered at signup cannot grant access via Google."""
        from allauth.account.models import EmailAddress
        return (super().can_authenticate_by_email(login, email)
                and EmailAddress.objects.filter(email__iexact=email, verified=True).exists())

    def on_authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        logger.error(f'[SOCIAL] auth error: provider={provider_id}, error={error}, exception={exception}')

    def pre_social_login(self, request, sociallogin):
        verified = any(address.verified and address.email.casefold() == sociallogin.user.email.casefold()
                       for address in sociallogin.email_addresses)
        if sociallogin.account.provider != 'google' or not verified:
            raise ImmediateHttpResponse(HttpResponse('Cần tài khoản Google có email đã xác minh.', status=403))
        if not sociallogin.is_existing:
            try:
                allowed = take_limit('signup', client_ip(request), 5, 3600)
            except DatabaseError:
                raise ImmediateHttpResponse(HttpResponse('Tạm thời chưa thể đăng ký. Vui lòng thử lại sau.', status=503))
            if not allowed:
                raise ImmediateHttpResponse(HttpResponse('Quá nhiều yêu cầu đăng ký. Vui lòng thử lại sau.', status=429))
        super().pre_social_login(request, sociallogin)
