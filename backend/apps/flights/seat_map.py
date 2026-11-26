import secrets
from dataclasses import dataclass

from django.core.cache import cache

from apps.flights.models import Flight

DEFAULT_SEAT_HOLD_TTL_SECONDS = 600  # 10 minutes
SEAT_HOLD_KEY_PREFIX = "djangoair:seat_hold"


class SeatHoldConflictError(Exception):
    """Raised when a requested seat is occupied, invalid, or held by another session."""


@dataclass
class CabinLayout:
    seats: list[dict]
    seat_lookup: dict[str, dict]
    rows: list[dict]


def _hold_cache_key(flight_id: str, seat_number: str) -> str:
    return f"{SEAT_HOLD_KEY_PREFIX}:{flight_id}:{seat_number.upper()}"


def _columns_for_cabin(seat_type_code: str) -> tuple[list[str], int]:
    """Return (column letters, aisle_after_index) for a cabin class."""
    code = seat_type_code.upper()
    if code in ("FIRST", "BUSINESS"):
        return ["A", "B", "C", "D"], 2
    return ["A", "B", "C", "D", "E", "F"], 3


def generate_cabin_layout(flight: Flight) -> CabinLayout:
    """Deterministically build the aircraft's cabin seat map from AirplaneSeatConfig."""
    from decimal import Decimal

    configs = sorted(
        flight.airplane.seat_configs.select_related("seat_type").all(),
        key=lambda cfg: (-cfg.seat_type.price_multiplier, cfg.seat_type.code),
    )

    seats: list[dict] = []
    seat_lookup: dict[str, dict] = {}
    rows: list[dict] = []
    current_row = 1

    for cfg in configs:
        columns, aisle_after = _columns_for_cabin(cfg.seat_type.code)
        unit_price = str(
            (flight.base_price * cfg.seat_type.price_multiplier).quantize(Decimal("0.01"))
        )
        placed = 0
        while placed < cfg.seat_count:
            row_seats: list[dict] = []
            for col in columns:
                if placed >= cfg.seat_count:
                    break
                seat_number = f"{current_row}{col}"
                seat_info = {
                    "seat_number": seat_number,
                    "row": current_row,
                    "column": col,
                    "seat_type_id": str(cfg.seat_type.id),
                    "seat_type_code": cfg.seat_type.code,
                    "seat_type_name": cfg.seat_type.name,
                    "unit_price": unit_price,
                }
                seats.append(seat_info)
                seat_lookup[seat_number] = seat_info
                row_seats.append(seat_info)
                placed += 1
            rows.append(
                {
                    "row_number": current_row,
                    "seat_type_id": str(cfg.seat_type.id),
                    "seat_type_code": cfg.seat_type.code,
                    "seat_type_name": cfg.seat_type.name,
                    "aisle_after": aisle_after,
                    "seats": row_seats,
                }
            )
            current_row += 1

    return CabinLayout(seats=seats, seat_lookup=seat_lookup, rows=rows)


def _occupied_seat_numbers(flight: Flight) -> set[str]:
    from apps.bookings.models import Ticket, TicketStatus

    return {
        s.upper()
        for s in Ticket.objects.filter(flight=flight)
        .exclude(status=TicketStatus.CANCELLED)
        .values_list("seat_number", flat=True)
    }


def _active_holds_map(flight_id: str, seat_numbers: list[str]) -> dict[str, str]:
    """Batch-read all active seat hold tokens from Redis/Django cache."""
    if not seat_numbers:
        return {}
    key_to_seat = {_hold_cache_key(flight_id, s): s for s in seat_numbers}
    cached = cache.get_many(list(key_to_seat.keys()))
    return {key_to_seat[k]: str(v) for k, v in cached.items() if v}


def get_flight_seat_map(flight: Flight, hold_token: str | None = None) -> dict:
    """Return full interactive cabin seat map with live occupied and Redis-held states."""
    layout = generate_cabin_layout(flight)
    occupied = _occupied_seat_numbers(flight)
    flight_id = str(flight.id)
    holds = _active_holds_map(flight_id, list(layout.seat_lookup.keys()))

    available_count = 0
    held_count = 0
    occupied_count = 0

    enriched_rows = []
    for row in layout.rows:
        enriched_seats = []
        for seat in row["seats"]:
            sn = seat["seat_number"]
            holder = holds.get(sn)
            if sn in occupied:
                seat_status = "OCCUPIED"
                occupied_count += 1
            elif holder:
                seat_status = "HELD_BY_ME" if (hold_token and holder == hold_token) else "HELD"
                held_count += 1
            else:
                seat_status = "AVAILABLE"
                available_count += 1
            enriched_seats.append({**seat, "status": seat_status})
        enriched_rows.append({**row, "seats": enriched_seats})

    return {
        "flight_id": flight_id,
        "flight_number": flight.flight_number,
        "airplane": flight.airplane.model_name,
        "hold_ttl_seconds": DEFAULT_SEAT_HOLD_TTL_SECONDS,
        "summary": {
            "total": len(layout.seats),
            "available": available_count,
            "held": held_count,
            "occupied": occupied_count,
        },
        "rows": enriched_rows,
    }


