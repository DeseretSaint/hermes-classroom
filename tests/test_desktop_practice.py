"""H-120b: the conversation-practice surface, exercised against the shipped plugin.

These cases render the real ``desktop/plugin.js`` and drive the real ``AttemptControls`` →
``PracticeSurface`` path over a stubbed ``ctx.rest``. Nothing about the controls is simulated in
Python: each case clicks the DOM node the plugin produced and asserts on what the backend stub
then received.

What is pinned here (``docs/CONVERSATION-PRACTICE.md`` §5, §7.4, §9):

* Start / End practice / Cancel are real route calls with the envelope the contract requires
  (``expected_revision`` on every write, one stable ``attempt_nonce`` for End practice);
* the transcript is rendered from the read, so refreshing cannot append the same learner turn
  twice;
* a practice never offers the written-answer form, and ``attempt.submit`` is never sent;
* visible target labels are printed, hidden ones are withheld even when the payload smuggles them;
* the verdict line is one compact line built only from values the backend returned, the full
  criteria stay behind Review grading, and no score or percentage is invented;
* every call carries the ``/runtime`` wire version (cb.rpc v16 on this branch), never a literal;
* the unavailable states each carry exactly one next action.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The shared stub draws ConfirmDialog as nothing, so the cancel path could not be exercised. This
# case needs the dialog's own confirm control, and the stub is extended in place rather than forked.
STUB = SDK_STUB.replace(
    "export const ConfirmDialog = () => null",
    "export const ConfirmDialog = (props) =>\n"
    "  props.open\n"
    "    ? el('div', { role: 'dialog', 'data-cb-confirm': 'open' }, [\n"
    "        el('div', { key: 't' }, props.title),\n"
    "        el('div', { key: 'd' }, props.description),\n"
    "        el('button', { key: 'ok', type: 'button', 'data-cb-confirm-ok': 'true', onClick: props.onConfirm }, props.confirmLabel),\n"
    "        el('button', { key: 'no', type: 'button', onClick: props.onClose }, 'Keep practice')\n"
    "      ])\n"
    "    : null",
)

LIVE_HARNESS = r"""
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import plugin, { AttemptControls } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/'
})
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent', 'FocusEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

const calls = []
const methods = payload.runtimeMethods || [
  'check.open',
  'check.get',
  'practice.state',
  'practice.start',
  'practice.end',
  'practice.cancel'
]
const checkId = 'chk_0123456789abcdef'
const wireVersion = payload.wireVersion || 16

const state = {
  session: payload.session || null,
  stateReads: 0,
  appended: false
}

const noneSession = {
  session_id: null,
  check_id: checkId,
  check_version: 1,
  state: 'none',
  learner_turns: 0,
  remaining: 0,
  awaiting_tutor: false,
  transcript: [],
  attempt_id: null,
  verdict: null,
  criteria: []
}

const ctx = {
  register: () => {},
  onDispose: () => {},
  rest: async (path, options = {}) => {
    if (String(path).startsWith('/runtime')) {
      return { wire_version: wireVersion, implemented_methods: methods, single_home_host: false }
    }
    const body = options.body || {}
    calls.push({
      method: body.method,
      contract_version: body.contract_version,
      payload: body.payload || null,
      expected_revision: body.expected_revision ?? null,
      idempotency_key: body.idempotency_key ?? null
    })
    const ok = (result) => ({ ok: true, contract_version: wireVersion, operation_id: body.operation_id, result })

    if (body.method === 'practice.state') {
      state.stateReads += 1
      globalThis.__CB_READS__ = state.stateReads
      if (payload.stateError) {
        return {
          ok: false,
          contract_version: wireVersion,
          operation_id: body.operation_id,
          error: payload.stateError
        }
      }
      let session = state.session || noneSession
      if (session.state === 'active' && payload.appendTurn && !state.appended) {
        const extra = { ordinal: session.transcript.length + 1, speaker: 'learner', text: payload.appendTurn }
        session = {
          ...session,
          transcript: [...session.transcript, extra],
          learner_turns: session.learner_turns + 1,
          remaining: Math.max(0, session.remaining - 1),
          awaiting_tutor: true
        }
        state.session = session
        state.appended = true
      }
      return ok(session)
    }
    if (body.method === 'practice.start') {
      // A start refusal can be scripted one-per-press, so a stale fence and its recovery are both
      // driven through the real click path.
      const startErrors = Array.isArray(payload.startErrors)
        ? payload.startErrors
        : payload.startError
          ? [payload.startError]
          : []
      const startCount = calls.filter((call) => call.method === 'practice.start').length
      const startError = startErrors[startCount - 1]
      if (startError) {
        return {
          ok: false,
          contract_version: wireVersion,
          operation_id: body.operation_id,
          error: startError
        }
      }
      state.session = payload.started || null
      return ok(payload.started || null)
    }
    if (body.method === 'practice.end') {
      if (payload.endError) {
        return {
          ok: false,
          contract_version: wireVersion,
          operation_id: body.operation_id,
          error: payload.endError
        }
      }
      if (state.session) state.session = { ...state.session, state: 'graded' }
      return ok(payload.endResult || null)
    }
    if (body.method === 'practice.cancel') {
      if (state.session) state.session = { ...state.session, state: 'cancelled' }
      return ok({ session_id: state.session ? state.session.session_id : null, state: 'cancelled', revision: 3, session_revision: 4 })
    }
    if (body.method === 'attempt.submit') {
      return ok({ verdict: 'pass', evidence_class: 'cold', criteria: [], next_action: 'complete_objective' })
    }
    return {
      ok: false,
      contract_version: wireVersion,
      operation_id: body.operation_id,
      error: { code: 'UNKNOWN', category: 'internal', message: 'unexpected method ' + body.method }
    }
  }
}

