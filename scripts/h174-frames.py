#!/usr/bin/env python3
"""H-174 frames: the four section states at 1049 / 460 / 200% text.

Three of the four states cannot be produced on the demo backend (a lessons job that failed, one
that is running, and a page that exists with no blocks), so these frames render the shipped
`SectionPage` through real React inside the scoped root the route paints — the same renderer
pipeline the M2-U2 evidence uses. What it is: geometry, copy and the action set of the component
that ships. What it is not: a live-app capture. The live read of the mounted route is
`scripts/h174-live.mjs` on the isolated Electron rig.

    python3 scripts/h174-frames.py
    node scripts/m2fq-shot.mjs audit/h174
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("m2fq_frames", ROOT / "scripts" / "m2fq-frames.py")
assert _spec and _spec.loader
m2fq_frames = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m2fq_frames)

from tests.test_desktop_h174_empty_textbook import (  # noqa: E402
    READABLE_BLOCKS,
    lessons_job,
    outline,
    page_document,
)

HARNESS = """
const payload = JSON.parse(process.env.CB_TEST_PAYLOAD)
// The shipped hook measures `[data-cb-route]` in a live window and falls back to the host viewport
// atom for a static render. The frame tells that atom the frame's own width, so a 460 px frame
// paints the stacked shell a 460 px window paints instead of the wide one.
globalThis.__CB_TEST_WIDTH__ = payload.width || 1280
const reducedMotion = (process.env.CB_TEST_MOTION || 'full') === 'reduced'
globalThis.window = {
  innerWidth: globalThis.__CB_TEST_WIDTH__,
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
const mode = process.env.CB_TEST_MODE || 'light'
const motion = process.env.CB_TEST_MOTION || 'full'

const body = React.createElement(mod.SectionPage, {
  row: {
    enrollment_id: 'enr_0123456789abcdef',
    profile: 'default',
    title: 'Order at a counter',
    recipe: 'committed',
    next_step: { kind: 'start_lesson', label: 'Start the first section' }
  },
  objectiveId: 'obj_0123456789abcdef',
  page: payload.page,
  pageStatus: payload.pageStatus || 'ready',
  pageError: null,
  onRetryPage: () => {},
  implemented: new Set(['check.open', 'notebook.save']),
  onBack: () => {},
  onChanged: () => {},
  review: null,
  outline: payload.outline,
  planStatus: payload.planStatus || 'ready',
  jobs: payload.jobs,
  onOpenPlan: () => {},
  onRetryLessonsJob: () => {},
  embedded: false,
  defaultLessonView: 'textbook'
})

// The same scoped root the route paints, with the host's SDK variables mapped onto the plugin
// palette so a control's own text colour resolves inside the frame.
const scopeStyle = Object.assign({}, mod.cbScopeStyle(mode), {
  '--ui-text-primary': 'var(--cb-ink)',
  '--ui-text-secondary': 'var(--cb-ink-soft)',
  '--ui-text-tertiary': 'var(--cb-ink-soft)',
  '--ui-stroke-tertiary': 'var(--cb-rule)',
  '--ui-bg-primary': 'var(--cb-paper)'
})

const scope = React.createElement('div', {
  'data-cb-scope': mode,
  'data-cb-motion': motion,
  style: scopeStyle
}, React.createElement('div', {
  'data-cb-route': '/coursebook',
  'data-cb-workspace-shell': 'wide',
  style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh', maxWidth: '72rem' }
}, [
  React.createElement('div', { key: 'eyebrow', style: { fontSize: '0.65rem', fontWeight: 600,
    letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--cb-ink-soft)' } }, 'Coursebook'),
  React.createElement('h2', { key: 'title', style: { margin: '0 0 0.9rem', fontSize: '1.6rem',
    lineHeight: 1.15, color: 'var(--cb-ink)' } }, 'Order at a counter'),
  body
]))

process.stdout.write(JSON.stringify({ html: renderToStaticMarkup(scope), mode }))
"""

# The frame shell has no Tailwind build (the route does). These are the utilities the section
# surface actually paints with; anything else is inline style, which needs no shim.
UTILITY_CSS = """
[data-cb-scope] .flex{display:flex}
[data-cb-scope] .flex-col{flex-direction:column}
[data-cb-scope] .flex-wrap{flex-wrap:wrap}
[data-cb-scope] .items-center{align-items:center}
[data-cb-scope] .justify-between{justify-content:space-between}
[data-cb-scope] .justify-center{justify-content:center}
[data-cb-scope] .gap-1{gap:0.25rem}
[data-cb-scope] .gap-2{gap:0.5rem}
[data-cb-scope] .gap-3{gap:0.75rem}
[data-cb-scope] .gap-4{gap:1rem}
[data-cb-scope] .min-w-0{min-width:0}
[data-cb-scope] .self-start{align-self:flex-start}
[data-cb-scope] .max-w-prose{max-width:65ch}
[data-cb-scope] .max-w-3xl{max-width:48rem}
[data-cb-scope] .px-3{padding-left:0.75rem;padding-right:0.75rem}
[data-cb-scope] .py-2{padding-top:0.5rem;padding-bottom:0.5rem}
[data-cb-scope] .py-6{padding-top:1.5rem;padding-bottom:1.5rem}
[data-cb-scope] .text-xs{font-size:0.75rem;line-height:1.45}
[data-cb-scope] .leading-relaxed{line-height:1.6}
[data-cb-scope] .text-\\(--ui-text-secondary\\){color:var(--cb-ink-soft)}
[data-cb-scope] .border-b{border-bottom:1px solid var(--cb-rule)}
[data-cb-scope] .border-\\(--ui-stroke-tertiary\\){border-color:var(--cb-rule)}
[data-cb-scope] .last\\:border-b-0:last-child{border-bottom:0}
[data-cb-scope] .empty-state{display:flex;flex-direction:column;gap:0.4rem;padding:1rem 0}
[data-cb-scope] .empty-title{font-weight:600;color:var(--cb-ink)}
[data-cb-scope] .loader{color:var(--cb-ink-soft);font-size:0.8rem}
"""


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
  {UTILITY_CSS}
</style></head>
<body>{body}</body></html>"""


def state_payload(state: str, *, mode: str = "light") -> dict:
    if state == "absent":
        payload = {
            "outline": outline(plan_state="approved"),
            "page": None,
            "jobs": {"jobs": []},
            "pageStatus": "ready",
        }
    elif state == "running":
        payload = {
            "outline": outline(plan_state="approved"),
            "page": None,
            "jobs": {"jobs": [lessons_job(state="running")]},
            "pageStatus": "ready",
        }
    elif state == "failed":
        payload = {
            "outline": outline(plan_state="approved"),
            "page": None,
            "jobs": {"jobs": [lessons_job(
                state="failed",
                error={"code": "JOB_FAILED", "message": "the authoring model stopped before it wrote a page"},
            )]},
            "pageStatus": "ready",
        }
    elif state == "present":
        payload = {
            "outline": outline(plan_state="approved"),
            "page": page_document(blocks=READABLE_BLOCKS),
            "jobs": {"jobs": [lessons_job(state="completed", lessons=1)]},
            "pageStatus": "ready",
        }
    else:  # pragma: no cover - a typo in FRAMES
        raise SystemExit(f"unknown state {state}")
    payload["view"] = state
    return payload


STATES = ("absent", "running", "failed", "present")

FRAMES = []
for _state in STATES:
    for _width, _height, _suffix, _mode in (
        (1049, 900, "", "light"),
        (460, 1200, "", "light"),
        (460, 1500, "-text200", "light"),
        (1049, 900, "-dark", "dark"),
    ):
        _payload = state_payload(_state)
        _payload["width"] = _width
        FRAMES.append({
            "id": f"h174-{_state}-{_width}{_suffix}",
            "mode": _mode,
            "width": _width,
            "height": _height,
            "payload": _payload,
            **({"font": "32px"} if _suffix == "-text200" else {}),
        })


def main() -> int:
    m2fq_frames.OUT = ROOT / "audit" / "h174"
    m2fq_frames.HARNESS = HARNESS
    m2fq_frames.shell_html = shell_html
    m2fq_frames.FRAMES = FRAMES
    code = m2fq_frames.main()
    if code == 0:
        frames = json.loads((m2fq_frames.OUT / "frames.json").read_text(encoding="utf-8"))
        print(json.dumps({"frames": len(frames["frames"]), "out": str(m2fq_frames.OUT)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
