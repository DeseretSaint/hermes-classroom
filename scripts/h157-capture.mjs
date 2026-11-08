#!/usr/bin/env node
/**
 * H-157 live capture: Course Detail composition at 1049 / 900 / 460 on the isolated window.
 *
 * Reads the four primary surfaces, the `More` disclosure, the heading level, keyboard arrow
 * movement on the tab row, the Evidence labels and horizontal overflow from the rendered page.
 * It refuses to write a screenshot of the wrong surface.
 *
 *   CB009_CDP_PORT=9348 node scripts/h157-capture.mjs docs/h157-shots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9348'
const OUT = resolve(process.argv[2] || 'docs/h157-shots')

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
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

await evaluate("location.hash='#/'; 'ok'")
await sleep(400)
await evaluate("location.hash='#/coursebook'; 'ok'")
await sleep(2200)
const mounted = await evaluate("!!document.querySelector('[data-cb-route]')")
if (!mounted) throw new Error('the Coursebook route did not mount; refusing to capture')

// Collapse host chrome so the route owns the measured width.
await evaluate(`(() => {
  for (const label of ['Hide right sidebar', 'Hide sidebar']) {
    const button = [...document.querySelectorAll('button[aria-label]')].find((node) => node.getAttribute('aria-label') === label)
    if (button) button.click()
  }
  return 'ok'
})()`)
await sleep(700)

// Open the first course from the desk. The button's own label is the surface's, not a selector
// invented here; if it is missing we say so instead of capturing a list.
const opened = await evaluate(`(() => {
  const buttons = [...document.querySelectorAll('button')]
  const open = buttons.find((node) => /^Open the section$/.test((node.innerText || '').trim()))
  if (!open) return 'no-open-button'
  open.click()
  return 'clicked'
})()`)
if (opened !== 'clicked') throw new Error(`could not open a course detail: ${opened}`)
await sleep(2500)
const detail = await evaluate("!!document.querySelector('[data-cb-course-detail]')")
if (!detail) throw new Error('course detail did not render; refusing to capture')

const setWidth = async (target) => {
  let override = target
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1100, deviceScaleFactor: 1, mobile: false })
    await sleep(250)
    const inner = await evaluate('window.innerWidth')
    if (Math.abs(inner - target) <= 1) return inner
    override = Math.round(override * target / inner)
  }
  throw new Error(`could not calibrate ${target}px`)
}

const measure = () => evaluate(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const detail = document.querySelector('[data-cb-course-detail]')
  const tabs = [...document.querySelectorAll('[data-cb-learning-tabs] [data-cb-tab]')]
  const more = document.querySelector('[data-cb-more]')
  const moreButtons = more ? [...more.querySelectorAll('[data-cb-tab]')] : []
  const title = document.querySelector('[data-cb-course-title]')
  const tabRow = document.querySelector('[data-cb-learning-tabs]')
  return {
    innerWidth: window.innerWidth,
    view: detail ? detail.getAttribute('data-cb-course-detail') : null,
    primaryCount: tabs.length,
    primaryLabels: tabs.map((node) => (node.innerText || '').trim()),
    selected: tabs.filter((node) => node.getAttribute('aria-selected') === 'true').map((node) => (node.innerText || '').trim()),
    moreSummary: more ? (more.querySelector('summary') || {}).innerText || null : null,
    moreOpen: more ? more.hasAttribute('open') : null,
    moreCount: moreButtons.length,
    moreLabels: moreButtons.map((node) => (node.innerText || '').trim()),
    moreVisible: moreButtons.filter((node) => node.getBoundingClientRect().height > 0).map((node) => (node.innerText || '').trim()),
    headingTag: title ? title.tagName : null,
    headingText: title ? (title.innerText || '').trim() : null,
    h1Count: root ? root.querySelectorAll('h1').length : null,
    h2Count: root ? root.querySelectorAll('h2').length : null,
    tabRowHeight: tabRow ? Math.round(tabRow.getBoundingClientRect().height) : null,
    tabRowScroll: tabRow ? tabRow.scrollWidth - tabRow.clientWidth : null,
    routeWidth: root ? root.clientWidth : null,
    pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
    routeOverflow: root ? root.scrollWidth - root.clientWidth : null,
    moreOverflow: more ? more.scrollWidth - more.clientWidth : null
  }
})()`)

const capture = async (file) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true }, 30000)
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  return file
}

const captureRoute = async (file) => {
  const rect = await evaluate("(() => { const node = document.querySelector('[data-cb-route]'); const r = node.getBoundingClientRect(); return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: Math.min(window.innerWidth, r.width), height: Math.min(window.innerHeight, r.height), scale: 1 }; })()")
  const shot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, clip: rect }, 30000)
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  return file
}

const captureTabs = async (file) => {
  const rect = await evaluate("(() => { const node = document.querySelector('[data-cb-learning-tabs]'); const more = document.querySelector('[data-cb-more]'); const a = node.getBoundingClientRect(); const b = more.getBoundingClientRect(); return { x: Math.max(0, a.x - 6), y: Math.max(0, a.y - 6), width: Math.min(window.innerWidth, Math.max(a.width, b.width) + 12), height: Math.max(1, b.bottom - a.top + 12), scale: 1 }; })()")
  const shot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, clip: rect }, 30000)
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  return file
}

mkdirSync(OUT, { recursive: true })
const report = { widths: {}, text200: null, keyboard: null, evidence: null, more: null }

for (const width of [1049, 900, 460]) {
  const inner = await setWidth(width)
  await sleep(500)
  await evaluate("(() => { const node = document.querySelector('[data-cb-learning-tabs]'); if (node) node.scrollIntoView({ block: 'center' }); return 'ok'; })()")
  await sleep(300)
  report.widths[width] = await measure()
  report.widths[width].innerWidth = inner
  report.widths[width].screenshot = await captureRoute(resolve(OUT, `detail-${width}.png`))
  report.widths[width].tabsScreenshot = await captureTabs(resolve(OUT, `tabs-${width}.png`))
}

// The `More` disclosure, opened by its own summary at 1049.
await setWidth(1049)
await sleep(400)
report.more = await evaluate(`(() => {
  const more = document.querySelector('[data-cb-more]')
  const summary = more.querySelector('summary')
  summary.click()
  return { openBefore: more.hasAttribute('open') }
})()`)
await sleep(400)
report.more.after = await evaluate(`(() => {
  const more = document.querySelector('[data-cb-more]')
  const buttons = [...more.querySelectorAll('[data-cb-tab]')]
  return {
    open: more.hasAttribute('open'),
    labels: buttons.map((node) => (node.innerText || '').trim()),
    visible: buttons.filter((node) => node.getBoundingClientRect().height > 0).map((node) => (node.innerText || '').trim()),
    summary: (more.querySelector('summary') || {}).innerText || null
  }
})()`)
report.more.screenshot = await captureTabs(resolve(OUT, 'more-1049.png'))

// A direct view link still resolves: Plan lives behind More and still renders.
await evaluate("(() => { const node = document.querySelector('[data-cb-tab=\"plan\"]'); if (node) node.click(); return 'ok'; })()")
await sleep(1500)
report.more.plan = await evaluate(`(() => {
  const detail = document.querySelector('[data-cb-course-detail]')
  const outside = document.querySelector('[data-cb-outside-route]')
  const more = document.querySelector('[data-cb-more]')
  return {
    view: detail ? detail.getAttribute('data-cb-course-detail') : null,
    moreOpen: more ? more.hasAttribute('open') : null,
    summary: more ? (more.querySelector('summary') || {}).innerText : null,
    notice: outside ? outside.innerText : null,
    selectedPrimary: [...document.querySelectorAll('[data-cb-learning-tabs] [data-cb-tab]')]
      .filter((node) => node.getAttribute('aria-selected') === 'true')
      .map((node) => (node.innerText || '').trim())
  }
})()`)
report.more.screenshotActive = await captureTabs(resolve(OUT, 'more-plan-1049.png'))

// Back to the reading surface, then the Evidence surface.
await evaluate("(() => { const node = document.querySelector('[data-cb-tab=\"learn\"]'); if (node) node.click(); return 'ok'; })()")
await sleep(1200)
await evaluate("(() => { const node = document.querySelector('[data-cb-tab=\"evidence\"]'); if (node) node.click(); return 'ok'; })()")
await sleep(1600)
report.evidence = await evaluate(`(() => {
  const labels = [...document.querySelectorAll('[data-cb-evidence-block]')].map((node) => ({
    block: node.getAttribute('data-cb-evidence-block'),
    label: (node.querySelector('.panel-label, div') || {}).innerText || null
  }))
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  const technical = document.querySelector('[data-cb-evidence-technical]')
  return {
    blocks: labels,
    hasL3: /L3 ·/.test(text),
    hasLayer: /layer 2/i.test(text),
    technicalOpen: technical ? technical.hasAttribute('open') : null,
    technicalText: technical ? technical.innerText.slice(0, 200) : null,
    text: text.slice(0, 700)
  }
})()`)
report.evidence.screenshot = await captureRoute(resolve(OUT, 'evidence-1049.png'))

// 200% text at 460: the tab row must not clip or overflow the route.
await setWidth(460)
await evaluate("(() => { const node = document.querySelector('[data-cb-tab=\"overview\"]'); if (node) node.click(); return 'ok'; })()")
await sleep(800)
await evaluate("document.documentElement.style.setProperty('font-size','32px','important'); 'ok'")
await sleep(700)
await evaluate("(() => { const node = document.querySelector('[data-cb-learning-tabs]'); if (node) node.scrollIntoView({ block: 'center' }); return 'ok'; })()")
await sleep(300)
report.text200 = await measure()
report.text200.screenshot = await captureTabs(resolve(OUT, 'tabs-460-text200.png'))
await evaluate("document.documentElement.style.removeProperty('font-size'); 'ok'")
await sleep(400)

// Keyboard: real Tab and ArrowRight presses on the tab row.
await setWidth(1049)
await evaluate("(() => { const node = document.querySelector('[data-cb-learning-tabs] [data-cb-tab=\"overview\"]'); if (node) node.focus(); return 'ok'; })()")
await sleep(200)
const readFocus = () => evaluate(`(() => {
  const active = document.activeElement
  const style = active ? getComputedStyle(active) : null
  return {
    tag: active && active.tagName,
    tab: active && active.getAttribute('data-cb-tab'),
    selected: active && active.getAttribute('aria-selected'),
    outlineWidth: style ? style.outlineWidth : null,
    outlineColor: style ? style.outlineColor : null,
    innerText: active ? (active.innerText || '').trim() : null
  }
})()`)
const keyboard = []
keyboard.push(await readFocus())
for (let index = 0; index < 3; index += 1) {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 })
  await sleep(250)
  keyboard.push(await readFocus())
}
report.keyboard = {
  stops: keyboard,
  viewAfter: await evaluate("(document.querySelector('[data-cb-course-detail]') || {}).getAttribute && document.querySelector('[data-cb-course-detail]').getAttribute('data-cb-course-detail')"),
  screenshot: await captureTabs(resolve(OUT, 'tabs-1049-keyboard.png'))
}

writeFileSync(resolve(OUT, 'measurements.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
socket.close()
