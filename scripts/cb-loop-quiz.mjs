/**
 * Loop 2 — Quiz: open the check, answer, submit, read the grading, then review the attempt.
 * Uses the section's own check panel; no RPC is called directly from this script.
 */
import { attach, openCourse, tab, openSectionByIndex, clickExact, shot, makeLog, routeText } from './cb-loops-lib.mjs'

const cdp = await attach()
const log = makeLog()
const activeEl = () => cdp.eval(`(() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.getAttribute('id') || '') + '|' + ((a.innerText || '').trim().slice(0, 40)) : 'none' })()`)
// The audited check for this objective accepts B / confession as the answer (pack stimulus:
// "Which line is the romantic confession"). The UI field records the answer the learner would give.
const ANSWER = 'B'

// ── 1. open the section that owns the live check ───────────────────────────
await openCourse(cdp, 'Japanese affection and register — an L0 demonstration classroom')
await openSectionByIndex(cdp, 0)
await cdp.waitFor(`!!document.querySelector('#cb-attempt-answer')`, { timeout: 20000, label: 'check panel' })
const check = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root.innerText
  const submit = [...root.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Submit answer')
  return {
    checkLabel: (text.match(/Check v\\d+/) || [null])[0],
    target: (text.match(/CURRENT CHECK\\n[^\\n]+\\n([^\\n]+)/) || [null, null])[1],
    submitDisabled: submit ? submit.disabled : null,
    bound: !/binding is detached/.test(text)
  }
})()`)
await log.add(cdp, 'check-open', 'A live check is offered for the section, Submit disabled until an answer exists', 'check panel rendered', check)
await shot(cdp, '20-quiz-check-open')

// ── 2. answer in the panel's own field ─────────────────────────────────────
const box = await cdp.json(`(() => {
  const el = document.querySelector('#cb-attempt-answer')
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
await cdp.click(box.x, box.y)
await cdp.wait(150)
const focusInField = await activeEl()
await cdp.type(ANSWER)
await cdp.wait(400)
const enabled = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Submit answer'); return b ? !b.disabled : null })()`)
await log.add(cdp, 'answer-typed', 'Answer lands in the check field and Submit enables', enabled ? 'Submit enabled' : 'Submit still disabled', {
  focus: focusInField,
  typedChars: ANSWER.length
})
await shot(cdp, '21-quiz-answer-typed')

// ── 3. submit and read the grading ─────────────────────────────────────────
await clickExact(cdp, 'Submit answer')
await cdp.wait(1200)
const pending = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
await log.add(cdp, 'submitted', 'Answer locks while one grading operation runs', /Grading this answer|Submitting/.test(pending) ? 'submitting state shown' : 'no submitting indicator observed', {
  focusAfterSubmit: await activeEl()
})
await shot(cdp, '22-quiz-grading')

await cdp.waitFor(
  `(() => {
    const t = document.querySelector('[data-cb-route]').innerText
    const formGone = !document.querySelector('#cb-attempt-answer')
    const verdict = /\\b(Passed|Partly there|Not yet|Grading failed)\\b/.test(t) || /couldn’t grade this attempt/.test(t)
    const failed = /VALIDATION_FAILED|HOST_UNAVAILABLE|INTERNAL/.test(t)
    return (formGone && verdict) || failed
  })()`,
  { timeout: 120000, interval: 100, label: 'graded verdict' }
)
await cdp.wait(600)
const gradedText = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
const feedback = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root.innerText
  const start = text.indexOf('CURRENT CHECK')
  return {
    segment: text.slice(start, start + 1200),
    verdict: (text.match(/\\n(Passed|Partly there|Not yet|Grading failed)\\n/) || [null, null])[1],
    error: (text.match(/(VALIDATION_FAILED|HOST_UNAVAILABLE|INTERNAL)[^\\n]*/) || [null])[0],
    answerStillShown: text.includes('好きだよ (suki da yo) is the casual line'),
    focusAfterGrading: (() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.innerText || '').trim().slice(0, 40) : 'none' })()
  }
})()`)
await log.add(cdp, 'graded', 'Backend returns a verdict, criteria feedback and the next permitted action', feedback.verdict ? `verdict: ${feedback.verdict}` : 'no verdict label matched', feedback)
await shot(cdp, '23-quiz-graded')

// ── 4. review the attempt in Quizzes ───────────────────────────────────────
await tab(cdp, 'Quizzes')
await cdp.wait(1600)
const list = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root.innerText
  const rows = [...root.querySelectorAll('button')].filter(b => /\\d{1,2}:\\d{2}|ago/.test((b.innerText || ''))).map(b => (b.innerText || '').trim().slice(0, 90))
  return {
    text: text.slice(0, 1400),
    rows,
    buttons: [...new Set([...root.querySelectorAll('button')].map(b => (b.innerText || '').trim()).filter(Boolean))].slice(0, 30)
  }
})()`)
await log.add(cdp, 'quiz-list', 'The new attempt appears in the attempt list with its verdict', list.text.includes('Cold') || list.rows.length ? 'attempt list rendered' : 'attempt list empty', {
  rows: list.rows.slice(0, 5),
  buttonCount: list.buttons.length
})
await shot(cdp, '24-quiz-list')

// open the newest attempt row (the list is newest first; each row has its own Open attempt control)
const opened = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const el = [...root.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Open attempt')
  if (!el) return { ok: false }
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  return { ok: true, x: r.x + r.width / 2, y: r.y + r.height / 2, label: 'Open attempt' }
})()`)
if (opened.ok) {
  await cdp.click(opened.x, opened.y)
  await cdp.wait(1500)
}
const review = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root.innerText
  return {
    hash: location.hash,
    segment: text.slice(0, 2200),
    readOnly: ![...root.querySelectorAll('button')].some(b => (b.innerText || '').trim() === 'Submit answer'),
    hasTextarea: !!root.querySelector('#cb-attempt-answer'),
    disputeField: !!root.querySelector('textarea'),
    actions: [...new Set([...root.querySelectorAll('button')].map(b => (b.innerText || '').trim()).filter(Boolean))]
  }
})()`)
await log.add(cdp, 'review-open', 'Opening an attempt shows the original answer and feedback read-only (no Submit, no answer field)', review.readOnly && !review.hasTextarea ? 'read-only review' : 'editable controls found', {
  openedRow: opened.ok ? opened.label : null,
  actions: review.actions.slice(0, 20),
  answerShown: /\nB\n/.test(review.segment),
  readOnlyNote: /Reviewing is read-only/.test(review.segment)
})
await shot(cdp, '25-quiz-review')

// ── 5. reload and confirm the review survives ──────────────────────────────
await cdp.reload()
await cdp.wait(4000)
await cdp.waitFor(`!!document.querySelector('button')`, { timeout: 20000, label: 'shell mount' })
await openCourse(cdp, 'Japanese affection and register — an L0 demonstration classroom')
await tab(cdp, 'Quizzes')
await cdp.wait(1800)
const afterReload = await routeText(cdp)
await log.add(cdp, 'review-persistence', 'After reload the attempt history still lists the graded attempt', /Cold/.test(afterReload) ? 'attempt still listed' : 'attempt missing', {
  newestRow: (afterReload.match(/[^\n]*\n[^\n]*Cold[^\n]*/) || [null])[0]
})
await shot(cdp, '26-quiz-after-reload')

console.log('ERRORS:', JSON.stringify(cdp.errors))
await log.add(cdp, 'console', 'No renderer exceptions or console errors during the loop', `${cdp.errors.length} captured`, { errors: cdp.errors })
console.log('LOG', await log.write('docs/cb-loops-quiz.json'))
cdp.close()
