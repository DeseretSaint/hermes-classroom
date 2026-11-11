#!/usr/bin/env node
/**
 * VQ-006 — one capture cell for the installed visual capture harness.
 *
 * What this is: the camera. It drives the *installed* plugin in the disposable Desktop rig
 * (`scripts/cb013-live-window.sh`), reaches one product destination at one route width, and writes
 * two files that are the only evidence a screen card may use:
 *
 *   <name>.png    the route itself, clipped to `[data-cb-route]`, at 1x
 *   <name>.json    the machine-readable cell record: destination actually rendered, window and
 *                  plugin sha, fonts/v3/render-error state, the screenshot sha256, and one inventory
 *                  row per image in the route (selector, currentSrc, natural size, rendered size,
 *                  sha256, and whether it is a bundled kit asset, a Press Plate, a data-URI
 *                  stand-in or a placeholder).
 *
 * Why an inventory and not only a screenshot: `docs/launch/VISUAL-QUALITY-PROGRAM.md` Gate 2/5
 * judges *assets*, not pixels. A frame can look plausible while every cover is a typographic
 * fallback; the inventory is what makes that visible and refusable.
 *
 * This script does not decide the verdict. `scripts/vq-manifest.py` applies the rules (missing
 * required image, below 2x, data URI standing in for a kit asset, proof-only page). Keeping the
 * camera and the judge apart is what makes the rules testable without an Electron host.
 *
 * Usage (inside the rig):
 *   node scripts/vq-capture.mjs --destination home --width 1344 \
 *     --out docs/visual-review/vq-006 --cdp-port 9391
 *
 * Destinations: home | discover | classroom | course-home | world-studio | design-system
 *
 *   home          [data-cb-nav-item="home"]
 *   discover      Workshop destination, then its Discover tab
 *   course-home   the first Home shelf card (or --course <course_id>)
 *   classroom     course home, then its "Open section" control
 *   world-studio  course home, then "Open World Studio"
 *   design-system the Design System surface — refused as `missing_surface` when the installed
 *                 plugin does not mount one. A component-lab render harness is never substituted:
 *                 a design fixture is not product evidence.
 *
 * Exit codes: 0 cell written; 1 the window could not be reached; 3 the destination does not exist
 * on this build (a cell record with `surface.missing` is still written); 4 a capture precondition
 * failed (no route, render error, fonts not loaded, proof-only page).
 */
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const argv = process.argv.slice(2)
const arg = (name, fallback = null) => {
  const index = argv.indexOf(`--${name}`)
  if (index < 0) return fallback
  const value = argv[index + 1]
  return value && !value.startsWith('--') ? value : true
}
const outDir = resolve(String(arg('out', 'docs/visual-review/vq-006')))
const destination = String(arg('destination', 'home'))
const width = Number(arg('width', 1344))
const height = Number(arg('height', 768))
const cdpPort = String(arg('cdp-port', process.env.CB015_CDP_PORT || '9337'))
const courseId = arg('course', null)
const pluginPath = arg('plugin', 'desktop/plugin.js') ? resolve(String(arg('plugin', 'desktop/plugin.js'))) : null
const name = String(arg('name', `${destination}--${width}`))
const timeoutMs = Number(arg('timeout', 30000))
const assetsFile = resolve(String(arg('assets', 'desktop/cb-assets.generated.js')))

/* ── a minimal CDP client (same protocol as scripts/cb015-lib.mjs, with an explicit port) ───── */
async function connect(port) {
  const base = `http://127.0.0.1:${port}`
  const targets = await (await fetch(`${base}/json`)).json()
  const page =
    targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) ||
    targets.find((entry) => entry.type === 'page')
  if (!page) throw new Error(`no page target on ${base}`)
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((done, fail) => {
    socket.addEventListener('open', done, { once: true })
    socket.addEventListener('error', fail, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (!message.id || !pending.has(message.id)) return
    const { done, fail } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) fail(new Error(JSON.stringify(message.error)))
    else done(message.result)
  })
  const send = (method, params = {}) =>
    new Promise((done, fail) => {
      const id = nextId++
      pending.set(id, { done, fail })
      socket.send(JSON.stringify({ id, method, params }))
    })
  const api = {
    send,
    close: () => socket.close(),
    async eval(expression) {
      const result = await send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
        userGesture: true
      })
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
      }
      return result.result.value
    },
    wait: (ms) => new Promise((done) => setTimeout(done, ms)),
    async waitFor(expression, label = expression, timeout = timeoutMs) {
      const started = Date.now()
      while (Date.now() - started < timeout) {
        if ((await api.eval(`Boolean(${expression})`).catch(() => false)) === true) {
          return Date.now() - started
        }
        await api.wait(150)
      }
      throw new Error(`timed out waiting for ${label}`)
    }
  }
  return api
}

