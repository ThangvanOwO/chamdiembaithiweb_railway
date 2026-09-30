"""
chamdiemtudong URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import HttpResponse

from django.views.generic import TemplateView
from website.views import legacy_upload
from accounts.private_media import private_media
from accounts import risk_admin

def sw_view(request):
    """Serve service worker at root for full scope."""
    sw_path = settings.STATICFILES_DIRS[0] / 'js' / 'sw.js'
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')


urlpatterns = [
    path('media/<path:path>', private_media, name='private_media'),
    # PWA — must be at root for full scope
    path('sw.js', sw_view),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='pwa_offline'),
    # App
    path('admin/security/', admin.site.admin_view(risk_admin.dashboard), name='risk_dashboard'),
    path('admin/security/<int:case_id>/', admin.site.admin_view(risk_admin.detail), name='risk_detail'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),     # Custom login/logout/profile (matched first)
    path('accounts/', include('allauth.socialaccount.providers.google.urls')),  # Google OAuth
    path('accounts/', include('allauth.urls')),     # allauth: social callbacks
    path('api/', include('api.urls')),            # REST API for mobile app
    path('grading/', include('grading.urls')),
    path('chamtn/', legacy_upload, name='chamtn_spa'),
    path('', include('dashboard.urls')),  # Dashboard handles /dashboard/ prefix internally
    path('', include('website.urls')),
]

# Media is private in development and production alike.
