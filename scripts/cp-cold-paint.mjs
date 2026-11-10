#!/usr/bin/env node
/**
 * CP-000 — cold route paint timing for the current module, with module provenance.
 *
 * Reloads the page with an empty cache, then polls until `[data-cb-route]` is present and has a
 * non-zero box. The number is wall-clock from the reload acknowledgement to that first route box,
 * which includes module re-evaluation, host boot and the first RPC-driven paint. Run it 3+ times
 * and record the median as the v3 baseline.
 *
 * A timing is only a baseline if it is pinned to a module. The script reads the plugin source the
 * WINDOW loaded through `window.hermesDesktop.readPluginSource` (the same door the runtime loader
 * uses), hashes it in-page, and stamps the sha together with the state dir, backend contract
 * (`wire_version`, contract/implemented method counts), theme, route width and page zoom. If the
 * window sha does not match the checkout (or `--expect-sha`), it writes `ok: false` and exits 2 —
 * a number measured on some other build is not a baseline.
 *
 *   node scripts/cp-cold-paint.mjs --cdp-port 9471 --runs 3 \
 *     --state "$COURSEBOOK_TEST_STATE" --backend-url http://127.0.0.1:44291 \
 *     [--expect-sha <sha256>] [--out docs/concept-parity/captures/cold-paint-baseline.json]
 *
 * Fixture mode (tests only — no Electron host):
 *   node scripts/cp-cold-paint.mjs --fixture tests/fixtures/cp-capture/cold-paint.html \
 *     --expect-sha <sha256> --out <dir>/cold.json
 */
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { spawn } from 'node:child_process'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  return args[index + 1] && !args[index + 1].startsWith('--') ? args[index + 1] : true
}
const port = String(flag('cdp-port', process.env.CB015_CDP_PORT || '9337'))
const runs = Number(flag('runs', 3))
const out = flag('out', null)
const pluginPath = resolve(String(flag('plugin', 'desktop/plugin.js')))
const loadedPluginArg = flag('loaded-plugin', null)
const stateDir = flag('state', process.env.COURSEBOOK_TEST_STATE || null)
const backendUrl = flag('backend-url', null)
const token = flag('token', process.env.CB013_TOKEN || '')
const expectSha = flag('expect-sha', null)
const fixture = flag('fixture', null)
// Like-for-like timing: a route a third the width is a different amount of layout and paint, so a
// bare wall-clock number is not comparable to a baseline captured at another geometry. `--emulate
// WxH` pins the layout viewport and `--expect-route-width` refuses a run whose route box does not
// match the baseline's, rather than measuring a different surface and calling it a delta.
const emulateFlag = flag('emulate', null)
const expectRouteWidth = Number(flag('expect-route-width', 0)) || null
const emulate = (() => {
  if (!emulateFlag || emulateFlag === true) return null
  const match = String(emulateFlag).match(/^(\d+)x(\d+)$/)
  if (!match) throw new Error(`--emulate wants WxH, got ${String(emulateFlag)}`)
  return { width: Number(match[1]), height: Number(match[2]) }
})()
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const sha256File = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

class CDP {
  constructor(socket) {
    this.socket = socket
    this.nextId = 1
    this.pending = new Map()
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id && this.pending.has(message.id)) {
        const { done, fail } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) fail(new Error(JSON.stringify(message.error)))
        else done(message.result)
      }
    })
  }
  send(method, params = {}) {
    return new Promise((done, fail) => {
      const id = this.nextId++
      this.pending.set(id, { done, fail })
      this.socket.send(JSON.stringify({ id, method, params }))
    })
  }
  close() { try { this.socket.close() } catch { /* already gone */ } }
}

const connect = async (url) => {
  const socket = new WebSocket(url)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  return new CDP(socket)
}

const evaluate = async (cdp, expression) => {
  const result = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'evaluate failed')
  return result.result.value
}

