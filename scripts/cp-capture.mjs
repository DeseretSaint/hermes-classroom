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
 *   5. no host element is painted above the route box (grid hit-test); a contaminated clip needs
 *      --crop-to-content, which records the overlay geometry and crops the unoccluded content rect;
 *   6. the captured pixels are not a significant share of the document background (pixel veto);
 *   7. the page zoom is 100% during capture (normalised through the host zoom bridge, restored after);
 *   8. with --require-v3, `[data-cb-v3-ready]` is present.
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
 *     --route-width 1049 [--require-v3] [--keep-console] [--crop-to-content]
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
const cropToContent = Boolean(flag('crop-to-content', false))

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
 *
 * It also measures host *occlusion*: for a grid of points inside the route box, which elements sit
 * ABOVE the route in the hit-test stack. A fixed host rail or status bar painted over the route is
 * capture contamination, not product UI, and must never reach a parity frame. The same geometry is
 * used to derive `content_width` / `content_height`, the actually usable painted surface.
 */
const probeExpression = (srcPath, wantSource) => `(async () => {
  const hashText = async (text) => {
    const bytes = new TextEncoder().encode(text)
    const digest = await crypto.subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }
  const fixture = window.__CP000_FIXTURE__ || null
  const round = (n) => Math.round(n * 100) / 100
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
  const isBoundary = (el) => el === root || root.contains(el) || el.contains(root)
  const overlayProbe = () => {
    const trims = { left: 0, right: 0, top: 0, bottom: 0 }
    if (!root || !rect || rect.width < 1 || rect.height < 1) {
      return { overlays: [], sampled: 0, occluded_points: 0, occluded_fraction: 0, trims, content_rect: null }
    }
    const cols = 16
    const rows = 24
    const seen = new Map()
    let sampled = 0
    let occluded = 0
    for (let col = 0; col < cols; col += 1) {
      for (let row = 0; row < rows; row += 1) {
        const x = rect.left + ((col + 0.5) * rect.width) / cols
        const y = rect.top + ((row + 0.5) * rect.height) / rows
        sampled += 1
        const stack = document.elementsFromPoint(x, y)
        const above = []
        for (const el of stack) {
          if (isBoundary(el)) break
          if (el === document.documentElement || el === document.body) continue
          above.push(el)
        }
        if (!above.length) continue
        occluded += 1
        const el = above[0]
        const er = el.getBoundingClientRect()
        const key = el.tagName + '|' + String(el.className || '').split(/\\s+/).slice(0, 3).join('.') + '|' +
          Math.round(er.x) + ',' + Math.round(er.y) + ',' + Math.round(er.width) + 'x' + Math.round(er.height)
        if (!seen.has(key)) {
          seen.set(key, {
            tag: el.tagName.toLowerCase(),
            class_fragment: String(el.className || '').split(/\\s+/).slice(0, 4).join('.'),
            slot: el.getAttribute('data-slot'),
            rect: { x: round(er.x), y: round(er.y), width: round(er.width), height: round(er.height) },
            background: getComputedStyle(el).backgroundColor,
            position: getComputedStyle(el).position,
            z_index: getComputedStyle(el).zIndex,
            points: 0
          })
        }
        seen.get(key).points += 1
      }
    }
    const overlays = [...seen.values()].sort((a, b) => b.points - a.points)
    for (const overlay of overlays) {
      const r = overlay.rect
      const spansV = r.height >= rect.height * 0.5
      const spansH = r.width >= rect.width * 0.5
      if (spansV && r.x > rect.left + 1 && r.x + r.width >= rect.right - 1) trims.right = Math.max(trims.right, rect.right - r.x)
      if (spansV && r.x <= rect.left + 1 && r.x + r.width < rect.right - 1) trims.left = Math.max(trims.left, r.x + r.width - rect.left)
      if (spansH && r.y > rect.top + 1 && r.y + r.height >= rect.bottom - 1) trims.bottom = Math.max(trims.bottom, rect.bottom - r.y)
      if (spansH && r.y <= rect.top + 1 && r.y + r.height < rect.bottom - 1) trims.top = Math.max(trims.top, r.y + r.height - rect.top)
    }
    const contentX = rect.left + trims.left
    const contentY = rect.top + trims.top
    return {
      overlays,
      sampled,
      occluded_points: occluded,
      occluded_fraction: sampled ? round(occluded / sampled) : 0,
      trims,
      content_rect: {
        x: round(contentX),
        y: round(contentY),
        width: round(Math.max(0, rect.width - trims.left - trims.right)),
        height: round(Math.max(0, rect.height - trims.top - trims.bottom))
      }
    }
  }
  const occlusion = overlayProbe()
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
      route_ancestors: root ? (() => { const out = []; let n = root.parentElement; while (n && out.length < 4) { out.push(n.tagName.toLowerCase() + '.' + String(n.className || '').split(/\\s+/).slice(0, 3).join('.')); n = n.parentElement } return out })() : [],
      html_background: getComputedStyle(document.documentElement).backgroundColor,
      body_background: getComputedStyle(document.body).backgroundColor,
      background_color: root ? getComputedStyle(root).backgroundColor : null,
      host_overlays: occlusion.overlays,
      host_overlay_points: occlusion.occluded_points,
      host_overlay_sampled: occlusion.sampled,
      host_overlay_fraction: occlusion.occluded_fraction,
      host_overlay_trims: occlusion.trims,
      content_rect: occlusion.content_rect,
      content_width: occlusion.content_rect ? occlusion.content_rect.width : null,
      content_height: occlusion.content_rect ? occlusion.content_rect.height : null
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
  if (fixture) {
    if (fixture.plugin) out.plugin = Object.assign({}, out.plugin, fixture.plugin)
    if (fixture.route) out.route = Object.assign(out.route, fixture.route)
    if (fixture.console) out.console = fixture.console
  }
  return out
})()`

