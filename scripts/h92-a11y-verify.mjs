#!/usr/bin/env node
/**
 * H-92 verification against the live Desktop window (CDP 9338).
 *
 * Reads the real accessibility tree the renderer exposes (Accessibility.getFullAXTree) and the
 * real tab order (Input.dispatchKeyEvent), at 1049 / 900 / 460 for every Coursebook surface:
 *
 *   courses-desk  destination nav -> the Field Desk
 *   library       destination nav -> Library
 *   studio        destination nav -> Parent Studio
 *   section       the desk path row -> course -> textbook section (reading column)
 *
 * For each surface it asserts: exactly one level-1 heading, the first heading is level 1, no
 * skipped heading level, a named navigation + main landmark (and a named complementary landmark on
 * the workspace), and that Tab lands on the skip link, which reveals on focus and moves focus into
 * `[data-cb-reading-column]` (or the main region when the surface has no reading column).
 *
 * Usage: node scripts/h92-a11y-verify.mjs [outdir] [--dark]
 * Exit code 0 only when every assertion passes.
 */
import { writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9338'
const outdir = resolve(process.argv[2] || 'audit/ux/round3/h92')
const dark = process.argv.includes('--dark')
const widths = [1049, 900, 460]
const theme = dark ? 'dark' : 'light'
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

await call('Runtime.enable'); await call('Page.enable'); await call('Accessibility.enable'); await call('DOM.enable')
await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }] })
if (dark) await ev("document.documentElement.classList.add('dark')")

const setWidth = async (w) => {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(w * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
  await ev('window.dispatchEvent(new Event("resize"))'); await wait(700)
}

const nav = async (id) => ev(`(()=>{const el=document.querySelector('[data-cb-nav-item="${id}"]');if(!el)return false;el.click();return true})()`)
const clickSel = async (sel) => ev(`(()=>{const el=document.querySelector(${JSON.stringify(sel)});if(!el)return false;(el.closest('button')||el).click();return true})()`)

// The route must be mounted, not bounced back to #/ by the plugin opt-in decision.
await ev("location.hash='#/coursebook'"); await wait(1500)
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 8000))) {
  await ev("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))")
  await call('Page.reload', { ignoreCache: true }); await wait(6000)
  await ev("location.hash='#/coursebook'")
}
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 20000))) { console.error('route never mounted'); process.exit(1) }
await wait(1200)

const results = []
const failures = []

const axSnapshot = async () => {
  // Scope the AX read to the Coursebook route: the page also hosts the chat transcript and the
  // lesson pane, and those are different surfaces with their own headings.
  const { root } = await call('DOM.getDocument', { depth: -1 })
  const domById = new Map()
  const indexDom = (node) => {
    domById.set(node.nodeId, node)
    for (const child of node.children || []) indexDom(child)
  }
  indexDom(root)
  const attributesOf = (node) => (node.attributes || []).join(' ')
  const routeNode = [...domById.values()].find((node) => attributesOf(node).includes('data-cb-route'))
  if (!routeNode) return { headings: [], landmarks: [], missingRoute: true }
  const inside = new Set()
  const collect = (node) => {
    if (!node) return
    if (node.backendNodeId) inside.add(node.backendNodeId)
    for (const child of node.children || []) collect(domById.get(child.nodeId))
  }
  collect(routeNode)
  const { nodes } = await call('Accessibility.getFullAXTree')
  const axById = new Map(nodes.map((n) => [n.nodeId, n]))
  const inRoute = (item) => {
    let cursor = item
    for (let depth = 0; depth < 200 && cursor; depth += 1) {
      if (cursor.backendDOMNodeId && inside.has(cursor.backendDOMNodeId)) return true
      cursor = cursor.parentId ? axById.get(cursor.parentId) : null
    }
    return false
  }
  const headings = []
  const landmarks = []
  for (const item of nodes) {
    if (!item.role || item.ignored || !inRoute(item)) continue
    const role = item.role.value
    const name = (item.name && item.name.value) || ''
    if (role === 'heading') {
      const levelProp = (item.properties || []).find((p) => p.name === 'level')
      headings.push({ level: levelProp ? Number(levelProp.value.value) : null, name: name.slice(0, 90) })
    } else if (['navigation', 'main', 'complementary', 'banner', 'region'].includes(role)) {
      landmarks.push({ role, name: name.slice(0, 90) })
    }
  }
  return { headings, landmarks }
}

