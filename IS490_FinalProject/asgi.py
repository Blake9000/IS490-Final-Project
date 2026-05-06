import os

from django.core.asgi import get_asgi_application


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IS490_FinalProject.settings.production')

application = get_asgi_application()