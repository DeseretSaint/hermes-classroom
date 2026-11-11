#!/usr/bin/env node
/**
 * Set the isolated window's host appearance (light | dark) through the app's own Coursebook
 * settings control, and verify the route repainted.
 *
 * Why not `--color-scheme` on the capture: the v3 route follows the *host* theme attribute, not
 * `prefers-color-scheme`, so an emulated scheme leaves a light route under a dark claim and the
 * capture door refuses it. This driver uses the same control a learner uses.
 *
 *   node docs/visual-review/cp-024/set-appearance.mjs dark --cdp-port 9357
 */
const args = process.argv.slice(2)
const mode = String(args[0] || 'light')
const portFlag = args.indexOf('--cdp-port')
const port = portFlag >= 0 ? args[portFlag + 1] : process.env.CB009_CDP_PORT || '9337'
if (!['light', 'dark'].includes(mode)) throw new Error(`unknown appearance: ${mode}`)

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
const page = targets.find((t) => t.type === 'page' && /Hermes/.test(t.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else resolve(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true
  })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'evaluate failed')
  return result.result.value
}

const picked = await evaluate(`(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
  const home = [...document.querySelectorAll('button,a,[role=button],[role=link]')].find(
    (el) => (el.innerText || '').trim() === 'Home'
  )
  if (home) {
    home.click()
    await sleep(1400)
  }
  const cascade = document.querySelector('[data-cb-course-back]')
  if (cascade) {
    cascade.click()
    await sleep(1200)
  }
  const open = [...document.querySelectorAll('button,a,[role=button],[role=link]')].find(
    (el) => (el.innerText || '').trim() === 'Settings'
  )
  if (!open) return 'no-settings'
  open.click()
  await sleep(600)
  const root = document.querySelector('[data-cb-settings-control="appearance"]')
  if (!root) return 'no-control'
  const option = [...root.querySelectorAll('button')].find(
    (b) => (b.innerText || '').trim().toLowerCase() === ${JSON.stringify(mode)}
  )
  if (!option) return 'no-option'
  option.click()
  await sleep(300)
  const close = document.querySelector('[data-cb-settings-close]')
  if (close) close.click()
  await sleep(500)
  return document.querySelector('[data-cb-route]')?.getAttribute('data-cb-scope') || 'no-scope'
})()`)
if (picked !== mode) throw new Error(`appearance ${mode}: route scope is ${picked}`)
console.log(`appearance ${mode} (route scope ${picked})`)
socket.close()
