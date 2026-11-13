"""L7 — XP is paid by every lesson surface, not only the desk classroom.

``awardCheck`` used to live inside ``ClassroomV3Surface`` alone, so the same passing check paid
when it was committed at the desk and paid nothing when it was committed in the reader, the Field
player or the course page's section (all of which commit through the shared ``AttemptControls``).
The award now lives in ``useCheckAward``, which both commit paths call.

Two proofs, both against the **shipped** ``desktop/plugin.js``:

* the shared commit card posts exactly one ``engagement.award`` for a passing attempt, with the
  committed ``attempt_id`` as the action id and an idempotency key that names that attempt — and
  posts nothing for a course that is not durably in Game mode, a build without
  ``engagement.award``, or a verdict that is not a pass;
* the same card, mounted against the **real kernel** through a local RPC bridge, raises
  ``engagement.read.xp_total`` for a pass committed on the reading path; replaying that attempt
  (the same envelope key, and then a fresh key for the same action) pays nothing more and writes
  no second ledger row.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from coursebook import api, db, engagement, generation
from tests.kernel_support import KernelCase
from tests.test_desktop_lesson_views import PLUGIN_JS, SDK_STUB, _desktop_node_modules

#: The shared stub renders no form controls; this card drives the answer form, so the textarea is
#: a real element and the card's own controlled value can be typed into.
INTERACTIVE_SDK_STUB = SDK_STUB.replace(
    "export const Textarea = () => null",
    """export const Textarea = (props) =>
  el('textarea', {
    id: props.id,
    value: props.value,
    disabled: Boolean(props.disabled),
    rows: props.rows,
    placeholder: props.placeholder,
    onChange: props.onChange,
    'aria-describedby': props['aria-describedby']
  })""",
)
assert "el('textarea'" in INTERACTIVE_SDK_STUB


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
const bridge = payload.bridge || null

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return {
      wire_version: payload.wireVersion || 1,
      implemented_methods: payload.implemented || [],
      single_home_host: false
    }
  }
  if (base !== '/rpc') return { ok: true, result: {} }
  const body = (options && options.body) || {}
  calls.push({
    method: body.method,
    payload: body.payload || null,
    idempotency_key: body.idempotency_key || null,
    expected_revision: body.expected_revision === undefined ? null : body.expected_revision
  })
  if (bridge) {
    const answer = await fetch(bridge + '/rpc', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body)
    })
    return await answer.json()
  }
  const result = responses[body.method]
  if (result === undefined) {
    return {
      ok: false,
      contract_version: payload.wireVersion || 1,
      operation_id: body.operation_id,
      error: { code: 'NOT_IMPLEMENTED', category: 'capability', message: `no stub for ${body.method}` }
    }
  }
  return {
    ok: true,
    contract_version: payload.wireVersion || 1,
    operation_id: body.operation_id,
    revision: payload.revision || 0,
    result
  }
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle)
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()

await act(async () => {
  root.render(
    React.createElement(mod.AttemptControls, {
      enrollmentId: payload.enrollmentId,
      objectiveId: payload.objectiveId,
      check: payload.check,
      revision: payload.revision || 0,
      implemented: new Set(payload.implemented || []),
      bindingState: 'active',
      courseId: payload.courseId || null,
      gameMode: Boolean(payload.gameMode),
      stimulusStatus: 'ready',
      onCommitted: () => {}
    })
  )
})
await flush(120)

const typeAnswer = async (value) => {
  const field = document.querySelector('#cb-attempt-answer')
  if (!field) return false
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
  await act(async () => {
    setter.call(field, value)
    field.dispatchEvent(new window.Event('input', { bubbles: true }))
  })
  await flush(30)
  return true
}

let typed = null
if (payload.answer !== null && payload.answer !== undefined) typed = await typeAnswer(payload.answer)

const submit = [...document.querySelectorAll('button')].find((button) =>
  /^(Submit answer|Submit choice|Submit confirmation)$/.test(text(button))
)
if (submit) {
  await act(async () => { submit.click() })
  // The commit is a real round trip in bridge mode; wait for it to settle rather than guessing.
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await flush(100)
    if (document.querySelector('[data-cb-verdict], .attempt-verdict, [data-cb-check-verdict]')) break
    if (!document.querySelector('#cb-attempt-answer') && calls.some((call) => call.method === 'attempt.submit')) break
  }
}
await flush(200)

process.stdout.write(
  JSON.stringify({
    calls,
    typed,
    submitted: Boolean(submit),
    body: text(document.getElementById('root')),
    verdict: [...document.querySelectorAll('[data-cb-verdict]')].map((node) => text(node))
  })
)
"""


