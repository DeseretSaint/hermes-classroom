#!/usr/bin/env node
/**
 * Capture the M1 Textbook/Guided evidence matrix from the isolated window.
 *
 *   CB009_CDP_PORT=9351 M1V_COURSE='Order coffee in Japanese' \
 *     node scripts/m1v-capture.mjs audit/visual/m1-guided-authoring
 *
 * The Guided half is not a hypothetical: each `data-cb-lesson-view="guided"` frame is taken after a
 * real click on the `[data-cb-view-switcher]` Guided button, and the frame records the pressed state
 * and the step text the plugin rendered. Every frame is gated on the route root having text (the
 * skill's rule: a click that never landed still looks plausible), and the JSON records the measured
 * DOM, not a description of it.
 */
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9351'
const outDir = resolve(process.argv[2] || 'audit/visual/m1-guided-authoring')
const pluginPath = process.env.M1V_PLUGIN ? resolve(process.env.M1V_PLUGIN) : null
const pluginSha = pluginPath ? createHash('sha256').update(readFileSync(pluginPath)).digest('hex') : null
const COURSE_HINT = process.env.M1V_COURSE || 'Order coffee in Japanese'
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

/**
 * Walk the real UI to the lesson section. Idempotent: an open lesson page is left alone.
 *
 * The route is entered by clicking the sidebar `Coursebook` nav item, not by assigning a hash: on an
 * isolated window a `location.hash` write made before the plugin's route contribution is mounted is
 * dropped by the router and leaves `#/` with no `[data-cb-route]` node. Clicking the nav item only
 * exists once the route is registered, so it cannot race the registration.
 */
async function ensureRoute() {
  if (await evaluate("!!document.querySelector('[data-cb-route]')")) return
  const entered = await evaluate(`(() => {
    const span = [...document.querySelectorAll('span')].find((node) => (node.textContent || '').trim() === 'Coursebook' && node.closest('button'))
    const button = span && span.closest('button')
    if (button) { button.click(); return 'nav' }
    location.hash = '#/coursebook'
    return 'hash'
  })()`)
  await sleep(2500)
  const route = await evaluate("!!document.querySelector('[data-cb-route]')")
  if (!route) throw new Error(`could not enter the Coursebook route (tried ${entered})`)
}

