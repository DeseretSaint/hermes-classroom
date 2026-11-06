#!/usr/bin/env node
/**
 * CB-009 phase 2: resume an already-bound chat, open its check from the section page, answer in the
 * Coursebook pane, and capture the verdict. This is the "return to a past section" path: the chat
 * keeps its stored id, the pane reads the binding for exactly that id, and the attempt is created
 * once for that check.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-pane-check.mjs <stored-session-id> [sectionIndex] [prefix]
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9222'
const sessionId = process.argv[2]
const sectionIndex = Number(process.argv[3] ?? '0')
const prefix = process.argv[4] || 'docs/cb009-shots/pane'
const ANSWER =
  process.env.CB009_ANSWER ||
  'The addressee is someone I respect but am not close to, and the setting is private, so polite teineigo fits; the same words to a close friend in public would switch to plain casual form.'
if (!sessionId) throw new Error('usage: cb009-pane-check.mjs <stored-session-id> [sectionIndex] [prefix]')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
const socket = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true })
  socket.addEventListener('error', rej, { once: true })
})
let nextId = 1
const pending = new Map()
socket.addEventListener('message', (event) => {
  const m = JSON.parse(event.data)
  if (m.id && pending.has(m.id)) {
    const { resolve: r, reject } = pending.get(m.id)
    pending.delete(m.id)
    if (m.error) reject(new Error(JSON.stringify(m.error)))
    else r(m.result)
  }
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params }))
  })
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result?.value
}
const waitUntil = async (expression, label, timeoutMs = 30000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(400)
  }
  throw new Error('timeout: ' + label)
}
const clickText = (text) =>
  evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === ${JSON.stringify(text)}); if (!b) return 'missing'; b.click(); return 'clicked' })()`)
const shot = async (name) => {
  const path = resolve(`${prefix}-${name}.png`)
  const data = await send('Page.captureScreenshot', { format: 'png' })
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const state = () =>
  evaluate(`(() => {
    const t = document.body.innerText || ''
    const at = t.indexOf('COURSEBOOK')
    return {
      hash: location.hash,
      paneBound: /COURSEBOOK/.test(t) && !/No durable chat yet/.test(t) && !/Not a Coursebook lesson/.test(t),
      phases: [
        /chat binding is detached/.test(t) ? 'detached' : null,
        /CURRENT CHECK/.test(t) ? 'check' : null,
        /I couldn.t grade this attempt/.test(t) ? 'needs_retry' : null,
        /Access granted/.test(t) ? 'overridden' : null,
        /ATTEMPTS ON THIS SECTION|Passed|Partly there|Not yet/.test(t) ? 'graded' : null
      ].filter(Boolean),
      hasAnswer: !!document.querySelector('#cb-attempt-answer'),
      answerDisabled: (document.querySelector('#cb-attempt-answer') || {}).disabled,
      submitDisabled: (() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Submit answer'); return b ? b.disabled : null })(),
      pane: at < 0 ? '' : t.slice(at, at + 1400)
    }
  })()`)
const log = async (label, extra = {}) => {
  const entry = { step: label, ...(await state()), ...extra }
  console.log(JSON.stringify(entry))
  return entry
}

await send('Page.enable')
await send('Runtime.enable')
const trace = { startedAt: new Date().toISOString(), sessionId, sectionIndex, steps: [], shots: [] }
if (!(await evaluate(`!!document.querySelector('[aria-label="Hide right sidebar"]')`))) {
  await evaluate(`(() => { const b = document.querySelector('[aria-label="Show right sidebar"]'); if (b) b.click(); return true })()`)
  await sleep(900)
}

// 1. resume the bound chat by its stored id
await evaluate(`location.hash = ${JSON.stringify('#/' + sessionId)}`)
await sleep(2800)
trace.steps.push(await log('resume-chat'))
trace.shots.push(await shot('10-resumed-chat'))

// 2. open the section so the backend opens (or returns) its check
await evaluate(`location.hash = '#/'`)
await sleep(500)
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2200)
if ((await clickText('Open')) === 'missing') {
  await clickText('Courses')
  await sleep(1200)
  if ((await clickText('Open')) === 'missing') throw new Error('no course row')
}
await sleep(2000)
if ((await clickText('Textbook')) === 'missing') throw new Error('no Textbook view tab')
await sleep(1600)
if ((await clickText('All sections')) === 'clicked') await sleep(1200)
const opened = await evaluate(`(() => {
  const buttons = [...document.querySelectorAll('button')].filter(b => b.innerText.trim() === 'Open section')
  const b = buttons[${sectionIndex}]
  if (!b) return 'no-open-section'
  b.click()
  return 'clicked'
})()`)
if (opened !== 'clicked') throw new Error('open section: ' + opened)
await waitUntil(`(() => { const t = document.body.innerText || ''; return /CURRENT CHECK/.test(t) })()`, 'section page')
await sleep(1500)
trace.steps.push(await log('section-page'))
trace.shots.push(await shot('11-section-page-bound'))

// 3. back in the chat: the pane must now show the open check for this same section
await evaluate(`location.hash = ${JSON.stringify('#/' + sessionId)}`)
await sleep(2600)
await waitUntil(`!!document.querySelector('#cb-attempt-answer') || /no open check/i.test(document.body.innerText)`, 'pane check', 25000)
await sleep(800)
trace.steps.push(await log('pane-check'))
trace.shots.push(await shot('12-pane-check'))

// 4. answer in the pane
if (await evaluate(`!!document.querySelector('#cb-attempt-answer')`)) {
  await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.scrollIntoView({block:'center'}); el.focus(); return true })()`)
  await send('Input.insertText', { text: ANSWER })
  await sleep(350)
  trace.shots.push(await shot('13-pane-answer-typed'))
  trace.steps.push(await log('pane-typed'))
  if ((await clickText('Submit answer')) === 'clicked') {
    const startedAt = Date.now()
    while (Date.now() - startedAt < 90000) {
      const s = await state()
      if (s.phases.some((p) => ['graded', 'needs_retry', 'overridden'].includes(p))) break
      await sleep(600)
    }
    await sleep(900)
    trace.shots.push(await shot('14-pane-verdict'))
    trace.steps.push(await log('pane-verdict'))
  }
}

// 5. narrow and 200% text with the pane open
await send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await sleep(900)
trace.shots.push(await shot('15-narrow-chat-pane'))
trace.steps.push(await log('narrow'))
await send('Emulation.clearDeviceMetricsOverride')
await evaluate(`document.documentElement.style.fontSize = '32px'`)
await sleep(700)
trace.shots.push(await shot('16-text200-chat-pane'))
trace.steps.push(await log('text200'))
await evaluate(`document.documentElement.style.fontSize = ''`)

writeFileSync(resolve('docs/REVIEW_CB009-pane-check.json'), JSON.stringify(trace, null, 2))
console.log(JSON.stringify({ done: true, shots: trace.shots.length, last: trace.steps.at(-1)?.phases }, null, 2))
socket.close()
