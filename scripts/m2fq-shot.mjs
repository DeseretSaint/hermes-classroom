#!/usr/bin/env node
/**
 * M2-U2 evidence: screenshot the shipped Field Quest view in Chromium.
 *
 *   node scripts/m2fq-shot.mjs audit/visual/m2-field-quest
 *
 * The frames in `frames.json` are static renders of the shipped `desktop/plugin.js` (see
 * `scripts/m2fq-frames.py`) wrapped in the same scoped root the route paints. This is a renderer
 * audit at the widths, modes and text scales the card names, not a live-app capture: no backend,
 * no chat, no RPC. Every number in `evidence.json` is read from the painted DOM.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'audit/visual/m2-field-quest')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.M2FQ_CDP_PORT || '9427'

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
  const scopeStyle = scope ? getComputedStyle(scope) : null
  const tokens = {}
  if (scopeStyle) {
    for (const name of ['paper','paper-raised','ink','ink-soft','rule','accent','accent-soft','field','ochre','coral']) {
      tokens[name] = scopeStyle.getPropertyValue('--cb-' + name).trim()
    }
  }
  const quest = document.querySelector('[data-cb-lesson-view="field_quest"]')
  const root = quest || document.querySelector('[data-cb-lesson-view]')
  const missions = [...document.querySelectorAll('[data-cb-mission]')]
  const checkpoints = missions.filter((mission) => mission.getAttribute('data-cb-mission-checkpoint') === 'true')
  const buttons = [...document.querySelectorAll('button')]
  const unnamed = buttons.filter((button) => !(button.innerText || '').trim() && !button.getAttribute('aria-label'))
  const motionHosts = [...document.querySelectorAll('*')].filter((node) => {
    const style = getComputedStyle(node)
    const trans = parseFloat(style.transitionDuration) || 0
    const anim = style.animationName && style.animationName !== 'none' ? style.animationDuration : '0s'
    return trans > 0 || (style.animationName && style.animationName !== 'none' && parseFloat(anim) > 0)
  })
  const text = document.body.innerText || ''
  const banned = ['mastery', 'mastered', 'streak', 'level up', ' xp', 'points earned']
    .filter((word) => text.toLowerCase().includes(word))
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    motion_attr: quest ? quest.getAttribute('data-cb-motion') : null,
    tokens,
    paper_painted: scopeStyle ? scopeStyle.backgroundColor : null,
    ink_painted: scopeStyle ? scopeStyle.color : null,
    lesson_view: root ? root.getAttribute('data-cb-lesson-view') : null,
    document_id: root ? root.getAttribute('data-cb-document') : null,
    mission_count: missions.length,
    mission_ids: missions.map((m) => m.getAttribute('data-cb-mission')),
    mission_roles: missions.map((m) => m.getAttribute('data-cb-mission-role')),
    mission_state_words: missions.map((m) => (m.querySelector('[data-cb-mission-state]') || {}).innerText || null),
    mission_indices: missions.map((m) => m.getAttribute('data-cb-mission-index')),
    checkpoint_ids: checkpoints.map((m) => m.getAttribute('data-cb-mission-check')),
    checkpoint_count: checkpoints.length,
    checkpoint_gate_text: (document.querySelector('[data-cb-mission-gate]') || {}).innerText || null,
    quest_progress: root ? root.getAttribute('data-cb-quest-progress') : null,
    quest_progress_text: (() => {
      const span = root ? [...root.querySelectorAll('span')].find((n) => /independent|recorded/.test(n.innerText || '')) : null
      return span ? span.innerText.trim() : null
    })(),
    quest_checkpoints_attr: root ? root.getAttribute('data-cb-quest-checkpoints') : null,
    check_node_count: document.querySelectorAll('[data-cb-mission-gate] [data-variant="default"], [data-cb-mission-gate] textarea').length,
    check_form_present: Boolean(document.querySelector('[data-cb-mission-gate] textarea')),
    check_error_text: (document.querySelector('[data-cb-check-error]') || {}).innerText || null,
    media_frames: document.querySelectorAll('[data-cb-block-media]').length,
    media_captions: [...document.querySelectorAll('[data-cb-media-caption]')].map((n) => n.innerText.trim()),
    source_chips: [...document.querySelectorAll('[data-block-source], [data-cb-block-sources]')]
      .map((n) => (n.innerText || '').trim()).filter(Boolean),
    mission_row_overlaps: (() => {
      let bad = 0
      missions.forEach((mission) => {
        const heading = mission.querySelector('h3')
        const state = mission.querySelector('[data-cb-mission-state]')
        if (!heading || !state) return
        const h = heading.getBoundingClientRect()
        const s = state.getBoundingClientRect()
        const sameRow = h.bottom > s.top + 1 && s.bottom > h.top + 1
        if (sameRow && h.right > s.left + 1) bad += 1
      })
      return bad
    })(),
    disabled_buttons: buttons.filter((button) => button.disabled).length,
    disabled_mission_controls: buttons.filter(
      (button) => button.disabled && !button.closest('[data-cb-mission-gate]')
    ).length,
    unnamed_buttons: unnamed.length,
    button_count: buttons.length,
    transitioned_or_animated_elements: motionHosts.length,
    banned_words: banned,
    table_count: document.querySelectorAll('table').length,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    active_element: (() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const style = getComputedStyle(el)
      return {
        tag: el.tagName.toLowerCase(),
        text: (el.innerText || el.value || '').trim().slice(0, 60),
        aria_label: el.getAttribute('aria-label'),
        outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor,
        box_shadow: style.boxShadow
      }
    })(),
    text_head: text.slice(0, 260)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
  contract: 'cb.rpc v8 lesson document (blocks, one check_id, source_ids, views.field_quest)',
  plugin_sha256: process.env.M2FQ_PLUGIN_SHA || null,
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
  console.log(`${frame.id}: view=${measured.lesson_view} missions=${measured.mission_count} checkpoints=${measured.checkpoint_count} overflow=${measured.horizontal_overflow} font=${measured.root_font_px}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
