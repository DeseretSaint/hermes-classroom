"""W2-4 — the tutor is beside the check, and the hint is a hint (CREATE-EXPERIENCE item 35).

The classroom's "Ask the tutor" door was conditional on a handler the shipped route never passed,
so the door was absent; "I used a hint" recorded a `hint_request` and answered nothing. These
tests mount the *registered route* — the same ``CoursebookPage`` the host renders — in jsdom, walk
to a section the way a person does, and mount the contributed tutor rail beside it. From that live
tree:

* the tutor door renders without any injected handler, and pressing it reveals the rail's pane and
  puts the caret in the tutor composer;
* the check's own "Ask for a hint" writes `lesson.assist` and the rail then asks the one hint
  question and renders the tutor's answer — a real hint, not a recorded one;
* the post-hoc "I already used a hint" disclosure still records the learner's statement and never
  asks the tutor anything.

What this does NOT prove: a live provider answer, or pixels against the concept frames; the card's
rig pass carries those.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import stage_desktop_node_modules, write_sdk_stub
from tests.test_desktop_lesson_views import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The shared stub's host has no pane door. The real host exposes `revealPane`, and this gate reads
# the pane id the classroom asks for, so the stub records it instead of silently dropping it.
SDK_STUB_WITH_PANE = SDK_STUB.replace(
    "  navigate: () => {},",
    "  navigate: () => {},\n"
    "  revealPane: (id) => { (globalThis.__CB_REVEALED_PANES = globalThis.__CB_REVEALED_PANES || []).push(id) },",
).replace(
    "export const Textarea = () => null",
    "export const Textarea = (props) =>\n"
    "  el('textarea', { id: props.id || null, rows: props.rows || null, 'data-cb-textarea': 'true' }, props.value || null)",
)
assert "revealPane" in SDK_STUB_WITH_PANE and "data-cb-textarea" in SDK_STUB_WITH_PANE, (
    "the shared SDK stub changed shape; update the pane/caret stub"
)

TUTOR_HINT_QUESTION = "Give me a hint for this check. Do not give the answer."
HINT_ANSWER = "Look at who is speaking: the second line asks someone out, not just describes a feeling."

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div><div id="tutor"></div><div id="answer"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.MouseEvent = dom.window.MouseEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
const runtime = {
  wire_version: 6,
  implemented_methods: payload.implemented || [],
  single_home_host: false
}
const generic = { items: [], entries: [], objectives: [], total: 0 }
let historyTurns = []
const reply = (method, body) => {
  // The backend stores the ask: the thread read that follows must carry it, or the pane would
  // erase the optimistic turn on its own reload (that behaviour is not under test here).
  if (method === 'tutor.ask') {
    const asked = body && body.payload ? body.payload.question : ''
    historyTurns = [
      { id: 'ttr_learner01', ordinal: 1, role: 'learner', text: asked, citations: [] },
      { id: 'ttr_tutor01', ordinal: 2, role: 'tutor', text: payload.hintAnswer, citations: [] }
    ]
    return { ok: true, result: { state: 'breadcrumb', turn: historyTurns[1] } }
  }
  if (method === 'tutor.history') return { ok: true, result: { turns: historyTurns, revision: 8 } }
  const entry = responses[method]
  if (entry === undefined) return { ok: true, result: generic }
  return { ok: true, result: entry }
}
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = options && options.body
  const method = body && body.method
  if (base === '/rpc') calls.push({ method, payload: body && body.payload })
  if (base === '/rpc') {
    const answer = reply(method, body)
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
  setTimeout: (fn, ms) => { const h = window.setTimeout(fn, ms); return () => window.clearTimeout(h) },
  clearTimeout: (handle) => window.clearTimeout(handle)
})
const route = contributions.find((entry) => entry.area === 'routes')
if (!route) throw new Error('the plugin registered no route')

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const tutorRoot = createRoot(document.getElementById('tutor'))
const answerRoot = createRoot(document.getElementById('answer'))
const flush = async (ms = 80) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (selector, wanted) => [...document.querySelectorAll(selector)].find((node) => text(node) === wanted) || null
const click = async (node, label) => {
  if (!node) throw new Error('no control ' + label)
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush(160)
}

await act(async () => { root.render(route.render()) })
await flush(160)

const opener = document.querySelector('[data-cb-home-card] button')
if (opener) await click(opener, 'home card')
const pathItem = document.querySelector('[data-cb-path-item]')
if (!pathItem) throw new Error('the desk rendered no path row')
await act(async () => { pathItem.closest('button').click() })
await flush(220)

const classroom = document.querySelector('[data-cb-classroom]')
const tutorPill = document.querySelector('[data-cb-aside-tutor]')
const hintControl = document.querySelector('[data-cb3-hint]')
const hintControlText = hintControl ? text(hintControl) : null

// The rail is a contributed pane: mount the shipped pane component with the binding the host
// resolves for this lesson run, beside the route in a second root of the same module instance.
await act(async () => { tutorRoot.render(React.createElement(mod.TutorRailPane, { binding: payload.binding })) })
await flush(220)

const revealBefore = (globalThis.__CB_REVEALED_PANES || []).slice()
let focusAfterTutor = null
if (tutorPill) {
  await click(tutorPill, 'Ask the tutor')
  focusAfterTutor = document.activeElement ? document.activeElement.id || document.activeElement.tagName.toLowerCase() : null
}
const revealed = (globalThis.__CB_REVEALED_PANES || []).slice(revealBefore.length)

const assistBefore = calls.filter((call) => call.method === 'lesson.assist').length
const askBefore = calls.filter((call) => call.method === 'tutor.ask').length
if (hintControl) await click(hintControl, 'Ask for a hint')
const assistCalls = calls.filter((call) => call.method === 'lesson.assist')
const askCalls = calls.filter((call) => call.method === 'tutor.ask')
const hintStatus = document.querySelector('[data-cb3-hint="recorded"]')
const tutorBody = text(document.getElementById('tutor'))

// The post-hoc disclosure is the v2 answer surface's control; mount it beside the classroom with
// the same open check so its write path is the shipped one, not a helper.
await act(async () => {
  answerRoot.render(React.createElement(mod.AttemptControls, {
    enrollmentId: payload.row.enrollment_id,
    objectiveId: payload.objectiveId,
    check: payload.check,
    revision: 7,
    implemented: new Set(payload.implemented || []),
    bindingState: 'active',
    stimulusStatus: 'ready',
    onRetryStimulus: () => {},
    onCommitted: () => {}
  }))
})
await flush(160)
const askButtonInAnswer = document.querySelector('[data-cb-ask-hint]')
const disclosure = document.querySelector('[data-cb-assist-disclosure="hint_request"]')
const disclosureText = disclosure ? text(disclosure) : null
const assistBeforeDisclosure = calls.filter((call) => call.method === 'lesson.assist').length
const askBeforeDisclosure = calls.filter((call) => call.method === 'tutor.ask').length
if (disclosure) await click(disclosure, 'I already used a hint')
const assistAfterDisclosure = calls.filter((call) => call.method === 'lesson.assist').length
const askAfterDisclosure = calls.filter((call) => call.method === 'tutor.ask').length
const disclosureFlag = document.querySelector('[data-cb-assist-used="hint_request"]')

process.stdout.write(JSON.stringify({
  classroom: Boolean(classroom),
  tutorPill: tutorPill ? text(tutorPill) : null,
  hintControl: hintControlText,
  revealed,
  focusAfterTutor,
  assistDeltaForHint: assistCalls.length - assistBefore,
  askDeltaForHint: askCalls.length - askBefore,
  assistKind: assistCalls.length ? assistCalls[assistCalls.length - 1].payload && assistCalls[assistCalls.length - 1].payload.kind : null,
  askedQuestion: askCalls.length ? askCalls[askCalls.length - 1].payload && askCalls[askCalls.length - 1].payload.question : null,
  hintStatus: hintStatus ? text(hintStatus) : null,
  tutorHasHint: tutorBody.includes(payload.hintAnswer),
  tutorBody,
  askButtonInAnswer: askButtonInAnswer ? text(askButtonInAnswer) : null,
  disclosure: disclosureText,
  assistDeltaForDisclosure: assistAfterDisclosure - assistBeforeDisclosure,
  askDeltaForDisclosure: askAfterDisclosure - askBeforeDisclosure,
  disclosureFlag: disclosureFlag ? text(disclosureFlag) : null
}))
"""


