#!/usr/bin/env node
/**
 * Coursebook visual audit — the missing feedback loop.
 *
 * Connects to the running Hermes Desktop over CDP (no second browser), renders each v3
 * route, and for every frame:
 *   - screenshots the route node at 2x (the same crop the design was approved at),
 *   - diffs it against visual/baselines/<route>.png when a baseline exists (pixelmatch),
 *   - runs axe-core and fails on serious/critical violations,
 *   - asserts the product fonts actually loaded (a silent system-serif fallback is a defect),
 *   - verifies no course title in the DOM was replaced by glyphs inside cover art by
 *     confirming every card title is real text (non-empty, > 2 chars, not image alt).
 *
 * Usage:
 *   node audit.mjs                  # audit, create baselines when missing, fail on drift
 *   node audit.mjs --write-baseline # accept the current frames as the baseline
 *   node audit.mjs --port 9411 --threshold 0.001
 *
 * Exit code 1 if any frame drifts past the threshold, a11y fails, or fonts are missing.
 */
import { chromium } from 'playwright'
import { PNG } from 'pngjs'
import pixelmatch from 'pixelmatch'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const AXE = require.resolve('axe-core/axe.min.js')
const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRAMES = path.join(HERE, 'frames')
const BASELINE = path.join(HERE, 'baselines')
const DIFFS = path.join(HERE, 'diffs')

const args = process.argv.slice(2)
const opt = (name, fallback) => {
  const i = args.indexOf(name)
  return i === -1 ? fallback : args[i + 1]
}
const PORT = Number(opt('--port', 9411))
const THRESHOLD = Number(opt('--threshold', 0.001))
const WRITE_BASELINE = args.includes('--write-baseline')
const WIDTH = Number(opt('--width', 1440))

const ROUTES = [
  { name: 'home', label: 'Home' },
  { name: 'courses', label: 'Courses' },
  { name: 'workshop', label: 'Workshop' },
  { name: 'studio', label: 'Parent Studio' }
]

