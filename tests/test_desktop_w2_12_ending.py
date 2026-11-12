"""W2-12 — Game mode has an ending (CREATE-EXPERIENCE item 38).

The complete panel existed but nothing ever set the classroom's learner state to ``complete``, so
finishing the last check left the learner on a graded card with no ending: a finished section read
as unfinished work. And the panel's body always claimed "Your check is recorded.", even for a
commit that stored no evidence row.

These tests mount the *registered route* — the same ``CoursebookPage`` the host renders — in jsdom,
walk to a section the way a person does, and drive the served selection check to a committed pass
through the shipped check card. From that live tree:

* the route reaches ``data-cb3-classroom-state="complete"`` and the panel renders with the one
  primary "Back to the path"; the check card is gone;
* a pass whose commit carried an attempt (the layer-1 evidence row) prints the recorded body;
* a pass whose lane names a self-reported class (no evidence row) never claims a recorded result.

What this does NOT prove: a live backend, or pixels against the concept frames. The check card,
the ending's geometry and the game-mode ending on a real window belong to the card's rig pass.
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

# The route's tutor door asks for a pane, and the shipped module reaches for it on mount. The shared
# stub has no host door; record the ask instead of dropping it so the render stays faithful.
SDK_STUB_WITH_PANE = SDK_STUB.replace(
    "  navigate: () => {},",
    "  navigate: () => {},\n"
    "  revealPane: (id) => { (globalThis.__CB_REVEALED_PANES = globalThis.__CB_REVEALED_PANES || []).push(id) },",
)
assert "revealPane" in SDK_STUB_WITH_PANE, "the shared SDK stub changed shape; update the pane stub"

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
globalThis.MouseEvent = dom.window.MouseEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1049)
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const responses = payload.responses || {}
const runtime = { wire_version: 6, implemented_methods: payload.implemented || [], single_home_host: false }
const generic = { items: [], entries: [], objectives: [], total: 0 }
let submitted = false
const reply = (method) => {
  // The page a real backend serves after the commit: the check is closed and the attempt is the
  // recorded one. The ending must still wait for the learner's own press.
  if (method === 'lesson.page' && submitted && payload.afterPage) {
    return { ok: true, result: payload.afterPage }
  }
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
    const answer = reply(method)
    if (method === 'attempt.submit') submitted = true
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
const flush = async (ms = 80) => { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
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

const beforeState = (document.querySelector('[data-cb-classroom]') || {}).getAttribute
  ? document.querySelector('[data-cb-classroom]').getAttribute('data-cb3-classroom-state')
  : null

// Answer the served selection check the way a person does: pick a choice, press the one primary.
const choice = document.querySelector('[data-cb3-choice] input')
if (!choice) throw new Error('the classroom rendered no selection check')
await act(async () => { choice.click() })
await flush(80)
const checkButton = [...document.querySelectorAll('[data-cb3-primary]')].find((node) => text(node) === 'Check answer')
if (!checkButton) throw new Error('the check card rendered no Check answer primary')
await click(checkButton, 'Check answer')
await flush(220)

// The pass is still the teaching beat: the verdict and its observation stay on the card, and the
// card's own primary is the door to the ending on the last check.
const gradedState = document.querySelector('[data-cb-classroom]').getAttribute('data-cb3-classroom-state')
const verdict = document.querySelector('[data-cb3-verdict]')
const verdictText = verdict ? text(verdict) : null
const advance = [...document.querySelectorAll('[data-cb3-primary]')].find((node) => text(node) === 'Next section')
if (!advance) throw new Error('the graded card rendered no Next section primary')
await click(advance, 'Next section')
await flush(220)

const surface = document.querySelector('[data-cb-classroom]')
const panel = document.querySelector('[data-cb3-classroom-state="complete"]')
const body = panel ? panel.querySelector('[data-cb3-complete-evidence]') : null
const submit = calls.filter((call) => call.method === 'attempt.submit')

const completionOf = (page) => mod.classroomCompletion(page, null)
const evidenceOf = (facts) => mod.classroomEvidenceRecorded(facts)
const lastOf = (outline, page) => mod.classroomLastSection(outline, page)

process.stdout.write(JSON.stringify({
  beforeState,
  gradedState,
  verdictText,
  advanceGone: ![...document.querySelectorAll('[data-cb3-primary]')].find((node) => text(node) === 'Next section'),
  afterState: surface ? surface.getAttribute('data-cb3-classroom-state') : null,
  panel: panel ? text(panel) : null,
  evidenceFlag: body ? body.getAttribute('data-cb3-complete-evidence') : null,
  bodyText: body ? text(body) : null,
  checkCardGone: !document.querySelector('[data-cb3-surface="check"]'),
  primaryCount: panel ? panel.querySelectorAll('[data-cb3-pill="primary"]').length : 0,
  submitCount: submit.length,
  submittedCheckId: submit.length ? submit[submit.length - 1].payload && submit[submit.length - 1].payload.check_id : null,
  revisit: completionOf(payload.revisitPage),
  revisitOverride: completionOf(payload.revisitOverridePage),
  superseded: completionOf(payload.supersededPage),
  evidenceFacts: (payload.passFacts || []).map(evidenceOf),
  lastHere: lastOf(payload.outlineData, payload.pageData),
  lastMid: lastOf(payload.multiOutline, payload.pageData),
  lastTruncated: lastOf(payload.truncatedOutline, payload.pageData)
}))
"""


