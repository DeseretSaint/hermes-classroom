"""Build the M2-U2 Field Quest evidence frames from the shipped Desktop module.

Renders `LessonDocumentView` in its `field_quest` view — and the Textbook lens of the same
document for the parity frame — through real React inside the scoped root the Coursebook route
paints, then writes one self-contained HTML document per frame for `scripts/m2fq-shot.mjs`.

What this is: a renderer audit of the shipped components at the widths, modes and text scales the
card names, including the checkpoint's real `AttemptControls` surface. What it is not: a live-app
capture. There is no backend and no RPC, so the frames prove geometry and the honest states, not
that a profile currently serves these blocks. The live read is covered by the rig capture in the
same directory.
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

from tests.test_desktop_field_quest import (  # noqa: E402
    EVIDENCE,
    QUEST_SDK_STUB,
    quest_document,
)
from tests.test_desktop_lesson_views import _desktop_node_modules  # noqa: E402

OUT = ROOT / "audit" / "visual" / "m2-field-quest"

# The frame stub is the shared SDK stub with the two inert components this surface needs made
# real: a textarea the checkpoint form can print, and a Badge that keeps its class name.
FRAME_STUB = QUEST_SDK_STUB.replace(
    "export const Textarea = () => null",
    """export const Textarea = (props) =>
  el('textarea', {
    id: props.id,
    rows: props.rows || 3,
    placeholder: props.placeholder || null,
    disabled: Boolean(props.disabled),
    'aria-describedby': props['aria-describedby'] || null,
    style: { width: '100%', minHeight: '4.5rem', font: 'inherit', padding: '0.4rem',
             border: '1px solid var(--cb-rule)', background: 'var(--cb-paper)', color: 'var(--cb-ink)' },
  }, props.value || '')""",
)

HARNESS = """
// The frame supplies the browser fact this component reads: the reduced-motion preference.
// `useCbMotion` asks `window.matchMedia` at mount, so a static render without this shim would
// always claim 'full' no matter which media emulation the capture used.
const reducedMotion = (process.env.CB_TEST_MOTION || 'full') === 'reduced'
globalThis.window = {
  matchMedia: (query) => ({
    matches: String(query).includes('prefers-reduced-motion') ? reducedMotion : false,
    addEventListener: () => {},
    removeEventListener: () => {}
  })
}
globalThis.__CB_TEST_MODE__ = process.env.CB_TEST_MODE || 'light'
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const mod = await import('./plugin.js')
const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
const mode = process.env.CB_TEST_MODE || 'light'
const motion = process.env.CB_TEST_MOTION || 'full'

const CHECK = {
  check_id: 'chk_0123456789abcdef',
  check_version: 3,
  evidence_target: 'production',
  stimulus: {
    prompt: 'Name one warm and one cold thing in the kitchen, in Japanese.',
    learner_instructions: 'Say both aloud, then write them the way you said them.',
    items: null,
    choices: null
  }
}

const checkNode = payload.checkError
  ? React.createElement('div', {
      'data-cb-check-error': 'true',
      style: { fontSize: '0.8rem', color: 'var(--cb-ink-soft)' }
    }, 'CHECK_UNAVAILABLE: The current check could not be opened.')
  : React.createElement(mod.AttemptControls, {
      enrollmentId: 'enr_0123456789abcdef',
      objectiveId: payload.document.objective_id,
      check: CHECK,
      revision: 7,
      implemented: new Set(['check.open', 'check.get', 'attempt.submit', 'artifact.get']),
      bindingState: 'active',
      onCommitted: () => {}
    })

const sources = {}
for (const source of payload.sources || []) sources[source.source_id] = source

const body = React.createElement(mod.LessonDocumentView, {
  document: payload.document,
  view: payload.view,
  sources,
  checkSlot: payload.ungated ? null : checkNode,
  checkLabels: [],
  progress: payload.evidence || null,
  focusBlockId: payload.focusBlockId || null,
  onOpenBlock: () => {}
})

