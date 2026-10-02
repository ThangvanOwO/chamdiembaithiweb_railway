"""
Django settings for chamdiemtudong project.
Chấm Điểm Trắc Nghiệm Online — Auto Exam Grading Platform
"""

from pathlib import Path
import os
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Password-reset delivery. Leave disabled until a real SMTP account is configured.
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'GradeFlow <noreply@gradeflow.io.vn>')
EMAIL_TIMEOUT = 15
PUBLIC_SITE_URL = os.environ.get('PUBLIC_SITE_URL', 'https://gradeflow.io.vn').rstrip('/')
TURNSTILE_SITE_KEY = os.environ.get('TURNSTILE_SITE_KEY', '')
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY', '')
TURNSTILE_HOSTNAMES = os.environ.get('TURNSTILE_HOSTNAMES', 'gradeflow.io.vn').split(',')
TRUST_PROXY_CLIENT_IP = os.environ.get('TRUST_PROXY_CLIENT_IP', '0') == '1'
# Explicitly enable username/password signup for the closed-testing period.
# No email is claimed or marked verified by this registration method.
ALLOW_USERNAME_SIGNUP = os.environ.get('ALLOW_USERNAME_SIGNUP', '0') == '1'

# No pricing or reward amount is assumed. These remain inactive until configured.
CREDIT_PAYMENT_PROVIDER = os.environ.get('CREDIT_PAYMENT_PROVIDER', '')
CREDIT_REWARD_PROVIDER = os.environ.get('CREDIT_REWARD_PROVIDER', 'accounts.admob_rewards.AdMobRewardProvider')
CREDIT_PACKAGES = {}
CREDIT_REWARD_POINTS = 5
CREDIT_REWARD_PERIOD = 'daily'  # Asia/Ho_Chi_Minh
CREDIT_REWARD_LIMIT = 3
ADMOB_REWARDED_UNIT_ID = 'ca-app-pub-6695808615282253/6070051413'
# Enable after setting and testing the callback URL in AdMob.
ADMOB_SSV_ENABLED = os.environ.get('ADMOB_SSV_ENABLED', '0') == '1'


# =============================================================================
# SECURITY
# =============================================================================

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-c=-0ad1%41m$477yny(c-t+or$_=e%%11v5z@26&9-9ds*v)3_'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

# Railway: thêm domain tự động
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)

# Railway environment: cho phép mọi host (healthcheck dùng IP nội bộ)
if os.environ.get('RAILWAY_ENVIRONMENT'):
    ALLOWED_HOSTS = ['*']
    # Railway terminates SSL at edge — tell Django requests are HTTPS
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:8001',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8001',
]
if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_PUBLIC_DOMAIN}')

# Custom domain (DuckDNS, custom DNS, ...) — set via env CSRF_TRUSTED_ORIGINS
_extra_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS.extend([o.strip() for o in _extra_csrf.split(',') if o.strip()])

# Tin Nginx forward HTTPS qua header X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')



# =============================================================================
# APPLICATIONS
# =============================================================================

INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_htmx',
    'import_export',

    # Local apps
    'accounts.apps.AccountsConfig',
    'grading.apps.GradingConfig',
    'dashboard.apps.DashboardConfig',
]

SITE_ID = 1


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'chamdiemtudong.middleware.DisableCSRFOriginCheckMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.security.AuthenticationSafetyMiddleware',
    'accounts.risk.RiskMonitoringMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =============================================================================
# URL & TEMPLATES
# =============================================================================

ROOT_URLCONF = 'chamdiemtudong.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'chamdiemtudong.wsgi.application'


# =============================================================================
# DATABASE — Railway PostgreSQL (DATABASE_URL) / SQLite fallback cho dev
# =============================================================================

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Production: Railway PostgreSQL
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    # Development: SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# =============================================================================
# AUTHENTICATION — django-allauth (email/password only, NO social login)
# =============================================================================

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth config
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_SIGNUP_CLOSED = False  # Public signup enabled

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# --- Google OAuth2 (Social Login) ---
# Credentials are stored in DB via setup_google_oauth management command
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# On Railway, allauth must use https for callback URLs
if os.environ.get('RAILWAY_ENVIRONMENT'):
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
SOCIALACCOUNT_AUTO_SIGNUP = True         # Auto-create user on first Google login
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True # Match existing user by email
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_LOGIN_ON_GET = True         # Skip intermediate "Continue?" page
SOCIALACCOUNT_QUERY_EMAIL = True

# Custom adapters: block email signup, allow Google signup
ACCOUNT_ADAPTER = 'accounts.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.GoogleSocialAdapter'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# =============================================================================
# INTERNATIONALIZATION — Vietnamese
# =============================================================================

LANGUAGE_CODE = 'vi'

TIME_ZONE = 'Asia/Ho_Chi_Minh'

USE_I18N = True

USE_TZ = True


# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise for production static file serving
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =============================================================================
# CELERY — Async grading tasks
# =============================================================================

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Ho_Chi_Minh'


# =============================================================================
# MISC
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# REST FRAMEWORK — Mobile API
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS — cho phép mobile app gọi API
# Native mobile requests do not need browser CORS. Separate web clients must be explicitly allowed.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()]

# Logging — show allauth errors in Railway logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'allauth': {'handlers': ['console'], 'level': 'WARNING'},
        'django.request': {'handlers': ['console'], 'level': 'DEBUG'},
        'grading.engine.hi': {'handlers': ['console'], 'level': 'WARNING'},
        'grading': {'handlers': ['console'], 'level': 'INFO'},
    },
}

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Live-only latency controls. Restart backend after changing environment values.
# Immediate rollback: set to 0. Upload/import never opt in.
LIVE_SINGLE_PASS_GRADING = os.environ.get('LIVE_SINGLE_PASS_GRADING', '1') == '1'


# =============================================================================
# PRODUCTION SECURITY (Railway)
# =============================================================================

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    if not os.environ.get('DJANGO_SECRET_KEY'):
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('DJANGO_SECRET_KEY is required when DJANGO_DEBUG=False.')
    SECURE_SSL_REDIRECT = True
    # The local container probes this public text file using HTTP.
    SECURE_REDIRECT_EXEMPT = [r'^ads\.txt$']
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
