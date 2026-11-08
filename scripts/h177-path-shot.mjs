#!/usr/bin/env node
/**
 * H-177 evidence: screenshot and measure the trail from the painted DOM.
 *
 *   node scripts/h177-path-shot.mjs audit/visual/h177-trail/after
 *
 * `frames.json` is produced by `scripts/h177-path-frames.py` from the shipped module (or from the
 * pre-change module, so the before and after sets are measured by this same code).
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/h177-trail/after')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8')).frames
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
mkdirSync(resolve(outDir, 'shots'), { recursive: true })
const PORT = process.env.H177_CDP_PORT || '9418'

const chromium = spawn('chromium', [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${resolve(outDir, '.chromium')}`,
  'about:blank'
], { stdio: 'ignore' })

const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 80; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
    if (targets.length) break
  } catch (error) {
    targets = null
  }
  await sleep(250)
}
if (!targets || !targets.length) {
  chromium.kill()
  throw new Error('chromium CDP did not open')
}

const page = targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: done, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else done(message.result)
  }
})
const send = (method, params = {}) => new Promise((done, reject) => {
  const id = nextId++
  pending.set(id, { resolve: done, reject })
  socket.send(JSON.stringify({ id, method, params }))
})
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}

await send('Page.enable')
await send('Runtime.enable')

const MEASURE = `(() => {
  const round = (value) => Math.round(value * 10) / 10
  const root = document.querySelector('[data-cb-route]')
  const path = document.querySelector('[data-cb-path]')
  const ol = path ? path.querySelector('ol') : null
  const olBox = ol ? ol.getBoundingClientRect() : null
  const markerX = (marker) => {
    const box = marker.getBoundingClientRect()
    return round(box.left + box.width / 2 - olBox.left)
  }
  const nodes = [...document.querySelectorAll('[data-cb-path-node]')].map((node, index) => {
    const item = node.querySelector('[data-cb-path-item]')
    const marker = node.querySelector('[data-cb-path-marker]')
    const button = node.querySelector('button')
    const rect = node.getBoundingClientRect()
    const style = getComputedStyle(node)
    const markerStyle = marker ? getComputedStyle(marker) : null
    return {
      index,
      id: node.getAttribute('data-cb-path-node'),
      motion: node.getAttribute('data-cb-path-node-motion'),
      state: item ? item.getAttribute('data-cb-path-state') : null,
      check: item ? item.getAttribute('data-cb-path-check') : null,
      kind: item ? item.getAttribute('data-cb-path-kind') : null,
      current: item ? item.getAttribute('data-cb-path-current') : null,
      declaredSize: item ? item.getAttribute('data-cb-path-node-size') : null,
      markerWidth: marker ? round(marker.getBoundingClientRect().width) : null,
      markerHeight: marker ? round(marker.getBoundingClientRect().height) : null,
      markerX: marker ? markerX(marker) : null,
      markerBorder: markerStyle ? markerStyle.borderTopWidth + ' ' + markerStyle.borderTopColor : null,
      markerRadius: markerStyle ? markerStyle.borderRadius : null,
      rowTop: round(rect.top - (olBox ? olBox.top : 0)),
      rowHeight: round(rect.height),
      ariaCurrent: button ? button.getAttribute('aria-current') : null,
      label: button ? button.getAttribute('aria-label') : null,
      focusable: button ? button.tabIndex >= 0 : false,
      transition: style.transition || '',
      transitionDuration: style.transitionDuration,
      transitionProperty: style.transitionProperty,
      opacity: style.opacity,
      transform: style.transform || 'none'
    }
  })
  const segments = [...document.querySelectorAll('[data-cb-path-node] svg')].map((svg) => {
    const box = svg.getBoundingClientRect()
    return {
      ariaHidden: svg.getAttribute('aria-hidden'),
      left: round(box.left - olBox.left),
      width: round(box.width),
      top: round(box.top - olBox.top),
      height: round(box.height),
      stroke: svg.querySelector('path') ? getComputedStyle(svg.querySelector('path')).strokeWidth : null
    }
  })
  // The line must pass through every marker: read the first (enter) path's endpoints and compare.
  const alignment = [...document.querySelectorAll('[data-cb-path-node]')].map((node) => {
    const svg = node.querySelector('svg')
    const line = svg && svg.querySelector('path')
    const marker = node.querySelector('[data-cb-path-marker]')
    if (!line || !marker) return null
    const box = svg.getBoundingClientRect()
    const nodeBox = node.getBoundingClientRect()
    const markerBox = marker.getBoundingClientRect()
    const total = line.getTotalLength()
    const start = line.getPointAtLength(0)
    const end = line.getPointAtLength(total)
    return {
      id: node.getAttribute('data-cb-path-node'),
      enterStartX: round(start.x + box.left - nodeBox.left),
      enterEndX: round(end.x + box.left - nodeBox.left),
      enterEndY: round((end.y / 100) * box.height + box.top - nodeBox.top),
      markerCentreX: round(markerBox.left + markerBox.width / 2 - nodeBox.left),
      markerCentreY: round(markerBox.top + markerBox.height / 2 - nodeBox.top)
    }
  })
  const active = document.activeElement
  const focusedRow = document.querySelector('[data-cb-path-focused="true"]')
  return {
    focusRow: focusedRow ? { id: focusedRow.getAttribute('data-cb-path-node'), outline: focusedRow.style.outline, outlineOffset: focusedRow.style.outlineOffset } : null,
    width: window.innerWidth,
    routeWidth: root ? root.clientWidth : null,
    pathLayout: path ? path.getAttribute('data-cb-path-layout') : null,
    runText: (document.querySelector('[data-cb-path-run]') || {}).innerText || null,
    tallyCaption: (document.querySelector('[data-cb-tally-caption]') || {}).innerText || null,
    startText: (document.querySelector('[data-cb-path-place="start"]') || {}).innerText || null,
    endText: (document.querySelector('[data-cb-path-place="end"]') || {}).innerText || null,
    nodes,
    markerCentres: nodes.map((node) => node.markerX),
    alignment,
    alignmentErrors: alignment.filter((row) => row && (Math.abs(row.enterEndX - row.markerCentreX) > 1 || Math.abs(row.enterEndY - row.markerCentreY) > 1)).map((row) => row.id),
    segments,
    segmentCount: segments.length,
    segmentsAllAriaHidden: segments.every((segment) => segment.ariaHidden === 'true'),
    segmentStrokeWidths: [...new Set(segments.map((segment) => segment.stroke))],
    gateCount: document.querySelectorAll('[data-cb-path-gate]').length,
    gateStates: [...document.querySelectorAll('[data-cb-path-gate]')].map((node) => node.getAttribute('data-cb-path-gate')),
    haloCount: document.querySelectorAll('[data-cb-path-halo]').length,
    detailIds: [...document.querySelectorAll('[data-cb-path-detail]')].map((node) => node.getAttribute('data-cb-path-detail')),
    detailsCount: document.querySelectorAll('details').length,
    companion: Boolean(document.querySelector('[data-cb-path-companion] canvas')),
    currentCount: document.querySelectorAll('[data-cb-path-current="true"]').length,
    ariaCurrentCount: document.querySelectorAll('[aria-current="step"]').length,
    olCount: document.querySelectorAll('ol').length,
    listItems: document.querySelectorAll('ol > li').length,
    focus: active ? {
      tag: active.tagName,
      label: active.getAttribute && active.getAttribute('aria-label'),
      outlineStyle: getComputedStyle(active).outlineStyle,
      outlineWidth: getComputedStyle(active).outlineWidth,
      outlineColor: getComputedStyle(active).outlineColor
    } : null,
    transitions: nodes.filter((node) => node.transitionDuration && node.transitionDuration !== '0s').length,
    pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
    routeOverflow: root ? root.scrollWidth - root.clientWidth : null,
    pathOverflow: path ? path.scrollWidth - path.clientWidth : null,
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches
  }
})()`

const evidence = { frames: [] }
for (const frame of frames) {
  const htmlPath = resolve(htmlDir, `${frame.id}.html`)
  writeFileSync(htmlPath, frame.html, 'utf8')
  await send('Emulation.setEmulatedMedia', {
    features: frame.reduced ? [{ name: 'prefers-reduced-motion', value: 'reduce' }] : []
  })
  await send('Emulation.setDeviceMetricsOverride', {
    width: frame.width,
    height: frame.height,
    deviceScaleFactor: 1,
    mobile: false
  })
  await send('Page.navigate', { url: `file://${htmlPath}` })
  await sleep(450)
  if (frame.focus) {
    await evaluate(`(() => {
      const buttons = [...document.querySelectorAll('[data-cb-path-open]')].map((node) => node.closest('button'))
      const button = buttons[${frame.focus}] || buttons[0]
      if (button) button.focus()
      return document.activeElement ? document.activeElement.getAttribute('aria-label') : null
    })()`)
    await sleep(120)
  }
  const measured = await evaluate(MEASURE)
  const shot = await send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(resolve(outDir, 'shots', `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({ id: frame.id, mode: frame.mode, font: frame.font || null, ...measured })
  console.log(frame.id, 'route', measured.routeWidth, 'overflow', measured.pageOverflow, '/', measured.routeOverflow)
}

writeFileSync(resolve(outDir, 'evidence.json'), JSON.stringify(evidence, null, 2), 'utf8')
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
