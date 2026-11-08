#!/usr/bin/env node
/**
 * H-94 verification against the live Desktop window.
 *
 * On the Parent Studio landing and the Field Desk, at 1049 and 460 (light and dark), asserts from
 * the real renderer:
 *
 *   - exactly one `variant=default` primary button on the surface
 *   - Parent Studio's header carries no second create action
 *   - the desk carries exactly one facts line and zero stat cells (no three-card triplet)
 *   - the facts line is one flex row at 1049 (it may wrap at 460)
 *   - the page does not overflow horizontally
 *   - the keyboard order still reaches the primary after the destination nav, unchanged
 *
 * Usage: CB009_CDP_PORT=9364 node scripts/h94-primary-verify.mjs [outdir] [--dark]
 * Exit code 0 only when every assertion passes.
 */
import { writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9364'
const args = process.argv.slice(2).filter((arg) => !arg.startsWith('--'))
const outdir = resolve(args[0] || 'audit/ux/round3/h94')
const dark = process.argv.includes('--dark')
const theme = dark ? 'dark' : 'light'
const widths = [1049, 460]
mkdirSync(outdir, { recursive: true })
const logPath = resolve(outdir, `verify-${theme}.jsonl`)
writeFileSync(logPath, '')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) { console.error('no page target'); process.exit(1) }
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { socket.addEventListener('open', res, { once: true }); socket.addEventListener('error', rej, { once: true }) })
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) } })
const send = (method, params = {}) => new Promise((res) => { const id = nextId++; pending.set(id, res); socket.send(JSON.stringify({ id, method, params })) })
const call = async (method, params = {}) => { const r = await send(method, params); if (r.error) throw new Error(JSON.stringify(r.error)); return r.result }
const ev = async (expression) => { const r = await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 500)); return r.result.value }
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 20000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await ev(expr)) return true; await wait(250) } return false }
const shot = async (name) => { const png = await call('Page.captureScreenshot', { format: 'png' }); const path = `${outdir}/${name}.png`; writeFileSync(path, Buffer.from(png.data, 'base64')); return path }

await call('Runtime.enable'); await call('Page.enable')
await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: theme }] })

// The app runs at a zoom factor (1049 innerWidth over a 1170 emulated width). Measure it instead
// of hard-coding, then ask for the window width the card names.
await call('Emulation.setDeviceMetricsOverride', { width: 1049, height: 1000, deviceScaleFactor: 1, mobile: false })
const zoom = (await ev('window.innerWidth')) / 1049
const setWidth = async (w) => {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(w / zoom), height: 1000, deviceScaleFactor: 1, mobile: false })
  await ev('window.dispatchEvent(new Event("resize"))')
  await wait(500)
}

const nav = async (id) => ev(`(()=>{const el=document.querySelector('[data-cb-nav-item="${id}"]');if(!el)return false;el.click();return true})()`)

await ev("location.hash='#/coursebook'"); await wait(1500)
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 8000))) {
  await ev("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))")
  await call('Page.reload', { ignoreCache: true }); await wait(6000)
  await ev("location.hash='#/coursebook'")
}
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 20000))) { console.error('route never mounted'); process.exit(1) }
await wait(1200)

const PROBE = `(() => {
  const route = document.querySelector('[data-cb-route]')
  if (!route) return { missing: true }
  const visible = (el) => !!(el.getClientRects && el.getClientRects().length) && getComputedStyle(el).visibility !== 'hidden'
  const primaries = [...route.querySelectorAll('button[data-variant="default"]')].filter(visible)
  const facts = [...route.querySelectorAll('[data-cb-desk-facts]')].filter(visible)
  const stats = [...route.querySelectorAll('[data-cb-desk-stat]')].filter(visible)
  const header = route.querySelector('header')
  const headerPrimaries = header ? [...header.querySelectorAll('button[data-variant="default"]')].filter(visible) : []
  const focusables = [...route.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter(visible)
    .map((el) => {
      const rect = el.getBoundingClientRect()
      return {
        tag: el.tagName.toLowerCase(),
        label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40),
        nav: el.hasAttribute('data-cb-nav-item') ? el.getAttribute('data-cb-nav-item') : null,
        variant: el.getAttribute('data-variant') || null,
        top: Math.round(rect.top),
        left: Math.round(rect.left)
      }
    })
  const line = facts[0] ? facts[0].querySelector('[data-cb-hero-facts]') : null
  const factNodes = line ? [...line.querySelectorAll('[data-cb-hero-fact]')].filter(visible) : []
  const rows = new Set(factNodes.map((el) => Math.round(el.getBoundingClientRect().top)))
  return {
    h1: [...route.querySelectorAll('h1')].map((el) => el.textContent.trim()),
    primaries: primaries.map((el) => ({ label: el.textContent.trim(), width: Math.round(el.getBoundingClientRect().width), height: Math.round(el.getBoundingClientRect().height) })),
    headerPrimaries: headerPrimaries.map((el) => el.textContent.trim()),
    factsLines: facts.length,
    factsCount: facts[0] ? Number(facts[0].dataset.cbDeskFacts) : 0,
    factsDisplay: line ? getComputedStyle(line).display : null,
    factsFlexWrap: line ? getComputedStyle(line).flexWrap : null,
    factLabels: factNodes.map((el) => el.dataset.cbHeroFact),
    factValues: factNodes.map((el) => [...el.children].filter((child) => child.getAttribute('aria-hidden') !== 'true')[0].textContent.trim()),
    factRows: rows.size,
    statCells: stats.length,
    tripletGrid: [...route.querySelectorAll('*')].some((el) => /repeat\\(3/.test(getComputedStyle(el).gridTemplateColumns || '')),
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    innerWidth: window.innerWidth,
    keyboard: focusables.slice(0, 14)
  }
})()`

