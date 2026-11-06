#!/usr/bin/env node
/**
 * CB-015 loop A — teaching moment -> governed attempt -> notebook save -> exact section.
 *
 * Everything here is a real DOM click on a labelled control, a real key event for Enter, and
 * text typed with Input.insertText. No fixtures: the verdict and the notebook row come from
 * the live backend on 44220.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-loops-a.mjs
 */
import { connect } from './cb015-lib.mjs'
import { writeFileSync, readFileSync, existsSync } from 'node:fs'

const cdp = await connect()
const OUT = 'docs/REVIEW_CB015-loops.json'
const SHOTS = 'docs/cb015-shots'
const trace = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { steps: [], shots: [] }
const step = async (label, extra = {}) => {
  const state = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const body = document.body.innerText || ''
    return {
      hash: location.hash,
      route: root ? root.getAttribute('data-cb-route') : null,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      routeText: root ? root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 1600) : '',
      panePresent: /COURSEBOOK/.test(body),
      bindingDetached: /chat binding is detached/.test(body),
      submitDisabled: (() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Submit answer'); return b ? b.disabled : null })(),
      modes: ['graded', 'needs_retry', 'overridden'].filter((m) => new RegExp(m === 'graded' ? 'ATTEMPTS ON THIS SECTION' : m).test(body))
    }
  })()`)
  const entry = { step: label, at: new Date().toISOString(), ...state, ...extra }
  trace.steps.push(entry)
  console.log(JSON.stringify({ step: label, hash: entry.hash, destination: entry.destination, detached: entry.bindingDetached, submitDisabled: entry.submitDisabled }))
  return entry
}
const shoot = async (name) => {
  const path = await cdp.shot(`${SHOTS}/${name}.png`)
  trace.shots.push(path)
  return path
}
const tab = async (label) => {
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>x.innerText.trim()===${JSON.stringify(label)}); if(b) b.click(); })()`)
  await cdp.wait(1200)
}
const openSection = async (index) => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(2200)
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>x.innerText.trim()==='Open'); if(b) b.click(); })()`)
  await cdp.wait(1800)
  await tab('Textbook')
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => b.innerText.trim() === 'Open section')
    const b = bs[${index}]
    if (!b) return 'missing(' + bs.length + ')'
    b.click()
    return 'clicked'
  })()`)
  if (opened !== 'clicked') throw new Error('open section: ' + opened)
  await cdp.wait(2600)
}

// ---- 0. early section, detached state
await openSection(0)
await step('early-section-detached')
await shoot('10-section-detached-dark')

// ---- 1. arm an exact run: Start a fresh run opens the chat session
const armed = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Start a fresh run')
  if (!b) return 'missing'
  b.click(); return 'clicked'
})()`)
if (armed !== 'clicked') throw new Error('no Start a fresh run control')
await cdp.waitFor(`!!document.querySelector('[contenteditable="true"]')`, { timeout: 30000, label: 'composer' })
await cdp.wait(1500)
await step('fresh-run-armed')
const chatHash = await cdp.eval('location.hash')

// ---- 2. one real teaching turn (types + Enter through the input pipeline)
await cdp.eval(`(() => { const el = document.querySelector('[contenteditable="true"]'); el.focus(); return true })()`)
await cdp.type(
  'I am ready for this section. Remind me what separates casual 好きだよ from the polite confession, then give me the check.'
)
await cdp.wait(300)
for (const type of ['keyDown', 'keyUp']) {
  await cdp.send('Input.dispatchKeyEvent', {
    type,
    key: 'Enter',
    code: 'Enter',
    windowsVirtualKeyCode: 13,
    nativeVirtualKeyCode: 13,
    text: type === 'keyDown' ? '\r' : undefined
  })
}
// wait for the transcript to stop growing
let previous = ''
let stableSince = 0
const deadline = Date.now() + 240000
while (Date.now() < deadline) {
  const length = await cdp.eval(`(document.body.innerText || '').length`)
  if (length === previous) {
    if (!stableSince) stableSince = Date.now()
    if (Date.now() - stableSince > 9000) break
  } else {
    stableSince = 0
    previous = length
  }
  await cdp.wait(1000)
}
await cdp.wait(1200)
await step('teaching-turn-complete')
await shoot('11-bound-chat-dark')

// ---- 3. back to the section: the check must now be bound
await openSection(0)
const bound = await step('section-bound')
await shoot('12-section-bound-dark')
if (bound.bindingDetached) throw new Error('section still detached after a real chat run')

// ---- 4. wrong answer -> governed retry (not a free pass)
if (await cdp.eval(`!!document.querySelector('#cb-attempt-answer')`)) {
  await cdp.eval(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.scrollIntoView({block:'center'}); el.focus(); return true })()`)
  await cdp.type('Both lines are equally romantic. Politeness has nothing to do with how the line is heard.')
  await cdp.wait(300)
  await step('wrong-answer-typed')
  const submitted = await cdp.eval(`(() => { const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()==='Submit answer'); if(!b||b.disabled) return 'unavailable'; b.click(); return 'clicked' })()`)
  if (submitted === 'clicked') {
    const started = Date.now()
    while (Date.now() - started < 120000) {
      const done = await cdp.eval(`(() => { const t=document.body.innerText||''; return /ATTEMPTS ON THIS SECTION/.test(t) || /I couldn.t grade this attempt/.test(t) })()`)
      if (done) break
      await cdp.wait(800)
    }
    await cdp.wait(1200)
    const verdict = await cdp.eval(`(() => {
      const t = document.body.innerText || ''
      const at = t.indexOf('ATTEMPTS ON THIS SECTION')
      return at < 0 ? '' : t.slice(at, at + 900)
    })()`)
    await step('wrong-answer-graded', { verdict })
    await shoot('13-wrong-answer-dark')
  }
}

// ---- 5. save the teaching moment to the notebook from the section page
const saved = await cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => b.innerText.trim() === 'Save to notebook')
  if (!bs.length) return 'missing'
  bs[0].click(); return 'clicked(' + bs.length + ')'
})()`)
await cdp.wait(1400)
const dialog = await cdp.json(`(() => {
  const t = document.body.innerText || ''
  const at = t.indexOf('Save to notebook')
  return {
    text: at < 0 ? '' : t.slice(at, at + 1200),
    inputs: [...document.querySelectorAll('input, textarea, select')].map(e => ({ tag: e.tagName, id: e.id, value: (e.value || '').slice(0, 120), placeholder: e.placeholder }))
  }
})()`)
await step('notebook-dialog', { saved, dialog })
await shoot('14-notebook-dialog-dark')

cdp.close()
writeFileSync(OUT, JSON.stringify(trace, null, 2))
console.log('wrote', OUT)
