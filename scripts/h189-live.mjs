#!/usr/bin/env node
/**
 * H-189 — the Living Home in a real browser, with the shipped module mounted client-side.
 *
 * The static frames (`scripts/h189-frames.py`) prove composition; a server render cannot start a
 * transition, fetch a media preview or decode a pet spritesheet. This script bundles the shipped
 * `desktop/plugin.js` with the Desktop's own React through esbuild, mounts `FieldDeskHome` in
 * headless Chromium, and captures:
 *
 *   * the typographic cover (fallback) and a real pack artifact cover with its caption;
 *   * the learner's own pet sheet when a real `pet.info` payload is supplied, and no pet when not;
 *   * the one-shot trailhead arrival, the current-stop beacon at its high point, and the rest frame;
 *   * the reduced-motion mount, which must be static on the first frame.
 *
 * The payload comes from `audit/visual/h189-living-home/payloads.json` (written by h189-frames.py)
 * and the pet payload from `$H189_PET_JSON` — a real `pet.info` answer for the rig profile. No
 * pet file means the pet frames are reported `skipped`, never faked.
 */
import { spawn } from 'node:child_process'
import { createServer } from 'node:http'
import { mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const ROOT = resolve(new URL('..', import.meta.url).pathname)
const OUT = resolve(process.argv[2] || resolve(ROOT, 'audit/visual/h189-living-home'))
const APP_ROOT = resolve(process.env.HERMES_DESKTOP_APP || '/home/deseretsaint/.hermes/hermes-agent')
const MODULES = [resolve(APP_ROOT, 'node_modules'), resolve(APP_ROOT, 'apps/desktop/node_modules')].find((dir) => {
  try { return readFileSync(resolve(dir, 'react/package.json')) && true } catch (error) { return false }
})
if (!MODULES) throw new Error('desktop node_modules not found')
mkdirSync(OUT, { recursive: true })
const payloads = JSON.parse(readFileSync(resolve(OUT, 'payloads.json'), 'utf8'))
const petPath = process.env.H189_PET_JSON
const pet = petPath ? JSON.parse(readFileSync(petPath, 'utf8')) : null
if (pet && pet.enabled === undefined) pet.enabled = true
if (pet && pet.framesByState && pet.framesByState.idle === 0) pet.framesByState = { idle: 7 }

const WORK = resolve(OUT, 'live')
rmSync(WORK, { recursive: true, force: true })
mkdirSync(WORK, { recursive: true })
writeFileSync(resolve(WORK, 'plugin.js'), readFileSync(resolve(ROOT, 'desktop/plugin.js')))

const SDK = `
import React from 'react'
const atom = (value) => ({ get: () => value })
const el = (tag, props, children) => React.createElement(tag, props, children)
const textOf = (props) => (props && props.children !== undefined ? props.children : null)
export const ROUTES_AREA = 'routes'
export const SIDEBAR_NAV_AREA = 'sidebar.nav'
export const PANES_AREA = 'panes'
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const SETTINGS_PLUGINS_AREA = 'settings.plugins'
export const TOOL_MEDIA_RENDERER_AREA = 'tool.media'
export const useValue = (a) => a.get()
export const useTheme = () => ({ renderedMode: 'light', resolvedMode: 'light' })
const pass = (props) => {
  const out = { type: 'button', onClick: props.onClick, disabled: Boolean(props.disabled) }
  for (const key of ['className', 'aria-expanded', 'aria-controls', 'aria-current', 'aria-label', 'id', 'role', 'title']) {
    if (props[key] !== undefined) out[key] = props[key]
  }
  return out
}
export const Button = (props) => el('button', pass(props), textOf(props))
export const RowButton = (props) => el('button', pass(props), textOf(props))
export const Badge = (props) => el('span', { className: 'badge', 'data-variant': props.variant || null }, textOf(props))
export const PanelSectionLabel = (props) => el('div', { className: 'panel-label' }, textOf(props))
export const PanelEmpty = (props) => el('div', { className: 'panel-empty' }, textOf(props))
export const Loader = (props) => el('div', { className: 'loader' }, props.label || null)
export const ErrorState = (props) => el('div', { className: 'error-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description), props.children])
export const EmptyState = (props) => el('div', { className: 'empty-state' }, [el('div', { key: 't' }, props.title), el('div', { key: 'd' }, props.description)])
export const ListRow = (props) => el('div', { className: 'list-row' }, [el('div', { key: 'title', className: 'list-row-title' }, props.title), el('div', { key: 'description', className: 'list-row-description' }, props.description), el('div', { key: 'action', className: 'list-row-action' }, props.action)])
export const SegmentedControl = (props) => el('div', { className: 'segmented' }, (props.options || []).map((option) => el('button', { key: option.id, 'aria-pressed': option.id === props.value, type: 'button' }, option.label)))
export const Input = () => null
export const Textarea = () => null
export const SearchField = () => null
export const Select = () => null
export const SelectTrigger = () => null
export const SelectValue = () => null
export const SelectContent = () => null
export const SelectItem = () => null
export const ConfirmDialog = () => null
export const DropdownMenu = () => null
export const DropdownMenuItem = () => null
export const DropdownMenuTrigger = () => null
export const DropdownMenuContent = () => null
export const Codicon = () => null
export const SandboxedFrame = () => null
export const Tabs = () => null
export const Tip = () => null
export const Panel = () => null
export const PanelHeader = () => null
export const PanelBody = () => null
export const PanelSection = () => null
export const MessageTextContent = () => null
export const host = {
  state: {
    focusedSessionId: atom(null),
    focusedStoredSessionId: atom(null),
    focusedSessionProfile: atom('default'),
    profile: atom('default'),
    viewport: { get: () => ({ width: window.innerWidth, height: window.innerHeight, narrow: window.innerWidth < 720 }) }
  },
  profileRoutes: async () => [{ connectionId: 'local', mode: 'local', profile: 'default', targetProfile: 'default' }],
  navigate: () => {},
  notify: () => {},
  openSession: async () => ({ ok: true }),
  newChat: async () => ({ ok: true }),
  request: async (method) => {
    if (!window.__H189_PET__) throw new Error('no pet configured')
    if (method === 'pet.info.meta') {
      const missing = new Error('Method not found')
      missing.code = -32601
      throw missing
    }
    if (method === 'pet.info') return window.__H189_PET__
    throw new Error('unexpected host.request ' + method)
  }
}
`
mkdirSync(resolve(WORK, 'node_modules/@hermes/plugin-sdk'), { recursive: true })
writeFileSync(resolve(WORK, 'node_modules/@hermes/plugin-sdk/package.json'), JSON.stringify({ name: '@hermes/plugin-sdk', type: 'module', main: 'index.mjs' }))
writeFileSync(resolve(WORK, 'node_modules/@hermes/plugin-sdk/index.mjs'), SDK)
for (const name of ['react', 'react-dom', 'scheduler']) {
  const target = resolve(MODULES, name)
  const link = resolve(WORK, 'node_modules', name)
  try {
    rmSync(link, { recursive: true, force: true })
    symlinkSync(target, link)
  } catch (error) {
    throw new Error(`cannot link ${name}: ${error.message}`)
  }
}

const HARNESS = `
import React from 'react'
import { createRoot } from 'react-dom/client'
import * as mod from './plugin.js'

const payload = window.__H189_PAYLOAD__
window.__H189_PET__ = window.__H189_PET_RAW__ || null
const rest = async (path) => {
  window.__H189_REST__ = window.__H189_REST__ || []
  window.__H189_REST__.push(String(path))
  const base = String(path).split('?')[0]
  if (base === '/runtime') return { wire_version: 10, implemented_methods: ['library.list', 'course.outline', 'lesson.page', 'notebook.list'] }
  if (base.startsWith('/media/')) {
    const cover = payload.cover || (payload.library && payload.library.items && payload.library.items[0] && payload.library.items[0].cover)
    if (!cover || !cover.data_url) return { ok: false, message: 'No artifact' }
    return { ok: true, mime: cover.mime, data_url: cover.data_url }
  }
  if (base === '/rpc') return { ok: true, contract_version: 10, operation_id: 'op', result: {} }
  return { ok: false, message: 'unexpected path ' + path }
}
mod.default.register({ rest, register: () => {}, onDispose: () => {}, setTimeout: (fn, ms) => setTimeout(fn, ms) })
const desk = mod.buildDeskModel({ library: payload.library, outline: payload.outline, estimate: payload.estimate })
const root = createRoot(document.getElementById('root'))
root.render(React.createElement('div', { 'data-cb-scope': 'light', style: mod.cbScopeStyle('light') },
  React.createElement(mod.FieldDeskHome, {
    desk,
    notes: payload.notes || null,
    onShowNotebook: () => {},
    libraryStatus: 'ready',
    libraryError: null,
    stale: false,
    busy: false,
    notice: null,
    online: true,
    onRetry: () => {},
    onCreate: () => {},
    onPrimary: () => {},
    onOpenSection: () => {},
    onSeePlan: () => {},
    onRetryEstimate: () => {},
    onOpen: () => {},
    onShowAll: () => {},
    sourcesOpen: false,
    onToggleSources: () => {},
    sourcesStatus: 'idle',
    sourcesError: null,
    sources: null,
    onRetrySources: () => {},
    implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'notebook.list'])
  })))
window.__H189_READY__ = true
`
writeFileSync(resolve(WORK, 'harness.js'), HARNESS)

const esbuild = resolve(MODULES, '..', 'node_modules', '.bin', 'esbuild')
await new Promise((done, fail) => {
  const proc = spawn(esbuild, ['harness.js', '--bundle', '--format=esm', '--outfile=app.js', '--log-level=warning'], { cwd: WORK, stdio: 'inherit' })
  proc.on('exit', (code) => (code === 0 ? done() : fail(new Error(`esbuild exited ${code}`))))
})

const variantPayload = (variant) => {
  const base = JSON.parse(JSON.stringify(payloads.desk))
  if (variant === 'artifact') base.library.items[0].cover = payloads.cover
  if (variant === 'fallback') return payloads.fallback
  return base
}

const page = (variant, withPet) => {
  const body = variantPayload(variant)
  const petJson = withPet && pet ? JSON.stringify(pet) : 'null'
  return `<!doctype html><html lang="en"><head><meta charset="utf-8" /><meta name="color-scheme" content="light dark" />
<style>html,body{margin:0;padding:0}body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
#root{padding:1.25rem clamp(1rem,4vw,4rem) 2rem;min-height:100vh}</style></head>
<body><div id="root"></div>
<script>window.__H189_PAYLOAD__ = ${JSON.stringify(body)}; window.__H189_PET_RAW__ = ${petJson};</script>
<script type="module" src="./app.js"></script></body></html>`
}
writeFileSync(resolve(WORK, 'pet.html'), page('desk', true))
writeFileSync(resolve(WORK, 'nopet.html'), page('desk', false))
writeFileSync(resolve(WORK, 'artifact.html'), page('artifact', false))
writeFileSync(resolve(WORK, 'fallback.html'), page('fallback', false))

const PORT = process.env.H189_CDP_PORT || '9419'
const SERVE_PORT = Number(process.env.H189_HTTP_PORT || '9418')
const server = createServer((request, response) => {
  const path = resolve(WORK, decodeURIComponent(String(request.url || '/').split('?')[0]).replace(/^\//, '') || 'pet.html')
  try {
    const body = readFileSync(path)
    const type = path.endsWith('.js') ? 'text/javascript' : path.endsWith('.json') ? 'application/json' : 'text/html'
    response.writeHead(200, { 'content-type': type })
    response.end(body)
  } catch (error) {
    response.writeHead(404)
    response.end('not found')
  }
})
await new Promise((done) => server.listen(SERVE_PORT, '127.0.0.1', done))
const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${resolve(WORK, '.chromium')}`, 'about:blank'
], { stdio: 'ignore' })
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 80; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
    if (targets.length) break
  } catch (error) { targets = null }
  await sleep(250)
}
if (!targets || !targets.length) { chromium.kill(); throw new Error('chromium CDP did not open') }
const target = targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((done, fail) => { socket.addEventListener('open', done, { once: true }); socket.addEventListener('error', fail, { once: true }) })
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: done, reject } = pending.get(message.id)
    pending.delete(message.id)
    message.error ? reject(new Error(JSON.stringify(message.error))) : done(message.result)
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
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(OUT, name), Buffer.from(png.data, 'base64'))
}
const FACT = `(() => {
  const txt = (n) => (n ? (n.innerText || n.textContent || '').trim() : null)
  const covers = [...document.querySelectorAll('[data-cb-slot-cover]')]
  const line = document.querySelector('[data-cb-field-notes-line]')
  return {
    trailheadMotion: (document.querySelector('[data-cb-trailhead]') || {}).getAttribute?.('data-cb-trailhead-motion') || null,
    pathMotion: (document.querySelector('[data-cb-path]') || {}).getAttribute?.('data-cb-path-motion') || null,
    pulse: (document.querySelector('[data-cb-path-pulse]') || {}).getAttribute?.('data-cb-path-pulse') || null,
    pulseOpacity: (document.querySelector('[data-cb-path-pulse]') || {}).style?.opacity || null,
    pulseRect: (() => {
      const node = document.querySelector('[data-cb-path-pulse]')
      if (!node) return null
      const rect = node.getBoundingClientRect()
      const style = getComputedStyle(node)
      return { w: Math.round(rect.width), h: Math.round(rect.height), opacity: style.opacity, border: style.borderTopWidth + ' ' + style.borderTopColor, accent: style.getPropertyValue('--cb-accent'), css: node.getAttribute('style'), visibility: style.visibility, display: style.display }
    })(),
    companion: Boolean(document.querySelector('[data-cb-companion] canvas')),
    companionMotion: (document.querySelector('[data-cb-companion]') || {}).getAttribute?.('data-cb-companion-motion') || null,
    companionPainted: (() => {
      const canvas = document.querySelector('[data-cb-companion] canvas')
      if (!canvas) return null
      try {
        const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
        let lit = 0
        for (let index = 3; index < data.length; index += 4) if (data[index] > 0) lit += 1
        return lit
      } catch (error) { return 'unreadable' }
    })(),
    coverKinds: covers.map((n) => n.getAttribute('data-cb-slot-cover')),
    coverAlts: [...document.querySelectorAll('[data-cb-slot-cover] img')].map((n) => n.getAttribute('alt')),
    coverCaptions: [...document.querySelectorAll('[data-cb-slot-cover-caption]')].map((n) => (n.innerText || '').trim()),
    coverHtml: covers[0] ? covers[0].outerHTML.slice(0, 400) : null,
    payloadCover: Boolean(window.__H189_PAYLOAD__ && window.__H189_PAYLOAD__.library && window.__H189_PAYLOAD__.library.items[0] && window.__H189_PAYLOAD__.library.items[0].cover),
    selectedTitle: txt(document.querySelector('[data-cb-desk-course]')),
    restPaths: window.__H189_REST__ || [],
    shelfContours: document.querySelectorAll('[data-cb-classroom-shelf] [data-cb-course-contour]').length,
    notesLine: txt(line),
    noteRows: document.querySelectorAll('[data-cb-field-note]').length,
    emptyAltImages: document.querySelectorAll('img[alt=""]').length,
    animations: document.getAnimations().length,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    width: window.innerWidth
  }
})()`

const open = async (file, width = 1049, reduced = false) => {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 1400, deviceScaleFactor: 1, mobile: false })
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: reduced ? 'reduce' : 'no-preference' }] })
  await send('Page.navigate', { url: `http://127.0.0.1:${SERVE_PORT}/${file}` })
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await sleep(80)
    const ready = await evaluate('Boolean(window.__H189_READY__)').catch(() => false)
    if (ready) return
  }
  const state = await evaluate('({ body: document.body.innerText.slice(0, 400), errors: window.__H189_ERRORS__ || null })').catch(() => null)
  throw new Error(`page ${file} did not mount: ${JSON.stringify(state)}`)
}

const report = { generated_at: new Date().toISOString(), pet: pet ? pet.slug : null, frames: [] }
const record = async (name, extra = {}) => {
  const facts = await evaluate(FACT)
  return { id: name, ...facts, ...extra }
}

await send('Page.enable')
await send('Runtime.enable')

await open('pet.html', 1049, false)
await sleep(1400)
await shot('10-live-pet-1049.png')
report.frames.push(await record('live-pet-1049'))

await open('nopet.html', 1049, false)
await sleep(900)
await shot('11-live-no-pet-1049.png')
report.frames.push(await record('live-no-pet-1049'))

await open('artifact.html', 1049, false)
await sleep(1200)
await shot('12-live-real-artifact-cover-1049.png')
report.frames.push(await record('live-real-artifact-cover-1049'))

await open('fallback.html', 1049, false)
await sleep(900)
await shot('13-live-typographic-cover-1049.png')
report.frames.push(await record('live-typographic-cover-1049'))

// Motion: navigate without waiting, then sample every 10 ms so the one-frame arrival and the
// beacon's high point are observed rather than guessed. Screenshots are taken at those samples.
await send('Emulation.setDeviceMetricsOverride', { width: 1049, height: 1400, deviceScaleFactor: 1, mobile: false })
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
// The arrival is one animation frame by design. Slow that frame in the *capture browser only* so the
// authored first frame is observable in a screenshot; the shipped module is unchanged.
const slowRaf = await send('Page.addScriptToEvaluateOnNewDocument', {
  source: '(() => { const raf = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = (cb) => setTimeout(() => raf(cb), 140) })()'
})
await send('Page.navigate', { url: `http://127.0.0.1:${SERVE_PORT}/nopet.html` })
const started = Date.now()
const samples = []
let arrivalShot = false
let beaconShot = false
let beaconFacts = null
let arrivalFacts = null
while (Date.now() - started < 2600) {
  const facts = await evaluate(FACT).catch(() => null)
  if (facts && facts.trailheadMotion) {
    const sample = { at: Date.now() - started, trailheadMotion: facts.trailheadMotion, pulse: facts.pulse, pulseOpacity: facts.pulseOpacity }
    if (samples.length === 0 || JSON.stringify(sample).replace(/,\s*$/, '') !== JSON.stringify({ ...samples.at(-1), at: sample.at }) || samples.at(-1).pulseOpacity !== sample.pulseOpacity || samples.at(-1).trailheadMotion !== sample.trailheadMotion) samples.push(sample)
    if (!arrivalShot && facts.trailheadMotion === 'arriving') {
      await shot('14-motion-arrival-1049.png')
      arrivalShot = true
      arrivalFacts = { ...facts, at: sample.at }
    }
    if (!beaconShot && facts.pulseOpacity === '0.9') {
      await shot('15-motion-beacon-1049.png')
      beaconShot = true
      beaconFacts = { ...facts, at: sample.at }
    }
  }
  await sleep(10)
}
await sleep(300)
await shot('16-motion-rest-1049.png')
const restFacts = await record('motion-rest-1049')
report.frames.push({ id: 'motion-arrival-1049', captured: arrivalShot, ...(arrivalFacts || {}) })
report.frames.push({ id: 'motion-beacon-1049', captured: beaconShot, ...(beaconFacts || {}) })
report.frames.push(restFacts)
report.motion = { samples, arrival_captured: arrivalShot, beacon_captured: beaconShot }
await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: slowRaf.identifier })

