"""The live learning surface: XP on a real completion, and a Field Challenge that is a challenge.

Two defects from ``docs/UX-AUDIT-E2E.md`` meet on one surface, so one jsdom harness drives both:

* WIRE-9 — ``engagement.award`` had no caller, so the chip read zero forever. A passing
  ``attempt.submit`` on the v3 classroom must award one ``check_submitted`` event for the
  backend's own ``attempt_id``, then re-read ``engagement.read`` so the chip moves. The award line
  paints the backend's own ``points`` and, when it supplies one, its own ``basis`` sentence —
  never a computed number and never an invented explanation. A non-passing attempt, a typed
  refusal and an already-awarded replay all award nothing and paint nothing.
* WIRE-8 — the Field Challenge printed the check already on screen and "Try it yourself" left the
  lesson. It now calls the existing ``progression.challenge_out``, adopts the returned revision,
  re-reads the open check, and the learner answers a different served stimulus in place.

The harness stages the shipped ``desktop/plugin.js``, registers it with a fake ``ctx.rest`` and
renders ``ClassroomV3Surface`` in jsdom, exactly like ``tests/test_desktop_pronunciation.py``. It
does not prove pixels or a live backend; the isolated rig carries those.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import desktop_node_modules, stage_desktop_node_modules
from tests.test_desktop_lesson_views import SDK_STUB

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

HARNESS = r"""
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
globalThis.MouseEvent = dom.window.MouseEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = '1349'
globalThis.__CB_TEST_MODE__ = 'light'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')

const calls = []
const events = []
let awarded = false
let challengeOpen = false
let challengeAvailable = payload.challengeAvailable !== false

const stimulusFirst = {
  prompt: 'Which line is the romantic confession?',
  format: 'selection',
  choices: ['A: うん、好きだよ。', 'B: 好きです。付き合ってください。'],
  items: []
}
const stimulusChallenge = {
  prompt: 'Which line is a polite refusal?',
  format: 'selection',
  choices: ['A: それはちょっと難しいです。', 'B: 好きです。'],
  items: []
}

const level = (total) => ({
  level: 1 + Math.floor(total / 100),
  title: 'Curious',
  xp_into_level: total % 100,
  xp_for_next_level: 100,
  is_cosmetic: true
})

