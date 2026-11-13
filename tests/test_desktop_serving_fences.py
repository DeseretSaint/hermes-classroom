"""E2E L2/L3 on the shipped learning surface: revision adoption and Start anyway.

The backend half is ``tests/test_serving_fences.py``. This module drives the real
``desktop/plugin.js`` in jsdom and clicks the real controls, so the two serving fences are proven
at the seam a learner actually touches:

* **L2** — ``check.open`` bumps the enrollment when it creates the check. The surface must adopt
  the revision the command returned *before* the card can submit, so a first answer after an
  on-demand check fences on the backend's number instead of the page read's older one.
* **L3** — an unmet prerequisite edge refuses ``check.open`` with a message that says the learner
  may start anyway. The card renders that as one **Start anyway** control; pressing it re-opens
  the check with ``acknowledge_prerequisites: true``, and the opened card states the
  acknowledgment instead of hiding the check.

What this does NOT prove: pixels, or a live backend. The backend contract and the fence are pinned
in Python; this is the surface half over a scripted ``ctx.rest``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.desktop_node_modules import desktop_node_modules, stage_desktop_node_modules
from tests.test_desktop_learning_live import outline, page, row
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

const stimulus = {
  prompt: 'Which line is the romantic confession?',
  format: 'selection',
  choices: ['A: うん、好きだよ。', 'B: 好きです。付き合ってください。'],
  items: []
}

const refusal = {
  ok: false,
  error: {
    code: 'PREREQUISITE_UNMET',
    category: 'policy',
    message:
      'Unit 2 assumes you can greet someone. 1 of 2 objectives there have not been shown independently yet: Say hello. You can start now; the course will not count the prerequisite as met.',
    retryable: false,
    details: {
      prerequisite_state: {
        state: 'unmet',
        unmet: [{ objective_id: 'obj_1', ordinal: 1, title: 'Say hello', state: 'not_started' }]
      },
      unit_ordinal: 2,
      prerequisite_unit_ordinals: [1]
    }
  }
}

const fakeRest = async (path, options = {}) => {
  const body = options.body || {}
  calls.push({
    method: body.method,
    payload: body.payload || null,
    expected_revision: body.expected_revision ?? null,
    idempotency_key: body.idempotency_key ?? null
  })
  if (String(path).split('?')[0] === '/runtime') {
    return { wire_version: 26, implemented_methods: payload.implemented }
  }
  const name = body.method
  if (name === 'course.outline') return { ok: true, result: payload.outline }
  if (name === 'lesson.page') return { ok: true, result: payload.page }
  if (name === 'world.read') return { ok: true, result: { world: null, style: null } }
  if (name === 'check.open') {
    const opens = calls.filter((call) => call.method === 'check.open')
    if (payload.scenario === 'prerequisite') {
      // The first open is the refusal; every later open is the acknowledged read.
      if (opens.length === 1 && !(body.payload && body.payload.acknowledge_prerequisites)) {
        return refusal
      }
      return {
        ok: true,
        result: {
          check_id: 'chk_first01',
          check_version: 1,
          evidence_target: 'discrimination',
          revision: payload.bumpedRevision || 8,
          prerequisite_state: { state: 'unmet_acknowledged', unmet: [{ objective_id: 'obj_1', ordinal: 1, title: 'Say hello', state: 'not_started' }] }
        }
      }
    }
    // L2: creating the check moved the enrollment past the page read's revision.
    return {
      ok: true,
      result: {
        check_id: 'chk_first01',
        check_version: 1,
        evidence_target: 'discrimination',
        revision: payload.bumpedRevision || 8
      }
    }
  }
  if (name === 'check.get') {
    return {
      ok: true,
      result: {
        check_id: 'chk_first01',
        objective_id: 'obj_2',
        check_version: 1,
        evidence_target: 'discrimination',
        state: 'open',
        audit_state: 'passed',
        attempt_count: 0,
        stimulus
      }
    }
  }
  if (name === 'attempt.submit') {
    return {
      ok: true,
      result: {
        attempt_id: 'att_0123456789abcdef',
        verdict: 'pass',
        evidence_class: 'cold',
        criteria: [],
        next_action: 'advance',
        revision: Number(body.expected_revision) + 1
      }
    }
  }
  throw new Error('unexpected rpc method ' + name)
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {}
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const props = {
  row: payload.row,
  enrollmentId: payload.row.enrollment_id,
  objectiveId: payload.objectiveId || 'obj_2',
  mode: 'guided',
  onBack: () => events.push('back'),
  onOpenSection: () => events.push('open-section'),
  onNextSection: () => events.push('next-section'),
  onStartChat: () => events.push('start-chat')
}

const flush = async (ms = 140) => {
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
const text = (selector) => {
  const node = document.querySelector(selector)
  return node ? (node.textContent || '').replace(/\s+/g, ' ').trim() : null
}

await act(async () => { root.render(React.createElement(mod.ClassroomV3Surface, props)) })
await flush(280)

const before = {
  check: Boolean(document.querySelector('[data-cb3-surface="check"]')),
  question: text('[data-cb3-question]'),
  refusal: text('[data-cb3-check-refusal]'),
  startAnyway: Boolean(byText('Start anyway')),
  acknowledged: text('[data-cb3-prerequisite-acknowledged]')
}

let after = null
if (payload.scenario === 'revision') {
  const choice = document.querySelectorAll('[data-cb3-choice] input')[1]
  await act(async () => { choice.click() })
  await flush(60)
  await click(byText('Check answer'))
  after = {
    verdict: (() => {
      const node = document.querySelector('[data-cb3-verdict]')
      return node ? node.getAttribute('data-cb3-verdict') : null
    })()
  }
} else if (payload.scenario === 'prerequisite') {
  await click(byText('Start anyway'))
  after = {
    check: Boolean(document.querySelector('[data-cb3-surface="check"]')),
    question: text('[data-cb3-question]'),
    refusal: text('[data-cb3-check-refusal]'),
    startAnyway: Boolean(byText('Start anyway')),
    acknowledged: text('[data-cb3-prerequisite-acknowledged]')
  }
}

process.stdout.write(JSON.stringify({
  before,
  after,
  calls: calls.filter((call) => call.method),
}))
"""


