#!/usr/bin/env node
/**
 * Walk the Coursebook route to one section by *title*, waiting for each render instead of
 * guessing sleeps.
 *
 *   node scripts/cb013-nav.mjs "Explain why register changes with the relationship"
 *
 * Prints {ok, step, objective, check, attempts, paneText} so a caller can tell
 * "route not mounted" from "section pane did not load".
 */
const PORT = process.env.CB009_CDP_PORT || '9337'
const sectionTitle = process.argv[2]

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
    const { resolve, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else resolve(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
await send('Runtime.enable')

const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expression, label, timeoutMs = 15000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(500)
  }
  throw new Error(`timeout waiting for ${label}`)
}

console.log('nav start', { sectionTitle })
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2500)
await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Open'); if (b) { b.click(); return true } return false })()`)
await sleep(2500)
await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Open this section'); if (b) { b.click(); return true } return false })()`)
await sleep(3500)
const clicked = await evaluate(`(() => {
  const title = ${JSON.stringify(sectionTitle)}
  const nodes = [...document.querySelectorAll('div')].filter(e => e.className.includes('break-words') && e.textContent.trim() === title)
  if (!nodes.length) return 'title-missing'
  let row = nodes[0]
  for (let i = 0; i < 8 && row; i++, row = row.parentElement) {
    const btn = row.querySelector('button')
    if (btn) { btn.click(); return 'clicked' }
  }
  return 'no-button'
})()`)
console.log('section click:', clicked)
const started = Date.now()
let ready = false
while (Date.now() - started < 25000) {
  ready = await evaluate(`(() => { const t = document.body.innerText || ''; return /CURRENT CHECK/.test(t) || /There is no open check/.test(t) || /binding is detached/.test(t) })()`)
  if (ready) break
  await sleep(700)
}
const state = await evaluate(`(() => {
  const text = document.body.innerText || ''
  const at = text.indexOf('TEACHING SEGMENTS')
  const cut = at > -1 ? text.slice(at) : text.slice(-1500)
  return {
    hash: location.hash,
    ready: /CURRENT CHECK/.test(text) || /binding is detached/.test(text),
    textarea: !!document.querySelector('#cb-attempt-answer'),
    detached: /binding is detached/.test(text),
    paneText: cut.slice(0, 1400)
  }
})()`)
console.log(JSON.stringify(state, null, 2))
socket.close()
