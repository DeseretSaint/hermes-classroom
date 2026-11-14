"""UP-15 — "I saw the answer" must show an answer, not only charge for one.

At HEAD the control's confirm promised the attempt would be marked "answer shown" and then
recorded the event while displaying nothing: the reference never leaves the backend, and the
control had no content of its own. A stuck learner paid the whole price of seeing an answer that
was never shown.

The change discloses the section's **authored worked example** — the `example` block `lesson.page`
already projects from `worked_example` (`coursebook/lesson_document.py`) and the Textbook view
already paints. It is a solved case, not the check's key, so no backend field is added, no
reference answer crosses the wire, and the event still records `evidence_class: answer_shown`.

Three claims are pinned here, on the shipped module:

1. after the confirm, the control renders the worked answer (prompt, steps, worked answer) beside
   the used flag — `test_the_answer_shown_control_renders_a_worked_answer`, the acceptance test;
2. a section with no authored worked example never promises one, and its confirmed state is the
   flag alone (the pre-change behaviour stays the honest one for that section);
3. `workedAnswerFromPage` refuses a block that restates the open check's own prompt, because that
   block is the check's case and disclosing it would be disclosing the key.

What this does NOT prove: that a live Desktop window paints these states. Evidence here is the
shipped source and the unit harness only (owner directive 2026-11-12).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
LEARNING_SRC = ROOT / "desktop" / "src" / "70-learning.js"

#: The authored worked example a generated section carries. It is deliberately a different solved
#: case from the check prompt below, exactly as `document_from_page` projects it: `headline` is the
#: worked prompt and `deep` is the steps plus the worked answer.
WORKED = {
    "prompt": "A worked example: round 42.7 to the nearest whole number",
    "body": "Find the digit after the decimal point: 7.\n7 is five or more, so round up.\nAnswer: 43",
    "short": "7 rounds 42.7 up to 43.",
}

STIMULUS = {"prompt": "Round 18.4 to the nearest whole number.", "format": "text", "items": []}

HARNESS = r"""
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import * as mod from './plugin.js'

// Tolerant by design: at HEAD there is no `workedAnswerFromPage` export, and the acceptance must
// fail on the defect (a confirmed control that renders only the used flag), not on an import
// error that hides which claim broke.
const plugin = mod.default
const AttemptControls = mod.AttemptControls
const workedAnswerFromPage = mod.workedAnswerFromPage || (() => null)

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

// The pure derivation first: it needs no mount, and the key-refusal claim is about the function.
const derivation = {}
if (payload.derivation) {
  const source = payload.derivation
  const page = {
    document: {
      blocks: [
        { id: 'blk_orient', role: 'orient', headline: 'Why rounding matters', deep: 'Text', media: [] },
        source.block
      ]
    }
  }
  const view = workedAnswerFromPage(page, source.stimulus || null)
  derivation.view = view
  derivation.present = Boolean(view)
  const empty = workedAnswerFromPage({ document: { blocks: [] } }, source.stimulus || null)
  derivation.emptyIsNull = empty === null
}

const rpcCalls = []
const ctx = {
  register: () => {},
  onDispose: () => {},
  rest: async (path, options = {}) => {
    if (String(path).startsWith('/runtime')) {
      return { wire_version: 18, implemented_methods: [], single_home_host: false }
    }
    const body = options.body || {}
    const data = body.payload || {}
    if (body.method === 'lesson.assist') {
      rpcCalls.push({ method: body.method, kind: data.kind })
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: { event_id: 'ev_' + data.kind, kind: data.kind, evidence_class: 'answer_shown', revision: 4 }
      }
    }
    if (body.method === 'evidence.inspect') {
      return {
        ok: true,
        contract_version: 18,
        operation_id: body.operation_id,
        result: {
          l1: { enrollment_id: 'enr_0123456789abcdef', objective_id: 'obj_0123456789abcdef', attempts: [], events: [] },
          l2: {}, l3: {}, disputes: {}
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
          attempt_count: 0,
          stimulus: payload.stimulus || null
        }
      }
    }
    return { ok: false, contract_version: 18, operation_id: body.operation_id, error: { code: 'UNKNOWN', category: 'internal', message: body.method } }
  }
}

plugin.register(ctx)

const root = createRoot(document.getElementById('root'))
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (predicate, timeout = 5000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return true
    await sleep(20)
  }
  return false
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()

