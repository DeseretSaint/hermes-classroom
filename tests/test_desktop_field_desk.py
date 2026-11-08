"""The Field Desk home answers "what do I do next?" from reads the contract already has.

The plugin is one ESM file with no build step, so the test renders the shipped module through
React and checks the DOM it produces. The fixtures are shaped like the contract's own responses
(`library.list` row, `course.outline` objectives, `lesson.page` sources) — they are *input*, and
the assertions are that the desk never invents an estimate, a next step, a source or a course.

What this does not prove: that a live backend currently returns these rows. It proves the view is
honest about whatever it is served, including the empty, loading, failed and not-recorded cases.
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

HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { FieldDeskHome, buildDeskModel, deskEstimateLabel, mainlineObjective, cbCourseContour } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

if (payload.kind === 'model') {
  const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
  process.stdout.write(JSON.stringify({
    desk,
    label: deskEstimateLabel(payload.estimate),
    mainline: mainlineObjective(payload.row, payload.outline ? payload.outline.objectives : []),
    contour: cbCourseContour(payload.courseId, payload.title)
  }))
} else {
  const desk = buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
  const html = renderToStaticMarkup(
    React.createElement('div', { 'data-cb-scope': payload.mode || 'light', style: { color: 'var(--cb-ink)' } },
      React.createElement(FieldDeskHome, {
        desk,
        libraryStatus: payload.libraryStatus || 'ready',
        libraryError: payload.libraryError || null,
        stale: Boolean(payload.stale),
        busy: false,
        notice: null,
        onRetry: () => {},
        onCreate: () => {},
        onPrimary: () => {},
        onOpenSection: () => {},
        onSeePlan: () => {},
        onRetryEstimate: () => {},
        onOpen: () => {},
        onShowAll: () => {},
        sourcesOpen: Boolean(payload.sourcesOpen),
        onToggleSources: () => {},
        sourcesStatus: payload.sourcesStatus || 'idle',
        sourcesError: payload.sourcesError || null,
        sources: payload.sources || null,
        onRetrySources: () => {},
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'parent.brief.get'])
      })
    )
  )
  process.stdout.write(html)
}
"""

DOM_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
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

const IMPLEMENTED = ['library.list', 'course.outline', 'parent.brief.get', 'pack.inspect', 'notebook.list']
const calls = []
const rpcMethods = []
let queues = {}

// One scripted answer per method. An array is consumed in order, repeating the last entry, so a
// retry can be proven to issue a second read that paints a different result.
const answer = (method) => {
  const entry = (payload.responses || {})[method]
  if (entry === undefined) throw new Error('unexpected rpc ' + method)
  if (!Array.isArray(entry)) return entry
  const index = queues[method] || 0
  queues[method] = index + 1
  return entry[Math.min(index, entry.length - 1)]
}

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const httpMethod = (options && options.method) || 'GET'
  calls.push({ path: base, method: httpMethod })
  if (base === '/runtime') return { wire_version: 10, implemented_methods: IMPLEMENTED }
  if (base !== '/rpc') throw new Error('unexpected rest path ' + path)
  const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body
  rpcMethods.push(body.method)
  const plan = answer(body.method)
  if (plan && plan.__throw) throw new Error(plan.__throw)
  if (plan && plan.__refuse) {
    return { ok: false, contract_version: 10, operation_id: body.operation_id, error: plan.__refuse }
  }
  return { ok: true, contract_version: 10, operation_id: body.operation_id, result: plan.result || {} }
}

const mod = await import('./plugin.js')
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => setTimeout(fn, ms)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const props = {
  implemented: new Set(IMPLEMENTED),
  onOpen: () => {},
  onShowAll: () => {},
  onStartCreate: () => {},
  onStartSyllabus: () => {},
  profile: 'default',
  onEmptyChange: () => {}
}

const flush = async (ms = 40) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}

