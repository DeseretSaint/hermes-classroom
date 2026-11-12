"""UI-K13 — the review queue has controls, and four other learner doors stop at their method.

The runtime plugin is one ESM file with no build step, so every render half of this suite loads the
shipped ``desktop/plugin.js`` (not a source copy) in jsdom with a stub ``@hermes/plugin-sdk`` and a
fake ``ctx.rest`` that records the envelopes the surfaces actually send.

What this proves:

* ``review.action`` — a due row offers snooze / stretch / drop; a row is Resume only when
  ``evidence.inspect``'s newest scheduling event is ``review_drop``; a never-dropped objective
  never offers Resume; every row the reads return renders with its controls (no display cap, so a
  paused row stays reachable past the eighth due row); a backlog larger than `review.queue`'s `cap`
  is disclosed with the read's own counts instead of looking like a complete queue; each control's
  accessible name names its section; a stale revision refusal is shown and records nothing; and the
  resume door is driven end to end through the real kernel handlers (no synthetic row, no mocked
  method).
* ``usage.summary`` — the settings read-out shows the backend's own fields, never a zero for a
  count it did not record, never calls an unrecorded field "recorded", and shows no total at all
  when the read fails.
* ``syllabus.delete`` — removal needs a confirm, shows the backend's ``deleted: true`` as evidence,
  and a bound syllabus is refused with its course ids.
* ``pronunciation.dispute`` — a dispute is recorded beside the score, shown as evidence, an empty
  note never reaches the backend, and a refusal records nothing.

``source.revalidate`` is deliberately absent: it is parked by ruling until the host fetch seam
exists, so a button here would lie. ``engagement.award`` still has no caller.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import SDK_STUB, _desktop_node_modules
from tests.test_review_evidence import ReviewCase

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"
SRC = ROOT / "desktop" / "src"

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
globalThis.HTMLTextAreaElement = dom.window.HTMLTextAreaElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const calls = []
const scripted = payload.responses || {}
const taken = {}
const pick = (key) => {
  const entry = scripted[key]
  if (entry === undefined) return null
  if (Array.isArray(entry)) {
    const index = taken[key] || 0
    taken[key] = index + 1
    return entry[Math.min(index, entry.length - 1)]
  }
  return entry
}
const implemented = payload.implemented || []

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = (options && options.body) || null
  if (base === '/rpc') {
    calls.push({
      kind: 'rpc',
      method: body && body.method,
      payload: body && body.payload,
      expected_revision: body && body.expected_revision,
      idempotency_key: body && body.idempotency_key
    })
    return pick(body && body.method) || { ok: true, contract_version: 26, operation_id: 't', result: {} }
  }
  calls.push({ kind: 'rest', path: base, body })
  if (base === '/runtime') {
    return pick('/runtime') || { wire_version: 26, implemented_methods: implemented, single_home_host: false }
  }
  return pick(base) || { ok: true }
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => {
    const handle = window.setTimeout(fn, ms)
    return () => window.clearTimeout(handle)
  },
  clearTimeout: (handle) => window.clearTimeout(handle),
  storage: {
    get: () => null,
    set: () => {},
    remove: () => {}
  }
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const flush = async (ms = 60) => {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) })
}
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const buttons = () => [...document.querySelectorAll('button')]
const click = async (node) => {
  if (!node) throw new Error('no such control')
  await act(async () => { node.click() })
  await flush()
}
const setField = async (node, value) => {
  const proto = window.HTMLTextAreaElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(node, value)
  await act(async () => {
    node.dispatchEvent(new window.Event('input', { bubbles: true }))
  })
}
let removed = false
let recorded = null

const scene = payload.scene

if (scene === 'review') {
  await act(async () => {
    root.render(React.createElement(mod.ReviewDuePanel, {
      enrollmentId: payload.enrollment_id || 'enr_1',
      revision: payload.revision === undefined ? 7 : payload.revision,
      review: payload.review || null,
      evidence: payload.evidence || null,
      onRecorded: (rev) => { recorded = rev },
      onOpenSection: () => {}
    }))
  })
  await flush()
  const actions = payload.actions || []
  for (const action of actions) {
    const target = document.querySelector('[data-cb-review-target="' + action.objective_id + '"]' + '[data-cb-review-action="' + action.action + '"]')
    await click(target)
  }
} else if (scene === 'usage') {
  await act(async () => {
    root.render(React.createElement(mod.CbGenerationUsage, {}))
  })
  await flush(200)
} else if (scene === 'pronounce') {
  await act(async () => {
    root.render(React.createElement(mod.PronunciationDispute, {
      enrollmentId: 'enr_1',
      attemptId: payload.attempt_id,
      implemented: new Set(implemented)
    }))
  })
  await flush()
  const opener = document.querySelector('[data-cb-pronunciation-dispute-open]')
  if (opener) {
    await click(opener)
    const note = document.querySelector('[data-cb-pronunciation-dispute-note]')
    if (note && payload.note !== undefined) await setField(note, payload.note)
    await click(document.querySelector('[data-cb-pronunciation-dispute-submit]'))
  }
} else if (scene === 'syllabus') {
  await act(async () => {
    root.render(React.createElement(mod.SyllabusParseReview, {
      parsed: payload.parsed,
      blocks: [],
      busy: false,
      onBack: () => {},
      onContinue: () => {},
      onRemoved: () => { removed = true }
    }))
  })
  await flush()
  await click(document.querySelector('[data-cb-syllabus-remove-start]'))
  await click(document.querySelector('[data-cb-syllabus-remove-confirm]'))
  const evidence = text(document.querySelector('[data-cb-syllabus-remove-evidence]'))
  const done = document.querySelector('[data-cb-syllabus-remove-done]')
  if (done) await click(done)
  globalThis.__CB_EVIDENCE__ = evidence
} else {
  throw new Error('unknown scene ' + scene)
}

const attr = (selector, name) => {
  const node = document.querySelector(selector)
  return node ? node.getAttribute(name) : null
}
const body = text(document.body)
const out = {
  scene,
  calls,
  text: body,
  removed,
  recorded,
  evidence: globalThis.__CB_EVIDENCE__ || null,
  rowActions: Object.fromEntries(
    [...document.querySelectorAll('[data-cb-review-item]')].map((row) => [
      row.getAttribute('data-cb-review-item'),
      [...row.querySelectorAll('[data-cb-review-action]')].map((node) => node.getAttribute('data-cb-review-action'))
    ])
  ),
  rowPaused: Object.fromEntries(
    [...document.querySelectorAll('[data-cb-review-item]')].map((row) => [
      row.getAttribute('data-cb-review-item'),
      row.getAttribute('data-cb-review-paused')
    ])
  ),
  rowControlLabels: Object.fromEntries(
    [...document.querySelectorAll('[data-cb-review-item]')].map((row) => [
      row.getAttribute('data-cb-review-item'),
      [...row.querySelectorAll('button')].map((node) => node.getAttribute('aria-label'))
    ])
  ),
  refunds: {
    reviewRefusal: attr('[data-cb-review-refusal]', 'data-cb-review-refusal'),
    usageCalls: attr('[data-cb-usage-calls]', 'data-cb-usage-calls'),
    usageError: attr('[data-cb-usage-error]', 'data-cb-usage-error'),
    usageUnknown: attr('[data-cb-usage-unknown]', 'data-cb-usage-unknown'),
    disputeRefusal: attr('[data-cb-pronunciation-dispute-refusal]', 'data-cb-pronunciation-dispute-refusal'),
    disputeId: attr('[data-cb-pronunciation-dispute-id]', 'data-cb-pronunciation-dispute-id'),
    disputeState: attr('[data-cb-pronunciation-dispute]', 'data-cb-pronunciation-dispute'),
    syllabusRemove: attr('[data-cb-syllabus-remove]', 'data-cb-syllabus-remove'),
    syllabusEvidence: attr('[data-cb-syllabus-remove-evidence]', 'data-cb-syllabus-remove-evidence'),
    syllabusRefusal: attr('[data-cb-syllabus-remove-refusal]', 'data-cb-syllabus-remove-refusal'),
    reviewActions: [...document.querySelectorAll('[data-cb-review-action]')].map((node) => node.getAttribute('data-cb-review-action')),
    reviewHidden: attr('[data-cb-review-hidden]', 'data-cb-review-hidden')
  }
}
process.stdout.write(JSON.stringify(out))
"""


