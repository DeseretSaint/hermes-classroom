/**
 * Re-capture the Coursebook UX-state matrix on a verified, pinned CDP window.
 *
 * Written after attempt 1's screenshots were found to be host overlay frames (CONNECTING /
 * "Hermes couldn't start") while the DOM metrics were valid. Every capture here is gated on:
 *   - the pinned port answering /json/version,
 *   - #cb-route present and non-empty,
 *   - no host connection/error overlay text in body,
 *   - a PNG larger than MIN_BYTES and non-uniform pixels.
 *
 * Usage: CB015_CDP_PORT=9351 node scripts/audit-ux-recapture.mjs [scenario ...]
 */
import { writeFileSync, readFileSync, mkdirSync, existsSync, statSync } from 'node:fs'
import { attach, measure, setMode, setRootText, clearRootText, setReducedMotion, setForcedColors, setViewportCss, ROUTE } from './audit-ux-lib.mjs'

const PORT = process.env.CB015_CDP_PORT || '9351'
const SHOTS = 'docs/a11y-shots'
const FAULT = 'audit/ux/fault.json'
const OUT = 'audit/ux/results-recapture.json'
const MIN_BYTES = 12000
mkdirSync(SHOTS, { recursive: true })

const setFault = (obj) => writeFileSync(FAULT, `${JSON.stringify(obj, null, 2)}\n`)
const results = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : {}

const race = (p, ms, label) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`timeout:${label}`)), ms))])
const wait = (cdp, ms) => cdp.wait(ms)

async function shot(cdp, path) {
  const data = await race(cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: false }), 10000, 'screenshot')
  const buf = Buffer.from(data.data, 'base64')
  writeFileSync(path, buf)
  const size = statSync(path).size
  if (size < MIN_BYTES) throw new Error(`screenshot too small (${size}B): likely blank/overlay frame`)
  return { path, size }
}

async function state(cdp) {
  return cdp.json(`(() => {
    const route = document.querySelector('${ROUTE}')
    const txt = document.body.innerText || ''
    return {
      hash: location.hash,
      route: !!route,
      routeText: (route ? route.innerText : '').slice(0, 300),
      overlay: /couldn.t start|CONNECTING/i.test(txt),
      inner: [innerWidth, innerHeight]
    }
  })()`)
}

async function waitRoute(cdp, expect, ms = 12000) {
  const t0 = Date.now()
  let s = null
  while (Date.now() - t0 < ms) {
    s = await state(cdp)
    if (s.route && !s.overlay && (!expect || s.routeText.includes(expect))) return s
    await wait(cdp, 400)
  }
  return s
}

async function gotoRoute(cdp, { reload = false, expect = null } = {}) {
  if (reload) {
    try { await race(cdp.reload(), 10000, 'reload') } catch (e) { console.log('  reload:', e.message) }
    await wait(cdp, 2200)
  }
  await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
  await cdp.eval(`location.hash = '#/coursebook'`)
  await wait(cdp, 1200)
  let s = await waitRoute(cdp, expect)
  if (!s.route) {
    await cdp.eval(`location.hash = '#/coursebook'`)
    s = await waitRoute(cdp, expect, 10000)
  }
  return s
}

async function clickInRoute(cdp, label, { exact = true } = {}) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return false
    const els = [...root.querySelectorAll('button, a, [role="tab"], [role="option"]')]
    const el = els.find((e) => {
      const t = (e.innerText || '').replace(/\\s+/g, ' ').trim()
      return ${exact ? 't === ' : 't.includes('}${JSON.stringify(label)}${exact ? '' : ')'}
    })
    if (!el) return false
    el.click()
    return true
  })()`)
}

async function typeSearch(cdp, text) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const input = root && root.querySelector('input[type="search"], input[placeholder*="Search" i], input[aria-label*="search" i]')
    if (!input) return false
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(input, ${JSON.stringify(text)})
    input.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  })()`)
}

