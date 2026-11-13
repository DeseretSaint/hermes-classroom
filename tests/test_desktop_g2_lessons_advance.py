"""E2E G2: the lessons job advances one unit, and a failed job can be retried.

The backend half is already proven over the real RPC path and SQLite
(`tests/test_learner_plan_flow.py::LearnerBlueprintLessonPathTest`): one lessons job authors the
next incomplete unit and the settled checkpoint carries `next_unit_ordinal`, `units_complete` and
`units_complete_all`. This file proves the **desktop half** against the shipped module: the plan
screen keys `jobs.create` by plan + the unit it is asking for, offers the next unit from the job's
own checkpoint, and offers Run again for a failed lessons job with a key that is fresh per failed
run.

The press sequence here is exactly what a person does — no internal function is called directly;
the component is mounted in jsdom and its buttons are clicked. The RPC stub replays a key the way
`jobs.create` does (same key, same job id) and scripts the checkpoint the pump would write.

What this does NOT prove: a live backend or a provider. Proven separately by the kernel suite named
above and by the live probe recorded in `docs/ADVERSARIAL-E2E-2026-11-12.md`.
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

STUB = SDK_STUB
for _old, _new in (
    ("export const Input = () => null", "export const Input = (props) => el('input', props)"),
    ("export const Textarea = () => null", "export const Textarea = (props) => el('textarea', props)"),
    ("export const Select = () => null", "export const Select = () => null"),
    ("export const SelectTrigger = () => null", "export const SelectTrigger = (props) => el('div', props)"),
    ("export const SelectValue = () => null", "export const SelectValue = () => null"),
    ("export const SelectContent = () => null", "export const SelectContent = (props) => el('div', props)"),
    ("export const SelectItem = () => null", "export const SelectItem = (props) => el('div', props)"),
    ("export const Checkbox = () => null", "export const Checkbox = (props) => el('input', { type: 'checkbox', ...props })"),
):
    STUB = STUB.replace(_old, _new)

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const caseData = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

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
globalThis.MouseEvent = dom.window.MouseEvent
globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')

const PLAN_ID = 'pln_0123456789abcdef'
const ENROLLMENT_ID = 'enr_0123456789abcdef'
const COURSE_ID = 'crs_0123456789abcdef'

// The fake kernel: jobs.create replays a key exactly as `coursebook/domain.py:jobs_create` does,
// and `mode` scripts the checkpoint the real pump would write for the job it mints.
let world = null
const freshWorld = () => ({
  jobSeq: 0,
  keyToJob: {},
  jobs: {},
  calls: [],
  mode: 'two-units'
})

const checkpointFor = (key, mode) => {
  if (mode === 'failed' || (mode === 'fail-first' && key.indexOf('-retry-') === -1)) {
    return {
      unit_ordinal: 1,
      next_unit_ordinal: null,
      units_total: 2,
      units_complete: [],
      units_complete_all: false,
      sections_total: 3,
      lessons: 1
    }
  }
  const unit = Number((key.match(/-(\d+)(?:-retry-|$)/) || [])[1] || 1)
  if (mode === 'two-units' && unit <= 1) {
    return {
      unit_ordinal: 1,
      next_unit_ordinal: 2,
      next_unit_to_author: 2,
      units_total: 2,
      units_complete: [1],
      units_complete_all: false,
      sections_total: 3,
      lessons: 3
    }
  }
  return {
    unit_ordinal: unit,
    next_unit_ordinal: null,
    next_unit_to_author: null,
    units_total: 2,
    units_complete: [1, 2],
    units_complete_all: true,
    sections_total: 3,
    lessons: 6
  }
}

const createJob = (brief, key) => {
  const world = currentWorld()
  const id = `job_lesson_${++world.jobSeq}`
  const mode = world.mode
  const pending = mode === 'pending'
  const failed = mode === 'failed' || (mode === 'fail-first' && key.indexOf('-retry-') === -1)
  const record = {
    job_id: id,
    kind: 'plan',
    state: pending ? 'queued' : failed ? 'failed' : 'completed',
    brief,
    checkpoint: pending ? {} : checkpointFor(key, mode),
    progress: { message: failed ? 'the provider timed out' : 'lessons authored' },
    error: failed ? { code: 'HOST_UNAVAILABLE', message: 'provider deadline hit' } : null,
    created_at: 1,
    updated_at: 2
  }
  world.jobs[id] = record
  if (key) world.keyToJob[key] = id
  return record
}

let ACTIVE = null
const currentWorld = () => ACTIVE

const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const body = (options && options.body) || {}
  if (base === '/rpc') {
    const method = body.method
    const payload = body.payload || {}
    const key = body.idempotency_key || null
    const world = currentWorld()
    if (method === 'jobs.create') {
      world.calls.push({ method, key, payload })
      if (key && world.keyToJob[key]) {
        return { ok: true, contract_version: 30, operation_id: 'test', result: { job_id: world.keyToJob[key], state: world.jobs[world.keyToJob[key]].state } }
      }
      const record = createJob(payload.brief, key)
      return { ok: true, contract_version: 30, operation_id: 'test', result: { job_id: record.job_id, state: record.state } }
    }
    if (method === 'jobs.get') {
      const record = world.jobs[payload.job_id] || { job_id: payload.job_id, state: 'unknown' }
      return { ok: true, contract_version: 30, operation_id: 'test', result: { job: record } }
    }
    if (method === 'course.outline') {
      return { ok: true, contract_version: 30, operation_id: 'test', result: world.outline || {} }
    }
    if (method === 'parent.blueprint.read') {
      return { ok: true, contract_version: 30, operation_id: 'test', result: world.book || {} }
    }
    if (method === 'jobs.list') {
      const rows = world.presetJobs || Object.values(world.jobs)
      return { ok: true, contract_version: 30, operation_id: 'test', result: { jobs: rows } }
    }
    return { ok: true, contract_version: 30, operation_id: 'test', result: {} }
  }
  if (base === '/runtime') {
    return {
      ok: true,
      contract_version: 30,
      result: {
        wire_version: 30,
        contract_version: 30,
        implemented_methods: ['jobs.create', 'jobs.get', 'jobs.cancel', 'jobs.list', 'plan.approve', 'plan.replan', 'parent.blueprint.read', 'course.outline'],
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
const buttons = () => [...container.querySelectorAll('button')]
const byText = (label) => buttons().find((node) => text(node) === label) || null
const press = async (node) => {
  if (!node) throw new Error('press target missing')
  await act(async () => { node.click() })
  await flush(40)
}
const lessonAction = () =>
  container.querySelector('[data-cb-lessons-unit]') ||
  buttons().find((node) => /Generate (missing )?lessons|Write unit \d+ lessons/.test(text(node))) ||
  null
const jobLine = () => container.querySelector('[data-cb-job-id]')

const objectives = [
  { objective_id: 'obj_a', ordinal: 1, title: 'Alpha', evidence_target: 'recall', state: 'not_started', check_state: 'none' },
  { objective_id: 'obj_b', ordinal: 2, title: 'Beta', evidence_target: 'comprehension', state: 'not_started', check_state: 'none' }
]
const validation = { approvable: false, verdict: 'pass', manual_authoring: false, reason: null }

const book = (pages) => ({
  status: 'ready',
  error: null,
  reload: () => {},
  data: {
    plan: {
      plan_id: PLAN_ID,
      state: 'approved',
      version: 2,
      plan_hash: 'sha256:plan',
      validation,
      units: [{ ordinal: 1, title: 'Unit one' }, { ordinal: 2, title: 'Unit two' }]
    },
    objectives,
    sections: [],
    tabs: { learner_pages: pages }
  }
})

const mount = async (mode, pages) => {
  // Unmount first: React would otherwise reuse the previous scenario's hook state (the settled
  // checkpoint), and the press would ask for a unit the fresh course does not have.
  await act(async () => { root.render(null) })
  await flush(20)
  ACTIVE = freshWorld()
  ACTIVE.mode = mode
  await act(async () => {
    root.render(
      React.createElement(mod.StudioPlanView, {
        course: { course_id: COURSE_ID, enrollment_id: ENROLLMENT_ID, title: 'Order at a counter' },
        revision: 2,
        onRevision: () => {},
        outline: {
          status: 'ready',
          error: null,
          reload: () => {},
          data: { plan: book(pages).data.plan, objectives }
        },
        book: book(pages),
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
  await flush(90)
  return ACTIVE
}

const out = {}

// ── A: two units, one press each, two job ids ────────────────────────────────────────────────
const worldA = await mount('two-units', [])
out.a = { firstLabel: text(lessonAction()), firstUnit: lessonAction() && lessonAction().getAttribute('data-cb-lessons-unit') }
await press(lessonAction())
await flush(120)
out.a.afterFirst = {
  label: text(lessonAction()),
  unit: lessonAction() && lessonAction().getAttribute('data-cb-lessons-unit'),
  jobId: jobLine() && jobLine().getAttribute('data-cb-job-id'),
  state: jobLine() && jobLine().getAttribute('data-cb-job-state')
}
await press(lessonAction())
await flush(120)
out.a.afterSecond = {
  label: text(lessonAction()),
  unit: lessonAction() && lessonAction().getAttribute('data-cb-lessons-unit'),
  jobId: jobLine() && jobLine().getAttribute('data-cb-job-id'),
  state: jobLine() && jobLine().getAttribute('data-cb-job-state')
}
out.a.calls = worldA.calls.map((call) => ({ key: call.key, stage: call.payload && call.payload.brief && call.payload.brief.stage, unit: (call.payload && call.payload.brief && call.payload.brief.unit_ordinal) ?? null }))
out.a.jobsCreated = Object.keys(worldA.jobs)

// ── B: a double click on one press sends one job ─────────────────────────────────────────────
const worldB = await mount('pending', [])
worldB.mode = 'pending'
const target = lessonAction()
if (target) {
  await act(async () => { target.click(); target.click() })
  await flush(60)
}
out.b = {
  keys: worldB.calls.map((call) => call.key),
  jobId: jobLine() && jobLine().getAttribute('data-cb-job-id'),
  jobsCreated: Object.keys(worldB.jobs),
  label: text(lessonAction())
}

// ── C: a failed lessons job offers Run again, and the retry is a new job id ──────────────────
const worldC = await mount('failed', [])
await press(lessonAction())
await flush(150)
const runAgain = byText('Run this stage again')
out.c = {
  failedJobId: jobLine() && jobLine().getAttribute('data-cb-job-id'),
  failedState: jobLine() && jobLine().getAttribute('data-cb-job-state'),
  offersRunAgain: Boolean(runAgain),
  unit: lessonAction() && lessonAction().getAttribute('data-cb-lessons-unit')
}
if (runAgain) {
  await press(runAgain)
  await flush(150)
}
out.c.afterRetry = {
  jobId: jobLine() && jobLine().getAttribute('data-cb-job-id'),
  state: jobLine() && jobLine().getAttribute('data-cb-job-state'),
  keys: worldC.calls.map((call) => call.key),
  jobsCreated: Object.keys(worldC.jobs)
}

// ── D: the learner header offers the next unit instead of "Start the first lesson" ──────────
const presetJob = (checkpoint) => ({
  job_id: 'job_preset_lesson',
  kind: 'plan',
  state: 'completed',
  brief: { stage: 'lessons', plan_id: PLAN_ID, enrollment_id: ENROLLMENT_ID },
  checkpoint,
  progress: {},
  error: null,
  created_at: 1,
  updated_at: 9
})

const mountLearner = async (presetJobs) => {
  await act(async () => { root.render(null) })
  await flush(20)
  const world = freshWorld()
  world.mode = 'two-units'
  const fixture = book([{ page_id: 'page_1' }])
  world.outline = { plan: fixture.data.plan, objectives, total: 2, truncated: false }
  world.book = fixture.data
  world.presetJobs = presetJobs
  ACTIVE = world
  await act(async () => {
    root.render(
      React.createElement(mod.LearnerPlanView, {
        course: { course_id: COURSE_ID, enrollment_id: ENROLLMENT_ID, title: 'Order at a counter' },
        revision: 2,
        onRevision: () => {},
        implemented: null,
        onOpenSection: () => {},
        onStartLesson: () => {},
        onChanged: () => {},
        jobHint: null,
        scopeHint: 'short',
        reloadSignal: 0,
        onChangeGoal: () => {},
        onNewSyllabus: () => {}
      })
    )
  })
  await flush(140)
  return {
    start: Boolean(byText('Start the first lesson')),
    writeUnit2: Boolean(byText('Write unit 2 lessons')),
    unitAction: lessonAction() && lessonAction().getAttribute('data-cb-lessons-unit')
  }
}

out.d = await mountLearner([
  presetJob({ unit_ordinal: 1, next_unit_ordinal: 2, units_total: 2, units_complete: [1], units_complete_all: false, lessons: 3 })
])
out.e = await mountLearner([
  presetJob({ unit_ordinal: 2, next_unit_ordinal: null, units_total: 2, units_complete: [1, 2], units_complete_all: true, lessons: 3 })
])

process.stdout.write(JSON.stringify(out))
"""


