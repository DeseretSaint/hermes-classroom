#!/usr/bin/env node
/**
 * Capture the M1 Textbook/Guided evidence matrix from the isolated window.
 *
 *   CB009_CDP_PORT=9351 node scripts/m1v-capture.mjs audit/visual/m1-textbook-guided
 *
 * Every frame is gated on the route root having text (the skill's rule: a click that never landed
 * still looks plausible), and the JSON records the measured DOM, not a description of it.
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9351'
const outDir = resolve(process.argv[2] || 'audit/visual/m1-textbook-guided')
const pluginPath = process.env.M1V_PLUGIN ? resolve(process.env.M1V_PLUGIN) : null
const pluginSha = pluginPath ? createHash('sha256').update(readFileSync(pluginPath)).digest('hex') : null
mkdirSync(outDir, { recursive: true })

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

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
const send = (method, params = {}) =>
  new Promise((done, reject) => {
    const id = nextId++
    pending.set(id, { resolve: done, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

await send('Page.enable')
await send('Runtime.enable')

/** Walk the real UI to the lesson section. Idempotent: an open lesson page is left alone. */
async function ensureLesson() {
  if (await evaluate("!!document.querySelector('[data-cb-block]')")) return
  await evaluate("location.hash = '#/coursebook'")
  await sleep(2500)
  const opened = await evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    if (!route) return 'no-route'
    const open = [...route.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Open' && b.closest('li, article, div'))
    const target = [...route.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Open')
    if (!target) return 'no-open'
    target.click()
    return 'course'
  })()`)
  if (opened === 'no-route' || opened === 'no-open') throw new Error(`could not open a course: ${opened}`)
  await sleep(2500)
  await evaluate(`(() => {
    const book = [...document.querySelectorAll('[data-cb-route] button')].find((b) => b.textContent.trim() === 'Textbook')
    if (book) book.click()
  })()`)
  await sleep(2000)
  const section = await evaluate(`(() => {
    const button = [...document.querySelectorAll('[data-cb-route] button')].find((b) => b.textContent.trim() === 'Open section')
    if (!button) return 'no-section'
    button.click()
    return 'section'
  })()`)
  if (section !== 'section') throw new Error(`could not open a section: ${section}`)
  await sleep(3000)
}

async function snapshot() {
  return evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const view = document.querySelector('[data-cb-lesson-view]')
    const switcher = document.querySelector('[data-cb-view-switcher]')
    const blocks = [...document.querySelectorAll('[data-cb-block]')].map((node) => ({
      id: node.getAttribute('data-cb-block'),
      role: node.getAttribute('data-cb-role'),
      headline: (node.querySelector('h3') || {}).textContent || null,
      media: node.querySelectorAll('[data-cb-media]').length,
      sources: node.querySelectorAll('[data-cb-block-sources] span').length,
      hasCheck: !!node.querySelector('[data-cb-block-check]')
    }))
    const root = document.documentElement
    return {
      routeTextLength: route ? route.innerText.trim().length : 0,
      lessonView: view ? view.getAttribute('data-cb-lesson-view') : null,
      documentId: view ? view.getAttribute('data-cb-document') : null,
      switcher: switcher ? switcher.getAttribute('data-cb-view-switcher') : null,
      step: (document.querySelector('[data-cb-step]') || {}).textContent || null,
      blocks,
      checkNodes: document.querySelectorAll('[data-cb-block-check]').length,
      horizontalOverflow: root.scrollWidth > window.innerWidth + 1,
      scrollWidth: root.scrollWidth,
      innerWidth: window.innerWidth,
      themeClass: root.className,
      bodyBackground: getComputedStyle(document.body).backgroundColor,
      rootFontSize: getComputedStyle(root).fontSize
    }
  })()`)
}

