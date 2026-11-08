"""H-178: the Field Stop — header, answer surface, integrity chip, close.

One learning surface: `STOP n OF m`, the section title, one objective sentence, one concept, one
check, one close. These cases render the shipped runtime module with ``react-dom/server`` and mount
the real ``AttemptControls`` under ``jsdom``, so the assertions are about the component the Desktop
mounts — not a description of it.

The integrity chip is proved on the only honest source: an ``attempt.submit`` / ``lesson.assist``
response's own ``evidence_class``, and the unconsumed event ``evidence.inspect`` returns. Nothing in
this file asserts a class the pane computed by itself.
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

STUB = SDK_STUB.replace(
    "export const Textarea = () => null",
    "export const Textarea = (props) =>\n"
    "  el('textarea', { id: props.id || null, rows: props.rows || null, 'data-cb-textarea': 'true' }, props.value || null)",
)

STATIC_HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { AttemptControls, EvidenceChip, evidenceChipView, PlayerClose, choiceAnswer } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

let out
if (payload.kind === 'chip') {
  out = renderToStaticMarkup(React.createElement(EvidenceChip, { value: payload.value, pending: payload.pending }))
} else if (payload.kind === 'chart') {
  out = JSON.stringify(['cold', 'hinted', 'answer_shown', 'self_reported', 'override', 'unknown'].map((value) => evidenceChipView(value)))
} else if (payload.kind === 'answer') {
  out = JSON.stringify(choiceAnswer(payload.choice))
} else if (payload.kind === 'close') {
  out = renderToStaticMarkup(
    React.createElement(PlayerClose, {
      section: { ordinal: 2 },
      progress: payload.progress || {},
      onBack: () => {},
      onReadSection: payload.readSection === false ? undefined : () => {},
      evidenceClass: payload.evidenceClass || null
    })
  )
} else {
  out = renderToStaticMarkup(
    React.createElement(AttemptControls, {
      enrollmentId: 'enr_0123456789abcdef',
      objectiveId: 'obj_0123456789abcdef',
      check: payload.check,
      revision: 3,
      implemented: new Set(payload.implemented || []),
      bindingState: 'active',
      stimulusStatus: 'ready',
      onRetryStimulus: () => {},
      onCommitted: () => {}
    })
  )
}
process.stdout.write(out)
"""

