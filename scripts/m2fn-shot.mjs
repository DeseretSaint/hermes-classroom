#!/usr/bin/env node
/**
 * M2-U3 evidence: screenshot the shipped Field Notes surfaces in Chromium.
 *
 *   python3 scripts/m2fn-frames.py && node scripts/m2fn-shot.mjs audit/visual/m2-field-notes
 *
 * Every frame is a static render of the shipped `desktop/plugin.js` inside the same scoped root
 * the route paints. This is a renderer audit at the widths, modes and text scales the card names,
 * not a live-app capture; the numbers in `evidence.json` are read from the painted DOM.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/m2-field-notes')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.M2FN_CDP_PORT || '9419'

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
  const noteRows = [...document.querySelectorAll('[data-cb-field-note]')]
  const widths = noteRows.map((row) => Math.round(row.getBoundingClientRect().width))
  const bodyWidth = Math.round(document.body.getBoundingClientRect().width)
  const buttons = [...document.querySelectorAll('button')]
  const unnamed = buttons.filter((button) => !(button.innerText || '').trim() && !button.getAttribute('aria-label'))
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    tokens,
    desk_state: (document.querySelector('[data-cb-desk]') || {}).getAttribute
      ? document.querySelector('[data-cb-desk]').getAttribute('data-cb-desk')
      : null,
    field_notes_state: (document.querySelector('[data-cb-field-notes]') || {}).getAttribute
      ? document.querySelector('[data-cb-field-notes]').getAttribute('data-cb-field-notes')
      : null,
    field_note_count: noteRows.length,
    field_note_rows_wider_than_body: widths.filter((width) => width > bodyWidth).length,
    field_notes_text: (document.querySelector('[data-cb-field-notes]') || {}).innerText
      ? document.querySelector('[data-cb-field-notes]').innerText.slice(0, 500)
      : null,
    notebook_entry_count: document.querySelectorAll('[data-cb-note-section]').length,
    notebook_excerpt_count: document.querySelectorAll('.md').length,
    block_save_count: document.querySelectorAll('[data-cb-block-save]').length,
    block_save_buttons: [...document.querySelectorAll('[data-cb-block-save] button')].map((b) => (b.innerText || '').trim()),
    lesson_view: (document.querySelector('[data-cb-lesson-view]') || {}).getAttribute
      ? document.querySelector('[data-cb-lesson-view]').getAttribute('data-cb-lesson-view')
      : null,
    button_count: buttons.length,
    buttons_without_a_name: unnamed.length,
    motion: (document.querySelector('[data-cb-scope]') || {}).getAttribute
      ? document.querySelector('[data-cb-scope]').getAttribute('data-cb-motion')
      : null,
    reduced_motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: (document.body.innerText || '').slice(0, 260)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
  contract: 'cb.rpc v9 (notebook.list entry, lesson.page document)',
  plugin_sha256: process.env.M2FN_PLUGIN_SHA || null,
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
  evidence.frames.push({ id: frame.id, state: frame.state, width: frame.width, height: frame.height, ...measured })
  console.log(`${frame.id}: notes=${measured.field_notes_state}/${measured.field_note_count} save=${measured.block_save_count} overflow=${measured.horizontal_overflow} font=${measured.root_font_px}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
