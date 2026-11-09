#!/usr/bin/env node
/**
 * M2-U1 evidence: screenshot the shipped Field Desk in Chromium.
 *
 *   node scripts/m2fd-shot.mjs audit/visual/m2-field-desk
 *
 * The frames in `frames.json` are static renders of the shipped `desktop/plugin.js` (see
 * `scripts/m2fd-frames.py`) wrapped in the same scoped root the route paints. This is a renderer
 * audit at the widths, modes and text scales the card names, not a live-app capture: no backend,
 * no chat, no RPC. Every number in `evidence.json` is read from the painted DOM.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/m2-field-desk')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.M2FD_CDP_PORT || '9417'

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
  const desk = document.querySelector('[data-cb-desk]')
  const cont = document.querySelector('[data-cb-continue]')
  const title = document.querySelector('[data-cb-continue-section]')
  const titleStyle = title ? getComputedStyle(title) : null
  const pathItems = [...document.querySelectorAll('[data-cb-path-item]')]
  const current = document.querySelectorAll('[data-cb-path-current="true"]')
  const drawer = document.querySelector('[data-cb-sources-drawer]')
  const drawerToggle = document.querySelector('[aria-controls="cb-desk-sources"]')
  const allCourses = document.querySelector('[data-cb-all-courses]')
  const buttons = [...document.querySelectorAll('button')]
  const unnamed = buttons.filter((button) => !(button.innerText || '').trim() && !button.getAttribute('aria-label'))
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    tokens,
    paper_painted: style ? style.backgroundColor : null,
    ink_painted: style ? style.color : null,
    desk_state: desk ? desk.getAttribute('data-cb-desk') : null,
    continue_present: Boolean(cont),
    continue_width_px: cont ? Math.round(cont.getBoundingClientRect().width) : null,
    trailhead_label: (document.querySelector('[data-cb-trailhead-label]') || {}).innerText || null,
    course_title: (document.querySelector('[data-cb-desk-course]') || {}).innerText || null,
    course_title_lines: (() => {
      const node = document.querySelector('[data-cb-desk-course]')
      if (!node) return null
      const size = parseFloat(getComputedStyle(node).lineHeight)
      return size ? Math.round(node.getBoundingClientRect().height / size) : null
    })(),
    next_stop: (document.querySelector('[data-cb-trailhead-next]') || {}).innerText || null,
    trailhead_actions: [...document.querySelectorAll('[data-cb-trailhead-actions] button')].map((b) => (b.innerText || '').trim()),
    trailhead_action_rows: document.querySelectorAll('[data-cb-trailhead-actions]').length,
    contours: document.querySelectorAll('[data-cb-course-contour]').length,
    first_run_contour: Boolean(document.querySelector('[data-cb-first-run-contour]')),
    companion_present: Boolean(document.querySelector('[data-cb-companion] canvas')),
    companion_motion: (document.querySelector('[data-cb-companion]') || {}).getAttribute?.('data-cb-companion-motion') || null,
    slot_covers: [...document.querySelectorAll('[data-cb-slot-cover]')].map((node) => node.getAttribute('data-cb-slot-cover')),
    slot_cover_alts: [...document.querySelectorAll('[data-cb-slot-cover] img')].map((node) => node.getAttribute('alt')),
    shelf_contours: document.querySelectorAll('[data-cb-classroom-shelf] [data-cb-course-contour]').length,
    field_notes_line: (document.querySelector('[data-cb-field-notes-line]') || {}).innerText || null,
    field_note_rows: document.querySelectorAll('[data-cb-field-note]').length,
    empty_alt_images: document.querySelectorAll('img[alt=""]').length,
    shelf_courses: document.querySelectorAll('[data-cb-slot-tab]').length,
    trailhead_order: (() => {
      const path = document.querySelector('[data-cb-path]')
      const shelf = document.querySelector('[data-cb-slot-rail-section]')
      const top = (node) => (node ? Math.round(node.getBoundingClientRect().top) : null)
      return { plate: top(cont), path: top(path), shelf: top(shelf) }
    })(),
    continue_section: title ? (title.innerText || '').trim() : null,
    continue_section_font_px: titleStyle ? titleStyle.fontSize : null,
    continue_section_line_height: titleStyle ? titleStyle.lineHeight : null,
    position_label: (document.querySelector('[data-cb-continue-position]') || {}).innerText || null,
    estimate_label: (document.querySelector('[data-cb-continue-minutes]') || {}).innerText || null,
    touched: (document.querySelector('[data-cb-continue-touched]') || {}).innerText || null,
    next_label: (document.querySelector('[data-cb-continue-next]') || {}).innerText || null,
    path_items: pathItems.length,
    path_states: pathItems.map((item) => item.getAttribute('data-cb-path-state')),
    path_row_overlaps: (() => {
      let bad = 0
      pathItems.forEach((item) => {
        const spans = [...item.children]
        if (spans.length < 3) return
        const title = spans[1].getBoundingClientRect()
        const state = spans[2].getBoundingClientRect()
        if (title.right > state.left + 1) bad += 1
      })
      return bad
    })(),
    path_summary: (document.querySelector('[data-cb-path-summary]') || {}).innerText || null,
    path_current_count: current.length,
    sources_drawer: drawer ? drawer.getAttribute('data-cb-sources-drawer') : null,
    sources_expanded: drawerToggle ? drawerToggle.getAttribute('aria-expanded') : null,
    source_rows: document.querySelectorAll('[data-cb-desk-source]').length,
    all_courses_present: Boolean(allCourses),
    button_count: buttons.length,
    buttons_without_a_name: unnamed.length,
    active_element: (() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const style = getComputedStyle(el)
      return {
        tag: el.tagName.toLowerCase(),
        text: (el.innerText || '').trim().slice(0, 60),
        aria_current: el.getAttribute('aria-current'),
        outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor,
        box_shadow: style.boxShadow
      }
    })(),
    table_count: document.querySelectorAll('table').length,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    text_head: (document.body.innerText || '').slice(0, 220)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
  contract: 'cb.rpc v8 (library.list item, course.outline objective, lesson.page sources)',
  plugin_sha256: process.env.M2FD_PLUGIN_SHA || null,
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
  if (frame.focus) {
    await evaluate(frame.focus)
    await sleep(120)
  }
  if (frame.tabs) {
    for (let index = 0; index < frame.tabs; index += 1) {
      for (const type of ['keyDown', 'keyUp']) {
        await send('Input.dispatchKeyEvent', {
          type,
          key: 'Tab',
          code: 'Tab',
          windowsVirtualKeyCode: 9,
          nativeVirtualKeyCode: 9
        })
      }
      await sleep(60)
    }
  }
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({ id: frame.id, state: frame.state, width: frame.width, height: frame.height, ...measured })
  console.log(`${frame.id}: desk=${measured.desk_state} overflow=${measured.horizontal_overflow} path=${measured.path_items} drawer=${measured.sources_drawer} font=${measured.root_font_px}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