const attach = async () => {
  if (fixture) {
    const target = /^https?:|^file:/.test(String(fixture)) ? String(fixture) : `file://${resolve(String(fixture))}`
    const debugPort = 9700 + Math.floor(Math.random() * 200)
    const chromium = spawn('chromium', [
      '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${resolve(dirname(resolve(String(out || '.'))), '.chromium-cold-paint')}`,
      'about:blank'
    ], { stdio: 'ignore' })
    let targets = null
    for (let attempt = 0; attempt < 80; attempt += 1) {
      try {
        targets = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()
        if (targets && targets.length) break
      } catch { targets = null }
      await sleep(250)
    }
    if (!targets || !targets.length) {
      chromium.kill()
      throw new Error('fixture chromium did not open a CDP port')
    }
    const page = targets.find((entry) => entry.type === 'page')
    const cdp = await connect(page.webSocketDebuggerUrl)
    await cdp.send('Page.enable')
    await cdp.send('Runtime.enable')
    await cdp.send('Page.navigate', { url: target })
    await sleep(500)
    return { cdp, close: () => { try { cdp.close() } catch {} ; chromium.kill() }, pageUrl: target }
  }
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  const page = targets.find((entry) => entry.type === 'page' && /Hermes/i.test(entry.title || '')) || targets.find((entry) => entry.type === 'page')
  if (!page) throw new Error(`no page target on ${port}`)
  const cdp = await connect(page.webSocketDebuggerUrl)
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  if (emulate) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: emulate.width, height: emulate.height, deviceScaleFactor: 1, mobile: false
    })
  }
  return { cdp, close: () => cdp.close(), pageUrl: page.url }
}

const readProvenance = async (cdp) => {
  const loadedPath = loadedPluginArg
    ? resolve(String(loadedPluginArg))
    : stateDir
      ? resolve(String(stateDir), 'home', 'desktop-plugins', 'coursebook', 'plugin.js')
      : null
  return evaluate(cdp, `(async () => {
    const hashText = async (text) => {
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
      return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
    }
    const route = document.querySelector('[data-cb-route]')
    const rect = route ? route.getBoundingClientRect() : null
    const out = {
      window_sha256: null,
      loaded_path: ${JSON.stringify(loadedPath)},
      bytes: null,
      error: null,
      theme: route ? route.getAttribute('data-cb-scope') : null,
      motion: route ? route.getAttribute('data-cb-motion') : null,
      route_width: rect ? Math.round(rect.width * 100) / 100 : null,
      route_height: rect ? Math.round(rect.height * 100) / 100 : null,
      window_width: innerWidth,
      window_height: innerHeight,
      reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      zoom_percent: null
    }
    const zoom = window.hermesDesktop && window.hermesDesktop.zoom
    if (zoom && zoom.get) {
      try { out.zoom_percent = (await zoom.get()).percent } catch (error) { out.zoom_percent = null }
    }
    if (${JSON.stringify(loadedPath)} && window.hermesDesktop && window.hermesDesktop.readPluginSource) {
      try {
        const read = await window.hermesDesktop.readPluginSource(${JSON.stringify(loadedPath)})
        out.loaded_path = read.path || out.loaded_path
        out.bytes = read.byteSize || read.text.length
        out.window_sha256 = await hashText(read.text)
      } catch (error) {
        out.error = String(error && error.message ? error.message : error)
      }
    }
    return out
  })()`)
}

