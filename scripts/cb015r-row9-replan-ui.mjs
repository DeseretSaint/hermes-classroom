#!/usr/bin/env node
/**
 * Row 9 (follow-up) — a parent edits an APPROVED plan and must reach export again.
 *
 * Drives the whole loop through the Desktop, with the backend's plan.replan carry in place:
 *   Start a new plan version -> retitle an objective -> Save changes -> Approve plan
 *   -> Generate lessons -> (job settles) -> Export: Approve this lesson set -> Export the approved files
 *
 *   node cb015r-row9-replan-ui.mjs <courseTitle> <outJson> <shotDir>
 */
import { connect, hardReload, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'

const title = process.argv[2] || 'Japanese café basics, revised'
const outPath = process.argv[3]
const shots = process.argv[4] || 'docs/cb015-shots'
const NEW_TITLE = `Name one warm and one cold thing in the kitchen (edited ${new Date().toISOString().slice(11, 19)}Z)`
let cdp = await connect()
const steps = []

const SEL = 'button, a, [role=tab], [role=option], [role=radio], [role=menuitem], [role=button]'

const boxOf = (expr) =>
  cdp.json(`(() => {
    const el = ${expr}
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)

const clickText = async (text, { exact = true, root = 'document' } = {}) => {
  const box = await boxOf(`[...${root}.querySelectorAll(${JSON.stringify(SEL)})].find((e) => ${
    exact ? `(e.innerText||'').trim() === ${JSON.stringify(text)}` : `(e.innerText||'').includes(${JSON.stringify(text)})`
  })`)
  if (!box) return 'missing'
  await cdp.click(box.x, box.y)
  return 'clicked'
}

const snapshot = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? root.innerText || '' : ''
    const NL = String.fromCharCode(10)
    const lines = text.split(NL).map((line) => line.trim())
    const after = (label) => {
      const at = lines.indexOf(label)
      return at >= 0 ? lines[at + 1] : null
    }
    const buttons = [...(root || document).querySelectorAll('button')]
    const byLabel = (label) => buttons.find((b) => (b.innerText || '').trim() === label)
    const jobEls = [...document.querySelectorAll('[data-cb-job-state]')]
    const jobs = jobEls.map((el) => ({
      id: el.getAttribute('data-cb-job-id'),
      state: el.getAttribute('data-cb-job-state'),
      text: (el.innerText || '').split(NL).filter(Boolean).join(' | ').slice(0, 300)
    }))
    const job = jobEls.length ? jobEls[jobEls.length - 1] : null
    const docGap = document.querySelector('[data-cb-plan-document]')
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      planLine: after('Plan'),
      editing: Boolean(document.querySelector('input[aria-label^="Objective 1 title"]')),
      generatePresent: Boolean(byLabel('Generate lessons') || byLabel('Generate missing lessons')),
      generateLabel: (byLabel('Generate lessons') || byLabel('Generate missing lessons') || {}).innerText || null,
      startVersionPresent: Boolean(byLabel('Start a new plan version')),
      approvePlanPresent: Boolean(byLabel('Approve plan')),
      savePresent: Boolean(byLabel('Save changes')),
      documentGap: docGap ? docGap.innerText : null,
      jobId: job ? job.getAttribute('data-cb-job-id') : null,
      jobState: job ? job.getAttribute('data-cb-job-state') : null,
      jobText: job ? (job.innerText || '').split(NL).filter(Boolean).join(' | ').slice(0, 300) : null,
      jobs,
      lessonSetApproval: after('Lesson set approval'),
      changesNeedReview: /Changes need review/.test(text),
      approveLessonSetPresent: Boolean(byLabel('Approve this lesson set')),
      exportDisabled: (() => { const b = byLabel('Export the approved files'); return b ? b.disabled : null })(),
      exportedFiles: /EXPORTED FILES/.test(text),
      exportSentence: lines.find((line) => line.startsWith('Export exp_')) || null,
      slice: lines.filter(Boolean).join(' | ').slice(0, 1200)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  steps.push(value)
  console.log(JSON.stringify({
    step, ...extra, plan: value.planLine, editing: value.editing, gen: value.generateLabel,
    job: value.jobId, jobState: value.jobState, gap: Boolean(value.documentGap),
    cnr: value.changesNeedReview, approval: value.lessonSetApproval,
    exportDisabled: value.exportDisabled, exported: value.exportedFiles
  }))
  return value
}

const selectView = async (name) => {
  const box = await boxOf(`document.querySelector('[role=combobox][aria-label="Studio view"]')`)
  if (!box) return 'no-trigger'
  await cdp.click(box.x, box.y)
  await cdp.wait(700)
  const opt = await boxOf(`[...document.querySelectorAll('[role=option]')].find(o => (o.innerText||'').trim() === ${JSON.stringify(name)})`)
  if (!opt) return 'no-option'
  await cdp.click(opt.x, opt.y)
  await cdp.wait(2200)
  const now = await cdp.eval(`(document.querySelector('[role=combobox][aria-label="Studio view"]')||{}).innerText || ''`)
  return String(now).trim() === name ? 'selected' : 'stuck:' + String(now).trim()
}

const setObjectiveTitle = async (ordinal, value) => {
  const box = await boxOf(`document.querySelector('input[aria-label="Objective ${ordinal} title"]')`)
  if (!box) return 'missing'
  await cdp.click(box.x, box.y)
  await cdp.eval(`(() => {
    const el = document.querySelector('input[aria-label="Objective ${ordinal} title"]')
    el.focus(); el.setSelectionRange(0, el.value.length)
    return el.value
  })()`)
  await cdp.type(value)
  await cdp.wait(300)
  return await cdp.eval(`document.querySelector('input[aria-label="Objective ${ordinal} title"]').value`)
}

const waitJobTerminal = async (baseIds, timeoutMs) => {
  const started = Date.now()
  let last = null
  while (Date.now() - started < timeoutMs) {
    last = await snapshot()
    const fresh = (last.jobs || []).filter((job) => job.id && !baseIds.includes(job.id))
    if (fresh.length > 0) {
      const target = fresh[fresh.length - 1]
      if (['completed', 'completed_late', 'failed', 'cancelled', 'interrupted_requires_retry'].includes(target.state)) {
        return { ...last, jobId: target.id, jobState: target.state, jobText: target.text }
      }
    }
    await cdp.wait(2000)
  }
  return last
}

// ── navigate ───────────────────────────────────────────────────────────────────────────
cdp = await hardReload(cdp)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await cdp.wait(1500)
await clickText('Coursebook')
await cdp.wait(2200)
await clickText('Parent Studio')
await cdp.wait(2200)
const rowClick = await boxOf(`(() => {
  const wanted = ${JSON.stringify(title)}
  const openers = [...document.querySelectorAll('button')].filter((b) => (b.innerText || '').trim() === 'Open studio')
  return openers.find((b) => {
    let node = b
    for (let i = 0; i < 8 && node; i += 1) {
      if ((node.innerText || '').includes(wanted)) return true
      node = node.parentElement
    }
    return false
  })
})()`)
if (!rowClick) throw new Error(`no studio row titled ${JSON.stringify(title)}`)
await cdp.click(rowClick.x, rowClick.y)
await cdp.wait(3000)

// ── Plan view, the dead-end state ──────────────────────────────────────────────────────
const planView = await selectView('Plan')
if (planView !== 'selected') throw new Error(`Plan view: ${planView}`)
const before = await record('plan-view-before-replan')
await cdp.shot(`${shots}/row9r-01-plan-before-replan.png`)

// ── Start a new plan version (plan.replan) ─────────────────────────────────────────────
const replan = await clickText('Start a new plan version')
if (replan === 'missing') throw new Error('no Start a new plan version control')
await cdp.wait(2500)
await cdp.waitFor(`!!document.querySelector('input[aria-label^="Objective 1 title"]')`, { timeout: 20000, label: 'editor after replan' })
await cdp.waitFor(
  `(() => {
    const inputs = [...document.querySelectorAll('input[aria-label$=" title"]')]
    return inputs.length > 0 && inputs.every((i) => (i.value || '').trim().length > 0)
  })()`,
  { timeout: 20000, label: 'objective titles rendered in the editor' }
)
const afterReplan = await record('replanned-into-editor', { replan })
await cdp.shot(`${shots}/row9r-02-replanned-editor.png`)

// ── Retitle the first objective and save (parent.plan.edit) ────────────────────────────
const typed = await setObjectiveTitle(1, NEW_TITLE)
const save = await clickText('Save changes')
if (save === 'missing') throw new Error(`no Save changes control (typed=${typed})`)
await cdp.wait(3500)
await cdp.waitFor(`!document.querySelector('input[aria-label^="Objective 1 title"]')`, { timeout: 20000, label: 'editor closed after save' })
const saved = await record('plan-edited-and-saved', { typed })
if (saved.planLine === afterReplan.planLine) throw new Error(`the save produced no new plan version: ${saved.slice}`)
await cdp.shot(`${shots}/row9r-03-plan-saved.png`)

// ── Approve the plan ──────────────────────────────────────────────────────────────────
const approve = await clickText('Approve plan')
if (approve === 'missing') throw new Error('no Approve plan control on the draft plan')
await cdp.wait(3500)
const approved = await record('plan-approved', { approve })
await cdp.shot(`${shots}/row9r-04-plan-approved.png`)
if (!approved.generatePresent) throw new Error(`Generate lessons is not offered after the carried replan: ${JSON.stringify(approved.slice)}`)

// ── Generate lessons (the step that used to fail with INTERNAL_ERROR) ─────────────────
const gen = await clickText(approved.generateLabel || 'Generate lessons')
if (gen === 'missing') throw new Error('no Generate lessons control')
await cdp.wait(4000)
const started = await record('lessons-started', { gen })
await cdp.shot(`${shots}/row9r-05-lessons-started.png`)
const baseIds = (started.jobs || []).map((job) => job.id).filter(Boolean)
const settledJob = await waitJobTerminal(baseIds, 20 * 60 * 1000)
const lessons = await record('lessons-settled')
await cdp.shot(`${shots}/row9r-06-lessons-settled.png`)
if (settledJob.jobState !== 'completed' && settledJob.jobState !== 'completed_late') {
  throw new Error(`lessons job did not complete: ${settledJob.jobState} ${settledJob.jobText}`)
}

// ── Export view: approve the lesson set, then export ──────────────────────────────────
const exportView = await selectView('Export')
if (exportView !== 'selected') throw new Error(`Export view: ${exportView}`)
await cdp.waitFor(
  `[...document.querySelectorAll('button')].some((b) => (b.innerText || '').trim() === 'Approve this lesson set')`,
  { timeout: 40000, label: 'Approve this lesson set' }
)
const blocked = await record('export-view-before-reapproval')
await cdp.shot(`${shots}/row9r-07-export-before-reapproval.png`)

const approveSet = await clickText('Approve this lesson set')
if (approveSet === 'missing') throw new Error('no Approve this lesson set control')
await cdp.waitFor(
  `(() => { const root = document.querySelector('[data-cb-route]'); return root ? !/Changes need review/.test(root.innerText || '') : false })()`,
  { timeout: 30000, label: 'approval no longer needs review' }
)
const reapproved = await record('lesson-set-reapproved', { approveSet })
await cdp.shot(`${shots}/row9r-08-lesson-set-reapproved.png`)

const exportClick = await clickText('Export the approved files')
if (exportClick === 'missing') throw new Error('no Export the approved files control')
await cdp.waitFor(
  `(() => { const root = document.querySelector('[data-cb-route]'); return root ? /EXPORTED FILES/.test(root.innerText || '') : false })()`,
  { timeout: 60000, label: 'exported files' }
)
const exported = await record('exported', { exportClick })
await cdp.shot(`${shots}/row9r-09-exported.png`)

await writeJson(outPath, {
  at: new Date().toISOString(),
  title,
  newTitle: NEW_TITLE,
  verdicts: {
    before: { plan: before.planLine, generate: before.generateLabel, gap: before.documentGap },
    afterReplan: { plan: afterReplan.planLine, editing: afterReplan.editing },
    approved: { plan: approved.planLine, generate: approved.generateLabel, gap: approved.documentGap },
    lessons: { jobId: settledJob.jobId, state: settledJob.jobState, text: settledJob.jobText },
    exportGate: { changesNeedReview: blocked.changesNeedReview, approval: blocked.lessonSetApproval, disabled: blocked.exportDisabled },
    afterReapproval: { approval: reapproved.lessonSetApproval, disabled: reapproved.exportDisabled },
    export: { files: exported.exportedFiles, sentence: exported.exportSentence }
  },
  steps
})
console.log('wrote', outPath)
cdp.close()