LIVE_HARNESS = """
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import plugin, { AttemptControls, useOpenCheck } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

const calls = []
let submitted = null
let nextClass = payload.startClass || 'cold'
const ctx = {
  register: () => {},
  onDispose: () => {},
  rest: async (path, options = {}) => {
    if (String(path).startsWith('/runtime')) {
      return { wire_version: 18, implemented_methods: payload.runtimeMethods || [], single_home_host: false }
    }
    const body = options.body || {}
    const data = body.payload || {}
    calls.push(body.method)
    if (body.method === 'lesson.assist') {
      nextClass = data.kind === 'answer_shown' ? 'answer_shown' : 'hinted'
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: { event_id: 'ev_' + data.kind, kind: data.kind, evidence_class: nextClass, revision: 4 }
      }
    }
    if (body.method === 'attempt.submit') {
      submitted = { answer: data.answer, check_id: data.check_id, revision: body.expected_revision }
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: {
          attempt_id: 'att_0123456789abcdef',
          verdict: payload.verdict || 'not_yet',
          evidence_class: nextClass,
          criteria: [{ id: 'c1', met: false, observed: payload.observed || 'the polite form was not used' }],
          next_action: 'retry_attempt',
          revision: 5
        }
      }
    }
    if (body.method === 'check.open') {
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: {
          check_id: 'chk_0123456789abcdef',
          check_version: 1,
          evidence_target: 'discrimination',
          revision: 3
        }
      }
    }
    if (body.method === 'check.get') {
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: {
          check_id: 'chk_0123456789abcdef',
          objective_id: 'obj_0123456789abcdef',
          check_version: 1,
          evidence_target: 'discrimination',
          state: 'open',
          audit_state: 'passed',
          attempt_count: payload.attemptCount === undefined ? 3 : payload.attemptCount,
          stimulus: payload.stimulus || null
        }
      }
    }
    if (body.method === 'evidence.inspect') {
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: {
          l1: { enrollment_id: 'enr_0123456789abcdef', objective_id: 'obj_0123456789abcdef', attempts: [], events: payload.events || [] },
          l2: {}, l3: {}, disputes: {}
        }
      }
    }
    return { ok: false, contract_version: 18, operation_id: body.operation_id, error: { code: 'UNKNOWN', category: 'internal', message: body.method } }
  }
}

plugin.register(ctx)

const root = createRoot(document.getElementById('root'))
let seenCheck = null
// `mode: "open"` mounts the shipped `useOpenCheck` and feeds its result to the same
// `AttemptControls` SectionPage renders, so the assertion covers the wiring (check.get →
// check object → chip) rather than a hand-built check payload handed straight to the component.
const OpenHost = () => {
  const open = useOpenCheck({
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    revision: 3,
    enabled: true,
    implemented: new Set(payload.implemented || ['check.get'])
  })
  seenCheck = open.check
  if (!open.check) return React.createElement('div', { 'data-cb-check-waiting': open.status })
  return React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: open.check,
    revision: 3,
    implemented: new Set(payload.implemented || ['check.get']),
    bindingState: 'active',
    stimulusStatus: open.stimulusStatus,
    onRetryStimulus: () => {},
    onCommitted: () => {}
  })
}
if (payload.mode === 'open') {
  root.render(React.createElement(OpenHost))
} else {
root.render(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: payload.check,
    revision: 3,
    implemented: new Set(payload.implemented || []),
    bindingState: 'active',
    stimulusStatus: 'ready',
    onRetryStimulus: () => {},
    onCommitted: () => {}
  })
)
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (predicate, timeout = 5000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return true
    await sleep(20)
  }
  return false
}
const button = (label) =>
  Array.from(document.querySelectorAll('button')).find((item) => item.textContent.trim() === label)
const chip = () => {
  const node = document.querySelector('[data-cb-evidence-chip]')
  return node ? { value: node.getAttribute('data-cb-evidence-chip'), text: node.textContent.replace(/\\s+/g, ' ').trim() } : null
}

await waitFor(() => document.querySelector('[data-cb-choice-group]'))
await sleep(200)
const group = document.querySelector('[data-cb-choice-group]')
const initial = chip()

if (payload.mode === 'assist') {
  button('I used a hint').click()
  await waitFor(() => chip() && chip().value === 'hinted')
}
const afterAssist = chip()

const keyEvent = new window.KeyboardEvent('keydown', { key: payload.key || '2', bubbles: true, cancelable: true })
const target = document.querySelector('[data-cb-choice="1"]') || group
target.dispatchEvent(keyEvent)
await sleep(80)
let keyWorked = Boolean(document.querySelector('[data-cb-choice-selected]').getAttribute('data-cb-choice-selected'))
if (!keyWorked) {
  // Fallback for a jsdom build whose synthetic key path drops the event: the pointer path must
  // reach the same state, and the recorded `selected` still proves the render, not the input.
  const option = document.querySelector('[data-cb-choice="2"]')
  option.click()
  await sleep(80)
}
const selected = document.querySelector('[data-cb-choice-selected]').getAttribute('data-cb-choice-selected')
const selectedText = document.querySelector('[data-cb-choice-answer]').textContent.trim()
const selectedOption = document.querySelector('[data-cb-choice="' + selected + '"]')
const selectedWords = selectedOption ? selectedOption.textContent.replace(/\\s+/g, ' ').trim() : null

button('Submit choice').click()
await waitFor(() => document.querySelector('[data-cb-verdict]'))
const afterSubmit = chip()

process.stdout.write(
  JSON.stringify({
    calls,
    submitted,
    initial,
    afterAssist,
    afterSubmit,
    selected,
    keyWorked,
    selectedText,
    selectedWords,
    checkKeys: seenCheck ? Object.keys(seenCheck) : null,
    attemptCount: seenCheck ? seenCheck.attempt_count : null,
    verdict: (document.querySelector('[data-cb-verdict]') || {}).getAttribute
      ? document.querySelector('[data-cb-verdict]').getAttribute('data-cb-verdict')
      : null,
    html: document.body.innerHTML
  })
)
"""


