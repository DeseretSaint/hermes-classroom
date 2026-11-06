#!/usr/bin/env node
/**
 * CB-015 residual — row 3, part B: wait for the requeued plan job, then edit the draft plan in the
 * UI and approve it. Result: one UI loop = new goal → cancel → reattach → approve edited plan.
 *
 *   CB015_CDP_PORT=9341 CB015_JOB=job_... node scripts/cb015r-row3b.mjs
 */
import { connect, writeJson, rel } from './cb015-lib.mjs'

const JOB = process.env.CB015_JOB
if (!JOB) throw new Error('CB015_JOB is required')
const BASE = process.env.CB013_BASE || 'http://127.0.0.1:44225'
const TOKEN = process.env.CB013_TOKEN || 'cb013-test-token'

async function job() {
  const body = {
    contract: 'cb.rpc',
    contract_version: 6,
    method: 'jobs.get',
    operation_id: `cb015r-${Date.now()}`,
    idempotency_key: `cb015r-${Date.now()}`,
    payload: { job_id: JOB }
  }
  const response = await fetch(`${BASE}/api/plugins/coursebook/rpc?profile=`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
    body: JSON.stringify(body)
  })
  return response.json()
}

const cdp = await connect()
await cdp.send('Page.enable')
await cdp.reload()
await cdp.wait(3000)
const trace = { startedAt: new Date().toISOString(), jobId: JOB, steps: [], shots: [] }
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
const chooseView = async (wanted) => {
  await cdp.eval(`document.getElementById('cb-studio-view').click()`)
  await cdp.wait(500)
  const dispatched = await cdp.eval(`(() => {
    const opt = [...document.querySelectorAll('[role="option"]')].find(o => (o.innerText || '').trim() === ${JSON.stringify(wanted)})
    if (!opt) return 'no-option'
    const rect = opt.getBoundingClientRect()
    const init = { bubbles: true, cancelable: true, composed: true, pointerId: 1, isPrimary: true, button: 0, buttons: 1,
                   clientX: rect.x + rect.width / 2, clientY: rect.y + rect.height / 2 }
    opt.dispatchEvent(new PointerEvent('pointerdown', init))
    opt.dispatchEvent(new PointerEvent('pointerup', { ...init, buttons: 0 }))
    opt.click()
    return 'dispatched'
  })()`)
  await cdp.wait(1600)
  return dispatched
}
const setValue = async (selector, value, byLabel = false) =>
  cdp.eval(`(() => {
    const el = ${byLabel ? `[...document.querySelectorAll('input')].find(i => i.getAttribute('aria-label') === ${JSON.stringify(selector)})` : `document.querySelector(${JSON.stringify(selector)})`}
    if (!el) return 'missing'
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, ${JSON.stringify(value)})
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return el.value
  })()`)

// 1. Wait for the plan job the UI queued (the second one) to reach a terminal state.
let final = null
const deadline = Date.now() + 8 * 60 * 1000
while (Date.now() < deadline) {
  const response = await job()
  const value = response && response.result && response.result.job
  if (value && ['completed', 'completed_late', 'failed', 'cancelled', 'interrupted_requires_retry'].includes(value.state)) {
    final = value
    break
  }
  await cdp.wait(4000)
}
if (!final) throw new Error('plan job did not settle in 8 minutes')
await log('plan-job-settled', { state: final.state, error: final.error || null, progress: final.progress })
if (final.state !== 'completed' && final.state !== 'completed_late') {
  writeJson(rel('docs/REVIEW_CB015-row3b.json'), { ...trace, finalState: final.state })
  throw new Error(`plan job ended ${final.state}: ${JSON.stringify(final.error)}`)
}

// 2. Reattach to the course and open the Plan view.
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(1200)
await cdp.clickText('Parent Studio')
await cdp.wait(1400)
await cdp.clickText('Open studio')
await cdp.wait(1600)
await cdp.clickText('Plan')
await cdp.waitFor(`[...document.querySelectorAll('button')].some(b => (b.innerText || '').trim() === 'Edit plan')`, {
  label: 'Edit plan',
  timeout: 20000
})
const before = await cdp.json(`(() => {
  const t = document.querySelector('[data-cb-route]').innerText
  return {
    badges: (t.match(/Plan (draft|approved|superseded) · v\\d+/g) || []),
    planHash: (t.match(/plan sha256:[0-9a-f]{12,}/) || [])[0] || null,
    firstObjective: (document.querySelector('[aria-label="Objective 1 title"]') || {}).value || null,
    titleText: t.slice(0, 900)
  }
})()`)
await log('plan-view-before-edit', before)
await shot('row3-07-plan-draft')

// 3. Edit one objective title through the plan editor.
await cdp.clickText('Edit plan')
await cdp.waitFor(`!!document.querySelector('[aria-label="Objective 1 title"]')`, { label: 'objective editor', timeout: 10000 })
const original = await cdp.eval(`document.querySelector('[aria-label="Objective 1 title"]').value`)
const edited = await setValue('Objective 1 title', `${original} — with the safe-standing rule made explicit`, true)
await log('objective-retitled', { original, edited })
await shot('row3-08-plan-editing')
await cdp.clickText('Save changes')
await cdp.waitFor(`!document.querySelector('[aria-label="Objective 1 title"]')`, { label: 'editor closed', timeout: 25000 })
await cdp.wait(1200)
const afterSave = await cdp.json(`(() => {
  const t = document.querySelector('[data-cb-route]').innerText
  return {
    badges: (t.match(/Plan (draft|approved|superseded) · v\\d+/g) || []),
    firstObjective: [...document.querySelectorAll('[data-cb-objective]')].map(e => e.innerText.split('\\n')[0]).slice(0, 2),
    notice: (t.match(/Saved[^\\n]*/) || [])[0] || null,
    text: t.slice(0, 900)
  }
})()`)
await log('plan-saved', afterSave)
await shot('row3-09-plan-saved')

// 4. Approve the edited draft plan.
await cdp.clickText('Approve plan')
await cdp.waitFor(`/Plan approved · v\\d+/.test(document.querySelector('[data-cb-route]').innerText)`, {
  label: 'plan approved badge',
  timeout: 25000
})
await cdp.wait(800)
const approved = await cdp.json(`(() => {
  const t = document.querySelector('[data-cb-route]').innerText
  return {
    badges: (t.match(/Plan (draft|approved|superseded) · v\\d+/g) || []),
    lessonSetBadge: (t.match(/Lesson set (not approved|approved)|Changes need review/g) || []),
    buttons: [...document.querySelectorAll('[data-cb-route] button')].map(b => (b.innerText || '').trim()).filter(Boolean)
  }
})()`)
await log('plan-approved', approved)
await shot('row3-10-plan-approved')

trace.result = {
  jobSettled: final.state,
  planBadgeBefore: before.badges,
  planBadgeAfterSave: afterSave.badges,
  planBadgeApproved: approved.badges,
  objectiveEdited: edited !== original,
  approvedPlanVisible: /Plan approved · v2/.test(approved.badges.join(' '))
}
console.log('RESULT ' + JSON.stringify(trace.result))
writeJson(rel('docs/REVIEW_CB015-row3b.json'), trace)
cdp.close()
