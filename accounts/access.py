"""Session authentication boundary for the legacy browser API."""
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect


def private_api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({'error': 'Vui lòng đăng nhập.'}, status=401)
        return view(request, *args, **kwargs)
    return never_cache(csrf_protect(wrapped))
