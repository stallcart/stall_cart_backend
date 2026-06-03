# stall_cart/settings.py
import os
from pathlib import Path
import environ
import firebase_admin
from firebase_admin import credentials

# ═══════════════════════════════════════════════════════════
# BASE DIRECTORY & ENV SETUP
# ═══════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-dev-fallback-key-change-in-production'),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ═══════════════════════════════════════════════════════════
# CORE DJANGO SETTINGS
# ═══════════════════════════════════════════════════════════
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'colorfield',  # Required dependency for admin_interface
    'admin_interface',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    # Custom apps
    'accounts',
    'shop',
    'orders',
    'delivery',
    'blog',
    'common',
    'items',
    # Firebase/FCM
    'fcm_django',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'stall_cart.middleware.CurrentUserMiddleware',  # Custom middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stall_cart.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'common.context_processors.site_settings',
            'common.context_processors.cart_count',
            'common.context_processors.cart_and_wishlist',
            'common.context_processors.firebase_config'
        ],
    },
}]
TEMPLATES[0]['OPTIONS']['builtins'] = [
    'common.templatetags.custom_filters',
]

WSGI_APPLICATION = 'stall_cart.wsgi.application'

# ═══════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════
DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE'),
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

# Use SQLite for running tests to bypass MySQL permissions and speed up testing
import sys
if 'test' in sys.argv or 'test_coverage' in sys.argv:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# ═══════════════════════════════════════════════════════════
# AUTH & USER SETTINGS
# ═══════════════════════════════════════════════════════════
AUTH_USER_MODEL = 'accounts.User'

# ═══════════════════════════════════════════════════════════
# INTERNATIONALIZATION
# ═══════════════════════════════════════════════════════════
LANGUAGE_CODE = 'en-in'
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True
USE_I18N = True
USE_L10N = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ═══════════════════════════════════════════════════════════
# STATIC & MEDIA FILES
# ═══════════════════════════════════════════════════════════
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ═══════════════════════════════════════════════════════════
# PAYMENT: RAZORPAY
# ═══════════════════════════════════════════════════════════
RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID', default='rzp_test_XXX')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET', default='XXX')
RAZORPAY_WEBHOOK_SECRET = env('RAZORPAY_WEBHOOK_SECRET', default='XXX')

# ═══════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'error.log',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ═══════════════════════════════════════════════════════════
# 📧 EMAIL CONFIGURATION (Console for Dev / SMTP for Prod)
# ═══════════════════════════════════════════════════════════
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp-relay.brevo.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
BREVO_API_KEY = env('BREVO_API_KEY', default='')
TWOFACTOR_API_KEY = env('TWOFACTOR_API_KEY', default='6f037587-5e8b-11f1-8352-0200cd936042')
TWOFACTOR_TEMPLATE_NAME = env('TWOFACTOR_TEMPLATE_NAME', default='StallCart OTP')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='StallCart <noreply@stallcart.in>')

# Admin error notifications
ADMINS = [('Admin', 'stallcart.in@gmail.com')]
MANAGERS = ADMINS

# ═══════════════════════════════════════════════════════════
# SHIPROCKET (Optional)
# ═══════════════════════════════════════════════════════════
SHIPROCKET_EMAIL = env('SHIPROCKET_EMAIL', default='')
SHIPROCKET_PASSWORD = env('SHIPROCKET_PASSWORD', default='')

# ═══════════════════════════════════════════════════════════
# 🔔 FIREBASE / FCM CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Firebase Admin SDK credentials path (relative to project root)
FIREBASE_CREDENTIALS_PATH = env('FIREBASE_CREDENTIALS_PATH', default='firebase_service_account.json')

# VAPID Public Key for Web Push Notifications (required for frontend)
FIREBASE_VAPID_PUBLIC_KEY = env('FIREBASE_VAPID_PUBLIC_KEY', default='')

# Firebase Web Config values (SAFE to expose in frontend JavaScript)
FIREBASE_API_KEY = env('FIREBASE_API_KEY', default='')
FIREBASE_AUTH_DOMAIN = env('FIREBASE_AUTH_DOMAIN', default='')
FIREBASE_PROJECT_ID = env('FIREBASE_PROJECT_ID', default='')
FIREBASE_STORAGE_BUCKET = env('FIREBASE_STORAGE_BUCKET', default='')
FIREBASE_MESSAGING_SENDER_ID = env('FIREBASE_MESSAGING_SENDER_ID', default='')
FIREBASE_APP_ID = env('FIREBASE_APP_ID', default='')
FIREBASE_MEASUREMENT_ID = env('FIREBASE_MEASUREMENT_ID', default='')

# Build a config dict for easy frontend template injection
FIREBASE_FRONTEND_CONFIG = {
    'apiKey': FIREBASE_API_KEY,
    'authDomain': FIREBASE_AUTH_DOMAIN,
    'projectId': FIREBASE_PROJECT_ID,
    'storageBucket': FIREBASE_STORAGE_BUCKET,
    'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID,
    'appId': FIREBASE_APP_ID,
    'measurementId': FIREBASE_MEASUREMENT_ID,
} if FIREBASE_PROJECT_ID else None

# Initialize Firebase Admin SDK (only if credentials file exists)
if Path(FIREBASE_CREDENTIALS_PATH).exists():
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {
            'messagingSenderId': FIREBASE_MESSAGING_SENDER_ID
        })
        print(f"✅ Firebase Admin SDK initialized for project: {FIREBASE_PROJECT_ID}")
    except Exception as e:
        print(f"⚠️ Firebase init warning: {e}")
else:
    print(f"⚠️ Firebase credentials file not found at '{FIREBASE_CREDENTIALS_PATH}' — push notifications disabled")

# fcm-django configuration
FCM_DJANGO_SETTINGS = {
    "DEFAULT_FIREBASE_APP": firebase_admin.get_app() if firebase_admin._apps else None,
    "APP_VERBOSE_NAME": "StallCart Notifications",
    "ONE_DEVICE_PER_USER": False,  # Allow multiple devices per user
    "DELETE_INACTIVE_DEVICES": True,  # Auto-remove failed tokens
    "UPDATE_ON_DUPLICATE_REG_ID": True,  # Update existing token if duplicate
}