import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.main import create_app
from tests.landmarks import obs
from tests.test_gesture_service import FakeCamera, FakeTracker

ORIGIN = {"origin": "http://localhost:5173"}


def make_client(cameras=None, frames=None):
    cameras = cameras if cameras is not None else []

    def cam_factory():
        c = FakeCamera()
        cameras.append(c)
        return c

    app = create_app(Settings(), camera_factory=cam_factory, tracker_factory=lambda: FakeTracker(frames or []))
    return TestClient(app), cameras, app


def recv_until(ws, pred, limit=50):
    for _ in range(limit):
        m = ws.receive_json()
        if pred(m):
            return m
    raise AssertionError("expected message not received")


def test_defaults_are_loopback_and_local_origins():
    s = Settings()
    assert s.host == "127.0.0.1"
    assert "*" not in s.allowed_origins
    assert s.allow_missing_origin is False


def test_health():
    client, _, _ = make_client()
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["protocol_version"] == 1


def test_hello_ping_and_commands():
    client, _, _ = make_client()
    with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["protocol_version"] == 1
        ws.send_json({"type": "command", "protocol_version": 1, "command": "ping", "timestamp_ms": 7})
        assert recv_until(ws, lambda m: m["type"] == "pong")["client_timestamp_ms"] == 7
        ws.send_json({"type": "command", "protocol_version": 1, "command": "set_sensitivity", "value": 1.5})
        assert recv_until(ws, lambda m: m["type"] == "ack")["command"] == "set_sensitivity"
        ws.send_json({"type": "command", "protocol_version": 1, "command": "set_enabled", "enabled": False})
        assert recv_until(ws, lambda m: m["type"] == "ack")["ok"] is True
        st = recv_until(ws, lambda m: m["type"] == "status" and m["tracking"] == "disabled")
        assert st["enabled"] is False


def test_invalid_messages_return_errors_and_keep_connection():
    client, _, _ = make_client()
    with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws:
        ws.receive_json()
        ws.send_text("not json")
        assert recv_until(ws, lambda m: m["type"] == "error")["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "command", "protocol_version": 1, "command": "format_disk"})
        assert recv_until(ws, lambda m: m["type"] == "error")["code"] == "UNSUPPORTED_COMMAND"
        ws.send_json({"type": "command", "protocol_version": 9, "command": "ping"})
        assert recv_until(ws, lambda m: m["type"] == "error")["code"] == "UNSUPPORTED_PROTOCOL"
        ws.send_json({"type": "command", "protocol_version": 1, "command": "set_sensitivity", "value": 99})
        assert recv_until(ws, lambda m: m["type"] == "error")["code"] == "INVALID_MESSAGE"
        ws.send_json({"type": "command", "protocol_version": 1, "command": "ping"})
        assert recv_until(ws, lambda m: m["type"] == "pong")


def test_disallowed_and_missing_origin_rejected():
    client, cams, _ = make_client()
    for headers in ({"origin": "http://evil.example"}, {}):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/gestures", headers=headers):
                pass
    assert cams == []  # camera never opened for rejected clients


def test_single_active_client_and_slot_release():
    client, cams, app = make_client()
    with client:  # one shared event loop so handler cleanup can run to completion
      with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws1:
        ws1.receive_json()
        with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws2:
            err = ws2.receive_json()
            assert err["type"] == "error" and err["code"] == "CLIENT_ALREADY_CONNECTED"
        time.sleep(0.2)
        assert len(cams) == 1  # camera not opened twice
      for _ in range(50):
        if not app.state.slot.occupied:
            break
        time.sleep(0.05)
      assert not app.state.slot.occupied
      assert all(c.released for c in cams)
      with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws3:
        assert ws3.receive_json()["type"] == "hello"


def test_gesture_events_flow_through_socket():
    frames = [obs("open")] * 5 + [obs("open", offset=(0.05, 0.0))]
    client, _, _ = make_client(frames=frames)
    with client.websocket_connect("/ws/gestures", headers=ORIGIN) as ws:
        ws.receive_json()
        start = recv_until(ws, lambda m: m["type"] == "gesture")
        assert start["phase"] == "start" and start["gesture"] == "rotate"
        upd = recv_until(ws, lambda m: m["type"] == "gesture")
        assert upd["phase"] == "update" and upd["delta"]["x"] > 0
