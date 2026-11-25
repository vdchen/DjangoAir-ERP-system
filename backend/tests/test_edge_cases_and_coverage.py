from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.bookings.models import Discount, DiscountType, TicketStatus
from apps.flights.models import Flight, FlightStatus
from apps.integrations.models import OutboxEvent, OutboxStatus, WebhookDelivery, WebhookSubscription
from apps.integrations.tasks import dispatch_webhook_event
from apps.notifications.models import EmailLog
from apps.notifications.tasks import (
    send_booking_confirmation_email,
    send_flight_cancellation_email,
)


@pytest.mark.django_db
def test_customer_registration_and_auth_edge_cases(api_client, users):
    # 1. Self-registration creates customer + profile + returns JWT
    reg = api_client.post(
        "/api/v1/auth/register/",
        {
            "email": "new.cust@example.com",
            "password": "Password123!",
            "first_name": "Nina",
            "last_name": "Simone",
            "phone": "+15551234",
            "passport_number": "US55599",
        },
        format="json",
    )
    assert reg.status_code == 201
    assert reg.data["access"]
    assert CustomerProfile.objects.filter(
        user__email="new.cust@example.com", passport_number="US55599"
    ).exists()

    # 2. Invalid credentials rejected
    bad = api_client.post(
        "/api/v1/auth/login/",
        {"email": "new.cust@example.com", "password": "WrongPassword"},
        format="json",
    )
    assert bad.status_code == 400

    # 3. Disabled account rejected on login
    user = User.objects.get(email="new.cust@example.com")
    user.is_active = False
    user.save(update_fields=["is_active"])
    disabled_resp = api_client.post(
        "/api/v1/auth/login/",
        {"email": "new.cust@example.com", "password": "Password123!"},
        format="json",
    )
    assert disabled_resp.status_code == 400


@pytest.mark.django_db
def test_google_oauth_negative_and_error_paths(api_client, users):
    # Missing both id_token and dev_mock
    missing = api_client.post("/api/v1/auth/google/", {}, format="json")
    assert missing.status_code == 400

    # Invalid email in dev_mock
    bad_email = api_client.post(
        "/api/v1/auth/google/", {"dev_mock": True, "email": ""}, format="json"
    )
    assert bad_email.status_code == 400

    # Missing GOOGLE_OAUTH_CLIENT_ID for real id_token verification
    with override_settings(GOOGLE_OAUTH_CLIENT_ID=""):
        no_client = api_client.post(
            "/api/v1/auth/google/", {"id_token": "some-jwt"}, format="json"
        )
        assert no_client.status_code == 400

    # Real tokeninfo network error, HTTP 400, and unverified email
    with override_settings(GOOGLE_OAUTH_CLIENT_ID="valid-client-id"):
        with patch(
            "apps.accounts.oauth.requests.get", side_effect=requests.RequestException("timeout")
        ):
            net_err = api_client.post(
                "/api/v1/auth/google/", {"id_token": "some-jwt"}, format="json"
            )
            assert net_err.status_code == 401

        with patch(
            "apps.accounts.oauth.requests.get", return_value=MagicMock(status_code=400)
        ):
            bad_tok = api_client.post(
                "/api/v1/auth/google/", {"id_token": "expired-jwt"}, format="json"
            )
            assert bad_tok.status_code == 401

        unverified_resp = MagicMock(status_code=200)
        unverified_resp.json.return_value = {
            "sub": "uid-1",
            "aud": "valid-client-id",
            "email": "unverified@gmail.com",
            "email_verified": "false",
        }
        with patch("apps.accounts.oauth.requests.get", return_value=unverified_resp):
            unv = api_client.post(
                "/api/v1/auth/google/", {"id_token": "unverified-jwt"}, format="json"
            )
            assert unv.status_code == 401


