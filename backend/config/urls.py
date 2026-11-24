import redis
from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


def health_live(_request):
    """Kubernetes-style liveness probe: confirms the Django process is alive."""
    return JsonResponse({"status": "alive", "env": settings.APP_ENV}, status=200)


def health_ready(_request):
    """Kubernetes-style readiness probe: verifies PostgreSQL and Redis connectivity."""
    db_ok = _check_database()
    redis_ok = _check_redis()
    all_ok = db_ok and redis_ok
    return JsonResponse(
        {
            "status": "ok" if all_ok else "degraded",
            "env": settings.APP_ENV,
            "database": db_ok,
            "redis": redis_ok,
        },
        status=200 if all_ok else 503,
    )


def health_check(_request):
    """Backward-compatible health endpoint verifying database connectivity."""
    db_ok = _check_database()
    return JsonResponse(
        {"status": "ok" if db_ok else "degraded", "env": settings.APP_ENV, "database": db_ok},
        status=200 if db_ok else 503,
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    path("api/v1/health/live/", health_live, name="health-live"),
    path("api/v1/health/ready/", health_ready, name="health-ready"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.fleet.urls")),
    path("api/v1/", include("apps.flights.urls")),
    path("api/v1/", include("apps.bookings.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.integrations.urls")),
]
