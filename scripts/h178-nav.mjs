#!/usr/bin/env node
/**
 * H-178: navigate the isolated Desktop window to the Field Stop player for one stop.
 *
 * Works from wherever the window is: opens the Coursebook route, the course shelf, the course's
 * Learn tab, the requested stop, and the Game (player) view. Prints the state it reached so a
 * caller can refuse to capture anything else.
 */
import { connect } from './h149-cdp.mjs'

const port = process.env.CB009_CDP_PORT || '9385'
const stop = process.argv[2] || '02'
const { evaluate, wait } = await connect(port)

const clickText = async (label, exact = true) =>
  evaluate(`(() => {
    const wanted = ${JSON.stringify(label)}
    const nodes = [...document.querySelectorAll('button, [role="tab"]')]
    const node = nodes.find((n) => {
      const text = (n.innerText || '').replace(/\\s+/g, ' ').trim()
      return ${exact ? 'text === wanted' : 'text.startsWith(wanted)'}
    })
    if (!node) return false
    node.click()
    return true
  })()`)

const clickAttr = async (attr, value) =>
  evaluate(`(() => {
    const node = document.querySelector('[${attr}="${value}"]')
    if (!node) return false
    node.click()
    return true
  })()`)

// The route, not a reload: a reload drops the remote connection.
await evaluate("location.hash='#/'; 'ok'")
await wait(500)
await evaluate("location.hash='#/coursebook'; 'ok'")
await wait(2500)

// Home → Courses, then the demonstration course.
if (!(await evaluate("!!document.querySelector('[data-cb-course-detail]')"))) {
  if (!(await clickText('Courses'))) throw new Error('no Courses destination')
  await wait(1500)
}
if (!(await clickText('Home'))) throw new Error('no Home destination')
await wait(1800)
// "Open section" on the review card lands on section 1; go through Courses for a chosen stop.
if (!(await clickText('Courses'))) throw new Error('no Courses destination')
await wait(1800)
const opened = await evaluate(`(() => {
  const buttons = [...document.querySelectorAll('[data-cb-route] button')].filter((b) => b.offsetParent !== null)
  const row = buttons.find((b) => (b.innerText || '').trim() === 'Open')
  if (!row) return null
  row.click()
  return 'Open'
})()`)
if (!opened) {
  // The shelf may render plain buttons instead of a row container.
  const fallback = await clickText('Open')
  if (!fallback) throw new Error('the demonstration course was not on the shelf')
}
await wait(2500)
if (!(await clickText('Learn'))) throw new Error('no Learn tab on the course')
await wait(1500)
const stopClicked = await evaluate(`(() => {
  const node = [...document.querySelectorAll('[data-cb-route] button')].find((n) => /^${stop}\\b/.test((n.innerText || '').trim()))
  if (!node) return false
  node.click()
  return true
})()`)
if (!stopClicked) throw new Error(`stop ${stop} was not on the trail`)
await wait(3500)
const view = await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null")
if (view !== 'player') {
  const clicked = await clickAttr('data-cb-view-choice', 'player')
  if (!clicked) throw new Error('the Game view control was not on the section')
  await wait(2500)
}
// Walk the player's steps until the answer field is on screen.
for (let i = 0; i < 4; i += 1) {
  if (await evaluate("!!document.querySelector('#cb-attempt-answer')")) break
  const label = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-player-footer] button')
    if (!b || b.disabled) return null
    const text = (b.innerText || '').trim()
    b.click()
    return text
  })()`)
  if (!label) break
  await wait(1500)
}
const state = await evaluate(`(() => {
  const text = (n) => (n ? (n.innerText || '').replace(/\\s+/g, ' ').trim() : null)
  return {
    player: !!document.querySelector('[data-cb-player]'),
    view: document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null,
    bar: text(document.querySelector('[data-cb-player-bar]')),
    step: text(document.querySelector('[data-cb-player-step]')),
    footer: text(document.querySelector('[data-cb-player-footer]')),
    chip: document.querySelector('[data-cb-evidence-chip]')?.getAttribute('data-cb-evidence-chip') || null,
    chipPending: document.querySelector('[data-cb-evidence-chip]')?.getAttribute('data-cb-evidence-pending') || null,
    chipText: text(document.querySelector('[data-cb-evidence-chip]')),
    textarea: !!document.querySelector('#cb-attempt-answer'),
    assist: [...document.querySelectorAll('[data-cb-assist] button')].map((b) => b.innerText.trim()),
    detached: /no longer connected/i.test(text(document.querySelector('[data-cb-player]')) || ''),
    primary: text(document.querySelector('[data-cb-player-footer] button')),
    primaryDisabled: (document.querySelector('[data-cb-player-footer] button') || {}).disabled ?? null
  }
})()`)
console.log(JSON.stringify(state, null, 1))
