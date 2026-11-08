#!/usr/bin/env node
/** H-146b: full-viewport capture at 2x plus the focused tab's viewport rect, for a pixel probe. */
import { writeFileSync } from 'node:fs'
const PORT = process.env.CB009_CDP_PORT || '9364'
const OUT = process.argv[2] || 'docs/h146-shots/focus-ring-frame.png'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { socket.addEventListener('open', res, { once: true }); socket.addEventListener('error', rej, { once: true }) })
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) { const { resolve, reject } = pending.get(m.id); pending.delete(m.id); m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result) }
})
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = nextId++
  pending.set(id, { resolve: res, reject: rej })
  socket.send(JSON.stringify({ id, method, params }))
  setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error(`timeout ${method}`)) } }, 20000)
})
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}
await send('Runtime.enable'); await send('Page.enable')
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/'`); await new Promise((r) => setTimeout(r, 300))
await evaluate(`location.hash = '#/coursebook'`); await new Promise((r) => setTimeout(r, 1600))
await evaluate(`(() => { const route = document.querySelector('[data-cb-route]'); const skip = route.querySelector('a[href],button:not([disabled])'); skip.focus(); return true })()`)
const pressTab = async () => {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await new Promise((r) => setTimeout(r, 140))
}
let found = null
for (let i = 0; i < 16; i += 1) {
  await pressTab()
  found = await evaluate(`(() => {
    const n = document.activeElement
    if (!n || !n.hasAttribute('data-cb-slot-tab')) return null
    const r = n.getBoundingClientRect()
    const s = getComputedStyle(n)
    return { x: r.x, y: r.y, w: r.width, h: r.height, label: (n.textContent || '').trim().slice(0, 40), ring: n.getAttribute('data-cb-focus-ring'), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor, offset: s.outlineOffset, dpr: window.devicePixelRatio, scrollY: window.scrollY }
  })()`)
  if (found) break
}
if (!found) throw new Error('no classroom tab reached by Tab')
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
writeFileSync(OUT, Buffer.from(shot.data, 'base64'))
const mode = await evaluate(`document.querySelector('[data-cb-route]').getAttribute('data-cb-scope')`)
console.log(JSON.stringify({ file: OUT, mode, tab: found, dpr: await evaluate('window.devicePixelRatio'), innerWidth: await evaluate('window.innerWidth') }, null, 2))
socket.close()
