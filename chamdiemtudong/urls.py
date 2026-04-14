"""
chamdiemtudong URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.socialaccount.urls')),  # Google OAuth callbacks only
    path('accounts/', include('accounts.urls')),               # Custom login/logout/profile
    path('grading/', include('grading.urls')),
    path('', include('dashboard.urls')),  # Dashboard handles /dashboard/ prefix internally
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