def _node_root(harness: str):
    modules = _desktop_node_modules()
    if modules is None:
        return None
    tmp = tempfile.TemporaryDirectory(prefix="coursebook-g2-lessons-")
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


def _run(root: Path) -> dict:
    case_file = root / "case.json"
    case_file.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        ["node", str(root / "harness.mjs"), str(case_file)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr[-4000:])
    return json.loads(result.stdout)


class LessonsAdvanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to run the desktop module")
        built = _node_root(HARNESS)
        if built is None:
            raise unittest.SkipTest("react/jsdom are not installed beside the desktop app")
        cls.tmp, root = built
        cls.out = _run(root)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # ── A ────────────────────────────────────────────────────────────────────────────────────
    def test_the_first_press_asks_for_unit_one(self) -> None:
        first = self.out["a"]
        self.assertEqual(first["firstLabel"], "Generate lessons")
        self.assertEqual(first["firstUnit"], "1")
        keys = [call["key"] for call in first["calls"]]
        self.assertEqual(keys[0], "cb-lessons-pln_0123456789abcdef-1")
        self.assertEqual(first["calls"][0]["stage"], "lessons")
        # The brief still names no unit: the executor resolves it from the stored plan.
        self.assertIsNone(first["calls"][0]["unit"])
        self.assertEqual(first["afterFirst"]["jobId"], "job_lesson_1")
        self.assertEqual(first["afterFirst"]["state"], "completed")

    def test_the_settled_job_offers_the_next_unit_from_its_checkpoint(self) -> None:
        after = self.out["a"]["afterFirst"]
        self.assertEqual(after["label"], "Write unit 2 lessons")
        self.assertEqual(after["unit"], "2")

    def test_the_second_press_creates_a_different_job_id(self) -> None:
        state = self.out["a"]
        self.assertEqual(state["afterSecond"]["jobId"], "job_lesson_2")
        self.assertNotEqual(state["afterSecond"]["jobId"], state["afterFirst"]["jobId"])
        self.assertEqual(state["afterSecond"]["state"], "completed")
        self.assertEqual([call["key"] for call in state["calls"]], [
            "cb-lessons-pln_0123456789abcdef-1",
            "cb-lessons-pln_0123456789abcdef-2",
        ])
        self.assertEqual(state["jobsCreated"], ["job_lesson_1", "job_lesson_2"])
        # Nothing left to author: the action names no next unit, so no third unit is invented.
        self.assertNotRegex(state["afterSecond"]["label"], r"Write unit \d+ lessons")

    # ── B ────────────────────────────────────────────────────────────────────────────────────
    def test_a_double_click_on_one_press_sends_one_job(self) -> None:
        state = self.out["b"]
        # Both clicks carry the same (plan, unit) key: the backend replays one job for them, so a
        # person who double-clicks gets one job id and one spend, never two.
        self.assertEqual(sorted(set(state["keys"])), ["cb-lessons-pln_0123456789abcdef-1"], state["keys"])
        self.assertEqual(state["jobsCreated"], ["job_lesson_1"])
        self.assertEqual(state["jobId"], "job_lesson_1")

    # ── C ────────────────────────────────────────────────────────────────────────────────────
    def test_a_failed_lessons_job_offers_run_again_for_the_same_unit(self) -> None:
        state = self.out["c"]
        self.assertEqual(state["failedState"], "failed")
        self.assertTrue(state["offersRunAgain"], "a failed lessons job must offer Run again")
        self.assertEqual(state["unit"], "1", "a failed unit is retried, not skipped")

    def test_the_retry_is_a_new_job_id_with_a_fresh_key(self) -> None:
        state = self.out["c"]
        self.assertNotEqual(state["afterRetry"]["jobId"], state["failedJobId"])
        self.assertEqual(state["afterRetry"]["jobId"], "job_lesson_2")
        self.assertEqual(
            state["afterRetry"]["keys"],
            [
                "cb-lessons-pln_0123456789abcdef-1",
                "cb-lessons-pln_0123456789abcdef-1-retry-job_lesson_1",
            ],
        )
        self.assertEqual(state["afterRetry"]["jobsCreated"], ["job_lesson_1", "job_lesson_2"])

    # ── D/E: the way into the course follows the written units ───────────────────────────────
    def test_a_half_written_course_offers_the_next_unit_not_the_first_lesson(self) -> None:
        state = self.out["d"]
        self.assertFalse(state["start"], "unit 2 is unwritten: starting the course would hide that")
        self.assertTrue(state["writeUnit2"])
        self.assertEqual(state["unitAction"], "2")

    def test_a_fully_written_course_offers_the_first_lesson(self) -> None:
        state = self.out["e"]
        self.assertTrue(state["start"])
        self.assertFalse(state["writeUnit2"])


class LessonsKeySourceTest(unittest.TestCase):
    """The shipped source keeps the two facts a later edit could silently undo."""

    def test_the_lessons_key_names_the_unit(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertIn("idempotencyKey: `cb-lessons-${plan.plan_id}-${lessonRequestOrdinal}`", source)
        self.assertNotIn("idempotencyKey: `cb-lessons-${plan.plan_id}`", source)

    def test_the_lessons_job_line_can_run_again(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        plan_view = source[source.index("function StudioPlanView"):source.index("function StudioBlueprintView")]
        self.assertIn("retryKey: (failedJobId, run) =>", plan_view)
        self.assertIn("onRunAgain: (newJobId) =>", plan_view)


if __name__ == "__main__":
    unittest.main()
