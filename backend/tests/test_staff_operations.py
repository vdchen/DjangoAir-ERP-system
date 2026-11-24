from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.bookings.models import BookingStatus, TicketStatus
from apps.flights.models import FlightStatus


def _create_paid_booking(api_client, flight_setup, customer_email="customer@test.local"):
    b_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight_setup["flight"].id),
            "seat_type_id": str(flight_setup["eco"].id),
            "contact_email": customer_email,
            "passengers": [
                {"first_name": "Jane", "last_name": "Doe", "document_number": "P90001"}
            ],
        },
        format="json",
    )
    assert b_resp.status_code == 201
    ref = b_resp.data["booking_reference"]
    p_resp = api_client.post(
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
    assert p_resp.status_code == 200
    return p_resp.data["booking"]


@pytest.mark.django_db
def test_gate_checkin_supervisor_hierarchy_and_operations(api_client, auth_client, users, flight_setup):
    booking = _create_paid_booking(api_client, flight_setup)
    ticket_code = booking["tickets"][0]["ticket_code"]

    gate_client = auth_client(users["gate"])
    checkin_client = auth_client(users["checkin"])
    sup_client = auth_client(users["supervisor"])

    # Gate Manager cannot perform Check-in Manager action
    forbidden_ci = gate_client.post(
        "/api/v1/staff/checkin/", {"ticket_code": ticket_code}, format="json"
    )
    assert forbidden_ci.status_code == 403

    # Gate Manager cannot board a passenger who has NOT checked in yet
    too_early = gate_client.post(
        "/api/v1/staff/gate/board/", {"ticket_code": ticket_code}, format="json"
    )
    assert too_early.status_code == 400

    # Check-in Manager checks in passenger, adds Hot Lunch option, and collects $35 luggage fee
    ci_resp = checkin_client.post(
        "/api/v1/staff/checkin/",
        {
            "ticket_code": ticket_code,
            "option_ids": [str(flight_setup["lunch"].id)],
            "luggage_fee": "35.00",
        },
        format="json",
    )
    assert ci_resp.status_code == 200
    assert ci_resp.data["status"] == TicketStatus.CHECKED_IN
    assert ci_resp.data["options_total"] == "20.00"
    assert ci_resp.data["luggage_fee"] == "35.00"

    # Gate Manager can now board the passenger using ticket_code
    board_resp = gate_client.post(
        "/api/v1/staff/gate/board/", {"ticket_code": ticket_code}, format="json"
    )
    assert board_resp.status_code == 200
    assert board_resp.data["status"] == TicketStatus.BOARDED

    # Check-in Manager cannot create options or flights (Supervisor only)
    opt_payload = {"name": "WiFi Pass", "category": "COMFORT", "price": "15.00"}
    assert checkin_client.post("/api/v1/staff/options/", opt_payload, format="json").status_code == 403

    # Supervisor creates and deletes an option
    opt_created = sup_client.post("/api/v1/staff/options/", opt_payload, format="json")
    assert opt_created.status_code == 201
    opt_id = opt_created.data["id"]
    assert sup_client.delete(f"/api/v1/staff/options/{opt_id}/").status_code == 204


@pytest.mark.django_db
def test_supervisor_create_and_cancel_flight_refunds_balance(
    api_client, auth_client, users, flight_setup
):
    sup_client = auth_client(users["supervisor"])
    dep = timezone.now() + timedelta(days=4)

    # Supervisor creates a new flight
    create_resp = sup_client.post(
        "/api/v1/staff/flights/",
        {
            "flight_number": "DA900",
            "origin": str(flight_setup["jfk"].id),
            "destination": str(flight_setup["lhr"].id),
            "airplane": str(flight_setup["plane"].id),
            "departure_time": dep.isoformat(),
            "arrival_time": (dep + timedelta(hours=6)).isoformat(),
            "base_price": "300.00",
            "gate": "F1",
        },
        format="json",
    )
    assert create_resp.status_code == 201

    # Customer pays for existing flight DA777, then Supervisor cancels DA777
    before_balance = CustomerProfile.objects.get(user=users["customer"]).balance
    booking = _create_paid_booking(api_client, flight_setup, customer_email="customer@test.local")
    assert booking["status"] == BookingStatus.PAID

    cancel_resp = sup_client.post(f"/api/v1/staff/flights/{flight_setup['flight'].id}/cancel/")
    assert cancel_resp.status_code == 200
    assert cancel_resp.data["flight"]["status"] == FlightStatus.CANCELLED
    assert cancel_resp.data["refunded_bookings"] == 1

    after_balance = CustomerProfile.objects.get(user=users["customer"]).balance
    assert after_balance == before_balance + Decimal("200.00")
