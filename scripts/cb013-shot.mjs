#!/usr/bin/env node
/**
 * Capture the isolated window's page target as a PNG.
 *
 *   CB009_CDP_PORT=9337 node scripts/cb013-shot.mjs docs/cb013-shots/10-detached.png
 *
 * Uses Page.captureScreenshot, so the file is whatever the renderer painted — no OS
 * window manager involved and no compositor scaling surprises.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9337'
const out = resolve(process.argv[2] || 'docs/cb013-shots/shot.png')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolveOpen, reject) => {
  socket.addEventListener('open', resolveOpen, { once: true })
  socket.addEventListener('error', reject, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve: res, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((res, reject) => {
    const id = nextId++
    pending.set(id, { resolve: res, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })

await send('Page.enable')
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, Buffer.from(shot.data, 'base64'))
console.log(`${out} ${Buffer.from(shot.data, 'base64').length} bytes`)
socket.close()