def choice_stimulus():
    return {
        "prompt": "Which expression is the polite way to ask a coworker to wait?",
        "format": "selection",
        "choices": ["ちょっと待って", "少々お待ちください", "待て", "待ってね"],
    }


def check_payload(**overrides):
    check = {
        "check_id": "chk_0123456789abcdef",
        "check_version": 1,
        "evidence_target": "discrimination",
        "attempt_count": 0,
        "stimulus": choice_stimulus(),
        # `check.get` never returns these; including them here proves the pane does not print them.
        "reference": {"kind": "exact", "answers": ["少々お待ちください"]},
        "accepted_answers": ["少々お待ちください"],
    }
    check.update(overrides)
    return check


class FieldStopBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h178-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "static.mjs").write_text(STATIC_HARNESS, encoding="utf-8")
        (root / "live.mjs").write_text(LIVE_HARNESS, encoding="utf-8")
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

    def run_harness(self, harness: str, payload: dict) -> str:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / harness), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2500:])
        return result.stdout

    def static(self, payload: dict) -> str:
        return self.run_harness("static.mjs", payload)

    def live(self, payload: dict) -> dict:
        return json.loads(self.run_harness("live.mjs", payload))


class IntegrityChipTest(FieldStopBase):
    """The chip changes from backend fields only, and says what the class means."""

    def test_every_backend_class_maps_to_one_label_and_one_sentence(self) -> None:
        chart = json.loads(self.static({"kind": "chart"}))
        by_value = {row["value"]: row for row in chart}
        self.assertEqual(by_value["cold"]["label"], "First try, no hints")
        self.assertEqual(by_value["hinted"]["label"], "Hinted")
        self.assertEqual(
            by_value["answer_shown"]["label"],
            "Answer shown — this attempt is no longer independent",
        )
        self.assertEqual(by_value["self_reported"]["label"], "Self-reported — you told us")
        self.assertEqual(by_value["override"]["label"], "Override — not independent evidence")
        for value in ("cold", "hinted", "answer_shown", "self_reported", "override"):
            self.assertTrue(by_value[value]["sentence"], value)
        self.assertIsNone(by_value["unknown"]["sentence"])

    def test_the_chip_renders_its_class_and_pending_marker(self) -> None:
        html = self.static({"kind": "chip", "value": "answer_shown", "pending": True})
        self.assertIn('data-cb-evidence-chip="answer_shown"', html)
        self.assertIn('data-cb-evidence-pending="true"', html)
        self.assertIn("Answer shown — this attempt is no longer independent", html)
        self.assertIn("if you submit now", html)
        self.assertNotIn("%", html)

    def test_no_class_renders_no_chip(self) -> None:
        self.assertEqual(self.static({"kind": "chip", "value": None}), "")

    def test_an_uncommitted_hint_event_names_the_next_attempt(self) -> None:
        out = self.live(
            {
                "check": check_payload(attempt_count=0),
                "implemented": ["check.get", "lesson.assist", "evidence.inspect"],
                "events": [
                    {
                        "evidence_id": "ev_hint",
                        "objective_id": "obj_0123456789abcdef",
                        "attempt_id": None,
                        "layer": 1,
                        "kind": "hint_request",
                        "evidence_class": "hinted",
                        "is_action": True,
                        "created_at": "2026-11-08T10:00:00+00:00",
                    }
                ],
                "mode": "plain",
            }
        )
        self.assertEqual(out["initial"]["value"], "hinted")
        self.assertIn("A hint was recorded before this answer", out["initial"]["text"])

    def test_a_prior_committed_attempt_is_at_least_hinted(self) -> None:
        out = self.live({"check": check_payload(attempt_count=1), "implemented": ["check.get"], "mode": "plain"})
        self.assertEqual(out["initial"]["value"], "hinted")

    def test_the_shipped_hook_carries_check_get_attempt_count_to_the_chip(self) -> None:
        """The retry chip must read `attempt_count` through `useOpenCheck`, not a fixture.

        `check.open` returns identity only; `check.get` is the read that reports `attempt_count`.
        A merge that drops it makes the second attempt print "First try, no hints" while the
        backend commits `hinted`.
        """
        out = self.live(
            {
                "mode": "open",
                "attemptCount": 3,
                "stimulus": choice_stimulus(),
                "implemented": ["check.get"],
            }
        )
        self.assertIn("check.open", out["calls"])
        self.assertIn("check.get", out["calls"])
        self.assertIn("attempt_count", out["checkKeys"])
        self.assertEqual(out["attemptCount"], 3)
        self.assertEqual(out["initial"]["value"], "hinted")
        self.assertIn("A hint was recorded before this answer", out["initial"]["text"])

    def test_the_shipped_hook_keeps_a_first_attempt_cold(self) -> None:
        out = self.live(
            {
                "mode": "open",
                "attemptCount": 0,
                "stimulus": choice_stimulus(),
                "implemented": ["check.get"],
            }
        )
        self.assertEqual(out["attemptCount"], 0)
        self.assertEqual(out["initial"]["value"], "cold")

    def test_a_first_attempt_is_cold_and_the_hint_changes_it_from_the_response(self) -> None:
        out = self.live(
            {
                "check": check_payload(attempt_count=0),
                "implemented": ["check.get", "lesson.assist", "evidence.inspect"],
                "events": [],
                "mode": "assist",
            }
        )
        self.assertEqual(out["initial"]["value"], "cold")
        self.assertEqual(out["afterAssist"]["value"], "hinted")
        self.assertIn("lesson.assist", out["calls"])
        self.assertEqual(out["afterSubmit"]["value"], "hinted")
        # The assist returned revision 4; the submit after it must fence on that revision, not the
        # page's stale 3, or the backend refuses it as STALE_REVISION (review round 1, item 3).
        self.assertEqual(out["submitted"]["revision"], 4)


