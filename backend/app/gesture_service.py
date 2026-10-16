"""Camera/inference worker thread that publishes protocol messages to a sink.

Design: one daemon worker thread owns the camera, the tracker and the gesture
processor, so blocking OpenCV/MediaPipe calls never run on the asyncio event loop.
Messages are handed to ``sink`` (which must be thread-safe, e.g. via
``loop.call_soon_threadsafe``). The camera is opened only while a client is connected
and is always released in ``finally``.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from . import protocol
from .camera import CameraUnavailableError, FrameSource
from .gesture_processor import GestureProcessor
from .hand_tracker import HandDetector, TrackerUnavailableError

logger = logging.getLogger(__name__)

Sink = Callable[[dict[str, Any]], None]
MAX_CONSECUTIVE_READ_FAILURES = 30


class GestureService:
    def __init__(
        self,
        *,
        sink: Sink,
        camera_factory: Callable[[], FrameSource],
        tracker_factory: Callable[[], HandDetector],
        processor: GestureProcessor,
        target_fps: int = 30,
    ) -> None:
        self._sink = sink
        self._camera_factory = camera_factory
        self._tracker_factory = tracker_factory
        self._processor = processor
        self._interval = 1.0 / max(1, target_fps)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._camera_state = "stopped"
        self._tracking_override: str | None = None
        self._status_message: str | None = None
        self._last_status: tuple | None = None

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="gesture-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():  # pragma: no cover - defensive
                logger.warning("Gesture worker did not stop within %.1fs", timeout)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -------------------------------------------------------------- commands

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            for msg in self._processor.set_enabled(enabled, protocol.now_ms()):
                self._emit(msg)
            self._emit_status_if_changed()

    def set_sensitivity(self, value: float) -> None:
        with self._lock:
            self._processor.set_sensitivity(value)

    # -------------------------------------------------------------- internals

    def _emit(self, msg: dict[str, Any]) -> None:
        try:
            self._sink(msg)
        except Exception:  # sink failures (e.g. closed loop) must not kill the worker
            logger.debug("Sink rejected message", exc_info=True)

    def _emit_status_if_changed(self) -> None:
        with self._lock:
            tracking = self._tracking_override or self._processor.tracking
            snapshot = (self._camera_state, tracking, self._processor.enabled, self._status_message)
            if snapshot == self._last_status:
                return
            self._last_status = snapshot
            self._emit(protocol.status(snapshot[0], snapshot[1], snapshot[2], snapshot[3]))

    def _set_camera(self, state: str, message: str | None = None, tracking_override: str | None = None) -> None:
        with self._lock:
            self._camera_state = state
            self._status_message = message
            self._tracking_override = tracking_override
            self._emit_status_if_changed()

    def _fail(self, code: str, user_message: str, recoverable: bool = True) -> None:
        self._emit(protocol.error(code, user_message, recoverable))
        self._set_camera("error", user_message, tracking_override="error")

    def _run(self) -> None:
        camera: FrameSource | None = None
        tracker: HandDetector | None = None
        try:
            self._set_camera("starting")
            try:
                tracker = self._tracker_factory()
            except TrackerUnavailableError as exc:
                logger.error("Tracker unavailable: %s", exc)
                self._fail("INTERNAL_ERROR", str(exc), recoverable=False)
                return
            camera = self._camera_factory()
            try:
                camera.open()
            except CameraUnavailableError:
                self._fail(
                    "CAMERA_UNAVAILABLE",
                    "The webcam could not be opened. It may be missing, in use, or blocked by OS permissions.",
                )
                return
            self._set_camera("ready")
            self._loop(camera, tracker)
        except Exception:
            logger.exception("Gesture worker crashed")
            self._fail("INTERNAL_ERROR", "Gesture tracking stopped unexpectedly.", recoverable=False)
        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Camera release failed")
            if tracker is not None:
                try:
                    tracker.close()
                except Exception:  # pragma: no cover - defensive
                    logger.exception("Tracker close failed")
            with self._lock:
                for msg in self._processor.reset(protocol.now_ms()):
                    self._emit(msg)
            if self._camera_state != "error":
                self._set_camera("stopped")

    def _loop(self, camera: FrameSource, tracker: HandDetector) -> None:
        failures = 0
        while not self._stop.is_set():
            if not self._processor.enabled:
                self._stop.wait(0.1)
                continue
            frame = camera.read()
            if frame is None:
                failures += 1
                if failures >= MAX_CONSECUTIVE_READ_FAILURES:
                    self._fail("CAMERA_UNAVAILABLE", "The webcam stopped delivering frames.")
                    return
                self._stop.wait(0.03)
                continue
            failures = 0
            ts = protocol.now_ms()
            obs = tracker.detect(frame, ts)
            with self._lock:
                for msg in self._processor.process(obs, ts):
                    self._emit(msg)
                self._emit_status_if_changed()
            self._stop.wait(self._interval)