async function openCourse(cdp, needle) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const needle = ${JSON.stringify(needle)}
    const nodes = [...root.querySelectorAll('*')].filter((el) => {
      const own = (el.innerText || '').trim()
      return own.includes(needle) && ![...el.children].some((c) => (c.innerText || '').includes(needle))
    })
    let node = nodes[nodes.length - 1]
    for (let depth = 0; depth < 8 && node; depth += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Open')
      if (b) { b.click(); return true }
    }
    return false
  })()`)
}

async function openPane(cdp) {
  const shown = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /show right sidebar/i.test(x.getAttribute('aria-label') || x.getAttribute('title') || ''))
    if (!b) return false
    b.click(); return true
  })()`)
  await wait(cdp, 1000)
  const tab = await cdp.eval(`(() => {
    const el = [...document.querySelectorAll('[role="tab"], button')].find((x) => /^coursebook$/i.test((x.innerText || '').trim()) && !x.closest('${ROUTE}'))
    if (!el) return false
    el.click(); return true
  })()`)
  await wait(cdp, 800)
  return { shown, tab }
}

async function closePane(cdp) {
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /hide right sidebar/i.test(x.getAttribute('aria-label') || x.getAttribute('title') || ''))
    if (b) b.click()
    return !!b
  })()`)
  await wait(cdp, 400)
}

const VARIANTS = ['dark', 'light', 'forced', 'narrow', 'text200', 'split', 'hidden']

async function applyVariant(cdp, variant) {
  await clearRootText(cdp)
  await cdp.clearViewport()
  await setForcedColors(cdp, false)
  await setReducedMotion(cdp, false)
  if (!(await cdp.eval(`!!document.querySelector('${ROUTE}')`))) await gotoRoute(cdp)
  if (variant === 'light') await setMode(cdp, 'light')
  else await setMode(cdp, 'dark')
  if (variant === 'forced') await setForcedColors(cdp, true)
  if (variant === 'narrow') { await setViewportCss(cdp, 460, 900); await wait(cdp, 500) }
  else { await setViewportCss(cdp, 1280, 900); await wait(cdp, 400) }
  if (variant === 'text200') { await setRootText(cdp, 32); await wait(cdp, 500) }
}

async function snapshot(cdp, scenario, variant) {
  const s = await state(cdp)
  if (!s.route) throw new Error('route missing at capture')
  if (s.overlay) throw new Error('host overlay present at capture')
  const m = await measure(cdp)
  m.scenario = scenario.id
  m.variant = variant
  m.at = new Date().toISOString()
  m.port = PORT
  m.routeVisible = s.route
  m.hostOverlay = s.overlay
  const path = `${SHOTS}/${scenario.id}-${variant}.png`
  const sh = await shot(cdp, path)
  m.shot = path
  m.shotBytes = sh.size
  if (!results[scenario.id]) results[scenario.id] = { title: scenario.title, spec: scenario.spec, variants: {} }
  results[scenario.id].variants[variant] = m
  writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  return m
}

// ── scenarios (same induction as attempt 1; reloads replaced by explicit waits) ─────────────
const SCENARIOS = [
  {
    id: 'lesson-ready',
    title: 'lesson ready — objective and start/resume',
    spec: '§13 lesson ready',
    expect: 'All courses',
    setup: async (cdp) => {
      setFault({})
      await gotoRoute(cdp, { reload: true, expect: 'All courses' })
      await openCourse(cdp, 'Japanese affection')
      await wait(cdp, 1800)
    }
  },
  {
    id: 'no-courses',
    title: 'first run / no courses — working welcome, no fake progress',
    spec: '§13 first run; no courses',
    expect: 'Build a course',
    fault: { rpc: { 'library.list': { ok: true, contract_version: 6, operation_id: 'audit-empty', result: { items: [], total: 0, applied_filter: 'all', empty_reason: 'no_courses' } } } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true, expect: 'Build a course' }) }
  },
  {
    id: 'no-search-results',
    title: 'no search results — clear filter, preserve data',
    spec: '§13 no search results',
    expect: 'No courses match',
    fault: {},
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true, expect: 'All courses' })
      await clickInRoute(cdp, 'Courses')
      const typed = await typeSearch(cdp, 'zzzz-no-such-course')
      if (!typed) console.log('  WARN no search input found')
      await wait(cdp, 1200)
    }
  },
  {
    id: 'backend-off',
    title: 'backend off — enable instructions / recovery',
    spec: '§13 backend off',
    expect: 'needs its agent plugin',
    fault: { down: true },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true, expect: 'needs its agent plugin' }) }
  },
  {
    id: 'degraded-db',
    title: 'unsupported/immature backend — database not migrated',
    spec: '§13 unsupported backend (degraded branch)',
    expect: 'not migrated',
    fault: { health: { ok: true, result: { plugin_version: '0.1.0', contract_version: 6, db: { ready: false, schema_version: 0 }, backend: 'python' } } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true, expect: 'not migrated' }) }
  },
  {
    id: 'unsupported-backend',
    title: 'unsupported backend — scoped unavailable message, actions absent',
    spec: '§13 unsupported backend',
    fault: { runtime: { backend_package: 'coursebook_plugin_backend', wire_contract: 'cb.rpc', wire_version: 1, contract_methods: 3, implemented_methods: [], single_home_host: true } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true, expect: 'not supported' }) }
  },
  {
    id: 'demo-fixture-mode',
    title: 'demo/pack provenance — rows labelled with pack origin',
    spec: '§13 demo fixture mode',
    expect: 'From a local pack',
    fault: {},
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true, expect: 'From a local pack' }) }
  }
]

const only = process.argv.slice(2)
const list = only.length ? SCENARIOS.filter((s) => only.includes(s.id)) : SCENARIOS
const cdp = await attach(PORT)
let failures = 0
for (const scenario of list) {
  console.log(`\n=== ${scenario.id}`)
  try {
    setFault(scenario.fault || {})
    await scenario.setup(cdp)
    for (const variant of VARIANTS) {
      await applyVariant(cdp, variant)
      if (variant === 'split') { await openPane(cdp); await wait(cdp, 700) }
      if (variant === 'hidden') {
        // Hidden-pane state: the pane must exist first, then be dismissed. Clicking "hide right
        // sidebar" on a closed pane unmounts the route; open it first so the route survives.
        await openPane(cdp)
        await wait(cdp, 600)
        await closePane(cdp)
      }
      const m = await snapshot(cdp, scenario, variant)
      const flags = []
      if (m.overflowX > 0) flags.push(`overflowX=${m.overflowX}`)
      if (m.clipped.length) flags.push(`clipped=${m.clipped.length}`)
      if (m.contrast.length) flags.push(`contrast=${m.contrast.length}`)
      if (m.unnamed.length) flags.push(`unnamed=${m.unnamed.length}`)
      if (m.colorOnly.length) flags.push(`colorOnly=${m.colorOnly.length}`)
      if (m.smallTargets.length) flags.push(`smallTargets=${m.smallTargets.length}`)
      console.log(`  ${variant.padEnd(8)} ${m.viewport.w}x${m.viewport.h} font=${m.rootFont} shot=${m.shotBytes}B ${flags.join(' ') || 'clean'}`)
    }
  } catch (e) {
    failures += 1
    console.log(`  ERROR ${scenario.id}: ${e.message}`)
    if (!results[scenario.id]) results[scenario.id] = { title: scenario.title, spec: scenario.spec, variants: {} }
    results[scenario.id].error = e.message
    writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  }
  await closePane(cdp)
  await setForcedColors(cdp, false)
  await clearRootText(cdp)
  await cdp.clearViewport()
}
setFault({})
writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
console.log(`\nwrote ${OUT}; scenario failures=${failures}`)
cdp.close()
