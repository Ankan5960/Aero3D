"""Landmark-based static gesture classification (pure functions, no camera needed).

Gesture mapping (application rules, not MediaPipe built-ins):
  open palm -> "rotate", pinch (thumb+index) -> "zoom", closed fist -> "pan".
"""

from __future__ import annotations

import math
from typing import Sequence

from .models import GestureName, Landmark

WRIST = 0
THUMB_TIP = 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20

LANDMARK_COUNT = 21
# (pip, tip) pairs for index, middle, ring, pinky
_FINGERS = ((INDEX_PIP, INDEX_TIP), (MIDDLE_PIP, MIDDLE_TIP), (RING_PIP, RING_TIP), (PINKY_PIP, PINKY_TIP))


def _dist(a: Landmark, b: Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_size(lm: Sequence[Landmark]) -> float:
    """Reference scale: wrist to middle-finger MCP distance."""
    return _dist(lm[WRIST], lm[MIDDLE_MCP])


def pinch_distance(lm: Sequence[Landmark]) -> float | None:
    """Thumb-tip to index-tip distance normalized by hand size (None if degenerate)."""
    size = hand_size(lm)
    if size < 1e-6:
        return None
    return _dist(lm[THUMB_TIP], lm[INDEX_TIP]) / size


def extended_finger_count(lm: Sequence[Landmark]) -> int:
    """Count index/middle/ring/pinky fingers whose tip is farther from the wrist than the PIP joint."""
    wrist = lm[WRIST]
    return sum(1 for pip, tip in _FINGERS if _dist(wrist, lm[tip]) > _dist(wrist, lm[pip]) * 1.05)


def palm_center(lm: Sequence[Landmark]) -> tuple[float, float]:
    """Stable hand anchor: mean of wrist and the four finger MCP joints."""
    pts = [lm[i] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)]
    return sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)


def classify(lm: Sequence[Landmark], pinch_threshold: float = 0.35) -> GestureName | None:
    """Classify a single frame. Returns None when no mapped gesture is recognized.

    ``pinch_threshold`` is the max normalized thumb-index distance counted as a pinch;
    callers pass a larger value while zoom is active to provide hysteresis.
    """
    if len(lm) != LANDMARK_COUNT:
        return None
    pinch = pinch_distance(lm)
    if pinch is None:
        return None
    if pinch < pinch_threshold:
        return "zoom"
    extended = extended_finger_count(lm)
    if extended >= 3:
        return "rotate"
    if extended == 0:
        return "pan"
    return None
