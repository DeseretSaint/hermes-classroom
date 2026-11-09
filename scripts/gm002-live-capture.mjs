#!/usr/bin/env node
/**
 * GM-002 — drive the isolated Desktop window and capture the visual-review cells.
 *
 * Real window (`scripts/cb013-live-window.sh`, its own HOME/userdata), real backend
 * (`scripts/cb013-live-backend.sh`, CB013_PORT), real `Page.captureScreenshot`. Nothing is
 * rendered off-line and no response is fabricated.
 *
 * States that need a fault use documented switches and are named in MANIFEST.md:
 *   - loading / error: a pass-through transport proxy in front of the isolated backend
 *     (`scripts/gm002-live-proxy.mjs`, MODE=slow|library-error|outline-error)
 *   - offline: Chromium `Network.emulateNetworkConditions` (real `navigator.onLine`)
 *   - empty: a migrated-but-empty Coursebook database (no rows invented)
 *
 *   CB015_CDP_PORT=9441 CB013_PORT=44279 COURSEBOOK_TEST_STATE=<state> \
 *     node scripts/gm002-live-capture.mjs --phase base|loading|error|offline|empty
 */
import { mkdirSync, writeFileSync, existsSync, copyFileSync, readFileSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { execFileSync, spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { connect } from './cb015-lib.mjs'

const OUT = resolve('docs/visual-review/gm-002')
const EVIDENCE = resolve(OUT, 'live-evidence.json')
const STATE = process.env.COURSEBOOK_TEST_STATE
const PORT = process.env.CB013_PORT || '44279'
const PROXY_PORT = process.env.GM002_PROXY_PORT || '44281'
const CDP_PORT = process.env.CB015_CDP_PORT || '9441'
const PHASE = (() => {
  const index = process.argv.indexOf('--phase')
  return index > 0 ? process.argv[index + 1] : 'base'
})()
if (!STATE) throw new Error('COURSEBOOK_TEST_STATE is required')
mkdirSync(OUT, { recursive: true })

let cdp = null
let evidence = existsSync(EVIDENCE) ? JSON.parse(readFileSync(EVIDENCE, 'utf8')).frames || [] : []
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const withTimeout = (promise, ms, label) =>
  Promise.race([promise, new Promise((_, fail) => setTimeout(() => fail(new Error(`timeout: ${label}`)), ms))])

const openPage = async () => {
  if (cdp) { try { cdp.close() } catch { /* already gone */ } cdp = null }
  let last = null
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      cdp = await connect()
      await withTimeout(cdp.send('Page.enable', {}), 20000, 'Page.enable')
      await withTimeout(cdp.send('Runtime.enable', {}), 20000, 'Runtime.enable')
      return
    } catch (error) {
      last = error
      cdp = null
      await wait(400)
    }
  }
  throw last || new Error('could not attach to the window')
}
const send = async (method, params = {}) => {
  if (!cdp) throw new Error('no page')
  const result = await withTimeout(cdp.send(method, params), 40000, method)
  if (result && result.exceptionDetails) throw new Error(result.exceptionDetails.text)
  return result
}
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result.value
}
const json = async (expression) => JSON.parse(await evaluate(`JSON.stringify(${expression})`))
const waitFor = async (expression, { timeout = 30000, label = expression } = {}) => {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try { if (await evaluate(`Boolean(${expression})`)) return true } catch { /* retry */ }
    await wait(120)
  }
  throw new Error(`timed out waiting for ${label}`)
}

let lastOverride = 1049
const setWidth = async (target, height = 900) => {
  let override = target
  for (let index = 0; index < 12; index += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    lastOverride = override
    await wait(240)
    const measured = await evaluate('window.innerWidth')
    if (measured === target) return measured
    override = Math.max(200, override + (target - measured))
  }
  return evaluate('window.innerWidth')
}
const setHeight = async (height) => {
  // A full-page shot needs the viewport itself to be as tall as the document: this Electron build
  // ignores captureBeyondViewport under a device-metrics override.
  await send('Emulation.setDeviceMetricsOverride', { width: lastOverride, height, deviceScaleFactor: 1, mobile: false })
  await wait(350)
}

const settingButton = `[...document.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === 'Open Coursebook settings')`

