"""MediaPipe Hand Landmarker wrapper. Produces :class:`HandObservation` per frame."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from .models import HandObservation, Landmark

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)


class TrackerUnavailableError(RuntimeError):
    """The hand-landmark model/library could not be initialised."""


class HandDetector(Protocol):
    def detect(self, frame_bgr: Any, timestamp_ms: int) -> HandObservation | None: ...
    def close(self) -> None: ...


class MediaPipeHandTracker:
    """Single-hand tracker. The frame is mirrored so x matches the user's view of themselves."""

    def __init__(self, model_path: Path, min_detection_confidence: float = 0.5) -> None:
        if not Path(model_path).is_file():
            raise TrackerUnavailableError(
                "Hand landmark model not found. Run 'python scripts/download_model.py' in backend/."
            )
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise TrackerUnavailableError("MediaPipe is not installed.") from exc

        self._mp = mp
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_detection_confidence,
        )
        try:
            self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise TrackerUnavailableError("Hand landmark model failed to load.") from exc
        self._last_ts = -1

    def detect(self, frame_bgr: Any, timestamp_ms: int) -> HandObservation | None:
        import cv2

        # MediaPipe requires strictly increasing timestamps in VIDEO mode.
        ts = max(timestamp_ms, self._last_ts + 1)
        self._last_ts = ts
        rgb = cv2.cvtColor(cv2.flip(frame_bgr, 1), cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts)
        if not result.hand_landmarks:
            return None
        lms = [Landmark(p.x, p.y, p.z) for p in result.hand_landmarks[0]]
        hand, score = "unknown", 0.0
        if result.handedness and result.handedness[0]:
            cat = result.handedness[0][0]
            name = (cat.category_name or "").lower()
            hand = name if name in ("left", "right") else "unknown"
            score = float(cat.score)
        return HandObservation(landmarks=lms, hand=hand, confidence=score)  # type: ignore[arg-type]

    def close(self) -> None:
        self._landmarker.close()
