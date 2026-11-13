"""W2-3: the plan screen tells the truth, and the plan can be adjusted.

CREATE-EXPERIENCE items 3, 4 and 5, driven through the shipped module:

* a waiting plan render a ticking elapsed clock, the job's own `progress.stage` wording and the
  scope's honest band — and a job with no progress shows the band, never a percentage;
* a queued job's price reaches `startLearnerPlan`'s returned outcome and renders on the result
  screen as a plain "Estimated price" from backend numbers only;
* the create review step states how many sections are written before Create and says plainly that
  a price appears once the course is sized (no invented dollar figure);
* the learner surface gets **Adjust this plan** (title/evidence, remove, reorder) and **Ask for a
  change**, while **Approve plan** stays the single primary action. A saved learner edit sends the
  full ordered id list, is versioned, and the screen names the new plan version.

What this does NOT prove: a live backend. `tests/test_contracts.py` and the domain suites drive
`parent.plan.edit` / `plan.replan` against a real SQLite database.
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
from tests.kernel_support import KernelCase
from coursebook import db, domain

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

# The create form is not mounted here; its source is read for the pre-Create preflight sentence.
SOURCE_50 = ROOT / "desktop" / "src" / "50-create.js"

STUB = SDK_STUB
for _old, _new in (
    ("export const Input = () => null",
     "export const Input = (props) => el('input', { id: props.id, className: props.className, placeholder: props.placeholder, value: props.value, onChange: props.onChange })"),
    ("export const Textarea = () => null",
     "export const Textarea = (props) => el('textarea', { id: props.id, rows: props.rows, value: props.value, onChange: props.onChange })"),
    ("export const Select = () => null",
     "export const Select = (props) => el('div', { 'data-select-value': props.value }, props.children)"),
    ("export const SelectTrigger = () => null",
     "export const SelectTrigger = (props) => el('div', { id: props.id, className: props.className }, props.children)"),
    ("export const SelectValue = () => null", "export const SelectValue = () => null"),
    ("export const SelectContent = () => null",
     "export const SelectContent = (props) => el('div', null, props.children)"),
    ("export const SelectItem = () => null",
     "export const SelectItem = (props) => el('div', { 'data-select-item': props.value }, props.children)"),
):
    STUB = STUB.replace(_old, _new)

assert "export const Input = (props)" in STUB, "the SDK stub did not gain a real Input"

STATIC_HARNESS = r"""
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { CreatePriceEstimateLine, StudioPlanView, startLearnerPlan } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const objectives = [
  { objective_id: 'obj_a', ordinal: 1, title: 'Alpha', evidence_target: 'recall', state: 'not_started', check_state: 'none' },
  { objective_id: 'obj_b', ordinal: 2, title: 'Beta', evidence_target: 'comprehension', state: 'not_started', check_state: 'none' }
]
const base = {
  course: { course_id: 'crs_0123456789abcdef', enrollment_id: 'enr_0123456789abcdef', title: 'Order at a counter' },
  revision: 1,
  onRevision: () => {},
  book: null,
  brief: null,
  planJobHint: null,
  onChangeGoal: () => {},
  onJobSettled: () => {},
  onChanged: () => {},
  supported: () => true,
  surface: 'learner',
  outlineHidden: false,
  syllabusGate: null,
  review: null,
  onOpenReview: () => {},
  onDirtyChange: () => {}
}
const blankOutline = { status: 'ready', error: null, reload: () => {}, data: { plan: null, objectives: [] } }

const runningJob = {
  job_id: 'job_0123456789abcdef',
  kind: 'plan',
  state: 'running',
  progress: {
    stage: 'research',
    steps_done: 1,
    steps_total: 4,
    message: 'Researching 6 sources for the goal'
  },
  created_at: 1794466000,
  updated_at: 1794466010
}

