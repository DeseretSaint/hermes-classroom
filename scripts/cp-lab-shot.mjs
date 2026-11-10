#!/usr/bin/env node
/**
 * Render the Field Atlas v3 component lab and photograph it in Chromium.
 *
 * This is the lab's own door, deliberately separate from `scripts/cp-capture.mjs`: a lab frame is
 * a **component preview**, not a Desktop capture. There is no host, no backend, no chat and no
 * `[data-cb-v3-ready]` settle marker, so it must never be filed as evidence of a live screen. What
 * it does prove is the thing a still cannot fake: the shipped primitives, the shipped stylesheet and
 * the shipped embedded assets, rendered by a real browser at the sizes and text scales they must
 * survive.
 *
 * Cells: light/dark × 100 %/200 % text, plus the two non-default postures the spec names —
 * `prefers-reduced-motion: reduce` and `forced-colors: active`.
 *
 * Usage:
 *   node scripts/cp-lab-shot.mjs --root <dir with plugin.js + node_modules> --out <dir> \
 *     [--width 1049] [--only anatomy]
 *
 * Output: `<out>/lab-<mode>-<cell>.png`, `<out>/lab-<mode>-<cell>.html` and `<out>/lab.json`
 * (the stamp index: plugin sha, cell geometry, media posture, png sha).
 */
import { createHash } from 'node:crypto'
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { spawn } from 'node:child_process'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  const value = args[index + 1]
  return value && !value.startsWith('--') ? value : true
}

const root = resolve(String(flag('root', '.')))
const out = resolve(String(flag('out', 'docs/concept-parity/lab')))
const width = Number(flag('width', 1049))
const only = flag('only', null)
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
const sha256 = (buffer) => createHash('sha256').update(buffer).digest('hex')

if (!existsSync(join(root, 'plugin.js'))) throw new Error(`no plugin.js under ${root}`)
mkdirSync(out, { recursive: true })

const requireFromRoot = createRequire(join(root, 'package.json'))
const React = requireFromRoot('react')
const { renderToStaticMarkup } = requireFromRoot('react-dom/server')
const h = React.createElement

const mod = await import(pathToFileURL(join(root, 'plugin.js')).href)
const { CbV3Scope, CbV3LabSheet, CollectibleCard, ShelfPlank, PillAction, CB3_LAB_COPY } = mod
if (!CbV3Scope || !CbV3LabSheet) throw new Error('the module exports no CbV3Scope/CbV3LabSheet')

// The anatomy cell is the side-by-side partner of R-SYS (§5.5 S6): one real card with its six
// callouts, rendered from the same primitives the product composes.
const anatomy = () =>
  h('div', { 'data-cb3-specimen': 'card-anatomy', style: { padding: '1.5rem', display: 'flex', gap: '1.5rem', alignItems: 'flex-start' } }, [
    h(ShelfPlank, { key: 'shelf', style: { overflowX: 'visible' } },
      h(CollectibleCard, {
        title: 'Japanese Lantern District',
        subject: 'Language',
        meta: '2 of 5 sections done',
        isNew: true,
        newLabel: 'New',
        action: h(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.anatomy.next, onClick: () => {} }),
        style: { width: '214px' }
      })),
    h('ol', {
      key: 'callouts',
      style: {
        margin: 0,
        paddingInlineStart: '1.1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.25rem',
        fontFamily: 'var(--cb3-font-ui)',
        fontSize: 'var(--cb3-text-caption)',
        color: 'var(--cb3-ink-soft)',
        maxWidth: '220px'
      }
    }, ['plate', 'title', 'subject', 'evidence', 'next', 'cover'].map((id) =>
      h('li', { key: id }, CB3_LAB_COPY.anatomy[id])))
  ])

const cdpConnect = async (url) => {
  const socket = new WebSocket(url)
  await new Promise((done, fail) => {
    socket.onopen = done
    socket.onerror = () => fail(new Error('CDP socket failed'))
  })
  let id = 0
  const pending = new Map()
  socket.onmessage = (event) => {
    const message = JSON.parse(String(event.data))
    const entry = pending.get(message.id)
    if (!entry) return
    pending.delete(message.id)
    if (message.error) entry.fail(new Error(message.error.message || 'CDP error'))
    else entry.done(message.result)
  }
  return {
    send: (method, params = {}) =>
      new Promise((done, fail) => {
        id += 1
        pending.set(id, { done, fail })
        socket.send(JSON.stringify({ id, method, params }))
      }),
    close: () => socket.close()
  }
}

const evaluate = async (cdp, expression) => {
  const answer = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (answer.exceptionDetails) throw new Error(answer.exceptionDetails.text || 'evaluate failed')
  return answer.result.value
}

const CELLS = [
  { id: 'light-100', mode: 'light', scale: 1, media: {} },
  { id: 'dark-100', mode: 'dark', scale: 1, media: {} },
  { id: 'light-200', mode: 'light', scale: 2, media: {} },
  { id: 'dark-200', mode: 'dark', scale: 2, media: {} },
  { id: 'light-reduced-motion', mode: 'light', scale: 1, media: { 'prefers-reduced-motion': 'reduce' } },
  { id: 'dark-forced-colors', mode: 'dark', scale: 1, media: { 'forced-colors': 'active' } }
]

