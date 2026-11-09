#!/usr/bin/env node
/** H-202: open the demonstration course via the shelf search, then reach stop 02's player. */
import { connect } from './h149-cdp.mjs'

const port = process.env.CB009_CDP_PORT || '9385'
const { evaluate, wait } = await connect(port)

const setValue = async (selector, value) => evaluate(`(() => {
  const el = document.querySelector(${JSON.stringify(selector)})
  if (!el) return false
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(el, ${JSON.stringify(value)})
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
  return true
})()`)

await evaluate("location.hash='#/'; 'ok'")
await wait(600)
await evaluate("location.hash='#/coursebook'; 'ok'")
await wait(2500)
await evaluate(`(() => { const b = document.querySelector('[data-cb-nav-item="courses"]'); if (b) b.click(); return true })()`)
await wait(1800)

const searched = await setValue('input[aria-label="Search courses"]', 'demonstration')
console.log('search set:', searched)
await wait(1500)

const shelf = await evaluate(`(() => {
  const t = (document.querySelector('[data-cb-route]') || {}).innerText || ''
  return t.replace(/\\s+/g, ' ').slice(0, 400)
})()`)
console.log('shelf now:', shelf)

const opened = await evaluate(`(() => {
  const btns = [...document.querySelectorAll('[data-cb-route] button')]
    .filter((b) => b.offsetParent !== null && /^(Open|Continue)$/.test((b.innerText || '').trim()))
  if (btns.length === 1) { btns[0].click(); return { ok: true, n: 1 } }
  return { ok: false, n: btns.length }
})()`)
console.log('open:', JSON.stringify(opened))
if (!opened.ok) throw new Error('shelf did not narrow to one card')
await wait(3000)

const detail = await evaluate(`(() => {
  const t = (document.querySelector('[data-cb-route]') || {}).innerText || ''
  return {
    title: (t.match(/All courses\\n([^\\n]+)/) || [])[1] || null,
    hasLearn: !!document.querySelector('[data-cb-tab="learn"]'),
    head: t.replace(/\\s+/g, ' ').slice(0, 260)
  }
})()`)
console.log('detail:', JSON.stringify(detail))
if (!(detail.title || '').includes('demonstration classroom')) throw new Error('wrong course: ' + JSON.stringify(detail))

await evaluate(`(() => { const b = document.querySelector('[data-cb-tab="learn"]'); if (!b) return false; b.click(); return true })()`)
await wait(2000)

const stops = await evaluate(`(() => {
  return [...document.querySelectorAll('[data-cb-route] button')].map((b) => (b.innerText || '').replace(/\\s+/g, ' ').trim()).filter((x) => /^0\\d\\b/.test(x))
})()`)
console.log('stops:', JSON.stringify(stops))

const stopClicked = await evaluate(`(() => {
  const node = [...document.querySelectorAll('[data-cb-route] button')]
    .find((n) => /^02\\b/.test((n.innerText || '').trim()))
  if (!node) return false
  node.click(); return true
})()`)
if (!stopClicked) throw new Error('stop 02 not on the trail')
await wait(3500)

const view = await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null")
if (view !== 'player') {
  await evaluate(`(() => { const b = document.querySelector('[data-cb-view-choice="player"]'); if (!b) return false; b.click(); return true })()`)
  await wait(2500)
}

for (let i = 0; i < 5; i += 1) {
  if (await evaluate("!!document.querySelector('#cb-attempt-answer')")) break
  const label = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-player-footer] button')
    if (!b || b.disabled) return null
    b.click(); return (b.innerText || '').trim()
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
    primaryDisabled: (document.querySelector('[data-cb-player-footer] button') || {}).disabled ?? null,
    width: innerWidth, rootFont: getComputedStyle(document.documentElement).fontSize
  }
})()`)
console.log('STATE ' + JSON.stringify(state, null, 1))
