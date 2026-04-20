"""
chamdiemtudong URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.http import HttpResponse

from django.views.generic import RedirectView, TemplateView

def sw_view(request):
    """Serve service worker at root for full scope."""
    sw_path = settings.STATICFILES_DIRS[0] / 'js' / 'sw.js'
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


urlpatterns = [
    # PWA — must be at root for full scope
    path('sw.js', sw_view),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='pwa_offline'),
    # App
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),     # Custom login/logout/profile (matched first)
    path('accounts/', include('allauth.socialaccount.providers.google.urls')),  # Google OAuth
    path('accounts/', include('allauth.urls')),     # allauth: social callbacks
    path('grading/', include('grading.urls')),
    path('', include('dashboard.urls')),  # Dashboard handles /dashboard/ prefix internally
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
