import os

from .base import *  # noqa: F401, F403

APP_ENV = "prod"
DEBUG = False

# Production Redis cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_CACHE_URL", "redis://redis:6379/2"),
    }
}

# Strict transport and cookie security behind TLS-terminating Nginx/Ingress
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIES", "1") == "1"
CSRF_COOKIE_SECURE = os.environ.get("SECURE_COOKIES", "1") == "1"
X_FRAME_OPTIONS = "DENY"
GOOGLE_OAUTH_DEV_MOCK_ENABLED = False
