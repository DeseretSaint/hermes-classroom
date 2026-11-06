#!/usr/bin/env node
/**
 * Submit one answer from the pane and capture the state it lands in.
 *
 *   node scripts/cb013-submit.mjs "suki desu" docs/cb013-shots/05b-pane-graded.png [waitMs]
 *
 * Types into #cb-attempt-answer with real CDP input, clicks Submit answer, waits for the pane to
 * leave the submitting phase, screenshots, and prints the pane text that names the verdict — so
 * a transient state is captured at the moment it exists instead of being guessed at afterwards.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const text = process.argv[2]
const shotPath = resolve(process.argv[3] || 'docs/cb013-shots/pane-submit.png')
const waitMs = Number(process.argv[4] || 2500)

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
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

await send('Page.enable')
await send('Runtime.enable')
const focused = await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); if (!el) return 'missing'; el.focus(); return el.disabled ? 'disabled' : 'focused' })()`)
console.log('textarea:', focused)
if (focused !== 'focused') process.exit(3)
await send('Input.insertText', { text })
await sleep(300)
console.log('click:', await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Submit answer'); if (!b || b.disabled) return 'unavailable'; b.click(); return 'clicked' })()`))

const started = Date.now()
let phase = 'unknown'
while (Date.now() - started < 30000) {
  phase = await evaluate(`(() => {
    const t = document.body.innerText || ''
    if (/I couldn’t grade this attempt/.test(t)) return 'needs_retry'
    if (/Access granted — not independent evidence/.test(t)) return 'overridden'
    if (/This check moved on while you were answering/.test(t)) return 'stale'
    if (/Answer locked\\. No second attempt/.test(t)) return 'submitting'
    if (/^Passed$|^Partly there$|^Not yet$/m.test(t) && /ATTEMPTS ON THIS SECTION/.test(t)) return 'graded'
    return 'waiting'
  })()`)
  if (phase !== 'waiting' && phase !== 'submitting') break
  await sleep(250)
}
await sleep(waitMs)
const state = await evaluate(`(() => {
  const t = document.body.innerText || ''
  const at = Math.max(0, t.indexOf('CURRENT CHECK'))
  return { phase: ${JSON.stringify(phase)}, text: t.slice(at, at + 1200) }
})()`)
const shot = await send('Page.captureScreenshot', { format: 'png' })
mkdirSync(dirname(shotPath), { recursive: true })
writeFileSync(shotPath, Buffer.from(shot.data, 'base64'))
console.log(JSON.stringify({ phase: state.phase, shot: shotPath, text: state.text }, null, 2))
socket.close()