class _Rig:
    def __init__(self) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        if desktop_node_modules() is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        self.tmp = tempfile.TemporaryDirectory(prefix="coursebook-serving-fences-")
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


IMPLEMENTED = [
    "course.outline",
    "lesson.page",
    "world.read",
    "check.open",
    "check.get",
    "attempt.submit",
]


class ServingFenceSurfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rig = _Rig()

    def test_the_submit_after_a_new_check_carries_the_revision_check_open_returned(self) -> None:
        """L2: page read says 7, `check.open` says 8 — the answer must fence on 8."""
        data = self.rig.run("revision", bumpedRevision=8)
        opens = [call for call in data["calls"] if call["method"] == "check.open"]
        self.assertEqual(opens[0]["expected_revision"], 7, data)
        # The adopted revision drives the next read too; nothing here sends 7 again.
        self.assertEqual(opens[-1]["expected_revision"], 8, data)
        submits = [call for call in data["calls"] if call["method"] == "attempt.submit"]
        self.assertEqual(len(submits), 1, data)
        self.assertEqual(submits[0]["expected_revision"], 8, data)
        self.assertEqual(data["after"]["verdict"], "pass")

    def test_an_unmet_prerequisite_is_a_start_anyway_control(self) -> None:
        """L3: the refusal names the choice, and the choice is the card's own control."""
        data = self.rig.run("prerequisite")
        self.assertTrue(data["before"]["startAnyway"], data)
        self.assertIn("You can start now", data["before"]["refusal"] or "")
        # The refusal is not the check form: no question, no submit while refused.
        self.assertIsNone(data["before"]["question"], data)
        opens = [call for call in data["calls"] if call["method"] == "check.open"]
        self.assertFalse((opens[0]["payload"] or {}).get("acknowledge_prerequisites"), data)

    def test_start_anyway_acknowledges_and_the_check_opens(self) -> None:
        data = self.rig.run("prerequisite")
        opens = [call for call in data["calls"] if call["method"] == "check.open"]
        acked = [call for call in opens if (call["payload"] or {}).get("acknowledge_prerequisites") is True]
        self.assertGreaterEqual(len(acked), 1, data)
        # The learner's press acknowledges the check at the fence the surface held (the page read),
        # and every read after the adopted revision keeps the acknowledgment — the decision does not
        # evaporate when `check.open` returns the bumped revision.
        self.assertEqual(acked[0]["expected_revision"], 7, data)
        self.assertIn(8, [call["expected_revision"] for call in acked], data)
        # The acknowledgment is a learner decision on the same check.
        self.assertEqual(acked[0]["payload"]["enrollment_id"], "enr_0123456789abcdef")
        self.assertEqual(acked[0]["payload"]["objective_id"], "obj_2")
        after = data["after"]
        self.assertTrue(after["check"], data)
        self.assertIn("romantic confession", after["question"] or "")
        self.assertIsNone(after["refusal"], data)
        self.assertFalse(after["startAnyway"], data)
        self.assertIn("Prerequisite not met — acknowledged", after["acknowledged"] or "")

    def test_no_submit_is_sent_by_the_acknowledgment_itself(self) -> None:
        data = self.rig.run("prerequisite")
        self.assertEqual([call for call in data["calls"] if call["method"] == "attempt.submit"], [], data)


if __name__ == "__main__":
    unittest.main()
