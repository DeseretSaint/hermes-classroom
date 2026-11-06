#!/usr/bin/env node
/**
 * Reload the isolated Hermes window and print its console + exception output.
 *
 * The pane states can only be judged from the live renderer, so this is the small driver that
 * answers "did the plugin module load and what did it say" without a devtools UI.
 *
 *   CB009_CDP_PORT=9337 node scripts/cb013-console.mjs [waitMs]
 */
const PORT = process.env.CB009_CDP_PORT || '9337'
const WAIT = Number(process.argv[2] || 8000)

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets[0]
if (!page) throw new Error('no page target on the isolated window')

const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})

let nextId = 1
const pending = new Map()
const lines = []
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
    const text = (message.params.args || [])
      .map((arg) => arg.value ?? arg.description ?? arg.unserializableValue ?? arg.type)
      .join(' ')
    lines.push(`[${message.params.type}] ${text}`)
  }
  if (message.method === 'Runtime.exceptionThrown') {
    const details = message.params.exceptionDetails || {}
    lines.push(`[exception] ${details.exception?.description || details.text}`)
  }
  if (message.method === 'Log.entryAdded') {
    const entry = message.params.entry
    if (entry.level === 'error' || entry.level === 'warning') {
      lines.push(`[log:${entry.level}] ${entry.text}`)
    }
  }
})

const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })

await send('Runtime.enable')
await send('Log.enable')
await send('Page.reload', { ignoreCache: true })
await new Promise((resolve) => setTimeout(resolve, WAIT))
const hash = await send('Runtime.evaluate', { expression: 'location.hash', returnByValue: true })
console.log(`hash: ${hash.result?.value}`)
console.log(lines.join('\n'))
socket.close()