plugin.register(ctx)

const check = {
  check_id: checkId,
  check_version: 1,
  evidence_target: 'production',
  stimulus: payload.stimulus
}

const implemented = new Set(methods)
const root = createRoot(document.getElementById('root'))
root.render(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check,
    revision: payload.revision === undefined ? 3 : payload.revision,
    implemented,
    bindingState: 'active',
    onCommitted: () => {}
  })
)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (predicate, timeout = 5000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return true
    await sleep(20)
  }
  return false
}
const practiceRoot = () => document.querySelector('[data-cb-practice]')
const practiceState = () => (practiceRoot() ? practiceRoot().getAttribute('data-cb-practice-state') : null)
const buttonByText = (text) =>
  Array.from(document.querySelectorAll('button')).find((button) => button.textContent.trim() === text)
const click = (text) => {
  const button = buttonByText(text)
  if (button) button.click()
  return Boolean(button)
}

await waitFor(() => practiceState() !== null && practiceState() !== 'loading')

if (payload.mode === 'start') {
  click('Start practice')
  await waitFor(() => practiceState() === 'active')
  // A refresh re-reads the same stored transcript; it must not append a second copy of a turn.
  click('Refresh transcript')
  await waitFor(() => globalThis.__CB_READS__ >= 3)
  await waitFor(() => document.querySelectorAll('[data-cb-practice-turn]').length === 2)
  click('Refresh transcript')
  await waitFor(() => globalThis.__CB_READS__ >= 4)
  await sleep(80)
} else if (payload.mode === 'end') {
  click('End practice')
  await waitFor(() => document.querySelector('[data-cb-practice-feedback]'))
  click('Review grading')
  await waitFor(() => document.querySelector('[data-cb-practice-criteria]'))
} else if (payload.mode === 'again') {
  // Grade once, then press the retry on the graded card itself: the second write must fence on the
  // revision the end returned, not on the one this card mounted with.
  click('End practice')
  await waitFor(() => document.querySelector('[data-cb-practice-feedback]'))
  click('Practice again')
  await sleep(120)
} else if (payload.mode === 'stale') {
  // The refusal names the revision the backend wants next; the following press must use it.
  click('End practice')
  await waitFor(() => document.querySelector('[data-cb-practice-feedback]'))
  click('Practice again')
  await waitFor(() => document.querySelector('[data-cb-practice-refusal]'))
  click('Practice again')
  await sleep(120)
} else if (payload.mode === 'pass') {
  click('End practice')
  await waitFor(() => document.querySelector('[data-cb-practice-feedback]'))
} else if (payload.mode === 'refuse') {
  click('End practice')
  await waitFor(() => document.querySelector('[data-cb-practice-refusal]'))
} else if (payload.mode === 'cancel') {
  click('Cancel practice')
  await waitFor(() => document.querySelector('[data-cb-confirm-ok]'))
  const confirm = document.querySelector('[data-cb-confirm-ok]')
  if (confirm) confirm.click()
  await waitFor(() => practiceState() === 'cancelled')
} else if (payload.mode === 'unsupported') {
  await waitFor(() => practiceState() === 'unsupported')
} else if (payload.mode === 'unavailable') {
  await waitFor(() => practiceState() === 'unavailable')
} else if (payload.mode === 'graded' || payload.mode === 'hidden') {
  await waitFor(() => practiceState() !== 'loading')
}

