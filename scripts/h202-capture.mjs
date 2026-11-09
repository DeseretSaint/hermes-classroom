#!/usr/bin/env node
/**
 * H-202: capture the Field Stop frame matrix on the after rig.
 *
 *   CB009_CDP_PORT=9385 node scripts/h202-capture.mjs light  audit/visual/h178-field-stop
 *   CB009_CDP_PORT=9385 node scripts/h202-capture.mjs dark   audit/visual/h178-field-stop
 *
 * Sets the plugin's own Appearance (Settings sheet → SegmentedControl, real clicks), walks the
 * route to the demonstration course's STOP 2 player with the answer surface on screen, then
 * captures 1049 / 900 / 460 at 100% plus 1049 at 200% text. Every frame is written with a
 * measurement row (viewport, root font size, theme the plugin painted, PNG sha256).
 */
import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs'
import { resolve, basename } from 'node:path'
import { createHash } from 'node:crypto'
import { connect } from './h149-cdp.mjs'

const port = process.env.CB009_CDP_PORT || '9385'
const theme = (process.argv[2] || 'dark').toLowerCase()
const OUT = resolve(process.argv[3] || 'audit/visual/h178-field-stop')
const LABEL = theme === 'dark' ? 'Dark' : 'Light'
const { evaluate, wait, send } = await connect(port)

const sleep = wait

const clickText = (label, root = '[data-cb-route]') => evaluate(`(() => {
  const wanted = ${JSON.stringify(label)}
  const node = [...document.querySelectorAll(${JSON.stringify(root)} + ' button, [role="tab"] button, [role="tab"]')]
    .find((n) => (n.innerText || '').replace(/\\s+/g, ' ').trim() === wanted && n.offsetParent !== null)
  if (!node) return false
  node.click(); return true
})()`)

const setSearch = (value) => evaluate(`(() => {
  const el = document.querySelector('input[aria-label="Search courses"]')
  if (!el) return false
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(el, ${JSON.stringify(value)})
  el.dispatchEvent(new Event('input', { bubbles: true }))
  return true
})()`)

async function setAppearance() {
  // Home owns the settings trigger.
  await evaluate("location.hash='#/'; 'ok'")
  await sleep(500)
  await evaluate("location.hash='#/coursebook'; 'ok'")
  await sleep(2200)
  if (!(await evaluate("!!document.querySelector('[data-cb-settings-open]')"))) {
    await evaluate(`(() => { document.querySelector('[data-cb-nav-item="home"]')?.click(); return true })()`)
    await sleep(1600)
  }
  const clicked = await evaluate(`(() => {
    const b = document.querySelector('[data-cb-settings-open]')
    if (!b) return false
    b.click(); return true
  })()`)
  if (!clicked) throw new Error('no settings trigger on the route')
  await sleep(1200)
  const before = await evaluate(`document.querySelector('[data-cb-settings-control="appearance"]')?.getAttribute('data-cb-settings-value')`)
  const picked = await evaluate(`(() => {
    const ctrl = document.querySelector('[data-cb-settings-control="appearance"]')
    if (!ctrl) return false
    const b = [...ctrl.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === ${JSON.stringify(LABEL)})
    if (!b) return false
    b.click(); return true
  })()`)
  if (!picked) throw new Error('no ' + LABEL + ' appearance option')
  await sleep(900)
  const after = await evaluate(`document.querySelector('[data-cb-settings-control="appearance"]')?.getAttribute('data-cb-settings-value')`)
  await evaluate(`(() => { const c = document.querySelector('[data-cb-settings-close]'); if (c) c.click(); return true })()`)
  await sleep(800)
  return { before, after }
}

async function goToPlayer() {
  await evaluate("location.hash='#/'; 'ok'")
  await sleep(500)
  await evaluate("location.hash='#/coursebook'; 'ok'")
  await sleep(2200)
  // Give the lesson surface the full window: the right rail is the chat pane, not the player.
  await evaluate(`(() => {
    const b = [...document.querySelectorAll('button')].find((n) => (n.getAttribute('aria-label') || '') === 'Hide right sidebar')
    if (b) b.click()
    return true
  })()`)
  await sleep(700)
  await evaluate(`(() => { document.querySelector('[data-cb-nav-item="courses"]')?.click(); return true })()`)
  await sleep(1600)
  await setSearch('demonstration')
  await sleep(1400)
  const opened = await evaluate(`(() => {
    const btns = [...document.querySelectorAll('[data-cb-route] button')]
      .filter((b) => b.offsetParent !== null && /^(Open|Continue)$/.test((b.innerText || '').trim()))
    if (btns.length !== 1) return false
    btns[0].click(); return true
  })()`)
  if (!opened) throw new Error('shelf did not narrow to the demonstration course')
  await sleep(2800)
  const title = await evaluate(`((document.querySelector('[data-cb-route]') || {}).innerText || '').split('\\n')[4] || ''`)
  await evaluate(`(() => { document.querySelector('[data-cb-tab="learn"]')?.click(); return true })()`)
  await sleep(1800)
  const stopClicked = await evaluate(`(() => {
    const node = [...document.querySelectorAll('[data-cb-route] button')].find((n) => /^02\\b/.test((n.innerText || '').trim()))
    if (!node) return false
    node.click(); return true
  })()`)
  if (!stopClicked) throw new Error('stop 02 not on the trail')
  await sleep(3000)
  const view = await evaluate("document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-lesson-view') || null")
  if (view !== 'player') {
    await evaluate(`(() => { document.querySelector('[data-cb-view-choice="player"]')?.click(); return true })()`)
    await sleep(2200)
  }
  for (let i = 0; i < 5; i += 1) {
    if (await evaluate("!!document.querySelector('#cb-attempt-answer')")) break
    const label = await evaluate(`(() => {
      const b = document.querySelector('[data-cb-player-footer] button')
      if (!b || b.disabled) return null
      b.click(); return (b.innerText || '').trim()
    })()`)
    if (!label) break
    await sleep(1400)
  }
  return title
}

