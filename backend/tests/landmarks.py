"""Deterministic synthetic hand-landmark fixtures (no camera required)."""

from __future__ import annotations

from app.models import HandObservation, Landmark

# Geometry (normalized coords): wrist at y=0.9, middle MCP at y=0.7 -> hand size 0.2.
_FINGER_X = {"index": 0.44, "middle": 0.5, "ring": 0.56, "pinky": 0.62}
_BASE = {"index": 5, "middle": 9, "ring": 13, "pinky": 17}


def make_hand(
    kind: str,
    offset: tuple[float, float] = (0.0, 0.0),
    pinch_gap: float | None = None,
) -> list[Landmark]:
    """kind: 'open' | 'fist' | 'pinch' | 'point'. ``pinch_gap`` = thumb-index distance in hand sizes."""
    lm = [Landmark(0.5, 0.9)] * 21
    pts: dict[int, tuple[float, float]] = {0: (0.5, 0.9), 1: (0.45, 0.85), 2: (0.4, 0.8), 3: (0.37, 0.7)}
    for name, x in _FINGER_X.items():
        base = _BASE[name]
        extended = kind in ("open", "pinch") or (kind == "point" and name == "index")
        pts[base] = (x, 0.7)  # MCP
        pts[base + 1] = (x, 0.6) if extended else (x, 0.62)  # PIP
        pts[base + 2] = (x, 0.52) if extended else (x, 0.68)  # DIP
        pts[base + 3] = (x, 0.45) if extended else (x, 0.72)  # TIP
    if kind == "open":
        pts[4] = (0.32, 0.55)
    elif kind in ("fist", "point"):
        pts[4] = (0.36, 0.78)
    elif kind == "pinch":
        gap = 0.1 if pinch_gap is None else pinch_gap
        ix, iy = pts[8]
        pts[4] = (ix - gap * 0.2, iy)
    else:
        raise ValueError(kind)
    dx, dy = offset
    out = list(lm)
    for i, (x, y) in pts.items():
        out[i] = Landmark(x + dx, y + dy)
    return out


def obs(kind: str, offset=(0.0, 0.0), pinch_gap=None, confidence: float = 0.95, hand: str = "right") -> HandObservation:
    return HandObservation(make_hand(kind, offset, pinch_gap), hand, confidence)  # type: ignore[arg-type]
