from .base import *


DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}