const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1400, deviceScaleFactor: 1, mobile: false })
    await sleep(160)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return override
    override = Math.round((override * target) / inner)
  }
  throw new Error(`could not calibrate ${target}`)
}

const measure = () => evaluate(`(() => {
  const t = (n) => (n ? (n.innerText || '').replace(/\\s+/g, ' ').trim() : null)
  const route = document.querySelector('[data-cb-route]')
  const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth
  const player = document.querySelector('[data-cb-player]')
  return {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    rootFontSize: getComputedStyle(document.documentElement).fontSize,
    scope: route && route.getAttribute('data-cb-scope'),
    darkClass: document.documentElement.classList.contains('dark'),
    player: !!player,
    bar: t(document.querySelector('[data-cb-player-bar]')),
    step: t(document.querySelector('[data-cb-player-step]')),
    chip: document.querySelector('[data-cb-evidence-chip]')?.getAttribute('data-cb-evidence-chip') || null,
    chipPending: document.querySelector('[data-cb-evidence-chip]')?.getAttribute('data-cb-evidence-pending') || null,
    chipText: t(document.querySelector('[data-cb-evidence-chip]')),
    answerField: !!document.querySelector('#cb-attempt-answer'),
    assist: [...document.querySelectorAll('[data-cb-assist] button')].map((b) => b.innerText.trim()),
    detached: /no longer connected/i.test(t(player) || ''),
    horizontalOverflow: overflow,
    stopHeaderPresent: /^STOP \\d+ OF \\d+/.test(t(document.querySelector('[data-cb-player-bar]')) || '')
  }
})()`)

const shoot = async (name) => {
  mkdirSync(OUT, { recursive: true })
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const buf = Buffer.from(shot.data, 'base64')
  const path = resolve(OUT, `${name}.png`)
  writeFileSync(path, buf)
  return { path, sha256: createHash('sha256').update(buf).digest('hex'), bytes: buf.length }
}

const appearance = await setAppearance()
console.log('appearance:', JSON.stringify(appearance))
const courseTitle = await goToPlayer()
console.log('course:', courseTitle)

const resultsPath = resolve(OUT, 'measurements.json')
let results = { port, theme, plugin_sha256: null, appearance, frames: [], sequence: [] }
if (existsSync(resultsPath)) {
  try {
    const prev = JSON.parse(readFileSync(resultsPath, 'utf8'))
    results = { ...results, ...prev, theme, appearance, frames: prev.frames || [], sequence: prev.sequence || [] }
  } catch (error) { /* first write */ }
}
results.frames = results.frames.filter((f) => f.theme !== theme)

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
for (const width of [1049, 900, 460]) {
  const override = await setWidth(width)
  await evaluate(`(() => { const p = document.querySelector('[data-cb-player]'); if (p) p.scrollIntoView({ block: 'start' }); return true })()`)
  await sleep(350)
  const snapshot = await measure()
  const file = await shoot(`field-stop-stop2-${theme}-${width}`)
  results.frames.push({
    name: basename(file.path), theme, width, text: '100%', override,
    viewport: { innerWidth: snapshot.innerWidth, innerHeight: snapshot.innerHeight },
    rootFontSize: snapshot.rootFontSize, scope: snapshot.scope, darkClass: snapshot.darkClass,
    sha256: file.sha256, bytes: file.bytes, state: snapshot
  })
  console.log(`frame ${theme}-${width}:`, snapshot.innerWidth, snapshot.scope, file.sha256.slice(0, 12))
}

// 200% text at 1049 — the card's fourth width/zoom cell.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
const override = await setWidth(1049)
await evaluate(`(() => { const p = document.querySelector('[data-cb-player]'); if (p) p.scrollIntoView({ block: 'start' }); return true })()`)
await sleep(400)
const snapshot = await measure()
const file = await shoot(`field-stop-stop2-${theme}-1049-text200`)
results.frames.push({
  name: basename(file.path), theme, width: 1049, text: '200%', override,
  viewport: { innerWidth: snapshot.innerWidth, innerHeight: snapshot.innerHeight },
  rootFontSize: snapshot.rootFontSize, scope: snapshot.scope, darkClass: snapshot.darkClass,
  sha256: file.sha256, bytes: file.bytes, state: snapshot
})
console.log(`frame ${theme}-1049-200%:`, snapshot.innerWidth, snapshot.rootFontSize, file.sha256.slice(0, 12))
await evaluate(`document.documentElement.style.removeProperty('font-size')`)

await setWidth(1049)
await send('Emulation.setEmulatedMedia', { features: [] })
writeFileSync(resultsPath, JSON.stringify(results, null, 2))
console.log('wrote', resultsPath, 'frames', results.frames.length)
