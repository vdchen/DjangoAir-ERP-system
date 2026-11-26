import os

from django.core.wsgi import get_wsgi_application

from config.telemetry import configure_telemetry

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
configure_telemetry("djangoair-backend", instrument_django=True)

application = get_wsgi_application()
