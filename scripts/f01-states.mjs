/**
 * The seven audited Coursebook states, induced exactly as `scripts/audit-ux-run.mjs` does
 * (same fault-injection shapes, same real UI actions), shared by the F-01 measurement scripts.
 */
import { writeFileSync } from 'node:fs'
import { ROUTE } from './audit-ux-lib.mjs'

export const FAULT = 'audit/ux/fault.json'
export const setFault = (obj) => writeFileSync(FAULT, `${JSON.stringify(obj, null, 2)}\n`)
export const wait = (cdp, ms) => cdp.wait(ms)
export const routeText = (cdp) => cdp.eval(`(document.querySelector('${ROUTE}') || document.body).innerText`)
export const has = async (cdp, text) => (await routeText(cdp)).includes(text)

export async function gotoRoute(cdp, { reload = false } = {}) {
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

export const clickInRoute = (cdp, label) => cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}')
  if (!root) return false
  const el = [...root.querySelectorAll('button, a, [role="tab"]')].find((e) => (e.innerText || '').replace(/\\s+/g, ' ').trim() === ${JSON.stringify(label)})
  if (!el) return false
  el.click()
  return true
})()`)

export const typeSearch = (cdp, text) => cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}')
  const input = root && root.querySelector('input[type="search"], input[placeholder*="Search" i], input[aria-label*="search" i]')
  if (!input) return false
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(input, ${JSON.stringify(text)})
  input.dispatchEvent(new Event('input', { bubbles: true }))
  return true
})()`)

const openCourse = (cdp, needle) => cdp.eval(`(() => {
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

const demo = 'Japanese affection'

export const SCENARIOS = [
  {
    id: 'lesson-ready',
    setup: async (cdp) => { setFault({}); await gotoRoute(cdp, { reload: true }); await openCourse(cdp, demo); await wait(cdp, 2000) },
    expect: 'All courses'
  },
  {
    id: 'no-courses',
    fault: { rpc: { 'library.list': { ok: true, contract_version: 6, operation_id: 'audit-empty',
      result: { items: [], total: 0, applied_filter: 'all', empty_reason: 'no_courses' } } } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true }) },
    expect: 'Build a course'
  },
  {
    id: 'no-search-results',
    setup: async (cdp) => {
      await gotoRoute(cdp, { reload: true })
      await clickInRoute(cdp, 'Courses')
      if (!(await typeSearch(cdp, 'zzzz-no-such-course'))) console.log('  WARN no search input')
      await wait(cdp, 1200)
    },
    expect: 'No courses match'
  },
  {
    id: 'backend-off',
    fault: { down: true },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true }); await wait(cdp, 1500) },
    expect: 'needs its agent plugin'
  },
  {
    id: 'degraded-db',
    fault: { health: { ok: true, result: { plugin_version: '0.1.0', contract_version: 6,
      db: { ready: false, schema_version: 0 }, backend: 'python' } } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true }) },
    expect: 'not migrated'
  },
  {
    id: 'unsupported-backend',
    fault: { runtime: { backend_package: 'coursebook_plugin_backend', wire_contract: 'cb.rpc', wire_version: 1,
      contract_methods: 3, implemented_methods: [], single_home_host: true } },
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true }) }
  },
  {
    id: 'demo-fixture-mode',
    setup: async (cdp) => { await gotoRoute(cdp, { reload: true }) },
    expect: 'From a local pack'
  }
]