const out = {}
out.withProgress = renderToStaticMarkup(
  React.createElement(StudioPlanView, {
    ...base,
    outline: blankOutline,
    planJobId: 'job_0123456789abcdef',
    planJob: runningJob,
    planScope: 'short'
  })
)
out.noProgress = renderToStaticMarkup(
  React.createElement(StudioPlanView, {
    ...base,
    outline: blankOutline,
    planJobId: 'job_0123456789abcdef',
    planJob: { job_id: 'job_0123456789abcdef', kind: 'plan', state: 'running', progress: {} },
    planScope: 'short'
  })
)
out.unknownScope = renderToStaticMarkup(
  React.createElement(StudioPlanView, {
    ...base,
    outline: blankOutline,
    planJobId: 'job_0123456789abcdef',
    planJob: { job_id: 'job_0123456789abcdef', kind: 'plan', state: 'queued', progress: {} },
    planScope: null
  })
)

const preflight = {
  minimum_cost_usd: 0.12,
  maximum_cost_usd: 0.48,
  minimum_calls: 3,
  maximum_calls: 12
}
out.priceEstimateLine = renderToStaticMarkup(React.createElement(CreatePriceEstimateLine, { estimate: preflight }))
out.priceEstimateAbsent = renderToStaticMarkup(React.createElement(CreatePriceEstimateLine, { estimate: null }))

