#!/usr/bin/env node
/**
 * M2-U3 live proof: save a moment, find it by search, return to its exact section, fresh reload.
 *
 *   CB009_CDP_PORT=9345 CB013_BASE=http://127.0.0.1:44281 node scripts/m2fn-live.mjs
 *
 * Drives the real isolated Desktop window against the real isolated backend. Two sequences, each
 * named for what it proves:
 *
 *   A. Field Notes strip + fresh-run persistence on the course the Field Desk continues. That
 *      enrollment currently serves a v7 lesson page (segments, no block document), so the save is
 *      the page's own structured segment — never a transcript selection.
 *   B. Block-level save -> backend ref -> notebook search -> exact block return, on the enrollment
 *      that serves a v8 block document.
 *
 * Every assertion reads the live DOM; rows are read back through `scripts/cb013-rpc.py` so no
 * claim rests on the renderer's own state. Screenshots and `live-evidence.json` land in
 * `audit/visual/m2-field-notes`.
 */
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { attach, clickExact, gotoCoursebook, openCourse, shot, tab } from './cb-loops-lib.mjs'

const OUT = resolve('audit/visual/m2-field-notes')
const STAMP = Date.now().toString(36)
const MARK_A = 'cb-strip-note-' + STAMP
const MARK_B = 'cb-block-note-' + STAMP
const TAG_A = 'strip-proof-' + STAMP.slice(-5)
const TAG_B = 'block-proof-' + STAMP.slice(-5)
const COURSE = 'Japanese affection and register — an L0 demonstration classroom'

mkdirSync(OUT, { recursive: true })
const cdp = await attach()
const observed = { markers: { strip: MARK_A, block: MARK_B }, steps: [], screenshots: [] }

