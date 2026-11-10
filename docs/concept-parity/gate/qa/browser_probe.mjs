#!/usr/bin/env node
/**
 * GM-015 browser probe runner.
 *
 * Reads a plan written by `probe.py`, launches one headless Chromium, and runs every browser
 * measurement against frames built from the shipped module. It returns one JSON object per probe:
 *
 *   { id, ok: true|false|null, skipped: bool, detail: {...}, error: string|null }
 *
 * `ok: null` with `skipped: true` is how a probe says it could not be measured honestly. It is
 * never reported as a pass. The renderer here is a component preview (real module, real Chromium,
 * no host window chrome); `probe.py --live` is the separate live-Desktop path.
 */
import { spawn } from 'node:child_process'
import { readFileSync, rmSync } from 'node:fs'

const planPath = process.argv[2]
if (!planPath) {
  console.error('usage: node browser_probe.mjs <plan.json>')
  process.exit(2)
}
const plan = JSON.parse(readFileSync(planPath, 'utf8'))
const PORT = Number(plan.port || 9451)
const WIDTH = 1049
const HEIGHT = 900

const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const attachPort = plan.attachPort ? Number(plan.attachPort) : null
let chromium = null
if (!attachPort) {
  chromium = spawn(plan.chromium || 'chromium', [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--hide-scrollbars',
    '--force-color-profile=srgb',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${plan.userDataDir}`,
    'about:blank'
  ], { stdio: 'ignore' })
}

const debugPort = attachPort || PORT
let targets = null
for (let attempt = 0; attempt < 120; attempt += 1) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()
    if (targets && targets.length) break
  } catch (error) {
    targets = null
  }
  await sleep(200)
}
if (!targets || !targets.length) {
  if (chromium) chromium.kill('SIGKILL')
  console.log(JSON.stringify({ fatal: `CDP did not answer on ${debugPort}` }))
  process.exit(1)
}

const page = targets.find((entry) => entry.type === 'page' && entry.url && entry.url.startsWith('file:')) ||
  targets.find((entry) => entry.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})

let nextId = 1
const pending = new Map()
const events = []
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else resolve(message.result)
    return
  }
  if (message.method) events.push(message)
})

const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })

await send('Runtime.enable')
await send('Page.enable')
await send('Network.enable')
await send('Log.enable')

const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true
  })
  if (result.exceptionDetails) {
    const description =
      (result.exceptionDetails.exception && result.exceptionDetails.exception.description) ||
      result.exceptionDetails.text
    throw new Error(description)
  }
  return result.result ? result.result.value : undefined
}

const UTIL = `
const route = document.querySelector('[data-cb-route]') || document.body
const visible = (el) => {
  const s = getComputedStyle(el)
  const r = el.getBoundingClientRect()
  return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) !== 0 && r.width > 1 && r.height > 1
}
const nameOf = (el) => {
  if (!el) return 'BODY'
  const aria = (el.getAttribute('aria-label') || '').trim()
  if (aria) return aria
  const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 70)
  if (text) return text
  const alt = (el.getAttribute('alt') || '').trim()
  if (alt) return alt
  return el.getAttribute('title') || el.tagName
}
const focusable = (host) => Array.from(host.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[tabindex]'))
  .filter((el) => visible(el) && !el.disabled && el.getAttribute('tabindex') !== '-1' && el.getAttribute('aria-hidden') !== 'true')
`

const pressTab = async (shift = false) => {
  const modifiers = shift ? 8 : 0
  await send('Input.dispatchKeyEvent', {
    type: 'rawKeyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9, modifiers
  })
  await send('Input.dispatchKeyEvent', {
    type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9, modifiers
  })
  await sleep(60)
}

const setMedia = async (features) => {
  await send('Emulation.setEmulatedMedia', { features: features || [] })
}

const setViewport = async (width, height = HEIGHT) => {
  await send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: false
  })
}

const resetErrors = () => {
  events.length = 0
}

const pageErrors = () =>
  events
    .filter((event) =>
      event.method === 'Runtime.exceptionThrown' ||
      (event.method === 'Runtime.consoleAPICalled' && event.params.type === 'error'))
    .map((event) => {
      if (event.method === 'Runtime.exceptionThrown') {
        return event.params.exceptionDetails.exception
          ? event.params.exceptionDetails.exception.description || event.params.exceptionDetails.text
          : event.params.exceptionDetails.text
      }
      return (event.params.args || []).map((arg) => arg.value || arg.description || '').join(' ')
    })

const failedRequests = () =>
  events.filter((event) => event.method === 'Network.loadingFailed').map((event) => event.params.errorText)

const loadFrame = async (file) => {
  resetErrors()
  await send('Page.navigate', { url: `file://${file}` })
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await sleep(100)
    try {
      if (await evaluate('Boolean(window.__CB_READY__)')) break
    } catch (error) {
      // navigation may still be committing
    }
  }
  // Flush effects and any settled async state.
  await sleep(350)
}

