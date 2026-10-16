"""FastAPI entrypoint: ``uvicorn app.main:app --host 127.0.0.1 --port 8000``."""

from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import protocol
from .camera import FrameSource, OpenCVCamera
from .config import Settings
from .gesture_processor import GestureConfig, GestureProcessor
from .gesture_service import GestureService
from .hand_tracker import HandDetector, MediaPipeHandTracker
from .websocket_manager import ClientSlot, OutboundBuffer

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    camera_factory: Callable[[], FrameSource] | None = None,
    tracker_factory: Callable[[], HandDetector] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cam_factory = camera_factory or (lambda: OpenCVCamera(settings.camera_index))
    trk_factory = tracker_factory or (lambda: MediaPipeHandTracker(settings.model_path))

    app = FastAPI(title="Aero3D gesture service")
    slot = ClientSlot()
    cleanup_tasks: set[asyncio.Future] = set()  # keep strong refs to in-flight cleanups
    seq = itertools.count(1).__next__  # monotonic for the lifetime of the process
    app.state.settings = settings
    app.state.slot = slot

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": protocol.SERVICE_NAME,
            "protocol_version": protocol.PROTOCOL_VERSION,
            "client_connected": slot.occupied,
            "model_available": settings.model_path.is_file(),
        }

    def origin_allowed(origin: str | None) -> bool:
        if origin is None:
            return settings.allow_missing_origin
        return origin in settings.allowed_origins

    async def sender(ws: WebSocket, buffer: OutboundBuffer) -> None:
        while True:
            for msg in await buffer.get_batch():
                await ws.send_json(msg)

    @app.websocket("/ws/gestures")
    async def ws_gestures(ws: WebSocket) -> None:
        if not origin_allowed(ws.headers.get("origin")):
            logger.warning("Rejected WebSocket from disallowed origin")
            await ws.close(code=1008)
            return
        await ws.accept()
        owner = object()
        if not slot.try_acquire(owner):
            await ws.send_json(
                protocol.error("CLIENT_ALREADY_CONNECTED", "Another gesture client is already connected.")
            )
            await ws.close(code=1013)
            return

        logger.info("Gesture client connected")
        loop = asyncio.get_running_loop()
        buffer = OutboundBuffer()

        def sink(msg: dict) -> None:
            loop.call_soon_threadsafe(buffer.push, msg)

        service = GestureService(
            sink=sink,
            camera_factory=cam_factory,
            tracker_factory=trk_factory,
            processor=GestureProcessor(GestureConfig(), seq_source=seq),
            target_fps=settings.target_fps,
            preview_window=settings.preview_window,
        )
        send_task = asyncio.create_task(sender(ws, buffer))
        try:
            buffer.push(protocol.hello())
            service.start()
            while True:
                raw = await ws.receive_text()
                try:
                    cmd = protocol.parse_command(raw, settings.max_message_bytes)
                except protocol.ProtocolError as exc:
                    buffer.push(protocol.error(exc.code, exc.message, recoverable=True))
                    continue
                if cmd.name == "set_enabled":
                    service.set_enabled(bool(cmd.enabled))
                    buffer.push(protocol.ack("set_enabled"))
                elif cmd.name == "set_sensitivity":
                    service.set_sensitivity(float(cmd.value))  # type: ignore[arg-type]
                    buffer.push(protocol.ack("set_sensitivity"))
                elif cmd.name == "ping":
                    buffer.push(protocol.pong(cmd.timestamp_ms))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("WebSocket handler error")
        finally:
            send_task.cancel()

            async def cleanup() -> None:
                await asyncio.to_thread(service.stop)
                slot.release(owner)
                logger.info("Gesture client disconnected; camera released")

            cleanup_task = asyncio.ensure_future(cleanup())
            cleanup_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(cleanup_tasks.discard)
            await asyncio.shield(cleanup_task)

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    s = Settings.from_env()
    uvicorn.run("app.main:app", host=s.host, port=s.port)
