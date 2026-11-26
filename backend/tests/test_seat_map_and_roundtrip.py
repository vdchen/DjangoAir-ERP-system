from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.flights.models import Flight, FlightStatus


@pytest.mark.django_db
def test_seat_map_and_atomic_ttl_seat_holds_lifecycle(api_client, flight_setup):
    cache.clear()
    flight = flight_setup["flight"]
    eco = flight_setup["eco"]
    biz = flight_setup["bus"]

    # 1. Fetch interactive cabin seat map
    map_resp = api_client.get(f"/api/v1/flights/{flight.id}/seat-map/")
    assert map_resp.status_code == 200
    assert map_resp.data["flight_number"] == flight.flight_number
    assert map_resp.data["summary"]["total"] == 5  # 2 business + 3 economy in fixture
    assert map_resp.data["summary"]["available"] == 5

    # Find Business and Economy seats from the generated layout
    biz_seats = [
        s["seat_number"]
        for r in map_resp.data["rows"]
        for s in r["seats"]
        if s["seat_type_id"] == str(biz.id)
    ]
    eco_seats = [
        s["seat_number"]
        for r in map_resp.data["rows"]
        for s in r["seats"]
        if s["seat_type_id"] == str(eco.id)
    ]
    assert len(biz_seats) == 2
    assert len(eco_seats) == 3

    seat_a, seat_b, seat_c = eco_seats[0], eco_seats[1], eco_seats[2]

    # 2. Shopper A places TTL holds on seat_a and seat_b
    hold_a = api_client.post(
        f"/api/v1/flights/{flight.id}/seat-holds/",
        {"seat_numbers": [seat_a, seat_b], "ttl_seconds": 300},
        format="json",
    )
    assert hold_a.status_code == 200
    token_a = hold_a.data["hold_token"]
    assert hold_a.data["held_seats"] == [seat_a, seat_b]

    # Map shows HELD_BY_ME for Shopper A and HELD for Shopper B
    map_a = api_client.get(f"/api/v1/flights/{flight.id}/seat-map/?hold_token={token_a}")
    statuses_a = {s["seat_number"]: s["status"] for r in map_a.data["rows"] for s in r["seats"]}
    assert statuses_a[seat_a] == "HELD_BY_ME"

    map_b = api_client.get(f"/api/v1/flights/{flight.id}/seat-map/?hold_token=OTHER-TOKEN")
    statuses_b = {s["seat_number"]: s["status"] for r in map_b.data["rows"] for s in r["seats"]}
    assert statuses_b[seat_a] == "HELD"

    # 3. Shopper B tries to hold [seat_c, seat_a] -> 409 Conflict AND seat_c is atomically rolled back!
    conflict = api_client.post(
        f"/api/v1/flights/{flight.id}/seat-holds/",
        {"seat_numbers": [seat_c, seat_a], "hold_token": "OTHER-TOKEN"},
        format="json",
    )
    assert conflict.status_code == 409

    map_after_conflict = api_client.get(f"/api/v1/flights/{flight.id}/seat-map/")
    statuses_after = {
        s["seat_number"]: s["status"] for r in map_after_conflict.data["rows"] for s in r["seats"]
    }
    assert statuses_after[seat_c] == "AVAILABLE"

    # 4. Shopper B cannot book Shopper A's held seat without token_a
    steal_resp = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(eco.id),
            "contact_email": "thief@example.com",
            "passengers": [
                {
                    "first_name": "Bad",
                    "last_name": "Actor",
                    "document_number": "BA1",
                    "seat_number": seat_a,
                }
            ],
        },
        format="json",
    )
    assert steal_resp.status_code == 400

    # 5. Wrong cabin class seat pick (Business seat in Economy booking) -> 400
    wrong_cabin = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(eco.id),
            "contact_email": "wrong@example.com",
            "passengers": [
                {
                    "first_name": "W",
                    "last_name": "C",
                    "document_number": "WC1",
                    "seat_number": biz_seats[0],
                }
            ],
        },
        format="json",
    )
    assert wrong_cabin.status_code == 400

    # 6. Shopper A books seat_a with token_a -> 201 and seat_a becomes OCCUPIED
    book_a = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(flight.id),
            "seat_type_id": str(eco.id),
            "hold_token": token_a,
            "contact_email": "shoppera@example.com",
            "passengers": [
                {
                    "first_name": "Shopper",
                    "last_name": "A",
                    "document_number": "SA1",
                    "seat_number": seat_a,
                }
            ],
        },
        format="json",
    )
    assert book_a.status_code == 201
    assert book_a.data["tickets"][0]["seat_number"] == seat_a

    # Attempting to hold already-booked seat_a -> 409 Conflict
    hold_occupied = api_client.post(
        f"/api/v1/flights/{flight.id}/seat-holds/",
        {"seat_numbers": [seat_a]},
        format="json",
    )
    assert hold_occupied.status_code == 409

    # 7. Shopper A releases seat_b via DELETE -> becomes AVAILABLE again
    rel = api_client.delete(
        f"/api/v1/flights/{flight.id}/seat-holds/",
        {"seat_numbers": [seat_b], "hold_token": token_a},
        format="json",
    )
    assert rel.status_code == 200
    assert rel.data["released_seats"] == [seat_b]

    map_final = api_client.get(f"/api/v1/flights/{flight.id}/seat-map/")
    statuses_final = {
        s["seat_number"]: s["status"] for r in map_final.data["rows"] for s in r["seats"]
    }
    assert statuses_final[seat_a] == "OCCUPIED"
    assert statuses_final[seat_b] == "AVAILABLE"


