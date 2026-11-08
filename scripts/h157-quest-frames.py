#!/usr/bin/env python3
"""H-157 Field Quest frames at 1049 / 900 / 460 from the shipped Desktop module.

Field Quest is a renderer surface until a backend authors short prose (the live demo profile
serves `views.field_quest: false` for every section), so this card proves its composition with the
same frame pipeline the M2-U2 evidence uses — the shipped `FieldQuestView`, real React, the real
`AttemptControls` checkpoint — rather than a mock. The live Course Detail capture is
`scripts/h157-capture.mjs` on the isolated Electron rig.

    python3 scripts/h157-quest-frames.py
    node scripts/m2fq-shot.mjs docs/h157-shots
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("m2fq_frames", ROOT / "scripts" / "m2fq-frames.py")
assert _spec and _spec.loader
m2fq_frames = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m2fq_frames)

FRAMES = [
    {"id": "quest-light-1049", "mode": "light", "width": 1049, "height": 1200, "payload": m2fq_frames.BASE},
    {"id": "quest-light-900", "mode": "light", "width": 900, "height": 1200, "payload": m2fq_frames.BASE},
    {"id": "quest-light-460", "mode": "light", "width": 460, "height": 1500, "payload": m2fq_frames.BASE},
    {"id": "quest-dark-1049", "mode": "dark", "width": 1049, "height": 1200, "payload": m2fq_frames.BASE},
    {"id": "quest-light-460-200pct", "mode": "light", "width": 460, "height": 1900, "font": "32px",
     "payload": m2fq_frames.BASE},
    {"id": "parity-textbook-light-1049", "mode": "light", "width": 1049, "height": 1200,
     "payload": {**m2fq_frames.BASE, "view": "textbook"}},
]


def main() -> int:
    m2fq_frames.OUT = ROOT / "docs" / "h157-shots"
    m2fq_frames.FRAMES = FRAMES
    return m2fq_frames.main()


if __name__ == "__main__":
    raise SystemExit(main())