const runGates = ({ probe, expectedSha, requireV3, pixelCheck, zoom, cropMode }) => {
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

  // Host chrome painted over the route box is capture contamination (a rail, a status bar, a chat
  // pane). Refuse unless the caller explicitly crops to the unoccluded content rect, in which case
  // the overlay geometry is recorded in the stamp and the crop excludes it.
  const occluded = Number(route.host_overlay_points || 0)
  if (cropMode === 'content') {
    gates.no_host_overlay = true
    gates.host_overlay_excluded = true
  } else {
    gates.no_host_overlay = occluded === 0
    if (!gates.no_host_overlay) {
      const overlays = (route.host_overlays || []).slice(0, 3)
        .map((o) => `${o.tag}.${o.class_fragment || '(no class)'} ${o.rect.width}x${o.rect.height} bg=${o.background}`)
        .join('; ')
      reasons.push(`host chrome occludes the route box (${occluded}/${route.host_overlay_sampled} sample points; ` +
        `content ${route.content_width}x${route.content_height} of route ${route.width}x${route.height}): ${overlays}` +
        ' — rerun with --crop-to-content to crop the usable surface and record the overlay geometry')
    }
  }

  // Post-capture pixel assertion: when the route paints a different background from the document,
  // a significant share of host-background pixels inside the clip means part of the route was never
  // painted (the historical Class C band). Only meaningful when the two colours differ.
  if (pixelCheck && pixelCheck.ok) {
    gates.no_unpainted_region = !pixelCheck.distinct_backgrounds || Number(pixelCheck.host_bg_fraction) <= 0.02
    if (!gates.no_unpainted_region) {
      reasons.push(`host background ${pixelCheck.html_bg} covers ${(Number(pixelCheck.host_bg_fraction) * 100).toFixed(1)}% ` +
        `of the route crop while the route paints ${pixelCheck.route_bg} — part of the frame was not painted`)
    }
  } else {
    gates.no_unpainted_region = false
    reasons.push(`pixel contamination check did not run${pixelCheck && pixelCheck.error ? `: ${pixelCheck.error}` : ''}`)
  }

  gates.zoom_neutral = !zoom || zoom.capture_percent === 100
  if (!gates.zoom_neutral) reasons.push(`page zoom was ${String(zoom && zoom.capture_percent)}% during capture; the capture door requires 100% so the emulated viewport is fully painted`)

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

/**
 * Decode the freshly captured PNG back inside the page and count how much of the crop is the
 * document (host) background. A route that paints its own paper must leave almost none; the
 * historical Class C defect left an L-shaped host-coloured band because the emulated viewport was
 * clipped by the rig's page zoom.
 */
const pixelContamination = async (cdp, png, routeBackground, htmlBackground) => {
  const dataUrl = `data:image/png;base64,${png.toString('base64')}`
  const expression = `(async () => {
    try {
      const img = new Image()
      img.src = ${JSON.stringify(dataUrl)}
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(img, 0, 0)
      const parse = (value) => {
        const match = String(value || '').match(/rgba?\\(([^)]+)\\)/)
        if (!match) return null
        const parts = match[1].split(',').map((entry) => Number(entry.trim()))
        if (parts.length < 3 || parts.some((entry) => Number.isNaN(entry))) return null
        return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1]
      }
      const html = parse(${JSON.stringify(String(htmlBackground || ''))})
      const route = parse(${JSON.stringify(String(routeBackground || ''))})
      if (!html) return { ok: false, error: 'html background is not an rgb colour: ' + String(htmlBackground) }
      if (html[3] === 0) {
        return { ok: true, sampled: 0, host_bg_pixels: 0, host_bg_fraction: 0, html_bg: 'transparent', route_bg: route ? route.slice(0, 3).join(', ') : null, distinct_backgrounds: false }
      }
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      const stepX = Math.max(1, Math.floor(canvas.width / 320))
      const stepY = Math.max(1, Math.floor(canvas.height / 320))
      let sampled = 0
      let host = 0
      for (let y = 0; y < canvas.height; y += stepY) {
        for (let x = 0; x < canvas.width; x += stepX) {
          const index = (y * canvas.width + x) * 4
          sampled += 1
          if (Math.abs(data[index] - html[0]) <= 2 && Math.abs(data[index + 1] - html[1]) <= 2 && Math.abs(data[index + 2] - html[2]) <= 2) host += 1
        }
      }
      return {
        ok: true,
        sampled,
        host_bg_pixels: host,
        host_bg_fraction: sampled ? Math.round((host / sampled) * 10000) / 10000 : 0,
        html_bg: html.join(', '),
        route_bg: route ? route.join(', ') : null,
        distinct_backgrounds: Boolean(route) && (route[0] !== html[0] || route[1] !== html[1] || route[2] !== html[2])
      }
    } catch (error) {
      return { ok: false, error: String(error && error.message ? error.message : error) }
    }
  })()`
  return evaluate(cdp, expression)
}

const readZoom = async (cdp) => evaluate(cdp, `(async () => {
  const zoom = window.hermesDesktop && window.hermesDesktop.zoom
  if (!zoom || !zoom.get) return null
  try {
    const state = await zoom.get()
    return { percent: state.percent, level: state.level }
  } catch (error) {
    return { error: String(error && error.message ? error.message : error) }
  }
})()`)

const setZoomPercent = async (cdp, percent) => evaluate(cdp, `(async () => {
  const zoom = window.hermesDesktop && window.hermesDesktop.zoom
  if (!zoom || !zoom.setPercent) return false
  await zoom.setPercent(${Number(percent)})
  return true
})()`)

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

  // Neutralise the rig's page zoom. Under a non-100% zoom, `Emulation.setDeviceMetricsOverride`
  // makes the layout viewport larger than the surface Chromium actually paints, so a route crop
  // keeps an unpainted host-coloured band on the right/bottom. The capture door requires 100% zoom
  // and restores the operator's setting afterwards.
  const originalZoom = await readZoom(cdp)
  const zoomApplied = Boolean(originalZoom && typeof originalZoom.percent === 'number')
  if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
    await setZoomPercent(cdp, 100)
    await sleep(600)
  }
  const captureZoom = (await readZoom(cdp)) || null
  const zoomRecord = {
    original_percent: zoomApplied ? originalZoom.percent : null,
    capture_percent: captureZoom && typeof captureZoom.percent === 'number' ? captureZoom.percent : null,
    bridge_available: zoomApplied
  }

  try {
  // Measure host chrome offset once, then size the viewport so the ROUTE is the requested width.
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

  const cropMode = cropToContent ? 'content' : 'route'
  const routeCrop = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  })()`)
  const contentCrop = probe.route.content_rect
  const crop = cropToContent && contentCrop && contentCrop.width > 0 && contentCrop.height > 0 ? contentCrop : routeCrop
  if (cropToContent && crop === routeCrop) {
    probe.route.host_overlay_trims = probe.route.host_overlay_trims || null
  }

  let png = null
  let pixelCheck = { ok: false, error: 'screenshot not attempted' }
  let captureError = null
  try {
    const shot = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: false,
      clip: { x: crop.x, y: crop.y, width: crop.width, height: crop.height, scale: 1 }
    })
    png = Buffer.from(shot.data, 'base64')
    pixelCheck = await pixelContamination(cdp, png, probe.route.background_color, probe.route.html_background)
  } catch (error) {
    captureError = String(error && error.message ? error.message : error)
  } finally {
    if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
      await setZoomPercent(cdp, originalZoom.percent).catch(() => false)
      await sleep(250)
    }
    zoomRecord.restored_percent = zoomApplied ? (await readZoom(cdp).catch(() => null) || {}).percent ?? null : null
  }
  if (captureError) throw new Error(`screenshot failed: ${captureError}`)

  const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
  const gate = runGates({ probe, expectedSha, requireV3, pixelCheck, zoom: zoomRecord, cropMode })
  if (!gate.ok) writeRefusal('gates', probe, gate)

  writeFileSync(pngPath, png)
  return finishStamp({ probe, gate, png, expectedSha, pageUrl: page.url, shotBox: crop, mode: 'live', cropMode, pixelCheck, zoom: zoomRecord })
  } finally {
    if (zoomApplied && Math.abs(originalZoom.percent - 100) > 0.01) {
      await setZoomPercent(cdp, originalZoom.percent).catch(() => false)
    }
  }
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
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: routeWidth, height: 900, deviceScaleFactor: 2, mobile: false })
  await sleep(150)
  const routeBox = await evaluate(cdp, `(() => {
    const root = document.querySelector('[data-cb-route]')
    const rect = root.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height }
  })()`)
  const contentBox = probe.route.content_rect
  const cropMode = cropToContent ? 'content' : 'route'
  const box = cropToContent && contentBox && contentBox.width > 0 && contentBox.height > 0 ? contentBox : routeBox
  const shot = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
    clip: { x: box.x, y: box.y, width: box.width, height: box.height, scale: 1 }
  })
  const png = Buffer.from(shot.data, 'base64')
  const pixelCheck = await pixelContamination(cdp, png, probe.route.background_color, probe.route.html_background)
  const expectedSha = expectSha ? String(expectSha) : sha256File(pluginPath)
  const gate = runGates({ probe, expectedSha, requireV3, pixelCheck, zoom: null, cropMode })
  if (!gate.ok) {
    cdp.close()
    chromium.kill()
    writeRefusal('gates', probe, gate)
  }
  writeFileSync(pngPath, png)
  cdp.close()
  chromium.kill()
  return finishStamp({ probe, gate, png, expectedSha, pageUrl: target, shotBox: box, mode: 'fixture', cropMode, pixelCheck, zoom: null })
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

const finishStamp = async ({ probe, gate, png, expectedSha, pageUrl, shotBox, mode, cropMode = 'route', pixelCheck = null, zoom = null }) => {
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
      route_ancestors: probe.route.route_ancestors,
      html_background: probe.route.html_background,
      background_color: probe.route.background_color,
      host_overlays: probe.route.host_overlays || [],
      host_overlay_points: probe.route.host_overlay_points,
      host_overlay_sampled: probe.route.host_overlay_sampled,
      host_overlay_fraction: probe.route.host_overlay_fraction,
      host_overlay_trims: probe.route.host_overlay_trims,
      content_width: probe.route.content_width,
      content_height: probe.route.content_height,
      content_rect: probe.route.content_rect
    },
    zoom: zoom,
    console: probe.console || { errors: [], warnings: 0 },
    capture: {
      file: pngPath.split('/').pop(),
      sha256: createHash('sha256').update(png).digest('hex'),
      bytes: png.length,
      crop_mode: cropMode,
      clip: { x: shotBox.x, y: shotBox.y, width: shotBox.width, height: shotBox.height },
      pixel_check: pixelCheck
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
