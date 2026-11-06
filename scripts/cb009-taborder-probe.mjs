#!/usr/bin/env node
/** Probe: print the first N Tab stops and N Shift+Tab stops from document.body. */
const PORT = process.env.CB009_CDP_PORT || '9222'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { socket.addEventListener('open', res, { once: true }); socket.addEventListener('error', rej, { once: true }) })
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) { const { resolve: r, reject } = pending.get(m.id); pending.delete(m.id); m.error ? reject(new Error(JSON.stringify(m.error))) : r(m.result) }
})
const send = (method, params = {}) => new Promise((resolve, reject) => { const id = nextId++; pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })) })
const evaluate = async (expression) => { const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description); return r.result?.value }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const tab = async (shift = false) => {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9, modifiers: shift ? 8 : 0 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9, modifiers: shift ? 8 : 0 })
  await sleep(30)
}
const info = () => evaluate(`(() => { const a = document.activeElement; if (!a || a === document.body) return 'BODY'; return ((a.getAttribute('aria-label') || (a.innerText||'').trim().replace(/\\s+/g,' ').slice(0,40) || a.tagName)) })()`)
await evaluate(`(() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); return 1 })()`)
const forward = []
for (let i = 0; i < 12; i++) { await tab(); forward.push(await info()) }
await evaluate(`(() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); return 1 })()`)
const backward = []
for (let i = 0; i < 6; i++) { await tab(true); backward.push(await info()) }
console.log(JSON.stringify({ forward, backward, viewport: await evaluate('innerWidth') }, null, 2))
socket.close()
