import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-dev-fallback-key-change-in-production'),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'colorfield',  # Required dependency
    'admin_interface',    'django.contrib.admin',
    'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'accounts', 'shop', 'orders', 'delivery', 'blog','common' ,'items'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'stall_cart.middleware.CurrentUserMiddleware',  #custom
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stall_cart.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'common.context_processors.site_settings',  # Add this line

    ]},
}]
WSGI_APPLICATION = 'stall_cart.wsgi.application'

env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-fallback-key'),
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))  # Reads .env safely

# ... rest of your settings (INSTALLED_APPS, MIDDLEWARE, etc.) ...

#Database Configuration (NO PASSWORDS VISIBLE)
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
AUTH_USER_MODEL = 'accounts.User'
LANGUAGE_CODE = 'en-in'
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