const scope = React.createElement('div', {
  'data-cb-scope': mode,
  'data-cb-motion': motion,
  style: mod.cbScopeStyle(mode)
}, React.createElement('div', {
  'data-cb-route': '/coursebook',
  'data-cb-workspace-shell': 'wide',
  style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh' }
}, [
  React.createElement('header', {
    key: 'head',
    'data-cb-workspace-header': '',
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end',
             justifyContent: 'space-between', gap: '0.5rem', paddingBottom: '0.5rem',
             borderBottom: '1px solid var(--cb-rule)', marginBottom: '0.85rem' }
  }, [
    React.createElement('div', { key: 'titles', style: { minWidth: 0 } }, [
      React.createElement('div', { key: 'eyebrow', style: { fontSize: '0.65rem', fontWeight: 600,
        letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--cb-ink-soft)' } }, 'Coursebook'),
      React.createElement('h2', { key: 'title', style: { margin: 0, fontSize: '1.6rem',
        lineHeight: 1.15, color: 'var(--cb-ink)' } }, payload.document.section_title)
    ]),
    React.createElement('div', {
      key: 'switcher',
      'data-cb-view-switcher': mod.lessonViewOptions(payload.document).length > 1 ? 'available' : 'textbook-only',
      'data-cb-view-options': mod.lessonViewOptions(payload.document).map((v) => v.id).join(' '),
      'data-cb-view-unavailable': mod.lessonViewChoices(payload.document).filter((v) => !v.available).map((v) => v.id).join(' '),
      style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem',
               fontSize: '0.75rem', color: 'var(--cb-ink-soft)' }
    }, [
      React.createElement('span', { key: 'label' }, 'Lesson view'),
      React.createElement('div', {
        key: 'seg',
        className: 'segmented',
        style: { display: 'inline-flex', flexWrap: 'wrap', border: '1px solid var(--cb-rule)' }
      }, mod.lessonViewChoices(payload.document).map((option) =>
        React.createElement('span', {
          key: option.id,
          'data-cb-view-choice': option.id,
          'data-cb-view-choice-state': option.available ? 'available' : 'unavailable',
          'aria-pressed': option.available ? (option.id === payload.view ? 'true' : 'false') : undefined,
          title: option.reason || undefined,
          style: {
            padding: '0.2rem 0.55rem',
            borderLeft: '1px solid var(--cb-rule)',
            background: option.id === payload.view ? 'var(--cb-accent-soft)' : 'transparent',
            color: all(option.id === payload.view),
            opacity: option.available ? 1 : 0.5
          }
        }, option.label)
      )),
      React.createElement('span', {
        key: 'reasons',
        'data-cb-view-reasons': '',
        style: { flexBasis: '100%', color: 'var(--cb-ink-soft)' }
      }, mod.lessonViewChoices(payload.document).filter((v) => !v.available).map((v) => v.reason).join(' '))
    ])
  ]),
  body
]))

function all(isOn) {
  return isOn ? 'var(--cb-ink)' : 'var(--cb-ink-soft)'
}