class ChoiceSurfaceTest(FieldStopBase):
    """A choice check is a real answer surface, and it submits the served choice."""

    def test_the_choice_check_renders_a_radiogroup_not_a_textarea(self) -> None:
        html = self.static(
            {"check": check_payload(), "implemented": ["check.get", "lesson.assist", "evidence.inspect"]}
        )
        self.assertIn('role="radiogroup"', html)
        self.assertIn('data-cb-choice-group="4"', html)
        for number in ("1", "2", "3", "4"):
            self.assertIn(f'data-cb-choice="{number}"', html)
        self.assertIn("Nothing selected yet.", html)
        self.assertIn("Submit choice", html)
        self.assertNotIn("data-cb-textarea", html)
        self.assertIn("Press 1–4", html)

    def test_the_written_check_keeps_a_first_class_textarea(self) -> None:
        check = check_payload()
        check["stimulus"] = {**choice_stimulus(), "format": "text", "choices": []}
        html = self.static({"check": check, "implemented": ["check.get"]})
        self.assertIn("data-cb-textarea", html)
        self.assertIn("Submit answer", html)
        self.assertNotIn('role="radiogroup"', html)

    def test_keyboard_selection_and_the_submitted_payload(self) -> None:
        out = self.live({"check": check_payload(), "implemented": ["check.get"], "mode": "plain", "key": "2"})
        self.assertTrue(out["keyWorked"], out)
        self.assertEqual(out["selected"], "2")
        self.assertIn("Selected: 2. 少々お待ちください", out["selectedText"])
        self.assertIn("Selected", out["selectedWords"])
        self.assertEqual(
            out["submitted"]["answer"],
            {"kind": "selection", "selection": ["少々お待ちください"], "text": "少々お待ちください"},
        )

    def test_the_reference_answer_is_never_printed(self) -> None:
        html = self.static({"check": check_payload(), "implemented": ["check.get"]})
        self.assertIn("少々お待ちください", html)  # it is one of the authored choices
        self.assertNotIn("reference", html)
        self.assertNotIn("accepted_answers", html)

    def test_the_submit_builds_a_contract_shaped_answer(self) -> None:
        answer = json.loads(self.static({"kind": "answer", "choice": "少々お待ちください"}))
        self.assertEqual(answer["kind"], "selection")
        self.assertEqual(answer["selection"], ["少々お待ちください"])
        self.assertEqual(answer["text"], "少々お待ちください")


