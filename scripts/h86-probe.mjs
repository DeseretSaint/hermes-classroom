#!/usr/bin/env node
/** Probe: reload the live window and report whether the H-86 module is the one rendered. */
const PORT = process.env.CB009_CDP_PORT || '9337'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
})
const call = (method, params = {}) => new Promise((res) => { const id = nextId++; pending.set(id, res); socket.send(JSON.stringify({ id, method, params })) })
const evaluate = async (expression) => (await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value
await call('Runtime.enable'); await call('Page.enable')
await call('Page.reload', { ignoreCache: true })
await new Promise((r) => setTimeout(r, 6000))
await evaluate("location.hash = '#/coursebook'")
await new Promise((r) => setTimeout(r, 3000))
const probe = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return JSON.stringify({
    route: !!route,
    navItems: document.querySelectorAll('[data-cb-nav-item]').length,
    navAria: [...document.querySelectorAll('[data-cb-nav-item]')].map((b) => (b.getAttribute('aria-current') || '-') + ':' + b.textContent.trim()),
    primaries: [...document.querySelectorAll('[data-cb-route] button')].filter((b) => b.dataset.variant === 'default').map((b) => b.textContent.trim()),
    startPlate: !!document.querySelector('[data-cb-first-run]'),
    moduleUrl: [...document.querySelectorAll('script')].map((s) => s.src).filter((s) => s.includes('plugin')).slice(-2)
  })
})()`)
console.log(probe)
socket.close()
