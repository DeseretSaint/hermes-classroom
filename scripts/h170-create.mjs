#!/usr/bin/env node
// H-170 live proof, second half: reach Review only with a goal + scope, then press Create once and
// read the real ids the backend returned.
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9350'
const OUT = resolve(process.env.H170_SHOTS || 'audit/h170')

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
const send = (method, params = {}, timeout = 25000) =>
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
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const path = `${OUT}/${name}.png`
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(png.data, 'base64'))
  console.log(`shot ${path}`)
}

await send('Runtime.enable')
await send('Page.enable')
await send('Emulation.setDeviceMetricsOverride', { width: 1049, height: 900, deviceScaleFactor: 1, mobile: false })
await wait(600)

const report = {}
report.stepBefore = await evalJs(`document.querySelector('[data-cb-create-step][aria-current="step"]')?.dataset.cbCreateStep`)
report.continueToReview = await clickText('Continue')
await wait(800)
report.review = await evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const text = route ? route.innerText : ''
  return {
    step: document.querySelector('[data-cb-create-step][aria-current="step"]')?.dataset.cbCreateStep || null,
    heading: route?.querySelector('h2')?.textContent || null,
    hasGoal: text.includes('Fix a flat tyre on my bike without help'),
    hasScope: text.includes('A short course'),
    hasCreate: [...document.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Create course'),
    body: text.split('\\n').filter(Boolean).slice(-14)
  }
})()`)
await shot('h170-step3-review-1049')

report.createClicked = await clickText('Create course')
// The job line reads a real backend; give it time to answer.
for (let i = 0; i < 30; i += 1) {
  await wait(1000)
  const done = await evalJs("!!document.querySelector('[data-cb-create-receipt]') || !!document.querySelector('[data-cb-action][data-cb-state=\"disabled\"]') === false && !!document.querySelector('*')?.textContent?.includes('Your plan is being researched')")
  if (done) break
}
await wait(1500)
report.result = await evalJs(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const text = route ? route.innerText : ''
  const receipt = document.querySelector('[data-cb-create-receipt]')
  if (receipt) receipt.open = true
  const rows = receipt ? [...receipt.querySelectorAll('div')].map((d) => d.textContent.trim()).filter((t) => /^(Course|Plan|Enrolment|Plan job)/.test(t)) : []
  return { lead: text.split('\\n').filter(Boolean).slice(0, 6), receipt: rows, error: route ? (route.innerText.match(/[A-Z_]{4,}:.*/) || [])[0] || null : null }
})()`)
await shot('h170-step3-created-1049')
writeFileSync(`${OUT}/h170-create.json`, JSON.stringify(report, null, 2))
console.log(JSON.stringify(report, null, 2))
socket.close()