@pytest.mark.django_db
def test_flight_search_no_n_plus_1_and_validation_guards(
    api_client, auth_client, users, flight_setup, django_assert_num_queries
):
    # Create 5 additional scheduled flights on the same route/date to verify constant SQL count
    base_dep = flight_setup["flight"].departure_time
    for i in range(5):
        Flight.objects.create(
            flight_number=f"DA80{i}",
            origin=flight_setup["jfk"],
            destination=flight_setup["lhr"],
            airplane=flight_setup["plane"],
            departure_time=base_dep + timedelta(minutes=30 * (i + 1)),
            arrival_time=base_dep + timedelta(hours=7, minutes=30 * (i + 1)),
            base_price=Decimal("210.00"),
            gate=f"G{i}",
            status=FlightStatus.SCHEDULED,
        )

    date_str = base_dep.strftime("%Y-%m-%d")
    # Constant O(1) query count regardless of 6 matching flights (no per-flight N+1!)
    with django_assert_num_queries(6):
        search = api_client.get(
            f"/api/v1/flights/search/?destination={flight_setup['lhr'].id}&date={date_str}&passengers=1"
        )
    assert search.status_code == 200
    assert len(search.data) == 6

    # Supervisor flight creation validation (same origin/dest and inverted times)
    sup = auth_client(users["supervisor"])
    same_ap = sup.post(
        "/api/v1/staff/flights/",
        {
            "flight_number": "DAB1",
            "origin": str(flight_setup["jfk"].id),
            "destination": str(flight_setup["jfk"].id),
            "airplane": str(flight_setup["plane"].id),
            "departure_time": base_dep.isoformat(),
            "arrival_time": (base_dep + timedelta(hours=2)).isoformat(),
            "base_price": "150.00",
        },
        format="json",
    )
    assert same_ap.status_code == 400

    bad_times = sup.post(
        "/api/v1/staff/flights/",
        {
            "flight_number": "DAB2",
            "origin": str(flight_setup["jfk"].id),
            "destination": str(flight_setup["lhr"].id),
            "airplane": str(flight_setup["plane"].id),
            "departure_time": (base_dep + timedelta(hours=4)).isoformat(),
            "arrival_time": base_dep.isoformat(),
            "base_price": "150.00",
        },
        format="json",
    )
    assert bad_times.status_code == 400

    # Cancelling an already-cancelled flight returns 400
    fid = flight_setup["flight"].id
    assert sup.post(f"/api/v1/staff/flights/{fid}/cancel/").status_code == 200
    assert sup.post(f"/api/v1/staff/flights/{fid}/cancel/").status_code == 400


@pytest.mark.django_db
def test_booking_payment_checkin_gate_negative_guards(api_client, auth_client, users, flight_setup):
    flight = flight_setup["flight"]
    eco = flight_setup["eco"]

    # Expired & nonexistent discount validation
    Discount.objects.create(
        code="EXPIRED50",
        discount_type=DiscountType.FIXED,
        value=Decimal("50.00"),
        valid_from=timezone.now() - timedelta(days=10),
        valid_until=timezone.now() - timedelta(days=1),
        is_active=True,
    )
    assert (
        api_client.post(
            "/api/v1/bookings/validate-discount/",
            {"code": "NOPE", "subtotal": "200.00"},
            format="json",
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/bookings/validate-discount/",
            {"code": "EXPIRED50", "subtotal": "200.00"},
            format="json",
        ).status_code
        == 400
    )

    # Empty passengers rejected
    assert (
        api_client.post(
            "/api/v1/bookings/",
            {
                "flight_id": str(flight.id),
                "seat_type_id": str(eco.id),
                "contact_email": users["customer"].email,
                "passengers": [],
            },
            format="json",
        ).status_code
        == 400
    )

    # Create valid booking and verify detail endpoint + gateway validation failures
    b_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(eco.id),
            "contact_email": users["customer"].email,
            "passengers": [
                {"first_name": "Edge", "last_name": "Case", "document_number": "EDG1"}
            ],
        },
        format="json",
    )
    assert b_resp.status_code == 201
    ref = b_resp.data["booking_reference"]
    ticket_code = b_resp.data["tickets"][0]["ticket_code"]

    detail = api_client.get(f"/api/v1/bookings/{ref}/")
    assert detail.status_code == 200
    assert detail.data["booking_reference"] == ref

    # Payment gateway edge cases: short card, expired year, bad CVV, insufficient funds (9995)
    for bad_card in [
        {"card_number": "1234", "exp_month": 12, "exp_year": 2030, "cvv": "123"},
        {"card_number": "4242424242424242", "exp_month": 12, "exp_year": 2020, "cvv": "123"},
        {"card_number": "4242424242424242", "exp_month": 12, "exp_year": 2030, "cvv": "ab"},
        {"card_number": "4000000000009995", "exp_month": 12, "exp_year": 2030, "cvv": "123"},
    ]:
        r = api_client.post(
            "/api/v1/payments/charge/",
            {"booking_reference": ref, "payment_method": "CARD", **bad_card},
            format="json",
        )
        assert r.status_code == 402

    # Insufficient balance payment rejected
    CustomerProfile.objects.filter(user=users["customer"]).update(balance=Decimal("10.00"))
    bal_fail = api_client.post(
        "/api/v1/payments/charge/",
        {"booking_reference": ref, "payment_method": "BALANCE"},
        format="json",
    )
    assert bal_fail.status_code == 402

    # Pay successfully, then duplicate non-idempotent charge rejected with 400
    paid = api_client.post(
        "/api/v1/payments/charge/",
        {
            "booking_reference": ref,
            "payment_method": "CARD",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "424",
        },
        format="json",
    )
    assert paid.status_code == 200
    assert (
        api_client.post(
            "/api/v1/payments/charge/",
            {
                "booking_reference": ref,
                "payment_method": "CARD",
                "card_number": "4242424242424242",
                "exp_month": 12,
                "exp_year": 2030,
                "cvv": "424",
            },
            format="json",
        ).status_code
        == 400
    )

    # Non-owner cannot online check in; staff ticket search & detail work
    gate_client = auth_client(users["gate"])
    assert gate_client.post(f"/api/v1/cabinet/tickets/{ticket_code}/check-in/").status_code == 400
    assert len(gate_client.get(f"/api/v1/staff/tickets/?q={ticket_code}").data) == 1
    assert gate_client.get(f"/api/v1/staff/tickets/{ticket_code}/").status_code == 200

    # Check-in Manager rejects negative luggage fee, accepts valid check-in, Gate Manager rejects double boarding
    ci_client = auth_client(users["checkin"])
    assert (
        ci_client.post(
            "/api/v1/staff/checkin/",
            {"ticket_code": ticket_code, "luggage_fee": "-5.00"},
            format="json",
        ).status_code
        == 400
    )
    assert ci_client.post("/api/v1/staff/checkin/", {"ticket_code": ticket_code}, format="json").status_code == 200
    assert gate_client.post("/api/v1/staff/gate/board/", {"ticket_code": ticket_code}, format="json").data["status"] == TicketStatus.BOARDED
    assert gate_client.post("/api/v1/staff/gate/board/", {"ticket_code": ticket_code}, format="json").status_code == 400
    assert gate_client.post("/api/v1/staff/gate/board/", {"ticket_code": "DA-UNKNOWN"}, format="json").status_code == 400


