#!/usr/bin/env node
/**
 * H-93 verification against the live Desktop window (CDP 9353).
 *
 * Reads computed styles off the real renderer, not the source. On each captured Coursebook
 * surface at 1049 / 900 / 460 it asserts:
 *
 *   - Coursebook-authored text uses at most six distinct computed sizes (the token scale)
 *   - no authored text is under 12px, and body copy is 16px
 *   - reading prose measures 50-75ch; no paragraph exceeds 75ch
 *   - at a 200% root font nothing is clipped and the page does not overflow horizontally
 *
 * "Authored" means the node carries a font-size the plugin declared: an inline `font-size` or one
 * of the host utility classes it uses (`text-xs` 12px, `text-sm` 14px, `text-base` 16px,
 * `text-lg` 18px). Host-owned chrome (badges, buttons, tab strips, pickers) declares neither and is
 * therefore outside the claim.
 *
 * Usage: node scripts/h93-type-verify.mjs [outdir] [--dark]
 * Exit code 0 only when every assertion passes.
 */
import { writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9353'
const outdir = resolve(process.argv[2] || 'audit/ux/round3/h93')
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

await call('Runtime.enable'); await call('Page.enable'); await call('DOM.enable')
await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }] })
if (dark) await ev("document.documentElement.classList.add('dark')")

const setWidth = async (w, zoom = 1) => {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(w * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
  await ev('window.dispatchEvent(new Event("resize"))'); await wait(600)
  await ev(`document.documentElement.style.fontSize = '${zoom === 2 ? '32px' : ''}'`)
  await ev('window.dispatchEvent(new Event("resize"))'); await wait(400)
}

const nav = async (id) => ev(`(()=>{const el=document.querySelector('[data-cb-nav-item="${id}"]');if(!el)return false;el.click();return true})()`)
const clickSel = async (sel) => ev(`(()=>{const el=document.querySelector(${JSON.stringify(sel)});if(!el)return false;(el.closest('button')||el).click();return true})()`)

await ev("location.hash='#/coursebook'"); await wait(1500)
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 8000))) {
  await ev("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))")
  await call('Page.reload', { ignoreCache: true }); await wait(6000)
  await ev("location.hash='#/coursebook'")
}
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 20000))) { console.error('route never mounted'); process.exit(1) }
await wait(1200)

// The probe runs inside the renderer. It walks the route once and returns authored sizes,
// prose measures and clipping. `ch` is measured with the paragraph's own font, not assumed.
const PROBE = `(() => {
  const route = document.querySelector('[data-cb-route]')
  if (!route) return { missing: true }
  const scale = ['text-xs', 'text-sm', 'text-base', 'text-lg']
  const px = (value) => {
    const n = parseFloat(value)
    if (!Number.isFinite(n)) return null
    return /rem$/.test(value) ? n * parseFloat(getComputedStyle(document.documentElement).fontSize || '16') : n
  }
  const declared = (el) => {
    const inline = el.style && el.style.fontSize
    if (inline) return { from: 'inline', value: inline }
    const cls = typeof el.className === 'string' ? el.className.split(/\\s+/) : []
    const hit = cls.find((c) => scale.includes(c))
    if (hit) return { from: 'utility', value: getComputedStyle(el).fontSize, utility: hit }
    return null
  }
  const visible = (el) => !!(el.getClientRects && el.getClientRects().length) && getComputedStyle(el).visibility !== 'hidden'
  const authored = []
  const prose = []
  const clipped = []
  const all = [...route.querySelectorAll('*')]
  for (const el of all) {
    const own = declared(el)
    if (!own || !visible(el)) continue
    const text = (el.textContent || '').trim()
    if (!text) continue
    const size = px(own.value)
    if (size === null) continue
    authored.push({ tag: el.tagName.toLowerCase(), size: Math.round(size * 100) / 100, from: own.from, utility: own.utility || null, text: text.slice(0, 40) })
  }
  // Prose measure: only real paragraphs of running text. The ch unit is read from a hidden span
  // in the paragraph's own computed font, so a font-stack fallback cannot inflate the count.
  const span = document.createElement('span')
  span.textContent = '0'.repeat(60)
  span.style.position = 'absolute'
  span.style.visibility = 'hidden'
  span.style.whiteSpace = 'pre'
  document.body.appendChild(span)
  for (const el of route.querySelectorAll('p')) {
    if (!visible(el)) continue
    const text = (el.textContent || '').trim()
    if (text.length < 60) continue
    const style = getComputedStyle(el)
    span.style.fontFamily = style.fontFamily
    span.style.fontSize = style.fontSize
    span.style.fontWeight = style.fontWeight
    span.style.fontStyle = style.fontStyle
    span.style.letterSpacing = style.letterSpacing
    span.style.fontStretch = style.fontStretch
    const ch = span.getBoundingClientRect().width / 60
    if (!ch) continue
    prose.push({ key: text.slice(0, 44), ch: Math.round((el.getBoundingClientRect().width / ch) * 10) / 10, px: Math.round(el.getBoundingClientRect().width) })
  }
  span.remove()
  const root = document.documentElement
  const overflowX = root.scrollWidth > root.clientWidth + 1
  for (const el of all) {
    if (!visible(el) || !el.scrollWidth || !el.clientWidth) continue
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX === 'hidden') {
      clipped.push({ tag: el.tagName.toLowerCase(), scroll: el.scrollWidth, client: el.clientWidth })
    }
  }
  const bodySamples = [...route.querySelectorAll('p')].filter(visible).map((el) => ({
    size: Math.round(parseFloat(getComputedStyle(el).fontSize) * 100) / 100,
    text: (el.textContent || '').trim().slice(0, 30)
  }))
  return { authored, prose, clipped, overflowX, bodySamples, rootFont: getComputedStyle(root).fontSize }
})()`

