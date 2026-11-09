#!/usr/bin/env node
/**
 * GM-002 — paint the Home frames in Chromium and read the painted DOM.
 *
 *   node scripts/gm002-shot.mjs docs/visual-review/gm-002
 *
 * Input is `frames.json` from `scripts/gm002-frames.py`: one self-contained HTML document per
 * screen / width / mode / text scale / motion posture, produced by mounting the shipped module in
 * jsdom. This script records what the layout actually did: horizontal overflow, the one primary,
 * card counts, the focus ring on the keyboard frame, the root font at 200 %, and banned vanity
 * claims. It is a renderer audit, not a live-window capture.
 */
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const outDir = resolve(process.argv[2] || 'docs/visual-review/gm-002')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8'))
const htmlDir = resolve(outDir, 'html')
rmSync(htmlDir, { recursive: true, force: true })
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.GM002_CDP_PORT || '9441'

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
    for (const name of ['paper','paper-raised','ink','ink-soft','rule','accent','lamp','field','ochre','coral']) {
      tokens[name] = scopeStyle.getPropertyValue('--cb-' + name).trim()
    }
  }
  const buttons = [...document.querySelectorAll('button')]
  const named = (node) => (node.innerText || '').trim() || node.getAttribute('aria-label') || ''
  const primaries = buttons.filter((button) => button.getAttribute('data-cb-action') === 'primary')
  const text = document.body.innerText || ''
  const banned = ['star', 'rating', 'recently played', 'streak', 'mastery', 'level up', 'xp', 'points earned']
    .filter((word) => new RegExp('\\\\b' + word + '\\\\b', 'i').test(text))
  const shelf = document.querySelector('[data-cb-home-shelf-row]')
  const active = document.activeElement
  const activeStyle = active && active !== document.body ? getComputedStyle(active) : null
  return {
    root_font_px: getComputedStyle(document.documentElement).fontSize,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    motion_attr: scope ? scope.getAttribute('data-cb-motion') : null,
    tokens,
    paper_painted: scopeStyle ? scopeStyle.backgroundColor : null,
    ink_painted: scopeStyle ? scopeStyle.color : null,
    home: document.querySelector('[data-cb-home]') ? document.querySelector('[data-cb-home]').getAttribute('data-cb-home') : null,
    course_home: Boolean(document.querySelector('[data-cb-course-home]')),
    continue_plate: document.querySelectorAll('[data-cb-continue]').length,
    card_count: document.querySelectorAll('[data-cb-home-card]').length,
    card_titles: [...document.querySelectorAll('[data-cb-home-card] h3')].map((node) => node.innerText.trim()),
    mode_badges: [...document.querySelectorAll('[data-cb-home-card] .badge')].map((node) => node.innerText.trim()),
    primary_count: primaries.length,
    primary_labels: primaries.map(named),
    primary_height: primaries[0] ? getComputedStyle(primaries[0]).minHeight : null,
    secondary_count: buttons.filter((button) => button.getAttribute('data-cb-action') === 'secondary').length,
    unnamed_buttons: buttons.filter((button) => !named(button)).length,
    see_all: [...buttons].some((button) => (button.innerText || '').trim() === 'See all'),
    shelf_scrolls: shelf ? shelf.scrollWidth > shelf.clientWidth + 1 : null,
    shelf_scroll_width: shelf ? shelf.scrollWidth : null,
    shelf_client_width: shelf ? shelf.clientWidth : null,
    path_rows: document.querySelectorAll('[data-cb-path-item]').length,
    banned_words: banned,
    horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    active_element: activeStyle ? {
      tag: active.tagName.toLowerCase(),
      label: active.getAttribute('aria-label'),
      outline: activeStyle.outlineStyle + ' ' + activeStyle.outlineWidth + ' ' + activeStyle.outlineColor
    } : null,
    text_head: text.replace(/\\s+/g, ' ').slice(0, 220)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind: 'static render of the shipped Desktop module in Chromium (no backend, no chat, no RPC)',
  contract: 'cb.rpc v20 / GM contract manifest (Home is not course-bound; mode badge is a real world.read when wired)',
  plugin_sha256: process.env.GM002_PLUGIN_SHA || null,
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
      await sleep(80)
    }
  }
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: frame.height, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({ id: frame.id, screen: frame.screen, state: frame.state, width: frame.width, mode: frame.mode, scale: frame.scale, ...measured })
  console.log(`${frame.id}: home=${measured.home} cards=${measured.card_count} primaries=${measured.primary_count} overflow=${measured.horizontal_overflow} font=${measured.root_font_px} focus=${measured.active_element ? measured.active_element.label + ' ' + measured.active_element.outline : 'none'}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), `${JSON.stringify(evidence, null, 2)}\n`)
socket.close()
chromium.kill()
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