const page = (markup, cell) => `<!doctype html>
<html lang="en" style="font-size:${cell.scale === 2 ? '200%' : '100%'}">
<head><meta charset="utf-8"><title>Coursebook component lab (preview)</title>
<style>
  html, body { margin: 0; padding: 0; }
  /* The route paints its own canvas; it only needs to be at least a viewport tall so a cell is a
     whole page rather than a strip. No brand colour is authored here. */
  [data-cb-route] { min-height: 100vh; }
  * { box-sizing: border-box; }
  .lab-banner {
    position: sticky; top: 0; z-index: 9;
    padding: 8px 16px;
    background: CanvasText; color: Canvas;
    font: 600 13px/1.4 system-ui, sans-serif; letter-spacing: 0.02em;
    white-space: normal;
  }
</style></head>
<body>
<div class="lab-banner" data-lab-banner>Component preview — not a live Desktop capture · ${CAPTIONS[cell.id] || cell.id}</div>
${markup}</body></html>`

const CAPTIONS = {
  'light-100': 'light · 100% text',
  'dark-100': 'dark · 100% text',
  'light-200': 'light · 200% text',
  'dark-200': 'dark · 200% text',
  'light-reduced-motion': 'light · reduced motion',
  'dark-forced-colors': 'dark · forced colors'
}

const build = (cell) => {
  const children = only === 'anatomy' ? anatomy() : h(CbV3LabSheet, { mode: cell.mode, scale: cell.scale })
  return renderToStaticMarkup(
    h(CbV3Scope, {
      mode: cell.mode,
      className: 'relative flex min-h-full flex-col',
      contentClassName: 'cb3-gutter',
      attributes: { 'data-cb-route': '/coursebook-lab', 'data-cb-scope': cell.mode, 'data-cb-lab-preview': '' },
      children
    })
  )
}

const port = 9700 + Math.floor(Math.random() * 200)
const profile = join(tmpdir(), `cb-lab-chromium-${process.pid}`)
const chromium = spawn('chromium', [
  '--headless=new',
  '--no-sandbox',
  '--disable-gpu',
  '--hide-scrollbars',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  'about:blank'
], { stdio: 'ignore' })

let targets = null
for (let attempt = 0; attempt < 80; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
    if (targets && targets.length) break
  } catch {
    targets = null
  }
  await sleep(250)
}
if (!targets || !targets.length) {
  chromium.kill()
  throw new Error('chromium did not open a CDP port')
}

const target = targets.find((entry) => entry.type === 'page')
const cdp = await cdpConnect(target.webSocketDebuggerUrl)
await cdp.send('Page.enable', {})
await cdp.send('Runtime.enable', {})

const htmlDir = join(tmpdir(), `cb-lab-html-${process.pid}`)
mkdirSync(htmlDir, { recursive: true })
const index = []
try {
  for (const cell of CELLS) {
    const file = join(htmlDir, `lab-${cell.id}.html`)
    const html = page(build(cell), cell)
    writeFileSync(file, html)
    const media = Object.entries(cell.media).map(([name, value]) => ({ name, value }))
    await cdp.send('Emulation.setEmulatedMedia', { media: '', features: media })
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width, height: 1200, deviceScaleFactor: 2, mobile: false
    })
    await cdp.send('Page.navigate', { url: pathToFileURL(file).href })
    // A lab cell is honest only once the embedded faces and every image (fox, rims, planks) have
    // settled; a frame taken earlier would show fallback type or empty objects.
    await evaluate(cdp, `(async () => {
      if (document.fonts && document.fonts.ready) await document.fonts.ready
      await Promise.all([...document.images].map((img) => {
        if (img.complete && img.naturalWidth > 0) return true
        return new Promise((done) => {
          img.addEventListener('load', () => done(true), { once: true })
          img.addEventListener('error', () => done(false), { once: true })
          setTimeout(() => done(img.complete), 1500)
        })
      }))
      return true
    })()`)
    // One more frame so the last decode and the layout settle land before the shutter.
    await sleep(200)
    const metrics = await cdp.send('Page.getLayoutMetrics')
    const content = metrics.cssContentSize || metrics.contentSize
    const shot = await cdp.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: Math.max(width, content.width), height: content.height, scale: 1 }
    })
    const png = Buffer.from(shot.data, 'base64')
    const pngPath = join(out, `lab-${cell.id}.png`)
    writeFileSync(pngPath, png)
    index.push({
      cell: cell.id,
      kind: 'component-preview',
      route: '/coursebook-lab',
      mode: cell.mode,
      text_scale: cell.scale,
      emulated_media: cell.media,
      viewport: { width, height: Math.round(content.height) },
      device_scale_factor: 2,
      html: null,
      // The page text is not shipped (CB_ASSETS inlines the fonts, so each page is ~1 MB); its hash
      // is, so a cell can be proved to have been rendered from one exact input.
      html_sha256: sha256(Buffer.from(html)),
      png: `lab-${cell.id}.png`,
      png_sha256: sha256(png),
      specimen_count: await evaluate(cdp, `document.querySelectorAll('[data-cb3-specimen]').length`)
    })
    process.stdout.write(`lab ${cell.id}: ${Math.round(content.width)}x${Math.round(content.height)} @2x\n`)
  }
} finally {
  cdp.close()
  chromium.kill()
}

const pluginSha = sha256(readFileSync(join(root, 'plugin.js')))
const stamp = {
  kind: 'component-preview',
  label: 'Component preview — rendered from the shipped primitives; not a live Desktop capture.',
  plugin_sha256: pluginSha,
  contract: 'contracts/cb.tokens.v3.json',
  reference: 'docs/concept-parity/refs/REF-SYS',
  cells: index
}
writeFileSync(join(out, 'lab.json'), `${JSON.stringify(stamp, null, 2)}\n`)
process.stdout.write(`lab.json: ${index.length} cells, plugin ${pluginSha.slice(0, 12)}\n`)
