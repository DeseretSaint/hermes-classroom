#!/usr/bin/env node
/**
 * CB-009 keyboard-only path, starting from the shell with NO programmatic focus.
 *
 * Every step is a real CDP key event (Tab / Shift+Tab / Enter) and the answer is typed with
 * Input.insertText. Nothing is focused with .focus() and nothing is clicked with .click().
 * The run deliberately walks the real Tab order from document.body, including the session sidebar,
 * because that is what a keyboard user actually meets first.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-keyboard.mjs [maxTabs]
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9222'
const MAX_TABS = Number(process.argv[2] ?? '420')
const SHOTS = 'docs/cb009-shots'
const ANSWER =
  process.env.CB009_ANSWER ||
  'The addressee is someone I respect but am not close to, and the setting is private, so polite teineigo fits; the same words to a close friend in public would switch to plain casual form.'

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
  const path = resolve(`${SHOTS}/${name}.png`)
  const data = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(SHOTS, { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const key = async (name, code, vk, modifiers = 0, text) => {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: name, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers, ...(text ? { text } : {}) })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: name, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers })
  await sleep(35)
}
const tab = (shift = false) => key('Tab', 'Tab', 9, shift ? 8 : 0)
const enter = async () => {
  // a rawKeyDown alone does not run a button's default activation in Chromium; the text-bearing
  // keyDown is what a real keyboard sends when Enter activates a focused control
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: '\r' })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
  await sleep(60)
}
const space = () => key(' ', 'Space', 32, 0, ' ')
const focusInfo = () =>
  evaluate(`(() => {
    const a = document.activeElement
    if (!a || a === document.body) return { tag: 'BODY', name: '', id: '', role: '' }
    const name = (a.getAttribute('aria-label') || (a.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 70) || a.placeholder || a.value || '')
    return { tag: a.tagName, id: a.id || '', role: a.getAttribute('role') || '', name }
  })()`)

await send('Page.enable')
await send('Runtime.enable')
const trace = { startedAt: new Date().toISOString(), steps: [], shots: [] }
const record = async (label, extra = {}) => {
  const info = await focusInfo()
  trace.steps.push({ label, ...info, ...extra })
  return info
}
/** Tab until the predicate matches, recording every stop. */
const tabUntil = async (predicate, label, max = MAX_TABS) => {
  for (let i = 0; i < max; i++) {
    await tab()
    const info = await focusInfo()
    trace.steps.push({ label, step: i + 1, ...info })
    if (predicate(info)) return { info, presses: i + 1 }
  }
  throw new Error(`focus never reached ${label} within ${max} Tabs`)
}

// start from nothing: blur whatever the last session left focused, without focusing anything new
await evaluate(`(() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); return document.activeElement.tagName })()`)
await evaluate(`location.hash = '#/'`)
await sleep(1200)
await record('start')

// 1. the shell's own Tab order, from the very beginning: reach the Coursebook nav entry
const nav = await tabUntil((info) => info.name === 'Coursebook', 'nav-coursebook', 120)
trace.steps.push({ label: 'nav-found', presses: nav.presses })
await enter()
await sleep(2600)
const routeHash = await evaluate(`location.hash`)
trace.steps.push({ label: 'route-hash', hash: routeHash })
if (!/coursebook/.test(routeHash)) throw new Error('Enter on the Coursebook nav did not open the route: ' + routeHash)
await record('route-open')
await shot('31-keyboard-route')

// 2. the route list: open the course
const openCourse = await tabUntil((info) => info.name === 'Open' && info.tag === 'BUTTON', 'open-course', 700)
trace.steps.push({ label: 'course-found', presses: openCourse.presses })
await enter()
await sleep(2400)
await record('course-open')
await shot('32-keyboard-course')

