/**
 * Loop 1 — Notebook: open, create, edit, persist through a full renderer reload.
 * Drives only the app's own controls; every assertion reads the live DOM.
 */
import { attach, openCourse, tab, openSectionByIndex, clickExact, shot, makeLog, routeText, OUT } from './cb-loops-lib.mjs'

const MARK = 'cb-loop-note-' + Date.now().toString(36)
const TAG = 'loop-proof-' + MARK.slice(-5)
const NOTE_V1 = `${MARK} v1 — polite form carries distance, not more affection.`
const NOTE_V2 = `${MARK} v2 — edited: です adds deliberate distance; the request makes it a confession.`

const cdp = await attach()
const log = makeLog()
const extra = { marker: MARK, tag: TAG }

const waitText = (text, timeout = 15000) =>
  cdp.waitFor(`(document.body.innerText || '').includes(${JSON.stringify(text)})`, { timeout, label: text })
const waitSearch = async (timeout = 15000) => {
  const present = () =>
    cdp.waitFor(`!!document.querySelector('input[aria-label="Search the notebook"]')`, { timeout, label: 'notebook search' })
  try {
    await present()
  } catch (error) {
    // The Notebook view can mount before its list query settles; re-enter the tab once.
    await tab(cdp, 'Notebook')
    await present()
  }
}
const activeEl = () => cdp.eval(`(() => { const a = document.activeElement; return a ? a.tagName + '|' + (a.getAttribute('id') || '') + '|' + ((a.innerText || '').trim().slice(0, 40)) : 'none' })()`)
const inDialog = async (label) =>
  cdp.json(`(() => {
    const d = document.querySelector('[role="dialog"]')
    if (!d) return null
    const b = [...d.querySelectorAll('button')].find(x => (x.innerText || '').trim() === ${JSON.stringify(label)})
    if (!b) return null
    const r = b.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
const dialogText = () => cdp.eval(`(document.querySelector('[role="dialog"]')?.innerText || '')`)
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

// ── 1. open the course and the first section that owns a teaching segment ───
await openCourse(cdp, 'Japanese affection and register — an L0 demonstration classroom')
let sectionIndex = null
for (const index of [1, 2, 0, 3]) {
  await openSectionByIndex(cdp, index)
  const hasSave = await cdp
    .waitFor(
      `[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText || '').trim() === 'Save to notebook')`,
      { timeout: 8000, label: 'save to notebook control' }
    )
    .then(() => true)
    .catch(() => false)
  if (hasSave) {
    sectionIndex = index
    break
  }
  const back = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='All sections'); if(b){b.click();return true} return false })()`)
  await cdp.wait(1500)
  if (!back) break
}
if (sectionIndex === null) throw new Error('no section with a teaching segment and Save to notebook')
await waitText('TEACHING SEGMENTS')
const sectionText = await routeText(cdp)
await log.add(cdp, 'section-open', 'A section with a teaching segment renders its lesson page with Save to notebook', 'section page rendered', {
  sectionIndex,
  sectionTitle: ((sectionText.match(/(?:Textbook\n)?([^\n]+)\n(?:Not started|In progress|Needs review|Independent evidence|Review due|Overridden)/) || [null, null])[1]),
  saveButtons: await cdp.eval(`(() => { const r = document.querySelector('[data-cb-route]'); return r ? [...r.querySelectorAll('button')].filter(b => (b.innerText||'').trim()==='Save to notebook').length : 0 })()`)
})
await shot(cdp, '10-notebook-section-before')

// ── 2. save a new notebook entry from the teaching segment ──────────────────
const beforeOpen = await activeEl()
await clickExact(cdp, 'Save to notebook')
await cdp.waitFor(`!!document.querySelector('[role="dialog"]')`, { timeout: 8000, label: 'save dialog' })
const prefill = await cdp.eval(`document.querySelector('#cb-note-excerpt')?.value || ''`)
await log.add(cdp, 'save-dialog-open', 'Editor prefilled with the segment excerpt, empty personal note, tags field', 'dialog opened', {
  excerptChars: prefill.length,
  excerptHead: prefill.slice(0, 80)
})
const v1 = await clearAndType('#cb-note-note', NOTE_V1)
const tags1 = await clearAndType('#cb-note-tags', TAG)
await log.add(cdp, 'notes-typed', 'Note and tag accepted into the editor', 'inputs hold typed values', { note: v1, tags: tags1 })
await shot(cdp, '11-notebook-save-dialog')

const confirm = await inDialog('Save to notebook')
if (!confirm) throw new Error('save confirm not found: ' + (await dialogText()))
await cdp.click(confirm.x, confirm.y)
const closed = await cdp.waitFor(`!document.querySelector('[role="dialog"]')`, { timeout: 20000, label: 'dialog close' })
await cdp.wait(500)
const focusAfterSave = await activeEl()
await log.add(cdp, 'entry-saved', 'Dialog closes after notebook.save commits and focus returns to the Save control', 'dialog closed', { waitedMs: closed, focusBefore: beforeOpen, focusAfter: focusAfterSave })

