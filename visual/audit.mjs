#!/usr/bin/env node
/**
 * Coursebook visual audit — runs on the secondary monitor, never steals focus.
 *
 * It opens a dedicated app window (a new CDP target) positioned on the secondary display,
 * screenshots each v3 route, diffs against baselines, runs axe, and asserts the product fonts
 * loaded. It never reloads, resizes or focuses a window the owner is using.
 *
 * Usage: node audit.mjs [--port 9371] [--write-baseline] [--monitor secondary|main|1344x768+3440+40]
 *                        [--reuse]   (attach to an existing coursebook page instead of opening one)
 */
import { chromium } from 'playwright'
import { PNG } from 'pngjs'
import pixelmatch from 'pixelmatch'
import fs from 'node:fs'
import path from 'node:path'
import { execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const AXE = require.resolve('axe-core/axe.min.js')
const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRAMES = path.join(HERE, 'frames')
const BASELINE = path.join(HERE, 'baselines')
const DIFFS = path.join(HERE, 'diffs')

const args = process.argv.slice(2)
const opt = (name, fallback) => { const i = args.indexOf(name); return i === -1 ? fallback : args[i + 1] }
const PORT = Number(opt('--port', 0))
const THRESHOLD = Number(opt('--threshold', 0.001))
const WRITE_BASELINE = args.includes('--write-baseline')
const REUSE = args.includes('--reuse')
const MONITOR = opt('--monitor', 'secondary')
// The approved frames are 1344x768. A route narrower than this is the docked pane, not the
// approved canvas; it must never be reported as a pass.
const MIN_ROUTE_WIDTH = Number(opt('--min-width', 1200))

const ROUTES = [
  { name: 'home', label: 'Home' },
  { name: 'courses', label: 'Courses' },
  { name: 'workshop', label: 'Workshop' },
  { name: 'studio', label: 'Parent Studio' }
]

for (const dir of [FRAMES, BASELINE, DIFFS]) fs.mkdirSync(dir, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function hyprJson(cmd) {
  try { return JSON.parse(execSync(`hyprctl ${cmd} -j`, { encoding: 'utf8' })) } catch { return null }
}

function monitorBounds() {
  if (MONITOR.includes('x') && MONITOR.includes('+')) {
    const m = MONITOR.match(/(\d+)x(\d+)\+(\d+)\+(\d+)/)
    if (m) return { width: +m[1], height: +m[2], left: +m[3], top: +m[4] }
  }
  const monitors = hyprJson('monitors')
  if (!monitors || !monitors.length) return { width: 1344, height: 768, left: 0, top: 0 }
  const target = MONITOR === 'main'
    ? monitors.find((m) => m.focused) || monitors[0]
    : monitors.find((m) => !m.focused) || monitors[0]
  return {
    width: Math.min(1880, target.width - 40),
    height: Math.min(1000, target.height - 40),
    left: target.x + 40,
    top: target.y + 40
  }
}

function restoreFocus(previousAddress) {
  if (!previousAddress) return
  try { execSync(`hyprctl dispatch focuswindow address:${previousAddress}`, { stdio: 'ignore' }) } catch { /* best effort */ }
}

async function discoverPort() {
  if (PORT) return PORT
  let ports = []
  try {
    const out = execSync('ss -ltnp 2>/dev/null | grep electron', { encoding: 'utf8' })
    ports = [...new Set(out.split('\n').map((l) => (l.match(/127\.0\.0\.1:(\d+)/) || [])[1]).filter(Boolean).map(Number))]
  } catch { return 0 }
  // Prefer the port whose target list actually shows the coursebook route. The highest port is
  // often a peer window that never mounted the plugin.
  for (const p of ports.sort((a, b) => b - a)) {
    try {
      const res = await fetch(`http://127.0.0.1:${p}/json/list`, { signal: AbortSignal.timeout(1500) })
      const targets = await res.json()
      if (targets.some((t) => t.type === 'page' && /coursebook/.test(t.url || ''))) return p
    } catch { /* port not answering */ }
  }
  return ports.sort((a, b) => b - a)[0] || 0
}

async function findCoursebookFrame(browser, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const ctx of browser.contexts()) {
      for (const page of ctx.pages()) {
        for (const frame of page.frames()) {
          try {
            if (await frame.evaluate(() => Boolean(document.querySelector('[data-cb-route]')))) return { page, frame }
          } catch { /* navigating */ }
        }
      }
    }
    await sleep(300)
  }
  return null
}

const port = await discoverPort()
if (!port) { console.error('no Electron CDP port found'); process.exit(2) }
const before = hyprJson('activewindow')
const previousAddress = before && before.address ? before.address : null
const bounds = monitorBounds()

