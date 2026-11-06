#!/usr/bin/env node
/**
 * CDP driver for the isolated Hermes Desktop window (CB-009).
 *
 * The window is a *separate* Electron instance with its own --user-data-dir and CDP port; the
 * operator's packaged window is never touched. Usage:
 *
 *   node scripts/cb009-cdp.mjs eval "document.title"
 *   node scripts/cb009-cdp.mjs shot docs/cb009-shots/01-x.png
 *   node scripts/cb009-cdp.mjs goto "#/coursebook"
 *   node scripts/cb009-cdp.mjs wait 800
 */
import fs from 'node:fs'

const PORT = process.env.CB009_CDP_PORT || '9333'
const BASE = `http://127.0.0.1:${PORT}`

async function target() {
  const response = await fetch(`${BASE}/json`)
  const list = await response.json()
  const page = list.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || list[0]
  if (!page) throw new Error('no page target on the isolated window')
  return page
}

async function connect() {
  const page = await target()
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
  return { send, close: () => socket.close() }
}

async function evaluate(send, expression, awaitPromise = true) {
  const result = await send('Runtime.evaluate', {
    expression,
    awaitPromise,
    returnByValue: true,
    userGesture: true
  })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || 'evaluation failed')
  }
  return result.result.value
}

const [, , verb, ...rest] = process.argv
const argument = rest.join(' ')

const { send, close } = await connect()
try {
  if (verb === 'eval') {
    console.log(JSON.stringify(await evaluate(send, argument), null, 2))
  } else if (verb === 'goto') {
    await evaluate(send, `location.hash = ${JSON.stringify(argument)}`)
    await new Promise((resolve) => setTimeout(resolve, 600))
    console.log(await evaluate(send, 'location.hash'))
  } else if (verb === 'wait') {
    await new Promise((resolve) => setTimeout(resolve, Number(argument) || 500))
    console.log('waited')
  } else if (verb === 'shot') {
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
    fs.mkdirSync(argument.split('/').slice(0, -1).join('/') || '.', { recursive: true })
    fs.writeFileSync(argument, Buffer.from(shot.data, 'base64'))
    console.log(argument)
  } else if (verb === 'size') {
    const [width, height] = argument.split('x').map(Number)
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
    console.log(`${width}x${height}`)
  } else if (verb === 'reset-size') {
    await send('Emulation.clearDeviceMetricsOverride')
    console.log('reset')
  } else if (verb === 'text') {
    console.log(await evaluate(send, 'document.body.innerText'))
  } else if (verb === 'reload') {
    await send('Page.reload', { ignoreCache: true })
    await new Promise((resolve) => setTimeout(resolve, Number(argument) || 2500))
    console.log('reloaded')
  } else {
    throw new Error(`unknown verb ${verb}`)
  }
} finally {
  close()
}
