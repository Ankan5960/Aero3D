# Aero3D

A local-first, browser-based 3D model viewer (STL · OBJ · GLB · glTF) that can be controlled with
hand gestures from your laptop webcam. The browser renders the model; a local Python service reads
the webcam, detects hand landmarks, and sends compact gesture events over a WebSocket.

- Camera frames **never leave the Python process** (no upload, no storage, no frame streaming).
- Model files **never leave the browser**.
- Mouse/touch controls always work, with or without gestures.

| Gesture | Action |
|---|---|
| Open palm | Rotate (move hand) |
| Pinch (thumb + index) | Zoom (spread / close fingers) |
| Closed fist | Pan (move hand) |

Design docs live in [`Agents/`](Agents): `PROJECT.md`, `ARCHITECTURE.md`, `API.md`, `TASKS.md`, `TESTING.md`, `AGENTS.md`.

## Quick start (Windows PowerShell)

### 1. Backend (Python 3.10–3.12)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/download_model.py        # one-time download of the MediaPipe hand model
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same `pip`/`uvicorn` commands.

### 2. Frontend (Node 20+)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173> (or `http://localhost:5173`), choose a model, then click **Enable gestures**.
The camera is only opened while gestures are enabled and the browser is connected.

## Configuration

Backend environment variables (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `GESTURE_HOST` | `127.0.0.1` | Bind address (keep loopback) |
| `GESTURE_PORT` | `8000` | Port |
| `GESTURE_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins (comma-separated) |
| `GESTURE_ALLOW_MISSING_ORIGIN` | `0` | Set `1` to allow non-browser clients with no `Origin` header |
| `GESTURE_CAMERA_INDEX` | `0` | Webcam index |
| `GESTURE_TARGET_FPS` | `30` | Inference/event cadence cap |
| `GESTURE_MODEL_PATH` | `backend/models/hand_landmarker.task` | Hand-landmarker model file |
| `GESTURE_PREVIEW_WINDOW` | `1` | Show local desktop camera pop-up window with hand landmarks (1=on, 0=off) |

Frontend: copy `frontend/.env.example` to `.env.local` and set `VITE_GESTURE_WS_URL` if needed.

## Tests

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest
cd frontend; npm run typecheck; npm run test; npm run build
```

See [`Agents/TESTING.md`](Agents/TESTING.md) for the manual hardware checklist.

## Notes

- Standalone `.gltf` files that reference external `.bin`/texture files cannot be loaded from a single
  file selection; use a self-contained `.glb` (the app explains this).
- OBJ materials (`.mtl`) are not loaded; default shading is used.
- Not for public networks: the service controls a webcam and is intended for `127.0.0.1` only.
