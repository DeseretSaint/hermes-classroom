#!/usr/bin/env node
/**
 * Click something in the isolated window and report what the renderer said.
 *
 *   CB009_CDP_PORT=9337 node scripts/cb013-click.mjs "Coursebook" [waitMs]
 *
 * Matches a button/link whose trimmed text equals the argument (or contains it when prefixed
 * with `~`). Prints the console/exceptions that follow the click, the resulting hash, and the
 * visible text of the main region — enough to tell "route not registered" from "route threw".
 */
const PORT = process.env.CB009_CDP_PORT || '9337'
const wanted = process.argv[2] || 'Coursebook'
const WAIT = Number(process.argv[3] || 4000)

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
})

const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })

const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true
  })
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  }
  return result.result?.value
}

await send('Runtime.enable')

const clicked = await evaluate(`(() => {
  const match = ${JSON.stringify(wanted)}
  const nodes = [...document.querySelectorAll('button,a,[role=link],[role=menuitem]')]
  const hit = match.startsWith('~')
    ? nodes.find((n) => (n.innerText || '').includes(match.slice(1)))
    : nodes.find((n) => (n.innerText || '').trim() === match)
  if (!hit) return 'not-found'
  hit.click()
  return 'clicked'
})()`)
console.log(`click(${wanted}): ${clicked}`)

await new Promise((resolve) => setTimeout(resolve, WAIT))

console.log(`hash: ${await evaluate('location.hash')}`)
console.log(`main: ${JSON.stringify((await evaluate(
  "(document.querySelector('main') || document.querySelector('#root')).innerText.slice(0, 400)"
)))}`)
console.log(lines.slice(-25).join('\n'))
socket.close()
