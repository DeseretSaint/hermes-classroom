#!/usr/bin/env node
/**
 * CP-024 — measure the course-home route for the binding visual gate.
 *
 * `visual/audit.mjs` scores the four destination routes; the course home is a *deep* screen
 * (shell state under `#/coursebook`), so the gate's course-home numbers have to be taken after a
 * real click into a course. This script attaches to the same rig over CDP, drives the same
 * learner clicks as `docs/visual-review/cp-024/drive-course-home.js`, and reports exactly the
 * fields the gate asks for: rendered route width × height, `data-cb-scope`, the two product fonts,
 * axe serious/critical on the course subtree, and the title word-wrap probe.
 *
 * It writes `docs/visual-review/cp-024/gate-course-home.json` and prints one line per fact.
 *
 *   node docs/visual-review/cp-024/measure-course-home.mjs --port 9361
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..', '..')
// The gate's browser toolchain lives beside `visual/audit.mjs`; resolve it from there so this
// script can sit with the rest of the card's evidence tooling.
const require = createRequire(path.join(ROOT, 'visual', 'package.json'))
const { chromium } = require('playwright')
const AXE = require.resolve('axe-core/axe.min.js')

const args = process.argv.slice(2)
const opt = (name, fallback) => {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}
const PORT = Number(opt('--port', 9361))
const EMULATE_WIDTH = Number(opt('--width', 1440))
const EMULATE_HEIGHT = Number(opt('--height', 900))
const ROOT_FONT = opt('--root-font', null)
const SHOT = opt('--shot', null)
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

async function attach() {
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`)
  const deadline = Date.now() + 15000
  while (Date.now() < deadline) {
    for (const context of browser.contexts()) {
      for (const page of context.pages()) {
        for (const frame of page.frames()) {
          try {
            if (await frame.evaluate(() => Boolean(document.querySelector('[data-cb-route]')))) {
              return { browser, page, frame }
            }
          } catch {
            /* frame navigating */
          }
        }
      }
    }
    await sleep(300)
  }
  throw new Error(`no [data-cb-route] frame on CDP port ${PORT}`)
}

const { browser, page, frame } = await attach()
await page.bringToFront().catch(() => {})
// The gate renders at the audit viewport, so measure there: the rig window is tiled small, and a
// 941-wide pane is a different breakpoint. The override is cleared before the script exits.
const cdp = await page.context().newCDPSession(page)
const settle = async () => {
  await frame.evaluate(() => window.dispatchEvent(new Event('resize')))
  await frame.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  await sleep(400)
}
await cdp.send('Emulation.setDeviceMetricsOverride', {
  width: EMULATE_WIDTH,
  height: EMULATE_HEIGHT,
  deviceScaleFactor: 1,
  mobile: false
})
await sleep(300)
await settle()
await frame.evaluate(() => { window.location.hash = '#/coursebook' })
await sleep(1200)
if (ROOT_FONT) {
  await frame.evaluate((value) => { document.documentElement.style.fontSize = value }, ROOT_FONT)
  await sleep(400)
  await settle()
}

const driver = fs.readFileSync(path.join(HERE, 'drive-course-home.js'), 'utf8')
await frame.evaluate(`(async () => { ${driver} })()`)
const deadline = Date.now() + 20000
let arrived = false
while (Date.now() < deadline) {
  arrived = await frame.evaluate(() => Boolean(document.querySelector('[data-cb-course-home-v3]')))
  if (arrived) break
  await sleep(250)
}
if (!arrived) throw new Error('the course home never appeared')
await sleep(800)

