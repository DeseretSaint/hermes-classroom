#!/usr/bin/env node
/**
 * H-194 live run: fine-tune controls in the real Desktop renderer.
 *
 * Drives the isolated Coursebook window (remote connection to the disposable backend) against a
 * course the real generation pipeline authored. Two phases, because the untouched-section read and
 * the export gate have to be checked between them:
 *
 *   edit    open the parent course → Plan view → edit one section's objective title AND its page
 *           title → save → reorder two sections → stop. Writes h194-editor,
 *           h194-reorder-confirmed and facts.edit.json.
 *   approve open the same course → Plan view → Review changes → capture the blocked gate →
 *           approve the exact reviewed bytes → capture the ready gate. Writes
 *           h194-export-blocked, h194-export-ready and facts.approve.json.
 *
 * Row selection matches the landing row whose own title CONTAINS H194_TITLE, and fails loudly when
 * zero or more than one row matches: the landing groups plans by their primary title, so an
 * exact-equality match is the wrong assertion.
 *
 *   CB013_CDP_PORT=9386 H194_TITLE="Counting to ten in Japanese" H194_PHASE=edit node scripts/h194-live.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const PORT = process.env.CB013_CDP_PORT || '9386'
const TITLE = process.env.H194_TITLE || 'Counting to ten in Japanese'
const PHASE = process.env.H194_PHASE || 'edit'
// The exact blocked_reason the approve phase must observe. H-194's stated gate is
// changes_need_review; a plan edit (reorder) supersedes the final approval first, so the measured
// reason can be no_final_approval. The value is asserted verbatim, never merely logged.
const EXPECTED_BLOCKED_REASON = process.env.H194_BLOCKED_REASON || 'changes_need_review'
const OUT = resolve(process.env.H194_SHOTS || 'audit/h194/live')
if (PHASE !== 'edit' && PHASE !== 'approve') throw new Error(`H194_PHASE must be edit or approve, got ${PHASE}`)
mkdirSync(OUT, { recursive: true })

const VIEWPORT = { width: 1280, height: 1200 }
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()
const page = targets.find((e) => e.type === 'page' && /Hermes/.test(e.title || '')) || targets.find((t) => t.type === 'page')
if (!page) throw new Error('no page target on the isolated window')

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
    const { res, rej } = pending.get(message.id)
    pending.delete(message.id)
    if (message.error) rej(new Error(JSON.stringify(message.error)))
    else res(message.result)
  }
})
const send = (method, params = {}, timeout = 30000) =>
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
const waitFor = async (expr, ms = 30000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    if (await evalJs(expr)) return true
    await wait(250)
  }
  return false
}
const shot = async (name) => {
  const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  writeFileSync(`${OUT}/${name}.png`, Buffer.from(png.data, 'base64'))
  console.log(`shot ${OUT}/${name}.png`)
}

const clickText = (label, selector = 'button, [role="button"]') =>
  evalJs(`(() => {
    const wanted = ${JSON.stringify(label)}
    const nodes = [...document.querySelectorAll(${JSON.stringify(selector)})]
    const node = nodes.find((n) => (n.innerText || '').trim() === wanted) || nodes.find((n) => (n.innerText || '').includes(wanted))
    if (!node) return false
    node.click()
    return true
  })()`)

const clickSelector = (selector) =>
  evalJs(`(() => {
    const node = document.querySelector(${JSON.stringify(selector)})
    if (!node) return false
    node.click()
    return true
  })()`)

const setInput = (selector, value) =>
  evalJs(`(() => {
    const node = document.querySelector(${JSON.stringify(selector)})
    if (!node) return { ok: false, why: 'no input ' + ${JSON.stringify(selector)} }
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(node, ${JSON.stringify(value)})
    node.dispatchEvent(new window.Event('input', { bubbles: true }))
    return { ok: true, value: node.value }
  })()`)

const facts = { phase: PHASE, viewport: VIEWPORT, started_at: new Date().toISOString() }

await send('Page.bringToFront')
await send('Emulation.setFocusEmulationEnabled', { enabled: true }).catch(() => {})
await send('Emulation.setDeviceMetricsOverride', { width: VIEWPORT.width, height: VIEWPORT.height, deviceScaleFactor: 1, mobile: false })
await wait(500)

await evalJs("location.hash='#/'; 'ok'")
await wait(400)
await evalJs("location.hash='#/coursebook'; 'ok'")
if (!(await waitFor("!!document.querySelector('[data-cb-route]')", 25000))) {
  throw new Error('the Coursebook route did not mount; refusing to capture')
}
for (const label of ['Hide right sidebar', 'Hide sidebar']) {
  await evalJs(`(() => {
    const b = [...document.querySelectorAll('button[aria-label]')].find((n) => n.getAttribute('aria-label') === ${JSON.stringify(label)})
    if (b) b.click()
    return 'ok'
  })()`)
}
await wait(600)
facts.theme = await evalJs(`(() => {
  const root = document.documentElement
  const body = getComputedStyle(document.body)
  return {
    attribute: root.getAttribute('data-theme') || root.getAttribute('data-cb-theme') || null,
    colorScheme: getComputedStyle(root).colorScheme || null,
    background: body.backgroundColor,
    color: body.color
  }
})()`)

if (!(await waitFor("!!document.querySelector('[data-cb-nav-item=\\\"studio\\\"]')", 15000))) {
  throw new Error('no Parent Studio destination on the route')
}
await clickSelector('[data-cb-nav-item="studio"]')
await wait(1500)

// The landing groups plans by their primary title. Match the row that CONTAINS the title and fail
// loudly unless exactly one row matches: zero means the rig is not looking at the seeded plan, more
// than one means the title is not distinctive enough to identify one course.
const rowMatch = await evalJs(`(() => {
  const wanted = ${JSON.stringify(TITLE)}
  const landing = document.querySelector('[data-cb-studio-landing]')
  if (!landing) return { total: 0, matches: [], error: 'no [data-cb-studio-landing]' }
  const articles = [...landing.querySelectorAll('article[data-cb-course-id]')]
  const matches = articles
    .filter((a) => ((a.innerText || '').replace(/\\s+/g, ' ').trim()).includes(wanted))
    .map((a) => ({
      courseId: a.getAttribute('data-cb-course-id'),
      text: (a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 240)
    }))
  return { total: articles.length, matches }
})()`)
facts.rowMatch = rowMatch
if (rowMatch.error) throw new Error(`the Parent Studio landing did not mount: ${rowMatch.error}`)
if (rowMatch.matches.length !== 1) {
  throw new Error(
    `row selection for ${JSON.stringify(TITLE)} matched ${rowMatch.matches.length} of ${rowMatch.total} landing rows; ` +
      `expected exactly one. Matches: ${JSON.stringify(rowMatch.matches)}`
  )
}
const courseId = rowMatch.matches[0].courseId
facts.courseId = courseId
const opened = await evalJs(`(() => {
  const article = [...document.querySelectorAll('[data-cb-studio-landing] article[data-cb-course-id]')]
    .find((a) => a.getAttribute('data-cb-course-id') === ${JSON.stringify(courseId)})
  if (!article) return false
  const button = [...article.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Open plan') || article.querySelector('button')
  if (!button) return false
  button.click()
  return true
})()`)
if (!opened) throw new Error(`the landing row for ${courseId} carried no open control`)
facts.opened = await waitFor("!!document.querySelector('[data-cb-view-picker]') || !!document.querySelector('[data-cb-finetune]') || document.body.innerText.includes('Studio view')", 15000)
if (!facts.opened) throw new Error('the course view did not mount after opening the row')

// Plan view: the segmented control renders one button per Studio view.
if (!(await clickText('Plan', '[aria-pressed], button'))) throw new Error('the Plan view control was not found')
if (!(await waitFor("!!document.querySelector('[data-cb-finetune]')", 25000))) {
  throw new Error('the fine-tune panel did not mount on the approved plan')
}
await wait(600)
facts.before = await evalJs(`(() => {
  const list = document.querySelector('[data-cb-finetune-order]')
  return {
    order: list ? list.getAttribute('data-cb-finetune-order') : null,
    rows: [...document.querySelectorAll('[data-cb-finetune-row]')].map((row) => ({
      id: row.getAttribute('data-cb-finetune-row'),
      title: ((row.querySelector('[data-cb-finetune-title]') || {}).textContent || '').trim(),
      chip: (row.querySelector('[data-cb-finetune-chip]') || {}).getAttribute?.('data-cb-finetune-chip') || null,
      moveDownDisabled: Boolean((row.querySelector('[data-cb-finetune-move="down"]') || {}).disabled)
    }))
  }
})()`)
if (!facts.before.rows.length) throw new Error('the fine-tune panel rendered no section rows')
if (!facts.before.rows[0].id) throw new Error('the first fine-tune row carried no objective id')

if (PHASE === 'edit') {
  // 1 — inline section edit: the objective title AND the section page title.
  await clickSelector('[data-cb-finetune-row] [data-cb-finetune-edit]')
  if (!(await waitFor("!!document.querySelector('[data-cb-finetune-editor]')", 10000))) throw new Error('the inline editor did not open')
  const editorId = await evalJs("document.querySelector('[data-cb-finetune-editor]').getAttribute('data-cb-finetune-editor')")
  const before = facts.before.rows[0]
  const newTitle = `${before.title} (revised)`
  const newPageTitle = `${before.title} page (revised)`
  const titleSet = await setInput(`#cb-finetune-title-${editorId}`, newTitle)
  const pageSet = await setInput(`#cb-finetune-page-title-${editorId}`, newPageTitle)
  if (!titleSet.ok || !pageSet.ok) throw new Error(`editor inputs missing: ${JSON.stringify({ titleSet, pageSet })}`)
  await wait(400)
  facts.editor = {
    objectiveId: editorId,
    titleField: titleSet.value,
    pageTitleField: pageSet.value,
    dirty: await evalJs("!!document.querySelector('[data-cb-finetune-dirty]')")
  }
  if (!facts.editor.dirty) throw new Error('the editor did not report a dirty draft after both fields changed')
  await shot('h194-editor')
  await clickSelector('[data-cb-finetune-save]')
  if (!(await waitFor("!!document.querySelector('[data-cb-finetune-notice]')", 20000))) throw new Error('saving the section produced no notice')
  await wait(800)
  facts.afterEdit = {
    notice: await evalJs("(document.querySelector('[data-cb-finetune-notice]') || {}).innerText || null"),
    chips: await evalJs("[...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip'))"),
    titles: await evalJs("[...document.querySelectorAll('[data-cb-finetune-title]')].map((n) => (n.textContent || '').trim())")
  }
  const saved = String(facts.afterEdit.notice || '')
  if (!/saved/i.test(saved)) throw new Error(`saving the section did not confirm: ${saved}`)
  if (!/page/i.test(saved)) {
    throw new Error(`the page-title edit was not part of the saved change; notice was ${JSON.stringify(saved)}`)
  }

  // 2 — reorder: move the first section down. The command decides the order; the screen adopts it.
  await clickSelector('[data-cb-finetune-row] [data-cb-finetune-move="down"]')
  if (!(await waitFor("(document.querySelector('[data-cb-finetune-notice]') || {}).innerText && document.querySelector('[data-cb-finetune-notice]').innerText.startsWith('Order saved.')", 20000))) {
    throw new Error('the reorder produced no stored-order confirmation')
  }
  await wait(600)
  facts.reorder = await evalJs(`(() => {
    const list = document.querySelector('[data-cb-finetune-order]')
    return {
      order: list ? list.getAttribute('data-cb-finetune-order') : null,
      notice: (document.querySelector('[data-cb-finetune-notice]') || {}).innerText || null,
      undo: (document.querySelector('[data-cb-finetune-undo]') || {}).getAttribute?.('data-cb-finetune-undo') || null,
      rows: [...document.querySelectorAll('[data-cb-finetune-row]')].map((row) => ((row.querySelector('[data-cb-finetune-title]') || {}).textContent || '').trim())
    }
  })()`)
  if (facts.reorder.order === facts.before.order) throw new Error('the stored order did not change after the reorder command')
  if (facts.reorder.rows[0] === facts.before.rows[0].title) throw new Error('the screen did not adopt the stored order')
  await shot('h194-reorder-confirmed')
} else {
  // 3 — Review changes: the pending diff and the export gate, opened from the Plan tab.
  facts.reviewBeforeApprove = await evalJs(`(() => ({
    reviewControl: !!document.querySelector('[data-cb-finetune-review]'),
    order: (document.querySelector('[data-cb-finetune-order]') || {}).getAttribute?.('data-cb-finetune-order') || null,
    titles: [...document.querySelectorAll('[data-cb-finetune-title]')].map((n) => (n.textContent || '').trim()),
    error: (document.querySelector('[data-cb-finetune-error]') || {}).innerText || null
  }))()`)
  await clickSelector('[data-cb-finetune-review]')
  if (!(await waitFor("!!document.querySelector('[data-cb-review-diff]')", 20000))) throw new Error('the review diff did not mount')
  await wait(800)
  facts.review = await evalJs(`(() => {
    const diff = document.querySelector('[data-cb-review-diff]')
    return {
      state: diff ? diff.getAttribute('data-cb-review-diff') : null,
      exportGate: (document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') || null,
      blockedReason: (document.querySelector('[data-cb-review-blocked-reason]') || {}).getAttribute?.('data-cb-review-blocked-reason') || null,
      blockedLine: (document.querySelector('[data-cb-export-blocked-reason]') || {}).textContent || null,
      changed: [...document.querySelectorAll('[data-cb-review-changed]')].map((n) => n.getAttribute('data-cb-review-changed')),
      chips: [...document.querySelectorAll('[data-cb-finetune-chip]')].map((n) => n.getAttribute('data-cb-finetune-chip')),
      approveDisabled: Boolean(([...document.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === 'Approve this lesson set') || {}).disabled)
    }
  })()`)
  if (facts.review.exportGate !== 'blocked') {
    throw new Error(`the export gate is ${JSON.stringify(facts.review.exportGate)} before approval; expected blocked`)
  }
  if (String(facts.review.blockedReason || '') !== EXPECTED_BLOCKED_REASON) {
    throw new Error(`the blocked gate names ${JSON.stringify(facts.review.blockedReason)}; expected ${EXPECTED_BLOCKED_REASON}`)
  }
  await shot('h194-export-blocked')

  // 4 — Approve the exact bytes that were just reviewed.
  if (!(await clickText('Approve this lesson set'))) throw new Error('the approve control was not found')
  const ready = await waitFor("(document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') === 'ready'", 30000)
  await wait(800)
  facts.afterApprove = await evalJs(`(() => {
    const diff = document.querySelector('[data-cb-review-diff]')
    const exportButton = [...document.querySelectorAll('button')].find((n) => (n.innerText || '').trim() === 'Export the approved files')
    return {
      exportGate: (document.querySelector('[data-cb-review-export]') || {}).getAttribute?.('data-cb-review-export') || null,
      blockedReason: (document.querySelector('[data-cb-review-blocked-reason]') || {}).getAttribute?.('data-cb-review-blocked-reason') || null,
      exportDisabled: exportButton ? Boolean(exportButton.disabled) : null,
      body: diff ? diff.innerText.slice(0, 400) : null
    }
  })()`)
  facts.afterApprove.reachedReady = ready
  if (!ready || facts.afterApprove.exportGate !== 'ready') {
    throw new Error(`the export gate did not reach ready after approval: ${JSON.stringify(facts.afterApprove)}`)
  }
  await shot('h194-export-ready')
}

facts.finished_at = new Date().toISOString()
const factsName = PHASE === 'edit' ? 'facts.edit.json' : 'facts.approve.json'
writeFileSync(`${OUT}/${factsName}`, JSON.stringify(facts, null, 2))
console.log(JSON.stringify(facts, null, 2))
socket.close()
process.exit(0)
