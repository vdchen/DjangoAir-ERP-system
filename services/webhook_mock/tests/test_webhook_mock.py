import hashlib
import hmac
import json

from app import WEBHOOK_SECRET, app, received_events


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_invalid_signature():
    client = app.test_client()
    body = json.dumps({"event": "booking.confirmed"}).encode("utf-8")
    resp = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DjangoAir-Signature": "sha256=invalid",
        },
    )
    assert resp.status_code == 401


def test_webhook_accepts_valid_hmac_signature_and_stores_event():
    received_events.clear()
    client = app.test_client()
    payload = {"event": "booking.confirmed", "data": {"booking_reference": "BK-123456"}}
    body = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DjangoAir-Event": "booking.confirmed",
            "X-DjangoAir-Signature": _sign(body),
        },
    )
    assert resp.status_code == 200
    assert resp.get_json()["received"] is True

    listing = client.get("/mock-webhook/events")
    assert listing.status_code == 200
    assert listing.get_json()["count"] == 1
    assert listing.get_json()["events"][0]["event"] == "booking.confirmed"


def test_webhook_rejects_stale_replay_timestamp():
    client = app.test_client()
    body = json.dumps({"event": "booking.confirmed"}).encode("utf-8")
    stale_ts = "1500000000"  # Year 2017 — far outside 300s replay window
    resp = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DjangoAir-Timestamp": stale_ts,
            "X-DjangoAir-Signature": _sign(body),
        },
    )
    assert resp.status_code == 401
    assert "replay window" in resp.get_json()["error"]