class DoorRenderMixin:
    """Shared jsdom runner. A mixin, not a TestCase: its scenes belong to one door each."""

    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None or not PLUGIN_JS.is_file():
            raise unittest.SkipTest("no host react/react-dom install to render the shipped module")

    def run_scene(self, payload: dict) -> dict:
        modules = _desktop_node_modules()
        assert modules is not None
        root = Path(tempfile.mkdtemp(prefix="cb-uik13-"))
        self.addCleanup(shutil.rmtree, root, True)
        # A private node_modules per run: the SDK stub never touches the host's shared tree.
        (root / "node_modules").mkdir(parents=True, exist_ok=True)
        for entry in modules.iterdir():
            if entry.name == "@hermes":
                (root / "node_modules" / "@hermes").mkdir(exist_ok=True)
                for child in entry.iterdir():
                    if child.name == "plugin-sdk":
                        continue
                    target = root / "node_modules" / "@hermes" / child.name
                    if not target.exists():
                        target.symlink_to(child, target_is_directory=child.is_dir())
            else:
                target = root / "node_modules" / entry.name
                if not target.exists():
                    target.symlink_to(entry, target_is_directory=entry.is_dir())
        sdk = root / "node_modules" / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True, exist_ok=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}),
            encoding="utf-8",
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        # The real module and the harness live beside the private node_modules so a bare
        # `import` resolves react from the temp root, not from the repo.
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        (root / "payload.json").write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", "harness.mjs", "payload.json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "NODE_PATH": str(root / "node_modules")},
        )
        if result.returncode != 0:
            self.fail(f"jsdom harness failed:\n{result.stderr}\n{result.stdout}")
        return json.loads(result.stdout)


