#!/usr/bin/env node
/**
 * Evaluate one JS expression in the isolated window's page target and print the JSON result.
 *
 *   CB009_CDP_PORT=9337 node scripts/cb013-eval.mjs "document.title"
 *   CB009_CDP_PORT=9337 node scripts/cb013-eval.mjs --file scripts/probes/foo.js
 *
 * Expression runs with `awaitPromise` so async bodies work: pass an IIFE.
 */
import { readFileSync } from 'node:fs'

const PORT = process.env.CB009_CDP_PORT || '9337'
const arg = process.argv[2] || 'document.title'
const expression = arg === '--file' ? readFileSync(process.argv[3], 'utf8') : arg

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
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

await send('Runtime.enable')
const result = await send('Runtime.evaluate', {
  expression,
  awaitPromise: true,
  returnByValue: true,
  userGesture: true
})
if (result.exceptionDetails) {
  console.error('EXCEPTION', result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  process.exit(2)
}
console.log(JSON.stringify(result.result?.value ?? null, null, 2))
socket.close()
