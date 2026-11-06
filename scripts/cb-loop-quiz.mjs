/**
 * Loop 2 — Quiz: open the check, answer, submit, read the grading, then review the attempt.
 * Uses the section's own check panel; no RPC is called directly from this script.
 *
 * This pass is the t_74066a11 re-drive. It repairs the two faults in the first capture:
 *
 *   1. the attempt list was read with a selector that only matched a clock time or the word
 *      "ago" (`whenLabel` renders "just now" for the newest row), so a populated list was
 *      recorded as `rows: []`. Rows are now counted from their own "Open attempt" control, and
 *      the run asserts the count grew by exactly one and that the new row carries the verdict;
 *   2. every screenshot is gated on `[data-cb-route]` having content (see `shot` in
 *      cb-loops-lib.mjs), so a snapshot of host chrome is refused instead of written.
 *
 * All steps are recorded by one `makeLog()` pass; `finished_at` is written last, so timestamps
 * are monotonic by construction and the file describes exactly one run.
 */
import {
  attach,
  openCourse,
  tab,
  openSectionByIndex,
  clickExact,
  shot,
  makeLog,
  KEY_WARNING,
  HOST_WARNING
} from './cb-loops-lib.mjs'

const cdp = await attach()
const log = makeLog()
const startedAt = new Date().toISOString()
const activeEl = () => cdp.eval(`(() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.getAttribute('id') || '') + '|' + ((a.innerText || '').trim().slice(0, 40)) : 'none' })()`)
// The audited check for this objective accepts B / confession as the answer (pack stimulus:
// "Which line is the romantic confession"). The UI field records the answer the learner would give.
const ANSWER = 'B'

/** Read the Quizzes attempt list from its own rows, newest first. */
async function readAttemptList() {
  return cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const opens = [...root.querySelectorAll('button')].filter(b => (b.innerText || '').trim() === 'Open attempt')
    const rows = opens.map((button) => {
      // row container: button → header row → attempt row
      const row = button.parentElement && button.parentElement.parentElement
      if (!row) return null
      const lines = (row.innerText || '').trim().split('\\n').map((line) => line.trim()).filter(Boolean)
      return {
        verdict: lines[0],
        assistance: lines[1],
        when: lines[2],
        answer: lines.slice(3).filter((line) => line !== 'Open attempt').join(' ').slice(0, 160)
      }
    }).filter(Boolean)
    return { count: rows.length, rows, destination: root.getAttribute('data-cb-destination') }
  })()`)
}

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
await log.add(cdp, 'check-open', 'A live check is offered for the section, Submit disabled until an answer exists', check.submitDisabled === true ? 'check panel rendered, Submit disabled' : 'check panel rendered', check)
await shot(cdp, '20-quiz-check-open')

// ── 2. record the attempt list BEFORE this submission ──────────────────────
await tab(cdp, 'Quizzes')
await cdp.waitFor(`document.querySelectorAll('[data-cb-route] button').length > 0`, { timeout: 10000, label: 'quizzes tab' })
await cdp.wait(900)
const before = await readAttemptList()
await log.add(cdp, 'list-before', 'The Quizzes destination lists the attempts that already exist', `attempt rows: ${before.count}`, {
  rows: before.count,
  newest: before.rows[0] || null,
  destination: before.destination
})
await shot(cdp, '24a-quiz-list-before')

// back to the section with the open check
await openSectionByIndex(cdp, 0)
await cdp.waitFor(`!!document.querySelector('#cb-attempt-answer')`, { timeout: 20000, label: 'check panel again' })

// ── 3. answer in the panel's own field ─────────────────────────────────────
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

// ── 4. submit and read the grading ────────────────────────────────────────
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
const feedback = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root.innerText
  const start = text.indexOf('CURRENT CHECK')
  return {
    segment: text.slice(start, start + 1200),
    verdict: (text.match(/\\n(Passed|Partly there|Not yet|Grading failed)\\n/) || [null, null])[1],
    error: (text.match(/(VALIDATION_FAILED|HOST_UNAVAILABLE|INTERNAL)[^\\n]*/) || [null])[0],
    criteriaRows: [...root.querySelectorAll('ul li')].map((li) => (li.innerText || '').trim()),
    focusAfterGrading: (() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.innerText || '').trim().slice(0, 40) : 'none' })()
  }
})()`)
await log.add(cdp, 'graded', 'Backend returns a verdict, criteria feedback and the next permitted action', feedback.verdict ? `verdict: ${feedback.verdict}` : 'no verdict label matched', feedback)
await shot(cdp, '23-quiz-graded')

