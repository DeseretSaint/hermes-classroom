"""UP-14: assistance is an authored ladder, not one binary event.

The card's failure, observed at HEAD: the pane always offers "Ask for a hint" and "I saw the
answer" whatever ``assistance_policy`` the check authored, because ``check.get`` never projected
it; any press writes the same ``hinted`` event, so there is no rung between no help and full
contamination.

This module proves the fix on both halves of the wire:

* the backend projects the authored policy and rung labels on ``check.get`` (text is withheld
  until a press), and ``lesson.assist`` records exactly one authored rung per press, in order;
* the shipped Desktop module mounts the real ``AttemptControls`` and hides the hint control when
  the check authored ``none``, while a laddered check advances one named rung per press.

The render half is the named acceptance test. It fails at HEAD because the module ignores
``check.assistance``: a policy-``none`` check still paints "Ask for a hint", and a laddered check
paints no rungs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coursebook import contracts
from tests.kernel_support import KernelCase, numeric_spec
from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

LADDER = [
    {"kind": "nudge", "text": "Start from the polite form, not the plain one."},
    {"kind": "cue", "text": "The verb changes stem before the request suffix."},
    {"kind": "worked_step", "text": "Wait politely: 少々お待ちください."},
]

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

const calls = []
const ladder = Array.isArray(payload.ladder) ? payload.ladder : []
let cursor = Number.isInteger(payload.nextRung) ? payload.nextRung : 0
let revision = 5

const ctx = {
  register: () => {},
  onDispose: () => {},
  rest: async (path, options = {}) => {
    if (String(path).startsWith('/runtime')) {
      return { wire_version: 29, implemented_methods: ['check.get', 'lesson.assist', 'evidence.inspect'] }
    }
    const body = options.body || {}
    const data = body.payload || {}
    if (body.method === 'lesson.assist') {
      const index = data.rung
      if (!Number.isInteger(index) || index !== cursor) {
        calls.push({ method: body.method, kind: data.kind, rung: data.rung, refusal: 'hint_rung_out_of_order' })
        return {
          ok: false,
          contract_version: 29,
          operation_id: body.operation_id,
          error: { code: 'VALIDATION_FAILED', category: 'caller', message: 'out of order', details: { reason: 'hint_rung_out_of_order', expected_rung: cursor } }
        }
      }
      const rung = ladder[index]
      const last = index === ladder.length - 1
      cursor = last ? ladder.length : index + 1
      revision += 1
      calls.push({ method: body.method, kind: last ? 'answer_shown' : 'hint_request', rung: index })
      return {
        ok: true,
        contract_version: 29,
        operation_id: body.operation_id,
        result: {
          event_id: 'evd_' + index,
          kind: last ? 'answer_shown' : 'hint_request',
          evidence_class: last ? 'answer_shown' : 'hinted',
          revision,
          rung: { index, kind: rung.kind, label: rung.label, text: rung.text, last }
        }
      }
    }
    calls.push(body.method)
    if (body.method === 'evidence.inspect') {
      return {
        ok: true,
        contract_version: 29,
        operation_id: body.operation_id,
        result: { l1: { enrollment_id: 'enr_0123456789abcdef', objective_id: 'obj_0123456789abcdef', attempts: [], events: [] }, l2: {}, l3: {}, disputes: {} }
      }
    }
    return { ok: false, contract_version: 29, operation_id: body.operation_id, error: { code: 'UNKNOWN', category: 'internal', message: body.method } }
  }
}

plugin.register(ctx)

const root = createRoot(document.getElementById('root'))
root.render(
  React.createElement(AttemptControls, {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    check: payload.check,
    revision: 3,
    implemented: new Set(['check.get', 'lesson.assist', 'evidence.inspect']),
    bindingState: 'active',
    stimulusStatus: 'ready',
    onRetryStimulus: () => {},
    onCommitted: () => {}
  })
)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const waitFor = async (predicate, timeout = 4000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (predicate()) return true
    await sleep(20)
  }
  return false
}

await waitFor(() => document.querySelector('[data-cb-choice-group]') || document.querySelector('[data-cb-assist]'))
await sleep(120)

const result = {
  askControls: document.querySelectorAll('[data-cb-ask-hint]').length,
  ladderBlocks: document.querySelectorAll('[data-cb-hint-ladder]').length,
  nextRungs: [],
  rungKinds: [],
  rungTexts: [],
  rungCounts: [],
  assistCalls: []
}

if (payload.mode === 'ladder') {
  for (let step = 0; step < ladder.length; step += 1) {
    await waitFor(() => document.querySelector('[data-cb-hint-next]'))
    const next = document.querySelector('[data-cb-hint-next]')
    if (!next) break
    const before = document.querySelectorAll('[data-cb-hint-rung]').length
    result.nextRungs.push({ attr: next.getAttribute('data-cb-hint-next'), text: next.textContent.trim() })
    next.click()
    await waitFor(() => document.querySelectorAll('[data-cb-hint-rung]').length === before + 1)
    await sleep(60)
    result.rungCounts.push(document.querySelectorAll('[data-cb-hint-rung]').length)
  }
  result.rungKinds = Array.from(document.querySelectorAll('[data-cb-hint-rung]')).map((node) => node.getAttribute('data-cb-hint-rung'))
  result.rungTexts = Array.from(document.querySelectorAll('[data-cb-hint-rung-text]')).map((node) => node.textContent.trim())
} else {
  // A policy-`none` check must offer no hint at all. If a control exists at all (the HEAD
  // behaviour), press it so the harness can report the write the learner should never trigger.
  const control = document.querySelector('[data-cb-ask-hint]')
  if (control) {
    control.click()
    await sleep(150)
  }
}

result.assistCalls = calls.filter((call) => call && call.method === 'lesson.assist')
result.finalAskControls = document.querySelectorAll('[data-cb-ask-hint]').length
process.stdout.write(JSON.stringify(result))
"""


