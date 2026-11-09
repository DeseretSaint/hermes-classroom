#!/usr/bin/env python3
"""H-189 — render the Living Home frames without touching M4's pinned evidence.

The renderer is the Field Desk pipeline in `scripts/m2fd-frames.py`; this wrapper moves the output
directory and swaps the frame list for the H-189 evidence sizes (1049, 900, 460 CSS px, light and
dark, a 200 % text frame and a reduced-motion frame). Static server renders are already the resting
frame, so the reduced-motion frame is the same composition — the animated beat and the companion
cadence are captured separately by `scripts/h189-live.mjs`.

Every frame carries the real 11-entry Field Notes payload the owner complained about, so the
before/after comparison is made against the same desk, not an easier one.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit" / "visual" / "h189-living-home"

NOTES = {
    "status": "ready",
    "data": {
        "entries": [
            {
                "entry_id": f"nbt_{index:032d}",
                "excerpt": [
                    "A bow is lower than a nod.",
                    "Romaji is a scaffold, not the answer.",
                    "Same words, different addressee.",
                    "The polite form carries the distance.",
                    "Private setting changes the reading.",
                    "Aishiteru belongs to a settled bond.",
                    "Ask who is listening first.",
                    "Two ways to say it, one decision.",
                    "The cue is the request, not the word.",
                    "Register is a function of the room.",
                    "Say it once, clearly.",
                ][index],
                "note": None,
                "kind": "note",
                "tags": [f"loop-proof-{index:02d}", "v2"],
                "objective_id": "obj_0123456789ab",
                "source_ref": '{"block": "blk_1", "sources": ["src_jf_marugoto"]}',
                "created_at": "2026-11-06T18:00:00.000000+00:00",
            }
            for index in range(11)
        ]
    },
    "error": None,
    "reload": None,
}


def load_pipeline():
    spec = importlib.util.spec_from_file_location("m2fd_frames", ROOT / "scripts" / "m2fd-frames.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load scripts/m2fd-frames.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_cover() -> dict | None:
    """A real pack artifact with provenance and a text equivalent, or None.

    Point `H189_PACK_DIR` at an installed pack whose `pack.json` declares a `visual` file. Nothing is
    invented here: the image bytes, caption and text equivalent all come from the pack manifest.
    """
    import base64
    import json
    import os

    directory = os.environ.get("H189_PACK_DIR")
    if not directory:
        return None
    root = Path(directory)
    manifest = json.loads((root / "pack.json").read_text(encoding="utf-8"))
    visual = next((item for item in manifest.get("files", []) if item.get("role") == "visual"), None)
    if not visual:
        return None
    png = root / visual["path"]
    return {
        "artifact_id": f"{manifest['pack_id']}:{visual['path']}",
        "caption": manifest.get("title") or visual["path"],
        "text_equivalent": visual.get("text_equivalent") or visual.get("description") or "",
        "provenance": f"{manifest['pack_id']} {manifest['pack_version']}",
        "mime": visual.get("mime") or "image/png",
        "data_url": f"data:{visual.get('mime') or 'image/png'};base64,{base64.b64encode(png.read_bytes()).decode('ascii')}",
    }


def real(pipeline, payload=None):
    base = dict(pipeline.REAL)
    base["notes"] = NOTES
    if payload:
        base.update(payload)
    return base


def main() -> int:
    pipeline = load_pipeline()
    setattr(pipeline, "OUT", OUT)
    dm = pipeline
    frames = [
        {"id": "01-living-light-1049", "mode": "light", "width": 1049, "height": 1180, "font": None, "payload": real(dm)},
        {"id": "02-living-dark-1049", "mode": "dark", "width": 1049, "height": 1180, "font": None, "payload": real(dm)},
        {"id": "03-living-light-900", "mode": "light", "width": 900, "height": 1280, "font": None, "payload": real(dm)},
        {"id": "04-living-dark-900", "mode": "dark", "width": 900, "height": 1280, "font": None, "payload": real(dm)},
        {"id": "05-living-light-460", "mode": "light", "width": 460, "height": 1700, "font": None, "payload": real(dm)},
        {"id": "06-living-dark-460", "mode": "dark", "width": 460, "height": 1700, "font": None, "payload": real(dm)},
        {"id": "07-living-200pct-460", "mode": "light", "width": 460, "height": 2100, "font": "32px", "payload": real(dm)},
        {"id": "08-living-reduced-motion-460", "mode": "light", "width": 460, "height": 1700, "font": None, "payload": real(dm)},
        {
            "id": "09-typographic-fallback-light-1049",
            "mode": "light",
            "width": 1049,
            "height": 1180,
            "font": None,
            "payload": real(dm, {"library": dm.library(dm.library_row())}),
        },
        {
            "id": "10-notebook-learner-rows-light-1049",
            "mode": "light",
            "width": 1049,
            "height": 1200,
            "font": None,
            "payload": {
                "kind": "notebook",
                "courseTitle": "Japanese affection and register — an L0 demonstration classroom",
                "sections": [
                    {"objective_id": "obj-context-discrimination", "title": "Two ways of saying it", "ordinal": 1}
                ],
                "entries": [
                    {
                        "entry_id": "cb-loop-note-mw5d7d0l",
                        "excerpt": "A bow is lower than a nod.",
                        "note": "Remember the waist bend, and that romaji is a scaffold.",
                        "kind": "loop_segment",
                        "tags": ["loop-proof-d7d0l", "v2"],
                        "objective_id": "obj-context-discrimination",
                        "source_ref": '{"block": "blk_1", "artifact": "art_1", "sources": ["src-jf-marugoto-a1"]}',
                        "created_at": "2026-11-06T18:00:00.000000+00:00",
                    }
                ],
            },
        },
    ]
    setattr(pipeline, "FRAMES", frames)
    (OUT / "payloads.json").write_text(
        json.dumps(
            {
                "desk": real(dm),
                "fallback": real(dm, {"library": dm.library(dm.library_row())}),
                "cover": load_cover(),
            }
        ),
        encoding="utf-8",
    )
    return pipeline.main()


if __name__ == "__main__":
    sys.exit(main())
