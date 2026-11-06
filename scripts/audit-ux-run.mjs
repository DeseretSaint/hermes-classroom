/**
 * Sentinel UX/a11y audit runner.
 *
 * One scenario = one documented Coursebook state. Each scenario is induced against the isolated
 * audit backend (44231) through the fault-injection proxy (44232) or by real UI action, then
 * measured in every required presentation:
 *
 *   dark | light | forced-colors | narrow(460) | split(pane) | text200 | hidden-pane
 *
 * Usage: CB015_CDP_PORT=9351 node scripts/audit-ux-run.mjs [scenario ...]
 */
import { writeFileSync, readFileSync, mkdirSync, existsSync } from 'node:fs'
import { attach, measure, setMode, setRootText, clearRootText, setReducedMotion, setForcedColors, tabWalk, focusNow, esc, ROUTE, setViewportCss } from './audit-ux-lib.mjs'

const SHOTS = 'docs/a11y-shots'
const FAULT = 'audit/ux/fault.json'
const OUT = 'audit/ux/results.json'
mkdirSync(SHOTS, { recursive: true })

const setFault = (obj) => writeFileSync(FAULT, `${JSON.stringify(obj, null, 2)}\n`)
const results = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : {}

const wait = (cdp, ms) => cdp.wait(ms)
const routeText = (cdp) => cdp.eval(`(document.querySelector('${ROUTE}') || document.body).innerText`)
const has = async (cdp, text) => (await routeText(cdp)).includes(text)

async function gotoRoute(cdp, { reload = false } = {}) {
  if (reload) {
    await cdp.reload()
    await wait(cdp, 2500)
  }
  await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
  await cdp.eval(`location.hash = '#/coursebook'`)
  await wait(cdp, 2200)
  if (!(await cdp.eval(`!!document.querySelector('${ROUTE}')`))) {
    await cdp.eval(`location.hash = '#/coursebook'`)
    await wait(cdp, 1800)
  }
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
    b.click()
    return true
  })()`)
  await wait(cdp, 1200)
  const tab = await cdp.eval(`(() => {
    const el = [...document.querySelectorAll('[role="tab"], button')].find((x) => /^coursebook$/i.test((x.innerText || '').trim()) && !x.closest('${ROUTE}'))
    if (!el) return false
    el.click()
    return true
  })()`)
  await wait(cdp, 900)
  return { shown, tab }
}

async function closePane(cdp) {
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find((x) => /hide right sidebar/i.test(x.getAttribute('aria-label') || x.getAttribute('title') || ''))
    if (b) b.click()
    return !!b
  })()`)
  await wait(cdp, 500)
}

const VARIANTS = ['dark', 'light', 'forced', 'narrow', 'text200', 'split', 'hidden']

async function applyVariant(cdp, variant) {
  await clearRootText(cdp)
  await cdp.clearViewport()
  await setForcedColors(cdp, false)
  await setReducedMotion(cdp, false)
  if (!(await cdp.eval(`!!document.querySelector('[data-cb-route]')`))) await gotoRoute(cdp)
  if (variant === 'dark' || variant === 'light' || variant === 'forced' || variant === 'narrow' || variant === 'text200') {
    await setMode(cdp, 'dark')
  }
  if (variant === 'light') await setMode(cdp, 'light')
  if (variant === 'forced') {
    await setMode(cdp, 'dark')
    await setForcedColors(cdp, true)
  }
  if (variant === 'narrow') {
    await setViewportCss(cdp, 460, 900)
    await wait(cdp, 500)
  } else {
    await setViewportCss(cdp, 1280, 900)
    await wait(cdp, 400)
  }
  if (variant === 'text200') {
    await setRootText(cdp, 32)
    await wait(cdp, 500)
  }
  return variant
}

async function snapshot(cdp, scenario, variant) {
  const metrics = await measure(cdp)
  metrics.scenario = scenario.id
  metrics.variant = variant
  metrics.at = new Date().toISOString()
  const shot = `${SHOTS}/${scenario.id}-${variant}.png`
  await cdp.shot(shot)
  metrics.shot = shot
  if (!results[scenario.id]) results[scenario.id] = { title: scenario.title, spec: scenario.spec, variants: {} }
  results[scenario.id].variants[variant] = metrics
  writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  return metrics
}

/** Shared keyboard audit: reachability, trap detection, escape behaviour. */
async function keyboardAudit(cdp, scenario) {
  await applyVariant(cdp, 'dark')
  await cdp.eval(`document.activeElement && document.activeElement.blur && document.activeElement.blur()`)
  const walk = await tabWalk(cdp, 45)
  const reached = walk.stops.filter((s) => s.inRoute)
  const escape = await esc(cdp)
  if (!results[scenario.id]) results[scenario.id] = { title: scenario.title, spec: scenario.spec, variants: {} }
  results[scenario.id].keyboard = {
    stops: walk.stops.length,
    routeStops: reached.map((s) => `${s.tag}:${s.name}`).slice(0, 40),
    trap: walk.trap,
    escape
  }
  writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  return results[scenario.id].keyboard
}