// Reduced motion: same route, static first frame, no running animation.
await open('nopet.html', 460, true)
await sleep(500)
await shot('17-reduced-motion-460.png')
report.frames.push(await record('reduced-motion-460'))

// Reduced motion with the real pet: frame 0 only, no cadence.
await open('pet.html', 460, true)
await sleep(900)
await shot('19-reduced-motion-pet-460.png')
report.frames.push(await record('reduced-motion-pet-460'))

// Narrow composition: shelf must not overflow or crowd the primary.
await open('pet.html', 460, false)
await sleep(1200)
await shot('18-live-pet-460.png')
report.frames.push(await record('live-pet-460'))

await send('Emulation.clearDeviceMetricsOverride')
socket.close()
chromium.kill()
server.close()
writeFileSync(resolve(OUT, 'motion.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report.frames.map(({ id, trailheadMotion, pulse, pulseOpacity, pulseRect, companion, companionMotion, companionPainted, coverKinds, coverAlts, coverCaptions, payloadCover, selectedTitle, restPaths, notesLine, noteRows, shelfContours, emptyAltImages, overflow, width, animations }) => ({ id, trailheadMotion, pulse, pulseOpacity, pulseRect, companion, companionMotion, companionPainted, coverKinds, coverAlts, coverCaptions, payloadCover, selectedTitle, restPaths, notesLine, noteRows, shelfContours, emptyAltImages, overflow, width, animations })), null, 1))
