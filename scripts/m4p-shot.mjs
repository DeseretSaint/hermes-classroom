#!/usr/bin/env node
/**
 * M4 procedure evidence: screenshot the shipped procedure layout in Chromium.
 *
 *   node scripts/m4p-shot.mjs audit/visual/m4-procedure
 *
 * Frames are static renders of the shipped `desktop/plugin.js` (see `scripts/m4p-frames.py`)
 * inside the scoped token root. Every number in `evidence.json` is read from the painted DOM.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/m4-procedure')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.M4P_CDP_PORT || '9421'

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
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}

await send('Page.enable')
await send('Runtime.enable')

const MEASURE = `(() => {
  const scope = document.querySelector('[data-cb-scope]')
  const style = scope ? getComputedStyle(scope) : null
  const tokens = {}
  if (style) {
    for (const name of ['paper','paper-raised','ink','ink-soft','rule','accent','accent-soft','field','ochre','coral']) {
      tokens[name] = style.getPropertyValue('--cb-' + name).trim()
    }
  }
  const q = (selector) => document.querySelector(selector)
  const steps = document.querySelectorAll('[data-cb-procedure-step]')
  const rows = document.querySelectorAll('[data-cb-procedure-rows] tr')
  const hazard = q('[data-cb-procedure-hazard]')
  const source = q('[data-cb-procedure-source]')
  const check = q('[data-cb-audit-check]')
  return {
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    motion: scope ? scope.getAttribute('data-cb-motion') : null,
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    tokens,
    procedure_view: Boolean(q('[data-cb-lesson-view="procedure"]')),
    header: Boolean(q('[data-cb-procedure-header]')),
    tools: q('[data-cb-procedure-tools]') ? Number(q('[data-cb-procedure-tools]').getAttribute('data-cb-procedure-tools')) : null,
    parts: q('[data-cb-procedure-parts]') ? Number(q('[data-cb-procedure-parts]').getAttribute('data-cb-procedure-parts')) : null,
    steps: steps.length,
    step_numbers: Array.from(steps).map((node) => node.getAttribute('data-cb-procedure-step')),
    hazard_present: Boolean(hazard),
    hazard_role: hazard ? hazard.getAttribute('role') : null,
    hazard_coral: hazard ? getComputedStyle(hazard).borderLeftColor : null,
    stop_condition: Boolean(q('[data-cb-procedure-stop]')),
    schematic: Boolean(q('[data-cb-procedure-schematic]')),
    schematic_rows: rows.length,
    source_permission: source ? (source.innerText || '').includes('Licensed for this course') : false,
    verification_once: document.querySelectorAll('[data-cb-audit-check]').length,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: (document.body.innerText || '').slice(0, 160)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop procedure layout in Chromium (no backend, no chat, no RPC)',
  chromium: (await send('Browser.getVersion')).product,
  frames: []
}

for (const frame of frames.frames) {
  const file = resolve(htmlDir, `${frame.id}.html`)
  writeFileSync(file, frame.html)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 1, mobile: false })
  await send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: frame.reduced_motion ? 'reduce' : 'no-preference' }]
  })
  await send('Page.navigate', { url: `file://${file}` })
  await sleep(400)
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({ id: frame.id, width: frame.width, height: frame.height, font: frame.font || 'root', reduced_motion: Boolean(frame.reduced_motion), ...measured })
  console.log(`${frame.id}: steps=${measured.steps} rows=${measured.schematic_rows} hazard=${measured.hazard_present} overflow=${measured.horizontal_overflow} font=${measured.root_font_px}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