@pytest.mark.django_db
def test_round_trip_search_and_multi_leg_booking_with_seat_picks(api_client, flight_setup):
    cache.clear()
    outbound = flight_setup["flight"]
    eco = flight_setup["eco"]
    biz = flight_setup["bus"]
    lunch = flight_setup["lunch"]

    # Create a matching return flight (LHR -> JFK) 3 days after outbound
    ret_dep = outbound.departure_time + timedelta(days=3)
    return_flight = Flight.objects.create(
        flight_number="DA102-RET",
        origin=outbound.destination,
        destination=outbound.origin,
        airplane=outbound.airplane,
        departure_time=ret_dep,
        arrival_time=ret_dep + timedelta(hours=7),
        base_price=Decimal("410.00"),
        gate="B14",
        status=FlightStatus.SCHEDULED,
    )
    return_flight.available_options.set([lunch])

    out_date = outbound.departure_time.strftime("%Y-%m-%d")
    ret_date = return_flight.departure_time.strftime("%Y-%m-%d")

    # 1. Round-trip search returns structured {trip_type, outbound, return}
    search = api_client.get(
        f"/api/v1/flights/search/?origin=JFK&destination=LHR&date={out_date}&return_date={ret_date}&passengers=1"
    )
    assert search.status_code == 200
    assert search.data["trip_type"] == "round_trip"
    assert any(f["id"] == str(outbound.id) for f in search.data["outbound"])
    assert any(f["id"] == str(return_flight.id) for f in search.data["return"])

    # 2. Invalid return flight (same as outbound or earlier departure) -> 400
    same_leg = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(outbound.id),
            "seat_type_id": str(eco.id),
            "return_flight_id": str(outbound.id),
            "contact_email": "rt@example.com",
            "passengers": [{"first_name": "R", "last_name": "T", "document_number": "RT1"}],
        },
        format="json",
    )
    assert same_leg.status_code == 400

    earlier_flight = Flight.objects.create(
        flight_number="DA099-EARLY",
        origin=outbound.destination,
        destination=outbound.origin,
        airplane=outbound.airplane,
        departure_time=timezone.now() + timedelta(hours=2),
        arrival_time=timezone.now() + timedelta(hours=9),
        base_price=Decimal("300.00"),
        gate="C1",
        status=FlightStatus.SCHEDULED,
    )
    bad_order = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(outbound.id),
            "seat_type_id": str(eco.id),
            "return_flight_id": str(earlier_flight.id),
            "contact_email": "rt@example.com",
            "passengers": [{"first_name": "R", "last_name": "T", "document_number": "RT1"}],
        },
        format="json",
    )
    assert bad_order.status_code == 400

    # 3. Valid round-trip booking with explicit outbound (Economy) & return (Business) seats
    out_map = api_client.get(f"/api/v1/flights/{outbound.id}/seat-map/").data
    ret_map = api_client.get(f"/api/v1/flights/{return_flight.id}/seat-map/").data
    out_seat = next(
        s["seat_number"] for r in out_map["rows"] for s in r["seats"] if s["seat_type_id"] == str(eco.id)
    )
    ret_seat = next(
        s["seat_number"] for r in ret_map["rows"] for s in r["seats"] if s["seat_type_id"] == str(biz.id)
    )

    rt_booking = api_client.post(
        "/api/v1/bookings/",
        {
            "flight_id": str(outbound.id),
            "seat_type_id": str(eco.id),
            "return_flight_id": str(return_flight.id),
            "return_seat_type_id": str(biz.id),
            "contact_email": "roundtrip@example.com",
            "option_ids": [str(lunch.id)],
            "passengers": [
                {
                    "first_name": "Clara",
                    "last_name": "Roundtrip",
                    "document_number": "CR9988",
                    "seat_number": out_seat,
                    "return_seat_number": ret_seat,
                }
            ],
        },
        format="json",
    )
    assert rt_booking.status_code == 201
    tickets = rt_booking.data["tickets"]
    assert len(tickets) == 2
    seats_by_flight = {t["flight_number"]: t["seat_number"] for t in tickets}
    assert seats_by_flight[outbound.flight_number] == out_seat
    assert seats_by_flight[return_flight.flight_number] == ret_seat

    # Expected total: outbound (200 + 20) + return (410 * 2.0 + 20) = 220 + 840 = 1060.00
    assert Decimal(rt_booking.data["total_amount"]) == Decimal("1060.00")

    # 4. Charge round-trip booking via emulated payment -> both tickets transition to PAID
    pay_resp = api_client.post(
        "/api/v1/payments/charge/",
        {
            "booking_reference": rt_booking.data["booking_reference"],
            "payment_method": "CARD",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "424",
            "cardholder_name": "Clara Roundtrip",
        },
        format="json",
    )
    assert pay_resp.status_code == 200
    assert all(t["status"] == "PAID" for t in pay_resp.data["booking"]["tickets"])
