from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.accounts.models import CustomerProfile
from apps.integrations.events import publish_domain_event
from apps.notifications.tasks import send_flight_cancellation_email

from .models import Flight, FlightStatus


class FlightAlreadyCancelledError(Exception):
    """Raised when a Supervisor attempts to cancel a flight that is already cancelled."""


@dataclass
class FlightCancellationResult:
    flight: Flight
    refunded_bookings: int


@transaction.atomic
def cancel_flight_and_refund(flight_pk) -> FlightCancellationResult:
    """Atomically cancel a flight, refund paid bookings to customer balance, and enqueue notifications."""
    from apps.bookings.models import Booking, BookingStatus, TicketStatus
    from apps.payments.models import PaymentStatus

    flight = get_object_or_404(Flight.objects.select_for_update(), pk=flight_pk)
    if flight.status == FlightStatus.CANCELLED:
        raise FlightAlreadyCancelledError("Flight is already cancelled.")

    flight.status = FlightStatus.CANCELLED
    flight.save(update_fields=["status"])

    affected_bookings = (
        Booking.objects.filter(tickets__flight=flight)
        .exclude(status=BookingStatus.CANCELLED)
        .distinct()
        .select_related("user")
        .prefetch_related("payments")
    )

    refunded_count = 0
    for booking in affected_bookings:
        refund_amount = Decimal("0.00")
        if booking.status == BookingStatus.PAID:
            refund_amount = booking.total_amount
            profile, _ = CustomerProfile.objects.get_or_create(user=booking.user)
            if refund_amount > 0:
                profile.credit(refund_amount)
            booking.payments.filter(status=PaymentStatus.SUCCEEDED).update(
                status=PaymentStatus.REFUNDED
            )
            refunded_count += 1

        booking.tickets.filter(flight=flight).update(status=TicketStatus.CANCELLED)
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status"])

        send_flight_cancellation_email.delay(
            recipient=booking.contact_email,
            flight_number=flight.flight_number,
            booking_reference=booking.booking_reference,
            refund_amount=str(refund_amount),
        )

    publish_domain_event(
        "flight.cancelled",
        {
            "flight_id": str(flight.id),
            "flight_number": flight.flight_number,
            "refunded_bookings": refunded_count,
        },
    )
    return FlightCancellationResult(flight=flight, refunded_bookings=refunded_count)
