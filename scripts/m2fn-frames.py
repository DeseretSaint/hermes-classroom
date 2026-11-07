"""Build the M2-U3 Field Notes evidence frames from the shipped Desktop module.

Renders the Field Desk with its Field Notes strip, the Notebook surface and the three lesson views
through real React, inside the same scoped root the Coursebook route paints, then writes one
self-contained HTML document per frame for `scripts/m2fn-shot.mjs`.

What this is: a renderer audit of the shipped components at the widths, modes and text scales the
card names. What it is not: a live-app capture. There is no backend, no chat and no RPC here, so
these frames prove geometry and the honest states; the save -> search -> exact-section walk is
proven separately by `scripts/m2fn-live.mjs` against the isolated window.
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
from tests.test_desktop_lesson_views import COMPLETE_BLOCKS, SDK_STUB, document  # noqa: E402

OUT = ROOT / "audit" / "visual" / "m2-field-notes"

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

const page = (children) =>
  React.createElement('div', {
    'data-cb-route': '/coursebook',
    style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh' }
  }, children)

let body
if (payload.kind === 'desk') {
  const desk = mod.buildDeskModel({ library: payload.library, outline: payload.outline, estimate: null })
  body = React.createElement(mod.FieldDeskHome, {
    desk,
    notes: {
      status: payload.notesStatus || 'ready',
      data: payload.notes ? { entries: payload.notes } : null,
      error: payload.notesError || null,
      reload: () => {}
    },
    onShowNotebook: () => {},
    libraryStatus: 'ready',
    libraryError: null,
    stale: Boolean(payload.stale),
    busy: false,
    notice: null,
    onRetry: () => {},
    onCreate: () => {},
    onPrimary: () => {},
    onOpenSection: () => {},
    onOpen: () => {},
    onShowAll: () => {},
    sourcesOpen: false,
    onToggleSources: () => {},
    sourcesStatus: 'idle',
    sourcesError: null,
    sources: null,
    onRetrySources: () => {},
    implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list'])
  })
} else if (payload.kind === 'strip') {
  body = React.createElement(mod.FieldNotesStrip, {
    notes: {
      status: payload.notesStatus || 'ready',
      data: payload.notes ? { entries: payload.notes } : null,
      error: payload.notesError || null,
      reload: () => {}
    },
    courseTitle: payload.courseTitle || 'Japanese affection (L0)',
    current: { objective_id: 'obj_0123456789abcdef', title: 'Affection and register' },
    stale: Boolean(payload.stale),
    onOpenSection: () => {},
    onShowNotebook: () => {},
    onRetry: () => {}
  })
} else if (payload.kind === 'notebook') {
  body = React.createElement(mod.NotebookView, {
    row: {
      enrollment_id: 'enr_0123456789abcdef',
      title: 'Japanese affection (L0)',
      evidence_summary: { current_objective_id: 'obj_0123456789abcdef' }
    },
    notebooks: { entries: payload.notes || [] },
    sections: [{ objective_id: 'obj_0123456789abcdef', title: 'Affection and register', ordinal: 1 }],
    implemented: new Set(['notebook.update', 'notebook.delete', 'notebook.save', 'artifact.get']),
    onOpenSection: () => {},
    onChanged: () => {}
  })
} else if (payload.kind === 'lesson') {
  body = React.createElement(mod.LessonDocumentView, {
    document: payload.document,
    view: payload.view,
    sources: { src_affection01: { source_id: 'src_affection01', title: 'Affection and register — field notes' } },
    checkSlot: null,
    onSaveBlock: () => {}
  })
} else {
  throw new Error('unknown frame kind ' + payload.kind)
}

const markup = renderToStaticMarkup(scope(page(body)))
process.stdout.write(JSON.stringify({ html: markup, mode }))
"""

