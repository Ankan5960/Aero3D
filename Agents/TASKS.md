# TASKS.md — Work Plan and Priorities

## How to use this file

- Keep one primary task in progress where possible.
- A task is complete only when its acceptance criteria pass; code existing is not enough.
- Update this file when work starts, when a blocker is found, and when criteria have been verified.
- Record test evidence or a command in the task notes when marking a task complete.
- `[ ]` means not complete, `[x]` means verified complete, and `[-]` means blocked or intentionally deferred.

## Priority definitions

- **P0:** Required for the first end-to-end MVP.
- **P1:** Important reliability/usability work for the MVP.
- **P2:** Enhancement after the core loop is stable.

## Milestone 0 — Repository and developer setup

- [x] **P0 — Create frontend scaffold** _(verified: `npm run build`, `npm run dev`; README added)_
  - Set up React + TypeScript with Vite.
  - Add Three.js, React Three Fiber, and Drei.
  - Acceptance: frontend starts locally; TypeScript/build command works; README/setup notes explain how to launch it.

- [x] **P0 — Create Python backend scaffold** _(verified: uvicorn on 127.0.0.1:8000, camera released on disconnect, `pytest`)_
  - Set up FastAPI, OpenCV, MediaPipe, and required dependencies.
  - Add a health/status startup path and configuration for the local WebSocket URL.
  - Acceptance: backend starts locally on `127.0.0.1:8000`; missing camera errors are surfaced cleanly; shutdown releases resources.

- [x] **P0 — Establish test and lint/type-check commands** _(verified: `pytest` 49 passed; `npm run typecheck/test/build` passed)_
  - Define repeatable frontend and backend test commands.
  - Acceptance: commands are documented in `TESTING.md` and work on a clean setup.

## Milestone 1 — Browser 3D viewer

- [ ] **P0 — Build viewer scene**
  - Implement scene, camera, lighting, background, basic grid/axes if useful, and mouse/touch controls.
  - Acceptance: a test model is visible, correctly framed, and can be inspected without a webcam or backend running.

- [ ] **P0 — Support STL loading**
  - Use `STLLoader`; center/fit the mesh and provide a sensible default material.
  - Acceptance: valid STL loads; corrupt/unsupported files show an error; replacing a model disposes previous resources.

- [ ] **P0 — Support OBJ loading**
  - Use `OBJLoader`; handle missing material files gracefully.
  - Acceptance: valid OBJ geometry renders; missing materials do not crash the viewer; error states are understandable.

- [ ] **P0 — Support GLB/glTF loading**
  - Use `GLTFLoader` for `.glb` and `.gltf`.
  - Acceptance: a GLB with embedded assets renders correctly; external-resource limitations for standalone glTF are explained to users.

- [ ] **P1 — Add viewer toolbar**
  - Include reset view, fit model, and gesture enable/disable controls.
  - Acceptance: reset returns to the initial view and toolbar states match the actual viewer state.

## Milestone 2 — Hand tracking and gesture logic

- [ ] **P0 — Implement camera capture**
  - Capture frames through OpenCV in a worker/thread boundary suitable for async serving.
  - Acceptance: camera starts/stops cleanly; unavailable or denied camera produces a clear state instead of a crash.

- [ ] **P0 — Implement hand landmark detection**
  - Integrate MediaPipe Hand Landmarker and normalize coordinates.
  - Acceptance: the service can report tracking/searching/lost states; no-hand frames do not cause false movement.

- [ ] **P0 — Implement gesture state machine**
  - Classify open palm, pinch, and closed fist; keep thresholds configurable.
  - Acceptance: synthetic landmark fixtures verify each class and transition; brief detection glitches do not cause uncontrolled viewer movement.

- [ ] **P0 — Implement movement deltas and smoothing**
  - Calculate rotate/pan deltas and pinch zoom ratios; reset baselines after tracking loss.
  - Acceptance: tests cover sign/direction, zero movement, thresholds, outliers, and tracking reset.

- [ ] **P1 — Add sensitivity tuning**
  - Implement the range specified in `API.md` and expose a frontend control.
  - Acceptance: values outside the allowed range are rejected; normal settings are stable and responsive.

## Milestone 3 — WebSocket integration

- [x] **P0 — Implement versioned WebSocket contract** _(verified: backend `test_protocol.py`/`test_websocket.py`, frontend `gestureProtocol.test.ts`)_
  - Add message schemas/validation and events in `API.md`.
  - Acceptance: contract tests cover each message type, missing fields, bad types, unsupported versions, and invalid commands.

- [ ] **P0 — Add frontend WebSocket hook/service**
  - Connect to the configurable local endpoint; handle open/message/error/close and reconnect.
  - Acceptance: status is visible; there is only one active socket/reconnect loop; disconnect leaves the viewer usable.

- [ ] **P0 — Connect gestures to viewer interaction controller**
  - Apply rotate, zoom, and pan updates to the viewer.
  - Acceptance: start/update/end are handled correctly; events do not move the viewer after gesture end or tracking loss; zoom is clamped.

- [ ] **P0 — Implement camera/status error UX**
  - Show camera and tracking status, protocol errors, and connection state.
  - Acceptance: the user can tell whether the service is connected, the camera is ready, and a hand is being tracked.

- [x] **P1 — Enforce single active gesture client** _(verified: `test_single_active_client_and_slot_release`)_
  - Reject another active connection with the documented error.
  - Acceptance: connection tests prove that the camera is not opened twice and disconnect releases the slot.

## Milestone 4 — Reliability and quality

- [ ] **P0 — Verify local privacy and binding**
  - Confirm camera frames never leave the local Python process and service binds to loopback by default.
  - Acceptance: code review confirms no frame transmission/storage; origin validation and safe bind configuration are tested.

- [ ] **P1 — Test model replacement and cleanup**
  - Test loading several models in succession and disposing old resources.
  - Acceptance: no stale model remains; cleanup paths run; errors do not break subsequent uploads.

- [ ] **P1 — Test on target laptop/OS**
  - Verify webcam detection, gesture stability, supported formats, and CPU/GPU behavior.
  - Acceptance: record OS, browser, model samples, observed update rate, known limitations, and test results.

- [ ] **P1 — Profile latency and responsiveness**
  - Measure gesture update rate and perceived viewer response on a representative model.
  - Acceptance: report measured results; adjust processing cadence/smoothing if the experience is too laggy.

- [ ] **P2 — Optional on-screen camera preview**
  - Add only if it materially helps users position their hands.
  - Acceptance: preview can be disabled; it does not create another webcam reader or stream frames off-device.

- [ ] **P2 — Optional two-hand gestures**
  - Consider two-hand zoom/translation only after single-hand controls are reliable.
  - Acceptance: gestures are documented and tested without regressing the basic mappings.

## Known risks / blockers to track

- MediaPipe/OpenCV package availability may differ by operating system and Python version; validate on the target environment.
- A browser-hosted HTTPS frontend connecting to a local service has extra security and mixed-content considerations. Local development is the initial target.
- Standalone `.gltf` files may reference external files that a single-file upload cannot provide. Decide whether to support asset bundles or recommend GLB.
- Very large or high-poly models may cause browser memory/GPU pressure; practical limits need testing.
- Webcam access may fail if another application is already using the camera.

## Current status

**Phase:** Planning / initial scaffold not yet verified.

No task should be marked complete until the relevant acceptance criteria have been checked in the actual repository.
