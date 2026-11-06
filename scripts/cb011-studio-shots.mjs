#!/usr/bin/env node
/**
 * CB-011 Parent Studio capture: drive the real installed Desktop window through the studio and
 * write screenshots + a text trace of what was actually rendered.
 *
 *   CB011_CDP_PORT=9337 node scripts/cb011-studio-shots.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB011_CDP_PORT || '9337'
const SHOTS = 'docs/cb011-shots'
const trace = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on ' + PORT)
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: r, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else r(message.result)
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
const shot = async (name) => {
  const data = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  mkdirSync(SHOTS, { recursive: true })
  const path = resolve(`${SHOTS}/${name}.png`)
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const clickText = async (text) => {
  const clicked = await evaluate(`(() => {
    const wanted = ${JSON.stringify(text)}
    const nodes = [...document.querySelectorAll('button, [role="tab"], a, [role="option"], [data-slot]')]
    const node = nodes.find((n) => (n.innerText || '').trim() === wanted) ||
      nodes.find((n) => (n.innerText || '').trim().startsWith(wanted))
    if (!node) return false
    node.click()
    return true
  })()`)
  await sleep(900)
  return clicked
}
const snapshot = async (step) => {
  const state = await evaluate(`(() => {
    const text = document.body.innerText || ''
    return {
      hash: location.hash,
      buttons: [...document.querySelectorAll('button')].map((b) => (b.innerText || '').trim()).filter(Boolean).slice(0, 40),
      hasAnswerTab: text.includes('Answers'),
      learnerNote: text.includes('No answer key is included here'),
      exportBlocked: /Export is blocked|not approved|Changes need review/.test(text),
      badges: [...document.querySelectorAll('[data-slot="badge"], .badge')].map((b) => (b.innerText || '').trim()).filter(Boolean).slice(0, 20),
      excerpt: text.slice(0, 1400)
    }
  })()`)
  trace.push({ step, ...state })
  return state
}

await send('Runtime.enable')
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2500)
await snapshot('01-route')

console.log('parent studio tab:', await clickText('Parent Studio'))
await sleep(1500)
await snapshot('02-studio-list')
await shot('01-studio-list')

console.log('new brief:', await clickText('New lesson brief'))
await sleep(1200)
await snapshot('03-brief-form')
await shot('02-brief-form')

// Leave the form without submitting, then open the authored course.
await clickText('Cancel')
await sleep(900)
const opened = await clickText('Open studio')
console.log('open studio:', opened)
await sleep(2200)
await snapshot('04-studio-brief')
await shot('03-studio-brief')

for (const [label, name] of [
  ['Plan', '04-studio-plan'],
  ['Pages', '05-studio-pages'],
  ['Export', '06-studio-export'],
  ['Reflection', '07-studio-reflection']
]) {
  const ok = await clickText(label)
  await sleep(1600)
  await snapshot(`${name}:${ok}`)
  await shot(name)
}

writeFileSync(resolve('docs/REVIEW_CB011-ui-trace.json'), JSON.stringify({ port: PORT, target: page.url, trace }, null, 2))
console.log('shots + trace written')
socket.close()
