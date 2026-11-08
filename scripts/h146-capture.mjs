#!/usr/bin/env node
/**
 * H-146 evidence capture: the classroom rail and the selected classroom.
 *
 * Drives the isolated Electron window over CDP (never the operator's window). For each width it
 * records the hub before and after a classroom switch: the rail kind, the tabs and `aria-current`,
 * the active classroom in words, the duplicate-enrollment disclosure, the one Continue surface and
 * its selected course/section, parent rows absent, no card grid, horizontal overflow and the
 * selected tab's target size and focus ring. The window's persisted mode chooses light/dark; this
 * script records the mode the plugin painted (`data-cb-scope`), it does not force one.
 *
 *   CB009_CDP_PORT=9364 node scripts/h146-capture.mjs docs/h146-shots
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9364'
const OUT = resolve(process.argv[2] || 'docs/h146-shots')
const LABEL = process.env.CB_H146_TARGET || 'Japanese'

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
await sleep(350)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1500)
if (!(await evaluate(`Boolean(document.querySelector('[data-cb-route]'))`))) {
  throw new Error(`#/coursebook did not mount. Body: ${await evaluate('document.body.innerText.slice(0, 400)')}`)
}

const facts = () =>
  evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const rail = document.querySelector('[data-cb-slot-rail]')
    const tabs = [...document.querySelectorAll('[data-cb-slot-tab]')]
    const continueCard = document.querySelector('[data-cb-continue]')
    const primary = continueCard ? continueCard.querySelector('button[data-variant="default"]') : null
    const main = document.querySelector('[data-cb-desk]')
    return {
      innerWidth: window.innerWidth,
      rootFont: getComputedStyle(document.documentElement).fontSize,
      mode: route && route.getAttribute('data-cb-scope'),
      destination: route && route.getAttribute('data-cb-destination'),
      rail: rail && rail.getAttribute('data-cb-slot-rail'),
      tabs: tabs.map((node) => {
        const style = getComputedStyle(node)
        return {
          name: text(node),
          state: node.getAttribute('data-cb-slot-state'),
          current: node.getAttribute('aria-current'),
          height: Math.round(node.getBoundingClientRect().height),
          fontWeight: style.fontWeight,
          underline: style.borderBottomWidth + ' ' + style.borderBottomColor,
          focusOutline: null
        }
      }),
      currentLine: text(document.querySelector('[data-cb-slot-current]')),
      disclosure: text(document.querySelector('[data-cb-slot-disclosure]')),
      select: Boolean(document.querySelector('[data-cb-classroom-select]')),
      selectOptions: [...document.querySelectorAll('[data-cb-classroom-select] option')].map(text),
      continueCards: document.querySelectorAll('[data-cb-continue]').length,
      continueCourse: text(document.querySelector('[data-cb-desk-course]')),
      continueSection: text(document.querySelector('[data-cb-continue-section]')),
      continuePrimary: primary ? { text: text(primary), disabled: primary.disabled } : null,
      pathNodes: [...document.querySelectorAll('[data-cb-path-item]')].map((node) => ({
        state: node.getAttribute('data-cb-path-state'),
        current: node.getAttribute('data-cb-path-current')
      })),
      pathError: document.querySelector('[data-cb-path]') && document.querySelector('[data-cb-path]').getAttribute('data-cb-path'),
      parentLeak: /Parent demo|H103 live reject check/.test(main ? main.innerText : ''),
      allCourses: document.querySelectorAll('[data-cb-all-courses]').length,
      covers: document.querySelectorAll('[data-cb-course-cover],[data-cb-course-stamp]').length,
      // H-176: a course contour is identity, not a generated cover; the companion is the learner's
      // own Hermes pet drawn to a canvas, not an invented avatar image. Record both so a visual
      // gate does not read either as the old H-145 "seal/avatar" regression.
      contours: document.querySelectorAll('[data-cb-course-contour]').length,
      companions: document.querySelectorAll('[data-cb-companion]').length,
      avatars: document.querySelectorAll('img[alt=""]:not([data-cb-companion] img), .avatar').length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      h1: document.querySelectorAll('h1').length,
      emptyOrError: main ? main.getAttribute('data-cb-desk') : null,
      activeDesk: (() => {
        const node = document.activeElement
        const style = node ? getComputedStyle(node) : null
        return {
          tag: node ? node.tagName.toLowerCase() : null,
          label: node ? (node.getAttribute('aria-label') || text(node)).slice(0, 60) : null,
          outline: style ? style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor : null,
          height: node ? Math.round(node.getBoundingClientRect().height) : null
        }
      })()
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
const selectClassroom = async (label) => {
  const found = await evaluate(`(() => {
    const text = (node) => ((node && node.textContent) || '').replace(/\\s+/g, ' ').trim()
    const tab = [...document.querySelectorAll('[data-cb-slot-tab]')].find((node) => text(node).includes(${JSON.stringify(label)}))
    if (!tab) return false
    tab.click()
    return true
  })()`)
  if (!found) throw new Error(`no classroom tab matching ${label}`)
  await sleep(900)
}
const selectFirstTab = async () => {
  await evaluate(`(() => {
    const tab = document.querySelector('[data-cb-slot-tab]')
    if (tab) tab.click()
  })()`)
  await sleep(900)
}

const mode = await evaluate(`document.querySelector('[data-cb-route]').getAttribute('data-cb-scope')`)
const resultsPath = resolve(OUT, 'h146-facts.json')
const results = { port: PORT, target: page.url, frames: [], facts: {} }
try {
  const previous = JSON.parse(readFileSync(resultsPath, 'utf8'))
  if (previous && previous.frames) results.frames = previous.frames
  if (previous && previous.facts) results.facts = previous.facts
  if (previous && previous.keyboard) results.keyboard = previous.keyboard
} catch (error) {
  // first pass of this mode
}

await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
for (const width of [1049, 900, 460]) {
  await setWidth(width)
  await sleep(250)
  await selectFirstTab()
  const initial = await facts()
  const initialFile = await shoot(`${mode}-${width}-initial`)
  results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.width === width && frame.state === 'initial'))
  results.frames.push({ mode, width, state: 'initial', file: initialFile })
  results.facts[`${mode}-${width}-initial`] = initial

  await selectClassroom(LABEL)
  const switched = await facts()
  const file = await shoot(`${mode}-${width}`)
  results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.width === width && frame.state === 'switched'))
  results.frames.push({ mode, width, state: 'switched', file })
  results.facts[`${mode}-${width}`] = switched
}

// 200% text and reduced motion: the rail must wrap or fall back to the select without overflow.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
for (const width of [1049, 460]) {
  await setWidth(width)
  await sleep(300)
  const snapshot = await facts()
  const file = await shoot(`text200-${mode}-${width}`)
  results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.width === width && frame.text === '200%'))
  results.frames.push({ mode, width, text: '200%', file })
  results.facts[`text200-${mode}-${width}`] = snapshot
}
await evaluate(`document.documentElement.style.removeProperty('font-size')`)

// Keyboard: a real Tab keypress, not `element.focus()`, because the tabs paint their ring on
// `:focus-visible` and Chromium only grants that to a keyboard-driven focus move.
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
await setWidth(1049)
await sleep(250)
const focusedInfo = () =>
  evaluate(`(() => {
    const node = document.activeElement
    const text = (n) => ((n && n.textContent) || '').replace(/\\s+/g, ' ').trim()
    if (!node) return null
    const style = getComputedStyle(node)
    return {
      tag: node.tagName.toLowerCase(),
      label: (node.getAttribute('aria-label') || text(node)).slice(0, 60),
      slotTab: node.hasAttribute('data-cb-slot-tab'),
      ringState: node.getAttribute('data-cb-focus-ring'),
      outline: style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor,
      outlineOffset: style.outlineOffset,
      height: Math.round(node.getBoundingClientRect().height),
      focusVisible: (() => { try { return node.matches(':focus-visible') } catch (error) { return null } })()
    }
  })()`)
const pressTab = async () => {
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9 })
  await sleep(140)
}
await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const skip = route.querySelector('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])')
  skip.focus()
  return true
})()`)
const skipInfo = await focusedInfo()
const stops = []
let tabStop = null
for (let i = 0; i < 16; i += 1) {
  await pressTab()
  const info = await focusedInfo()
  stops.push(info)
  if (info && info.slotTab) { tabStop = info; break }
}
const tabFocusFile = await shoot(`focus-${mode}-1049`)
results.frames = results.frames.filter((frame) => !(frame.mode === mode && frame.focus === true))
results.frames.push({ mode, width: 1049, focus: true, file: tabFocusFile })
const keyboard = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const tab = route.querySelector('[data-cb-slot-tab]')
  const style = tab ? getComputedStyle(tab) : null
  return {
    firstStop: ${JSON.stringify(skipInfo && skipInfo.tag)},
    firstLabel: ${JSON.stringify(skipInfo && skipInfo.label)},
    tabLabel: tab ? ((tab.textContent || '').replace(/\\s+/g, ' ').trim()) : null,
    tabHeight: tab ? Math.round(tab.getBoundingClientRect().height) : null,
    tabOutline: style ? style.outlineStyle + ' ' + style.outlineWidth + ' ' + style.outlineColor : null,
    tabOutlineOffset: style ? style.outlineOffset : null
  }
})()`)
keyboard.stops = stops
keyboard.tabStop = tabStop
keyboard.focusRingVisible = Boolean(tabStop && tabStop.outline && !/^none/.test(tabStop.outline))
keyboard.focusFrame = tabFocusFile
results.keyboard = results.keyboard || {}
results.keyboard[mode] = keyboard

await evaluate(`location.hash = '#/coursebook'`)
await setWidth(1049)
await sleep(250)
writeFileSync(resultsPath, JSON.stringify(results, null, 2))
console.log(JSON.stringify({ mode, frames: results.frames.length, keyboard }, null, 2))
socket.close()
