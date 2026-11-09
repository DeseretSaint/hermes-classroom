"""H-183 check-surface frames: the shipped Field Quest checkpoint, before and after.

`scripts/m2fq-frames.py` already composes the lesson document with a live-shaped check and renders
the shipped module. This driver only points its output at the H-183 evidence directory and keeps the
four widths modes the card names. The "before" PNGs are the committed frames under
`audit/visual/m2-field-quest` (same harness, module at d84cfc5); the card's before/after pair for the
check caption is those files against these.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit" / "visual" / "h183-copy" / "check-after"
BEFORE = ROOT / "audit" / "visual" / "h183-copy" / "check-before"

spec = importlib.util.spec_from_file_location("m2fq_frames", ROOT / "scripts" / "m2fq-frames.py")
frames_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames_module)

frames_module.OUT = OUT
frames_module.FRAMES = [
    frame for frame in frames_module.FRAMES
    if frame["id"] in {
        "01-quest-light-wide",
        "02-quest-dark-wide",
        "03-quest-light-460",
        "05-quest-light-460-200pct",
    }
]

if __name__ == "__main__":
    raise SystemExit(frames_module.main())
