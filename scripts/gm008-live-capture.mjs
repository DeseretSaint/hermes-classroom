#!/usr/bin/env node
/**
 * GM-008 — drive the isolated Desktop window and capture the homework proof.
 *
 * Real window, real backend (cb.rpc v24), real Page.captureScreenshot. The task is proposed by the
 * shipped `homework.create` through the shipped UI; the sheet on screen is the backend's
 * `homework.read` answer; the report and the notebook list are the backend's rows.
 *
 *   CB015_CDP_PORT=9361 COURSEBOOK_TEST_STATE=~/.hermes/coursebook-test-gm008 \
 *     node scripts/gm008-live-capture.mjs
 */
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { connect } from './cb015-lib.mjs'

const OUT = resolve('docs/visual-review/gm-008')
mkdirSync(OUT, { recursive: true })
const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const withTimeout = (promise, ms, label) =>
  Promise.race([promise, new Promise((_, fail) => setTimeout(() => fail(new Error(`timeout: ${label}`)), ms))])

let cdp = null
const open = async () => {
  cdp = await connect()
  await withTimeout(cdp.send('Page.enable', {}), 20000, 'Page.enable')
  await withTimeout(cdp.send('Runtime.enable', {}), 20000, 'Runtime.enable')
}
const send = async (method, params = {}) => withTimeout(cdp.send(method, params), 60000, method)
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text)
  return r.result.value
}
const waitFor = async (expression, label, timeout = 30000) => {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    try { if (await evaluate(`Boolean(${expression})`)) return true } catch { /* retry */ }
    await wait(150)
  }
  throw new Error(`timed out: ${label}`)
}
const clickText = async (text, scope = 'document') => {
  const clicked = await evaluate(`(() => {
    const root = ${scope}
    const node = [...root.querySelectorAll('button, a')].find(
      (candidate) => candidate.innerText.trim().toLowerCase() === ${JSON.stringify(text.toLowerCase())}
    )
    if (!node) return false
    node.click()
    return true
  })()`)
  if (!clicked) throw new Error(`no control with text ${text}`)
  return clicked
}
const clickAny = async (texts) => {
  for (const text of texts) {
    const clicked = await evaluate(`(() => {
      const node = [...document.querySelectorAll('button, a')].find(
        (candidate) => candidate.innerText.trim().toLowerCase() === ${JSON.stringify(text.toLowerCase())}
      )
      if (!node) return false
      node.click()
      return true
    })()`)
    if (clicked) return text
  }
  throw new Error(`no control with any of ${texts.join(' / ')}`)
}
const frames = []
const state = async () => ({
  hash: await evaluate('location.hash'),
  innerWidth: await evaluate('window.innerWidth'),
  rootFont: await evaluate("getComputedStyle(document.documentElement).fontSize"),
  overflow: await evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'),
  homework: await evaluate("document.querySelector('[data-cb-homework]')?.getAttribute('data-cb-homework') || null"),
  panel: await evaluate("document.querySelector('[data-cb-homework-panel]')?.getAttribute('data-cb-homework-panel') || null"),
  sheetState: await evaluate("document.querySelector('[data-cb-homework-sheet]')?.getAttribute('data-cb-homework-state') || null"),
  completion: await evaluate("document.querySelector('[data-cb-homework-completion]')?.getAttribute('data-cb-homework-completion') || null"),
  record: await evaluate("document.querySelector('[data-cb-homework-record]')?.getAttribute('data-cb-homework-record') || null"),
  list: await evaluate("document.querySelector('[data-cb-homework-list]')?.getAttribute('data-cb-homework-list') || null"),
  studio: await evaluate("document.querySelector('[data-cb-homework-studio]')?.getAttribute('data-cb-homework-studio') || null"),
  forbidden: await evaluate(`(() => {
    const text = (document.querySelector('[data-cb-homework-panel]')?.innerText || '').toLowerCase()
    return ['xp', 'grade', 'score', 'mastery', 'streak', 'answer'].filter((word) =>
      new RegExp('(^|[^a-z0-9])' + word + '($|[^a-z0-9])').test(text)
    )
  })()`),
  text: await evaluate("(document.querySelector('[data-cb-homework-panel]')?.innerText || '').replace(/\\s+/g, ' ').slice(0, 260)")
})
const shot = async (id, { full = false } = {}) => {
  let params = { format: 'png', captureBeyondViewport: full }
  if (full) {
    const metrics = await evaluate('({ width: window.innerWidth, height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight) })')
    params = { ...params, clip: { x: 0, y: 0, width: metrics.width, height: metrics.height, scale: 1 } }
  }
  const png = await send('Page.captureScreenshot', params)
  const buffer = Buffer.from(png.data, 'base64')
  writeFileSync(resolve(OUT, `${id}.png`), buffer)
  const record = { id, file: `${id}.png`, md5: createHash('md5').update(buffer).digest('hex'), bytes: buffer.length, ...(await state()) }
  frames.push(record)
  console.log(id, JSON.stringify({ w: record.innerWidth, state: record.sheetState, overflow: record.overflow, forbidden: record.forbidden }))
}
let override = 1049
const setWidth = async (target, height = 1000) => {
  override = target
  for (let i = 0; i < 14; i += 1) {
    await send('Emulation.setDeviceMetricsOverride', { width: override, height, deviceScaleFactor: 1, mobile: false })
    await wait(280)
    const measured = await evaluate('window.innerWidth')
    if (measured === target) return measured
    override = Math.max(200, override + (target - measured))
  }
  throw new Error(`width ${target} did not settle (last ${await evaluate('window.innerWidth')})`)
}
const setText = async (scale) => {
  await evaluate(scale === 200
    ? "document.documentElement.style.setProperty('font-size','32px','important')"
    : "document.documentElement.style.removeProperty('font-size')")
  await wait(300)
}

