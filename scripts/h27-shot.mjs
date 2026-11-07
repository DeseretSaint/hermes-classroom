#!/usr/bin/env node
/**
 * H-27 evidence: screenshot the shipped student-syllabus surfaces in Chromium.
 *
 *   node scripts/h27-shot.mjs audit/visual/h27-student-syllabus
 *
 * The frames in `frames.json` are static renders of the shipped `desktop/plugin.js` (see
 * `scripts/h27-frames.py`) wrapped in the same scoped root the route paints, at 1280 and 460 in
 * light and dark. This is a renderer audit of the components and the token layer, not a live-app
 * capture: no backend, no chat, no RPC. Every number in `evidence.json` is read from the painted
 * DOM, not described.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/h27-student-syllabus')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.H27_CDP_PORT || '9431'

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
  const unknown = [...document.querySelectorAll('[data-cb-syllabus-state="unknown"]')]
  const text = document.body.innerText || ''
  return {
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    tokens,
    paper_painted: style ? style.backgroundColor : null,
    ink_painted: style ? style.color : null,
    unknown_fields: unknown.length,
    anchor_buttons: document.querySelectorAll('button[data-variant="text"]').length,
    align_rows: document.querySelectorAll('[data-cb-align-row]').length,
    align_conflict_rows: document.querySelectorAll('[data-cb-align-row="conflict"]').length,
    approve_state: (document.querySelector('[data-cb-syllabus-approve]') || {}).getAttribute
      ? document.querySelector('[data-cb-syllabus-approve]').getAttribute('data-cb-syllabus-approve')
      : null,
    has_authority_line: text.includes('Your syllabus is the authority'),
    has_not_official: text.includes('Not official course material'),
    has_missing_due: text.includes('Due date not in your file'),
    has_forbidden_claim: /\\benrolled\\b|counts toward your grade|accredited/i.test(text),
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: text.slice(0, 180)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
  fixture: 'syllabus.parse.v1 FIXTURE (tests/test_desktop_syllabus_ui.py) — not a backend response',
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
  await sleep(350)
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({
    id: frame.id,
    mode: frame.mode,
    surface: frame.surface,
    width: frame.width,
    height: frame.height,
    reduced_motion: Boolean(frame.reduced_motion),
    ...measured
  })
  console.log(`${frame.id}: mode=${measured.scope_mode} overflow=${measured.horizontal_overflow} unknown=${measured.unknown_fields} approve=${measured.approve_state}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
