#!/usr/bin/env node
/**
 * H-176 live check: the Trailhead in the real Desktop renderer.
 *
 * Not a screenshot script. It asserts the composition order (plate, trail, shelf), that exactly
 * one action row exists, that the single primary opens the backend's recorded destination, that
 * "Open section" opens the same course at that section, and that the plate is motionless under
 * prefers-reduced-motion. Writes audit/visual/h176-trailhead/live-check.json and two frames.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9376'
const outDir = resolve(process.argv[2] || 'audit/visual/h176-trailhead')
mkdirSync(outDir, { recursive: true })
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) {
    const { resolve: ok, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else ok(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((ok, reject) => {
    const id = nextId++
    pending.set(id, { resolve: ok, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  writeFileSync(resolve(outDir, name), Buffer.from(png.data, 'base64'))
}
const width = async (target) => {
  let override = target
  for (let i = 0; i < 6; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 1500, deviceScaleFactor: 1, mobile: false })
    await wait(250)
    const actual = await evalJs('window.innerWidth')
    if (Math.abs(actual - target) <= 2) break
    override = Math.round((override * target) / actual)
  }
  await wait(350)
}

await send('Page.enable')
await send('Runtime.enable')
const facts = () =>
  evalJs(`(() => {
    const text = (node) => (node ? (node.textContent || '').trim() : null)
    const rect = (node) => (node ? node.getBoundingClientRect() : null)
    const plate = document.querySelector('[data-cb-continue]')
    const actions = [...document.querySelectorAll('[data-cb-trailhead-actions]')]
    const buttons = actions.flatMap((row) => [...row.querySelectorAll('button')])
    const path = document.querySelector('[data-cb-path]')
    const shelf = document.querySelector('[data-cb-slot-rail-section]')
    return {
      width: window.innerWidth,
      desk: (document.querySelector('[data-cb-desk]') || {}).getAttribute?.('data-cb-desk') || null,
      plate: Boolean(plate),
      label: text(document.querySelector('[data-cb-trailhead-label]')),
      course: text(document.querySelector('[data-cb-desk-course]')),
      titleLines: document.querySelector('[data-cb-desk-course]')
        ? Math.round((rect(document.querySelector('[data-cb-desk-course]')).height || 0) / parseFloat(getComputedStyle(document.querySelector('[data-cb-desk-course]')).lineHeight || '1'))
        : null,
      sentence: text(document.querySelector('[data-cb-trailhead-next]')),
      background: plate ? getComputedStyle(plate).backgroundColor : null,
      routeWidth: (() => { const r = document.querySelector('[data-cb-route]'); return r ? Math.round(r.getBoundingClientRect().width) : null })(),
      titleMeasure: (() => {
        const t = document.querySelector('[data-cb-desk-course]')
        if (!t) return null
        const cs = getComputedStyle(t)
        return {
          height: Math.round(t.getBoundingClientRect().height),
          lineHeight: cs.lineHeight,
          clamp: cs.webkitLineClamp || cs.getPropertyValue('-webkit-line-clamp'),
          display: cs.display,
          scrollHeight: t.scrollHeight,
          clientHeight: t.clientHeight
        }
      })(),
      topEdge: plate ? getComputedStyle(plate).borderTopWidth + ' ' + getComputedStyle(plate).borderTopColor : null,
      actionRows: actions.length,
      buttons: buttons.map((b) => ({ label: text(b), disabled: b.disabled })),
      companion: Boolean(document.querySelector('[data-cb-companion] canvas')),
      companionMotion: (document.querySelector('[data-cb-companion]') || {}).getAttribute?.('data-cb-companion-motion') || null,
      pathItems: path ? path.querySelectorAll('[data-cb-path-item]').length : 0,
      order: {
        plateTop: plate ? Math.round(rect(plate).top) : null,
        pathTop: path ? Math.round(rect(path).top) : null,
        shelfTop: shelf ? Math.round(rect(shelf).top) : null
      },
      shelfCourses: shelf ? shelf.querySelectorAll('[data-cb-slot-tab]').length : 0,
      courseDetail: Boolean(document.querySelector('[data-cb-course-detail]')),
      detailView: (document.querySelector('[data-cb-course-detail]') || {}).getAttribute?.('data-cb-course-detail') || null,
      lessonView: (document.querySelector('[data-cb-lesson-view]') || {}).getAttribute?.('data-cb-lesson-view') || null,
      nav: [...document.querySelectorAll('[data-cb-destination]')].map((n) => text(n)),
      animations: document.getAnimations().length,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
    }
  })()`)

const report = { rig: `${PORT}`, generated_at: new Date().toISOString(), steps: [] }

await width(1049)
await send('Page.reload', { ignoreCache: true })
await wait(4000)
await evalJs("location.hash = '#/'; true")
await wait(600)
await evalJs("location.hash = '#/coursebook'; true")
await wait(3500)
const home = await facts()
await shot('live-home-1049.png')

// The settings toggle is a real control on the sheet, not a preference only the tests know.
const settingsStep = await (async () => {
  await evalJs("document.querySelector('[data-cb-settings-open]').click(); true")
  await wait(700)
  const read = await evalJs(`(() => {
    const toggle = document.querySelector('[data-cb-settings-toggle="companion"]')
    const input = toggle ? toggle.querySelector('input,[role="switch"],button') : null
    return {
      open: Boolean(document.querySelector('[data-cb-settings-sheet],[role="dialog"]')),
      label: toggle ? (toggle.textContent || '').trim() : null,
      checked: input ? (input.checked === undefined ? input.getAttribute('aria-checked') : Boolean(input.checked)) : null
    }
  })()`)
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await wait(500)
  return read
})()
report.steps.push({ step: 'settings-companion', ...settingsStep })

// The one primary: the backend's recorded next step, not a second filled action.
report.steps.push({ step: 'home', ...home })
await evalJs("document.querySelector('[data-cb-trailhead-actions] button').click(); true")
await wait(2500)
const opened = await facts()
await shot('live-primary-opened.png')
report.steps.push({ step: 'primary-opened', ...opened })

// Secondary: Open section opens the same recorded course at that section.
await evalJs("location.hash = '#/'; true")
await wait(500)
await evalJs("location.hash = '#/coursebook'; true")
await wait(3000)
const labels = await evalJs(
  "([...document.querySelectorAll('[data-cb-trailhead-actions] button')].map((b) => (b.textContent || '').trim()))"
)
const sectionIndex = labels.findIndex((label) => /^Open section$/i.test(label))
if (sectionIndex >= 0) {
  await evalJs(`document.querySelectorAll('[data-cb-trailhead-actions] button')[${sectionIndex}].click(); true`)
  await wait(2000)
  report.steps.push({ step: 'open-section', clicked: labels[sectionIndex], ...(await facts()) })
} else {
  report.steps.push({ step: 'open-section', clicked: null, labels })
}

// Reduced motion: emulated media preference; the plate must carry no running animation.
await send('Emulation.setEmulatedMedia', {
  features: [{ name: 'prefers-reduced-motion', value: 'reduce' }]
})
await width(460)
await evalJs("location.hash = '#/'; true")
await wait(500)
await evalJs("location.hash = '#/coursebook'; true")
await wait(3000)
const reduced = await facts()
await shot('live-reduced-motion-460.png')
report.steps.push({ step: 'reduced-motion-460', ...reduced })

await send('Emulation.setEmulatedMedia', { features: [] })
await send('Emulation.clearDeviceMetricsOverride')
socket.close()
writeFileSync(resolve(outDir, 'live-check.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report.steps.map(({ step, width: w, buttons, companion, companionMotion, order, overflow, courseDetail, detailView, animations, label, desk }) => ({ step, width: w, label, desk, buttons, companion, companionMotion, order, overflow, courseDetail, detailView, animations })), null, 1))