// ── 5. the new attempt is in Quizzes, with its verdict ────────────────────
await tab(cdp, 'Quizzes')
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Open attempt').length > ${before.count}`,
  { timeout: 30000, interval: 200, label: 'new attempt row' }
)
await cdp.wait(500)
const after = await readAttemptList()
const newest = after.rows[0] || null
const verdictOk = Boolean(newest && newest.verdict === feedback.verdict)
const grewByOne = after.count === before.count + 1
await log.add(
  cdp,
  'quiz-list',
  'The attempt that was just graded appears in the attempt list with its verdict',
  grewByOne && verdictOk ? `new row: ${newest.verdict} · ${newest.assistance}` : `rows ${before.count} → ${after.count}, newest ${JSON.stringify(newest)}`,
  {
    rowsBefore: before.count,
    rowsAfter: after.count,
    grewByOne,
    verdictOk,
    newest
  }
)
if (!grewByOne || !verdictOk) throw new Error(`quiz-list assertion failed: before=${before.count} after=${after.count} newest=${JSON.stringify(newest)}`)
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
  answerShown: /(^|\n)B(\n|$)/.test(review.segment),
  readOnlyNote: /Reviewing is read-only/.test(review.segment),
  segment: review.segment.slice(0, 900)
})
await shot(cdp, '25-quiz-review')

// ── 6. reload and confirm the attempt survives ────────────────────────────
await cdp.reload()
await cdp.wait(4000)
await cdp.waitFor(`!!document.querySelector('button')`, { timeout: 20000, label: 'shell mount' })
await openCourse(cdp, 'Japanese affection and register — an L0 demonstration classroom')
await tab(cdp, 'Quizzes')
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Open attempt').length >= ${after.count}`,
  { timeout: 30000, interval: 200, label: 'persisted attempt rows' }
)
await cdp.wait(600)
const reloaded = await readAttemptList()
const reloadedNewest = reloaded.rows[0] || null
const persisted =
  reloaded.count === after.count &&
  Boolean(reloadedNewest) &&
  reloadedNewest.verdict === newest.verdict &&
  reloadedNewest.assistance === newest.assistance &&
  reloadedNewest.answer === newest.answer
await log.add(
  cdp,
  'review-persistence',
  'After a renderer reload the attempt is still listed with the same verdict',
  persisted ? `attempt still listed: ${reloadedNewest.verdict} · ${reloadedNewest.assistance}` : `rows ${after.count} → ${reloaded.count}, newest ${JSON.stringify(reloadedNewest)}`,
  {
    rowsAfterReload: reloaded.count,
    persisted,
    newest: reloadedNewest
  }
)
if (!persisted) throw new Error(`persistence assertion failed: before=${JSON.stringify(newest)} after=${JSON.stringify(reloadedNewest)}`)
await shot(cdp, '26-quiz-after-reload')

// ── 7. console: no errors, and no React key warning ───────────────────────
const keyWarnings = cdp.errors.filter((e) => KEY_WARNING.test(e.text || '')).concat(cdp.warnings.filter((w) => KEY_WARNING.test(w.text || '')))
const hostWarnings = cdp.warnings.filter((w) => HOST_WARNING.test(w.text || ''))
const pluginWarnings = cdp.warnings.filter((w) => !HOST_WARNING.test(w.text || ''))
await log.add(
  cdp,
  'console',
  'No renderer exceptions, no console errors, and no React list-key warning during the loop',
  `${cdp.errors.length} error(s), ${keyWarnings.length} key warning(s), ${pluginWarnings.length} other plugin warning(s)`,
  {
    errors: cdp.errors,
    keyWarnings,
    pluginWarnings,
    hostWarnings: hostWarnings.length
  }
)
if (cdp.errors.length > 0 || keyWarnings.length > 0) {
  throw new Error(`console gate failed: ${JSON.stringify({ errors: cdp.errors, keyWarnings })}`)
}

console.log('ERRORS:', JSON.stringify(cdp.errors))
console.log('WARNINGS:', JSON.stringify(pluginWarnings))
console.log('LOG', await log.write(process.env.CB_LOOPS_QUIZ_OUT || 'docs/cb-loops-quiz.json', {
  run: {
    started_at: startedAt,
    window_cdp_port: process.env.CB015_CDP_PORT || '9337',
    plugin_sha256: process.env.CB_PLUGIN_SHA256 || 'not recorded',
    git_head: process.env.CB_GIT_HEAD || 'not recorded',
    backend_base: process.env.CB013_BASE || 'http://127.0.0.1:44219',
    wire_version: process.env.CB_WIRE_VERSION || 'not recorded'
  }
}))
cdp.close()
