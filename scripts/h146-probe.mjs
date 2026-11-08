#!/usr/bin/env node
/** One-off probe: can CDP's prefers-color-scheme emulation flip the isolated window's theme? */
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
const sleep = (ms) => new Promise((res) => setTimeout(res, ms))
await send('Page.enable')
await send('Runtime.enable')
await evaluate(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await evaluate(`location.hash = '#/'`)
await sleep(400)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1500)
const read = () => evaluate(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return {
    mounted: Boolean(route),
    scope: route && route.getAttribute('data-cb-scope'),
    dark: document.documentElement.classList.contains('dark'),
    media: matchMedia('(prefers-color-scheme: dark)').matches,
    text: document.body.innerText.slice(0, 200)
  }
})()`)
console.log('initial', JSON.stringify(await read()))
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] })
await sleep(500)
console.log('emulated-dark', JSON.stringify(await read()))
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] })
await sleep(500)
console.log('emulated-light', JSON.stringify(await read()))
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: '' }] })
socket.close()
