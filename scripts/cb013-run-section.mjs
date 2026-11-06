#!/usr/bin/env node
/**
 * Advance one Coursebook section in the live window and capture the state the pane lands in.
 *
 *   node scripts/cb013-run-section.mjs "<section title>" "<chat message>" "<answer>" <shot path>
 *
 * Steps, each waiting for the render it depends on:
 *   pane -> Start a fresh run -> chat turn (real model) -> back to the pane -> submit -> screenshot.
 * The chat turn is what gives the fresh chat its durable stored id, so the binding seam can bind
 * it; without it the pane stays "detached" and Submit is disabled by design.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const [sectionTitle, chatMessage, answer, shotArg] = process.argv.slice(2)
const shotPath = resolve(shotArg || 'docs/cb013-shots/pane-section.png')

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
const waitUntil = async (expression, label, timeoutMs = 20000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(400)
  }
  throw new Error('timeout: ' + label)
}
const clickText = (text) =>
  evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === ${JSON.stringify(text)}); if (!b) return 'missing'; b.click(); return 'clicked' })()`)

await send('Page.enable')
await send('Runtime.enable')

const openSection = async () => {
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(2200)
  await clickText('Open')
  await sleep(2200)
  const opened = await clickText('Open section')
  if (opened === 'missing') {
    const all = await clickText('All sections')
    if (all === 'missing') throw new Error('cannot reach the textbook list')
    await sleep(1800)
  }
  await sleep(2600)
  const clicked = await evaluate(`(() => {
    const nodes = [...document.querySelectorAll('div')].filter(e => e.className.includes('break-words') && e.textContent.trim() === ${JSON.stringify(sectionTitle)})
    if (!nodes.length) return 'title-missing'
    let row = nodes[0]
    for (let i = 0; i < 8 && row; i++, row = row.parentElement) {
      const b = row.querySelector('button')
      if (b) { b.click(); return 'clicked' }
    }
    return 'no-button'
  })()`)
  if (clicked !== 'clicked') throw new Error('section row: ' + clicked)
  await waitUntil(`(() => { const t = document.body.innerText || ''; return /CURRENT CHECK/.test(t) || /binding is detached/.test(t) })()`, 'pane ready')
  await sleep(1200)
}

await openSection()
const before = await evaluate(`(() => ({ detached: /binding is detached/.test(document.body.innerText || ''), disabled: (document.querySelector('#cb-attempt-answer') || {}).disabled }))()`)
console.log('pane:', before)

if (before.detached) {
  const armed = await clickText('Start a fresh run')
  console.log('fresh run:', armed)
  await waitUntil(`!!document.querySelector('[contenteditable="true"]')`, 'chat composer')
  await sleep(1500)
  await evaluate(`(() => { const el = document.querySelector('[contenteditable="true"]'); el.focus(); return true })()`)
  await send('Input.insertText', { text: chatMessage })
  await sleep(300)
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined })
  }
  console.log('chat message sent')
  // Wait for the turn to finish: the waking indicator disappears and the transcript stops growing.
  await waitUntil(`(() => { const t = document.body.innerText || ''; return !/Waking up/.test(t) && (t.match(/AM|PM/g) || []).length > 0 })()`, 'chat turn', 120000)
  await sleep(2500)
  await openSection()
}

const ready = await evaluate(`(() => ({ detached: /binding is detached/.test(document.body.innerText || ''), disabled: (document.querySelector('#cb-attempt-answer') || {}).disabled }))()`)
console.log('pane after bind:', ready)
if (ready.detached || ready.disabled === undefined) {
  console.log('NOT bound; stopping before submit')
  socket.close()
  process.exit(0)
}

await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.focus(); return true })()`)
await send('Input.insertText', { text: answer })
await sleep(300)
console.log('submit:', await clickText('Submit answer'))

const phase = await (async () => {
  const started = Date.now()
  let seen = 'waiting'
  while (Date.now() - started < 40000) {
    seen = await evaluate(`(() => {
      const t = document.body.innerText || ''
      if (/I couldn’t grade this attempt/.test(t)) return 'needs_retry'
      if (/Access granted — not independent evidence/.test(t)) return 'overridden'
      if (/This check moved on while you were answering/.test(t)) return 'stale'
      if (/Answer locked\\. No second attempt/.test(t)) return 'submitting'
      if (/ATTEMPTS ON THIS SECTION/.test(t) && /Passed|Partly there|Not yet/.test(t)) return 'graded'
      return 'waiting'
    })()`)
    if (seen !== 'waiting' && seen !== 'submitting') break
    await sleep(250)
  }
  return seen
})()
const shot = await send('Page.captureScreenshot', { format: 'png' })
mkdirSync(dirname(shotPath), { recursive: true })
writeFileSync(shotPath, Buffer.from(shot.data, 'base64'))
const text = await evaluate(`(() => { const t = document.body.innerText || ''; const at = Math.max(0, t.indexOf('CURRENT CHECK')); return t.slice(at, at + 1100) })()`)
console.log(JSON.stringify({ phase, shot: shotPath, text }, null, 2))
socket.close()
