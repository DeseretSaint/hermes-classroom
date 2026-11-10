#!/usr/bin/env node
/**
 * CP-000 — cold route paint timing for the current module.
 *
 * Reloads the page with an empty cache, then polls until `[data-cb-route]` is present and has a
 * non-zero box. The number is wall-clock from the reload acknowledgement to that first route box,
 * which includes module re-evaluation, host boot and the first RPC-driven paint. Run it 3+ times
 * and record the median as the v3 baseline.
 *
 *   node scripts/cp-cold-paint.mjs --cdp-port 9471 [--runs 3] [--out <file.json>]
 */
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const args = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const index = args.indexOf(`--${name}`)
  if (index < 0) return fallback
  return args[index + 1] && !args[index + 1].startsWith('--') ? args[index + 1] : true
}
const port = String(flag('cdp-port', process.env.CB015_CDP_PORT || '9337'))
const runs = Number(flag('runs', 3))
const out = flag('out', null)
const sleep = (ms) => new Promise((done) => setTimeout(done, ms))

const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
const page = targets.find((entry) => entry.type === 'page' && /Hermes/i.test(entry.title || '')) || targets.find((entry) => entry.type === 'page')
if (!page) throw new Error(`no page target on ${port}`)
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((done, fail) => {
  socket.addEventListener('open', done, { once: true })
  socket.addEventListener('error', fail, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id && pending.has(message.id)) {
    const { done, fail } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) fail(new Error(JSON.stringify(message.error)))
    else done(message.result)
  }
})
const send = (method, params = {}) => new Promise((done, fail) => {
  const id = nextId++
  pending.set(id, { done, fail })
  socket.send(JSON.stringify({ id, method, params }))
})
const evaluate = async (expression) => {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
  return result.result.value
}

await send('Page.enable')
await send('Runtime.enable')

const samples = []
for (let run = 0; run < runs; run += 1) {
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(300)
  const oldOrigin = await evaluate(`performance.timeOrigin`)
  const started = Date.now()
  await send('Page.reload', { ignoreCache: true })
  let elapsed = null
  let newDocument = false
  for (let attempt = 0; attempt < 800; attempt += 1) {
    const state = await evaluate(`(() => {
      if (performance.timeOrigin === ${oldOrigin}) return { fresh: false, route: null }
      const root = document.querySelector('[data-cb-route]')
      const rect = root ? root.getBoundingClientRect() : null
      return { fresh: true, route: rect && rect.width > 0 && rect.height > 0 ? { width: rect.width, height: rect.height } : null }
    })()`)
    if (state.fresh) newDocument = true
    if (state.fresh && !state.route && attempt % 8 === 0) {
      await evaluate(`location.hash = '#/coursebook'`).catch(() => {})
    }
    if (state.fresh && state.route) { elapsed = Date.now() - started; samples.push({ run: run + 1, ms: elapsed, ...state.route }); break }
    await sleep(15)
  }
  if (elapsed === null) samples.push({ run: run + 1, ms: null, new_document: newDocument })
  await sleep(500)
}

const values = samples.map((sample) => sample.ms).filter((value) => typeof value === 'number').sort((a, b) => a - b)
const median = values.length ? values[Math.floor(values.length / 2)] : null
const result = {
  tool: 'scripts/cp-cold-paint.mjs',
  captured_at: new Date().toISOString(),
  cdp_port: port,
  measured: '[data-cb-route] present with a non-zero box after Page.reload(ignoreCache)',
  samples,
  median_ms: median,
  min_ms: values[0] ?? null,
  max_ms: values[values.length - 1] ?? null
}
if (out) writeFileSync(resolve(String(out)), `${JSON.stringify(result, null, 2)}\n`)
console.log(JSON.stringify(result, null, 2))
socket.close()
