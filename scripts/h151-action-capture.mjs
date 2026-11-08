#!/usr/bin/env node
/**
 * H-151 evidence capture: the Coursebook action and type system in the isolated window.
 *
 * Drives the isolated Electron window over CDP (never the operator's window) and measures the
 * facts the card must prove on every core surface: how many host-blue default buttons remain,
 * how many primaries a screen carries, the painted target size and fill of each variant, the h1
 * and PlateHead sizes, the Codicon size, clipping at 1049/900/460 and at 200% text, and a visible
 * keyboard focus ring on a Coursebook action.
 *
 *   CB009_CDP_PORT=9371 node scripts/h151-action-capture.mjs docs/h151-shots
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9371'
const OUT = resolve(process.argv[2] || 'docs/h151-shots')

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

await send('Page.enable')
await send('Runtime.enable')
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/'`)
await sleep(400)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1400)
if (!(await evaluate(`Boolean(document.querySelector('[data-cb-route]'))`))) {
  const seen = await evaluate(`document.body.innerText.slice(0, 400)`)
  throw new Error(`#/coursebook did not mount. Body: ${seen}`)
}

const facts = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const px = (value) => {
      const n = parseFloat(value)
      return Number.isFinite(n) ? n : null
    }
    const controls = [...route.querySelectorAll('button,a[href],input,select,textarea')]
    const buttons = [...route.querySelectorAll('button')].map((b) => {
      const s = getComputedStyle(b)
      const r = b.getBoundingClientRect()
      return {
        label: text(b).slice(0, 40),
        action: b.getAttribute('data-cb-action'),
        variant: b.getAttribute('data-variant'),
        disabled: Boolean(b.disabled),
        width: Math.round(r.width * 10) / 10,
        height: Math.round(r.height * 10) / 10,
        background: s.backgroundColor,
        color: s.color,
        fontSize: s.fontSize,
        minHeight: s.minHeight
      }
    })
    const title = document.querySelector('[data-cb-page-title]')
    const plateHeads = [...route.querySelectorAll('[data-cb-plate-head] h2')].map((h) => ({
      text: text(h).slice(0, 30),
      fontSize: getComputedStyle(h).fontSize
    }))
    const headings = [...route.querySelectorAll('h1,h2,h3,h4')].map((h) => ({
      tag: h.tagName.toLowerCase(),
      text: text(h).slice(0, 30),
      fontSize: getComputedStyle(h).fontSize
    }))
    const zero = controls.filter((c) => {
      const r = c.getBoundingClientRect()
      const s = getComputedStyle(c)
      return s.display !== 'none' && s.visibility !== 'hidden' && (r.width < 1 || r.height < 1)
    }).map((c) => ({ tag: c.tagName.toLowerCase(), label: text(c).slice(0, 30) }))
    const primaries = buttons.filter((b) => b.action === 'primary')
    const hostDefaults = buttons.filter((b) => b.variant === 'default' && !b.action)
    return {
      destination: route.getAttribute('data-cb-destination'),
      mode: route.getAttribute('data-cb-scope'),
      innerWidth: window.innerWidth,
      h1: { count: route.querySelectorAll('h1').length, text: text(title), fontSize: title ? getComputedStyle(title).fontSize : null },
      plateHeads,
      headings,
      buttons,
      primaryCount: primaries.length,
      primaries,
      hostDefaultCount: hostDefaults.length,
      hostDefaults,
      zeroSizedControls: zero,
      codicons: [...route.querySelectorAll('.codicon, [class*="codicon"]')].map((c) => ({
        name: c.getAttribute('data-icon') || c.className,
        fontSize: getComputedStyle(c).fontSize,
        size: c.getAttribute('data-size') || ''
      })),
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      routeOverflowX: route.scrollWidth - route.clientWidth
    }
  })()`)

const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 900, deviceScaleFactor: 1, mobile: false })
    await sleep(150)
    const inner = await evaluate('window.innerWidth')
    if (inner === target) return override
    override = Math.round((override * target) / inner)
  }
  throw new Error(`could not calibrate ${target}`)
}

const shoot = async (name) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(OUT, { recursive: true })
  const path = resolve(OUT, `${name}.png`)
  writeFileSync(path, Buffer.from(shot.data, 'base64'))
  return path
}

const go = async (destination) => {
  const button = await evaluate(`(() => {
    const item = document.querySelector('[data-cb-nav-item="${destination}"]')
    if (!item) return false
    item.click()
    return true
  })()`)
  if (!button) throw new Error(`no nav item ${destination}`)
  await sleep(1100)
}

const clickLabel = async (selector, label) => {
  const clicked = await evaluate(`(() => {
    const root = document.querySelector('${selector}')
    if (!root) return false
    const target = [...root.querySelectorAll('button')].find((b) => ((b.textContent || '').replace(/\\s+/g, ' ').trim()) === ${JSON.stringify(label)})
    if (!target) return false
    target.click()
    return true
  })()`)
  await sleep(1200)
  return clicked
}

const mode = await evaluate(`document.querySelector('[data-cb-route]').getAttribute('data-cb-scope')`)
const results = { port: PORT, target: page.url, mode, surfaces: {}, frames: [], keyboard: null, text200: null }

const record = async (name) => {
  const snapshot = await facts()
  results.surfaces[name] = snapshot
  return snapshot
}

const scanWidths = async (prefix) => {
  for (const width of [1049, 900, 460]) {
    await setWidth(width)
    await sleep(260)
    await record(`${prefix}-${width}`)
    results.frames.push(await shoot(`${prefix}-${mode}-${width}`))
  }
  await setWidth(1049)
}

// Home: the launcher and its one Continue surface.
await setWidth(1049)
await record('home-1049')
await scanWidths('home')

// Courses: the catalog.
await go('courses')
await scanWidths('courses')
// Course Detail: open the first course from the catalog.
const opened = await clickLabel('[data-cb-course-cover]', 'Open')
if (opened) await scanWidths('course-detail')

// Library: the shelf and its header action.
await go('library')
await scanWidths('library')

// Parent Studio: the landing plate.
await go('studio')
await scanWidths('studio')

// Section: back Home, then open the current section from the Continue card.
await go('home')
const sectionOpened = await clickLabel('[data-cb-continue]', 'Open the section')
if (sectionOpened) await scanWidths('section')

// 200% text at 460: nothing clips and no control collapses.
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
await setWidth(460)
await sleep(420)
results.text200 = await facts()
results.frames.push(await shoot(`text200-${mode}-460`))
await evaluate(`document.documentElement.style.removeProperty('font-size')`)
await setWidth(1049)

// Keyboard: reach the Home route, then press Tab so the browser applies `:focus-visible`.
await evaluate(`location.hash = '#/'`)
await sleep(500)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1500)
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
await sleep(250)
for (let i = 0; i < 6; i += 1) {
  const advanced = await evaluate(`(() => {
    const active = document.activeElement
    return Boolean(active && active.closest('[data-cb-route]') && active.tagName === 'BUTTON' && active.getAttribute('data-cb-action'))
  })()`)
  if (advanced) break
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await sleep(180)
}
const keyboard = await evaluate(`(async () => {
  const primary = document.activeElement
  if (!primary || !primary.closest('[data-cb-route]')) return { found: false }
  const s = getComputedStyle(primary)
  const rect = primary.getBoundingClientRect()
  return {
    found: true,
    label: (primary.textContent || '').trim().slice(0, 40),
    tag: primary.tagName.toLowerCase(),
    action: primary.getAttribute('data-cb-action'),
    ring: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || (s.boxShadow !== 'none' && /rgb|oklab/.test(s.boxShadow)),
    outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor,
    boxShadow: s.boxShadow,
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    background: s.backgroundColor,
    color: s.color,
    focusVisible: primary.matches(':focus-visible')
  }
})()`)
results.keyboard = keyboard
results.frames.push(await shoot(`keyboard-${mode}-1049`))

await evaluate(`location.hash = '#/coursebook'`)
await setWidth(1049)
writeFileSync(resolve(OUT, 'h151-facts.json'), JSON.stringify(results, null, 2))
console.log(JSON.stringify({
  mode,
  surfaces: Object.fromEntries(Object.entries(results.surfaces).map(([key, value]) => [key, {
    destination: value.destination,
    h1: value.h1,
    primaryCount: value.primaryCount,
    hostDefaultCount: value.hostDefaultCount,
    zero: value.zeroSizedControls.length,
    overflowX: value.overflowX,
    plateHead: value.plateHeads[0] || null
  }])),
  text200: results.text200 && { innerWidth: results.text200.innerWidth, overflowX: results.text200.overflowX, zero: results.text200.zeroSizedControls.length },
  keyboard,
  frames: results.frames.length
}, null, 2))
socket.close()