const measured = await frame.evaluate(() => {
  const root = document.querySelector('[data-cb-route]')
  const rect = root.getBoundingClientRect()
  const words = []
  for (const selector of ['[data-cb-course-title]', '[data-cb-course-plate-title]']) {
    const el = document.querySelector(selector)
    if (!el) continue
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    let node = walker.nextNode()
    while (node) {
      const value = node.nodeValue || ''
      const re = /\S+/g
      let match = re.exec(value)
      while (match) {
        const range = document.createRange()
        range.setStart(node, match.index)
        range.setEnd(node, match.index + match[0].length)
        const tops = new Set(
          [...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top / 2))
        )
        if (tops.size > 1) words.push({ selector, word: match[0], lines: tops.size })
        match = re.exec(value)
      }
      node = walker.nextNode()
    }
  }
  return {
    route: { width: Math.round(rect.width), height: Math.round(rect.height) },
    scope: root.getAttribute('data-cb-scope'),
    motion: root.getAttribute('data-cb-motion'),
    fonts: ['CB Display', 'CB UI'].map((family) => ({
      family,
      loaded: document.fonts.check(`16px "${family}"`)
    })),
    fonts_status: document.fonts.status,
    course_home_mode: (document.querySelector('[data-cb-course-home-v3]') || {}).getAttribute
      ? document.querySelector('[data-cb-course-home-v3]').getAttribute('data-cb-course-home-v3')
      : null,
    body_mode: (document.querySelector('[data-cb-course-body]') || {}).getAttribute
      ? document.querySelector('[data-cb-course-body]').getAttribute('data-cb-course-body')
      : null,
    primaries: document.querySelectorAll(
      '[data-cb-course-detail] [data-cb3-pill="primary"], [data-cb-course-detail] [data-cb-action="primary"]'
    ).length,
    dom_order: [
      ...document.querySelectorAll(
        '[data-cb-course-plate],[data-cb-course-route="list"],[data-cb-course-aside]'
      )
    ].map((el) =>
      el.hasAttribute('data-cb-course-aside')
        ? 'aside'
        : el.hasAttribute('data-cb-course-route')
          ? 'route'
          : 'plate'
    ),
    overflows_horizontally: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    plate_title: (() => {
      const el = document.querySelector('[data-cb-course-plate-title]')
      if (!el) return null
      const style = getComputedStyle(el)
      return {
        font_size: style.fontSize,
        client_height: el.clientHeight,
        scroll_height: el.scrollHeight,
        clipped_vertically: el.scrollHeight > el.clientHeight + 1
      }
    })(),
    word_wraps: words
  }
})

let axe = { violations: [] }
try {
  await frame.addScriptTag({ path: AXE })
  axe = await frame.evaluate(async () => {
    const root = document.querySelector('[data-cb-course-detail]') || document.body
    const result = await window.axe.run(root, { resultTypes: ['violations'] })
    return {
      violations: result.violations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        nodes: violation.nodes.length
      }))
    }
  })
} catch (error) {
  axe = { violations: [], error: String((error && error.message) || error) }
}

const serious = axe.violations.filter(
  (violation) => violation.impact === 'serious' || violation.impact === 'critical'
)
await cdp.send('Emulation.clearDeviceMetricsOverride').catch(() => {})
if (SHOT) {
  await page.locator('[data-cb-course-plate]').first().screenshot({ path: SHOT, animations: 'disabled' })
  console.log(`plate shot:   ${SHOT}`)
}
const record = {
  generated: new Date().toISOString(),
  port: PORT,
  emulated_viewport: { width: EMULATE_WIDTH, height: EMULATE_HEIGHT },
  ...measured,
  axe,
  serious_critical: serious.map((violation) => violation.id)
}
const out = path.join(HERE, `gate-course-home-${EMULATE_WIDTH}.json`)
fs.writeFileSync(out, `${JSON.stringify(record, null, 2)}\n`)
console.log(`route:        ${record.route.width} x ${record.route.height}`)
console.log(`scope:        ${record.scope}   motion: ${record.motion}`)
console.log(`fonts:        ${record.fonts.map((f) => `${f.family}=${f.loaded}`).join('  ')} (${record.fonts_status})`)
console.log(`course home:  ${record.course_home_mode}   body: ${record.body_mode}   primaries: ${record.primaries}`)
console.log(`dom order:    ${record.dom_order.join(' -> ')}   overflow: ${record.overflows_horizontally}`)
console.log(`plate title:  ${record.plate_title ? JSON.stringify(record.plate_title) : 'no type field'}`)
console.log(`axe serious/critical: ${record.serious_critical.length ? record.serious_critical.join(', ') : 'none'}`)
console.log(`word splits:  ${record.word_wraps.length ? JSON.stringify(record.word_wraps) : 'none'}`)
console.log(`wrote ${path.relative(ROOT, out)}`)
await browser.close().catch(() => {})
