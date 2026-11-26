from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.fleet.models import AirplaneSeatConfig
from apps.flights.models import Flight, FlightStatus, Option
from apps.flights.seat_map import SeatHoldConflictError, verify_and_pick_seats
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


def _validate_leg_and_pick_seats(
    *,
    flight: Flight,
    seat_type_id,
    passengers_count: int,
    requested_seats: list[str | None],
    hold_token: str | None,
    leg_label: str,
) -> tuple[AirplaneSeatConfig, list[str], list[str]]:
    if flight.status != FlightStatus.SCHEDULED:
        raise ValidationError({leg_label: "This flight is not open for booking."})

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
    if available < passengers_count:
        raise ValidationError(
            {
                "passengers": (
                    f"Only {max(available, 0)} seat(s) remaining in {seat_config.seat_type.name}."
                )
            }
        )

    try:
        assigned, keys_to_release = verify_and_pick_seats(
            flight=flight,
            seat_type_id=str(seat_type_id),
            requested_seats=requested_seats,
            hold_token=hold_token,
        )
    except SeatHoldConflictError as exc:
        raise ValidationError({"seat_number": str(exc)}) from exc

    return seat_config, assigned, keys_to_release


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
    return_flight_id=None,
    return_seat_type_id=None,
    hold_token: str | None = None,
    return_hold_token: str | None = None,
) -> Booking:
    if not passengers_data:
        raise ValidationError({"passengers": "At least one passenger is required."})

    if return_flight_id and str(return_flight_id) == str(flight_id):
        raise ValidationError({"return_flight_id": "Return flight must differ from outbound flight."})

    # Acquire row-level locks on Flight(s) in deterministic UUID order to prevent deadlocks
    lock_ids = sorted({str(flight_id), *([str(return_flight_id)] if return_flight_id else [])})
    locked_flights = {
        str(f.id): f
        for f in Flight.objects.select_for_update()
        .select_related("airplane", "origin", "destination")
        .filter(pk__in=lock_ids)
        .order_by("id")
    }
    if str(flight_id) not in locked_flights:
        raise ValidationError({"flight_id": "Outbound flight not found."})
    flight = locked_flights[str(flight_id)]

    return_flight: Flight | None = None
    if return_flight_id:
        if str(return_flight_id) not in locked_flights:
            raise ValidationError({"return_flight_id": "Return flight not found."})
        return_flight = locked_flights[str(return_flight_id)]
        if return_flight.departure_time <= flight.departure_time:
            raise ValidationError(
                {"return_flight_id": "Return flight must depart after the outbound flight."}
            )

    outbound_requests = [pdata.get("seat_number") for pdata in passengers_data]
    seat_config, outbound_seats, release_keys = _validate_leg_and_pick_seats(
        flight=flight,
        seat_type_id=seat_type_id,
        passengers_count=len(passengers_data),
        requested_seats=outbound_requests,
        hold_token=hold_token,
        leg_label="flight",
    )

    return_seat_config: AirplaneSeatConfig | None = None
    return_seats: list[str] = []
    if return_flight is not None:
        effective_ret_seat_type = return_seat_type_id or seat_type_id
        ret_requests = [pdata.get("return_seat_number") for pdata in passengers_data]
        return_seat_config, return_seats, ret_release_keys = _validate_leg_and_pick_seats(
            flight=return_flight,
            seat_type_id=effective_ret_seat_type,
            passengers_count=len(passengers_data),
            requested_seats=ret_requests,
            hold_token=return_hold_token or hold_token,
            leg_label="return_flight",
        )
        release_keys.extend(ret_release_keys)

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
    options_sum = sum((opt.price for opt in selected_options), Decimal("0.00")).quantize(
        Decimal("0.01")
    )
    unit_base_fare = (flight.base_price * seat_config.seat_type.price_multiplier).quantize(
        Decimal("0.01")
    )

    booking = Booking.objects.create(
        user=user,
        contact_email=email_normalized,
        discount=discount,
        status=BookingStatus.RESERVED,
    )

    passengers: list[Passenger] = []
    for idx, pdata in enumerate(passengers_data):
        passenger = Passenger.objects.create(
            first_name=pdata["first_name"],
            last_name=pdata["last_name"],
            document_number=pdata["document_number"],
            date_of_birth=pdata.get("date_of_birth"),
        )
        passengers.append(passenger)
        ticket = Ticket.objects.create(
            booking=booking,
            flight=flight,
            passenger=passenger,
            seat_type=seat_config.seat_type,
            seat_number=outbound_seats[idx],
            base_fare=unit_base_fare,
            options_total=options_sum,
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

    if return_flight is not None and return_seat_config is not None:
        return_base_fare = (
            return_flight.base_price * return_seat_config.seat_type.price_multiplier
        ).quantize(Decimal("0.01"))
        for idx, passenger in enumerate(passengers):
            ret_ticket = Ticket.objects.create(
                booking=booking,
                flight=return_flight,
                passenger=passenger,
                seat_type=return_seat_config.seat_type,
                seat_number=return_seats[idx],
                base_fare=return_base_fare,
                options_total=options_sum,
                status=TicketStatus.RESERVED,
            )
            for opt in selected_options:
                TicketOption.objects.create(
                    ticket=ret_ticket,
                    option=opt,
                    quantity=1,
                    unit_price=opt.price,
                    added_stage=AddedStage.BOOKING,
                )

    if release_keys:
        transaction.on_commit(lambda keys=list(release_keys): cache.delete_many(keys))

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
