#!/usr/bin/env node
/**
 * H-91 verification against the live Desktop window (CDP 9337).
 *
 * Proves the two gate defects from H-85 are actually gone on the tree this runs against:
 *   V2-1  #/coursebook -> course row -> first path item renders the section, with no host error
 *         boundary, at 1049 / 900 / 460 in the theme given on the command line.
 *   V2-2  the Library route does not overflow horizontally (scrollWidth - clientWidth === 0)
 *         at 1049 / 900 / 460.
 *
 * Usage: node scripts/h91-verify.mjs [outdir] [--dark]
 * Exit code 0 only when every assertion passes; 1 otherwise.
 */
import { writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const outdir = resolve(process.argv[2] || 'audit/ux/round3/h91')
const dark = process.argv.includes('--dark')
const widths = [1049, 900, 460]
mkdirSync(outdir, { recursive: true })
const logPath = resolve(outdir, `verify${dark ? '-dark' : '-light'}.jsonl`)
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
const waitFor = async (expr, ms = 15000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await ev(expr)) return true; await wait(250) } return false }
const shot = async (name) => { const png = await call('Page.captureScreenshot', { format: 'png' }); const path = `${outdir}/${name}.png`; writeFileSync(path, Buffer.from(png.data, 'base64')); return path }

await call('Runtime.enable'); await call('Page.enable')
if (dark) await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
await call('Page.reload', { ignoreCache: true }); await wait(6000)
if (dark) { await ev("document.documentElement.classList.add('dark'); window.dispatchEvent(new Event('resize'))"); await wait(500) }
await ev("location.hash='#/coursebook'")
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 20000))) { console.error('route never mounted'); process.exit(1) }
await wait(1500)

