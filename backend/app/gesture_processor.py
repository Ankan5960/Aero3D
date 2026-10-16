"""Gesture lifecycle state machine: stability, smoothing, dead zones, deltas.

Coordinate model: positions are normalized to [0, 1] in the *mirrored* camera view
(x grows to the user's right, y grows downward). Deltas are screen-space changes since the
previous valid sample; positive delta.y means the hand moved down. For zoom, a pinch
distance that grows (fingers spreading) yields scale_delta > 1 (zoom in).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from . import protocol
from .gesture_classifier import classify, palm_center, pinch_distance
from .models import HandObservation


@dataclass
class GestureConfig:
    min_confidence: float = 0.6
    stable_frames: int = 3  # consecutive frames required to start a gesture
    release_frames: int = 3  # consecutive differing frames required to end a gesture
    lost_frames: int = 4  # consecutive missing frames before tracking is "lost"
    smoothing: float = 0.5  # EMA alpha in (0, 1]; higher = less smoothing
    dead_zone: float = 0.002  # min normalized movement magnitude to emit
    max_delta: float = 0.1  # per-update clamp for each delta axis
    pinch_enter: float = 0.35
    pinch_exit: float = 1.1
    zoom_dead_zone: float = 0.01
    zoom_max_step: float = 1.1  # scale_delta clamped to [1/step, step]
    sensitivity: float = 1.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class GestureProcessor:
    """Feeds per-frame hand observations in, produces protocol ``gesture`` messages out."""

    def __init__(self, config: GestureConfig | None = None, seq_source: Callable[[], int] | None = None) -> None:
        self.config = config or GestureConfig()
        self._next_seq = seq_source or _SeqCounter()
        self.enabled = True
        self.tracking = "searching"
        self._active: str | None = None
        self._candidate: str | None = None
        self._candidate_count = 0
        self._release_count = 0
        self._missed = 0
        self._hand = "unknown"
        self._confidence = 0.0
        self._last_pos = (0.5, 0.5)
        self._smooth_pos: tuple[float, float] | None = None
        self._prev_pos: tuple[float, float] | None = None
        self._smooth_dist: float | None = None
        self._prev_dist: float | None = None

    # ---------------------------------------------------------------- control

    def set_sensitivity(self, value: float) -> None:
        self.config.sensitivity = _clamp(value, protocol.SENSITIVITY_MIN, protocol.SENSITIVITY_MAX)

    def set_enabled(self, enabled: bool, timestamp_ms: int | None = None) -> list[dict[str, Any]]:
        """Enable/disable processing. Disabling ends any active gesture first."""
        msgs: list[dict[str, Any]] = []
        if self.enabled and not enabled:
            msgs = self._end_active(timestamp_ms)
            self._reset_candidate()
            self.tracking = "disabled"
        elif not self.enabled and enabled:
            self._reset_candidate()
            self._missed = 0
            self.tracking = "searching"
        self.enabled = enabled
        return msgs

    def reset(self, timestamp_ms: int | None = None) -> list[dict[str, Any]]:
        """End any active gesture and clear all tracking state (e.g. on shutdown)."""
        msgs = self._end_active(timestamp_ms)
        self._reset_candidate()
        self._missed = 0
        if self.enabled:
            self.tracking = "searching"
        return msgs

    # ---------------------------------------------------------------- process

    def process(self, obs: HandObservation | None, timestamp_ms: int | None = None) -> list[dict[str, Any]]:
        """Process one frame; returns gesture messages (``self.tracking`` holds tracking state)."""
        if not self.enabled:
            return []
        cfg = self.config
        msgs: list[dict[str, Any]] = []

        if obs is None or obs.confidence < cfg.min_confidence or len(obs.landmarks) != 21:
            self._missed += 1
            if self._missed >= cfg.lost_frames:
                msgs += self._end_active(timestamp_ms)
                self._reset_candidate()
                if self.tracking == "tracking":
                    self.tracking = "lost"
            return msgs

        self._missed = 0
        self.tracking = "tracking"
        self._hand = obs.hand
        self._confidence = obs.confidence
        lm = obs.landmarks

        threshold = cfg.pinch_exit if self._active == "zoom" else cfg.pinch_enter
        kind = classify(lm, pinch_threshold=threshold)
        pos = palm_center(lm)
        dist = pinch_distance(lm)

        if self._active is None:
            self._maybe_start(kind, pos, dist, timestamp_ms, msgs)
        elif kind == self._active:
            self._release_count = 0
            self._update(pos, dist, timestamp_ms, msgs)
        else:
            # Brief glitch: emit nothing and drop baselines so we never jump on recovery.
            self._release_count += 1
            self._smooth_pos = self._prev_pos = None
            self._smooth_dist = self._prev_dist = None
            if self._release_count >= cfg.release_frames:
                msgs += self._end_active(timestamp_ms)
                self._candidate, self._candidate_count = (kind, 1) if kind else (None, 0)
        return msgs

    # ---------------------------------------------------------------- internals

    def _maybe_start(self, kind, pos, dist, ts, msgs) -> None:
        if kind is None:
            self._reset_candidate()
            return
        if kind == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate, self._candidate_count = kind, 1
        if self._candidate_count >= self.config.stable_frames:
            self._active = kind
            self._release_count = 0
            self._smooth_pos = self._prev_pos = pos
            self._smooth_dist = self._prev_dist = dist
            self._last_pos = pos
            msgs.append(self._message("start", (0.0, 0.0), 1.0 if kind == "zoom" else None, ts))
            self._reset_candidate()

    def _update(self, pos, dist, ts, msgs) -> None:
        cfg = self.config
        a = cfg.smoothing
        if self._smooth_pos is None or self._prev_pos is None:
            self._smooth_pos = self._prev_pos = pos
            self._smooth_dist = self._prev_dist = dist
            return
        self._smooth_pos = (
            self._smooth_pos[0] + a * (pos[0] - self._smooth_pos[0]),
            self._smooth_pos[1] + a * (pos[1] - self._smooth_pos[1]),
        )
        self._last_pos = (_clamp(self._smooth_pos[0], 0, 1), _clamp(self._smooth_pos[1], 0, 1))

        if self._active == "zoom":
            if dist is None or self._smooth_dist is None or self._prev_dist is None:
                return
            self._smooth_dist += a * (dist - self._smooth_dist)
            if self._prev_dist < 1e-6:
                self._prev_dist = self._smooth_dist
                return
            ratio = self._smooth_dist / self._prev_dist
            if abs(ratio - 1.0) < cfg.zoom_dead_zone:
                return
            ratio = _clamp(ratio, 1 / cfg.zoom_max_step, cfg.zoom_max_step)
            ratio = _clamp(ratio ** cfg.sensitivity, 1 / cfg.zoom_max_step, cfg.zoom_max_step)
            self._prev_dist = self._smooth_dist
            msgs.append(self._message("update", (0.0, 0.0), ratio, ts))
            return

        dx = self._smooth_pos[0] - self._prev_pos[0]
        dy = self._smooth_pos[1] - self._prev_pos[1]
        if math.hypot(dx, dy) < cfg.dead_zone:
            return
        self._prev_pos = self._smooth_pos
        dx = _clamp(dx * cfg.sensitivity, -cfg.max_delta, cfg.max_delta)
        dy = _clamp(dy * cfg.sensitivity, -cfg.max_delta, cfg.max_delta)
        msgs.append(self._message("update", (dx, dy), None, ts))

    def _end_active(self, ts: int | None) -> list[dict[str, Any]]:
        if self._active is None:
            return []
        msg = self._message("end", (0.0, 0.0), None, ts)
        self._active = None
        self._release_count = 0
        self._smooth_pos = self._prev_pos = None
        self._smooth_dist = self._prev_dist = None
        return [msg]

    def _reset_candidate(self) -> None:
        self._candidate = None
        self._candidate_count = 0

    def _message(self, phase, delta, scale, ts) -> dict[str, Any]:
        return protocol.gesture(
            seq=self._next_seq(),
            gesture_name=self._active_name(phase),
            phase=phase,
            hand=self._hand,
            confidence=self._confidence,
            position=self._last_pos,
            delta=delta,
            scale_delta=scale if self._active_name(phase) == "zoom" and scale is not None else None,
            timestamp_ms=ts,
        )

    def _active_name(self, phase: str) -> str:
        # During "start" the gesture is the candidate (already promoted to _active before calling).
        return self._active or "none"


@dataclass
class _SeqCounter:
    value: int = field(default=0)

    def __call__(self) -> int:
        self.value += 1
        return self.value
