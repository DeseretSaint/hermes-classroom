#!/usr/bin/env node
/**
 * Row 9 — parent edits an approved course, export is refused, re-approval restores it.
 *
 * Precondition (RPC half, docs/REVIEW_CB015-row9-rpc.json): the course had an ACTIVE final
 * approval and export.ready=true; plan.replan + parent.plan.edit then superseded the approval.
 * This script drives the Desktop half: the blocked Export screen, approving the plan, approving
 * the lesson set, and exporting the same files again.
 *
 *   node row9-ui.mjs <courseTitle> <outJson> <shotDir>
 */
import { connect, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'

const title = process.argv[2] || 'Japanese café basics, revised'
const outPath = process.argv[3]
const shots = process.argv[4] || 'docs/cb015-shots'
let cdp = await connect()
const steps = []

const SEL = 'button, a, [role=tab], [role=option], [role=radio], [role=menuitem], [role=button]'

const clickText = async (text, { exact = true, root = 'document' } = {}) => {
  const box = await cdp.json(`(() => {
    const all = [...${root}.querySelectorAll(${JSON.stringify(SEL)})]
    const el = all.find((e) => ${exact ? `(e.innerText||'').trim() === ${JSON.stringify(text)}` : `(e.innerText||'').includes(${JSON.stringify(text)})`})
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, label: (el.innerText || '').trim().slice(0, 80) }
  })()`)
  if (!box) return 'missing'
  await cdp.click(box.x, box.y)
  return 'clicked'
}

const snapshot = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? root.innerText || '' : ''
    const buttons = [...(root || document).querySelectorAll('button')]
    const byLabel = (label) => buttons.find((b) => (b.innerText || '').trim() === label)
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      hasExportGate: /EXPORT GATE/.test(text),
      lessonSetApproval: (text.match(/Lesson set approval\\n([^\\n]+)/) || [null, null])[1],
      planLine: (text.match(/Plan\\n([^\\n]+)/) || [null, null])[1],
      changesNeedReview: /Changes need review/.test(text),
      blockedCopy: (text.match(/(The plan is not approved[^\\n]*|Changes need review\\.[^\\n]*|Export is available[^\\n]*)/) || [null, null])[1],
      exportDisabled: (() => { const b = byLabel('Export the approved files'); return b ? b.disabled : null })(),
      exportPresent: Boolean(byLabel('Export the approved files')),
      approvePlanPresent: Boolean(byLabel('Approve plan')),
      approveLessonSetPresent: Boolean(byLabel('Approve this lesson set')),
      approvedLessonCopy: (text.match(/Lesson set approved[^\\n]*/) || [null, null])[1],
      exportedFiles: /EXPORTED FILES/.test(text),
      exportSentence: (text.match(/Export exp_[^\\n]+/) || [null, null])[1],
      slice: text.replace(/\\n{2,}/g, '\\n').slice(0, 1500)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  steps.push(value)
  console.log(JSON.stringify({ step, ...extra, approval: value.lessonSetApproval, cnr: value.changesNeedReview, blocked: value.blockedCopy, exportDisabled: value.exportDisabled, exported: value.exportedFiles }))
  return value
}

const selectView = async (name) => {
  const box = await cdp.json(`(() => {
    const el = document.querySelector('[role=combobox][aria-label="Studio view"]')
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!box) return 'no-trigger'
  await cdp.click(box.x, box.y)
  await cdp.wait(700)
  const opt = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('[role=option]')].find(o => (o.innerText||'').trim() === ${JSON.stringify(name)})
    if (!el) return null
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!opt) return 'no-option'
  await cdp.click(opt.x, opt.y)
  await cdp.wait(2200)
  const now = await cdp.eval(`(document.querySelector('[role=combobox][aria-label="Studio view"]')||{}).innerText || ''`)
  return String(now).trim() === name ? 'selected' : 'stuck:' + String(now).trim()
}

// ── navigate: sidebar Coursebook -> Parent Studio -> the revised course ─────────────────
cdp = await (await import('/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs')).hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await clickText('Coursebook')
await cdp.wait(2200)
await clickText('Parent Studio')
await cdp.wait(2200)
const rowClick = await cdp.json(`(() => {
  const wanted = ${JSON.stringify(title)}
  const openers = [...document.querySelectorAll('button')].filter((b) => (b.innerText || '').trim() === 'Open studio')
  const hit = openers.find((b) => {
    let node = b
    for (let i = 0; i < 8 && node; i += 1) {
      if ((node.innerText || '').includes(wanted)) return true
      node = node.parentElement
    }
    return false
  })
  if (!hit) return null
  hit.scrollIntoView({ block: 'center' })
  const r = hit.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (!rowClick) throw new Error(`no studio row titled ${JSON.stringify(title)}`)
await cdp.click(rowClick.x, rowClick.y)
await cdp.wait(3000)
await record('studio-opened')

// ── Export view: the gate must refuse ───────────────────────────────────────────────────
let clicked = await selectView('Export')
if (clicked !== 'selected') throw new Error(`Export view: ${clicked}`)
const blocked = await record('export-view-after-edit')
if (!blocked.changesNeedReview) console.log('NOTE: banner text not present; see slice')
await cdp.shot(`${shots}/row9-01-export-blocked-after-edit.png`)

// ── Plan view: approve the new draft plan ───────────────────────────────────────────────
console.log('plan view:', await selectView('Plan'))
await record('plan-view')
const approvePlan = await clickText('Approve plan')
if (approvePlan === 'missing') throw new Error('no Approve plan control on the draft plan')
await cdp.wait(3500)
await record('plan-approved', { approvePlan })
await cdp.shot(`${shots}/row9-02-plan-approved.png`)

// ── Export view again: still blocked until the lesson set is re-approved ────────────────
console.log('export view:', await selectView('Export'))
const stillBlocked = await record('export-view-plan-approved')
await cdp.shot(`${shots}/row9-03-export-blocked-changes-need-review.png`)

const approveSet = await clickText('Approve this lesson set')
if (approveSet === 'missing') throw new Error('no Approve this lesson set control')
await cdp.wait(4000)
const reapproved = await record('lesson-set-reapproved', { approveSet })
await cdp.shot(`${shots}/row9-04-lesson-set-reapproved.png`)

// ── export the approved files ───────────────────────────────────────────────────────────
const exportClick = await clickText('Export the approved files')
if (exportClick === 'missing') throw new Error('no export control')
await cdp.wait(6000)
const exported = await record('exported', { exportClick })
await cdp.shot(`${shots}/row9-05-exported-after-reapproval.png`)

await writeJson(outPath, {
  at: new Date().toISOString(),
  title,
  verdicts: {
    blockedAfterEdit: {
      changesNeedReview: blocked.changesNeedReview,
      lessonSetApproval: blocked.lessonSetApproval,
      blockedCopy: blocked.blockedCopy,
      exportDisabled: blocked.exportDisabled
    },
    stillBlockedAfterPlanApproval: {
      blockedCopy: stillBlocked.blockedCopy,
      exportDisabled: stillBlocked.exportDisabled
    },
    afterReapproval: {
      approvedLessonCopy: reapproved.approvedLessonCopy,
      exportDisabled: reapproved.exportDisabled,
      exportedFiles: exported.exportedFiles,
      exportSentence: exported.exportSentence
    }
  },
  steps
})
console.log('wrote', outPath)
cdp.close()
