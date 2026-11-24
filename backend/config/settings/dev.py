import os

from .base import *  # noqa: F401, F403

APP_ENV = "dev"
DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
