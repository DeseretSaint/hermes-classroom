#!/usr/bin/env node
/**
 * CP-000 — the one capture door for Coursebook concept-parity evidence.
 *
 * Every screenshot used as parity evidence must come from this script and must be accompanied by
 * its `<name>.stamp.json`. The stamp is what makes a frame checkable: it records the module sha the
 * window itself read, the backend contract it talked to, the route geometry, the theme, the text
 * scale, motion/forced-colors posture, font status, image decode state and capture hash.
 *
 * The script REFUSES to capture — and exits 2 with `<name>.refused.json` — unless:
 *   1. the plugin source the window reads hashes to the checkout module sha (or --expect-sha);
 *   2. `[data-cb-route]` exists and no render-error marker is present;
 *   3. `document.fonts.status === 'loaded'`;
 *   4. every `img` inside the route is complete with naturalWidth > 0;
 *   5. with --require-v3, `[data-cb-v3-ready]` is present.
 *
 * Why the sha is read through the window: `window.hermesDesktop.readPluginSource(path)` is the same
 * IPC door the host's runtime loader uses to fetch `plugin.js` before evaluating it. Hashing that
 * text and comparing it to the checkout is the only in-window proof of which module is on screen;
 * reading the file from Node alone would prove what is on disk, not what the renderer loaded. The
 * script also hard-reloads with `ignoreCache` before probing, so a repointed rig cannot answer from
 * a pre-swap module.
 *
 * Usage (live Electron window):
 *   node scripts/cp-capture.mjs --name home-1049-light --out docs/concept-parity/captures \
 *     --cdp-port 9411 --state "$COURSEBOOK_TEST_STATE" --plugin desktop/plugin.js \
 *     --backend-url http://127.0.0.1:44311 --token cb013-test-token \
 *     --route-width 1049 [--require-v3] [--keep-console]
 *
 * Usage (recorded fixture page, used by tests — no Electron host):
 *   node scripts/cp-capture.mjs --name fixture-ok --out <dir> --fixture tests/fixtures/cp-capture/ok.html \
 *     --expect-sha <sha256>
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  const value = args[index + 1]
  return value && !value.startsWith('--') ? value : true
}
const outDir = resolve(String(flag('out', 'docs/concept-parity/captures')))
const name = String(flag('name', `capture-${Date.now()}`))
const cdpPort = String(flag('cdp-port', process.env.CB015_CDP_PORT || '9337'))
const pluginPath = resolve(String(flag('plugin', 'desktop/plugin.js')))
const stateDir = flag('state', process.env.COURSEBOOK_TEST_STATE || null)
const loadedPluginArg = flag('loaded-plugin', null)
const fixture = flag('fixture', null)
const requireV3 = Boolean(flag('require-v3', false))
const backendUrl = flag('backend-url', null)
const token = flag('token', process.env.CB013_TOKEN || '')
const routeWidth = Number(flag('route-width', 1049))
const expectSha = flag('expect-sha', null)
const timeoutMs = Number(flag('timeout', 45000))
const keepConsole = Boolean(flag('keep-console', false))

mkdirSync(outDir, { recursive: true })
const pngPath = resolve(outDir, `${name}.png`)
const stampPath = resolve(outDir, `${name}.stamp.json`)
const refusedPath = resolve(outDir, `${name}.refused.json`)

const sha256File = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const RENDER_ERROR_SELECTORS = [
  '[data-cb-render-error]',
  '[data-cb-route-error]',
  '[data-cb-render-failed]',
  '[data-cb-error-page]'
]

/**
 * Probe run inside the page. `SRC_PATH` is injected. In live mode it asks the host for the raw
 * plugin source through the runtime loader's own read door and hashes it in-page.
 */
