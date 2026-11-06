#!/usr/bin/env node
/**
 * CB-015 gallery — recapture every evidence still with the host setup overlay dismissed.
 * Navigation is by the app's own controls; no state is fabricated. The notebook dialog is opened,
 * captured, then closed with Escape (which also proves single-action Escape).
 */
import { connect, setMode } from './cb015-lib.mjs'
import { writeFileSync } from 'node:fs'

const cdp = await connect()
const shots = []
const notes = []

const dismissSetup = async () => {
  const present = await cdp.eval(`/Let's get you setup/.test(document.body.innerText || '')`)
  if (!present) return false
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button, a')].find(x => /choose a provider later/i.test((x.innerText || '').trim()))
    if (b) b.click()
    return !!b
  })()`)
  await cdp.wait(1500)
  return true
}
const shoot = async (name) => {
  await dismissSetup()
  const path = await cdp.shot(`docs/cb015-shots/${name}.png`)
  shots.push(path)
  console.log('shot', name)
}
const tab = async (label) => {
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()===${JSON.stringify(label)}); if(b) b.click(); })()`)
  await cdp.wait(1300)
}
const openCourse = async (needle) => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(1500)
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='All courses'); if(b) b.click(); })()`)
  await cdp.wait(1500)
  let hasRows = await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText||'').trim() === 'Open')`)
  if (!hasRows) {
    await cdp.reload()
    await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 25000, label: 'route' })
    await cdp.wait(1500)
  }
  const opened = await cdp.eval(`(() => {
    const needle = ${JSON.stringify(needle)}
    const root = document.querySelector('[data-cb-route]')
    // the deepest element whose own text names the course (a row title/heading), then the
    // nearest ancestor that actually owns an Open button — never a container shared by rows.
    const titles = [...root.querySelectorAll('*')].filter(el => {
      const own = (el.innerText || '').trim()
      return own.includes(needle) && ![...el.children].some(c => (c.innerText || '').includes(needle))
    })
    const title = titles[titles.length - 1]
    if (!title) return 'no-title'
    let node = title
    for (let depth = 0; depth < 8 && node; depth += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Open')
      if (b) { b.click(); return 'clicked' }
    }
    return 'no-open-for-title'
  })()`)
  if (opened !== 'clicked') throw new Error('no course row for ' + needle + ': ' + opened)
  await cdp.wait(2000)
}
const openSection = async (index) => {
  await tab('Textbook')
  const opened = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open section')
    if (!bs[${index}]) return 'missing(' + bs.length + ')'
    bs[${index}].click(); return 'clicked'
  })()`)
  if (opened !== 'clicked') throw new Error('open section ' + index + ': ' + opened)
  await cdp.wait(2400)
}

// ---- courses list, dark + light
await dismissSetup()
await openCourse('Japanese affection and register')
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(1800)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='All courses'); if(b) b.click(); })()`)
await cdp.wait(1500)
await setMode(cdp, 'dark')
await shoot('40-courses-dark')
await setMode(cdp, 'light')
await shoot('41-courses-light')
await setMode(cdp, 'dark')

// ---- demo course: overview, textbook, section, notebook, quizzes
await openCourse('Japanese affection and register')
await shoot('42-course-overview-dark')
await tab('Textbook')
await shoot('43-textbook-index-dark')
await openSection(0)
await shoot('44-section-evidence-dark')

// notebook list with the saved note
await tab('Notebook')
await shoot('45-notebook-dark')
await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] input')].find(i => i.placeholder === 'Search the notebook')
  if (el) { el.focus() }
})()`)
await cdp.type('separator')
await cdp.wait(1200)
await shoot('46-notebook-search-dark')
await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] input')].find(i => i.placeholder === 'Search the notebook')
  if (el) { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, ''); el.dispatchEvent(new Event('input', { bubbles: true })) }
})()`)
await cdp.wait(900)

// quizzes list + a real past-attempt review (hinted attempt carries the answer)
await tab('Quizzes')
await shoot('47-quizzes-list-dark')
const review = await cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => /Open attempt/i.test((b.innerText || '').trim()))
  if (bs.length < 2) return 'missing(' + bs.length + ')'
  bs[1].click(); return 'clicked'
})()`)
await cdp.wait(2200)
await shoot('48-quiz-review-dark')
notes.push({ step: 'quiz-review-opened', review })

// ---- notebook dialog + Escape (single action closes, focus returns)
await openCourse('Japanese affection and register')
await openSection(0)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Save to notebook'); if(b) b.click(); })()`)
await cdp.wait(1200)
await shoot('49-notebook-dialog-dark')
const dialogOpen = await cdp.eval(`!!document.querySelector('#cb-note-excerpt')`)
await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 })
await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 })
await cdp.wait(900)
const dialogClosed = !(await cdp.eval(`!!document.querySelector('#cb-note-excerpt')`))
const focusAfter = await cdp.eval(`(() => { const a = document.activeElement; return { tag: a.tagName, text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 60) } })()`)
notes.push({ step: 'escape-closes-dialog', dialogOpen, dialogClosed, focusAfter })

// ---- perf course: 55 rows, last section, 200% and narrow
await openCourse('fifty-five')
await tab('Textbook')
await shoot('50-perf-textbook-55-dark')
await openSection(54)
await shoot('51-perf-last-section-dark')
await cdp.eval(`document.documentElement.style.fontSize = '32px'`)
await cdp.wait(700)
await shoot('52-perf-text200-dark')
await cdp.eval(`document.documentElement.style.fontSize = ''`)
await cdp.setViewport(460, 900)
await cdp.wait(800)
await shoot('53-perf-narrow-dark')
await cdp.clearViewport()

// ---- light appearance of the long section (same DOM)
await setMode(cdp, 'light')
await cdp.wait(600)
await shoot('54-perf-last-section-light')
await setMode(cdp, 'dark')

writeFileSync(
  'docs/REVIEW_CB015-gallery.json',
  `${JSON.stringify({ capturedAt: new Date().toISOString(), shots, notes }, null, 2)}\n`
)
console.log('wrote docs/REVIEW_CB015-gallery.json with', shots.length, 'shots')
cdp.close()
