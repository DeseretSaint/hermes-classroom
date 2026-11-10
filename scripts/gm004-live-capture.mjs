#!/usr/bin/env node
/**
 * GM-004 — drive the isolated Desktop window and capture the live visual-review matrix.
 * Real window, real backend, real Page.captureScreenshot. World frames are produced from worlds
 * staged through the real handlers with the deterministic provider seam; every such frame is
 * labelled in MANIFEST.md. No image is fabricated.
 *
 *   CB015_CDP_PORT=9471 CB013_PORT=44291 COURSEBOOK_TEST_STATE=<state> \
 *     node scripts/gm004-live-capture.mjs
 */
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { connect } from './cb015-lib.mjs'

const OUT = resolve('docs/visual-review/gm-004')
const STATE = process.env.COURSEBOOK_TEST_STATE
const CDP_PORT = process.env.CB015_CDP_PORT || '9471'
mkdirSync(OUT, { recursive: true })
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const withTimeout = (promise, ms, label) => Promise.race([promise, new Promise((_, fail) => setTimeout(() => fail(new Error(`timeout: ${label}`)), ms))])

let cdp = null
const open = async () => {
  cdp = await connect()
  await withTimeout(cdp.send('Page.enable', {}), 20000, 'Page.enable')
  await withTimeout(cdp.send('Runtime.enable', {}), 20000, 'Runtime.enable')
}
const send = async (method, params = {}) => withTimeout(cdp.send(method, params), 40000, method)
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text)
  return r.result.value
}
const json = async (expression) => JSON.parse(await evaluate(`JSON.stringify(${expression})`))
const waitFor = async (expression, label, timeout = 30000) => {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try { if (await evaluate(`Boolean(${expression})`)) return true } catch { /* retry */ }
    await wait(150)
  }
  throw new Error(`timed out: ${label}`)
}
const state = () => json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const world = document.querySelector('[data-cb-world]')
  const studio = document.querySelector('[data-cb-world-studio]')
  const heading = document.querySelector('[data-cb-course-home] h1, [data-cb-course-home] h2, [data-cb-home] h1')
  return {
    hash: location.hash,
    scope: route ? route.getAttribute('data-cb-scope') : null,
    page: route ? route.getAttribute('data-cb-page') : null,
    course: heading ? heading.innerText.trim().slice(0, 90) : null,
    courseHome: !!document.querySelector('[data-cb-course-home]'),
    modeRow: document.querySelector('[data-cb-mode-row]')?.getAttribute('data-cb-mode-row') || null,
    modeBadge: document.querySelector('[data-cb-mode-badge]')?.getAttribute('data-cb-mode-badge') || null,
    world: world ? world.getAttribute('data-cb-world') : null,
    hero: !!document.querySelector('[data-cb-world-hero]'),
    sections: document.querySelectorAll('[data-cb-world-section]').length,
    studio: studio ? studio.getAttribute('data-cb-world-studio') : null,
    concepts: document.querySelectorAll('[data-cb-world-concept]').length,
    primary: document.querySelector('[data-cb-world-primary]')?.getAttribute('data-cb-world-primary') || null,
    dialog: document.querySelector('[data-cb-mode-dialog]')?.getAttribute('data-cb-mode-dialog') || null,
    createMode: document.querySelector('[data-cb-create-mode]')?.getAttribute('data-cb-create-mode') || null,
    innerWidth: window.innerWidth,
    rootFont: getComputedStyle(document.documentElement).fontSize,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    text: (route ? route.innerText : '').replace(/\\s+/g, ' ').slice(0, 240)
  }
})()`)
const frames = []
const shot = async (id) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const buffer = Buffer.from(png.data, 'base64')
  writeFileSync(resolve(OUT, `${id}.png`), buffer)
  frames.push({ id, file: `${id}.png`, md5: createHash('md5').update(buffer).digest('hex'), bytes: buffer.length, ...(await state()) })
  console.log(id, JSON.stringify(frames.at(-1)).slice(0, 220))
}
let override = 1049
const setWidth = async (target, height = 900) => {
  override = target
  for (let i = 0; i < 10; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    await wait(260)
    const measured = await evaluate('window.innerWidth')
    if (measured === target) return
    override = Math.max(200, override + (target - measured))
  }
}
const setText = async (scale) => {
  await evaluate(scale === 200
    ? "document.documentElement.style.setProperty('font-size','32px','important')"
    : "document.documentElement.style.removeProperty('font-size')")
  await wait(260)
}
const setAppearance = async (mode) => {
  const opened = await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === 'Open Coursebook settings')
    if (!b) return false
    b.click(); return true
  })()`)
  if (!opened) throw new Error('no settings button')
  await wait(450)
  const clicked = await evaluate(`(() => {
    const root = document.querySelector('[data-cb-settings-control="appearance"]')
    if (!root) return 'no-control'
    const btn = [...root.querySelectorAll('button')].find((b) => b.innerText.trim().toLowerCase() === ${JSON.stringify(mode)})
    if (!btn) return 'no-option:' + root.innerText.replace(/\\s+/g, ' ').slice(0, 60)
    btn.click(); return 'ok'
  })()`)
  await wait(400)
  await evaluate(`document.querySelector('[data-cb-settings-close]')?.click()`)
  await wait(450)
  const painted = await evaluate("document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope')")
  if (painted !== mode) throw new Error(`appearance ${mode} -> ${painted} (${clicked})`)
}
const nav = async (hash) => { await evaluate(`location.hash = ${JSON.stringify(hash)}`); await wait(500) }
const ensureHome = async () => {
  await nav('#/courses'); await nav('#/coursebook')
  await waitFor(`document.querySelector('[data-cb-home]')?.getAttribute('data-cb-home') === 'ready'`, 'home ready')
  await wait(500)
}
const openCard = async (match) => {
  const opened = await evaluate(`(() => {
    const card = [...document.querySelectorAll('[data-cb-home-card]')].find((c) => (c.innerText || '').includes(${JSON.stringify(match)}))
    if (!card) return false
    card.querySelector('button')?.click(); return true
  })()`)
  if (!opened) throw new Error(`no home card matching ${match}`)
  await waitFor(`!!document.querySelector('[data-cb-course-home]')`, `course home ${match}`)
  await wait(900)
}
const backHome = async () => { await ensureHome() }
const clickText = async (selector, text) => evaluate(`(() => {
  const node = [...document.querySelectorAll(${JSON.stringify(selector)})].find((n) => (n.innerText || '').trim() === ${JSON.stringify(text)})
  if (!node) return false
  node.click(); return true
})()`)

