#!/usr/bin/env node
/**
 * Type into the isolated window's composer and press Enter — real CDP input, so React's
 * synthetic events fire exactly as they do for a person (no value-poking shortcuts).
 *
 *   CB009_CDP_PORT=9337 node scripts/cb013-send.mjs "I'm ready for lesson 1."
 */
const PORT = process.env.CB009_CDP_PORT || '9337'
const text = process.argv[2]
const selector = process.argv[3] || '[contenteditable="true"]'
if (!text) {
  console.error('usage: cb013-send.mjs "<text>"')
  process.exit(2)
}

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')

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
await send('Input.setIgnoreInputEvents', { ignore: false })
const focused = await send('Runtime.evaluate', {
  expression: `(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return 'missing'; el.focus(); return 'focused'; })()`,
  returnByValue: true
})
console.log('focus:', focused.result?.value)
await send('Input.insertText', { text })
await new Promise((r) => setTimeout(r, 400))
const clickText = process.argv[4]
if (clickText) {
  const clicked = await send('Runtime.evaluate', {
    expression: `(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === ${JSON.stringify(clickText)}); if (!b) return 'missing-button'; b.click(); return 'clicked'; })()`,
    returnByValue: true
  })
  console.log('button:', clicked.result?.value)
} else {
  for (const type of ['keyDown', 'keyUp']) {
    await send('Input.dispatchKeyEvent', {
      type,
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13,
      text: type === 'keyDown' ? '\r' : undefined
    })
  }
}
console.log('sent')
socket.close()
