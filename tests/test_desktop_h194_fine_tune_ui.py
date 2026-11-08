"""H-194 (UI): the Plan/Textbook fine-tune controls.

What this proves, against the shipped module:

* a keyboard move (Alt+ArrowDown on a focused row) sends `plan.edit` with the **full** ordered id
  list read from the current revision, together with the plan digest and the envelope fence, and
  the order on screen becomes the ids the command returned — not the ones the UI computed;
* a `prerequisite_order_conflict` refusal keeps the stored order and says why; the screen never
  keeps an order storage rejected;
* `Undo last structural change` calls `plan.undo` with the stored revision id and refreshes the
  persisted order from the response;
* an inline section edit is a real draft: Cancel and navigation ask first, a window close is
  guarded, and Save sends `plan.edit` `objective_edits` for objective metadata and/or
  `lesson.revise` for the authored page title, fenced on the `page_hash` the blueprint served
  (never a digest computed in the Desktop half), with `confirm_evidence_consequence` only after
  the refusal named the stored attempts;
* `Regenerate this section` prints `1 section: <title>` and the cost before the click, then sends
  `lesson.regenerate` with that section id and surfaces the queued job, its scope and its preflight;
* the provenance chip reads the lesson state the blueprint serves (`needs_review` /
  `parent_approved`) and the revision rows, and never upgrades an edit to an approval;
* the review diff is read from `parent.review.read`, prints the backend's `blocked_reason`
  verbatim, and the export gate stays closed until `parent.final.approve` covers the bytes it was
  served — a stale approval is refused and the export button stays disabled.

The section identity (`section_id` + `page_hash`) comes from `parent.blueprint.read` `sections[]`,
the cb.rpc v20 amendment built for this card. A course whose blueprint serves no section identity
(a pack-backed course) withholds the one-section actions and says so on screen.
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
assert "export const SelectTrigger = (props)" in STUB, "the SDK stub did not gain a real SelectTrigger"

HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/', pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const mod = await import('./plugin.js')
const calls = []
const queues = {}
const responses = payload.responses || {}
const runtime = {
  wire_version: 19,
  implemented_methods: ['plan.edit', 'plan.undo', 'lesson.revise', 'lesson.regenerate', 'parent.review.read', 'jobs.list', 'parent.final.approve', 'parent.export'],
  single_home_host: false
}
const fakeRest = async (path, options) => {
  const base = String(path).split('?')[0]
  const method = options && options.body && options.body.method
  if (base === '/rpc') {
    calls.push({
      method,
      payload: options.body.payload,
      expected_revision: options.body.expected_revision,
      idempotency_key: options.body.idempotency_key
    })
    const queue = queues[method]
    if (queue && queue.length) return queue.shift()
    const result = Object.prototype.hasOwnProperty.call(responses, method) ? responses[method] : {}
    return { ok: true, contract_version: 19, operation_id: 'test', result }
  }
  if (base === '/runtime') return runtime
  if (base === '/health') {
    return { ok: true, contract_version: 19, result: { db: { ready: true }, plugin_version: 'test', contract_version: 19 } }
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
const byText = (rootNode, label) =>
  [...rootNode.querySelectorAll('button')].find((n) => text(n) === label) || null
const row = (id) => document.querySelector(`[data-cb-finetune-row="${id}"]`)
const orderAttr = () => {
  const list = document.querySelector('[data-cb-finetune-order]')
  return list ? list.getAttribute('data-cb-finetune-order') : null
}
const setInput = async (node, value) => {
  const proto = node.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
  await act(async () => {
    setter.call(node, value)
    node.dispatchEvent(new window.Event('input', { bubbles: true }))
  })
  await flush()
}
const key = async (node, keyName) => {
  await act(async () => {
    node.dispatchEvent(new window.KeyboardEvent('keydown', { key: keyName, altKey: true, bubbles: true, cancelable: true }))
  })
  await flush()
}
const unmount = async () => { await act(async () => { root.render(null) }) ; await flush(20) }

const objectives = [
  { objective_id: 'obj_a', ordinal: 1, title: 'Alpha', evidence_target: 'recall', state: 'new', check_state: 'none' },
  { objective_id: 'obj_b', ordinal: 2, title: 'Beta', evidence_target: 'comprehension', state: 'new', check_state: 'none' },
  { objective_id: 'obj_c', ordinal: 3, title: 'Gamma', evidence_target: 'production', state: 'new', check_state: 'none' }
]
const plan = { plan_id: 'pln_1', state: 'approved', version: 2, plan_hash: 'sha256:plan' }
// The v20 `parent.blueprint.read` section identity: one row per composed section, carrying the
// exact `page_hash` fence `lesson.revise` compares and the lesson state the provenance chip reads.
const sectionRows = [
  { section_id: 'sec_a', objective_id: 'obj_a', ordinal: 1, title: 'Alpha', lesson_state: 'validated', lesson_version: 1, page_hash: 'sha256:page-a' },
  { section_id: 'sec_b', objective_id: 'obj_b', ordinal: 2, title: 'Beta', lesson_state: 'needs_review', lesson_version: 2, page_hash: 'sha256:page-b' },
  { section_id: 'sec_c', objective_id: 'obj_c', ordinal: 3, title: 'Gamma', lesson_state: null, lesson_version: null, page_hash: null }
]
const reviewData = {
  course_id: 'crs_1',
  plan: plan,
  approval: { state: 'superseded', plan_hash: 'sha256:old', content_hash: 'sha256:oldc', approved_at: null, invalidated_reason: 'plan_edited' },
  content_hash: 'sha256:content',
  plan_revisions: [
    {
      revision_id: 'prv_1', kind: 'reorder', state: 'needs_review', created_at: '2026-11-08T12:00:00Z',
      plan_hash_before: 'sha256:p1', plan_hash_after: 'sha256:p2',
      before: objectives.map((o) => ({ ...o, criteria: [], version: 1 })),
      after: [objectives[1], objectives[0], objectives[2]].map((o, i) => ({ ...o, ordinal: i + 1, criteria: [], version: 2 })),
      changed_fields: ['order', 'obj_a.ordinal', 'obj_b.ordinal']
    }
  ],
  lesson_revisions: [],
  export: { ready: false, blocked_reason: 'changes_need_review' }
}

const renderPanel = async (overrides = {}) => {
  const review = {
    status: 'ready',
    data: overrides.reviewData || reviewData,
    error: null,
    reload: () => {}
  }
  await act(async () => {
    root.render(
      React.createElement(mod.StudioFineTunePanel, {
        course: { course_id: 'crs_1', enrollment_id: 'enr_1' },
        revision: 3,
        onRevision: () => {},
        plan,
        objectives,
        sections: overrides.sections === undefined ? sectionRows : overrides.sections,
        planHash: 'sha256:plan',
        supported: () => true,
        onChanged: () => {},
        onOpenReview: () => {},
        review,
        onDirtyChange: () => {}
      })
    )
  })
  await flush(120)
}

const facts = {}
// The panel's `jobs.list` read mounts once with the first render, so the recorded lessons preflight
// is seeded here rather than just before the regenerate scenario.
responses['jobs.list'] = {
  jobs: [
    { job_id: 'job_lessons_last', kind: 'plan', state: 'completed', brief: { stage: 'lessons' }, checkpoint: { preflight: { section_count: 2, cost_per_call_usd: 0.02, minimum_calls: 1, maximum_calls: 4, budget_source: 'course' } } }
  ]
}

// 1 — keyboard reorder sends the full list and adopts the returned order.
queues['plan.edit'] = [
  {
    ok: true, contract_version: 19, operation_id: 't',
    result: { plan_id: 'pln_1', plan_version: 3, plan_hash: 'sha256:new', objective_ids: ['obj_b', 'obj_a', 'obj_c'], changes_need_review: true, review: {}, revision: 4 }
  }
]
await renderPanel()
await key(row('obj_a'), 'ArrowDown')
facts.reorder = {
  order: orderAttr(),
  notice: text(document.querySelector('[data-cb-finetune-notice]')),
  call: calls.filter((c) => c.method === 'plan.edit').at(-1) || null
}

// 2 — a refused move keeps the stored order and says why.
queues['plan.edit'] = [
  {
    ok: false, contract_version: 19, operation_id: 't',
    error: { code: 'POLICY_VIOLATION', category: 'policy', message: 'that order crosses a unit prerequisite backwards', retryable: false, details: { reason: 'prerequisite_order_conflict' } }
  }
]
await renderPanel()
await click(byText(row('obj_a'), 'Move down'))
facts.refused = {
  order: orderAttr(),
  error: text(document.querySelector('[data-cb-finetune-error]'))
}

// 3 — undo calls plan.undo with the stored revision and refreshes the order.
queues['plan.undo'] = [
  {
    ok: true, contract_version: 19, operation_id: 't',
    result: { plan_id: 'pln_1', plan_version: 4, plan_hash: 'sha256:undo', objective_ids: ['obj_a', 'obj_b', 'obj_c'], reverted_revision_id: 'prv_1', changes_need_review: true, revision: 5 }
  }
]
await renderPanel()
await click(byText(document, 'Undo last structural change'))
facts.undo = {
  order: orderAttr(),
  notice: text(document.querySelector('[data-cb-finetune-notice]')),
  call: calls.filter((c) => c.method === 'plan.undo').at(-1) || null
}

// 4 — the unsaved-change guard, then a real save.
await renderPanel()
await click(byText(row('obj_a'), 'Edit section'))
const titleInput = document.querySelector('#cb-finetune-title-obj_a')
await setInput(titleInput, 'Alpha revised')
const beforeUnload = new window.Event('beforeunload', { cancelable: true })
window.dispatchEvent(beforeUnload)
const dirtyWhileTyping = Boolean(document.querySelector('[data-cb-finetune-dirty]'))
await click(byText(row('obj_a'), 'Cancel'))
const discardPrompt = (document.querySelector('[data-cb-finetune-discard]') || {}).getAttribute?.('data-cb-finetune-discard')
const editorStillMounted = Boolean(document.querySelector('[data-cb-finetune-editor="obj_a"]'))
await click(byText(document.querySelector('[data-cb-finetune-discard]'), 'Keep editing'))
const keptEditing = Boolean(document.querySelector('[data-cb-finetune-editor="obj_a"]'))
await click(byText(row('obj_a'), 'Cancel'))
await click(byText(document.querySelector('[data-cb-finetune-discard]'), 'Discard changes'))
const closedByDiscard = !document.querySelector('[data-cb-finetune-editor="obj_a"]')
const savesAfterDiscard = calls.filter((c) => c.method === 'plan.edit').length
const noticeAfterDiscard = text(document.querySelector('[data-cb-finetune-notice]'))

queues['plan.edit'] = [
  { ok: true, contract_version: 19, operation_id: 't', result: { plan_id: 'pln_1', plan_version: 5, plan_hash: 'sha256:saved', objective_ids: ['obj_a', 'obj_b', 'obj_c'], changes_need_review: true, review: {}, revision: 6 } }
]
await click(byText(row('obj_a'), 'Edit section'))
await setInput(document.querySelector('#cb-finetune-title-obj_a'), 'Alpha revised')
const callsBeforeSave = calls.filter((c) => c.method === 'plan.edit').length
await click(byText(document.querySelector('[data-cb-finetune-editor="obj_a"]'), 'Save section'))
facts.guard = {
  dirtyWhileTyping,
  beforeUnloadPrevented: beforeUnload.defaultPrevented,
  discardPrompt,
  editorStillMounted,
  keptEditing,
  closedByDiscard,
  savesAfterDiscard,
  noticeAfterDiscard,
  callsBeforeSave,
  saveCall: calls.filter((c) => c.method === 'plan.edit').at(-1) || null,
  notice: text(document.querySelector('[data-cb-finetune-notice]')),
  editorClosedAfterSave: !document.querySelector('[data-cb-finetune-editor="obj_a"]')
}

// 4b — the authored page title is saved through lesson.revise on the digest the blueprint served.
queues['lesson.revise'] = [
  {
    ok: true, contract_version: 20, operation_id: 't',
    result: { section_id: 'sec_a', objective_id: 'obj_a', lesson_id: 'lsn_a2', lesson_version: 2, lesson_state: 'needs_review', page_hash: 'sha256:page-a2', changes_need_review: true, review: {}, revision: 8 }
  }
]
await renderPanel()
await click(byText(row('obj_a'), 'Edit section'))
const pageTitleInput = document.querySelector('#cb-finetune-page-title-obj_a')
const pageTitleDisabled = Boolean(pageTitleInput.disabled)
const pageTitleValue = pageTitleInput.value
await setInput(pageTitleInput, 'Alpha revised page')
await click(byText(document.querySelector('[data-cb-finetune-editor="obj_a"]'), 'Save section'))
facts.pageTitle = {
  disabled: pageTitleDisabled,
  initialValue: pageTitleValue,
  call: calls.filter((c) => c.method === 'lesson.revise').at(-1) || null,
  notice: text(document.querySelector('[data-cb-finetune-notice]')),
  editorClosed: !document.querySelector('[data-cb-finetune-editor="obj_a"]')
}

// 4c — an edit after stored attempts is refused; the consequence is shown and the retry confirms.
queues['lesson.revise'] = [
  {
    ok: false, contract_version: 20, operation_id: 't',
    error: {
      code: 'POLICY_VIOLATION', category: 'policy', retryable: false,
      message: '2 learner attempt(s) already reference this section; confirm the evidence consequence before editing.',
      details: { reason: 'evidence_consequence_confirmation_required', section_id: 'sec_b', evidence_attempts: 2 }
    }
  },
  {
    ok: true, contract_version: 20, operation_id: 't',
    result: { section_id: 'sec_b', objective_id: 'obj_b', lesson_id: 'lsn_b3', lesson_version: 3, lesson_state: 'needs_review', page_hash: 'sha256:page-b3', changes_need_review: true, review: {}, revision: 9 }
  }
]
await renderPanel()
await click(byText(row('obj_b'), 'Edit section'))
await setInput(document.querySelector('#cb-finetune-page-title-obj_b'), 'Beta revised page')
await click(byText(document.querySelector('[data-cb-finetune-editor="obj_b"]'), 'Save section'))
const evidencePrompt = document.querySelector('[data-cb-finetune-evidence]')
facts.evidence = {
  prompt: evidencePrompt ? evidencePrompt.getAttribute('data-cb-finetune-evidence') : null,
  promptText: text(evidencePrompt),
  error: text(document.querySelector('[data-cb-finetune-error]')),
  refusedCall: calls.filter((c) => c.method === 'lesson.revise').at(-1) || null
}
await click(byText(evidencePrompt, 'Confirm and save'))
facts.evidence.retryCall = calls.filter((c) => c.method === 'lesson.revise').at(-1) || null
facts.evidence.notice = text(document.querySelector('[data-cb-finetune-notice]'))
facts.evidence.editorClosed = !document.querySelector('[data-cb-finetune-editor="obj_b"]')
facts.chips = [...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip'))

// 4d — Regenerate this section shows the scope and the cost before queueing, then surfaces the job.
responses['jobs.get'] = { job: { job_id: 'job_regen', kind: 'plan', state: 'queued', brief: { stage: 'lessons', section_id: 'sec_a' } } }
queues['lesson.regenerate'] = [
  {
    ok: true, contract_version: 20, operation_id: 't',
    result: {
      job_id: 'job_regen', kind: 'plan', state: 'queued',
      scope: { section_id: 'sec_a', objective_id: 'obj_a', section_count: 1 },
      preflight: {
        section_count: 1, minimum_calls: 1, maximum_calls: 2, cost_per_call_usd: 0.02,
        minimum_cost_usd: 0.02, maximum_cost_usd: 0.04, max_calls: 2, max_cost_usd: 0.5,
        budget_source: 'course', fits_minimum: true, fits_maximum: true
      },
      revision: 10
    }
  }
]
await renderPanel()
const regenButton = document.querySelector('[data-cb-finetune-regenerate]')
await click(byText(row('obj_a'), 'Regenerate this section'))
const scopeLine = text(document.querySelector('[data-cb-regenerate-scope]'))
const costBeforeClick = text(document.querySelector('[data-cb-regenerate-cost]'))
await click(document.querySelector('[data-cb-regenerate-queue]'))
facts.regenerate = {
  button: regenButton ? regenButton.getAttribute('data-cb-finetune-regenerate') : null,
  buttonDisabled: Boolean(regenButton && regenButton.disabled),
  scopeLine,
  costBeforeClick,
  call: calls.filter((c) => c.method === 'lesson.regenerate').at(-1) || null,
  result: text(document.querySelector('[data-cb-regenerate-result]'))
}

// 4e — a course whose blueprint serves no section identity withholds the actions and says why.
await renderPanel({ sections: [] })
const missingButton = document.querySelector('[data-cb-finetune-regenerate]')
facts.noSection = {
  regenerate: missingButton ? missingButton.getAttribute('data-cb-finetune-regenerate') : null,
  disabled: Boolean(missingButton && missingButton.disabled),
  marker: text(document.querySelector('[data-cb-finetune-section="unknown"]'))
}

// 5 — the review diff prints the backend's blocked reason verbatim.
await act(async () => {
  root.render(
    React.createElement(mod.StudioReviewDiff, {
      review: { status: 'ready', data: reviewData, error: null, reload: () => {} },
      objectives
    })
  )
})
await flush(40)
facts.reviewDiff = {
  state: document.querySelector('[data-cb-review-diff]').getAttribute('data-cb-review-diff'),
  exportGate: document.querySelector('[data-cb-review-export]').getAttribute('data-cb-review-export'),
  blockedReason: document.querySelector('[data-cb-review-blocked-reason]').getAttribute('data-cb-review-blocked-reason'),
  body: text(document.querySelector('[data-cb-review-diff]')).slice(0, 600),
  chips: [...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip')),
  changedFields: [...document.querySelectorAll('[data-cb-review-changed]')].map((n) => n.getAttribute('data-cb-review-changed'))
}

// 6 — a stale approval is refused and the export stays closed.
queues['parent.final.approve'] = [
  {
    ok: false, contract_version: 19, operation_id: 't',
    error: {
      code: 'VALIDATION_FAILED', category: 'validation', retryable: false,
      message: 'the content changed since it was read; re-read the blueprint.',
      field: 'content_hash', details: {}
    }
  }
]
const book = {
  status: 'ready',
  error: null,
  reload: () => {},
  data: {
    course_id: 'crs_1',
    plan: { plan_id: 'pln_1', version: 2, state: 'approved', plan_hash: 'sha256:plan' },
    approval: { state: 'superseded', plan_hash: 'sha256:old', content_hash: 'sha256:oldc', approved_at: null, invalidated_reason: 'plan_edited' },
    content_hash: 'sha256:content',
    export: { ready: false, blocked_reason: 'changes_need_review' },
    tabs: { parent_guide: [], learner_pages: [], answers: [], narration: [] },
    sources: []
  }
}
await act(async () => {
  root.render(
    React.createElement(mod.StudioExportPanel, {
      course: { course_id: 'crs_1', enrollment_id: 'enr_1' },
      book,
      revision: 3,
      onRevision: () => {},
      supported: () => true,
      onChanged: () => {},
      review: { status: 'ready', data: reviewData, error: null, reload: () => {} },
      objectives
    })
  )
})
await flush(80)
const exportButton = byText(document, 'Export the approved files')
const exportDisabledBefore = Boolean(exportButton && exportButton.disabled)
await click(byText(document, 'Approve this lesson set'))
const approveCall = calls.filter((c) => c.method === 'parent.final.approve').at(-1) || null
facts.staleExport = {
  blockedReason: (document.querySelector('[data-cb-export-blocked-reason]') || {}).textContent || null,
  blockedAttr: (document.querySelector('[data-cb-export-blocked]') || {}).getAttribute?.('data-cb-export-blocked') || null,
  exportDisabledBefore,
  exportDisabledAfter: Boolean((byText(document, 'Export the approved files') || {}).disabled),
  approveCall,
  errorText: text(document.querySelector('[data-cb-export-blocked]')) + ' | ' + text(document.body).slice(-260)
}

process.stdout.write(JSON.stringify({ facts }))
"""


