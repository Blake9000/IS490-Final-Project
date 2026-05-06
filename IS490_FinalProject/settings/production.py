from .base import *


DEBUG = False

ALLOWED_HOSTS = [
    'resume.blake4it.com',
    'localhost',
    '127.0.0.1',
]

CSRF_TRUSTED_ORIGINS = [
    'https://resume.blake4it.com',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

STATIC_ROOT = '/var/www/finalaiproject/static'
MEDIA_ROOT = '/var/www/finalaiproject/media'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/var/www/finalaiproject/app/db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}