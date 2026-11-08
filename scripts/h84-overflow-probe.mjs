#!/usr/bin/env node
/** Which elements overflow the route at 460 and does the host chrome cause it? */
const PORT = process.env.CB009_CDP_PORT || '9337'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res) => socket.addEventListener('open', res, { once: true }))
let id = 1
const pend = new Map()
socket.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id) } })
const send = (method, params = {}) => new Promise((res) => { const i = id++; pend.set(i, res); socket.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.result.value
await send('Emulation.setDeviceMetricsOverride', { width: Math.round(460 * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
await ev("window.dispatchEvent(new Event('resize'))")
await new Promise((r) => setTimeout(r, 900))
console.log(await ev(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const doc = document.scrollingElement
  const offenders = [...route.querySelectorAll('*')]
    .filter((e) => e.scrollWidth - e.clientWidth > 4)
    .slice(0, 10)
    .map((e) => ({ tag: e.tagName, data: Object.keys(e.dataset).join(','), sw: e.scrollWidth, cw: e.clientWidth, t: (e.textContent || '').trim().slice(0, 32), style: (e.getAttribute('style') || '').slice(0, 80) }))
  return JSON.stringify({
    innerWidth: innerWidth,
    routeOverflow: route.scrollWidth - route.clientWidth,
    bodyOverflow: doc.scrollWidth - doc.clientWidth,
    routeW: route.clientWidth,
    hostSidebars: [...document.querySelectorAll('aside,[class*=sidebar]')].map((e) => e.className && String(e.className).slice(0, 40)),
    offenders
  }, null, 1)
})()`))
socket.close()
