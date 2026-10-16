# AGENTS.md — Coding Agent Instructions

## Purpose

These instructions apply to the entire repository unless a more specific `AGENTS.md` exists in a subdirectory. The project is a local-first browser-based 3D model viewer with hand-gesture controls powered by a Python computer-vision service.

## Core rules

1. **Read before editing.** Read `PROJECT.md`, `ARCHITECTURE.md`, `API.md`, `TASKS.md`, and `TESTING.md` before making substantial changes. Inspect the existing code and follow its established patterns.
2. **Keep responsibilities separated.** The frontend owns 3D rendering and viewer interaction. The Python backend owns webcam capture, hand-landmark detection, gesture classification, and gesture event production. WebSocket messages are the boundary between them.
3. **Preserve the interface contract.** Treat `API.md` as the source of truth for WebSocket message names, required fields, units, ranges, and lifecycle semantics. Update the contract and corresponding tests whenever an intentional protocol change is necessary.
4. **Keep model files in the browser.** The MVP loads STL, OBJ, GLB, and glTF files in the frontend. Do not upload model files to the Python service unless a separately approved requirement calls for server-side processing.
5. **Keep camera frames local.** The MVP captures the webcam from the local Python process and must not transmit raw frames to the frontend, an external server, or a third-party service.
6. **Avoid unrequested scope.** Do not add accounts, cloud storage, databases, analytics, payments, or remote deployment infrastructure unless explicitly requested.
7. **Prefer small, testable changes.** Keep functions focused and modules independently testable. Avoid large rewrites when a targeted change will solve the problem.
8. **Do not silently change behavior.** If a change affects gesture mappings, viewer controls, WebSocket messages, file support, or runtime setup, document it and add or update tests.
9. **Do not invent results.** Never claim that a command, test, build, or manual verification passed unless it was actually run and passed. State any tests that could not be run and why.

## Frontend conventions

- Use React with TypeScript. Prefer strict types; avoid `any` unless a specific external boundary makes it unavoidable and the reason is documented.
- Use Three.js for scence, loaders and utilities for model handling.
- Keep model loading, viewer state, gesture socket handling, and gesture-to-viewer transformations in separate modules.
- Keep mouse/touch controls available as a fallback when gesture tracking is disabled or disconnected.
- Do not mutate React state on every render frame. Use refs or the rendering loop for high-frequency Three.js updates, and use React state for UI/status changes.
- Dispose of geometries, materials, textures, object URLs, listeners, animation resources, and WebSocket connections when their owning component or service is cleaned up.
- Validate file extensions and handle loader errors. Do not assume STL, OBJ, and glTF files have identical material, color, scale, or scene semantics.
- Keep gesture sensitivity, enable/disable controls, reset-view, loading/error states, and connection status accessible from the UI.

## Python conventions

- Use type hints for public functions and important data structures.
- Keep camera capture, landmark tracking, gesture classification, smoothing, and WebSocket routing separate.
- Do not block the asyncio event loop with sustained camera reads or CPU-heavy inference. Use a suitable worker/thread boundary and document the chosen design.
- Release the camera and clean up resources after disconnects, shutdown, or exceptions.
- Handle a missing camera, camera permission failure, no detected hand, and temporary tracking loss without crashing the service.
- Normalize and validate outgoing values. Reject malformed or unsupported client commands with a documented error response.
- Keep camera access on the host machine. Never add hidden recording, persistence, or transmission of camera frames.

## WebSocket and security rules

- Follow `API.md` exactly. Include the protocol version on protocol messages where specified.
- Validate message types, ranges, and payload sizes. Ignore or reject unknown commands predictably.
- Bind the local MVP service to `127.0.0.1` by default, not `0.0.0.0`.
- Restrict accepted browser origins to configured local development origins. Do not use wildcard origin checks for a local-control service.
- Do not expose this webcam-control service directly to a public network. Remote access requires a separate security review and explicit authentication/origin design.
- Avoid logging frame data or unnecessary personal information. Logs should describe states and errors, not camera imagery.

## Dependencies and configuration

- Reuse existing dependencies before adding new ones.
- Do not upgrade or replace major dependencies without explaining why and checking compatibility.
- Keep Python dependencies in `backend/requirements.txt` and JavaScript dependencies in the frontend package manifest.
- Never commit API keys, credentials, private certificates, local machine paths, camera recordings, virtual environments, `node_modules`, or generated build output.
- Keep environment-specific values configurable; provide safe defaults for local development.

## Testing and completion requirements

Before declaring a task complete:

1. Add or update tests for changed behavior.
2. Run relevant frontend type-check/build/tests and backend tests when available.
3. Run the applicable protocol or integration tests for changes that cross the WebSocket boundary.
4. Update `TASKS.md` only when acceptance criteria are met, not merely when code has been written.
5. Update `API.md`, `ARCHITECTURE.md`, or `TESTING.md` if the change alters contracts, system responsibilities, or verification procedures.
6. Summarize changes, commands run, results, and known limitations in the final response.

## When requirements are ambiguous

Use the smallest change consistent with the existing architecture and acceptance criteria. If an ambiguity could change a public interface, privacy behavior, security boundary, or core interaction, document the assumption before proceeding. Do not make unrelated architectural changes to solve a local bug.
