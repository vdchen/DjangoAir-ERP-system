import os

from celery import Celery
from celery.signals import worker_process_init

from config.telemetry import configure_telemetry

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("djangoair")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_process_init.connect(weak=False)
def _init_celery_telemetry(**_kwargs):
    configure_telemetry("djangoair-celery", instrument_celery=True)