const fakeRest = async (path, options = {}) => {
  const method = options.method || 'GET'
  const body = options.body || null
  calls.push({ path: String(path).split('?')[0], method, body })
  if (String(path).split('?')[0] === '/runtime') {
    return { wire_version: 26, implemented_methods: payload.implemented }
  }
  if (String(path).split('?')[0] !== '/rpc') throw new Error('unexpected rest path ' + path)
  const name = body && body.method
  if (name === 'course.outline') return { ok: true, result: payload.outline }
  if (name === 'lesson.page') {
    const result = { ...payload.page, revision: challengeOpen ? 8 : 7 }
    return { ok: true, result }
  }
  if (name === 'world.read') return { ok: true, result: { world: null, style: null } }
  if (name === 'engagement.read') {
    const total = awarded ? 20 : 0
    return {
      ok: true,
      result: {
        xp_total: total,
        level: level(total),
        progress: {
          label: 'Game progress',
          is_play_progress: true,
          assigned_steps: 3,
          completed_steps: awarded ? 1 : 0,
          feedback_visible: true
        },
        recent_events: []
      }
    }
  }
  if (name === 'check.open') {
    const revision = Number(body.expected_revision)
    return {
      ok: true,
      result: {
        check_id: challengeOpen ? 'chk_challenge01' : 'chk_first01',
        check_version: challengeOpen ? 2 : 1,
        evidence_target: 'discrimination',
        revision
      }
    }
  }
  if (name === 'check.get') {
    const challenge = body && body.payload && body.payload.check_id === 'chk_challenge01'
    return {
      ok: true,
      result: {
        check_id: challenge ? 'chk_challenge01' : 'chk_first01',
        objective_id: 'obj_2',
        check_version: challenge ? 2 : 1,
        evidence_target: 'discrimination',
        state: 'open',
        audit_state: 'passed',
        attempt_count: 0,
        stimulus: challenge ? stimulusChallenge : stimulusFirst
      }
    }
  }
  if (name === 'attempt.submit') {
    const verdict = payload.verdict || 'pass'
    return {
      ok: true,
      result: {
        attempt_id: 'att_0123456789abcdef',
        verdict,
        evidence_class: 'cold',
        criteria: [],
        next_action: verdict === 'pass' ? 'advance' : 'retry',
        revision: 9
      }
    }
  }
  if (name === 'engagement.award') {
    if (payload.awardRefusal) {
      return {
        ok: false,
        error: {
          code: 'VALIDATION_FAILED',
          category: 'validation',
          message: 'XP is awarded only for a real recorded action; that action id is not one.',
          retryable: false,
          details: { field: 'action_id', reason: 'not_a_real_action' }
        }
      }
    }
    if (payload.awardReplay) {
      return { ok: true, result: { awarded: false, points: 0, xp_total: 0, level: level(0) } }
    }
    awarded = true
    return {
      ok: true,
      result: {
        awarded: true,
        points: 20,
        xp_total: 20,
        level: level(20),
        ...(payload.awardBasis ? { basis: payload.awardBasis } : {})
      }
    }
  }
  if (name === 'progression.challenge_out') {
    if (!challengeAvailable) {
      return {
        ok: false,
        error: {
          code: 'VALIDATION_FAILED',
          category: 'validation',
          message: 'no unused, audited variant of this check exists; a replay would not be a challenge.',
          retryable: false,
          details: { reason: 'no_varied_challenge_available', objective_id: 'obj_2' }
        }
      }
    }
    challengeOpen = true
    return { ok: true, result: { check_id: 'chk_challenge01', check_version: 2, revision: 8 } }
  }
  throw new Error('unexpected rpc method ' + name)
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  storage: payload.storage
    ? {
        get: (key, fallback) => (String(key).includes('home-preferences') ? payload.storage : fallback),
        set: () => {}
      }
    : undefined
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const props = {
  row: payload.row,
  enrollmentId: payload.row.enrollment_id,
  objectiveId: 'obj_2',
  mode: 'game',
  onBack: () => events.push('back'),
  onOpenSection: () => events.push('open-section'),
  onNextSection: () => events.push('next-section'),
  onStartChat: () => events.push('start-chat')
}

const flush = async (ms = 120) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}
const byText = (text) =>
  [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === text) || null
const click = async (node) => {
  if (!node) {
    process.stderr.write('HTML-AT-FAILURE:' + document.getElementById('root').innerHTML)
    throw new Error('button not found')
  }
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
}
const question = () => {
  const node = document.querySelector('[data-cb3-question]')
  return node ? (node.textContent || '').trim() : null
}
const challengeText = () => {
  const node = document.querySelector('[data-cb3-challenge]')
  return node ? (node.textContent || '').trim() : null
}
const xp = () => {
  const node = document.querySelector('[data-cb3-xp]')
  return node ? (node.textContent || '').trim() : null
}
const rpc = (name) => calls.filter((call) => call.path === '/rpc' && call.body && call.body.method === name)

await act(async () => { root.render(React.createElement(mod.ClassroomV3Surface, props)) })
await flush(240)

const before = { question: question(), xp: xp(), challenge: challengeText() }

if (payload.scenario === 'award') {
  const choice = document.querySelectorAll('[data-cb3-choice] input')[1]
  await act(async () => { choice.click() })
  await flush(60)
  await click(byText('Check answer'))
} else if (payload.scenario === 'challenge') {
  await click(byText('Try it yourself'))
} else if (payload.scenario === 'challenge-none') {
  await click(byText('Try it yourself'))
}

const after = {
  question: question(),
  xp: xp(),
  award: (() => {
    const node = document.querySelector('[data-cb3-award]')
    return node ? (node.textContent || '').trim() : null
  })(),
  challenge: challengeText(),
  verdict: (() => {
    const node = document.querySelector('[data-cb3-verdict]')
    return node ? node.getAttribute('data-cb3-verdict') : null
  })()
}

