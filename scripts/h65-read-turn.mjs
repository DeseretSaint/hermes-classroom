/** H-65: read the live lesson chat's latest turn without sending anything. */
const PORT = process.env.CB013_CDP_PORT || '9337'
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data)
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id)
    pending.delete(m.id)
    m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const r = await send('Runtime.evaluate', {
  expression: `(() => {
    const t = document.body.innerText || ''
    const i = t.indexOf('I want to try this section')
    return { hash: location.hash, text: i >= 0 ? t.slice(i, i + 4000) : t.slice(-4000) }
  })()`,
  returnByValue: true
})
console.log(JSON.stringify(r.result.value, null, 2))
