#!/usr/bin/env node
/**
 * Capture renderer console output, exceptions and plugin-related network calls across one reload.
 * Used by the CB-014 adversarial pass to explain why a route does or does not mount.
 *
 *   node tests/adversarial/cdp_console.mjs [--url '#/coursebook'] [--ms 9000]
 */
const PORT = process.env.CB009_CDP_PORT || '9337'
const args = process.argv.slice(2)
const url = args.includes('--url') ? args[args.indexOf('--url') + 1] : null
const ms = Number(args.includes('--ms') ? args[args.indexOf('--ms') + 1] : 9000)

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})
let nextId = 1
const pending = new Map()
const events = []
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) reject(new Error(JSON.stringify(message.error)))
    else resolve(message.result)
    return
  }
  if (message.method === 'Runtime.consoleAPICalled') {
    events.push({
      kind: 'console',
      level: message.params.type,
      text: (message.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(' ').slice(0, 400)
    })
  }
  if (message.method === 'Runtime.exceptionThrown') {
    events.push({ kind: 'exception', text: (message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text || '').slice(0, 600) })
  }
  if (message.method === 'Log.entryAdded') {
    events.push({ kind: `log:${message.params.entry.level}`, text: String(message.params.entry.text || '').slice(0, 400) })
  }
  if (message.method === 'Network.requestWillBeSent' && /plugin|coursebook/i.test(message.params.request.url)) {
    events.push({ kind: 'request', text: message.params.request.url.slice(0, 300) })
  }
  if (message.method === 'Network.responseReceived' && /plugin|coursebook/i.test(message.params.response.url)) {
    events.push({ kind: 'response', text: `${message.params.response.status} ${message.params.response.url.slice(0, 300)}` })
  }
})
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++
  pending.set(id, { resolve, reject })
  socket.send(JSON.stringify({ id, method, params }))
})

await send('Runtime.enable')
await send('Log.enable')
await send('Network.enable')
await send('Page.enable')
await send('Page.reload', { ignoreCache: true })
await new Promise((r) => setTimeout(r, ms))
if (url) {
  await send('Runtime.evaluate', { expression: `location.hash = ${JSON.stringify(url)}`, userGesture: true })
  await new Promise((r) => setTimeout(r, 3000))
}
const state = await send('Runtime.evaluate', {
  expression: `({hash: location.hash, title: document.title,
    mainText: (document.querySelector('main')||document.body).innerText.slice(0,400),
    pluginGlobals: Object.keys(window).filter(k => /plugin|hermes/i.test(k)).slice(0,20)})`,
  returnByValue: true, awaitPromise: true, userGesture: true
})
console.log(JSON.stringify({ state: state.result?.value, events: events.slice(-120) }, null, 2))
socket.close()
