"""Download the MediaPipe hand landmarker model into backend/models/ (explicit, one-time)."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DEFAULT_MODEL_PATH  # noqa: E402
from app.hand_tracker import MODEL_URL  # noqa: E402


def main() -> None:
    dest = DEFAULT_MODEL_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"Model already present: {dest}")
        return
    print(f"Downloading {MODEL_URL}\n  -> {dest}")
    urllib.request.urlretrieve(MODEL_URL, dest)
    print("Done.")


if __name__ == "__main__":
    main()
