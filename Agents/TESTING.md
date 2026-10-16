# TESTING.md — Verification and Quality Rules

## 1. Purpose

Use this document to verify changes consistently. Update the commands here when repository scripts or environment setup change. Do not report a test as passing unless it was run and passed.

## 2. Test layers

1. **Unit tests:** pure logic such as gesture classification, coordinate normalization, smoothing, file-type checks, and protocol validation.
2. **Component tests:** upload states, toolbar actions, status indicators, and WebSocket lifecycle behavior.
3. **Integration tests:** frontend/backend WebSocket exchange and gesture-to-viewer event handling.
4. **Manual hardware tests:** webcam availability, real hand tracking, latency, and gesture stability.
5. **Regression checks:** supported model formats, mouse/touch fallback, resource cleanup, and local privacy.

Automated CI must not depend on a physical webcam. Use mocked camera frames or injected landmark fixtures for automated tests; reserve hardware checks for an explicitly configured manual test run.

## 3. Frontend checks

Run commands from `frontend/` after the package scripts have been configured.

```bash
npm install
npm run typecheck
npm run test
npm run build
```

If a script has not been configured in `package.json`, add it as part of the initial setup or document the actual equivalent command. Do not silently skip the type check or tests because a script is missing.

Frontend test coverage should include:

- Supported and unsupported file extension handling.
- Loader success and failure states for STL, OBJ, GLB, and glTF.
- Model replacement and cleanup/disposal behavior where testable.
- Reset-view and gesture enable/disable behavior.
- Validation of malformed or unknown WebSocket messages.
- Handling of `hello`, `status`, `gesture`, `error`, `ack`, and `pong` messages.
- Ignoring stale sequence numbers and gesture updates after gesture end/tracking loss.
- Reconnect behavior without duplicate sockets or reconnect loops.
- Mouse/touch control usability with gesture tracking disabled or disconnected.
- Clamping extreme zoom inputs and handling non-finite values.

## 4. Backend checks

Run commands from `backend/` using the project virtual environment.

```bash
python -m pytest
```

Backend test coverage should include:

- Coordinate normalization and bounds.
- Landmark-based gesture classification for open palm, pinch, closed fist, and no gesture.
- Confidence thresholds, smoothing, movement dead zones, and outlier clamping.
- Gesture lifecycle transitions (`start`, `update`, `end`).
- Baseline reset after tracking loss and re-acquisition.
- Pinch distance-to-scale mapping and upper/lower bounds.
- Protocol schema validation, unsupported versions, unknown commands, malformed JSON, and invalid sensitivity values.
- Camera failure and cleanup paths using a mocked camera.
- WebSocket connect/disconnect and single-active-client behavior.
- Service shutdown without leaked worker threads or camera handles.

Prefer deterministic fixtures for landmarks and frame-independent gesture tests. Keep unit tests fast and independent of actual camera availability.

## 5. Local end-to-end test

### Start the backend

Create and activate a virtual environment, then install the dependencies from `backend/requirements.txt`. Example for macOS/Linux:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows PowerShell activation example:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Configure the frontend WebSocket URL to `ws://127.0.0.1:8000/ws/gestures` for local development.

The commands above are intended for the planned structure. Adjust the import path or scripts if the implemented application deliberately uses a different entrypoint, then update this document.

## 6. Manual acceptance checklist

### Model viewer

- [ ] Load one valid STL model.
- [ ] Load one valid OBJ model; verify behavior if material files are missing.
- [ ] Load one GLB model with embedded resources.
- [ ] Load one glTF model and verify documented external-resource behavior.
- [ ] Try an unsupported extension and a corrupt file; the page must remain usable.
- [ ] Replace one model with another; the old model disappears and resources are cleaned up.
- [ ] Rotate, pan, zoom, and reset using conventional controls.

### Camera and tracking

- [ ] Start the Python service without another app holding the webcam.
- [ ] Confirm camera status reaches `ready`.
- [ ] Show no hand: the viewer must not move on its own.
- [ ] Show an open palm and move slowly in both axes: rotation follows the documented direction.
- [ ] Pinch fingers closer and farther apart: zoom follows the documented direction.
- [ ] Make a fist and move: pan follows the documented direction.
- [ ] Drop the hand out of view, then bring it back: movement stops on tracking loss and resumes only after stable re-detection.
- [ ] Disable and re-enable tracking; verify active gestures end cleanly.
- [ ] Cover/occupy the camera or deny camera permission; the UI explains the failure and mouse controls still work.

### WebSocket and resilience

- [ ] Connect and verify a `hello` event with supported protocol version.
- [ ] Verify camera/tracking status changes are reflected in the UI.
- [ ] Disable the backend during a session; frontend shows disconnected state without crashing.
- [ ] Restart the backend; frontend reconnects without creating multiple sockets.
- [ ] Try a second active client; it receives the documented rejection.
- [ ] Send malformed/unsupported messages in a controlled test; the service handles them predictably.
- [ ] Verify raw camera frames are not sent through the WebSocket or stored by the application.

## 7. Performance checks

Record results rather than assuming targets are met.

| Measurement | Record |
|---|---|
| OS, CPU, RAM, GPU |  |
| Python and browser versions |  |
| Test model format and approximate triangle/face count |  |
| Sustained gesture update rate |  |
| Approximate perceived gesture-to-view latency |  |
| CPU usage while tracking |  |
| Rendering responsiveness with tracking on/off |  |
| Lighting and camera-distance conditions |  |

Initial target: about 20–30 gesture updates per second when stable, while keeping the viewer responsive. If the target is not met, profile first; then reduce inference work, improve frame scheduling, or tune smoothing without hiding the measured limitation.

## 8. Privacy and security checks

- [ ] Default backend bind address is `127.0.0.1`.
- [ ] WebSocket origin checks use an explicit allowlist for expected local development origins.
- [ ] No raw camera frame is included in any WebSocket payload.
- [ ] No frame recording or persistent frame storage is enabled.
- [ ] Logs do not contain images, secrets, or continuous high-volume landmark dumps.
- [ ] Unknown commands and out-of-range numeric values are rejected or handled according to `API.md`.
- [ ] The app makes it clear when the camera/tracking is active.

## 9. Before merging or declaring a task complete

1. Run targeted tests for the modified module.
2. Run the frontend type-check, tests, and production build when frontend code changes.
3. Run backend tests when backend code changes.
4. Run protocol/integration tests when either side of the WebSocket contract changes.
5. Complete relevant manual checklist items for camera, real gestures, or 3D rendering changes.
6. Update the related task acceptance status in `TASKS.md` only if verified.
7. Include exact commands run, pass/fail outcomes, and unresolved limitations in the change summary.
