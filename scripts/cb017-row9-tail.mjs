#!/usr/bin/env node
/**
 * Row 9 — TAIL ONLY. Picks up after the lessons job reached `completed`:
 * approve the generated lesson set, then export the approved files.
 *
 * Writes docs/REVIEW_CB017-row9-ui.json and stills row9r-06..09.
 * Never touches row9r-01..05 (those are committed with pinned hashes in REVIEW_CB017-FINAL §8).
 *
 *   node cb017-row9-tail.mjs <courseTitle> <outJson> <shotDir>
 */
import { connect, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'

const title = process.argv[2] || 'Japanese café basics, revised'
const outPath = process.argv[3] || 'docs/REVIEW_CB017-row9-ui.json'
const shots = process.argv[4] || 'docs/cb017-shots'
const JOB = 'job_2390ab7ac33d4bff9e62d8eae5649ee7'

let cdp = await connect()
const steps = []
const SEL = 'button, a, [role=tab], [role=option], [role=radio], [role=menuitem], [role=button]'

const clickText = async (text, { exact = true } = {}) => {
  const box = await cdp.json(`(() => {
    const all = [...document.querySelectorAll(${JSON.stringify(SEL)})]
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
      planLine: (text.match(/Plan\\n(approved[^\\n]*)/) || [null, null])[1],
      changesNeedReview: /Changes need review/.test(text),
      blockedCopy: (text.match(/(The generated lesson set has not been approved[^\\n]*|You edited the plan[^\\n]*)/) || [null, null])[1],
      exportDisabled: (() => { const b = byLabel('Export the approved files'); return b ? b.disabled : null })(),
      exportPresent: Boolean(byLabel('Export the approved files')),
      approveLessonSetPresent: Boolean(byLabel('Approve this lesson set')),
      approvedLessonCopy: (text.match(/Lesson set approved[^\\n]*/) || [null, null])[1],
      approvedHash: (text.match(/Approved content hash\\n([^\\n]+)/) || [null, null])[1],
      currentHash: (text.match(/Current content hash\\n([^\\n]+)/) || [null, null])[1],
      exportedFiles: /EXPORTED FILES/.test(text),
      exportSentence: (text.match(/Export exp_[^\\n]+/) || [null, null])[1],
      fileLines: (text.match(/EXPORTED FILES\\n([\\s\\S]{0,600})/) || [null, null])[1] || null,
      slice: text.replace(/\\n{2,}/g, '\\n').slice(0, 1600)
    }
  })()`)

const record = async (step, extra = {}) => {
  const value = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  steps.push(value)
  console.log(JSON.stringify({
    step, extra,
    approval: value.lessonSetApproval,
    exportDisabled: value.exportDisabled,
    approved: value.approvedLessonCopy,
    exported: value.exportedFiles,
    sentence: value.exportSentence
  }))
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

// ── fresh load: Coursebook -> Parent Studio -> the revised course ────────────────────────
cdp = await (await import('/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs')).hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route' })
await clickText('Coursebook'); await cdp.wait(2200)
await clickText('Parent Studio'); await cdp.wait(2200)
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
await record('studio-opened', { lessonsJob: JOB })

// ── 06: the export gate must still refuse a plan-approved, lesson-set-unapproved course ──
const view = await selectView('Export')
if (view !== 'selected') throw new Error(`Export view: ${view}`)
const blocked = await record('export-gate-blocked')
await cdp.shot(`${shots}/row9r-06-export-gate-blocked.png`)

// ── 07: approve the generated lesson set (the step the plan approval does not cover) ─────
const approveSet = await clickText('Approve this lesson set')
if (approveSet === 'missing') throw new Error('no Approve this lesson set control')
await cdp.wait(4500)
const reapproved = await record('lesson-set-approved', { approveSet })
await cdp.shot(`${shots}/row9r-07-lesson-set-approved.png`)

// ── 08: export the approved files ────────────────────────────────────────────────────────
const exportClick = await clickText('Export the approved files')
if (exportClick === 'missing') throw new Error('no export control')
await cdp.wait(7000)
const exported = await record('exported', { exportClick })
await cdp.shot(`${shots}/row9r-08-exported-files.png`)

// ── 09: the exported file list itself ────────────────────────────────────────────────────
await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('*')].find((n) => (n.innerText || '').trim().startsWith('EXPORTED FILES'))
  if (el) el.scrollIntoView({ block: 'center' })
  return true
})()`)
await cdp.wait(900)
await cdp.shot(`${shots}/row9r-09-exported-files-detail.png`)

await writeJson(outPath, {
  at: new Date().toISOString(),
  title,
  lessonsJob: JOB,
  branch: 'wt/cb-017-atlas',
  verdicts: {
    gateBlockedBeforeApproval: {
      changesNeedReview: blocked.changesNeedReview,
      lessonSetApproval: blocked.lessonSetApproval,
      blockedCopy: blocked.blockedCopy,
      exportDisabled: blocked.exportDisabled,
      approvedHash: blocked.approvedHash,
      currentHash: blocked.currentHash
    },
    afterLessonSetApproval: {
      lessonSetApproval: reapproved.lessonSetApproval,
      approvedLessonCopy: reapproved.approvedLessonCopy,
      approvedHash: reapproved.approvedHash,
      exportDisabled: reapproved.exportDisabled
    },
    afterExport: {
      exportedFiles: exported.exportedFiles,
      exportSentence: exported.exportSentence,
      fileLines: exported.fileLines
    }
  },
  ok: Boolean(blocked.changesNeedReview && blocked.exportDisabled === true &&
              reapproved.exportDisabled === false && exported.exportedFiles),
  steps
})
console.log('wrote', outPath, 'ok=', Boolean(exported.exportedFiles))
cdp.close()