const JAPANESE = 'Japanese affection and register'
const TEXTBOOK = 'Order coffee and ask for the bill'
const STUDIO = 'a Sample L0 classroom'
const widths = [1049, 900, 460]

await open()
await wait(1200)
await setWidth(1049)

// ---- Home ----
await setAppearance('dark')
await ensureHome()
await shot('home--1049--dark')
await setAppearance('light')
await ensureHome()
await shot('home--1049--light')

const captureSurface = async (id, match, { zoom = true } = {}) => {
  for (const theme of ['dark', 'light']) {
    await setAppearance(theme)
    await backHome()
    await openCard(match)
    await setWidth(1049)
    await shot(`${id}--1049--${theme}`)
    for (const width of widths.slice(1)) {
      await setWidth(width)
      await shot(`${id}--${width}--${theme}`)
    }
    if (zoom) {
      await setWidth(460)
      await setText(200)
      await shot(`${id}--460--${theme}--200`)
      await setText(100)
    }
    await setWidth(1049)
    await backHome()
  }
}

// ---- Approved Game world: Japanese course, field_atlas, staged through real handlers ----
await captureSurface('course-world', JAPANESE)

// ---- Textbook course: no world surface, mode row + Textbook badge ----
await captureSurface('course-textbook', TEXTBOOK)

// ---- Textbook -> Game prompt ----
for (const theme of ['dark', 'light']) {
  await setAppearance(theme)
  await backHome()
  await openCard(TEXTBOOK)
  await setWidth(1049)
  await clickText('[data-cb-mode-change]', 'Change mode')
  await waitFor(`!!document.querySelector('[data-cb-mode-dialog]')`, 'mode dialog')
  await wait(400)
  await shot(`mode-dialog--1049--${theme}`)
  await setWidth(460)
  await shot(`mode-dialog--460--${theme}`)
  await setWidth(1049)
  // Cancel returns to the course home.
  await evaluate(`(() => {
    const root = document.querySelector('[data-cb-mode-dialog]')
    const btn = [...root.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Cancel')
    if (btn) { btn.click(); return true }
    return false
  })()`)
  await wait(600)
  await backHome()
}

// ---- World Studio: three authored concept boards (concepts_ready, seam swatches) ----
for (const theme of ['dark', 'light']) {
  await setAppearance(theme)
  await backHome()
  await openCard(STUDIO)
  await setWidth(1049)
  await clickText('[data-cb-mode-change]', 'Change mode')
  await waitFor(`!!document.querySelector('[data-cb-mode-dialog]')`, 'mode dialog')
  await wait(300)
  await evaluate(`document.querySelector('[data-cb-mode-primary] button')?.click()`)
  await waitFor(`!!document.querySelector('[data-cb-world-studio]')`, 'studio')
  await wait(800)
  await shot(`studio-concepts--1049--${theme}`)
  await setWidth(900); await shot(`studio-concepts--900--${theme}`)
  await setWidth(460); await shot(`studio-concepts--460--${theme}`)
  await setText(200); await shot(`studio-concepts--460--${theme}--200`)
  await setText(100); await setWidth(1049)
  await evaluate(`document.querySelector('[data-cb-world-studio-close]')?.click()`)
  await wait(600)
  await backHome()
}

// ---- Create: the mode choice on the shape step ----
for (const theme of ['dark', 'light']) {
  await setAppearance(theme)
  await ensureHome()
  await evaluate(`[...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Start a new course')?.click()`)
  await wait(700)
  await evaluate(`(() => { const i = document.querySelector('#cb-goal'); if (i) { const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set; set.call(i, 'Replace a head gasket on a four-cylinder engine'); i.dispatchEvent(new Event('input', { bubbles: true })) } })()`)
  await wait(400)
  await evaluate(`[...document.querySelectorAll('button')].find((b) => /Continue/.test(b.innerText || ''))?.click()`)
  await wait(700)
  await setWidth(1049)
  await shot(`create-mode--1049--${theme}`)
  await setWidth(460); await shot(`create-mode--460--${theme}`)
  await setWidth(1049)
  await ensureHome()
}

writeFileSync(resolve(OUT, 'live-evidence.json'), `${JSON.stringify({
  generated_at: new Date().toISOString(),
  kind: 'live capture from the isolated Electron window (Page.captureScreenshot)',
  window: 'scripts/cb013-live-window.sh',
  backend: `127.0.0.1:${process.env.CB013_PORT || '44291'}`,
  state_dir: STATE,
  plugin_sha256: createHash('sha256').update(readFileSync(`${STATE}/home/desktop-plugins/coursebook/plugin.js`)).digest('hex'),
  frames
}, null, 2)}\n`)
console.log(`frames ${frames.length}`)
cdp.close()