const output = { derivation }
const props = {
  enrollmentId: 'enr_0123456789abcdef',
  objectiveId: 'obj_0123456789abcdef',
  check: {
    check_id: 'chk_0123456789abcdef',
    check_version: 1,
    evidence_target: 'discrimination',
    state: 'open',
    attempt_count: 0,
    stimulus: payload.stimulus || null
  },
  revision: 3,
  implemented: new Set(['lesson.assist', 'evidence.inspect']),
  bindingState: 'active',
  stimulusStatus: 'ready',
  onRetryStimulus: () => {},
  onCommitted: () => {}
}
if (payload.workedAnswer) props.workedAnswer = payload.workedAnswer

root.render(React.createElement(AttemptControls, props))
await waitFor(() => document.querySelector('[data-cb-assist-answer]'))
await sleep(150)

const trigger = () => document.querySelector('[data-cb-assist-answer]')
const confirm = () => document.querySelector('[data-cb-assist-confirm]')
const yesButton = () => document.querySelector('[data-cb-answer-confirm-yes]')
const used = () => document.querySelector('[data-cb-assist-used="answer_shown"]')
const worked = () => document.querySelector('[data-cb-assist-worked-example]')

if (!trigger()) {
  output.error = 'the answer disclosure control never rendered'
} else {
  trigger().click()
  await sleep(150)
  const beforeConfirm = {
    confirmOpen: Boolean(confirm()),
    consequence: text(confirm()),
    writes: rpcCalls.length
  }
  yesButton().click()
  await waitFor(() => used())
  await sleep(150)
  output.confirmed = {
    used: text(used()),
    assistState: (document.querySelector('[data-cb-assist]') || {}).getAttribute
      ? document.querySelector('[data-cb-assist]').getAttribute('data-cb-assist-state')
      : null,
    kinds: rpcCalls.filter((call) => call.method === 'lesson.assist').map((call) => call.kind),
    writes: rpcCalls.length,
    workedPresent: Boolean(worked()),
    workedText: text(worked()),
    workedPrompt: text(document.querySelector('[data-cb-assist-worked-prompt]')),
    workedBody: text(document.querySelector('[data-cb-assist-worked-body]')),
    workedIsLabelled: Boolean(worked() && worked().getAttribute('aria-labelledby') === 'cb-worked-answer-heading'),
    triggerGone: !trigger(),
    text: text(document.querySelector('[data-cb-assist]'))
  }
  output.beforeConfirm = beforeConfirm
}

