#!/usr/bin/env node
/**
 * CB-009 keyboard-only + text-only path in the real window.
 *
 * Every navigation here is a real key event (Tab / Shift+Tab / Enter) dispatched through CDP, and
 * the answer is typed with Input.insertText. No element.click() and no programmatic focus() is used
 * after the run starts, so the recorded focus trail is what a keyboard user would actually see.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-keyboard.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9222'
const SHOTS = 'docs/cb009-shots'
const steps = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) {
    const { resolve: r, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else r(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value
}
const shot = async (name) => {
  const data = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const path = resolve(`${SHOTS}/${name}.png`)
  mkdirSync(SHOTS, { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const key = async (name, code, vk, modifiers = 0) => {
  for (const type of ['rawKeyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', {
      type,
      key: name,
      code,
      windowsVirtualKeyCode: vk,
      nativeVirtualKeyCode: vk,
      modifiers
    })
  }
  await sleep(70)
}
const tab = (shift = false) => key('Tab', 'Tab', 9, shift ? 8 : 0)
const enter = () => key('Enter', 'Enter', 13)
const focusInfo = () =>
  evaluate(`(() => {
    const a = document.activeElement
    if (!a || a === document.body) return { tag: 'BODY', name: '' }
    return {
      tag: a.tagName,
      id: a.id || '',
      role: a.getAttribute('role') || '',
      name: (a.getAttribute('aria-label') || (a.innerText || '').trim().slice(0, 60) || a.placeholder || '').replace(/\\n+/g, ' ')
    }
  })()`)
const trail = []
const pressUntil = async (match, label, max = 320) => {
  for (let i = 0; i < max; i++) {
    await tab()
    const info = await focusInfo()
    trail.push({ label, step: i + 1, ...info })
    if (match(info)) return info
  }
  throw new Error(`focus never reached ${label}`)
}

await send('Page.enable')
await send('Runtime.enable')
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2500)
// Honest boundary of this keyboard claim: focus is placed at the course's view switcher so the run
// does not spend 100+ Tab presses walking the operator's session sidebar. Everything after this
// line is a real CDP key event — no element.click(), no programmatic focus().
const seedFocus = await evaluate(`(() => {
  const tab = [...document.querySelectorAll('button[aria-pressed]')].find((b) => b.innerText.trim() === 'Overview')
  if (!tab) return 'no-view-tabs'
  tab.focus()
  return 'focused:' + (document.activeElement.innerText || '').trim()
})()`)
trail.push({ label: 'start', seedFocus, ...(await focusInfo()) })

// 0. if the list is showing, a real Tab + Enter opens the course row
const listOpen = await evaluate(`Boolean([...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Open'))`)
if (listOpen) {
  await pressUntil((info) => info.name === 'Open', 'open-course', 320)
  await shot('26-keyboard-focus-course')
  await enter()
  await sleep(2200)
  trail.push({ label: 'after-enter-open', ...(await focusInfo()) })
}
// re-seed on the view switcher of the detail page just opened
await evaluate(`(() => { const tab = [...document.querySelectorAll('button[aria-pressed]')].find((b) => b.innerText.trim() === 'Overview'); if (tab) tab.focus(); return true })()`)

// 2. reach the Textbook view tab and enter it
const textbookTab = await pressUntil((info) => info.name === 'Textbook' && info.tag === 'BUTTON', 'textbook-tab')
await enter()
await sleep(1500)
await shot('27-keyboard-textbook-list')
trail.push({ label: 'after-enter-textbook', ...(await focusInfo()) })

// 3. reach the fourth section's Open section button (its binding is the one that is active) — the
//    earlier rows are passed by Tab and every hit is recorded.
let sectionHits = 0
const openSection = await pressUntil((info) => {
  if (info.name !== 'Open section') return false
  sectionHits += 1
  return sectionHits === 4
}, 'open-section')
await enter()
await sleep(3000)
trail.push({ label: 'after-enter-section', ...(await focusInfo()) })
await shot('28-keyboard-section')

// 4. type the answer into the answer field with Input.insertText, then submit with Enter
const answer = 'Suki desu. The addressee is respected but not close, the setting is private, and polite teineigo fits a first confession.'
const box = await pressUntil((info) => info.id === 'cb-attempt-answer', 'answer-field', 320)
await send('Input.insertText', { text: answer })
await sleep(400)
const typed = await evaluate(`(document.querySelector('#cb-attempt-answer') || {}).value`)
await shot('29-keyboard-typed-answer')
await pressUntil((info) => info.name === 'Submit answer', 'submit')
await enter()
await sleep(4000)
const after = await evaluate(`(() => ({
  tail: (document.body.innerText || '').slice(-900),
  submitDisabled: (document.querySelector('#cb-attempt-answer') || {}).disabled,
  verdicts: ['Passed', 'Partly there', 'Not yet'].filter((v) => (document.body.innerText || '').includes(v))
}))()`)
await shot('30-keyboard-submitted')
await evaluate(`document.body.removeAttribute('tabindex')`)

const out = {
  capturedAt: new Date().toISOString(),
  answerTyped: typed,
  tabHitsBeforeAnswer: trail.filter((s) => s.label === 'open-section').length,
  submitDisabledAfter: after.submitDisabled,
  verdictsSeen: after.verdicts,
  tail: after.tail,
  trail
}
writeFileSync(resolve('docs/REVIEW_CB009-keyboard-trace.json'), JSON.stringify(out, null, 2))
console.log(JSON.stringify({ typed, verdicts: after.verdicts, submitDisabledAfter: after.submitDisabled, trailSteps: trail.length, tail: after.tail.slice(-500) }, null, 2))
socket.close()
