#!/usr/bin/env node
/**
 * H-196 — screenshot the Workshop frames in Chromium and read the painted DOM.
 *
 *   node scripts/h197-cover-shot.mjs
 *
 * Input is `audit/visual/h197-covers/frames.json` (built by `scripts/h197-cover-frames.py`):
 * one self-contained HTML document per width / mode / text scale / motion posture, produced by
 * mounting the shipped module in jsdom against recorded real backend payloads. This script paints
 * them in a real browser and records what the layout actually did: horizontal overflow, the cover
 * kind that painted, whether an image loaded, the badge word, the primary action, one-h1/one-primary
 * counts, and the rendered first line of text.
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { spawn } from 'node:child_process'

const ROOT = resolve(process.argv[2] || '.')
const outDir = resolve(ROOT, 'audit/visual/h197-covers')
const frames = JSON.parse(readFileSync(resolve(outDir, 'frames.json'), 'utf8')).frames
const htmlDir = resolve(outDir, 'html')
mkdirSync(htmlDir, { recursive: true })
const PORT = process.env.H197_CDP_PORT || '9427'

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
    const { resolve: ok, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else ok(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((ok, reject) => {
    const id = nextId++
    pending.set(id, { resolve: ok, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}

const MEASURE = `(() => {
  const root = document.documentElement
  const scope = document.querySelector('[data-cb-scope]')
  const style = scope ? getComputedStyle(scope) : null
  const tokens = {}
  if (style) {
    for (const name of ['paper','paper-raised','ink','ink-soft','rule','accent','accent-soft','field','lamp','lamp-soft','coral']) {
      tokens[name] = style.getPropertyValue('--cb-' + name).trim()
    }
  }
  const text = (node) => (node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : null)
  const covers = [...document.querySelectorAll('[data-cb-workshop-cover]')]
  const imgs = [...document.querySelectorAll('img')]
  const buttons = [...document.querySelectorAll('button')]
  const primaries = buttons.filter((b) => b.getAttribute('data-cb-action') === 'primary')
  const figure = covers[0]
  const figRect = figure ? figure.getBoundingClientRect() : null
  const hero = document.querySelector('[data-cb-workshop-hero]')
  return {
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    scope_motion: scope ? scope.getAttribute('data-cb-motion') : null,
    root_font_px: getComputedStyle(root).fontSize,
    tokens,
    paper_painted: style ? style.backgroundColor : null,
    ink_painted: style ? style.color : null,
    h1_count: document.querySelectorAll('h1').length,
    h2_count: document.querySelectorAll('h2').length,
    tab_current: text(document.querySelector('[data-cb-workshop-tab][aria-current="page"]')),
    tabs: [...document.querySelectorAll('[data-cb-workshop-tab]')].map((n) => text(n)),
    hero_present: Boolean(hero),
    hero_title: text(document.querySelector('#cb-workshop-hero-title')),
    hero_primary: hero ? [...hero.querySelectorAll('button')].map((b) => text(b)) : [],
    cover_count: covers.length,
    cover_kinds: covers.map((n) => n.getAttribute('data-cb-workshop-cover-kind')),
    cover_first_w_px: figRect ? Math.round(figRect.width) : null,
    cover_first_h_px: figRect ? Math.round(figRect.height) : null,
    images: imgs.map((img) => ({
      alt: img.getAttribute('alt'),
      src_head: (img.getAttribute('src') || '').slice(0, 24),
      loaded: img.complete && img.naturalWidth > 0,
      natural: [img.naturalWidth, img.naturalHeight],
      displayed: [Math.round(img.getBoundingClientRect().width), Math.round(img.getBoundingClientRect().height)]
    })),
    empty_alt_images: imgs.filter((img) => !(img.getAttribute('alt') || '').trim()).length,
    badges: [...document.querySelectorAll('[data-cb-workshop-badge]')].map((n) => ({
      word: text(n),
      kind: n.getAttribute('data-cb-workshop-badge')
    })),
    detail_title: text(document.querySelector('#cb-workshop-detail-title')),
    detail_primary: [...document.querySelectorAll('[data-cb-workshop-detail] button')].map((b) => text(b)),
    detail_sections: document.querySelectorAll('[data-cb-workshop-detail] ol li').length,
    detail_fact_labels: [...document.querySelectorAll('[data-cb-workshop-detail] dt')].map((n) => text(n)),
    notice: text(document.querySelector('[data-cb-workshop-notice]')),
    library_rows: document.querySelectorAll('[data-cb-pack-row-action]').length,
    library_empty: text(document.querySelector('.empty-state')),
    card_count: document.querySelectorAll('[data-cb-workshop-card]').length,
    card_titles: [...document.querySelectorAll('[data-cb-workshop-card]')].map((n) => text(n.querySelector('h3, h4, strong'))),
    shelf_count: [...document.querySelectorAll('[data-cb-workshop-shelf-section]')].map((n) => n.getAttribute('data-cb-workshop-shelf-section')),
    primary_count: primaries.length,
    button_without_a_name: buttons.filter((b) => !text(b) && !b.getAttribute('aria-label')).length,
    horizontal_overflow: root.scrollWidth > root.clientWidth,
    scroll_width: root.scrollWidth,
    client_width: root.clientWidth,
    document_height: root.scrollHeight,
    text_head: (document.body.innerText || '').slice(0, 240)
  }
})()`

const evidence = {
  generated_at: new Date().toISOString(),
  kind:
    'shipped desktop/plugin.js mounted in jsdom (real effects, real clicks) against recorded real backend payloads, painted in headless Chromium',
  plugin_sha256: process.env.H197_PLUGIN_SHA || null,
  chromium: (await send('Browser.getVersion')).product,
  frames: []
}

for (const frame of frames) {
  const file = resolve(htmlDir, `${frame.id}.html`)
  writeFileSync(file, frame.html)
  await send('Emulation.setDeviceMetricsOverride', {
    width: frame.width,
    height: frame.height,
    deviceScaleFactor: 1,
    mobile: false
  })
  await send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: frame.motion === 'reduced' ? 'reduce' : 'no-preference' }]
  })
  await send('Page.navigate', { url: `file://${file}` })
  await sleep(700)
  // The page's own content height, not a guessed box: a storefront frame should not carry a
  // footer of empty paper because the screenshot was taller than the page.
  const contentHeight = await evaluate('Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)')
  const height = Math.max(520, Math.min(6000, Math.round(contentHeight)))
  await send('Emulation.setDeviceMetricsOverride', {
    width: frame.width,
    height,
    deviceScaleFactor: 1,
    mobile: false
  })
  await sleep(300)
  const measured = await evaluate(MEASURE)
  await send('Emulation.setDeviceMetricsOverride', {
    width: frame.width,
    height,
    deviceScaleFactor: 2,
    mobile: false
  })
  await sleep(200)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  evidence.frames.push({
    id: frame.id,
    view: frame.view,
    mode: frame.mode,
    width: frame.width,
    height,
    font: frame.font,
    motion: frame.motion,
    interactions: frame.notes,
    ...measured
  })
  console.log(`${frame.id}: overflow=${measured.horizontal_overflow} covers=${measured.cover_kinds.join('/')} primary=${measured.primary_count}`)
}

writeFileSync(resolve(outDir, 'evidence.json'), JSON.stringify(evidence, null, 2))
console.log(JSON.stringify({ frames: evidence.frames.length, path: resolve(outDir, 'evidence.json') }))
chromium.kill()
socket.close()
process.exit(0)
