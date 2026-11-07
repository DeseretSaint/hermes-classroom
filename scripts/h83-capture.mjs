#!/usr/bin/env node
/**
 * H-83 live capture: screenshots of the isolated window at a given CSS viewport.
 *
 *   CB009_CDP_PORT=9339 node scripts/h83-capture.mjs <width> <out.png> [--dark] [--full]
 *
 * Uses Emulation.setDeviceMetricsOverride so the plugin's own viewport atom (not a media query)
 * decides the layout range, exactly as a real window of that CSS width would. `--dark` toggles the
 * host theme class and the group's colour-scheme so the scoped token layer repaints.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const width = Number(process.argv[2] || 1049)
const out = resolve(process.argv[3] || 'audit/ux/round3/h83-live/shot.png')
const dark = process.argv.includes('--dark')
const full = process.argv.includes('--full')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message)
    pending.delete(message.id)
  }
})
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = nextId++
    pending.set(id, res)
    socket.send(JSON.stringify({ id, method, params }))
  })

await send('Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }]
})
await send('Emulation.setDeviceMetricsOverride', {
  width,
  height: 1000,
  deviceScaleFactor: 1,
  mobile: false,
})
await send('Runtime.evaluate', {
  expression: `document.documentElement.classList.${dark ? 'add' : 'remove'}('dark'); window.dispatchEvent(new Event('resize'));`,
  awaitPromise: true,
})
await new Promise((r) => setTimeout(r, 900))

const metrics = await send('Runtime.evaluate', {
  expression: `(() => {
    const route = document.querySelector('[data-cb-route]');
    const scroller = route || document.scrollingElement;
    const shell = document.querySelector('[data-cb-workspace-shell]');
    const detail = document.querySelector('[data-cb-course-detail]');
    const paper = route ? getComputedStyle(route).getPropertyValue('--cb-paper').trim() : null;
    return JSON.stringify({
      width: innerWidth,
      height: innerHeight,
      layout: shell ? shell.dataset.cbWorkspaceShell : null,
      detail: detail ? detail.dataset.cbCourseDetail : null,
      view: document.querySelector('[data-cb-lesson-view]') ? document.querySelector('[data-cb-lesson-view]').dataset.cbLessonView : null,
      blocks: document.querySelectorAll('[data-cb-block]').length,
      missions: document.querySelectorAll('[data-cb-mission]').length,
      paper,
      overflowX: scroller ? scroller.scrollWidth - scroller.clientWidth : null,
      docOverflowX: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
      tabs: [...document.querySelectorAll('[data-cb-tab]')].map((t) => t.dataset.cbTab),
      h1: document.querySelectorAll('[data-cb-route] h1').length,
      primary: [...document.querySelectorAll('[data-cb-route] button')].filter((b) => b.dataset.variant === 'default').map((b) => b.textContent.trim()),
      offenders: route ? [...route.querySelectorAll('*')]
        .filter((e) => e.scrollWidth - e.clientWidth > 8)
        .slice(0, 6)
        .map((e) => ({ tag: e.tagName, d: Object.keys(e.dataset).join(','), sw: e.scrollWidth, cw: e.clientWidth, t: e.textContent.trim().slice(0, 28) })) : [],
    });
  })()`,
  returnByValue: true,
})
const metricsValue = JSON.parse(metrics.result.result.value)

const shot = await send('Page.captureScreenshot', {
  format: 'png',
  captureBeyondViewport: Boolean(full),
  ...(full ? { clip: { x: 0, y: 0, width, height: metricsValue.fullHeight || 2400, scale: 1 } } : {}),
})
mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, Buffer.from(shot.result.data, 'base64'))
console.log(JSON.stringify({ out, ...metricsValue }))
socket.close()
