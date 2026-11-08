#!/usr/bin/env node
/**
 * H-177 live check: the trail in the real Desktop renderer.
 *
 * Asserts the geometry the static frames cannot: the route line actually passes through every
 * marker in the live layout, the reading order is still the `<ol>`, every node opens its real
 * destination, keyboard focus reaches each stop by Tab, the companion is present only in its
 * posture, and nothing overflows at 1049 / 900 / 460.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9376'
const outDir = resolve(process.argv[2] || 'audit/visual/h177-trail/live')
mkdirSync(outDir, { recursive: true })
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) {
    const { resolve: ok, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else ok(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((ok, reject) => {
    const id = nextId++
    pending.set(id, { resolve: ok, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, name), Buffer.from(png.data, 'base64'))
}
const width = async (target) => {
  let override = target
  for (let i = 0; i < 6; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1500, deviceScaleFactor: 1, mobile: false })
    await wait(250)
    const actual = await evalJs('window.innerWidth')
    if (Math.abs(actual - target) <= 2) break
    override = Math.round((override * target) / actual)
  }
  await wait(350)
}

const facts = () =>
  evalJs(`(() => {
    const round = (value) => Math.round(value * 10) / 10
    const text = (node) => (node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null)
    const route = document.querySelector('[data-cb-route]')
    const path = document.querySelector('[data-cb-path]')
    const ol = path ? path.querySelector('ol') : null
    const view = {
      courseDetail: (document.querySelector('[data-cb-course-detail]') || {}).getAttribute?.('data-cb-course-detail') || null,
      lesson: (document.querySelector('[data-cb-lesson-view]') || {}).getAttribute?.('data-cb-lesson-view') || null,
      heading: text(document.querySelector('[data-cb-route] h1')),
      sectionText: text(document.querySelector('[data-cb-course-detail]')) ? text(document.querySelector('[data-cb-course-detail]')).slice(0, 240) : null
    }
    if (!path || !ol) return { mounted: false, width: window.innerWidth, view }
    const olBox = ol.getBoundingClientRect()
    const nodes = [...ol.querySelectorAll('[data-cb-path-node]')].map((node, index) => {
      const item = node.querySelector('[data-cb-path-item]')
      const marker = node.querySelector('[data-cb-path-marker]')
      const button = node.querySelector('button')
      const svg = node.querySelector('svg')
      const line = svg && svg.querySelector('path')
      const box = svg ? svg.getBoundingClientRect() : null
      const nodeBox = node.getBoundingClientRect()
      const markerBox = marker ? marker.getBoundingClientRect() : null
      let alignment = null
      if (line && markerBox && box) {
        const end = line.getPointAtLength(line.getTotalLength())
        alignment = {
          lineX: round(end.x + box.left - nodeBox.left),
          lineY: round((end.y / 100) * box.height + box.top - nodeBox.top),
          markerX: round(markerBox.left + markerBox.width / 2 - nodeBox.left),
          markerY: round(markerBox.top + markerBox.height / 2 - nodeBox.top)
        }
      }
      return {
        index,
        id: node.getAttribute('data-cb-path-node'),
        state: item ? item.getAttribute('data-cb-path-state') : null,
        check: item ? item.getAttribute('data-cb-path-check') : null,
        kind: item ? item.getAttribute('data-cb-path-kind') : null,
        current: item ? item.getAttribute('data-cb-path-current') : null,
        size: item ? Number(item.getAttribute('data-cb-path-node-size')) : null,
        markerX: markerBox ? round(markerBox.left + markerBox.width / 2 - olBox.left) : null,
        alignment,
        ariaCurrent: button ? button.getAttribute('aria-current') : null,
        label: button ? button.getAttribute('aria-label') : null,
        stateWord: text(item ? item.querySelector('[data-cb-path-word]') : null),
        checkWord: text(item ? item.querySelector('[data-cb-path-check-word]') : null),
        detail: Boolean(item ? item.querySelector('[data-cb-path-detail]') : false),
        focusable: button ? button.tabIndex >= 0 : false
      }
    })
    const svgs = [...ol.querySelectorAll('[data-cb-path-node] svg')]
    const companion = document.querySelector('[data-cb-path-companion]')
    return {
      mounted: true,
      width: window.innerWidth,
      routeWidth: route ? Math.round(route.getBoundingClientRect().width) : null,
      layout: path.getAttribute('data-cb-path-layout'),
      run: text(document.querySelector('[data-cb-path-run]')),
      tally: text(document.querySelector('[data-cb-tally-caption]')),
      places: [...document.querySelectorAll('[data-cb-path-place]')].map((node) => text(node)),
      nodes,
      sizes: nodes.map((node) => node.size),
      centres: nodes.map((node) => node.markerX),
      alignmentErrors: nodes.filter((node) => node.alignment && (Math.abs(node.alignment.lineX - node.alignment.markerX) > 1.5 || Math.abs(node.alignment.lineY - node.alignment.markerY) > 1.5)).map((node) => node.id),
      segmentCount: svgs.length,
      segmentsAriaHidden: svgs.every((svg) => svg.getAttribute('aria-hidden') === 'true'),
      strokeWidths: [...new Set(svgs.map((svg) => getComputedStyle(svg.querySelector('path')).strokeWidth))],
      gates: [...document.querySelectorAll('[data-cb-path-gate]')].map((node) => node.getAttribute('data-cb-path-gate')),
      halos: document.querySelectorAll('[data-cb-path-halo]').length,
      details: document.querySelectorAll('[data-cb-path-detail]').length,
      detailsElements: document.querySelectorAll('[data-cb-path] details').length,
      currentCount: document.querySelectorAll('[data-cb-path-current="true"]').length,
      focusedRow: (() => {
        const row = document.querySelector('[data-cb-path-focused="true"]')
        return row ? { id: row.getAttribute('data-cb-path-node'), outline: row.style.outline, outlineOffset: row.style.outlineOffset } : null
      })(),
      ariaCurrentCount: document.querySelectorAll('[aria-current="step"]').length,
      olCount: document.querySelectorAll('[data-cb-path] ol').length,
      listItems: document.querySelectorAll('[data-cb-path] ol > li').length,
      companion: companion ? {
        canvas: Boolean(companion.querySelector('canvas')),
        label: text(companion.querySelector('[data-cb-companion-name]'))
      } : null,
      companionCount: document.querySelectorAll('[data-cb-path-companion]').length,
      pathAnimations: svgs.filter((svg) => svg.getAnimations().length > 0).length,
      animations: document.getAnimations().length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      routeOverflow: route ? route.scrollWidth - route.clientWidth : null,
      pathOverflow: path.scrollWidth - path.clientWidth,
      active: document.activeElement ? {
        tag: document.activeElement.tagName,
        label: document.activeElement.getAttribute ? document.activeElement.getAttribute('aria-label') : null,
        outline: getComputedStyle(document.activeElement).outlineStyle + ' ' + getComputedStyle(document.activeElement).outlineWidth,
        shadow: getComputedStyle(document.activeElement).boxShadow,
        focusVisible: document.activeElement.matches ? document.activeElement.matches(':focus-visible') : null
      } : null,
      view
    }
  })()`)

const openCoursebook = async () => {
  await evalJs("location.hash = '#/'; true")
  await wait(600)
  await evalJs("location.hash = '#/coursebook'; true")
  await wait(3200)
  // Measure the route as the product presents it: the host's own sidebars collapse, so the
  // route owns the window at each width (the earlier bug was a 199 px route inside a 460 px
  // window, which is not the layout the card asks about).
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const info = await evalJs(`(() => {
      const route = document.querySelector('[data-cb-route]')
      const routeWidth = route ? Math.round(route.getBoundingClientRect().width) : 0
      let clicked = null
      for (const label of ['Hide right sidebar', 'Hide sidebar']) {
        const button = [...document.querySelectorAll('button[aria-label]')].find((node) => node.getAttribute('aria-label') === label)
        if (button) { button.click(); clicked = label; break }
      }
      return { routeWidth, clicked, inner: window.innerWidth }
    })()`)
    await wait(750)
    if (!info.clicked || info.routeWidth >= info.inner - 80) break
  }
}

const report = { rig: PORT, generated_at: new Date().toISOString(), steps: [] }

await send('Page.enable')
await send('Runtime.enable')
await width(1049)
await send('Page.reload', { ignoreCache: true })
await wait(4500)
await openCoursebook()

const wide = await facts()
await shot('live-1049.png')
report.steps.push({ step: 'wide-1049', ...wide })

await width(900)
await wait(500)
report.steps.push({ step: 'mid-900', ...(await facts()) })
await shot('live-900.png')

await width(460)
await wait(500)
const narrow = await facts()
report.steps.push({ step: 'narrow-460', ...narrow })
await shot('live-460.png')

// Keyboard: real Tab presses from the top of the route, not programmatic focus.
await width(1049)
await wait(400)
await evalJs("document.activeElement && document.activeElement.blur(); true")
const tabs = []
for (let i = 0; i < 12; i += 1) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await wait(60)
  const active = await evalJs(`(() => {
    const node = document.activeElement
    if (!node) return null
    const style = getComputedStyle(node)
    return {
      tag: node.tagName,
      label: node.getAttribute('aria-label'),
      text: (node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
      inPath: Boolean(node.closest('[data-cb-path]')),
      outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor,
      shadow: style.boxShadow,
      focusVisible: node.matches(':focus-visible'),
      rowOutline: node.closest('[data-cb-path-node]') ? node.closest('[data-cb-path-node]').style.outline : null
    }
  })()`)
  tabs.push(active)
  if (active && active.inPath && active.label && active.label.startsWith('Checkpoint 2')) break
}
report.steps.push({ step: 'keyboard-tabs', tabs })
await shot('live-keyboard-focus-1049.png')

// A stop is a real destination and the keyboard can open it: press Enter on the Tab-focused row.
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: '\r', unmodifiedText: '\r' })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
await wait(2400)
const destination = await facts()
await shot('live-keyboard-destination.png')
report.steps.push({ step: 'keyboard-enter', ...destination })

// Back to the trail for the reduced-motion posture.
await openCoursebook()
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await wait(900)
const reduced = await facts()
await shot('live-reduced-motion-1049.png')
report.steps.push({ step: 'reduced-motion-1049', ...reduced })

await send('Emulation.setEmulatedMedia', { features: [] })
await send('Emulation.clearDeviceMetricsOverride')
socket.close()
writeFileSync(resolve(outDir, 'live-check.json'), `${JSON.stringify(report, null, 2)}\n`)
for (const step of report.steps) {
  console.log(JSON.stringify({
    step: step.step,
    width: step.width,
    layout: step.layout,
    run: step.run,
    centres: step.centres,
    sizes: step.sizes,
    gateCount: step.gates ? step.gates.length : null,
    halos: step.halos,
    detailCount: step.details,
    companion: step.companion,
    alignmentErrors: step.alignmentErrors,
    overflow: step.overflow,
    routeWidth: step.routeWidth,
    routeOverflow: step.routeOverflow,
    animations: step.animations,
    pathAnimations: step.pathAnimations,
    ariaCurrentCount: step.ariaCurrentCount,
    currentCount: step.currentCount,
    listItems: step.listItems,
    view: step.view,
    active: step.active,
    tabs: step.tabs
  }))
}
