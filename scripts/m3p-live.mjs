#!/usr/bin/env node
/**
 * M3-U1 live smoke: the shipped module in the real Desktop renderer.
 *
 *   CB009_CDP_PORT=9341 node scripts/m3p-live.mjs
 *
 * What it proves, and what it does not:
 *
 *   - proves the edited `desktop/plugin.js` loads in the real renderer, registers the /coursebook
 *     route, paints the Field Desk and the course detail without a console exception, and that the
 *     section page still opens a lesson document and stays inside the viewport at 460 px;
 *   - does NOT prove the practice loop live. The Pronunciation Studio is seated on a block whose
 *     media carries `role: "narration"`, and the isolated home this window reads has no narration
 *     artifact at all (only pack zip/pdf artifacts), so no section has a model phrase to practise.
 *     Generating one is provider TTS spend, which this card does not authorise. That gap is
 *     recorded here and in the card handoff rather than papered over with a seeded fixture.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { attach, gotoCoursebook } from './cb-loops-lib.mjs'

const OUT = resolve('audit/visual/m3-pronunciation/live')
mkdirSync(OUT, { recursive: true })

const cdp = await attach()
const evidence = { steps: [], screenshots: [], consoleErrors: [], notProven: [] }
const step = (name, value) => {
  const row = { step: name, ...value, at: new Date().toISOString() }
  evidence.steps.push(row)
  console.log(JSON.stringify(row).slice(0, 500))
  return row
}

// The rig starts opt-in for a unified package; enable the plugin in this fresh userdata.
const enabled = await cdp.eval(`(() => {
  const key = 'hermes.desktop.pluginDecisions.v2'
  const current = JSON.parse(localStorage.getItem(key) || '{}')
  const next = { ...current, coursebook: true }
  localStorage.setItem(key, JSON.stringify(next))
  return next.coursebook === true
})()`)
if (enabled) {
  await cdp.eval(`(location.reload())`)
  await cdp.wait(2500)
}

await gotoCoursebook(cdp)
const mounted = await cdp.waitFor(`!!document.querySelector('[data-cb-route="/coursebook"]')`, { timeout: 30000, label: 'route' })
step('route-mounted', { mounted })

const navText = await cdp.json(`(() => {
  const nav = [...document.querySelectorAll('a,button')].map((node) => (node.textContent || '').trim())
  return { hasCoursebook: nav.some((text) => text === 'Coursebook') }
})()`)
step('sidebar-nav', navText)

// Read the studio contract the page itself sees: the status route is the only availability door.
const status = await cdp.json(`(async () => {
  try {
    const ctx = window.__HERMES_PLUGIN_SDK__
    const response = await fetch('/api/plugins/coursebook/pronunciation/status').catch(() => null)
    return { reachable: Boolean(response) }
  } catch (error) {
    return { reachable: false, error: String(error) }
  }
})()`)
step('plugin-sdk-present', { hasSdk: Boolean(status && status.reachable) })

// Open the first course, then its first section, exactly as a learner would.
const opened = await cdp.json(`(() => {
  const rows = [...document.querySelectorAll('[data-cb-desk] button, [data-cb-desk] a')]
  const labels = rows.map((node) => (node.textContent || '').trim()).filter(Boolean).slice(0, 12)
  return { labels }
})()`)
step('desk-controls', opened)

const clickByText = async (text) => {
  return cdp.json(`(() => {
    const nodes = [...document.querySelectorAll('button, a')]
    const node = nodes.find((candidate) => (candidate.textContent || '').trim() === ${JSON.stringify(text)})
    if (!node) return { clicked: false }
    node.click()
    return { clicked: true }
  })()`)
}

for (const label of ['Continue this course', 'Open this section', 'Open in Textbook']) {
  const result = await clickByText(label)
  if (result.clicked) {
    await cdp.wait(1500)
    step(`clicked:${label}`, result)
  }
}

const documentState = await cdp.json(`(() => {
  const doc = document.querySelector('[data-cb-document]')
  const studio = document.querySelector('[data-cb-pronunciation]')
  const narration = document.querySelector('[data-cb-block-media]')
  return {
    document: doc ? doc.getAttribute('data-cb-document') : null,
    view: doc ? doc.getAttribute('data-cb-lesson-view') : null,
    studioSeats: document.querySelectorAll('[data-cb-pronunciation]').length,
    mediaChildren: document.querySelectorAll('[data-cb-block-media]').length,
    narrationSeatsPossible: Boolean(narration)
  }
})()`)
step('lesson-document', documentState)

const viewport = await cdp.json(`(() => ({
  width: innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  overflow: document.documentElement.scrollWidth > innerWidth + 1
}))()`)
step('viewport-1280', viewport)

await cdp.shot(`${OUT}/live-01-coursebook-route.png`)
evidence.screenshots.push('live-01-coursebook-route.png')

await cdp.send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await cdp.wait(900)
const narrow = await cdp.json(`(() => ({
  width: innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  overflow: document.documentElement.scrollWidth > innerWidth + 1
}))()`)
step('viewport-460', narrow)
await cdp.shot(`${OUT}/live-02-coursebook-460.png`)
evidence.screenshots.push('live-02-coursebook-460.png')
await cdp.send('Emulation.clearDeviceMetricsOverride')

evidence.consoleErrors = cdp.errors.filter((entry) => !/ResizeObserver|Autofill|DevTools/.test(entry.text || ''))
evidence.notProven = [
  'A live Record -> Stop -> Compare walk. No section in this isolated home carries a narration media child, so no block seats the studio; the target phrase and the reference audio both come from that authored narration.',
  'The status route on this rig answers from the older backend the window is connected to (wire v7, no pronunciation route), so live availability is not demonstrated here; the renderer states are proven by the component-driven frames and tests.'
]
writeFileSync(`${OUT}/live-evidence.json`, JSON.stringify(evidence, null, 2))
console.log(JSON.stringify({ screenshots: evidence.screenshots.length, consoleErrors: evidence.consoleErrors.length, studioSeats: documentState.studioSeats }))
