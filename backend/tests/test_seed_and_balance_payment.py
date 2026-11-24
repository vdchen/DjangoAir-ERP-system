from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.accounts.models import CustomerProfile, User
from apps.bookings.models import BookingStatus
from apps.flights.models import Flight


@pytest.mark.django_db
def test_seed_demo_data_is_idempotent():
    call_command("seed_demo_data")
    first_flights = Flight.objects.count()
    first_users = User.objects.count()

    call_command("seed_demo_data")
    assert Flight.objects.count() == first_flights
    assert User.objects.count() == first_users
    assert User.objects.filter(email="supervisor@djangoair.local").exists()
    assert User.objects.filter(email="alice@example.com").exists()


@pytest.mark.django_db
def test_pay_booking_with_personal_cabinet_balance(auth_client, users, flight_setup):
    cust_client = auth_client(users["customer"])
    start_balance = CustomerProfile.objects.get(user=users["customer"]).balance

    booking_resp = cust_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight_setup["flight"].id),
            "seat_type_id": str(flight_setup["eco"].id),
            "contact_email": users["customer"].email,
            "passengers": [
                {"first_name": "Jane", "last_name": "Doe", "document_number": "BAL123"}
            ],
        },
        format="json",
    )
    assert booking_resp.status_code == 201
    ref = booking_resp.data["booking_reference"]

    pay_resp = cust_client.post(
        "/api/v1/payments/charge/",
        {"booking_reference": ref, "payment_method": "BALANCE"},
        format="json",
    )
    assert pay_resp.status_code == 200
    assert pay_resp.data["booking"]["status"] == BookingStatus.PAID
    assert pay_resp.data["payment"]["provider"] == "cabinet_balance"

    end_balance = CustomerProfile.objects.get(user=users["customer"]).balance
    assert end_balance == start_balance - Decimal("200.00")
