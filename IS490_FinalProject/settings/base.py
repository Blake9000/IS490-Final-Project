import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / '.env')


def get_env(name, default='', required=False):
    value = os.environ.get(name, default)

    if required and not value:
        raise RuntimeError(f'Missing required environment variable: {name}')

    return value


def get_env_int(name, default):
    value = os.environ.get(name, default)

    try:
        return int(value)
    except ValueError:
        return default


SECRET_KEY = get_env('DJANGO_SECRET_KEY', required=True)

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'resume_fixer.apps.ResumeFixerConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'IS490_FinalProject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
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

WSGI_APPLICATION = 'IS490_FinalProject.wsgi.application'
ASGI_APPLICATION = 'IS490_FinalProject.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 30,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

ADZUNA_APP_ID = get_env('ADZUNA_APP_ID')
ADZUNA_APP_KEY = get_env('ADZUNA_APP_KEY')
ADZUNA_COUNTRY = get_env('ADZUNA_COUNTRY', 'us')
ADZUNA_DEFAULT_QUERY = get_env('ADZUNA_DEFAULT_QUERY', 'software engineer')
ADZUNA_DEFAULT_LOCATION = get_env('ADZUNA_DEFAULT_LOCATION', '')
ADZUNA_RESULTS_PER_PAGE = get_env_int('ADZUNA_RESULTS_PER_PAGE', 50)

USAJOBS_API_KEY = get_env('USAJOBS_API_KEY')
USAJOBS_USER_AGENT = get_env('USAJOBS_USER_AGENT')
USAJOBS_DEFAULT_KEYWORD = get_env('USAJOBS_DEFAULT_KEYWORD', 'information technology')
USAJOBS_DEFAULT_LOCATION = get_env('USAJOBS_DEFAULT_LOCATION', '')
USAJOBS_RESULTS_PER_PAGE = get_env_int('USAJOBS_RESULTS_PER_PAGE', 50)

OPENAI_API_KEY = get_env('OPENAI_API_KEY')
OPENAI_MODEL = get_env('OPENAI_MODEL', 'gpt-4o-mini')

FILE_UPLOAD_MAX_MEMORY_SIZE = get_env_int('DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE', 10485760)
DATA_UPLOAD_MAX_MEMORY_SIZE = get_env_int('DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE', 10485760)