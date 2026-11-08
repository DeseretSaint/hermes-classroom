"""H-201: every record in a shared-pack disclosure can be opened from the Courses shelf.

The shelf groups several enrollments of one pack into one cover and lists the rest under a
disclosure. On master that disclosure rendered empty `<li>` elements: the member rows called
`jsxs('li', props, children, key)` — React's jsx-runtime takes children in `props` and the third
argument is the key, so the content array was stored as a key and the row painted nothing. A
learner could see the group but had no control to open the second enrollment.

This module mounts the shipped route in jsdom, navigates to Courses the way a person does, and
reads the real disclosure. It fails on the master wiring (zero controls per member row) and
proves the fix: exactly one openable control per member row, labelled with what it opens, keyboard
reachable with the identity focus ring, and activating it selects that member's enrollment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The shared stub's Button forwards only data-/aria- attributes and onClick. The real host Button
# (apps/desktop/src/components/ui/button.tsx) spreads every prop onto a `<button>`, so a caller's
# style and focus handlers do reach the DOM. This gate reads the ring, so it needs the real shape.
SDK_STUB = SDK_STUB.replace(
    """export const Button = (props) => {
  const attrs = {
    type: 'button',
    disabled: Boolean(props.disabled),
    'data-variant': props.variant || null,
    onClick: props.onClick
  }
  if (props.className) attrs.className = props.className
  if (props.title) attrs.title = props.title
  for (const [name, value] of Object.entries(props)) {
    if ((name.startsWith('data-') || name.startsWith('aria-')) && value !== undefined && !(name in attrs)) {
      attrs[name] = value
    }
  }
  return el('button', attrs, textOf(props))
}""",
    """export const Button = (props) => {
  const attrs = { type: 'button' }
  for (const [name, value] of Object.entries(props)) {
    if (name === 'children' || value === undefined) continue
    attrs[name] = value
  }
  if (props.disabled) attrs.disabled = true
  return el('button', attrs, textOf(props))
}""",
)
assert "name === 'children'" in SDK_STUB.split("export const Button")[1].split("export const RowButton")[0], (
    "the shared SDK stub changed shape; H-201's focus gate needs the forwarding stub"
)


HARNESS = r"""
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
    'library.list', 'course.outline', 'review.queue', 'notebook.list', 'quiz.history',
    'evidence.inspect', 'lesson.page', 'binding.get', 'pack.inspect', 'parent.brief.get',
    'parent.brief.list', 'course.export.read', 'course.create', 'pack.import',
    'syllabus.intake.create', 'parent.brief.create'
  ],
  single_home_host: false
}
const generic = { items: [], entries: [], objectives: [], total: 0 }
const fakeRest = async (path, options) => {
  const body = (options && options.body) || {}
  const method = body.method
  const base = String(path).split('?')[0]
  if (base === '/rpc') calls.push({ method, payload: body.payload || null })
  if (base === '/rpc') {
    const result = Object.prototype.hasOwnProperty.call(responses, method) ? responses[method] : generic
    return { ok: true, contract_version: 6, operation_id: 'test', result }
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
  setTimeout: (fn, ms) => { const h = window.setTimeout(fn, ms); return () => window.clearTimeout(h) },
  clearTimeout: (handle) => window.clearTimeout(handle)
})
const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 60) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()

// jsdom cannot answer `:focus-visible`; answer it the way the live renderer does (a Tab stop
// paints, a pointer press does not). The product's own branch is still the code under test.
let focusVisibleAnswer = true
const realMatches = dom.window.Element.prototype.matches
dom.window.Element.prototype.matches = function (selector) {
  if (selector === ':focus-visible') return focusVisibleAnswer
  return realMatches.call(this, selector)
}

await act(async () => { root.render(route.render()) })
await flush()
const nav = document.querySelector('[data-cb-nav-item="courses"]')
if (!nav) throw new Error('the route rendered no Courses destination')
await act(async () => { nav.click() })
await flush(120)

const disclosure = document.querySelector('[data-cb-shelf-versions]')
// A person opens the disclosure before reaching for a row; closed `<details>` content is not a
// focusable area, so the keyboard probe below needs the same state the learner is in.
if (disclosure && payload.interact) {
  await act(async () => { disclosure.open = true })
  await flush(30)
}
const memberControls = (li) => [
  ...li.querySelectorAll('button, a[href], [role="button"], [tabindex]:not([tabindex="-1"])')
]
const rows = disclosure
  ? [...disclosure.querySelectorAll('li')].map((li) => ({
      text: text(li),
      controls: memberControls(li).map((control) => ({
        tag: control.tagName.toLowerCase(),
        text: text(control),
        aria: control.getAttribute('aria-label'),
        focusHandle: control.getAttribute('data-cb-shelf-member-open'),
        ringState: control.getAttribute('data-cb-focus-ring')
      }))
    }))
  : []

const result = {
  disclosurePresent: Boolean(disclosure),
  summary: disclosure ? text(disclosure.querySelector('summary')) : null,
  rows,
  calls: []
}

if (disclosure && payload.interact) {
  const secondRow = disclosure.querySelectorAll('li')[1]
  const control = secondRow ? memberControls(secondRow)[0] : null
  if (control) {
    await act(async () => {
      control.focus()
      control.dispatchEvent(new dom.window.FocusEvent('focusin', { bubbles: true }))
    })
    result.focusedRing = {
      state: control.getAttribute('data-cb-focus-ring'),
      outline: control.style.outline,
      offset: control.style.outlineOffset
    }
    await act(async () => { control.click() })
    await flush(150)
    result.afterClick = {
      destination: document.querySelector('[data-cb-route]') && document.querySelector('[data-cb-route]').getAttribute('data-cb-destination'),
      title: text(document.querySelector('[data-cb-page-title]')),
      focusedTag: document.activeElement ? document.activeElement.tagName.toLowerCase() : null
    }
  }
  result.calls = calls.map((call) => ({ method: call.method, enrollment: call.payload && call.payload.enrollment_id }))
}