const checkTabOrder = async (probe) => {
  const selector = probe.selector
  const expected = await evaluate(`(() => { ${UTIL}
    const host = document.querySelector(${JSON.stringify(selector)})
    if (!host) return { error: 'selector not found' }
    const list = focusable(host)
    return {
      expected: list.map(nameOf),
      total: list.length,
      html: list.map((el) => el.tagName.toLowerCase()).slice(0, 40)
    }
  })()`)
  if (expected.error) return { ok: false, detail: expected }
  if (!expected.total) return { ok: false, detail: { ...expected, reason: 'no focusable controls' } }
  await evaluate(`(() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur()
    document.body.setAttribute('tabindex', '-1'); document.body.focus(); return true })()`)
  const forward = []
  const wanted = expected.total
  for (let index = 0; index < wanted + 3; index += 1) {
    await pressTab(false)
    forward.push(await evaluate(`(() => { ${UTIL} return nameOf(document.activeElement) })()`))
    if (forward.length > wanted && forward[forward.length - 1] === forward[0]) break
  }
  await evaluate(`(() => { ${UTIL}
    const host = document.querySelector(${JSON.stringify(selector)})
    const list = focusable(host)
    if (list.length) list[list.length - 1].focus()
    return true
  })()`)
  await sleep(60)
  const backward = []
  for (let index = 0; index < Math.min(wanted, 8); index += 1) {
    backward.push(await evaluate(`(() => { ${UTIL} return nameOf(document.activeElement) })()`))
    await pressTab(true)
  }
  const measured = forward.slice(0, wanted)
  const orderOk = JSON.stringify(measured) === JSON.stringify(expected.expected)
  const reverseOk = JSON.stringify(backward) === JSON.stringify(expected.expected.slice().reverse().slice(0, backward.length))
  const unnamed = measured.filter((name) => !name || name === 'DIV' || name === 'SPAN').length
  return {
    ok: orderOk && reverseOk && unnamed === 0,
    detail: {
      selector,
      expected: expected.expected,
      forward: measured,
      backward,
      order_matches_dom: orderOk,
      shift_tab_reverses: reverseOk,
      unnamed_stops: unnamed,
      stops: expected.total
    }
  }
}

