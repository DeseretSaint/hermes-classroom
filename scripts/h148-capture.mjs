#!/usr/bin/env node
/**
 * H-148 live capture: CheckpointPath at 1049 / 900 / 460, plus the geometry, ARIA and zero-evidence
 * shelf paint read from the same rendered page. Fails loudly instead of writing a screenshot of the
 * wrong surface.
 *
 *   CB009_CDP_PORT=9348 node <this> docs/h148-shots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9348'
const OUT = resolve(process.argv[2] || 'docs/h148-shots')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((ok, bad) => {
  socket.addEventListener('open', ok, { once: true })
  socket.addEventListener('error', bad, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: res, reject, timer } = pending.get(message.id)
    clearTimeout(timer)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 20000) =>
  new Promise((res, reject) => {
    const id = nextId++
    const timer = setTimeout(() => {
      pending.delete(id)
      reject(new Error(`CDP timeout: ${method}`))
    }, timeout)
    pending.set(id, { resolve: res, reject, timer })
    socket.send(JSON.stringify({ id, method, params }))
  })

await send('Runtime.enable')
await send('Page.enable')
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}

// The route is the surface; never capture host chrome.
await evaluate("location.hash='#/'; 'ok'")
await new Promise((r) => setTimeout(r, 400))
await evaluate("location.hash='#/coursebook'; 'ok'")
await new Promise((r) => setTimeout(r, 1800))
const mounted = await evaluate("!!document.querySelector('[data-cb-route]') && (document.querySelector('[data-cb-route]').innerText||'').includes('The route')")
if (!mounted) throw new Error('the Coursebook route did not mount; refusing to capture')

// Measure the route as the product presents it: collapse the host's session sidebar and the chat
// sidebar so the route owns the window at each width (the earlier bug was a 199 px route inside a
// 460 px window, which is not the 460 px layout the card asks about).
await evaluate(`(() => {
  for (const label of ['Hide right sidebar', 'Hide sidebar']) {
    const button = [...document.querySelectorAll('button[aria-label]')].find((node) => node.getAttribute('aria-label') === label)
    if (button) button.click()
  }
  return 'ok'
})()`)
await new Promise((r) => setTimeout(r, 700))

const setWidth = async (target) => {
  let override = target
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1000, deviceScaleFactor: 1, mobile: false })
    await new Promise((r) => setTimeout(r, 250))
    const inner = await evaluate('window.innerWidth')
    if (Math.abs(inner - target) <= 1) return inner
    override = Math.round(override * target / inner)
  }
  throw new Error(`could not calibrate ${target}px`)
}

const measure = () => evaluate(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const path = document.querySelector('[data-cb-path]')
  const markers = [...document.querySelectorAll('[data-cb-path-marker]')].map((node) => ({
    id: node.getAttribute('data-cb-path-marker'),
    check: node.getAttribute('data-cb-path-marker-check'),
    declared: node.parentElement?.querySelector('[data-cb-path-item]')?.getAttribute('data-cb-path-node-size'),
    width: Math.round(node.getBoundingClientRect().width),
    height: Math.round(node.getBoundingClientRect().height)
  }))
  const buttons = [...document.querySelectorAll('[data-cb-path-open]')].map((node) => ({
    id: node.getAttribute('data-cb-path-open'),
    label: node.closest('button')?.getAttribute('aria-label') || null,
    current: node.closest('button')?.getAttribute('aria-current') || null,
    focusable: node.closest('button')?.tabIndex >= 0
  }))
  const details = [...document.querySelectorAll('[data-cb-path-detail]')].map((node) => ({
    id: node.getAttribute('data-cb-path-detail'),
    open: node.hasAttribute('open')
  }))
  const styles = [...document.querySelectorAll('[data-cb-course-path]')].map((node) => ({
    segments: node.getAttribute('data-cb-course-path'),
    caption: node.querySelector('[data-cb-course-path-caption]')?.innerText || null,
    accentPaint: [...node.querySelectorAll('span')].some((span) => {
      const style = getComputedStyle(span)
      return style.backgroundColor === 'rgb(179, 74, 42)' || (style.background || '').includes('cb-accent')
    }),
    segmentBackgrounds: [...node.querySelectorAll('span')].map((span) => getComputedStyle(span).backgroundColor)
  }))
  const words = [...document.querySelectorAll('[data-cb-path-word]')].map((node) => node.innerText)
  const checkWords = [...document.querySelectorAll('[data-cb-path-check-word]')].map((node) => node.innerText)
  return {
    innerWidth: window.innerWidth,
    routeWidth: root.clientWidth,
    routeText: (root.innerText || '').slice(0, 220),
    pathCaption: path?.querySelector('[data-cb-tally-caption]')?.innerText || null,
    markers,
    buttons,
    details,
    words,
    checkWords,
    shelfPaths: styles,
    pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
    routeOverflow: root.scrollWidth - root.clientWidth,
    h1s: document.querySelectorAll('[data-cb-route] h1').length,
    fonts: [...document.querySelectorAll('[data-cb-path-word]')].map((node) => getComputedStyle(node).fontSize)
  }
})()`)

const capture = async (file) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true }, 30000)
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  return file
}

const scrollPath = async () => {
  await evaluate("(() => { const node = document.querySelector('[data-cb-path]'); if (node) node.scrollIntoView({ block: 'start' }); return 'ok'; })()")
  await new Promise((r) => setTimeout(r, 350))
}
const capturePath = async (file) => {
  const rect = await evaluate("(() => { const node = document.querySelector('[data-cb-path]'); if (!node) return null; const r = node.getBoundingClientRect(); return { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: Math.min(window.innerWidth, r.width + 16), height: r.height + 16 }; })()")
  if (!rect) throw new Error('no path section to capture')
  const shot = await send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    clip: { ...rect, scale: 1 }
  }, 30000)
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  return file
}

mkdirSync(OUT, { recursive: true })
const report = { widths: {}, shelf: null, text200: null, keyboard: null }

for (const width of [1049, 900, 460]) {
  const inner = await setWidth(width)
  await new Promise((r) => setTimeout(r, 500))
  await scrollPath()
  report.widths[width] = await measure()
  report.widths[width].innerWidth = inner
  report.widths[width].screenshot = await capture(resolve(OUT, `path-${width}.png`))
  report.widths[width].pathScreenshot = await capturePath(resolve(OUT, `path-${width}-section.png`))
}

// 200% text on the 460 route: the geometry must not clip the nodes.
await setWidth(460)
await evaluate("document.documentElement.style.setProperty('font-size','32px','important'); 'ok'")
await new Promise((r) => setTimeout(r, 600))
await scrollPath()
report.text200 = await measure()
report.text200.screenshot = await capture(resolve(OUT, 'path-460-text200.png'))
await evaluate("document.documentElement.style.removeProperty('font-size'); 'ok'")

// Keyboard order: real Tab presses move through the node buttons in reading order, and the focused
// current node paints a visible ring.
await setWidth(1049)
await evaluate("document.querySelector('[data-cb-path-open]').closest('button').focus(); 'ok'")
const keyboard = []
const readFocus = () => evaluate(`(() => {
  const active = document.activeElement
  const style = active ? getComputedStyle(active) : null
  return {
    tag: active && active.tagName,
    label: active && active.getAttribute('aria-label'),
    current: active && active.getAttribute('aria-current'),
    outlineWidth: style ? style.outlineWidth : null,
    outlineColor: style ? style.outlineColor : null,
    outlineOffset: style ? style.outlineOffset : null
  }
})()`)
keyboard.push(await readFocus())
for (let index = 0; index < 4; index += 1) {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await new Promise((r) => setTimeout(r, 120))
  keyboard.push(await readFocus())
}
report.keyboard = {
  stops: keyboard,
  focusables: await evaluate("document.querySelectorAll('[data-cb-path-open]').length")
}
report.keyboard.screenshot = await capture(resolve(OUT, 'path-1049-keyboard-focus.png'))

// Zero-evidence shelf record: the desk's own secondary course list draws CoursePath per row. Read
// the painted segments and capture the list itself, not the whole window behind a failed click.
report.shelf = await evaluate(`(() => {
  const list = document.querySelector('[data-cb-all-courses]')
  const rows = [...document.querySelectorAll('[data-cb-course-path]')]
  return {
    listRect: list ? (() => { const r = list.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height } })() : null,
    rows: rows.map((node) => {
      const spans = [...node.querySelectorAll('span')]
      return {
        segments: node.getAttribute('data-cb-course-path'),
        caption: node.querySelector('[data-cb-course-path-caption]')?.innerText || null,
        backgrounds: spans.map((span) => getComputedStyle(span).backgroundColor),
        dataBackgrounds: spans.map((span) => span.style.background)
      }
    })
  }
})()`)
if (report.shelf.listRect) {
  const r = report.shelf.listRect
  const clip = { x: Math.max(0, r.x), y: Math.max(0, r.y), width: Math.max(1, r.width), height: Math.max(1, r.height), scale: 1 }
  const shot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, clip }, 30000)
  writeFileSync(resolve(OUT, 'shelf-zero-evidence-1049.png'), Buffer.from(shot.data, 'base64'))
  report.shelf.screenshot = resolve(OUT, 'shelf-zero-evidence-1049.png')
}

writeFileSync(resolve(OUT, 'measurements.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
socket.close()
