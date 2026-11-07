// M1 narrow-width capture: real 460px window, Textbook/Guided, 100%/200% text.
// Same measurement shape as scripts/m1v-capture.mjs (data-cb-route / data-cb-lesson-view).
// node capture-narrow.mjs <cdpPort> <outDir>
import { mkdirSync, writeFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const PORT = process.argv[2] || '9361'
const OUT = process.argv[3] || 'frames'
mkdirSync(OUT, { recursive: true })

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find(t => t.type === 'page' && /Hermes/.test(t.title || '')) || targets.find(t => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => { socket.addEventListener('open', res, { once: true }); socket.addEventListener('error', rej, { once: true }) })
let id = 1
const pending = new Map()
socket.addEventListener('message', ev => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result) }
})
const send = (method, params = {}) => new Promise((resolve, reject) => { const i = id++; pending.set(i, { resolve, reject }); socket.send(JSON.stringify({ id: i, method, params })) })
const evaluate = async expression => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error((r.exceptionDetails.exception && r.exceptionDetails.exception.description) || 'eval failed')
  return r.result.value
}
const wait = ms => new Promise(r => setTimeout(r, ms))

const SNAPSHOT = `(() => {
  const route = document.querySelector('[data-cb-route]')
  const view = document.querySelector('[data-cb-lesson-view]')
  const switcher = document.querySelector('[data-cb-view-switcher]')
  const groups = [...document.querySelectorAll('[data-tree-group]')].map(g => ({
    id: g.getAttribute('data-tree-group'),
    width: Math.round(g.getBoundingClientRect().width),
    visible: g.getBoundingClientRect().width > 0
  }))
  const root = document.documentElement
  const body = document.body
  return {
    routeTextLength: route ? route.innerText.trim().length : 0,
    lessonView: view ? view.getAttribute('data-cb-lesson-view') : null,
    documentId: view ? view.getAttribute('data-cb-document') : null,
    switcher: switcher ? switcher.getAttribute('data-cb-view-switcher') : null,
    switcherPressed: [...document.querySelectorAll('[data-cb-view-switcher] button')].map(b => [b.textContent.trim(), b.getAttribute('aria-pressed')]),
    step: (document.querySelector('[data-cb-step]') || {}).textContent ? document.querySelector('[data-cb-step]').textContent.trim() : null,
    viewText: view ? view.innerText.trim().slice(0, 400) : null,
    blocks: [...document.querySelectorAll('[data-cb-block]')].map(n => ({ id: n.getAttribute('data-cb-block'), role: n.getAttribute('data-cb-role'), textLength: (n.innerText || '').trim().length })),
    checkNodes: document.querySelectorAll('[data-cb-block-check]').length,
    routeWidth: route ? Math.round(route.getBoundingClientRect().width) : null,
    viewWidth: view ? Math.round(view.getBoundingClientRect().width) : null,
    horizontalOverflow: root.scrollWidth > window.innerWidth + 1,
    scrollWidth: root.scrollWidth,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    rootFontSize: getComputedStyle(root).fontSize,
    hermesMode: body.dataset.hermesMode || root.dataset.hermesMode || null,
    bodyLuminance: (() => {
      const raw = getComputedStyle(body).backgroundColor
      const nums = (raw.match(/[\\d.]+/g) || []).map(Number)
      if (nums.length < 3) return null
      // rgb()/rgba() are 0-255; color(srgb ...) is 0-1.
      const scale = /^color\\(/.test(raw) ? 1 : 255
      const [r, g, b] = nums.slice(0, 3).map(v => v / scale)
      const f = v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
      return Math.round((0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)) * 1000) / 1000
    })(),
    groups,
    mainWidth: (() => { const m = document.querySelector('[data-tree-group="grp-main"]'); return m ? Math.round(m.getBoundingClientRect().width) : null })(),
    narrowOverlay: document.querySelector('[data-narrow-overlay]') ? document.querySelector('[data-narrow-overlay]').getAttribute('data-narrow-overlay') : null,
    paneVisible: window.__HERMES_PLUGIN_SDK__ ? window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get() : null
  }
})()`

const key = async (keyName, code, vk, modifiers = 0) => {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: keyName, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: keyName, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, modifiers })
}

const setView = async wanted => {
  let current = await evaluate(`(() => { const v = document.querySelector('[data-cb-lesson-view]'); return v && v.getAttribute('data-cb-lesson-view') })()`)
  for (let attempt = 0; attempt < 4 && current !== wanted; attempt++) {
    const res = await evaluate(`(() => {
      const btn = [...document.querySelectorAll('[data-cb-view-switcher] button')].find(b => b.textContent.trim().toLowerCase() === ${JSON.stringify(wanted)})
      if (!btn) return 'missing'
      btn.scrollIntoView({ block: 'center' })
      btn.click()
      return 'clicked'
    })()`)
    if (res === 'missing') throw new Error(`no switcher button for ${wanted}`)
    await wait(1000)
    current = await evaluate(`(() => { const v = document.querySelector('[data-cb-lesson-view]'); return v && v.getAttribute('data-cb-lesson-view') })()`)
  }
  return current
}