// Paste-free typing into a React-controlled field: the native setter then a real input event.
const typeInto = async (selector, text) => {
  const done = await evaluate(`(() => {
    const node = document.querySelector(${JSON.stringify(selector)})
    if (!node) return false
    const proto = node.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(node, ${JSON.stringify(text)})
    node.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  })()`)
  if (!done) throw new Error(`no field ${selector}`)
  await wait(250)
}

await open()
await waitFor("!!document.querySelector('[data-cb-route]')", 'coursebook route', 30000)
// A re-capture starts from a clean task index: the rows were reset out of band, so a stale id
// would open the panel on a NOT_FOUND instead of the lesson's real proposal.
await evaluate(`(() => {
  const keys = Object.keys(localStorage).filter((key) => key.includes('homework-index'))
  for (const key of keys) localStorage.removeItem(key)
  return keys.length
})()`)
await evaluate("location.hash = '#/'")
await wait(600)
await evaluate("location.hash = '#/coursebook'")
await waitFor("document.querySelector('[data-cb-destination]')?.getAttribute('data-cb-destination') === 'home'", 'home', 30000)
await setWidth(1049)

// The shelf card for the course whose page carries the task (the rig also holds a rehearsal stub).
const opened = await evaluate(`(() => {
  const card = [...document.querySelectorAll('[data-cb-home-card]')].find(
    (node) => node.innerText.includes('Japanese at home')
  )
  const action = card && card.querySelector('[data-cb-home-card-action]')
  if (!action) return false
  action.click()
  return true
})()`)
if (!opened) throw new Error('no Japanese at home card')
await waitFor("!!document.querySelector('[data-cb-main] button')", 'course detail', 30000)
await wait(1200)
await shot('homework-course-home--1049--dark', { full: true })

// Open the section, then the task action in its footer.
await clickAny(['Open section', 'Start', 'Continue', 'Open the lesson'])
await waitFor("!!document.querySelector('[data-cb-homework-action]')", 'homework action', 40000)
await evaluate("document.querySelector('[data-cb-homework-action]')?.scrollIntoView({ block: 'center' })")
await wait(400)
await shot('homework-lesson--1049--dark')