async function runScenario(cdp, scenario) {
  console.log(`\n=== ${scenario.id} — ${scenario.title}`)
  setFault(scenario.fault || {})
  await scenario.setup(cdp)
  await wait(cdp, scenario.settle ?? 1200)
  if (scenario.expect && !(await has(cdp, scenario.expect))) {
    console.log(`  WARN expected copy not present: ${scenario.expect}`)
    console.log('  saw:', (await routeText(cdp)).slice(0, 240).replace(/\n+/g, ' | '))
  }
  let variantList = VARIANTS
  if (scenario.variants) variantList = scenario.variants
  for (const variant of variantList) {
    await applyVariant(cdp, variant)
    if (variant === 'split') {
      await openPane(cdp)
      await wait(cdp, 800)
    } else if (variant === 'hidden') {
      await closePane(cdp)
    }
    const m = await snapshot(cdp, scenario, variant)
    const flags = []
    if (m.overflowX > 0) flags.push(`overflowX=${m.overflowX}`)
    if (m.clipped.length) flags.push(`clipped=${m.clipped.length}`)
    if (m.contrast.length) flags.push(`contrast=${m.contrast.length}`)
    if (m.unnamed.length) flags.push(`unnamed=${m.unnamed.length}`)
    if (m.colorOnly.length) flags.push(`colorOnly=${m.colorOnly.length}`)
    console.log(`  ${variant.padEnd(8)} ${m.viewport.w}x${m.viewport.h} font=${m.rootFont} ${flags.join(' ') || 'clean'}`)
  }
  if (scenario.keyboard !== false) await keyboardAudit(cdp, scenario)
  await closePane(cdp)
  await setForcedColors(cdp, false)
  await clearRootText(cdp)
  await cdp.setViewport(1280, 900)
}

// ── scenarios ────────────────────────────────────────────────────────────────────────────────

const demo = 'Japanese affection'

const SCENARIOS = [
  {
    id: 'lesson-ready',
    title: 'lesson ready — objective and start/resume',
    spec: '§13 lesson ready',
    setup: async (cdp) => {
      setFault({})
      await gotoRoute(cdp, { reload: true })
      await openCourse(cdp, demo)
      await wait(cdp, 2000)
    },
    expect: 'All courses'
  },
  {
    id: 'no-courses',
    title: 'first run / no courses — working welcome, no fake progress',
    spec: '§13 first run; no courses',
    fault: {
      rpc: {
        'library.list': {
          ok: true,
          contract_version: 6,
          operation_id: 'audit-empty',
          result: { items: [], total: 0, applied_filter: 'all', empty_reason: 'no_courses' }
        }
      }
    },
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
    },
    expect: 'Build a course'
  },
  {
    id: 'no-search-results',
    title: 'no search results — clear filter, preserve data',
    spec: '§13 no search results',
    fault: {},
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
      await clickInRoute(cdp, 'Courses')
      const typed = await typeSearch(cdp, 'zzzz-no-such-course')
      if (!typed) console.log('  WARN no search input found')
      await wait(cdp, 1200)
    },
    expect: 'No courses match'
  },
  {
    id: 'backend-off',
    title: 'backend off — enable instructions / recovery',
    spec: '§13 backend off',
    fault: { down: true },
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
      await wait(cdp, 1500)
    },
    expect: 'needs its agent plugin'
  },
  {
    id: 'degraded-db',
    title: 'unsupported/immature backend — database not migrated',
    spec: '§13 unsupported backend (degraded branch)',
    fault: { health: { ok: true, result: { plugin_version: '0.1.0', contract_version: 6, db: { ready: false, schema_version: 0 }, backend: 'python' } } },
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
    },
    expect: 'not migrated'
  },
  {
    id: 'unsupported-backend',
    title: 'unsupported backend — scoped unavailable message, actions absent',
    spec: '§13 unsupported backend',
    fault: {
      runtime: {
        backend_package: 'coursebook_plugin_backend',
        wire_contract: 'cb.rpc',
        wire_version: 1,
        contract_methods: 3,
        implemented_methods: [],
        single_home_host: true
      }
    },
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
    }
  },
  {
    id: 'demo-fixture-mode',
    title: 'demo/pack provenance — rows labelled with pack origin',
    spec: '§13 demo fixture mode',
    fault: {},
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
    },
    expect: 'From a local pack'
  }
]

const only = process.argv.slice(2)
const cdp = await attach()
const list = only.length ? SCENARIOS.filter((s) => only.includes(s.id)) : SCENARIOS
for (const scenario of list) {
  try {
    await runScenario(cdp, scenario)
  } catch (error) {
    console.log(`  ERROR ${scenario.id}: ${error.message}`)
    if (!results[scenario.id]) results[scenario.id] = { title: scenario.title, spec: scenario.spec, variants: {} }
    results[scenario.id].error = error.message
    writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  }
}
setFault({})
writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
console.log('\nwrote', OUT)
cdp.close()
