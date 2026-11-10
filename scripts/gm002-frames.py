#!/usr/bin/env python3
"""GM-002 — build the global Home and course-home evidence frames.

The renderer mounts the shipped `desktop/plugin.js` through React in Node and paints the two
surfaces the card splits: `CoursebookHome` (the field library) and the selected course's home
(`FieldDeskHome` inside the route's `data-cb-course-home` wrapper). The rows, outline, next step
and estimate are the contract's own fixture shapes already used by the Field Desk render suite;
the component, the tokens and the interactions are the shipped ones.

`scripts/gm002-shot.mjs` paints each frame in Chromium, captures the PNG and records the painted
facts (one primary, card count, horizontal overflow, focus ring, root font). Like the M2/H-189
pipelines this is a renderer audit, not a live-window capture; the walkthrough proof and the live
rig are named separately in the manifest.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_desktop_field_desk import (  # noqa: E402
    OUTLINE,
    _desktop_node_modules,
    library,
    library_row,
)
from tests.test_desktop_lesson_views import SDK_STUB  # noqa: E402

OUT = ROOT / "docs" / "visual-review" / "gm-002"

HARNESS = r"""
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'
globalThis.__CB_TEST_WIDTH__ = process.env.CB_TEST_WIDTH || '1049'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
const mode = process.env.CB_TEST_MODE || 'light'

const scope = (children) =>
  React.createElement('div', {
    'data-cb-scope': mode,
    'data-cb-motion': process.env.CB_TEST_MOTION || 'full',
    style: mod.cbScopeStyle(mode)
  }, children)

let body
if (payload.kind === 'home') {
  body = React.createElement(mod.CoursebookHome, {
    library: {
      status: payload.status || 'ready',
      data: payload.status === 'idle' ? null : payload.library,
      error: payload.error || null,
      stale: Boolean(payload.stale)
    },
    modes: payload.modes || {},
    modesSupported: true,
    online: payload.online !== false,
    canCreate: true,
    onStartCreate: () => {},
    onBrowseLibrary: () => {},
    onOpenCourse: () => {},
    onShowAll: () => {},
    onOpenStudio: () => {},
    onRetry: () => {}
  })
} else {
  const desk = mod.buildDeskModel({
    library: payload.library,
    outline: payload.outline,
    estimate: payload.estimate || null,
    selectedCourseId: payload.library.items[0] ? payload.library.items[0].course_id : null,
    outlineState: payload.outlineStatus || (payload.outline ? 'ready' : 'idle')
  })
  body = React.createElement('div', { 'data-cb-course-home': 'frame' },
    React.createElement(mod.FieldDeskHome, {
      desk,
      notes: null,
      onShowNotebook: () => {},
      libraryStatus: payload.libraryStatus || 'ready',
      libraryError: payload.error || null,
      stale: false,
      busy: false,
      notice: null,
      online: true,
      onRetry: () => {},
      onCreate: null,
      onPrimary: () => {},
      onOpenSection: () => {},
      onSeePlan: () => {},
      onRetryEstimate: () => {},
      onSelectCourse: () => {},
      onOpenStudio: () => {},
      onOpen: () => {},
      onShowAll: () => {},
      sourcesOpen: false,
      onToggleSources: () => {},
      sourcesStatus: 'idle',
      sourcesError: null,
      sources: null,
      onRetrySources: () => {},
      outlineStatus: payload.outlineStatus || (payload.outline ? 'ready' : 'idle'),
      outlineError: payload.outlineError || null,
      onRetryOutline: () => {},
      implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list'])
    })
  )
}

