/** Attempt states + delete-confirmation dialog: live exercise on the isolated backend. */
import { writeFileSync } from 'node:fs'
import { attach, measure, setMode, setRootText, clearRootText, setForcedColors, setViewportCss, tabWalk, focusNow, esc, ROUTE } from './audit-ux-lib.mjs'

const SHOTS = 'docs/a11y-shots'
const setFault = (obj) => writeFileSync('audit/ux/fault.json', `${JSON.stringify(obj, null, 2)}\n`)
const wait = (cdp, ms) => cdp.wait(ms)
const text = (cdp) => cdp.eval(`(document.querySelector('${ROUTE}')||document.body).innerText`)
const click = (cdp, label) => cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}') || document.body
  const el = [...root.querySelectorAll('button,a,[role="tab"]')].find((e) => (e.innerText||'').replace(/\\s+/g,' ').trim() === ${JSON.stringify(label)})
  if (!el) return false
  el.click(); return true
})()`)

const cdp = await attach()
const out = {}
const shot = async (path) => {
  const { writeFileSync: wf, mkdirSync } = await import('node:fs')
  const { dirname, resolve } = await import('node:path')
  const target = resolve(path)
  mkdirSync(dirname(target), { recursive: true })
  let data = null
  for (const params of [{ format: 'png', fromSurface: false }, { format: 'png' }]) {
    try {
      data = (await cdp.send('Page.captureScreenshot', params)).data
      if (data) break
    } catch {}
  }
  if (!data) throw new Error(`screenshot failed: ${path}`)
  wf(target, Buffer.from(data, 'base64'))
  return target
}

// ── section + attempt ────────────────────────────────────────────────────────
setFault({})
await cdp.eval(`location.hash = '#/coursebook'`)
await wait(cdp, 1500)
await click(cdp, 'Courses')
await wait(cdp, 800)
await cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}')
  const title = [...root.querySelectorAll('*')].find((el) => (el.innerText||'').includes('Japanese affection'))
  let node = title
  for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
    const b = [...node.querySelectorAll('button')].find((x) => (x.innerText||'').trim() === 'Open')
    if (b) { b.click(); return true }
  }
  return false
})()`)
await wait(cdp, 2200)
await click(cdp, 'Textbook')
await wait(cdp, 1200)
await click(cdp, 'Open section')
await wait(cdp, 2200)

out.section = {}
for (const variant of ['dark', 'light', 'text200', 'narrow']) {
  await setMode(cdp, variant === 'light' ? 'light' : 'dark')
  await clearRootText(cdp)
  await setForcedColors(cdp, false)
  await setViewportCss(cdp, variant === 'narrow' ? 460 : 1280, 900)
  if (variant === 'text200') await setRootText(cdp, 32)
  await wait(cdp, 500)
  const m = await measure(cdp)
  await shot(`${SHOTS}/attempt-section-${variant}.png`)
  out.section[variant] = m
}
await clearRootText(cdp)
await setViewportCss(cdp, 1280, 900)
await setMode(cdp, 'dark')

// Answer + submit (real grading path).
const answered = await cdp.eval(`(() => {
  const input = document.querySelector('#cb-attempt-answer') || [...document.querySelectorAll('[data-cb-route] textarea, [data-cb-route] input[type="text"]')][0]
  if (!input) return false
  const proto = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, 'Because the relationship changes which ending is allowed.')
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.focus()
  return true
})()`)
out.answered = answered
await wait(cdp, 400)
const submitted = await click(cdp, 'Submit answer')
out.submitted = submitted
await wait(cdp, 150)
out.pending = { text: (await text(cdp)).slice(0, 900) }
await shot(`${SHOTS}/attempt-pending-dark.png`)
await wait(cdp, 3500)
out.afterSubmit = { text: (await text(cdp)).slice(0, 1400) }
await shot(`${SHOTS}/attempt-graded-dark.png`)

