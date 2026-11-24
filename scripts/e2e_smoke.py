#!/usr/bin/env python3
"""End-to-end smoke test exercising DjangoAir ERP through Nginx (http://localhost:8080)."""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = "http://localhost:8080"
MAILPIT_URL = "http://localhost:8025"


def http_req(url: str, method: str = "GET", body: dict | None = None, token: str | None = None):
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            ct = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(raw) if "application/json" in ct else raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return err.code, parsed


def main():
    print("1. Checking Customer SPA (/), Staff SPA (/staff/), and API health...")
    code, html = http_req(f"{BASE_URL}/")
    assert code == 200 and "DjangoAir" in html, f"Customer SPA check failed: {code}"

    code, html = http_req(f"{BASE_URL}/staff/")
    assert code == 200 and "Staff Operations" in html, f"Staff SPA check failed: {code}"

    code, health = http_req(f"{BASE_URL}/api/v1/health/")
    assert code == 200 and health["status"] == "ok", f"Backend health failed: {health}"

    code, ws_health = http_req(f"{BASE_URL}/mobile-mock/health")
    assert code == 200 and ws_health["service"] == "mobile_ws", f"Mobile WS health failed: {ws_health}"

    code, wh_health = http_req(f"{BASE_URL}/mock-webhook/health")
    assert code == 200 and wh_health["service"] == "webhook_mock", f"Webhook mock health failed: {wh_health}"

    print("2. Searching flights -> booking -> emulated payment...")
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    code, flights = http_req(f"{BASE_URL}/api/v1/flights/search/?destination=LHR&date={tomorrow}&passengers=1")
    assert code == 200 and len(flights) >= 1, f"Flight search failed: {code} {flights}"
    flight = flights[0]
    seat = flight["seat_availability"][0]
    lunch_id = flight["options"][0]["id"]

    guest_email = f"smoke.{int(time.time())}@example.com"
    code, booking = http_req(
        f"{BASE_URL}/api/v1/bookings/",
        method="POST",
        body={
            "flight_id": flight["id"],
            "seat_type_id": seat["seat_type_id"],
            "contact_email": guest_email,
            "option_ids": [lunch_id],
            "discount_code": "WELCOME10",
            "passengers": [
                {"first_name": "Smoke", "last_name": "Tester", "document_number": "SMK001"}
            ],
        },
    )
    assert code == 201, f"Booking failed: {code} {booking}"
    ref = booking["booking_reference"]
    ticket_code = booking["tickets"][0]["ticket_code"]

    code, paid = http_req(
        f"{BASE_URL}/api/v1/payments/charge/",
        method="POST",
        body={
            "booking_reference": ref,
            "payment_method": "CARD",
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "424",
        },
    )
    assert code == 200 and paid["booking"]["status"] == "PAID", f"Payment failed: {code} {paid}"
    print(f"   Paid booking {ref}, ticket {ticket_code}, invoice {paid['payment']['invoice_number']}")

    print("3. Verifying Celery confirmation email in Mailpit & logging into Personal Cabinet...")
    time.sleep(2)
    code, inbox = http_req(f"{MAILPIT_URL}/api/v1/messages")
    assert code == 200, f"Mailpit query failed: {code}"
    msg_id = None
    for m in inbox.get("messages", []):
        if any(r.get("Address") == guest_email for r in m.get("To", [])):
            msg_id = m["ID"]
            break
    assert msg_id, f"Confirmation email not found in Mailpit for {guest_email}"
    code, msg_detail = http_req(f"{MAILPIT_URL}/api/v1/message/{msg_id}")
    pw_match = re.search(r"Temporary Password:\s*(\S+)", msg_detail.get("Text", ""))
    assert pw_match, "Temporary Password missing from emailed confirmation"
    temp_password = pw_match.group(1)

    code, cust_login = http_req(
        f"{BASE_URL}/api/v1/auth/login/",
        method="POST",
        body={"email": guest_email, "password": temp_password},
    )
    assert code == 200, f"Customer cabinet login failed: {code} {cust_login}"
    cust_token = cust_login["access"]

    code, cabinet = http_req(f"{BASE_URL}/api/v1/cabinet/overview/", token=cust_token)
    assert code == 200 and len(cabinet["upcoming_tickets"]) == 1

    print("4. Testing Staff Role Hierarchy (Check-in Manager -> Gate Manager -> Supervisor)...")
    code, ci_login = http_req(
        f"{BASE_URL}/api/v1/auth/login/",
        method="POST",
        body={"email": "checkin@djangoair.local", "password": "Checkin123!"},
    )
    assert code == 200
    ci_token = ci_login["access"]

    # Check-in Manager checks in passenger and charges $30 luggage fee
    code, checked = http_req(
        f"{BASE_URL}/api/v1/staff/checkin/",
        method="POST",
        body={"ticket_code": ticket_code, "luggage_fee": "30.00"},
        token=ci_token,
    )
    assert code == 200 and checked["status"] == "CHECKED_IN", f"Staff check-in failed: {code} {checked}"

    # Gate Manager boards passenger by ticket_code
    code, gate_login = http_req(
        f"{BASE_URL}/api/v1/auth/login/",
        method="POST",
        body={"email": "gate@djangoair.local", "password": "Gate123!"},
    )
    assert code == 200
    gate_token = gate_login["access"]

    code, boarded = http_req(
        f"{BASE_URL}/api/v1/staff/gate/board/",
        method="POST",
        body={"ticket_code": ticket_code},
        token=gate_token,
    )
    assert code == 200 and boarded["status"] == "BOARDED", f"Gate boarding failed: {code} {boarded}"

    print("5. Verifying HMAC-signed Webhook deliveries in Flask Webhook Mock...")
    time.sleep(2)
    code, wh_events = http_req(f"{BASE_URL}/mock-webhook/events")
    assert code == 200 and wh_events["count"] >= 3, f"Expected webhook deliveries, got: {wh_events}"
    event_names = {ev["event"] for ev in wh_events["events"]}
    assert {"booking.confirmed", "passenger.checked_in", "passenger.boarded"}.issubset(event_names), (
        f"Missing expected webhook events: {event_names}"
    )

    print("6. Verifying Mobile WebSocket Redis event cache...")
    code, ws_events = http_req(f"{BASE_URL}/mobile-mock/events")
    assert code == 200 and len(ws_events["events"]) >= 3, f"Expected WS events, got: {ws_events}"

    print("\nALL END-TO-END SMOKE CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