process.stdout.write(JSON.stringify({
  before,
  after,
  events,
  calls: calls
    .filter((call) => call.path === '/rpc')
    .map((call) => ({
      method: call.body.method,
      payload: call.body.payload,
      expected_revision: call.body.expected_revision,
      idempotency_key: call.body.idempotency_key || null
    }))
}))
"""


def outline() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "plan": None,
        "total": 3,
        "truncated": False,
        "objectives": [
            {
                "objective_id": "obj_1",
                "ordinal": 1,
                "title": "Hear both ways of saying it",
                "evidence_target": "discrimination",
                "state": "independent_evidence",
                "check_state": "closed",
                "attempt_count": 2,
                "independent": True,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_2",
                "ordinal": 2,
                "title": "Tell affection from a confession",
                "evidence_target": "discrimination",
                "state": "not_started",
                "check_state": "open",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
            {
                "objective_id": "obj_3",
                "ordinal": 3,
                "title": "Say it politely",
                "evidence_target": "production",
                "state": "not_started",
                "check_state": "none",
                "attempt_count": 0,
                "independent": False,
                "last_opened_at": None,
            },
        ],
    }


def page() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "course": {"course_id": "crs_0123456789abcdef", "title": "Japanese affection and register"},
        "section": {
            "objective_id": "obj_2",
            "title": "Tell everyday affection from a direct romantic declaration",
            "ordinal": 2,
            "state": "not_started",
            "evidence_target": "discrimination",
            "last_opened_at": None,
        },
        "runtime": {
            "lesson_run_id": "run_0123456789abcdef",
            "binding_id": None,
            "binding_status": "detached",
            "session_state": "missing",
            "last_active_at": None,
        },
        "segments": [],
        "document": None,
        "sources": [],
        "artifacts": [],
        "checks": [
            {
                "check_id": "chk_first01",
                "version": 1,
                "evidence_target": "discrimination",
                "state": "open",
                "audit_state": "passed",
                "attempt_count": 0,
            }
        ],
        "notebook_entries": [],
        "attempts": [],
        "state": "not_started",
        "revision": 7,
        "provenance": None,
    }


def row() -> dict:
    return {
        "enrollment_id": "enr_0123456789abcdef",
        "course_id": "crs_0123456789abcdef",
        "title": "Japanese affection and register",
        "recipe": "learner",
        "revision": 7,
        "next_step": {"kind": "continue_lesson", "label": "Continue section 3"},
        "evidence_summary": {
            "independent": 1,
            "total_objectives": 3,
            "current_objective_id": "obj_2",
        },
    }


IMPLEMENTED = [
    "course.outline",
    "lesson.page",
    "world.read",
    "engagement.read",
    "engagement.award",
    "check.open",
    "check.get",
    "attempt.submit",
    "progression.challenge_out",
]


class _Rig:
    def __init__(self) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        if desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-learning-live-")
        self.root = Path(self.tmp.name)
        (self.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        sdk = stage_desktop_node_modules(self.root)
        assert sdk is not None
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    def run(self, scenario: str, **payload) -> dict:
        case = {
            "scenario": scenario,
            "row": row(),
            "outline": outline(),
            "page": page(),
            "implemented": IMPLEMENTED,
            **payload,
        }
        case_file = self.root / f"case-{scenario}.json"
        case_file.write_text(json.dumps(case), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case_file)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(f"render failed: {result.stderr[-6000:] or result.stdout[-6000:]}")
        return json.loads(result.stdout)


class LearningLiveSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rig = _Rig()

    def test_a_passing_check_awards_xp_for_the_real_attempt(self) -> None:
        data = self.rig.run("award")
        self.assertEqual(data["before"]["xp"], "0 XP")
        self.assertEqual(data["after"]["verdict"], "pass")
        awards = [call for call in data["calls"] if call["method"] == "engagement.award"]
        self.assertEqual(len(awards), 1, "a passing check did not award exactly one XP event")
        award = awards[0]
        self.assertEqual(
            award["payload"],
            {
                "course_id": "crs_0123456789abcdef",
                "enrollment_id": "enr_0123456789abcdef",
                "action_kind": "check_submitted",
                "action_id": "att_0123456789abcdef",
            },
        )
        self.assertTrue(award["idempotency_key"].startswith("cb-award-enr_0123456789abcdef-att_"))
        # The chip is painted from `engagement.read`, and the read is repeated after the award:
        # the learner sees the number move, not a locally incremented guess.
        reads = [call for call in data["calls"] if call["method"] == "engagement.read"]
        self.assertGreaterEqual(len(reads), 2, "the XP chip was not re-read after the award")
        self.assertEqual(data["after"]["xp"], "20 XP")
        # The current contract has no `basis` field, so the line is the backend's number and the
        # label only. No explanation is invented.
        self.assertEqual(data["after"]["award"], "20 XP")
        self.assertNotIn("next-section", data["events"], "a check pass left the section instead of advancing the surface state")

    def test_the_award_line_paints_the_backends_own_basis_when_it_supplies_one(self) -> None:
        basis = "comprehension check passed first attempt"
        data = self.rig.run("award", awardBasis=basis)
        self.assertEqual(data["after"]["award"], f"20 XP: {basis}")

    def test_feedback_off_hides_xp_but_still_records_the_real_award(self) -> None:
        data = self.rig.run("award", storage={"gameFeedback": False})
        # The settings sheet's switch is honoured by the classroom: no chip, no award line.
        self.assertIsNone(data["after"]["xp"], "Game feedback off still painted the XP chip")
        self.assertIsNone(data["after"]["award"], "Game feedback off still painted an award")
        # Hiding is not deleting: the committed attempt is still priced in the ledger.
        awards = [call for call in data["calls"] if call["method"] == "engagement.award"]
        self.assertEqual(len(awards), 1, "hiding Game feedback stopped the real award")

    def test_a_typed_refusal_is_silent(self) -> None:
        data = self.rig.run("award", awardRefusal=True)
        self.assertEqual(data["after"]["verdict"], "pass")
        self.assertIsNone(data["after"]["award"], "a refused award painted a sentence")
        self.assertEqual(data["after"]["xp"], "0 XP")
        # No error sentence either: the check verdict is the only thing that changed.
        self.assertNotIn("VALIDATION_FAILED", data["after"]["question"] or "")

    def test_an_already_awarded_replay_is_silent(self) -> None:
        data = self.rig.run("award", awardReplay=True)
        self.assertIsNone(data["after"]["award"], "an already-awarded replay painted a second award")

    def test_a_non_passing_check_awards_no_xp(self) -> None:
        data = self.rig.run("award", verdict="not_yet")
        self.assertEqual(data["after"]["verdict"], "not_yet")
        awards = [call for call in data["calls"] if call["method"] == "engagement.award"]
        self.assertEqual(awards, [], "XP was awarded for an attempt that did not pass")
        self.assertIsNone(data["after"]["award"], "a non-passing attempt painted an award")
        self.assertEqual(data["after"]["xp"], "0 XP")

    def test_try_it_yourself_opens_a_different_check_in_place(self) -> None:
        data = self.rig.run("challenge")
        self.assertEqual(data["before"]["question"], "Which line is the romantic confession?")
        # The card no longer repeats the visible question: it describes the fresh check it opens.
        self.assertIn("Field Challenge", data["before"]["challenge"])
        self.assertIn("A fresh, unseen question", data["before"]["challenge"])
        self.assertNotIn("Which line is the romantic confession?", data["before"]["challenge"])

        opens = [call for call in data["calls"] if call["method"] == "progression.challenge_out"]
        self.assertEqual(len(opens), 1, "Try it yourself did not ask the backend for a fresh challenge")
        self.assertEqual(
            opens[0]["payload"],
            {"enrollment_id": "enr_0123456789abcdef", "objective_id": "obj_2"},
        )
        self.assertEqual(opens[0]["expected_revision"], 7)
        self.assertNotIn("next-section", data["events"], "Try it yourself left the lesson")

        # The returned revision fences the re-read, and the served stimulus is the variant.
        check_opens = [call for call in data["calls"] if call["method"] == "check.open"]
        self.assertGreaterEqual(len(check_opens), 2, "the open check was not re-read after the challenge")
        self.assertEqual(check_opens[-1]["expected_revision"], 8)
        self.assertEqual(data["after"]["question"], "Which line is a polite refusal?")
        self.assertIn("Challenge open", data["after"]["challenge"])

    def test_a_section_with_no_variant_says_so_and_stays(self) -> None:
        data = self.rig.run("challenge-none", challengeAvailable=False)
        self.assertIn("No fresh challenge is available", data["after"]["challenge"])
        self.assertNotIn("next-section", data["events"], "a refused challenge left the lesson")
        self.assertEqual(data["after"]["question"], "Which line is the romantic confession?")


if __name__ == "__main__":
    unittest.main()
