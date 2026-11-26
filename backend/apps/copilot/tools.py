from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.bookings.models import Ticket
from apps.flights.models import Flight, FlightStatus

from .rag import get_policy_kb

# OpenAI / Gemini compatible JSON-schema declarations for read-only Copilot tools.
# Security invariant: NONE of these tools mutate bookings, tickets, or balances.
COPILOT_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_passenger_tickets",
            "description": (
                "Inspect the authenticated passenger's tickets, flight statuses (including CANCELLED), "
                "routes, cabin classes, and base fares."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_code": {
                        "type": "string",
                        "description": "Optional specific ticket code (e.g. DA-12345678).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_alternative_flights",
            "description": (
                "Search scheduled DjangoAir flights on the same route with available seats "
                "for disruption rebooking or voluntary flight changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_code": {"type": "string", "description": "3-letter IATA origin code."},
                    "destination_code": {
                        "type": "string",
                        "description": "3-letter IATA destination code.",
                    },
                    "seat_type_code": {
                        "type": "string",
                        "description": "Preferred cabin code (e.g. ECO, BUS, FIRST).",
                    },
                    "exclude_flight_id": {
                        "type": "string",
                        "description": "Optional UUID of original flight to exclude.",
                    },
                    "original_fare": {
                        "type": "string",
                        "description": "Original ticket base fare as decimal string.",
                    },
                    "involuntary_cancellation": {
                        "type": "boolean",
                        "description": "True if original flight was cancelled by airline (waives fare diff).",
                    },
                },
                "required": ["origin_code", "destination_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_airline_policies",
            "description": (
                "Retrieve authoritative DjangoAir policy clauses (refunds, EU261/DOT disruption rights, "
                "free 72-hour rebooking waiver, baggage, seat holds, check-in deadlines)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Policy question or keywords."},
                    "top_k": {"type": "integer", "description": "Number of clauses to return (1-5)."},
                },
                "required": ["query"],
            },
        },
    },
]


def tool_lookup_passenger_tickets(user: User, ticket_code: str | None = None) -> list[dict]:
    qs = Ticket.objects.select_related(
        "booking", "flight__origin", "flight__destination", "seat_type", "passenger"
    ).order_by("-flight__departure_time")

    if user.role == UserRole.CUSTOMER and not user.is_superuser:
        qs = qs.filter(booking__user=user)
    if ticket_code:
        qs = qs.filter(ticket_code__iexact=ticket_code.strip())

    results = []
    for t in qs[:10]:
        results.append(
            {
                "ticket_id": str(t.id),
                "ticket_code": t.ticket_code,
                "booking_reference": t.booking.booking_reference,
                "ticket_status": t.status,
                "flight_id": str(t.flight.id),
                "flight_number": t.flight.flight_number,
                "flight_status": t.flight.status,
                "origin": t.flight.origin.code,
                "destination": t.flight.destination.code,
                "departure_time": t.flight.departure_time.isoformat(),
                "seat_type_id": str(t.seat_type.id),
                "seat_type_code": t.seat_type.code,
                "seat_type_name": t.seat_type.name,
                "seat_number": t.seat_number,
                "base_fare": str(t.base_fare),
                "passenger_name": t.passenger.full_name,
            }
        )
    return results


def tool_find_alternative_flights(
    *,
    origin_code: str,
    destination_code: str,
    seat_type_code: str = "",
    exclude_flight_id: str = "",
    original_fare: str = "0.00",
    involuntary_cancellation: bool = False,
) -> list[dict]:
    qs = (
        Flight.objects.select_related("origin", "destination", "airplane")
        .prefetch_related("airplane__seat_configs__seat_type")
        .filter(
            status=FlightStatus.SCHEDULED,
            origin__code__iexact=origin_code.strip(),
            destination__code__iexact=destination_code.strip(),
            departure_time__gte=timezone.now(),
        )
        .order_by("departure_time")
    )
    if exclude_flight_id:
        qs = qs.exclude(pk=exclude_flight_id)

    flights = Flight.attach_booked_counts(list(qs[:10]))
    orig_dec = Decimal(original_fare or "0.00")
    candidates: list[dict] = []

    for flight in flights:
        avail_list = flight.seat_availability()
        preferred = None
        if seat_type_code:
            preferred = next(
                (
                    s
                    for s in avail_list
                    if s["seat_type_code"].upper() == seat_type_code.upper()
                    and s["available_seats"] >= 1
                ),
                None,
            )
        if preferred is None:
            preferred = next((s for s in avail_list if s["available_seats"] >= 1), None)
        if preferred is None:
            continue

        new_fare = Decimal(preferred["unit_price"])
        fare_diff = (
            Decimal("0.00")
            if involuntary_cancellation
            else max(new_fare - orig_dec, Decimal("0.00"))
        )
        candidates.append(
            {
                "flight_id": str(flight.id),
                "flight_number": flight.flight_number,
                "origin": flight.origin.code,
                "destination": flight.destination.code,
                "departure_time": flight.departure_time.isoformat(),
                "arrival_time": flight.arrival_time.isoformat(),
                "gate": flight.gate,
                "seat_type_id": preferred["seat_type_id"],
                "seat_type_code": preferred["seat_type_code"],
                "seat_type_name": preferred["seat_type_name"],
                "available_seats": preferred["available_seats"],
                "unit_price": preferred["unit_price"],
                "fee_waived": involuntary_cancellation,
                "fare_difference": str(fare_diff.quantize(Decimal("0.01"))),
            }
        )
    return candidates[:5]


def tool_search_airline_policies(query: str, top_k: int = 3) -> list[dict]:
    return get_policy_kb().search(query=query, top_k=top_k)


def execute_copilot_tool(name: str, arguments: dict, *, user: User) -> dict:
    """Safely dispatch a read-only Copilot tool call and return a JSON-serializable payload."""
    if name == "lookup_passenger_tickets":
        tickets = tool_lookup_passenger_tickets(user, ticket_code=arguments.get("ticket_code"))
        return {"tickets": tickets}
    if name == "find_alternative_flights":
        alts = tool_find_alternative_flights(
            origin_code=str(arguments.get("origin_code", "")),
            destination_code=str(arguments.get("destination_code", "")),
            seat_type_code=str(arguments.get("seat_type_code", "")),
            exclude_flight_id=str(arguments.get("exclude_flight_id", "")),
            original_fare=str(arguments.get("original_fare", "0.00")),
            involuntary_cancellation=bool(arguments.get("involuntary_cancellation", False)),
        )
        return {"alternatives": alts}
    if name == "search_airline_policies":
        clauses = tool_search_airline_policies(
            query=str(arguments.get("query", "")),
            top_k=int(arguments.get("top_k", 3) or 3),
        )
        return {"citations": clauses}
    return {"error": f"Unknown tool: {name}"}
