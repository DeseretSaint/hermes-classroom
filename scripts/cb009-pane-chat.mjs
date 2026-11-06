#!/usr/bin/env node
/**
 * CB-009: the bound lesson chat + Coursebook context pane, end to end in the real window.
 *
 * Path: detached section -> Start a fresh run (arms the exact run) -> one real chat turn (the pane
 * binds by the chat's stored id) -> open the section so the backend opens its check -> back in the
 * bound chat, answer in the PANE -> verdict. Every click is a real DOM click on a labelled control;
 * the chat message and the answer are typed with Input.insertText and sent with a real Enter key.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-pane-chat.mjs [sectionIndex] [prefix]
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9222'
const sectionIndex = Number(process.argv[2] ?? '0')
const prefix = process.argv[3] || 'docs/cb009-shots/pane'
const CHAT_MESSAGE =
  process.env.CB009_CHAT_MESSAGE ||
  'I am ready for this section. Remind me what the difference is between casual and polite affection, then give me the check.'
const ANSWER =
  process.env.CB009_ANSWER ||
  'The addressee is someone I respect but am not close to, and the setting is private, so polite teineigo fits; the same words to a close friend in public would switch to plain casual form.'

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
      rightSidebar: !!document.querySelector('[aria-label="Hide right sidebar"]'),
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
      pane: at < 0 ? '' : t.slice(at, at + 1200)
    }
  })()`)
const log = async (label, extra = {}) => {
  const entry = { step: label, ...(await state()), ...extra }
  console.log(JSON.stringify(entry))
  return entry
}

await send('Page.enable')
await send('Runtime.enable')
const trace = { startedAt: new Date().toISOString(), sectionIndex, steps: [], shots: [] }

/** Course list -> course detail -> Textbook -> the section page. */
const openSectionPage = async (index, label) => {
  await evaluate(`location.hash = '#/'`)
  await sleep(500)
  await evaluate(`location.hash = '#/coursebook'`)
  await sleep(2200)
  trace.steps.push(await log(`${label}-route`))
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
    const b = buttons[${index}]
    if (!b) return 'no-open-section'
    b.click()
    return 'clicked'
  })()`)
  if (opened !== 'clicked') throw new Error('open section: ' + opened)
  await waitUntil(`(() => { const t = document.body.innerText || ''; return /CURRENT CHECK/.test(t) || /binding is detached/.test(t) })()`, 'section page')
  await sleep(1200)
  trace.steps.push(await log(`${label}-section`))
}

// 0. right rail visible — the pane lives there, next to the transcript
if (!(await evaluate(`!!document.querySelector('[aria-label="Hide right sidebar"]')`))) {
  await evaluate(`(() => { const b = document.querySelector('[aria-label="Show right sidebar"]'); if (b) b.click(); return true })()`)
  await sleep(900)
}

// 1. the detached section
await openSectionPage(sectionIndex, 'start')
trace.shots.push(await shot('01-section-detached'))

// 2. arm the exact run and open the chat it starts
if ((await clickText('Start a fresh run')) === 'missing') {
  const started = await evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim().startsWith('New session')); if (!b) return 'missing'; b.click(); return 'clicked' })()`)
  if (started === 'missing') throw new Error('neither Start a fresh run nor New session is available')
}
await waitUntil(`!!document.querySelector('[contenteditable="true"]')`, 'chat composer', 30000)
await sleep(1500)
trace.steps.push(await log('fresh-chat'))

// 3. one real chat turn: focus the composer, type, Enter
await evaluate(`(() => { const el = document.querySelector('[contenteditable="true"]'); el.focus(); return true })()`)
await send('Input.insertText', { text: CHAT_MESSAGE })
await sleep(350)
const composerText = await evaluate(`(document.querySelector('[contenteditable="true"]') || {}).innerText`)
for (const type of ['keyDown', 'keyUp']) {
  await send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: type === 'keyDown' ? '\r' : undefined })
}
trace.steps.push({ step: 'chat-sent', composerText })
const deadline = Date.now() + 300000
let previous = ''
let stableSince = 0
while (Date.now() < deadline) {
  const current = await evaluate(`(document.body.innerText || '').length`)
  if (current === previous) {
    if (!stableSince) stableSince = Date.now()
    if (Date.now() - stableSince > 9000) break
  } else {
    stableSince = 0
    previous = current
  }
  await sleep(1000)
}
await sleep(1500)
trace.shots.push(await shot('02-bound-chat-pane'))
const bound = await log('after-turn')
trace.steps.push(bound)
const chatHash = bound.hash

// 3b. a fresh run has no check until the section asks for one; do that, then come back to the chat
if (!bound.hasAnswer) {
  await openSectionPage(sectionIndex, 'check-open')
  await evaluate(`location.hash = ${JSON.stringify(chatHash)}`)
  await sleep(2500)
  await waitUntil(`!!document.querySelector('#cb-attempt-answer') || /no open check/i.test(document.body.innerText)`, 'pane check', 20000)
  await sleep(800)
  trace.shots.push(await shot('03-bound-chat-check'))
  trace.steps.push(await log('pane-check'))
}

// 4. answer from the pane, not from the route
if (await evaluate(`!!document.querySelector('#cb-attempt-answer')`)) {
  await evaluate(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.scrollIntoView({block:'center'}); el.focus(); return true })()`)
  await send('Input.insertText', { text: ANSWER })
  await sleep(350)
  trace.shots.push(await shot('04-pane-answer-typed'))
  trace.steps.push(await log('pane-typed'))
  if ((await clickText('Submit answer')) === 'clicked') {
    const startedAt = Date.now()
    let last = null
    while (Date.now() - startedAt < 90000) {
      last = await state()
      if (last.phases.some((p) => ['graded', 'needs_retry', 'overridden'].includes(p))) break
      await sleep(600)
    }
    await sleep(800)
    trace.shots.push(await shot('05-pane-verdict'))
    trace.steps.push(await log('pane-verdict'))
  }
}

// 5. the same state at 460px and at 200% text
await send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await sleep(900)
trace.shots.push(await shot('06-bound-chat-narrow'))
trace.steps.push(await log('narrow'))
await send('Emulation.clearDeviceMetricsOverride')
await evaluate(`document.documentElement.style.fontSize = '32px'`)
await sleep(700)
trace.shots.push(await shot('07-bound-chat-text200'))
trace.steps.push(await log('text200'))
await evaluate(`document.documentElement.style.fontSize = ''`)

const identity = await evaluate(`(() => ({
  hash: location.hash,
  pane: (() => { const t = document.body.innerText || ''; const at = t.indexOf('COURSEBOOK'); return at < 0 ? '' : t.slice(at, at + 500) })()
}))()`)

writeFileSync(resolve('docs/REVIEW_CB009-pane-chat.json'), JSON.stringify({ ...trace, identity }, null, 2))
console.log(JSON.stringify({ done: true, hash: identity.hash, shots: trace.shots.length, lastPhases: trace.steps.at(-1)?.phases }, null, 2))
socket.close()
