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
        preview_window: bool = True,
    ) -> None:
        self._sink = sink
        self._camera_factory = camera_factory
        self._tracker_factory = tracker_factory
        self._processor = processor
        self._interval = 1.0 / max(1, target_fps)
        self._preview_window = preview_window
        self._window_name = "Aero3D Hand Tracking - Camera Preview"
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
            if self._preview_window:
                self._close_preview()
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

            if self._preview_window and hasattr(frame, "shape") and len(frame.shape) == 3:
                self._update_preview(frame, obs)

            self._stop.wait(self._interval)

    def _update_preview(self, frame_bgr: Any, obs: Any) -> None:
        try:
            import cv2

            h, w = frame_bgr.shape[:2]
            display = cv2.flip(frame_bgr, 1)

            if obs is not None and getattr(obs, "landmarks", None):
                pts = [(int(lm.x * w), int(lm.y * h)) for lm in obs.landmarks]
                connections = [
                    (0, 1), (1, 2), (2, 3), (3, 4),
                    (0, 5), (5, 6), (6, 7), (7, 8),
                    (5, 9), (9, 10), (10, 11), (11, 12),
                    (9, 13), (13, 14), (14, 15), (15, 16),
                    (13, 17), (17, 18), (18, 19), (19, 20),
                    (0, 17),
                ]
                for p1, p2 in connections:
                    if 0 <= p1 < len(pts) and 0 <= p2 < len(pts):
                        cv2.line(display, pts[p1], pts[p2], (255, 191, 0), 2)

                for i, pt in enumerate(pts):
                    if i in (4, 8):
                        cv2.circle(display, pt, 6, (0, 165, 255), -1)
                        cv2.circle(display, pt, 8, (255, 255, 255), 1)
                    else:
                        cv2.circle(display, pt, 4, (147, 20, 255), -1)
                        cv2.circle(display, pt, 2, (255, 255, 255), -1)

            active = getattr(self._processor, "_active", None) or "none"
            tracking = getattr(self._processor, "tracking", "searching")
            status_color = (0, 255, 128) if tracking == "tracking" else (0, 165, 255)

            cv2.rectangle(display, (0, 0), (w, 55), (20, 20, 30), -1)
            cv2.line(display, (0, 55), (w, 55), status_color, 2)

            text_gesture = f"Gesture: {active.upper()}"
            if active == "rotate":
                text_gesture += " (Open Palm)"
            elif active == "zoom":
                text_gesture += " (Pinch)"
            elif active == "pan":
                text_gesture += " (Fist)"

            cv2.putText(display, text_gesture, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

            info = f"Tracking: {tracking.upper()}"
            if obs is not None and hasattr(obs, "hand"):
                info += f" | {obs.hand.upper()} ({int(getattr(obs, 'confidence', 0) * 100)}%)"
            cv2.putText(display, info, (15, 47), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1)

            cv2.imshow(self._window_name, display)
            cv2.waitKey(1)
        except Exception as exc:
            logger.debug("Preview window update failed: %s", exc)
            self._preview_window = False

    def _close_preview(self) -> None:
        try:
            import cv2

            cv2.destroyWindow(self._window_name)
            cv2.waitKey(1)
        except Exception:
            pass
