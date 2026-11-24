import re
from decimal import Decimal

import pytest
from django.core import mail

from apps.accounts.models import User
from apps.bookings.models import BookingStatus, TicketStatus
from apps.notifications.models import EmailLog
from apps.payments.models import PaymentStatus


@pytest.mark.django_db
def test_customer_search_booking_emulated_payment_email_and_cabinet(api_client, flight_setup):
    flight = flight_setup["flight"]
    eco = flight_setup["eco"]
    lunch = flight_setup["lunch"]
    luggage = flight_setup["luggage"]

    # 1. Search flights by destination, date, passengers
    date_str = flight.departure_time.strftime("%Y-%m-%d")
    search_resp = api_client.get(
        f"/api/v1/flights/search/?destination=LHR&date={date_str}&passengers=2"
    )
    assert search_resp.status_code == 200
    assert len(search_resp.data) == 1
    assert search_resp.data[0]["flight_number"] == "DA777"
    assert search_resp.data[0]["total_available_seats"] == 5

    # 2. Validate discount code
    disc_resp = api_client.post(
        "/api/v1/bookings/validate-discount/",
        {"code": "SAVE10", "subtotal": "520.00"},
        format="json",
    )
    assert disc_resp.status_code == 200
    assert disc_resp.data["discount_amount"] == "52.00"

    # 3. Create guest booking for 2 passengers with Lunch + Luggage + SAVE10
    booking_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(eco.id),
            "contact_email": "guest.traveler@example.com",
            "option_ids": [str(lunch.id), str(luggage.id)],
            "discount_code": "SAVE10",
            "passengers": [
                {"first_name": "Ada", "last_name": "Lovelace", "document_number": "UK1001"},
                {"first_name": "Alan", "last_name": "Turing", "document_number": "UK1002"},
            ],
        },
        format="json",
    )
    assert booking_resp.status_code == 201
    # 2 passengers * (200 base + 20 lunch + 40 luggage) = 520; -10% = 468.00
    assert booking_resp.data["subtotal_amount"] == "520.00"
    assert booking_resp.data["discount_amount"] == "52.00"
    assert booking_resp.data["total_amount"] == "468.00"
    assert booking_resp.data["status"] == BookingStatus.RESERVED
    ref = booking_resp.data["booking_reference"]
    ticket_code = booking_resp.data["tickets"][0]["ticket_code"]

    # 4. Declined card returns 402 and keeps booking RESERVED
    declined = api_client.post(
        "/api/v1/payments/charge/",
        {
            "booking_reference": ref,
            "payment_method": "CARD",
            "card_number": "4000000000000002",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
        format="json",
    )
    assert declined.status_code == 402
    assert declined.data["payment"]["status"] == PaymentStatus.FAILED

    # 5. Approved card succeeds, sends confirmation email with cabinet password
    paid = api_client.post(
        "/api/v1/payments/charge/",
        {
            "booking_reference": ref,
            "payment_method": "CARD",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
        format="json",
    )
    assert paid.status_code == 200
    assert paid.data["booking"]["status"] == BookingStatus.PAID
    assert paid.data["payment"]["status"] == PaymentStatus.SUCCEEDED
    assert paid.data["new_cabinet_account"] is True

    # Verify invoice endpoint
    payment_id = paid.data["payment"]["id"]
    inv = api_client.get(f"/api/v1/payments/{payment_id}/invoice/")
    assert inv.status_code == 200
    assert inv.data["total"] == "468.00"
    assert len(inv.data["items"]) == 2

    # Verify Celery email sent + EmailLog created + extract generated cabinet password
    assert len(mail.outbox) == 1
    assert EmailLog.objects.filter(
        recipient="guest.traveler@example.com", status=EmailLog.Status.SENT
    ).exists()
    email_body = mail.outbox[0].body
    assert ticket_code in email_body
    match = re.search(r"Temporary Password:\s*(\S+)", email_body)
    assert match is not None
    temp_password = match.group(1)

    # 6. Log into Personal Cabinet using emailed credentials & perform online check-in
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "guest.traveler@example.com", "password": temp_password},
        format="json",
    )
    assert login.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    cabinet = api_client.get("/api/v1/cabinet/overview/")
    assert cabinet.status_code == 200
    assert len(cabinet.data["upcoming_tickets"]) == 2
    assert Decimal(cabinet.data["balance"]) == Decimal("0.00")

    # Top up balance via emulated card
    topup = api_client.post(
        "/api/v1/cabinet/balance/top-up/",
        {
            "amount": "125.00",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
        format="json",
    )
    assert topup.status_code == 200
    assert topup.data["balance"] == "125.00"

    # Online check-in
    checkin = api_client.post(f"/api/v1/cabinet/tickets/{ticket_code}/check-in/")
    assert checkin.status_code == 200
    assert checkin.data["status"] == TicketStatus.CHECKED_IN


@pytest.mark.django_db
def test_seat_capacity_prevents_overbooking(api_client, flight_setup):
    flight = flight_setup["flight"]
    bus = flight_setup["bus"]  # Only 2 seats configured

    resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(bus.id),
            "contact_email": "group@example.com",
            "passengers": [
                {"first_name": "P1", "last_name": "L1", "document_number": "D1"},
                {"first_name": "P2", "last_name": "L2", "document_number": "D2"},
                {"first_name": "P3", "last_name": "L3", "document_number": "D3"},
            ],
        },
        format="json",
    )
    assert resp.status_code == 400
    assert not User.objects.filter(email="group@example.com").exists()