def _payload(**overrides) -> dict:
    base = {
        "enrollmentId": "enr_l7",
        "objectiveId": "obj_l7",
        "courseId": "course_l7",
        "gameMode": True,
        "revision": 3,
        "answer": "4",
        "implemented": ["check.open", "check.get", "attempt.submit", "evidence.inspect", "engagement.award"],
        "check": {
            "check_id": "chk_l7",
            "check_version": 1,
            "attempt_count": 0,
            "evidence_target": "procedure",
            "stimulus": {"prompt": "Compute the answer.", "format": "text"},
        },
        "responses": {
            "evidence.inspect": {"l1": {"events": []}},
            "attempt.submit": {
                "verdict": "pass",
                "attempt_id": "att_l7_1",
                "evidence_class": "cold",
                "criteria": [],
                "next_action": "complete_objective",
            },
        },
    }
    base.update(overrides)
    return base


class AwardModuleHarness:
    """Runs the shipped module's shared commit card in jsdom with a stubbed transport."""

    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-l7-")
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
        (sdk / "index.js").write_text(INTERACTIVE_SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def run_card(self, **overrides) -> dict:
        payload = _payload(**overrides)
        case = self.root / f"case-{os.urandom(4).hex()}.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "harness.mjs"), str(case)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-6000:])
        return json.loads(result.stdout)

    @staticmethod
    def awards(report: dict) -> list[dict]:
        return [call for call in report["calls"] if call["method"] == "engagement.award"]

class AwardModuleTests(AwardModuleHarness, unittest.TestCase):
    """The shared commit card pays once, gated on Game mode and backend support."""

    # ── the shared card pays once, for the committed attempt ─────────────────────────────────

    def test_a_reader_pass_awards_the_committed_attempt(self) -> None:
        report = self.run_card()
        self.assertTrue(report["submitted"], "the card rendered no submit control")
        awards = self.awards(report)
        self.assertEqual(len(awards), 1, f"expected one award, got {awards}")
        award = awards[0]
        self.assertEqual(award["payload"]["course_id"], "course_l7")
        self.assertEqual(award["payload"]["enrollment_id"], "enr_l7")
        self.assertEqual(award["payload"]["action_kind"], "check_submitted")
        self.assertEqual(award["payload"]["action_id"], "att_l7_1")
        # The key names the attempt, so a duplicate delivery of the same commit replays instead of
        # paying again; nothing else (a click, a render, a view) can produce this value.
        self.assertEqual(award["idempotency_key"], "cb-award-enr_l7-att_l7_1")

    def test_the_same_attempt_committed_twice_sends_one_award_key(self) -> None:
        # Two mounts whose backend returns the same committed row model a replayed commit: the
        # envelope key is identical, so the second call is the backend's stored answer, not a
        # second award.
        first = self.awards(self.run_card())
        second = self.awards(self.run_card())
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["idempotency_key"], second[0]["idempotency_key"])
        self.assertEqual(first[0]["payload"], second[0]["payload"])

    def test_a_non_pass_verdict_does_not_award(self) -> None:
        partial = _payload()["responses"]["attempt.submit"] | {"verdict": "partial"}
        report = self.run_card(responses={"evidence.inspect": {"l1": {"events": []}}, "attempt.submit": partial})
        self.assertEqual(self.awards(report), [])

    # ── the gates: Game mode and backend support ────────────────────────────────────────────

    def test_a_textbook_course_never_awards(self) -> None:
        report = self.run_card(gameMode=False)
        self.assertTrue(any(call["method"] == "attempt.submit" for call in report["calls"]))
        self.assertEqual(self.awards(report), [])

    def test_a_backend_without_the_method_never_awards(self) -> None:
        report = self.run_card(
            implemented=["check.open", "check.get", "attempt.submit", "evidence.inspect"]
        )
        self.assertEqual(self.awards(report), [])

    def test_an_unknown_course_id_never_awards(self) -> None:
        # A surface that does not know which course it is serving cannot pay: the backend needs a
        # real course, and "unknown" is not one.
        report = self.run_card(courseId=None)
        self.assertEqual(self.awards(report), [])