def described(evidence_class: str) -> dict:
    """One section with one served selection check, and a pass that commits with ``evidence_class``."""
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
            "total_objectives": 1,
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
    ]
    stimulus = {
        "prompt": "Which line is a confession rather than a description?",
        "format": "selection",
        "choices": ["A: うん、好きだよ。", "B: 好きです。付き合ってください。"],
        "items": [],
    }
    check = {
        "check_id": "chk_0123456789abcdef",
        "objective_id": "obj_0123456789abcdef",
        "check_version": 1,
        "evidence_target": "discrimination",
        "state": "open",
        "audit_state": "passed",
        "attempt_count": 0,
        "revision": 7,
        "stimulus": stimulus,
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
        "segments": [
            {"segment_id": "seg_1", "ordinal": 1, "kind": "teaching", "text": "Two ways of saying it."}
        ],
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
    graded = {
        "attempt_id": "att_0123456789abcdef",
        "verdict": "pass",
        "evidence_class": evidence_class,
        "criteria": [],
        "next_action": "complete_objective",
        "revision": 8,
    }
    responses = {
        "library.list": {"items": [row], "total": 1, "applied_filter": "all", "empty_reason": None},
        "course.outline": {"revision": 0, "objectives": objectives, "plan": {"units": []}},
        "lesson.page": page,
        "check.open": check,
        "check.get": {"check_id": check["check_id"], "state": "open", "attempt_count": 0, "stimulus": stimulus},
        "attempt.submit": graded,
        "tutor.history": {"turns": [], "revision": 7},
        "practice.state": {"declaration": None, "state": "idle"},
        "world.read": {"world": None},
        "review.queue": {"items": [], "total_overdue": 0},
        "notebook.list": {"entries": []},
        "quiz.history": {"items": []},
        "evidence.inspect": {"items": []},
    }
    implemented = [
        "library.list",
        "course.outline",
        "lesson.page",
        "check.open",
        "check.get",
        "attempt.submit",
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
        "responses": responses,
        "implemented": implemented,
        "revisitPage": _page_with_recorded_pass(page),
        "afterPage": _page_with_recorded_pass(
            page,
            attempts=[
                {"attempt_id": "att_0123456789abcdef", "check_id": check["check_id"],
                 "verdict": "pass", "evidence_class": evidence_class, "state": "committed"}
            ],
        ),
        "revisitOverridePage": _page_with_recorded_pass(page, attempts=[
            {"attempt_id": "att_3", "check_id": check["check_id"], "verdict": "overridden",
             "evidence_class": "override", "state": "committed"},
        ]),
        "supersededPage": _page_with_recorded_pass(page, superseded=True),
        "passFacts": [
            {"verdict": "pass", "attempt_id": "att_1", "evidence_class": "cold"},
            {"verdict": "pass", "attempt_id": "att_2", "evidence_class": "self_reported"},
            {"verdict": "pass", "attempt_id": None, "evidence_class": "cold"},
            {"verdict": "not_yet", "attempt_id": "att_4", "evidence_class": "cold"},
        ],
        "outlineData": responses["course.outline"],
        "pageData": page,
        "multiOutline": {
            **responses["course.outline"],
            "total": 2,
            "objectives": objectives
            + [
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
                }
            ],
        },
        "truncatedOutline": {**responses["course.outline"], "truncated": True, "total": 9},
    }