class FineTuneSourceContractTest(unittest.TestCase):
    """The wiring is pinned where it is written: one command per move, no local-only order."""

    def setUp(self) -> None:
        self.source = PLUGIN_JS.read_text(encoding="utf-8")

    def test_a_move_sends_the_full_ordered_id_list(self) -> None:
        self.assertIn("const ids = display.map((objective) => objective.objective_id)", self.source)
        self.assertIn("reorder: next", self.source)
        self.assertIn("expected_plan_hash: planHash", self.source)

    def test_the_screen_adopts_the_returned_order_and_never_keeps_a_local_one(self) -> None:
        panel = self.source[self.source.index("function StudioFineTunePanel("): self.source.index("function StudioPlanView(")]
        self.assertIn("const saved = result.objective_ids || next", panel)
        self.assertIn("setOrder(saved)", panel)
        # No optimistic-only assignment: the only `setOrder` with a computed list is cleared to
        # null on refusal, never set before the command answers.
        self.assertNotIn("setOrder(next)", panel)
        self.assertNotIn("setOrder(ids)", panel)

    def test_a_keyboard_path_exists_beside_the_buttons(self) -> None:
        self.assertIn("event.altKey", self.source)
        self.assertIn("'aria-keyshortcuts': 'Alt+ArrowUp Alt+ArrowDown'", self.source)
        self.assertIn("if (event.key === 'ArrowUp')", self.source)
        self.assertIn("if (event.key === 'ArrowDown')", self.source)

    def test_the_order_conflict_keeps_the_stored_order(self) -> None:
        panel = self.source[self.source.index("function StudioFineTunePanel("): self.source.index("function StudioPlanView(")]
        conflict = panel[panel.index("details.reason === 'prerequisite_order_conflict'"):]
        self.assertIn("stored order was kept", conflict)
        refusal = panel[panel.index("if (!response.ok)"): panel.index("const result = response.result")]
        self.assertIn("setOrder(null)", refusal)

    def test_undo_calls_the_backend_command(self) -> None:
        self.assertIn("rpc('plan.undo'", self.source)
        self.assertIn("payload.revision_id = latestRevision.revision_id", self.source)

    def test_unsaved_changes_are_guarded_on_close_and_navigation(self) -> None:
        self.assertIn("window.addEventListener('beforeunload', guard)", self.source)
        self.assertIn("requestCancel", self.source)
        self.assertIn("data-cb-finetune-discard", self.source)
        self.assertIn("data-cb-studio-leave-guard", self.source)
        self.assertIn("The section editor has unsaved changes", self.source)

    def test_save_sends_plan_edit_objective_edits(self) -> None:
        self.assertIn("objective_edits: [edits]", self.source)
        self.assertIn("const edits = { objective_id: draft.objectiveId }", self.source)

    def test_review_diff_reads_parent_review_read_and_prints_the_reason_verbatim(self) -> None:
        self.assertIn("'parent.review.read'", self.source)
        self.assertIn("'data-cb-review-blocked-reason': blockedReason || ''", self.source)
        self.assertIn("'data-cb-export-blocked-reason': status.blocked_reason || ''", self.source)

    def test_the_plan_tab_mounts_the_panel_only_for_an_approved_parent_plan(self) -> None:
        self.assertIn("!isDraft && !learner\n        ? jsx(StudioFineTunePanel", self.source)

    def test_the_section_id_gap_is_stated_on_screen_not_in_the_console(self) -> None:
        self.assertIn("'data-cb-finetune-section': 'unknown'", self.source)
        self.assertIn("'no authored section'", self.source)
        self.assertIn("`sections[]`", self.source)
        self.assertIn("Nothing here invents a section id or a digest.", self.source)

    def test_the_panel_reads_the_section_identity_from_the_blueprint(self) -> None:
        self.assertIn("sections: (book && book.data && book.data.sections) || [],", self.source)
        self.assertIn("for (const row of sections || [])", self.source)
        self.assertIn("page_hash: row.page_hash || null", self.source)

    def test_the_page_title_is_fenced_on_the_served_digest(self) -> None:
        panel = self.source[self.source.index("function StudioFineTunePanel("): self.source.index("function StudioPlanView(")]
        self.assertIn("expected_page_hash: ref.page_hash", panel)
        self.assertIn("page: { section_title: pageTitle.slice(0, 300) }", panel)
        # The digest is never recomputed in the Desktop half.
        self.assertNotIn("createHash", panel)
        self.assertNotIn("sha256(", panel)

    def test_an_edit_after_attempts_asks_for_the_evidence_confirmation(self) -> None:
        panel = self.source[self.source.index("function StudioFineTunePanel("): self.source.index("function StudioPlanView(")]
        self.assertIn("details.reason === 'evidence_consequence_confirmation_required'", panel)
        self.assertIn("confirm_evidence_consequence = true", panel)
        self.assertIn("'data-cb-finetune-evidence'", panel)

    def test_regenerate_shows_the_scope_and_cost_and_is_not_gated_on_the_digest(self) -> None:
        panel = self.source[self.source.index("function StudioFineTunePanel("): self.source.index("function StudioPlanView(")]
        self.assertIn("'data-cb-regenerate-scope'", panel)
        self.assertIn("'data-cb-regenerate-cost'", panel)
        self.assertIn("fineTuneScopeLine(objective.title)", panel)
        # A section with no page yet is exactly what a one-section regenerate is for.
        self.assertIn("disabled: !ref || !ref.section_id,", panel)


