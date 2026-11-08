#!/usr/bin/env node
/** Shared CDP plumbing for the H-149 live capture. */
export async function connect(port = process.env.CB009_CDP_PORT || '9359') {
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
  const page =
    targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) ||
    targets.find((t) => t.type === 'page')
  if (!page) throw new Error('no page target on the isolated window')
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((ok, bad) => {
    socket.addEventListener('open', ok, { once: true })
    socket.addEventListener('error', bad, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve: res, reject, timer } = pending.get(message.id)
      clearTimeout(timer)
      pending.delete(message.id)
      if (message.error) reject(new Error(JSON.stringify(message.error)))
      else res(message.result)
    }
  })
  const send = (method, params = {}, timeout = 20000) =>
    new Promise((res, reject) => {
      const id = nextId++
      const timer = setTimeout(() => {
        pending.delete(id)
        reject(new Error(`CDP timeout: ${method}`))
      }, timeout)
      pending.set(id, { resolve: res, reject, timer })
      socket.send(JSON.stringify({ id, method, params }))
    })
  await send('Runtime.enable')
  await send('Page.enable')
  const evaluate = async (expression) => {
    const result = await send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true
    })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  const screenshot = async (path) => {
    const shot = await send('Page.captureScreenshot', { format: 'png' }, 30000)
    const { writeFileSync } = await import('node:fs')
    writeFileSync(path, Buffer.from(shot.data, 'base64'))
  }
  const setWidth = async (target) => {
    let override = target
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await send('Emulation.setDeviceMetricsOverride', {
        width: override,
        height: 1000,
        deviceScaleFactor: 1,
        mobile: false
      })
      await wait(250)
      const inner = await evaluate('window.innerWidth')
      if (Math.abs(inner - target) <= 1) return inner
      override = Math.round((override * target) / inner)
    }
    throw new Error(`could not calibrate ${target}px`)
  }
  const clickSelector = async (selector) => {
    const box = await evaluate(`(() => {
      const node = document.querySelector(${JSON.stringify(selector)})
      if (!node) return null
      node.scrollIntoView({ block: 'center' })
      const rect = node.getBoundingClientRect()
      return { x: rect.left + Math.min(rect.width / 2, 80), y: rect.top + rect.height / 2, w: rect.width, h: rect.height }
    })()`)
    if (!box) return false
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 })
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 })
    await wait(200)
    return true
  }
  return { send, evaluate, wait, screenshot, setWidth, clickSelector }
}