const pickSetting = async (control, optionText) => {
  const opened = await evaluate(`(() => { const b = ${settingButton}; if (!b) return false; b.click(); return true })()`)
  if (!opened) return 'no-settings'
  await wait(380)
  const picked = await evaluate(`(() => {
    const root = document.querySelector('[data-cb-settings-control="${control}"]')
    if (!root) return 'no-control'
    const btn = [...root.querySelectorAll('button')].find((b) => b.innerText.trim().toLowerCase() === ${JSON.stringify(optionText.toLowerCase())})
    if (!btn) return 'no-option'
    btn.click(); return 'clicked'
  })()`)
  await wait(300)
  await evaluate(`document.querySelector('[data-cb-settings-close]')?.click()`)
  await wait(380)
  return picked
}
const setAppearance = async (mode) => {
  const picked = await pickSetting('appearance', mode)
  if (picked !== 'clicked') throw new Error(`appearance ${mode}: ${picked}`)
  const painted = await evaluate("document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope') || null")
  if (painted !== mode) throw new Error(`appearance did not repaint: ${mode} -> ${painted}`)
}
const setMotion = async (reduce) => {
  await pickSetting('reduced-motion', reduce ? 'Reduce motion' : 'Follow system')
  await send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: reduce ? 'reduce' : 'no-preference' }]
  })
  await wait(250)
}
const setTextScale = async (scale) => {
  await evaluate(scale === 200
    ? "document.documentElement.style.setProperty('font-size','32px','important')"
    : "document.documentElement.style.removeProperty('font-size')")
  await wait(250)
}
const navigate = async (hash) => { await evaluate(`location.hash = ${JSON.stringify(hash)}`); await wait(420) }

const state = () => json(`(() => {
  const home = document.querySelector('[data-cb-home]')
  const route = document.querySelector('[data-cb-route]')
  const primary = document.querySelector('[data-cb-action="primary"]')
  const scope = document.querySelector('[data-cb-scope]')
  const shelf = document.querySelector('[data-cb-home-shelf-row]')
  const style = primary ? getComputedStyle(primary) : null
  const active = document.activeElement
  const activeStyle = active && active !== document.body ? getComputedStyle(active) : null
  return {
    hash: location.hash,
    home: home ? home.getAttribute('data-cb-home') : null,
    shelf: document.querySelector('[data-cb-home-shelf-state]')?.getAttribute('data-cb-home-shelf-state') || null,
    cards: document.querySelectorAll('[data-cb-home-card]').length,
    mode: scope ? scope.getAttribute('data-cb-scope') : null,
    paper: scope ? getComputedStyle(scope).backgroundColor : null,
    primary: primary ? (primary.innerText || '').trim() : null,
    primaryBg: style ? style.backgroundColor : null,
    primaryOutline: style ? style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor : null,
    focusRing: primary ? primary.getAttribute('data-cb-focus-ring') : null,
    active: activeStyle ? {
      tag: active.tagName.toLowerCase(),
      label: (active.innerText || active.getAttribute('aria-label') || '').trim().slice(0, 60),
      outline: activeStyle.outlineStyle + ' ' + activeStyle.outlineWidth + ' ' + activeStyle.outlineColor
    } : null,
    courseHome: Boolean(document.querySelector('[data-cb-course-home]')),
    continuePlate: document.querySelectorAll('[data-cb-continue]').length,
    trailhead: document.querySelector('[data-cb-trailhead-state]')?.getAttribute('data-cb-trailhead-state') || null,
    shelfScrolls: shelf ? shelf.scrollWidth > shelf.clientWidth + 1 : null,
    pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
    rootFont: getComputedStyle(document.documentElement).fontSize,
    textHead: (route ? route.innerText : document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 320)
  }
})()`)

const shot = async (id) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const buffer = Buffer.from(png.data, 'base64')
  writeFileSync(resolve(OUT, `${id}.png`), buffer)
  return { file: `${id}.png`, md5: createHash('md5').update(buffer).digest('hex'), bytes: buffer.length }
}

const shotFull = async (id) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  const buffer = Buffer.from(png.data, 'base64')
  writeFileSync(resolve(OUT, `${id}.png`), buffer)
  return { file: `${id}.png`, md5: createHash('md5').update(buffer).digest('hex'), bytes: buffer.length }
}

