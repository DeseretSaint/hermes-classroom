/**
 * Shared CDP harness for the CB-015 proof suite.
 *
 * The window under test is the *isolated* Electron instance from
 * `scripts/cb013-live-window.sh` (its own HOME/userdata, CDP on 9337). Nothing here touches the
 * operator's window. Every helper returns real values read from the renderer — no fixture data.
 *
 *   import { connect, waitFor, shot, key, textOf } from './cb015-lib.mjs'
 */
const PORT = process.env.CB015_CDP_PORT || process.env.CB009_CDP_PORT || '9337'
const BASE = `http://127.0.0.1:${PORT}`

export async function connect() {
  const targets = await (await fetch(`${BASE}/json`)).json()
  const page =
    targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) ||
    targets.find((entry) => entry.type === 'page')
  if (!page) throw new Error(`no page target on ${BASE}`)
  const socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  const listeners = []
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) reject(new Error(JSON.stringify(message.error)))
      else resolve(message.result)
      return
    }
    for (const listener of listeners) listener(message)
  })
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++
      pending.set(id, { resolve, reject })
      socket.send(JSON.stringify({ id, method, params }))
    })

  const api = {
    send,
    on: (listener) => listeners.push(listener),
    close: () => socket.close(),
    async eval(expression) {
      const result = await send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
        userGesture: true
      })
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
      }
      return result.result.value
    },
    async json(expression) {
      const value = await api.eval(`JSON.stringify(${expression})`)
      return JSON.parse(value)
    },
    async wait(ms) {
      await new Promise((resolve) => setTimeout(resolve, ms))
    },
    async waitFor(expression, { timeout = 20000, interval = 150, label = expression } = {}) {
      const started = Date.now()
      let last
      while (Date.now() - started < timeout) {
        try {
          last = await api.eval(`Boolean(${expression})`)
        } catch (error) {
          last = false
        }
        if (last === true) return Date.now() - started
        await api.wait(interval)
      }
      throw new Error(`timed out waiting for ${label} after ${timeout}ms`)
    },
    async shot(path) {
      const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
      const { writeFileSync, mkdirSync } = await import('node:fs')
      const { dirname, resolve } = await import('node:path')
      const target = resolve(path)
      mkdirSync(dirname(target), { recursive: true })
      writeFileSync(target, Buffer.from(data, 'base64'))
      return target
    },
    async setViewport(width, height, scale = 1) {
      await send('Emulation.setDeviceMetricsOverride', {
        width,
        height,
        deviceScaleFactor: scale,
        mobile: false
      })
    },
    async clearViewport() {
      await send('Emulation.clearDeviceMetricsOverride')
    },
    async reload() {
      await send('Page.reload', { ignoreCache: false })
      await api.wait(1200)
    },
    /** A real key event through Chromium's input pipeline (not `element.focus()` or `.click()`). */
    async key(keyName, { modifiers = 0, code, text } = {}) {
      const map = {
        Tab: { key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 },
        Enter: { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 },
        Escape: { key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 },
        ArrowDown: { key: 'ArrowDown', code: 'ArrowDown', windowsVirtualKeyCode: 40 },
        ArrowUp: { key: 'ArrowUp', code: 'ArrowUp', windowsVirtualKeyCode: 38 },
        ArrowRight: { key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 },
        ArrowLeft: { key: 'ArrowLeft', code: 'ArrowLeft', windowsVirtualKeyCode: 37 },
        Home: { key: 'Home', code: 'Home', windowsVirtualKeyCode: 36 },
        End: { key: 'End', code: 'End', windowsVirtualKeyCode: 35 },
        Space: { key: ' ', code: 'Space', windowsVirtualKeyCode: 32 },
        X: { key: 'X', code: 'KeyX', windowsVirtualKeyCode: 88, text: 'X' }
      }
      const entry = map[keyName] || { key: keyName, code: keyName }
      const base = { ...entry, modifiers, nativeVirtualKeyCode: 0 }
      if (entry.text && !modifiers) base.text = entry.text
      if (modifiers & 8) delete base.text // Shift+X is a shortcut, not text input
      await send('Input.dispatchKeyEvent', { type: 'keyDown', ...base })
      await send('Input.dispatchKeyEvent', { type: 'keyUp', ...base })
    },
    async type(text) {
      await send('Input.insertText', { text })
    },
    async click(x, y) {
      for (const type of ['mousePressed', 'mouseReleased']) {
        await send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
      }
    },
    /** Click the first element whose innerText matches, by its real geometry. */
    async clickText(text, { exact = true } = {}) {
      const box = await api.json(`(() => {
        const all = [...document.querySelectorAll('button, a, [role="tab"], [role="option"], [role="menuitem"]')]
        const wanted = ${JSON.stringify(text)}
        const el = all.find((e) => {
          const label = (e.innerText || '').trim()
          return ${exact ? 'label === wanted' : 'label.includes(wanted)'}
        })
        if (!el) return null
        el.scrollIntoView({ block: 'center' })
        const r = el.getBoundingClientRect()
        return { x: r.x + r.width / 2, y: r.y + r.height / 2, label: (el.innerText || '').trim().slice(0, 80) }
      })()`)
      if (!box) throw new Error(`no control labelled ${JSON.stringify(text)}`)
      await api.click(box.x, box.y)
      return box
    }
  }
  return api
}

/** Turn the host's light/dark switch with its own rebindable action (Shift+X), not a CSS hack. */
export async function setMode(cdp, mode) {
  const current = await cdp.eval('document.documentElement.dataset.hermesMode')
  if (current === mode) return current
  await cdp.key('X', { modifiers: 8 })
  await cdp.waitFor(`document.documentElement.dataset.hermesMode === ${JSON.stringify(mode)}`, {
    timeout: 6000,
    label: `theme ${mode}`
  })
  return mode
}

export function rel(path) {
  return new URL(`../${path}`, import.meta.url).pathname
}

export async function writeJson(path, value) {
  const { writeFileSync, mkdirSync } = await import('node:fs')
  const { dirname, resolve } = await import('node:path')
  const target = resolve(path)
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(target, `${JSON.stringify(value, null, 2)}\n`)
  return target
}
