#!/usr/bin/env node
/** H-147 probe: the sheet scrolls, and its text contrast is measured, not eyeballed. */
const PORT = process.env.CB009_CDP_PORT || '9381'
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
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        rej(new Error(`timeout ${method}`))
      }
    }, 20000)
  })
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
  return result.result.value
}
const sleep = (ms) => new Promise((res) => setTimeout(res, ms))
await send('Runtime.enable')
await evaluate(`location.hash = '#/coursebook'`)
await sleep(1200)
await evaluate(`(() => { const b = document.querySelector('[data-cb-settings-open]'); if (b) b.click(); return true })()`)
await sleep(700)
const facts = await evaluate(`(() => {
  const sheet = document.querySelector('[data-cb-settings-sheet]')
  if (!sheet) return { sheet: false }
  const parse = (value) => {
    const m = /rgba?\\(([^)]+)\\)/.exec(value || '')
    if (!m) return null
    const parts = m[1].split(',').map((part) => parseFloat(part.trim()))
    return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1]
  }
  const lum = (rgb) => {
    const channel = (v) => {
      const c = v / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    }
    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])
  }
  const contrast = (fg, bg) => {
    const a = lum(fg) + 0.05
    const b = lum(bg) + 0.05
    return Math.round(((Math.max(a, b) / Math.min(a, b)) * 100)) / 100
  }
  const sheetBg = parse(getComputedStyle(sheet).backgroundColor)
  const sample = (selector) => {
    const node = sheet.querySelector(selector)
    if (!node) return null
    const style = getComputedStyle(node)
    const fg = parse(style.color)
    return {
      text: (node.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 48),
      color: style.color,
      ratio: fg && sheetBg ? contrast(fg, sheetBg) : null
    }
  }
  const description = sheet.querySelector('section p')
  const inactive = [...sheet.querySelectorAll('[data-cb-settings-control="appearance"] button')].find(
    (node) => node.getAttribute('aria-pressed') !== 'true'
  )
  const inactiveFg = inactive ? parse(getComputedStyle(inactive).color) : null
  return {
    sheet: true,
    scope: sheet.closest('[data-cb-route]').getAttribute('data-cb-scope'),
    scrollHeight: sheet.scrollHeight,
    clientHeight: sheet.clientHeight,
    scrolls: sheet.scrollHeight > sheet.clientHeight,
    scrolledTo: (() => { sheet.scrollTop = sheet.scrollHeight; return sheet.scrollTop })(),
    sheetBackground: getComputedStyle(sheet).backgroundColor,
    samples: {
      heading: sample('h3'),
      description: description ? sample('section p') : null,
      inactiveSegment: inactive
        ? { text: (inactive.textContent || '').trim(), color: getComputedStyle(inactive).color, ratio: inactiveFg && sheetBg ? contrast(inactiveFg, sheetBg) : null }
        : null,
      soundLabel: (() => {
        const node = [...sheet.querySelectorAll('*')].find(
          (candidate) => (candidate.textContent || '').trim() === 'Check cue sound' && candidate.children.length === 0
        )
        if (!node) return null
        const fg = parse(getComputedStyle(node).color)
        return { color: getComputedStyle(node).color, ratio: fg && sheetBg ? contrast(fg, sheetBg) : null }
      })()
    }
  }
})()`)
console.log(JSON.stringify(facts, null, 2))
socket.close()