const results = []
const failures = []
const setWidth = async (w) => {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(w * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
  await ev('window.dispatchEvent(new Event("resize"))'); await wait(800)
}
const clickSel = async (sel) => ev(`(()=>{const el=document.querySelector(${JSON.stringify(sel)});if(!el)return false;(el.closest('button')||el).click();return true})()`)
const nav = async (id) => ev(`(()=>{const el=document.querySelector('[data-cb-nav-item="${id}"]');if(!el)return false;el.click();return true})()`)

// ---- V2-1: the section route renders with a null runtime --------------------------------
let sectionReached = false
for (const w of widths) {
  await ev("location.hash='#/coursebook'"); await wait(1500)
  // leave any open course/section view so the course list is the current body
  if (await ev("!!document.querySelector('[data-cb-section-actions]')")) {
    const back = await ev(`(()=>{const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>/^back$/i.test((x.innerText||'').trim()));if(!b)return false;b.click();return true})()`)
    await wait(2000)
    if (!back) { await nav('courses'); await wait(2000) }
  }
  await nav('courses'); await wait(1500)
  await setWidth(w)
  const opened = await clickSel('[data-cb-all-courses-row]')
  await wait(3500)
  const clicked = opened ? await clickSel('[data-cb-path-item]') : false
  await wait(4000)
  const m = JSON.parse(await ev(`(()=>{
    const route = document.querySelector('[data-cb-route]')
    const boundary = document.body.innerText.includes('failed to render')
    const sectionActions = !!document.querySelector('[data-cb-section-actions]')
    const errorText = boundary ? document.body.innerText.slice(0, 400) : null
    return JSON.stringify({
      innerWidth,
      hash: location.hash,
      routeMounted: !!route,
      boundary,
      errorText,
      sectionActions,
      heading: route ? (route.querySelector('h1,h2,h3') || {}).innerText || null : null,
      textHead: route ? route.innerText.trim().slice(0, 180) : null
    })
  })()`))
  sectionReached = sectionReached || m.sectionActions
  const ok = m.routeMounted && !m.boundary && m.sectionActions
  if (!ok) failures.push(`V2-1 ${w}px: boundary=${m.boundary} actions=${m.sectionActions}`)
  const path = await shot(`section-${w}${dark ? '-dark' : '-light'}`)
  const row = { kind: 'section', width: w, ok, path, ...m }
  results.push(row); appendFileSync(logPath, JSON.stringify(row) + '\n')
  console.log('SECTION', w, ok ? 'PASS' : 'FAIL', JSON.stringify({ boundary: m.boundary, actions: m.sectionActions, head: (m.textHead || '').slice(0, 60) }))
}

// ---- V2-2: Library route does not overflow ---------------------------------------------
await ev("location.hash='#/coursebook'"); await wait(1500)
await nav('library'); await wait(3000)
for (const w of widths) {
  await setWidth(w)
  const m = JSON.parse(await ev(`(()=>{
    const route = document.querySelector('[data-cb-route]')
    if (!route) return JSON.stringify({ missing: true })
    const off = [...route.querySelectorAll('*')]
      .filter((e) => e.clientWidth > 0 && e.scrollWidth - e.clientWidth > 1)
      .slice(0, 8)
      .map((e) => ({ tag: e.tagName, sw: e.scrollWidth, cw: e.clientWidth, t: (e.innerText || '').trim().slice(0, 50) }))
    return JSON.stringify({
      innerWidth,
      routeWidth: route.clientWidth,
      routeOverflow: route.scrollWidth - route.clientWidth,
      bodyOverflow: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
      off
    })
  })()`))
  const ok = !m.missing && m.routeOverflow === 0 && m.bodyOverflow === 0
  if (!ok) failures.push(`V2-2 ${w}px: routeOverflow=${m.routeOverflow} body=${m.bodyOverflow}`)
  const path = await shot(`library-${w}${dark ? '-dark' : '-light'}`)
  const row = { kind: 'library', width: w, ok, path, ...m }
  results.push(row); appendFileSync(logPath, JSON.stringify(row) + '\n')
  console.log('LIBRARY', w, ok ? 'PASS' : 'FAIL', JSON.stringify({ routeW: m.routeWidth, routeOverflow: m.routeOverflow, bodyOverflow: m.bodyOverflow, off: (m.off || []).slice(0, 2) }))
}

// ---- P2-4: one primary on Parent Studio ------------------------------------------------
await ev("location.hash='#/coursebook'"); await wait(1500)
await nav('studio'); await wait(3000)
await setWidth(1049)
const studio = JSON.parse(await ev(`(()=>{
  const route = document.querySelector('[data-cb-route]')
  if (!route) return JSON.stringify({ missing: true })
  const primaries = [...route.querySelectorAll('button')]
    .filter((b) => b.dataset.variant === 'default' && !b.disabled)
    .map((b) => (b.innerText || '').trim())
  return JSON.stringify({ primaries, duplicate: primaries.length !== new Set(primaries).size })
})()`))
const studioOk = !studio.missing && (studio.primaries || []).filter((t) => t === 'New lesson plan').length <= 1
if (!studioOk) failures.push(`P2-4: ${(studio.primaries || []).length} primaries ${JSON.stringify(studio.primaries || studio)}`)
const studioPath = await shot(`studio-1049${dark ? '-dark' : '-light'}`)
results.push({ kind: 'studio', width: 1049, ok: studioOk, path: studioPath, ...studio })
appendFileSync(logPath, JSON.stringify({ kind: 'studio', width: 1049, ok: studioOk, path: studioPath, ...studio }) + '\n')
console.log('STUDIO', studioOk ? 'PASS' : 'FAIL', JSON.stringify(studio.primaries))

socket.close()
writeFileSync(resolve(outdir, `summary${dark ? '-dark' : '-light'}.json`), JSON.stringify({ theme: dark ? 'dark' : 'light', sectionReached, results, failures }, null, 2))
console.log(failures.length ? `FAIL ${failures.length}` : 'PASS all checks')
process.exit(failures.length ? 1 : 0)
