#!/usr/bin/env node
/**
 * H-65 live turn: open the bound L0 lesson chat, send ONE lesson-shaped prompt, read the reply.
 *   node scripts/h65-live-turn.mjs 20261106_095109_eac24e
 */
const PORT = process.env.CB013_CDP_PORT || '9337'
const STORED = process.argv[2] || '20261106_095109_eac24e'
const MESSAGE = process.env.CB013_CHAT_MESSAGE || 'I want to try this section. What am I practising, and what should I send?'
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
await evaluate(`location.hash = '#/${STORED}'`)
await sleep(3000)
const before = await evaluate(`(() => {
  const skill = document.querySelector('[data-cb-skill]')
  return {
    hash: location.hash,
    skill: skill ? skill.getAttribute('data-cb-skill') : null,
    skillText: skill ? skill.innerText : null,
    bindingId: document.querySelector('[data-cb-binding-id]')?.getAttribute('data-cb-binding-id') || '',
    storedId: document.querySelector('[data-cb-stored-id]')?.getAttribute('data-cb-stored-id') || ''
  }
})()`)
const focused = await evaluate(`(() => {
  const el = document.querySelector('textarea, [contenteditable="true"]')
  if (!el) return 'no-composer'
  el.focus()
  return el.tagName
})()`)
await send('Input.insertText', { text: MESSAGE })
await sleep(400)
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
const started = Date.now()
let last = ''
while (Date.now() - started < 180000) {
  last = await evaluate(`document.body.innerText`)
  if (/skill_view|coursebook:lesson-tutoring/.test(last) && last.length > 500) break
  await sleep(3000)
}
await sleep(3000)
const transcript = await evaluate(`(() => {
  const t = document.body.innerText || ''
  const i = t.indexOf(${JSON.stringify(MESSAGE.slice(0, 24))})
  return i >= 0 ? t.slice(i, i + 3000) : t.slice(-3000)
})()`)
console.log(JSON.stringify({ before, focused, transcript }, null, 2))