class _Bridge(BaseHTTPRequestHandler):
    """A local HTTP door that forwards ``/rpc`` envelopes to the real kernel dispatcher."""

    def do_POST(self) -> None:  # noqa: N802 - http.server's spelling
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        answer = api.dispatch(body)
        data = json.dumps(answer).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - http.server's spelling
        if self.path.startswith("/runtime"):
            answer = {
                "wire_version": api.RPC_CONTRACT_VERSION,
                "implemented_methods": list(api.method_names()),
                "single_home_host": False,
            }
        else:
            answer = {"ok": True}
        data = json.dumps(answer).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - http.server's spelling
        return


class ReaderBridgeCase(KernelCase, AwardModuleHarness):
    """A real kernel, a real seeded Game course, and a local RPC bridge for the shipped module."""

    @classmethod
    def setUpClass(cls) -> None:
        AwardModuleHarness.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        AwardModuleHarness.tearDownClass.__func__(cls)

    def setUp(self) -> None:
        KernelCase.setUp(self)
        engagement.configure_feedback(None)
        course_id, plan_id = self.new_course(title="Braise at the table", recipe="committed")
        objective_id = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id)
        revision = self.approve(enrollment_id, plan_id, 0)
        with db.transaction() as connection:
            generation.ensure_schema(connection)
        self.execute("UPDATE courses SET presentation_mode = 'game' WHERE id = ?", (course_id,))
        opened = self.ok(
            "check.open",
            {"enrollment_id": enrollment_id, "objective_id": objective_id},
            expected_revision=revision,
        )["result"]
        detail = self.ok(
            "check.get", {"enrollment_id": enrollment_id, "check_id": opened["check_id"]}
        )["result"]
        self.course_id = course_id
        self.objective_id = objective_id
        self.enrollment_id = enrollment_id
        self.revision = opened["revision"]
        self.check = {
            **opened,
            "attempt_count": int(detail.get("attempt_count") or 0),
            "stimulus": detail["stimulus"],
        }
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Bridge)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.bridge = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        if getattr(self, "server", None) is not None:
            self.server.shutdown()
            self.server.server_close()
        engagement.configure_feedback(None)
        KernelCase.tearDown(self)

    def xp_total(self) -> int:
        read = self.ok(
            "engagement.read",
            {"course_id": self.course_id, "enrollment_id": self.enrollment_id},
        )["result"]
        return int(read["xp_total"])

    def xp_rows(self) -> int:
        return int(
            self.scalar(
                "SELECT COUNT(*) FROM game_engagement WHERE enrollment_id = ?",
                (self.enrollment_id,),
            )
        )

