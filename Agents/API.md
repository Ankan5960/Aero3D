# API.md — WebSocket Interface Contract

## 1. Status and scope

This document defines protocol version `1` between the local Python gesture service and the browser frontend. It is the source of truth for message shapes and semantics. The MVP does not need a REST API for model upload because models are loaded in the browser.

## 2. Connection

- **Local development URL:** `ws://127.0.0.1:8000/ws/gestures`
- **Transport:** WebSocket, JSON text frames.
- **Client:** browser frontend.
- **Server:** local FastAPI Python service.
- **MVP concurrency:** one active gesture client. Reject additional active clients with an `error` event; do not silently steal the camera.
- **Protocol version:** integer `1`.

The frontend URL should be configurable (for example, with a Vite environment variable) rather than hard-coded throughout the codebase. The server should allow only configured local frontend origins. The default URL is for local development only.

## 3. Conventions

- Field names use `snake_case`.
- Timestamps named `timestamp_ms` are Unix epoch time in milliseconds.
- `confidence` is a number from `0.0` to `1.0`.
- Normalized positions use numbers in the range `[0.0, 1.0]`.
- Delta values represent change since the preceding valid tracking sample, not absolute coordinates. They are normalized screen-space deltas unless a message definition states otherwise.
- The frontend must validate messages at runtime; TypeScript types alone do not validate network input.
- The backend must validate every client message and must not trust a client-supplied value.

## 4. Server-to-client messages

### 4.1 `hello`

Sent once after a successful WebSocket connection.

```json
{
  "type": "hello",
  "protocol_version": 1,
  "service": "gesture-3d-viewer",
  "timestamp_ms": 1792183200000
}
```

Required fields: `type`, `protocol_version`, `service`, `timestamp_ms`.

The client should close the connection and show an unsupported-protocol status if `protocol_version` is not supported.

### 4.2 `status`

Describes camera and hand-tracking state.

```json
{
  "type": "status",
  "protocol_version": 1,
  "timestamp_ms": 1792183200000,
  "camera": "ready",
  "tracking": "tracking",
  "enabled": true,
  "message": null
}
```

Allowed values:

- `camera`: `"starting" | "ready" | "error" | "stopped"`
- `tracking`: `"searching" | "tracking" | "lost" | "disabled" | "error"`
- `enabled`: whether gesture tracking is enabled.
- `message`: optional user-readable status/error text; use `null` when there is no message.

Send a status update when one of these state values changes, not necessarily on every camera frame.

### 4.3 `gesture`

Represents the current gesture lifecycle and incremental motion.

```json
{
  "type": "gesture",
  "protocol_version": 1,
  "seq": 42,
  "timestamp_ms": 1792183200000,
  "gesture": "rotate",
  "phase": "update",
  "hand": "right",
  "confidence": 0.97,
  "position": { "x": 0.62, "y": 0.38 },
  "delta": { "x": 0.012, "y": -0.004 },
  "scale_delta": null
}
```

Required fields: `type`, `protocol_version`, `seq`, `timestamp_ms`, `gesture`, `phase`, `hand`, `confidence`, `position`, `delta`, `scale_delta`.

Allowed values and meanings:

- `gesture`: `"rotate" | "zoom" | "pan" | "none"`
- `phase`: `"start" | "update" | "end"`
- `hand`: `"left" | "right" | "unknown"`
- `position`: palm/hand anchor position normalized to `[0, 1]`. If no valid position is available for an `end` event, use `null` if the implementation updates the schema accordingly; the initial implementation should prefer carrying the last valid position.
- `delta.x`, `delta.y`: normalized movement since the preceding valid sample. These are normally used by `rotate` and `pan` events. For `zoom`, use `scale_delta` and send `{ "x": 0, "y": 0 }` for `delta`.
- `scale_delta`: multiplicative zoom factor for this update. For example, `1.02` means a small zoom-in step and `0.98` means a small zoom-out step. Use `null` for non-zoom gestures.
- `seq`: monotonically increasing sequence number for the lifetime of the service process. The frontend may use it to discard duplicate or older events.

Lifecycle rules:

1. Send `start` when a gesture becomes active.
2. Send `update` while that gesture remains active, subject to the configured event cadence.
3. Send `end` when the gesture stops, changes to a different gesture, tracking is lost, or tracking is disabled.
4. On gesture change, end the previous gesture before starting the next one.
5. `none` is for an explicit no-gesture state only if the client needs it; ordinary idle frames should be represented by `status` changes and should not flood the socket.
6. A client must not apply movement from `start` or `end` events. Apply deltas/scale only on `update` events unless the implementation explicitly tests another behavior.

