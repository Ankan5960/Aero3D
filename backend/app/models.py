"""Shared plain data types for landmark processing."""

from __future__ import annotations

from typing import Literal, NamedTuple, Sequence

GestureName = Literal["rotate", "zoom", "pan"]
HandLabel = Literal["left", "right", "unknown"]


class Landmark(NamedTuple):
    """A hand landmark in normalized image coordinates ([0, 1], already mirrored)."""

    x: float
    y: float
    z: float = 0.0


class HandObservation(NamedTuple):
    """One frame's hand detection result (21 landmarks, MediaPipe ordering)."""

    landmarks: Sequence[Landmark]
    hand: HandLabel
    confidence: float
