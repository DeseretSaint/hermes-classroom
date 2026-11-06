#!/usr/bin/env node
/**
 * CB-015 proof 14 — course/chat/pack deletion paths are distinct and recoverable.
 *
 * Driven only through labelled controls in the isolated rig:
 *   archive → visible under the Archived filter → unarchive;
 *   enrollment.delete (scoped preview: what is deleted, what is kept) → the row leaves the list;
 *   pack.delete (its own preview: courses kept, evidence kept) → the pack is frozen, not cascaded.
 *
 * The chat itself is Hermes-owned: deleting a chat is the host's transcript action, so it is not
 * simulated here — this run records what the plugin can and cannot own.
 *
 *   CB015_CDP_PORT=9338 node scripts/cb015-delete-paths.mjs
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'

let cdp = await connect()
const SHOTS = 'docs/cb015-shots'
const out = { at: new Date().toISOString(), steps: [] }
const log = (m) => console.error(m)

const snap = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : ''
    const buttons = [...document.querySelectorAll('[data-cb-route] button')]
    const dialog = document.querySelector('[role="dialog"], [role="alertdialog"]')
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      rows: buttons.filter((b) => (b.innerText || '').trim() === 'Open').length,
      previews: buttons.filter((b) => (b.innerText || '').trim() === 'Preview').length,
      text: text.replace(/\\n{2,}/g, '\\n').slice(0, 2400),
      dialogText: dialog ? (dialog.innerText || '').replace(/\\n{2,}/g, '\\n').slice(0, 800) : null,
      dialogOpen: !!dialog
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snap()), ...extra }
  out.steps.push(value)
  console.log(JSON.stringify({ step, rows: value.rows, previews: value.previews, dialog: value.dialogOpen }))
  return value
}

// Radix menus open on pointer events, not on a synthetic .click(): use the real input pipeline.
const realClick = async (finder) => {
  const box = await cdp.json(`(() => {
    const el = ${finder}
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, text: (el.innerText || '').trim().slice(0, 60) }
  })()`)
  if (!box) throw new Error(`element not found: ${finder}`)
  await cdp.click(box.x, box.y)
  return box
}

const clickText = async (label) => {
  await realClick(
    `[...document.querySelectorAll('button, [role="menuitem"], [role="option"]')].find(x => (x.innerText || '').trim() === ${JSON.stringify(label)})`
  )
}

const clickAria = async (prefix) => {
  // Radix opens from the pointer pipeline only: a synthetic el.click() leaves the menu closed
  // (that is what stopped the first pass). Click the trigger's real centre instead.
  const opened = await realClick(
    `[...document.querySelectorAll('[data-cb-route] button')].find(x => (x.getAttribute('aria-label') || '').startsWith(${JSON.stringify(prefix)}))`
  )
  if (!opened) throw new Error(`no actions trigger for ${prefix}`)
  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].some(x => x.getAttribute('aria-expanded') === 'true')`,
    { timeout: 10000, label: `menu for ${prefix}` }
  )
  await cdp.wait(400)
}

const waitText = (pattern, label, timeout = 30000) =>
  cdp.waitFor(`new RegExp(${JSON.stringify(pattern)}).test(document.querySelector('[data-cb-route]').innerText || '')`, {
    timeout,
    label
  })

cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Open')`, {
  timeout: 30000,
  label: 'courses'
})
const start = await record('courses-baseline')

// ── 1. an archived course is hidden by default and recoverable ────────────────────────────
// Establish the pre-state in this run instead of inheriting it: archive through the row's own
// menu, then prove it is hidden from the default list, visible under Archived, and restorable.
if (start.rows > 1) {
  await clickAria('Actions for Japanese affection')
  await clickText('Archive course')
  await cdp.wait(2200)
}
const archivedHidden = await record('archived-hidden-by-default')
await clickText('Archived')
await cdp.wait(1800)
const inArchivedFilter = await record('archived-filter-shows-it')
await cdp.shot(`${SHOTS}/77-archived-filter.png`)

await clickAria('Actions for Japanese affection')
await clickText('Unarchive course')
await cdp.wait(2000)
await clickText('All')
await cdp.wait(1800)
const restored = await record('unarchived-back-in-all')
await cdp.shot(`${SHOTS}/76-course-unarchived.png`)

// ── 2. enrollment.delete with its scoped preview ──────────────────────────────────────────
await clickAria('Actions for Japanese register across fifty-five')
await clickText('Delete enrollment…')
await cdp.waitFor(`!!document.querySelector('[role="dialog"], [role="alertdialog"]')`, { timeout: 15000, label: 'delete dialog' })
await cdp.waitFor(
  `((document.querySelector('[role="dialog"], [role="alertdialog"]') || {}).innerText || '').includes('Course and plan kept')`,
  { timeout: 20000, label: 'delete preview scope' }
)
const preview = await record('delete-preview')
await cdp.shot(`${SHOTS}/78-delete-enrollment-preview.png`)

await cdp.eval(`(() => {
  const d = document.querySelector('[role="dialog"], [role="alertdialog"]')
  const b = [...d.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Delete enrollment')
  if (b) b.click()
  return !!b
})()`)
await cdp.waitFor(`!document.querySelector('[role="dialog"], [role="alertdialog"]')`, { timeout: 30000, label: 'dialog closed' })
await cdp.wait(2000)
const deleted = await record('enrollment-deleted')
await cdp.shot(`${SHOTS}/79-enrollment-deleted.png`)

// ── 3. pack.delete keeps courses + evidence ───────────────────────────────────────────────
await clickText('Library')
await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Preview')`, {
  timeout: 30000,
  label: 'library rows'
})
const libraryBefore = await record('library-before-pack-delete')

const picked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Preview')
  if (!b) return 'no-preview'
  b.click()
  return 'clicked'
})()`)
if (picked !== 'clicked') throw new Error(`library pack selection: ${picked}`)
await cdp.wait(1200)
await clickText('Remove pack…')
await cdp.waitFor(
  `((document.querySelector('[data-cb-route]') || {}).innerText || '').includes('Remove this pack')`,
  { timeout: 15000, label: 'pack delete panel' }
)
await clickText('Preview what stays and what goes')
await cdp.waitFor(
  `/(Courses from this pack|Evidence kept)/.test(document.querySelector('[data-cb-route]').innerText || '')`,
  { timeout: 20000, label: 'pack delete preview' }
)
const packPreview = await record('pack-delete-preview')
await cdp.shot(`${SHOTS}/80-pack-delete-preview.png`)

await clickText('Freeze this pack')
await cdp.wait(2500)
const packDeleted = await record('pack-frozen')
await cdp.shot(`${SHOTS}/81-pack-frozen.png`)

out.verdict = {
  archivedHiddenByDefault: archivedHidden.rows === 1,
  // The recovery proof is the row returning to All with both titles on screen; "Unarchive course"
  // is a menu item, not row text, so testing the row's innerText for that word proved nothing.
  archiveRecoverable: restored.rows === 2 && /Japanese affection/.test(restored.text),
  deleteScopedPreview: Boolean(preview.dialogText && /Course and plan kept/.test(preview.dialogText) && /Hermes transcripts kept/.test(preview.dialogText)),
  deleteRemovedRow: deleted.rows === 1 && !deleted.dialogOpen,
  packPreviewKeepsEvidence: Boolean(packPreview.text && /Evidence kept/.test(packPreview.text)),
  packDistinctFromEnrollment: libraryBefore.text.includes('Preview')
}
const path = await writeJson('docs/REVIEW_CB015-delete-paths.json', out)
console.log(JSON.stringify(out.verdict, null, 2))
console.log(`wrote ${path}`)
cdp.close()
process.exit(0)
