#!/usr/bin/env node
/**
 * H-86 live capture: the start plate, the three New Course steps, a section with no chat, and the
 * two secondary destinations. Measures one-primary counts, nav current state and overflow.
 *
 *   CB009_CDP_PORT=9337 node scripts/h86-capture.mjs <outdir> [--dark]
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const outdir = resolve(process.argv[2] || 'audit/ux/round3/h86-live')
const dark = process.argv.includes('--dark')
mkdirSync(outdir, { recursive: true })

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m)
    pending.delete(m.id)
  }
})
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = nextId++
    pending.set(id, res)
    socket.send(JSON.stringify({ id, method, params }))
  })
const call = async (method, params = {}) => {
  const r = await send(method, params)
  if (r.error) throw new Error(`${method}: ${JSON.stringify(r.error)}`)
  return r.result
}
const evaluate = async (expression) => {
  const r = await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400))
  return r.result.value
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 12000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await evaluate(expr)) return true
    await wait(250)
  }
  return false
}

await call('Runtime.enable')
await call('Page.enable')
if (dark) await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
await call('Page.reload', { ignoreCache: true })
await wait(4500)
if (dark) {
  await evaluate("document.documentElement.classList.add('dark'); window.dispatchEvent(new Event('resize'));")
}
await evaluate("location.hash = '#/coursebook'")
await waitFor("!!document.querySelector('[data-cb-route]')", 15000)
await wait(1500)

const WIDTHS = (process.env.H86_WIDTHS || '1049,900,460').split(',').map(Number)

async function shot(name, width) {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(width * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
  await evaluate('window.dispatchEvent(new Event("resize"))')
  await wait(700)
  const metrics = JSON.parse(
    await evaluate(`(() => {
      const route = document.querySelector('[data-cb-route]')
      const scroller = route || document.scrollingElement
      const inRoute = [...document.querySelectorAll('[data-cb-route] button')]
      return JSON.stringify({
        width: innerWidth,
        hash: location.hash,
        routeWidth: route ? route.clientWidth : null,
        overflowX: scroller ? scroller.scrollWidth - scroller.clientWidth : null,
        h1: document.querySelectorAll('[data-cb-route] h1').length,
        primaries: inRoute.filter((b) => b.dataset.variant === 'default').map((b) => b.textContent.trim()),
        nav: [...document.querySelectorAll('[data-cb-nav-item]')].map((b) => (b.getAttribute('aria-current') || '-') + ':' + b.textContent.trim()),
        startPlate: !!document.querySelector('[data-cb-first-run]'),
        spine: [...document.querySelectorAll('[data-cb-create-step]')].map((s) => (s.getAttribute('aria-current') || '-') + ':' + s.textContent.trim()),
        sectionActions: document.querySelector('[data-cb-section-actions]')?.dataset.cbSectionActions || null,
        sectionButtons: [...(document.querySelector('[data-cb-section-actions]')?.querySelectorAll('button') || [])].map((b) => b.textContent.trim()),
        noChatLine: !!document.body.textContent.includes('This section has no lesson chat yet')
      })
    })()`)
  )
  const png = await call('Page.captureScreenshot', { format: 'png' })
  const path = `${outdir}/${name}-${width}${dark ? '-dark' : ''}.png`
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(JSON.stringify({ path, ...metrics }))
}

const clickText = async (selector, text) =>
  evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find((b) => b.textContent.trim().includes(${JSON.stringify(text)}))
    if (!el) return false
    el.click()
    return true
  })()`)

for (const w of WIDTHS) await shot('01-first-run-empty-or-desk', w)

// New Course steps 1-3 -------------------------------------------------------
const opened = await clickText("header button", "New course")
await wait(1200)
await waitFor("!!document.querySelector('[data-cb-create-spine]')", 8000)
for (const w of WIDTHS) await shot('02-new-course-step1', w)

await evaluate(`(() => {
  const el = document.querySelector('[data-cb-scope-option="short"]')
  if (el) el.click()
  return !!el
})()`)
await wait(600)
await clickText("button", "Continue")
await wait(900)
for (const w of WIDTHS) await shot('03-new-course-step2', w)

// fill the goal + name so step 3 is reachable, then advance
await evaluate(`(() => {
  const setValue = (el, value) => {
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }
  const goal = document.querySelector('#cb-goal')
  const title = document.querySelector('#cb-title')
  if (goal) setValue(goal, 'I want to be able to fix a flat tyre on my bike without help.')
  if (title) setValue(title, 'Fixing a flat tyre')
  return [!!goal, !!title]
})()`)
await wait(500)
await clickText("button", "Continue")
await wait(900)
for (const w of WIDTHS) await shot('04-new-course-step3', w)

// leave the flow without creating anything
await clickText("button", "Cancel")
await wait(1200)
for (const w of [1049]) await shot('05-desk-with-course', w)

// nav: library and parent studio ---------------------------------------------
await evaluate(`document.querySelector('[data-cb-nav-item="library"]').click()`)
await wait(1500)
for (const w of WIDTHS) await shot('06-library', w)
await evaluate(`document.querySelector('[data-cb-nav-item="studio"]').click()`)
await wait(1800)
for (const w of WIDTHS) await shot('07-parent-studio', w)
await evaluate(`document.querySelector('[data-cb-nav-item="courses"]').click()`)
await wait(1500)

// section with no chat -------------------------------------------------------
await evaluate(`(() => {
  const row = document.querySelector('[data-cb-all-courses-row]')
  if (!row) return false
  ;(row.querySelector('button') || row).click()
  return true
})()`)
await wait(2500)
await evaluate(`(() => {
  const el = document.querySelector('[data-cb-path-item]') || document.querySelector('[data-cb-section-row]')
  if (!el) return false
  ;(el.closest('button') || el).click()
  return true
})()`)
await wait(3500)
for (const w of WIDTHS) await shot('08-section-no-chat', w)

console.log(JSON.stringify({ opened }))
socket.close()
