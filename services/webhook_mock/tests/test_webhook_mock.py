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


def test_webhook_health_ui_clear_and_v2_signature_paths():
    import time

    received_events.clear()
    client = app.test_client()

    assert client.get("/mock-webhook/health").status_code == 200
    assert client.get("/mock-webhook/").status_code == 200

    body = json.dumps({"event": "flight.cancelled"}).encode("utf-8")

    # Missing signature header
    assert client.post("/mock-webhook/events", data=body).status_code == 401

    # Malformed timestamp header
    bad_ts = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "X-DjangoAir-Timestamp": "not-an-int",
            "X-DjangoAir-Signature": _sign(body),
        },
    )
    assert bad_ts.status_code == 401

    # Valid timestamp + invalid V2 signature
    now_ts = str(int(time.time()))
    bad_v2 = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "X-DjangoAir-Timestamp": now_ts,
            "X-DjangoAir-Signature": _sign(body),
            "X-DjangoAir-Signature-V2": "sha256=deadbeef",
        },
    )
    assert bad_v2.status_code == 401

    # Valid timestamp + valid V2 signature
    v2_sig = _sign(f"{now_ts}.".encode() + body)
    ok_v2 = client.post(
        "/mock-webhook/events",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-DjangoAir-Timestamp": now_ts,
            "X-DjangoAir-Signature": _sign(body),
            "X-DjangoAir-Signature-V2": v2_sig,
        },
    )
    assert ok_v2.status_code == 200

    # DELETE clears stored events
    clear_resp = client.delete("/mock-webhook/events")
    assert clear_resp.status_code == 200
    assert clear_resp.get_json()["cleared"] is True
    assert client.get("/mock-webhook/events").get_json()["count"] == 0

