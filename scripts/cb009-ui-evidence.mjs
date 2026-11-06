#!/usr/bin/env node
/**
 * CB-009 UI evidence run: drive the real Desktop window through the learning workspace and write
 * every screenshot plus a step trace. Nothing here fabricates backend state — each step reads the
 * rendered DOM after an action and records what it saw.
 *
 *   CB009_CDP_PORT=9222 node scripts/cb009-ui-evidence.mjs
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB009_CDP_PORT || '9222'
const SHOTS = 'docs/cb009-shots'
const trace = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target')
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
const shot = async (name) => {
  const data = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const path = resolve(`${SHOTS}/${name}.png`)
  mkdirSync(SHOTS, { recursive: true })
  writeFileSync(path, Buffer.from(data.data, 'base64'))
  return path
}
const record = async (step, extra = {}) => {
  const state = await evaluate(`(() => {
    const t = document.body.innerText || ''
    const active = document.activeElement
    return {
      hash: location.hash,
      focused: active ? (active.getAttribute('aria-label') || (active.innerText || '').trim().slice(0, 60) || active.id || active.tagName) : null,
      hasDialog: Boolean(document.querySelector('[role=dialog]')),
      tail: t.slice(-320).replace(/\\n+/g, ' | ')
    }
  })()`)
  trace.push({ step, ...extra, ...state })
  console.log(step, JSON.stringify({ ...extra, hasDialog: state.hasDialog }))
}
const clickText = (text, index = 0) =>
  evaluate(`(() => {
    const all = [...document.querySelectorAll('button')].filter((b) => (b.innerText || '').trim() === ${JSON.stringify(text)})
    const b = all[${index}]
    if (!b) return 'missing:${text}'
    b.click()
    return 'clicked:${text}'
  })()`)
const setValue = (selector, value) =>
  evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)})
    if (!el) return 'missing:${selector}'
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)})
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return 'set:${selector}'
  })()`)
const openSection = (title) =>
  evaluate(`(() => {
    const nodes = [...document.querySelectorAll('div')].filter((e) => e.className && String(e.className).includes('break-words') && e.textContent.trim() === ${JSON.stringify(title)})
    if (!nodes.length) {
      const buttons = [...document.querySelectorAll('button')].filter((b) => b.innerText.trim() === 'Open section')
      if (!buttons.length) return 'title-missing'
      buttons[1].click()
      return 'opened-by-index'
    }
    let row = nodes[0]
    for (let i = 0; i < 8 && row; i++, row = row.parentElement) {
      const b = row.querySelector('button')
      if (b) { b.click(); return 'opened' }
    }
    return 'no-button'
  })()`)
const waitFor = async (expression, label, timeoutMs = 20000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) return true
    await sleep(400)
  }
  throw new Error('timeout: ' + label)
}

await send('Page.enable')
await send('Runtime.enable')

// ── 1. route → course detail → every view ───────────────────────────────────
await evaluate(`location.hash = '#/coursebook'`)
await sleep(2500)
record('route-mounted')
console.log(await clickText('Open'))
await sleep(2200)
await shot('08-course-detail-overview')
await record('course-detail-overview')

for (const view of ['Textbook', 'Notebook', 'Quizzes', 'Plan', 'Evidence', 'Sources']) {
  console.log(await clickText(view))
  await sleep(1500)
  await shot(`09-view-${view.toLowerCase()}`)
  await record(`view-${view.toLowerCase()}`, { hasBody: await evaluate(`(document.body.innerText || '').length > 1200`) })
}

// ── 2. section page: non-current section must load its own lesson.page ──────
console.log(await clickText('Textbook'))
await sleep(1200)
const opened = await openSection('Choose the polite expression for a first confession')
await waitFor(`/TEACHING SEGMENTS/.test(document.body.innerText || '')`, 'section page')
await shot('10-section-page-detached')
await record('section-page', { opened, checkVisible: await evaluate(`/CURRENT CHECK/.test(document.body.innerText)`) })

// ── 3. notebook save from a teaching segment ───────────────────────────────
console.log(await clickText('Save to notebook'))
await sleep(700)
await shot('11-notebook-save-dialog')
await record('notebook-dialog')
await setValue('#cb-note-note', 'Daisuki / aishiteru: warmth and intimacy sit above suki desu in weight.')
await setValue('#cb-note-tags', 'polite, intimacy, lesson2')
await sleep(200)
await evaluate(`(() => { const d = document.querySelector('[role=dialog]'); const b = [...d.querySelectorAll('button')].find((x) => x.innerText.trim() === 'Save to notebook'); b.click(); return 'saved' })()`)
await sleep(2500)
await record('notebook-save-submitted', { dialogClosed: await evaluate(`!document.querySelector('[role=dialog]')`) })

// ── 4. notebook: list, edit, tag filter, search, filtered-empty ─────────────
console.log(await clickText('Notebook'))
await sleep(1800)
await shot('12-notebook-list')
await record('notebook-list', { entries: await evaluate(`document.body.innerText.split('Open in textbook').length - 1`) })

console.log(await clickText('Edit note and tags'))
await sleep(500)
await shot('13-notebook-edit')
await record('notebook-edit-open', { noteValue: await evaluate(`(document.querySelector('#cb-edit-note') || {}).value`) })
await setValue('#cb-edit-note', 'Suki desu: the polite choice for a respected, not-yet-close addressee (reviewed).')
await setValue('#cb-edit-tags', 'polite, first-confession, reviewed')
await sleep(200)
console.log(await clickText('Save changes'))
await sleep(2200)
await shot('14-notebook-edited')
await record('notebook-edit-saved', {
  formClosed: await evaluate(`!document.querySelector('#cb-edit-note')`),
  updated: await evaluate(`(document.body.innerText || '').includes('reviewed')`)
})

// tag filter (Radix select)
await evaluate(`(() => { const t = document.querySelector('[aria-label="Filter by tag"]'); if (!t) return 'no-trigger'; t.click(); return 'open' })()`)
await sleep(500)
await shot('15-notebook-tag-menu')
const tagClick = await evaluate(`(() => {
  const item = [...document.querySelectorAll('[role=option]')].find((e) => e.innerText.trim() === 'reviewed')
  if (!item) return 'no-option'
  item.click()
  return 'picked'
})()`)
await sleep(1200)
await shot('16-notebook-tag-filter')
await record('notebook-tag-filter', {
  tagClick,
  rows: await evaluate(`document.body.innerText.split('Open in textbook').length - 1`)
})

// search → no match → honest clear
await setValue('input[aria-label="Search the notebook"]', 'zzz-no-such-note')
await sleep(900)
await shot('17-notebook-search-empty')
await record('notebook-search-empty', { empty: await evaluate(`(document.body.innerText || '').includes('No saved moment matches')`) })
console.log(await clickText('Clear search and tag'))
await sleep(1000)
await record('notebook-search-cleared', { restored: await evaluate(`!document.body.innerText.includes('No saved moment matches')`) })

// ── 5. continue from here → the exact section ──────────────────────────────
await setValue('input[aria-label="Search the notebook"]', 'polite')
await sleep(900)
console.log(await clickText('Continue from here'))
await sleep(3000)
await shot('18-continue-from-here')
await record('continue-from-here', {
  sectionLoaded: await evaluate(`/TEACHING SEGMENTS/.test(document.body.innerText)`),
  title: await evaluate(`(() => { const t = document.body.innerText; const i = t.indexOf('TEACHING SEGMENTS'); return i > -1 ? t.slice(Math.max(0, i - 300), i).split('\\n').filter(Boolean).slice(-4) : [] })()`)
})

// ── 6. quizzes: review, new version, dispute ───────────────────────────────
console.log(await clickText('Quizzes'))
await sleep(1800)
await shot('19-quizzes-list')
await record('quizzes-list', { attempts: await evaluate(`document.body.innerText.split('Open attempt').length - 1`) })
console.log(await clickText('Open attempt'))
await sleep(900)
await shot('20-quiz-review')
await record('quiz-review', {
  readOnlyCopy: await evaluate(`(document.body.innerText || '').includes('Reviewing is read-only')`),
  disputeField: await evaluate(`Boolean(document.querySelector('#cb-dispute'))`)
})
await setValue('#cb-dispute', 'The criterion observed only half of my answer; the register explanation was present in sentence two.')
await sleep(300)
console.log(await clickText('Record dispute'))
await sleep(2400)
await shot('21-quiz-dispute')
await record('quiz-dispute', {
  history: await evaluate(`(document.body.innerText || '').includes('DISPUTE HISTORY')`),
  notice: await evaluate(`(document.body.innerText || '').includes('Dispute recorded')`)
})
console.log(await clickText('Try a new version'))
await sleep(2500)
await shot('22-quiz-new-version')
await record('quiz-new-version', {
  notice: await evaluate(`(document.body.innerText || '').includes('new audited version')`),
  error: await evaluate(`(() => { const t = document.body.innerText; const i = t.indexOf('VALIDATION_FAILED'); const j = t.indexOf('STALE_REVISION'); return i > -1 || j > -1 ? t.slice(Math.max(i, j) - 20, Math.max(i, j) + 160) : null })()`)
})

// ── 7. narrow width (460) and 200% text ────────────────────────────────────
await send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await sleep(900)
await shot('23-narrow-quiz-review')
await record('narrow-view', { width: await evaluate('innerWidth'), picker: await evaluate(`Boolean(document.querySelector('#cb-view-picker'))`) })
console.log(await clickText('Textbook'))
await sleep(1200)
await shot('24-narrow-textbook')
await send('Emulation.clearDeviceMetricsOverride')
await sleep(600)

await evaluate(`document.documentElement.style.fontSize = '200%'`)
await sleep(1200)
await shot('25-text-200')
await record('text-200', { rootFontSize: await evaluate(`getComputedStyle(document.documentElement).fontSize`) })
await evaluate(`document.documentElement.style.fontSize = ''`)
await sleep(600)

// ── 8. accessibility snapshot ─────────────────────────────────────────────
const a11y = await evaluate(`(() => {
  const buttons = [...document.querySelectorAll('button')].filter((b) => b.offsetParent !== null)
  const nameless = buttons.filter((b) => !((b.innerText || '').trim() || b.getAttribute('aria-label')))
  const fields = [...document.querySelectorAll('input,textarea,[role=combobox]')].filter((e) => e.offsetParent !== null)
  const unlabelled = fields.filter((e) => {
    if (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby')) return false
    if (e.id) { const l = document.querySelector('label[for="' + e.id + '"]'); if (l) return false }
    return true
  })
  const headings = [...document.querySelectorAll('h1,h2,h3')].map((h) => h.tagName + ':' + h.innerText.trim().slice(0, 50))
  return {
    visibleButtons: buttons.length,
    namelessButtons: nameless.map((b) => b.outerHTML.slice(0, 90)),
    visibleFields: fields.length,
    unlabelledFields: unlabelled.map((e) => e.tagName + '#' + e.id),
    headings,
    focusRingClasses: (() => { const b = buttons[0]; return b ? /focus-visible:ring/.test(b.className) : null })()
  }
})()`)
trace.push({ step: 'a11y-snapshot', a11y })
console.log('a11y-snapshot', JSON.stringify(a11y).slice(0, 400))

const path = resolve('docs/REVIEW_CB009-ui-trace.json')
writeFileSync(path, JSON.stringify({ capturedAt: new Date().toISOString(), steps: trace }, null, 2))
console.log('trace:', path, trace.length, 'steps')
socket.close()