const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`)
let page
let frame
let testAddress = null

if (REUSE) {
  const found = await findCoursebookFrame(browser, 10000)
  if (!found) { console.error('no coursebook page to reuse'); process.exit(2) }
  ;({ page, frame } = found)
} else {
  // Electron does not implement Target.createTarget or Browser.setWindowBounds. The host's own
  // openWindow() creates a peer full-chrome window; we then place it on the secondary monitor
  // with hyprctl and hand focus straight back to the owner.
  const opener = await findCoursebookFrame(browser, 10000)
  if (!opener) { console.error('no coursebook page to open from'); process.exit(2) }
  const beforePages = new Set(browser.contexts().flatMap((c) => c.pages().map((p) => p)))
  const beforeAddrs = new Set((hyprJson('clients') || []).map((c) => c.address))
  await opener.page.evaluate(async () => await window.hermesDesktop.openWindow()).catch(() => {})
  page = await (async () => {
    const deadline = Date.now() + 15000
    while (Date.now() < deadline) {
      const fresh = browser.contexts().flatMap((c) => c.pages()).find((p) => !beforePages.has(p))
      if (fresh) return fresh
      await sleep(200)
    }
    return null
  })()
  if (!page) { console.error('openWindow produced no new page'); process.exit(2) }

  const deadline = Date.now() + 8000
  while (Date.now() < deadline && !testAddress) {
    const fresh = (hyprJson('clients') || []).find((c) => !beforeAddrs.has(c.address) && /hermes/i.test(c.class))
    if (fresh) testAddress = fresh.address
    else await sleep(150)
  }
  if (testAddress) {
    try {
      // Place it on the secondary monitor. Do not resize: Hyprland ignores resize for tiled
      // windows and floating it fights the app's own window state. The report records the real
      // geometry so a narrow pane cannot be mistaken for parity.
      execSync(`hyprctl dispatch movewindowpixel exact ${bounds.left} ${bounds.top},address:${testAddress}`, { stdio: 'ignore' })
    } catch { /* placement is best effort; the report records the real size */ }
  }
  restoreFocus(previousAddress)
  await sleep(500)
  await page.evaluate(() => { window.location.hash = '#/coursebook' }).catch(() => {})
  const deadline2 = Date.now() + 15000
  while (Date.now() < deadline2 && !frame) {
    for (const f of page.frames()) {
      try { if (await f.evaluate(() => Boolean(document.querySelector('[data-cb-route]')))) { frame = f; break } } catch { /* navigating */ }
    }
    if (!frame) await sleep(250)
  }
  if (!frame) { console.error('the test window never rendered [data-cb-route]'); process.exit(2) }
}

// Give the host back to the owner immediately; the audit never needs focus.
restoreFocus(previousAddress)
await sleep(400)

const report = {
  generated: new Date().toISOString(),
  port,
  monitor: MONITOR,
  bounds,
  window: await page.evaluate(() => ({ w: innerWidth, h: innerHeight })).catch(() => null),
  scope: await frame.evaluate(() => {
    const r = document.querySelector('[data-cb-route]')
    return {
      width: r?.clientWidth,
      height: r?.clientHeight,
      scope: r?.getAttribute('data-cb-scope'),
      destination: r?.getAttribute('data-cb-destination')
    }
  }).catch(() => null),
  frames: [],
  failures: []
}

if (!report.scope || report.scope.width < MIN_ROUTE_WIDTH) {
  report.geometry_ok = false
  report.failures.push(`geometry: route ${report.scope ? report.scope.width : 0}px wide (< ${MIN_ROUTE_WIDTH}) — this is the docked pane, not the approved 1344x768 canvas`)
} else {
  report.geometry_ok = true
}

// A route attribute and loaded fonts can both be true behind an app-level error dialog. The
// capture must prove the coursebook shell actually mounted, or the frame is a screenshot of a crash.
const health = await frame.evaluate(() => {
  const text = document.body ? document.body.innerText : ''
  return {
    errorModal: /Hermes couldn't start|background service stopped|background service didn't come up/i.test(text),
    route: Boolean(document.querySelector('[data-cb-route]')),
    navCount: document.querySelectorAll('[data-cb-nav-item]').length,
    textLength: text.trim().length
  }
}).catch(() => ({ errorModal: true, route: false, navCount: 0, textLength: 0 }))
report.health = health
if (health.errorModal) report.failures.push('app did not start: the Hermes error modal is on screen; every frame would be a crash dialog')
if (!health.route) report.failures.push('no [data-cb-route] in the captured surface')
if (health.navCount < 4) report.failures.push(`only ${health.navCount} nav items mounted; the coursebook shell did not render`)

if (report.failures.length) {
  if (testAddress) { try { execSync(`hyprctl dispatch closewindow address:${testAddress}`, { stdio: 'ignore' }) } catch { /* best effort */ } }
  restoreFocus(previousAddress)
  fs.writeFileSync(path.join(HERE, 'report.json'), JSON.stringify(report, null, 2))
  console.log(`FAIL\n${report.failures.join('\n')}`)
  process.exit(1)
}

async function routeTo(label) {
  const clicked = await frame.evaluate((l) => {
    const el = [...document.querySelectorAll('[data-cb-nav-item]')].find((n) => (n.textContent || '').trim() === l)
    if (!el) return false
    el.click()
    return true
  }, label).catch(() => false)
  if (!clicked) return false
  const deadline = Date.now() + 10000
  while (Date.now() < deadline) {
    const ready = await frame.evaluate(() => Boolean(document.querySelector('[data-cb-v3]')) && document.fonts.status === 'loaded').catch(() => false)
    if (ready) { await sleep(250); return true }
    await sleep(180)
  }
  return false
}

await frame.evaluate(() => { window.location.hash = '#/coursebook' }).catch(() => {})
await sleep(1200)

for (const route of ROUTES) {
  const ok = await routeTo(route.label)
  const shotPath = path.join(FRAMES, `${route.name}.png`)
  await frame.locator('[data-cb-route]').first().screenshot({ path: shotPath, animations: 'disabled' }).catch(() => {})

  const fonts = await frame.evaluate(() => ['CB Display', 'CB UI'].map((f) => ({ family: f, loaded: document.fonts.check(`16px "${f}"`) }))).catch(() => [])
  let axe = { violations: [] }
  try {
    await frame.addScriptTag({ path: AXE })
    axe = await frame.evaluate(async () => {
      const root = document.querySelector('[data-cb-route]') || document.body
      const res = await window.axe.run(root, { resultTypes: ['violations'] })
      return { violations: res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })) }
    })
  } catch (e) { axe = { violations: [], error: String(e.message || e) } }

  const serious = axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  if (!ok) report.failures.push(`${route.name}: route never reached v3-ready`)
  if (serious.length) report.failures.push(`${route.name}: axe ${serious.map((v) => v.id).join(',')}`)
  if (fonts.some((f) => !f.loaded)) report.failures.push(`${route.name}: font fallback ${fonts.filter((f) => !f.loaded).map((f) => f.family).join(',')}`)

  const fr = { route: route.name, ready: ok, shot: shotPath, fonts, axe }
  const basePath = path.join(BASELINE, `${route.name}.png`)
  if (WRITE_BASELINE || !fs.existsSync(basePath)) {
    fs.copyFileSync(shotPath, basePath)
    fr.diff = null
  } else {
    const a = PNG.sync.read(fs.readFileSync(basePath))
    const b = PNG.sync.read(fs.readFileSync(shotPath))
    if (a.width !== b.width || a.height !== b.height) {
      fr.diff = { ratio: 1, reason: `size ${a.width}x${a.height} -> ${b.width}x${b.height}` }
      report.failures.push(`${route.name}: frame size changed`)
    } else {
      const diff = new PNG({ width: a.width, height: a.height })
      const changed = pixelmatch(a.data, b.data, diff.data, a.width, a.height, { threshold: 0.1 })
      fr.diff = { ratio: changed / (a.width * a.height) }
      fs.writeFileSync(path.join(DIFFS, `${route.name}.png`), PNG.sync.write(diff))
      if (fr.diff.ratio > THRESHOLD) report.failures.push(`${route.name}: ${(fr.diff.ratio * 100).toFixed(2)}% pixels changed`)
    }
  }
  report.frames.push(fr)
  console.log(`${route.name}: ready=${ok} fonts=${fonts.map((f) => `${f.family}:${f.loaded}`).join(' ')} axe=${serious.length}`)
}

if (testAddress) {
  try { execSync(`hyprctl dispatch closewindow address:${testAddress}`, { stdio: 'ignore' }) } catch { /* best effort */ }
}
restoreFocus(previousAddress)

fs.writeFileSync(path.join(HERE, 'report.json'), JSON.stringify(report, null, 2))
console.log(`window ${report.window?.w}x${report.window?.h} at ${bounds.left},${bounds.top}; route ${report.scope?.width}x${report.scope?.height} scope=${report.scope?.scope}`)
console.log(report.failures.length ? `FAIL\n${report.failures.join('\n')}` : 'PASS')
await browser.close().catch(() => {})
process.exit(report.failures.length ? 1 : 0)
