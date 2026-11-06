#!/usr/bin/env node
/**
 * CB-015 a11y re-check — the two defects recorded in REVIEW_CB015 §9.
 *
 *   1. Escape must close the notebook dialog AND return focus to the control that opened it,
 *      not to <body>.
 *   2. The narrow-viewport view picker's accessible name must include the selected view, and
 *      follow it when the keyboard changes the view.
 *
 * Real key events through Chromium's input pipeline; no synthetic .focus() for the operation
 * under test (the trigger is only marked so the probe can identify it afterwards).
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-a11y2.mjs
 */
import { connect, writeJson } from './cb015-lib.mjs'

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), checks: {} }

// A plugin edit is only live after a page reload, and a reload detaches the evaluated context:
// close the socket, reload blind, then attach to the new page.
const reloadAndReattach = async () => {
  await cdp.send('Page.reload', { ignoreCache: false }).catch(() => {})
  cdp.close()
  await new Promise((resolve) => setTimeout(resolve, 4500))
  cdp = await connect()
  await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'coursebook route' })
}

const shoot = (name) => cdp.shot(`${SHOTS}/${name}.png`)
const log = (m) => console.error(new Date().toISOString().slice(11, 23) + ' ' + m)

const openSection = async (index) => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(2000)
  await cdp.eval(
    `(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>x.innerText.trim()==='Open'); if(b) b.click(); return !!b })()`
  )
  await cdp.wait(1800)
  await cdp.eval(
    `(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>x.innerText.trim()==='Textbook'); if(b) b.click(); return !!b })()`
  )
  await cdp.wait(1400)
  const state = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => b.innerText.trim() === 'Open section')
    if (!bs[${index}]) return 'missing(' + bs.length + ')'
    bs[${index}].click()
    return 'clicked'
  })()`)
  if (state !== 'clicked') throw new Error(`open section ${index}: ${state}`)
  await cdp.wait(2600)
}

log('reloading')
await reloadAndReattach()
log('reloaded')

// ── 1. Escape restores focus to the trigger ────────────────────────────────────────────────
log('opening section')
await openSection(0)
log('section open')
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].some(b => b.innerText.trim() === 'Save to notebook')`,
  { timeout: 20000, label: 'Save to notebook trigger' }
)
const opened = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => x.innerText.trim() === 'Save to notebook')
  b.dataset.cbTrigger = 'save-notebook'
  b.focus()
  b.click()
  return { label: b.innerText.trim() }
})()`)
await cdp.waitFor(`!!document.querySelector('[role="dialog"]')`, { timeout: 10000, label: 'notebook dialog' })
await cdp.wait(400)
await shoot('60-notebook-dialog-focus-before')
const dialogOpen = await cdp.eval(`(() => {
  const d = document.querySelector('[role="dialog"]')
  return { open: !!d, title: d ? (d.querySelector('[role="heading"], h2') && (d.querySelector('[role="heading"], h2').innerText || '').trim()) : null }
})()`)

await cdp.key('Escape')
await cdp.wait(700)
const afterEscape = await cdp.json(`(() => {
  const active = document.activeElement
  const trigger = document.querySelector('[data-cb-trigger="save-notebook"]')
  return {
    dialogOpen: !!document.querySelector('[role="dialog"]'),
    activeTag: active ? active.tagName.toLowerCase() : null,
    activeText: active ? (active.innerText || '').trim().slice(0, 80) : null,
    activeIsBody: active === document.body,
    activeIsTrigger: !!trigger && active === trigger,
    triggerConnected: !!trigger,
    triggerText: trigger ? (trigger.innerText || '').trim() : null
  }
})()`)
await shoot('61-after-escape-focus')
out.checks.escapeFocusReturn = { trigger: opened.label, dialogOpenAtOpen: dialogOpen, afterEscape }

// ── 2. View picker name carries the selected view ──────────────────────────────────────────
await cdp.setViewport(513, 1004, 1)
await cdp.wait(800)
await openSection(0)
await cdp.wait(900)

const nameOf = () =>
  cdp.json(`(() => {
    const el = document.querySelector('#cb-view-picker')
    if (!el) return { found: false }
    const visible = el.getClientRects().length > 0
    return {
      found: true,
      visible,
      ariaLabel: el.getAttribute('aria-label'),
      text: (el.innerText || '').trim(),
      role: el.getAttribute('role'),
      tabIndex: el.tabIndex
    }
  })()`)

const pickerAtTextbook = await nameOf()
await shoot('62-view-picker-textbook-narrow')

// A real keyboard change: Enter opens the listbox, ArrowDown moves, Enter commits.
await cdp.eval(`(() => { const el = document.querySelector('#cb-view-picker'); el.focus(); return document.activeElement === el })()`)
await cdp.key('Enter')
await cdp.wait(500)
await cdp.key('ArrowDown')
await cdp.wait(250)
await cdp.key('Enter')
await cdp.wait(1400)
const pickerAfterArrow = await nameOf()
const bodyAfter = await cdp.eval(`(() => (document.querySelector('[data-cb-route]').innerText || '').slice(0, 200))()`)
await shoot('63-view-picker-after-keyboard-change')

out.checks.viewPickerName = {
  atTextbook: pickerAtTextbook,
  afterKeyboardChange: pickerAfterArrow,
  routeTextAfterChange: bodyAfter
}

await cdp.clearViewport()
const path = await writeJson('docs/REVIEW_CB015-a11y2.json', out)
console.log(JSON.stringify(out, null, 2))
console.log(`wrote ${path}`)
cdp.close()
process.exit(0)