def queue_view(items: list[dict], *, total_due: int | None = None) -> dict:
    """The `review.queue` response shape the shipped panel consumes (contract frozen)."""
    overdue = [item for item in items if item.get("overdue")]
    return {
        "enrollment_id": "enr_1",
        "now": "2026-11-11T20:00:00Z",
        "cap": 25,
        "total_due": len(overdue) if total_due is None else total_due,
        "total_overdue": len(overdue) if total_due is None else total_due,
        "total_scheduled": len(items),
        "items": items,
        "upcoming_hidden": 0,
    }


def review_item(objective_id: str, *, state: str = "independent_evidence", overdue: bool = True) -> dict:
    return {
        "objective_id": objective_id,
        "title": f"Section {objective_id}",
        "ordinal": 1,
        "evidence_target": "independent",
        "state": state,
        "interval_days": 7,
        "step": 1,
        "ladder_days": [1, 3, 7, 14],
        "last_evidence_at": "2026-11-01T20:00:00Z",
        "due_at": "2026-11-04T20:00:00Z",
        "overdue": overdue,
        "overdue_days": 7 if overdue else 0,
    }


def evidence_view(objectives: list[dict], events: list[dict]) -> dict:
    """The `evidence.inspect` shape: layer-1 events (newest first) plus layer-2 objectives."""
    return {
        "l1": {"enrollment_id": "enr_1", "objective_id": None, "attempts": [], "events": events},
        "l2": {"enrollment_id": "enr_1", "objective_id": None, "objectives": objectives},
        "l3": {"enrollment_id": "enr_1", "recommendations": [], "as_of": None, "is_persona": False},
        "disputes": {"enrollment_id": "enr_1", "disputes": [], "count": 0, "truncated": False},
    }


def evidence_objective(objective_id: str, *, state: str = "independent_evidence") -> dict:
    return {
        "objective_id": objective_id,
        "title": f"Section {objective_id}",
        "ordinal": 1,
        "evidence_target": "independent",
        "state": state,
        "independent": True,
        "delayed": False,
        "L2_evidence_ids": [],
        "independent_at": "2026-11-01T20:00:00Z",
        "attempt_classes": {"cold": 1},
        "criteria": [],
    }


def layer1_event(objective_id: str, kind: str, created_at: str) -> dict:
    return {
        "evidence_id": f"evd_{objective_id}_{kind}",
        "objective_id": objective_id,
        "attempt_id": None,
        "layer": 1,
        "kind": kind,
        "evidence_class": "self_reported",
        "is_action": True,
        "created_at": created_at,
    }


