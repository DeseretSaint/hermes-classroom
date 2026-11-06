#!/usr/bin/env node
/**
 * Row 7 — hide / reopen the Coursebook pane while an answer is in flight.
 *
 * The bound chat's open check is answered from the pane: type, click Submit answer, then hide the
 * host's right sidebar (the pane's own container) before grading settles, wait, reopen it, and read
 * the pane back. Records the attempts block before/after and whether the pane stayed mounted.
 *
 *   node row7-hide-split.mjs <outJson> <shotDir>
 */
import { connect, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'

const outPath = process.argv[2]
const shots = process.argv[3] || 'docs/cb015-shots'
let cdp = await connect()
const steps = []

const snapshot = () =>
  cdp.json(`(() => {
    const body = document.body.innerText || ''
    const i = body.indexOf('COURSEBOOK')
    const pane = i >= 0 ? body.slice(i, i + 2600) : ''
    const root = document.querySelector('[data-cb-route]')
    const buttons = [...document.querySelectorAll('button')]
    const has = (label) => buttons.some((b) => (b.innerText || '').trim() === label)
    const sidebarToggle = buttons
      .map((b) => (b.getAttribute('aria-label') || '').trim())
      .filter((l) => /sidebar/i.test(l))
    return {
      hash: location.hash,
      paneMounted: i >= 0,
      paneText: pane.replace(/\\n{2,}/g, '\\n').slice(0, 2400),
      hasAnswerBox: !!document.querySelector('#cb-attempt-answer'),
      answerDisabled: (document.querySelector('#cb-attempt-answer') || {}).disabled ?? null,
      submitDisabled: (() => { const b = buttons.find((x) => (x.innerText || '').trim() === 'Submit answer'); return b ? b.disabled : null })(),
      verdict: (pane.match(/Passed|Partly there|Not yet/) || [null])[0],
      attemptsBlock: (pane.match(/ATTEMPTS ON THIS SECTION\\n([\\s\\S]{0,900})/) || [null, null])[1],
      sidebarToggle,
      route: !!root
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  steps.push(value)
  console.log(JSON.stringify({ step, ...extra, verdict: value.verdict, submitDisabled: value.submitDisabled, paneMounted: value.paneMounted, toggles: value.sidebarToggle }))
  return value
}

/** Click a host control by its exact aria-label, through real mouse geometry. */
const clickLabel = async (label) => {
  const box = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('button')].find((e) => (e.getAttribute('aria-label') || '').trim() === ${JSON.stringify(label)})
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
  if (!box) return 'missing'
  await cdp.click(box.x, box.y)
  return 'clicked'
}

const before = await record('bound-open-check')
if (!before.hasAnswerBox) throw new Error('no answer box in the bound pane — open the bound chat first')
if (!/CURRENT CHECK/.test(before.paneText)) throw new Error('pane is not showing an open check')
await cdp.shot(`${shots}/row7-01-before-answer.png`)

// ── type the answer into the pane's own field ────────────────────────────────────────────
const field = await cdp.json(`(() => {
  const el = document.querySelector('#cb-attempt-answer')
  if (!el) return null
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (!field) throw new Error('answer field has no geometry')
await cdp.click(field.x, field.y)
await cdp.wait(200)
await cdp.type('Casual 好きだよ is for a close friend or partner in private; polite 好きです keeps distance and is safe with someone new.')
await cdp.wait(300)
await record('typed')

// ── submit, then hide the pane immediately while the attempt is in flight ────────────────
const submitted = await cdp.json(`(() => {
  const b = [...document.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Submit answer')
  if (!b || b.disabled) return b ? 'disabled' : 'missing'
  const r = b.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (typeof submitted === 'string') throw new Error(`submit: ${submitted}`)
await cdp.click(submitted.x, submitted.y)
const hideLabel = (await snapshot()).sidebarToggle.find((l) => /right sidebar/i.test(l) && /^hide/i.test(l))
const hideResult = hideLabel ? await clickLabel(hideLabel) : 'no-hide-control'
const inFlight = await record('submitted-then-hidden', { hideLabel, hideResult })
const mountedWhileHidden = inFlight.paneMounted
await cdp.shot(`${shots}/row7-02-pane-hidden-in-flight.png`)

// ── wait for the attempt to settle with the pane hidden ─────────────────────────────────
await cdp.wait(12000)
const hidden = await record('hidden-while-settling', { paneMountedExpected: mountedWhileHidden })

// ── reopen and read the pane back ───────────────────────────────────────────────────────
const showLabel = (await snapshot()).sidebarToggle.find((l) => /right sidebar/i.test(l) && /^show/i.test(l))
const showResult = showLabel ? await clickLabel(showLabel) : 'no-show-control'
await cdp.wait(1800)
const reopened = await record('reopened', { showLabel, showResult })
await cdp.shot(`${shots}/row7-03-reopened.png`)

// Give the pane one more settling window if the verdict had not rendered yet.
if (!reopened.verdict) {
  await cdp.wait(8000)
  await record('reopened-late')
}
const final = await record('final')

await writeJson(outPath, {
  at: new Date().toISOString(),
  objective: 'row7-hide-reopen-pane-mid-attempt',
  verdicts: {
    paneMountedWhileHidden: mountedWhileHidden,
    hideControl: hideResult,
    showControl: showResult,
    verdictVisibleAfterReopen: Boolean(final.verdict),
    submitDisabledAfter: final.submitDisabled,
    attemptsBlockAfter: final.attemptsBlock
  },
  steps
})
console.log('wrote', outPath)
cdp.close()