const probeExpression = (srcPath, wantSource) => `(async () => {
  const hashText = async (text) => {
    const bytes = new TextEncoder().encode(text)
    const digest = await crypto.subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }
  const fixture = window.__CP000_FIXTURE__ || null
  if (fixture) return fixture
  const root = document.querySelector('[data-cb-route]')
  const rect = root ? root.getBoundingClientRect() : null
  const imgs = root ? [...root.querySelectorAll('img')] : []
  const styleSheets = [...document.styleSheets]
  let cssRuleCount = 0
  for (const sheet of styleSheets) {
    try { cssRuleCount += sheet.cssRules ? sheet.cssRules.length : 0 } catch { /* cross-origin */ }
  }
  const h1 = document.querySelector('[data-cb-route] h1')
  const bodyFont = getComputedStyle(document.body).fontFamily
  const out = {
    plugin: { window_sha256: null, loaded_path: ${JSON.stringify(srcPath || null)}, bytes: null, error: null },
    route: {
      selector: '[data-cb-route]',
      present: Boolean(root),
      marker: root ? root.getAttribute('data-cb-route') : null,
      width: rect ? Math.round(rect.width * 100) / 100 : null,
      height: rect ? Math.round(rect.height * 100) / 100 : null,
      top: rect ? Math.round(rect.top * 100) / 100 : null,
      left: rect ? Math.round(rect.left * 100) / 100 : null,
      window_width: window.innerWidth,
      window_height: window.innerHeight,
      theme: root ? root.getAttribute('data-cb-scope') : null,
      motion: root ? root.getAttribute('data-cb-motion') : null,
      text_scale_root_px: getComputedStyle(document.documentElement).fontSize,
      reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      forced_colors: matchMedia('(forced-colors: active)').matches,
      fonts_status: document.fonts.status,
      font_faces: [...document.fonts].map((face) => face.family + ' ' + face.weight + ' ' + face.status).slice(0, 40),
      images_total: imgs.length,
      images_decoded: imgs.filter((img) => img.complete && img.naturalWidth > 0).length,
      images_broken: imgs.filter((img) => !img.complete || img.naturalWidth === 0).map((img) => (img.currentSrc || img.src || '').slice(0, 160)),
      render_error_markers: ${JSON.stringify(RENDER_ERROR_SELECTORS)}.filter((sel) => document.querySelector(sel)),
      v3_ready: Boolean(document.querySelector('[data-cb-v3-ready]')),
      style_sheet_count: styleSheets.length,
      css_rule_count: cssRuleCount,
      host_slots: document.querySelectorAll('[data-slot]').length,
      host_shell: Boolean(document.querySelector('#root')) && !document.body.className.includes('cb-standalone'),
      heading_font_family: h1 ? getComputedStyle(h1).fontFamily : null,
      body_font_family: bodyFont,
      route_ancestors: root ? (() => { const out = []; let n = root.parentElement; while (n && out.length < 4) { out.push(n.tagName.toLowerCase() + '.' + String(n.className || '').split(/\\s+/).slice(0, 3).join('.')); n = n.parentElement } return out })() : []
    },
    console: { errors: [], warnings: 0 }
  }
  if (${wantSource ? 'true' : 'false'} && ${JSON.stringify(srcPath || null)} && window.hermesDesktop && window.hermesDesktop.readPluginSource) {
    try {
      const read = await window.hermesDesktop.readPluginSource(${JSON.stringify(srcPath || null)})
      out.plugin.loaded_path = read.path || out.plugin.loaded_path
      out.plugin.bytes = read.byteSize || read.text.length
      out.plugin.window_sha256 = await hashText(read.text)
    } catch (error) {
      out.plugin.error = String(error && error.message ? error.message : error)
    }
  }
  return out
})()`

const runGates = ({ probe, expectedSha, requireV3 }) => {
  const gates = {}
  const reasons = []
  const pluginSha = probe.plugin && probe.plugin.window_sha256 ? probe.plugin.window_sha256 : null
  gates.plugin_sha_match = Boolean(pluginSha) && pluginSha === expectedSha
  if (!pluginSha) reasons.push(`plugin sha unavailable in window${probe.plugin && probe.plugin.error ? `: ${probe.plugin.error}` : ''}`)
  else if (pluginSha !== expectedSha) reasons.push(`stale module: window reads ${pluginSha}, expected ${expectedSha}`)

  const route = probe.route || {}
  gates.route_present = route.present === true
  if (!gates.route_present) reasons.push('no [data-cb-route] element — the route did not render')

  gates.no_render_error = Array.isArray(route.render_error_markers) && route.render_error_markers.length === 0
  if (!gates.no_render_error) reasons.push(`render-error marker present: ${(route.render_error_markers || []).join(', ')}`)

  gates.fonts_loaded = route.fonts_status === 'loaded'
  if (!gates.fonts_loaded) reasons.push(`document.fonts.status is ${String(route.fonts_status)} — fonts not settled`)

  gates.images_decoded = (route.images_broken || []).length === 0
  if (!gates.images_decoded) reasons.push(`undecoded image(s) in the route: ${(route.images_broken || []).join(' | ')}`)

  if (requireV3) {
    gates.v3_ready = route.v3_ready === true
    if (!gates.v3_ready) reasons.push('--require-v3 set but [data-cb-v3-ready] is absent')
  }
  return { gates, reasons, ok: reasons.length === 0 }
}