/* ── the page probe ───────────────────────────────────────────────────────────────────────────
 * Runs inside the renderer. Every value is read from the live DOM; nothing is inferred here.
 * `payload.assets` is the CB_ASSETS index (sha256 -> {key, path, role}) so a data URI that is a
 * shipped, hashed brand asset is distinguishable from a data URI invented for a display plate.
 */
async function pageProbe(payload) {
  const route = document.querySelector('[data-cb-route]')
  const round = (n) => Math.round(n * 100) / 100
  const nearestMarker = (el) => {
    const marks = []
    let node = el
    let guard = 0
    while (node && guard < 40) {
      guard += 1
      if (node.hasAttribute) {
        for (const attr of node.attributes) {
          if (!attr.name.startsWith('data-cb')) continue
          marks.push(`${attr.name}=${attr.value === '' ? '""' : attr.value}`)
        }
      }
      if (node === route || node === document.body) break
      node = node.parentElement
    }
    return marks
  }
  const kindOf = (marks) => {
    const has = (prefix) => marks.some((m) => m.startsWith(prefix))
    if (has('data-cb3-fox=')) return 'fox_pose'
    if (has('data-cb3-feature-art')) return 'scene_plate' // the Discover banner plate
    if (has('data-cb3-scene=')) return 'scene_plate'
    if (has('data-cb3-cover=')) return 'cover_plate'
    if (has('data-cb-home-cover-plate')) return 'cover_plate'
    if (has('data-cb-workshop-cover-image')) return 'workshop_cover'
    if (has('data-cb-slot-cover=')) return 'artifact_media'
    return 'unknown'
  }
  const selectorOf = (el) => {
    const marker = nearestMarker(el)
      .filter((m) => !/^data-cb-route=/.test(m))
      .slice(0, 2)
      .map((m) => {
        const split = m.indexOf('=')
        const attr = m.slice(0, split)
        const value = m.slice(split + 1).replace(/^"(.*)"$/, '$1')
        return value === '' ? `[${attr}]` : `[${attr}="${value.replace(/"/g, '\\"')}"]`
      })
    const tag = el.tagName.toLowerCase()
    return `${marker.length ? marker.join(' ') : '[data-cb-route]'} > ${tag}`
  }
  const digestBytes = async (bytes) => {
    const digest = await crypto.subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }
  const fetchSha = async (url) => {
    try {
      const response = await fetch(url, { credentials: 'include' })
      if (!response.ok) return { sha256: null, bytes: null, error: `http ${response.status}` }
      const buffer = await response.arrayBuffer()
      return { sha256: await digestBytes(buffer), bytes: buffer.byteLength, error: null }
    } catch (error) {
      return { sha256: null, bytes: null, error: String(error && error.message ? error.message : error) }
    }
  }
  const dataUriSha = async (url) => {
    try {
      const comma = url.indexOf(',')
      const meta = url.slice(5, comma)
      const text = url.slice(comma + 1)
      let bytes
      if (/;base64/.test(meta)) {
        const binary = atob(text)
        bytes = new Uint8Array(binary.length)
        for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
      } else {
        bytes = new TextEncoder().encode(decodeURIComponent(text))
      }
      return { sha256: await digestBytes(bytes), bytes: bytes.length, error: null }
    } catch (error) {
      return { sha256: null, bytes: null, error: String(error && error.message ? error.message : error) }
    }
  }

  if (!route) return { route: null }
  const routeRect = route.getBoundingClientRect()
  const images = [...route.querySelectorAll('img')]
  const inventory = []
  for (const img of images) {
    const marks = nearestMarker(img)
    const rect = img.getBoundingClientRect()
    const currentSrc = img.currentSrc || img.src || ''
    const isData = currentSrc.startsWith('data:')
    const sha = isData ? await dataUriSha(currentSrc) : await fetchSha(currentSrc)
    const bundled = sha && sha.sha256 ? payload.assets[sha.sha256] || null : null
    const naturalWidth = img.naturalWidth || 0
    const naturalHeight = img.naturalHeight || 0
    inventory.push({
      selector: selectorOf(img),
      markers: marks.slice(0, 6),
      kind: kindOf(marks),
      src_attr: (img.getAttribute('src') || '').slice(0, 200),
      current_src: currentSrc.startsWith('data:') ? `data:${currentSrc.slice(5, 40)}…` : currentSrc,
      current_src_data_uri: isData,
      natural: { width: naturalWidth, height: naturalHeight },
      rendered: { width: round(rect.width), height: round(rect.height) },
      scale_ratio: rect.width > 0 ? round(naturalWidth / rect.width) : null,
      sha256: sha && sha.sha256 ? sha.sha256 : null,
      sha_error: sha ? sha.error : 'no source',
      bytes: sha ? sha.bytes : null,
      bundled_asset: bundled,
      alt: img.getAttribute('alt') || '',
      complete: Boolean(img.complete)
    })
  }
  const backgrounds = []
  for (const el of route.querySelectorAll('*')) {
    const style = getComputedStyle(el)
    const value = style.backgroundImage
    if (!value || !value.startsWith('url(')) continue
    const url = value.slice(5, -2).replace(/^["']|["']$/g, '')
    const rect = el.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) continue
    const loaded = await new Promise((done) => {
      const probe = new Image()
      probe.onload = () => done({ width: probe.naturalWidth, height: probe.naturalHeight })
      probe.onerror = () => done({ width: 0, height: 0 })
      probe.src = url
    })
    const sha = url.startsWith('data:') ? await dataUriSha(url) : await fetchSha(url)
    const bundled = sha && sha.sha256 ? payload.assets[sha.sha256] || null : null
    backgrounds.push({
      selector: selectorOf(el),
      url: url.startsWith('data:') ? `data:${url.slice(5, 40)}…` : url,
      data_uri: url.startsWith('data:'),
      natural: loaded,
      rendered: { width: round(rect.width), height: round(rect.height) },
      sha256: sha && sha.sha256 ? sha.sha256 : null,
      bundled_asset: bundled,
      marks: nearestMarker(el).slice(0, 4)
    })
  }
  const fontsOk = document.fonts.status === 'loaded'
  const h1 = route.querySelector('h1')
  return {
    route: {
      selector: '[data-cb-route]',
      present: true,
      marker: route.getAttribute('data-cb-route'),
      destination: route.getAttribute('data-cb-destination'),
      scope: route.getAttribute('data-cb-scope'),
      motion: route.getAttribute('data-cb-motion'),
      v3_ready: Boolean(document.querySelector('[data-cb-v3-ready]')),
      v3_textures: route.getAttribute('data-cb-v3-textures'),
      width: round(routeRect.width),
      height: round(routeRect.height),
      scroll_height: route.scrollHeight,
      top: round(routeRect.top),
      left: round(routeRect.left),
      window_width: window.innerWidth,
      window_height: window.innerHeight,
      fonts_status: document.fonts.status,
      fonts_ok: fontsOk,
      page_title: h1 ? h1.textContent.trim().slice(0, 120) : null,
      course_home: (() => {
        const el = document.querySelector('[data-cb-course-home]')
        return el ? el.getAttribute('data-cb-course-home') : null
      })(),
      lesson_view: (() => {
        const el = document.querySelector('[data-cb-lesson-view]')
        return el ? el.getAttribute('data-cb-lesson-view') : null
      })(),
      scene: (() => {
        const el = document.querySelector('[data-cb3-scene]')
        return el ? el.getAttribute('data-cb3-scene') : null
      })(),
      surfaces_probed: payload.probes.map((selector) => ({
        selector,
        present: Boolean(document.querySelector(selector))
      })),
      render_error_markers: [
        '[data-cb-render-error]',
        '[data-cb-route-error]',
        '[data-cb-error-page]'
      ].filter((selector) => Boolean(document.querySelector(selector))),
      proof_markers: ['[data-cb-proof]', '[data-vq-proof]', '#vq-proof-root'].filter((selector) =>
        Boolean(document.querySelector(selector))
      )
    },
    page: {
      url: location.href,
      protocol: location.protocol,
      proof_script: Boolean(window.__VQ_PROOF__ || window.__CP000_FIXTURE__),
      images: inventory,
      backgrounds
    }
  }
}

/* ── CB_ASSETS index: sha256 -> {key, path, role} ─────────────────────────────────────────── */
function loadAssetIndex(path) {
  if (!existsSync(path)) return {}
  const text = readFileSync(path, 'utf8')
  const start = text.indexOf('Object.freeze(')
  if (start < 0) return {}
  const open = text.indexOf('{', start)
  let depth = 0
  let end = -1
  for (let index = open; index < text.length; index += 1) {
    if (text[index] === '{') depth += 1
    else if (text[index] === '}') {
      depth -= 1
      if (depth === 0) {
        end = index + 1
        break
      }
    }
  }
  if (end < 0) return {}
  let parsed
  try {
    parsed = JSON.parse(text.slice(open, end))
  } catch {
    return {}
  }
  const index = {}
  for (const [key, row] of Object.entries(parsed.assets || {})) {
    if (!row || !row.sha256) continue
    index[row.sha256] = { key, path: row.path || null, role: row.role || null, group: row.group || null }
  }
  return index
}

const PROBES = {
  'design-system': ['[data-cb-design-system]', '[data-cb3-surface="component.lab"]', '[data-cb3-lab]', '[data-cb-nav-item="system"]'],
  'world-studio': ['[data-cb-course-world-studio]', '[data-cb-world-studio]'],
  classroom: ['[data-cb-lesson-view]', '[data-cb3-scene]', '[data-cb-continue]'],
  'course-home': ['[data-cb-course-home]'],
  discover: ['[data-cb-workshop-tab="discover"]', '[data-cb-workshop]'],
  home: ['[data-cb-home-card]', '[data-cb-home-invitation]', '[data-cb-desk]']
}

const say = (message) => console.log(message)
const sha256File = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

async function clickText(cdp, text, { within = '[data-cb-route]' } = {}) {
  const box = await cdp.eval(`(() => {
    const root = document.querySelector(${JSON.stringify(within)}) || document
    const wanted = ${JSON.stringify(text)}
    const all = [...root.querySelectorAll('button, a, [role="button"], [role="tab"]')]
    const el = all.find((node) => (node.innerText || '').trim() === wanted)
    if (!el) return null
    el.scrollIntoView({ block: 'center', inline: 'center' })
    const rect = el.getBoundingClientRect()
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, label: wanted }
  })()`)
  if (!box) throw new Error(`no control labelled ${JSON.stringify(text)} inside ${within}`)
  for (const type of ['mousePressed', 'mouseReleased']) {
    await cdp.send('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 })
  }
  return box
}

async function clickSelector(cdp, selector) {
  const box = await cdp.eval(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)})
    if (!el) return null
    el.scrollIntoView({ block: 'center', inline: 'center' })
    const rect = el.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) return null
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
  })()`)
  if (!box) return null
  for (const type of ['mousePressed', 'mouseReleased']) {
    await cdp.send('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 })
  }
  return box
}

async function ensureRoute(cdp) {
  const hasRoute = await cdp.eval("Boolean(document.querySelector('[data-cb-route]'))")
  if (hasRoute) return
  const decision = await cdp.eval("localStorage.getItem('hermes.desktop.pluginDecisions.v2')")
  let enabled = false
  try {
    enabled = Boolean(decision && JSON.parse(decision).coursebook)
  } catch {
    enabled = false
  }
  if (!enabled) {
    await cdp.eval(
      "localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))"
    )
    await cdp.send('Page.reload', { ignoreCache: false })
    await cdp.wait(4000)
  }
  await cdp.eval("location.hash = '#/coursebook'")
  await cdp.waitFor("Boolean(document.querySelector('[data-cb-route]'))", 'the Coursebook route')
  await cdp.wait(600)
}

async function warmLazyImages(cdp) {
  // Course cards carry `loading="lazy"` covers. An image that never entered the viewport is not a
  // placeholder, so the harness walks the route's scroll container once and returns to the top
  // before it measures anything.
  return cdp.eval(`(async () => {
    const route = document.querySelector('[data-cb-route]')
    if (!route) return null
    let node = route
    let scroller = document.scrollingElement
    while (node && node !== document.body) {
      const style = getComputedStyle(node)
      if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 4) {
        scroller = node
        break
      }
      node = node.parentElement
    }
    const step = Math.max(200, Math.round(scroller.clientHeight * 0.8))
    for (let index = 0; index < 14; index += 1) {
      if (scroller.scrollTop >= scroller.scrollHeight - scroller.clientHeight) break
      scroller.scrollTop = Math.min(scroller.scrollHeight, scroller.scrollTop + step)
      await new Promise((r) => setTimeout(r, 140))
    }
    scroller.scrollTop = 0
    await new Promise((r) => setTimeout(r, 250))
    return {
      scroller: scroller.tagName.toLowerCase() + '.' + String(scroller.className || '').split(/\\s+/).slice(0, 2).join('.'),
      scroll_height: scroller.scrollHeight,
      client_height: scroller.clientHeight
    }
  })()`)
}

async function openCourse(cdp, courseId) {
  const candidates = [
    courseId ? `[data-cb-course-id="${courseId}"] [data-cb-home-card-action]` : null,
    courseId ? `[data-cb-course-id="${courseId}"]` : null,
    '[data-cb-home-card-action]',
    '[data-cb-home-scene-card]',
    '[data-cb-home-card]'
  ].filter(Boolean)
  const present = `Boolean(${JSON.stringify(candidates)}.some((selector) => document.querySelector(selector)))`
  const openHome = async () => {
    await clickSelector(cdp, '[data-cb-nav-item="home"]')
    await cdp.wait(500)
    await warmLazyImages(cdp)
  }
  await openHome()
  try {
    await cdp.waitFor(present, 'a Home shelf card', 25000)
  } catch {
    // A cold library read can answer after the first route paint; one reload retries the shelf.
    await cdp.send('Page.reload', { ignoreCache: false })
    await cdp.wait(3500)
    await ensureRoute(cdp)
    await openHome()
    await cdp.waitFor(present, 'a Home shelf card', 25000)
  }
  let clicked = null
  for (const selector of candidates) {
    clicked = await clickSelector(cdp, selector)
    if (clicked) break
  }
  if (!clicked) throw new Error(`no Home shelf card is addressable (tried ${candidates.join(', ')})`)
  await cdp.waitFor("Boolean(document.querySelector('[data-cb-course-home]'))", 'the course home', 25000)
  await cdp.wait(800)
  await warmLazyImages(cdp)
  const opened = await cdp.eval(
    "(() => { const el = document.querySelector('[data-cb-course-home]'); return el ? el.getAttribute('data-cb-course-home') : null })()"
  )
  if (courseId && opened !== courseId) {
    throw new Error(`opened course ${opened} but the cell asked for ${courseId}`)
  }
  return opened
}

async function navigate(cdp, destination) {
  // Every destination starts from the route and uses the product's own control.
  await cdp.eval("location.hash = '#/coursebook'")
  await cdp.wait(300)
  if (destination === 'home') {
    await clickSelector(cdp, '[data-cb-nav-item="home"]')
    await cdp.waitFor(`Boolean(document.querySelector('[data-cb-destination="home"]'))`, 'Home')
    return { control: '[data-cb-nav-item="home"]' }
  }
  if (destination === 'discover') {
    await clickSelector(cdp, '[data-cb-nav-item="workshop"]')
    await cdp.waitFor("Boolean(document.querySelector('[data-cb-workshop]'))", 'the Workshop surface')
    const tab = await clickSelector(cdp, '[data-cb-workshop-tab="discover"]')
    if (!tab) throw new Error('the Workshop has no Discover tab control')
    await cdp.wait(700)
    return { control: '[data-cb-nav-item="workshop"] + [data-cb-workshop-tab="discover"]' }
  }
  if (destination === 'course-home') {
    const opened = await openCourse(cdp, courseId)
    return { control: '[data-cb-home-card-action]', course_home_id: opened }
  }
  if (destination === 'classroom') {
    const opened = await openCourse(cdp, courseId)
    await clickText(cdp, 'Open section')
    await cdp.waitFor(
      "Boolean(document.querySelector('[data-cb-lesson-view]') || document.querySelector('[data-cb3-scene]'))",
      'the classroom surface',
      20000
    )
    await cdp.wait(1200)
    return { control: '[data-cb-trailhead-actions] "Open section"', course_home_id: opened }
  }
  if (destination === 'world-studio') {
    const opened = await openCourse(cdp, courseId)
    const probes = [
      '[data-cb-world-change]',
      '[data-cb-world-open-studio]',
      '[data-cb-course-world-studio]'
    ]
    let control = null
    for (const selector of probes) {
      if (await clickSelector(cdp, selector)) { control = selector; break }
    }
    if (!control) {
      for (const label of ['Review the world', 'Open World Studio']) {
        try { await clickText(cdp, label); control = `text:${label}`; break } catch { /* next */ }
      }
    }
    if (!control) {
      // The approved-world hero and the studio entry live on the course *detail* surface, which the
      // Courses destination opens; the Home desk does not carry them.
      await clickSelector(cdp, '[data-cb-nav-item="courses"]')
      await cdp.wait(600)
      try { await clickText(cdp, 'Open course') } catch {
        throw Object.assign(new Error('no course row control labelled "Open course"'), { missing: true })
      }
      await cdp.waitFor("Boolean(document.querySelector('[data-cb-course-detail]'))", 'the course detail', 20000)
      await cdp.wait(800)
      for (const selector of probes) {
        if (await clickSelector(cdp, selector)) { control = selector; break }
      }
      if (!control) {
        for (const label of ['Review the world', 'Open World Studio']) {
          try { await clickText(cdp, label); control = `text:${label}`; break } catch { /* next */ }
        }
      }
    }
    if (!control) throw new Error('no World Studio control on the course surface')
    await cdp.waitFor("Boolean(document.querySelector('[data-cb-world-studio]'))", 'the World Studio', 20000)
    await cdp.wait(800)
    return { control }
  }
  if (destination === 'design-system') {
    for (const selector of PROBES['design-system']) {
      const clicked = await clickSelector(cdp, selector)
      if (clicked) {
        await cdp.wait(800)
        return { control: selector }
      }
    }
    throw Object.assign(new Error('the installed plugin mounts no Design System surface'), {
      missing: true
    })
  }
  throw new Error(`unknown destination ${destination}`)
}

async function fitRouteWidth(cdp, target) {
  const read = () => cdp.eval("Math.round(document.querySelector('[data-cb-route]').getBoundingClientRect().width)")
  const base = await cdp.eval(
    `({ w: window.innerWidth, r: Math.round(document.querySelector('[data-cb-route]').getBoundingClientRect().width) })`
  )
  const chrome = Math.max(0, base.w - base.r)
  let viewport = target + chrome
  let measured = base.r
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: viewport,
      height,
      deviceScaleFactor: 1,
      mobile: false
    })
    await cdp.wait(250)
    measured = await read()
    if (Math.abs(measured - target) <= 1) break
    viewport += target - measured
  }
  return { requested: target, route_width: measured, viewport_width: viewport, chrome }
}

async function main() {
  mkdirSync(outDir, { recursive: true })
  const pngPath = resolve(outDir, `${name}.png`)
  const jsonPath = resolve(outDir, `${name}.json`)
  let cdp
  try {
    cdp = await connect(cdpPort)
  } catch (error) {
    say(`vq-capture: cannot reach the rig on 127.0.0.1:${cdpPort}: ${error.message}`)
    return 1
  }
  const record = {
    schema: 'vq.capture.v1',
    cell: { name, destination, width, height },
    captured_at: new Date().toISOString(),
    window: { cdp_port: Number(cdpPort) },
    route: null,
    surface: { requested: destination, resolved: null, control: null, missing: null },
    screenshot: null,
    images: [],
    backgrounds: [],
    page: null,
    error: null
  }
  let exit = 0
  try {
    await cdp.send('Runtime.enable', {})
    await cdp.send('Page.enable', {})
    // Every cell starts from a fresh document: a course home, a classroom and the World Studio are
    // React shell state, and the only reproducible way back to global Home is a reload.
    await cdp.send('Page.reload', { ignoreCache: false })
    await cdp.wait(2500)
    await ensureRoute(cdp)
    const nav = await navigate(cdp, destination)
    record.surface.control = nav.control
    if (nav.course_home_id) record.surface.course_home_id = nav.course_home_id
    record.lazy = await warmLazyImages(cdp).catch(() => null)
    const fit = await fitRouteWidth(cdp, width)
    record.route_request = fit
    // A destination click can trigger a read; settle until every image has decoded or 15 s pass.
    const settleStart = Date.now()
    while (Date.now() - settleStart < 15000) {
      const pending = await cdp.eval(
        "[...document.querySelectorAll('[data-cb-route] img')].filter((img) => !img.complete || img.naturalWidth === 0).length"
      )
      if (pending === 0) break
      await cdp.wait(300)
    }
    await cdp.wait(400)
    const assetIndex = loadAssetIndex(assetsFile)
    const probe = await cdp.eval(
      `(${pageProbe.toString()})(${JSON.stringify({
        assets: assetIndex,
        probes: PROBES[destination] || []
      })})`
    )
    record.route = probe.route
    record.images = probe.page.images
    record.backgrounds = probe.page.backgrounds
    record.page = { url: probe.page.url, protocol: probe.page.protocol, proof_script: probe.page.proof_script }
    record.surface.resolved = probe.route ? probe.route.destination : null
    record.window.plugin = await cdp
      .eval(
        `(async () => {
          const path = ${JSON.stringify(pluginPath)}
          if (!path || !window.hermesDesktop || !window.hermesDesktop.readPluginSource) {
            return { error: 'readPluginSource unavailable' }
          }
          try {
            const read = await window.hermesDesktop.readPluginSource(path)
            const bytes = new TextEncoder().encode(read.text)
            const digest = await crypto.subtle.digest('SHA-256', bytes)
            const sha256 = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
            return { loaded_path: read.path || path, bytes: read.byteSize || read.text.length, sha256 }
          } catch (error) {
            return { error: String(error && error.message ? error.message : error) }
          }
        })()`
      )
      .catch((error) => ({ error: error.message }))
    const clip = {
      x: Math.round(probe.route.left),
      y: Math.round(probe.route.top),
      width: Math.round(probe.route.width),
      height: Math.min(Math.round(probe.route.height), height),
      scale: 1
    }
    const shot = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip
    })
    writeFileSync(pngPath, Buffer.from(shot.data, 'base64'))
    record.screenshot = {
      file: `${name}.png`,
      sha256: sha256File(pngPath),
      bytes: readFileSync(pngPath).byteLength,
      clip
    }
    await cdp.send('Emulation.clearDeviceMetricsOverride')

    const route = record.route
    const problems = []
    if (!route || !route.present) problems.push('no [data-cb-route] after navigation')
    if (route && route.render_error_markers.length) problems.push(`render error: ${route.render_error_markers.join(', ')}`)
    if (route && !route.fonts_ok) problems.push(`fonts not loaded (${route.fonts_status})`)
    if (record.page.protocol !== 'http:' && record.page.protocol !== 'https:') problems.push(`not a live page (${record.page.protocol})`)
    if (record.page.proof_script) problems.push('proof fixture script detected')
    if (route && route.proof_markers.length) problems.push(`proof-only markers: ${route.proof_markers.join(', ')}`)
    if (route && expectedDestination(destination) && route.destination !== expectedDestination(destination)) {
      problems.push(`rendered ${route.destination}, expected ${expectedDestination(destination)}`)
    }
    if (problems.length) {
      record.error = problems.join('; ')
      exit = 4
    }
    } catch (error) {
    if (error.missing) {
      record.surface.missing = {
        reason: error.message,
        probed: PROBES[destination] || [],
        installed_destinations: await cdp
          .eval("[...document.querySelectorAll('[data-cb-nav-item]')].map((el) => el.getAttribute('data-cb-nav-item'))")
          .catch(() => [])
      }
      record.error = error.message
      exit = 3
    } else {
      record.error = error.message
      exit = 4
    }
    // A surface that does not exist gets no screenshot: a picture of whatever was on screen would
    // be a Home frame wearing a Design System name, which is exactly the confusion this packet
    // exists to prevent. A failed *capture* of a surface that does exist keeps its screenshot.
    if (!error.missing) {
      try {
        const shot = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
        writeFileSync(pngPath, Buffer.from(shot.data, 'base64'))
        record.screenshot = { file: `${name}.png`, sha256: sha256File(pngPath), bytes: readFileSync(pngPath).byteLength, clip: null }
      } catch {
        /* no page to photograph */
      }
    }
  } finally {
    cdp.close()
  }
  writeFileSync(jsonPath, `${JSON.stringify(record, null, 2)}\n`)
  say(`vq-capture: ${name} -> ${exit === 0 ? 'ok' : record.error}`)
  say(`  ${jsonPath}`)
  return exit
}

function expectedDestination(destination) {
  // A lesson, a course home and the World Studio are shell state under the Home destination, so
  // the route's own `data-cb-destination` is `home` for all three. Discover is the Workshop
  // destination. The Design System, when a build mounts one, is its own surface.
  const map = {
    home: 'home',
    discover: 'workshop',
    'course-home': 'home',
    classroom: 'home',
    'world-studio': 'home',
    'design-system': null
  }
  return map[destination] ?? null
}

main().then((code) => process.exit(code))
