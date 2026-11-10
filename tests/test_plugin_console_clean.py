"""No Coursebook surface may render an unkeyed element array.

React only reports a missing `key` through `console.error` in development — the shipped Desktop
module renders in development inside the shell, so a tree full of unkeyed `children: [...]` arrays
paints normally while logging a warning per array. CP-038's capture door reads the renderer console
and refuses a frame when it sees one (`scripts/cp-capture.mjs`), which is how CP-043 found that
every non-Home surface on master was uncapturable.

A green unit suite said nothing about that, because no harness read the console. This module is that
harness: it mounts the surfaces the door captures through the real plugin module (React + jsdom +
the scripted host stub from the other desktop suites) and fails if any render logs

* `Each child in a list should have a unique "key" prop` — an array child entry with no key, or
* `A props object containing a key prop is being spread into JSX` — a key passed inside `props`
  instead of as the third argument to `jsx`/`jsxs`.

What this does not prove: that the live route paints these exact frames, or that the backend serves
this data. `docs/concept-parity/captures/cp043-*.json` is the live proof; this test is the guard
that runs on every commit without a rig.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

KEY_PATTERNS = (
    'Each child in a list should have a unique "key" prop',
    "A props object containing a key prop is being spread into JSX",
)

#: Every surface the capture door names, mounted one after another in one jsdom document. Each
#: entry says which exported component to render and what the surface is called in a refusal.
HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

// Every warning React prints is kept with the surface that produced it. `console.error` is the
// channel the capture door reads, so it is the channel this harness reads too.
const seen = []
let surface = 'startup'
const realError = console.error
console.error = (...args) => {
  const text = args.map((value) => (typeof value === 'string' ? value : String(value))).join(' ')
  seen.push({ surface, text })
}

const IMPLEMENTED = [
  'library.list', 'course.outline', 'lesson.page', 'world.read', 'course.mode.set',
  'parent.brief.get', 'notebook.list', 'pack.inspect'
]

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') return { wire_version: 25, implemented_methods: IMPLEMENTED }
  if (base === '/workshop/catalog') return { ok: true, ...payload.catalog }
  if (base === '/rpc') {
    const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body
    if (body.method === 'library.list') return { ok: true, result: payload.library }
    if (body.method === 'course.outline') return { ok: true, result: payload.outline }
    return { ok: true, result: {} }
  }
  if (base === '/artifacts') return { ok: true, items: [] }
  throw new Error('unexpected rest path ' + path)
}

const mod = await import('./plugin.js')
mod.default.register({
  rest: fakeRest,

  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => setTimeout(fn, ms)
})

const { createRoot } = await import('react-dom/client')
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}

const quiet = () => {}

const mount = async (name, element) => {
  surface = name
  const host = document.createElement('div')
  host.setAttribute('data-surface', name)
  document.body.appendChild(host)
  const root = createRoot(host)
  await act(async () => { root.render(element) })
  await flush()
  const html = host.innerHTML
  await act(async () => { root.unmount() })
  host.remove()
  return { name, html_length: html.length, controls: (html.match(/<button/g) || []).length }
}

const mounted = []

// 1. Global Home — the library launcher.
mounted.push(await mount('home', React.createElement(mod.HomeLibraryPanel, {
  online: true,
  canCreate: true,
  onStartCreate: quiet,
  onBrowseLibrary: quiet,
  onOpenCourse: quiet,
  onShowAll: quiet,
  onOpenStudio: quiet
})))

// 2. All Courses, through the shelf disclosure that names a shared course's other records.
mounted.push(await mount('all-courses', React.createElement(mod.ShelfDisclosure, {
  group: payload.shelfGroup,
  onOpen: quiet,
  onOpenLibrary: quiet,
  label: 'Records'
})))

// 3. Workshop — the storefront with at least three real catalogue rows.
mounted.push(await mount('workshop', React.createElement(mod.WorkshopView, {
  implemented: new Set(IMPLEMENTED),
  createOpen: false,
  onOpenCourse: quiet,
  onStartSyllabus: null,
  onStartImport: null,
  canSyllabus: false,
  canImport: false,
  onEmptyChange: quiet
})))

// 4. The course home: the trailhead, the path stops and the desk around them.
mounted.push(await mount('course-home', React.createElement(mod.FieldDesk, {
  implemented: new Set(IMPLEMENTED),
  onOpen: quiet,
  onShowAll: quiet,
  onStartCreate: null,
  onStartSyllabus: null,
  profile: 'default',
  onEmptyChange: quiet,
  selectedCourseId: payload.library.items[0].course_id,
  onSelectCourse: quiet,
  onOpenStudio: quiet,
  onBrowseLibrary: quiet,
  onSelectedClassroom: quiet,
  online: true,
  prefs: payload.prefs
})))

// 5. The world badge that names Game/Textbook on a course surface.
mounted.push(await mount('world-badge', React.createElement(mod.ModeBadge, { mode: 'game' })))

console.error = realError
process.stdout.write(JSON.stringify({ mounted, warnings: seen }))
"""

