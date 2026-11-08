#!/usr/bin/env python3
"""H-176 — render the Trailhead frames at the card's widths, without touching M4's pinned frames.

The renderer is the existing Field Desk frame pipeline (scripts/m2fd-frames.py). This wrapper only
moves its output directory and swaps the frame list for the H-176 evidence sizes: 1049, 900 and 460
CSS px, light and dark, plus a 200% text frame. The static render is already motionless, so the
reduced-motion frame is the same static composition.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit" / "visual" / "h176-trailhead"


def load_pipeline():
    spec = importlib.util.spec_from_file_location("m2fd_frames", ROOT / "scripts" / "m2fd-frames.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load scripts/m2fd-frames.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    pipeline = load_pipeline()
    setattr(pipeline, "OUT", OUT)
    dm = pipeline
    setattr(
        pipeline,
        "FRAMES",
        [
        {"id": "01-real-light-1049", "mode": "light", "width": 1049, "height": 1000, "font": None, "payload": dm.REAL},
        {"id": "02-real-dark-1049", "mode": "dark", "width": 1049, "height": 1000, "font": None, "payload": dm.REAL},
        {"id": "03-real-light-900", "mode": "light", "width": 900, "height": 1100, "font": None, "payload": dm.REAL},
        {"id": "04-real-dark-900", "mode": "dark", "width": 900, "height": 1100, "font": None, "payload": dm.REAL},
        {"id": "05-real-light-460", "mode": "light", "width": 460, "height": 1500, "font": None, "payload": dm.REAL},
        {"id": "06-real-dark-460", "mode": "dark", "width": 460, "height": 1500, "font": None, "payload": dm.REAL},
        {"id": "07-real-200pct-460", "mode": "light", "width": 460, "height": 1900, "font": "32px", "payload": dm.REAL},
        {"id": "08-empty-light", "mode": "light", "width": 1049, "height": 800, "font": None, "payload": dm.EMPTY},
        {"id": "09-loading-dark", "mode": "dark", "width": 1049, "height": 600, "font": None, "payload": dm.LOADING},
        {"id": "10-error-light", "mode": "light", "width": 1049, "height": 700, "font": None, "payload": dm.ERROR},
        {"id": "11-backend-off-light", "mode": "light", "width": 1049, "height": 700, "font": None, "payload": dm.BACKEND_OFF},
        {"id": "12-keyboard-focus-460", "mode": "light", "width": 460, "height": 1500, "font": None, "payload": dm.REAL, "tabs": 4},
        {"id": "13-first-use-light", "mode": "light", "width": 1049, "height": 800, "font": None, "payload": {**dm.EMPTY, "firstUse": True}},
    ],
    )
    return pipeline.main()


if __name__ == "__main__":
    sys.exit(main())
