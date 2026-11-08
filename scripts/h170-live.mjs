#!/usr/bin/env node
/**
 * H-170 live proof: drive the isolated Coursebook window from the first-run plate through the
 * reordered create flow, capture 1049/900/460 and 200% text, and print what the DOM actually says.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9350'
const OUT = resolve(process.env.H170_SHOTS || 'audit/h170')

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/.test(entry.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

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
    const timer = setTimeout(() => {
      pending.delete(id)
      rej(new Error(`CDP timeout: ${method}`))
    }, timeout)
    pending.set(id, {
      res: (value) => { clearTimeout(timer); res(value) },
      rej: (error) => { clearTimeout(timer); rej(error) }
    })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evalJs = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
  return result.result?.value ?? null
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const waitFor = async (expr, ms = 15000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await evalJs(expr)) return true
    await wait(200)
  }
  return false
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, 30000)
  const path = `${OUT}/${name}.png`
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(`shot ${path}`)
  return path
}

// Calibrate an override until window.innerWidth is the target CSS width (this Electron build
// applies a ~0.896 page zoom, so the requested pixels are not the measured ones).
const setWidth = async (target) => {
  let override = target
  for (let i = 0; i < 8; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height: 900, deviceScaleFactor: 1, mobile: false })
    await wait(350)
    const measured = await evalJs('window.innerWidth')
    if (Math.abs(measured - target) <= 1) return measured
    override = Math.round((override * target) / measured)
  }
  return evalJs('window.innerWidth')
}

await send('Page.enable')
await send('Runtime.enable')

const state = () => evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const goal = document.querySelector('#cb-goal')
  const title = document.querySelector('#cb-title')
  return {
    hash: location.hash,
    step: document.querySelector('[data-cb-create-step][aria-current="step"]')?.dataset.cbCreateStep || null,
    spine: [...document.querySelectorAll('[data-cb-create-step]')].map((n) => n.textContent),
    next: document.querySelector('[data-cb-create-next]')?.textContent || null,
    heading: document.querySelector('[data-cb-route] h2')?.textContent || null,
    scopeOptions: document.querySelectorAll('[data-cb-scope-option]').length,
    goalValue: goal ? goal.value : null,
    titleValue: title ? title.value : null,
    titleInput: !!title,
    continueDisabled: (() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Continue'); return b ? b.disabled : null })(),
    describedBy: (() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === 'Continue'); return b ? b.getAttribute('aria-describedby') : null })(),
    overflow: route ? { scrollWidth: route.scrollWidth, clientWidth: route.clientWidth } : null,
    innerWidth: window.innerWidth,
    rootFont: getComputedStyle(document.documentElement).fontSize
  }
})()`)

const setValue = (selector, value) => evalJs(`(() => {
  const el = document.querySelector(${JSON.stringify(selector)})
  if (!el) return false
  const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)})
  el.dispatchEvent(new Event('input', { bubbles: true }))
  return true
})()`)

const clickText = (text) => evalJs(`(() => {
  const el = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === ${JSON.stringify(text)})
  if (!el) return false
  el.click()
  return true
})()`)

const report = { steps: [] }

// The plate -> create flow.
if (!(await evalJs("!!document.querySelector('[data-cb-create-spine]')"))) {
  const started = await clickText('Start with a goal')
  report.started = started
  await waitFor("!!document.querySelector('[data-cb-create-spine]')")
}

report.plateClaim = await evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return route ? route.innerText.split('\\n').filter(Boolean).slice(-6) : null
})()`)

// Reset the window to its widest so each measurement starts from the same layout.
await setWidth(1049)
await wait(400)

report.steps.push({ label: 'fresh-step1', ...(await state()) })

// The title follows the goal until edited.
await setValue('#cb-goal', 'Fix a flat tyre on my bike without help')
await wait(400)
report.afterGoal = await state()

for (const width of [1049, 900, 460]) {
  const measured = await setWidth(width)
  await wait(500)
  await shot(`h170-step1-goal-${width}`)
  report.steps.push({ label: `step1-${width}`, measured, ...(await state()) })
}

// 200% text at the narrow and wide widths.
for (const width of [1049, 460]) {
  await setWidth(width)
  await evalJs("document.documentElement.style.setProperty('font-size','32px','important')")
  await wait(500)
  await shot(`h170-step1-goal-${width}-text200`)
  report.steps.push({ label: `step1-${width}-text200`, ...(await state()) })
  await evalJs("document.documentElement.style.removeProperty('font-size')")
  await wait(300)
}

await setWidth(1049)
await wait(300)

// Continue on the goal step, then measure the size step.
report.continueClicked = await clickText('Continue')
await wait(700)
report.steps.push({ label: 'step2-size', ...(await state()) })
for (const width of [1049, 900, 460]) {
  const measured = await setWidth(width)
  await wait(500)
  await shot(`h170-step2-size-${width}`)
  report.steps.push({ label: `step2-${width}`, measured, ...(await state()) })
}
for (const width of [1049, 460]) {
  await setWidth(width)
  await evalJs("document.documentElement.style.setProperty('font-size','32px','important')")
  await wait(500)
  await shot(`h170-step2-size-${width}-text200`)
  report.steps.push({ label: `step2-${width}-text200`, ...(await state()) })
  await evalJs("document.documentElement.style.removeProperty('font-size')")
  await wait(300)
}

// Back keeps the goal text; the size step's Continue stays disabled until a scope is chosen.
await setWidth(1049)
await wait(300)
report.scopeClicked = await evalJs(`(() => {
  const el = document.querySelector('[data-cb-scope-option="short"]')
  if (!el) return false
  el.click()
  return true
})()`)
await wait(400)
report.steps.push({ label: 'step2-size-chosen', ...(await state()) })
report.backClicked = await clickText('Back')
await wait(600)
report.steps.push({ label: 'back-on-goal', ...(await state()) })

writeFileSync(`${OUT}/h170-live.json`, JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
socket.close()
