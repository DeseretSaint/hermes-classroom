#!/usr/bin/env node
const PORT = process.env.CB009_CDP_PORT || '9364'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
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
    const { resolve: res, reject } = pending.get(message.id)
    pending.delete(message.id)
    message.error ? reject(new Error(JSON.stringify(message.error))) : res(message.result)
  }
})
const send = (method, params = {}) =>
  new Promise((res, rej) => {
    const id = nextId++
    pending.set(id, { resolve: res, reject: rej })
    socket.send(JSON.stringify({ id, method, params }))
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error(`timeout ${method}`)) } }, 20000)
  })
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
await send('Runtime.enable')
const keys = await evaluate(`(() => {
  const out = {}
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i)
    if (/theme|appearance|mode/i.test(key)) out[key] = localStorage.getItem(key)
  }
  return out
})()`)
console.log(JSON.stringify(keys, null, 2))
socket.close()
