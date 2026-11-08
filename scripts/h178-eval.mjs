#!/usr/bin/env node
/** Minimal CDP one-shot: evaluate an expression and print the result. */
const port = process.env.CB009_CDP_PORT || '9385'
const expr = process.argv[2] || 'document.title'
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
const page = targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((ok, bad) => {
  socket.addEventListener('open', ok, { once: true })
  socket.addEventListener('error', bad, { once: true })
})
const result = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('evaluate timeout')), 15000)
  socket.addEventListener('message', (event) => {
    const m = JSON.parse(event.data)
    if (m.id === 1) {
      clearTimeout(timer)
      resolve(m)
    }
  })
  socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression: expr, awaitPromise: true, returnByValue: true } }))
})
console.log(JSON.stringify(result).slice(0, 3000))
socket.close()
