#!/usr/bin/env node
/** CB-015 loop D — open a past attempt's read-only review and its new-version affordance. */
import { connect } from './cb015-lib.mjs'
import { writeFileSync, readFileSync } from 'node:fs'

const cdp = await connect()
const OUT = 'docs/REVIEW_CB015-loops.json'
const trace = JSON.parse(readFileSync(OUT, 'utf8'))
const record = async (label, extra = {}) => {
  const state = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return {
      hash: location.hash,
      routeText: root ? root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 3200) : '',
      modalOpen: !!document.querySelector('[role="dialog"], [aria-modal="true"]')
    }
  })()`)
  const entry = { step: label, at: new Date().toISOString(), ...state, ...extra }
  trace.steps.push(entry)
  console.log(JSON.stringify({ step: label, modal: entry.modalOpen }))
  return entry
}
const shoot = async (name) => {
  const path = await cdp.shot(`docs/cb015-shots/${name}.png`)
  trace.shots.push(path)
  return path
}

await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(2000)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>x.innerText.trim()==='Open'); if(b) b.click(); })()`)
await cdp.wait(1600)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>x.innerText.trim()==='Quizzes'); if(b) b.click(); })()`)
await cdp.wait(1800)
await record('quizzes-open')

const clicked = await cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => /Open attempt/i.test((b.innerText || '').trim()))
  if (!bs.length) return 'missing'
  bs[0].click(); return 'clicked(' + bs.length + ')'
})()`)
if (clicked !== 'missing') {
  await cdp.wait(2600)
  await record('quiz-review-opened', { clicked })
  await shoot('21-quiz-review-dark')
  const review = await cdp.eval(`(() => {
    const t = document.querySelector('[data-cb-route]')?.innerText || ''
    return {
      answer: (t.match(/Your answer[\\s\\S]{0,400}/) || [''])[0],
      verdict: (t.match(/(Passed|Not yet|Partly there)/) || [''])[0],
      hasCriteria: /criteria|Feedback|feedback/i.test(t),
      controls: [...document.querySelectorAll('[data-cb-route] button')].map(b => (b.innerText || '').trim()).filter(Boolean).slice(-16),
      tail: t.slice(-1600)
    }
  })()`)
  record('quiz-review-detail', review)

  const newVersion = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => /new version|New version/i.test((x.innerText || '').trim()))
    if (!b) return 'missing'
    b.click(); return 'clicked:' + b.innerText.trim()
  })()`)
  if (newVersion !== 'missing') {
    await cdp.wait(3500)
    const after = await record('quiz-new-version', { newVersion })
    await shoot('22-quiz-new-version-dark')
    trace.steps.push({ step: 'quiz-new-version-tail', at: new Date().toISOString(), tail: after.routeText.slice(-900) })
  } else {
    record('quiz-new-version-missing', { newVersion })
  }
}

cdp.close()
writeFileSync(OUT, JSON.stringify(trace, null, 2))
console.log('wrote', OUT)
