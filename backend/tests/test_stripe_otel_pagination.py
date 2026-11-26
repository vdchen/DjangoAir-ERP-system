import json
import logging
from decimal import Decimal
from unittest.mock import patch

import pytest
import stripe
from django.test import override_settings

from apps.bookings.models import BookingStatus, TicketStatus
from apps.integrations.logging_utils import JsonLogFormatter
from apps.payments.gateway import (
    EmulatedGatewayProvider,
    StripeGatewayProvider,
    get_payment_provider,
)
from apps.payments.models import Payment, PaymentStatus
from config.telemetry import configure_telemetry, get_current_trace_context


@pytest.mark.django_db
def test_payment_provider_factory_and_stripe_gateway_outcomes():
    with override_settings(PAYMENT_PROVIDER="emulated"):
        assert isinstance(get_payment_provider(), EmulatedGatewayProvider)

    with override_settings(PAYMENT_PROVIDER="stripe", STRIPE_SECRET_KEY=""):
        provider = get_payment_provider()
        assert isinstance(provider, StripeGatewayProvider)
        missing_key_res = provider.charge(
            amount=Decimal("120.00"),
            card_number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            cvv="424",
        )
        assert missing_key_res.success is False
        assert missing_key_res.provider == "stripe"
        assert "STRIPE_SECRET_KEY" in missing_key_res.failure_reason

    stripe_provider = StripeGatewayProvider(api_key="sk_test_fake_key_12345")

    # 1. Successful PaymentIntent with pm_ token
    with patch("stripe.PaymentIntent.create", return_value={"id": "pi_test_ok", "status": "succeeded"}) as mock_pi:
        ok = stripe_provider.charge(
            amount=Decimal("250.50"),
            card_number="pm_card_visa",
            exp_month=12,
            exp_year=2030,
            cvv="424",
            cardholder_name="Alice",
            idempotency_key="idem-stripe-1",
        )
    assert ok.success is True
    assert ok.transaction_id == "pi_test_ok"
    assert ok.provider == "stripe"
    assert mock_pi.call_args.kwargs["amount"] == 25050
    assert mock_pi.call_args.kwargs["idempotency_key"] == "idem-stripe-1"

    # 2. CardError declined
    card_err = stripe.CardError(message="Your card was declined.", param="card", code="card_declined")
    with patch("stripe.PaymentIntent.create", side_effect=card_err):
        declined = stripe_provider.charge(
            amount=Decimal("99.00"),
            card_number="4000000000000002",
            exp_month=12,
            exp_year=2030,
            cvv="424",
        )
    assert declined.success is False
    assert declined.card_last4 == "0002"
    assert "declined" in declined.failure_reason.lower()

    # 3. Generic StripeError
    with patch("stripe.PaymentIntent.create", side_effect=stripe.APIConnectionError("network timeout")):
        api_err = stripe_provider.charge(
            amount=Decimal("99.00"),
            card_number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            cvv="424",
        )
    assert api_err.success is False
    assert "Stripe gateway error" in api_err.failure_reason

    # 4. Non-succeeded PaymentIntent status (e.g. requires_action)
    with patch("stripe.PaymentIntent.create", return_value={"id": "pi_test_pending", "status": "requires_action"}):
        pending = stripe_provider.charge(
            amount=Decimal("99.00"),
            card_number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            cvv="424",
        )
    assert pending.success is False
    assert "requires_action" in pending.failure_reason


