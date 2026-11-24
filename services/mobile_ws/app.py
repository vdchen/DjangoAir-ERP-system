import json
import logging
import os

ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "gevent")
if ASYNC_MODE == "gevent":
    from gevent import monkey

    monkey.patch_all()

import redis  # noqa: E402
from flask import Flask, jsonify, render_template, request  # noqa: E402
from flask_socketio import SocketIO, emit, join_room, leave_room  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mobile_ws")

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
REDIS_EVENTS_CHANNEL = os.environ.get("REDIS_EVENTS_CHANNEL", "djangoair:events")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "mobile-ws-dev-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE, manage_session=False)

recent_events: list[dict] = []
MAX_EVENTS = 50


def broadcast_domain_event(envelope: dict) -> None:
    """Broadcast a domain event envelope to global, flight, and ticket rooms."""
    recent_events.insert(0, envelope)
    del recent_events[MAX_EVENTS:]

    data = envelope.get("data", {}) if isinstance(envelope, dict) else {}
    socketio.emit("flight_event", envelope, room="all_events")

    flight_number = data.get("flight_number")
    if flight_number:
        socketio.emit("flight_event", envelope, room=f"flight:{flight_number}")

    ticket_code = data.get("ticket_code")
    if ticket_code:
        socketio.emit("flight_event", envelope, room=f"ticket:{ticket_code}")

    for code in data.get("ticket_codes", []) or []:
        socketio.emit("flight_event", envelope, room=f"ticket:{code}")


def redis_listener() -> None:
    """Subscribe to DjangoAir Redis Pub/Sub events and push them over WebSockets."""
    while True:
        try:
            client = redis.Redis.from_url(REDIS_URL)
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(REDIS_EVENTS_CHANNEL)
            logger.info("Subscribed to Redis channel %s", REDIS_EVENTS_CHANNEL)
            while True:
                message = pubsub.get_message(timeout=1.0)
                if message and message.get("data") is not None:
                    raw = message.get("data")
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    try:
                        envelope = json.loads(raw)
                        broadcast_domain_event(envelope)
                    except Exception as exc:
                        logger.warning("Invalid event payload: %s", exc)
                socketio.sleep(0.05)
        except Exception as exc:
            logger.warning("Redis listener error (retrying): %s", exc)
            socketio.sleep(3)


@app.route("/mobile-mock/")
@app.route("/")
def index():
    return render_template("index.html", recent_events=recent_events)


@app.route("/mobile-mock/health")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "mobile_ws", "cached_events": len(recent_events)})


@app.route("/mobile-mock/events", methods=["GET", "POST"])
def mock_events():
    """GET recent mobile push events or POST a simulated event for testing."""
    if request.method == "POST":
        envelope = request.get_json(silent=True) or {}
        broadcast_domain_event(envelope)
        return jsonify({"broadcasted": True, "event": envelope}), 200
    return jsonify({"events": recent_events}), 200


@socketio.on("connect")
def handle_connect():
    join_room("all_events")
    emit("connected", {"message": "Connected to DjangoAir Mobile WebSocket API"})


@socketio.on("subscribe_flight")
def handle_subscribe_flight(payload):
    flight_number = (payload or {}).get("flight_number", "").strip()
    if flight_number:
        room = f"flight:{flight_number}"
        join_room(room)
        emit("subscribed", {"room": room, "flight_number": flight_number})


@socketio.on("unsubscribe_flight")
def handle_unsubscribe_flight(payload):
    flight_number = (payload or {}).get("flight_number", "").strip()
    if flight_number:
        room = f"flight:{flight_number}"
        leave_room(room)
        emit("unsubscribed", {"room": room})


@socketio.on("subscribe_ticket")
def handle_subscribe_ticket(payload):
    ticket_code = (payload or {}).get("ticket_code", "").strip()
    if ticket_code:
        room = f"ticket:{ticket_code}"
        join_room(room)
        emit("subscribed", {"room": room, "ticket_code": ticket_code})


@socketio.on("ping_mobile")
def handle_ping():
    emit("pong_mobile", {"status": "alive"})


if __name__ == "__main__":
    socketio.start_background_task(redis_listener)
    socketio.run(app, host="0.0.0.0", port=5001)