const persist = () => {
  writeFileSync(EVIDENCE, `${JSON.stringify({
    generated_at: new Date().toISOString(),
    kind: 'live capture from the isolated Electron window (Page.captureScreenshot)',
    window: 'scripts/cb013-live-window.sh',
    backend: `127.0.0.1:${PORT}`,
    state_dir: STATE,
    plugin_sha256: createHash('sha256').update(readFileSync(`${STATE}/home/desktop-plugins/coursebook/plugin.js`)).digest('hex'),
    frames: evidence
  }, null, 2)}\n`)
}
const capture = async (id, extra = {}) => {
  const facts = await state()
  const file = await shot(id)
  evidence = evidence.filter((frame) => frame.id !== id)
  evidence.push({ id, ...file, ...facts, ...extra })
  persist()
  console.log(`${id}: home=${facts.home} shelf=${facts.shelf} cards=${facts.cards} course=${facts.courseHome} continue=${facts.continuePlate} mode=${facts.mode} width=${facts.innerWidth} font=${facts.rootFont} overflow=${facts.pageOverflow} active=${facts.active ? facts.active.outline : '-'}`)
  return facts
}

const backend = (arg) => execFileSync('bash', ['scripts/cb013-live-backend.sh', arg], {
  env: { ...process.env, COURSEBOOK_TEST_HOME: `${STATE}/home`, CB013_PORT: PORT },
  encoding: 'utf8'
}).trim()