const writeRefusal = (stage, probe, gate) => {
  const record = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    name,
    captured_at: new Date().toISOString(),
    ok: false,
    stage,
    reasons: gate.reasons,
    gates: gate.gates,
    plugin: probe ? probe.plugin : null,
    route: probe ? probe.route : null
  }
  writeFileSync(refusedPath, `${JSON.stringify(record, null, 2)}\n`)
  console.error(`REFUSED (${name}): ${gate.reasons.join('; ')}`)
  console.error(`wrote ${refusedPath}`)
  process.exit(2)
}

class CDP {
  constructor(socket) {
    this.socket = socket
    this.nextId = 1
    this.pending = new Map()
    this.listeners = []
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id && this.pending.has(message.id)) {
        const { done, fail } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) fail(new Error(JSON.stringify(message.error)))
        else done(message.result)
        return
      }
      for (const listener of this.listeners) listener(message)
    })
  }
  send(method, params = {}) {
    return new Promise((done, fail) => {
      const id = this.nextId++
      this.pending.set(id, { done, fail })
      this.socket.send(JSON.stringify({ id, method, params }))
    })
  }
  on(listener) { this.listeners.push(listener) }
  close() { try { this.socket.close() } catch { /* already gone */ } }
}

const connectSocket = async (url) => {
  const socket = new WebSocket(url)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  return new CDP(socket)
}

const attachLive = async () => {
  const base = `http://127.0.0.1:${cdpPort}`
  let targets = null
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      targets = await (await fetch(`${base}/json`)).json()
      if (targets && targets.length) break
    } catch { targets = null }
    await sleep(250)
  }
  if (!targets || !targets.length) throw new Error(`no CDP target on ${base}`)
  const pages = targets.filter((entry) => entry.type === 'page')
  const page = pages.find((entry) => /Hermes/i.test(entry.title || '')) || pages[0]
  const cdp = await connectSocket(page.webSocketDebuggerUrl)
  await cdp.send('Page.enable', {})
  await cdp.send('Runtime.enable', {})
  await cdp.send('Log.enable', {})
  return { cdp, page }
}

const collectConsole = (cdp) => {
  const errors = []
  let warnings = 0
  cdp.on((message) => {
    if (message.method === 'Runtime.consoleAPICalled') {
      const { type, args } = message.params
      if (type === 'error') errors.push(args.map((arg) => String(arg.value ?? arg.description ?? '')).join(' ').slice(0, 400))
      if (type === 'warning') warnings += 1
    }
    if (message.method === 'Log.entryAdded') {
      const entry = message.params.entry
      if (entry.level === 'error') errors.push(String(entry.text || '').slice(0, 400))
      if (entry.level === 'warning') warnings += 1
    }
  })
  return () => ({ errors: errors.slice(0, 40), warnings })
}

const evaluate = async (cdp, expression) => {
  const result = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'evaluate failed')
  }
  return result.result.value
}

