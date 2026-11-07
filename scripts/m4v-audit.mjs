/**
 * M4-V1 painted audit: load each rendered frame in headless Chromium, emulate the variant, read
 * the painted DOM, screenshot it, and write a machine-readable audit.
 *
 *   node scripts/m4v-audit.mjs <frames.json> <outDir>
 *
 * Every number comes from Chromium (computed styles, layout, accessibility tree, real key events).
 * Nothing here is inferred from the module source.
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync, mkdtempSync, rmSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'

const framesDoc = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const outDir = resolve(process.argv[3] || 'audit/visual/m4-visual')
mkdirSync(outDir, { recursive: true })

/* Bind a port the OS says is free, rather than a fixed 9433. A fixed port means a second audit
 * (or a leftover browser from an earlier one) silently answers the CDP handshake, so the run
 * measures somebody else's browser instead of the one it spawned. */
const freePort = () => new Promise((done, fail) => {
  const server = createServer()
  server.on('error', fail)
  server.listen(0, '127.0.0.1', () => {
    const { port } = server.address()
    server.close(() => done(port))
  })
})
const PORT = Number(process.env.M4V_CDP_PORT) || await freePort()
// A short profile path: Chromium derives its process-singleton socket path from the temp root plus
// the profile dir, and a long TMPDIR (a nested scratch tree is easily 100+ chars) makes Chromium
// abort with "Socket path too long" before CDP ever opens.
const SHORT_TMP = existsSync('/tmp') ? '/tmp' : tmpdir()
const profileDir = mkdtempSync(join(SHORT_TMP, 'cb-m4v-chromium-'))