const DECISION = {
  title: 'Coffee in Kyoto',
  goal: 'Order coffee and ask for the bill in Kyoto, politely.',
  recipe: 'casual',
  dials: { pace: 'steady', depth: 'working', assessment: 'graded', autonomy: 'guided' },
  locale: 'ja-JP',
  level: 'L0',
  subjectDomain: 'language',
  scope: 'short'
}
const calls = []
const call = async (method, body, options = {}) => {
  calls.push({ method, payload: body, options })
  if (method === 'course.create') return { ok: true, result: { course_id: 'course_1', plan_id: 'plan_draft_1' } }
  if (method === 'enrollment.create') return { ok: true, result: { enrollment_id: 'enr_1' } }
  if (method === 'jobs.create') {
    return { ok: true, result: { job_id: 'job_plan_1', state: 'queued', preflight } }
  }
  throw new Error(`unexpected method ${method}`)
}
out.outcome = await startLearnerPlan({ call, key: 'cb-course-create-key1', ...DECISION })
out.calls = calls
process.stdout.write(JSON.stringify(out))
"""

INTERACTION_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/', pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.KeyboardEvent = dom.window.KeyboardEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')
const calls = []
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const method = options && options.body && options.body.method
    calls.push({
      method,
      payload: options.body.payload,
      expected_revision: options.body.expected_revision,
      idempotency_key: options.body.idempotency_key
    })
    if (method === 'parent.plan.edit') {
      return {
        ok: true,
        contract_version: 20,
        operation_id: 'test',
        result: {
          plan_id: 'pln_0123456789abcdef',
          plan_version: 2,
          plan_hash: 'sha256:edited',
          objective_ids: options.body.payload.order || ['obj_a', 'obj_b'],
          changes_need_review: true,
          revision: 2
        }
      }
    }
    return { ok: true, contract_version: 20, operation_id: 'test', result: {} }
  }
  if (base === '/runtime') {
    return {
      ok: true,
      contract_version: 20,
      result: {
        wire_version: 20,
        implemented_methods: ['parent.plan.edit', 'plan.edit', 'plan.replan', 'plan.approve', 'jobs.create'],
        single_home_host: false
      }
    }
  }
  return { ok: true, result: {} }
}
mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {},
  setTimeout: (fn, ms) => { const h = window.setTimeout(fn, ms); return () => window.clearTimeout(h) },
  clearTimeout: (h) => window.clearTimeout(h)
})

const { createRoot } = await import('react-dom/client')
const container = document.getElementById('root')
const root = createRoot(container)
const flush = async (ms = 80) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const click = async (node) => {
  if (!node) throw new Error('click target missing')
  await act(async () => { node.click() })
  await flush()
}
const byText = (label) =>
  [...container.querySelectorAll('button')].find((node) => text(node) === label) || null
const row = (id) => container.querySelector(`[data-cb-objective="${id}"]`)
const primaries = () =>
  [...container.querySelectorAll('[data-cb-action="primary"]')].filter((node) => !node.disabled)

const objectives = [
  { objective_id: 'obj_a', ordinal: 1, title: 'Alpha', evidence_target: 'recall', state: 'not_started', check_state: 'none' },
  { objective_id: 'obj_b', ordinal: 2, title: 'Beta', evidence_target: 'comprehension', state: 'not_started', check_state: 'none' }
]
const validation = {
  approvable: true,
  verdict: 'pass',
  manual_authoring: false,
  reason: null
}
const draftBook = {
  status: 'ready',
  error: null,
  reload: () => {},
  data: {
    plan: { plan_id: 'pln_0123456789abcdef', state: 'draft', version: 1, plan_hash: 'sha256:plan', validation },
    objectives,
    sections: []
  }
}
const approvedBook = {
  ...draftBook,
  data: {
    plan: { plan_id: 'pln_0123456789abcdef', state: 'approved', version: 2, plan_hash: 'sha256:plan', validation },
    objectives,
    sections: []
  }
}
const render = async (book) => {
  await act(async () => {
    root.render(
      React.createElement(mod.StudioPlanView, {
        course: { course_id: 'crs_0123456789abcdef', enrollment_id: 'enr_0123456789abcdef', title: 'Order at a counter' },
        revision: 1,
        onRevision: () => {},
        outline: {
          status: 'ready',
          error: null,
          reload: () => {},
          data: { plan: book.data.plan, objectives }
        },
        book,
        brief: null,
        planJobId: null,
        planJobHint: null,
        onChangeGoal: () => {},
        onJobSettled: () => {},
        onChanged: () => {},
        supported: () => true,
        surface: 'learner',
        outlineHidden: false,
        syllabusGate: null,
        review: null,
        onOpenReview: () => {},
        onDirtyChange: () => {}
      })
    )
  })
  await flush()
}

const out = { before: {}, calls, after: {}, approved: {} }
await render(draftBook)
out.before.adjust = Boolean(byText('Adjust this plan'))
out.before.primaryCount = primaries().length
out.before.primaryLabels = primaries().map(text)

await click(byText('Adjust this plan'))
out.before.inEdit = Boolean(byText('Save changes'))
out.before.editText = text(container)
// Move Alpha below Beta: the editor's own Down control on the first row.
const down = [...row('obj_a').querySelectorAll('button')].find((node) => text(node) === 'Down')
out.before.downFound = Boolean(down)
await click(down)
out.before.afterDownText = text(container)
await click(byText('Save changes'))
await flush(120)
out.before.afterSaveText = text(container)

out.after.calls = calls.map((call) => ({ method: call.method, payload: call.payload, expected_revision: call.expected_revision }))
out.after.notice = text(container)
out.after.adjust = Boolean(byText('Adjust this plan'))
out.after.primaryCount = primaries().length
out.after.primaryLabels = primaries().map(text)

await render(approvedBook)
out.approved.askForChange = Boolean(byText('Ask for a change'))
out.approved.adjust = Boolean(byText('Adjust this plan'))

// The clock really ticks: mount the wait panel with a running job and read the clock twice.
await act(async () => {
  root.render(
    React.createElement(mod.PlanWritingPanel, {
      jobId: 'job_0123456789abcdef',
      job: {
        job_id: 'job_0123456789abcdef',
        state: 'running',
        progress: { stage: 'research', steps_done: 1, steps_total: 4, message: 'Researching 6 sources' }
      },
      scope: 'short',
      onSettled: () => {},
      onRunAgain: () => {}
    })
  )
})
await flush(60)
const elapsedNow = () => {
  const node = container.querySelector('[data-cb-plan-elapsed]')
  return node ? Number(node.getAttribute('data-cb-plan-elapsed')) : null
}
out.tick = { start: elapsedNow() }
await flush(1300)
out.tick.after = elapsedNow()
out.tick.text = text(container)
// Unmount so the panel's 1s interval is cleared and node can exit.
await act(async () => { root.render(null) })
await flush(30)

process.stdout.write(JSON.stringify(out))
"""


def _node_root(prefix: str, harness: str):
    modules = _desktop_node_modules()
    if modules is None:
        return None
    tmp = tempfile.TemporaryDirectory(prefix=prefix)
    root = Path(tmp.name)
    (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "harness.mjs").write_text(harness, encoding="utf-8")
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
    return tmp, root


