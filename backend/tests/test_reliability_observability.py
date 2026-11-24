import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from apps.bookings.models import Booking
from apps.integrations.logging_utils import JsonLogFormatter, request_id_var
from apps.integrations.models import OutboxEvent, OutboxStatus, WebhookSubscription
from apps.integrations.tasks import relay_outbox_event
from apps.payments.models import Payment


@pytest.mark.django_db
def test_idempotency_key_prevents_duplicate_bookings_and_payments(api_client, flight_setup):
    payload = {
        "flight_id": str(flight_setup["flight"].id),
        "seat_type_id": str(flight_setup["eco"].id),
        "contact_email": "idem@example.com",
        "passengers": [
            {"first_name": "Grace", "last_name": "Hopper", "document_number": "IDEM01"}
        ],
    }

    # 1. First request creates booking
    r1 = api_client.post(
        "/api/v1/bookings/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="booking-key-001",
    )
    assert r1.status_code == 201
    assert r1["X-Idempotent-Replayed"] == "false"

    # 2. Identical retry replays exact response without creating a second booking
    r2 = api_client.post(
        "/api/v1/bookings/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="booking-key-001",
    )
    assert r2.status_code == 201
    assert r2["X-Idempotent-Replayed"] == "true"
    assert r2.data["booking_reference"] == r1.data["booking_reference"]
    assert Booking.objects.filter(contact_email="idem@example.com").count() == 1

    # 3. Same key with a mutated payload returns 409 Conflict
    mutated = dict(payload, contact_email="other@example.com")
    r3 = api_client.post(
        "/api/v1/bookings/",
        mutated,
        format="json",
        HTTP_IDEMPOTENCY_KEY="booking-key-001",
    )
    assert r3.status_code == 409

    # 4. Idempotent payment charge prevents double-charging on retry
    ref = r1.data["booking_reference"]
    pay_body = {
        "booking_reference": ref,
        "payment_method": "CARD",
        "card_number": "4242424242424242",
        "exp_month": 12,
        "exp_year": 2030,
        "cvv": "424",
    }
    p1 = api_client.post(
        "/api/v1/payments/charge/",
        pay_body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="pay-key-001",
    )
    assert p1.status_code == 200
    assert p1["X-Idempotent-Replayed"] == "false"

    p2 = api_client.post(
        "/api/v1/payments/charge/",
        pay_body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="pay-key-001",
    )
    assert p2.status_code == 200
    assert p2["X-Idempotent-Replayed"] == "true"
    assert p2.data["payment"]["transaction_id"] == p1.data["payment"]["transaction_id"]
    assert Payment.objects.filter(booking__booking_reference=ref).count() == 1


@pytest.mark.django_db
def test_transactional_outbox_dead_letter_and_supervisor_replay(auth_client, users):
    WebhookSubscription.objects.create(
        name="Flaky Partner",
        target_url="http://partner.local/hook",
        secret="secret-123",
        events=["booking.confirmed"],
        is_active=True,
    )
    outbox = OutboxEvent.objects.create(
        event_type="booking.confirmed",
        payload={"event": "booking.confirmed", "data": {"booking_reference": "BK-DLQ1"}},
        status=OutboxStatus.PENDING,
        max_attempts=2,
    )

    fail_resp = MagicMock(status_code=500, text="upstream down")
    with patch("apps.integrations.tasks.requests.post", return_value=fail_resp):
        relay_outbox_event(str(outbox.id))
        outbox.refresh_from_db()
        assert outbox.status == OutboxStatus.PENDING
        assert outbox.attempts == 1

        relay_outbox_event(str(outbox.id))
        outbox.refresh_from_db()
        assert outbox.status == OutboxStatus.DEAD_LETTER
        assert outbox.attempts == 2

    # Supervisor replays dead-lettered event once partner recovers
    sup_client = auth_client(users["supervisor"])
    ok_resp = MagicMock(status_code=200, text='{"received": true}')
    with patch("apps.integrations.tasks.requests.post", return_value=ok_resp):
        replay = sup_client.post(f"/api/v1/integrations/outbox/{outbox.id}/replay/")
    assert replay.status_code == 200
    assert replay.data["outbox"]["status"] == OutboxStatus.PUBLISHED


@pytest.mark.django_db
def test_request_id_correlation_prometheus_metrics_and_json_logging(api_client):
    resp = api_client.get("/api/v1/health/live/", HTTP_X_REQUEST_ID="trace-abc-123")
    assert resp.status_code == 200
    assert resp["X-Request-ID"] == "trace-abc-123"

    auto_resp = api_client.get("/api/v1/health/live/")
    assert auto_resp["X-Request-ID"]

    metrics = api_client.get("/api/v1/metrics/")
    assert metrics.status_code == 200
    body = metrics.content.decode("utf-8")
    assert "djangoair_http_requests_total" in body
    assert "djangoair_http_request_duration_seconds" in body

    token = request_id_var.set("req-json-999")
    try:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="djangoair.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="structured log check",
            args=(),
            exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["request_id"] == "req-json-999"
        assert parsed["message"] == "structured log check"
        assert parsed["level"] == "INFO"
    finally:
        request_id_var.reset(token)