const waitForRoute = async (cdp, ms) => {
  const deadline = Date.now() + ms
  while (Date.now() < deadline) {
    const state = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      return { route: Boolean(root), ready: document.readyState, home: root ? root.getAttribute('data-cb-destination') : null }
    })()`)
    if (state.route) return state
    await sleep(200)
  }
  return null
}

const liveCapture = async () => {
  const { cdp, page } = await attachLive()
  const consoleReader = collectConsole(cdp)

  // Hard reload with an empty cache so a repointed rig cannot answer from a pre-swap module.
  await cdp.send('Page.reload', { ignoreCache: true })
  await sleep(400)
  await evaluate(cdp, `location.hash = '#/coursebook'`)
  let state = await waitForRoute(cdp, timeoutMs)
  if (!state) {
    const probe = { plugin: { window_sha256: null, loaded_path: null, error: 'route never appeared' }, route: { present: false, render_error_markers: [] } }
    const gate = { gates: { route_present: false }, reasons: ['[data-cb-route] never appeared after reload'], ok: false }
    writeRefusal('route-wait', probe, gate)
  }

  // Measure host chrome offset once, then size the window so the ROUTE is the requested width.
  // This Electron build runs the page at ~0.896 zoom, so an Emulation width is not the page's
  // innerWidth; calibrate against the measured zoom on every pass instead of assuming 1:1.
  let emWidth = routeWidth + 240
  let targetHeight = 1200
  let zoom = 1
  for (let pass = 0; pass < 6; pass += 1) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: emWidth,
      height: targetHeight,
      deviceScaleFactor: 2,
      mobile: false
    })
    await sleep(250)
    const measured = await evaluate(cdp, `(() => {
      const root = document.querySelector('[data-cb-route]')
      const rect = root.getBoundingClientRect()
      const scroller = document.querySelector('main#cb-main-content')
      if (scroller) scroller.scrollTop = 0
      return { route: rect.width, height: rect.height, window: window.innerWidth }
    })()`)
    zoom = measured.window / emWidth || 1
    const chrome = Math.max(0, measured.window - measured.route)
    const innerTarget = routeWidth + chrome
    if (Math.abs(measured.route - routeWidth) <= 1.5) break
    emWidth = Math.max(320, Math.round(innerTarget / zoom))
  }

  // Grow the viewport to contain the whole route so the crop never cuts a scroll container.
  const box = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    const scroller = document.querySelector('main#cb-main-content')
    if (scroller) scroller.scrollTop = 0
    return { height: rect.height, top: rect.top, left: rect.left, width: rect.width }
  })()`)
  const wantedHeight = Math.min(5000, Math.max(targetHeight, Math.ceil(box.height + box.top + 40)))
  if (wantedHeight !== targetHeight) {
    targetHeight = wantedHeight
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: emWidth,
      height: targetHeight,
      deviceScaleFactor: 2,
      mobile: false
    })
    await sleep(300)
  }

  // Apply reduced-motion / forced-colors emulation only when asked; never silently.
  if (flag('reduced-motion', false)) {
    await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
    await sleep(120)
  }
  if (flag('forced-colors', false)) {
    await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'forced-colors', value: 'active' }] })
    await sleep(120)
  }

  const loadedPlugin = loadedPluginArg
    ? resolve(String(loadedPluginArg))
    : stateDir
      ? resolve(String(stateDir), 'home', 'desktop-plugins', 'coursebook', 'plugin.js')
      : null
  const probe = await evaluate(cdp, probeExpression(loadedPlugin, Boolean(loadedPlugin)))
  probe.console = consoleReader()
  probe.route.backend = null

  const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
  const gate = runGates({ probe, expectedSha, requireV3 })
  if (!gate.ok) writeRefusal('gates', probe, gate)

  // Re-measure the crop box after any emulation change.
  const crop = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  })()`)
  const shot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
    clip: { x: crop.x, y: crop.y, width: crop.width, height: crop.height, scale: 1 }
  })
  const png = Buffer.from(shot.data, 'base64')
  writeFileSync(pngPath, png)

  return finishStamp({ probe, gate, png, expectedSha, pageUrl: page.url, shotBox: crop, mode: 'live' })
}

const fixtureCapture = async () => {
  const target = /^https?:|^file:/.test(String(fixture)) ? String(fixture) : `file://${resolve(String(fixture))}`
  const port = 9500 + Math.floor(Math.random() * 200)
  const chromium = spawn('chromium', [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${resolve(outDir, '.chromium-fixture')}`,
    'about:blank'
  ], { stdio: 'ignore' })
  let targets = null
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      if (targets && targets.length) break
    } catch { targets = null }
    await sleep(250)
  }
  if (!targets || !targets.length) {
    chromium.kill()
    throw new Error('fixture chromium did not open a CDP port')
  }
  const page = targets.find((entry) => entry.type === 'page')
  const cdp = await connectSocket(page.webSocketDebuggerUrl)
  await cdp.send('Page.enable', {})
  await cdp.send('Runtime.enable', {})
  await cdp.send('Page.navigate', { url: target })
  await sleep(500)
  const probe = await evaluate(cdp, probeExpression(null, false))
  const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
  const gate = runGates({ probe, expectedSha, requireV3 })
  if (!gate.ok) {
    cdp.close()
    chromium.kill()
    writeRefusal('gates', probe, gate)
  }
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: routeWidth, height: 900, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const box = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  })()`)
  const shot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
    clip: { x: box.x, y: box.y, width: box.width, height: box.height, scale: 1 }
  })
  const png = Buffer.from(shot.data, 'base64')
  writeFileSync(pngPath, png)
  cdp.close()
  chromium.kill()
  return finishStamp({ probe, gate, png, expectedSha, pageUrl: target, shotBox: box, mode: 'fixture' })
}