def hold_seats(
    *,
    flight: Flight,
    seat_numbers: list[str],
    hold_token: str | None = None,
    ttl_seconds: int = DEFAULT_SEAT_HOLD_TTL_SECONDS,
) -> dict:
    """Atomically place a TTL hold on one or more seats in Redis/cache."""
    cleaned = [s.strip().upper() for s in seat_numbers if s and s.strip()]
    if not cleaned:
        raise SeatHoldConflictError("At least one seat_number is required.")

    token = (hold_token or "").strip() or f"HOLD-{secrets.token_hex(8)}"
    ttl = max(30, min(int(ttl_seconds), 1800))
    layout = generate_cabin_layout(flight)
    occupied = _occupied_seat_numbers(flight)
    flight_id = str(flight.id)

    for sn in cleaned:
        if sn not in layout.seat_lookup:
            raise SeatHoldConflictError(f"Seat {sn} does not exist on flight {flight.flight_number}.")
        if sn in occupied:
            raise SeatHoldConflictError(f"Seat {sn} is already booked.")

    newly_acquired: list[str] = []
    try:
        for sn in cleaned:
            key = _hold_cache_key(flight_id, sn)
            if cache.add(key, token, timeout=ttl):
                newly_acquired.append(key)
            else:
                current_holder = cache.get(key)
                if current_holder == token:
                    cache.set(key, token, timeout=ttl)
                else:
                    raise SeatHoldConflictError(
                        f"Seat {sn} is currently held by another passenger."
                    )
    except SeatHoldConflictError:
        for key in newly_acquired:
            if cache.get(key) == token:
                cache.delete(key)
        raise

    return {
        "flight_id": flight_id,
        "hold_token": token,
        "held_seats": cleaned,
        "expires_in_seconds": ttl,
    }


def release_seats(*, flight_id: str, seat_numbers: list[str], hold_token: str) -> dict:
    """Release seat holds owned by hold_token."""
    released: list[str] = []
    for raw in seat_numbers:
        sn = raw.strip().upper()
        key = _hold_cache_key(flight_id, sn)
        if cache.get(key) == hold_token:
            cache.delete(key)
            released.append(sn)
    return {"flight_id": flight_id, "released_seats": released}


def verify_and_pick_seats(
    *,
    flight: Flight,
    seat_type_id: str,
    requested_seats: list[str | None],
    hold_token: str | None = None,
) -> tuple[list[str], list[str]]:
    """Validate explicit seat picks (or auto-assign available seats) for a booking leg.

    Returns (assigned_seat_numbers, cache_keys_to_release_after_commit).
    """
    layout = generate_cabin_layout(flight)
    occupied = _occupied_seat_numbers(flight)
    flight_id = str(flight.id)
    holds = _active_holds_map(flight_id, list(layout.seat_lookup.keys()))

    assigned: list[str] = []
    used_in_booking: set[str] = set()
    keys_to_release: list[str] = []

    # Candidate auto-assign pool for this cabin class (unoccupied & not held by others)
    cabin_pool = [
        s["seat_number"]
        for s in layout.seats
        if s["seat_type_id"] == str(seat_type_id) and s["seat_number"] not in occupied
    ]

    for req in requested_seats:
        if req and req.strip():
            sn = req.strip().upper()
            info = layout.seat_lookup.get(sn)
            if not info:
                raise SeatHoldConflictError(
                    f"Seat {sn} does not exist on flight {flight.flight_number}."
                )
            if info["seat_type_id"] != str(seat_type_id):
                raise SeatHoldConflictError(
                    f"Seat {sn} belongs to {info['seat_type_name']}, not the selected cabin class."
                )
            if sn in occupied or sn in used_in_booking:
                raise SeatHoldConflictError(f"Seat {sn} is already taken.")
            holder = holds.get(sn)
            if holder and holder != hold_token:
                raise SeatHoldConflictError(
                    f"Seat {sn} is temporarily held by another passenger."
                )
            assigned.append(sn)
            used_in_booking.add(sn)
            if holder and holder == hold_token:
                keys_to_release.append(_hold_cache_key(flight_id, sn))
        else:
            # Prefer unheld seats first, then own-held seats
            picked = next(
                (
                    sn
                    for sn in cabin_pool
                    if sn not in used_in_booking
                    and (sn not in holds or (hold_token and holds[sn] == hold_token))
                ),
                None,
            )
            if picked is None:
                # Fallback to any unoccupied seat in cabin if holds exceed remaining
                picked = next(
                    (sn for sn in cabin_pool if sn not in used_in_booking),
                    None,
                )
            if picked is None:
                raise SeatHoldConflictError("No available seats remain in the selected cabin.")
            assigned.append(picked)
            used_in_booking.add(picked)
            if holds.get(picked) == hold_token:
                keys_to_release.append(_hold_cache_key(flight_id, picked))

    return assigned, keys_to_release