// ── 3. find it in the Notebook view by search ───────────────────────────────
await tab(cdp, 'Notebook')
await waitSearch()
const search = await fieldBox('input[aria-label="Search the notebook"]')
if (!search) throw new Error('notebook search field missing')
await cdp.click(search.x, search.y)
await cdp.type(MARK)
await cdp.wait(1200)
const found = await cdp.eval(`(document.querySelector('[data-cb-route]').innerText || '')`)
const entryCount = await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim()==='Edit note and tags').length`)
await log.add(cdp, 'notebook-search', 'One entry matches the unique note marker', found.includes(NOTE_V1) ? 'entry and note shown' : 'note missing', {
  entries: entryCount,
  noteVisible: found.includes(NOTE_V1)
})
await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] *')].find(e => (e.innerText || '').trim() === ${JSON.stringify(NOTE_V1)})
  if (el) el.scrollIntoView({ block: 'center' })
})()`)
await cdp.wait(600)
await shot(cdp, '12-notebook-entry-saved')

// ── 4. edit the entry, then confirm the edit lands ─────────────────────────
await clickExact(cdp, 'Edit note and tags')
await cdp.waitFor(`!!document.querySelector('#cb-edit-note')`, { timeout: 8000, label: 'inline editor' })
await cdp.wait(300)
const editPrefill = await cdp.eval(`document.querySelector('#cb-edit-note')?.value || ''`)
const editorFocus = await activeEl()
const v2 = await clearAndType('#cb-edit-note', NOTE_V2)
const tags2 = await clearAndType('#cb-edit-tags', `${TAG}, edited`)
await log.add(cdp, 'edit-open', 'Inline editor opens prefilled with the saved note and tags', 'fields prefilled', {
  prefillMatches: editPrefill.includes(MARK),
  note: v2,
  tags: tags2,
  focus: editorFocus
})
await shot(cdp, '12b-notebook-edit-open')
const saveChanges = await cdp.json(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'Save changes')
  if (!b) return null
  b.scrollIntoView({ block: 'center' })
  const r = b.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (!saveChanges) throw new Error('Save changes control missing')
await cdp.click(saveChanges.x, saveChanges.y)
await cdp.waitFor(`!document.querySelector('#cb-edit-note')`, { timeout: 20000, label: 'editor close' })
await cdp.wait(1200)
const afterEditFocus = await activeEl()
const afterEdit = await routeText(cdp)
await log.add(cdp, 'entry-edited', 'notebook.update keeps one entry with the new note and tags; focus stays in the notebook', afterEdit.includes(NOTE_V2) ? 'edited note visible' : 'edited note missing', {
  v2Visible: afterEdit.includes(NOTE_V2),
  oldNoteGone: !afterEdit.includes(NOTE_V1),
  focusAfter: afterEditFocus
})

// ── 5. full renderer reload, then re-find the entry ─────────────────────────
const beforeReloadHash = await cdp.eval('location.hash')
await cdp.reload()
await cdp.wait(4000)
// wait for the shell to finish mounting, then route back through the sidebar
await cdp.waitFor(`!!document.querySelector('button')`, { timeout: 20000, label: 'shell mount' })
await openCourse(cdp, 'Japanese affection and register — an L0 demonstration classroom')
await tab(cdp, 'Notebook')
await waitSearch(20000)
const search2 = await fieldBox('input[aria-label="Search the notebook"]')
await cdp.click(search2.x, search2.y)
await cdp.type(MARK)
await cdp.wait(1500)
const afterReload = await routeText(cdp)
await log.add(cdp, 'reload-persistence', 'After a full renderer reload the edited entry still has the edited note and both tags', afterReload.includes(NOTE_V2) ? 'edited content survived reload' : 'content lost', {
  hashBefore: beforeReloadHash,
  hashAfter: await cdp.eval('location.hash'),
  noteSurvived: afterReload.includes(NOTE_V2),
  originalGone: !afterReload.includes(NOTE_V1),
  tagVisible: afterReload.includes(TAG)
})
await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] *')].find(e => (e.innerText || '').trim() === ${JSON.stringify(NOTE_V2)})
  if (el) el.scrollIntoView({ block: 'center' })
})()`)
await cdp.wait(600)
await shot(cdp, '13-notebook-after-reload')

console.log('ERRORS:', JSON.stringify(cdp.errors))
await log.add(cdp, 'console', 'No renderer exceptions or console errors during the loop', `${cdp.errors.length} captured`, { errors: cdp.errors })
const path = await log.write('docs/cb-loops-notebook.json')
console.log('LOG', path, 'OUT', OUT)
cdp.close()
