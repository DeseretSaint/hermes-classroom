#!/usr/bin/env python3
"""H-183 before/after copy frames.

Renders the shipped `desktop/plugin.js` from two commits (before = the merge base, after = this
worktree) through `scripts/h183-copy-render.mjs`, then paints and screenshots every frame in
headless Chromium through `scripts/m2fq-shot.mjs`.

    python3 scripts/h183-copy-frames.py

This is a renderer audit of the shipped component tree: no backend, no chat, no RPC. The "before"
module is the file at H183_BEFORE_REF (default `d84cfc5`), written to scratch and rendered with the
same harness, so the two PNG sets differ only by the module under test.
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
from tests.test_desktop_h147_home_settings import SETTINGS_SDK_STUB  # noqa: E402
from tests.test_desktop_field_desk import OUTLINE, library, library_row  # noqa: E402

OUT = Path(os.environ.get("H183_OUT") or (ROOT / "audit" / "visual" / "h183-copy"))
BEFORE_REF = os.environ.get("H183_BEFORE_REF", "d84cfc5")
SCRATCH = Path(tempfile.mkdtemp(prefix="coursebook-h183-frames-"))

READABLE_BLOCKS = [
    {
        "id": "blk_orient0001",
        "role": "orient",
        "headline": "Start here",
        "short": "Say the greeting before you order.",
        "deep": "Say the greeting before you order, then ask for one item.",
        "check_id": None,
        "media": [],
        "source_ids": [],
    }
]


def outline(*, plan_state: str = "approved") -> dict:
    return {
        "plan": {
            "plan_id": "pln_0123456789abcdef",
            "state": plan_state,
            "version": 1,
            "units": [],
        },
        "objectives": [
            {
                "objective_id": "obj_0123456789abcdef",
                "title": "Order at a counter",
                "state": "not_started",
                "ordinal": 1,
            }
        ],
    }


def page_document(*, blocks=None) -> dict:
    return {
        "revision": 4,
        "section": {
            "objective_id": "obj_0123456789abcdef",
            "title": "Order at a counter",
            "state": "not_started",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {"lesson_run_id": None, "binding_id": None, "binding_status": "detached",
                    "session_state": "stored_only"},
        "segments": [],
        "attempts": [],
        "notebook_entries": [],
        "sources": [],
        "document": {
            "schema_version": 1,
            "document_id": "doc_0123456789abcdef0123",
            "content_hash": "sha256:" + "a" * 64,
            "section_title": "Order at a counter",
            "objective_id": "obj_0123456789abcdef",
            "state": "textbook_only",
            "view_note": None,
            "views": {"textbook": True, "guided": False, "field_quest": False, "field_notes": False},
            "blocks": blocks or [],
            "check_id": None,
            "source_ids": [],
        },
    }


def lessons_job(*, state: str, error=None) -> dict:
    return {
        "job_id": "job_0123456789abcdef",
        "kind": "plan",
        "state": state,
        "brief": {"stage": "lessons", "plan_id": "pln_0123456789abcdef",
                  "enrollment_id": "enr_0123456789abcdef"},
        "checkpoint": {"lessons": 0},
        "error": error,
        "updated_at": "2026-11-08T00:00:00Z",
    }


READINESS = {
    "empty": {
        "outline": outline(),
        "page": None,
        "jobs": {"jobs": []},
        "planStatus": "ready",
        "pageStatus": "ready",
    },
    "failed": {
        "outline": outline(),
        "page": None,
        "jobs": {"jobs": [lessons_job(state="failed", error={
            "code": "JOB_FAILED", "message": "the model stopped"})]},
        "planStatus": "ready",
        "pageStatus": "ready",
    },
    "incomplete": {
        "outline": outline(),
        "page": page_document(blocks=[]),
        "jobs": {"jobs": []},
        "planStatus": "ready",
        "pageStatus": "ready",
    },
}

FRAME_CASES = [
    ("first-run", "light", 1049, 16, 1500),
    ("first-run", "light", 460, 16, 2100),
    ("first-run", "dark", 1049, 16, 1500),
    ("first-run", "light", 1049, 32, 2400),
    ("home", "light", 1049, 16, 1500),
    ("home", "light", 460, 16, 2200),
    ("home", "dark", 1049, 16, 1500),
    ("home", "light", 1049, 32, 2400),
    ("lesson-empty", "light", 1049, 16, 1200),
    ("lesson-empty", "light", 460, 16, 1400),
    ("lesson-empty", "dark", 1049, 16, 1200),
    ("lesson-empty", "light", 1049, 32, 1800),
    ("lesson-failed", "light", 1049, 16, 1400),
    ("lesson-failed", "light", 460, 16, 1600),
    ("lesson-failed", "dark", 1049, 16, 1400),
    ("lesson-failed", "light", 1049, 32, 2000),
    ("settings", "light", 1049, 16, 1600),
    ("settings", "light", 460, 16, 2600),
    ("settings", "dark", 1049, 16, 1600),
    ("settings", "light", 1049, 32, 3000),
]


def module_dir(name: str) -> Path:
    base = SCRATCH / name
    base.mkdir(parents=True, exist_ok=True)
    modules = _desktop_node_modules()
    if modules is None:
        raise SystemExit("react/react-dom are not installed beside the desktop app")
    node_modules = base / "node_modules"
    if node_modules.exists():
        shutil.rmtree(node_modules)
    node_modules.mkdir()
    for package in ("react", "react-dom", "scheduler", "jsdom"):
        source = modules / package
        if source.is_dir():
            (node_modules / package).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
        encoding="utf-8",
    )
    (sdk / "index.js").write_text(SETTINGS_SDK_STUB, encoding="utf-8")
    return base


def write_modules() -> dict[str, Path]:
    after = module_dir("after")
    (after / "plugin.js").write_text(
        (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8"
    )
    before = module_dir("before")
    shown = subprocess.run(
        ["git", "show", f"{BEFORE_REF}:desktop/plugin.js"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    (before / "plugin.js").write_text(shown.stdout, encoding="utf-8")
    return {"before": before, "after": after}


def render(module: Path, frame: dict, out: Path) -> Path:
    payload_file = out / "payload.json"
    payload_file.write_text(json.dumps({
        "frame": frame,
        "readiness": READINESS,
        "library": library(library_row()),
        "outline": OUTLINE,
        "implemented": ["course.create", "pack.import", "syllabus.intake.create",
                        "library.list", "course.outline", "lesson.page", "job.assist"],
    }), encoding="utf-8")
    frame_dir = out / "frame"
    frame_dir.mkdir(parents=True, exist_ok=True)
    # ESM resolves bare imports from the script's own directory, not the process cwd, so the
    # harness is copied beside the module's node_modules.
    harness = module / "render.mjs"
    shutil.copyfile(ROOT / "scripts" / "h183-copy-render.mjs", harness)
    result = subprocess.run(
        ["node", str(harness), str(module), str(payload_file), str(frame_dir)],
        cwd=module,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr[-3000:])
    return frame_dir / "frame.html"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    modules = write_modules()
    frames = []
    for module_name, module in modules.items():
        for surface, mode, width, font, height in FRAME_CASES:
            frame_id = f"{module_name}-{surface}-{mode}-{width}-{font}"
            state = {
                "surface": surface,
                "mode": mode,
                "fontPx": font,
                "readiness": {},
            }
            work = SCRATCH / "work" / frame_id
            work.mkdir(parents=True, exist_ok=True)
            html_file = render(module, {**state,
                                        "readiness": {k: {"page": v["page"],
                                                          "pageStatus": v["pageStatus"],
                                                          "planStatus": v["planStatus"],
                                                          "jobs": v["jobs"],
                                                          "outline": v["outline"]}
                                                      for k, v in READINESS.items()}},
                               work)
            frames.append({
                "id": frame_id,
                "state": surface,
                "module": module_name,
                "width": width,
                "height": height,
                "reduced_motion": False,
                "tabs": None,
                "html": html_file.read_text(encoding="utf-8"),
            })
            print(f"rendered {frame_id}")
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=1), encoding="utf-8")
    env = dict(os.environ)
    env.setdefault("M2FQ_CDP_PORT", "9441")
    result = subprocess.run(
        ["node", str(ROOT / "scripts" / "m2fq-shot.mjs"), str(OUT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    print(result.stdout[-4000:])
    if result.returncode != 0:
        raise SystemExit(result.stderr[-3000:])


if __name__ == "__main__":
    main()
