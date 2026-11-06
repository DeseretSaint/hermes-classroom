#!/usr/bin/env node
/**
 * CB-015 proof 6 — grader unavailable → needs_retry → explicit override, end to end.
 *
 * The JP demo course's 4th section ("Explain why register changes with the relationship") is an
 * open-response (rubric_only) check. This build injects no aux grader, so the backend fails closed
 * to `needs_retry` — a real backend verdict, not a simulated UI flag. The run then takes the two
 * actions the spec requires: Retry grading (same nonce, no second attempt) and Move on… (explicit
 * override), and reads the resulting state back off the page.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-needs-retry.mjs
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), steps: [] }

const snapshot = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : ''
    const buttons = [...document.querySelectorAll('[data-cb-route] button')]
    const has = (label) => buttons.some((b) => (b.innerText || '').trim() === label)
    return {
      hash: location.hash,
      text: text.replace(/\\n{2,}/g, '\\n').slice(0, 2600),
      needsRetryCopy: /I couldn.t grade this attempt/.test(text),
      retryGrading: has('Retry grading'),
      editAnswer: has('Edit answer'),
      moveOn: has('Move on…'),
      overriddenCopy: /Access granted — not independent evidence/.test(text),
      overrideEvidenceTag: /Override — not independent evidence/.test(text),
      objectiveOverridden: /Overridden/.test(text),
      attemptsBlock: (text.match(/ATTEMPTS ON THIS SECTION\\n([\\s\\S]{0,700})/) || [null, null])[1],
      dialogOpen: !!document.querySelector('[role="dialog"]'),
      dialogText: (() => {
        const d = document.querySelector('[role="dialog"]')
        return d ? (d.innerText || '').replace(/\\n{2,}/g, '\\n').slice(0, 400) : null
      })()
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  out.steps.push(value)
  console.log(
    JSON.stringify({
      step,
      needsRetry: value.needsRetryCopy,
      retry: value.retryGrading,
      moveOn: value.moveOn,
      overridden: value.overriddenCopy,
      dialog: value.dialogOpen
    })
  )
  return value
}

// ── open the JP course's 4th section ───────────────────────────────────────────────────────
cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`,
  { timeout: 30000, label: 'course rows' }
)
const courseOpened = await cdp.eval(`(() => {
  const wanted = [...document.querySelectorAll('[data-cb-route] *')]
    .filter(n => /^Japanese affection/.test((n.textContent || '').trim()))
    .sort((a, b) => (a.textContent || '').length - (b.textContent || '').length)[0]
  if (!wanted) return 'no-title'
  let node = wanted
  for (let i = 0; i < 10 && node; i += 1) {
    const open = [...node.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Open')
    if (open) { open.click(); return 'clicked' }
    node = node.parentElement
  }
  return 'no-open'
})()`)
if (courseOpened !== 'clicked') throw new Error(`open affection course: ${courseOpened}`)
await cdp.wait(2200)
const courseTitle = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '').slice(0, 400)`)
if (!/affection/i.test(courseTitle)) throw new Error(`wrong course opened: ${courseTitle.slice(0, 160)}`)

const textbook = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x => (x.innerText || '').trim() === 'Textbook')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (textbook !== 'clicked') throw new Error('no Textbook tab')
await cdp.wait(1500)

// The JP demo course's 4th section (ordinal 4) carries an open rubric_only (open-response)
// check — the only kind this build can fail closed on — and its binding is active.
const sectionOpened = await cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Open section')
  const b = bs[3]
  if (!b) return 'missing(' + bs.length + ')'
  b.click()
  return 'clicked:' + bs.length
})()`)
if (!String(sectionOpened).startsWith('clicked')) throw new Error(`last section: ${sectionOpened}`)
await cdp.wait(2800)
const before = await record('section-open')
if (!/register changes with the relationship/i.test(before.text)) {
  throw new Error(`the 4th section is not the open-response section this proof needs: ${before.text.slice(0, 160)}`)
}
await cdp.shot(`${SHOTS}/72-needs-retry-before-answer.png`)

// ── answer it: the backend must fail closed to needs_retry ────────────────────────────────
const typed = await cdp.eval(`(() => {
  const el = document.querySelector('#cb-attempt-answer')
  if (!el) return 'missing'
  el.focus()
  return el.tagName.toLowerCase()
})()`)
if (typed === 'missing') throw new Error('no answer field on the section page')
await cdp.type('The register changes because the addressee changes: a friend in private gets casual 好きだよ, a first meeting needs よろしくお願いいたします.')
await cdp.wait(300)
const submitted = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Submit answer')
  if (!b || b.disabled) return b ? 'disabled' : 'missing'
  b.click()
  return 'clicked'
})()`)
if (submitted !== 'clicked') throw new Error(`submit: ${submitted}`)
await cdp.waitFor(`/I couldn.t grade this attempt/.test(document.querySelector('[data-cb-route]').innerText || '')`, {
  timeout: 90000,
  label: 'needs_retry copy'
})
const needsRetry = await record('needs-retry')
await cdp.shot(`${SHOTS}/73-needs-retry-dark.png`)

// ── Retry grading: a retry is not a second attempt ────────────────────────────────────────
const retried = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Retry grading')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (retried !== 'clicked') throw new Error('no Retry grading control')
await cdp.wait(400)
await cdp.waitFor(`/I couldn.t grade this attempt|ATTEMPTS ON THIS SECTION/.test(document.querySelector('[data-cb-route]').innerText || '')`, {
  timeout: 90000,
  label: 'retry settled'
})
await cdp.wait(2500)
const afterRetry = await record('retry-grading')

// ── Move on… → Record override ────────────────────────────────────────────────────────────
const moveOn = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Move on…')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (moveOn !== 'clicked') throw new Error('no Move on… control')
await cdp.waitFor(`!!document.querySelector('[role="dialog"]')`, { timeout: 10000, label: 'override dialog' })
await cdp.wait(400)
const dialog = await record('override-dialog')
await cdp.shot(`${SHOTS}/74-override-confirm-dark.png`)

const confirmed = await cdp.eval(`(() => {
  const d = document.querySelector('[role="dialog"]')
  if (!d) return 'no-dialog'
  const b = [...d.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Record override')
  if (!b) return 'missing'
  b.click()
  return 'clicked'
})()`)
if (confirmed !== 'clicked') throw new Error(`confirm override: ${confirmed}`)

// The immediate verdict panel is short-lived: onCommitted reloads the section, so the panel is
// replaced by the fresh check. Poll for it, then assert the durable record instead.
let panelSeen = false
for (let i = 0; i < 120 && !panelSeen; i += 1) {
  panelSeen = await cdp.eval(
    `/Access granted — not independent evidence/.test(document.querySelector('[data-cb-route]').innerText || '')`
  )
  if (!panelSeen) await cdp.wait(100)
}
await cdp.waitFor(
  `/Override — not independent evidence/.test(document.querySelector('[data-cb-route]').innerText || '')`,
  { timeout: 60000, label: 'durable override row' }
)
await cdp.wait(1500)
const overridden = await record('overridden', { immediatePanelSeen: panelSeen })
await cdp.shot(`${SHOTS}/75-overridden-dark.png`)

out.verdict = {
  honestNeedsRetryCopy: needsRetry.needsRetryCopy && needsRetry.retryGrading && needsRetry.moveOn,
  retryDidNotAdvance: afterRetry.needsRetryCopy && !afterRetry.overriddenCopy,
  overrideRecorded: overridden.overrideEvidenceTag && overridden.objectiveOverridden,
  dialogExplainedFence: Boolean(dialog.dialogText && /never counted as independent evidence|not independent/i.test(dialog.dialogText)),
  dialogClosed: !overridden.dialogOpen,
  immediatePanelSeen: panelSeen
}
const path = await writeJson('docs/REVIEW_CB015-needs-retry.json', out)
console.log(JSON.stringify(out.verdict, null, 2))
console.log(`wrote ${path}`)
cdp.close()
process.exit(0)