const text = document.body.textContent.replace(/\s+/g, ' ').trim()
process.stdout.write(
  JSON.stringify({
    state: practiceState(),
    text,
    html: document.body.innerHTML,
    calls,
    turnCount: document.querySelectorAll('[data-cb-practice-turn]').length,
    feedbackCount: document.querySelectorAll('[data-cb-practice-feedback]').length,
    feedback: (() => {
      const node = document.querySelector('[data-cb-practice-feedback]')
      return node ? node.textContent.trim() : null
    })(),
    criteriaCount: document.querySelectorAll('[data-cb-practice-criterion]').length,
    refusal: (() => {
      const node = document.querySelector('[data-cb-practice-refusal]')
      return node ? node.getAttribute('data-cb-practice-refusal') : null
    })(),
    buttons: Array.from(document.querySelectorAll('button')).map((button) => button.textContent.trim()),
    dialogs: document.querySelectorAll('[data-cb-confirm]').length
  })
)
"""

STATIC_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { AttemptControls } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const html = renderToStaticMarkup(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: payload.check,
    revision: 3,
    implemented: new Set(payload.implemented || []),
    bindingState: 'active',
    onCommitted: () => {}
  })
)
process.stdout.write(html)
"""


class PracticeSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h120b-practice-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "live.mjs").write_text(LIVE_HARNESS, encoding="utf-8")
        (root / "static.mjs").write_text(STATIC_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def _run(self, harness: str, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / harness), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        return result.stdout

    def live(self, payload: dict) -> dict:
        return json.loads(self._run("live.mjs", payload))

    def render(self, payload: dict) -> str:
        return self._run("static.mjs", payload)

    # -- fixtures -----------------------------------------------------------------------------
    TURN_RANGE = {"min": 3, "max": 5}

    def visible_practice(self, **overrides) -> dict:
        declaration = {
            "scenario": "Buying one train ticket at a station counter",
            "learner_role": "a traveller going to Kyoto",
            "tutor_role": "the station clerk",
            "turns": dict(self.TURN_RANGE),
            "targets": [
                {"id": "t1", "label": "one ticket to Kyoto, please"},
                {"id": "t2", "label": "how much is it?"},
                {"id": "t3", "label": "where is platform four?"},
            ],
            "targets_visible": True,
            "rubric_angle": "language_production",
            "opening": "Welcome. Where are you travelling today?",
        }
        declaration.update(overrides)
        return declaration

    def hidden_practice(self) -> dict:
        # The backend's `_stimulus_view` already omits `label` when targets are hidden. The fixture
        # keeps a label anyway, so the assertion is about the pane's own withholding and not only
        # about a well-behaved server.
        return self.visible_practice(
            targets_visible=False,
            targets=[
                {"id": "t1", "label": "one ticket to Kyoto, please"},
                {"id": "t2", "label": "how much is it?"},
                {"id": "t3", "label": "where is platform four?"},
            ],
        )

    def stimulus(self, declaration: dict) -> dict:
        return {
            "prompt": "Practise buying a train ticket.",
            "format": "text",
            "choices": [],
            "learner_instructions": None,
            "items": [],
            "practice": declaration,
        }

    def active_session(self, **overrides) -> dict:
        session = {
            "session_id": "ses_0123456789abcdef",
            "check_id": "chk_0123456789abcdef",
            "check_version": 1,
            "state": "active",
            "learner_turns": 1,
            "remaining": 4,
            "awaiting_tutor": False,
            "transcript": [
                {"ordinal": 1, "speaker": "tutor", "text": "Welcome. Where are you travelling today?"},
                {"ordinal": 2, "speaker": "learner", "text": "One ticket to Kyoto, please."},
            ],
            "attempt_id": None,
            "verdict": None,
            "criteria": [],
        }
        session.update(overrides)
        return session

    def no_session(self) -> dict:
        return {
            "session_id": None,
            "check_id": "chk_0123456789abcdef",
            "check_version": 1,
            "state": "none",
            "learner_turns": 0,
            "remaining": 0,
            "awaiting_tutor": False,
            "transcript": [],
            "attempt_id": None,
            "verdict": None,
            "criteria": [],
        }

    END_RESULT = {
        "attempt_id": "att_0123456789abcdef",
        "verdict": "partial",
        "evidence_class": "hinted",
        "next_action": "retry_attempt",
        "learner_turns": 3,
        "transcript_sha256": "a" * 64,
        "session_revision": 4,
        # `practice.end` commits one transition, so the backend answers with the *next* enrollment
        # revision while the graded card stays mounted on the old prop.
        "revision": 4,
        "criteria": [
            {"id": "t1", "met": True, "observed": "one ticket to Kyoto, please"},
            {"id": "t2", "met": True, "observed": "how much is it?"},
            {"id": "t3", "met": False, "observed": "target t3 not produced"},
            {"id": "turns", "met": True, "observed": "3 learner turns; the practice asks for 3 to 5"},
        ],
    }

    # -- start / transcript -------------------------------------------------------------------
    def test_start_practice_calls_the_route_and_shows_the_opening_once(self) -> None:
        result = self.live(
            {
                "mode": "start",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.no_session(),
                "started": self.active_session(learner_turns=0, remaining=5, awaiting_tutor=False,
                                               transcript=[{"ordinal": 1, "speaker": "tutor",
                                                            "text": "Welcome. Where are you travelling today?"}]),
                "appendTurn": "One ticket to Kyoto, please.",
            }
        )
        self.assertEqual(result["state"], "active")
        calls = [call for call in result["calls"] if call["method"].startswith("practice.")]
        methods = [call["method"] for call in calls]
        self.assertEqual(methods[0], "practice.state")
        self.assertIn("practice.start", methods)
        self.assertGreaterEqual(methods.count("practice.state"), 3)
        start = calls[methods.index("practice.start")]
        self.assertEqual(start["payload"], {"enrollment_id": "enr_0123456789abcdef", "objective_id": "obj_0123456789abcdef"})
        self.assertEqual(start["expected_revision"], 3)
        self.assertTrue(start["idempotency_key"].startswith("cb-practice-start-"))
        # The transcript is read, not accumulated: the learner turn appears once after two refreshes.
        self.assertEqual(result["turnCount"], 2, result["html"])
        self.assertEqual(result["text"].count("One ticket to Kyoto, please."), 1)
        # A practice is never submitted as a plain answer.
        self.assertNotIn("attempt.submit", [call["method"] for call in result["calls"]])
        self.assertEqual(result["feedbackCount"], 0)

    def test_every_practice_call_carries_the_branch_wire_version(self) -> None:
        result = self.live(
            {
                "mode": "start",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.no_session(),
                "started": self.active_session(),
            }
        )
        practice_calls = [call for call in result["calls"] if call["method"].startswith("practice.")]
        self.assertTrue(practice_calls)
        for call in practice_calls:
            self.assertEqual(call["contract_version"], 16, call)

    # -- end / feedback -----------------------------------------------------------------------
    def test_end_practice_grades_once_and_renders_one_feedback_line(self) -> None:
        result = self.live(
            {
                "mode": "end",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endResult": self.END_RESULT,
            }
        )
        methods = [call["method"] for call in result["calls"]]
        self.assertIn("practice.end", methods)
        self.assertNotIn("attempt.submit", methods)
        end = next(call for call in result["calls"] if call["method"] == "practice.end")
        self.assertEqual(end["payload"]["check_id"], "chk_0123456789abcdef")
        self.assertEqual(end["payload"]["check_version"], 1)
        self.assertTrue(end["payload"]["attempt_nonce"])
        self.assertEqual(end["expected_revision"], 3)
        # One compact line, built from the backend's own verdict and counts.
        self.assertEqual(result["feedbackCount"], 1, result["html"])
        self.assertEqual(
            result["feedback"],
            "Partly there: 2 of 3 target expressions used, over 3 learner turns.",
        )
        # The compact line does not change the verdict's words and shows no score.
        self.assertNotIn("%", result["text"])
        self.assertNotIn("score", result["text"].lower())
        # Criteria appear only under Review grading, exactly as returned.
        self.assertEqual(result["criteriaCount"], 4, result["html"])
        for observed in ("one ticket to Kyoto, please", "target t3 not produced",
                         "3 learner turns; the practice asks for 3 to 5"):
            self.assertIn(observed, result["text"])
        # The verdict is the focus target, not a vanished button.
        self.assertIn('tabindex="-1"', result["html"])

    def test_end_before_minimum_is_a_refusal_that_keeps_the_transcript(self) -> None:
        result = self.live(
            {
                "mode": "refuse",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endError": {
                    "code": "VALIDATION_FAILED",
                    "category": "validation",
                    "message": "this practice needs at least 3 learner turns; 1 are recorded.",
                    "retryable": False,
                    "details": {"reason": "practice_not_complete", "learner_turns": 1, "min_turns": 3},
                },
                "endResult": self.END_RESULT,
            }
        )
        self.assertEqual(result["refusal"], "practice_not_complete")
        self.assertIn("needs at least 3 learner turns", result["text"])
        self.assertIn("1 is recorded", result["text"])
        self.assertEqual(result["state"], "active")
        self.assertEqual(result["turnCount"], 2)
        # No verdict and no invented progress.
        self.assertEqual(result["feedbackCount"], 0)
        self.assertIn("End practice", result["buttons"])
        self.assertEqual(result["text"].count("One ticket to Kyoto, please."), 1)

    # -- the graded card's own retry (H-120c) --------------------------------------------------
    def test_practice_again_after_a_graded_end_fences_on_the_returned_revision(self) -> None:
        result = self.live(
            {
                "mode": "again",
                "revision": 3,
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endResult": self.END_RESULT,
                "started": self.active_session(
                    learner_turns=0,
                    remaining=5,
                    awaiting_tutor=False,
                    transcript=[
                        {"ordinal": 1, "speaker": "tutor",
                         "text": "Welcome. Where are you travelling today?"}
                    ],
                ),
            }
        )
        kinds = [call["method"] for call in result["calls"]]
        self.assertEqual(kinds.count("practice.end"), 1, result["html"])
        starts = [call for call in result["calls"] if call["method"] == "practice.start"]
        self.assertEqual(len(starts), 1, result["html"])
        # The card mounted on revision 3; the end returned revision 4. The retry must send the new one.
        self.assertEqual(starts[0]["expected_revision"], 4, result["html"])
        self.assertTrue(starts[0]["idempotency_key"].startswith("cb-practice-start-"))
        self.assertEqual(result["state"], "active")
        self.assertEqual(result["feedbackCount"], 0, result["html"])

    def test_a_stale_refusal_is_adopted_so_the_next_press_is_not_refused(self) -> None:
        result = self.live(
            {
                "mode": "stale",
                "revision": 3,
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endResult": self.END_RESULT,
                "startErrors": [
                    {
                        "code": "STALE_REVISION",
                        "category": "conflict",
                        "message": "the enrollment moved on before this practice started.",
                        "retryable": False,
                        "current_revision": 5,
                        "details": {"current_revision": 5},
                    }
                ],
                "started": self.active_session(
                    learner_turns=0,
                    remaining=5,
                    awaiting_tutor=False,
                    transcript=[
                        {"ordinal": 1, "speaker": "tutor",
                         "text": "Welcome. Where are you travelling today?"}
                    ],
                ),
            }
        )
        starts = [call for call in result["calls"] if call["method"] == "practice.start"]
        self.assertEqual([call["expected_revision"] for call in starts], [4, 5], result["html"])
        # The stale refusal is words, not a wire code, and it does not read as a lost practice.
        self.assertNotIn("STALE_REVISION", result["text"])
        self.assertEqual(result["state"], "active")

    def test_a_pass_does_not_offer_a_retry_the_backend_would_refuse(self) -> None:
        result = self.live(
            {
                "mode": "pass",
                "revision": 3,
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endResult": dict(
                    self.END_RESULT, verdict="pass", next_action="complete_objective"
                ),
            }
        )
        self.assertEqual(result["feedbackCount"], 1)
        # The pass closed the check: no button that would be refused with `practice_not_open`.
        self.assertNotIn("Practice again", result["buttons"])
        self.assertNotIn("Start practice", result["buttons"])
        self.assertIn("Review grading", result["buttons"])
        self.assertIn("This section is finished", result["text"])
        # The counter follows the graded card, not the still-`active` stored session.
        self.assertIn("Graded after 3 of at most 5 learner turns.", result["text"])
        self.assertNotIn("waiting for the tutor", result["text"])
        self.assertNotIn("CHECK_STALE", result["text"])

    def test_a_graded_card_does_not_answer_a_refusal_with_raw_wire_words(self) -> None:
        result = self.live(
            {
                "mode": "again",
                "revision": 3,
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
                "endResult": self.END_RESULT,
                "startErrors": [
                    {
                        "code": "CHECK_STALE",
                        "category": "conflict",
                        "message": "that practice check is not open for work.",
                        "retryable": False,
                        "details": {"reason": "practice_not_open", "check_state": "closed"},
                    }
                ],
            }
        )
        self.assertEqual(result["refusal"], "practice_not_open")
        self.assertIn("already graded", result["text"])
        # A learner on a graded card is never told to press Start practice, and never shown the code.
        self.assertNotIn("Press Start practice", result["text"])
        self.assertNotIn("CHECK_STALE", result["text"])

    def test_cancel_keeps_every_turn_and_is_never_graded(self) -> None:
        result = self.live(
            {
                "mode": "cancel",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(),
            }
        )
        methods = [call["method"] for call in result["calls"]]
        self.assertIn("practice.cancel", methods)
        self.assertNotIn("practice.end", methods)
        self.assertNotIn("attempt.submit", methods)
        cancel = next(call for call in result["calls"] if call["method"] == "practice.cancel")
        self.assertEqual(cancel["expected_revision"], 3)
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["turnCount"], 2)
        self.assertIn("Practice cancelled", result["text"])
        self.assertIn("check is still open", result["text"])
        self.assertEqual(result["feedbackCount"], 0)

    # -- targets ------------------------------------------------------------------------------
    def test_visible_targets_are_printed(self) -> None:
        result = self.live(
            {
                "mode": "hidden",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.no_session(),
            }
        )
        self.assertIn("Expressions to practise", result["text"])
        for label in ("one ticket to Kyoto, please", "how much is it?", "where is platform four?"):
            self.assertIn(label, result["text"])
        self.assertEqual(result["state"], "none")
        self.assertIn("Start practice", result["buttons"])

    def test_hidden_targets_are_withheld_even_when_the_payload_carries_them(self) -> None:
        result = self.live(
            {
                "mode": "hidden",
                "stimulus": self.stimulus(self.hidden_practice()),
                "session": self.no_session(),
            }
        )
        for label in ("one ticket to Kyoto, please", "how much is it?", "where is platform four?"):
            self.assertNotIn(label, result["text"])
        self.assertNotIn("Expressions to practise", result["text"])
        self.assertIn("not shown for this practice", result["text"])
        # The ids are not learner-facing text either.
        self.assertNotIn("t1", result["text"])

    # -- verdicts -----------------------------------------------------------------------------
    def test_a_needs_retry_verdict_reads_as_a_system_failure(self) -> None:
        result = self.live(
            {
                "mode": "graded",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(
                    state="graded",
                    learner_turns=3,
                    remaining=2,
                    verdict="needs_retry",
                    criteria=[],
                    attempt_id="att_0123456789abcdef",
                ),
            }
        )
        self.assertEqual(result["state"], "graded")
        self.assertEqual(result["feedbackCount"], 1)
        self.assertIn("saved", result["feedback"])
        self.assertIn("no verdict was recorded", result["feedback"])
        self.assertNotIn("Passed", result["text"])
        self.assertNotIn("Not yet", result["text"])
        self.assertIn("Practice again", result["buttons"])

    def test_a_not_yet_verdict_is_repeated_not_reworded(self) -> None:
        result = self.live(
            {
                "mode": "graded",
                "stimulus": self.stimulus(self.visible_practice()),
                "session": self.active_session(
                    state="graded",
                    learner_turns=4,
                    remaining=1,
                    verdict="not_yet",
                    criteria=[
                        {"id": "t1", "met": False, "observed": "target t1 not produced"},
                        {"id": "t2", "met": False, "observed": "target t2 not produced"},
                        {"id": "t3", "met": False, "observed": "target t3 not produced"},
                        {"id": "turns", "met": True, "observed": "4 learner turns; the practice asks for 3 to 5"},
                    ],
                    attempt_id="att_0123456789abcdef",
                ),
            }
        )
        self.assertEqual(result["feedback"], "Not yet: 0 of 3 target expressions used, over 4 learner turns.")
        # No alternative verdict vocabulary is invented for the §7.2 ambiguity.
        for phrase in ("incomplete", "failed", "try harder"):
            self.assertNotIn(phrase, result["text"].lower())

    # -- unavailable states -------------------------------------------------------------------
    def test_a_state_read_failure_offers_exactly_one_retry(self) -> None:
        result = self.live(
            {
                "mode": "unavailable",
                "stimulus": self.stimulus(self.visible_practice()),
                "stateError": {
                    "code": "HOST_UNAVAILABLE",
                    "category": "capability",
                    "message": "the backend is not reachable",
                    "retryable": True,
                },
            }
        )
        self.assertEqual(result["state"], "unavailable")
        self.assertIn("This practice could not be read", result["text"])
        self.assertIn("HOST_UNAVAILABLE", result["text"])
        self.assertEqual(result["buttons"].count("Retry"), 1)
        # No control that could grade or submit something unread.
        for button in ("Start practice", "End practice", "Cancel practice"):
            self.assertNotIn(button, result["buttons"])

    def test_a_build_without_practice_state_says_so_and_offers_a_re_read(self) -> None:
        result = self.live(
            {
                "mode": "unsupported",
                "stimulus": self.stimulus(self.visible_practice()),
                "runtimeMethods": ["check.open", "check.get"],
            }
        )
        self.assertEqual(result["state"], "unsupported")
        self.assertIn("does not implement practice.state", result["text"])
        self.assertEqual(result["buttons"].count("Re-read the backend"), 1)
        self.assertNotIn("Start practice", result["buttons"])
        # The read itself is never attempted on a build that declared it cannot serve it.
        self.assertNotIn("practice.state", [call["method"] for call in result["calls"]])

    # -- the answer form is not this surface --------------------------------------------------
    def test_a_practice_check_never_renders_the_written_answer_form(self) -> None:
        html = self.render(
            {
                "check": {
                    "check_id": "chk_0123456789abcdef",
                    "check_version": 1,
                    "evidence_target": "production",
                    "stimulus": self.stimulus(self.visible_practice()),
                },
                "implemented": ["check.open", "check.get", "practice.state", "practice.start"],
            }
        )
        self.assertIn("Conversation practice", html)
        self.assertIn("Buying one train ticket at a station counter", html)
        self.assertNotIn("Submit answer", html)
        self.assertNotIn("cb-attempt-answer", html)
        self.assertNotIn("Your answer", html)


