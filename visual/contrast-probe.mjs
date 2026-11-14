// Dev-only measured-contrast probe. Reads what the browser actually paints.
//
// Usage: node contrast-probe.mjs <page.html> [--out result.json]
//
// The page carries the pairs to measure: every element marked `data-cb-measure` is one row.
//   data-cb-id    stable row id (e.g. "light:ink-soft-on-paper")
//   data-cb-kind  "pair" for a static token pair, "mix" for a surface the token table cannot express
//   data-cb-fg    the token role named for the foreground (informational)
//   data-cb-bg    the token role named for the background (informational)
// The probe reads `getComputedStyle(el).color` and `.backgroundColor` from Chromium and turns
// those *painted* colour strings into WCAG 2.x ratios with colorjs.io. It never reads the token
// table itself: a hand-computed ratio cannot disagree with the browser it is not asking.
//
// It never attaches to the Desktop app or a rig backend: it spawns and kills its own headless
// Chromium on a random port with a throwaway profile. Nothing here is a live-window probe.
//
// APCA is reported as an informational column only. colorjs.io's implementation is APCA 0.0.98G,
// whose constants are still draft; it is never a pass/fail gate here. `apca-w3` is deliberately
// NOT used: it is All-Rights-Reserved with patents pending, while colorjs.io is MIT.
//
// Exit codes: 0 measured, 2 usage/licence problem, 3 browser or page problem.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import Color from 'colorjs.io'

const [pagePath, ...flags] = process.argv.slice(2)
if (!pagePath) {
  console.error('usage: node contrast-probe.mjs <page.html> [--out result.json]')
  process.exit(2)
}
if (!fs.existsSync(pagePath)) {
  console.error(`contrast-probe: no such page: ${pagePath}`)
  process.exit(2)
}
const outIndex = flags.indexOf('--out')
const outPath = outIndex === -1 ? null : flags[outIndex + 1]

const CHROMIUM = process.env.CB_CHROMIUM || 'chromium'
const port = 17000 + Math.floor(Math.random() * 800)
const profileDir = fs.mkdtempSync(path.join(process.env.CB_SCRATCH || os.tmpdir(), 'cb-contrast-'))
const chromium = spawn(CHROMIUM, [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--force-device-scale-factor=1',
  `--remote-debugging-port=${port}`, `--user-data-dir=${profileDir}`, 'about:blank',
], { stdio: 'ignore' })

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
let socket = null
// Chromium keeps writing into its profile while it shuts down, so removing the tree before the
// process has exited loses a race and leaves a directory behind. Kill, wait for exit, then remove
// with retries; a dev probe must not litter the scratch dir.
const stop = async () => {
  try { socket?.close() } catch { /* already gone */ }
  try { chromium.kill('SIGKILL') } catch { /* already gone */ }
  await Promise.race([
    new Promise((resolve) => chromium.once('exit', resolve)),
    sleep(1000),
  ])
  try {
    fs.rmSync(profileDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
  } catch { /* best effort */ }
}

async function fail(code, message) {
  await stop()
  console.error(`contrast-probe: ${message}`)
  process.exit(code)
}

try {
  let targets = null
  for (let attempt = 0; attempt < 160; attempt += 1) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json()
      if (targets.length) break
    } catch { targets = null }
    await sleep(250)
  }
  if (!targets || !targets.length) await fail(3, 'chromium did not open a debugging port')
  const page = targets.find((entry) => entry.type === 'page')
  if (!page) await fail(3, 'chromium exposed no page target')

  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  let nextId = 1
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const entry = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)))
      else entry.resolve(message.result)
    }
  })
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async (expression) => {
    const answer = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (answer.exceptionDetails) throw new Error(JSON.stringify(answer.exceptionDetails))
    return answer.result.value
  }

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Emulation.setDeviceMetricsOverride', {
    width: 900, height: 1400, deviceScaleFactor: 1, mobile: false,
  })
  await send('Page.navigate', { url: `file://${pagePath}` })
  await sleep(600)
  await evaluate('document.fonts.ready.then(() => true)')
  await evaluate('new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(true))))')

  const painted = await evaluate(`(() => {
    const rows = []
    for (const el of document.querySelectorAll('[data-cb-measure]')) {
      const style = getComputedStyle(el)
      rows.push({
        id: el.getAttribute('data-cb-id'),
        kind: el.getAttribute('data-cb-kind') || 'pair',
        foreground_token: el.getAttribute('data-cb-fg'),
        background_token: el.getAttribute('data-cb-bg'),
        foreground: style.color,
        background: style.backgroundColor,
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height
      })
    }
    return { engine: navigator.userAgent, rows }
  })()`)

  const rows = painted.rows.map((row) => {
    let wcag = null
    let apca = null
    let error = null
    try {
      const background = new Color(row.background)
      const foreground = new Color(row.foreground)
      wcag = background.contrast(foreground, 'WCAG21')
      // Informational only: APCA 0.0.98G draft constants, never a gate.
      apca = background.contrastAPCA(foreground)
    } catch (exception) {
      error = String(exception && exception.message ? exception.message : exception)
    }
    return { ...row, wcag, apca, error }
  })

  const report = {
    page: path.resolve(pagePath),
    engine: painted.engine,
    apca: {
      informational: true,
      implementation: 'colorjs.io contrastAPCA (APCA 0.0.98G draft constants)',
      refused: 'apca-w3 (All Rights Reserved, patents pending)',
    },
    measurements: rows,
  }
  const text = JSON.stringify(report, null, 2)
  if (outPath) fs.writeFileSync(outPath, text)
  process.stdout.write(text)
  await stop()
} catch (exception) {
  await fail(3, String(exception && exception.stack ? exception.stack : exception))
}
