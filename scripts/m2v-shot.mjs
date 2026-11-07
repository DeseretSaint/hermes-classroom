#!/usr/bin/env node
/**
 * M2-V1 evidence: screenshot the shipped Coursebook shell in Chromium.
 *
 *   node scripts/m2v-shot.mjs audit/visual/m2-ink-field-notes
 *
 * The frames in `frames.json` are static renders of the shipped `desktop/plugin.js` (see
 * `scripts/m2v-frames.py`) wrapped in the same scoped root the route paints. This is a renderer
 * audit of the token layer and the route shell, not a live-app capture: no backend, no chat, no
 * RPC. Every number in `evidence.json` is read from the painted DOM, not described.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/m2-ink-field-notes')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.M2V_CDP_PORT || '9411'

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
  const shell = document.querySelector('[data-cb-workspace-shell]')
  const reading = document.querySelector('[data-cb-reading-column]')
  const rail = document.querySelector('[data-cb-rail-slot]')
  const media = document.querySelector('[data-cb-media]')
  const title = document.querySelector('[data-cb-workspace-title]')
  const titleStyle = title ? getComputedStyle(title) : null
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    motion: scope ? scope.getAttribute('data-cb-motion') : null,
    tokens,
    paper_painted: style ? style.backgroundColor : null,
    ink_painted: style ? style.color : null,
    layout: shell ? shell.getAttribute('data-cb-workspace-shell') : null,
    rail_slot: rail ? rail.getAttribute('data-cb-rail-slot') : null,
    reading_width_px: reading ? Math.round(reading.getBoundingClientRect().width) : null,
    title_font_px: titleStyle ? titleStyle.fontSize : null,
    title_line_height: titleStyle ? titleStyle.lineHeight : null,
    media_caption: Boolean(media && media.querySelector('[data-cb-media-caption]')),
    media_provenance: Boolean(media && media.querySelector('[data-cb-media-provenance]')),
    media_text_equivalent: Boolean(media && media.querySelector('[data-cb-media-text-equivalent]')),
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: (document.body.innerText || '').slice(0, 200)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
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
  console.log(`${frame.id}: layout=${measured.layout} rail=${measured.rail_slot} overflow=${measured.horizontal_overflow} font=${measured.root_font_px}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
