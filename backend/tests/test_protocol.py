import json

import pytest

from app import protocol
from app.protocol import ProtocolError, parse_command


def cmd(**kw):
    base = {"type": "command", "protocol_version": 1}
    base.update(kw)
    return json.dumps(base)


def code_of(raw):
    with pytest.raises(ProtocolError) as e:
        parse_command(raw)
    return e.value.code


def test_valid_commands():
    assert parse_command(cmd(command="set_enabled", enabled=False)).enabled is False
    assert parse_command(cmd(command="set_sensitivity", value=1.5)).value == 1.5
    assert parse_command(cmd(command="ping", timestamp_ms=5)).timestamp_ms == 5
    assert parse_command(cmd(command="ping")).timestamp_ms is None


def test_malformed_json_and_shapes():
    assert code_of("{nope") == "INVALID_MESSAGE"
    assert code_of("[1,2]") == "INVALID_MESSAGE"
    assert code_of(json.dumps({"type": "hello"})) == "INVALID_MESSAGE"
    assert code_of(json.dumps({"type": "command", "protocol_version": 1})) == "INVALID_MESSAGE"


def test_unsupported_version_and_command():
    assert code_of(cmd(command="ping", protocol_version=2)) == "UNSUPPORTED_PROTOCOL"
    assert code_of(json.dumps({"type": "command", "command": "ping"})) == "INVALID_MESSAGE"
    assert code_of(cmd(command="reboot")) == "UNSUPPORTED_COMMAND"


@pytest.mark.parametrize("value", [0.1, 2.5, "1", None, True, float("inf")])
def test_invalid_sensitivity(value):
    raw = '{"type":"command","protocol_version":1,"command":"set_sensitivity","value":%s}' % (
        "Infinity" if value == float("inf") else json.dumps(value)
    )
    assert code_of(raw) == "INVALID_MESSAGE"


def test_sensitivity_bounds_inclusive():
    assert parse_command(cmd(command="set_sensitivity", value=0.25)).value == 0.25
    assert parse_command(cmd(command="set_sensitivity", value=2.0)).value == 2.0


def test_set_enabled_requires_bool():
    assert code_of(cmd(command="set_enabled", enabled="yes")) == "INVALID_MESSAGE"


def test_oversized_message_rejected():
    with pytest.raises(ProtocolError):
        parse_command(cmd(command="ping", pad="x" * 5000))


def test_message_builders_have_required_fields():
    g = protocol.gesture(
        seq=1, gesture_name="rotate", phase="update", hand="right", confidence=0.9,
        position=(0.5, 0.5), delta=(0.01, 0.0), scale_delta=None,
    )
    required = {"type", "protocol_version", "seq", "timestamp_ms", "gesture", "phase", "hand",
                "confidence", "position", "delta", "scale_delta"}
    assert required <= g.keys()
    assert protocol.hello()["service"] == "gesture-3d-viewer"
    assert protocol.status("ready", "tracking", True)["message"] is None
    assert protocol.pong(None)["client_timestamp_ms"] is None
    assert protocol.ack("ping")["ok"] is True
    assert protocol.error("X", "m")["recoverable"] is True