### 4.4 `error`

A structured error for connection, camera, or protocol problems.

```json
{
  "type": "error",
  "protocol_version": 1,
  "timestamp_ms": 1792183200000,
  "code": "CAMERA_UNAVAILABLE",
  "message": "The webcam could not be opened.",
  "recoverable": true
}
```

Suggested codes:

- `CAMERA_UNAVAILABLE`
- `CAMERA_PERMISSION_DENIED`
- `CLIENT_ALREADY_CONNECTED`
- `INVALID_MESSAGE`
- `UNSUPPORTED_COMMAND`
- `UNSUPPORTED_PROTOCOL`
- `INTERNAL_ERROR`

`message` must be safe for display and must not expose tracebacks, local secrets, or sensitive machine details. Use `recoverable` to indicate whether reconnecting/retrying may help.

### 4.5 `ack`

Acknowledges a supported client command.

```json
{
  "type": "ack",
  "protocol_version": 1,
  "timestamp_ms": 1792183200000,
  "command": "set_enabled",
  "ok": true,
  "message": null
}
```

For a rejected command, use `ok: false` with a safe explanation, or send the applicable `error` message. Be consistent and test the chosen behavior.

### 4.6 `pong`

Response to a client `ping`.

```json
{
  "type": "pong",
  "protocol_version": 1,
  "timestamp_ms": 1792183200000,
  "client_timestamp_ms": 1792183199990
}
```

`client_timestamp_ms` echoes the timestamp supplied by the client when present; otherwise it may be `null`.

## 5. Client-to-server messages

### 5.1 `set_enabled` command

Enable or disable gesture processing. The camera may remain open while disabled, depending on the service implementation; if it does, the service must make that status clear.

```json
{
  "type": "command",
  "protocol_version": 1,
  "command": "set_enabled",
  "enabled": false
}
```

The server returns an `ack` and updates `status`. When disabling, end any active gesture before reporting tracking as disabled.

### 5.2 `set_sensitivity` command

Changes a bounded interaction sensitivity multiplier.

```json
{
  "type": "command",
  "protocol_version": 1,
  "command": "set_sensitivity",
  "value": 1.0
}
```

`value` must be a finite number in the inclusive range `[0.25, 2.0]`. A value of `1.0` is the default. Sensitivity should change the interpretation/output scale of movement, not bypass confidence checks or safety bounds.

### 5.3 `ping` command

Used to check that the socket is responsive.

```json
{
  "type": "command",
  "protocol_version": 1,
  "command": "ping",
  "timestamp_ms": 1792183199990
}
```

The server responds with `pong`.

## 6. Ordering, cadence, and flow control

- The server should aim for approximately 20–30 `gesture` update events per second on hardware that supports it, but the frontend must not depend on a fixed rate.
- Prefer latest-state delivery and bounded buffers over an unbounded queue. Dropping stale `update` events is acceptable; dropping required `start`/`end` transitions is not.
- The frontend should ignore duplicate/stale sequence numbers when doing so is safe, and should always process status/error events.
- UI rendering must not be tied to the rate of socket messages. The Three.js renderer should continue rendering independently.
- If a client disconnects while a gesture is active, the backend must clear that active state before serving another client.

## 7. Reconnect behavior

- The frontend should show connection state and retry with bounded exponential backoff, for example starting at 500 ms and capping at 5 seconds.
- Reset the retry delay after a successful connection.
- Do not create multiple concurrent reconnect timers/sockets.
- On reconnect, reset any local gesture delta baseline and wait for fresh status/gesture events before applying movement.
- The backend must release client-owned resources after disconnect and should not leak camera handles or inference workers.

## 8. Validation requirements

- Reject unsupported `protocol_version` values.
- Reject malformed JSON, unknown commands, missing required fields, non-finite numbers, and out-of-range sensitivity values.
- Bound incoming message size.
- Apply a maximum reasonable zoom step in the frontend even if the server sends an extreme `scale_delta`.
- Do not accept file paths, shell commands, or arbitrary URLs through this protocol.

## 9. Compatibility policy

Treat version `1` fields and semantics as a stable contract. Backward-compatible additions may introduce optional fields. Renaming/removing fields, changing units, changing gesture lifecycle semantics, or changing required fields requires a protocol-version change or a carefully documented migration. Update `API.md`, frontend runtime validation/types, backend schemas, and protocol tests together.
