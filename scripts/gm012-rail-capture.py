#!/usr/bin/env python3
"""GM-012 evidence packet: paint the shipped TutorRail at the card's required widths.

Component evidence, not a live Desktop capture. ``scripts/gm012-rail-render.mjs`` renders the
shipped component with the module's own token styles; ``scripts/m4v-audit.mjs`` paints each frame
in headless Chromium and records contrast, clipping, overflow, unnamed controls and target sizes.
The MANIFEST states what this does not prove.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_desktop_lesson_views import _desktop_node_modules  # noqa: E402

OUT = ROOT / "docs" / "visual-review" / "gm-012"
SCRATCH = Path(tempfile.mkdtemp(prefix="gm012-rail-"))

FRAMES = []
for surface in ("ask", "quote", "practice", "no-lesson"):
    for mode in ("light", "dark"):
        for width in (1049, 900, 460):
            rail_width = 340 if width >= 900 else 460
            FRAMES.append({
                "id": f"rail-{surface}--{width}--{mode}",
                "render": f"rail-{surface}-{width}-{mode}",
                "surface": surface,
                "mode": mode,
                "width": width,
                "height": 1100,
                "font_px": 16,
                "railWidth": rail_width,
                "forced_colors": "none",
            })
        FRAMES.append({
            "id": f"rail-{surface}--460--200--{mode}",
            "render": f"rail-{surface}-460-200-{mode}",
            "surface": surface,
            "mode": mode,
            "width": 460,
            "height": 1600,
            "font_px": 32,
            "railWidth": 420,
            "forced_colors": "none",
        })


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 1
    (SCRATCH / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (SCRATCH / "gm012-rail-render.mjs").write_text(
        (ROOT / "scripts" / "gm012-rail-render.mjs").read_text(encoding="utf-8"), encoding="utf-8"
    )
    node_modules = SCRATCH / "node_modules"
    node_modules.mkdir(exist_ok=True)
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir() and not (node_modules / name).exists():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True, exist_ok=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    from tests.test_desktop_lesson_views import SDK_STUB

    (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
    frames_doc = {"frames": FRAMES, "html_dir": str(SCRATCH), "outDir": str(SCRATCH), "reference_time": None}
    (SCRATCH / "frames.json").write_text(json.dumps(frames_doc), encoding="utf-8")
    render = subprocess.run(
        ["node", str(SCRATCH / "gm012-rail-render.mjs"), str(SCRATCH / "frames.json")],
        cwd=SCRATCH, capture_output=True, text=True, timeout=300,
    )
    print(render.stdout[-2000:])
    if render.returncode != 0:
        print(render.stderr[-3000:], file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    audit = subprocess.run(
        ["node", str(ROOT / "scripts" / "m4v-audit.mjs"), str(SCRATCH / "frames.json"), str(OUT)],
        capture_output=True, text=True, timeout=900,
    )
    print(audit.stdout[-4000:])
    if audit.returncode != 0:
        print(audit.stderr[-3000:], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