await evaluate("document.querySelector('[data-cb-homework-action]')?.click()")
await waitFor("!!document.querySelector('[data-cb-homework-panel]')", 'homework panel', 30000)
await waitFor("document.querySelector('[data-cb-homework-panel]')?.getAttribute('data-cb-homework-panel') === 'ready'", 'panel ready', 30000)
await evaluate("document.querySelector('[data-cb-homework-panel]')?.scrollIntoView({ block: 'center' })")
await wait(400)
await shot('homework-panel--1049--dark')

await typeInto('#cb-homework-context', 'At our own table, just before dinner tonight.')
await clickText('Show me the task')
await waitFor("!!document.querySelector('[data-cb-homework-sheet]')", 'task proposed', 40000)
await evaluate("document.querySelector('[data-cb-homework-sheet]')?.scrollIntoView({ block: 'start' })")
await wait(500)
await shot('homework-sheet--1049--dark')

// Keyboard: the action is a real button and takes focus; record what the host paints.
await evaluate("document.querySelector('[data-cb-homework-action]')?.focus()")
await evaluate("document.querySelector('[data-cb-homework-action]')?.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))")
await wait(250)
const focus = await evaluate(`(() => {
  const node = document.activeElement
  if (!node || node === document.body) return null
  const style = getComputedStyle(node)
  return {
    tag: node.tagName,
    label: (node.innerText || node.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').slice(0, 60),
    reachable: node.getAttribute('data-cb-homework-action') === 'take-this-with-you',
    outline: style.outlineStyle + ' ' + style.outlineWidth,
    boxShadow: style.boxShadow
  }
})()`)
console.log('focus', JSON.stringify(focus))

await setWidth(900)
await evaluate("document.querySelector('[data-cb-homework-sheet]')?.scrollIntoView({ block: 'start' })")
await wait(400)
await shot('homework-sheet--900--dark')

await setWidth(460)
await evaluate("document.querySelector('[data-cb-homework-sheet]')?.scrollIntoView({ block: 'start' })")
await wait(400)
await shot('homework-sheet--460--dark')
await setText(200)
await evaluate("document.querySelector('[data-cb-homework-sheet]')?.scrollIntoView({ block: 'start' })")
await wait(500)
await shot('homework-sheet--460--dark--200')
await setText(100)
await setWidth(1049)

// A report, not a pass.
await clickText('I did it')
await waitFor("document.querySelector('[data-cb-homework-completion]')?.getAttribute('data-cb-homework-completion') === 'reported'", 'reported', 30000)
await evaluate("document.querySelector('[data-cb-homework-sheet]')?.scrollIntoView({ block: 'start' })")
await wait(400)
await shot('homework-reported--1049--dark')

// The notebook holds the record; Parent Studio holds the parent's door.
const saved = await evaluate(`(() => {
  const button = [...document.querySelectorAll('[data-cb-homework-actions] button')].find(
    (node) => node.innerText.trim().toLowerCase() === 'save to notebook'
  )
  if (!button) return false
  button.click()
  return true
})()`)
if (!saved) throw new Error('no save-to-notebook control inside the homework panel')
await wait(1500)
await clickAny(['Notebook'])
await waitFor("!!document.querySelector('[data-cb-notebook-homework]')", 'notebook homework list', 30000)
await evaluate("document.querySelector('[data-cb-notebook-homework]')?.scrollIntoView({ block: 'start' })")
await wait(500)
await shot('homework-notebook--1049--dark')

await evaluate("document.querySelector('[data-cb-nav-item=\"studio\"]')?.click()")
await waitFor("!!document.querySelector('[data-cb-parent-studio-tabs]')", 'parent studio', 30000)
await clickText('Homework')
await waitFor("!!document.querySelector('[data-cb-homework-studio]')", 'homework studio', 30000)
await wait(1200)
await shot('homework-studio--1049--dark')

const pluginSha = createHash('sha256').update(readFileSync('desktop/plugin.js')).digest('hex')
const evidence = {
  captured_at: new Date().toISOString(),
  plugin_sha256: pluginSha,
  cdp_port: process.env.CB015_CDP_PORT || '9361',
  focus,
  frames
}
writeFileSync(resolve(OUT, 'live-evidence.json'), JSON.stringify(evidence, null, 2))
console.log('wrote', frames.length, 'frames')
cdp.close()
