from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.bookings.models import (
    Booking,
    BookingStatus,
    Discount,
    DiscountType,
    Passenger,
    Ticket,
    TicketStatus,
)
from apps.fleet.models import Airplane, AirplaneSeatConfig, Airport, SeatType
from apps.flights.models import Flight, FlightStatus, Option, OptionCategory
from apps.integrations.models import WebhookSubscription
from apps.payments.models import Payment, PaymentStatus


class Command(BaseCommand):
    help = "Idempotently seed DjangoAir demo fleet, flights, options, discounts, users, and webhooks."

    def handle(self, *args, **options):
        self.stdout.write("Seeding DjangoAir demo data...")

        # 1. Airports
        airports_spec = [
            ("JFK", "John F. Kennedy International", "New York", "USA"),
            ("LHR", "London Heathrow", "London", "United Kingdom"),
            ("CDG", "Paris Charles de Gaulle", "Paris", "France"),
            ("BER", "Berlin Brandenburg", "Berlin", "Germany"),
            ("DXB", "Dubai International", "Dubai", "UAE"),
            ("NRT", "Tokyo Narita International", "Tokyo", "Japan"),
        ]
        airports = {}
        for code, name, city, country in airports_spec:
            airport, _ = Airport.objects.get_or_create(
                code=code, defaults={"name": name, "city": city, "country": country}
            )
            airports[code] = airport

        # 2. Seat Types
        seat_types_spec = [
            ("ECO", "Economy", Decimal("1.00"), "Standard cabin seating with carry-on included."),
            ("BUS", "Business", Decimal("2.20"), "Spacious cabin, lounge access, and priority service."),
            ("FST", "First Class", Decimal("3.50"), "Private suite, fine dining, and flexible changes."),
        ]
        seat_types = {}
        for code, name, mult, desc in seat_types_spec:
            st, _ = SeatType.objects.get_or_create(
                code=code,
                defaults={"name": name, "price_multiplier": mult, "description": desc},
            )
            seat_types[code] = st

        # 3. Airplanes & Seat Configs
        planes_spec = [
            ("DA-737A", "Boeing 737-800", [("ECO", 120), ("BUS", 16)]),
            ("DA-320B", "Airbus A320neo", [("ECO", 132), ("BUS", 18)]),
            ("DA-787C", "Boeing 787-9 Dreamliner", [("ECO", 180), ("BUS", 28), ("FST", 8)]),
        ]
        planes = {}
        for reg, model_name, cfgs in planes_spec:
            total = sum(cnt for _, cnt in cfgs)
            plane, _ = Airplane.objects.get_or_create(
                registration_number=reg,
                defaults={"model_name": model_name, "total_capacity": total},
            )
            for st_code, cnt in cfgs:
                AirplaneSeatConfig.objects.get_or_create(
                    airplane=plane, seat_type=seat_types[st_code], defaults={"seat_count": cnt}
                )
            planes[reg] = plane

        # 4. Options
        options_spec = [
            ("Hot Lunch", OptionCategory.MEAL, Decimal("18.00"), "Chef-prepared hot meal with beverage."),
            ("Vegetarian Meal", OptionCategory.MEAL, Decimal("16.00"), "Fresh plant-based seasonal menu."),
            ("Extra 20kg Luggage", OptionCategory.LUGGAGE, Decimal("45.00"), "Additional checked suitcase up to 20kg."),
            ("Priority Boarding", OptionCategory.COMFORT, Decimal("22.00"), "Board first in Group 1."),
            ("Extra Legroom", OptionCategory.COMFORT, Decimal("35.00"), "Exit-row or bulkhead seating."),
        ]
        all_options = []
        for name, cat, price, desc in options_spec:
            opt, _ = Option.objects.get_or_create(
                name=name,
                defaults={"category": cat, "price": price, "description": desc, "is_active": True},
            )
            all_options.append(opt)

        # 5. Discounts
        Discount.objects.get_or_create(
            code="WELCOME10",
            defaults={
                "discount_type": DiscountType.PERCENT,
                "value": Decimal("10.00"),
                "is_active": True,
            },
        )
        Discount.objects.get_or_create(
            code="FLY50",
            defaults={
                "discount_type": DiscountType.FIXED,
                "value": Decimal("50.00"),
                "is_active": True,
            },
        )

        # 6. Staff & Demo Customer Users
        staff_users = [
            ("supervisor@djangoair.local", "Supervisor123!", "Elena", "Vance", UserRole.SUPERVISOR, True),
            ("checkin@djangoair.local", "Checkin123!", "Marcus", "Reed", UserRole.CHECKIN_MANAGER, False),
            ("gate@djangoair.local", "Gate123!", "Liam", "Carter", UserRole.GATE_MANAGER, False),
        ]
        for email, pwd, fn, ln, role, is_super in staff_users:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(
                    email=email,
                    password=pwd,
                    first_name=fn,
                    last_name=ln,
                    role=role,
                    is_staff=True,
                    is_superuser=is_super,
                )

        alice, alice_created = User.objects.get_or_create(
            email="alice@example.com",
            defaults={"first_name": "Alice", "last_name": "Morgan", "role": UserRole.CUSTOMER},
        )
        if alice_created:
            alice.set_password("Customer123!")
            alice.save(update_fields=["password"])
        alice_profile, _ = CustomerProfile.objects.get_or_create(user=alice)
        if alice_created:
            alice_profile.balance = Decimal("250.00")
            alice_profile.passport_number = "US9823412"
            alice_profile.save(update_fields=["balance", "passport_number"])

        # 7. Scheduled Upcoming Flights across next 5 days + 1 past flight
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        base_day = now.replace(hour=0)
        routes = [
            ("DA101", "JFK", "LHR", "DA-787C", 7, Decimal("420.00"), "B12"),
            ("DA204", "JFK", "CDG", "DA-787C", 7, Decimal("440.00"), "A4"),
            ("DA310", "LHR", "BER", "DA-320B", 2, Decimal("150.00"), "C8"),
            ("DA415", "CDG", "DXB", "DA-787C", 6, Decimal("510.00"), "D2"),
            ("DA520", "BER", "LHR", "DA-737A", 2, Decimal("145.00"), "A9"),
            ("DA630", "DXB", "NRT", "DA-787C", 9, Decimal("680.00"), "E1"),
        ]

        created_upcoming = None
        for day_offset in range(1, 6):
            for idx, (fnum, orig, dest, reg, dur_h, price, gate) in enumerate(routes):
                dep = base_day + timedelta(days=day_offset, hours=8 + (idx * 2))
                arr = dep + timedelta(hours=dur_h)
                code = f"{fnum}-{day_offset}"
                flight, created = Flight.objects.get_or_create(
                    flight_number=code,
                    defaults={
                        "origin": airports[orig],
                        "destination": airports[dest],
                        "airplane": planes[reg],
                        "departure_time": dep,
                        "arrival_time": arr,
                        "base_price": price,
                        "gate": gate,
                        "status": FlightStatus.SCHEDULED,
                    },
                )
                if created:
                    flight.available_options.set(all_options)
                if created_upcoming is None and code == "DA101-1":
                    created_upcoming = flight

        # Past flight for Alice's Personal Cabinet history
        past_flight, _ = Flight.objects.get_or_create(
            flight_number="DA099-PAST",
            defaults={
                "origin": airports["LHR"],
                "destination": airports["CDG"],
                "airplane": planes["DA-320B"],
                "departure_time": now - timedelta(days=14),
                "arrival_time": now - timedelta(days=14) + timedelta(hours=2),
                "base_price": Decimal("180.00"),
                "gate": "C3",
                "status": FlightStatus.DEPARTED,
            },
        )

        # Seed Alice's demo upcoming & past bookings if she has none yet
        if not Booking.objects.filter(user=alice).exists() and created_upcoming:
            p_alice = Passenger.objects.create(
                first_name="Alice", last_name="Morgan", document_number="US9823412"
            )
            upcoming_booking = Booking.objects.create(
                booking_reference="BK-ALICE1",
                user=alice,
                contact_email=alice.email,
                subtotal_amount=Decimal("420.00"),
                total_amount=Decimal("420.00"),
                status=BookingStatus.PAID,
            )
            Ticket.objects.create(
                booking=upcoming_booking,
                flight=created_upcoming,
                passenger=p_alice,
                seat_type=seat_types["ECO"],
                ticket_code="DA-ALICE101",
                seat_number="E1A",
                base_fare=Decimal("420.00"),
                status=TicketStatus.PAID,
            )
            Payment.objects.create(
                booking=upcoming_booking,
                transaction_id="TXN-SEED-UPCOMING",
                amount=Decimal("420.00"),
                status=PaymentStatus.SUCCEEDED,
                card_last4="4242",
                invoice_number="INV-SEED-0001",
                paid_at=now - timedelta(days=1),
            )

            past_booking = Booking.objects.create(
                booking_reference="BK-ALICE0",
                user=alice,
                contact_email=alice.email,
                subtotal_amount=Decimal("180.00"),
                total_amount=Decimal("180.00"),
                status=BookingStatus.PAID,
            )
            Ticket.objects.create(
                booking=past_booking,
                flight=past_flight,
                passenger=p_alice,
                seat_type=seat_types["ECO"],
                ticket_code="DA-ALICE099",
                seat_number="E2B",
                base_fare=Decimal("180.00"),
                status=TicketStatus.BOARDED,
                checked_in_at=now - timedelta(days=14, hours=2),
                boarded_at=now - timedelta(days=14, hours=1),
            )

        # 8. Default Third-Party Webhook Subscription (Flask Webhook Mock)
        WebhookSubscription.objects.get_or_create(
            name="Flask Third-Party Webhook Mock",
            defaults={
                "target_url": settings.WEBHOOK_MOCK_URL,
                "secret": settings.WEBHOOK_DEFAULT_SECRET,
                "events": ["*"],
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("DjangoAir demo data seeded successfully."))
