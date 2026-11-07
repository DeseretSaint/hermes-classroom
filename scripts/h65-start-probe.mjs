#!/usr/bin/env node
/** H-65 live probe: list the Coursebook route's controls, then start/resume the current lesson. */
const PORT = process.env.CB013_CDP_PORT || '9337'
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
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1200)
const text = await evaluate(`document.body.innerText.slice(0, 2500)`)
const buttons = await evaluate(`[...document.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean).slice(0, 60)`)
console.log(JSON.stringify({ text, buttons }, null, 2))
const clicked = await evaluate(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => /Go to the current lesson|Start a fresh run|Open this section|Start lesson/i.test(x.innerText || ''))
  if (!b) return 'missing'
  b.click(); return b.innerText.trim()
})()`)
await sleep(4000)
const after = await evaluate(`(() => {
  const skill = document.querySelector('[data-cb-skill]')
  const t = document.body.innerText || ''
  return {
    clicked: ${JSON.stringify(clicked)},
    hash: location.hash,
    skill: skill ? skill.getAttribute('data-cb-skill') : null,
    skillReason: skill ? skill.getAttribute('data-cb-skill-reason') : null,
    skillText: skill ? skill.innerText : null,
    bindingId: document.querySelector('[data-cb-binding-id]')?.getAttribute('data-cb-binding-id') || '',
    storedId: document.querySelector('[data-cb-stored-id]')?.getAttribute('data-cb-stored-id') || '',
    note: (t.match(/A governed run[^\\n]*/g) || []).slice(-2),
    head: t.slice(0, 600)
  }
})()`)
console.log(JSON.stringify(after, null, 2))