def _page_with_recorded_pass(page: dict, attempts: list | None = None, superseded: bool = False) -> dict:
    """The same page as a later read would serve it: the check answered and closed."""
    out = json.loads(json.dumps(page))
    out["checks"] = [
        {
            "check_id": "chk_0123456789abcdef",
            "version": 1,
            "evidence_target": "discrimination",
            "state": "closed",
            "audit_state": "passed",
            "attempt_count": 1,
        }
    ]
    if superseded:
        out["checks"] = [
            {
                "check_id": "chk_0123456789abcdf0",
                "version": 2,
                "evidence_target": "discrimination",
                "state": "open",
                "audit_state": "passed",
                "attempt_count": 0,
            },
            dict(out["checks"][0]),
        ]
    out["attempts"] = attempts or [
        {"attempt_id": "att_1", "check_id": "chk_0123456789abcdef", "verdict": "pass",
         "evidence_class": "cold", "state": "committed"}
    ]
    return out


class GameModeEndingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-w212-")
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

    def run_harness(self, evidence_class: str = "cold") -> dict:
        payload = described(evidence_class)
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

    def test_the_last_check_passes_and_the_section_ends(self) -> None:
        result = self.run_harness("cold")
        self.assertEqual(result["beforeState"], "default",
                         "the section was already complete before the check was answered")
        self.assertEqual(result["submitCount"], 1, "the answer did not reach attempt.submit")
        self.assertEqual(result["submittedCheckId"], "chk_0123456789abcdef")
        # The verdict is still the teaching beat; the ending does not erase the answer's feedback.
        self.assertEqual(result["gradedState"], "default",
                         "the ending replaced the graded card before the learner read it")
        self.assertEqual(result["verdictText"], "That is right.")
        self.assertEqual(result["afterState"], "complete",
                         "finishing the last check never reached the ending (item 38)")
        self.assertIsNotNone(result["panel"], "the complete panel did not render")
        self.assertIn("Section finished", result["panel"] or "")
        self.assertIn("Back to the path", result["panel"] or "")
        self.assertEqual(result["primaryCount"], 1, "the ending invented a second primary")
        self.assertTrue(result["advanceGone"], "the graded card's primary stayed beside the ending")
        self.assertTrue(result["checkCardGone"], "the answering surface stayed under the ending")

    def test_a_recorded_pass_says_the_check_is_recorded(self) -> None:
        result = self.run_harness("cold")
        self.assertEqual(result["evidenceFlag"], "recorded")
        self.assertIn("Your check is recorded.", result["bodyText"] or "")

    def test_a_pass_without_an_evidence_row_never_claims_a_recorded_result(self) -> None:
        # `self_reported` is the lane that commits without a layer-1 evidence row. The section still
        # ends (the learner did finish), but the body may not claim a recorded result.
        result = self.run_harness("self_reported")
        self.assertEqual(result["afterState"], "complete",
                         "a pass from a no-evidence lane did not end the section")
        self.assertEqual(result["evidenceFlag"], "unrecorded")
        self.assertNotIn("Your check is recorded.", result["bodyText"] or "",
                         "the ending claimed a recorded result when no evidence row was written")
        self.assertIn("nothing was recorded", (result["bodyText"] or "").lower())

    def test_a_finished_section_still_ends_when_it_is_read_again(self) -> None:
        # The same defect from the other side: a learner who returns to a section they finished must
        # see the ending, read back from the recorded rows rather than from this session's commit.
        result = self.run_harness()
        self.assertEqual(result["revisit"], {"evidence": True},
                         "a section with a recorded pass and no open check read as unfinished")
        self.assertIsNone(result["superseded"],
                          "a newer open check (a fresh challenge) was treated as already finished")
        self.assertIsNone(result["revisitOverride"],
                          "an override is not a pass and must not end the section")

    def test_evidence_is_only_claimed_for_a_committed_pass(self) -> None:
        result = self.run_harness()
        self.assertEqual(
            result["evidenceFacts"],
            [True, False, False, False],
            "evidence was claimed for a self-reported pass, an uncommitted answer or a non-pass",
        )

    def test_only_the_last_section_can_end_the_course(self) -> None:
        result = self.run_harness()
        self.assertTrue(result["lastHere"], "the last section of the path was not read as last")
        self.assertFalse(result["lastMid"],
                         "a section with teaching after it was treated as the course ending")
        self.assertFalse(result["lastTruncated"],
                         "a truncated outline was treated as a finished path")


if __name__ == "__main__":
    unittest.main()