MEDIA_BLOCK = {
    "id": "blk_media00001",
    "role": "explain",
    "headline": "The bow",
    "short": "A bow bends at the waist.",
    "deep": "A bow bends at the waist; a nod comes from the neck. The angle is the difference.",
    "check_id": None,
    "media": [
        {
            "kind": "visual",
            "role": "schematic",
            "artifact_id": "art_0000000000000001",
            "purpose": "Show the angle",
            "text_equivalent": "A bow is lower than a nod.",
            "label": "Bow angle",
        }
    ],
    "source_ids": ["src_affection01"],
}

NOTES = [
    {
        "entry_id": "nbt_00000000000000000000000000000001",
        "objective_id": "obj_0123456789abcdef",
        "kind": "artifact",
        "excerpt": "A bow is lower than a nod.",
        "note": "Remember the waist bend, not the neck.",
        "tags": ["register", "politeness"],
        "source_ref": json.dumps(
            {"block": "blk_media00001", "artifact": "art_0000000000000001", "sources": ["src_affection01"]}
        ),
        "created_at": "2026-11-06T12:00:00.000000+00:00",
        "revision": 0,
    },
    {
        "entry_id": "nbt_00000000000000000000000000000002",
        "objective_id": "obj_0123456789abcdef",
        "kind": "lesson_segment",
        "excerpt": "The angle is the difference between respect and familiarity.",
        "note": None,
        "tags": ["register"],
        "source_ref": json.dumps({"block": "blk_explain001", "sources": ["src_affection01"]}),
        "created_at": "2026-11-05T09:00:00.000000+00:00",
        "revision": 0,
    },
]

DESK = {
    "kind": "desk",
    "library": library(library_row()),
    "outline": OUTLINE,
    "notes": NOTES,
    "notesStatus": "ready",
}

DESK_EMPTY = {**DESK, "notes": [], "notesStatus": "ready"}
DESK_ERROR = {**DESK, "notes": None, "notesStatus": "error", "notesError": {"code": "HOST_UNAVAILABLE", "message": "The backend did not answer."}}
DESK_LOADING = {**DESK, "notes": None, "notesStatus": "loading"}

DOC = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
DOC_MEDIA = document(guided=True, blocks=[MEDIA_BLOCK, *COMPLETE_BLOCKS[:2]], check_id=None)

