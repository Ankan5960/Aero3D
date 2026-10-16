"""Local webcam capture via OpenCV. Frames never leave this process."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class CameraUnavailableError(RuntimeError):
    """The webcam could not be opened (missing, busy, or permission denied)."""


class FrameSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> Any | None: ...
    def release(self) -> None: ...


class OpenCVCamera:
    """Thin wrapper around ``cv2.VideoCapture`` with explicit open/release."""

    def __init__(self, index: int = 0) -> None:
        self._index = index
        self._cap: Any = None

    def open(self) -> None:
        import cv2  # imported lazily so tests/tools without OpenCV still import the package

        cap = cv2.VideoCapture(self._index)
        if not cap.isOpened():
            cap.release()
            raise CameraUnavailableError("The webcam could not be opened.")
        self._cap = cap
        logger.info("Camera opened (index %s)", self._index)

    def read(self) -> Any | None:
        """Return a BGR frame, or None if the read failed."""
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released")
