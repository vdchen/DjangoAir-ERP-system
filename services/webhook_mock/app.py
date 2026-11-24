import hashlib
import hmac
import os
from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_DEFAULT_SECRET", "djangoair-webhook-dev-secret")
MAX_STORED_EVENTS = 100

_events_lock = Lock()
received_events: list[dict] = []


def verify_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.route("/mock-webhook/")
@app.route("/")
def index():
    with _events_lock:
        snapshot = list(received_events)
    return render_template("index.html", events=snapshot)


@app.route("/mock-webhook/health")
@app.route("/health")
def health():
    with _events_lock:
        count = len(received_events)
    return jsonify({"status": "ok", "service": "webhook_mock", "received_count": count})


@app.route("/mock-webhook/events", methods=["GET", "POST", "DELETE"])
def webhook_events():
    if request.method == "GET":
        with _events_lock:
            return jsonify({"count": len(received_events), "events": list(received_events)})

    if request.method == "DELETE":
        with _events_lock:
            received_events.clear()
        return jsonify({"cleared": True}), 200

    raw_body = request.get_data()
    sig_header = request.headers.get("X-DjangoAir-Signature", "")
    ts_header = request.headers.get("X-DjangoAir-Timestamp", "").strip()
    sig_v2_header = request.headers.get("X-DjangoAir-Signature-V2", "").strip()
    secret = os.environ.get("WEBHOOK_DEFAULT_SECRET", WEBHOOK_SECRET)

    if ts_header:
        try:
            req_ts = int(ts_header)
        except ValueError:
            return jsonify({"error": "Malformed X-DjangoAir-Timestamp header"}), 401
        if abs(int(datetime.now(timezone.utc).timestamp()) - req_ts) > 300:
            return jsonify({"error": "Webhook timestamp outside 300s replay window"}), 401
        if sig_v2_header:
            signed_payload = f"{ts_header}.".encode() + raw_body
            if not verify_signature(secret, signed_payload, sig_v2_header):
                return jsonify({"error": "Invalid HMAC-V2 timestamped signature"}), 401

    if not verify_signature(secret, raw_body, sig_header):
        return jsonify({"error": "Invalid or missing HMAC signature"}), 401

    payload = request.get_json(silent=True) or {}
    record = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "event": request.headers.get("X-DjangoAir-Event", payload.get("event", "unknown")),
        "signature_verified": True,
        "payload": payload,
    }
    with _events_lock:
        received_events.insert(0, record)
        del received_events[MAX_STORED_EVENTS:]

    return jsonify({"received": True, "event": record["event"]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
