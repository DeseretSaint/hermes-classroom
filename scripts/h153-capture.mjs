#!/usr/bin/env node
/**
 * H-153 evidence capture: the first-run start plate and its cold states.
 *
 * Drives the isolated Electron window over CDP (never the operator's window). The backend behind
 * this rig serves an empty profile (`library.list` -> total 0, `empty_reason: "no_courses"`), so
 * the first-run plate here is a real cold read, not a fixture.
 *
 * Records, per frame: the plate's headline/line/actions, whether any second primary or seal is on
 * screen, horizontal overflow, and the gutter. States captured:
 *   first run     1049 / 900 / 460, plus 200% text
 *   loading       the read held open by Network.emulateNetworkConditions latency
 *   error         a failed read (offline emulation, fresh mount) — never an empty profile
 *   offline       cached read + `navigator.onLine === false`: what is paused, one retry
 *
 * The window's own appearance setting chooses light or dark; run it once per mode and pass the
 * mode as the output directory suffix. The script records what the plugin painted (`data-cb-scope`).
 *
 *   CB009_CDP_PORT=9363 node scripts/h153-capture.mjs docs/h153-shots
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9363'
const OUT = resolve(process.argv[2] || 'docs/h153-shots')

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
await send('Network.enable')

// The plugin is opt-in when Electron reconciles a unified package: turn it on, then mount.
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
const mount = async () => {
  await evaluate(`location.hash = '#/'`)
  await sleep(320)
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(1100)
}

// Five-second cold task: how long from the route request to a pressable plate.
await evaluate(`location.hash = '#/'`)
await sleep(320)
const coldStart = Date.now()
await evaluate(`location.hash = '#/coursebook'`)
let coldPressable = null
for (let i = 0; i < 120; i += 1) {
  const pressable = await evaluate(`(() => {
    const button = document.querySelector('[data-cb-first-run-primary]')
    return Boolean(button && button.getBoundingClientRect().width > 1)
  })()`)
  if (pressable) {
    coldPressable = Date.now() - coldStart
    break
  }
  await sleep(50)
}
await sleep(400)

const mounted = await evaluate(`Boolean(document.querySelector('[data-cb-route]'))`)
if (!mounted) {
  const seen = await evaluate(`document.body.innerText.slice(0, 600)`)
  throw new Error(`#/coursebook did not mount. Body: ${seen}`)
}

const snapshot = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const rect = (node) => { if (!node) return null; const r = node.getBoundingClientRect(); return { width: Math.round(r.width), height: Math.round(r.height) } }
    const plate = document.querySelector('[data-cb-first-run]')
    const primary = document.querySelector('[data-cb-first-run-primary]')
    const secondary = document.querySelector('[data-cb-first-run-secondary]')
    const routeStyle = route ? getComputedStyle(route) : null
    const controls = plate ? [...plate.querySelectorAll('button')] : []
    return {
      innerWidth: window.innerWidth,
      online: navigator.onLine !== false,
      mode: route && route.getAttribute('data-cb-scope'),
      destination: route && route.getAttribute('data-cb-destination'),
      h1: { count: document.querySelectorAll('h1').length, text: text(document.querySelector('[data-cb-page-title]')) },
      wordmark: text(document.querySelector('[data-cb-wordmark]')),
      plate: plate && {
        state: plate.getAttribute('data-cb-first-run-state'),
        headline: text(plate.querySelector('[data-cb-first-run-title]')),
        line: text(plate.querySelector('[data-cb-first-run-line]')),
        words: text(plate).split(/\\s+/).filter(Boolean).length,
        visibleText: text(plate),
        primary: primary && { label: text(primary), variant: primary.getAttribute('data-variant'), rect: rect(primary), background: getComputedStyle(primary).backgroundColor },
        secondary: secondary && { label: text(secondary), variant: secondary.getAttribute('data-variant'), rect: rect(secondary) },
        controls: controls.map((node) => ({ label: text(node), variant: node.getAttribute('data-variant'), rect: rect(node) })),
        minors: plate.querySelectorAll('button[data-variant="default"]').length,
        svgs: plate.querySelectorAll('svg').length,
        seals: plate.querySelectorAll('svg[data-cb-seal]').length,
        pathRows: plate.querySelectorAll('[data-cb-first-run-step]').length,
        pathList: plate.querySelectorAll('[data-cb-first-run-path]').length,
        inventoryNote: /Not in this|backend build|sample data/.test(text(plate))
      },
      desk: route && route.querySelector('[data-cb-desk]') && route.querySelector('[data-cb-desk]').getAttribute('data-cb-desk'),
      loader: text(document.querySelector('[data-cb-desk="loading"] *')),
      error: route && route.querySelector('[data-cb-desk="error"]') ? {
        title: text(route.querySelector('[data-cb-desk="error"]')),
        buttons: [...route.querySelectorAll('[data-cb-desk="error"] button')].map(text)
      } : null,
      continueCards: document.querySelectorAll('[data-cb-continue]').length,
      courseRows: document.querySelectorAll('[data-cb-course-stamp]').length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      gutter: routeStyle && { left: routeStyle.paddingLeft, right: routeStyle.paddingRight },
      offlineBanner: [...document.querySelectorAll('[data-cb-route] *')].some((n) => /^Offline\\./.test(text(n)))
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
const resultsPath = resolve(OUT, 'h153-facts.json')
const results = { port: PORT, target: page.url, mode, frames: [], facts: {}, states: {} }
try {
  const previous = JSON.parse(readFileSync(resultsPath, 'utf8'))
  if (previous && previous.frames) results.frames = previous.frames
  if (previous && previous.facts) results.facts = previous.facts
  if (previous && previous.states) results.states = previous.states
} catch (error) {
  // first pass of this window
}

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
for (const width of [1049, 900, 460]) {
  await setWidth(width)
  await sleep(220)
  const facts = await snapshot()
  const file = await shoot(`${mode}-firstrun-${width}`)
  results.frames.push({ mode, width, state: 'firstrun', file })
  results.facts[`${mode}-firstrun-${width}`] = facts
}

// 200% text: the plate must still hold one column and one pressable action.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
for (const width of [1049, 460]) {
  await setWidth(width)
  await sleep(260)
  const facts = await snapshot()
  const file = await shoot(`text200-${mode}-firstrun-${width}`)
  results.frames.push({ mode, width, text: '200%', state: 'firstrun', file })
  results.facts[`text200-${mode}-firstrun-${width}`] = facts
}
await evaluate(`document.documentElement.style.removeProperty('font-size')`)
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })

// Keyboard: reach the plate's action with real Tab presses (so `:focus-visible` applies) and record
// the ring the host Button paints (box-shadow ring + border, not an outline).
await setWidth(1049)
await evaluate(`document.activeElement && document.activeElement.blur()`)
const pressTab = async () => {
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  }
  await sleep(90)
}
const stops = []
let primaryFocus = null
for (let i = 0; i < 14; i += 1) {
  await pressTab()
  const stop = await evaluate(`(() => {
    const node = document.activeElement
    if (!node) return null
    const style = getComputedStyle(node)
    return {
      tag: node.tagName.toLowerCase(),
      label: (node.getAttribute('aria-label') || node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
      primary: Boolean(node.closest('[data-cb-first-run]') && node.getAttribute('data-cb-first-run-primary') !== null),
      outline: style.outlineStyle + ' ' + style.outlineWidth,
      boxShadow: style.boxShadow,
      borderColor: style.borderColor
    }
  })()`)
  if (!stop) break
  stops.push(stop)
  if (stop.primary) {
    primaryFocus = stop
    break
  }
}
const keyboard = {
  stops: stops.map((stop) => stop.label),
  primary: primaryFocus,
  ringPaint: primaryFocus ? /\d/.test(primaryFocus.boxShadow) || primaryFocus.outline !== 'none 0px' : false
}
results[`${mode}Keyboard`] = keyboard
await evaluate(`document.activeElement && document.activeElement.blur()`)

// States, in the order a cold learner meets them.
import { execFileSync } from 'node:child_process'
import { readFileSync as readSync } from 'node:fs'

const RIG_HOME = process.env.COURSEBOOK_TEST_HOME
const RIG_PORT = process.env.CB013_PORT
const backend = (args) =>
  execFileSync('bash', ['scripts/cb013-live-backend.sh', ...args], {
    env: { ...process.env, COURSEBOOK_TEST_HOME: RIG_HOME, CB013_PORT: RIG_PORT },
    encoding: 'utf8'
  })
const backendPid = () => Number(readSync(resolve(process.env.COURSEBOOK_TEST_STATE || '', `serve-${RIG_PORT}.pid`), 'utf8').trim())
const goDestination = async (id) => {
  await evaluate(`(() => { const nav = document.querySelector('[data-cb-nav-item="${id}"]'); if (nav) nav.click(); return Boolean(nav) })()`)
  await sleep(700)
}

await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
await mount()
await sleep(900)

// Offline (renderer reports no connection) with a cached read: the plate keeps its headline, says
// what is paused and offers one retry.
await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 })
await sleep(1300)
results.states[`${mode}-offline`] = await snapshot()
results.frames.push({ mode, width: 1049, state: 'offline', file: await shoot(`${mode}-offline`) })
await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
await sleep(800)

// The backend goes away: remount the Home surface while it is down and record what the learner
// gets. A failed read must never be presented as an empty profile.
backend(['--stop'])
await sleep(300)
await goDestination('courses')
await goDestination('home')
await sleep(1600)
results.states[`${mode}-backenddown`] = await snapshot()
results.frames.push({ mode, width: 1049, state: 'backend-down', file: await shoot(`${mode}-error`) })

// Back up: the same surface recovers without a relaunch.
backend([])
await sleep(1500)
await goDestination('courses')
await goDestination('home')
await sleep(1600)
results.states[`${mode}-recovered`] = await snapshot()

// A read held open: freeze the backend process, remount, and the loader is the state — not a blank
// page and not an empty profile.
process.kill(backendPid(), 'SIGSTOP')
await goDestination('courses')
await goDestination('home')
await sleep(900)
results.states[`${mode}-loading`] = await snapshot()
results.frames.push({ mode, width: 1049, state: 'loading', file: await shoot(`${mode}-loading`) })
process.kill(backendPid(), 'SIGCONT')
await sleep(2000)
results.states[`${mode}-afterload`] = await snapshot()

// Restore a clean 1049 frame for the window's owner.
await mount()
await setWidth(1049)
await sleep(300)
results.coldPressableMs = coldPressable

writeFileSync(resultsPath, JSON.stringify(results, null, 2))
console.log(JSON.stringify({ mode, coldPressableMs: coldPressable, frames: results.frames.length, keyboard }, null, 2))
socket.close()
