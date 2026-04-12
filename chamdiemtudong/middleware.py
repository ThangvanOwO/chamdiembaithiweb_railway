"""
Custom middleware for development.
"""
from django.conf import settings


class DisableCSRFOriginCheckMiddleware:
    """
    In DEBUG mode, skip CSRF origin checking for localhost requests.
    This allows browser preview proxies (random ports) to work.
    Only active when DEBUG=True.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            origin = request.META.get('HTTP_ORIGIN', '')
            if origin.startswith('http://127.0.0.1:') or origin.startswith('http://localhost:'):
                request.META['HTTP_ORIGIN'] = f'http://127.0.0.1:{request.META.get("SERVER_PORT", "8000")}'
        return self.get_response(request)