async function ensureLesson() {
  if (await evaluate("!!document.querySelector('[data-cb-block]')")) return
  await ensureRoute()
  const opened = await evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const hint = ${JSON.stringify(COURSE_HINT)}
    const leaf = [...route.querySelectorAll('*')].find((node) => node.children.length === 0 && (node.textContent || '').trim() === hint)
    const anchor = leaf || route
    let row = anchor
    while (row && !(row.querySelector && [...row.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Open'))) row = row.parentElement
    const target = row ? [...row.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Open') : null
    if (!target) return 'no-open'
    target.click()
    return 'course'
  })()`)
  if (opened === 'no-open') throw new Error('could not open a course row')
  await sleep(3000)
  // Course page -> section page. Two labels exist in the product; accept both so the walk is not
  // coupled to one wording.
  const section = await evaluate(`(() => {
    const button = [...document.querySelectorAll('[data-cb-route] button')].find((b) => /^Open (this )?section$/.test(b.textContent.trim()))
    if (!button) return 'no-section'
    button.click()
    return 'section'
  })()`)
  if (section !== 'section') throw new Error(`could not open a section: ${section}`)
  await sleep(3500)
}

const switcherTransitions = []

/** Press a Textbook/Guided segment for real, then confirm the DOM actually flipped. */
async function ensureView(view) {
  const before = await evaluate(`(() => {
    const root = document.querySelector('[data-cb-lesson-view]')
    return root ? root.getAttribute('data-cb-lesson-view') : null
  })()`)
  if (before === view) return before
  const pressed = await evaluate(`(() => {
    const switcher = document.querySelector('[data-cb-view-switcher]')
    if (!switcher) return 'no-switcher'
    const target = [...switcher.querySelectorAll('button')].find((b) => b.textContent.trim() === ${JSON.stringify(view === 'guided' ? 'Guided' : 'Textbook')})
    if (!target) return 'no-button'
    target.click()
    return 'clicked'
  })()`)
  if (pressed !== 'clicked') throw new Error(`could not press ${view}: ${pressed}`)
  await sleep(700)
  const after = await evaluate(`(() => {
    const root = document.querySelector('[data-cb-lesson-view]')
    return {
      view: root ? root.getAttribute('data-cb-lesson-view') : null,
      pressed: [...document.querySelectorAll('[data-cb-view-switcher] button')].map((b) => [b.textContent.trim(), b.getAttribute('aria-pressed')])
    }
  })()`)
  if (after.view !== view) throw new Error(`switcher click did not reach ${view}; DOM says ${after.view}`)
  switcherTransitions.push({ from: before, to: after.view, pressed: after.pressed, at: new Date().toISOString() })
  return after.view
}

async function snapshot() {
  return evaluate(`(() => {
    const route = document.querySelector('[data-cb-route]')
    const view = document.querySelector('[data-cb-lesson-view]')
    const switcher = document.querySelector('[data-cb-view-switcher]')
    const blocks = [...document.querySelectorAll('[data-cb-block]')].map((node) => ({
      id: node.getAttribute('data-cb-block'),
      role: node.getAttribute('data-cb-role'),
      headline: (node.querySelector('h3, h2') || {}).textContent || null,
      textLength: (node.innerText || '').trim().length,
      media: node.querySelectorAll('[data-cb-media]').length,
      sources: node.querySelectorAll('[data-cb-block-sources] span').length,
      hasCheck: !!node.querySelector('[data-cb-block-check]')
    }))
    const root = document.documentElement
    return {
      routeTextLength: route ? route.innerText.trim().length : 0,
      lessonView: view ? view.getAttribute('data-cb-lesson-view') : null,
      documentId: view ? view.getAttribute('data-cb-document') : null,
      documentState: view ? view.getAttribute('data-cb-document-state') : null,
      switcher: switcher ? switcher.getAttribute('data-cb-view-switcher') : null,
      switcherPressed: [...document.querySelectorAll('[data-cb-view-switcher] button')].map((b) => [b.textContent.trim(), b.getAttribute('aria-pressed')]),
      step: (document.querySelector('[data-cb-step]') || {}).textContent ? (document.querySelector('[data-cb-step]') || {}).textContent.trim() : null,
      viewText: view ? view.innerText.trim().slice(0, 600) : null,
      blocks,
      checkNodes: document.querySelectorAll('[data-cb-block-check]').length,
      routeWidth: route ? Math.round(route.getBoundingClientRect().width) : null,
      viewWidth: view ? Math.round(view.getBoundingClientRect().width) : null,
      paneVisible: window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get(),
      horizontalOverflow: root.scrollWidth > window.innerWidth + 1,
      scrollWidth: root.scrollWidth,
      innerWidth: window.innerWidth,
      themeClass: root.className,
      bodyBackground: getComputedStyle(document.body).backgroundColor,
      rootFontSize: getComputedStyle(root).fontSize
    }
  })()`)
}

async function capture(name, { theme, width, textScale, view }) {
  await ensureView(view)
  // A probe or a previous run may have left a context menu open; a frame that includes host chrome
  // the plugin did not draw is not evidence for the plugin.
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await sleep(150)
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
  await sleep(600)
  const state = await snapshot()
  if (state.routeTextLength === 0) throw new Error(`refusing to write ${name}: the route root is empty`)
  if (state.lessonView !== view) throw new Error(`refusing to write ${name}: wanted ${view}, DOM says ${state.lessonView}`)
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
  return { name, theme, width, textScale, view, file: `${name}.png`, bytes: Buffer.from(shot.data, 'base64').length, ...state, ...framed }
}

// Host chrome is not part of the plugin. On a narrow window the real app collapses its left
// sidebar, so the capture collapses it too: otherwise the emulated 460 px viewport keeps both host
// sidebars at full width and the plugin is judged on a sliver the product never shows.
async function setHostSidebar(hidden) {
  return evaluate(`(() => {
    const button = [...document.querySelectorAll('button[aria-label]')].find((b) => {
      const label = b.getAttribute('aria-label') || ''
      return ${hidden ? "/^Hide sidebar/" : "/^Show sidebar/"}.test(label)
    })
    if (!button) return 'no-button'
    button.click()
    return 'clicked'
  })()`)
}

// The Guided stepper resumes where the last viewer left it (this rig is often on step 5). Rewind
// with the real Back button so a guided frame set always starts at step 1 and the walk proves the
// whole pass instead of a stale tail.
async function rewindGuided() {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const position = await evaluate(`(() => {
      const step = document.querySelector('[data-cb-step]')
      const text = step ? step.textContent.trim() : ''
      return { text, index: text.startsWith('Step ') ? Number(text.split(' ')[1]) : null }
    })()`)
    if (!position.index || position.index <= 1) return position.text
    const backed = await evaluate(`(() => {
      const button = [...document.querySelectorAll('[data-cb-route] button')].find((b) => b.textContent.trim() === 'Back')
      if (!button) return 'no-back'
      button.click()
      return 'clicked'
    })()`)
    if (backed !== 'clicked') return position.text
    await sleep(600)
  }
  return null
}

await ensureLesson()
const initial = await snapshot()
// The Textbook half is the regression control: the same section must still read as the full body.
await ensureView('textbook')
const textbookFirst = await snapshot()
const frames = []
frames.push(await capture('01-textbook-dark', { theme: 'dark', width: 1280, textScale: 1, view: 'textbook' }))
frames.push(await capture('02-textbook-light', { theme: 'light', width: 1280, textScale: 1, view: 'textbook' }))
frames.push(await capture('03-textbook-dark-200pct', { theme: 'dark', width: 1280, textScale: 2, view: 'textbook' }))

// The Guided half: a real switcher click, then the same matrix. `ensureView` throws if the click did
// not land, so a frame can never be labelled guided while the DOM is still textbook.
await ensureView('guided')
await rewindGuided()
frames.push(await capture('04-guided-dark', { theme: 'dark', width: 1280, textScale: 1, view: 'guided' }))
frames.push(await capture('05-guided-light', { theme: 'light', width: 1280, textScale: 1, view: 'guided' }))
frames.push(await capture('06-guided-dark-200pct', { theme: 'dark', width: 1280, textScale: 2, view: 'guided' }))

const collapsed = await setHostSidebar(true)
await sleep(800)
frames.push(await capture('07-textbook-dark-460px', { theme: 'dark', width: 460, textScale: 1, view: 'textbook' }))
frames.push(await capture('08-textbook-light-460px', { theme: 'light', width: 460, textScale: 1, view: 'textbook' }))
frames.push(await capture('09-textbook-dark-460px-200pct', { theme: 'dark', width: 460, textScale: 2, view: 'textbook' }))
frames.push(await capture('10-guided-dark-460px', { theme: 'dark', width: 460, textScale: 1, view: 'guided' }))
frames.push(await capture('11-guided-light-460px', { theme: 'light', width: 460, textScale: 1, view: 'guided' }))
frames.push(await capture('12-guided-dark-460px-200pct', { theme: 'dark', width: 460, textScale: 2, view: 'guided' }))
const guidedFinal = await snapshot()
if (collapsed === 'clicked') await setHostSidebar(false)

// Walk every guided step through the real Continue button and record what each step renders. This is
// the "a click that never landed still looks plausible" guard applied to the stepper itself: each
// step must report a distinct index and non-empty text before the next Continue is pressed.
await send('Emulation.clearDeviceMetricsOverride')
await ensureView('guided')
await rewindGuided()
const steps = []
let checkFrame = null
for (let index = 0; index < 8; index += 1) {
  const state = await evaluate(`(() => {
    const step = document.querySelector('[data-cb-step]')
    const view = document.querySelector('[data-cb-lesson-view]')
    const next = [...document.querySelectorAll('[data-cb-route] button')].find((b) => /^(Continue|Next|Finish|Start practice|Review)$/.test(b.textContent.trim()))
    return {
      step: step ? step.textContent.trim() : null,
      heading: (document.querySelector('[data-cb-lesson-view] h2, [data-cb-lesson-view] h3') || {}).textContent || null,
      body: view ? view.innerText.trim().slice(0, 400) : null,
      nextLabel: next ? next.textContent.trim() : null,
      hasNext: !!next,
      hasCheck: !!document.querySelector('[data-cb-block-check]'),
      inputs: document.querySelectorAll('[data-cb-lesson-view] input, [data-cb-lesson-view] textarea, [data-cb-lesson-view] select').length
    }
  })()`)
  steps.push(state)
  if (state.hasCheck && !checkFrame) {
    // The practice step is where the authored check lands; capture it so the Guided set shows the
    // check in place, not just the reading steps.
    checkFrame = await capture('13-guided-practice-check-dark', { theme: 'dark', width: 1280, textScale: 1, view: 'guided' })
    frames.push(checkFrame)
  }
  if (!state.hasNext) break
  await evaluate(`(() => {
    const next = [...document.querySelectorAll('[data-cb-route] button')].find((b) => /^(Continue|Next|Finish|Start practice|Review)$/.test(b.textContent.trim()))
    if (next) next.click()
  })()`)
  await sleep(900)
  const after = await evaluate(`(() => {
    const step = document.querySelector('[data-cb-step]')
    return step ? step.textContent.trim() : null
  })()`)
  if (after === state.step && index < 7) {
    steps.push({ stuckAt: state.step })
    break
  }
}

// Keyboard probe: the lesson region must expose the reading controls in DOM order and the switcher
// must be reachable by real focus.
const keyboard = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const nodes = [...route.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])')]
  const visible = nodes.filter((node) => {
    const rect = node.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0
  })
  const switcherButton = [...document.querySelectorAll('[data-cb-view-switcher] button')].find((b) => b.textContent.trim() === 'Guided')
  if (switcherButton) switcherButton.focus()
  return {
    focusableCount: visible.length,
    firstTen: visible.slice(0, 10).map((node) => (node.textContent || node.getAttribute('aria-label') || node.tagName).trim().slice(0, 40)),
    hasSwitcher: !!document.querySelector('[data-cb-view-switcher] button'),
    focusedAfterSwitchFocus: document.activeElement ? document.activeElement.textContent.trim() : null
  }
})()`)

// Restore the window to its own theme so the rig is left usable.
await evaluate(`(() => { const root = document.documentElement; root.classList.remove('light'); root.classList.add('dark'); root.style.fontSize = '' })()`)

const evidence = {
  card: 't_0a030589 — live Guided frame',
  captured_at: new Date().toISOString(),
  plugin_sha256: pluginSha,
  window: {
    cdp_port: PORT,
    target_url: page.url,
    backend: process.env.M1V_BACKEND || 'http://127.0.0.1:44331 (isolated, checkout under test)',
    course_opened: COURSE_HINT
  },
  document: {
    lesson_view_at_entry: initial.lessonView,
    document_id: initial.documentId,
    document_state: initial.documentState,
    switcher: initial.switcher,
    textbook_blocks: textbookFirst.blocks,
    textbook_text_length: textbookFirst.viewText ? textbookFirst.viewText.length : null,
    guided_blocks: guidedFinal.blocks,
    guided_text: guidedFinal.viewText,
    guided_step: guidedFinal.step,
    guided_check_frame: checkFrame ? checkFrame.file : null,
    check_nodes: guidedFinal.checkNodes
  },
  switcher_transitions: switcherTransitions,
  frames,
  guided_steps: steps,
  keyboard,
  limits: [
    'The lesson rendered here was authored by the deterministic offline adapter (tests.test_generation.FakeLLM / FakeSearch) and served over the real plugin RPC by an isolated hermes serve. No provider was called and no spend occurred; the pre-existing demo course still reports textbook_only because re-authoring it with a real provider run requires owner approval and was not run.',
    'No media segments exist for this section, so the degraded media text-equivalent block is not exercised.',
    'The 460 px frames emulate the viewport with the host chat zone still open. The host gives the route its 22vw floor (~101 px at 460 px) and the chat zone keeps the rest, so plugin labels truncate. Each frame records routeWidth/viewWidth and horizontalOverflow=false: the plugin itself never overflows its box; the truncation is host width allocation and is the same on Textbook and Guided.',
    'Text scale is emulated by setting the root font size to 200%, which is how the plugin consumes rem tokens; it is not OS-level display scaling.',
  ]
}
writeFileSync(`${outDir}/evidence.json`, JSON.stringify(evidence, null, 2))
console.log(
  JSON.stringify(
    {
      outDir,
      frames: frames.length,
      switcher: initial.switcher,
      transitions: switcherTransitions.map((t) => `${t.from}->${t.to}`),
      guidedSteps: steps.map((s) => s.step || s.stuckAt),
      keyboard
    },
    null,
    2
  )
)
socket.close()
