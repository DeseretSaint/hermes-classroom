#!/usr/bin/env node
/**
 * CB-009 layout probe at 460px and 200% text: measure what actually overflows instead of guessing
 * from a screenshot. Prints the route's horizontal overflow, the Coursebook pane's box, and whether
 * the pane's answer control and the chat composer are inside the viewport.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-layout-probe.mjs
 */
import { writeFileSync } from 'node:fs'

const PORT = process.env.CB009_CDP_PORT || '9222'
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
const measure = () =>
  evaluate(`(() => {
    const doc = document.documentElement
    const paneLabel = [...document.querySelectorAll('*')].find((e) => (e.innerText || '').trim() === 'COURSEBOOK' && e.children.length === 0)
    const pane = paneLabel ? paneLabel.closest('div.flex.h-full') || paneLabel.parentElement?.parentElement : null
    const answer = document.querySelector('#cb-attempt-answer')
    const composer = document.querySelector('[contenteditable="true"]')
    const rect = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), onScreen: r.right > 0 && r.left < innerWidth && r.bottom > 0 && r.top < innerHeight } }
    const overflows = [...document.querySelectorAll('main *, [data-slot=sidebar] *, [data-slot=sidebar-content] *')]
      .filter((e) => e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX === 'visible')
      .slice(0, 8)
      .map((e) => ({ tag: e.tagName, cls: String(e.className).slice(0, 50), sw: e.scrollWidth, cw: e.clientWidth }))
    return {
      viewport: { w: innerWidth, h: innerHeight },
      docOverflowX: doc.scrollWidth - doc.clientWidth,
      bodyOverflowX: document.body.scrollWidth - document.body.clientWidth,
      paneRect: rect(pane),
      paneText: pane ? (pane.innerText || '').slice(0, 220) : null,
      answerRect: rect(answer),
      composerRect: rect(composer),
      overflowing: overflows
    }
  })()`)

await send('Page.enable')
await send('Runtime.enable')
const out = {}
out.wide = await measure()
await send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await sleep(900)
out.narrow = await measure()
out.narrowPaneTabs = await evaluate(`[...document.querySelectorAll('[data-slot=pane-tab]')].map((e) => e.getAttribute('aria-label') || (e.innerText || '').trim()).filter(Boolean)`)
const narrowShot = await send('Page.captureScreenshot', { format: 'png' })
writeFileSync('docs/cb009-shots/pane-17-narrow-measured.png', Buffer.from(narrowShot.data, 'base64'))
await send('Emulation.clearDeviceMetricsOverride')
await evaluate(`document.documentElement.style.fontSize = '32px'`)
await sleep(800)
out.text200 = await measure()
const bigShot = await send('Page.captureScreenshot', { format: 'png' })
writeFileSync('docs/cb009-shots/pane-18-text200-measured.png', Buffer.from(bigShot.data, 'base64'))
await evaluate(`document.documentElement.style.fontSize = ''`)
out.capturedAt = new Date().toISOString()
writeFileSync('docs/REVIEW_CB009-layout-probe.json', JSON.stringify(out, null, 2))
console.log(JSON.stringify(out, null, 2))
socket.close()