class ReviewDoorRenderTest(DoorRenderMixin, unittest.TestCase):
    """1. ``review.action`` — four scheduling actions, one fence, no invented "dropped" state."""

    def test_a_never_dropped_overdue_row_offers_the_three_queue_actions_and_no_resume(self) -> None:
        # Before `refresh_due` runs, an overdue objective is exactly `independent_evidence` +
        # `overdue: true`. Inferring "dropped" from that state hid snooze/stretch/drop and printed
        # a sentence that was false; only a `review_drop` event may say a row was dropped.
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([review_item("obj_due")]),
                "evidence": evidence_view([evidence_objective("obj_due")], []),
            }
        )
        self.assertEqual(out["rowActions"].get("obj_due"), ["snooze", "stretch", "drop"])
        self.assertNotIn("resume", out["refunds"]["reviewActions"])
        self.assertEqual(out["rowPaused"].get("obj_due"), "false")
        self.assertIn("due 2026-11-04", out["text"])
        self.assertNotIn("You took this out of the queue", out["text"])

    def test_an_upcoming_row_is_not_a_queue_row(self) -> None:
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                # Scheduled but not due, and not in review: the panel must not invent a row for it.
                "review": queue_view([review_item("obj_later", state="independent_evidence", overdue=False)]),
                "evidence": evidence_view([], []),
            }
        )
        self.assertEqual(out["rowActions"], {})

    def test_a_dropped_objective_is_a_resume_row_derived_from_evidence(self) -> None:
        # The queue cannot express this row: the panel receives an empty queue and the backend's
        # own `review_drop` event, and must still offer exactly one control.
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([]),
                "evidence": evidence_view(
                    [evidence_objective("obj_dropped")],
                    [layer1_event("obj_dropped", "review_drop", "2026-11-10T20:00:00Z")],
                ),
            }
        )
        self.assertEqual(out["rowActions"].get("obj_dropped"), ["resume"])
        self.assertEqual(out["rowPaused"].get("obj_dropped"), "true")
        self.assertIn("dropped 2026-11-10", out["text"])

    def test_a_resumed_objective_is_not_offered_resume_again(self) -> None:
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "review": queue_view([review_item("obj_back", state="review_due")]),
                "evidence": evidence_view(
                    [evidence_objective("obj_back", state="review_due")],
                    [
                        layer1_event("obj_back", "review_resume", "2026-11-11T19:00:00Z"),
                        layer1_event("obj_back", "review_drop", "2026-11-10T20:00:00Z"),
                    ],
                ),
            }
        )
        self.assertEqual(out["rowActions"].get("obj_back"), ["snooze", "stretch", "drop"])
        self.assertNotIn("resume", out["refunds"]["reviewActions"])

    def test_every_due_row_keeps_its_controls_past_the_eighth(self) -> None:
        # A display cap of 8 silently rendered rows 9-10 with no control while the banner above
        # still counted all ten. Every row the page read must carry its controls.
        items = [review_item(f"obj_{index:02d}") for index in range(1, 11)]
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view(items),
                "evidence": evidence_view([evidence_objective(f"obj_{index:02d}") for index in range(1, 11)], []),
            }
        )
        rendered = sorted(out["rowActions"])
        self.assertEqual(rendered, [f"obj_{index:02d}" for index in range(1, 11)])
        for objective_id in rendered:
            self.assertEqual(out["rowActions"][objective_id], ["snooze", "stretch", "drop"], objective_id)

    def test_a_backlog_larger_than_the_read_says_how_many_rows_are_hidden(self) -> None:
        # `review.queue`'s `cap` (25 here) bounds `items` only; `total_due` / `total_overdue` are the
        # whole backlog. A panel that renders the 25 returned rows beside a banner counting 30 hid
        # five objectives' controls without a word. The line must name the read's real counts.
        items = [review_item(f"obj_{index:02d}") for index in range(1, 26)]
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view(items, total_due=30),
                "evidence": evidence_view([evidence_objective(f"obj_{index:02d}") for index in range(1, 26)], []),
            }
        )
        self.assertEqual(len(out["rowActions"]), 25)
        for objective_id, actions in out["rowActions"].items():
            self.assertEqual(actions, ["snooze", "stretch", "drop"], objective_id)
        self.assertEqual(out["refunds"]["reviewHidden"], "5")
        self.assertIn("Showing 25 of 30 due sections.", out["text"])
        self.assertIn("The other 5 return as you clear these.", out["text"])

    def test_the_hidden_line_counts_what_the_read_reported_not_a_constant(self) -> None:
        # A second shape proves the sentence is computed from the read (2 rows, 3 due, one hidden)
        # rather than echoing the cap or a hard-coded backlog.
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([review_item("obj_a"), review_item("obj_b")], total_due=3),
                "evidence": evidence_view([evidence_objective("obj_a"), evidence_objective("obj_b")], []),
            }
        )
        self.assertEqual(out["refunds"]["reviewHidden"], "1")
        self.assertIn("Showing 2 of 3 due sections.", out["text"])
        self.assertIn("One more returns as you clear these.", out["text"])

    def test_a_complete_queue_says_nothing_about_hidden_rows(self) -> None:
        # When the read is the whole queue there is no backlog to disclose, and the panel must not
        # imply one exists.
        items = [review_item(f"obj_{index:02d}") for index in range(1, 4)]
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view(items),
                "evidence": evidence_view([evidence_objective(f"obj_{index:02d}") for index in range(1, 4)], []),
            }
        )
        self.assertIsNone(out["refunds"]["reviewHidden"])
        self.assertNotIn("as you clear these", out["text"])
        self.assertEqual(len(out["rowActions"]), 3)

    def test_an_empty_read_with_a_real_backlog_still_says_the_backlog_is_not_shown(self) -> None:
        # The read returned no rows but the contract counts 30 due. An empty panel would read as an
        # empty queue, which the contract exists to prevent.
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([], total_due=30),
                "evidence": evidence_view([], []),
            }
        )
        self.assertEqual(out["rowActions"], {})
        self.assertEqual(out["refunds"]["reviewHidden"], "30")
        self.assertIn("Showing 0 of 30 due sections.", out["text"])

    def test_a_dropped_row_stays_visible_when_many_sections_are_due(self) -> None:
        # The reviewer's case: 8 due rows plus one dropped objective. The dropped row is not in
        # `review.queue`; if the panel cuts the tail of its merged list, no Resume control exists
        # anywhere on the page while the banner still says a section is out of the queue.
        due = [review_item(f"obj_{index:02d}") for index in range(1, 9)]
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view(due),
                "evidence": evidence_view(
                    [evidence_objective(f"obj_{index:02d}") for index in range(1, 9)]
                    + [evidence_objective("obj_dropped")],
                    [layer1_event("obj_dropped", "review_drop", "2026-11-10T20:00:00Z")],
                ),
                "actions": [{"objective_id": "obj_dropped", "action": "resume"}],
                "responses": {
                    "review.action": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "revision": 8,
                        "result": {
                            "objective_id": "obj_dropped",
                            "action": "resume",
                            "recorded_at": "2026-11-11T20:05:00Z",
                            "state": "review_due",
                            "due_at": "2026-11-11T20:05:00Z",
                        },
                    }
                },
            }
        )
        self.assertEqual(out["rowActions"].get("obj_dropped"), ["resume"])
        self.assertEqual(out["rowPaused"].get("obj_dropped"), "true")
        self.assertEqual(len(out["rowActions"]), 9, "every due row and the paused row render")
        call = next(item for item in out["calls"] if item.get("method") == "review.action")
        self.assertEqual(call["payload"]["action"], "resume")
        self.assertEqual(call["payload"]["objective_id"], "obj_dropped")
        self.assertIn("Resume recorded", out["text"])

    def test_each_review_control_names_its_section(self) -> None:
        # Three rows of "Snooze" are three identical accessible names without a target. Each
        # control must name the section it acts on.
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([review_item(f"obj_{index}") for index in (1, 2, 3)]),
                "evidence": evidence_view([evidence_objective(f"obj_{index}") for index in (1, 2, 3)], []),
            }
        )
        labels = out["rowControlLabels"]
        for objective_id in ("obj_1", "obj_2", "obj_3"):
            row = labels[objective_id]
            self.assertTrue(all(row), f"every control on {objective_id} has an aria-label: {row}")
        snoozes = [labels[key][1] for key in ("obj_1", "obj_2", "obj_3")]
        self.assertEqual(len(set(snoozes)), 3, snoozes)
        self.assertTrue(all("Section obj_" in label for label in snoozes), snoozes)
        self.assertTrue(all(label.startswith("Snooze review of ") for label in snoozes), snoozes)
        for objective_id in ("obj_1", "obj_2", "obj_3"):
            opens = [label for label in labels[objective_id] if label and label.startswith("Open ")]
            self.assertEqual(len(opens), 1, objective_id)
            self.assertIn(f"Section {objective_id}", opens[0])

    def test_review_snooze_calls_review_action_with_the_enrolment_fence(self) -> None:
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([review_item("obj_due")]),
                "evidence": evidence_view([evidence_objective("obj_due")], []),
                "actions": [{"objective_id": "obj_due", "action": "snooze"}],
                "responses": {
                    "review.action": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "revision": 8,
                        "result": {
                            "objective_id": "obj_due",
                            "action": "snooze",
                            "recorded_at": "2026-11-11T20:05:00Z",
                            "state": "review_due",
                            "due_at": "2026-11-18T20:05:00Z",
                        },
                    }
                },
            }
        )
        call = next(item for item in out["calls"] if item.get("method") == "review.action")
        self.assertEqual(call["payload"], {"enrollment_id": "enr_1", "objective_id": "obj_due", "action": "snooze"})
        self.assertEqual(call["expected_revision"], 7)
        self.assertEqual(call["idempotency_key"], "cb-review-obj_due-snooze-7")
        self.assertEqual(out["recorded"], 8)
        # The answer is shown as evidence, not only as a toast.
        self.assertIn("Snooze recorded", out["text"])
        self.assertIn("next due 2026-11-18", out["text"])

    def test_review_refusal_is_shown_and_no_due_date_is_invented(self) -> None:
        out = self.run_scene(
            {
                "scene": "review",
                "implemented": ["review.queue", "review.action", "evidence.inspect"],
                "revision": 7,
                "review": queue_view([review_item("obj_due")]),
                "evidence": evidence_view([evidence_objective("obj_due")], []),
                "actions": [{"objective_id": "obj_due", "action": "drop"}],
                "responses": {
                    "review.action": {
                        "ok": False,
                        "contract_version": 26,
                        "operation_id": "t",
                        "error": {
                            "code": "STALE_REVISION",
                            "message": "the enrollment moved on.",
                            "details": {"current_revision": 9},
                        },
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["reviewRefusal"], "STALE_REVISION")
        self.assertIn("The queue is unchanged", out["text"])
        self.assertNotIn("Drop recorded", out["text"])
        # The refusal names the revision the backend expects next; the page adopts it.
        self.assertEqual(out["recorded"], 9)


class ReviewResumeReachabilityTest(DoorRenderMixin, ReviewCase):
    """The resume door, driven end to end through the real handlers and the shipped panel.

    No synthetic row: the backend's own drop is what makes the objective disappear from
    `review.queue`, its own `review_drop` event is what makes the panel offer resume, and its own
    handler records the resume that puts the objective back in the queue.
    """

    def setUp(self) -> None:
        super().setUp()
        self.lesson = self.prepare_multi(1)
        self.objective_id = self.lesson["objective_ids"][0]
        self.pass_objective(self.lesson, self.objective_id)
        self.backdate(self.objective_id, days=10)

    def revision(self) -> int:
        return int(self.scalar("SELECT revision FROM enrollments WHERE id = ?", (self.lesson["enrollment_id"],)))

    def queue(self) -> dict:
        return self.ok("review.queue", {"enrollment_id": self.lesson["enrollment_id"], "cap": 25})["result"]

    def evidence(self) -> dict:
        return self.ok("evidence.inspect", {"enrollment_id": self.lesson["enrollment_id"], "limit": 200})["result"]

    def test_drop_then_resume_through_the_shipped_panel(self) -> None:
        before = self.queue()
        self.assertEqual(before["total_due"], 1)
        self.assertEqual(before["items"][0]["objective_id"], self.objective_id)
        # The pre-drop row really is `independent_evidence` + overdue: the state the panel must
        # not read as "dropped".
        self.assertEqual(before["items"][0]["state"], "independent_evidence")

        dropped = self.ok(
            "review.action",
            {"enrollment_id": self.lesson["enrollment_id"], "objective_id": self.objective_id,
             "action": "drop"},
            expected_revision=self.revision(),
            idempotency_key="uik13-drop",
        )
        self.assertIsNone(dropped["result"]["due_at"])
        after_drop = self.queue()
        self.assertEqual(after_drop["items"], [], "review.queue cannot express a dropped item")

        # The panel receives exactly what the page reads: the queue and the evidence bundle.
        out = self.run_scene(
            {
                "scene": "review",
                "enrollment_id": self.lesson["enrollment_id"],
                "revision": self.revision(),
                "review": after_drop,
                "evidence": self.evidence(),
                "actions": [{"objective_id": self.objective_id, "action": "resume"}],
            }
        )
        self.assertEqual(out["rowActions"].get(self.objective_id), ["resume"])
        self.assertEqual(out["rowPaused"].get(self.objective_id), "true")

        # The control's own payload is what goes back through the kernel — no hand-built request.
        call = next(item for item in out["calls"] if item.get("method") == "review.action")
        self.assertEqual(call["payload"]["action"], "resume")
        self.assertEqual(call["payload"]["objective_id"], self.objective_id)
        resumed = self.ok(
            "review.action",
            call["payload"],
            expected_revision=call["expected_revision"],
            idempotency_key=call["idempotency_key"],
        )
        self.assertEqual(resumed["result"]["state"], "review_due")
        self.assertIsNotNone(resumed["result"]["due_at"])

        # Durable state: a `review_resume` event, the objective back in the queue, and the paused
        # row gone from the derived list. The attempt row is not compared here: it can carry
        # microsecond precision while the scheduling events are second-precision, so only the
        # scheduler's own events decide which scheduling event is newest.
        events = [
            event
            for event in self.evidence()["l1"]["events"]
            if event["objective_id"] == self.objective_id
        ]
        scheduling = [event["kind"] for event in events if event["kind"] in ("review_drop", "review_resume")]
        self.assertEqual(scheduling[0], "review_resume")
        self.assertIn("review_drop", scheduling)
        back = self.queue()
        self.assertEqual([item["objective_id"] for item in back["items"]], [self.objective_id])

        emptied = self.run_scene(
            {
                "scene": "review",
                "revision": self.revision(),
                "review": back,
                "evidence": self.evidence(),
            }
        )
        self.assertNotIn("resume", emptied["rowActions"].get(self.objective_id, []))

    def test_a_stale_revision_refuses_the_resume_and_records_nothing(self) -> None:
        self.ok(
            "review.action",
            {"enrollment_id": self.lesson["enrollment_id"], "objective_id": self.objective_id,
             "action": "drop"},
            expected_revision=self.revision(),
            idempotency_key="uik13-drop-stale",
        )
        stale = self.revision() - 1
        refused = self.dispatch(
            "review.action",
            {"enrollment_id": self.lesson["enrollment_id"], "objective_id": self.objective_id,
             "action": "resume"},
            expected_revision=stale,
            idempotency_key="uik13-resume-stale",
        )
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "STALE_REVISION")
        kinds = [
            event["kind"]
            for event in self.evidence()["l1"]["events"]
            if event["objective_id"] == self.objective_id
        ]
        self.assertNotIn("review_resume", kinds)
        self.assertEqual(self.queue()["items"], [])


class DoorSourceTest(unittest.TestCase):
    """Source-level half: every method name now has a call site, and XP still does not."""

    def test_every_ledger_door_has_a_call_site(self) -> None:
        text = PLUGIN_JS.read_text(encoding="utf-8")
        for call in (
            "review.action",
            "usage.summary",
            "syllabus.delete",
            "pronunciation.dispute",
        ):
            self.assertIn(f"'{call}'", text, f"{call} has no call site in the shipped bundle")

    def test_engagement_award_is_left_alone(self) -> None:
        # The card said to leave `engagement.award` alone. On this base it already has a caller
        # (ClassroomV3Surface, 70-learning.js); this change neither adds nor removes one, so the
        # only assertion that belongs here is that none of this card's surfaces mentions it.
        for name in ("30-home.js", "60-syllabus.js", "62-syllabus-surfaces.js", "90-course.js"):
            self.assertNotIn("engagement.award", (SRC / name).read_text(encoding="utf-8"), name)

    def test_the_settings_sheet_mounts_the_usage_read_out(self) -> None:
        text = (SRC / "30-home.js").read_text(encoding="utf-8")
        self.assertIn("id: 'usage'", text)
        self.assertIn("jsx(CbGenerationUsage", text)

    def test_the_course_page_mounts_the_review_panel(self) -> None:
        text = (SRC / "90-course.js").read_text(encoding="utf-8")
        self.assertIn("jsx(ReviewDuePanel", text)
        # The paused derivation is bounded by the contract's own maximum.
        self.assertIn("limit: 200", text)


class UsageDoorRenderTest(DoorRenderMixin, unittest.TestCase):
    def test_usage_shows_the_backend_fields_and_never_invents_a_zero(self) -> None:
        out = self.run_scene(
            {
                "scene": "usage",
                "implemented": ["usage.summary"],
                "responses": {
                    "usage.summary": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "result": {
                            "calls": 12,
                            "tokens": {"input": 3400, "output": None, "cache_read": None, "cache_write": None},
                            "artifacts": 3,
                            "unknown_fields": ["latency_ms"],
                        },
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["usageCalls"], "12")
        self.assertIn("Generation calls: 12", out["text"])
        self.assertIn("Tokens in: 3,400", out["text"])
        self.assertIn("out: not recorded", out["text"])
        self.assertIn("Cache read: not recorded", out["text"])
        self.assertEqual(out["refunds"]["usageUnknown"], "1")
        self.assertIn("latency_ms", out["text"])
        self.assertIn("Not recorded on every usage row: latency_ms.", out["text"])
        self.assertNotIn("Also recorded", out["text"])

    def test_usage_does_not_call_unrecorded_fields_recorded(self) -> None:
        # `domain.usage_summary` puts a token field in `unknown_fields` exactly when a usage row
        # recorded no value for it, so a fresh profile returns the same four names it prints
        # "not recorded" for above. The block must not then say they were "also recorded".
        out = self.run_scene(
            {
                "scene": "usage",
                "implemented": ["usage.summary"],
                "responses": {
                    "usage.summary": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "result": {
                            "calls": 0,
                            "tokens": {
                                "input": None,
                                "output": None,
                                "cache_read": None,
                                "cache_write": None,
                            },
                            "artifacts": 0,
                            "unknown_fields": ["cache_read", "cache_write", "input", "output"],
                        },
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["usageUnknown"], "4")
        text = out["text"]
        self.assertNotIn("Also recorded", text)
        self.assertNotIn("recorded, and not read here", text)
        self.assertIn("Not recorded on every usage row: cache_read, cache_write, input, output.", text)
        self.assertIn("Tokens in: not recorded · out: not recorded", text)
        # The only statement about a missing count is "not recorded"; nothing claims a total.
        self.assertNotIn("Generation calls: 0 ·", text)

    def test_usage_refusal_shows_no_totals(self) -> None:
        out = self.run_scene(
            {
                "scene": "usage",
                "implemented": ["usage.summary"],
                "responses": {
                    "usage.summary": {
                        "ok": False,
                        "contract_version": 26,
                        "operation_id": "t",
                        "error": {"code": "HOST_UNAVAILABLE", "message": "the backend is not reachable."},
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["usageError"], "HOST_UNAVAILABLE")
        self.assertIsNone(out["refunds"]["usageCalls"])
        self.assertIn("No usage total is shown", out["text"])


class PronounceDoorRenderTest(DoorRenderMixin, unittest.TestCase):
    def test_a_dispute_is_recorded_and_shown_as_evidence(self) -> None:
        out = self.run_scene(
            {
                "scene": "pronounce",
                "implemented": ["pronunciation.dispute"],
                "attempt_id": "prn_abc",
                "note": "It heard the wrong word: I said suki, not tsuki.",
                "responses": {
                    "pronunciation.dispute": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "revision": 4,
                        "result": {"dispute_id": "dsp_123", "state": "open", "revision": 4},
                    }
                },
            }
        )
        call = next(item for item in out["calls"] if item.get("method") == "pronunciation.dispute")
        self.assertEqual(call["payload"]["attempt_id"], "prn_abc")
        self.assertEqual(call["payload"]["enrollment_id"], "enr_1")
        self.assertIn("suki", call["payload"]["note"])
        self.assertEqual(out["refunds"]["disputeId"], "dsp_123")
        self.assertEqual(out["refunds"]["disputeState"], "recorded")
        self.assertIn("Dispute recorded and open", out["text"])
        self.assertIn("unchanged", out["text"])

    def test_an_empty_note_is_refused_before_any_call(self) -> None:
        out = self.run_scene(
            {
                "scene": "pronounce",
                "implemented": ["pronunciation.dispute"],
                "attempt_id": "prn_abc",
                "note": "",
            }
        )
        self.assertFalse([item for item in out["calls"] if item.get("method") == "pronunciation.dispute"])
        self.assertEqual(out["refunds"]["disputeRefusal"], "VALIDATION_FAILED")

    def test_a_refused_dispute_records_nothing(self) -> None:
        out = self.run_scene(
            {
                "scene": "pronounce",
                "implemented": ["pronunciation.dispute"],
                "attempt_id": "prn_abc",
                "note": "The recogniser heard the wrong word.",
                "responses": {
                    "pronunciation.dispute": {
                        "ok": False,
                        "contract_version": 26,
                        "operation_id": "t",
                        "error": {"code": "NOT_FOUND", "message": "no such pronunciation attempt."},
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["disputeRefusal"], "NOT_FOUND")
        self.assertIsNone(out["refunds"]["disputeId"])
        self.assertNotIn("Dispute recorded", out["text"])

    def test_without_the_method_the_control_is_absent(self) -> None:
        out = self.run_scene(
            {
                "scene": "pronounce",
                "implemented": [],
                "attempt_id": "prn_abc",
                "note": "x",
            }
        )
        self.assertEqual(out["refunds"]["disputeState"], None)
        self.assertFalse([item for item in out["calls"] if item.get("method") == "pronunciation.dispute"])


class SyllabusDoorRenderTest(DoorRenderMixin, unittest.TestCase):
    PARSED = {
        "syllabus_id": "syl_1",
        "revision": 1,
        "parse_state": "parsed",
        "document": {
            "course": {"code": {"value": "CS 101", "state": "extracted"}, "title": {"value": "Intro", "state": "extracted"}},
            "learning_outcomes": [],
            "weeks": [],
            "assessments": [],
            "policies": [],
            "unknowns": [],
            "coverage": {"pages": 1, "items_total": 0, "items_extracted": 0},
        },
    }

    def test_remove_needs_a_confirm_then_shows_deleted_true(self) -> None:
        out = self.run_scene(
            {
                "scene": "syllabus",
                "implemented": ["syllabus.delete"],
                "parsed": self.PARSED,
                "responses": {
                    "syllabus.delete": {
                        "ok": True,
                        "contract_version": 26,
                        "operation_id": "t",
                        "revision": 0,
                        "result": {"deleted": True},
                    }
                },
            }
        )
        call = next(item for item in out["calls"] if item.get("method") == "syllabus.delete")
        self.assertEqual(call["payload"], {"syllabus_id": "syl_1"})
        self.assertEqual(out["refunds"]["syllabusEvidence"], "deleted")
        self.assertIn("deleted: true", out["evidence"] or "")
        self.assertTrue(out["removed"], "the surface did not leave the deleted syllabus")

    def test_a_bound_syllabus_is_refused_with_its_course_ids(self) -> None:
        out = self.run_scene(
            {
                "scene": "syllabus",
                "implemented": ["syllabus.delete"],
                "parsed": self.PARSED,
                "responses": {
                    "syllabus.delete": {
                        "ok": False,
                        "contract_version": 26,
                        "operation_id": "t",
                        "error": {
                            "code": "SYLLABUS_IN_USE",
                            "message": "this syllabus is bound to a live companion course.",
                            "details": {"course_ids": ["crs_9"]},
                        },
                    }
                },
            }
        )
        self.assertEqual(out["refunds"]["syllabusRefusal"], "SYLLABUS_IN_USE")
        self.assertIn("Still used by: crs_9", out["text"])
        self.assertIsNone(out["refunds"]["syllabusEvidence"])
        self.assertFalse(out["removed"], "a refused removal closed the surface")


if __name__ == "__main__":
    unittest.main()