const measureText200 = async (probe) => {
  await evaluate(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
  await sleep(300)
  return evaluate(`(() => { ${UTIL}
    const selectors = ${JSON.stringify(probe.selectors)}
    const out = { selectors: {}, violations: [], rootFont: getComputedStyle(document.documentElement).fontSize }
    out.viewport = [window.innerWidth, document.documentElement.clientWidth]
    out.pageOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth
    for (const selector of selectors) {
      const nodes = Array.from(document.querySelectorAll(selector))
      out.selectors[selector] = { found: nodes.length }
      for (const node of nodes) {
        const style = getComputedStyle(node)
        const overflowX = node.scrollWidth - node.clientWidth
        const overflowY = node.scrollHeight - node.clientHeight
        // A deliberate scroller (overflow auto/scroll) is allowed to have hidden content; only a
        // container that clips with no scroll path is a defect.
        const clipsX = ['hidden', 'clip'].includes(style.overflowX)
        const clipsY = ['hidden', 'clip'].includes(style.overflowY)
        out.selectors[selector].scroll = { overflowX, overflowY, clipsX, clipsY }
        if ((clipsX && overflowX > 1) || (clipsY && overflowY > 1)) {
          out.violations.push({ selector, kind: 'container-overflow', overflowX, overflowY, text: nameOf(node).slice(0, 50) })
        }
        const right = node.getBoundingClientRect().right
        if (right > window.innerWidth + 1) {
          out.violations.push({ selector, kind: 'outside-viewport', right: Math.round(right), viewport: window.innerWidth })
        }
      }
    }
    for (const el of Array.from(route.querySelectorAll('*'))) {
      if (!visible(el)) continue
      const style = getComputedStyle(el)
      const clipsX = ['hidden', 'clip'].includes(style.overflowX)
      const clipsY = ['hidden', 'clip'].includes(style.overflowY)
      if (!clipsX && !clipsY) continue
      if (style.webkitLineClamp && style.webkitLineClamp !== 'none') continue
      const overflowX = el.scrollWidth - el.clientWidth
      const overflowY = el.scrollHeight - el.clientHeight
      if ((clipsX && overflowX > 1) || (clipsY && overflowY > 1)) {
        out.violations.push({
          selector: el.tagName.toLowerCase(),
          marker: el.getAttribute('data-cb-tutor-rail') || el.getAttribute('data-cb-home-shelf') || null,
          kind: 'clipped-text',
          overflowX, overflowY,
          text: nameOf(el).slice(0, 60)
        })
      }
    }
    out.violations = out.violations.slice(0, 25)
    return out
  })()`)
}

const checkText200 = async (probe) => {
  const widths = probe.widths || [probe.width || WIDTH]
  const cells = []
  for (const width of widths) {
    await setViewport(width, probe.height || HEIGHT)
    await sleep(300)
    const result = await measureText200(probe)
    cells.push({ width, ...result })
  }
  const bad = cells.filter((cell) => cell.pageOverflow > 1 || cell.violations.length > 0)
  return {
    ok: bad.length === 0,
    detail: { widths, cells }
  }
}

const checkForcedColors = async (probe) => {
  const result = await evaluate(`(() => { ${UTIL}
    const supports = window.matchMedia('(forced-colors: active)').matches
    const violations = []
    let textCount = 0
    for (const el of Array.from(route.querySelectorAll('*'))) {
      if (!visible(el)) continue
      const own = Array.from(el.childNodes).some((node) => node.nodeType === 3 && node.textContent.trim())
      if (!own) continue
      textCount += 1
      const style = getComputedStyle(el)
      if (style.color === 'transparent' || style.webkitTextFillColor === 'transparent') {
        violations.push({ kind: 'transparent-text', text: nameOf(el).slice(0, 50) })
      }
      if (Number(style.opacity) === 0) violations.push({ kind: 'zero-opacity', text: nameOf(el).slice(0, 50) })
      if (style.getPropertyValue('forced-color-adjust') === 'none') violations.push({ kind: 'forced-color-adjust-none', text: nameOf(el).slice(0, 50) })
    }
    return { supports, textCount, violations: violations.slice(0, 20) }
  })()`)
  // Focus visibility is a live state change; press Tab and read the first stop's indicator.
  await evaluate(`(() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur()
    document.body.setAttribute('tabindex', '-1'); document.body.focus(); return true })()`)
  await pressTab(false)
  await sleep(120)
  const focus = await evaluate(`(() => { ${UTIL}
    const el = document.activeElement
    if (!el || el === document.body) return { focused: false }
    const style = getComputedStyle(el)
    const width = parseFloat(style.outlineWidth) || 0
    const bordered = parseFloat(style.borderTopWidth) > 0 && style.borderTopStyle !== 'none'
    return {
      focused: true,
      name: nameOf(el),
      outlineStyle: style.outlineStyle,
      outlineWidth: width,
      borderWidth: style.borderTopWidth,
      visible: (style.outlineStyle !== 'none' && width > 0) || bordered
    }
  })()`)
  const focusOk = focus.focused ? focus.visible : false
  return {
    ok: result.supports && result.textCount > 0 && result.violations.length === 0 && focusOk,
    detail: { ...result, focus }
  }
}

const checkReducedMotion = async (probe) => {
  const result = await evaluate(`(() => { ${UTIL}
    const ms = (value) => Math.max(0, ...String(value || '0s').split(',').map((part) => {
      const text = part.trim()
      if (text.endsWith('ms')) return parseFloat(text)
      return parseFloat(text) * 1000
    }))
    const violations = []
    let maxTransition = 0
    let maxAnimation = 0
    const animated = []
    for (const el of Array.from(route.querySelectorAll('*'))) {
      const style = getComputedStyle(el)
      const transition = ms(style.transitionDuration)
      const animation = ms(style.animationDuration)
      maxTransition = Math.max(maxTransition, transition)
      maxAnimation = Math.max(maxAnimation, animation)
      if (style.animationName && style.animationName !== 'none') animated.push(nameOf(el).slice(0, 30) + ':' + style.animationName + '/' + style.animationDuration + '/' + style.animationIterationCount)
      if (transition > 10) violations.push({ kind: 'transition', ms: transition, text: nameOf(el).slice(0, 50) })
      if (animation > 10) violations.push({ kind: 'animation', ms: animation, text: nameOf(el).slice(0, 50) })
      if (style.animationIterationCount === 'infinite') violations.push({ kind: 'infinite', text: nameOf(el).slice(0, 50) })
    }
    return {
      mediaMatches: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      maxTransition,
      maxAnimation,
      animated: animated.slice(0, 10),
      violations: violations.slice(0, 20)
    }
  })()`)
  return {
    ok: result.mediaMatches && result.violations.length === 0,
    detail: result
  }
}

const checkImageFailure = async (probe) => {
  const before = await evaluate(`(() => { ${UTIL}
    return { images: Array.from(route.querySelectorAll('img')).length,
      text: (route.innerText || '').trim().length,
      textSample: (route.innerText || '').trim().slice(0, 200),
      media: document.querySelectorAll('[data-cb-media]').length }
  })()`)
  await evaluate(`(() => { ${UTIL} for (const img of route.querySelectorAll('img')) { img.src = 'http://127.0.0.1:9/gm015-missing.png' } return true })()`)
  await sleep(600)
  const after = await evaluate(`(() => { ${UTIL}
    const images = Array.from(route.querySelectorAll('img'))
    const violations = []
    for (const img of images) {
      const named = Boolean((img.getAttribute('alt') || '').trim()) || img.getAttribute('aria-hidden') === 'true'
      if (!named) violations.push({ kind: 'unnamed-image', src: (img.getAttribute('src') || '').slice(0, 80) })
      const rect = img.getBoundingClientRect()
      if (rect.height < 1) violations.push({ kind: 'collapsed-image', height: rect.height })
    }
    const fallback = Array.from(route.querySelectorAll('[data-cb-media], [data-cb-slot-cover], [data-cb-workshop-cover]'))
      .map((node) => (node.innerText || '').trim())
      .filter(Boolean)
    return {
      images: images.length,
      loaded: images.filter((img) => img.complete && img.naturalWidth > 0).length,
      broken: images.filter((img) => img.complete && img.naturalWidth === 0).length,
      text: (route.innerText || '').trim().length,
      fallbackText: fallback.join(' ').slice(0, 200),
      violations
    }
  })()`)
  const textSurvives = after.text > 0 && after.text >= before.text - 5
  const fallbackOk = after.images === 0 ? Boolean(after.fallbackText) : true
  return {
    ok: textSurvives && after.violations.length === 0 && fallbackOk,
    detail: { before, after, text_survives: textSurvives, fallback_ok: fallbackOk }
  }
}

const checkFontFailure = async (probe) => {
  const result = await evaluate(`(() => { ${UTIL}
    const violations = []
    let textCount = 0
    for (const el of Array.from(route.querySelectorAll('*'))) {
      if (!visible(el)) continue
      const own = Array.from(el.childNodes).some((node) => node.nodeType === 3 && node.textContent.trim())
      if (!own) continue
      textCount += 1
      const style = getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) violations.push({ kind: 'zero-size', text: nameOf(el).slice(0, 50) })
      if (style.color === 'transparent') violations.push({ kind: 'transparent-text', text: nameOf(el).slice(0, 50) })
    }
    return {
      textCount,
      fontStatus: document.fonts ? document.fonts.status : 'unsupported',
      violations: violations.slice(0, 20)
    }
  })()`)
  return { ok: result.textCount > 0 && result.violations.length === 0, detail: result }
}

const checkOffline = async (probe) => {
  const result = await evaluate(`(() => { ${UTIL}
    return {
      route: Boolean(route),
      text: (route.innerText || '').trim().length,
      nodes: route.querySelectorAll('*').length,
      errors: window.__CB_ERRORS__ || [],
      offlineNotice: Boolean(document.querySelector('[data-cb-home-offline], [data-cb-offline]'))
    }
  })()`)
  return {
    ok: Boolean(result.route) && result.text > 0 && result.nodes > 0 && result.errors.length === 0,
    detail: { ...result, failedRequests: failedRequests().slice(0, 10) }
  }
}

const checkCold = async (probe) => {
  const result = await evaluate(`(() => { ${UTIL}
    const shelf = document.querySelector('[data-cb-home-shelf]')
    const primaries = Array.from(route.querySelectorAll('[data-cb-action="primary"]')).filter(visible)
    const cards = route.querySelectorAll('[data-cb-home-card]').length
    const courseHome = route.querySelectorAll('[data-cb-course-home], [data-cb-continue]').length
    return {
      shelf: shelf ? shelf.getAttribute('data-cb-home-shelf') : null,
      invitation: Boolean(document.querySelector('[data-cb-home-invitation]')),
      question: (document.querySelector('[data-cb-home-question]') || {}).textContent || null,
      primaries: primaries.map((el) => nameOf(el)),
      cards,
      courseHome,
      text: (route.innerText || '').trim().slice(0, 300)
    }
  })()`)
  return {
    ok:
      result.shelf === 'empty' &&
      result.invitation === true &&
      result.primaries.length === 1 &&
      result.cards === 0 &&
      result.courseHome === 0,
    detail: result
  }
}

const checkNullRuntime = async (probe) => {
  await sleep(900)
  const result = await evaluate(`(() => { ${UTIL}
    const selectors = ['[data-cb-home-shelf="error"]', '[data-cb-home-invitation]', '[data-cb-backend-off]',
      '[data-cb-route-error]', '[data-cb-boot]', '[data-cb-home-shelf]']
    const found = selectors.filter((selector) => document.querySelector(selector))
    const text = (route.innerText || '').trim()
    // A named state can be copy rather than an attribute; both are honest evidence that the route
    // explained itself instead of rendering a blank or a crashed tree.
    const namedText = ['Backend off', 'needs its agent plugin', 'Try again', 'Start a new course']
      .filter((phrase) => text.includes(phrase))
    return {
      route: Boolean(document.querySelector('[data-cb-route]')),
      bootError: window.__CB_BOOT_ERROR__ || null,
      errors: (window.__CB_ERRORS__ || []).slice(0, 10),
      markers: found.concat(namedText.map((phrase) => 'text:' + phrase)),
      textLength: text.length,
      text: text.slice(0, 400),
      rawUndefined: /\bundefined\b|\bNaN\b/.test(text)
    }
  })()`)
  return {
    ok:
      result.route === true &&
      !result.bootError &&
      result.errors.length === 0 &&
      result.textLength > 0 &&
      !result.rawUndefined &&
      result.markers.length > 0,
    detail: result
  }
}

const checkModuleLoad = async (probe) => {
  const info = await evaluate(`(() => ({ module: window.__CB_MODULE__ || null,
    errors: (window.__CB_ERRORS__ || []).slice(0, 5),
    bootError: window.__CB_BOOT_ERROR__ || null }))()`)
  const mod = info.module || {}
  return {
    ok: mod.id === 'coursebook' && mod.hasRegister === true && mod.exports > 100 && info.errors.length === 0 && !info.bootError,
    detail: info
  }
}

const runProbe = async (probe) => {
  const file = plan.frames[probe.frame]
  if (!file && !probe.attach) return { id: probe.id, ok: null, skipped: true, detail: { reason: `no frame ${probe.frame}` } }
  const media = []
  if (probe.media === 'forced-colors') media.push({ name: 'forced-colors', value: 'active' })
  if (probe.media === 'reduced-motion') media.push({ name: 'prefers-reduced-motion', value: 'reduce' })
  await setMedia(media)
  await setViewport(probe.width || WIDTH, probe.height || HEIGHT)
  await send('Network.setBlockedURLs', { urls: probe.block || [] })
  await send('Network.emulateNetworkConditions', {
    offline: Boolean(probe.offline),
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1
  })
  if (!probe.attach) await loadFrame(file)
  else await sleep(400)
  if (probe.kind === 'module_load') return { id: probe.id, ...(await checkModuleLoad(probe)) }
  if (probe.kind === 'tab_order') return { id: probe.id, ...(await checkTabOrder(probe)) }
  if (probe.kind === 'text_200') return { id: probe.id, ...(await checkText200(probe)) }
  if (probe.kind === 'forced_colors') return { id: probe.id, ...(await checkForcedColors(probe)) }
  if (probe.kind === 'reduced_motion') return { id: probe.id, ...(await checkReducedMotion(probe)) }
  if (probe.kind === 'image_failure') return { id: probe.id, ...(await checkImageFailure(probe)) }
  if (probe.kind === 'font_failure') return { id: probe.id, ...(await checkFontFailure(probe)) }
  if (probe.kind === 'offline') return { id: probe.id, ...(await checkOffline(probe)) }
  if (probe.kind === 'cold') return { id: probe.id, ...(await checkCold(probe)) }
  if (probe.kind === 'null_runtime') return { id: probe.id, ...(await checkNullRuntime(probe)) }
  return { id: probe.id, ok: null, skipped: true, detail: { reason: `unknown kind ${probe.kind}` } }
}

const results = []
for (const probe of plan.probes || []) {
  try {
    const result = await runProbe(probe)
    result.errors = pageErrors().slice(0, 10)
    results.push(result)
  } catch (error) {
    results.push({ id: probe.id, ok: false, detail: { error: String(error && (error.stack || error.message || error)) } })
  }
}

console.log(JSON.stringify({ results }))
socket.close()
if (chromium) {
  try {
    chromium.kill('SIGKILL')
  } catch (error) {
    // already gone
  }
}
if (!attachPort) {
  try {
    rmSync(plan.userDataDir, { recursive: true, force: true })
  } catch (error) {
    // best effort
  }
}
process.exit(0)
