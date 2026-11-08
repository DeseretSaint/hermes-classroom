#!/usr/bin/env node
/**
 * H-145 evidence capture for the Home launcher.
 *
 * Drives the isolated Electron window over CDP (never the operator's window), mounts the route,
 * and records the facts the card must prove: one h1, the wordmark, the destination order, one
 * Continue surface, no seal, the measured gutter, horizontal overflow, and keyboard focus.
 *
 * The window's own appearance setting chooses light or dark; this script records the mode the
 * plugin actually painted (`data-cb-scope`) rather than forcing one.
 *
 *   CB009_CDP_PORT=9361 node scripts/h145-capture.mjs docs/h145-shots
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9361'
const OUT = resolve(process.argv[2] || 'docs/h145-shots')

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

// The plugin is opt-in when Electron reconciles a unified package: turn it on, then mount.
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/'`)
await sleep(300)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1200)

const mounted = await evaluate(`Boolean(document.querySelector('[data-cb-route]'))`)
if (!mounted) {
  const seen = await evaluate(`document.body.innerText.slice(0, 400)`)
  throw new Error(`#/coursebook did not mount. Body: ${seen}`)
}

const facts = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const title = document.querySelector('[data-cb-page-title]')
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const h1s = [...document.querySelectorAll('h1')]
    const styles = title ? getComputedStyle(title) : null
    const routeStyle = route ? getComputedStyle(route) : null
    return {
      innerWidth: window.innerWidth,
      mode: route && route.getAttribute('data-cb-scope'),
      destination: route && route.getAttribute('data-cb-destination'),
      paper: routeStyle && routeStyle.backgroundColor,
      h1: { count: h1s.length, text: text(title), fontSize: styles && styles.fontSize, family: styles && styles.fontFamily, weight: styles && styles.fontWeight },
      wordmarks: [...document.querySelectorAll('[data-cb-wordmark]')].map((n) => ({ text: text(n), tag: n.tagName.toLowerCase(), fontSize: getComputedStyle(n).fontSize })),
      nav: [...document.querySelectorAll('[data-cb-nav-item]')].map((n) => ({ id: n.getAttribute('data-cb-nav-item'), text: text(n), current: n.getAttribute('aria-current') })),
      continueCards: document.querySelectorAll('[data-cb-continue]').length,
      seals: document.querySelectorAll('svg[data-cb-seal]').length,
      stamps: document.querySelectorAll('[data-cb-course-stamp]').length,
      nextSentences: document.querySelectorAll('[data-cb-continue-next]').length,
      gutter: routeStyle && { left: routeStyle.paddingLeft, right: routeStyle.paddingRight },
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      course: text(document.querySelector('[data-cb-desk-course]')),
      section: text(document.querySelector('[data-cb-continue-section]')),
      position: text(document.querySelector('[data-cb-continue-position]')),
      minutes: text(document.querySelector('[data-cb-continue-minutes]')),
      tally: text(document.querySelector('[data-cb-tally-caption]')),
      buttons: [...document.querySelectorAll('[data-cb-continue] button')].map((b) => {
        const s = getComputedStyle(b)
        return { label: text(b), background: s.backgroundColor, color: s.color, border: s.borderColor, height: b.getBoundingClientRect().height }
      })
    }
  })()`)

// Calibrate the emulated width: this Electron build zooms the page (~0.896), so the override is
// adjusted until window.innerWidth is the requested CSS width.
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

const shoot = async (name) => {
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(OUT, { recursive: true })
  const path = resolve(OUT, `${name}.png`)
  writeFileSync(path, Buffer.from(shot.data, 'base64'))
  return path
}

const mode = await evaluate(`document.querySelector('[data-cb-route]').getAttribute('data-cb-scope')`)
const resultsPath = resolve(OUT, 'h145-facts.json')
const results = { port: PORT, target: page.url, frames: [], facts: {} }
try {
  const previous = JSON.parse(readFileSync(resultsPath, 'utf8'))
  if (previous && previous.frames) results.frames = previous.frames
  if (previous && previous.facts) results.facts = previous.facts
} catch (error) {
  // first pass of this window
}
results[`${mode}Keyboard`] = null

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
for (const width of [1049, 900, 460]) {
  await setWidth(width)
  await sleep(220)
  const snapshot = await facts()
  const file = await shoot(`${mode}-${width}`)
  results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.width === width && !frame.text))
  results.frames.push({ mode, width, file })
  results.facts[`${mode}-${width}`] = snapshot
}

// 200% text and reduced motion, which strips movement but not the state change.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
for (const width of [1049, 460]) {
  await setWidth(width)
  await sleep(260)
  const snapshot = await facts()
  const file = await shoot(`text200-${mode}-${width}`)
  results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.width === width && frame.text === '200%'))
  results.frames.push({ mode, width, text: '200%', file })
  results.facts[`text200-${mode}-${width}`] = snapshot
}
await evaluate(`document.documentElement.style.removeProperty('font-size')`)

// Keyboard: the skip path is the first focus stop and it reveals itself; then the destination nav
// takes focus with a visible ring, in Home → Courses → Library → Parent Studio order.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
await setWidth(1049)
const keyboard = await evaluate(`(async () => {
  const route = document.querySelector('[data-cb-route]')
  const focusables = [...route.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')]
    .filter((n) => n.getAttribute('aria-hidden') !== 'true')
  const skip = focusables[0]
  skip.focus()
  const skipRect = skip.getBoundingClientRect()
  const home = route.querySelector('[data-cb-nav-item="home"]')
  home.focus()
  const homeStyle = getComputedStyle(home)
  const ring = homeStyle.outlineStyle !== 'none' && homeStyle.outlineWidth !== '0px'
  return {
    firstStop: skip.tagName.toLowerCase(),
    firstLabel: (skip.getAttribute('aria-label') || skip.textContent || '').trim(),
    skipRevealed: skipRect.width > 1 && skipRect.height > 1,
    navFocusRing: ring,
    navFocusOutline: homeStyle.outlineStyle + ' ' + homeStyle.outlineWidth + ' ' + homeStyle.outlineColor,
    navOrder: [...route.querySelectorAll('[data-cb-nav-item]')].map((n) => n.getAttribute('data-cb-nav-item'))
  }
})()`)
results[`${mode}Keyboard`] = keyboard

// Restore a clean 1049 frame for the window's owner.
await evaluate(`location.hash = '#/coursebook'`)
await setWidth(1049)
await sleep(200)

writeFileSync(resolve(OUT, 'h145-facts.json'), JSON.stringify(results, null, 2))
console.log(JSON.stringify({ mode, frames: results.frames.length, keyboard }, null, 2))
socket.close()