class ReaderCardPassPaysTests(ReaderBridgeCase):
    """The shared commit card, mounted as the reader mounts it, raises the real XP total."""

    def test_a_reader_pass_raises_the_backend_xp_total(self) -> None:
        self.assertEqual(self.xp_total(), 0)
        report = self.run_card(
            enrollmentId=self.enrollment_id,
            objectiveId=self.objective_id,
            courseId=self.course_id,
            revision=self.revision,
            check=self.check,
            implemented=list(api.method_names()),
            wireVersion=api.RPC_CONTRACT_VERSION,
            bridge=self.bridge,
        )
        self.assertTrue(report["submitted"], "the card rendered no submit control")
        submits = [call for call in report["calls"] if call["method"] == "attempt.submit"]
        self.assertEqual(len(submits), 1, report["body"])
        awards = [call for call in report["calls"] if call["method"] == "engagement.award"]
        self.assertEqual(len(awards), 1, f"the reader did not award: {report['calls']}")
        total = self.xp_total()
        self.assertGreater(total, 0, "a pass committed in the reader paid nothing")
        self.assertEqual(self.xp_rows(), 1)

        # The same attempt committed again: the UI's key is attempt-scoped, so the identical
        # envelope replays the stored answer (same points, same total) and a fresh key for the same
        # action is refused as already paid. Neither pays a second time.
        award = awards[0]["payload"]
        key = awards[0]["idempotency_key"]
        replayed = self.dispatch("engagement.award", award, idempotency_key=key)
        self.assertTrue(replayed["ok"], replayed.get("error"))
        self.assertEqual(replayed["result"]["xp_total"], total)
        fresh = self.dispatch("engagement.award", award)
        self.assertTrue(fresh["ok"], fresh.get("error"))
        self.assertFalse(fresh["result"]["awarded"])
        self.assertEqual(fresh["result"]["points"], 0)
        self.assertEqual(self.xp_total(), total)
        self.assertEqual(self.xp_rows(), 1)


class WiringTests(unittest.TestCase):
    """Every lesson surface hands the shared commit card a real course id and its Game gate.

    The card's behaviour is proved above against the real kernel. This pins the three wiring
    points that make a *reading* surface pay exactly like the desk: ``SectionPage`` (the reader,
    the Field player and the course page's section) passes both props on both of its cards,
    ``CourseDetail`` threads its own ``world.read`` mode into ``TextbookView``/``SectionPage``,
    and the bound chat pane reads the same durable mode instead of assuming one.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.src = (Path(__file__).resolve().parent.parent / "desktop" / "src")
        cls.learning = (cls.src / "70-learning.js").read_text(encoding="utf-8")
        cls.components = (cls.src / "80-components.js").read_text(encoding="utf-8")
        cls.course = (cls.src / "90-course.js").read_text(encoding="utf-8")

    def test_the_shared_card_owns_the_only_award_call(self) -> None:
        self.assertEqual(self.learning.count('rpc(\n        \'engagement.award\''), 1)
        self.assertIn("function useCheckAward(", self.learning)
        self.assertIn("courseId: row.course_id || null,\n          gameMode,", self.components)

    def test_both_section_cards_carry_the_gate(self) -> None:
        self.assertEqual(
            self.components.count("courseId: row.course_id || null,\n          gameMode,"), 2,
            "the reader and the Field player must both hand the card a course id and the gate",
        )
        self.assertIn("gameMode = false", self.components)

    def test_the_course_page_threads_its_durable_mode_down(self) -> None:
        self.assertIn("gameMode: courseGame", self.course)
        self.assertIn("gameMode\n    })", self.course)
        # The pane reads the mode the same way the course page does, never from a preference.
        self.assertIn("const courseGame = cbGameCourse(row, world.data ? world.data.presentation_mode : null)", self.course)

    def test_the_classroom_pays_through_the_same_hook(self) -> None:
        self.assertIn("const { award, resetAward, awardCheck } = useCheckAward({", self.learning)
        self.assertIn("gameMode: mode === 'game'", self.learning)
        self.assertIn("awardCheck(graded)", self.learning)


if __name__ == "__main__":
    unittest.main()