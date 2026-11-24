import os

os.environ["SOCKETIO_ASYNC_MODE"] = "threading"

from app import app, broadcast_domain_event, socketio  # noqa: E402


def test_health_endpoint():
    client = app.test_client()
    resp = client.get("/mobile-mock/health")
    assert resp.status_code == 200
    assert resp.get_json()["service"] == "mobile_ws"


def test_socketio_connect_subscribe_and_broadcast():
    ws_client = socketio.test_client(app)
    assert ws_client.is_connected()

    received = ws_client.get_received()
    assert any(msg["name"] == "connected" for msg in received)

    ws_client.emit("subscribe_flight", {"flight_number": "DA101-1"})
    sub_msgs = ws_client.get_received()
    assert any(
        msg["name"] == "subscribed" and msg["args"][0]["room"] == "flight:DA101-1"
        for msg in sub_msgs
    )

    broadcast_domain_event(
        {
            "event": "passenger.boarded",
            "data": {"flight_number": "DA101-1", "ticket_code": "DA-TEST0001"},
        }
    )
    event_msgs = ws_client.get_received()
    assert any(
        msg["name"] == "flight_event" and msg["args"][0]["event"] == "passenger.boarded"
        for msg in event_msgs
    )
    ws_client.disconnect()