@pytest.mark.django_db
def test_idempotency_oversized_key_outbox_filter_and_failure_logging(
    api_client, auth_client, users, flight_setup
):
    # Oversized Idempotency-Key (>128 chars) returns 400
    too_long = api_client.post(
        "/api/v1/bookings/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="x" * 129,
    )
    assert too_long.status_code == 400

    # Supervisor Outbox status filtering & Webhook network exception logging
    OutboxEvent.objects.create(
        event_type="test.event", payload={"event": "test.event"}, status=OutboxStatus.PENDING
    )
    sup = auth_client(users["supervisor"])
    outbox_resp = sup.get("/api/v1/integrations/outbox/?status=PENDING")
    assert outbox_resp.status_code == 200
    assert len(outbox_resp.data) >= 1

    sub = WebhookSubscription.objects.create(
        name="Unreachable",
        target_url="http://down.local/hook",
        secret="s3cr3t",
        events=["*"],
        is_active=True,
    )
    with patch("apps.integrations.tasks.requests.post", side_effect=requests.ConnectionError("refused")):
        res = dispatch_webhook_event("test.event", {"event": "test.event"})
    assert res["failed"] == 1
    assert WebhookDelivery.objects.filter(subscription=sub, success=False).exists()

    # Notification SMTP exception logs EmailLog.Status.FAILED cleanly
    with patch("apps.notifications.tasks.send_mail", side_effect=RuntimeError("smtp down")):
        cancel_res = send_flight_cancellation_email("a@example.com", "DA101", "BK-1", "100.00")
    assert cancel_res["status"] == "failed"
    assert EmailLog.objects.filter(recipient="a@example.com", status=EmailLog.Status.FAILED).exists()

    # Confirmation email SMTP exception logs FAILED cleanly
    b_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight_setup["flight"].id),
            "seat_type_id": str(flight_setup["eco"].id),
            "contact_email": "failmail@example.com",
            "passengers": [{"first_name": "F", "last_name": "M", "document_number": "FM1"}],
        },
        format="json",
    )
    with patch("apps.notifications.tasks.EmailMessage.send", side_effect=RuntimeError("smtp down")):
        conf_res = send_booking_confirmation_email(b_resp.data["id"], "Temp123!", "INV-FAIL")
    assert conf_res["status"] == "failed"
    assert EmailLog.objects.filter(recipient="failmail@example.com", status=EmailLog.Status.FAILED).exists()
