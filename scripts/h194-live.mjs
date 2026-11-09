#!/usr/bin/env node
/**
 * H-194 live run: fine-tune controls in the real Desktop renderer.
 *
 * Drives the isolated Coursebook window (remote connection to the disposable backend) against a
 * course the real generation pipeline authored. It performs, in the UI: open the parent course →
 * Plan view → edit one section's objective metadata → reorder two sections → open Review changes →
 * approve the lesson set again. Screenshots are written for the editor, the reorder confirmation
 * and the review diff. Nothing is asserted here that the DOM does not carry.
 *
 *   CB013_CDP_PORT=9386 H194_TITLE="Counting to ten in Japanese" node scripts/h194-live.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB013_CDP_PORT || '9386'
const TITLE = process.env.H194_TITLE || 'Counting to ten in Japanese'
const OUT = resolve(process.env.H194_SHOTS || 'audit/h194/live')
mkdirSync(OUT, { recursive: true })

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
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
    const { res, rej } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) rej(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 30000) =>
  new Promise((res, rej) => {
    const id = nextId++
    const timer = setTimeout(() => {
      pending.delete(id)
      rej(new Error(`CDP timeout: ${method}`))
    }, timeout)
    pending.set(id, {
      res: (value) => { clearTimeout(timer); res(value) },
      rej: (error) => { clearTimeout(timer); rej(error) }
    })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 30000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await evalJs(expr)) return true
    await wait(250)
  }
  return false
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, 'base64'))
  console.log(`shot ${OUT}/${name}.png`)
}
const text = (node) => (node ? (node.innerText || '').replace(/\s+/g, ' ').trim() : null)

const clickText = (label, selector = 'button, [role="button"]') =>
  evalJs(`(() => {
    const wanted = ${JSON.stringify(label)}
    const nodes = [...document.querySelectorAll(${JSON.stringify(selector)})]
    const node = nodes.find((n) => (n.innerText || '').trim() === wanted) || nodes.find((n) => (n.innerText || '').includes(wanted))
    if (!node) return false
    node.click()
    return true
  })()`)

const clickSelector = (selector) =>
  evalJs(`(() => {
    const node = document.querySelector(${JSON.stringify(selector)})
    if (!node) return false
    node.click()
    return true
  })()`)

const facts = {}

await send('Page.bringToFront')
await send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {})
await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1200, deviceScaleFactor: 1, mobile: false })
await wait(500)

await evalJs("location.hash='#/'; 'ok'")
await wait(400)
await evalJs("location.hash='#/coursebook'; 'ok'")
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 25000))) {
  throw new Error('the Coursebook route did not mount; refusing to capture')
}
for (const label of ['Hide right sidebar', 'Hide sidebar']) {
  await evalJs(`(() => {
    const b = [...document.querySelectorAll('button[aria-label]')].find((n) => n.getAttribute('aria-label') === ${JSON.stringify(label)})
    if (b) b.click()
    return 'ok'
  })()`)
}
await wait(600)

if (!(await waitFor("!!document.querySelector('[data-cb-nav-item=\"studio\"]')", 15000))) {
  throw new Error('no Parent Studio destination on the route')
}
await clickSelector('[data-cb-nav-item="studio"]')
await wait(1200)

// The course the seed created is the newest parent plan; open it by its own title.
let opened = await clickText(TITLE)
if (!opened) {
  opened = await evalJs(`(() => {
    const nodes = [...document.querySelectorAll('button')]
    const node = nodes.find((n) => (n.innerText || '').includes('Counting to ten'))
    if (!node) return false
    node.click()
    return true
  })()`)
}
if (!opened) throw new Error(`the seeded course "${TITLE}" is not on the Parent Studio landing`)
facts.opened = await waitFor("!!document.querySelector('[data-cb-studio-view]') || !!document.querySelector('[data-cb-finetune]') || !!document.querySelector('[data-cb-view-picker]')", 15000)

// Plan view: the segmented control renders one button per Studio view.
if (!(await clickText('Plan', '[aria-pressed], button'))) throw new Error('the Plan view control was not found')
if (!(await waitFor("!!document.querySelector('[data-cb-finetune]')", 25000))) {
  throw new Error('the fine-tune panel did not mount on the approved plan')
}
await wait(600)
facts.before = await evalJs(`(() => {
  const list = document.querySelector('[data-cb-finetune-order]')
  return {
    order: list ? list.getAttribute('data-cb-finetune-order') : null,
    rows: [...document.querySelectorAll('[data-cb-finetune-row]')].map((row) => ({
      id: row.getAttribute('data-cb-finetune-row'),
      title: ((row.querySelector('[data-cb-finetune-title]') || {}).textContent || '').trim(),
      chip: (row.querySelector('[data-cb-finetune-chip]') || {}).getAttribute?.('data-cb-finetune-chip') || null,
      moveDownDisabled: Boolean((row.querySelector('[data-cb-finetune-move="down"]') || {}).disabled)
    }))
  }
})()`)
await shot('h194-plan-approved')

// 1 — inline section edit (objective metadata) on the first section.
await clickSelector('[data-cb-finetune-row] [data-cb-finetune-edit]')
if (!(await waitFor("!!document.querySelector('[data-cb-finetune-editor]')", 10000))) throw new Error('the inline editor did not open')
const editorId = await evalJs("document.querySelector('[data-cb-finetune-editor]').getAttribute('data-cb-finetune-editor')")
const newTitle = `${facts.before.rows[0].title} (revised)`
await evalJs(`(() => {
  const node = document.querySelector('#cb-finetune-title-${editorId}')
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(node, ${JSON.stringify(newTitle)})
  node.dispatchEvent(new window.Event('input', { bubbles: true }))
  return node.value
})()`)
await wait(400)
facts.editorDirty = await evalJs("!!document.querySelector('[data-cb-finetune-dirty]')")
await shot('h194-editor')
await clickSelector('[data-cb-finetune-save]')
if (!(await waitFor("!!document.querySelector('[data-cb-finetune-notice]')", 20000))) throw new Error('saving the section produced no notice')
await wait(800)
facts.afterEdit = {
  notice: await evalJs("(document.querySelector('[data-cb-finetune-notice]') || {}).innerText || null"),
  chips: await evalJs("[...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip'))")
}

// 2 — reorder: move the first section down. The command decides the order; the screen adopts it.
await clickSelector('[data-cb-finetune-row] [data-cb-finetune-move="down"]')
if (!(await waitFor("(document.querySelector('[data-cb-finetune-notice]') || {}).innerText && document.querySelector('[data-cb-finetune-notice]').innerText.startsWith('Order saved.')", 20000))) {
  throw new Error('the reorder produced no stored-order confirmation')
}
await wait(600)
facts.reorder = await evalJs(`(() => {
  const list = document.querySelector('[data-cb-finetune-order]')
  return {
    order: list ? list.getAttribute('data-cb-finetune-order') : null,
    notice: (document.querySelector('[data-cb-finetune-notice]') || {}).innerText || null,
    undo: (document.querySelector('[data-cb-finetune-undo]') || {}).getAttribute?.('data-cb-finetune-undo') || null,
    rows: [...document.querySelectorAll('[data-cb-finetune-row]')].map((row) => ((row.querySelector('[data-cb-finetune-title]') || {}).textContent || '').trim())
  }
})()`)
await shot('h194-reorder-confirmed')

// 3 — Review changes: the pending diff and the export gate, opened from the Plan tab.
await clickSelector('[data-cb-finetune-review]')
if (!(await waitFor("!!document.querySelector('[data-cb-review-diff]')", 20000))) throw new Error('the review diff did not mount')
await wait(600)
facts.review = await evalJs(`(() => {
  const diff = document.querySelector('[data-cb-review-diff]')
  return {
    state: diff ? diff.getAttribute('data-cb-review-diff') : null,
    exportGate: (document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') || null,
    blockedReason: (document.querySelector('[data-cb-review-blocked-reason]') || {}).getAttribute?.('data-cb-review-blocked-reason') || null,
    blockedLine: (document.querySelector('[data-cb-export-blocked-reason]') || {}).textContent || null,
    changed: [...document.querySelectorAll('[data-cb-review-changed]')].map((n) => n.getAttribute('data-cb-review-changed')),
    chips: [...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip')),
    approveDisabled: Boolean(([...document.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === 'Approve this lesson set') || {}).disabled)
  }
})()`)
await shot('h194-review-diff')

// 4 — Approve the exact bytes that were just reviewed.
await clickText('Approve this lesson set')
const approved = await waitFor("(document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') === 'ready'", 30000)
await wait(800)
facts.afterApprove = await evalJs(`(() => {
  const diff = document.querySelector('[data-cb-review-diff]')
  const exportButton = [...document.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === 'Export the approved files')
  return {
    exportGate: (document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') || null,
    blockedReason: (document.querySelector('[data-cb-review-blocked-reason]') || {}).getAttribute?.('data-cb-review-blocked-reason') || null,
    exportDisabled: exportButton ? Boolean(exportButton.disabled) : null,
    body: diff ? diff.innerText.slice(0, 400) : null
  }
})()`)
facts.afterApprove.reachedReady = approved
await shot('h194-export-ready')

writeFileSync(`${OUT}/facts.json`, JSON.stringify(facts, null, 2))
console.log(JSON.stringify(facts, null, 2))
