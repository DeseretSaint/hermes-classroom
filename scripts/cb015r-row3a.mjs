#!/usr/bin/env node
/**
 * CB-015 residual — row 3, part A: new goal → queued plan generation → cancel in the UI →
 * leave the studio → come back (reattach to the same course and job) → queue the stage again.
 *
 * The job tick is stopped by the operator before this runs, so the plan job is deterministically
 * QUEUED when Cancel generation is clicked. Every click is a real DOM/geometry click; the brief is
 * typed through native value setters + input events, exactly what a person does.
 *
 *   CB015_CDP_PORT=9341 node scripts/cb015r-row3a.mjs
 */
import { connect, writeJson, rel } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.send('Page.enable')
const trace = { startedAt: new Date().toISOString(), steps: [], shots: [], jobIds: {} }
const log = (step, data = {}) => {
  const entry = { step, at: new Date().toISOString(), ...data }
  trace.steps.push(entry)
  console.log(JSON.stringify(entry))
  return entry
}
const shot = async (name) => {
  const path = await cdp.shot(rel(`docs/cb015-residual/${name}.png`))
  trace.shots.push(path)
  return path
}
const routeText = () =>
  cdp.eval(`((document.querySelector('[data-cb-route]') || document.body).innerText || '').replace(/\\n{2,}/g, '\\n')`)
const jobState = () =>
  cdp.json(`(() => {
    const line = document.querySelector('[data-cb-job-state]')
    return {
      jobId: line ? line.getAttribute('data-cb-job-id') : null,
      state: line ? line.getAttribute('data-cb-job-state') : null,
      text: line ? (line.innerText || '').replace(/\\n{2,}/g, '\\n') : null,
      buttons: [...document.querySelectorAll('[data-cb-route] button')].map(b => (b.innerText || '').trim()).filter(Boolean)
    }
  })()`)
const setValue = async (id, value) =>
  cdp.eval(`(() => {
    const el = document.getElementById(${JSON.stringify(id)})
    if (!el) return 'missing'
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, ${JSON.stringify(value)})
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return el.value
  })()`)
const clickId = (id) => cdp.eval(`(() => { const el = document.getElementById(${JSON.stringify(id)}); if (!el) return false; el.click(); return true })()`)

// 0. The coursebook route is already mounted; go to Parent Studio.
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(1200)
await cdp.clickText('Parent Studio')
await cdp.wait(1400)
await log('studio-destination', { text: (await routeText()).slice(0, 260) })
await shot('row3-01-studio-empty')

// 1. New goal: the §10 brief.
await cdp.clickText('Write a lesson brief')
await cdp.waitFor(`!!document.getElementById('cb-brief-title')`, { label: 'brief form', timeout: 10000 })
await log('brief-form-open')
const fields = {
  'cb-brief-title': 'Boiling water and steam safety — one kitchen demonstration',
  'cb-brief-goal':
    'Explain, in their own words, why steam burns worse than boiling water, and show the one safe place to stand while an adult pours hot water into a cup.',
  'cb-brief-start': 'Has watched water boil with an adult; can read short sentences.',
  'cb-brief-reading': 'Year 4, short sentences with a few technical words explained inline',
  'cb-brief-materials': 'kettle\nmetal spoon\nheat-proof jug\nthermometer',
  'cb-brief-exclusions': 'no open flame\nno child handling the kettle',
  'cb-brief-supervision': 'An adult pours and stands between the child and the kettle; the child watches from a marked line.'
}
const filled = {}
for (const [id, value] of Object.entries(fields)) filled[id] = await setValue(id, value)
await clickId('cb-brief-egress')
await cdp.wait(400)
await log('brief-filled', { filled, egress: await cdp.eval(`document.getElementById('cb-brief-egress').checked`) })
await shot('row3-02-brief-filled')

const disabled = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Create the course and queue the plan')
  return b ? b.disabled : 'missing'
})()`)
await log('submit-affordance', { disabled })
await cdp.clickText('Create the course and queue the plan')
await cdp.waitFor(`!!document.querySelector('[data-cb-job-state]')`, { label: 'plan job line', timeout: 20000 })
await cdp.wait(400)
const queued = await jobState()
trace.jobIds.plan = queued.jobId
await log('plan-job-created', queued)
await shot('row3-03-plan-queued')

// 2. Cancel generation in the UI while the job is queued (no tick is running).
await cdp.clickText('Cancel generation')
await cdp.waitFor(
  `(() => { const l = document.querySelector('[data-cb-job-state]'); return l && ['cancelled','cancel_requested','cancelling'].includes(l.getAttribute('data-cb-job-state')) })()`,
  { label: 'cancelled job state', timeout: 20000 }
)
await cdp.wait(500)
const cancelled = await jobState()
await log('cancelled', cancelled)
await shot('row3-04-cancelled')

// 3. Leave the studio entirely, then reattach to the same course from the list.
await cdp.clickText('Courses')
await cdp.wait(1200)
await cdp.clickText('Parent Studio')
await cdp.wait(1500)
const listText = await routeText()
await log('studio-list-after-cancel', { text: listText.slice(0, 400) })
await cdp.clickText('Open studio')
await cdp.wait(1600)
const reattached = await jobState()
await log('reattached', { ...reattached, courseText: (await routeText()).slice(0, 500) })
await shot('row3-05-reattached-cancelled')

const briefStillThere = await cdp.eval(`/Boiling water and steam safety/.test(document.body.innerText || '')`)
await log('brief-preserved-on-reattach', { briefStillThere })

// 4. Queue the same stage again from the cancelled job's own brief.
await cdp.clickText('Run this stage again')
await cdp.waitFor(
  `(() => { const l = document.querySelector('[data-cb-job-state]'); return l && l.getAttribute('data-cb-job-id') !== ${JSON.stringify(queued.jobId)} })()`,
  { label: 'new plan job id', timeout: 30000 }
)
await cdp.wait(600)
const retried = await jobState()
trace.jobIds.retry = retried.jobId
await log('stage-requeued', retried)
await shot('row3-06-requeued')

trace.finishedAt = new Date().toISOString()
trace.result = {
  cancelledState: cancelled.state,
  cancelledJobId: queued.jobId,
  retryJobId: retried.jobId,
  retryState: retried.state,
  briefPreservedOnReattach: briefStillThere,
  sameCourseAfterReattach: Boolean(reattached.text && /Boiling water and steam safety/.test(reattached.text))
}
console.log('RESULT ' + JSON.stringify(trace.result))
writeJson(rel('docs/REVIEW_CB015-row3a.json'), trace)
cdp.close()