const domSnapshot = async () => JSON.parse(await ev(`(()=>{
  const route = document.querySelector('[data-cb-route]')
  const headings = [...route.querySelectorAll('h1,h2,h3,h4,h5,h6')].map((h) => ({ level: Number(h.getAttribute('aria-level') || h.tagName.slice(1)), text: (h.innerText || '').trim().slice(0, 90) }))
  const landmarks = [...route.querySelectorAll('header,nav,main,aside,[role]')].map((el) => ({ tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), label: el.getAttribute('aria-label') }))
  const skip = route.querySelector('[data-cb-skip]')
  const main = route.querySelector('main')
  const title = route.querySelector('[data-cb-page-title]')
  return JSON.stringify({
    innerWidth,
    destination: route.getAttribute('data-cb-destination'),
    title: title ? (title.innerText || '').trim() : null,
    headings,
    landmarks,
    skip: skip ? { href: skip.getAttribute('href'), text: (skip.innerText || '').trim() } : null,
    main: main ? { label: main.getAttribute('aria-label'), id: main.id } : null,
    hasReadingColumn: !!route.querySelector('[data-cb-reading-column]')
  })
})()`))

const keyboardProbe = async () => {
  // The host chrome owns tab stops before the route. Focus the tabbable that precedes the route's
  // first control, then drive a real Tab: the skip link must be the next stop, and no Coursebook
  // control may sit between route entry and the skip link.
  const start = JSON.parse(await ev(`(()=>{
    const route = document.querySelector('[data-cb-route]')
    const skip = document.querySelector('[data-cb-skip]')
    const tabbables = [...document.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
      .filter((el) => el.getClientRects().length > 0)
    const routeStops = tabbables.filter((el) => route.contains(el))
    const firstRoute = routeStops[0] || null
    const index = tabbables.indexOf(firstRoute)
    const predecessor = index > 0 ? tabbables[index - 1] : null
    if (predecessor) predecessor.focus()
    if (!firstRoute) return JSON.stringify({ missingSkip: !skip, firstRoute: false })
    return JSON.stringify({
      firstRouteIsSkip: firstRoute === skip,
      firstRouteTag: firstRoute.tagName.toLowerCase(),
      firstRouteText: (firstRoute.innerText || '').trim().slice(0, 40),
      predecessorTag: predecessor ? predecessor.tagName.toLowerCase() : null,
      predecessorText: predecessor ? (predecessor.innerText || '').trim().slice(0, 30) : null,
      focused: document.activeElement === predecessor
    })
  })()`))
  await wait(120)
  await call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await wait(250)
  const landed = JSON.parse(await ev(`(()=>{
    const el = document.activeElement
    const skip = document.querySelector('[data-cb-skip]')
    return JSON.stringify({
      isSkip: el === skip,
      tag: el ? el.tagName.toLowerCase() : null,
      text: el ? (el.innerText || '').trim().slice(0, 40) : null
    })
  })()`))
  const visibility = JSON.parse(await ev(`(()=>{
    const skip = document.querySelector('[data-cb-skip]')
    if (!skip) return JSON.stringify({ missing: true })
    return JSON.stringify({
      width: Math.round(skip.getBoundingClientRect().width),
      height: Math.round(skip.getBoundingClientRect().height),
      clip: getComputedStyle(skip).clip,
      position: getComputedStyle(skip).position
    })
  })()`))
  let target = null
  if (landed.isSkip) {
    await call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
    await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 })
    await wait(350)
    target = JSON.parse(await ev(`(()=>{
      const el = document.activeElement
      return JSON.stringify({
        tag: el ? el.tagName.toLowerCase() : null,
        isReadingColumn: !!(el && el.hasAttribute('data-cb-reading-column')),
        isMain: !!(el && el.id === 'cb-main-content'),
        inHeader: !!(el && el.closest('header')),
        label: el ? (el.getAttribute('aria-label') || '') : null
      })
    })()`))
  }
  return { start, landed, visibility, target }
}