process.stdout.write(JSON.stringify({ html: renderToStaticMarkup(scope), mode }))
"""


def media_block(doc: dict) -> dict:
    doc = json.loads(json.dumps(doc))
    doc["blocks"][1]["media"] = [{
        "kind": "visual",
        "role": "illustration",
        "artifact_id": "art_0123456789abcdef",
        "purpose": "A shelf with two labelled jars.",
        "text_equivalent": "A shelf with two labelled jars, the warm one on the left.",
        "label": "Kitchen shelf",
        "degraded": False,
        "reason": None,
    }]
    return doc


SOURCES = [
    {"source_id": "src_affection01", "title": "Affection and register — field notes"},
]

BASE = {
    "view": "field_quest",
    "document": quest_document(),
    "evidence": EVIDENCE,
    "sources": SOURCES,
}

FRAMES = [
    {"id": "01-quest-light-wide", "mode": "light", "width": 1280, "height": 1400, "payload": BASE},
    {"id": "02-quest-dark-wide", "mode": "dark", "width": 1280, "height": 1400, "payload": BASE},
    {"id": "03-quest-light-460", "mode": "light", "width": 460, "height": 1900, "payload": BASE},
    {"id": "04-quest-dark-200pct", "mode": "dark", "width": 1280, "height": 1900,
     "font": "32px", "payload": BASE},
    {"id": "05-quest-light-460-200pct", "mode": "light", "width": 460, "height": 2600,
     "font": "32px", "payload": BASE},
    {"id": "06-quest-keyboard-focus-460", "mode": "light", "width": 460, "height": 1900,
     "payload": BASE, "tabs": 1},
    {"id": "06b-quest-checkpoint-focus-460", "mode": "light", "width": 460, "height": 1900,
     "payload": BASE, "tabs": 3},
    {"id": "07-quest-reduced-motion", "mode": "light", "width": 1280, "height": 1400,
     "payload": BASE, "reduced_motion": True},
    {"id": "08-quest-media-light", "mode": "light", "width": 1280, "height": 1550,
     "payload": {**BASE, "document": media_block(quest_document())}},
    {"id": "09-quest-check-error-light", "mode": "light", "width": 1280, "height": 1400,
     "payload": {**BASE, "checkError": True}},
    {"id": "10-quest-ungated-light", "mode": "light", "width": 1280, "height": 1400,
     "payload": {**BASE, "ungated": True}},
    {"id": "11-parity-textbook-light", "mode": "light", "width": 1280, "height": 1400,
     "payload": {**BASE, "view": "textbook"}},
    {"id": "12-parity-guided-light", "mode": "light", "width": 1280, "height": 900,
     "payload": {**BASE, "view": "guided"}},
    {"id": "13-quest-no-objectives-light", "mode": "light", "width": 1280, "height": 1400,
     "payload": {**BASE, "evidence": {"independent": 0, "review_due": 0, "total_objectives": 0}}},
]


def build_env(root: Path) -> None:
    (root / "plugin.js").write_text((ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8"),
                                    encoding="utf-8")
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
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.mjs"}),
        encoding="utf-8",
    )
    (sdk / "index.mjs").write_text(FRAME_STUB, encoding="utf-8")


def shell_html(body: str, font: str | None) -> str:
    root_font = f"<style>html{{font-size:{font};}}</style>" if font else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
{root_font}
<style>
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  [data-cb-scope] h2, [data-cb-scope] h3 {{ font-family: inherit; }}
</style></head>
<body>{body}</body></html>"""


def main() -> int:
    if _desktop_node_modules() is None:
        print("react/react-dom are not installed beside the desktop app", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    with tempfile.TemporaryDirectory(prefix="coursebook-m2fq-frames-") as tmp:
        root = Path(tmp)
        build_env(root)
        for frame in FRAMES:
            env = dict(os.environ)
            env.update({
                "CB_TEST_PAYLOAD": json.dumps(frame["payload"]),
                "CB_TEST_MODE": frame["mode"],
                "CB_TEST_MOTION": "reduced" if frame.get("reduced_motion") else "full",
            })
            result = subprocess.run(["node", "harness.mjs"], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(result.stderr[-3000:], file=sys.stderr)
                return 1
            rendered = json.loads(result.stdout)
            frames.append({
                "id": frame["id"],
                "state": frame["payload"]["view"],
                "width": frame["width"],
                "height": frame["height"],
                "reduced_motion": bool(frame.get("reduced_motion")),
                "tabs": frame.get("tabs"),
                "html": shell_html(rendered["html"], frame.get("font")),
            })
    (OUT / "frames.json").write_text(json.dumps({"frames": frames}, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "path": str(OUT / "frames.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
