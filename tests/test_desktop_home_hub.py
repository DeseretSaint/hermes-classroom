"""H-146 — the classroom rail and the selected classroom.

The hub is a read model over rows Coursebook already owns: a `library_item` is a course plus its
active enrollment. These tests prove the shipped projection and the mounted route against the
contract's own row shape: one slot per course, a disclosed duplicate enrollment, parent rows kept
out, Continue re-keyed to the selected enrollment, selection surviving Course Detail, and the
empty/loading/error/archived/parent-only states staying distinct.

They do not prove a live backend currently returns these rows, and they do not prove a human
understood the screen; the card's live frames and walkthrough cover that.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# `profileRoutes` is the host's only door to the profile → connection map. The rail must never
# call it on a slot switch, so the stub counts calls.
COUNTING_SDK_STUB = SDK_STUB.replace(
    "  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],",
    "  profileRoutes: async () => {\n"
    "    globalThis.__CB_PROFILE_ROUTES_CALLS = (globalThis.__CB_PROFILE_ROUTES_CALLS || 0) + 1\n"
    "    return [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }]\n"
    "  },",
)
assert COUNTING_SDK_STUB != SDK_STUB, "the shared SDK stub changed shape; update the counting stub"

MODEL_HARNESS = r"""
import fs from 'node:fs'
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')

const hub = mod.hubSlots(payload.rows)
const desk = mod.buildDeskModel({
  library: { items: payload.rows, total: payload.rows.length, empty_reason: null, applied_filter: 'all' },
  outline: payload.outline || null,
  estimate: null,
  selectedCourseId: payload.selectedCourseId || null,
  outlineState: payload.outline ? 'ready' : 'idle'
})
process.stdout.write(JSON.stringify({
  hub,
  selected: desk.selected,
  row: desk.row,
  current: desk.current,
  primaryKind: desk.primaryKind,
  primaryLabel: desk.primaryLabel,
  sectionLabel: desk.sectionLabel,
  selectionLost: desk.selectionLost
}))
"""

RENDER_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import fs from 'node:fs'
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
const mod = await import('./plugin.js')

const rows = payload.rows
const hub = mod.hubSlots(rows)
const desk = mod.buildDeskModel({
  library: { items: rows, total: payload.total === undefined ? rows.length : payload.total, empty_reason: payload.emptyReason || null, applied_filter: 'all' },
  outline: payload.outline || null,
  estimate: null,
  selectedCourseId: payload.selectedCourseId || null,
  outlineState: payload.outlineState || (payload.outline ? 'ready' : 'idle')
})
const html = renderToStaticMarkup(
  React.createElement('div', { 'data-cb-scope': payload.mode || 'light' },
    React.createElement(mod.FieldDeskHome, {
      desk,
      libraryStatus: payload.libraryStatus || 'ready',
      libraryError: payload.libraryError || null,
      libraryEmptyReason: payload.emptyReason || null,
      stale: Boolean(payload.stale),
      busy: false,
      notice: null,
      online: payload.online === undefined ? true : payload.online,
      onRetry: () => {},
      onCreate: () => {},
      onSyllabus: () => {},
      onPrimary: () => {},
      onOpenSection: () => {},
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
      notes: null,
      implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list'])
    })
  )
)
process.stdout.write(html)
"""

PAGE_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
const runtime = {
  wire_version: 6,
  implemented_methods: [
    'library.list', 'course.outline', 'lesson.page', 'notebook.list', 'review.queue',
    'evidence.inspect', 'pack.inspect', 'parent.brief.get', 'parent.brief.list', 'course.create'
  ],
  single_home_host: false
}
const generic = { items: [], entries: [], objectives: [], total: 0 }

const reply = (method, body) => {
  const entry = responses[method]
  if (entry === undefined) return { ok: true, result: generic }
  if (entry.__refuse) return { ok: false, error: entry.__refuse }
  if (method === 'course.outline') {
    const per = entry.by_enrollment || {}
    const chosen = per[body.payload.enrollment_id] || entry.result || generic
    return { ok: true, result: chosen }
  }
  return { ok: true, result: entry.result === undefined ? entry : entry.result }
}

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = options && options.body
  calls.push({
    path: base,
    method: body && body.method,
    payload: body && body.payload
  })
  if (base === '/rpc') {
    const answer = reply(body.method, body)
    return { ...answer, contract_version: 6, operation_id: 'test' }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') {
    return { ok: true, contract_version: 6, result: { db: { ready: true }, plugin_version: 'test', contract_version: 6 } }
  }
  return { ok: true, result: {} }
}

