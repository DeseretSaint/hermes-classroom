#!/usr/bin/env node
/**
 * H-84 live capture. Walks the real window: field desk -> course detail -> section (textbook).
 * Reloads the page first so the plugin module is re-read from the symlinked repo.
 *
 *   CB009_CDP_PORT=9337 node scripts/h84-capture.mjs <outdir> [--dark]
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const outdir = resolve(process.argv[2] || 'audit/ux/round3/h84-live')
const dark = process.argv.includes('--dark')
const only = process.argv.find((a) => a.startsWith('--only='))?.split('=')[1] || null
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
if (dark) {
  await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
}
// reload so the plugin module is re-read from the symlinked repo
await call('Page.reload', { ignoreCache: true })
await wait(4000)
if (dark) {
  await evaluate("document.documentElement.classList.add('dark'); window.dispatchEvent(new Event('resize'));")
}
await evaluate("location.hash = '#/coursebook'")
await waitFor("!!document.querySelector('[data-cb-route]')", 15000)
await wait(1200)

async function shot(name, width) {
  await call('Emulation.setDeviceMetricsOverride', { width: Math.round(width * 0.896), height: 1000, deviceScaleFactor: 1, mobile: false })
  await evaluate('window.dispatchEvent(new Event("resize"))')
  await wait(800)
  const metrics = JSON.parse(
    await evaluate(`(() => {
      const route = document.querySelector('[data-cb-route]')
      const scroller = route || document.scrollingElement
      return JSON.stringify({
        width: innerWidth,
        hash: location.hash,
        overflowX: scroller ? scroller.scrollWidth - scroller.clientWidth : null,
        h1: document.querySelectorAll('[data-cb-route] h1').length,
        uppercaseLabels: [...document.querySelectorAll('[data-cb-route] *')]
          .filter((e) => getComputedStyle(e).textTransform === 'uppercase' && e.textContent.trim())
          .slice(0, 8).map((e) => e.textContent.trim().slice(0, 40)),
        thinLabels: [...document.querySelectorAll('[data-cb-route] *')]
          .filter((e) => e.children.length === 0 && e.textContent.trim() && parseFloat(getComputedStyle(e).fontSize) < 12)
          .slice(0, 8).map((e) => e.textContent.trim().slice(0, 40) + ' @' + getComputedStyle(e).fontSize),
        thicks: [...document.querySelectorAll('[data-cb-route] *')]
          .filter((e) => { const s = getComputedStyle(e); return ['2px','3px','4px','5px','6px','8px'].includes(s.borderTopWidth) || ['2px','3px','4px','5px','6px','8px'].includes(s.borderLeftWidth) })
          .slice(0, 8).map((e) => e.tagName + ' ' + getComputedStyle(e).borderTopWidth + '/' + getComputedStyle(e).borderLeftWidth),
        primary: [...document.querySelectorAll('[data-cb-route] button')].filter((b) => b.dataset.variant === 'default').map((b) => b.textContent.trim()),
        title: document.title
      })
    })()`)
  )
  const png = await call('Page.captureScreenshot', { format: 'png' })
  const path = `${outdir}/${name}-${width}${dark ? '-dark' : ''}.png`
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(JSON.stringify({ path, ...metrics }))
}

const widths = [1049, 900, 460]
for (const w of widths) await shot('01-field-desk', w)

if (!only || only === 'course') {
  // open the first course row in the all-courses list
  const opened = await evaluate(`(() => {
    const row = document.querySelector('[data-cb-all-courses-row]')
    if (!row) return null
    const btn = row.querySelector('button') || row
    btn.click()
    return (btn.textContent || '').trim().slice(0, 60)
  })()`)
  await wait(2500)
  for (const w of widths) await shot('02-course-detail', w)

  // open the first section in the course
  const section = await evaluate(`(() => {
    const el = document.querySelector('[data-cb-path-item]') || document.querySelector('[data-cb-section-row]')
    if (!el) return null
    const target = el.closest('button') || el
    target.click()
    return target.textContent.trim().slice(0, 60)
  })()`)
  await wait(3500)
  for (const w of widths) await shot('03-section-textbook', w)
  console.log(JSON.stringify({ opened, section }))
}
socket.close()