// Grader unavailable: inject the contract's own refusal on the next submit.
setFault({
  rpc: {
    'attempt.submit': {
      __error: {
        code: 'GRADER_UNAVAILABLE',
        category: 'capability',
        message: 'The grader is unavailable, so nothing was recorded. Retry, edit, or override.',
        retryable: true,
        details: { check_id: 'audit' }
      }
    }
  }
})
await cdp.eval(`(() => {
  const input = document.querySelector('#cb-attempt-answer') || [...document.querySelectorAll('[data-cb-route] textarea, [data-cb-route] input[type="text"]')][0]
  if (!input) return false
  const proto = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, 'A second attempt under a failing grader.')
  input.dispatchEvent(new Event('input', { bubbles: true }))
  return true
})()`)
await wait(cdp, 300)
out.retrySubmitted = await click(cdp, 'Submit answer')
await wait(cdp, 2500)
out.graderUnavailable = { text: (await text(cdp)).slice(0, 1400) }
await shot(`${SHOTS}/attempt-grader-unavailable-dark.png`)
for (const variant of ['light', 'text200', 'narrow']) {
  await setMode(cdp, variant === 'light' ? 'light' : 'dark')
  await clearRootText(cdp)
  if (variant === 'text200') await setRootText(cdp, 32)
  await setViewportCss(cdp, variant === 'narrow' ? 460 : 1280, 900)
  await wait(cdp, 500)
  out[`graderUnavailable-${variant}`] = await measure(cdp)
  await shot(`${SHOTS}/attempt-grader-unavailable-${variant}.png`)
}
setFault({})
await clearRootText(cdp)
await setViewportCss(cdp, 1280, 900)
await setMode(cdp, 'dark')

// ── delete confirmation dialog (a11y: focus, escape, return) ───────────────
await cdp.eval(`location.hash = '#/coursebook'`)
await wait(cdp, 1600)
await click(cdp, 'Courses')
await wait(cdp, 900)
// row overflow menu: find a button whose accessible name mentions actions
const opened = await cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}')
  const buttons = [...root.querySelectorAll('button')]
  const menu = buttons.find((b) => /more|actions|options|row actions/i.test((b.getAttribute('aria-label')||b.getAttribute('title')||'').trim()))
  if (menu) { menu.click(); return 'menu:' + (menu.getAttribute('aria-label')||menu.getAttribute('title')) }
  return 'no-menu'
})()`)
out.deleteMenu = opened
await wait(cdp, 800)
out.menuItems = await cdp.json(`[...document.querySelectorAll('[role="menuitem"], [role="menu"] button')].map(b => (b.innerText||'').trim()).filter(Boolean)`)
const deleteClicked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[role="menuitem"], button')].find((x) => /^delete/i.test((x.innerText||'').trim()))
  if (!b) return false
  b.click(); return true
})()`)
out.deleteClicked = deleteClicked
await wait(cdp, 1500)
out.dialogText = (await text(cdp)).slice(0, 1200)
await shot(`${SHOTS}/delete-confirm-dark.png`)
out.dialogFocus = await focusNow(cdp)
const dialogWalk = await tabWalk(cdp, 12)
out.dialogWalk = { stops: dialogWalk.stops.map((s) => `${s.tag}:${s.name}:${s.outline}:${s.ring}`), trap: dialogWalk.trap }
const escRes = await esc(cdp)
out.dialogEscape = escRes
await wait(cdp, 600)
out.afterEscapeText = (await text(cdp)).slice(0, 300)
out.afterEscape = await focusNow(cdp)
out.dialogClosed = !(await cdp.eval(`/Delete this course\\?|deleted|permanently/i.test((document.querySelector('${ROUTE}')||document.body).innerText)`))
await shot(`${SHOTS}/delete-after-escape-dark.png`)

writeFileSync('audit/ux/attempt-dialog.json', `${JSON.stringify(out, null, 2)}\n`)
console.log(JSON.stringify({
  answered: out.answered,
  submitted: out.submitted,
  pendingText: out.pending.text.slice(0, 300),
  afterSubmit: out.afterSubmit.text.slice(0, 400),
  graderUnavailable: out.graderUnavailable.text.slice(0, 400),
  deleteMenu: out.deleteMenu,
  menuItems: out.menuItems,
  deleteClicked: out.deleteClicked,
  dialogText: out.dialogText.slice(0, 300),
  dialogFocus: out.dialogFocus,
  dialogWalk: out.dialogWalk,
  dialogEscape: out.dialogEscape,
  dialogClosed: out.dialogClosed
}, null, 2))
cdp.close()