const read = () => {
  const node = document.querySelector('[data-cb-continue-minutes]')
  const buttons = [...document.querySelectorAll('button')]
  return {
    html: document.getElementById('root').innerHTML,
    minutes: node ? (node.textContent || '').trim() : null,
    state: node ? node.getAttribute('data-cb-continue-minutes-state') : null,
    title: node ? node.getAttribute('title') : null,
    retryControls: buttons.filter(
      (button) => button.getAttribute('aria-label') === 'Retry reading the session length'
    ).length,
    retryLabels: buttons.map((button) => (button.textContent || '').trim()).filter((text) => text === 'Retry'),
    companion: document.querySelector('[data-cb-companion]')
      ? {
          name: (document.querySelector('[data-cb-companion-name]') || {}).textContent || null,
          canvas: Boolean(document.querySelector('[data-cb-companion] canvas')),
          motion: document.querySelector('[data-cb-companion]').getAttribute('data-cb-companion-motion')
        }
      : null,
    rpc: calls.filter((call) => call.path === '/rpc').length,
    methods: rpcMethods.slice()
  }
}

await act(async () => { root.render(React.createElement(mod.FieldDesk, props)) })
await flush()

const observed = { steps: [] }
observed.steps.push({ step: 'initial', ...read() })

if (payload.script === 'retry') {
  const retry = [...document.querySelectorAll('button')].find(
    (button) => button.getAttribute('aria-label') === 'Retry reading the session length'
  )
  if (!retry) throw new Error('no retry control rendered for the failed estimate read')
  await act(async () => { retry.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
  observed.steps.push({ step: 'after-retry', ...read() })
}

// A second read of the scripted queue proves the retry issues a new request.
observed.rpcMethods = calls.filter((call) => call.path === '/rpc').map((call) => call.path)
process.stdout.write(JSON.stringify({ observed, html: document.getElementById('root').innerHTML }))
"""


SDK_STUB = """
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

const pass = (props) => {
  const out = { type: 'button', onClick: props.onClick, disabled: Boolean(props.disabled) }
  for (const key of ['className', 'aria-expanded', 'aria-controls', 'aria-current', 'aria-label', 'id', 'role', 'title']) {
    if (props[key] !== undefined) out[key] = props[key]
  }
  return out
}

export const Button = (props) => el('button', pass(props), textOf(props))
export const RowButton = (props) => el('button', pass(props), textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) =>
  el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) =>
  el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) =>
  el('div', { className: 'list-row' }, [
    el('div', { key: 'title', className: 'list-row-title' }, props.title),
    el('div', { key: 'description', className: 'list-row-description' }, props.description),
    el('div', { key: 'action', className: 'list-row-action' }, props.action)
  ])
export const SegmentedControl = (props) =>
  el('div', { className: 'segmented' }, (props.options || []).map((option) =>
    el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
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
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const MessageTextContent = () => null

export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: atom({ width: Number(process.env.CB_TEST_WIDTH || 1280), height: 900, narrow: false })
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true }),
  ...(process.env.CB_TEST_PET === '1'
    ? {
        request: async (method) => {
          if (method === 'pet.info.meta') {
            const missing = new Error('Method not found')
            missing.code = -32601
            throw missing
          }
          if (method !== 'pet.info') throw new Error('unexpected host.request ' + method)
          return {
            enabled: true,
            slug: 'ada',
            displayName: 'Ada',
            mime: 'image/png',
            spritesheetBase64:
              'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
            spritesheetRevision: 'r1',
            frameW: 1,
            frameH: 1,
            stateRows: ['idle']
          }
        }
      }
    : {})
}
"""


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


def library_row(**overrides) -> dict:
    """One `library.list` item, in the contract's own field names."""
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
        "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
        "evidence_summary": {
            "independent": 1,
            "review_due": 1,
            "total_objectives": 4,
            "current_objective_id": "obj_0000000000000003",
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
        {
            "objective_id": "obj_0000000000000004",
            "ordinal": 4,
            "title": "Check compression safely",
            "evidence_target": "procedure",
            "state": "not_started",
            "check_state": "none",
            "attempt_count": 0,
            "independent": False,
            "last_opened_at": None,
        },
    ],
    "total": 4,
    "truncated": False,
}

