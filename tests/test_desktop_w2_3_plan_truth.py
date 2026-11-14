"""W2-3: the plan screen tells the truth, and the plan can be adjusted.

CREATE-EXPERIENCE items 3, 4 and 5, driven through the shipped module:

* a waiting plan render a ticking elapsed clock, the job's own `progress.stage` wording and the
  scope's honest band — and a job with no progress shows the band, never a percentage;
* a queued plan job returns only `{job_id, state}` (the contract sizes a price on the lessons
  stage, not this one), so `startLearnerPlan` carries no price and the result screen renders none —
  the flow never promises a figure it cannot show;
* the create review step states how many sections are written before Create and says plainly that
  nothing is priced yet (no invented dollar figure, no promise of a price the flow never shows);
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
SOURCE_95 = ROOT / "desktop" / "src" / "95-studio.js"

#: The stored course a resume reads back: the same composed goal, recipe, dials, locale, level,
#: subject domain and scope the create flow sent to `course.create`.
RESUME_COURSE = {
    "course_id": "crs_0123456789abcdef",
    "title": "Order at a counter",
    "goal": "Order coffee and ask for the bill in Kyoto, politely.",
    "recipe": "casual",
    "dials": {"pace": "steady", "depth": "working", "assessment": "graded", "autonomy": "guided"},
    "locale": "ja-JP",
    "level": "L0",
    "subject_domain": "language",
    "scope": "short",
}
PLACEHOLDER_PLAN = {"plan_id": "pln_0123456789abcdef", "version": 1, "state": "draft", "plan_hash": None}

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
import { StudioPlanView, startLearnerPlan } from './plugin.js'

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
    // The real handler's answer for a plan-stage brief, cb.rpc v27: a queued job and nothing
    // else. The contract sizes a price on the lessons stage, so there is no figure to carry.
    return { ok: true, result: { job_id: 'job_plan_1', state: 'queued' } }
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
const render = async (book, extra = {}) => {
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
        onChangeGoal: (seed) => { goalSeeds.push(seed) },
        onJobSettled: () => {},
        onChanged: () => {},
        supported: () => true,
        surface: 'learner',
        outlineHidden: false,
        syllabusGate: null,
        review: null,
        onOpenReview: () => {},
        onDirtyChange: () => {},
        ...extra
      })
    )
  })
  await flush()
}

const out = { before: {}, calls, after: {}, approved: {} }
const goalSeeds = []
await render(draftBook)
out.before.adjust = Boolean(byText('Adjust this plan'))
out.before.changeGoal = Boolean(container.querySelector('[data-cb-plan-change-goal]'))
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

// The plan job that wrote the approved plan: the brief is the record of every choice that ran, so
// it is where "Change the goal" reads the goal, the outcome and the rest of the create decisions.
const approvedJob = {
  job_id: 'job_0123456789abcdef',
  kind: 'plan',
  state: 'completed',
  brief: {
    stage: 'plan',
    course_id: 'crs_0123456789abcdef',
    enrollment_id: 'enr_0123456789abcdef',
    goal: 'Learn Spanish\n\nWhen this course is done I want to be able to: hold a conversation',
    title: 'Order at a counter',
    recipe: 'casual',
    dials: { depth: 'balanced' },
    locale: 'es',
    level: 'none',
    subject_domain: 'language',
    scope: 'short'
  },
  checkpoint: { validation_verdict: 'pass' },
  created_at: 1794466000,
  updated_at: 1794466010
}
await render(approvedBook, { planJob: approvedJob })
out.approved.askForChange = Boolean(byText('Ask for a change'))
out.approved.adjust = Boolean(byText('Adjust this plan'))
out.approved.changeGoal = Boolean(container.querySelector('[data-cb-plan-change-goal]'))
out.approved.changeGoalNote = text(container).includes(
  'This starts a new course; this one and its evidence stay.'
)
// Clicking it hands the brief back to the create form: no plan.replan, no course mutation.
const callsBeforeGoal = calls.length
await click(container.querySelector('[data-cb-plan-change-goal]'))
out.approved.goalCalls = calls.length - callsBeforeGoal
out.approved.goalSeeds = goalSeeds
out.approved.replanCalls = calls.filter((call) => call.method === 'plan.replan').length

// UP-5: the plan header restates the goal. The learner route finds the plan job by enrolment and
// hands this panel its brief; that brief is the exact goal the planner ran, composed with the
// learner's proof sentence. The header must show both, without folding one into the other and
// without dropping the version line it already carried.
const GOAL_TEXT = 'Order at a counter without switching to English, and ask for the bill politely.'
const PROOF_TEXT = 'Hold a two-minute order with the shopkeeper.'
const headerJob = {
  job_id: 'job_0123456789abcdef',
  kind: 'plan',
  state: 'completed',
  brief: {
    stage: 'plan',
    goal: `${GOAL_TEXT}\n\nWhen this course is done I want to be able to: ${PROOF_TEXT}`
  }
}
await render(draftBook, { planJob: headerJob })
const goalNode = container.querySelector('[data-cb-plan-goal]')
const proofNode = container.querySelector('[data-cb-plan-proof]')
out.header = {
  goal: goalNode ? goalNode.textContent.trim() : null,
  proof: proofNode ? text(proofNode) : null,
  clamp: goalNode ? goalNode.style.webkitLineClamp || null : null,
  text: text(container)
}

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


RESUME_HARNESS = r"""
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
const CASE = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const mod = await import('./plugin.js')
const calls = []
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/runtime') {
    return {
      ok: true,
      contract_version: 28,
      result: {
        wire_version: 28,
        implemented_methods: ['course.outline', 'course.get', 'jobs.list', 'jobs.create', 'jobs.get', 'parent.blueprint.read'],
        single_home_host: false
      }
    }
  }
  if (base === '/rpc') {
    const body = options.body
    calls.push({ method: body.method, payload: body.payload, idempotency_key: body.idempotency_key })
    const answered = (result) => ({ ok: true, contract_version: 28, operation_id: 'test', result })
    if (body.method === 'jobs.list') return answered({ jobs: CASE.jobs || [] })
    if (body.method === 'course.get') return answered({ course: CASE.course })
    if (body.method === 'jobs.create') return answered({ job_id: 'job_resume_1', state: 'queued' })
    if (body.method === 'jobs.get') {
      return answered({ job: { job_id: 'job_resume_1', kind: 'plan', state: 'queued', progress: {} } })
    }
    return answered({})
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
const flush = async (ms = 120) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (label) => [...container.querySelectorAll('button')].find((node) => text(node) === label) || null

const outline = {
  status: 'ready',
  error: null,
  reload: () => {},
  data: { plan: CASE.plan, objectives: [] }
}

await act(async () => {
  root.render(
    React.createElement(mod.StudioPlanView, {
      course: { course_id: CASE.course.course_id, enrollment_id: 'enr_0123456789abcdef', title: 'Order at a counter' },
      revision: 1,
      onRevision: () => {},
      outline,
      book: null,
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

const out = {}
out.resumeControl = container.querySelector('[data-cb-plan-resume]')
  ? container.querySelector('[data-cb-plan-resume]').getAttribute('data-cb-plan-resume')
  : null
out.resumeButton = Boolean(byText("Write this course's plan"))
out.beforeText = text(container)
out.callsBefore = calls.length

const press = byText("Write this course's plan")
if (press) {
  await act(async () => { press.click() })
  await flush(200)
}
out.calls = calls.map((call) => ({
  method: call.method,
  payload: call.payload,
  idempotency_key: call.idempotency_key
}))
out.afterText = text(container)
out.waitPanel = container.querySelector('[data-cb-plan-wait]')
  ? container.querySelector('[data-cb-plan-wait]').getAttribute('data-cb-plan-wait')
  : null
out.resumeAfter = Boolean(container.querySelector('[data-cb-plan-resume]'))

await act(async () => { root.render(null) })
await flush(20)
process.stdout.write(JSON.stringify(out))
"""


LEARNER_JOBS_ERROR_HARNESS = r"""
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
const counts = {}
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  if (base === '/rpc') {
    const method = options && options.body && options.body.method
    counts[method] = (counts[method] || 0) + 1
    if (method === 'course.outline') {
      return { ok: true, contract_version: 30, operation_id: 'test', result: { plan: null, objectives: [] } }
    }
    if (method === 'jobs.list') {
      // The read itself fails. The surface must not read that as "this course has no plan":
      // the plan job may be running and unreachable through a failing read.
      return {
        ok: false,
        contract_version: 30,
        operation_id: 'test',
        error: { code: 'HOST_UNAVAILABLE', message: 'jobs.list did not answer' }
      }
    }
    return { ok: true, contract_version: 30, operation_id: 'test', result: {} }
  }
  if (base === '/runtime') {
    return {
      ok: true,
      contract_version: 30,
      operation_id: 'test',
      result: {
        wire_version: 30,
        implemented_methods: [
          'jobs.list',
          'course.outline',
          'parent.blueprint.read',
          'plan.approve',
          'jobs.create'
        ],
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
const flush = async (ms = 120) => { await act(async () => { await new Promise((r) => setTimeout(r, ms)) }) }
const text = (node) => ((node && node.textContent) || '').replace(/\s+/g, ' ').trim()
const byText = (label) =>
  [...container.querySelectorAll('button')].find((node) => text(node) === label) || null

await act(async () => {
  root.render(
    React.createElement(mod.LearnerPlanView, {
      course: { course_id: 'crs_0123456789abcdef', enrollment_id: 'enr_0123456789abcdef', title: 'Order at a counter' },
      revision: 1,
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
await flush(180)
const before = { text: text(container), retry: Boolean(byText('Try again')), counts: { ...counts } }
const retry = byText('Try again')
if (retry) {
  await act(async () => { retry.click() })
  await flush(180)
}
const after = { text: text(container), retry: Boolean(byText('Try again')), counts: { ...counts } }

// The same surface when the backend does not implement jobs.list at all: it cannot know whether a
// plan is being written, so it must not claim the course has none.
await act(async () => { root.render(null) })
await flush(30)
await act(async () => {
  root.render(
    React.createElement(mod.LearnerPlanView, {
      course: { course_id: 'crs_0123456789abcdef', enrollment_id: 'enr_0123456789abcdef', title: 'Order at a counter' },
      revision: 1,
      onRevision: () => {},
      implemented: new Set(['course.outline', 'parent.blueprint.read', 'plan.approve', 'jobs.create']),
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
await flush(180)
const unsupported = { text: text(container), retry: Boolean(byText('Try again')) }
await act(async () => { root.render(null) })
await flush(20)
process.stdout.write(JSON.stringify({ before, after, unsupported }))
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
        error_built = _node_root("coursebook-w23-jobs-error-", LEARNER_JOBS_ERROR_HARNESS)
        if error_built is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp_error, error_root = error_built
        cls.error_out = _run(error_root, {})

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()
        if hasattr(cls, "tmp_error"):
            cls.tmp_error.cleanup()

    # -- Upgrade 2: a failed jobs.list read is an error, not an empty course ---------------------
    def test_a_jobs_list_error_is_never_presented_as_no_plan(self) -> None:
        before = self.error_out["before"]
        self.assertIn("The plan's progress could not be read", before["text"], before["text"])
        self.assertTrue(before["retry"], "a failed jobs.list read must offer Try again")
        self.assertNotIn("This course has no plan attached", before["text"])
        self.assertNotIn("No plan yet", before["text"])
        after = self.error_out["after"]
        self.assertTrue(after["retry"], "the error state survives a retry that still fails")
        self.assertGreater(
            after["counts"].get("jobs.list", 0),
            before["counts"].get("jobs.list", 0),
            after,
        )
        self.assertGreater(
            after["counts"].get("course.outline", 0),
            before["counts"].get("course.outline", 0),
            after,
        )
        # The same absence of knowledge when the backend does not implement jobs.list.
        unsupported = self.error_out["unsupported"]
        self.assertIn("The plan's progress could not be read", unsupported["text"], unsupported["text"])
        self.assertTrue(unsupported["retry"], "an unsupported jobs.list must still offer Try again")
        self.assertNotIn("This course has no plan attached", unsupported["text"])

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

    # -- item 2: a plan job has no price, and the flow invents none ------------------------------
    def test_a_plan_job_result_carries_no_price_and_the_flow_invents_none(self) -> None:
        outcome = self.out["outcome"]
        self.assertTrue(outcome["ok"], outcome)
        self.assertNotIn("priceEstimate", outcome)
        self.assertEqual(
            [call["method"] for call in self.out["calls"]],
            ["course.create", "enrollment.create", "jobs.create"],
        )
        # The flow asks for the plan stage, the stage the contract does not price — this is why
        # no figure can exist here, not an accident of the stub.
        job = next(call for call in self.out["calls"] if call["method"] == "jobs.create")
        self.assertEqual(job["payload"]["brief"]["stage"], "plan")

    def test_the_result_screen_renders_no_price_because_none_arrives(self) -> None:
        # E2E U8: the create result shows what happened, never a price the next screen cannot
        # supply. The read of the contract's price field and the component that printed it are gone.
        source = SOURCE_50.read_text(encoding="utf-8")
        for absent in (
            "CreatePriceEstimateLine",
            "priceEstimate",
            "job.result.preflight",
            "Estimated price",
        ):
            self.assertNotIn(absent, source)

    # -- resume: a half-finished create is offered its missing step -----------------------------
    def test_a_placeholder_plan_with_no_job_offers_to_write_it_again(self) -> None:
        """A create that stopped after the course and enrolment is resumable, not abandoned.

        At HEAD the empty screen said "Start a new course to generate one" and offered no control,
        so a learner who closed the app between `course.create` and `jobs.create` had to buy the
        same research twice. Here the screen renders the stored course's own choices back into one
        action, and one press queues exactly one plan job under a course-keyed idempotency key.
        """
        case = {"plan": PLACEHOLDER_PLAN, "jobs": [], "course": RESUME_COURSE}
        built = _node_root("coursebook-w23-resume-", RESUME_HARNESS)
        if built is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        tmp, root = built
        try:
            out = _run(root, case)
        finally:
            tmp.cleanup()

        # The control exists on a placeholder plan with no plan job.
        self.assertEqual(out["resumeControl"], "offered", out["beforeText"])
        self.assertTrue(out["resumeButton"], out["beforeText"])
        self.assertIn("Your goal and the choices you made are saved.", out["beforeText"])
        # The sentence that spent the research twice is gone from the plan screen.
        source = SOURCE_95.read_text(encoding="utf-8")
        self.assertNotIn(
            "This course has no plan attached. Start a new course to generate one", source
        )

        # One press queues exactly one plan job.
        created = [call for call in out["calls"] if call["method"] == "jobs.create"]
        self.assertEqual(len(created), 1, out["calls"])
        job = created[0]
        self.assertEqual(job["payload"]["kind"], "plan")
        brief = job["payload"]["brief"]
        self.assertEqual(brief["stage"], "plan")
        self.assertEqual(brief["course_id"], RESUME_COURSE["course_id"])
        self.assertEqual(brief["enrollment_id"], "enr_0123456789abcdef")
        # The stored scope, not a default: every create-form choice comes back from the course row.
        self.assertEqual(brief["goal"], RESUME_COURSE["goal"])
        self.assertEqual(brief["recipe"], RESUME_COURSE["recipe"])
        self.assertEqual(brief["dials"], RESUME_COURSE["dials"])
        self.assertEqual(brief["locale"], RESUME_COURSE["locale"])
        self.assertEqual(brief["level"], RESUME_COURSE["level"])
        self.assertEqual(brief["subject_domain"], RESUME_COURSE["subject_domain"])
        self.assertEqual(brief["scope"], RESUME_COURSE["scope"])
        # The key is the course's, so a second press or a revisit replays the same job.
        self.assertEqual(job["idempotency_key"], f"cb-plan-resume-{RESUME_COURSE['course_id']}")
        self.assertIn("course.get", [call["method"] for call in out["calls"]])

        # The queued job becomes the wait panel, and the resume door steps away.
        self.assertIsNotNone(out["waitPanel"], out["afterText"])
        self.assertFalse(out["resumeAfter"], out["afterText"])
        self.assertIn("The plan is being written", out["afterText"])

    def test_a_course_that_already_has_a_plan_job_is_never_offered_a_second_one(self) -> None:
        """The resume door is only opened by an empty jobs read, never by an absent job id."""
        stored_job = {
            "job_id": "job_0123456789abcdef",
            "kind": "plan",
            "state": "completed",
            "brief": {"stage": "plan"},
            "updated_at": 1794466010,
        }
        case = {"plan": PLACEHOLDER_PLAN, "jobs": [stored_job], "course": RESUME_COURSE}
        built = _node_root("coursebook-w23-resume-jobs-", RESUME_HARNESS)
        if built is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        tmp, root = built
        try:
            out = _run(root, case)
        finally:
            tmp.cleanup()

        self.assertIsNone(out["resumeControl"], out["beforeText"])
        self.assertFalse(
            [call for call in out["calls"] if call["method"] == "jobs.create"], out["calls"]
        )
        # With a plan job on record the screen keeps its plain empty state instead.
        self.assertIn("No plan yet", out["beforeText"])

    # -- item 3 (before Create): the review step prices it only once it is sized ---------------
    def test_the_review_step_names_the_sections_and_says_when_a_price_appears(self) -> None:
        source = SOURCE_50.read_text(encoding="utf-8")
        block = source[source.index("'data-cb-create-price-waiting'"):]
        block = block[: block.index("planTimingCopy(scope)")]
        self.assertIn("scopeSectionBand(scope)", block)
        # E2E U8: the sizing rule survives in the learner's own words…
        self.assertIn("Nothing is priced yet — we price it once we know how big the course is.", block)
        # …with no promise of a price the flow never shows…
        self.assertNotIn("You see the price", block)
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

    def test_an_approved_plan_can_hand_its_goal_back_to_create(self) -> None:
        # The goal is not an outline edit: "Ask for a change" keeps every objective and supersedes
        # this course's plan, so it can never say the goal itself was wrong. This control hands the
        # brief that ran back to the create form, where a new goal is a new course and this one's
        # committed evidence stays bound to the plan it was recorded against.
        approved = self.out["approved"]
        self.assertTrue(approved["changeGoal"], "an approved learner plan must offer Change the goal")
        self.assertTrue(approved["changeGoalNote"], "the control must say what it does before the press")
        self.assertFalse(self.out["before"]["changeGoal"], "a draft plan is changed in place, not by a new course")

        seeds = approved["goalSeeds"]
        self.assertEqual(len(seeds), 1, seeds)
        seed = seeds[0]
        # The composed goal is split back into the learner's own goal and their outcome.
        self.assertEqual(seed["goal"], "Learn Spanish")
        self.assertEqual(seed["outcome"], "hold a conversation")
        self.assertEqual(seed["title"], "Order at a counter")
        self.assertEqual(seed["recipe"], "casual")
        self.assertEqual(seed["dials"], {"depth": "balanced"})
        self.assertEqual(seed["locale"], "es")
        self.assertEqual(seed["level"], "none")
        self.assertEqual(seed["subjectDomain"], "language")
        self.assertEqual(seed["scope"], "short")
        # Handing the goal back is not a plan version of this course: no replan, no write at all.
        self.assertEqual(approved["goalCalls"], 0, "the control calls no RPC of its own")
        self.assertEqual(approved["replanCalls"], 0, "an approved plan's goal is never replanned in place")
    def test_the_plan_header_restates_the_goal(self) -> None:
        """The gate names the version; it must also name the intent that version serves.

        `Plan draft · v1` plus a truncated hash told a learner which bytes they were approving and
        never what those bytes were for. The plan job's brief is the goal the planner actually ran
        (composed with the learner's own proof sentence), so the header restates both, exactly.
        """
        header = self.out["header"]
        goal = "Order at a counter without switching to English, and ask for the bill politely."
        proof = "Hold a two-minute order with the shopkeeper."
        self.assertEqual(header["goal"], goal, "the exact goal, not a paraphrase")
        self.assertIn(goal, header["text"], "the goal is readable on the approval gate")
        # The proof travels inside the brief; the header names it as the proof, not as the goal.
        self.assertEqual(header["proof"], f"Proof: {proof}")
        # Two lines are the layout's ceiling; the sentence is never cut in the source.
        self.assertEqual(header["clamp"], "2")
        # The header keeps what it already said: the state and the version digest are not replaced
        # by the intent.
        self.assertIn("plan sha256:plan", header["text"])
        self.assertIn("Plan draft · v1", header["text"])

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


class PlanResumeBackend(KernelCase):
    """The resume the plan screen offers is a real, replayable backend command.

    The Desktop test above proves the control and the exact payload it builds. This replays that
    payload against a migrated SQLite database: the course row the resume reads is the one
    `course.create` wrote, the brief it rebuilds is an accepted `plan_brief`, and the course-keyed
    idempotency key replays instead of minting a second plan job.
    """

    def test_a_create_interrupted_before_jobs_create_resumes_from_the_stored_row(self) -> None:
        decision = {
            "title": "Order at a counter",
            "goal": "Order coffee and ask for the bill in Kyoto, politely.",
            "recipe": "casual",
            "dials": {
                "pace": "steady",
                "depth": "working",
                "assessment": "graded",
                "autonomy": "guided",
            },
            "locale": "ja-JP",
            "level": "L0",
            "subject_domain": "language",
            "scope": "short",
            "presentation_mode": "game",
        }
        created = self.ok("course.create", decision, idempotency_key="cb-course-create-key1")["result"]
        course_id, plan_id = created["course_id"], created["plan_id"]
        enrollment_id = self.new_enrollment(course_id, label=decision["title"])

        # The app closed here: the course, its draft plan row and the enrolment are real, and no
        # plan job was ever queued.
        self.assertTrue(plan_id)
        self.assertEqual(
            self.ok("jobs.list", {"enrollment_id": enrollment_id, "kind": ["plan"]})["result"]["jobs"],
            [],
        )
        objectives = self.scalar(
            "SELECT COUNT(*) FROM objectives WHERE plan_id = ?", (plan_id,)
        )
        self.assertEqual(objectives, 0)

        # The resume reads the course row and rebuilds the brief from it — never from memory.
        stored = self.ok("course.get", {"course_id": course_id})["result"]["course"]
        for field in ("goal", "recipe", "dials", "locale", "level", "subject_domain", "scope"):
            self.assertEqual(stored[field], decision[field], field)
        brief = {
            "stage": "plan",
            "course_id": course_id,
            "enrollment_id": enrollment_id,
            "goal": stored["goal"],
            "recipe": stored["recipe"],
            "dials": stored["dials"],
            "locale": stored["locale"],
            "level": stored["level"],
            "subject_domain": stored["subject_domain"],
            "scope": stored["scope"],
        }
        key = f"cb-plan-resume-{course_id}"
        first = self.ok("jobs.create", {"kind": "plan", "brief": brief}, idempotency_key=key)["result"]
        second = self.ok("jobs.create", {"kind": "plan", "brief": brief}, idempotency_key=key)["result"]

        # One press, one job: the same key replays the stored answer.
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(first["state"], "queued")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)
        jobs = self.ok("jobs.list", {"enrollment_id": enrollment_id, "kind": ["plan"]})["result"]["jobs"]
        self.assertEqual([job["job_id"] for job in jobs], [first["job_id"]])
        # The stored brief is the one the screen rebuilt, field for field.
        self.assertEqual(jobs[0]["brief"]["stage"], "plan")
        self.assertEqual(jobs[0]["brief"]["scope"], "short")
        self.assertEqual(jobs[0]["brief"]["level"], "L0")

        # A different payload under the same key is a conflict, never a silent second job.
        changed = dict(brief, scope="full")
        error = self.err("jobs.create", {"kind": "plan", "brief": changed}, idempotency_key=key)
        self.assertEqual(error["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM jobs"), 1)


if __name__ == "__main__":
    unittest.main()