class FieldStopCloseTest(FieldStopBase):
    """The close is one authored beat: the chip, the trail, and the reference."""

    def test_the_close_leads_back_to_the_trail_and_offers_the_section(self) -> None:
        html = self.static(
            {"kind": "close", "progress": {"total_objectives": 4, "independent": 3, "review_due": 0}, "evidenceClass": "cold"}
        )
        self.assertIn("You finished Section 2", html)
        self.assertIn("3 of 4 with evidence", html)
        self.assertIn("Return to the trail", html)
        self.assertIn("Read the section", html)
        self.assertIn('data-cb-evidence-chip="cold"', html)
        self.assertEqual(html.count('data-variant="default"'), 1)
        for word in ("%", "XP", "streak", "confetti", "score", "mastered"):
            self.assertNotIn(word, html)

    def test_without_a_section_callback_there_is_no_second_action(self) -> None:
        html = self.static({"kind": "close", "progress": {}, "readSection": False})
        self.assertNotIn("Read the section", html)
        self.assertIn("Return to the trail", html)

    def test_no_companion_is_invented_when_the_host_has_none(self) -> None:
        html = self.static({"kind": "close", "progress": {}})
        self.assertNotIn("data-cb-player-gate", html)
        self.assertNotIn("study companion", html)

    def test_a_close_without_a_recorded_class_prints_no_chip(self) -> None:
        """A stop with no check finishes without an attempt; nothing was earned, so nothing is claimed."""
        html = self.static({"kind": "close", "progress": {}})
        self.assertIn("Return to the trail", html)
        self.assertNotIn("data-cb-evidence-chip", html)


class FieldStopHonestyTest(unittest.TestCase):
    """Source invariants the render cannot see."""

    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_the_pane_never_leaks_the_reference_answer(self) -> None:
        controls = self.source.split("function AttemptControls(", 1)[1].split("function NotebookSaveDialog(", 1)[0]
        for token in ("accepted_answers", "reference_answer", "check_spec_withheld"):
            self.assertNotIn(token, controls)

    def test_the_assist_control_records_before_the_answer(self) -> None:
        controls = self.source.split("function AttemptControls(", 1)[1].split("function NotebookSaveDialog(", 1)[0]
        self.assertIn("lesson.assist", controls)
        self.assertIn("hint_request", controls)
        self.assertIn("answer_shown", controls)

    def test_no_timer_streak_or_score_is_added(self) -> None:
        player = self.source.split("H-149 · the lesson player", 1)[1].split("\nfunction LessonDocumentView(", 1)[0]
        for word in ("XP", "streak", "percent", "confetti", "mastery", "league", "score", "timer"):
            self.assertNotIn(word, player, word)


if __name__ == "__main__":
    unittest.main()