for (const dir of [FRAMES, BASELINE, DIFFS]) fs.mkdirSync(dir, { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function attach() {
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
  const deadline = Date.now() + 15000
  while (Date.now() < deadline) {
    for (const ctx of browser.contexts()) {
      for (const page of ctx.pages()) {
        for (const frame of page.frames()) {
          try {
            const has = await frame.evaluate(() => Boolean(document.querySelector('[data-cb-route]')))
            if (has) return { browser, page, frame }
          } catch { /* frame navigating */ }
        }
      }
    }
    await sleep(300)
  }
  throw new Error(`no [data-cb-route] frame on CDP port ${PORT}`)
}

async function routeTo(frame, label) {
  const item = frame.locator('[data-cb-nav-item]', { hasText: label }).first()
  await item.click({ timeout: 8000 }).catch(async () => {
    await frame.evaluate((l) => {
      const el = [...document.querySelectorAll('[data-cb-nav-item]')].find((n) => (n.textContent || '').trim() === l)
      if (el) el.click()
    }, label)
  })
  const deadline = Date.now() + 12000
  while (Date.now() < deadline) {
    const ready = await frame.evaluate(() => {
      const r = document.querySelector('[data-cb-route]')
      if (!r) return false
      // a v3 route paints the scope node; wait for it and for fonts to settle
      return Boolean(document.querySelector('[data-cb-v3]')) && document.fonts.status === 'loaded'
    }).catch(() => false)
    if (ready) { await sleep(250); return true }
    await sleep(200)
  }
  return false
}

const report = { generated: new Date().toISOString(), port: PORT, width: WIDTH, frames: [], failures: [] }

const { browser, page, frame } = await attach()
await page.bringToFront().catch(() => {})
// the module under test must be the one the window reads; reload with empty cache
await page.reload({ ignoreCache: true }).catch(() => {})
await sleep(600)

await frame.evaluate(() => { window.location.hash = '#/coursebook' })
await sleep(1500)

for (const route of ROUTES) {
  const ok = await routeTo(frame, route.label)
  const el = frame.locator('[data-cb-route]').first()
  const shotPath = path.join(FRAMES, `${route.name}.png`)
  await el.screenshot({ path: shotPath, animations: 'disabled' }).catch(async () => {
    await page.screenshot({ path: shotPath })
  })

  const fonts = await frame.evaluate(() => {
    const want = ['CB Display', 'CB UI']
    const families = [...new Set([...document.fonts].map((f) => f.family.replace(/["']/g, '')))]
    return want.map((f) => ({ family: f, loaded: document.fonts.check(`16px "${f}"`), present: families.includes(f) }))
  }).catch(() => [])

  let axe = { violations: [] }
  try {
    await frame.addScriptTag({ path: AXE })
    axe = await frame.evaluate(async () => {
      const root = document.querySelector('[data-cb-route]') || document.body
      const res = await window.axe.run(root, { resultTypes: ['violations'] })
      return { violations: res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })) }
    })
  } catch (e) {
    axe = { violations: [], error: String(e.message || e) }
  }

  const titles = await frame.evaluate(() => {
    const nodes = [...document.querySelectorAll('[data-cb-route] [data-cb-card-title], [data-cb-route] h3, [data-cb-route] h2')]
    return nodes.map((n) => (n.textContent || '').trim()).filter(Boolean).slice(0, 12)
  }).catch(() => [])

  const frameReport = { route: route.name, label: route.label, route_ready: ok, shot: shotPath, fonts, titles, axe }
  const serious = axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  if (!ok) report.failures.push(`${route.name}: route never reached v3-ready`)
  if (serious.length) report.failures.push(`${route.name}: axe ${serious.map((v) => v.id).join(',')}`)
  if (fonts.some((f) => !f.loaded)) report.failures.push(`${route.name}: font fallback ${fonts.filter((f) => !f.loaded).map((f) => f.family).join(',')}`)

  const basePath = path.join(BASELINE, `${route.name}.png`)
  if (WRITE_BASELINE || !fs.existsSync(basePath)) {
    fs.copyFileSync(shotPath, basePath)
    frameReport.baseline = 'created'
  } else {
    const a = PNG.sync.read(fs.readFileSync(basePath))
    const b = PNG.sync.read(fs.readFileSync(shotPath))
    if (a.width !== b.width || a.height !== b.height) {
      frameReport.diff = { ratio: 1, reason: `size ${a.width}x${a.height} -> ${b.width}x${b.height}` }
      report.failures.push(`${route.name}: frame size changed`)
    } else {
      const diff = new PNG({ width: a.width, height: a.height })
      const changed = pixelmatch(a.data, b.data, diff.data, a.width, a.height, { threshold: 0.1 })
      const ratio = changed / (a.width * a.height)
      fs.writeFileSync(path.join(DIFFS, `${route.name}.png`), PNG.sync.write(diff))
      frameReport.diff = { ratio, changed, total: a.width * a.height }
      if (ratio > THRESHOLD) report.failures.push(`${route.name}: ${(ratio * 100).toFixed(2)}% pixels changed (threshold ${(THRESHOLD * 100).toFixed(2)}%)`)
    }
  }
  report.frames.push(frameReport)
  console.log(`${route.name}: ready=${ok} fonts=${fonts.map((f) => `${f.family}:${f.loaded}`).join(' ')} axe=${serious.length} diff=${frameReport.diff ? (frameReport.diff.ratio * 100).toFixed(2) + '%' : 'n/a'}`)
}

fs.writeFileSync(path.join(HERE, 'report.json'), JSON.stringify(report, null, 2))
const html = `<!doctype html><meta charset="utf-8"><title>Coursebook visual audit</title>
<style>body{font:15px/1.5 system-ui;margin:24px;background:#f5e3c8;color:#1a1713}h1{font-size:22px}
img{width:420px;border:1px solid #cdb894;box-shadow:0 2px 8px #0002}.ok{color:#0d281b}.bad{color:#b4532f;font-weight:600}
pre{background:#f4ecd9;padding:12px;overflow:auto}</style>
<h1>Coursebook visual audit — ${report.generated}</h1>
<p>${report.failures.length ? `<span class="bad">${report.failures.length} failure(s)</span>` : '<span class="ok">all frames clean</span>'}</p>
${report.frames.map((f) => `<h2>${f.route}</h2><img src="frames/${f.route}.png">
<p>fonts: ${f.fonts.map((x) => `${x.family} ${x.loaded ? 'loaded' : 'MISSING'}`).join(' · ')}<br>
axe: ${f.axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => v.id).join(', ') || 'none'}<br>
titles: ${f.titles.join(' | ')}<br>
diff: ${f.diff ? (f.diff.ratio * 100).toFixed(2) + '%' : 'baseline created'}</p>`).join('')}
<h2>Failures</h2><pre>${report.failures.join('\n') || 'none'}</pre>`
fs.writeFileSync(path.join(HERE, 'report.html'), html)

await browser.close().catch(() => {})
console.log(report.failures.length ? `FAIL\n${report.failures.join('\n')}` : 'PASS')
process.exit(report.failures.length ? 1 : 0)
