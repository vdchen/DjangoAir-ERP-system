import importlib
from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_health_live_and_ready_endpoints(api_client):
    live = api_client.get("/api/v1/health/live/")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    assert live.json()["env"] == "test"

    with patch("config.urls._check_redis", return_value=True):
        ready = api_client.get("/api/v1/health/ready/")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "env": "test", "database": True, "redis": True}

    with patch("config.urls._check_redis", return_value=False):
        degraded = api_client.get("/api/v1/health/ready/")
    assert degraded.status_code == 503
    assert degraded.json()["status"] == "degraded"
    assert degraded.json()["redis"] is False


def test_environment_settings_modules_invariants():
    dev = importlib.import_module("config.settings.dev")
    test = importlib.import_module("config.settings.test")
    staging = importlib.import_module("config.settings.staging")
    prod = importlib.import_module("config.settings.prod")

    assert dev.APP_ENV == "dev"
    assert dev.DEBUG is True

    assert test.APP_ENV == "test"
    assert test.DEBUG is False
    assert test.CELERY_TASK_ALWAYS_EAGER is True

    assert staging.APP_ENV == "staging"
    assert staging.DEBUG is False
    assert "RedisCache" in staging.CACHES["default"]["BACKEND"]
    assert staging.SECURE_HSTS_SECONDS >= 3600

    assert prod.APP_ENV == "prod"
    assert prod.DEBUG is False
    assert "RedisCache" in prod.CACHES["default"]["BACKEND"]
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SECURE_HSTS_SECONDS >= 31536000
    assert prod.X_FRAME_OPTIONS == "DENY"
