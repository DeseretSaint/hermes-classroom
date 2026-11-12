#!/usr/bin/env python3
"""Render a Coursebook screen from the *built module* at a reference width, with its sha.

Why this exists: a Desktop window shows whatever module the app loaded when it started, so a review
that opens a window can photograph a build that is not the branch under review (the 12:23 window
against a 12:44 install, again today). This harness has no window and no backend: it stages
`desktop/plugin.js` in a throwaway dir with the host's React and a stub plugin SDK, renders the real
component inside the same `CbV3Scope` the route mounts, and screenshots that page with the system
Chromium. What is photographed is therefore the module in this checkout, and the frame carries the
sha it was rendered from.

Usage:
  python3 scripts/cb-frame.py --component course-home --width 1344 900
  python3 scripts/cb-frame.py --component home --width 1344 --out .coursebook/frames
  python3 scripts/cb-frame.py --list

Every run writes <out>/<component>-<width>.png plus <out>/frame-<component>-<width>.json holding:
module_sha256, component, width, height, host_header, fonts, and `installed` — the sha of
~/.hermes/desktop-plugins/coursebook/plugin.js at run time. When the two differ the frame is still
valid evidence of the branch, and the manifest says so: never present it as the installed build.

The SDK stub renders `Codicon` as a visible stand-in glyph (the published stub returns null, which
would hide every state mark in the frame). It is an icon-font stand-in, not a product asset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules  # noqa: E402
from tests.test_desktop_h147_home_settings import (  # noqa: E402
    SETTINGS_SDK_STUB,
    SEGMENTED_NEW,
)

#: The shared SDK stub renders `SegmentedControl` as bare buttons and every form primitive as null.
#: That is right for a semantics test and wrong for a *frame*: a filter row reads as one run-on
#: string, and the create/studio forms photograph with no fields at all. These replacements carry
#: the host's own markup (classes included), taken from
#: `apps/desktop/src/components/ui/segmented-control.tsx` and the host's form primitives. A control
#: that exists only after this substitution is still host chrome, not Coursebook design; the frame
#: manifest says so.
SEGMENTED_REAL = """export const SegmentedControl = (props) =>
  el(
    'div',
    {
      className: [
        'inline-grid w-fit grid-flow-col gap-0.5 rounded-[5px] bg-(--ui-bg-tertiary) p-0.5',
        props.sizing === 'content' ? 'auto-cols-max' : 'auto-cols-fr',
        props.disabled ? 'opacity-50' : '',
        props.className || ''
      ].filter(Boolean).join(' '),
      'data-disabled': props.disabled ? 'true' : null
    },
    (props.options || []).map((option) =>
      el(
        'button',
        {
          key: option.id,
          type: 'button',
          'aria-pressed': option.id === props.value,
          'data-option': option.id,
          disabled: Boolean(props.disabled),
          className:
            'flex items-center justify-center gap-1 rounded-[3px] px-2.5 py-0.5 text-[0.6875rem] font-medium ' +
            (option.id === props.value ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground'),
          onClick: () => {
            if (!props.disabled && props.onChange) props.onChange(option.id)
          }
        },
        option.label
      )
    )
  )"""

BUTTON_HEAD_OLD = "export const Button = (props) => {"
BUTTON_HEAD_NEW = """const HOST_BUTTON_BASE =
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-[2.5px] text-xs leading-4 font-medium whitespace-nowrap shadow-none'
const HOST_BUTTON_SIZE = {
  default: 'px-3 py-1.5',
  xs: 'gap-1 px-2 py-0.5 text-[0.6875rem]',
  sm: 'px-2.5 py-1',
  lg: 'px-5 py-2 text-sm',
  inline: 'h-auto gap-1 p-0',
  micro: 'h-auto px-1 py-0 text-xs',
  touch: 'min-h-11 min-w-11 px-3 py-2 text-sm'
}
const HOST_BUTTON_VARIANT = {
  default: 'bg-primary text-primary-foreground',
  secondary: 'bg-(--ui-bg-quaternary) text-(--ui-text-primary)',
  outline: 'bg-transparent text-(--ui-text-primary)',
  ghost: 'text-(--ui-text-secondary)',
  chip: 'bg-(--ui-bg-quaternary) text-(--ui-text-primary)',
  text: 'text-muted-foreground',
  textStrong: 'font-semibold text-muted-foreground underline',
  link: 'text-primary underline',
  destructive: 'bg-destructive text-white'
}
export const Button = (props) => {"""

BUTTON_ATTRS_OLD = """  if (props.className) attrs.className = props.className"""
BUTTON_ATTRS_NEW = """  // The host sizes and pads every SDK button from its own class list. A stub that renders a bare
  // <button> makes a plugin action photograph flush against its border and unfilled: a frame
  // artifact the reviewer would read as a product defect. CbAction's inline palette still wins.
  attrs.className = [
    HOST_BUTTON_BASE,
    HOST_BUTTON_SIZE[props.size || 'default'] || HOST_BUTTON_SIZE.default,
    HOST_BUTTON_VARIANT[props.variant || 'default'] || '',
    props.className || ''
  ].filter(Boolean).join(' ')"""

FORM_STUBS_OLD = """export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null"""

FORM_STUBS_NEW = """const FIELD_CLASS =
  'w-full rounded-[4px] border border-(--ui-stroke-secondary) bg-transparent px-2 py-1 text-sm text-(--ui-text-primary)'
export const Input = (props) =>
  el('input', {
    type: props.type || 'text',
    id: props.id || null,
    value: props.value === undefined || props.value === null ? '' : props.value,
    placeholder: props.placeholder || null,
    disabled: Boolean(props.disabled),
    readOnly: Boolean(props.readOnly),
    onChange: props.onChange || (() => {}),
    'aria-label': props['aria-label'] || null,
    'aria-describedby': props['aria-describedby'] || null,
    'aria-invalid': props['aria-invalid'] || null,
    className: FIELD_CLASS + ' h-8 ' + (props.className || '')
  })
export const Textarea = (props) =>
  el('textarea', {
    id: props.id || null,
    value: props.value === undefined || props.value === null ? '' : props.value,
    placeholder: props.placeholder || null,
    rows: props.rows || 4,
    disabled: Boolean(props.disabled),
    readOnly: Boolean(props.readOnly),
    onChange: props.onChange || (() => {}),
    'aria-label': props['aria-label'] || null,
    'aria-describedby': props['aria-describedby'] || null,
    'aria-invalid': props['aria-invalid'] || null,
    className: FIELD_CLASS + ' ' + (props.className || '')
  })
export const SearchField = (props) =>
  el('input', {
    type: 'search',
    id: props.id || null,
    value: props.value === undefined || props.value === null ? '' : props.value,
    placeholder: props.placeholder || 'Search',
    onChange: props.onChange || (() => {}),
    'aria-label': props['aria-label'] || props.placeholder || 'Search',
    className: 'h-8 w-full rounded-[4px] border border-(--ui-stroke-secondary) bg-transparent px-2 text-sm ' + (props.className || '')
  })
const collectOptions = (node, out) => {
  if (Array.isArray(node)) {
    node.forEach((child) => collectOptions(child, out))
    return out
  }
  if (!node || typeof node !== 'object' || !node.props) return out
  if (node.props.value !== undefined && typeof node.props.children !== 'object') {
    out.push({ value: node.props.value, label: node.props.children })
  }
  collectOptions(node.props.children, out)
  return out
}
export const Select = (props) => {
  const options = collectOptions(props.children, [])
  return el(
    'select',
    {
      value: props.value === undefined || props.value === null ? '' : props.value,
      disabled: Boolean(props.disabled),
      onChange: (event) => props.onValueChange && props.onValueChange(event.target.value),
      className: FIELD_CLASS + ' h-8 ' + (props.className || '')
    },
    options.map((option) => el('option', { key: option.value, value: option.value }, option.label))
  )
}"""

PLUGIN = ROOT / "desktop" / "plugin.js"
INSTALLED = Path.home() / ".hermes" / "desktop-plugins" / "coursebook" / "plugin.js"
CHROMIUM = "/usr/lib/chromium/chromium"

#: component -> {component export, fixture, route height}. Fixtures are the deck's own shapes:
#: a course home reads `row`, `objectives`, `page`, `plate`, `others`.
COMPONENTS = {
    "course-home": {
        "export": "CourseHomeV3",
        "props": {
            "row": {
                "course_id": "course-japanese",
                "title": "Reading a pack before you install it",
                "subject_label": "Packs",
                "revision": 3,
                "sections_done": 1,
                "sections_total": 5,
                "next_step": {"kind": "start_lesson", "label": "Start the next section"},
                "evidence_summary": {"current_objective_id": "obj-2", "independent": 1, "total_objectives": 5},
            },
            "objectives": [
                {"objective_id": "obj-1", "title": "Read what a pack manifest declares", "state": "completed", "independent": True, "ordinal": 1},
                {"objective_id": "obj-2", "title": "Say what an unreviewed check record means", "state": "ready", "ordinal": 2},
                {"objective_id": "obj-3", "title": "Install a pack without a review", "state": "ready", "ordinal": 3},
                {"objective_id": "obj-4", "title": "Run the first section", "state": "ready", "ordinal": 4},
                {"objective_id": "obj-5", "title": "Close the loop with evidence", "state": "locked", "locked": True, "ordinal": 5},
            ],
            "page": {"section": {"objective_id": "obj-2"}},
            "plate": {"artifactId": None, "src": None, "anchors": []},
            "anchors": [],
            "others": [
                {"course_id": "c-1", "title": "Japanese: ordering at a cafe", "next_step": {"label": "Continue Section 3"}},
                {"course_id": "c-2", "title": "Sourdough: the starter", "next_step": {"label": "Start Section 1"}},
            ],
            "sectionsDone": 1,
            "sectionsTotal": 5,
            "parentLabel": "Home",
            "busy": False,
            "worldState": "approved",
            "readState": "ready",
        },
    },
    "home": {"export": "CoursebookHome", "props": {}},
    "lesson-textbook": {"export": "mod.LessonDocumentView", "lesson": {"kind": "document", "view": "textbook"}},
    "lesson-guided": {"export": "mod.LessonDocumentView", "lesson": {"kind": "document", "view": "guided"}},
    "lesson-quest": {"export": "mod.LessonDocumentView", "lesson": {"kind": "document", "view": "field_quest"}},
    "lesson-section": {"export": "mod.SectionPage", "lesson": {"kind": "section"}},
    "classroom-guided": {"export": "ClassroomV3", "classroom": "guided"},
    "classroom-game": {"export": "ClassroomV3", "classroom": "game"},
}

def _pack_lesson() -> dict:
    """A lesson document built from the bundled L0 pack, never from invented prose.

    The pack ships the section markdown; the deck's document shape wants blocks with short and deep
    text, so the markdown's `##` sections become explain blocks and the objective's own check becomes
    the practice block. The frame therefore shows the product holding real course content.
    """
    import re

    pack = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
    meta = json.loads((pack / "pack.json").read_text(encoding="utf-8"))
    objective = meta["objectives"][0]
    section = objective["sections"][0]
    markdown = (pack / section["path"]).read_text(encoding="utf-8")
    check = objective["checks"][0]

    def sentence(text: str, limit: int = 180) -> str:
        """A complete first sentence, never a mid-word cut: the guided view shows this line alone."""
        flat = " ".join(text.split())
        cut = flat[:limit]
        stop = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        return (cut[: stop + 1] if stop > 40 else cut).strip()

    def plain(chunk: str) -> str:
        chunk = re.sub(r"^#+\s.*$", "", chunk, flags=re.M)
        chunk = re.sub(r"`([^`]+)`", r"\1", chunk)
        chunk = re.sub(r"\*\*([^*]+)\*\*", r"\1", chunk)
        return re.sub(r"[ \t]+\n", "\n", chunk).strip()

    parts = [plain(chunk) for chunk in re.split(r"^## ", markdown, flags=re.M)]
    parts = [part for part in parts if part]
    blocks = [{
        "id": "blk_orient0001",
        "role": "orient",
        "headline": section["title"],
        "short": sentence(parts[0]),
        "deep": parts[0],
        "media": [],
        "check_id": None,
        "source_ids": ["src_pack01"],
    }]
    for index, chunk in enumerate(parts[1:4], start=1):
        head, _, rest = chunk.partition("\n")
        blocks.append({
            "id": f"blk_explain{index:03d}",
            "role": "explain",
            "headline": head.strip()[:90],
            "short": sentence(rest.strip() or head.strip()),
            "deep": chunk,
            "media": [],
            "check_id": None,
            "source_ids": ["src_pack01"],
        })
    blocks.append({
        "id": "blk_practice01",
        "role": "practice",
        "headline": "Which line is the confession?",
        "short": "Read both lines, then name the cue that changes the reading.",
        "deep": check["stimulus"],
        "media": [],
        "check_id": check["check_id"],
        "source_ids": ["src_pack01"],
    })
    return {
        "schema_version": 1,
        "document_id": "doc_0123456789abcdef0123",
        "content_hash": "sha256:" + "a" * 64,
        "section_title": section["title"],
        "objective_id": objective["objective_id"],
        "state": "complete",
        "view_note": None,
        "views": {"textbook": True, "guided": True, "field_quest": True, "field_notes": True},
        "blocks": blocks,
        "check_id": check["check_id"],
        "source_ids": ["src_pack01"],
    }


LESSON_SOURCES = [{"source_id": "src_pack01", "title": "Japanese affection in context - L0 pack"}]


LESSON_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as mod from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const h = React.createElement
const sources = {}
for (const source of payload.sources || []) sources[source.source_id] = source
const wrap = (node) =>
  mod.CbV3Scope
    ? h(mod.CbV3Scope, {
        mode: payload.mode || 'light',
        attributes: { 'data-cb-route': '', 'class': 'cb3-route' },
        children: h('div', { className: 'cb3-gutter' }, node)
      })
    : node

if (payload.kind === 'section') {
  const page = {
    revision: 4,
    section: {
      objective_id: payload.document.objective_id,
      title: payload.document.section_title,
      state: 'needs_review',
      evidence_target: 'discrimination',
      last_opened_at: null
    },
    runtime: { lesson_run_id: 'run_1', binding_id: null, binding_status: 'detached', session_state: 'stored_only' },
    segments: [], attempts: [], notebook_entries: [],
    sources: payload.sources || [],
    document: payload.document
  }
  const node = h(mod.SectionPage, {
    row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default' },
    objectiveId: payload.document.objective_id,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['check.open', 'artifact.get', 'notebook.save']),
    onBack: () => {},
    onChanged: () => {}
  })
  process.stdout.write(renderToStaticMarkup(wrap(node)))
} else {
  const checkNode = h('div', { className: 'cb-check-standin' },
    h('p', null, payload.practiceStimulus || ''),
    h('button', { type: 'button' }, 'Answer'))
  const node = h(mod.LessonDocumentView, {
    document: payload.document,
    view: payload.view,
    withCheck: true,
    sources,
    checkNode
  })
  process.stdout.write(renderToStaticMarkup(wrap(node)))
}
"""


HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
globalThis.__CB_TEST_MODE__ = payload.mode || 'light'
const mod = await import('./plugin.js')
const h = React.createElement

const Comp = mod[payload.component]
if (!Comp) throw new Error('the module does not export ' + payload.component)
const props = { ...payload.props, width: payload.width }
if (payload.component === 'CourseHomeV3') {
  Object.assign(props, {
    onBack: () => {}, onContinue: () => {}, onOpenPlan: () => {},
    onOpenSection: () => {}, onOpenStudio: () => {}
  })
}
const scope = h(mod.CbV3Scope, {
  mode: payload.mode || 'light',
  attributes: { 'data-cb-route': '' },
  children: h(Comp, props)
})
process.stdout.write(renderToStaticMarkup(scope))
"""

CLASSROOM_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width)
globalThis.__CB_TEST_MODE__ = payload.mode || 'light'
const mod = await import('./plugin.js')
const h = React.createElement
const node = h(mod.ClassroomV3, { ...payload.props, mode: payload.viewMode })
const wrapped = mod.CbV3Scope
  ? h(mod.CbV3Scope, {
      mode: payload.mode || 'light',
      attributes: { 'data-cb-route': '', 'class': 'cb3-route' },
      children: h('div', { className: 'cb3-gutter' }, node)
    })
  : node
process.stdout.write(renderToStaticMarkup(wrapped))
"""

SHOT = r"""
const { chromium } = require('playwright')
;(async () => {
  const [, , file, out, width, hostHeader] = process.argv
  const browser = await chromium.launch({ executablePath: '/usr/lib/chromium/chromium', args: ['--no-sandbox'] })
  const page = await browser.newPage({ viewport: { width: Number(width), height: 900 }, deviceScaleFactor: 2 })
  await page.goto('file://' + file)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(350)
  const info = await page.evaluate(() => {
    const uses = (family) => {
      const needle = '"' + family + '"'
      const nodes = document.querySelectorAll('*')
      for (const node of nodes) {
        if (getComputedStyle(node).fontFamily.indexOf(needle) >= 0) return true
      }
      return false
    }
    const usedDisplay = uses('CB Display')
    const usedUi = uses('CB UI')
    return {
      full: document.documentElement.scrollHeight,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      h1_count: document.querySelectorAll('h1').length,
      h1_text: (document.querySelector('h1') || {}).textContent || null,
      heading_order: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].slice(0, 12).map((n) => n.tagName + ':' + (n.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)),
      primary_actions: [...document.querySelectorAll('[data-cb-action="primary"],[data-cb3-pill="primary"]')].map((n) => (n.textContent || '').replace(/\s+/g, ' ').trim()),
      fontDisplay: document.fonts.check('16px "CB Display"'),
      fontUi: document.fonts.check('16px "CB UI"'),
      fontDisplayUsed: usedDisplay,
      fontUiUsed: usedUi,
      // A face that no painted element asks for is not a missing font: the check() call is lazy.
      fontDisplayOk: document.fonts.check('16px "CB Display"') || !usedDisplay,
      fontUiOk: document.fonts.check('16px "CB UI"') || !usedUi
    }
  })
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: Number(width), height: info.full } })
  process.stdout.write(JSON.stringify(info))
  await browser.close()
})()
"""


def stage(root: Path) -> None:
    modules = _desktop_node_modules()
    if modules is None:
        raise SystemExit("react/react-dom are not installed beside the desktop app")
    (root / "plugin.js").write_text(PLUGIN.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
    (root / "lesson-harness.mjs").write_text(LESSON_HARNESS, encoding="utf-8")
    (root / "classroom-harness.mjs").write_text(CLASSROOM_HARNESS, encoding="utf-8")
    (root / "destination-harness.mjs").write_text(
        (ROOT / "scripts" / "cb-frame-render.mjs").read_text(encoding="utf-8"), encoding="utf-8"
    )
    nm = root / "node_modules"
    nm.mkdir()
    for name in ("react", "react-dom", "scheduler", "jsdom"):
        source = modules.parent / name if (modules.parent / name).is_dir() else modules / name
        if source.is_dir():
            (nm / name).symlink_to(source, target_is_directory=True)
    sdk = nm / "@hermes" / "plugin-sdk"
    sdk.mkdir(parents=True)
    (sdk / "package.json").write_text(
        json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
    )
    stub = (
        SETTINGS_SDK_STUB.replace(SEGMENTED_NEW, SEGMENTED_REAL)
        .replace(FORM_STUBS_OLD, FORM_STUBS_NEW)
        .replace(BUTTON_HEAD_OLD, BUTTON_HEAD_NEW)
        .replace(BUTTON_ATTRS_OLD, BUTTON_ATTRS_NEW)
    )
    stub = stub.replace(
        "export const Codicon = () => null",
        "export const Codicon = (props) => "
        "React.createElement('span', { className: 'cb-codicon', 'data-icon': props && props.name, 'aria-hidden': 'true' }, "
        "({ 'arrow-left': '←', 'chevron-left': '‹', play: '\\u25B8', check: '\\u2713', lock: '\\u25A0', 'chevron-right': '\\u203A' })[props && props.name] || '\\u00B7')",
    )
    (sdk / "index.js").write_text(stub, encoding="utf-8")


def page(markup: str, width: int, header: bool) -> str:
    host = '<div class="host-header"><span>H</span></div>' if header else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Coursebook module frame</title>
<style>
  html, body {{ margin: 0; background: #f5e3c8; }}
  .host-header {{ height: 86px; background: #1b1712; }}
  .host-header span {{ display: inline-block; margin: 24px 0 0 28px; color: #8a7a63; font: 20px system-ui; }}
  .frame {{ width: {width}px; margin: 0 auto; }}
  .cb-codicon {{ font: 16px/1 system-ui, sans-serif; color: currentColor; }}
</style></head>
<body>{host}<div class="frame">{markup}</div></body></html>
"""


def _host_stylesheet() -> tuple[str, str | None, str | None]:
    """The installed Desktop's compiled utility CSS, which the sidebar/nav/settings rely on.

    The plugin ships its own `CB_V3_CSS` (already in the frame via `CbV3Scope`), but a handful of
    host utility classes (`text-xs`, `max-w-prose`, `mt-1`) are the host's, and the real window
    loads them. A frame without them is a slightly different type scale. This reads the installed
    build's stylesheet and records its sha, so the frame names the host version it was painted with.
    """
    candidates = []
    override = os.environ.get("HERMES_DESKTOP_APP")
    if override:
        candidates.append(Path(override) / "dist" / "assets")
    candidates.append(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop" / "dist" / "assets")
    for directory in candidates:
        if not directory.is_dir():
            continue
        sheets = sorted(directory.glob("main-*.css"))
        if sheets:
            text = sheets[0].read_text(encoding="utf-8")
            return text, hashlib.sha256(text.encode("utf-8")).hexdigest(), str(sheets[0])
    return "", None, None


def destination_page(markup: str, width: int, mode: str, host_css: str = "") -> str:
    """The shell around a route destination frame: no host chrome, the module's own stylesheet."""
    paper = "#14110c" if mode == "dark" else "#f5e3c8"
    return f"""<!doctype html>
<html lang="en" data-mode="{mode}"><head><meta charset="utf-8"><title>Coursebook destination frame</title>
<meta name="color-scheme" content="light dark">
<style>{host_css}</style>
<style>
  html, body {{ margin: 0; padding: 0; background: {paper}; }}
  body {{ width: {width}px; overflow-x: hidden; }}
  /* The route's own page body carries the block rhythm above and below a destination; the
     frame's root must too, or a sheet paints flush against the top edge. */
  #root {{ width: {width}px; padding-block: 1.5rem; box-sizing: border-box; }}
  .cb-codicon {{ font: 16px/1 system-ui, sans-serif; color: currentColor; }}
  img {{ max-width: 100%; }}
</style></head>
<body><div id="root">{markup}</div></body></html>
"""


def render_destinations(selected: list[dict], widths: list[int], mode: str, out: Path,
                        data: dict | None = None) -> int:
    """Render every requested route destination at every width, with a manifest per frame."""
    from scripts import cb_frame_fixtures as fixtures_mod

    if data is None:
        print("reading real backend fixtures for the route destinations ...", file=sys.stderr)
        data = fixtures_mod.build()
    record = fixtures_mod.fixture_record(data)
    host_css, host_css_sha, host_css_path = _host_stylesheet()
    if not host_css:
        print("WARNING: the installed Desktop stylesheet was not found; host utilities are absent", file=sys.stderr)
    sha = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
    installed = hashlib.sha256(INSTALLED.read_bytes()).hexdigest() if INSTALLED.is_file() else None

    tmp = tempfile.TemporaryDirectory(prefix="cb-frame-all-")
    root = Path(tmp.name)
    stage(root)
    (root / "shot.js").write_text(SHOT, encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    rc = 0
    for spec in selected:
        for width in widths:
            case = {
                "width": width,
                "mode": mode,
                "destination": spec["id"],
                "surface": spec["surface"],
                "props": spec["props"],
                "rest": spec["rest"],
                "rpc": spec["rpc"],
                "storage": spec.get("storage") or {},
                "implemented": spec.get("implemented") or data["implemented"],
                "actions": spec.get("actions") or [],
            }
            case_file = root / "case.json"
            case_file.write_text(json.dumps(case), encoding="utf-8")
            rendered = subprocess.run(
                ["node", str(root / "destination-harness.mjs"), str(case_file)],
                cwd=root, capture_output=True, text=True, timeout=300,
            )
            if rendered.returncode != 0:
                sys.stderr.write(f"\n[{spec['id']} {width}] render failed:\n{rendered.stderr[-4000:]}\n")
                rc = 2
                continue
            if rendered.stdout.startswith("{"):
                payload = json.loads(rendered.stdout)
            else:  # a stray console line; the JSON is the last line
                payload = json.loads(rendered.stdout.strip().splitlines()[-1])
            html_path = (out / f"{spec['id']}-{width}.html").resolve()
            html_path.write_text(destination_page(payload["html"], width, mode, host_css), encoding="utf-8")
            png = out / f"{spec['id']}-{width}.png"
            shot = subprocess.run(
                ["node", str(root / "shot.js"), str(html_path), str(png), str(width), "1"],
                cwd=ROOT / "visual",
                env={**os.environ, "NODE_PATH": str(ROOT / "visual" / "node_modules")},
                capture_output=True, text=True, timeout=300,
            )
            if shot.returncode != 0:
                sys.stderr.write(f"\n[{spec['id']} {width}] shot failed:\n{shot.stderr[-4000:]}\n")
                rc = 2
                continue
            info = json.loads(shot.stdout or "{}")
            manifest = {
                "surface": "route destination frame (no window, no backend)",
                "destination": spec["id"],
                "title": spec.get("title"),
                "component": spec["surface"],
                "width": width,
                "frame_height": info.get("full"),
                "scroll_width": info.get("scrollWidth"),
                "client_width": info.get("clientWidth"),
                "horizontal_overflow": info.get("overflow"),
                "h1_count": info.get("h1_count"),
                "h1_text": info.get("h1_text"),
                "heading_order": info.get("heading_order"),
                "primary_actions": info.get("primary_actions"),
                "mode": mode,
                "module_sha256": sha,
                "installed_module_sha256": installed,
                "installed_matches_branch": installed == sha,
                "fonts": {"CB Display": info.get("fontDisplay"), "CB UI": info.get("fontUi")},
                "fonts_used": {"CB Display": info.get("fontDisplayUsed"), "CB UI": info.get("fontUiUsed")},
                "host_stylesheet": {"sha256": host_css_sha, "path": host_css_path},
                "fixture_source": spec.get("source") or [],
                "fixture_text": {key: record.get(key) for key in (spec.get("source") or []) if key in record},
                "fixture_sha256": record.get("fixture_sha256"),
                "interactions": payload.get("notes") or [],
                "requests": payload.get("requests") or [],
                "unmapped": payload.get("unmapped") or [],
                "png": str(png.relative_to(ROOT)) if str(png).startswith(str(ROOT)) else str(png),
                "note": (
                    "The module in this checkout, mounted in jsdom through the real register() and "
                    "CbV3Scope, painted by headless Chromium. The transport is stubbed with payloads "
                    "recorded from the real backend (see fixture_source). Not a live install."
                ),
            }
            (out / f"frame-{spec['id']}-{width}.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            index.append(manifest)
            print(
                f"{png.relative_to(ROOT)}  sha {sha[:12]}  {width}px  h={info.get('full')}"
                f"  unmapped={len(manifest['unmapped'])}"
            )
            if manifest["unmapped"]:
                print(f"  UNMAPPED fixtures requested: {', '.join(manifest['unmapped'])}", file=sys.stderr)
                rc = 1
            if manifest["horizontal_overflow"]:
                print(
                    f"  overflows: scrollWidth {manifest['scroll_width']} > clientWidth {manifest['client_width']}",
                    file=sys.stderr,
                )
                rc = 1
            if not (info.get("fontDisplayOk") and info.get("fontUiOk")):
                print("  WARNING: a display face a painted element asks for did not load", file=sys.stderr)
                rc = 1
    (out / "frames-index.json").write_text(
        json.dumps(
            {
                "kind": "route destinations",
                "module_sha256": sha,
                "installed_module_sha256": installed,
                "host_stylesheet": {"sha256": host_css_sha, "path": host_css_path},
                "fixtures": record,
                "frames": index,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"\n{len(index)} frames  -> {out / 'frames-index.json'}")
    tmp.cleanup()
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--component", default="course-home")
    ap.add_argument("--destination", action="append", default=[], help="render one route destination by id (repeatable)")
    ap.add_argument("--all", action="store_true", help="render every route destination at 1344 and 460")
    ap.add_argument("--width", type=int, nargs="+", default=None)
    ap.add_argument("--mode", default="light")
    ap.add_argument("--out", default=str(ROOT / ".coursebook" / "frames"))
    ap.add_argument("--no-host-header", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--list-destinations", action="store_true")
    ap.add_argument(
        "--preflight",
        action="store_true",
        help="answer only: may a Desktop window be reviewed right now? Never captures.",
    )
    args = ap.parse_args()

    if args.preflight:
        sha = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
        installed = hashlib.sha256(INSTALLED.read_bytes()).hexdigest() if INSTALLED.is_file() else None
        fresh_build = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_plugin.py"), "--check"],
            capture_output=True, text=True,
        ).returncode == 0
        print(f"branch plugin.js   {sha}")
        print(f"installed plugin   {installed or 'absent'}")
        print(f"src builds clean   {fresh_build}")
        if installed != sha:
            print("\nREFUSE a window review: the installed module is not this checkout's build.")
            print("A Desktop window holds the module it loaded at start, so it is photographing a")
            print("different build. Either review with `python3 scripts/cb-frame.py --component ...`")
            print("(frames the branch by construction), or install and restart the app first:")
            print("  cp desktop/plugin.js ~/.hermes/desktop-plugins/coursebook/plugin.js   # then restart")
            return 1
        print("\nA window may be reviewed, but only after the app was started *after* this install.")
        print("Prefer `python3 scripts/cb-frame.py` for composition: it has no window and no backend.")
        return 0

    widths = args.width or ([1344, 460] if (args.all or args.destination) else [1344])

    if args.all or args.destination:
        from scripts import cb_frame_fixtures as fixtures_mod

        data = fixtures_mod.build()
        specs = fixtures_mod.frames(data)
        if args.destination:
            known = {spec["id"] for spec in specs}
            unknown = [name for name in args.destination if name not in known]
            if unknown:
                raise SystemExit(
                    f"unknown destination {unknown!r}; known: {', '.join(sorted(known))}"
                )
            wanted = set(args.destination)
            specs = [spec for spec in specs if spec["id"] in wanted]
        return render_destinations(specs, widths, args.mode, Path(args.out).resolve(), data)

    if args.list_destinations:
        from scripts import cb_frame_fixtures as fixtures_mod

        for spec in fixtures_mod.frames(fixtures_mod.build()):
            print(f"{spec['id']:24s} {spec['surface']:24s} {spec['title']}")
        return 0

    if args.list:
        for name, spec in COMPONENTS.items():
            print(f"{name:14s} {spec['export']}")
        return 0
    if args.component not in COMPONENTS:
        raise SystemExit(f"unknown component {args.component!r}; --list shows the registry")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
    installed = hashlib.sha256(INSTALLED.read_bytes()).hexdigest() if INSTALLED.is_file() else None
    spec = COMPONENTS[args.component]

    tmp = tempfile.TemporaryDirectory(prefix="cb-frame-")
    root = Path(tmp.name)
    stage(root)
    (root / "shot.js").write_text(SHOT, encoding="utf-8")
    rc = 0
    for width in widths:
        case = root / "case.json"
        if spec.get("classroom"):
            from tests.test_cp_023_classroom import check as fixture_check
            from tests.test_cp_023_classroom import outline as fixture_outline
            from tests.test_cp_023_classroom import page as fixture_page
            from tests.test_cp_023_classroom import row as fixture_row

            payload = {
                "width": width,
                "mode": args.mode,
                "viewMode": spec["classroom"],
                "props": {
                    "row": fixture_row(),
                    "outline": fixture_outline(),
                    "page": fixture_page(),
                    "check": fixture_check(),
                    "scene": None,
                    "onBack": None,
                    "onOpenSection": None,
                    "onNextSection": None,
                    "onStartChat": None,
                    "onAskTutor": None,
                    "onRetry": None,
                    "onCommitted": None,
                },
            }
            harness = root / "classroom-harness.mjs"
        elif spec.get("lesson"):
            lesson = _pack_lesson()
            payload = {
                "kind": spec["lesson"]["kind"],
                "document": lesson,
                "sources": LESSON_SOURCES,
                "mode": args.mode,
                "practiceStimulus": lesson["blocks"][-1]["deep"],
            }
            if spec["lesson"]["kind"] == "document":
                payload["view"] = spec["lesson"]["view"]
            harness = root / "lesson-harness.mjs"
        else:
            payload = {"width": width, "mode": args.mode, "component": spec["export"], "props": spec["props"]}
            harness = root / "harness.mjs"
        case.write_text(json.dumps(payload), encoding="utf-8")
        rendered = subprocess.run(
            ["node", str(harness), str(case)], cwd=root, capture_output=True, text=True, timeout=300
        )
        if rendered.returncode != 0:
            sys.stderr.write(rendered.stderr[-4000:])
            return 2
        html = (out / f"{args.component}-{width}.html").resolve()
        html.write_text(page(rendered.stdout, width, not args.no_host_header), encoding="utf-8")
        png = out / f"{args.component}-{width}.png"
        shot = subprocess.run(
            ["node", str(root / "shot.js"), str(html), str(png), str(width), "1"],
            cwd=ROOT / "visual",
            env={**os.environ, "NODE_PATH": str(ROOT / "visual" / "node_modules")},
            capture_output=True,
            text=True,
            timeout=300,
        )
        if shot.returncode != 0:
            sys.stderr.write(shot.stderr[-4000:])
            return 2
        info = json.loads(shot.stdout or "{}")
        manifest = {
            "surface": "module frame (no window, no backend)",
            "component": args.component,
            "export": spec["export"],
            "width": width,
            "frame_height": info.get("full"),
            "host_header": not args.no_host_header,
            "mode": args.mode,
            "module_sha256": sha,
            "installed_module_sha256": installed,
            "installed_matches_branch": installed == sha,
            "fonts": {"CB Display": info.get("fontDisplay"), "CB UI": info.get("fontUi")},
            "png": str(png.relative_to(ROOT)) if str(png).startswith(str(ROOT)) else str(png),
            "note": "Valid evidence of the module in this checkout. Not a live install: a Desktop "
            "window holds whatever module it loaded at start.",
        }
        (out / f"frame-{args.component}-{width}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"{png}  sha {sha[:12]}  installed {str(installed)[:12]}  match={installed == sha}")
        if not (info.get("fontDisplay") and info.get("fontUi")):
            print("  WARNING: a display face did not report loaded; the frame is a fallback render", file=sys.stderr)
            rc = 1
    tmp.cleanup()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