def _run(root: Path, case: dict) -> dict:
    case_file = root / "case.json"
    case_file.write_text(json.dumps(case), encoding="utf-8")
    result = subprocess.run(
        ["node", str(root / "harness.mjs"), str(case_file)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr[-3000:])
    return json.loads(result.stdout)


VISIBLE = re.compile(r"<[^>]+>")
PERCENT = re.compile(r"\d+\s*%")


def visible_text(html: str) -> str:
    return re.sub(r"\s+", " ", VISIBLE.sub(" ", html or "")).strip()


class PlanWaitTruth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        built = _node_root("coursebook-w23-static-", STATIC_HARNESS)
        if built is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp, root = built
        cls.out = _run(root, {})

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # -- item 3: clock, real stage, honest band ------------------------------------------------
    def test_a_waiting_plan_renders_a_clock_the_real_stage_and_the_scope_band(self) -> None:
        html = self.out["withProgress"]
        text = visible_text(html)
        self.assertIn('data-cb-plan-elapsed="0"', html)
        self.assertIn("0s elapsed", text)
        self.assertIn('data-cb-plan-stage="research"', html)
        self.assertIn("Researching the goal", text)
        self.assertIn('data-cb-plan-message=""', html)
        self.assertIn("Researching 6 sources for the goal", text)
        self.assertIn('data-cb-plan-band="short"', html)
        self.assertIn("Short courses usually take a few minutes.", text)
        # steps come from progress.steps_done/steps_total, not from a UI guess
        self.assertIn("Step 1 of 4", text)

    def test_a_plan_with_no_progress_shows_the_band_and_never_a_percentage(self) -> None:
        html = self.out["noProgress"]
        text = visible_text(html)
        self.assertIn('data-cb-plan-band="short"', html)
        self.assertIn("Short courses usually take a few minutes.", text)
        self.assertIsNone(PERCENT.search(text), text)
        self.assertNotIn("data-cb-plan-stage", html)
        self.assertNotIn("data-cb-plan-message", html)
        # The old opaque sentence is gone.
        self.assertNotIn("no progress percentage to show", text)

    def test_the_band_is_honest_when_the_scope_is_unknown(self) -> None:
        text = visible_text(self.out["unknownScope"])
        self.assertIn("A plan usually takes a few minutes.", text)
        self.assertIsNone(PERCENT.search(text), text)
        # A queued job's stage is the job's own state, in words.
        self.assertIn("Waiting to start", text)

    # -- item 2: the price survives and renders -------------------------------------------------
    def test_a_queued_job_price_survives_start_learner_plan(self) -> None:
        outcome = self.out["outcome"]
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual(
            outcome["priceEstimate"],
            {
                "minimum_cost_usd": 0.12,
                "maximum_cost_usd": 0.48,
                "minimum_calls": 3,
                "maximum_calls": 12,
            },
        )
        self.assertEqual(
            [call["method"] for call in self.out["calls"]],
            ["course.create", "enrollment.create", "jobs.create"],
        )

    def test_the_price_estimate_is_rendered_from_backend_numbers(self) -> None:
        # E2E U8: the learner reads a price, not the pipeline's count of model calls.
        text = visible_text(self.out["priceEstimateLine"])
        self.assertIn("Estimated price:", text)
        self.assertIn("$0.12–$0.48", text)
        self.assertNotIn("Preflight", text)
        self.assertNotIn("call", text.lower())
        # Absent means absent: no invented dollar figure.
        self.assertEqual(visible_text(self.out["priceEstimateAbsent"]), "")

    # -- item 3 (before Create): the review step prices it only once it is sized ---------------
    def test_the_review_step_names_the_sections_and_says_when_a_price_appears(self) -> None:
        source = SOURCE_50.read_text(encoding="utf-8")
        block = source[source.index("'data-cb-create-price-waiting'"):]
        block = block[: block.index("planTimingCopy(scope)")]
        self.assertIn("scopeSectionBand(scope)", block)
        # E2E U8: the sizing rule survives in the learner's own words…
        self.assertIn("once we know how big the course is", block)
        # …and no pipeline noun reaches the learner.
        for banned in ("band", "preflight", "backend", "routing"):
            self.assertNotRegex(block, rf"\b{banned}\b")
        # No invented dollar figure in the sentence the learner reads (template interpolation of
        # the section band only, never a `$` price).
        self.assertNotRegex(block, r"\$\d")
        self.assertIsNone(re.search(r"\d+\s*(min|minute|hour)", block, re.I))


class LearnerPlanAdjust(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        built = _node_root("coursebook-w23-learn-", INTERACTION_HARNESS)
        if built is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp, root = built
        cls.out = _run(root, {})

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_approve_is_the_only_primary_on_the_learner_plan(self) -> None:
        before = self.out["before"]
        self.assertTrue(before["adjust"], "the learner surface must expose Adjust this plan")
        self.assertEqual(before["primaryCount"], 1, before["primaryLabels"])
        self.assertIn("Approve plan", before["primaryLabels"])

    def test_a_learner_edit_sends_the_ordered_id_list_and_is_versioned(self) -> None:
        calls = [call for call in self.out["after"]["calls"] if call["method"] == "parent.plan.edit"]
        self.assertEqual(len(calls), 1, self.out["after"]["calls"])
        payload = calls[0]["payload"]
        self.assertEqual(payload["order"], ["obj_b", "obj_a"])
        self.assertEqual(payload["plan_id"], "pln_0123456789abcdef")
        self.assertIn("expected_plan_hash", payload)
        # fenced on the revision the screen was on
        self.assertEqual(calls[0]["expected_revision"], 1)
        # The saved plan is explicitly versioned and the screen names the version.
        self.assertIn("Plan saved as version 2", self.out["after"]["notice"])

    def test_approve_survives_the_edit_and_is_still_the_only_primary(self) -> None:
        after = self.out["after"]
        self.assertTrue(after["adjust"], "Adjust this plan returns after saving")
        self.assertEqual(after["primaryCount"], 1, after["primaryLabels"])
        self.assertIn("Approve plan", after["primaryLabels"])

    def test_the_approved_learner_plan_offers_ask_for_a_change_instead_of_editing(self) -> None:
        approved = self.out["approved"]
        self.assertTrue(approved["askForChange"], "an approved learner plan must offer Ask for a change")
        self.assertFalse(approved["adjust"], "an approved plan is changed by a new version, not edited in place")

    def test_the_elapsed_clock_ticks_while_the_job_runs(self) -> None:
        tick = self.out["tick"]
        self.assertIsNotNone(tick["start"])
        self.assertGreaterEqual(tick["after"], tick["start"] + 1, tick)
        self.assertRegex(tick["text"], r"\d+s elapsed")


class LearnerEditIsVersionedBackend(KernelCase):
    """The learner's Adjust-this-plan order is a real, versioned backend mutation.

    The Desktop cannot prove this alone (its test stubs the transport), so the exact ordered-id
    payload a learner edit sends is replayed here against a migrated SQLite database: the order is
    persisted, the plan version advances, and the course revision is fenced.
    """

    def test_an_ordered_learner_edit_persists_the_order_and_bumps_the_version(self) -> None:
        course_id, plan_id = self.new_course(recipe="casual")
        first = self.seed_objective(plan_id)
        second = self.seed_objective(plan_id)
        enrollment_id = self.new_enrollment(course_id, label="Learner")
        with db.read() as connection:
            version_before = int(
                connection.execute("SELECT version FROM plans WHERE id = ?", (plan_id,)).fetchone()["version"]
            )

        result = self.ok(
            "parent.plan.edit",
            {
                "enrollment_id": enrollment_id,
                "plan_id": plan_id,
                "expected_plan_hash": domain.plan_hash(plan_id),
                "order": [second, first],
            },
            expected_revision=0,
            idempotency_key="cb-learner-adjust-order-1",
        )["result"]

        self.assertEqual(result["objective_ids"], [second, first])
        self.assertEqual(result["plan_version"], version_before + 1)
        self.assertEqual(result["revision"], 1)
        outline = self.ok("course.outline", {"enrollment_id": enrollment_id})["result"]
        self.assertEqual(
            [row["objective_id"] for row in outline["objectives"]],
            [second, first],
        )


if __name__ == "__main__":
    unittest.main()
