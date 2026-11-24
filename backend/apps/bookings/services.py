from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.fleet.models import AirplaneSeatConfig, SeatType
from apps.flights.models import Flight, FlightStatus, Option
from apps.integrations.events import publish_domain_event

from .models import (
    AddedStage,
    Booking,
    BookingStatus,
    Discount,
    Passenger,
    Ticket,
    TicketOption,
    TicketStatus,
)


def _allocate_seat_number(flight: Flight, seat_type: SeatType, offset: int) -> str:
    prefix = seat_type.code[:1].upper()
    existing_count = (
        Ticket.objects.filter(flight=flight, seat_type=seat_type)
        .exclude(status=TicketStatus.CANCELLED)
        .count()
    )
    index = existing_count + offset
    row = (index // 6) + 1
    col = "ABCDEF"[index % 6]
    return f"{prefix}{row}{col}"


@transaction.atomic
def create_booking(
    *,
    flight_id,
    seat_type_id,
    contact_email: str,
    passengers_data: list[dict],
    option_ids: list | None = None,
    discount_code: str | None = None,
    authenticated_user: User | None = None,
) -> Booking:
    if not passengers_data:
        raise ValidationError({"passengers": "At least one passenger is required."})

    # Row-level lock on Flight to prevent concurrent overbooking
    flight = (
        Flight.objects.select_for_update()
        .select_related("airplane", "origin", "destination")
        .get(pk=flight_id)
    )
    if flight.status != FlightStatus.SCHEDULED:
        raise ValidationError({"flight": "This flight is not open for booking."})

    try:
        seat_config = AirplaneSeatConfig.objects.select_related("seat_type").get(
            airplane=flight.airplane, seat_type_id=seat_type_id
        )
    except AirplaneSeatConfig.DoesNotExist as exc:
        raise ValidationError({"seat_type": "Seat type not configured on this airplane."}) from exc

    booked_count = (
        Ticket.objects.filter(flight=flight, seat_type_id=seat_type_id)
        .exclude(status=TicketStatus.CANCELLED)
        .count()
    )
    available = seat_config.seat_count - booked_count
    if available < len(passengers_data):
        raise ValidationError(
            {
                "passengers": (
                    f"Only {max(available, 0)} seat(s) remaining in {seat_config.seat_type.name}."
                )
            }
        )

    discount = None
    if discount_code:
        try:
            discount = Discount.objects.get(code__iexact=discount_code.strip())
        except Discount.DoesNotExist as exc:
            raise ValidationError({"discount_code": "Invalid discount code."}) from exc
        if not discount.is_valid_now():
            raise ValidationError({"discount_code": "Discount code has expired or is inactive."})

    # Provision or reuse customer account
    email_normalized = contact_email.strip().lower()
    if authenticated_user and authenticated_user.is_authenticated and authenticated_user.role == UserRole.CUSTOMER:
        user = authenticated_user
    else:
        user, created = User.objects.get_or_create(
            email=email_normalized,
            defaults={
                "first_name": passengers_data[0].get("first_name", ""),
                "last_name": passengers_data[0].get("last_name", ""),
                "role": UserRole.CUSTOMER,
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        CustomerProfile.objects.get_or_create(user=user)

    selected_options = list(Option.objects.filter(id__in=(option_ids or []), is_active=True))
    unit_base_fare = (flight.base_price * seat_config.seat_type.price_multiplier).quantize(
        Decimal("0.01")
    )

    booking = Booking.objects.create(
        user=user,
        contact_email=email_normalized,
        discount=discount,
        status=BookingStatus.RESERVED,
    )

    for idx, pdata in enumerate(passengers_data):
        passenger = Passenger.objects.create(
            first_name=pdata["first_name"],
            last_name=pdata["last_name"],
            document_number=pdata["document_number"],
            date_of_birth=pdata.get("date_of_birth"),
        )
        options_sum = sum((opt.price for opt in selected_options), Decimal("0.00"))
        seat_number = _allocate_seat_number(flight, seat_config.seat_type, idx)
        ticket = Ticket.objects.create(
            booking=booking,
            flight=flight,
            passenger=passenger,
            seat_type=seat_config.seat_type,
            seat_number=seat_number,
            base_fare=unit_base_fare,
            options_total=options_sum.quantize(Decimal("0.01")),
            status=TicketStatus.RESERVED,
        )
        for opt in selected_options:
            TicketOption.objects.create(
                ticket=ticket,
                option=opt,
                quantity=1,
                unit_price=opt.price,
                added_stage=AddedStage.BOOKING,
            )

    booking.recalculate_totals()
    return booking


@transaction.atomic
def online_check_in(*, ticket_code: str, user: User) -> Ticket:
    try:
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("booking", "flight", "passenger", "seat_type")
            .get(ticket_code__iexact=ticket_code.strip())
        )
    except Ticket.DoesNotExist as exc:
        raise ValidationError({"ticket_code": "Ticket not found."}) from exc

    if ticket.booking.user_id != user.id:
        raise ValidationError({"ticket_code": "You can only check in your own tickets."})
    if ticket.flight.status == FlightStatus.CANCELLED:
        raise ValidationError({"flight": "Cannot check in for a cancelled flight."})
    if ticket.status != TicketStatus.PAID:
        raise ValidationError(
            {"status": f"Ticket cannot be checked in from status '{ticket.status}'."}
        )

    ticket.status = TicketStatus.CHECKED_IN
    ticket.checked_in_at = timezone.now()
    ticket.checked_in_by = user
    ticket.save(update_fields=["status", "checked_in_at", "checked_in_by"])

    publish_domain_event(
        "passenger.checked_in",
        {
            "ticket_code": ticket.ticket_code,
            "flight_number": ticket.flight.flight_number,
            "passenger": ticket.passenger.full_name,
            "seat_number": ticket.seat_number,
            "channel": "ONLINE",
        },
    )
    return ticket


@transaction.atomic
def staff_check_in(
    *,
    ticket_code: str,
    staff_user: User,
    option_ids: list | None = None,
    luggage_fee: Decimal = Decimal("0.00"),
) -> Ticket:
    try:
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("booking", "flight", "passenger", "seat_type")
            .get(ticket_code__iexact=ticket_code.strip())
        )
    except Ticket.DoesNotExist as exc:
        raise ValidationError({"ticket_code": "Ticket not found."}) from exc

    if ticket.flight.status == FlightStatus.CANCELLED:
        raise ValidationError({"flight": "Cannot check in for a cancelled flight."})
    if ticket.status not in (TicketStatus.PAID, TicketStatus.CHECKED_IN):
        raise ValidationError(
            {"status": f"Ticket must be PAID or CHECKED_IN (current: {ticket.status})."}
        )

    luggage_fee = Decimal(luggage_fee or 0)
    if luggage_fee < 0:
        raise ValidationError({"luggage_fee": "Luggage fee cannot be negative."})

    added_options_total = Decimal("0.00")
    if option_ids:
        options = list(Option.objects.filter(id__in=option_ids, is_active=True))
        for opt in options:
            TicketOption.objects.create(
                ticket=ticket,
                option=opt,
                quantity=1,
                unit_price=opt.price,
                added_stage=AddedStage.CHECKIN,
            )
            added_options_total += opt.price

    ticket.options_total = (ticket.options_total + added_options_total).quantize(Decimal("0.01"))
    ticket.luggage_fee = (ticket.luggage_fee + luggage_fee).quantize(Decimal("0.01"))
    ticket.status = TicketStatus.CHECKED_IN
    if not ticket.checked_in_at:
        ticket.checked_in_at = timezone.now()
    ticket.checked_in_by = staff_user
    ticket.save(
        update_fields=["options_total", "luggage_fee", "status", "checked_in_at", "checked_in_by"]
    )
    ticket.booking.recalculate_totals()

    publish_domain_event(
        "passenger.checked_in",
        {
            "ticket_code": ticket.ticket_code,
            "flight_number": ticket.flight.flight_number,
            "passenger": ticket.passenger.full_name,
            "seat_number": ticket.seat_number,
            "luggage_fee": str(ticket.luggage_fee),
            "channel": "COUNTER",
            "staff": staff_user.email,
        },
    )
    return ticket


@transaction.atomic
def staff_board_passenger(*, ticket_code: str, staff_user: User) -> Ticket:
    try:
        ticket = (
            Ticket.objects.select_for_update()
            .select_related("booking", "flight", "passenger", "seat_type")
            .get(ticket_code__iexact=ticket_code.strip())
        )
    except Ticket.DoesNotExist as exc:
        raise ValidationError({"ticket_code": "Ticket not found."}) from exc

    if ticket.flight.status == FlightStatus.CANCELLED:
        raise ValidationError({"flight": "Cannot board a cancelled flight."})
    if ticket.status == TicketStatus.BOARDED:
        raise ValidationError({"status": "Passenger is already boarded."})
    if ticket.status != TicketStatus.CHECKED_IN:
        raise ValidationError(
            {"status": f"Passenger must be checked in before boarding (current: {ticket.status})."}
        )

    ticket.status = TicketStatus.BOARDED
    ticket.boarded_at = timezone.now()
    ticket.boarded_by = staff_user
    ticket.save(update_fields=["status", "boarded_at", "boarded_by"])

    publish_domain_event(
        "passenger.boarded",
        {
            "ticket_code": ticket.ticket_code,
            "flight_number": ticket.flight.flight_number,
            "gate": ticket.flight.gate,
            "passenger": ticket.passenger.full_name,
            "seat_number": ticket.seat_number,
            "staff": staff_user.email,
        },
    )
    return ticket