const step = (name, expected, actual, extra = {}) => {
  const row = { step: name, expected, actual, ...extra, at: new Date().toISOString() }
  observed.steps.push(row)
  console.log(JSON.stringify(row).slice(0, 700))
  return row
}
const shotTo = async (name) => {
  await cdp.shot(`${OUT}/${name}.png`)
  observed.screenshots.push(name)
}
const asDesk = async () => {
  await cdp.eval(`(location.hash = '#/')`)
  await cdp.wait(800)
  await cdp.eval(`(location.hash = '#/coursebook')`)
  await cdp.wait(1200)
  await gotoCoursebook(cdp)
  await cdp.waitFor(`!!document.querySelector('[data-cb-desk="ready"]')`, { timeout: 25000, label: 'field desk' })
  await cdp.wait(900)
}
const fieldBox = async (selector) =>
  cdp.json(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)})
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, value: el.value }
  })()`)
const clearAndType = async (selector, value) => {
  const box = await fieldBox(selector)
  if (!box) throw new Error('field missing ' + selector)
  await cdp.click(box.x, box.y)
  await cdp.wait(120)
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8 })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8 })
  await cdp.type(value)
  await cdp.wait(250)
  return cdp.eval(`document.querySelector(${JSON.stringify(selector)}).value`)
}
const stripState = () =>
  cdp.json(`(() => {
    const strip = document.querySelector('[data-cb-field-notes]')
    return {
      state: strip ? strip.getAttribute('data-cb-field-notes') : null,
      notes: document.querySelectorAll('[data-cb-field-note]').length,
      text: strip ? (strip.innerText || '').slice(0, 4000) : null
    }
  })()`)
const activeBlock = () =>
  cdp.json(`(() => {
    const a = document.activeElement
    const block = a && a.closest ? a.closest('[data-cb-block]') : null
    const view = document.querySelector('[data-cb-lesson-view]')
    const style = a ? getComputedStyle(a) : null
    return {
      tag: a ? a.tagName.toLowerCase() : null,
      block: block ? block.getAttribute('data-cb-block') : null,
      document: view ? view.getAttribute('data-cb-document') : null,
      outline: style ? style.outlineStyle + ' ' + style.outlineWidth : null
    }
  })()`)
const clickIn = async (containerSelector, label) => {
  const box = await cdp.json(`(() => {
    const root = document.querySelector(${JSON.stringify(containerSelector)})
    if (!root) return null
    const b = [...root.querySelectorAll('button')].find(x => (x.innerText || '').trim() === ${JSON.stringify(label)})
    if (!b) return null
    b.scrollIntoView({ block: 'center' })
    const r = b.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
  if (!box) throw new Error(`${label} missing inside ${containerSelector}`)
  await cdp.click(box.x, box.y)
}
const saveFromDialog = async (note, tags) => {
  await cdp.waitFor(`!!document.querySelector('[role="dialog"]')`, { timeout: 10000, label: 'save dialog' })
  const prefill = await cdp.eval(`document.querySelector('#cb-note-excerpt')?.value || ''`)
  const provenance = await cdp.eval(`document.querySelector('[data-cb-save-provenance]')?.innerText || ''`)
  await clearAndType('#cb-note-note', note)
  await clearAndType('#cb-note-tags', tags)
  const confirm = await cdp.json(`(() => {
    const dialog = document.querySelector('[role="dialog"]')
    const b = [...dialog.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Save to notebook')
    const r = b.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
  await cdp.click(confirm.x, confirm.y)
  await cdp.waitFor(`!document.querySelector('[role="dialog"]')`, { timeout: 25000, label: 'dialog close' })
  await cdp.wait(700)
  return { prefill, provenance }
}
const backendNotebook = () => {
  const payload = JSON.parse(
    execFileSync('python3', ['scripts/cb013-rpc.py', 'notebook.list', '{}'], {
      env: { ...process.env, CB013_BASE: process.env.CB013_BASE || 'http://127.0.0.1:44281' },
      encoding: 'utf8'
    })
  )
  return payload.result?.entries || []
}

// ══ A. the Field Desk strip, from the course the desk continues ═════════════════════════════
await asDesk()
const stripBefore = await stripState()
await shotTo('live-01-desk-strip-before')
step('A1-strip-before', 'The Field Desk shows a Field Notes strip with no dummy rows', `strip ${stripBefore.state}, ${stripBefore.notes} rows`, {
  stripBefore
})

await clickExact(cdp, 'Open the section')
await cdp.wait(2600)
const pageMode = await cdp.json(`(() => ({
  document: document.querySelector('[data-cb-lesson-view]')?.getAttribute('data-cb-document') || null,
  blockSaves: document.querySelectorAll('[data-cb-block-save]').length,
  segmentSaves: [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Save to notebook').length
}))()`)
step('A2-section-open', 'The continued section offers a Save to notebook action on its own structured segment', JSON.stringify(pageMode), pageMode)
if (pageMode.segmentSaves === 0) throw new Error('the continued section offered no save action')

await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Save to notebook')
  b.scrollIntoView({ block: 'center' })
  return true
})()`)
await cdp.wait(300)
await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Save to notebook')
  b.click(); return true
})()`)
const savedA = await saveFromDialog(`${MARK_A} — why register shifts with the relationship.`, TAG_A)
await shotTo('live-02-save-dialog')
step('A3-saved', 'The editor is prefilled from the served segment and the save commits', 'dialog closed', {
  excerptChars: savedA.prefill.length,
  excerptHead: savedA.prefill.slice(0, 80),
  provenance: savedA.provenance.slice(0, 260)
})

const rowA = backendNotebook().find((entry) => (entry.note || '').includes(MARK_A))
if (!rowA) throw new Error('backend has no row with the strip marker')
step('A4-backend-readback', 'The saved row is on the backend with its course/objective provenance', 'row found', {
  entryId: rowA.entry_id,
  enrollmentId: rowA.enrollment_id,
  objectiveId: rowA.objective_id,
  kind: rowA.kind,
  tags: rowA.tags
})

await asDesk()
const stripAfter = await stripState()
await shotTo('live-03-desk-strip-after-reload')
step(
  'A5-fresh-run-strip',
  'After a fresh route mount the strip still shows the saved moment',
  stripAfter.text && stripAfter.text.includes(MARK_A) ? 'strip shows the marker' : 'marker missing from strip',
  { stripAfter }
)
if (!stripAfter.text || !stripAfter.text.includes(MARK_A)) throw new Error('strip did not show the saved marker after a fresh mount')

// The strip's own return path must land on the same exact block the save recorded.
if (rowA.source_ref) {
  let refA = null
  try {
    refA = JSON.parse(rowA.source_ref)
  } catch (error) {
    refA = null
  }
  if (refA && refA.block) {
    await clickIn('[data-cb-field-notes]', 'Open in textbook')
    await cdp.wait(2600)
    const fromStrip = await activeBlock()
    await shotTo('live-04-strip-exact-block')
    step('A6-strip-exact-section', 'The strip returns to the exact block the moment was saved from', fromStrip.block === refA.block ? 'focused block matches' : 'focus mismatch', {
      expectedBlock: refA.block,
      active: fromStrip
    })
    await asDesk()
  }
}

await clickIn('[data-cb-field-notes]', 'All field notes')
await cdp.waitFor(`!!document.querySelector('input[aria-label="Search the notebook"]')`, { timeout: 20000, label: 'notebook search' })
await cdp.wait(900)
const beforeA = await cdp.eval(`document.querySelectorAll('[data-cb-note-section]').length`)
const boxA = await fieldBox('input[aria-label="Search the notebook"]')
await cdp.click(boxA.x, boxA.y)
await cdp.type(MARK_A)
await cdp.wait(1400)
const afterA = await cdp.eval(`document.querySelectorAll('[data-cb-note-section]').length`)
const textA = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
await shotTo('live-04-strip-note-search')
step('A6-search', 'Search narrows this course\'s notebook to the saved moment', `${beforeA} → ${afterA}`, {
  markerVisible: textA.includes(MARK_A),
  sectionProvenance: textA.includes('Section ·'),
  courseProvenance: textA.includes('Course ·')
})

// ══ B. block save -> exact block return, on the enrollment that serves a block document ═════
await asDesk()
await openCourse(cdp, COURSE)
let block = null
for (const index of [1, 2, 0, 3]) {
  await tab(cdp, 'Textbook')
  const onSection = await cdp.eval(
    `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'All sections')`
  )
  if (onSection) {
    await clickExact(cdp, 'All sections')
    await cdp.wait(1200)
  }
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText || '').trim() === 'Open section')
    if (!bs[${index}]) return 'missing'
    bs[${index}].click(); return 'clicked'
  })()`)
  if (opened !== 'clicked') continue
  await cdp.wait(2600)
  const ready = await cdp
    .waitFor(`!!document.querySelector('[data-cb-block-save]')`, { timeout: 10000, label: 'block save' })
    .then(() => true)
    .catch(() => false)
  if (!ready) continue
  block = await cdp.json(`(() => {
    const holder = document.querySelector('[data-cb-block-save]')
    const holderBlock = holder.closest('[data-cb-block]')
    const button = [...holder.querySelectorAll('button')].find(b => (b.innerText || '').trim() === 'Save to notebook')
    button.scrollIntoView({ block: 'center' })
    const r = button.getBoundingClientRect()
    return {
      id: holderBlock.getAttribute('data-cb-block'),
      headline: (holderBlock.querySelector('h3') || {}).innerText || '',
      x: r.x + r.width / 2,
      y: r.y + r.height / 2
    }
  })()`)
  break
}
if (!block) throw new Error('no enrollment served a block document with a save action')
await shotTo('live-05-section-blocks')
step('B1-section-open', 'The block document renders one save action per block', 'block save controls present', {
  blockId: block.id,
  headline: block.headline,
  saveActions: await cdp.eval(`document.querySelectorAll('[data-cb-block-save]').length`)
})