FRAMES = [
    {"id": "01-desk-strip-light-wide", "mode": "light", "width": 1280, "height": 1200, "payload": DESK},
    {"id": "02-desk-strip-dark-wide", "mode": "dark", "width": 1280, "height": 1200, "payload": DESK},
    {"id": "03-desk-strip-light-460", "mode": "light", "width": 460, "height": 1500, "payload": DESK},
    {"id": "04-desk-strip-dark-200pct", "mode": "dark", "width": 1280, "height": 1500, "font": "32px", "payload": DESK},
    {"id": "05-desk-strip-light-460-200pct", "mode": "light", "width": 460, "height": 1900, "font": "32px", "payload": DESK},
    {"id": "06-strip-empty-light", "mode": "light", "width": 1280, "height": 900, "payload": DESK_EMPTY},
    {"id": "07-strip-error-light", "mode": "light", "width": 1280, "height": 900, "payload": DESK_ERROR},
    {"id": "08-strip-loading-dark", "mode": "dark", "width": 1280, "height": 900, "payload": DESK_LOADING},
    {"id": "09-strip-stale-light", "mode": "light", "width": 1280, "height": 1000, "payload": {**DESK, "stale": True}},
    {"id": "10-notebook-light-wide", "mode": "light", "width": 1280, "height": 1100, "payload": {"kind": "notebook", "notes": NOTES}},
    {"id": "11-notebook-dark-460", "mode": "dark", "width": 460, "height": 1400, "payload": {"kind": "notebook", "notes": NOTES}},
    {"id": "12-notebook-empty-light", "mode": "light", "width": 1280, "height": 800, "payload": {"kind": "notebook", "notes": []}},
    {"id": "13-textbook-save-light", "mode": "light", "width": 1280, "height": 1100, "payload": {"kind": "lesson", "view": "textbook", "document": DOC_MEDIA}},
    {"id": "14-guided-save-dark-460", "mode": "dark", "width": 460, "height": 1200, "payload": {"kind": "lesson", "view": "guided", "document": DOC}},
    {"id": "15-quest-save-light", "mode": "light", "width": 1280, "height": 1200, "payload": {"kind": "lesson", "view": "field_quest", "document": {**DOC, "views": {**DOC["views"], "field_quest": True}}}},
    {"id": "16-desk-strip-reduced-motion", "mode": "light", "width": 1280, "height": 1200, "payload": DESK, "reduced_motion": True},
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
  /* Frame-only shim: the static render has no Tailwind build, so the handful of utility classes
     the notebook and lesson surfaces use are defined here at their Tailwind defaults. The real
     Desktop supplies them; this keeps the frame's geometry honest. */
  [data-cb-scope] {{
    --ui-text-secondary: var(--cb-ink-soft);
    --ui-text-tertiary: var(--cb-ink-soft);
    --ui-stroke-secondary: var(--cb-rule);
    --ui-stroke-tertiary: var(--cb-rule);
  }}
  .flex {{ display: flex; }} .flex-col {{ flex-direction: column; }} .flex-wrap {{ flex-wrap: wrap; }}
  .flex-1 {{ flex: 1 1 0%; }} .min-w-0 {{ min-width: 0; }} .items-center {{ align-items: center; }}
  .items-baseline {{ align-items: baseline; }} .items-start {{ align-items: flex-start; }}
  .justify-between {{ justify-content: space-between; }} .justify-start {{ justify-content: flex-start; }}
  .gap-1 {{ gap: 0.25rem; }} .gap-2 {{ gap: 0.5rem; }} .gap-3 {{ gap: 0.75rem; }}
  .py-1 {{ padding: 0.25rem 0; }} .py-2 {{ padding: 0.5rem 0; }} .pt-1 {{ padding-top: 0.25rem; }}
  .text-xs {{ font-size: 0.75rem; line-height: 1rem; }} .text-sm {{ font-size: 0.875rem; line-height: 1.25rem; }}
  .text-base {{ font-size: 1rem; line-height: 1.5rem; }} .font-medium {{ font-weight: 500; }}
  .font-semibold {{ font-weight: 600; }} .leading-snug {{ line-height: 1.375; }} .leading-relaxed {{ line-height: 1.625; }}
  .max-w-prose {{ max-width: 65ch; }} .max-w-3xl {{ max-width: 48rem; }} .max-w-sm {{ max-width: 24rem; }}
  .max-w-2xl {{ max-width: 42rem; }} .w-40 {{ width: 10rem; }} .w-full {{ width: 100%; }}
  .border-b {{ border-bottom: 1px solid var(--ui-stroke-tertiary); }}
  .border-t {{ border-top: 1px solid var(--ui-stroke-tertiary); }}
  .border-l {{ border-left: 1px solid var(--ui-stroke-secondary); }}
  .break-words {{ overflow-wrap: break-word; }}
</style></head>
<body>{body}</body></html>"""


def main() -> int:
    modules = _desktop_node_modules()
    if modules is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-m2fn-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update(
                {
                    "CB_TEST_PAYLOAD": json.dumps(frame["payload"]),
                    "CB_TEST_MODE": frame["mode"],
                    "CB_TEST_MOTION": "full",
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
                    "state": frame["payload"].get("notesStatus") or frame["payload"]["kind"],
                    "width": frame["width"],
                    "height": frame["height"],
                    "reduced_motion": bool(frame.get("reduced_motion")),
                    "tabs": frame.get("tabs"),
                    "html": shell_html(rendered["html"], frame.get("font")),
                }
            )
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