def check_payload(*, policy: str, ladder=None, next_rung=0) -> dict:
    assistance = {
        "policy": policy,
        "available": policy == "available",
        "rungs": [{"kind": rung["kind"], "label": rung["label"]} for rung in (ladder or [])],
        "used": 0,
        "next_rung": next_rung if policy == "available" and ladder else None,
        "total": len(ladder or []),
    }
    stimulus = {
        "prompt": "Which expression is the polite way to ask a coworker to wait?",
        "format": "selection",
        "choices": ["ちょっと待って", "少々お待ちください", "待て", "待ってね"],
        "items": [],
        "learner_instructions": None,
        "practice": None,
        "assistance_policy": {
            "hint": policy,
            "answer_marks_evidence_class": "hinted",
            "ladder": [{"kind": rung["kind"], "label": rung["label"]} for rung in (ladder or [])],
        },
    }
    return {
        "check_id": "chk_0123456789abcdef",
        "check_version": 1,
        "evidence_target": "discrimination",
        "attempt_count": 0,
        "stimulus": stimulus,
        "assistance": assistance,
    }


LABELLED_LADDER = [
    {"kind": "nudge", "label": "Nudge", "text": LADDER[0]["text"]},
    {"kind": "cue", "label": "Cue", "text": LADDER[1]["text"]},
    {"kind": "worked_step", "label": "Worked step", "text": LADDER[2]["text"]},
]


