#!/usr/bin/env node
/**
 * CB-015 loop C — notebook -> exact textbook section, past quiz read-only review, and an
 * early/late section jump that opens a separate context-bound run without touching old evidence.
 */
import { connect } from './cb015-lib.mjs'
import { writeFileSync, readFileSync } from 'node:fs'

const cdp = await connect()
const OUT = 'docs/REVIEW_CB015-loops.json'
const trace = JSON.parse(readFileSync(OUT, 'utf8'))
const record = async (label, extra = {}) => {
  const state = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const body = document.body.innerText || ''
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      routeText: root ? root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 3000) : '',
      modalOpen: !!document.querySelector('[role="dialog"], [aria-modal="true"]')
    }
  })()`)
  const entry = { step: label, at: new Date().toISOString(), ...state, ...extra }
  trace.steps.push(entry)
  console.log(JSON.stringify({ step: label, hash: entry.hash, modal: entry.modalOpen }))
  return entry
}
const shoot = async (name) => {
  const path = await cdp.shot(`docs/cb015-shots/${name}.png`)
  trace.shots.push(path)
  return path
}
const tab = async (label) => {
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>x.innerText.trim()===${JSON.stringify(label)}); if(b) b.click(); })()`)
  await cdp.wait(1500)
}
const openSection = async (index) => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(2200)
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>x.innerText.trim()==='Open'); if(b) b.click(); })()`)
  await cdp.wait(1800)
  await tab('Textbook')
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => b.innerText.trim() === 'Open section')
    if (!bs[${index}]) return 'missing(' + bs.length + ')'
    bs[${index}].click(); return 'clicked'
  })()`)
  if (opened !== 'clicked') throw new Error('open section ' + index + ': ' + opened)
  await cdp.wait(2600)
}

// ---- 1. notebook row -> exact textbook section
await tab('Notebook')
const jumped = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => /Open in textbook/i.test((x.innerText || '').trim()))
  if (!b) return 'missing'
  b.click(); return 'clicked'
})()`)
if (jumped === 'clicked') {
  await cdp.wait(2800)
  await record('notebook-open-in-textbook', { jumped })
  await shoot('19-notebook-to-section-dark')
  const identity = await cdp.eval(`(() => {
    const t = document.querySelector('[data-cb-route]')?.innerText || ''
    return {
      hasLessonHeading: /Lesson 1/.test(t),
      heading: (t.match(/Lesson 1[^\\n]{0,80}/) || [''])[0],
      attempts: (t.match(/ATTEMPTS ON THIS SECTION([\\s\\S]{0,200})/) || ['', ''])[1],
      checkQuestion: (t.match(/Two lines are shown[^\\n]{0,120}/) || [''])[0]
    }
  })()`)
  record('notebook-section-identity', identity)
} else {
  record('notebook-open-in-textbook-missing', { jumped })
}

// ---- 2. quizzes: past attempts, read-only review
await tab('Quizzes')
const quizList = await record('quizzes-list')
await shoot('20-quizzes-list-dark')
const rows = await cdp.json(`(() => [...document.querySelectorAll('[data-cb-route] button')].map(b => (b.innerText || '').trim()).filter(t => /Not yet|Passed|Partly|failed/i.test(t)).slice(0, 10))()`)
record('quizzes-result-rows', { rows })
const openedQuiz = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => /Not yet|Passed|Partly there/i.test((x.innerText || '').trim()) && !/Grading failed/.test((x.innerText || '').trim()))
  if (!b) return 'missing'
  b.click(); return 'clicked:' + (b.innerText || '').trim().slice(0, 40)
})()`)
if (openedQuiz !== 'missing') {
  await cdp.wait(2400)
  await record('quiz-review', { openedQuiz })
  await shoot('21-quiz-review-dark')
  const review = await cdp.eval(`(() => {
    const t = document.querySelector('[data-cb-route]')?.innerText || ''
    return {
      hasOriginalAnswer: /Your answer|Answer you gave/i.test(t),
      hasFeedback: /Feedback|Why|criteria/i.test(t),
      readOnlyControls: [...document.querySelectorAll('[data-cb-route] button')].map(b => (b.innerText || '').trim()).filter(Boolean).slice(-14),
      snippet: t.slice(-1400)
    }
  })()`)
  record('quiz-review-identity', review)

  const newVersion = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => /new version|Try a new version|New version/i.test((x.innerText || '').trim()))
    if (!b) return 'missing'
    b.click(); return 'clicked'
  })()`)
  if (newVersion === 'clicked') {
    await cdp.wait(3000)
    const after = await record('quiz-new-version', { newVersion })
    await shoot('22-quiz-new-version-dark')
    trace.steps.push({ step: 'quiz-new-version-copy', at: new Date().toISOString(), tail: after.routeText.slice(-700) })
  } else {
    record('quiz-new-version-missing', { newVersion })
  }
}

// ---- 3. proof 19: late section opens its own context-bound run; early evidence stays
const earlyCount = await cdp.eval(`(() => (document.querySelector('[data-cb-route]')?.innerText || '').match(/Not yet/g)?.length || 0)()`)
await openSection(3)
const late = await record('late-section-detached', { earlyCount })
await shoot('23-late-section-dark')
const lateTitle = await cdp.eval(`(() => (document.querySelector('[data-cb-route]')?.innerText || '').match(/Explain why register[^\\n]{0,60}/)?.[0] || '')()`)
const armed = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Start a fresh run')
  if (!b) return 'missing'
  b.click(); return 'clicked'
})()`)
if (armed === 'clicked') {
  await cdp.waitFor(`!!document.querySelector('[contenteditable="true"]')`, { timeout: 30000, label: 'composer' })
  await cdp.wait(1400)
  const lateHash = await cdp.eval('location.hash')
  record('late-run-armed', { lateHash, lateTitle })
  await cdp.eval(`(() => { const el = document.querySelector('[contenteditable="true"]'); el.focus(); return true })()`)
  await cdp.type('Give me the transfer check for this section, in one question.')
  for (const type of ['keyDown', 'keyUp']) {
    await cdp.send('Input.dispatchKeyEvent', {
      type,
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13,
      text: type === 'keyDown' ? '\r' : undefined
    })
  }
  let previous = ''
  let stable = 0
  const deadline = Date.now() + 200000
  while (Date.now() < deadline) {
    const length = await cdp.eval(`(document.body.innerText || '').length`)
    if (length === previous) {
      if (!stable) stable = Date.now()
      if (Date.now() - stable > 8000) break
    } else {
      stable = 0
      previous = length
    }
    await cdp.wait(1000)
  }
  record('late-run-turn-complete')
  // back to the early section: its evidence must be intact
  await openSection(0)
  const earlyAfter = await record('early-section-after-late-run')
  await shoot('24-early-section-intact-dark')
  const intact = await cdp.eval(`(() => {
    const t = document.querySelector('[data-cb-route]')?.innerText || ''
    return {
      attempts: (t.match(/ATTEMPTS ON THIS SECTION([\\s\\S]{0,220})/) || ['', ''])[1],
      notYet: (t.match(/Not yet/g) || []).length,
      savedNotebook: /SAVED FROM THIS SECTION/.test(t)
    }
  })()`)
  record('early-evidence-intact', intact)
}

cdp.close()
writeFileSync(OUT, JSON.stringify(trace, null, 2))
console.log('wrote', OUT)
