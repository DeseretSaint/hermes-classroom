"""Build the M2-U1 Field Desk evidence frames from the shipped Desktop module.

Renders `FieldDeskHome` (and the route's own `BackendUnavailable`) through real React, inside the
same scoped root the Coursebook route paints, then writes one self-contained HTML document per
frame for `scripts/m2fd-shot.mjs`.

What this is: a renderer audit of the shipped components at the widths, modes and text scales the
card names. What it is not: a live-app capture. There is no backend, no chat and no RPC, so the
frames prove the view's geometry and its honest states, not that a profile currently holds these
rows. The live read is covered separately by the rig capture in the same directory.
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
    SDK_STUB,
    SOURCES,
    _desktop_node_modules,
    library,
    library_row,
)

OUT = ROOT / "audit" / "visual" / "m2-field-desk"

HARNESS = """
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'
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
if (payload.kind === 'backend-off') {
  body = React.createElement(mod.BackendUnavailable, {
    error: { code: 'HOST_UNAVAILABLE', message: 'The Coursebook backend did not answer.' },
    reload: () => {}
  })
} else {
  const desk = mod.buildDeskModel({
    library: payload.library,
    outline: payload.outline,
    estimate: payload.estimate
  })
  const abilities = ['library.list', 'course.outline', 'lesson.page', 'parent.brief.get', 'pack.inspect']
  if (payload.firstUse) abilities.push('course.create', 'syllabus.intake.create')
  body = React.createElement(mod.FieldDeskHome, {
    desk,
    libraryStatus: payload.libraryStatus || 'ready',
    libraryError: payload.libraryError || null,
    stale: Boolean(payload.stale),
    busy: false,
    notice: null,
    onRetry: () => {},
    onCreate: payload.firstUse ? () => {} : undefined,
    onPrimary: () => {},
    onOpenSection: () => {},
    onSeePlan: () => {},
    onOpen: () => {},
    onShowAll: () => {},
    onBrowseLibrary: payload.firstUse ? () => {} : undefined,
    sourcesOpen: Boolean(payload.sourcesOpen),
    onToggleSources: () => {},
    sourcesStatus: payload.sourcesStatus || 'idle',
    sourcesError: payload.sourcesError || null,
    sources: payload.sources || null,
    onRetrySources: () => {},
    implemented: new Set(abilities)
  })
}

const markup = renderToStaticMarkup(scope(
  React.createElement('div', {
    'data-cb-route': '/coursebook',
    style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh' }
  }, body)
))

process.stdout.write(JSON.stringify({ html: markup, mode }))
"""

SECOND = library_row(
    enrollment_id="enr_ffffffffffffffff",
    course_id="crs_ffffffffffffffff",
    title="Japanese greetings (L0)",
    recipe="casual",
    next_step={"kind": "start_lesson", "label": "Start あいさつと自己紹介"},
    evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 6, "current_objective_id": None},
    updated_at="2026-11-04T09:00:00.000000+00:00",
)

REAL = {
    "kind": "desk",
    "library": library(library_row(), SECOND),
    "outline": OUTLINE,
    "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
    "sourcesOpen": False,
    "sourcesStatus": "idle",
}

REAL_OPEN = {
    **REAL,
    "sourcesOpen": True,
    "sourcesStatus": "ready",
    "sources": SOURCES,
}

REAL_NO_ESTIMATE = {
    **REAL,
    "estimate": {"status": "none", "minutes": None, "source": None, "error": None},
}

EMPTY = {
    "kind": "desk",
    "library": library(),
    "outline": None,
    "estimate": {"status": "none", "minutes": None, "source": None, "error": None},
}

LOADING = {
    "kind": "desk",
    "library": None,
    "libraryStatus": "loading",
    "outline": None,
    "estimate": {"status": "none", "minutes": None, "source": None, "error": None},
}

ERROR = {
    "kind": "desk",
    "library": None,
    "libraryStatus": "error",
    "libraryError": {"code": "HOST_UNAVAILABLE", "message": "The Coursebook backend did not answer."},
    "outline": None,
    "estimate": {"status": "none", "minutes": None, "source": None, "error": None},
}

BACKEND_OFF = {"kind": "backend-off"}

FRAMES = [
    {"id": "01-real-light-wide", "mode": "light", "width": 1280, "height": 1000, "font": None, "payload": REAL},
    {"id": "02-real-dark-wide", "mode": "dark", "width": 1280, "height": 1000, "font": None, "payload": REAL},
    {"id": "03-real-light-460", "mode": "light", "width": 460, "height": 1300, "font": None, "payload": REAL},
    {"id": "04-real-dark-200pct", "mode": "dark", "width": 1280, "height": 1300, "font": "32px", "payload": REAL},
    {"id": "05-real-light-460-200pct", "mode": "light", "width": 460, "height": 1700, "font": "32px", "payload": REAL},
    {"id": "06-real-sources-open-light", "mode": "light", "width": 1280, "height": 1150, "font": None, "payload": REAL_OPEN},
    {"id": "07-real-no-estimate-dark", "mode": "dark", "width": 1280, "height": 1000, "font": None, "payload": REAL_NO_ESTIMATE},
    {"id": "08-empty-light", "mode": "light", "width": 1280, "height": 800, "font": None, "payload": EMPTY},
    {"id": "09-loading-dark", "mode": "dark", "width": 1280, "height": 600, "font": None, "payload": LOADING},
    {"id": "10-error-light", "mode": "light", "width": 1280, "height": 700, "font": None, "payload": ERROR},
    {"id": "11-backend-off-light", "mode": "light", "width": 1280, "height": 700, "font": None, "payload": BACKEND_OFF},
    {
        "id": "12-keyboard-focus-460",
        "mode": "light",
        "width": 460,
        "height": 1300,
        "font": None,
        "payload": REAL,
        "tabs": 4,
    },
]


def build_env(root: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    node_modules = root / "node_modules"
    node_modules.mkdir()
    modules = _desktop_node_modules()
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
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-m2fd-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update(
                {
                    "CB_TEST_PAYLOAD": json.dumps(frame["payload"]),
                    "CB_TEST_MODE": frame["mode"],
                    "CB_TEST_MOTION": "full",
                    "CB_TEST_WIDTH": str(frame["width"]),
                }
            )
            result = subprocess.run(
                ["node", "harness.mjs"], cwd=root, env=env, capture_output=True, text=True, timeout=180
            )
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            frames.append(
                {
                    "id": frame["id"],
                    "state": frame["payload"].get("libraryStatus")
                    or ("backend-off" if frame["payload"]["kind"] == "backend-off" else "ready"),
                    "width": frame["width"],
                    "height": frame["height"],
                    "reduced_motion": False,
                    "focus": frame.get("focus"),
                    "tabs": frame.get("tabs"),
                    "html": shell_html(rendered["html"], frame["font"]),
                }
            )
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
