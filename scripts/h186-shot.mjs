#!/usr/bin/env node
/**
 * H-186 renderer captures for audit/h186/frames.json (shipped desktop/plugin.js).
 *   node scripts/h186-shot.mjs
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve('audit/h186')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.H186_SHOT_CDP_PORT || '9421'

const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
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
  } catch { targets = null }
  await sleep(250)
}
if (!targets || !targets.length) { chromium.kill(); throw new Error('chromium CDP did not open') }
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
  const expected = Array.isArray(window.__CB_EXPECTED_EQUIVALENTS__) ? window.__CB_EXPECTED_EQUIVALENTS__ : []
  const frames = [...document.querySelectorAll('[data-cb-media]')].map((media) => {
    const caption = media.querySelector('[data-cb-media-caption]')
    const equivalent = media.querySelector('[data-cb-media-text-equivalent]')
    const captionText = caption ? (caption.innerText || '').trim() : null
    const disclosureText = equivalent
      ? ((equivalent.querySelector('div') || equivalent).textContent || '').trim()
      : null
    // The visible text equivalent is either an explicit disclosure, or a figcaption that is
    // byte-equal to the authored text_equivalent (pack v2 defines media[].caption as the
    // equivalent). Both are readable text on screen; neither is inferred.
    let textEquivalent = disclosureText
    let source = disclosureText ? 'disclosure' : null
    if (!textEquivalent && captionText && expected.includes(captionText)) {
      textEquivalent = captionText
      source = 'caption'
    }
    return {
      kind: media.getAttribute('data-cb-media-kind'),
      caption: captionText,
      text_equivalent: textEquivalent,
      text_equivalent_present: Boolean(textEquivalent),
      text_equivalent_source: source,
      disclosure_present: Boolean(equivalent)
    }
  })
  const route = document.querySelector('[data-cb-scope]') || document.body
  const clipped = [...document.querySelectorAll('[data-cb-scope] *')].filter((el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && (r.right > document.documentElement.clientWidth + 1 || r.left < -1)
  }).map((el) => (el.tagName + ' ' + (el.innerText || '').trim().slice(0, 50))).slice(0, 8)
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    inner_width: window.innerWidth,
    media_frame_count: frames.length,
    media: frames,
    all_text_equivalents_present: frames.length > 0 && frames.every((f) => f.text_equivalent_present && f.text_equivalent),
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    clipped,
    text_head: (route.innerText || '').slice(0, 300)
  }
})()`

const evidence = { generated_at: new Date().toISOString(), kind: 'renderer audit of the shipped desktop/plugin.js with the real imported lesson.page document (no live app window)', chromium: (await send('Browser.getVersion')).product, frames: [] }
for (const frame of frames.frames) {
  const file = resolve(htmlDir, `${frame.id}.html`)
  writeFileSync(file, frame.html)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: `file://${file}` })
  await sleep(500)
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 2, mobile: false })
  await sleep(200)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({ id: frame.id, page: frame.page, width: frame.width, height: frame.height, font: frame.font || 'root', ...measured })
  console.log(`${frame.id}: frames=${measured.media_frame_count} equivalents=${measured.all_text_equivalents_present} overflow=${measured.horizontal_overflow} clipped=${measured.clipped.length}`)
}
writeFileSync(resolve(outDir, 'render-evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
