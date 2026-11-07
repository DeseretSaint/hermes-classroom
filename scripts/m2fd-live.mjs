#!/usr/bin/env node
/**
 * Capture the live Field Desk from the isolated Desktop window and record what the DOM proves.
 *
 *   CB009_CDP_PORT=9345 node scripts/m2fd-live.mjs audit/visual/m2-field-desk
 *
 * This is the live read: the real Hermes Desktop renderer, the real coursebook plugin half, and a
 * real isolated backend. The screenshot and the measurements come from the same paint.
 */
import { writeFileSync, readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9345'
const outDir = resolve(process.argv[2] || 'audit/visual/m2-field-desk')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

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
  const desk = document.querySelector('[data-cb-desk]')
  const cont = document.querySelector('[data-cb-continue]')
  const title = document.querySelector('[data-cb-continue-section]')
  const pathItems = [...document.querySelectorAll('[data-cb-path-item]')]
  const drawer = document.querySelector('[data-cb-sources-drawer]')
  const style = scope ? getComputedStyle(scope) : null
  const tokens = {}
  if (style) {
    for (const name of ['paper','paper-raised','ink','ink-soft','rule','accent','accent-soft','field','ochre','coral']) {
      tokens[name] = style.getPropertyValue('--cb-' + name).trim()
    }
  }
  return {
    url: location.href,
    rendered_mode: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
    desk_state: desk ? desk.getAttribute('data-cb-desk') : null,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    tokens,
    continue_section: title ? (title.innerText || '').trim() : null,
    position_label: (document.querySelector('[data-cb-continue-position]') || {}).innerText || null,
    estimate_label: (document.querySelector('[data-cb-continue-minutes]') || {}).innerText || null,
    touched: (document.querySelector('[data-cb-continue-touched]') || {}).innerText || null,
    touched_source: (document.querySelector('[data-cb-continue-touched]') || {}).getAttribute
      ? document.querySelector('[data-cb-continue-touched]').getAttribute('data-cb-continue-touched')
      : null,
    next_label: (document.querySelector('[data-cb-continue-next]') || {}).innerText || null,
    path_items: pathItems.length,
    path_states: pathItems.map((item) => item.getAttribute('data-cb-path-state')),
    path_titles: pathItems.map((item) => (item.children[1] ? item.children[1].innerText : '').trim()),
    path_current_count: document.querySelectorAll('[data-cb-path-current="true"]').length,
    path_summary: (document.querySelector('[data-cb-path-summary]') || {}).innerText || null,
    sources_drawer: drawer ? drawer.getAttribute('data-cb-sources-drawer') : null,
    all_courses_present: Boolean(document.querySelector('[data-cb-all-courses]')),
    table_count: document.querySelectorAll('table').length,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: (document.querySelector('[data-cb-route]') || {}).innerText
      ? document.querySelector('[data-cb-route]').innerText.slice(0, 400)
      : (document.body.innerText || '').slice(0, 400)
  }
})()`

const measured = await evaluate(MEASURE)
await send('Emulation.setDeviceMetricsOverride', {
  width: Number(process.env.CB_LIVE_WIDTH || 1280),
  height: Number(process.env.CB_LIVE_HEIGHT || 900),
  deviceScaleFactor: 2,
  mobile: false
})
await new Promise((done) => setTimeout(done, 250))
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
const name = process.env.CB_LIVE_NAME || 'live-01-real.png'
writeFileSync(resolve(outDir, name), Buffer.from(shot.data, 'base64'))

const file = resolve(outDir, 'live-evidence.json')
const previous = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : { kind: 'live isolated Desktop capture', frames: [] }
previous.captured_at = new Date().toISOString()
previous.plugin_sha256 = process.env.CB_LIVE_PLUGIN_SHA || null
previous.frames = previous.frames.filter((frame) => frame.id !== name).concat([{ id: name, ...measured }])
writeFileSync(file, `${JSON.stringify(previous, null, 2)}\n`)
console.log(`${name}: desk=${measured.desk_state} section=${measured.continue_section} estimate=${measured.estimate_label} path=${measured.path_items} overflow=${measured.horizontal_overflow}`)
socket.close()
