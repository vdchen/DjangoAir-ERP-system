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
            "data": {
                "flight_number": "DA101-1",
                "ticket_code": "DA-TEST0001",
                "ticket_codes": ["DA-TEST0002"],
            },
        }
    )
    event_msgs = ws_client.get_received()
    assert any(
        msg["name"] == "flight_event" and msg["args"][0]["event"] == "passenger.boarded"
        for msg in event_msgs
    )

    ws_client.emit("subscribe_ticket", {"ticket_code": "DA-TEST0001"})
    ticket_msgs = ws_client.get_received()
    assert any(
        msg["name"] == "subscribed" and msg["args"][0]["room"] == "ticket:DA-TEST0001"
        for msg in ticket_msgs
    )

    ws_client.emit("unsubscribe_flight", {"flight_number": "DA101-1"})
    unsub_msgs = ws_client.get_received()
    assert any(
        msg["name"] == "unsubscribed" and msg["args"][0]["room"] == "flight:DA101-1"
        for msg in unsub_msgs
    )

    ws_client.emit("ping_mobile")
    pong_msgs = ws_client.get_received()
    assert any(msg["name"] == "pong_mobile" for msg in pong_msgs)
    ws_client.disconnect()


def test_http_index_and_events_endpoints():
    client = app.test_client()
    assert client.get("/mobile-mock/").status_code == 200

    post_resp = client.post(
        "/mobile-mock/events",
        json={"event": "flight.delayed", "data": {"flight_number": "DA202"}},
    )
    assert post_resp.status_code == 200
    assert post_resp.get_json()["broadcasted"] is True

    get_resp = client.get("/mobile-mock/events")
    assert get_resp.status_code == 200
    assert any(ev.get("event") == "flight.delayed" for ev in get_resp.get_json()["events"])