const checks = []
const record = (surface, width, result) => {
  const row = { surface, width, theme, ...result }
  appendFileSync(logPath, JSON.stringify(row) + '\n')
  return row
}

for (const width of widths) {
  await setWidth(width)

  // Field Desk: the default Courses destination and the desk view.
  await nav('courses'); await wait(1600)
  if (await ev("!!document.querySelector('[data-cb-courses-list]') && !document.querySelector('[data-cb-desk]')")) {
    await ev("(()=>{const b=[...document.querySelectorAll('button')].find(x=>/Field Desk/i.test(x.textContent));if(b)b.click()})()")
    await wait(1200)
  }
  const desk = record('desk', width, await ev(PROBE))
  checks.push(['desk primary count = 1', width, desk.primaries.length === 1, desk.primaries])
  checks.push(['desk facts line = 1', width, desk.factsLines === 1, desk.factsLines])
  checks.push(['desk stat cells = 0', width, desk.statCells === 0, desk.statCells])
  checks.push(['desk no 3-column grid', width, desk.tripletGrid === false, desk.tripletGrid])
  checks.push(['desk facts flex row', width, desk.factsDisplay === 'flex', desk.factsDisplay])
  if (width === 1049) checks.push(['desk facts on one row at 1049', width, desk.factRows === 1, desk.factRows])
  checks.push(['desk no horizontal overflow', width, desk.overflowX <= 1, desk.overflowX])
  const deskPrimaryIdx = desk.keyboard.findIndex((item) => item.variant === 'default')
  const deskNavIdx = desk.keyboard.findIndex((item) => item.nav === 'courses')
  checks.push(['desk keyboard: nav before primary', width, deskNavIdx >= 0 && deskPrimaryIdx > deskNavIdx, { deskNavIdx, deskPrimaryIdx }])
  checks.push(['desk screenshot', width, Boolean(await shot(`desk-${width}-${theme}`)), null])

  // Parent Studio landing.
  await nav('studio'); await wait(1600)
  const studio = record('studio', width, await ev(PROBE))
  checks.push(['studio primary count = 1', width, studio.primaries.length === 1, studio.primaries])
  checks.push(['studio primary is New lesson plan', width, studio.primaries[0] && studio.primaries[0].label === 'New lesson plan', studio.primaries])
  checks.push(['studio header has no primary', width, studio.headerPrimaries.length === 0, studio.headerPrimaries])
  checks.push(['studio no horizontal overflow', width, studio.overflowX <= 1, studio.overflowX])
  const studioPrimaryIdx = studio.keyboard.findIndex((item) => item.variant === 'default')
  const studioNavIdx = studio.keyboard.findIndex((item) => item.nav === 'studio')
  checks.push(['studio keyboard: nav before primary', width, studioNavIdx >= 0 && studioPrimaryIdx > studioNavIdx, { studioNavIdx, studioPrimaryIdx }])
  checks.push(['studio screenshot', width, Boolean(await shot(`studio-${width}-${theme}`)), null])
}

await call('Emulation.clearDeviceMetricsOverride')
let failures = 0
for (const [name, width, ok, detail] of checks) {
  if (!ok) { failures += 1; console.log(`FAIL ${name} @${width}: ${JSON.stringify(detail)}`) }
}
console.log(`${failures === 0 ? 'PASS' : 'FAIL'} h94 ${theme}: ${checks.length - failures}/${checks.length} checks, 0 failures expected`)
if (failures === 0) console.log('frames:', outdir)
process.exit(failures === 0 ? 0 : 1)
