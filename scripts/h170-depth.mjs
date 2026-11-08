#!/usr/bin/env node
// H-168 live check: choosing "full" raises the default depth to Deep and states the floor.
const PORT = process.env.CB009_CDP_PORT || '9350'
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
    const { res, rej } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) rej(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 20000) =>
  new Promise((res, rej) => {
    const id = nextId++
    const timer = setTimeout(() => { pending.delete(id); rej(new Error(`timeout ${method}`)) }, timeout)
    pending.set(id, { res: (v) => { clearTimeout(timer); res(v) }, rej: (e) => { clearTimeout(timer); rej(e) } })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const clickText = (text) => evalJs(`(() => {
  const el = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === ${JSON.stringify(text)})
  if (!el) return false
  el.click()
  return true
})()`)

await send('Runtime.enable')
// Ensure we are on step 2 with a filled goal.
const step = await evalJs(`document.querySelector('[data-cb-create-step][aria-current="step"]')?.dataset.cbCreateStep`)
if (step === '1') { await clickText('Continue'); await wait(700) }
const out = {}
for (const scope of ['single', 'full']) {
  await evalJs(`document.querySelector('[data-cb-scope-option="${scope}"]')?.click()`)
  await wait(400)
  // Open the tune disclosure and read the depth control's selected option.
  await evalJs(`(() => { const d = document.querySelector('[data-cb-tune]'); if (d) d.open = true; return !!d })()`)
  await wait(300)
  out[scope] = await evalJs(`(() => {
    const tune = document.querySelector('[data-cb-tune]')
    const segs = tune ? [...tune.querySelectorAll('.segmented, [role="group"]')] : []
    const depthRow = [...(tune ? tune.querySelectorAll('div') : [])].find((d) => d.textContent.trim().startsWith('Depth') && d.querySelector('button'))
    const pressed = depthRow ? [...depthRow.querySelectorAll('button')].filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.textContent.trim()) : null
    return {
      floorNote: document.querySelector('[data-cb-depth-floor]')?.textContent || null,
      depthPressed: pressed,
      depthLabel: depthRow ? depthRow.textContent.replace(/\\s+/g, ' ').slice(0, 120) : null
    }
  })()`)
}
console.log(JSON.stringify(out, null, 2))
socket.close()
