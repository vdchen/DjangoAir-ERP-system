import uuid
from decimal import Decimal

from django.db import models

from apps.fleet.models import Airplane, Airport


class OptionCategory(models.TextChoices):
    MEAL = "MEAL", "Meal / Lunch"
    LUGGAGE = "LUGGAGE", "Luggage"
    COMFORT = "COMFORT", "Comfort"
    OTHER = "OTHER", "Other"


class Option(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(
        max_length=24, choices=OptionCategory.choices, default=OptionCategory.OTHER
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self) -> str:
        return f"{self.name} (${self.price})"


class FlightStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    BOARDING = "BOARDING", "Boarding"
    DEPARTED = "DEPARTED", "Departed"
    CANCELLED = "CANCELLED", "Cancelled"


class Flight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flight_number = models.CharField(max_length=20, db_index=True)
    origin = models.ForeignKey(Airport, on_delete=models.PROTECT, related_name="departing_flights")
    destination = models.ForeignKey(
        Airport, on_delete=models.PROTECT, related_name="arriving_flights"
    )
    airplane = models.ForeignKey(Airplane, on_delete=models.PROTECT, related_name="flights")
    departure_time = models.DateTimeField(db_index=True)
    arrival_time = models.DateTimeField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    gate = models.CharField(max_length=16, default="A1")
    status = models.CharField(
        max_length=20, choices=FlightStatus.choices, default=FlightStatus.SCHEDULED, db_index=True
    )
    available_options = models.ManyToManyField(Option, blank=True, related_name="flights")
    _prefetched_booked_counts: dict | None = None
    _seat_availability_cache: list[dict] | None = None

    class Meta:
        ordering = ["departure_time"]

    def __str__(self) -> str:
        return f"{self.flight_number} ({self.origin.code} -> {self.destination.code})"

    @classmethod
    def attach_booked_counts(cls, flights: list["Flight"]) -> list["Flight"]:
        """Bulk-load non-cancelled ticket counts for a list of flights in a single SQL query."""
        if not flights:
            return flights
        from apps.bookings.models import Ticket, TicketStatus

        flight_ids = [f.id for f in flights]
        rows = (
            Ticket.objects.filter(flight_id__in=flight_ids)
            .exclude(status=TicketStatus.CANCELLED)
            .values("flight_id", "seat_type_id")
            .annotate(cnt=models.Count("id"))
        )
        counts_map: dict = {fid: {} for fid in flight_ids}
        for row in rows:
            counts_map[row["flight_id"]][row["seat_type_id"]] = row["cnt"]
        for flight in flights:
            flight._prefetched_booked_counts = counts_map.get(flight.id, {})
            flight._seat_availability_cache = None
        return flights

    def seat_availability(self) -> list[dict]:
        """Return seat capacity, booked count, available count, and unit fare per SeatType."""
        cached = getattr(self, "_seat_availability_cache", None)
        if cached is not None:
            return cached

        booked_counts = getattr(self, "_prefetched_booked_counts", None)
        if booked_counts is None:
            from apps.bookings.models import Ticket, TicketStatus

            booked_counts = {}
            active_tickets = (
                Ticket.objects.filter(flight=self)
                .exclude(status=TicketStatus.CANCELLED)
                .values("seat_type_id")
                .annotate(cnt=models.Count("id"))
            )
            for row in active_tickets:
                booked_counts[row["seat_type_id"]] = row["cnt"]

        result = []
        # Iterate .all() directly to honor airplane__seat_configs__seat_type prefetch cache
        for cfg in self.airplane.seat_configs.all():
            booked = booked_counts.get(cfg.seat_type_id, 0)
            available = max(cfg.seat_count - booked, 0)
            fare = (self.base_price * cfg.seat_type.price_multiplier).quantize(Decimal("0.01"))
            result.append(
                {
                    "seat_type_id": str(cfg.seat_type.id),
                    "seat_type_code": cfg.seat_type.code,
                    "seat_type_name": cfg.seat_type.name,
                    "price_multiplier": str(cfg.seat_type.price_multiplier),
                    "unit_price": str(fare),
                    "total_seats": cfg.seat_count,
                    "booked_seats": booked,
                    "available_seats": available,
                }
            )
        if getattr(self, "_prefetched_booked_counts", None) is not None:
            self._seat_availability_cache = result
        return result

    def total_available_seats(self) -> int:
        return sum(item["available_seats"] for item in self.seat_availability())
