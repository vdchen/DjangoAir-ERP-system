import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.fleet.models import SeatType
from apps.flights.models import Flight, Option


def generate_booking_reference() -> str:
    return f"BK-{secrets.token_hex(3).upper()}"


def generate_ticket_code() -> str:
    return f"DA-{secrets.token_hex(4).upper()}"


class DiscountType(models.TextChoices):
    PERCENT = "PERCENT", "Percentage"
    FIXED = "FIXED", "Fixed Amount"


class Discount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    discount_type = models.CharField(
        max_length=16, choices=DiscountType.choices, default=DiscountType.PERCENT
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.discount_type}: {self.value})"

    def is_valid_now(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        subtotal = Decimal(subtotal)
        if not self.is_valid_now() or subtotal <= 0:
            return Decimal("0.00")
        if self.discount_type == DiscountType.PERCENT:
            amt = (subtotal * self.value / Decimal("100")).quantize(Decimal("0.01"))
        else:
            amt = self.value.quantize(Decimal("0.01"))
        return min(amt, subtotal)


class BookingStatus(models.TextChoices):
    RESERVED = "RESERVED", "Reserved"
    PAID = "PAID", "Paid"
    CANCELLED = "CANCELLED", "Cancelled"


class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(
        max_length=20, unique=True, default=generate_booking_reference, db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    contact_email = models.EmailField()
    discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings"
    )
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.RESERVED, db_index=True
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.booking_reference} ({self.status})"

    def recalculate_totals(self) -> None:
        subtotal = Decimal("0.00")
        for ticket in self.tickets.exclude(status=TicketStatus.CANCELLED):
            subtotal += ticket.base_fare + ticket.options_total + ticket.luggage_fee
        discount_amt = (
            self.discount.calculate_discount(subtotal) if self.discount else Decimal("0.00")
        )
        self.subtotal_amount = subtotal.quantize(Decimal("0.01"))
        self.discount_amount = discount_amt.quantize(Decimal("0.01"))
        self.total_amount = max(subtotal - discount_amt, Decimal("0.00")).quantize(Decimal("0.01"))
        self.save(update_fields=["subtotal_amount", "discount_amount", "total_amount"])


class Passenger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    document_number = models.CharField(max_length=64)
    date_of_birth = models.DateField(null=True, blank=True)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.full_name} ({self.document_number})"


class TicketStatus(models.TextChoices):
    RESERVED = "RESERVED", "Reserved"
    PAID = "PAID", "Paid"
    CHECKED_IN = "CHECKED_IN", "Checked In"
    BOARDED = "BOARDED", "Boarded"
    CANCELLED = "CANCELLED", "Cancelled"


class Ticket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="tickets")
    flight = models.ForeignKey(Flight, on_delete=models.PROTECT, related_name="tickets")
    passenger = models.ForeignKey(Passenger, on_delete=models.PROTECT, related_name="tickets")
    seat_type = models.ForeignKey(SeatType, on_delete=models.PROTECT, related_name="tickets")
    ticket_code = models.CharField(
        max_length=24, unique=True, default=generate_ticket_code, db_index=True
    )
    seat_number = models.CharField(max_length=12)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2)
    options_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    luggage_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20, choices=TicketStatus.choices, default=TicketStatus.RESERVED, db_index=True
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_in_tickets",
    )
    boarded_at = models.DateTimeField(null=True, blank=True)
    boarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boarded_tickets",
    )

    class Meta:
        ordering = ["flight__departure_time", "ticket_code"]

    def __str__(self) -> str:
        return f"{self.ticket_code} ({self.passenger.full_name} - {self.status})"


class AddedStage(models.TextChoices):
    BOOKING = "BOOKING", "Booking"
    CHECKIN = "CHECKIN", "Check-in Counter"


class TicketOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="ticket_options")
    option = models.ForeignKey(Option, on_delete=models.PROTECT, related_name="ticket_options")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    added_stage = models.CharField(
        max_length=16, choices=AddedStage.choices, default=AddedStage.BOOKING
    )

    def __str__(self) -> str:
        return f"{self.ticket.ticket_code} + {self.option.name} x{self.quantity}"
