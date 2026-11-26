import os

from .base import *  # noqa: F401, F403

APP_ENV = "dev"
DEBUG = True
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
GOOGLE_OAUTH_DEV_MOCK_ENABLED = os.environ.get("GOOGLE_OAUTH_DEV_MOCK_ENABLED", "1") == "1"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get(
            "REDIS_CACHE_URL", os.environ.get("REDIS_URL", "redis://redis:6379/2")
        ),
    }
}