const readBackend = async () => {
  if (!backendUrl) return null
  try {
    const response = await fetch(`${String(backendUrl).replace(/\/$/, '')}/api/plugins/coursebook/runtime`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (!response.ok) return { url: String(backendUrl), error: `HTTP ${response.status}` }
    const runtime = await response.json()
    return {
      url: String(backendUrl),
      wire_contract: runtime.wire_contract || null,
      wire_version: runtime.wire_version || null,
      contract_methods: runtime.contract_methods || null,
      implemented_count: Array.isArray(runtime.implemented_methods) ? runtime.implemented_methods.length : null,
      plugin_root: runtime.plugin_root || null,
      backend_package: runtime.backend_package || null
    }
  } catch (error) {
    return { url: String(backendUrl), error: String(error && error.message ? error.message : error) }
  }
}

const main = async () => {
  const { cdp, close, pageUrl } = await attach()
  const samples = []
  try {
    for (let run = 0; run < runs; run += 1) {
      await evaluate(cdp, `location.hash = '#/coursebook'`).catch(() => {})
      await sleep(300)
      const oldOrigin = await evaluate(cdp, `performance.timeOrigin`)
      const started = Date.now()
      await cdp.send('Page.reload', { ignoreCache: true })
      let elapsed = null
      let newDocument = false
      for (let attempt = 0; attempt < 800; attempt += 1) {
        const state = await evaluate(cdp, `(() => {
          if (performance.timeOrigin === ${oldOrigin}) return { fresh: false, route: null }
          const root = document.querySelector('[data-cb-route]')
          const rect = root ? root.getBoundingClientRect() : null
          return { fresh: true, route: rect && rect.width > 0 && rect.height > 0 ? { width: rect.width, height: rect.height } : null }
        })()`)
        if (state.fresh) newDocument = true
        if (state.fresh && !state.route && attempt % 8 === 0) {
          await evaluate(cdp, `location.hash = '#/coursebook'`).catch(() => {})
        }
        if (state.fresh && state.route) { elapsed = Date.now() - started; samples.push({ run: run + 1, ms: elapsed, ...state.route }); break }
        await sleep(15)
      }
      if (elapsed === null) samples.push({ run: run + 1, ms: null, new_document: newDocument })
      await sleep(500)
    }

    const provenance = await readProvenance(cdp)
    const backend = await readBackend()
    const values = samples.map((sample) => sample.ms).filter((value) => typeof value === 'number').sort((a, b) => a - b)
    const median = values.length ? values[Math.floor(values.length / 2)] : null
    const expected = expectSha ? String(expectSha) : sha256File(pluginPath)
    const shaMatches = Boolean(provenance.window_sha256) && provenance.window_sha256 === expected
    const routeWidth = provenance.route_width
    const geometryMatches = expectRouteWidth === null || (
      typeof routeWidth === "number" && Math.abs(routeWidth - expectRouteWidth) <= 2
    )
    const result = {
      tool: 'scripts/cp-cold-paint.mjs',
      ok: shaMatches && median !== null && geometryMatches,
      captured_at: new Date().toISOString(),
      measured: '[data-cb-route] present with a non-zero box after Page.reload(ignoreCache)',
      page_url: pageUrl,
      plugin: {
        expected_sha256: expected,
        window_sha256: provenance.window_sha256,
        loaded_path: provenance.loaded_path,
        checkout_path: pluginPath,
        bytes: provenance.bytes,
        error: provenance.error
      },
      state_dir: stateDir ? String(stateDir) : null,
      backend,
      theme: provenance.theme,
      motion: provenance.motion,
      zoom_percent: provenance.zoom_percent,
      reduced_motion: provenance.reduced_motion,
      route_width: provenance.route_width,
      route_height: provenance.route_height,
      window_width: provenance.window_width,
      window_height: provenance.window_height,
      cdp_port: fixture ? null : port,
      emulation: emulate ? { width: emulate.width, height: emulate.height, device_scale_factor: 1 } : null,
      geometry: {
        expect_route_width: expectRouteWidth,
        route_width: routeWidth,
        route_height: provenance.route_height,
        window_width: provenance.window_width,
        window_height: provenance.window_height,
        matches: geometryMatches
      },
      samples,
      median_ms: median,
      min_ms: values[0] ?? null,
      max_ms: values[values.length - 1] ?? null
    }
    if (out) writeFileSync(resolve(String(out)), `${JSON.stringify(result, null, 2)}\n`)
    console.log(JSON.stringify(result, null, 2))
    if (!shaMatches) {
      console.error(`REFUSED: window module sha ${String(provenance.window_sha256)} does not match expected ${expected}; ` +
        'a cold-paint number without module provenance is not a baseline')
      process.exit(2)
    }
    if (!geometryMatches) {
      console.error(`REFUSED: route is ${String(routeWidth)} px wide, expected ${String(expectRouteWidth)} px; ` +
        'a timing at another route width is not comparable to the baseline')
      process.exit(2)
    }
    if (median === null) process.exit(2)
  } finally {
    close()
  }
}

main().catch((error) => {
  console.error(`cold-paint failed: ${error && error.stack ? error.stack.split('\n')[0] : error}`)
  process.exit(3)
})
