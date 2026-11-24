from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.bookings.models import Discount, DiscountType
from apps.fleet.models import Airplane, AirplaneSeatConfig, Airport, SeatType
from apps.flights.models import Flight, FlightStatus, Option, OptionCategory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    def _make(user: User) -> APIClient:
        client = APIClient()
        token = str(RefreshToken.for_user(user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _make


@pytest.fixture
def users(db):
    customer = User.objects.create_user(
        email="customer@test.local", password="Password123!", first_name="Jane", last_name="Doe"
    )
    CustomerProfile.objects.filter(user=customer).update(balance=Decimal("500.00"))
    gate = User.objects.create_user(
        email="gate@test.local",
        password="Password123!",
        first_name="Gate",
        last_name="Mgr",
        role=UserRole.GATE_MANAGER,
    )
    checkin = User.objects.create_user(
        email="checkin@test.local",
        password="Password123!",
        first_name="Checkin",
        last_name="Mgr",
        role=UserRole.CHECKIN_MANAGER,
    )
    supervisor = User.objects.create_user(
        email="supervisor@test.local",
        password="Password123!",
        first_name="Super",
        last_name="Visor",
        role=UserRole.SUPERVISOR,
    )
    return {
        "customer": customer,
        "gate": gate,
        "checkin": checkin,
        "supervisor": supervisor,
    }


@pytest.fixture
def flight_setup(db):
    jfk = Airport.objects.create(code="JFK", name="JFK Intl", city="New York", country="USA")
    lhr = Airport.objects.create(code="LHR", name="Heathrow", city="London", country="UK")
    eco = SeatType.objects.create(code="ECO", name="Economy", price_multiplier=Decimal("1.00"))
    bus = SeatType.objects.create(code="BUS", name="Business", price_multiplier=Decimal("2.00"))

    plane = Airplane.objects.create(
        registration_number="TEST-737", model_name="Boeing 737", total_capacity=5
    )
    AirplaneSeatConfig.objects.create(airplane=plane, seat_type=eco, seat_count=3)
    AirplaneSeatConfig.objects.create(airplane=plane, seat_type=bus, seat_count=2)

    lunch = Option.objects.create(
        name="Hot Lunch", category=OptionCategory.MEAL, price=Decimal("20.00")
    )
    luggage = Option.objects.create(
        name="Extra Luggage", category=OptionCategory.LUGGAGE, price=Decimal("40.00")
    )
    discount = Discount.objects.create(
        code="SAVE10", discount_type=DiscountType.PERCENT, value=Decimal("10.00"), is_active=True
    )

    dep = timezone.now() + timedelta(days=2)
    flight = Flight.objects.create(
        flight_number="DA777",
        origin=jfk,
        destination=lhr,
        airplane=plane,
        departure_time=dep,
        arrival_time=dep + timedelta(hours=7),
        base_price=Decimal("200.00"),
        gate="G5",
        status=FlightStatus.SCHEDULED,
    )
    flight.available_options.set([lunch, luggage])

    return {
        "jfk": jfk,
        "lhr": lhr,
        "eco": eco,
        "bus": bus,
        "plane": plane,
        "lunch": lunch,
        "luggage": luggage,
        "discount": discount,
        "flight": flight,
    }