const chromium = spawn('chromium', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profileDir}`,
  'about:blank'
], {
  stdio: ['ignore', 'ignore', 'pipe'],
  detached: true,
  // Chromium derives its process-singleton socket from TMPDIR. The audit's own scratch TMPDIR is
  // often long enough that Chromium aborts with "Socket path too long", so the browser gets the
  // short profile dir as its temp root instead.
  env: { ...process.env, TMPDIR: profileDir }
})
let chromiumStderr = ''
chromium.stderr.on('data', (chunk) => { chromiumStderr = (chromiumStderr + chunk.toString()).slice(-8000) })

const sleep = (ms) => new Promise((done) => setTimeout(done, ms))
let targets = null
for (let attempt = 0; attempt < 100; attempt += 1) {
  if (chromium.exitCode !== null) break
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
    if (targets.length) break
  } catch (error) { targets = null }
  await sleep(250)
}
if (!targets || !targets.length) {
  chromium.kill('SIGKILL')
  throw new Error(`chromium CDP did not open (pid ${chromium.pid}, exit ${chromium.exitCode})\n${chromiumStderr}`)
}

const page = targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: done, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else done(message.result)
  }
})
const send = (method, params = {}) => new Promise((done, reject) => {
  const id = nextId++
  pending.set(id, { resolve: done, reject })
  socket.send(JSON.stringify({ id, method, params }))
})
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}

await send('Page.enable')
await send('Runtime.enable')
await send('Accessibility.enable')

const TOKEN_NAMES = ['paper', 'paper-raised', 'ink', 'ink-soft', 'rule', 'accent', 'accent-soft', 'field', 'ochre', 'coral']
const INTERACTIVE_ROLES = new Set([
  'button', 'link', 'checkbox', 'radio', 'textbox', 'combobox', 'slider', 'tab',
  'menuitem', 'menuitemcheckbox', 'menuitemradio', 'switch', 'spinbutton', 'searchbox'
])

const MEASURE = (tokenNames) => `(() => {
  const scope = document.querySelector('[data-cb-scope]')
  const root = scope || document.body
  const cs = (el) => getComputedStyle(el)

  // ── tokens as painted ────────────────────────────────────────────────────────────────────
  const tokens = {}
  const style = scope ? cs(scope) : null
  if (style) for (const name of ${JSON.stringify(tokenNames)}) tokens[name] = style.getPropertyValue('--cb-' + name).trim()

  // ── colour values as computed (for the token classification of authored inline paint) ────
  const inlineColourLiterals = []
  const parse = (value) => {
    const text = String(value || '')
    let match = /^rgba?\\(([^)]+)\\)$/.exec(text)
    if (match) {
      const parts = match[1].split(/[,/\\s]+/).filter(Boolean).map(Number)
      return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
    }
    match = /^color\\(srgb ([^)]+)\\)$/.exec(text)
    if (match) {
      const parts = match[1].split(/[/\\s]+/).filter(Boolean).map(Number)
      return { r: Math.round(parts[0] * 255), g: Math.round(parts[1] * 255), b: Math.round(parts[2] * 255), a: parts.length > 3 ? parts[3] : 1 }
    }
    return null
  }
  const lum = ({ r, g, b }) => {
    const lin = (c) => { const v = c / 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  }
  const ratioOf = (fg, bg) => {
    const a = lum(fg), b = lum(bg)
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
  }

  // Authored paint only: the Coursebook components style inline. A raw literal here is a defect.
  for (const el of [scope, ...root.querySelectorAll('[style]')]) {
    if (!el) continue
    for (const prop of ['color', 'backgroundColor', 'borderTopColor', 'borderLeftColor', 'fill', 'stroke']) {
      const value = el.style ? el.style[prop] : ''
      if (!value) continue
      if (/var\\(--cb-|var\\(--ui-|inherit|transparent|currentcolor/i.test(value)) continue
      if (/^(rgb|hsl|#|[a-z]+$)/i.test(value)) inlineColourLiterals.push({ tag: el.tagName, prop, value })
    }
  }

  // ── contrast on painted text ─────────────────────────────────────────────────────────────
  const backgrounds = new Map()
  const effectiveBg = (el) => {
    const chain = []
    let node = el
    while (node && node !== document.documentElement) {
      const cached = backgrounds.get(node)
      if (cached) { return [cached] }
      const parsed = parse(cs(node).backgroundColor)
      chain.push(node)
      if (parsed && parsed.a > 0.9) {
        for (const item of chain) backgrounds.set(item, parsed)
        return [parsed]
      }
      node = node.parentElement
    }
    for (const item of chain) backgrounds.set(item, { r: 255, g: 255, b: 255, a: 1 })
    return [{ r: 255, g: 255, b: 255, a: 1 }]
  }
  const textRows = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  while (walker.nextNode()) {
    const text = (walker.currentNode.nodeValue || '').trim()
    if (!text) continue
    const el = walker.currentNode.parentElement
    if (!el || seen.has(el)) continue
    seen.add(el)
    const style = cs(el)
    if (style.visibility === 'hidden' || style.display === 'none') continue
    const fg = parse(style.color)
    const bgChain = effectiveBg(el)
    const bg = bgChain[0]
    if (!fg || !bg) continue
    const size = parseFloat(style.fontSize)
    const weight = Number(style.fontWeight) || 400
    const large = size >= 24 || (size >= 18.66 && weight >= 700)
    const ratio = ratioOf(fg, bg)
    textRows.push({
      tag: el.tagName.toLowerCase(),
      text: text.slice(0, 48),
      fg: style.color,
      bg: 'rgb(' + bg.r + ', ' + bg.g + ', ' + bg.b + ')',
      size: Math.round(size * 10) / 10,
      weight,
      large,
      ratio: Math.round(ratio * 100) / 100,
      required: large ? 3 : 4.5,
      pass: ratio >= (large ? 3 : 4.5),
      // A host primitive paints its own chrome; the stub's usable UA surface is not the host's
      // real theme paint, so these rows are reported separately and never counted as product
      // contrast evidence.
      host_primitive: Boolean(el.closest && el.closest('[data-cb-host-primitive]'))
    })
  }
  const contrastFails = textRows.filter((row) => !row.pass && !row.host_primitive)
  const hostPrimitiveFails = textRows.filter((row) => !row.pass && row.host_primitive)

  // ── clipping ─────────────────────────────────────────────────────────────────────────────
  const clipped = []
  for (const el of root.querySelectorAll('*')) {
    const style = cs(el)
    const own = Array.from(el.childNodes).some((node) => node.nodeType === 3 && (node.nodeValue || '').trim())
    if (!own) continue
    const hiddenX = ['hidden', 'clip'].includes(style.overflowX)
    const hiddenY = ['hidden', 'clip'].includes(style.overflowY)
    const ellipsis = style.textOverflow === 'ellipsis'
    if ((hiddenX && el.scrollWidth > el.clientWidth + 1) || (hiddenY && el.scrollHeight > el.clientHeight + 1) || (ellipsis && el.scrollWidth > el.clientWidth + 1)) {
      clipped.push({ tag: el.tagName.toLowerCase(), text: (el.innerText || '').slice(0, 48), scrollW: el.scrollWidth, clientW: el.clientWidth, scrollH: el.scrollHeight, clientH: el.clientHeight })
    }
  }

  // ── media ────────────────────────────────────────────────────────────────────────────────
  const frames = [...root.querySelectorAll('[data-cb-media]')].map((el) => {
    const labelNode = el.querySelector('[data-cb-media-label]')
    const disclosure = el.querySelector('[data-cb-media-text-equivalent]')
    const captionNode = el.querySelector('[data-cb-media-caption]')
    return {
      artifact: el.getAttribute('data-cb-media'),
      kind: el.getAttribute('data-cb-media-kind'),
      label: labelNode ? (labelNode.innerText || '').trim() : '',
      caption: captionNode ? (captionNode.innerText || '').trim().slice(0, 120) : '',
      text_equivalent: disclosure ? (disclosure.innerText || '').replace('Text equivalent', '').trim().slice(0, 200) : '',
      has_text_equivalent: Boolean(disclosure),
      caption_is_text_equivalent: Boolean((captionNode && (captionNode.innerText || '').trim()) || disclosure),
      has_audio: Boolean(el.querySelector('audio')),
      has_image: Boolean(el.querySelector('img'))
    }
  })
  const images = [...root.querySelectorAll('img')].map((img) => ({ alt: img.getAttribute('alt') || '', has_alt: Boolean((img.getAttribute('alt') || '').trim()), complete: img.complete, naturalWidth: img.naturalWidth }))
  const audios = [...root.querySelectorAll('audio')].map((audio) => ({
    autoplay_attribute: audio.hasAttribute('autoplay'),
    autoplay_property: audio.autoplay === true,
    playing: audio.paused === false,
    controls: audio.controls === true,
    preload: audio.preload,
    aria_label: audio.getAttribute('aria-label') || '',
    src_kind: audio.src.startsWith('data:') ? 'data-url' : 'other'
  }))

  // ── motion ───────────────────────────────────────────────────────────────────────────────
  const animated = []
  for (const el of [root, ...root.querySelectorAll('*')]) {
    const style = cs(el)
    const durations = String(style.transitionDuration || '0s').split(',').map((v) => v.trim())
    const anim = String(style.animationDuration || '0s')
    const moves = durations.some((d) => parseFloat(d) > 0) || parseFloat(anim) > 0
    if (moves) animated.push({ tag: el.tagName.toLowerCase(), transition: style.transitionDuration, animation: style.animationDuration })
  }

  // ── layout ───────────────────────────────────────────────────────────────────────────────
  const docEl = document.documentElement
  const interactive = [...root.querySelectorAll('a[href], button, input, select, textarea, [tabindex], [role="button"], [role="tab"]')]
    .filter((el) => el.getAttribute('tabindex') !== '-1')
  const positiveTabindex = interactive.filter((el) => Number(el.getAttribute('tabindex')) > 0).length

  return {
    surface: scope ? scope.getAttribute('data-cb-audit-surface') : null,
    scope_mode: scope ? scope.getAttribute('data-cb-scope') : null,
    motion_attr: scope ? scope.getAttribute('data-cb-motion') : null,
    root_font_px: cs(docEl).fontSize,
    tokens,
    inline_colour_literals: inlineColourLiterals,
    text_nodes: textRows.length,
    contrast_min: (() => {
      const finite = textRows.map((row) => row.ratio).filter((value) => Number.isFinite(value))
      return finite.length ? Math.min(...finite) : null
    })(),
    contrast_min_authored: (() => {
      const finite = textRows.filter((row) => !row.host_primitive).map((row) => row.ratio).filter((value) => Number.isFinite(value))
      return finite.length ? Math.min(...finite) : null
    })(),
    contrast_failures: contrastFails.length,
    contrast_host_primitive_failures: hostPrimitiveFails.length,
    contrast_fail_sample: contrastFails.slice(0, 8),
    contrast_host_fail_sample: hostPrimitiveFails.slice(0, 4),
    contrast_rows: textRows.slice(0, 60),
    clipped_count: clipped.length,
    clipped_sample: clipped.slice(0, 8),
    horizontal_overflow: docEl.scrollWidth > docEl.clientWidth + 1,
    scroll_width: docEl.scrollWidth,
    client_width: docEl.clientWidth,
    content_height: docEl.scrollHeight,
    media_frames: frames,
    images,
    audios,
    animated_nodes: animated.length,
    animated_sample: animated.slice(0, 5),
    interactive_count: interactive.length,
    positive_tabindex: positiveTabindex,
    body_text_len: (root.innerText || '').length,
    media_fallback_text: (() => {
      const text = root.innerText || ''
      const lines = text.split(String.fromCharCode(10)).map((line) => line.trim()).filter(Boolean)
      return lines.filter((line) => /could not be previewed|No generated artifact|text equivalent|Loading media/i.test(line)).slice(0, 6)
    })()
  }
})()`

const FOCUSABLE_SELECTOR = 'a[href], button, input, select, textarea, [tabindex]'

/* ── settled keyboard walk ───────────────────────────────────────────────────────────────────
 * The walk answers one question: can every control the DOM declares be reached with Tab?
 *
 * The previous version pressed `interactive_count + 2` Tabs and counted every press that landed
 * on an element. That number was never a control count: the extra presses walked past the last
 * control, wrapped to the first and counted it a second time, so the total changed between two
 * runs of the same module. The `<audio controls>` host adds further steps — its UA shadow parts
 * each report `document.activeElement === audio`, so one host produced five or six identical
 * rows and the authored controls after it were never reached.
 *
 * This version stamps every declared control, presses Tab until each stamped control has been
 * seen once AND focus has wrapped (a repeat or the document boundary), and reports the distinct
 * authored stops. Host-widget stops (audio UA internals) are recorded separately and never
 * counted as coursebook controls.
 */
async function settle() {
  await evaluate(`(async () => {
    if (document.fonts && document.fonts.ready) { try { await document.fonts.ready } catch (error) {} }
    await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))
    return true
  })()`)
}

const DECLARED = `(() => {
  const root = document.querySelector('[data-cb-scope]') || document.body
  const els = [...root.querySelectorAll('${FOCUSABLE_SELECTOR}')]
    .filter((el) => el.getAttribute('tabindex') !== '-1' && !el.disabled)
  els.forEach((el, index) => el.setAttribute('data-cb-tab', String(index)))
  return els.map((el) => ({
    tab: Number(el.getAttribute('data-cb-tab')),
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
    name: el.getAttribute('aria-label') || ''
  }))
})()`

const ACTIVE = `(() => {
  const el = document.activeElement
  if (!el) return { kind: 'none' }
  if (el === document.body || el === document.documentElement) return { kind: 'boundary', tag: el.tagName.toLowerCase() }
  const style = getComputedStyle(el)
  const rect = el.getBoundingClientRect()
  const authored = el.getAttribute('data-cb-tab')
  return {
    kind: authored === null ? 'host-widget' : 'authored',
    tab: authored === null ? null : Number(authored),
    tag: el.tagName.toLowerCase(),
    text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 40),
    name: el.getAttribute('aria-label') || '',
    ring: (parseFloat(style.outlineWidth) > 0 && style.outlineStyle !== 'none') || (style.boxShadow && style.boxShadow !== 'none'),
    in_viewport: rect.width > 0 && rect.height > 0,
    scroll_y: Math.round(window.scrollY)
  }
})()`

async function pressTab() {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  return evaluate(ACTIVE)
}

async function keyboardWalk() {
  const declared = await evaluate(DECLARED)
  if (!declared.length) {
    return { declared: 0, count: 0, stops: [], unreachable: [], shadow_stops: [], unnamed: 0, ring_missing: 0, presses: 0 }
  }
  await evaluate('document.body.focus && document.body.focus()')
  const seen = new Map()
  const shadow = []
  const limit = declared.length * 4 + 40
  let presses = 0
  for (; presses < limit; presses += 1) {
    const info = await pressTab()
    if (info.kind === 'boundary' || info.kind === 'none') {
      if (seen.size >= declared.length) break
      continue
    }
    if (info.kind === 'host-widget') { shadow.push({ tag: info.tag, text: info.text }); continue }
    if (seen.has(info.tab)) {
      if (seen.size >= declared.length) break
      continue
    }
    seen.set(info.tab, info)
  }
  const stops = [...seen.values()].sort((first, second) => first.tab - second.tab)
  return {
    declared: declared.length,
    count: stops.length,
    stops,
    unreachable: declared.filter((item) => !seen.has(item.tab)),
    shadow_stops: shadow,
    unnamed: stops.filter((row) => !row.text && !row.name).length,
    ring_missing: stops.filter((row) => !row.ring).length,
    presses
  }
}

async function axNames() {
  const tree = await send('Accessibility.getFullAXTree')
  const unnamed = []
  const controls = []
  for (const node of tree.nodes) {
    const role = node.role && node.role.value
    if (!role || !INTERACTIVE_ROLES.has(role)) continue
    if (node.ignored) continue
    const name = (node.name && node.name.value) || ''
    const record = { role, name, backendDOMNodeId: node.backendDOMNodeId }
    controls.push(record)
    if (!String(name).trim()) unnamed.push(record)
  }
  return { controls, unnamed }
}

const evidence = {
  generated_at: new Date().toISOString(),
  reference_time: framesDoc.reference_time || null,
  kind: 'painted audit of the shipped Desktop module rendered in jsdom, painted and measured in headless Chromium',
  chromium: (await send('Browser.getVersion')).product,
  frames: []
}

for (const frame of framesDoc.frames) {
  const html = resolve(framesDoc.html_dir, `${frame.render}.html`)
  if (!existsSync(html)) throw new Error(`missing render ${html}`)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height: Math.min(frame.height, 1800), deviceScaleFactor: 1, mobile: false })
  await send('Emulation.setEmulatedMedia', {
    features: [
      { name: 'prefers-reduced-motion', value: frame.render.includes('reduced') ? 'reduce' : 'no-preference' },
      { name: 'forced-colors', value: frame.forced_colors === 'active' ? 'active' : 'none' }
    ]
  })
  await send('Page.navigate', { url: `file://${html}` })
  await sleep(450)
  await evaluate(`document.documentElement.style.fontSize = '${frame.font_px}px'`)
  await sleep(150)
  await settle()
  const measured = await evaluate(MEASURE(TOKEN_NAMES))
  const ax = frame.forced_colors === 'none' && frame.width === 1280 ? await axNames() : null
  let keyboard = null
  if (frame.forced_colors === 'none' && frame.width === 1280 && measured.interactive_count > 0) {
    keyboard = await keyboardWalk()
  }
  const height = Math.min(Math.max(measured.content_height, 400), 6000)
  await send('Emulation.setDeviceMetricsOverride', { width: frame.width, height, deviceScaleFactor: 1, mobile: false })
  await sleep(120)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, `${frame.id}.png`), Buffer.from(shot.data, 'base64'))
  const record = {
    id: frame.id,
    render: frame.render,
    width: frame.width,
    font_px: frame.font_px,
    forced_colors: frame.forced_colors === 'active',
    ...measured,
    ax_controls: ax ? ax.controls.length : null,
    ax_unnamed: ax ? ax.unnamed.length : null,
    ax_unnamed_sample: ax ? ax.unnamed.slice(0, 6) : null,
    keyboard_declared: keyboard ? keyboard.declared : null,
    keyboard_order: keyboard ? keyboard.stops : null,
    keyboard_count: keyboard ? keyboard.count : null,
    keyboard_presses: keyboard ? keyboard.presses : null,
    keyboard_shadow_stops: keyboard ? keyboard.shadow_stops.length : null,
    keyboard_unreachable: keyboard ? keyboard.unreachable : null,
    keyboard_unnamed: keyboard ? keyboard.unnamed : null,
    keyboard_ring_missing: keyboard ? keyboard.ring_missing : null,
    keyboard_visible_ring: keyboard ? keyboard.stops.filter((row) => row.ring).length : null
  }
  evidence.frames.push(record)
  console.log(`${frame.id}: contrast_min=${record.contrast_min} fails=${record.contrast_failures} clipped=${record.clipped_count} overflow=${record.horizontal_overflow} unnamed=${record.ax_unnamed} media=${record.media_frames.length} audio=${record.audios.length} img=${record.images.length}`)
}

writeFileSync(resolve(outDir, 'audit.json'), `${JSON.stringify(evidence, null, 2)}\n`)
try { await send('Browser.close') } catch (error) { /* the browser may already be gone */ }
await sleep(400)
socket.close()
try { if (chromium.exitCode === null) process.kill(-chromium.pid, 'SIGKILL') } catch (error) { /* already exited */ }
await sleep(200)
try { rmSync(profileDir, { recursive: true, force: true }) } catch (error) { /* best effort */ }
console.log(`wrote ${evidence.frames.length} frames to ${outDir}`)
