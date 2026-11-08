#!/usr/bin/env node
/**
 * H-150b — focus evidence for the Library shelf.
 *
 * The H-150 capture harness measured `outline: none` because it focused a row that was hidden at
 * 460 px while a preview selection was open. This probe records the element that actually holds
 * focus, its computed outline, and a cropped frame of the row, at 1049 and 460 px, before and
 * after the whole-row action is driven from a real CDP key event.
 *
 *   CB009_CDP_PORT=9362 node scripts/h150-focus-probe.mjs audit/ux/h150-shots
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9362'
const OUT = resolve(process.argv[2] || 'audit/ux/h150-shots')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: res, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const id = nextId++
    pending.set(id, { resolve: res, reject: rej })
    socket.send(JSON.stringify({ id, method, params }))
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        rej(new Error(`timeout: ${method}`))
      }
    }, 20000)
  })
const sleep = (ms) => new Promise((res) => setTimeout(res, ms))
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const key = async (keyName) => {
  const params = keyName === 'Enter'
    ? { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 }
    : { key: ' ', code: 'Space', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32, text: ' ' }
  // One physical press is one `keydown` and one `keyup`. Sending `rawKeyDown` *and* `keyDown` made
  // the page receive two presses: at a compact shelf the first opened the preview and moved focus
  // to `All packs`, and the second then activated that control and closed it again — a measurement
  // artifact (H-150c).
  await send('Input.dispatchKeyEvent', { type: 'keyDown', ...params })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', ...params })
  await sleep(500)
}

const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 900, deviceScaleFactor: 1, mobile: false })
    await sleep(140)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return override
    override = Math.round((override * target) / inner)
  }
  throw new Error(`could not calibrate ${target}`)
}

const shoot = async (name, clip) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, ...(clip ? { clip } : {}) })
  mkdirSync(OUT, { recursive: true })
  const path = resolve(OUT, `${name}.png`)
  writeFileSync(path, Buffer.from(shot.data, 'base64'))
  return path
}

const describeFocus = () => evaluate(`(() => {
  const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim().slice(0, 80)
  const el = document.activeElement
  const overlay = document.querySelector('[data-cb-pack-row] button[aria-pressed]')
  const style = el && el !== document.body ? getComputedStyle(el) : null
  const rect = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null
  const row = document.querySelector('[data-cb-pack-row]')
  const route = document.querySelector('[data-cb-route]')
  const routeRect = route ? route.getBoundingClientRect() : null
  return {
    tag: el ? el.tagName.toLowerCase() : null,
    label: el ? el.getAttribute('aria-label') : null,
    text: text(el),
    isBody: el === document.body,
    isRowOverlay: Boolean(overlay && el === overlay),
    insidePreview: Boolean(el && el.closest('[data-cb-pack-preview]')),
    visible: Boolean(el && el.offsetParent !== null),
    outline: style ? style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor : null,
    outlineOffset: style ? style.outlineOffset : null,
    focusVisible: el && el.matches ? el.matches(':focus-visible') : null,
    rect: rect && rect.width ? { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) } : null,
    rowRect: row ? (() => { const r = row.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } })() : null,
    pageScroll: { x: window.scrollX, y: window.scrollY },
    routeRect: routeRect ? { x: Math.round(routeRect.x), y: Math.round(routeRect.y), w: Math.round(routeRect.width), h: Math.round(routeRect.height) } : null,
    documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    rowVisible: Boolean(row && row.offsetParent !== null),
    previewPanel: Boolean(document.querySelector('[data-cb-pack-preview]')),
    selectedCount: document.querySelectorAll('[data-cb-pack-selected="true"]').length,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    rootFontSize: getComputedStyle(document.documentElement).fontSize,
    bodyFontSize: getComputedStyle(document.body).fontSize
  }
})()`)

const focusRow = async (index) => {
  // The ring is the H-146a `:focus-visible` identity, so the sample has to be a keyboard stop: a
  // script focus straight after the harness's own click on `All packs` inherits that pointer
  // modality and the engine answers `:focus-visible` false. One Tab establishes the keyboard
  // modality; the `focusin` is announced because this Electron build moves `activeElement` without
  // firing it (H-146b), so React's `onFocus` would otherwise never run.
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await sleep(120)
  return evaluate(`(() => {
  const row = document.querySelectorAll('[data-cb-pack-row]')[${index}]
  const overlay = row && row.querySelector('button[aria-pressed]')
  if (!overlay) return false
  overlay.focus()
  overlay.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
  overlay.scrollIntoView({ block: 'center' })
  return true
})()`)
}

const clearSelection = async () => {
  await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find((n) => (n.textContent || '').trim() === 'All packs'); if (b) b.click() })()`)
  await sleep(500)
}

await send('Page.enable')
await send('Runtime.enable')
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1200)
await evaluate(`(() => { const b = document.querySelector('[data-cb-nav-item="library"]'); if (b) b.click() })()`)
await sleep(1200)
await clearSelection()

const results = {
  port: PORT,
  target: page.url,
  deployedPlugin: await evaluate(`(() => { const scripts = [...document.querySelectorAll('script')].map((n) => n.src); return { title: document.title, scripts } })()`),
  light: {},
  wide: {},
  narrow: {}
}

// 1. Wide: the visible keyboard focus ring, measured and cropped.
await setWidth(1049)
await sleep(300)
results.light.rootFontSize = (await describeFocus()).rootFontSize
await focusRow(0)
await sleep(350)
const wideFocus = await describeFocus()
results.wide.focusRing = wideFocus
results.wide.focusRingFrame = await shoot('focus-ring-light-1049', wideFocus.rowRect ? {
  x: Math.max(0, wideFocus.rowRect.x + wideFocus.pageScroll.x - 6),
  y: Math.max(0, wideFocus.rowRect.y + wideFocus.pageScroll.y - 6),
  width: wideFocus.rowRect.w + 12,
  height: wideFocus.rowRect.h + 12,
  scale: 3
} : undefined)
results.wide.focusRingFull = await shoot('focus-ring-light-1049-full')
await evaluate(`document.activeElement.blur()`)
await sleep(250)
results.wide.blurred = await describeFocus()
results.wide.blurredFull = await shoot('focus-ring-light-1049-blurred')

// 2. Wide: real Enter opens the preview. Record where focus went.
await focusRow(0)
await sleep(150)
results.wide.beforeEnter = await describeFocus()
await key('Enter')
results.wide.afterKeyboardEnter = await describeFocus()
results.wide.afterKeyboardEnterFrame = await shoot('overlay-open-enter-1049')

// 3. Wide: clear, then real Space on another row.
await clearSelection()
await focusRow(1)
await sleep(150)
results.wide.beforeSpace = await describeFocus()
await key(' ')
results.wide.afterKeyboardSpace = await describeFocus()
results.wide.afterKeyboardSpaceFrame = await shoot('overlay-open-space-1049')

// 4. Narrow 460: clear selection, focus visible row, ring frame, then Space.
await clearSelection()
await setWidth(460)
await sleep(350)
await focusRow(0)
await sleep(350)
const narrowFocus = await describeFocus()
results.narrow.focusRing = narrowFocus
results.narrow.focusRingFrame = await shoot('focus-ring-light-460', narrowFocus.rowRect ? {
  x: Math.max(0, narrowFocus.rowRect.x + narrowFocus.pageScroll.x - 6),
  y: Math.max(0, narrowFocus.rowRect.y + narrowFocus.pageScroll.y - 6),
  width: narrowFocus.rowRect.w + 12,
  height: narrowFocus.rowRect.h + 12,
  scale: 3
} : undefined)
results.narrow.focusRingFull = await shoot('focus-ring-light-460-full')
await evaluate(`document.activeElement.blur()`)
await sleep(250)
results.narrow.blurred = await describeFocus()
results.narrow.blurredFull = await shoot('focus-ring-light-460-blurred')

await focusRow(0)
await sleep(150)
results.narrow.beforeSpace = await describeFocus()
await key(' ')
results.narrow.afterKeyboardSpace = await describeFocus()
results.narrow.afterKeyboardSpaceFrame = await shoot('overlay-open-space-460')

// 5. 200% text at 460, with the root font asserted and measured at capture time.
await clearSelection()
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
await setWidth(460)
await sleep(350)
await evaluate(`(() => { const row = document.querySelector('[data-cb-pack-row]'); if (row) row.scrollIntoView({ block: 'start' }) })()`)
await sleep(300)
results.text200 = await describeFocus()
results.text200.frame = await shoot('text200-measured-light-460')
results.text200.full = await shoot('text200-measured-light-460-full')
await evaluate(`document.documentElement.style.removeProperty('font-size')`)
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })

mkdirSync(OUT, { recursive: true })
writeFileSync(resolve(OUT, 'h150-focus-facts.json'), JSON.stringify(results, null, 2))
console.log(JSON.stringify({
  wideRing: results.wide.focusRing && results.wide.focusRing.outline,
  wideAfterEnter: results.wide.afterKeyboardEnter && { tag: results.wide.afterKeyboardEnter.tag, label: results.wide.afterKeyboardEnter.label, isBody: results.wide.afterKeyboardEnter.isBody, insidePreview: results.wide.afterKeyboardEnter.insidePreview, preview: results.wide.afterKeyboardEnter.previewPanel },
  wideAfterSpace: results.wide.afterKeyboardSpace && { tag: results.wide.afterKeyboardSpace.tag, label: results.wide.afterKeyboardSpace.label, isBody: results.wide.afterKeyboardSpace.isBody, preview: results.wide.afterKeyboardSpace.previewPanel },
  narrowRing: results.narrow.focusRing && results.narrow.focusRing.outline,
  narrowAfterSpace: results.narrow.afterKeyboardSpace && { tag: results.narrow.afterKeyboardSpace.tag, label: results.narrow.afterKeyboardSpace.label, isBody: results.narrow.afterKeyboardSpace.isBody, visible: results.narrow.afterKeyboardSpace.visible, insidePreview: results.narrow.afterKeyboardSpace.insidePreview, preview: results.narrow.afterKeyboardSpace.previewPanel },
  text200: { rootFontSize: results.text200.rootFontSize, bodyFontSize: results.text200.bodyFontSize, innerWidth: results.text200.innerWidth }
}, null, 2))
socket.close()