const fetchRuntime = async (probe) => {
  if (!backendUrl) {
    probe.route.backend = null
    return
  }
  try {
    const response = await fetch(`${String(backendUrl).replace(/\/$/, '')}/api/plugins/coursebook/runtime`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (!response.ok) {
      probe.route.backend = { error: `HTTP ${response.status}`, url: String(backendUrl) }
      return
    }
    const runtime = await response.json()
    probe.route.backend = {
      url: String(backendUrl),
      wire_contract: runtime.wire_contract || null,
      wire_version: runtime.wire_version || null,
      contract_methods: runtime.contract_methods || null,
      implemented_count: Array.isArray(runtime.implemented_methods) ? runtime.implemented_methods.length : null,
      plugin_root: runtime.plugin_root || null,
      backend_package: runtime.backend_package || null
    }
  } catch (error) {
    probe.route.backend = { error: String(error && error.message ? error.message : error), url: String(backendUrl) }
  }
}

const finishStamp = async ({ probe, gate, png, expectedSha, pageUrl, shotBox, mode }) => {
  await fetchRuntime(probe)
  const stamp = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    mode,
    name,
    captured_at: new Date().toISOString(),
    ok: true,
    gates: gate.gates,
    plugin: {
      expected_sha256: expectedSha,
      window_sha256: probe.plugin.window_sha256,
      loaded_path: probe.plugin.loaded_path,
      checkout_path: pluginPath,
      bytes: probe.plugin.bytes
    },
    backend: probe.route.backend,
    route: {
      selector: probe.route.selector,
      marker: probe.route.marker,
      destination: probe.route.destination || null,
      width: probe.route.width,
      height: probe.route.height,
      window_width: probe.route.window_width,
      window_height: probe.route.window_height,
      theme: probe.route.theme,
      text_scale_root_px: probe.route.text_scale_root_px,
      motion: probe.route.motion,
      reduced_motion: probe.route.reduced_motion,
      forced_colors: probe.route.forced_colors,
      fonts_status: probe.route.fonts_status,
      font_faces: probe.route.font_faces,
      images_total: probe.route.images_total,
      images_decoded: probe.route.images_decoded,
      style_sheet_count: probe.route.style_sheet_count,
      css_rule_count: probe.route.css_rule_count,
      host_slots: probe.route.host_slots,
      host_shell: probe.route.host_shell,
      heading_font_family: probe.route.heading_font_family,
      body_font_family: probe.route.body_font_family,
      route_ancestors: probe.route.route_ancestors
    },
    console: probe.console || { errors: [], warnings: 0 },
    capture: {
      file: pngPath.split('/').pop(),
      sha256: createHash('sha256').update(png).digest('hex'),
      bytes: png.length,
      clip: { x: shotBox.x, y: shotBox.y, width: shotBox.width, height: shotBox.height }
    },
    page_url: pageUrl
  }
  writeFileSync(stampPath, `${JSON.stringify(stamp, null, 2)}\n`)
  console.log(`OK ${name}: route=${stamp.route.width}x${stamp.route.height} theme=${stamp.route.theme} ` +
    `fonts=${stamp.route.fonts_status} images=${stamp.route.images_decoded}/${stamp.route.images_total} ` +
    `sha=${String(stamp.plugin.window_sha256).slice(0, 12)}`)
  console.log(`wrote ${pngPath}`)
  console.log(`wrote ${stampPath}`)
  if (keepConsole && stamp.console.errors.length) {
    console.error(`console errors (${stamp.console.errors.length}):`)
    for (const error of stamp.console.errors) console.error(`  ${error}`)
  }
  return stamp
}

const main = async () => {
  if (flag('help', false)) {
    console.log('usage: node scripts/cp-capture.mjs --name <name> --out <dir> [--fixture <page>] [--cdp-port N]')
    return
  }
  if (fixture) {
    await fixtureCapture()
    process.exit(0)
  }
  await liveCapture()
  process.exit(0)
}

main().catch((error) => {
  const record = {
    stamp_version: 1,
    tool: 'scripts/cp-capture.mjs',
    name,
    captured_at: new Date().toISOString(),
    ok: false,
    stage: 'error',
    reasons: [String(error && error.stack ? error.stack.split('\n')[0] : error)]
  }
  writeFileSync(refusedPath, `${JSON.stringify(record, null, 2)}\n`)
  console.error(`CAPTURE ERROR (${name}): ${record.reasons[0]}`)
  process.exit(3)
})