let proxy = null
const startProxy = async (mode) => {
  stopProxy()
  proxy = spawn('node', ['scripts/gm002-live-proxy.mjs'], {
    env: { ...process.env, GM002_PROXY_MODE: mode, GM002_PROXY_PORT: PROXY_PORT, GM002_UPSTREAM_PORT: PORT },
    stdio: 'ignore',
    detached: true
  })
  proxy.unref()
  for (let index = 0; index < 60; index += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${PROXY_PORT}/health`)
      if (response.ok) return
    } catch { /* not up */ }
    await wait(200)
  }
  throw new Error('proxy did not start')
}
const stopProxy = () => {
  if (proxy && proxy.pid) { try { process.kill(-proxy.pid) } catch { try { process.kill(proxy.pid) } catch { /* gone */ } } }
  proxy = null
  try { execFileSync('pkill', ['-f', 'gm002-live-proxy.mjs'], { stdio: 'ignore' }) } catch { /* none running */ }
}

const pointWindow = (port) => {
  const files = ['connections.json', 'connection.json', 'active-profile.json']
  for (const name of files) {
    const path = `${STATE}/userdata/${name}`
    if (!existsSync(path)) continue
    const text = readFileSync(path, 'utf8').replaceAll(String(PORT), String(port)).replaceAll(String(PROXY_PORT), String(port))
    writeFileSync(path, text)
  }
}
const restartWindow = async () => {
  if (cdp) { try { cdp.close() } catch { /* gone */ } cdp = null }
  const env = { ...process.env, COURSEBOOK_TEST_STATE: STATE, CB013_CDP_PORT: CDP_PORT }
  try {
    execFileSync('bash', ['scripts/cb013-live-window.sh', '--restart'], { env, encoding: 'utf8', stdio: 'pipe' })
  } catch (error) {
    // The previous Electron can hold the port for a moment; stop, confirm, start once more.
    try { execFileSync('bash', ['scripts/cb013-live-window.sh', '--stop'], { env, encoding: 'utf8', stdio: 'pipe' }) } catch { /* none */ }
    await wait(1200)
    execFileSync('bash', ['scripts/cb013-live-window.sh'], { env, encoding: 'utf8', stdio: 'pipe' })
  }
  await openPage()
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
}

const ensureHome = async () => {
  await navigate('#/courses')
  await navigate('#/coursebook')
  await waitFor(`!!document.querySelector('[data-cb-home]')`, { timeout: 30000, label: 'global home' })
  await waitFor(`document.querySelector('[data-cb-home]').getAttribute('data-cb-home') === 'ready'`, { timeout: 30000, label: 'ready shelf' })
}
const openCard = async (index = 0) => {
  const clicked = await evaluate(`(() => {
    const card = document.querySelectorAll('[data-cb-home-card]')[${index}]
    const button = card && card.querySelector('button')
    if (button) button.click()
    return Boolean(button)
  })()`)
  await waitFor(`!!document.querySelector('[data-cb-course-home]')`, { timeout: 30000, label: 'course home' })
  await wait(900)
  return clicked
}
const ensureCourseHome = async (index = 0) => { await ensureHome(); await openCard(index) }

const focusPrimary = async () => {
  for (let tab = 0; tab < 90; tab += 1) {
    for (const type of ['keyDown', 'keyUp']) {
      await send('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
    }
    await wait(40)
    const focused = await evaluate(`(() => {
      const active = document.activeElement
      if (!active || !active.matches || active.getAttribute('data-cb-action') !== 'primary') return null
      const style = getComputedStyle(active)
      return { label: (active.innerText || '').trim(), outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor, ring: active.getAttribute('data-cb-focus-ring') }
    })()`)
    if (focused) return focused
  }
  return null
}

await openPage()

if (PHASE === 'base') {
  pointWindow(PORT)
  await setWidth(1049)
  await evaluate(`location.hash = '#/coursebook'`)
  await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route' })
  await wait(700)
  await setAppearance('light')
  await ensureHome()
  await setWidth(1049); await capture('home.global--1049--light--100--default')
  await setAppearance('dark'); await capture('home.global--1049--dark--100--default'); await setAppearance('light')
  await setWidth(900); await capture('home.global--900--light--100--default')
  await setWidth(460); await capture('home.global--460--light--100--default')
  await setWidth(1049); await setTextScale(200); await setWidth(1049)
  await capture('home.global--1049--light--200--default')
  await setWidth(460); await capture('home.global--460--light--200--default')
  await setWidth(1049); await setTextScale(100); await setWidth(1049)

  await ensureHome()
  const focusTarget = await focusPrimary()
  if (!focusTarget) throw new Error('no primary action reached by Tab')
  await capture('home.global--1049--light--100--focus', { focus_target: focusTarget })

  await setMotion(true); await capture('home.global--1049--light--100--reduced-motion'); await setMotion(false)
  await capture('home.global--1049--light--100--overflow', { note: 'shelf scrolls horizontally; the page itself must not overflow' })

  await ensureCourseHome(0)
  await capture('home.course--1049--light--100--default')
  await setAppearance('dark'); await capture('home.course--1049--dark--100--default'); await setAppearance('light')
  await setWidth(900); await capture('home.course--900--light--100--default')
  await setWidth(460); await capture('home.course--460--light--100--default')
  await setWidth(1049); await setTextScale(200); await setWidth(1049)
  await capture('home.course--1049--light--200--default')
  await setWidth(460); await capture('home.course--460--light--200--default')
  await setWidth(1049); await setTextScale(100); await setWidth(1049)
  await ensureCourseHome(0)
  const courseFocus = await focusPrimary()
  await capture('home.course--1049--light--100--focus', { focus_target: courseFocus })
  await setMotion(true); await capture('home.course--1049--light--100--reduced-motion'); await setMotion(false)

  // plan in review: shelf card 2 is a draft whose next step is "Review and approve the plan"
  await ensureCourseHome(1)
  await capture('home.course--1049--light--100--plan-in-review')
  await ensureCourseHome(0)
  await capture('home.course--1049--light--100--no-world', { note: 'no course in this rig carries a world yet; the mode badge is honest' })
}

if (PHASE === 'loading' || PHASE === 'error') {
  if (PHASE === 'loading') {
    await startProxy('slow')
  } else {
    await startProxy('library-error')
  }
  pointWindow(PROXY_PORT)
  await restartWindow()
  await setWidth(1049)
  await evaluate(`location.hash = '#/coursebook'`)
  await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after restart' })
  await wait(700)
  await setAppearance('light')
  if (PHASE === 'loading') {
    await navigate('#/courses')
    await evaluate(`location.hash = '#/coursebook'`)
    await waitFor(`document.querySelector('[data-cb-home]')?.getAttribute('data-cb-home') === 'loading'`, { timeout: 6000, label: 'loading home' })
    await capture('home.global--1049--light--100--loading', { failure_switch: 'transport proxy: 3s delay on library.list' })
    await waitFor(`document.querySelector('[data-cb-home]')?.getAttribute('data-cb-home') === 'ready'`, { timeout: 30000, label: 'ready after loading' })
    // course outline loading
    await evaluate(`document.querySelectorAll('[data-cb-home-card] button')[0].click()`)
    await waitFor(`!!document.querySelector('[data-cb-course-home]')`, { timeout: 10000, label: 'course home loading' })
    await capture('home.course--1049--light--100--loading', { failure_switch: 'transport proxy: 3s delay on course.outline' })
  } else {
    await navigate('#/courses')
    await evaluate(`location.hash = '#/coursebook'`)
    await waitFor(`document.querySelector('[data-cb-home]')?.getAttribute('data-cb-home') === 'error'`, { timeout: 20000, label: 'error home' })
    await capture('home.global--1049--light--100--error', { failure_switch: 'proxy: RPC error envelope on library.list' })
    stopProxy()
    await startProxy('outline-error')
    pointWindow(PROXY_PORT)
    await restartWindow()
    await setWidth(1049)
    await evaluate(`location.hash = '#/coursebook'`)
    await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after restart' })
    await wait(700)
    await setAppearance('light')
    await ensureHome()
    await evaluate(`document.querySelectorAll('[data-cb-home-card] button')[0].click()`)
    await wait(2500)
    const courseErrorText = await evaluate("[...document.querySelectorAll('[data-cb-route] *')].map((n) => n.innerText || '').join(' ').replace(/\\s+/g, ' ')")
    if (!/route was not read|could not be read/i.test(courseErrorText)) {
      throw new Error(`course outline error did not paint: ${courseErrorText.slice(0, 300)}`)
    }
    await capture('home.course--1049--light--100--error', { failure_switch: 'proxy: RPC error envelope on course.outline' })
  }
  stopProxy()
  pointWindow(PORT)
  await restartWindow()
}

if (PHASE === 'offline') {
  pointWindow(PORT)
  await restartWindow()
  await setWidth(1049)
  await evaluate(`location.hash = '#/coursebook'`)
  await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after restart' })
  await wait(700)
  await setAppearance('light')
  await ensureHome()
  await send('Network.enable', {})
  await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
  await waitFor(`navigator.onLine === false`, { timeout: 10000, label: 'navigator offline' })
  await wait(700)
  await capture('home.global--1049--light--100--offline', { failure_switch: 'Network.emulateNetworkConditions offline' })
  await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
  await waitFor(`navigator.onLine === true`, { timeout: 10000, label: 'navigator online' })
}

if (PHASE === 'empty') {
  const dbDir = `${STATE}/home/plugin-data/coursebook`
  const live = `${dbDir}/data.db`
  const real = `${dbDir}/data.db.real`
  const empty = `${dbDir}/data.db.empty`
  if (!existsSync(real) || !existsSync(empty)) throw new Error('prepare data.db.real and data.db.empty before --phase empty')
  backend('--stop')
  copyFileSync(real, live)
  copyFileSync(empty, live)
  backend('')
  pointWindow(PORT)
  await restartWindow()
  await setWidth(1049)
  await evaluate(`location.hash = '#/coursebook'`)
  await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after restart' })
  await wait(700)
  await setAppearance('light')
  await navigate('#/courses'); await navigate('#/coursebook')
  await waitFor(`!!document.querySelector('[data-cb-home]')`, { timeout: 30000, label: 'empty home' })
  await wait(800)
  await capture('home.global--1049--light--100--empty', { failure_switch: 'migrated empty Coursebook database' })
  backend('--stop')
  copyFileSync(real, live)
  backend('')
}

if (PHASE === 'full') {
  pointWindow(PORT)
  await restartWindow()
  await setWidth(1049)
  await evaluate(`location.hash = '#/coursebook'`)
  await waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after restart' })
  await wait(700)
  await setAppearance('light')
  await ensureCourseHome(0)
  for (const [width, scale] of [[460, 100], [460, 200], [900, 100]]) {
    await setTextScale(scale)
    await setWidth(width)
    const fullHeight = await evaluate('document.documentElement.scrollHeight')
    await setHeight(fullHeight)
    const facts = await state()
    const file = await shot(`home.course--${width}--light--${scale}--full`)
    evidence = evidence.filter((frame) => frame.id !== `home.course--${width}--light--${scale}--full`)
    evidence.push({ id: `home.course--${width}--light--${scale}--full`, ...file, ...facts, full_page: true, captured_height: fullHeight })
    persist()
    await setHeight(900)
    console.log(`full ${width}/${scale}: width=${facts.innerWidth} font=${facts.rootFont} course=${facts.courseHome} height=${fullHeight}`)
  }
  await setTextScale(100)
}

persist()
console.log(`phase ${PHASE}: ${evidence.length} frames recorded`)
process.exit(0)