const check = async (name) => {
  await wait(600)
  const dom = await domSnapshot()
  const ax = await axSnapshot()
  const keys = await keyboardProbe()
  const domLevels = dom.headings.map((h) => h.level)
  const axH1 = ax.headings.filter((h) => h.level === 1).length
  const axFirst = ax.headings.length ? ax.headings[0].level : null
  const navs = ax.landmarks.filter((l) => l.role === 'navigation')
  const mains = ax.landmarks.filter((l) => l.role === 'main')
  const comps = ax.landmarks.filter((l) => l.role === 'complementary')

  const problems = []
  if (axH1 !== 1) problems.push(`AX h1 count ${axH1}`)
  if (axFirst !== 1) problems.push(`AX first heading level ${axFirst}`)
  let previous = ax.headings.length ? ax.headings[0].level : null
  for (const heading of ax.headings.slice(1)) {
    if (heading.level > previous + 1) problems.push(`AX skips ${previous}->${heading.level} at "${heading.name}"`)
    previous = heading.level
  }
  if (domLevels.join(',') !== ax.headings.map((h) => h.level).join(',')) problems.push(`DOM/AX heading order differs: ${domLevels} vs ${ax.headings.map((h) => h.level)}`)
  if (!navs.length) problems.push('no navigation landmark')
  if (navs.some((l) => !l.name)) problems.push('unnamed navigation landmark')
  if (mains.length !== 1) problems.push(`main landmark count ${mains.length}`)
  if (mains.some((l) => !l.name)) problems.push('unnamed main landmark')
  if (name === 'section' && (!comps.length || comps.some((l) => !l.name))) problems.push(`complementary landmark ${JSON.stringify(comps)}`)
  if (!dom.skip) problems.push('no skip link')
  if (dom.skip && dom.skip.href !== '#cb-main-content') problems.push(`skip href ${dom.skip.href}`)
  if (!keys.start || keys.start.firstRouteIsSkip !== true) problems.push(`the route's first focusable is not the skip link: ${JSON.stringify(keys.start)}`)
  if (!keys.landed || !keys.landed.isSkip) problems.push(`Tab after the route boundary landed on ${keys.landed && keys.landed.tag} "${keys.landed && keys.landed.text}"`)
  if (!keys.visibility || !(keys.visibility.width > 4)) problems.push(`skip link is not visible while focused: ${JSON.stringify(keys.visibility)}`)
  if (!keys.target) {
    problems.push('the skip link was never keyboard-activated')
  } else {
    if (keys.target.inHeader) problems.push('skip link moved focus into the header')
    if (name === 'section') {
      if (!keys.target.isReadingColumn) problems.push(`section skip target is ${keys.target.tag}, not the reading column`)
    } else if (!keys.target.isMain) {
      problems.push(`${name} skip target is ${keys.target.tag}`)
    }
  }
  if (problems.length) failures.push(`${name} ${theme} ${dom.innerWidth}px: ${problems.join('; ')}`)

  const png = await shot(`${name}-${theme}-${dom.innerWidth}`)
  const row = { surface: name, theme, width: dom.innerWidth, png, problems, dom, ax: { headings: ax.headings, landmarks: ax.landmarks }, keyboard: keys }
  results.push(row)
  appendFileSync(logPath, JSON.stringify(row) + '\n')
  console.log(name, theme, dom.innerWidth, problems.length ? 'FAIL' : 'PASS', problems.join('; '))
}

for (const w of widths) {
  await setWidth(w)
  await ev("location.hash='#/coursebook'"); await wait(900)
  if (await ev("!!document.querySelector('[data-cb-section-actions]')")) {
    const back = await ev(`(()=>{const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>/back to the section index/i.test((x.innerText||'').trim()));if(!b)return false;b.click();return true})()`)
    await wait(800)
    if (!back) { await nav('courses'); await wait(900) }
  }
  await nav('courses'); await wait(800)
  await check('courses-desk')
  await nav('library'); await wait(900)
  await check('library')
  await nav('studio'); await wait(900)
  await check('studio')
  await nav('courses'); await wait(900)

  // Into a section: the desk path row, else the all-courses row, else Library's row.
  let opened = await clickSel('[data-cb-path-item]')
  await wait(1500)
  if (!opened) {
    opened = await clickSel('[data-cb-all-courses-row]')
    await wait(1500)
    if (opened) { await clickSel('[data-cb-path-item]'); await wait(1500) }
  }
  if (opened && (await waitFor("!!document.querySelector('[data-cb-reading-column]')", 8000))) {
    await check('section')
  } else {
    failures.push(`section ${theme} ${w}px: could not reach a reading column (opened=${opened})`)
    console.log('section', theme, w, 'FAIL', 'could not reach a reading column')
  }
}

writeFileSync(resolve(outdir, `summary-${theme}.json`), JSON.stringify({ theme, widths, failures, results: results.map((r) => ({ surface: r.surface, width: r.width, problems: r.problems, headings: r.ax.headings, landmarks: r.ax.landmarks })) }, null, 2))
await call('Emulation.clearDeviceMetricsOverride').catch(() => {})
console.log(failures.length ? `FAILURES ${failures.length}` : 'ALL PASS')
process.exit(failures.length ? 1 : 0)
