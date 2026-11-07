#!/usr/bin/env node
/**
 * H-35: drive the confirmation checklist in the live Desktop window and print what it did.
 *
 *   node scripts/cb013-checklist.mjs [prefix]
 *
 * Opens the rig's one-off verification course through the Courses list, clicks two of the three
 * served items, records the exact `attempt.submit` body off the wire, submits, and prints the
 * rendered verdict rows plus the frozen self-reported copy. Writes a screenshot beside the prefix.
 *
 * Evidence, not a claim: every line comes from the live renderer / the network body.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB013_CDP_PORT || '9337'
const prefix = process.argv[2] || 'docs/h35-shots/checklist'
const shotPath = resolve(`${prefix}.png`)
mkdirSync(dirname(shotPath), { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no Desktop page target on CDP')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
const submitted = []
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: r, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else r(message.result)
    return
  }
  if (message.method === 'Network.requestWillBeSent') {
    const { request } = message.params
    if (request && /\/rpc$/.test(request.url) && request.postData) {
      try {
        const body = JSON.parse(request.postData)
        if (body.method === 'attempt.submit') submitted.push(body)
      } catch {
        /* not our envelope */
      }
    }
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value
}
const waitFor = async (expression, label, timeoutMs = 20000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const value = await evaluate(expression)
    if (value) return value
    await sleep(250)
  }
  throw new Error(`timed out waiting for ${label}`)
}

await send('Page.enable')
await send('Runtime.enable')
await send('Network.enable')

// The isolated rig starts with the plugin opted-in; this is idempotent and survives a reload.
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
// A hard reload, not a hash change: the renderer keeps the module it loaded at boot, so a swapped
// plugin.js only proves anything after the script is fetched again.
await send('Page.reload', { ignoreCache: true })
await sleep(4500)
await evaluate(`(() => { location.hash = '#/coursebook'; return true })()`)
await sleep(1200)
await waitFor(`Boolean(document.querySelector('[data-cb-route="/coursebook"]'))`, 'the Coursebook route')

// Courses list -> the seeded one-off course. Deterministic and re-runnable: if a course detail is
// already on screen, use it; otherwise list the courses and open the row by its own title.
const state = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route="/coursebook"]')
  if ([...route.querySelectorAll('button')].some((b) => (b.innerText || '').trim() === 'Open the section')) return 'course detail'
  const list = [...route.querySelectorAll('button')].find((b) => /All courses/i.test(b.innerText || ''))
  if (list) list.click()
  return 'listing'
})()`)
console.log('course state:', state)
if (state !== 'course detail') {
  await sleep(1500)
  const chosen = await evaluate(`(() => {
    const route = document.querySelector('[data-cb-route="/coursebook"]')
    if ([...route.querySelectorAll('button')].some((b) => (b.innerText || '').trim() === 'Open the section')) return 'course detail'
    const node = [...route.querySelectorAll('*')].find((el) => el.children.length === 0 && (el.innerText || '').trim() === 'Order coffee in Japanese')
    if (!node) return 'title not found'
    let scope = node
    for (let depth = 0; depth < 8 && scope; depth += 1, scope = scope.parentElement) {
      const open = [...scope.querySelectorAll('button')].find((b) => /^(Open|View|Continue)$/i.test((b.innerText || '').trim()))
      if (open) { open.click(); return 'opened: ' + node.innerText.trim() }
    }
    return 'no open control near the title'
  })()`)
  console.log('course open:', chosen)
}
await sleep(1800)

// Inside the course, open the section that carries the check.
const section = await evaluate(`(() => {
  const route = document.querySelector('[data-cb-route="/coursebook"]')
  const target = [...route.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Open the section')
  if (!target) return null
  target.click()
  return 'Open the section'
})()`)
console.log('section control:', section)
await sleep(1500)

const checklist = await waitFor(
  `(() => {
    const box = document.querySelector('[data-cb-check-items-mode="selection"]')
    if (!box) return null
    const ticks = [...box.querySelectorAll('[data-cb-check-tick]')].map((el) => el.getAttribute('data-cb-check-tick'))
    const labels = [...box.querySelectorAll('label')].map((el) => (el.innerText || '').trim())
    return { count: ticks.length, ids: ticks, labels }
  })()`,
  'the served checklist'
)
console.log('served checklist:', JSON.stringify(checklist))

const before = await evaluate(`(() => {
  const button = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Submit confirmation')
  return button ? { disabled: button.disabled } : null
})()`)
console.log('submit before any tick:', JSON.stringify(before))

// Tick two of the three served items with real clicks.
const ticked = await evaluate(`(() => {
  const box = document.querySelector('[data-cb-check-items-mode="selection"]')
  const rows = [...box.querySelectorAll('li')]
  const clicked = []
  for (const index of [0, 1]) {
    const input = rows[index].querySelector('input[type="checkbox"], [role="checkbox"], button')
    if (!input) return { error: 'no control in row ' + index }
    input.click()
    clicked.push(rows[index].getAttribute('data-cb-check-item'))
  }
  return clicked
})()`)
console.log('ticked:', JSON.stringify(ticked))
await sleep(500)

const after = await evaluate(`(() => {
  const button = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Submit confirmation')
  const ticks = [...document.querySelectorAll('[data-cb-check-items-mode="selection"] input, [data-cb-check-items-mode="selection"] [role="checkbox"]')]
    .map((el) => el.getAttribute('aria-checked') || String(el.checked))
  return { disabled: button ? button.disabled : null, ticks }
})()`)
console.log('submit after two ticks:', JSON.stringify(after))

const clicked = await evaluate(`(() => {
  const button = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Submit confirmation')
  if (!button || button.disabled) return false
  button.click()
  return true
})()`)
console.log('submit clicked:', clicked)

await waitFor(`Boolean(document.querySelector('[data-cb-verdict]'))`, 'a rendered verdict', 25000)
await sleep(600)

const verdict = await evaluate(`(() => {
  const panel = document.querySelector('[data-cb-verdict]')
  const rows = [...panel.querySelectorAll('[data-cb-criterion]')].map((el) => ({
    id: el.getAttribute('data-cb-criterion'),
    met: el.getAttribute('data-cb-criterion-met'),
    label: (el.querySelector('label') || {}).innerText || '',
    state: (el.querySelector('span:last-child') || {}).innerText || ''
  }))
  return {
    verdict: panel.getAttribute('data-cb-verdict'),
    evidence_class: panel.getAttribute('data-cb-evidence-class'),
    text: (panel.innerText || '').trim(),
    criteria: rows,
    evidence_notice: (document.querySelector('[data-cb-evidence-notice]') || {}).innerText || '',
    submit_label_present: Boolean([...document.querySelectorAll('button')].find((b) => /Submit confirmation/.test(b.innerText)))
  }
})()`)
console.log('verdict:', JSON.stringify(verdict, null, 1))
console.log('attempt.submit bodies:', JSON.stringify(submitted, null, 1))

const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
writeFileSync(shotPath, Buffer.from(shot.data, 'base64'))
console.log('screenshot:', shotPath)
socket.close()