@unittest.skipIf(shutil.which("node") is None, "node is required to render the runtime desktop plugin")
class FineTuneRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-h194-ui-")
        cls.root = Path(cls.tmp.name)
        (cls.root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (cls.root / "harness.mjs").write_text(HARNESS, encoding="utf-8")
        node_modules = cls.root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(STUB, encoding="utf-8")
        cls.case = cls.root / "case.json"
        cls.case.write_text(json.dumps({"responses": {}}), encoding="utf-8")
        result = subprocess.run(
            ["node", str(cls.root / "harness.mjs"), str(cls.case)],
            cwd=cls.root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr[-12000:])
        cls.facts = json.loads(result.stdout)["facts"]

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_keyboard_move_persists_the_returned_order(self) -> None:
        moved = self.facts["reorder"]
        self.assertEqual(moved["order"], "obj_b,obj_a,obj_c")
        self.assertIn("Order saved.", moved["notice"])
        payload = moved["call"]["payload"]
        self.assertEqual(payload["reorder"], ["obj_b", "obj_a", "obj_c"])
        self.assertEqual(payload["expected_plan_hash"], "sha256:plan")
        self.assertEqual(moved["call"]["expected_revision"], 3)
        self.assertTrue(moved["call"]["idempotency_key"])

    def test_a_refused_move_keeps_the_stored_order(self) -> None:
        refused = self.facts["refused"]
        self.assertEqual(refused["order"], "obj_a,obj_b,obj_c")
        self.assertIn("stored order was kept", refused["error"])

    def test_undo_calls_plan_undo_with_the_stored_revision(self) -> None:
        undo = self.facts["undo"]
        self.assertEqual(undo["call"]["payload"]["revision_id"], "prv_1")
        self.assertEqual(undo["call"]["payload"]["expected_plan_hash"], "sha256:plan")
        self.assertEqual(undo["order"], "obj_a,obj_b,obj_c")
        self.assertIn("Undid the last structural change", undo["notice"])

    def test_unsaved_changes_are_guarded_and_cancel_leaves_storage_alone(self) -> None:
        guard = self.facts["guard"]
        self.assertTrue(guard["dirtyWhileTyping"])
        self.assertTrue(guard["beforeUnloadPrevented"])
        self.assertEqual(guard["discardPrompt"], "cancel")
        self.assertTrue(guard["editorStillMounted"])
        self.assertTrue(guard["keptEditing"])
        self.assertTrue(guard["closedByDiscard"])
        self.assertEqual(guard["savesAfterDiscard"], guard["callsBeforeSave"])
        self.assertNotIn("Section metadata saved", guard["noticeAfterDiscard"] or "")

    def test_save_sends_objective_edits_and_closes_the_editor(self) -> None:
        guard = self.facts["guard"]
        call = guard["saveCall"]
        self.assertEqual(call["method"], "plan.edit")
        self.assertEqual(call["payload"]["objective_edits"], [{"objective_id": "obj_a", "title": "Alpha revised"}])
        self.assertEqual(call["payload"]["expected_plan_hash"], "sha256:plan")
        self.assertIn("needs review before export", guard["notice"])
        self.assertTrue(guard["editorClosedAfterSave"])

    def test_review_diff_prints_state_and_the_verbatim_reason(self) -> None:
        diff = self.facts["reviewDiff"]
        self.assertEqual(diff["state"], "pending")
        self.assertEqual(diff["exportGate"], "blocked")
        self.assertEqual(diff["blockedReason"], "changes_need_review")
        self.assertIn("changes_need_review", diff["body"])
        self.assertIn("needs_review", diff["chips"])
        self.assertIn("order", diff["changedFields"][0])

    def test_the_authored_page_title_is_saved_through_lesson_revise(self) -> None:
        page = self.facts["pageTitle"]
        self.assertFalse(page["disabled"], "a section with a served digest must be editable")
        self.assertEqual(page["initialValue"], "Alpha")
        call = page["call"]
        self.assertEqual(call["method"], "lesson.revise")
        self.assertEqual(call["payload"]["section_id"], "sec_a")
        self.assertEqual(call["payload"]["expected_page_hash"], "sha256:page-a")
        self.assertEqual(call["payload"]["title"], "Alpha revised page")
        self.assertEqual(call["payload"]["page"], {"section_title": "Alpha revised page"})
        self.assertEqual(call["expected_revision"], 3)
        self.assertTrue(call["idempotency_key"])
        self.assertNotIn("confirm_evidence_consequence", call["payload"])
        self.assertIn("needs review before export", page["notice"])
        self.assertTrue(page["editorClosed"])

    def test_an_edit_after_attempts_shows_the_consequence_and_confirms_it(self) -> None:
        evidence = self.facts["evidence"]
        self.assertEqual(evidence["prompt"], "2")
        self.assertIn("2 stored attempt(s)", evidence["promptText"])
        self.assertIn("keeps every stored attempt", evidence["promptText"])
        self.assertIn("2 learner attempt(s) already reference this section", evidence["error"])
        refused = evidence["refusedCall"]["payload"]
        self.assertNotIn("confirm_evidence_consequence", refused)
        retry = evidence["retryCall"]["payload"]
        self.assertTrue(retry["confirm_evidence_consequence"])
        self.assertEqual(retry["expected_page_hash"], "sha256:page-b")
        self.assertIn("needs review before export", evidence["notice"])
        # The chip for the edited section is `needs_review`, never an approval.
        self.assertIn("needs_review", self.facts["chips"])

    def test_regenerate_shows_scope_and_cost_before_queueing(self) -> None:
        regen = self.facts["regenerate"]
        self.assertEqual(regen["button"], "sec_a")
        self.assertFalse(regen["buttonDisabled"])
        self.assertEqual(regen["scopeLine"], "1 section: Alpha")
        self.assertIn("Estimated", regen["costBeforeClick"])
        call = regen["call"]
        self.assertEqual(call["method"], "lesson.regenerate")
        self.assertEqual(call["payload"]["section_id"], "sec_a")
        self.assertEqual(call["payload"]["plan_id"], "pln_1")
        self.assertIn("job_regen", regen["result"])
        self.assertIn("1 section: Alpha", regen["result"])

    def test_a_course_without_section_identity_withholds_the_actions(self) -> None:
        missing = self.facts["noSection"]
        self.assertEqual(missing["regenerate"], "unavailable")
        self.assertTrue(missing["disabled"])
        self.assertEqual(missing["marker"], "no authored section")

    def test_a_stale_approval_keeps_export_closed(self) -> None:
        stale = self.facts["staleExport"]
        self.assertEqual(stale["blockedAttr"], "changes_need_review")
        self.assertIn("Backend reason: changes_need_review", stale["blockedReason"])
        self.assertTrue(stale["exportDisabledBefore"])
        self.assertTrue(stale["exportDisabledAfter"])
        self.assertEqual(stale["approveCall"]["method"], "parent.final.approve")


if __name__ == "__main__":
    unittest.main()