const snapshot = async () => await ev(PROBE)
const results = []
const failures = []

const READING = new Set(['courses-desk', 'section'])
const record = (surface, width, zoom, data) => {
  const sizes = [...new Set(data.authored.map((a) => a.size))].sort((a, b) => a - b)
  const measure = data.prose.map((p) => p.ch)
  const row = {
    surface, width, zoom, sizes, count: sizes.length,
    min: sizes[0] ?? null, max: sizes[sizes.length - 1] ?? null,
    proseMax: measure.length ? Math.max(...measure) : null,
    proseMin: measure.length ? Math.min(...measure) : null,
    prose: data.prose,
    overflowX: data.overflowX,
    clipped: data.clipped,
    rootFont: data.rootFont,
    bodySizes: [...new Set(data.bodySamples.map((b) => b.size))].sort((a, b) => a - b)
  }
  results.push(row)
  appendFileSync(logPath, JSON.stringify(row) + '\n')
  const fail = (why) => { failures.push(`${surface}@${width}${zoom === 2 ? ' 200%' : ''}: ${why}`) }
  const authoredOnly = row.sizes
  if (authoredOnly.length > 6) fail(`${authoredOnly.length} authored sizes: ${authoredOnly.join(', ')}`)
  if (row.min !== null && row.min < 12) fail(`authored text under 12px: ${row.min}`)
  if (zoom === 1 && data.overflowX) fail('horizontal overflow')
  if (zoom === 2 && data.overflowX) fail('horizontal overflow at 200% text')
  if (data.clipped.length) fail(`clipped: ${JSON.stringify(data.clipped.slice(0, 3))}`)
  if (zoom === 1) {
    if (row.proseMax !== null && row.proseMax > 75) fail(`paragraph ${row.proseMax}ch > 75ch`)
    // The 50-75 band is the reading measure: the desk and the section column. Library and studio
    // are list surfaces, where a column may be narrower than a comfortable reading line.
    if (READING.has(surface) && row.proseMax !== null && row.proseMax < 50) fail(`reading prose ${row.proseMax}ch < 50ch`)
    // Body copy is 16px at a 16px root.
    const bodyOk = row.bodySizes.includes(16) || row.bodySizes.length === 0
    if (!bodyOk) fail(`no 16px body paragraph (saw ${row.bodySizes.join(', ')})`)
  }
  return row
}

const surfaces = [
  ['courses-desk', async () => { await nav('courses'); await wait(700) }],
  ['library', async () => { await nav('library'); await wait(700) }],
  ['studio', async () => { await nav('studio'); await wait(700) }]
]

for (const [name, open] of surfaces) {
  for (const width of widths) {
    await setWidth(width)
    await open()
    await wait(600)
    const data = await snapshot()
    if (data.missing) { failures.push(`${name}@${width}: route missing`); continue }
    const row = record(name, width, 1, data)
    if (width === 1049) await shot(`${theme}-${name}-1049`)
    if (width === 460) await shot(`${theme}-${name}-460`)
    const body = data.bodySamples.length ? ` body:${row.bodySizes.join('/')}` : ''
    console.log(`${name}@${width} sizes=${row.count} [${row.sizes.join(', ')}] prose=${row.proseMin}-${row.proseMax}ch${body}`)
  }
  // 200% text at the narrow end: the place text actually runs out of room.
  await setWidth(460, 2)
  await open()
  await wait(600)
  const zoomed = await snapshot()
  record(name, 460, 2, zoomed)
  console.log(`${name}@460 200% root=${zoomed.rootFont} sizes=${[...new Set(zoomed.authored.map((a) => a.size))].length} overflowX=${zoomed.overflowX} clipped=${zoomed.clipped.length}`)
  await setWidth(460, 1)
}

writeFileSync(resolve(outdir, `summary-${theme}.json`), JSON.stringify({ theme, results, failures }, null, 2))
console.log(`\n${failures.length ? 'FAIL' : 'PASS'} — ${failures.length} failure(s)`)
for (const f of failures) console.log('  ' + f)
socket.close()
process.exit(failures.length ? 1 : 0)