SDK_STUB = r"""
import React from 'react'

const atom = (value) => ({ get: () => value })
const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)

export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (a) => a.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })

export const Button = (props) => el('button', { type: 'button', onClick: props.onClick, disabled: Boolean(props.disabled) }, textOf(props))
export const RowButton = (props) => el('button', { type: 'button', onClick: props.onClick }, textOf(props))
export const Badge = (props) => el('span', { className: 'badge' }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) => el('div', { className: 'list-row' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const Checkbox = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const MessageTextContent = () => null
export const ToggleRow = (props) =>
  el('button', { type: 'button', onClick: props.onChange, 'aria-pressed': Boolean(props.checked) }, props.label || null)

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: 1049, height: 900, narrow: false })
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true })
}
"""


def library_row(**overrides) -> dict:
    row = {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Small-engine maintenance",
        "subtitle": None,
        "recipe": "committed",
        "level_label": None,
        "locale": None,
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resume_lesson", "label": "Resume this lesson"},
        "evidence_summary": {
            "independent": 1,
            "review_due": 0,
            "total_objectives": 3,
            "current_objective_id": "obj_0000000000000002",
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 7,
    }
    row.update(overrides)
    return row


def library(*rows: dict) -> dict:
    return {
        "items": list(rows),
        "next_cursor": None,
        "total": len(rows),
        "empty_reason": None,
        "applied_filter": "all",
    }


OUTLINE = {
    "enrollment_id": "enr_0123456789abcdef",
    "plan": {"plan_id": "pln_0123456789abcdef", "version": 1, "state": "approved", "plan_hash": "sha256:" + "b" * 64},
    "objectives": [
        {
            "objective_id": "obj_0000000000000001",
            "ordinal": 1,
            "title": "Name the three things an engine needs",
            "evidence_target": "recall",
            "state": "independent_evidence",
            "check_state": "closed",
            "attempt_count": 1,
            "independent": True,
            "last_opened_at": "2026-11-05T10:00:00.000000+00:00",
        },
        {
            "objective_id": "obj_0000000000000002",
            "ordinal": 2,
            "title": "Diagnose a no-start",
            "evidence_target": "procedure",
            "state": "review_due",
            "check_state": "open",
            "attempt_count": 1,
            "independent": False,
            "last_opened_at": "2026-11-06T17:30:00.000000+00:00",
        },
        {
            "objective_id": "obj_0000000000000003",
            "ordinal": 3,
            "title": "Replace a fouled plug",
            "evidence_target": "procedure",
            "state": "introduced",
            "check_state": "none",
            "attempt_count": 0,
            "independent": False,
            "last_opened_at": None,
        },
    ],
    "total": 3,
    "truncated": False,
}


def workshop_item(pack_id: str, title: str, **overrides) -> dict:
    """One `/workshop/catalog` row, shaped like `coursebook.workshop._entry_item` returns."""
    item = {
        "pack_id": pack_id,
        "pack_version": "1.0.0",
        "title": title,
        "subtitle": None,
        "recipe": "committed",
        "level_label": "L0",
        "locale": "en",
        "content_hash": "sha256:" + "c" * 64,
        "attribution": "",
        "license": {"id": "CC0-1.0", "note": None, "redistribution": "allowed"},
        "contributors": [],
        "outcome": "Read a shop manual page and name the part it describes.",
        "objectives": 3,
        "sections": [
            {"title": "Read the page", "objective": "Name the part", "minutes": 10},
            {"title": "Say it back", "objective": "Name the part", "minutes": 5},
        ],
        "minutes": 15,
        "sources": [],
        "trust": {"labels": ["Bundled", "Reviewed"], "notes": []},
        "cover": None,
        "featured": False,
        "installed": None,
        "source": {"id": "bundled", "label": "Bundled"},
        "category": "Workshop",
    }
    item.update(overrides)
    return item


CATALOG = {
    "generated": "2026-11-01T00:00:00.000000+00:00",
    "items": [
        workshop_item("pack_shop_reading", "Shop-manual reading"),
        workshop_item("pack_engine_basics", "Engine basics", featured=True),
        workshop_item("pack_tool_safety", "Tool safety"),
    ],
    "featured_pack_id": "pack_engine_basics",
    "refused": [],
    "count": 3,
}

SHELF_GROUP = {
    "key": "crs_0123456789abcdef",
    "label": "2 records for this course",
    "primary": library_row(),
    "members": [
        library_row(enrollment_id="enr_0000000000000002", updated_at="2026-11-05T18:00:00.000000+00:00"),
        library_row(enrollment_id="enr_0000000000000003", updated_at="2026-11-04T18:00:00.000000+00:00"),
    ],
}


def _desktop_node_modules() -> Path | None:
    candidates = [
        os.environ.get("HERMES_DESKTOP_APP"),
        str(Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop"),
        str(Path.home() / ".hermes" / "hermes-agent"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        react = Path(candidate) / "node_modules" / "react"
        server = Path(candidate) / "node_modules" / "react-dom" / "server.js"
        if react.is_dir() and server.is_file():
            return Path(candidate) / "node_modules"
    return None


class ConsoleCleanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-console-clean-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root
        cls.result = cls._run(root)

    @classmethod
    def _run(cls, root: Path) -> dict:
        case = root / "case.json"
        case.write_text(
            json.dumps(
                {
                    "library": library(library_row()),
                    "outline": OUTLINE,
                    "catalog": CATALOG,
                    "shelfGroup": SHELF_GROUP,
                    "prefs": {},
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            ["node", str(root / "harness.mjs"), str(case)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(f"console-clean harness failed:\n{result.stderr[-4000:]}")
        return json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_every_surface_mounted(self) -> None:
        mounted = {entry["name"]: entry for entry in self.result["mounted"]}
        for name in ("home", "all-courses", "workshop", "course-home", "world-badge"):
            self.assertIn(name, mounted, f"the {name} surface did not mount")
        # A surface that renders nothing proves nothing: each one has to produce real markup with
        # at least one control, or the cleanliness assertion below is vacuous.
        for name, entry in mounted.items():
            self.assertGreater(entry["html_length"], 200, f"{name} rendered almost no markup")
            if name != "world-badge":
                self.assertGreaterEqual(entry["controls"], 1, f"{name} rendered no control")

    def test_no_react_key_warning_on_any_surface(self) -> None:
        offenders = [
            f"[{entry['surface']}] {entry['text'][:400]}"
            for entry in self.result["warnings"]
            if any(pattern in entry["text"] for pattern in KEY_PATTERNS)
        ]
        self.assertEqual(
            offenders,
            [],
            "React logged a key warning; the capture door refuses such a frame:\n" + "\n".join(offenders[:20]),
        )


if __name__ == "__main__":
    unittest.main()
