"""Runtime configuration with safe local-development defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


@dataclass(frozen=True)
class Settings:
    """Service settings. Defaults bind to loopback and allow only local dev origins."""

    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    allow_missing_origin: bool = False
    camera_index: int = 0
    target_fps: int = 30
    model_path: Path = DEFAULT_MODEL_PATH
    max_message_bytes: int = 4096
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        origins_env = os.environ.get("GESTURE_ALLOWED_ORIGINS")
        origins = (
            tuple(o.strip() for o in origins_env.split(",") if o.strip())
            if origins_env
            else DEFAULT_ORIGINS
        )
        return cls(
            host=os.environ.get("GESTURE_HOST", cls.host),
            port=int(os.environ.get("GESTURE_PORT", cls.port)),
            allowed_origins=origins,
            allow_missing_origin=os.environ.get("GESTURE_ALLOW_MISSING_ORIGIN", "0") == "1",
            camera_index=int(os.environ.get("GESTURE_CAMERA_INDEX", cls.camera_index)),
            target_fps=int(os.environ.get("GESTURE_TARGET_FPS", cls.target_fps)),
            model_path=Path(os.environ.get("GESTURE_MODEL_PATH", str(DEFAULT_MODEL_PATH))),
            log_level=os.environ.get("GESTURE_LOG_LEVEL", cls.log_level),
        )