class HintLadderPaneTest(unittest.TestCase):
    """The shipped Desktop module, mounted over the check the backend now serves."""

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-hint-ladder-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "live.mjs").write_text(HARNESS, encoding="utf-8")
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
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def render(self, payload: dict) -> dict:
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "live.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2500:])
        return json.loads(result.stdout)

    def test_a_none_policy_offers_no_hint_and_a_laddered_check_offers_one_rung(self) -> None:
        # Before: the pane ignores the policy and paints both binary controls. After: `none`
        # paints no hint control, and each press on a laddered check reveals exactly one rung.
        none = self.render(
            {"mode": "none", "check": check_payload(policy="none"), "ladder": [], "nextRung": None}
        )
        self.assertEqual(none["askControls"], 0, "a policy-none check still offered a hint control")
        self.assertEqual(none["ladderBlocks"], 0, "a policy-none check still rendered a rung ladder")
        self.assertEqual(none["assistCalls"], [], "a policy-none check recorded an assistance event")
        self.assertEqual(none["finalAskControls"], 0)

        laddered = self.render(
            {
                "mode": "ladder",
                "check": check_payload(policy="available", ladder=LABELLED_LADDER),
                "ladder": LABELLED_LADDER,
                "nextRung": 0,
            }
        )
        self.assertEqual(laddered["ladderBlocks"], 1, "a laddered check painted no ladder")
        self.assertEqual(
            [entry["attr"] for entry in laddered["nextRungs"]],
            ["nudge", "cue", "worked_step"],
            "the pane did not offer the authored rungs in order",
        )
        self.assertEqual(
            laddered["rungKinds"],
            ["nudge", "cue", "worked_step"],
            "the pane revealed the wrong rung sequence",
        )
        self.assertEqual(laddered["rungTexts"], [rung["text"] for rung in LADDER])
        self.assertEqual(laddered["rungCounts"], [1, 2, 3], "a press revealed more than one rung")
        self.assertEqual(
            [call["rung"] for call in laddered["assistCalls"]],
            [0, 1, 2],
            "each press must record exactly the next authored rung",
        )
        self.assertEqual(
            [call["kind"] for call in laddered["assistCalls"]],
            ["hint_request", "hint_request", "answer_shown"],
            "the last rung must carry the existing answer_shown penalty",
        )
        self.assertEqual(laddered["nextRungs"][0]["text"], "Get a nudge")
        self.assertEqual(laddered["finalAskControls"], 0, "the exhausted ladder still offered a press")


