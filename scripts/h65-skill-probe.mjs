#!/usr/bin/env node
/**
 * H-65 live check: a lesson chat is bound BEFORE its first turn and the pane names the skill.
 *
 *   node scripts/h65-skill-probe.mjs
 *
 * Drives the real window over CDP: open Coursebook, open a course, start the fresh run, wait for
 * the chat to exist, and read (a) the pane's skill line and (b) whether the chat is bound before
 * any message was typed. The one lesson-shaped prompt is sent by a separate call so this probe
 * stays cheap when only the wiring is under test.
 */
const PORT = process.env.CB013_CDP_PORT || '9337'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')
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
const waitUntil = async (expression, label, timeoutMs = 40000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(500)
  }
  throw new Error('timeout: ' + label)
}
const clickText = (text) =>
  evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === ${JSON.stringify(text)}); if (!b) return 'missing'; b.click(); return 'clicked' })()`)

await evaluate(`location.hash = '#/coursebook'`)
await sleep(1500)
const route = await evaluate(`location.hash`)
const buttons = await evaluate(`[...document.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean).slice(0, 40)`)

// Open the first course row.
const opened = await evaluate(`(() => {
  const row = [...document.querySelectorAll('[role="button"], button, a')].find(el => /Open course|Continue/.test(el.innerText || ''))
  if (!row) return 'missing'
  row.click(); return 'clicked'
})()`)
await sleep(2500)
console.log(JSON.stringify({ route, opened, buttons }, null, 2))
const started = await clickText('Start a fresh run')
await sleep(1500)
let startNote = await evaluate(`document.body.innerText.match(/A governed run[^\\n]*/)?.[0] || null`)
if (startNote === null) {
  const alt = await evaluate(`[...document.querySelectorAll('button')].map(b => b.innerText.trim()).filter(t => /start|lesson/i.test(t))`)
  console.log(JSON.stringify({ started, startNote, alt }))
} else {
  console.log(JSON.stringify({ started, startNote }))
}
await sleep(3000)
const state = await evaluate(`(() => {
  const skill = document.querySelector('[data-cb-skill]')
  const t = document.body.innerText || ''
  return {
    hash: location.hash,
    skill: skill ? skill.getAttribute('data-cb-skill') : null,
    skillReason: skill ? skill.getAttribute('data-cb-skill-reason') : null,
    skillText: skill ? skill.innerText : null,
    bindingId: document.querySelector('[data-cb-binding-id]')?.getAttribute('data-cb-binding-id') || '',
    storedId: document.querySelector('[data-cb-stored-id]')?.getAttribute('data-cb-stored-id') || '',
    paneBound: /COURSEBOOK/.test(t) && !/No durable chat yet/.test(t) && !/Not a Coursebook lesson/.test(t),
    notLesson: /Not a Coursebook lesson/.test(t)
  }
})()`)
console.log(JSON.stringify({ state }, null, 2))