async function capture(name, { theme, width, textScale }) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
  await evaluate(`(() => {
    const root = document.documentElement
    root.classList.remove('dark', 'light')
    root.classList.add(${JSON.stringify(theme)})
    root.style.fontSize = ${JSON.stringify(textScale === 2 ? '200%' : '')}
    window.scrollTo(0, 0)
    const view = document.querySelector('[data-cb-lesson-view]')
    if (view) view.scrollIntoView({ block: 'start' })
  })()`)
  await sleep(500)
  const state = await snapshot()
  if (state.routeTextLength === 0) throw new Error(`refusing to write ${name}: the route root is empty`)
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const file = `${outDir}/${name}.png`
  writeFileSync(file, Buffer.from(shot.data, 'base64'))
  const framed = await evaluate(`(() => {
    const media = [...document.querySelectorAll('[data-cb-media]')]
    return {
      mediaNodes: media.length,
      mediaStates: media.map((node) => node.getAttribute('data-cb-media')),
      viewportWidth: window.innerWidth,
      focused: document.activeElement ? document.activeElement.tagName : null
    }
  })()`)
  return { name, theme, width, textScale, file: `${name}.png`, bytes: Buffer.from(shot.data, 'base64').length, ...state, ...framed }
}

await ensureLesson()
const initial = await snapshot()
const frames = []
frames.push(await capture('01-textbook-dark', { theme: 'dark', width: 1280, textScale: 1 }))
frames.push(await capture('02-textbook-light', { theme: 'light', width: 1280, textScale: 1 }))
frames.push(await capture('03-textbook-dark-200pct', { theme: 'dark', width: 1280, textScale: 2 }))
frames.push(await capture('04-textbook-dark-460px', { theme: 'dark', width: 460, textScale: 1 }))
frames.push(await capture('05-textbook-light-460px', { theme: 'light', width: 460, textScale: 1 }))
frames.push(await capture('06-textbook-dark-460px-200pct', { theme: 'dark', width: 460, textScale: 2 }))

// Keyboard probe: the lesson region must expose the reading controls in DOM order and no element
// in it may trap focus. Records the tab stops the plugin itself rendered.
const keyboard = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const nodes = [...route.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])')]
  const visible = nodes.filter((node) => {
    const rect = node.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0
  })
  return {
    focusableCount: visible.length,
    firstTen: visible.slice(0, 10).map((node) => (node.textContent || node.getAttribute('aria-label') || node.tagName).trim().slice(0, 40)),
    hasSwitcher: !!document.querySelector('[data-cb-view-switcher] button')
  }
})()`)

// Restore the window to its own theme so the rig is left usable.
await evaluate(`(() => { const root = document.documentElement; root.classList.remove('light'); root.classList.add('dark'); root.style.fontSize = '' })()`)
await send('Emulation.clearDeviceMetricsOverride')

const evidence = {
  card: 'M1-U1 Textbook and Guided renderers',
  captured_at: new Date().toISOString(),
  plugin_sha256: pluginSha,
  window: { cdp_port: PORT, target_url: page.url, backend: 'http://127.0.0.1:44301 (isolated, this checkout)' },
  document: {
    lesson_view: initial.lessonView,
    document_id: initial.documentId,
    switcher: initial.switcher,
    blocks: initial.blocks,
    check_nodes: initial.checkNodes
  },
  keyboard,
  frames,
  limits: [
    'The live backend reports state=textbook_only for every lesson.page it serves today: the lesson authoring prompt writes segments only, never authored `short`/`blocks`. views.guided is therefore false and the window honestly renders the Textbook-only state.',
    'The Guided renderer and the Textbook/Guided switcher are exercised against contract v8 documents in tests/test_desktop_lesson_views.py (real React render of this plugin module), not against a live backend page.'
  ]
}
writeFileSync(`${outDir}/evidence.json`, JSON.stringify(evidence, null, 2))
console.log(JSON.stringify({ outDir, frames: frames.length, switcher: initial.switcher, blocks: initial.blocks.length, keyboard }, null, 2))
socket.close()