SOURCES = [
    {"source_id": "src_manual001", "title": "Shop manual §4 — ignition", "support_status": "supported", "fetched_at": "2026-11-01T00:00:00.000000+00:00"},
    {"source_id": "src_forum0002", "title": "Field notes — spark inspection", "support_status": "stale", "fetched_at": "2026-10-20T00:00:00.000000+00:00"},
]


class FieldDeskRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-field-desk-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        (root / "dom.mjs").write_text(DOM_HARNESS, encoding="utf-8")
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

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(payload.get("width", 1280))
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def render(self, **overrides) -> str:
        payload = {
            "kind": "render",
            "library": library(library_row()),
            "outline": OUTLINE,
            "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
            "sourcesOpen": False,
            "sourcesStatus": "idle",
        }
        payload.update(overrides)
        return self.run_harness(payload)

    def model(self, **overrides) -> dict:
        payload = {
            "kind": "model",
            "library": library(library_row()),
            "outline": OUTLINE,
            "estimate": {"status": "ready", "minutes": 20, "source": "parent_brief", "error": None},
        }
        payload.update(overrides)
        return json.loads(self.run_harness(payload))

    def run_dom(self, payload: dict) -> dict:
        """Mount the real FieldDesk container against a scripted `ctx.rest`."""
        case = self.root / "dom-case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(payload.get("width", 1280))
        env["CB_TEST_PET"] = "1" if payload.get("pet") else "0"
        result = subprocess.run(
            ["node", str(self.root / "dom.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return json.loads(result.stdout)

    def desk_dom(self, responses: dict, *, script: str = "none", row: dict | None = None, pet: bool = False) -> dict:
        return self.run_dom(
            {
                "script": script,
                "pet": pet,
                "library": library(row or library_row()),
                "outline": OUTLINE,
                "responses": {
                    "library.list": {"result": library(row or library_row())},
                    "course.outline": {"result": OUTLINE},
                    "notebook.list": {"result": {"items": [], "next_cursor": None, "total": 0}},
                    **responses,
                },
            }
        )

    def first_step(self, observed: dict) -> dict:
        return observed["observed"]["steps"][0]

    def test_the_companion_appears_only_when_a_real_pet_answers(self) -> None:
        without = self.first_step(self.desk_dom({}))
        self.assertIsNone(without["companion"])
        # The scripted host knows `pet.info` but refuses `pet.info.meta` with -32601, so this also
        # proves the meta-first fall-through.
        with_pet = self.first_step(self.desk_dom({}, pet=True))
        self.assertIsNotNone(with_pet["companion"], with_pet)
        self.assertTrue(with_pet["companion"]["canvas"])
        self.assertEqual(with_pet["companion"]["motion"], "static")
        self.assertIn("Ada", with_pet["companion"]["name"])

    # -- the Continue card ------------------------------------------------------------------
    def test_continue_names_the_section_the_next_action_and_the_position(self) -> None:
        html = self.render()
        self.assertIn('data-cb-desk="ready"', html)
        self.assertIn('data-cb-continue-section', html)
        # `resolve_review_due` in the row's next_step makes the due review the section to continue.
        self.assertIn("Diagnose a no-start", html)
        self.assertIn("Start the review", html)
        # H-145: the section title is the next step; the duplicate "Next ·" sentence is gone.
        self.assertNotIn("Next · ", html)
        self.assertIn("Section 2 of 4", html)

    def test_a_narrow_desk_stacks_and_drops_the_course_stamp(self) -> None:
        html = self.render(width=460)
        self.assertIn('data-cb-desk-layout="stacked"', html)
        self.assertIn('data-cb-continue-compact="true"', html)
        self.assertNotIn("data-cb-course-stamp", html)
        # The title is not being squeezed into a term-per-line column; the full row remains.
        self.assertIn("Diagnose a no-start", html)
        self.assertIn("Open section", html)

    def test_the_continue_plate_has_no_seal_at_any_width(self) -> None:
        # H-145: the 64 px seal read as an avatar and needed an explanation. The plate carries the
        # course title as text instead.
        for width in (460, 900, 1280):
            with self.subTest(width=width):
                html = self.render(width=width)
                self.assertNotIn("data-cb-course-stamp", html)
                self.assertIn("data-cb-desk-course", html)

    def test_continue_shows_the_recorded_estimate_and_last_touched(self) -> None:
        html = self.render()
        self.assertIn("≈ 20 min", html)
        self.assertIn("Last touched", html)
        self.assertIn('data-cb-continue-touched="section"', html)

    def test_a_course_with_no_recorded_estimate_says_so_instead_of_guessing(self) -> None:
        html = self.render(estimate={"status": "none", "minutes": None, "source": None, "error": None})
        self.assertIn("Session length not recorded", html)
        self.assertNotRegex(html, r"≈ \d+ min")

    def test_a_failed_estimate_read_is_not_reported_as_not_recorded(self) -> None:
        """A read failure is `error`, never the author's silence: 'could not be read' + one retry."""
        html = self.render(
            estimate={
                "status": "error",
                "minutes": None,
                "source": None,
                "error": {"code": "HOST_UNAVAILABLE", "message": "the backend did not answer"},
            }
        )
        self.assertIn("Session length could not be read", html)
        self.assertNotIn("not recorded", html)
        self.assertIn('data-cb-continue-minutes-state="error"', html)
        self.assertEqual(html.count('aria-label="Retry reading the session length"'), 1)

    def test_a_successful_answer_without_an_estimate_still_says_not_recorded(self) -> None:
        html = self.render(estimate={"status": "none", "minutes": None, "source": None, "error": None})
        self.assertIn("Session length not recorded", html)
        self.assertIn('data-cb-continue-minutes-state="none"', html)
        self.assertNotIn("could not be read", html)
        self.assertNotIn('aria-label="Retry reading the session length"', html)

    def test_estimate_label_never_derives_minutes(self) -> None:
        self.assertEqual(self.model(estimate={"status": "none"})["label"], "Session length not recorded")
        self.assertEqual(self.model(estimate={"status": "loading"})["label"], "Reading the estimate")
        self.assertEqual(self.model(estimate={"status": "ready", "minutes": 0})["label"], "Session length not recorded")
        self.assertEqual(self.model(estimate={"status": "error"})["label"], "Session length could not be read")
        self.assertEqual(
            self.model(estimate={"status": "ready", "minutes": 15, "source": "pack_manifest"})["label"], "≈ 15 min"
        )

    # -- the estimate read, mounted against a scripted ctx.rest ------------------------------
    def test_a_thrown_parent_brief_read_renders_could_not_be_read_with_one_retry(self) -> None:
        observed = self.desk_dom({"parent.brief.get": {"__throw": "the backend did not answer"}})
        step = self.first_step(observed)
        self.assertEqual(step["minutes"], "Session length could not be read")
        self.assertEqual(step["state"], "error")
        self.assertEqual(step["retryControls"], 1)
        # The failure offers a next action, and it is a Retry, not a second path.
        self.assertEqual(step["retryLabels"], ["Retry"])
        self.assertNotIn("not recorded", step["html"])
        self.assertIn("HOST_UNAVAILABLE", step["title"])
        # The failed read really was attempted: the desk did not decide "none" without asking.
        self.assertIn("parent.brief.get", step["methods"])

    def test_a_thrown_pack_manifest_read_renders_the_same_failure_state(self) -> None:
        row = library_row(provenance={"source": "pack", "pack_id": "pk_0123456789abcdef", "pack_version": 2})
        observed = self.desk_dom({"pack.inspect": {"__throw": "pack manifest unreadable"}}, row=row)
        step = self.first_step(observed)
        self.assertEqual(step["minutes"], "Session length could not be read")
        self.assertEqual(step["state"], "error")
        self.assertEqual(step["retryControls"], 1)
        self.assertNotIn("not recorded", step["html"])

    def test_a_refused_estimate_read_is_a_failure_but_parent_brief_not_found_is_an_answer(self) -> None:
        refused = self.first_step(
            self.desk_dom(
                {
                    "parent.brief.get": {
                        "__refuse": {
                            "code": "INTERNAL_ERROR",
                            "message": "the brief store failed",
                            "category": "internal",
                            "retryable": True,
                        }
                    }
                }
            )
        )
        self.assertEqual(refused["minutes"], "Session length could not be read")
        self.assertEqual(refused["state"], "error")
        self.assertIn("INTERNAL_ERROR", refused["title"])
        # An authored course that never had a parent brief is a successful "no estimate", not a
        # failure: NOT_FOUND keeps the original copy.
        not_found = self.first_step(
            self.desk_dom(
                {
                    "parent.brief.get": {
                        "__refuse": {
                            "code": "NOT_FOUND",
                            "message": "this course has no parent brief",
                            "category": "not_found",
                            "retryable": False,
                        }
                    }
                }
            )
        )
        self.assertEqual(not_found["minutes"], "Session length not recorded")
        self.assertEqual(not_found["state"], "none")
        self.assertEqual(not_found["retryControls"], 0)

    def test_retry_re_reads_the_estimate_and_paints_the_real_answer(self) -> None:
        observed = self.desk_dom(
            {
                "parent.brief.get": [
                    {"__throw": "the backend did not answer"},
                    {"result": {"brief": {"duration_minutes": 25}}},
                ]
            },
            script="retry",
        )
        steps = {step["step"]: step for step in observed["observed"]["steps"]}
        self.assertEqual(steps["initial"]["state"], "error")
        self.assertEqual(steps["after-retry"]["minutes"], "≈ 25 min")
        self.assertEqual(steps["after-retry"]["state"], "ready")
        self.assertEqual(steps["after-retry"]["retryControls"], 0)
        # The retry issued a second read instead of repainting the same stale state.
        self.assertGreater(steps["after-retry"]["rpc"], steps["initial"]["rpc"])
        self.assertEqual(
            steps["after-retry"]["methods"].count("parent.brief.get"),
            steps["initial"]["methods"].count("parent.brief.get") + 1,
        )

    def test_a_successful_empty_answer_mounted_in_the_desk_still_says_not_recorded(self) -> None:
        observed = self.desk_dom({"parent.brief.get": {"result": {"brief": {"duration_minutes": None}}}})
        step = self.first_step(observed)
        self.assertEqual(step["minutes"], "Session length not recorded")
        self.assertEqual(step["state"], "none")
        self.assertEqual(step["retryControls"], 0)
        self.assertNotIn("could not be read", step["html"])


    def test_path_lists_every_objective_with_its_state_word(self) -> None:
        html = self.render()
        for title in ("Name the three things an engine needs", "Diagnose a no-start",
                      "Replace a fouled plug", "Check compression safely"):
            self.assertIn(title, html)
        for state in ("independent_evidence", "review_due", "introduced", "not_started"):
            self.assertIn(f'data-cb-path-state="{state}"', html)
        # State is text, never colour alone.
        for word in ("Evidence", "Review due", "Started", "Not started"):
            self.assertIn(word, html)

    def test_path_marks_exactly_one_current_step(self) -> None:
        html = self.render()
        self.assertEqual(html.count('data-cb-path-current="true"'), 1)
        self.assertEqual(html.count('aria-current="step"'), 1)

    def test_path_summary_counts_real_states_not_vanity(self) -> None:
        html = self.render()
        # H-145 / ENG-D5: one evidence caption on the path, not the plate caption and the tally.
        self.assertEqual(html.count("with evidence"), 1, html)
        self.assertIn("1 of 4 sections with evidence", html)
        self.assertIn("1 due", html)
        self.assertNotIn("Course evidence ·", html)

    def test_a_single_section_reads_as_one_section(self) -> None:
        # ENG-D4: no "1 of 1 sections".
        outline = {"revision": 0, "objectives": OUTLINE["objectives"][:1], "plan": {"units": []}}
        html = self.render(outline=outline)
        self.assertIn("1 of 1 section with evidence", html)
        self.assertNotIn("1 sections", html)

    def test_path_is_not_a_table(self) -> None:
        html = self.render()
        self.assertNotIn("<table", html)

    # -- sources ----------------------------------------------------------------------------
    def test_sources_are_collapsed_by_default_and_read_nothing(self) -> None:
        html = self.render()
        self.assertIn('data-cb-sources-drawer="closed"', html)
        self.assertNotIn("Shop manual §4 — ignition", html)
        self.assertIn('aria-expanded="false"', html)

    def test_open_sources_name_the_section_and_its_real_rows(self) -> None:
        html = self.render(sourcesOpen=True, sourcesStatus="ready", sources=SOURCES)
        self.assertIn('data-cb-sources-drawer="open"', html)
        self.assertIn("Sources for “Diagnose a no-start”", html)
        self.assertIn("Shop manual §4 — ignition", html)
        self.assertIn("supported", html)
        self.assertIn("stale", html)
        self.assertIn('aria-expanded="true"', html)

    def test_a_failed_source_read_is_shown_with_no_source_rows(self) -> None:
        html = self.render(
            sourcesOpen=True,
            sourcesStatus="error",
            sourcesError={"code": "NOT_IMPLEMENTED", "message": "no handler"},
            sources=None,
        )
        self.assertIn("The sources were not read.", html)
        self.assertIn("Try again", html)
        self.assertNotIn("data-cb-desk-source", html)

    def test_empty_sources_say_the_backend_recorded_none(self) -> None:
        html = self.render(sourcesOpen=True, sourcesStatus="ready", sources=[])
        self.assertIn("No sources are recorded for this section yet.", html)

    # -- course selection -------------------------------------------------------------------
    def test_model_continues_the_due_review_when_the_next_step_says_so(self) -> None:
        desk = self.model()["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000002")
        self.assertEqual(desk["primaryKind"], "resolve_review_due")
        self.assertEqual(desk["primaryLabel"], "Start the review")

    def test_model_labels_a_resume_from_the_backends_next_step(self) -> None:
        row = library_row(
            next_step={"kind": "resume_lesson", "label": "Continue Diagnosing a no-start"},
            evidence_summary={
                "independent": 1,
                "review_due": 0,
                "total_objectives": 4,
                "current_objective_id": "obj_0000000000000002",
            },
        )
        desk = self.model(library=library(row))["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000002")
        self.assertEqual(desk["primaryKind"], "resume_lesson")
        self.assertEqual(desk["primaryLabel"], "Resume the lesson")

    def test_model_falls_back_to_the_rows_own_current_objective(self) -> None:
        row = library_row(next_step={"kind": "start_lesson", "label": "Start Replace a fouled plug"})
        desk = self.model(library=library(row))["desk"]
        self.assertEqual(desk["current"]["objective_id"], "obj_0000000000000003")
        self.assertEqual(desk["primaryLabel"], "Start a fresh run")

    def test_mainline_objective_never_matches_on_title(self) -> None:
        row = library_row(
            next_step={"kind": "start_lesson", "label": "Start"},
            evidence_summary={"independent": 0, "review_due": 0, "total_objectives": 4, "current_objective_id": None},
        )
        mainline = self.model(library=library(row), outline=OUTLINE)["mainline"]
        self.assertEqual(mainline["objective_id"], "obj_0000000000000002")
        self.assertFalse(mainline["independent"])

    def test_mainline_objective_prefers_the_section_open_over_the_course_write(self) -> None:
        desk = self.model()["desk"]
        self.assertEqual(desk["touchedSource"], "section")
        self.assertEqual(desk["lastTouched"], "2026-11-06T17:30:00.000000+00:00")

    def test_last_touched_falls_back_to_the_course_write_and_says_which(self) -> None:
        outline = json.loads(json.dumps(OUTLINE))
        for objective in outline["objectives"]:
            objective["last_opened_at"] = None
        desk = self.model(outline=outline)["desk"]
        self.assertEqual(desk["touchedSource"], "course")
        self.assertEqual(desk["lastTouched"], "2026-11-06T18:00:00.000000+00:00")

    # -- the other states -------------------------------------------------------------------
    def test_no_courses_renders_first_run_not_a_sample_course(self) -> None:
        html = self.render(library=library(), outline=None)
        self.assertIn('data-cb-desk="empty"', html)
        self.assertNotIn("data-cb-continue", html)
        self.assertNotIn("Small-engine maintenance", html)

    def test_loading_renders_a_loader_and_no_course(self) -> None:
        html = self.render(library=None, libraryStatus="loading")
        self.assertIn('data-cb-desk="loading"', html)
        self.assertIn("Reading the trail", html)
        # H-153: the spinner carries a visible line, not only an aria-label.
        self.assertIn("Reading the trail… nothing already saved is lost.</p>", html)
        self.assertNotIn("data-cb-continue", html)

    def test_a_failed_read_keeps_its_code_and_retry(self) -> None:
        html = self.render(
            library=None,
            libraryStatus="error",
            libraryError={"code": "HOST_UNAVAILABLE", "message": "the backend did not answer"},
        )
        self.assertIn('data-cb-desk="error"', html)
        self.assertIn("HOST_UNAVAILABLE", html)
        self.assertIn("Try again", html)
        self.assertNotIn("data-cb-desk=\"empty\"", html)

    def test_a_stale_read_says_it_is_reconnecting(self) -> None:
        html = self.render(stale=True)
        self.assertIn("Reconnecting", html)
        self.assertIn("Retry now", html)

    def test_the_home_names_the_other_classroom_without_a_card_grid(self) -> None:
        second = library_row(
            enrollment_id="enr_ffffffffffffffff",
            course_id="crs_ffffffffffffffff",
            title="Japanese greetings",
            learner_label="Ada",
            next_step={"kind": "start_lesson", "label": "Start あいさつ"},
        )
        html = self.render(library=library(library_row(), second))
        # H-146: the rail is navigation. The other classroom is one text tab with a real
        # `aria-current`, and the all-courses catalog stays behind the Courses destination.
        self.assertIn('data-cb-slot-rail="tabs"', html)
        self.assertIn('data-cb-slot-tab="crs_ffffffffffffffff"', html)
        self.assertIn(">Ada<", html)
        self.assertIn("All courses", html)
        self.assertNotIn("data-cb-all-courses", html)
        self.assertNotIn("data-cb-course-cover", html)

    def test_a_single_classroom_names_itself_without_a_switcher(self) -> None:
        html = self.render()
        self.assertIn('data-cb-slot-rail="single"', html)
        self.assertIn("Showing Small-engine maintenance", html)
        self.assertNotIn("data-cb-slot-tab", html)
        self.assertNotIn("data-cb-classroom-select", html)

    def test_above_four_classrooms_becomes_one_labelled_select(self) -> None:
        rows = [library_row()]
        for index in range(5):
            rows.append(
                library_row(
                    enrollment_id=f"enr_{index:016d}",
                    course_id=f"crs_{index:016d}",
                    title=f"Other course {index}",
                    updated_at=f"2026-10-{index + 1:02d}T10:00:00.000000+00:00",
                )
            )
        html = self.render(library=library(*rows))
        self.assertIn('data-cb-slot-rail="select"', html)
        self.assertIn("data-cb-classroom-select", html)
        self.assertIn("Choose a classroom", html)
        self.assertEqual(html.count("<option"), 6)
        self.assertNotIn("data-cb-slot-tab", html)

    def test_the_wide_desk_is_one_trailhead_not_a_card_grid(self) -> None:
        html = self.render()
        # H-176: one content column, not a rail beside a table.
        self.assertNotIn("minmax(0, 1.2fr)", html)
        self.assertIn('data-cb-trailhead', html)
        self.assertIn('data-cb-course-contour', html)
        self.assertIn('data-cb-trailhead-actions', html)
        # H-94 V2-5: the desk carries one facts line, not a three-cell stat strip.
        self.assertEqual(html.count('data-cb-desk-facts='), 1, html)
        self.assertNotIn('data-cb-desk-stats', html)
        self.assertNotIn('data-cb-desk-stat=', html)
        self.assertNotIn('data-cb-course-stamp', html)
        # H-176: the plate leads, the path is joined directly below it, and the classroom shelf
        # follows the trail instead of sitting above it.
        self.assertLess(html.index('data-cb-continue'), html.index('data-cb-path'))
        self.assertLess(html.index('data-cb-path'), html.index('data-cb-slot-rail-section'))
        self.assertIn('data-cb-classroom-shelf', html)
        self.assertIn('data-cb-shelf-new-course', html)
        self.assertNotIn('data-cb-all-courses', html)

    def test_the_trailhead_falls_back_without_a_pet_and_keeps_continue(self) -> None:
        # The harness SDK exposes no `host.request`, exactly like an older host: the plate must
        # render no companion and still carry the one recorded primary action.
        html = self.render()
        self.assertIn('data-cb-trailhead', html)
        self.assertNotIn('data-cb-companion', html)
        self.assertIn('data-cb-trailhead-actions', html)
        self.assertIn('Start the review', html)
        self.assertIn('See the plan', html)

    def test_a_course_contour_is_stable_and_distinct_per_course(self) -> None:
        first = self.model(courseId='crs_0123456789abcdef', title='Small-engine maintenance')['contour']
        again = self.model(courseId='crs_0123456789abcdef', title='Small-engine maintenance')['contour']
        other = self.model(courseId='crs_fedcba9876543210', title='Register and affection')['contour']
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 3)

    def test_resume_without_a_binding_opens_the_section_instead_of_a_blank_chat(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("reason: 'no-binding'", source)
        self.assertIn("else if (outcome.reason === 'no-binding') openSection(target)", source)
        self.assertNotIn("if (mode === 'resume') {\n      armPendingBind", source)

    # -- the module's shape -----------------------------------------------------------------
    def test_path_titles_wrap_without_colliding_with_the_state_label(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        path = source.split("function CheckpointPath(", 1)[1].split("function SourcesDrawer(", 1)[0]
        self.assertIn("whiteSpace: 'normal'", path)
        self.assertIn("flex: '1 1 8rem'", path)

    def test_the_field_desk_return_is_on_the_courses_list_not_the_library(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        courses = source.split("function CoursesView(", 1)[1].split("\nfunction sourceLabel(", 1)[0]
        library = source.split("function LibraryView(", 1)[1].split("\nfunction planTimingCopy(", 1)[0]
        self.assertIn("Back to the Field Desk", courses)
        self.assertNotIn("Back to the Field Desk", library)
        self.assertNotIn("onShowDesk", library)

    def test_the_desk_arms_the_exact_run_before_opening_a_chat(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        desk = source.split("// ══ M2 — the Field Desk home", 1)[1].split("function CoursesView(", 1)[0]
        self.assertNotIn("MessageTextContent", desk)
        self.assertNotIn("Composer", desk)
        # The desk arms the run first, then delegates the new-chat seam to the named helper. It
        # still never calls host.newChat inline, so the Field Desk itself has no second chat.
        self.assertIn("openArmedLessonChat(", desk)
        self.assertNotIn("host.newChat(", desk)

    def test_the_desk_paints_only_from_the_token_layer(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        desk = source.split("// ══ M2 — the Field Desk home", 1)[1].split("function CoursesView(", 1)[0]
        self.assertNotRegex(desk, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotIn("gradient", desk)
        self.assertNotIn("boxShadow", desk)


if __name__ == "__main__":
    unittest.main()