const contributions = []
mod.default.register({
  rest: fakeRest,
  register: (entry) => contributions.push(entry),
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 80) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const exists = (selector) => Boolean(document.querySelector(selector))

const snapshot = () => ({
  home: (document.querySelector('[data-cb-home]') || {}).getAttribute
    ? document.querySelector('[data-cb-home]').getAttribute('data-cb-home')
    : null,
  homeShelf: (document.querySelector('[data-cb-home-shelf]') || {}).getAttribute
    ? document.querySelector('[data-cb-home-shelf]').getAttribute('data-cb-home-shelf')
    : null,
  homeError: text(document.querySelector('[data-cb-home-shelf-state="error"]')),
  deskState: (document.querySelector('[data-cb-desk]') || {}).getAttribute
    ? document.querySelector('[data-cb-desk]').getAttribute('data-cb-desk')
    : null,
  rail: exists('[data-cb-slot-rail]') ? document.querySelector('[data-cb-slot-rail]').getAttribute('data-cb-slot-rail') : null,
  tabs: [...document.querySelectorAll('[data-cb-slot-tab]')].map((node) => ({
    courseId: node.getAttribute('data-cb-slot-tab'),
    name: text(node),
    current: node.getAttribute('aria-current'),
    state: node.getAttribute('data-cb-slot-state'),
    minHeight: node.style.minHeight
  })),
  currentLine: text(document.querySelector('[data-cb-slot-current]')),
  disclosure: text(document.querySelector('[data-cb-slot-disclosure]')),
  selectOptions: [...document.querySelectorAll('[data-cb-classroom-select] option')].map((node) => ({
    value: node.value,
    name: text(node)
  })),
  continueCourse: text(document.querySelector('[data-cb-desk-course]')),
  continueSection: text(document.querySelector('[data-cb-continue-section]')),
  continuePrimary: (() => {
    const node = document.querySelector('[data-cb-continue] button[data-variant="default"]')
    return node ? { text: text(node), disabled: node.disabled } : null
  })(),
  pathState: document.querySelector('[data-cb-path]')
    ? document.querySelector('[data-cb-path]').getAttribute('data-cb-path')
    : null,
  pathText: text(document.querySelector('[data-cb-path]')),
  pathNodes: [...document.querySelectorAll('[data-cb-path-item]')].map((node) => ({
    id: node.getAttribute('data-cb-path-item'),
    state: node.getAttribute('data-cb-path-state'),
    current: node.getAttribute('data-cb-path-current')
  })),
  selectionLost: text(document.querySelector('[data-cb-desk-selection-lost]')),
  offline: text(document.querySelector('[data-cb-desk-offline]')),
  error: text(document.querySelector('[data-cb-desk="error"]')),
  emptyTitle: document.querySelector('[data-cb-desk] .empty-title') ? text(document.querySelector('[data-cb-desk] .empty-title')) : null,
  whole: text(document.getElementById('root')),
  outlineReads: calls.filter((call) => call.method === 'course.outline').map((call) => call.payload && call.payload.enrollment_id),
  libraryReads: calls.filter((call) => call.method === 'library.list').length,
  profileRouteReads: globalThis.__CB_PROFILE_ROUTES_CALLS || 0,
  runtimeReads: calls.filter((call) => call.path === '/runtime').length
})

await act(async () => { root.render(route.render()) })
await flush(140)

// GM-002: the desk is the selected course's home, one step in from the library Home. A profile
// with no learner course has no card to open and stays on the library surface.
const opener = document.querySelector('[data-cb-home-card] button')
if (opener) {
  await act(async () => { opener.click() })
  await flush(220)
}

const steps = []
steps.push({ step: 'initial', ...snapshot() })

if (payload.script === 'switch') {
  const target = document.querySelector('[data-cb-slot-tab="' + payload.target + '"]')
  if (!target) throw new Error('no classroom tab ' + payload.target)
  await act(async () => { target.click() })
  await flush(140)
  steps.push({ step: 'after-switch', ...snapshot() })

  const pathItem = document.querySelector('[data-cb-path-item]')
  if (!pathItem) throw new Error('the selected classroom rendered no path row')
  await act(async () => { pathItem.closest('button').click() })
  await flush(160)
  const back = document.querySelector('[data-cb-course-back]') || [...document.querySelectorAll('button')].find(
    (node) => text(node) === 'Back to the section index'
  )
  if (!back) throw new Error('course detail rendered no back control')
  await act(async () => { back.click() })
  await flush(320)
  steps.push({ step: 'after-back', ...snapshot() })
}

if (payload.script === 'select-option') {
  const select = document.querySelector('[data-cb-classroom-select]')
  if (!select) throw new Error('no classroom select above four')
  await act(async () => {
    select.value = payload.target
    select.dispatchEvent(new window.Event('change', { bubbles: true }))
  })
  await flush(140)
  steps.push({ step: 'after-select', ...snapshot() })
}

// H-146a: the ring is a style the control paints, so the contract is read off the element itself.
const focusInfo = (node) => ({
  courseId: node.getAttribute('data-cb-slot-tab'),
  active: document.activeElement === node,
  outline: node.style.outline,
  outlineOffset: node.style.outlineOffset,
  ring: node.getAttribute('data-cb-focus-ring')
})

if (payload.script === 'focus') {
  const target = document.querySelector('[data-cb-slot-tab="' + payload.target + '"]')
  if (!target) throw new Error('no classroom tab ' + payload.target)
  steps.push({ step: 'before-focus', focus: focusInfo(target) })
  // jsdom moves activeElement on focus() but React listens for focusin on the root, so both the
  // real event and its bubbling companion are dispatched the way a browser would.
  await act(async () => {
    // GM-002: the walkthrough clicks a library card before it reaches this tab, and jsdom reads
    // that pointer interaction as the modality — a plain focus() then reports :focus-visible as
    // false. A Tab keydown restores keyboard modality the way a real keyboard user arrives.
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    target.focus()
    target.dispatchEvent(new window.FocusEvent('focusin', { bubbles: true }))
  })
  await flush(60)
  steps.push({ step: 'focused', focus: focusInfo(target) })
  await act(async () => {
    target.blur()
    target.dispatchEvent(new window.FocusEvent('focusout', { bubbles: true }))
  })
  await flush(60)
  steps.push({ step: 'blurred', focus: focusInfo(target) })
}

process.stdout.write(JSON.stringify({ steps, profileRouteReads: globalThis.__CB_PROFILE_ROUTES_CALLS || 0 }))
"""


def row(**overrides) -> dict:
    base = {
        "enrollment_id": "enr_aaaaaaaaaaaaaaaa",
        "course_id": "crs_aaaaaaaaaaaaaaaa",
        "title": "Small-engine maintenance",
        "subtitle": None,
        "recipe": "committed",
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resolve_review_due", "label": "Review 1 objective(s)"},
        "evidence_summary": {
            "independent": 1,
            "review_due": 1,
            "total_objectives": 2,
            "current_objective_id": "obj_aaaaaaaaaaaaaa02",
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 7,
    }
    base.update(overrides)
    return base


def second_row(**overrides) -> dict:
    base = row(
        enrollment_id="enr_bbbbbbbbbbbbbbbb",
        course_id="crs_bbbbbbbbbbbbbbbb",
        title="Japanese greetings",
        learner_label="Ada",
        next_step={"kind": "start_lesson", "label": "Start あいさつ"},
        evidence_summary={
            "independent": 0,
            "review_due": 0,
            "total_objectives": 2,
            "current_objective_id": "obj_bbbbbbbbbbbbbb01",
        },
        updated_at="2026-11-05T10:00:00.000000+00:00",
    )
    base.update(overrides)
    return base


def library(*rows: dict, empty_reason=None, total=None) -> dict:
    return {
        "items": list(rows),
        "next_cursor": None,
        "total": len(rows) if total is None else total,
        "empty_reason": empty_reason,
        "applied_filter": "all",
    }


def outline(enrollment_id: str, *, title: str, current: str, state: str = "introduced") -> dict:
    other = current[:-1] + ("1" if current.endswith("2") else "2")
    return {
        "enrollment_id": enrollment_id,
        "revision": 0,
        "plan": {"plan_id": "pln_x", "version": 1, "state": "approved", "plan_hash": "sha256:" + "b" * 64},
        "objectives": [
            {
                "objective_id": other,
                "ordinal": 1,
                "title": f"{title}: first step",
                "state": "independent_evidence",
                "check_state": "closed",
                "attempt_count": 1,
                "independent": True,
                "last_opened_at": "2026-11-05T09:00:00.000000+00:00",
            },
            {
                "objective_id": current,
                "ordinal": 2,
                "title": f"{title}: next step",
                "state": state,
                "check_state": "open",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
        ],
    }


OUTLINE_A = outline("enr_aaaaaaaaaaaaaaaa", title="Small-engine", current="obj_aaaaaaaaaaaaaa02", state="review_due")
OUTLINE_B = outline("enr_bbbbbbbbbbbbbbbb", title="Greetings", current="obj_bbbbbbbbbbbbbb01", state="introduced")


class Harness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = _desktop_node_modules()
        if cls.modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h146-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "model.mjs").write_text(MODEL_HARNESS, encoding="utf-8")
        (cls.root / "render.mjs").write_text(RENDER_HARNESS, encoding="utf-8")
        (cls.root / "page.mjs").write_text(PAGE_HARNESS, encoding="utf-8")
        # Private node_modules: the SDK stub must never be written through a
        # symlink into the host's shared install (H-208 cross-suite flake).
        stage_desktop_node_modules(cls.root)
        write_sdk_stub(cls.root, COUNTING_SDK_STUB)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_script(self, name: str, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        env = dict(os.environ)
        env["CB_TEST_WIDTH"] = str(payload.get("width", 1049))
        result = subprocess.run(
            ["node", str(self.root / name), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return result.stdout

    def model(self, rows: list[dict], **overrides) -> dict:
        payload = {"rows": rows}
        payload.update(overrides)
        return json.loads(self.run_script("model.mjs", payload))

    def render(self, rows: list[dict], **overrides) -> str:
        payload = {"rows": rows}
        payload.update(overrides)
        return self.run_script("render.mjs", payload)

    def page(self, responses: dict, script: str = "none", **overrides) -> dict:
        payload = {"responses": responses, "script": script}
        payload.update(overrides)
        return json.loads(self.run_script("page.mjs", payload))

    def default_responses(self, rows: list[dict]) -> dict:
        return {
            "library.list": {"result": library(*rows)},
            "course.outline": {"by_enrollment": {"enr_aaaaaaaaaaaaaaaa": OUTLINE_A, "enr_bbbbbbbbbbbbbbbb": OUTLINE_B}},
            "notebook.list": {"result": {"items": [], "next_cursor": None, "total": 0}},
        }


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HubProjectionTest(Harness):
    def test_one_slot_per_course_and_duplicate_enrollments_are_disclosed_not_split(self) -> None:
        newer = row(
            enrollment_id="enr_aaaaaaaaaaaaaa99",
            updated_at="2026-11-07T09:00:00.000000+00:00",
            learner_label="Ada",
        )
        result = self.model([row(), newer, second_row()])["hub"]
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["all"]), 2)
        courses = [slot["course_id"] for slot in result["all"]]
        self.assertEqual(courses.count("crs_aaaaaaaaaaaaaaaa"), 1)
        dup = next(slot for slot in result["all"] if slot["course_id"] == "crs_aaaaaaaaaaaaaaaa")
        self.assertEqual(dup["recordCount"], 2)
        # The newest enrollment is the one the hub continues, and it is the named one.
        self.assertEqual(dup["enrollment_id"], "enr_aaaaaaaaaaaaaa99")
        self.assertEqual(dup["name"], "Ada")
        html = self.render([row(), newer])
        self.assertIn("This course has 2 progress records; showing the most recent.", html)
        self.assertIn('data-cb-slot-disclosure="2"', html)

    def test_slot_name_uses_learner_label_then_course_title_and_never_invents_one(self) -> None:
        labelled = self.model([row(learner_label="Ada")])
        self.assertEqual(labelled["hub"]["all"][0]["name"], "Ada")
        unlabelled = self.model([row(learner_label=None, title="Small-engine maintenance")])
        self.assertEqual(unlabelled["hub"]["all"][0]["name"], "Small-engine maintenance")
        blank = self.model([row(learner_label="   ", title="Japanese greetings")])
        self.assertEqual(blank["hub"]["all"][0]["name"], "Japanese greetings")
        for result in (labelled, unlabelled, blank):
            names = [slot["name"] for slot in result["hub"]["all"]]
            self.assertNotIn("Learner 1", names)

    def test_parent_recipe_rows_never_appear_as_learner_slots(self) -> None:
        parent = row(
            enrollment_id="enr_pppppppppppppppp",
            course_id="crs_pppppppppppppppp",
            title="Parent-led lesson",
            recipe="parent",
        )
        result = self.model([parent, row(), second_row()])["hub"]
        self.assertEqual(result["total"], 2)
        self.assertNotIn("crs_pppppppppppppppp", [slot["course_id"] for slot in result["all"]])
        html = self.render([parent, row(), second_row()])
        self.assertNotIn("Parent-led lesson", html)
        self.assertIn("Small-engine maintenance", html)

    def test_continue_reads_the_selected_slots_next_step(self) -> None:
        result = self.model(
            [row(), second_row()],
            selectedCourseId="crs_bbbbbbbbbbbbbbbb",
            outline=OUTLINE_B,
        )
        self.assertEqual(result["row"]["course_id"], "crs_bbbbbbbbbbbbbbbb")
        self.assertEqual(result["primaryKind"], "start_lesson")
        self.assertEqual(result["primaryLabel"], "Start a fresh run")
        self.assertEqual(result["current"]["objective_id"], "obj_bbbbbbbbbbbbbb01")
        self.assertEqual(result["sectionLabel"], "Section 2 of 2")
        self.assertFalse(result["selectionLost"])

    def test_slot_count_uses_deduped_rows_and_total_only_as_truncation(self) -> None:
        rows = [row()]
        rows.append(row(enrollment_id="enr_aaaaaaaaaaaaaa98", updated_at="2026-11-04T10:00:00.000000+00:00"))
        for index in range(5):
            rows.append(
                row(
                    enrollment_id=f"enr_{index:016d}",
                    course_id=f"crs_{index:016d}",
                    title=f"Classroom {index}",
                    updated_at=f"2026-10-{index + 1:02d}T10:00:00.000000+00:00",
                )
            )
        result = self.model(rows)["hub"]
        self.assertEqual(result["rowTotal"], 7)
        self.assertEqual(result["total"], 6)
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(result["hidden"], 2)
        html = self.render(rows, total=120)
        self.assertIn('data-cb-slot-rail="select"', html)
        self.assertEqual(html.count("<option"), 6)

    def test_selected_row_still_works_when_the_outline_read_failed(self) -> None:
        result = self.model([row()], selectedCourseId="crs_aaaaaaaaaaaaaaaa", outline=None)
        # With no outline answer the model keeps only the row's own current-objective pointer:
        # an id and no title/ordinal, so nothing is invented.
        self.assertEqual(result["current"]["objective_id"], "obj_aaaaaaaaaaaaaa02")
        self.assertIsNone(result["current"]["title"])
        self.assertIsNone(result["sectionLabel"])
        html = self.render([row()], outline=None, outlineStatus="error", outlineError={"code": "HOST_UNAVAILABLE", "message": "the backend did not answer"})
        self.assertIn('data-cb-path="error"', html)
        self.assertIn("HOST_UNAVAILABLE", html)
        self.assertIn("Continue still uses the next step this course recorded.", html)
        # Continue still has a live primary from the row's recorded next step.
        self.assertIn("Start the review", html)

    def test_path_nodes_read_only_recorded_states_and_invent_no_gate(self) -> None:
        html = self.render([row()], outline=OUTLINE_A, selectedCourseId="crs_aaaaaaaaaaaaaaaa")
        self.assertIn('data-cb-path-state="review_due"', html)
        self.assertIn('data-cb-path-state="independent_evidence"', html)
        # H-148 owns the checkpoint marker, so "Checkpoint N" is its label now; this card must
        # still not invent a lock or a percentage.
        for forbidden in ("Locked", "locked", "XP", "% complete"):
            self.assertNotIn(forbidden, html)

    def test_hub_paints_only_token_layer_values(self) -> None:
        html = self.render([row(), second_row()])
        self.assertIn("var(--cb-", html)
        self.assertNotRegex(html, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(html, r"\brgba?\(")
        self.assertNotRegex(html, r"\bhsla?\(")


@unittest.skipIf(shutil.which("node") is None, "node is required to run the runtime desktop plugin")
class HubRouteTest(Harness):
    def test_library_failure_is_not_an_empty_hub(self) -> None:
        responses = self.default_responses([row()])
        responses["library.list"] = {"__refuse": {"code": "HOST_UNAVAILABLE", "category": "transport", "message": "the backend did not answer", "retryable": True}}
        steps = self.page(responses)["steps"]
        first = steps[0]
        self.assertEqual(first["homeShelf"], "error")
        self.assertIn("HOST_UNAVAILABLE", first["homeError"])
        self.assertIn("This is a failed read, not an empty library", first["homeError"])
        self.assertIsNone(first["deskState"])

    def test_all_archived_is_its_own_state_not_first_run(self) -> None:
        steps = self.page({"library.list": {"result": library(empty_reason="all_archived", total=0)}})["steps"]
        first = steps[0]
        self.assertEqual(first["homeShelf"], "empty")
        self.assertIn("Every course here is archived.", first["whole"])
        self.assertIn("Unarchive one in Courses", first["whole"])
        self.assertNotIn("Start with a goal", first["whole"])

    def test_a_parent_only_profile_names_parent_studio(self) -> None:
        parent = row(
            enrollment_id="enr_pppppppppppppppp",
            course_id="crs_pppppppppppppppp",
            title="Parent-led lesson",
            recipe="parent",
        )
        steps = self.page({"library.list": {"result": library(parent)}})["steps"]
        first = steps[0]
        self.assertEqual(first["homeShelf"], "parent-only")
        self.assertIn("Parent Studio holds your lesson plans.", first["whole"])
        self.assertIn("Open Parent Studio", first["whole"])
        self.assertIsNone(first["deskState"])

    def test_a_genuinely_empty_profile_renders_the_start_plate(self) -> None:
        steps = self.page({"library.list": {"result": library(empty_reason="no_courses", total=0)}})["steps"]
        first = steps[0]
        self.assertEqual(first["home"], "empty")
        self.assertEqual(first["homeShelf"], "empty")
        self.assertIn("No courses yet.", first["whole"])
        self.assertIn("Start a new course", first["whole"])
        self.assertNotIn("Parent Studio holds your lesson plans.", first["whole"])
        self.assertNotIn("Every classroom here is archived.", first["whole"])

    def test_switching_a_slot_rekeys_continue_and_the_outline_read(self) -> None:
        result = self.page(self.default_responses([row(), second_row()]), script="switch", target="crs_bbbbbbbbbbbbbbbb")
        initial, switched = result["steps"][0], result["steps"][1]
        self.assertEqual(initial["rail"], "tabs")
        self.assertEqual(len(initial["tabs"]), 2)
        chosen = next(tab for tab in switched["tabs"] if tab["courseId"] == "crs_bbbbbbbbbbbbbbbb")
        self.assertEqual(chosen["current"], "true")
        self.assertEqual(chosen["state"], "current")
        self.assertEqual(switched["continueCourse"], "Japanese greetings")
        self.assertEqual(switched["continueSection"], "Greetings: next step")
        self.assertEqual(switched["continuePrimary"]["text"], "Start a fresh run")
        self.assertEqual(switched["outlineReads"][-1], "enr_bbbbbbbbbbbbbbbb")
        self.assertIn("Showing Ada", switched["currentLine"])

    def test_selection_survives_course_detail_and_back(self) -> None:
        result = self.page(self.default_responses([row(), second_row()]), script="switch", target="crs_bbbbbbbbbbbbbbbb")
        after_back = result["steps"][2]
        chosen = next(tab for tab in after_back["tabs"] if tab["courseId"] == "crs_bbbbbbbbbbbbbbbb")
        self.assertEqual(chosen["current"], "true")
        self.assertEqual(after_back["continueCourse"], "Japanese greetings")
        self.assertEqual(after_back["outlineReads"][-1], "enr_bbbbbbbbbbbbbbbb")

    def test_slot_switch_never_changes_the_profile_scope(self) -> None:
        result = self.page(self.default_responses([row(), second_row()]), script="switch", target="crs_bbbbbbbbbbbbbbbb")
        initial, switched = result["steps"][0], result["steps"][1]
        self.assertEqual(initial["profileRouteReads"], switched["profileRouteReads"])
        self.assertEqual(initial["runtimeReads"], switched["runtimeReads"])
        source = PLUGIN_JS.read_text(encoding="utf-8")
        rail = source.split("function SlotRail(", 1)[1].split("/* ── H-176", 1)[0]
        for forbidden in ("profileRoutes", "?profile=", "currentScope", "host.navigate"):
            self.assertNotIn(forbidden, rail)

    def test_selected_slot_missing_falls_back_and_says_so(self) -> None:
        html = self.render([row()], selectedCourseId="crs_deleted000000000")
        self.assertIn("That classroom is no longer on this profile. Showing Small-engine maintenance.", html)
        self.assertIn("Small-engine maintenance", html)

    def test_above_four_slots_is_one_labelled_select(self) -> None:
        rows = [row()]
        for index in range(5):
            rows.append(
                row(
                    enrollment_id=f"enr_{index:016d}",
                    course_id=f"crs_{index:016d}",
                    title=f"Classroom {index}",
                    updated_at=f"2026-10-{index + 1:02d}T10:00:00.000000+00:00",
                )
            )
        result = self.page(self.default_responses(rows), script="select-option", target="crs_0000000000000004")
        initial, switched = result["steps"][0], result["steps"][1]
        self.assertEqual(initial["rail"], "select")
        self.assertEqual(len(initial["selectOptions"]), 6)
        self.assertEqual(len(initial["tabs"]), 0)
        self.assertEqual(switched["continueCourse"], "Classroom 4")

    def test_narrow_hub_has_no_fixed_overflow_and_44px_targets(self) -> None:
        html = self.render([row(), second_row()], width=460)
        self.assertIn('data-cb-desk-layout="stacked"', html)
        self.assertIn("min-height:44px", html)
        self.assertIn("flex-wrap:wrap", html)
        self.assertNotRegex(html, r"min-width:\s*[3-9][0-9]{2}px")
        self.assertIn("data-cb-slot-tab", html)

    def test_focused_classroom_tab_paints_the_identity_focus_ring(self) -> None:
        """H-146a: the tab keeps a visible ring while it holds focus, in the identity's own terms.

        The host's reset clears the user agent ring on a bare button, so the plugin paints its own
        inline outline; this asserts the property the control actually sets, and that it is not
        `none` while focused and is `none` again once focus leaves.
        """
        result = self.page(
            self.default_responses([row(), second_row()]), script="focus", target="crs_bbbbbbbbbbbbbbbb"
        )
        steps = {step["step"]: step["focus"] for step in result["steps"] if "focus" in step}
        before, focused, blurred = steps["before-focus"], steps["focused"], steps["blurred"]
        self.assertEqual(before["courseId"], "crs_bbbbbbbbbbbbbbbb")
        self.assertFalse(before["active"])
        self.assertEqual(before["outline"], "none")
        self.assertEqual(before["ring"], "none")
        self.assertTrue(focused["active"])
        self.assertNotEqual(focused["outline"], "none")
        self.assertEqual(focused["outline"], "2px solid var(--cb-accent)")
        self.assertEqual(focused["outlineOffset"], "2px")
        self.assertEqual(focused["ring"], "visible")
        self.assertEqual(blurred["outline"], "none")
        self.assertEqual(blurred["ring"], "none")
        # The ring is a token, never a raw colour, and it is not the browser default either.
        self.assertNotRegex(focused["outline"], r"#[0-9a-fA-F]{3,8}\b|rgba?\(")

    def test_offline_and_stale_keep_the_classroom_and_say_it_is_paused(self) -> None:
        html = self.render([row()], online=False, stale=True)
        self.assertIn("Showing Small-engine maintenance", html)
        self.assertIn("the desk is paused", html)
        self.assertIn("starting a lesson is paused", html)
        # The selected row is still named; a pause is not an empty hub.
        self.assertIn("Start the review", html)


if __name__ == "__main__":
    unittest.main()