@pytest.mark.django_db
def test_stripe_webhook_signature_validation_and_idempotent_reconciliation(api_client, flight_setup):
    # Create RESERVED booking with a PENDING Stripe payment
    b_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight_setup["flight"].id),
            "seat_type_id": str(flight_setup["eco"].id),
            "contact_email": "stripe.hook@example.com",
            "passengers": [{"first_name": "Sam", "last_name": "Stripe", "document_number": "ST123"}],
        },
        format="json",
    )
    assert b_resp.status_code == 201
    payment = Payment.objects.create(
        booking_id=b_resp.data["id"],
        transaction_id="pi_webhook_reconcile_1",
        provider="stripe",
        amount=Decimal(b_resp.data["total_amount"]),
        status=PaymentStatus.PENDING,
        card_last4="4242",
    )

    # Unconfigured secret -> 503
    with override_settings(STRIPE_WEBHOOK_SECRET=""):
        r503 = api_client.post("/api/v1/payments/webhooks/stripe/", data={}, format="json")
    assert r503.status_code == 503

    with override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret"):
        # Missing signature -> 400
        assert api_client.post("/api/v1/payments/webhooks/stripe/", data={}, format="json").status_code == 400

        # Invalid signature -> 400
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad sig", "sig"),
        ):
            r_bad_sig = api_client.post(
                "/api/v1/payments/webhooks/stripe/",
                data={"id": "evt_1"},
                format="json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=invalid",
            )
        assert r_bad_sig.status_code == 400

        # Valid payment_intent.succeeded -> marks Payment SUCCEEDED & Booking/Tickets PAID
        succeeded_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_webhook_reconcile_1"}},
        }
        with patch("stripe.Webhook.construct_event", return_value=succeeded_event):
            r_ok = api_client.post(
                "/api/v1/payments/webhooks/stripe/",
                data=succeeded_event,
                format="json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        assert r_ok.status_code == 200
        assert r_ok.data["handled"] is True
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.booking.status == BookingStatus.PAID
        assert payment.booking.tickets.filter(status=TicketStatus.PAID).count() == 1

        # Idempotent replay of the same succeeded webhook
        with patch("stripe.Webhook.construct_event", return_value=succeeded_event):
            r_dup = api_client.post(
                "/api/v1/payments/webhooks/stripe/",
                data=succeeded_event,
                format="json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        assert r_dup.status_code == 200
        assert r_dup.data["idempotent"] is True

        # Failed payment_intent webhook on a separate PENDING payment
        payment_fail = Payment.objects.create(
            booking_id=b_resp.data["id"],
            transaction_id="pi_webhook_fail_1",
            provider="stripe",
            amount=Decimal("50.00"),
            status=PaymentStatus.PENDING,
            card_last4="0002",
        )
        failed_event = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_webhook_fail_1",
                    "last_payment_error": {"message": "Insufficient funds"},
                }
            },
        }
        with patch("stripe.Webhook.construct_event", return_value=failed_event):
            r_fail = api_client.post(
                "/api/v1/payments/webhooks/stripe/",
                data=failed_event,
                format="json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        assert r_fail.status_code == 200
        payment_fail.refresh_from_db()
        assert payment_fail.status == PaymentStatus.FAILED
        assert "Insufficient funds" in payment_fail.failure_reason


@pytest.mark.django_db
def test_optional_pagination_preserves_arrays_and_supports_page_envelope(
    api_client, auth_client, users, flight_setup
):
    # Unpaginated default returns a plain list (backward-compatible)
    plain = api_client.get("/api/v1/fleet/airports/")
    assert plain.status_code == 200
    assert isinstance(plain.data, list)
    assert len(plain.data) >= 2

    # Paginated request with ?page=1&page_size=1 returns standard DRF pagination envelope
    paged = api_client.get("/api/v1/fleet/airports/?page=1&page_size=1")
    assert paged.status_code == 200
    assert paged.data["count"] >= 2
    assert len(paged.data["results"]) == 1
    assert paged.data["next"] is not None

    # Paginated flight search and staff flights
    search_paged = api_client.get("/api/v1/flights/search/?destination=LHR&page=1&page_size=1")
    assert search_paged.status_code == 200
    assert search_paged.data["count"] >= 1
    assert len(search_paged.data["results"]) == 1

    sup = auth_client(users["supervisor"])
    staff_paged = sup.get("/api/v1/staff/flights/?page=1&page_size=1")
    assert staff_paged.status_code == 200
    assert staff_paged.data["count"] >= 1
    assert len(staff_paged.data["results"]) == 1


@pytest.mark.django_db
def test_opentelemetry_trace_context_in_json_logs_and_response_header(api_client):
    assert configure_telemetry("djangoair-test", force=True) is True

    from opentelemetry import trace

    tracer = trace.get_tracer("djangoair.tests")
    with tracer.start_as_current_span("test-flight-search") as span:
        trace_id, span_id = get_current_trace_context()
        assert len(trace_id) == 32
        assert len(span_id) == 16
        assert trace_id == f"{span.get_span_context().trace_id:032x}"

        # Structured JSON log carries active trace_id and span_id
        formatter = JsonLogFormatter()
        rec = logging.LogRecord(
            name="djangoair.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="traced log event",
            args=(),
            exc_info=None,
        )
        parsed = json.loads(formatter.format(rec))
        assert parsed["trace_id"] == trace_id
        assert parsed["span_id"] == span_id

        # Middleware exposes active trace_id in X-Trace-ID response header
        resp = api_client.get("/api/v1/health/live/")
        assert resp.status_code == 200
        assert resp["X-Trace-ID"] == trace_id