await cdp.click(block.x, block.y)
const savedB = await saveFromDialog(`${MARK_B} — the explanation I want back.`, TAG_B)
await shotTo('live-06-block-save-dialog')
step('B2-saved', 'The block editor is prefilled with the block\'s own text and provenance', 'dialog closed', {
  excerptChars: savedB.prefill.length,
  provenance: savedB.provenance.slice(0, 260)
})

const rowB = backendNotebook().find((entry) => (entry.note || '').includes(MARK_B))
if (!rowB) throw new Error('backend has no row with the block marker')
const refB = JSON.parse(rowB.source_ref)
if (refB.block !== block.id) throw new Error(`ref block ${refB.block} != served block ${block.id}`)
step('B3-backend-readback', 'The saved row carries the exact block id and source ids', 'row found', {
  entryId: rowB.entry_id,
  enrollmentId: rowB.enrollment_id,
  objectiveId: rowB.objective_id,
  kind: rowB.kind,
  refBlock: refB.block,
  refSources: refB.sources || [],
  refArtifact: refB.artifact || null
})

await tab(cdp, 'Notebook')
await cdp.waitFor(`!!document.querySelector('input[aria-label="Search the notebook"]')`, { timeout: 20000, label: 'notebook search' })
await cdp.wait(900)
const beforeB = await cdp.eval(`document.querySelectorAll('[data-cb-note-section]').length`)
const boxB = await fieldBox('input[aria-label="Search the notebook"]')
await cdp.click(boxB.x, boxB.y)
await cdp.type(MARK_B)
await cdp.wait(1400)
const afterB = await cdp.eval(`document.querySelectorAll('[data-cb-note-section]').length`)
const textB = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
await shotTo('live-07-block-note-search')
step('B4-search', 'Search narrows the notebook to the saved block moment', `${beforeB} → ${afterB}`, {
  markerVisible: textB.includes(MARK_B),
  sectionProvenance: textB.includes('Section ·'),
  sourceProvenance: /Source · src_/.test(textB)
})

await clickExact(cdp, 'Open in textbook')
await cdp.wait(2600)
const landed = await activeBlock()
await shotTo('live-08-exact-block')
step('B5-exact-section', 'Open in textbook returns to the block the moment was saved from', landed.block === block.id ? 'focused block matches' : 'focus mismatch', {
  expectedBlock: block.id,
  active: landed
})

await cdp.send('Emulation.setDeviceMetricsOverride', { width: 460, height: 1100, deviceScaleFactor: 2, mobile: false })
await cdp.wait(700)
const narrow = await cdp.json(`(() => ({
  overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  scroll: document.documentElement.scrollWidth,
  client: document.documentElement.clientWidth
}))()`)
await shotTo('live-09-narrow-460')
step('B6-narrow-460', 'The section and its save actions fit 460 px without horizontal overflow', narrow.overflow ? 'overflow' : 'no overflow', narrow)
await cdp.send('Emulation.clearDeviceMetricsOverride')

observed.kind = 'live isolated Desktop capture (real backend, real plugin, no provider calls)'
observed.plugin_sha256 = process.env.M2FN_PLUGIN_SHA || null
observed.finished_at = new Date().toISOString()
observed.backend = process.env.CB013_BASE || 'http://127.0.0.1:44281'
writeFileSync(resolve(OUT, 'live-evidence.json'), `${JSON.stringify(observed, null, 2)}\n`)
console.log(`live proof: ${observed.steps.length} steps, ${observed.screenshots.length} screenshots`)
