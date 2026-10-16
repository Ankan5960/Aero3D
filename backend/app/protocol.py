"""WebSocket protocol v1 message builders and client-command validation (see API.md)."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
SERVICE_NAME = "gesture-3d-viewer"
SENSITIVITY_MIN = 0.25
SENSITIVITY_MAX = 2.0

CAMERA_STATES = ("starting", "ready", "error", "stopped")
TRACKING_STATES = ("searching", "tracking", "lost", "disabled", "error")


def now_ms() -> int:
    return int(time.time() * 1000)


class ProtocolError(Exception):
    """Raised for malformed/unsupported client messages. Message is safe to display."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- builders


def hello() -> dict[str, Any]:
    return {
        "type": "hello",
        "protocol_version": PROTOCOL_VERSION,
        "service": SERVICE_NAME,
        "timestamp_ms": now_ms(),
    }


def status(camera: str, tracking: str, enabled: bool, message: str | None = None) -> dict[str, Any]:
    assert camera in CAMERA_STATES and tracking in TRACKING_STATES
    return {
        "type": "status",
        "protocol_version": PROTOCOL_VERSION,
        "timestamp_ms": now_ms(),
        "camera": camera,
        "tracking": tracking,
        "enabled": enabled,
        "message": message,
    }


def gesture(
    *,
    seq: int,
    gesture_name: str,
    phase: str,
    hand: str,
    confidence: float,
    position: tuple[float, float],
    delta: tuple[float, float],
    scale_delta: float | None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "type": "gesture",
        "protocol_version": PROTOCOL_VERSION,
        "seq": seq,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else now_ms(),
        "gesture": gesture_name,
        "phase": phase,
        "hand": hand,
        "confidence": round(float(confidence), 4),
        "position": {"x": round(position[0], 5), "y": round(position[1], 5)},
        "delta": {"x": round(delta[0], 5), "y": round(delta[1], 5)},
        "scale_delta": None if scale_delta is None else round(scale_delta, 5),
    }


def error(code: str, message: str, recoverable: bool = True) -> dict[str, Any]:
    return {
        "type": "error",
        "protocol_version": PROTOCOL_VERSION,
        "timestamp_ms": now_ms(),
        "code": code,
        "message": message,
        "recoverable": recoverable,
    }


def ack(command: str, ok: bool = True, message: str | None = None) -> dict[str, Any]:
    return {
        "type": "ack",
        "protocol_version": PROTOCOL_VERSION,
        "timestamp_ms": now_ms(),
        "command": command,
        "ok": ok,
        "message": message,
    }


def pong(client_timestamp_ms: int | None) -> dict[str, Any]:
    return {
        "type": "pong",
        "protocol_version": PROTOCOL_VERSION,
        "timestamp_ms": now_ms(),
        "client_timestamp_ms": client_timestamp_ms,
    }


# -------------------------------------------------------------- validation


@dataclass(frozen=True)
class Command:
    """A validated client command."""

    name: str  # "set_enabled" | "set_sensitivity" | "ping"
    enabled: bool | None = None
    value: float | None = None
    timestamp_ms: int | None = None


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def parse_command(raw: str, max_bytes: int = 4096) -> Command:
    """Validate a raw client text frame. Raises ProtocolError on any problem."""
    if len(raw.encode("utf-8", errors="ignore")) > max_bytes:
        raise ProtocolError("INVALID_MESSAGE", "Message is too large.")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise ProtocolError("INVALID_MESSAGE", "Message is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ProtocolError("INVALID_MESSAGE", "Message must be a JSON object.")
    if data.get("type") != "command":
        raise ProtocolError("INVALID_MESSAGE", "Message type must be 'command'.")
    version = data.get("protocol_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ProtocolError("INVALID_MESSAGE", "Missing or invalid protocol_version.")
    if version != PROTOCOL_VERSION:
        raise ProtocolError("UNSUPPORTED_PROTOCOL", f"Unsupported protocol version {version}.")
    name = data.get("command")
    if not isinstance(name, str):
        raise ProtocolError("INVALID_MESSAGE", "Missing command name.")

    if name == "set_enabled":
        enabled = data.get("enabled")
        if not isinstance(enabled, bool):
            raise ProtocolError("INVALID_MESSAGE", "'enabled' must be a boolean.")
        return Command(name="set_enabled", enabled=enabled)
    if name == "set_sensitivity":
        value = data.get("value")
        if not _is_number(value):
            raise ProtocolError("INVALID_MESSAGE", "'value' must be a finite number.")
        if not SENSITIVITY_MIN <= value <= SENSITIVITY_MAX:
            raise ProtocolError(
                "INVALID_MESSAGE",
                f"'value' must be between {SENSITIVITY_MIN} and {SENSITIVITY_MAX}.",
            )
        return Command(name="set_sensitivity", value=float(value))
    if name == "ping":
        ts = data.get("timestamp_ms")
        if ts is not None and not _is_number(ts):
            raise ProtocolError("INVALID_MESSAGE", "'timestamp_ms' must be a number.")
        return Command(name="ping", timestamp_ms=None if ts is None else int(ts))
    raise ProtocolError("UNSUPPORTED_COMMAND", "Unknown command.")
