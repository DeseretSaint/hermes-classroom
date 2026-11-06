#!/usr/bin/env node
/**
 * Row 9, part 2: generate the lesson set for the replanned course, re-approve it, export.
 * Continues from the state row9-ui.mjs left (plan v3 approved, approval superseded).
 *
 *   node row9-generate.mjs <outJson> <shotDir>
 */
import { connect, writeJson } from '/home/deseretsaint/Projects/hermes-classroom/scripts/cb015-lib.mjs'
const outPath = process.argv[2]
const shots = process.argv[3] || 'docs/cb015-shots'
const cdp = await connect()
const steps = []

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
  await cdp.wait(2000)
  return String(await cdp.eval(`(document.querySelector('[role=combobox][aria-label="Studio view"]')||{}).innerText || ''`)).trim() === name ? 'selected' : 'stuck'
}

const clickText = async (text) => {
  const box = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('[data-cb-route] button')].find(e => (e.innerText||'').trim() === ${JSON.stringify(text)})
    if (!el || el.disabled) return el ? 'disabled' : null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
  })()`)
  if (!box) return 'missing'
  if (box === 'disabled') return 'disabled'
  await cdp.click(box.x, box.y); return 'clicked'
}

const snapshot = () =>
  cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const t = root ? root.innerText || '' : ''
    const byLabel = (l) => [...(root||document).querySelectorAll('button')].find(b => (b.innerText||'').trim() === l)
    return {
      text: t.replace(/\\n{2,}/g,'\\n').slice(0,1600),
      planLine: (t.match(/Plan\\n([^\\n]+)/) || [null,null])[1],
      lessonSetApproval: (t.match(/Lesson set approval\\n([^\\n]+)/) || [null,null])[1],
      approvedLessonCopy: (t.match(/Lesson set approved[^\\n]*/) || [null,null])[1],
      blockedCopy: (t.match(/(Changes need review\\.[^\\n]*|The plan is not approved[^\\n]*|Export is available[^\\n]*|No lesson pages[^\\n]*|[A-Z][^\\n]*blocked[^\\n]*)/) || [null,null])[1],
      exportDisabled: (() => { const b = byLabel('Export the approved files'); return b ? b.disabled : null })(),
      exportedFiles: /EXPORTED FILES/.test(t),
      exportSentence: (t.match(/Export exp_[^\\n]+/) || [null,null])[1],
      jobText: (t.match(/(Working[^\\n]*|Finished[^\\n]*|Failed[^\\n]*)/) || [null,null])[1]
    }
  })()`)

const record = async (step, extra = {}) => {
  const v = { step, at: new Date().toISOString(), ...(await snapshot()), ...extra }
  steps.push(v)
  console.log(JSON.stringify({ step, ...extra, plan: v.planLine, approval: v.lessonSetApproval, blocked: v.blockedCopy, exportDisabled: v.exportDisabled, job: v.jobText, exported: v.exportedFiles }))
  return v
}

console.log('plan view:', await selectView('Plan'))
await record('plan-view')
const gen = await clickText('Generate lessons')
console.log('generate:', gen)
await record('generate-clicked', { gen })

// Poll the job line the UI itself renders, up to 6 minutes.
let settled = null
for (let i = 0; i < 72; i += 1) {
  await cdp.wait(5000)
  const s = await snapshot()
  const line = (s.text.match(/(Finished[^\\n]*|Failed[^\\n]*|Interrupted[^\\n]*)/) || [null,null])[1]
  if (line) { settled = line; break }
  if (i % 6 === 0) console.log('waiting…', Math.round((i * 5) / 60), 'min')
}
await record('generation-settled', { settled })
await cdp.shot(`${shots}/row9-06-generation-settled.png`)

if (!settled || !/Finished/.test(settled)) {
  await writeJson(outPath, { at: new Date().toISOString(), outcome: 'generation did not finish', steps })
  console.log('stopped: generation did not finish')
  cdp.close()
  process.exit(0)
}

console.log('export view:', await selectView('Export'))
const afterGen = await record('export-view-after-generation')
const approve = await clickText('Approve this lesson set')
console.log('approve lesson set:', approve)
await cdp.wait(4000)
const reapproved = await record('lesson-set-reapproved', { approve })
await cdp.shot(`${shots}/row9-07-lesson-set-reapproved.png`)

const exportClick = await clickText('Export the approved files')
console.log('export click:', exportClick)
await cdp.wait(8000)
const exported = await record('exported', { exportClick })
await cdp.shot(`${shots}/row9-08-exported-after-reapproval.png`)

await writeJson(outPath, {
  at: new Date().toISOString(),
  outcome: 'complete',
  verdicts: {
    generationSettled: settled,
    blockedBeforeReapproval: { approval: afterGen.lessonSetApproval, blocked: afterGen.blockedCopy, exportDisabled: afterGen.exportDisabled },
    afterReapproval: { approval: reapproved.lessonSetApproval, approvedLessonCopy: reapproved.approvedLessonCopy, exportDisabled: reapproved.exportDisabled },
    exported: { files: exported.exportedFiles, sentence: exported.exportSentence }
  },
  steps
})
console.log('wrote', outPath)
cdp.close()