const markup = renderToStaticMarkup(scope(
  React.createElement('div', {
    'data-cb-route': '/coursebook',
    style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh' }
  }, body)
))
process.stdout.write(JSON.stringify({ html: markup }))
"""

SECOND = library_row(
    enrollment_id="enr_bbbbbbbbbbbbbbbb",
    course_id="crs_bbbbbbbbbbbbbbbb",
    title="Japanese greetings (L0)",
    recipe="casual",
    next_step={"kind": "start_lesson", "label": "Start あいさつと自己紹介"},
    evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 6, "current_objective_id": None},
    updated_at="2026-11-04T09:00:00.000000+00:00",
)
THIRD = library_row(
    enrollment_id="enr_cccccccccccccccc",
    course_id="crs_cccccccccccccccc",
    title="Reading a schematic",
    recipe="committed",
    next_step={"kind": "review_plan", "label": "Review the plan"},
    evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 5, "current_objective_id": None},
    updated_at="2026-11-03T09:00:00.000000+00:00",
)
FOURTH = library_row(
    enrollment_id="enr_dddddddddddddddd",
    course_id="crs_dddddddddddddddd",
    title="Sourdough: the first loaf",
    recipe="one_off",
    next_step={"kind": "start_lesson", "label": "Start the task"},
    evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 3, "current_objective_id": None},
    updated_at="2026-11-02T09:00:00.000000+00:00",
)
FIFTH = library_row(
    enrollment_id="enr_eeeeeeeeeeeeeeee",
    course_id="crs_eeeeeeeeeeeeeeee",
    title="Celestial navigation",
    recipe="companion",
    next_step={"kind": "resume_lesson", "label": "Resume this lesson"},
    evidence_summary={"independent": 2, "review_due": 0, "total_objectives": 8, "current_objective_id": "obj_0000000000000003"},
    updated_at="2026-11-01T09:00:00.000000+00:00",
)
SIXTH = library_row(
    enrollment_id="enr_ffffffffffffffff",
    course_id="crs_ffffffffffffffff",
    title="Engine diagnostics",
    evidence_summary={"independent": 1, "review_due": 1, "total_objectives": 4, "current_objective_id": "obj_0000000000000003"},
    updated_at="2026-10-31T09:00:00.000000+00:00",
)

SHELF = library(library_row(), SECOND, THIRD, FOURTH, FIFTH, SIXTH)
MODES = {
    row["course_id"]: {"state": "ready", "mode": "game" if index % 2 == 0 else "textbook"}
    for index, row in enumerate(SHELF["items"])
}

HOME = {"kind": "home", "library": SHELF, "modes": MODES}

CELLS = [
    ("1049", "light", "100", "default", None, None),
    ("1049", "dark", "100", "default", None, None),
    ("900", "light", "100", "default", None, None),
    ("460", "light", "100", "default", None, None),
    ("1049", "light", "200", "default", None, "32px"),
    ("460", "light", "200", "default", None, "32px"),
    ("1049", "light", "100", "focus", None, None),
    ("1049", "light", "100", "reduced-motion", "reduce", None),
]


def frame(screen: str, width: str, mode: str, scale: str, state: str, payload: dict,
          font: str | None = None, motion: str | None = None) -> dict:
    return {
        "id": f"{screen}--{width}--{mode}--{scale}--{state}",
        "screen": screen,
        "state": state,
        "width": int(width),
        "height": 900,
        "mode": mode,
        "scale": int(scale),
        "font": font,
        "reduced_motion": motion == "reduce",
        "focus": state == "focus",
        "tabs": 7 if state == "focus" else None,
        "payload": payload,
    }


def frames() -> list[dict]:
    out: list[dict] = []
    for width, mode, scale, state, motion, font in CELLS:
        out.append(frame("home.global", width, mode, scale, state, HOME, font, motion))
    out.append(frame("home.global", "1049", "light", "100", "empty",
                     {"kind": "home", "library": library(), "modes": {}}))
    out.append(frame("home.global", "1049", "light", "100", "loading",
                     {"kind": "home", "status": "loading", "library": SHELF, "modes": MODES}))
    out.append(frame("home.global", "1049", "light", "100", "error",
                     {"kind": "home", "status": "error", "library": library(), "modes": {},
                      "error": {"code": "HOST_UNAVAILABLE", "message": "The backend did not answer."}}))
    out.append(frame("home.global", "1049", "light", "100", "offline",
                     {"kind": "home", "library": SHELF, "modes": MODES, "online": False}))
    out.append(frame("home.global", "900", "light", "100", "overflow", HOME))

    course = {
        "kind": "course-home",
        "library": library(library_row()),
        "outline": OUTLINE,
        "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
    }
    for width, mode, scale, state, motion, font in CELLS:
        out.append(frame("home.course", width, mode, scale, state, course, font, motion))
    out.append(frame("home.course", "1049", "light", "100", "loading",
                     {"kind": "course-home", "library": library(), "outline": None, "libraryStatus": "loading"}))
    out.append(frame("home.course", "1049", "light", "100", "error",
                     {"kind": "course-home", "library": library(), "outline": None, "libraryStatus": "error",
                      "error": {"code": "HOST_UNAVAILABLE", "message": "The backend did not answer."}}))
    out.append(frame("home.course", "1049", "light", "100", "no-outline",
                     {"kind": "course-home", "library": library(library_row()), "outline": None,
                      "outlineStatus": "error",
                      "outlineError": {"code": "HOST_UNAVAILABLE", "message": "The trail could not be read."}}))
    return out


def build_env(root: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    modules = _desktop_node_modules()
    node_modules = root / "node_modules"
    node_modules.mkdir()
    for name in ("react", "react-dom", "scheduler"):
        source = modules / name
        if source.is_dir():
            (node_modules / name).symlink_to(source, target_is_directory=True)
    sdk = node_modules / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}), encoding="utf-8"
    )
    (sdk / "index.mjs").write_text(SDK_STUB, encoding="utf-8")


def shell_html(body: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
</style></head>
<body>{body}</body></html>"""


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    built: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="coursebook-gm002-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for item in frames():
            env = dict(os.environ)
            env.update(
                {
                    "CB_TEST_PAYLOAD": json.dumps(item["payload"]),
                    "CB_TEST_MODE": item["mode"],
                    "CB_TEST_MOTION": "reduce" if item["reduced_motion"] else "full",
                    "CB_TEST_WIDTH": str(item["width"]),
                }
            )
            result = subprocess.run(
                ["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            built.append({**{k: v for k, v in item.items() if k != "payload"},
                          "html": shell_html(rendered["html"], item["font"])})
    (OUT / "frames.json").write_text(json.dumps({"frames": built}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(built), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
