"""U2 (item 25) — "I saw the answer" must ask before it downgrades the attempt.

``docs/ADVERSARIAL-E2E-2026-11-12.md`` §U2: the text-weight "I saw the answer" button beside Submit
called ``lesson.assist(kind:'answer_shown')`` on the first press, with no consequence sentence, no
confirm and no way back, and the next committed attempt could never be ``independent`` again. One
low-emphasis misclick permanently downgraded the record.

The contract this file pins, on the shipped module:

1. the first press writes nothing and replaces itself with one consequence sentence and a confirm;
2. cancel writes nothing and leaves the attempt exactly as it was;
3. a refused write keeps the confirm open with the refusal beside its buttons, so the learner can
   decide again;
4. focus moves into the confirm on open and back to the assist group on close, never on mount;
5. the confirm is the only path that ever sends ``lesson.assist(kind:'answer_shown')``.

The plugin is one ESM file, so the harness mounts the shipped ``AttemptControls`` in jsdom with the
stub ``@hermes/plugin-sdk`` and the plugin's own ``ctx.rest`` seam, then drives it with real clicks.
Every write the surface makes lands in a recorded list, so a click that sends nothing is a missing
entry rather than something inferred from the DOM.

What this does NOT prove: that a live Desktop window paints these states. Evidence here is the
shipped source and the unit harness only.
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

HARNESS = r"""
import React from 'react'
import { createRoot } from 'react-dom/client'
import { JSDOM } from 'jsdom'
import plugin, { AttemptControls } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
for (const name of ['HTMLElement', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent']) {
  if (globalThis[name] === undefined) globalThis[name] = dom.window[name]
}
globalThis.IS_REACT_ACT_ENVIRONMENT = false

// The plugin's own rpc seam. Every write lands in `rpcCalls` with its kind, so "the first press sent
// nothing" is a measured empty list, not a claim about the markup.
const rpcCalls = []
const refusals = Number(payload.refuseAssistFirst || 0)
let assistAttempts = 0
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
      assistAttempts += 1
      if (assistAttempts <= refusals) {
        return {
          ok: false,
          contract_version: 18,
          operation_id: body.operation_id,
          error: { code: 'REVISION_CONFLICT', category: 'conflict', message: 'The lesson moved on before this was recorded.' }
        }
      }
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

root.render(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: {
      check_id: 'chk_0123456789abcdef',
      check_version: 1,
      evidence_target: 'discrimination',
      state: 'open',
      attempt_count: 0,
      stimulus: payload.stimulus || { prompt: 'Which form is polite?', items: [] }
    },
    revision: 3,
    implemented: new Set(['lesson.assist', 'evidence.inspect']),
    bindingState: 'active',
    stimulusStatus: 'ready',
    onRetryStimulus: () => {},
    onCommitted: () => {}
  })
)
await waitFor(() => document.querySelector('[data-cb-assist-answer]'))
await sleep(150)

const output = {}
const trigger = () => document.querySelector('[data-cb-assist-answer]')
const confirm = () => document.querySelector('[data-cb-assist-confirm]')
const assistGroup = () => document.querySelector('[data-cb-assist]')
const yesButton = () => document.querySelector('[data-cb-answer-confirm-yes]')
const cancelButton = () => document.querySelector('[data-cb-answer-confirm-cancel]')
const assistWrites = () => rpcCalls.filter((call) => call.method === 'lesson.assist').length
const focusInside = (node) => Boolean(node && document.activeElement && node.contains(document.activeElement))
const focusName = () => {
  const node = document.activeElement
  if (!node || node === document.body) return 'body'
  if (confirm() && confirm().contains(node)) return 'confirm'
  if (assistGroup() && assistGroup().contains(node)) return 'assist-group'
  return 'other'
}

// 4. Mount: nothing has been pressed, so nothing may take focus away from the page.
output.mountFocus = focusName()

