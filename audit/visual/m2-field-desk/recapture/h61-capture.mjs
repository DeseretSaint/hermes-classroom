#!/usr/bin/env node
/**
 * H-61 — recapture the Field Desk live evidence on the learning-cockpit build.
 *
 * Drives the plugin inside the isolated Hermes Desktop window (Electron, CDP 9361) against a real
 * Coursebook backend, and records what the renderer actually painted and measured.
 *
 *   window -> 127.0.0.1:44281 (loopback proxy) -> 44291 (course data) | 44292 (empty profile)
 *
 * The proxy only forwards, delays, or refuses; it never rewrites a Coursebook response. The
 * 6 s delay exists to hold the desk's own loader on screen long enough for a real frame; the
 * `down` mode is the same thing an unreachable backend does. Nothing in desk output is synthesised.
 *
 *   node h61-capture.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { execFileSync } from 'node:child_process'

const PORT = process.env.CB615_CDP_PORT || '9361'
const STATE = process.env.CB615_PROXY_STATE || '/tmp/h61-proxy-state.json'
const OUT = new URL('..', import.meta.url).pathname.replace(/\/$/, '')
const DESK = `${OUT}/live-evidence.json`
const RIG_STATE = process.env.COURSEBOOK_TEST_STATE || `${process.env.HOME}/.hermes/coursebook-test-h61fd`
const CHECKOUT = new URL('../../../..', import.meta.url).pathname.replace(/\/$/, '')
let HOST_ZOOM = 1
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const setProxy = (obj) => writeFileSync(STATE, JSON.stringify(obj))

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no Desktop page target on CDP ' + PORT)
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { socket.addEventListener('open', res, { once: true }); socket.addEventListener('error', rej, { once: true }) })
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) {
    const { res, rej } = pending.get(m.id)
    pending.delete(m.id)
    m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)
  }
})
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = nextId++
  pending.set(id, { res, rej })
  socket.send(JSON.stringify({ id, method, params }))
})
const ev = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result.value
}
const waitFor = async (expr, label, ms = 30000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await ev(expr)) return true
    await sleep(300)
  }
  throw new Error('timeout: ' + label)
}
const shot = async (name) => {
  const data = await send('Page.captureScreenshot', { format: 'png', fromSurface: false })
  const buf = Buffer.from(data.data, 'base64')
  writeFileSync(`${OUT}/${name}`, buf)
  if (buf.length < 8000) throw new Error(`blank-looking frame ${name} (${buf.length} B)`)
  return buf.length
}
const setViewport = async (width, height) => {
  await send('Emulation.clearDeviceMetricsOverride')
  await sleep(200)
  const zoom = HOST_ZOOM
  let deviceWidth = Math.round(width * zoom)
  let deviceHeight = Math.round(height * zoom)
  await send('Emulation.setDeviceMetricsOverride', { width: deviceWidth, height: deviceHeight, deviceScaleFactor: 1, mobile: false })
  await sleep(400)
  const got = await ev('[innerWidth, innerHeight]')
  if (Math.abs(got[0] - width) > 6) {
    const fw = got[0] / width
    const fh = got[1] / height
    await send('Emulation.setDeviceMetricsOverride', { width: Math.round(deviceWidth * fw), height: Math.round(deviceHeight * fh), deviceScaleFactor: 1, mobile: false })
    await sleep(400)
  }
  return await ev('JSON.stringify([innerWidth, innerHeight])')
}
const route = (hash) => ev(`location.hash = ${JSON.stringify(hash)}`)
const openRoute = async ({ reload = false, target, delay_ms = 0, down = false } = {}) => {
  setProxy({ target, delay_ms, down })
  if (reload) {
    await send('Page.reload', { ignoreCache: false })
    await sleep(2500)
  }
  await ev(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
  await route('#/')
  await sleep(500)
  await route('#/coursebook')
  await sleep(900)
}

const MEASURE = `(() => {
  const route = document.querySelector('[data-cb-route]')
  const desk = document.querySelector('[data-cb-desk]')
  const q = (sel) => document.querySelector(sel)
  const qa = (sel) => [...document.querySelectorAll(sel)]
  const txt = (sel) => { const el = q(sel); return el ? (el.innerText || '').replace(/\\s+/g, ' ').trim() : null }
  const cs = route ? getComputedStyle(route) : null
  const vars = ['--cb-paper','--cb-paper-raised','--cb-ink','--cb-ink-soft','--cb-rule','--cb-accent','--cb-accent-soft','--cb-field','--cb-ochre','--cb-coral']
  const tokens = cs ? Object.fromEntries(vars.map((v) => [v, cs.getPropertyValue(v).trim()])) : null
  const root = document.documentElement
  const unnamed = [...(route || document).querySelectorAll('button, a[href], [role="button"]')].filter((b) => {
    const n = (b.getAttribute('aria-label') || b.innerText || b.getAttribute('title') || '').replace(/\\s+/g, ' ').trim()
    return !n
  }).length
  const items = qa('[data-cb-path-item]').map((el) => ({
    id: el.getAttribute('data-cb-path-item'),
    state: el.getAttribute('data-cb-path-state'),
    current: el.getAttribute('data-cb-path-current') === 'true',
    title: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 140)
  }))
  const stats = {}
  qa('[data-cb-desk-stat]').forEach((el) => { stats[el.getAttribute('data-cb-desk-stat')] = (el.innerText || '').replace(/\\s+/g, ' ').trim() })
  const active = document.activeElement
  return JSON.stringify({
    hash: location.hash,
    url: location.href.split('#')[0] + location.hash,
    route: !!route,
    route_attrs: route ? Object.fromEntries([...route.attributes].map((a) => [a.name, String(a.value).slice(0, 120)])) : null,
    desk_state: desk ? desk.getAttribute('data-cb-desk') : null,
    scope_mode: route ? route.getAttribute('data-cb-scope') : null,
    tokens,
    continue_course: txt('[data-cb-desk-course]'),
    continue_section: txt('[data-cb-continue-section]'),
    position_label: txt('[data-cb-continue-position]'),
    estimate_label: txt('[data-cb-continue-minutes]'),
    touched: txt('[data-cb-continue-touched]'),
    next_label: txt('[data-cb-continue-next]'),
    stats,
    path_items: items.length,
    path_states: items.map((i) => i.state),
    path_titles: items.map((i) => i.title),
    path_current: items.filter((i) => i.current).length,
    path_summary: txt('[data-cb-path-summary]'),
    courses_listed: qa("[data-cb-all-courses-row]").length,
    sources_drawer: q('[data-cb-sources-drawer]') ? q('[data-cb-sources-drawer]').getAttribute('data-cb-sources-drawer') : null,
    sources_count: qa("[data-cb-desk-source]").length,
    note_count: qa("[data-cb-field-note]").length,
    table_count: document.querySelectorAll('table').length,
    horizontal_overflow: root.scrollWidth > root.clientWidth + 1,
    scroll_width: root.scrollWidth,
    client_width: root.clientWidth,
    inner: [innerWidth, innerHeight],
    body_text_head: (route ? route.innerText : document.body.innerText).replace(/\\s+/g, ' ').trim().slice(0, 700),
    unnamed_controls: unnamed,
    active_element: active ? { tag: active.tagName, name: (active.getAttribute('aria-label') || active.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60) } : null
  })
})()`

const frames = []
const capture = async (id, meta) => {
  const m = JSON.parse(await ev(MEASURE))
  const body = await ev('((document.querySelector("[data-cb-route]") || document.body).innerText || "").slice(0, 6000)')
  const overlay = /CONNECTING|couldn.t start/i.test(body)
  if (overlay) throw new Error(`host overlay on screen for ${id}: ${body.slice(0, 120)}`)
  if (!m.route) throw new Error(`no Coursebook route for ${id}`)
  const bytes = await shot(id)
  frames.push({ id, bytes, ...meta, ...m })
  console.log(`${id}: desk=${m.desk_state} route=${m.route} ${m.inner.join('x')} bytes=${bytes}`)
  return m
}

try {
  await send('Page.enable')
  await send('Emulation.clearDeviceMetricsOverride')
  await sleep(600)
  HOST_ZOOM = await ev('(outerWidth || innerWidth) / innerWidth')
  console.log('host zoom', HOST_ZOOM, 'inner', await ev('JSON.stringify([innerWidth, innerHeight, outerWidth, outerHeight])'))

  // 1 — ready: real course rows from the course-data backend, wide cockpit.
  await openRoute({ reload: true, target: 'http://127.0.0.1:44291' })
  await waitFor(`document.querySelector('[data-cb-desk]')?.getAttribute('data-cb-desk') === 'ready'`, 'ready desk')
  await setViewport(1280, 1500)
  await sleep(1200)
  await capture('live-01-real.png', { desk_state_claim: 'ready', backend: '44291 (course data)', viewport_note: '1280x1500 emulated CSS viewport in the isolated window: the whole cockpit in one frame' })

  // 2 — sources drawer opened on the continued section.
  await ev(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const b = [...root.querySelectorAll('button')].find((x) => /sources/i.test(x.innerText || ''))
    if (!b) return 'missing'
    b.click()
    return 'clicked'
  })()`)
  await sleep(2000)
  const drawer = await ev(`document.querySelector('[data-cb-sources-drawer]')?.getAttribute('data-cb-sources-drawer') || 'absent'`)
  console.log('sources drawer:', drawer)
  await ev(`(() => { const d = document.querySelector('[data-cb-sources-drawer]'); if (d) d.scrollIntoView({ block: 'center' }); return true })()`)
  await sleep(900)
  await capture('live-03-sources-open.png', { desk_state_claim: 'ready, drawer open', backend: '44291 (course data)', viewport_note: 'drawer scrolled into view' })
  await ev(`(() => { const b = [...document.querySelectorAll('[data-cb-route] button')].find((x) => /sources/i.test(x.innerText || '')); if (b) b.click(); return true })()`)
  await sleep(600)

  // 3 — backend off: the loopback transport refuses, exactly as a stopped backend does.
  await openRoute({ reload: true, target: 'http://127.0.0.1:44291', down: true })
  await waitFor(`/could not|unavailable|offline|backend/i.test(document.querySelector('[data-cb-route]')?.innerText || '')`, 'backend-off screen')
  await sleep(1500)
  await capture('live-02-backend-off.png', { desk_state_claim: 'backend off', backend: 'refused by the loopback transport (503)' })

  // 4 — empty profile: a second isolated home with no Coursebook database.
  await openRoute({ reload: true, target: 'http://127.0.0.1:44292' })
  await waitFor(`document.querySelector('[data-cb-desk]')?.getAttribute('data-cb-desk') === 'empty'`, 'empty desk')
  await sleep(1000)
  await capture('live-04-empty.png', { desk_state_claim: 'empty (first run)', backend: '44292 (fresh home, no coursebook data.db)' })

  // 5 — loading: the desk's own loader, held open by a 6 s transport delay, then released.
  setProxy({ target: 'http://127.0.0.1:44291', delay_ms: 6000 })
  await send('Page.reload', { ignoreCache: false })
  await sleep(400)
  await waitFor(`!!document.querySelector('[data-cb-desk="loading"]')`, 'desk loader', 10000)
  await setViewport(1280, 900)
  await capture('live-05-loading.png', { desk_state_claim: 'loading', backend: '44291 behind a 6 s transport delay' })
  setProxy({ target: 'http://127.0.0.1:44291', delay_ms: 0 })
  await sleep(6000)
  await waitFor(`document.querySelector('[data-cb-desk]')?.getAttribute('data-cb-desk') === 'ready'`, 'ready after delay')
  console.log('loader released -> ready')

  // sha of the module that is actually loaded in this window (materialised copy).
  const materialised = `${RIG_STATE}/home/desktop-plugins/coursebook/plugin.js`
  const sha = execFileSync('sha256sum', [materialised], { encoding: 'utf8' }).split(/\s+/)[0]
  const checkoutSha = execFileSync('sha256sum', [`${CHECKOUT}/desktop/plugin.js`], { encoding: 'utf8' }).split(/\s+/)[0]
  if (sha !== checkoutSha) throw new Error(`materialised plugin sha ${sha} != checkout ${checkoutSha}`)

  const payload = {
    kind: 'live isolated Desktop capture',
    rig: {
      window: `Hermes Desktop (apps/desktop) on Electron, dev server 127.0.0.1:5174, CDP 127.0.0.1:${PORT}`,
      state: RIG_STATE,
      transport: 'loopback proxy 127.0.0.1:44281 -> backend; it forwards, delays or refuses and never rewrites a Coursebook response',
      backends: {
        course_data: '127.0.0.1:44291 (isolated home copied from a disposable test home; real Coursebook data.db, 20 courses)',
        empty: '127.0.0.1:44292 (isolated home with no plugin-data/coursebook/data.db)'
      },
      desktop_plugin: materialised,
      command: 'COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-h61fd-1789000000 CB013_CDP_PORT=9361 bash scripts/cb013-live-window.sh && node <capture driver>'
    },
    states_covered: ['ready', 'ready + sources drawer', 'backend off', 'empty (first run)', 'loading'],
    frames,
    captured_at: new Date().toISOString(),
    plugin_sha256: sha
  }
  writeFileSync(DESK, JSON.stringify(payload, null, 2) + '\n')
  console.log('wrote', DESK, 'plugin_sha256', sha)
} finally {
  socket.close()
}
