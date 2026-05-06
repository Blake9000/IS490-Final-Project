import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure--2y$z%q-0=&mx^%)a$*v*!4$)_!%k=pjtc%0#fnl6_et##a2wh'

DEBUG = True

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

WSGI_APPLICATION = 'IS490_FinalProject.wsgi.application'

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
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

ADZUNA_APP_ID = os.environ.get('ADZUNA_APP_ID', '01d76713')
ADZUNA_APP_KEY = os.environ.get('ADZUNA_APP_KEY', 'fb2fc02d146f46ba203e273e3974c8b7')
ADZUNA_COUNTRY = os.environ.get('ADZUNA_COUNTRY', 'us')
ADZUNA_DEFAULT_QUERY = os.environ.get('ADZUNA_DEFAULT_QUERY', 'software engineer')
ADZUNA_DEFAULT_LOCATION = os.environ.get('ADZUNA_DEFAULT_LOCATION', '')
ADZUNA_RESULTS_PER_PAGE = int(os.environ.get('ADZUNA_RESULTS_PER_PAGE', '50'))

USAJOBS_API_KEY = os.environ.get('USAJOBS_API_KEY', 'fC5Uu55+zXXR3n46JpT6OFMPEd7zR3BAI3knSa1nuq4=')
USAJOBS_USER_AGENT = os.environ.get('USAJOBS_USER_AGENT', 'tchan34@illinois.edu')
USAJOBS_DEFAULT_KEYWORD = os.environ.get('USAJOBS_DEFAULT_KEYWORD', 'information technology')
USAJOBS_DEFAULT_LOCATION = os.environ.get('USAJOBS_DEFAULT_LOCATION', '')
USAJOBS_RESULTS_PER_PAGE = int(os.environ.get('USAJOBS_RESULTS_PER_PAGE', '50'))