// 3. the course detail: Textbook view. With the context pane open the route is narrower than
//    47.5rem, so the canonical tab strip is display:none and the labelled Select is the control —
//    a keyboard user opens it with Enter and moves with the arrow keys.
const textbookVisible = await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Textbook'); return b ? b.getBoundingClientRect().width > 0 : false })()`)
if (textbookVisible) {
  const textbook = await tabUntil((info) => info.name === 'Textbook' && info.tag === 'BUTTON', 'textbook', 700)
  trace.steps.push({ label: 'textbook-found', presses: textbook.presses })
  await enter()
} else {
  const picker = await tabUntil((info) => info.name === 'Course view', 'view-picker', 700)
  trace.steps.push({ label: 'view-picker-found', presses: picker.presses })
  await enter()
  await sleep(600)
  const options = await evaluate(`[...document.querySelectorAll('[role="option"]')].map((o) => (o.innerText || '').trim())`)
  trace.steps.push({ label: 'view-menu', options })
  if (!options.includes('Textbook')) throw new Error('the view picker did not open: ' + JSON.stringify(options))
  const index = options.indexOf('Textbook')
  for (let i = 0; i < index; i++) await key('ArrowDown', 'ArrowDown', 40)
  await enter()
}
await sleep(1800)
await record('textbook-open')
if (!(await evaluate(`/Open section/.test(document.body.innerText)`))) throw new Error('Textbook view did not render section rows')

// 4. the first section row
const section = await tabUntil((info) => info.name === 'Open section', 'open-section', 320)
trace.steps.push({ label: 'section-found', presses: section.presses })
await enter()
await sleep(3200)
await record('section-open')
await shot('33-keyboard-section')

// 4b. a committed check is locked until "Edit answer"; a keyboard user unlocks it the same way
const locked = await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); return el ? el.disabled : null })()`)
if (locked) {
  const edit = await tabUntil((info) => info.name === 'Edit answer', 'edit-answer', 320)
  trace.steps.push({ label: 'edit-found', presses: edit.presses })
  await enter()
  await sleep(1800)
  await record('edit-answer')
}

// 4. the answer field, typed with real inserted text
const field = await tabUntil((info) => info.id === 'cb-attempt-answer', 'answer-field', 220)
trace.steps.push({ label: 'answer-found', presses: field.presses })
await send('Input.insertText', { text: ANSWER })
await sleep(350)
const typed = await evaluate(`(document.querySelector('#cb-attempt-answer') || {}).value`)
await record('answer-typed', { typed })
await shot('33-keyboard-answer-typed')

// 5. Submit, with Enter on the focused button
const submit = await tabUntil((info) => info.name === 'Submit answer', 'submit', 80)
trace.steps.push({ label: 'submit-found', presses: submit.presses })
const submitDisabled = await evaluate(`(() => { const b = document.activeElement; return b ? b.disabled : null })()`)
await enter()
await sleep(4500)
const after = await evaluate(`(() => {
  const t = document.body.innerText || ''
  return {
    verdicts: ['Passed', 'Partly there', 'Not yet', 'Needs review', 'Hinted', 'I couldn’t grade this attempt'].filter((v) => t.includes(v)),
    keyboardFocus: document.activeElement ? (document.activeElement.innerText || document.activeElement.tagName).slice(0, 60) : null,
    stillOnSection: /CURRENT CHECK/.test(t)
  }
})()`)
await record('after-submit', after)
await shot('34-keyboard-submitted')

// 6. text-only audit: controls inside the plugin without any text or accessible name
const names = await evaluate(`(() => {
  const scope = [...document.querySelectorAll('button, [role="button"], input, textarea, select')]
    .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 })
  const unnamed = scope.filter((e) => !((e.getAttribute('aria-label') || '').trim() || (e.innerText || '').trim() || (e.getAttribute('placeholder') || '').trim() || (e.getAttribute('title') || '').trim()))
  return {
    total: scope.length,
    unnamed: unnamed.length,
    unnamedSamples: unnamed.slice(0, 6).map((e) => ({ tag: e.tagName, slot: e.getAttribute('data-slot'), cls: String(e.className).slice(0, 50) }))
  }
})()`)

const out = { ...trace, typed, submitDisabled, after, textOnlyAudit: names }
writeFileSync(resolve('docs/REVIEW_CB009-keyboard-trace.json'), JSON.stringify(out, null, 2))
console.log(JSON.stringify({ typed: (typed || '').slice(0, 60), submitDisabled, verdicts: after.verdicts, navPresses: nav.presses, totalFocusStops: trace.steps.length, textOnlyAudit: names }, null, 2))
socket.close()