def described() -> dict:
    row = {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Affection and register",
        "subtitle": None,
        "recipe": "committed",
        "learner_label": None,
        "enrollment_status": "active",
        "course_status": "active",
        "provenance": {"source": "authored", "pack_id": None, "pack_version": None},
        "next_step": {"kind": "resume_lesson", "label": "Continue: Register and affection"},
        "evidence_summary": {
            "independent": 0,
            "review_due": 0,
            "total_objectives": 2,
            "current_objective_id": "obj_0123456789abcdef",
        },
        "warning": None,
        "updated_at": "2026-11-06T18:00:00.000000+00:00",
        "revision": 7,
    }
    objectives = [
        {
            "objective_id": "obj_0123456789abcdef",
            "title": "Register and affection",
            "ordinal": 1,
            "state": "introduced",
            "evidence_target": "discrimination",
            "last_opened_at": None,
            "check_state": "open",
            "attempt_count": 0,
            "independent": False,
        },
        {
            "objective_id": "obj_0123456789abcdea",
            "title": "Ask in the polite register",
            "ordinal": 2,
            "state": "not_started",
            "evidence_target": "production",
            "last_opened_at": None,
            "check_state": "none",
            "attempt_count": 0,
            "independent": False,
        },
    ]
    check = {
        "check_id": "chk_0123456789abcdef",
        "objective_id": "obj_0123456789abcdef",
        "check_version": 1,
        "evidence_target": "discrimination",
        "state": "open",
        "audit_state": "passed",
        "attempt_count": 0,
        "revision": 7,
        "stimulus": {
            "prompt": "Which line is a confession rather than a description?",
            "format": "selection",
            "choices": ["A: うん、好きだよ。", "B: 好きです。付き合ってください。"],
            "items": [],
        },
    }
    page = {
        "enrollment_id": "enr_0123456789abcdef",
        "course": {"course_id": "crs_0123456789abcdef", "title": "Affection and register"},
        "section": {
            "objective_id": "obj_0123456789abcdef",
            "title": "Register and affection",
            "ordinal": 1,
            "state": "introduced",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {
            "lesson_run_id": "run_0123456789abcdef",
            "binding_id": None,
            "binding_status": "detached",
            "session_state": "stored_only",
        },
        "segments": [{"segment_id": "seg_1", "ordinal": 1, "kind": "teaching", "text": "Two ways of saying it."}],
        "document": None,
        "sources": [],
        "artifacts": [],
        "checks": [
            {
                "check_id": "chk_0123456789abcdef",
                "version": 1,
                "evidence_target": "discrimination",
                "state": "open",
                "audit_state": "passed",
                "attempt_count": 0,
            }
        ],
        "notebook_entries": [],
        "attempts": [],
        "state": "introduced",
        "revision": 7,
    }
    responses = {
        "library.list": {"items": [row], "total": 1, "applied_filter": "all", "empty_reason": None},
        "course.outline": {"revision": 0, "objectives": objectives, "plan": {"units": []}},
        "lesson.page": page,
        "check.open": check,
        "tutor.history": {"turns": [], "revision": 7},
        "practice.state": {"declaration": None, "state": "idle"},
        "world.read": {"world": None},
        "review.queue": {"items": [], "total_overdue": 0},
        "notebook.list": {"entries": []},
        "quiz.history": {"items": []},
        "evidence.inspect": {"items": []},
        "lesson.assist": {"event_id": "ev_1", "kind": "hint_request", "evidence_class": "hinted", "revision": 8},
        "tutor.ask": {
            "state": "breadcrumb",
            "turn": {
                "id": "ttr_tutor01",
                "ordinal": 2,
                "role": "tutor",
                "text": HINT_ANSWER,
                "citations": [],
            },
        },
    }
    implemented = [
        "library.list",
        "course.outline",
        "lesson.page",
        "check.open",
        "lesson.assist",
        "tutor.ask",
        "tutor.history",
        "practice.state",
        "world.read",
        "review.queue",
        "notebook.list",
        "quiz.history",
        "evidence.inspect",
        "binding.get",
        "pack.inspect",
    ]
    return {
        "row": row,
        "objectiveId": "obj_0123456789abcdef",
        "check": check,
        "binding": {
            "enrollment_id": row["enrollment_id"],
            "objective_id": "obj_0123456789abcdef",
            "lesson_run_id": "run_0123456789abcdef",
            "profile": "default",
        },
        "responses": responses,
        "implemented": implemented,
        "hintAnswer": HINT_ANSWER,
    }


class TutorBesideCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-w24-")
        root = Path(cls.tmp.name)
        if stage_desktop_node_modules(root) is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        write_sdk_stub(root, SDK_STUB_WITH_PANE)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def run_harness(self) -> dict:
        payload = described()
        (self.root / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
        proc = subprocess.run(
            ["node", "harness.mjs", "payload.json"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, f"harness failed:\n{proc.stdout}\n{proc.stderr}")
        return json.loads(proc.stdout)

    def test_the_route_passes_the_tutor_door_and_it_focuses_the_rail(self) -> None:
        result = self.run_harness()
        self.assertTrue(result["classroom"], "the route did not mount the classroom from a path row")
        self.assertEqual(result["tutorPill"], "Ask the tutor",
                         "the shipped route rendered no tutor door (onAskTutor not passed)")
        self.assertIn("coursebook:pane", result["revealed"],
                      "pressing the tutor door did not reveal the contributed pane")
        self.assertEqual(result["focusAfterTutor"], "cb-tutor-input",
                         "pressing the tutor door did not put the caret in the tutor composer")

    def test_ask_for_a_hint_records_the_assist_and_the_tutor_answers(self) -> None:
        result = self.run_harness()
        self.assertEqual(result["hintControl"], "Ask for a hint",
                         "the check card rendered no real hint control")
        self.assertEqual(result["assistDeltaForHint"], 1,
                         "Ask for a hint did not write exactly one lesson.assist")
        self.assertEqual(result["assistKind"], "hint_request")
        self.assertEqual(result["askDeltaForHint"], 1,
                         "the recorded hint was not followed by the one tutor question")
        self.assertEqual(result["askedQuestion"], TUTOR_HINT_QUESTION)
        self.assertTrue(result["tutorHasHint"],
                        f"the tutor rail surfaced no hint answer:\n{result['tutorBody']}")
        self.assertIn("Hint recorded", result["hintStatus"] or "")

    def test_the_disclosure_records_without_pretending_to_answer(self) -> None:
        result = self.run_harness()
        self.assertEqual(result["askButtonInAnswer"], "Ask for a hint",
                         "the v2 answer surface has no door to a real hint")
        self.assertEqual(result["disclosure"], "I already used a hint",
                         "the post-hoc control was not renamed to a disclosure")
        self.assertEqual(result["assistDeltaForDisclosure"], 1,
                         "the disclosure did not record the learner's own statement")
        self.assertEqual(result["askDeltaForDisclosure"], 0,
                         "the disclosure asked the tutor — it must only record what happened")
        self.assertIn("Hint recorded", result["disclosureFlag"] or "")


if __name__ == "__main__":
    unittest.main()