if (payload.noHandler) {
  // The fallback branch: a shelf that was not given an open handler must say so, not render nothing.
  const React2 = (await import('react')).default
  const { renderToStaticMarkup } = await import('react-dom/server')
  const { ShelfDisclosure } = mod
  const group = {
    key: payload.groupKey,
    label: '2 enrollments',
    primary: payload.members[0],
    members: payload.members
  }
  result.fallbackHTML = renderToStaticMarkup(
    React2.createElement(ShelfDisclosure, { group, onOpenLibrary: () => {} })
  )
}

process.stdout.write(JSON.stringify(result))
"""


def _member(**overrides) -> dict:
    row = {
        "enrollment_id": "enr_sample000000000001",
        "course_id": "crs_sample00000000001",
        "title": "Sample course",
        "recipe": "casual",
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "bundled", "pack_id": "japanese-affection-context-l0", "pack_version": "1.0.0"},
        "next_step": {"kind": "resume_lesson", "label": "Continue: Sample"},
        "evidence_summary": {"independent": 1, "review_due": 0, "total_objectives": 3},
        "warning": None,
        "updated_at": "2026-11-01T10:00:00Z",
        "revision": 1,
    }
    row.update(overrides)
    return row


def shared_pack_members() -> list[dict]:
    """The measured pair: the Sample enrollment plus the second pack member H-198 found."""
    return [
        _member(),
        _member(
            enrollment_id="enr_544f0aba033e4fc0a2f50fb61aceda25",
            course_id="crs_secondmember00001",
            title="Affection and context",
            updated_at="2026-10-01T10:00:00Z",
        ),
    ]


class CoursesShelfMemberOpenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render the runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        if not (modules / "jsdom").is_dir():
            raise unittest.SkipTest("jsdom is not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h201-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            (node_modules / name).symlink_to(modules / name, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root
        cls.cache = {}

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_harness(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def measured(self) -> dict:
        if "measured" not in type(self).cache:
            members = shared_pack_members()
            type(self).cache["measured"] = self.run_harness(
                {
                    "width": 1049,
                    "interact": True,
                    "groupKey": "pack:japanese-affection-context-l0",
                    "members": members,
                    "responses": {
                        "library.list": {"items": members, "total": 2, "applied_filter": "all"},
                        "course.outline": {"revision": 1, "objectives": [], "plan": {"units": []}},
                        "review.queue": {"items": [], "total_overdue": 0},
                        "notebook.list": {"entries": []},
                        "quiz.history": {"items": []},
                        "evidence.inspect": {"items": []},
                        "parent.brief.list": {"items": []},
                        "pack.inspect": {},
                        "parent.brief.get": {},
                    },
                }
            )
        return type(self).cache["measured"]

    def test_the_shared_pack_group_lists_one_openable_control_per_member(self) -> None:
        measured = self.measured()
        self.assertTrue(measured["disclosurePresent"], "the two pack enrollments must be one group")
        self.assertEqual(measured["summary"], "2 enrollments")
        self.assertEqual(len(measured["rows"]), 2, "both member rows must render")
        for row in measured["rows"]:
            with self.subTest(row=row["text"]):
                self.assertEqual(len(row["controls"]), 1, f"member row exposed {len(row['controls'])} controls: {row}")
                self.assertEqual(row["controls"][0]["tag"], "button")
                self.assertTrue(row["controls"][0]["focusHandle"], "the control must carry the member's enrollment id")

    def test_the_control_names_the_course_it_opens(self) -> None:
        measured = self.measured()
        labels = [row["controls"][0]["text"] for row in measured["rows"]]
        self.assertIn("Affection and context", labels[1])
        self.assertNotEqual(labels[1].strip(), "Open", "a bare 'Open' does not say what it opens")
        self.assertIn("Sample course", labels[0])

    def test_the_member_control_is_keyboard_reachable_with_the_identity_ring(self) -> None:
        measured = self.measured()
        ring = measured.get("focusedRing") or {}
        self.assertEqual(ring.get("state"), "visible", measured)
        self.assertIn("2px", ring.get("outline") or "")
        self.assertIn("var(--cb-accent)", ring.get("outline") or "")

    def test_activating_a_member_control_selects_that_member_enrollment(self) -> None:
        measured = self.measured()
        outlines = [call for call in measured["calls"] if call["method"] == "course.outline"]
        self.assertTrue(
            any(call["enrollment"] == "enr_544f0aba033e4fc0a2f50fb61aceda25" for call in outlines),
            f"the second member's enrollment was never selected: {outlines}",
        )
        self.assertEqual(measured["afterClick"]["destination"], "courses")

    def test_an_unopenable_member_says_so_and_offers_the_library(self) -> None:
        members = shared_pack_members()
        result = self.run_harness(
            {"noHandler": True, "groupKey": "pack:japanese-affection-context-l0", "members": members}
        )
        html = result["fallbackHTML"]
        self.assertIn("Affection and context", html)
        self.assertIn("can", html.lower())
        self.assertIn("Library", html, "the fallback must offer the working next action")
        self.assertEqual(html.count("<button"), 2, "one working action per unopenable member row")


if __name__ == "__main__":
    unittest.main()