if (!trigger()) {
  output.error = 'the answer disclosure control never rendered'
} else {
  // 1. One press: the consequence opens; nothing is written.
  trigger().click()
  await sleep(150)
  const firstPress = {
    confirmOpen: Boolean(confirm()),
    triggerGone: !trigger(),
    writes: assistWrites(),
    consequence: text(confirm()),
    yesLabel: text(yesButton()),
    cancelLabel: text(cancelButton()),
    focus: focusName(),
    refusalsShown: document.querySelectorAll('[role="alert"]').length
  }

  // 3. A refused write keeps the confirm open, prints the refusal beside the buttons and leaves the
  // learner able to try again.
  let refused = null
  if (refusals > 0) {
    yesButton().click()
    await waitFor(() => document.querySelector('[data-cb-answer-confirm-error]'))
    await sleep(120)
    refused = {
      confirmOpen: Boolean(confirm()),
      writes: assistWrites(),
      refusal: text(document.querySelector('[data-cb-answer-confirm-error]')),
      refusalIsAlert: Boolean(document.querySelector('[data-cb-answer-confirm-error][role="alert"]')),
      focus: focusName(),
      yesStillThere: Boolean(yesButton())
    }
  }

  // 2. Cancel: back to an untouched attempt, and still nothing written.
  cancelButton().click()
  await sleep(150)
  const afterCancel = {
    confirmOpen: Boolean(confirm()),
    triggerBack: Boolean(trigger()),
    writes: assistWrites(),
    focus: focusName()
  }

  // 5. Ask again, then confirm: exactly one write, of one kind, and the used state takes over.
  trigger().click()
  await sleep(80)
  yesButton().click()
  await waitFor(() => document.querySelector('[data-cb-assist-used="answer_shown"]'))
  await sleep(150)
  const afterConfirm = {
    writes: assistWrites(),
    kinds: rpcCalls.filter((call) => call.method === 'lesson.assist').map((call) => call.kind),
    used: text(document.querySelector('[data-cb-assist-used="answer_shown"]')),
    triggerGone: !trigger(),
    confirmOpen: Boolean(confirm()),
    focus: focusName()
  }

  output.assist = { firstPress, refused, afterCancel, afterConfirm }
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-u2-")
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


class AnswerDisclosureConfirmTest(_Rig):
    """U2: the answer disclosure asks before it writes, and writes once."""

    def test_first_press_writes_nothing_and_only_the_confirm_writes(self) -> None:
        out = self.drive({"mode": "assist"})
        self.assertNotIn("error", out, out.get("error"))
        assist = out["assist"]

        # 4. A card that mounts with the confirm closed never moves focus.
        self.assertEqual(out["mountFocus"], "body", "a fresh AttemptControls stole focus on mount")

        first = assist["firstPress"]
        self.assertTrue(first["confirmOpen"], "the first press did not open a confirm")
        self.assertTrue(first["triggerGone"], "the one-click control is still on screen")
        self.assertEqual(first["writes"], 0, "the first press wrote lesson.assist")
        # The consequence is an explicit sentence about what the click costs, not a shrug.
        self.assertIn("answer shown", first["consequence"])
        self.assertIn("cannot count as independent evidence", first["consequence"])
        self.assertIn("cannot be undone", first["consequence"])
        self.assertIn("Yes", first["yesLabel"])
        self.assertEqual(first["cancelLabel"], "Cancel")
        self.assertEqual(first["focus"], "confirm", "focus did not move into the confirm")

        cancelled = assist["afterCancel"]
        self.assertFalse(cancelled["confirmOpen"], "cancel left the confirm open")
        self.assertTrue(cancelled["triggerBack"], "cancel did not return the original control")
        self.assertEqual(cancelled["writes"], 0, "cancelling wrote lesson.assist")
        self.assertEqual(cancelled["focus"], "assist-group", "focus did not return to the assist group")

        confirmed = assist["afterConfirm"]
        self.assertEqual(confirmed["writes"], 1, "the confirm did not write exactly one assist event")
        self.assertEqual(confirmed["kinds"], ["answer_shown"])
        self.assertIn("Answer shown", confirmed["used"])
        self.assertTrue(confirmed["triggerGone"], "the answer link survived the recorded answer")
        self.assertFalse(confirmed["confirmOpen"], "the confirm stayed open after a recorded answer")

    def test_a_refused_write_keeps_the_confirm_open_with_the_refusal(self) -> None:
        out = self.drive({"mode": "assist", "refuseAssistFirst": 1})
        self.assertNotIn("error", out, out.get("error"))
        assist = out["assist"]

        refused = assist["refused"]
        self.assertIsNotNone(refused, "the refusal case never ran")
        self.assertEqual(refused["writes"], 0, "a refused write was counted as a write")
        self.assertTrue(refused["confirmOpen"], "the confirm closed itself on a refused write")
        self.assertTrue(refused["yesStillThere"], "the learner was left with nothing to press")
        self.assertTrue(refused["refusalIsAlert"], "the refusal is not announced as an alert")
        self.assertIn("moved on before this was recorded", refused["refusal"])

        # The learner can still decide again: cancel writes nothing, and a second confirm succeeds.
        self.assertEqual(assist["afterCancel"]["writes"], 0)
        self.assertEqual(assist["afterConfirm"]["writes"], 1)
        self.assertEqual(assist["afterConfirm"]["kinds"], ["answer_shown"])


class OneWritePathTest(unittest.TestCase):
    """The shipped source has exactly one `answer_shown` write, and the first press cannot reach it."""

    def setUp(self) -> None:
        self.source = LEARNING_SRC.read_text(encoding="utf-8")

    def test_the_first_press_calls_a_local_opener_and_is_not_a_write(self) -> None:
        # `data-cb-assist-answer` is the control the learner presses first; its handler must be the
        # local opener, never `recordAssist`.
        trigger = re.search(
            r"data-cb-assist-answer'.{0,400}?onClick:\s*([A-Za-z0-9_$]+)",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(trigger, "the answer disclosure trigger is missing from the shipped source")
        self.assertEqual(trigger.group(1), "openAnswerConfirm")
        self.assertNotIn("recordAssist", trigger.group(0))

    def test_record_assist_answer_shown_has_one_call_site_inside_the_confirm(self) -> None:
        calls = re.findall(r"recordAssist\(\s*'answer_shown'\s*\)", self.source)
        self.assertEqual(len(calls), 1, f"expected one answer_shown write, found {len(calls)}")
        # ...and it lives in `confirmAnswerShown`, the handler bound to the confirm button alone.
        handler = re.search(r"const confirmAnswerShown = useCallback\(", self.source)
        self.assertIsNotNone(handler)
        start = handler.start()
        end = self.source.find("}, [recordAssist])", start)
        self.assertNotEqual(end, -1)
        self.assertIn("recordAssist('answer_shown')", self.source[start:end])
        confirm_button = re.search(
            r"data-cb-answer-confirm-yes'.{0,400}?onClick:\s*([A-Za-z0-9_$]+)",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(confirm_button, "the confirm button is missing from the shipped source")
        self.assertEqual(confirm_button.group(1), "confirmAnswerShown")


if __name__ == "__main__":
    unittest.main()