class PracticeFeedbackCopyTest(unittest.TestCase):
    """The feedback line is a pure function: it must only repeat what it is handed."""

    def test_no_verdict_means_no_line(self) -> None:
        result = self._call({"verdict": None, "criteria": [], "learnerTurns": 0, "targets": []})
        self.assertIsNone(result)

    def _call(self, payload: dict):
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to evaluate the shipped module")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        with tempfile.TemporaryDirectory(prefix="coursebook-h120b-feedback-") as tmp:
            root = Path(tmp)
            (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "node_modules").mkdir()
            for name in ("react", "react-dom", "scheduler", "jsdom"):
                source = modules / name
                if source.is_dir():
                    (root / "node_modules" / name).symlink_to(source, target_is_directory=True)
            sdk = root / "node_modules" / "@hermes" / "plugin-sdk"
            sdk.mkdir(parents=True)
            (sdk / "package.json").write_text(
                json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
            )
            (sdk / "index.js").write_text(STUB, encoding="utf-8")
            (root / "run.mjs").write_text(
                "import { practiceFeedback } from './plugin.js'\n"
                "const payload = JSON.parse(process.argv[2])\n"
                "process.stdout.write(JSON.stringify({ line: practiceFeedback(payload) }))\n",
                encoding="utf-8",
            )
            done = subprocess.run(
                ["node", str(root / "run.mjs"), json.dumps(payload)],
                cwd=root, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            return json.loads(done.stdout)["line"]


PANE_HARNESS = r"""
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

const mod = await import('./plugin.js')
const sdk = await import('@hermes/plugin-sdk')

const checkId = 'chk_0123456789abcdef'
const calls = []
const practice = {
  scenario: 'Buying one train ticket at a station counter',
  learner_role: 'a traveller going to Kyoto',
  tutor_role: 'the station clerk',
  turns: { min: 3, max: 5 },
  targets: [
    { id: 't1', label: 'one ticket to Kyoto, please' },
    { id: 't2', label: 'how much is it?' },
    { id: 't3', label: 'where is platform four?' }
  ],
  targets_visible: true,
  rubric_angle: 'language_production',
  opening: 'Welcome. Where are you travelling today?'
}
const session = {
  session_id: 'ses_0123456789abcdef',
  check_id: checkId,
  check_version: 1,
  state: 'active',
  learner_turns: 3,
  remaining: 2,
  awaiting_tutor: false,
  transcript: [
    { ordinal: 1, speaker: 'tutor', text: 'Welcome. Where are you travelling today?' },
    { ordinal: 2, speaker: 'learner', text: 'One ticket to Kyoto, please.' },
    { ordinal: 3, speaker: 'tutor', text: 'Certainly. That is 1,200 yen.' },
    { ordinal: 4, speaker: 'learner', text: 'How much is it?' }
  ],
  attempt_id: null,
  verdict: null,
  criteria: []
}
const endResult = {
  attempt_id: 'att_0123456789abcdef',
  verdict: 'not_yet',
  evidence_class: 'hinted',
  next_action: 'retry_attempt',
  learner_turns: 3,
  transcript_sha256: 'b'.repeat(64),
  session_revision: 6,
  criteria: [
    { id: 't1', met: true, observed: 'one ticket to Kyoto, please' },
    { id: 't2', met: false, observed: 'target t2 not produced' },
    { id: 't3', met: false, observed: 'target t3 not produced' },
    { id: 'turns', met: true, observed: '3 learner turns; the practice asks for 3 to 5' }
  ]
}

const fakeRest = async (path, options = {}) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return {
      wire_version: 16,
      single_home_host: false,
      implemented_methods: [
        'binding.get',
        'library.list',
        'lesson.page',
        'review.queue',
        'check.open',
        'check.get',
        'practice.state',
        'practice.start',
        'practice.end',
        'practice.cancel'
      ]
    }
  }
  if (base === '/sessions/skill') return { skill: null }
  if (base !== '/rpc') return { reason: 'unrelated_session' }
  const body = options.body || {}
  calls.push({
    method: body.method,
    contract_version: body.contract_version,
    payload: body.payload || null,
    expected_revision: body.expected_revision ?? null
  })
  const ok = (result) => ({ ok: true, contract_version: 16, operation_id: body.operation_id, result })
  if (body.method === 'binding.get') {
    return ok({
      binding: {
        stored_session_id: 'sess_0123456789abcdef',
        enrollment_id: 'enr_0123456789abcdef',
        objective_id: 'obj_0123456789abcdef',
        status: 'active',
        profile: null,
        snapshot_failures: 0
      }
    })
  }
  if (body.method === 'library.list') {
    return ok({
      items: [
        {
          enrollment_id: 'enr_0123456789abcdef',
          title: 'Japanese cafe basics',
          revision: 3,
          recipe: 'learner',
          locale: 'ja',
          evidence_summary: { independent: 0, total_objectives: 4, current_objective_id: 'obj_0123456789abcdef' }
        }
      ]
    })
  }
  if (body.method === 'lesson.page') {
    return ok({
      revision: 3,
      section: { title: 'Order a drink', state: 'in_progress' },
      runtime: { binding_status: 'active', binding_id: 'bnd_0123456789abcdef' },
      sources: [],
      segments: []
    })
  }
  if (body.method === 'review.queue') return ok({ total_overdue: 0, items: [], total_upcoming: 0 })
  if (body.method === 'check.open') return ok({ check_id: checkId, check_version: 1, evidence_target: 'production' })
  if (body.method === 'check.get') {
    return ok({
      stimulus: {
        prompt: 'Practise buying a train ticket.',
        format: 'text',
        choices: [],
        learner_instructions: null,
        items: [],
        practice
      }
    })
  }
  if (body.method === 'practice.state') return ok(session)
  if (body.method === 'practice.end') return ok(endResult)
  if (body.method === 'practice.cancel') {
    return ok({ session_id: session.session_id, state: 'cancelled', revision: 3, session_revision: 6 })
  }
  return {
    ok: false,
    contract_version: 16,
    operation_id: body.operation_id,
    error: { code: 'UNKNOWN', category: 'internal', message: 'unexpected method ' + body.method }
  }
}

let pane = null
mod.default.register({
  rest: fakeRest,
  register: (contribution) => {
    if (contribution && contribution.id === 'pane') pane = contribution
  },
  onDispose: () => {}
})
const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))

sdk.host.state.focusedStoredSessionId = { get: () => 'sess_0123456789abcdef', subscribe: () => () => {} }
await act(async () => { root.render(React.createElement(pane.render)) })
await act(async () => { await new Promise((done) => setTimeout(done, 120)) })

const text = (document.body.textContent || '').replace(/\s+/g, ' ').trim()
const buttonByText = (label) =>
  Array.from(document.querySelectorAll('button')).find((button) => button.textContent.trim() === label)
const endButton = buttonByText('End practice')
if (endButton) {
  await act(async () => { endButton.click() })
  await act(async () => { await new Promise((done) => setTimeout(done, 150)) })
}
const after = (document.body.textContent || '').replace(/\s+/g, ' ').trim()
process.stdout.write(
  JSON.stringify({
    text,
    after,
    calls,
    buttons: Array.from(document.querySelectorAll('button')).map((button) => button.textContent.trim()),
    feedback: (() => {
      const node = document.querySelector('[data-cb-practice-feedback]')
      return node ? node.textContent.trim() : null
    })()
  })
)
"""


class PanePracticeControlTest(unittest.TestCase):
    """The bound pane itself, not a standalone component: the practice controls are its controls."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h120b-pane-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "pane.mjs").write_text(PANE_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_the_bound_pane_renders_and_runs_the_practice(self) -> None:
        result = subprocess.run(
            ["node", str(self.root / "pane.mjs")],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        observed = json.loads(result.stdout)
        # The pane is scoped to the binding and shows the practice declaration it read.
        self.assertIn("Order a drink", observed["text"])
        self.assertIn("Conversation practice", observed["text"])
        self.assertIn("one ticket to Kyoto, please", observed["text"])
        self.assertIn("End practice", observed["text"])
        self.assertIn("One ticket to Kyoto, please.", observed["text"])
        # Its End practice is the real route call, with the envelope the contract requires.
        end = [call for call in observed["calls"] if call["method"] == "practice.end"]
        self.assertEqual(len(end), 1, observed["calls"])
        self.assertEqual(end[0]["expected_revision"], 3)
        self.assertEqual(end[0]["contract_version"], 16)
        self.assertEqual(end[0]["payload"]["check_id"], "chk_0123456789abcdef")
        # One compact line, and no plain attempt path anywhere in the pane.
        self.assertIn("Not yet: 1 of 3 target expressions used, over 3 learner turns.", observed["feedback"])
        self.assertNotIn("attempt.submit", [call["method"] for call in observed["calls"]])


if __name__ == "__main__":
    unittest.main()