process.stdout.write(JSON.stringify(output))
"""


class _Rig(unittest.TestCase):
    """One staged copy of the shipped module, mounted in jsdom by a Node harness."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to mount a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-up15-")
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
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def drive(self, payload: dict) -> dict:
        root = Path(self.tmp.name)
        case = root / "payload.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        done = subprocess.run(
            ["node", str(root / "harness.mjs"), str(case)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(done.returncode, 0, f"harness failed:\n{done.stdout}\n{done.stderr}")
        return json.loads(done.stdout)


class AnswerShownDisclosesAWorkedAnswerTest(_Rig):
    """The acceptance: the confirmed control renders a worked answer, not only the penalty."""

    def test_the_answer_shown_control_renders_a_worked_answer(self) -> None:
        out = self.drive({"stimulus": STIMULUS, "workedAnswer": WORKED})
        self.assertNotIn("error", out, out.get("error"))
        before = out["beforeConfirm"]
        self.assertTrue(before["confirmOpen"], "the first press did not open a confirm")
        self.assertEqual(before["writes"], 0, "the first press wrote lesson.assist")

        confirmed = out["confirmed"]
        # The acceptance claim, first: the confirmed control must render the worked answer it
        # charged for. At HEAD this is the assertion that fails — the flag is all there is.
        self.assertTrue(confirmed["workedPresent"], "the confirmed control rendered only the used flag")
        # The event is unchanged: one write, `answer_shown`.
        self.assertEqual(confirmed["writes"], 1, "the confirm did not write exactly one assist event")
        self.assertEqual(confirmed["kinds"], ["answer_shown"])
        self.assertEqual(confirmed["assistState"], "answer_shown")
        self.assertIn("Answer shown", confirmed["used"])
        self.assertTrue(confirmed["triggerGone"], "the disclosure control survived the recorded answer")

        # The sentence now names the content the confirm actually produces.
        self.assertIn("worked example", before["consequence"])
        self.assertIn("cannot count as independent evidence", before["consequence"])

        # ...and the control now shows the answer it charged for.
        self.assertIn(WORKED["prompt"], confirmed["workedPrompt"])
        self.assertIn("Find the digit after the decimal point: 7.", confirmed["workedBody"])
        self.assertIn("Answer: 43", confirmed["workedBody"])
        self.assertIn("Worked example", confirmed["workedText"])
        self.assertTrue(confirmed["workedIsLabelled"], "the worked answer is not a labelled region")
        # It says what it is: a worked example, not the check's key.
        self.assertIn("not the check’s own answer", confirmed["workedText"])


class NoWorkedAnswerSectionTest(_Rig):
    """A section with no authored worked answer is never asked to confirm a disclosure it lacks."""

    def test_a_section_without_a_worked_answer_does_not_promise_one(self) -> None:
        out = self.drive({"stimulus": STIMULUS, "workedAnswer": None})
        self.assertNotIn("error", out, out.get("error"))
        consequence = out["beforeConfirm"]["consequence"]
        self.assertIn("no worked example on file", consequence)
        self.assertNotIn("shows the worked example", consequence)
        self.assertIn("cannot count as independent evidence", consequence)
        confirmed = out["confirmed"]
        self.assertEqual(confirmed["kinds"], ["answer_shown"], "the route still records the disclosure")
        self.assertFalse(confirmed["workedPresent"], "a worked answer appeared for a section with none")
        self.assertIn("Answer shown", confirmed["used"])


class WorkedAnswerRefusesTheCheckKeyTest(_Rig):
    """The derivation discloses an authored solved case — never the check's own case."""

    def test_a_block_that_restates_the_check_prompt_is_refused(self) -> None:
        same = {
            "prompt": "Round 18.4 to the nearest whole number",
            "body": "4 is less than five, so round down.\nAnswer: 18",
            "short": "18.4 rounds down to 18.",
        }
        out = self.drive(
            {
                "stimulus": STIMULUS,
                "workedAnswer": None,
                "derivation": {
                    "block": {
                        "id": "blk_example",
                        "role": "example",
                        "headline": same["prompt"],
                        "deep": same["body"],
                        "short": same["short"],
                        "media": [],
                    },
                    "stimulus": STIMULUS,
                },
            }
        )
        self.assertNotIn("error", out, out.get("error"))
        derivation = out["derivation"]
        self.assertFalse(
            derivation["present"],
            "a worked example that restates the check prompt is the check's key and must be refused",
        )
        self.assertTrue(derivation["emptyIsNull"])

    def test_a_different_solved_case_is_disclosed(self) -> None:
        out = self.drive(
            {
                "stimulus": STIMULUS,
                "workedAnswer": None,
                "derivation": {
                    "block": {
                        "id": "blk_example",
                        "role": "example",
                        "headline": WORKED["prompt"],
                        "deep": WORKED["body"],
                        "short": WORKED["short"],
                        "media": [],
                    },
                    "stimulus": STIMULUS,
                },
            }
        )
        derivation = out["derivation"]
        self.assertTrue(derivation["present"], "the authored worked example was not disclosed")
        self.assertEqual(derivation["view"]["prompt"], WORKED["prompt"])
        self.assertEqual(derivation["view"]["body"], WORKED["body"])


class ShippedSourceTest(unittest.TestCase):
    """The shipped source keeps the disclosure on the same one-write path the confirm always had."""

    def setUp(self) -> None:
        self.source = LEARNING_SRC.read_text(encoding="utf-8")

    def test_the_answer_shown_write_is_still_answer_shown(self) -> None:
        calls = re.findall(r"recordAssist\(\s*'answer_shown'\s*\)", self.source)
        self.assertEqual(len(calls), 1, f"expected one answer_shown write, found {len(calls)}")

    def test_the_confirmed_state_renders_the_worked_answer_beside_the_flag(self) -> None:
        # The used-state branch must mount the panel; a flag alone is the defect this card fixes.
        branch = re.search(
            r"answerUsed\s*\?\s*jsxs\('div',\s*\{\s*'data-cb-assist-answer-shown'",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(branch, "the confirmed answer state is not a group that can hold the worked answer")
        assert branch is not None
        start = branch.start()
        end = self.source.find(": answerConfirmOpen", start)
        self.assertNotEqual(end, -1)
        self.assertIn("WorkedAnswerPanel", self.source[start:end])

    def test_no_job_or_stage_vocabulary_reaches_the_worked_answer_note(self) -> None:
        panel = re.search(r"function WorkedAnswerPanel\(\{ workedAnswer \}\)(.*?)\n}\n", self.source, re.DOTALL)
        self.assertIsNotNone(panel)
        assert panel is not None
        for banned in ("job_id", "stage", "reason_code", "evidence_class"):
            self.assertNotIn(banned, panel.group(1), f"{banned} leaked onto the worked-answer panel")


if __name__ == "__main__":
    unittest.main()