class HintLadderBackendTest(KernelCase):
    """``check.get`` projects the policy; ``lesson.assist`` records one rung per press."""

    def ladder_spec(self, *, hint: str = "available", ladder=None) -> dict:
        spec = numeric_spec()
        spec["stimulus"]["format"] = "selection"
        spec["stimulus"]["choices"] = ["4", "5", "6"]
        spec["stimulus"]["assistance_policy"] = {
            "hint": hint,
            "answer_marks_evidence_class": "hinted",
            "ladder": list(LADDER if ladder is None else ladder),
        }
        return spec

    def detail(self, lesson: dict) -> dict:
        return self.ok(
            "check.get",
            {"enrollment_id": lesson["enrollment_id"], "check_id": lesson["check_id"]},
        )["result"]

    def assist(self, lesson: dict, rung: int | None, key: str) -> dict:
        payload = {
            "enrollment_id": lesson["enrollment_id"],
            "objective_id": lesson["objective_id"],
            "kind": "hint_request",
        }
        if rung is not None:
            payload["rung"] = rung
        return self.dispatch(
            "lesson.assist", payload,
            expected_revision=lesson["revision"], idempotency_key=key,
        )

    def test_check_get_projects_the_policy_and_withholds_rung_text(self) -> None:
        lesson = self.prepare_lesson(self.ladder_spec())
        detail = self.detail(lesson)
        assistance = detail["assistance"]
        self.assertEqual(assistance["policy"], "available")
        self.assertTrue(assistance["available"])
        self.assertEqual(
            [rung["kind"] for rung in assistance["rungs"]], ["nudge", "cue", "worked_step"]
        )
        self.assertEqual([rung["label"] for rung in assistance["rungs"]], ["Nudge", "Cue", "Worked step"])
        self.assertEqual(assistance["used"], 0)
        self.assertEqual(assistance["next_rung"], 0)
        projected = detail["stimulus"]["assistance_policy"]
        self.assertEqual(projected["hint"], "available")
        self.assertEqual(projected["ladder"], [
            {"kind": "nudge", "label": "Nudge"},
            {"kind": "cue", "label": "Cue"},
            {"kind": "worked_step", "label": "Worked step"},
        ])
        self.assertNotIn("text", projected["ladder"][0], "check.get served a rung the learner did not press")

    def test_lesson_assist_reveals_one_rung_and_refuses_a_skip(self) -> None:
        lesson = self.prepare_lesson(self.ladder_spec())
        first = self.ok(
            "lesson.assist",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "kind": "hint_request",
                "rung": 0,
            },
            expected_revision=lesson["revision"],
            idempotency_key="ladder-0",
        )
        self.assertEqual(first["result"]["rung"]["kind"], "nudge")
        self.assertEqual(first["result"]["rung"]["text"], LADDER[0]["text"])
        self.assertEqual(first["result"]["evidence_class"], "hinted")
        lesson["revision"] = first["revision"]
        after_first = self.detail(lesson)
        self.assertEqual(after_first["assistance"]["used"], 1)
        self.assertEqual(after_first["assistance"]["next_rung"], 1)

        skipped = self.assist(lesson, 2, "ladder-skip")
        self.assertFalse(skipped["ok"])
        self.assertEqual(skipped["error"]["details"]["reason"], "hint_rung_out_of_order")
        self.assertEqual(skipped["error"]["details"]["expected_rung"], 1)

        second = self.assist(lesson, 1, "ladder-1")
        self.assertTrue(second["ok"], second.get("error"))
        self.assertEqual(second["result"]["rung"]["kind"], "cue")
        self.assertEqual(second["result"]["evidence_class"], "hinted")
        lesson["revision"] = second["revision"]

        third = self.assist(lesson, 2, "ladder-2")
        self.assertTrue(third["ok"], third.get("error"))
        self.assertEqual(third["result"]["rung"]["kind"], "worked_step")
        self.assertTrue(third["result"]["rung"]["last"])
        self.assertEqual(third["result"]["kind"], "answer_shown")
        self.assertEqual(third["result"]["evidence_class"], "answer_shown")
        lesson["revision"] = third["revision"]
        exhausted = self.detail(lesson)
        self.assertEqual(exhausted["assistance"]["used"], 3)
        self.assertIsNone(exhausted["assistance"]["next_rung"])

    def test_a_none_policy_refuses_a_hint_press(self) -> None:
        lesson = self.prepare_lesson(self.ladder_spec(hint="none"))
        error = self.err(
            "lesson.assist",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "kind": "hint_request",
                "rung": 0,
            },
            expected_revision=lesson["revision"],
            idempotency_key="none-rung",
        )
        self.assertEqual(error["details"]["reason"], "hint_policy_none")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)

    def test_a_laddered_check_refuses_the_binary_hint(self) -> None:
        lesson = self.prepare_lesson(self.ladder_spec())
        error = self.err(
            "lesson.assist",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "kind": "hint_request",
            },
            expected_revision=lesson["revision"],
            idempotency_key="binary-on-ladder",
        )
        self.assertEqual(error["details"]["reason"], "hint_rung_required")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM evidence"), 0)

    def test_the_after_attempt_gate_holds_the_first_rung(self) -> None:
        lesson = self.prepare_lesson(self.ladder_spec(hint="after_attempt"))
        detail = self.detail(lesson)
        self.assertFalse(detail["assistance"]["available"])
        self.assertIsNone(detail["assistance"]["next_rung"])
        error = self.err(
            "lesson.assist",
            {
                "enrollment_id": lesson["enrollment_id"],
                "objective_id": lesson["objective_id"],
                "kind": "hint_request",
                "rung": 0,
            },
            expected_revision=lesson["revision"],
            idempotency_key="after-attempt",
        )
        self.assertEqual(error["details"]["reason"], "hint_not_available")


class HintLadderContractTest(unittest.TestCase):
    """v29 is derived from v28, and the new keys are the only movement."""

    def test_v29_is_the_derived_delta_not_a_hand_copy(self) -> None:
        import importlib.util

        # v29 is *composed*: UP-14's ladder delta, then UP-19's recognition-label delta on the
        # union. One contract version cannot be forked into two files, so the shipped document
        # must equal the composition — and still carry the ladder, not just the later delta.
        spec = importlib.util.spec_from_file_location(
            "derive_rpc_v29_pronunciation",
            contracts.CONTRACT_DIR.parent / "probes" / "derive_rpc_v29_pronunciation.py",
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        shipped = (contracts.CONTRACT_DIR / "rpc.v29.json").read_text(encoding="utf-8")
        source = json.loads((contracts.CONTRACT_DIR / "rpc.v28.json").read_text(encoding="utf-8"))
        self.assertEqual(shipped, module.serialise(module.derive(source)))
        document = json.loads(shipped)
        self.assertIn("assistance_policy", document["$defs"]["check_stimulus"]["properties"])
        self.assertEqual(
            document["$defs"]["pronunciation_assessment"]["properties"]["measure"]["enum"],
            ["word_recognition", "none"],
        )


if __name__ == "__main__":
    unittest.main()
