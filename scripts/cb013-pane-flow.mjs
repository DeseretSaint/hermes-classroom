#!/usr/bin/env node
/**
 * Drive ONE section from a detached pane to a graded outcome in the live window, capturing each
 * state. Unlike cb013-run-section.mjs it never needs the downstream user to read logs: it prints a
 * JSON line per phase and always writes the screenshot.
 *
 *   node scripts/cb013-pane-flow.mjs "<chat message>" "<answer>" "<shot prefix>" [sectionIndex]
 *
 * Phases: detached -> (fresh run + chat turn) -> bound/awaiting_input -> submitted -> one of
 * graded | needs_retry | overridden | stale.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const [chatMessage, answer, prefixArg, indexArg] = process.argv.slice(2)
const prefix = prefixArg || 'docs/cb013-shots/pane'
const sectionIndex = Number(indexArg ?? '0')

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
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const waitUntil = async (expression, label, timeoutMs = 30000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(400)
  }
  throw new Error('timeout: ' + label)
}
const clickText = (text) =>
  evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === ${JSON.stringify(text)}); if (!b) return 'missing'; b.click(); return 'clicked' })()`)
const shot = async (name) => {
  const path = resolve(`${prefix}-${name}.png`)
  const data = await send('Page.captureScreenshot', { format: 'png' })
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const paneState = () =>
  evaluate(`(() => {
    const t = document.body.innerText || ''
    const phases = []
    if (/chat binding is detached/.test(t)) phases.push('detached')
    if (/CURRENT CHECK/.test(t)) phases.push('check-open')
    if (/I couldn’t grade this attempt/.test(t)) phases.push('needs_retry')
    if (/Access granted — not independent evidence/.test(t)) phases.push('overridden')
    if (/Passed|Partly there|Not yet/.test(t) && /ATTEMPTS ON THIS SECTION/.test(t)) phases.push('graded')
    return {
      phases,
      disabled: (document.querySelector('#cb-attempt-answer') || {}).disabled,
      hasAnswerBox: !!document.querySelector('#cb-attempt-answer'),
      hash: location.hash,
      tail: t.slice(-900)
    }
  })()`)

await send('Page.enable')
await send('Runtime.enable')

// --- open the section page -------------------------------------------------
const openSection = async () => {
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(2000)
  await clickText('Open')
  await sleep(2000)
  if ((await clickText('All sections')) === 'missing') await sleep(500)
  await sleep(1500)
  const clicked = await evaluate(`(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.innerText.trim() === 'Open section')
    const b = buttons[${sectionIndex}]
    if (!b) return 'no-open-section'
    b.click()
    return 'clicked'
  })()`)
  if (clicked !== 'clicked') throw new Error('open section: ' + clicked)
  await waitUntil(`(() => { const t = document.body.innerText || ''; return /CURRENT CHECK/.test(t) || /binding is detached/.test(t) })()`, 'section pane')
  await sleep(800)
}

await openSection()
const start = await paneState()
console.log(JSON.stringify({ step: 'start', ...start, shot: await shot('detached') }))

// --- fresh run + one real chat turn ----------------------------------------
if (start.phases.includes('detached')) {
  if ((await clickText('Start a fresh run')) === 'missing') throw new Error('no Start a fresh run control')
  await waitUntil(`!!document.querySelector('[contenteditable="true"]')`, 'chat composer', 30000)
  await sleep(1200)
  await evaluate(`(() => { const el = document.querySelector('[contenteditable="true"]'); el.focus(); return true })()`)
  await send('Input.insertText', { text: chatMessage })
  await sleep(300)
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined })
  }
  console.log(JSON.stringify({ step: 'chat-sent' }))
  // One real turn. The shell keeps a "Waking up …" status label even after the assistant text
  // lands, so judge completion by the transcript going quiet instead of by that label.
  const deadline = Date.now() + 240000
  let previous = ''
  let stableSince = 0
  while (Date.now() < deadline) {
    const current = await evaluate(`(() => (document.body.innerText || '').length)()`)
    if (current === previous) {
      if (!stableSince) stableSince = Date.now()
      if (Date.now() - stableSince > 8000) break
    } else {
      stableSince = 0
      previous = current
    }
    await sleep(1000)
  }
  await sleep(2000)
  await shot('chat-turn')
  await openSection()
}

const bound = await paneState()
console.log(JSON.stringify({ step: 'after-bind', ...bound, shot: await shot('awaiting-input') }))
if (!bound.hasAnswerBox || bound.disabled === true) {
  console.log(JSON.stringify({ step: 'stop', reason: 'pane not bindable in this state' }))
  socket.close()
  process.exit(0)
}

// --- submit the answer -----------------------------------------------------
await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.focus(); return true })()`)
await send('Input.insertText', { text: answer })
await sleep(400)
console.log(JSON.stringify({ step: 'submit', result: await clickText('Submit answer') }))

const started = Date.now()
let last = null
while (Date.now() - started < 60000) {
  last = await paneState()
  if (last.phases.some((p) => ['needs_retry', 'overridden', 'graded', 'stale'].includes(p))) break
  await sleep(500)
}
const verdict = await paneState()
console.log(JSON.stringify({ step: 'verdict', ...verdict, shot: await shot('verdict') }))

// Report any override / move-on controls so the next step can reach `overridden` deliberately.
const controls = await evaluate(`(() => [...document.querySelectorAll('button')].map(b => b.innerText.trim()).filter(t => t && /move on|override|continue anyway|accept anyway|not independent/i.test(t)))()`)
console.log(JSON.stringify({ step: 'controls', controls }))
socket.close()
