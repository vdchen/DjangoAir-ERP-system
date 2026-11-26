import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_ENV = os.environ.get("APP_ENV", "dev")
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "djangoair-insecure-dev-secret-key-min-32-bytes-rfc7518"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,nginx,backend").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    # DjangoAir domain apps
    "apps.accounts",
    "apps.fleet",
    "apps.flights",
    "apps.bookings",
    "apps.payments",
    "apps.notifications",
    "apps.integrations",
    "apps.copilot",
]

MIDDLEWARE = [
    "apps.integrations.middleware.RequestCorrelationAndMetricsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "djangoair"),
        "USER": os.environ.get("POSTGRES_USER", "djangoair"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "djangoair_secret"),
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "djangoair-default",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "DjangoAir ERP API",
    "DESCRIPTION": "Airline Management ERP System REST API for Customer Booking, Personal Cabinet, Payments, and Role-Governed Staff Operations.",
    "VERSION": "1.0.0",
}

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Redis & Celery
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
REDIS_EVENTS_CHANNEL = os.environ.get("REDIS_EVENTS_CHANNEL", "djangoair:events")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Email
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "mailpit")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "tickets@djangoair.local")

# Integrations / Webhooks
WEBHOOK_DEFAULT_SECRET = os.environ.get(
    "WEBHOOK_DEFAULT_SECRET", "djangoair-webhook-dev-secret"
)
WEBHOOK_MOCK_URL = os.environ.get(
    "WEBHOOK_MOCK_URL", "http://webhook_mock:5002/mock-webhook/events"
)
WEBHOOK_TIMEOUT_SECONDS = int(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "5"))

# Google OAuth2 Social Login (Optional #2)
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_DEV_MOCK_ENABLED = os.environ.get("GOOGLE_OAUTH_DEV_MOCK_ENABLED", "0") == "1"

# Pluggable Payment Gateway Provider ("emulated" | "stripe")
PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "emulated").strip().lower()
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# OpenTelemetry Distributed Tracing (OTLP HTTP)
OTEL_TRACES_ENABLED = os.environ.get("OTEL_TRACES_ENABLED", "0") == "1"
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "djangoair-backend")

# AI Disruption & Rebooking Copilot ("deterministic" | "openai" | "gemini")
AI_COPILOT_PROVIDER = os.environ.get("AI_COPILOT_PROVIDER", "deterministic").strip().lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_COPILOT_MODEL = os.environ.get("OPENAI_COPILOT_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_COPILOT_MODEL = os.environ.get("GEMINI_COPILOT_MODEL", "gemini-2.0-flash")

# Structured Logging (set LOG_FORMAT=json for single-line JSON logs with request_id)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = os.environ.get("LOG_FORMAT", "standard")
LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        },
        "json": {
            "()": "apps.integrations.logging_utils.JsonLogFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}