const setTheme = async wanted => {
  let mode = await evaluate(`(() => document.body.dataset.hermesMode || document.documentElement.dataset.hermesMode)()`)
  for (let i = 0; i < 3 && mode !== wanted; i++) {
    await key('X', 'KeyX', 88, 8) // appearance.toggleMode = Shift+X
    await wait(700)
    mode = await evaluate(`(() => document.body.dataset.hermesMode || document.documentElement.dataset.hermesMode)()`)
  }
  return mode
}

const setScale = async scale => {
  await evaluate(`(() => { document.documentElement.style.fontSize = '${16 * scale}px'; return true })()`)
  await wait(600)
}

/** The narrow overlay is hover-revealed and pins on an event reveal; a stray
 *  pointer near the right edge would otherwise cover the lesson in every
 *  frame. Close it and prove it is gone before measuring. */
const closeOverlay = async () => {
  for (let attempt = 0; attempt < 3; attempt++) {
    const open = await evaluate(`(() => Boolean(document.querySelector('[data-narrow-overlay]')))()`)
    if (!open) return true
    await evaluate(`(() => { window.dispatchEvent(new CustomEvent('hermes:pane-toggle-reveal', { detail: { id: 'coursebook:pane', mode: 'close' } })); return true })()`)
    await key('Escape', 'Escape', 27)
    await wait(500)
  }
  return !(await evaluate(`(() => Boolean(document.querySelector('[data-narrow-overlay]')))()`))
}

/** Frame the LESSON BODY, not the page chrome: the acceptance is about the
 *  lesson view being usable, so the first block sits at the top of the frame. */
const scrollLesson = async () => {
  await evaluate(`(() => {
    const view = document.querySelector('[data-cb-lesson-view]')
    if (!view) return false
    view.scrollIntoView({ block: 'start' })
    window.scrollBy(0, -8)
    return true
  })()`)
  await wait(400)
}

const shot = async name => {
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const path = join(OUT, `${name}.png`)
  writeFileSync(path, Buffer.from(r.data, 'base64'))
  return { file: `${name}.png`, bytes: statSync(path).size }
}

const frames = []
const plan = [
  ['07-textbook-dark-460px', 'textbook', 'dark', 1],
  ['08-textbook-light-460px', 'textbook', 'light', 1],
  ['09-textbook-dark-460px-200pct', 'textbook', 'dark', 2],
  ['10-guided-dark-460px', 'guided', 'dark', 1],
  ['11-guided-light-460px', 'guided', 'light', 1],
  ['12-guided-dark-460px-200pct', 'guided', 'dark', 2]
]

for (const [name, view, theme, scale] of plan) {
  const gotView = await setView(view)
  const gotTheme = await setTheme(theme)
  await setScale(scale)
  const overlayClosed = await closeOverlay()
  await scrollLesson()
  await wait(500)
  const snapshot = await evaluate(`JSON.stringify(${SNAPSHOT})`)
  const data = JSON.parse(snapshot)
  const image = await shot(name)
  frames.push({ name, requested: { view, theme, textScale: scale }, observed: { view: gotView, theme: gotTheme, overlayClosed }, ...image, ...data })
  console.log(`${name}: view=${gotView} theme=${gotTheme} route=${data.routeWidth} lesson=${data.viewWidth} overflow=${data.horizontalOverflow} overlay=${data.narrowOverlay} failedView=${gotView !== view} failedTheme=${gotTheme !== theme} overlayClosed=${overlayClosed}`)
}

// Chat pane reachable at 460: the host collapsed the rail out of the grid, so
// prove the narrow overlay still surfaces it.
await setView('textbook')
await setTheme('dark')
await setScale(1)
await send('Runtime.evaluate', {
  expression: `window.dispatchEvent(new CustomEvent('hermes:pane-toggle-reveal', { detail: { id: 'coursebook:pane', mode: 'open' } }))`,
  returnByValue: true,
  userGesture: true
})
await wait(900)
const overlay = JSON.parse(await evaluate(`JSON.stringify(${SNAPSHOT})`))
const overlayShot = await shot('14-chat-overlay-dark-460px')
frames.push({ name: '14-chat-overlay-dark-460px', requested: { overlay: 'coursebook:pane' }, ...overlayShot, ...overlay })
console.log(`14-chat-overlay: overlay=${overlay.narrowOverlay} width=${overlay.viewWidth}`)

writeFileSync(join(OUT, 'frames.json'), JSON.stringify({ capturedAt: new Date().toISOString(), viewport: { width: frames[0]?.innerWidth, height: frames[0]?.innerHeight }, frames }, null, 1))
console.log('wrote', join(OUT, 'frames.json'))
socket.close()
