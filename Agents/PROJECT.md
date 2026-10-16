# PROJECT.md — Project Overview

## Working title

**Gesture 3D Viewer**

## Product summary

Gesture 3D Viewer is a browser-based application for opening and inspecting 3D model files with natural hand movements captured by the user's laptop webcam. The browser renders the model. A local Python service processes the webcam feed, recognizes hand landmarks and gestures, and sends compact control events to the browser over a WebSocket connection.

The project is local-first: camera frames are processed on the same machine and are not sent to a cloud service in the MVP.

## Problem to solve

Traditional 3D viewers usually require a mouse, keyboard, or touch screen to rotate, pan, and zoom a model. This application adds a hands-free interaction mode while preserving standard controls as a fallback.

## Target users

- Developers and people exploring browser-based computer vision.
- Designers, students, and engineers who inspect 3D assets.
- Users who want to explore a model without continuously touching a mouse.
- Potential future users of dental, CAD, product-visualization, or educational 3D tools.

## Primary goals

1. Let a user select and view local 3D model files in a web browser.
2. Support STL, OBJ, GLB, and glTF model formats.
3. Use the laptop webcam via a local Python process to detect hand landmarks and classify a small set of gestures.
4. Send gesture events from Python to the frontend through a WebSocket connection.
5. Map gestures to 3D-viewer actions with responsive, stable controls.
6. Keep mouse/touch controls available and provide visible tracking/connection status.
7. Handle common errors gracefully: invalid files, unsupported formats, missing camera, no detected hand, and lost WebSocket connection.

## MVP gesture mapping

| Gesture | Intended action | Initial behavior |
|---|---|---|
| Open palm | Rotate | Hand movement controls the view's rotation/orbit. |
| Pinch (thumb and index finger) | Zoom | Change pinch distance to zoom in/out. |
| Closed fist | Pan | Hand movement shifts the view or target. |
| No recognized gesture | No gesture action | Keep the view still; mouse/touch controls remain usable. |

These mappings are application rules, not built-in MediaPipe behavior. The implementation must support tuning sensitivity and smoothing. Avoid treating brief tracking loss as a deliberate gesture.

## MVP user journey

1. Start the frontend and local Python backend.
2. Open the local web application.
3. Upload/select an STL, OBJ, GLB, or glTF file.
4. Inspect it using the mouse or touch controls.
5. Enable hand tracking and grant any required operating-system camera permission to the Python process.
6. View camera/connection/tracking status in the UI.
7. Use open-palm, pinch, and fist gestures to rotate, zoom, and pan.
8. Reset the view or disable gestures at any time.

## Scope included in the MVP

- Client-side model loading and rendering.
- Local webcam capture and hand-landmark processing.
- Gesture classification and smoothing.
- WebSocket event transport and connection status.
- Viewer rotation/orbit, zoom, pan, and reset.
- Sensible loading, error, and empty states.
- Unit and integration tests for key logic and message contracts.

## Explicitly out of scope for the MVP

- User accounts, sign-in, or role-based access.
- Cloud upload, model hosting, collaboration, and shared sessions.
- A database or persistent history of uploaded models.
- Uploading camera frames to remote infrastructure.
- Training a custom ML model; use an available hand-landmark model initially.
- Medical/dental measurement, diagnosis, engineering validation, or claims of measurement-grade accuracy.
- Multi-user concurrent webcam sessions.
- Native mobile apps and deployment as a public hosted webcam service.

## Proposed stack

### Frontend

- React + TypeScript, using Vite for development tooling.
- Three.js via React Three Fiber.
- `@react-three/drei` for useful scene helpers and controls.
- Three.js loaders: `STLLoader`, `OBJLoader`, and `GLTFLoader` (GLB is loaded through `GLTFLoader`).
- WebSocket API for gesture events.

### Local backend

- Python.
- FastAPI and its WebSocket support.
- OpenCV for camera capture.
- MediaPipe Hand Landmarker for hand landmarks.
- NumPy for coordinate/distance calculations where useful.

### Communication

- WebSocket endpoint: `ws://127.0.0.1:8000/ws/gestures` in local development.
- JSON control/status events as defined in `API.md`.

## Non-functional requirements

- **Responsiveness:** target roughly 20–30 gesture updates per second on a typical supported laptop; measure performance rather than assuming the target is met.
- **Local privacy:** raw camera frames remain in the Python process and are not transmitted or stored by the application.
- **Recoverability:** losing the camera or WebSocket connection must not crash the viewer; mouse controls should remain usable.
- **Clarity:** show whether the service is connected, tracking is active, and a gesture is currently recognized.
- **Portability:** document setup for supported Windows, macOS, and Linux environments where dependencies permit. Test the target OS explicitly before claiming support.
- **Usability:** include reset, gesture enable/disable, status messages, and sensible default sensitivity.

## Success criteria

The MVP is successful when a user can load each supported format, inspect the model with standard controls, start local gesture tracking, and reliably rotate/zoom/pan using the documented gestures without sending webcam frames off-device. See `TASKS.md` and `TESTING.md` for verifiable acceptance criteria.

## Open decisions

Record decisions here until they are resolved in implementation:

- Whether gestures manipulate the camera/orbit controls or the model transform. Default: camera/orbit controls for a familiar inspection experience.
- Whether the MVP should allow multiple browser tabs to share one camera process. Default: one active gesture WebSocket client.
- The precise dependency versions and supported OS matrix.
- The final UI styling and whether a camera preview is needed. Default: show tracking status first; do not display a preview unless it provides clear value.
