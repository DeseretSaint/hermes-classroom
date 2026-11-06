#!/usr/bin/env node
/**
 * CB-015 loop B (corrected) — save the draft note from inside the dialog, then find it by
 * search/tag and open its exact section. Controls are scoped to the dialog so the page trigger
 * behind it can never absorb the click.
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
      routeText: root ? root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 2400) : '',
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
const setValue = async (selector, value) => {
  await cdp.eval(`(() => {
    const el = document.querySelector(${JSON.stringify(selector)})
    if (!el) return 'missing'
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)})
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return 'set'
  })()`)
  await cdp.wait(250)
}

// --- 0. return to the section page (the previous probe left the Notebook tab mounted)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(2200)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>x.innerText.trim()==='Open'); if(b) b.click(); })()`)
await cdp.wait(1800)
await tab('Textbook')
const sectionOpened = await cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => b.innerText.trim() === 'Open section')
  if (!bs.length) return 'missing(' + bs.length + ')'
  bs[0].click(); return 'clicked'
})()`)
if (sectionOpened !== 'clicked') throw new Error('open section: ' + sectionOpened)
await cdp.wait(2600)
await record('section-returned-for-notebook')

// --- 1. open the notebook dialog from the teaching segment (page-level trigger)
const opened = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => x.innerText.trim() === 'Save to notebook')
  if (!b) return 'missing'
  b.click(); return 'clicked'
})()`)
if (opened !== 'clicked') throw new Error('no page Save to notebook trigger')
await cdp.wait(1200)
if (!(await cdp.eval(`!!document.querySelector('#cb-note-excerpt')`))) throw new Error('dialog did not open')
await setValue('#cb-note-note', 'Politeness alone is not the separator; the request is what makes it a confession.')
await setValue('#cb-note-tags', 'register, politeness')
await record('notebook-dialog-filled')
await shoot('14-notebook-dialog-dark')

const dialogButtons = await cdp.json(`(() => [...document.querySelectorAll('[role="dialog"] button, [aria-modal="true"] button')].map(b => ({ t: (b.innerText||'').trim(), disabled: !!b.disabled })))()`)
record('notebook-dialog-buttons', { dialogButtons })
const confirmed = await cdp.eval(`(() => {
  const scope = document.querySelector('[role="dialog"], [aria-modal="true"]')
  if (!scope) return 'no-dialog'
  const b = [...scope.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Save to notebook')
  if (!b) return 'no-confirm'
  b.click(); return 'clicked'
})()`)
if (confirmed !== 'clicked') throw new Error('dialog confirm: ' + confirmed)
await cdp.wait(2500)
const afterSave = await record('notebook-saved', { confirmed })
await shoot('15-notebook-saved-dark')
if (afterSave.modalOpen) {
  const error = await cdp.eval(`(() => (document.querySelector('[role="dialog"], [aria-modal="true"]') || {}).innerText || '')()`)
  throw new Error('dialog still open after confirm; text: ' + error.slice(-400))
}

// --- 2. notebook list -> search -> tag filter
await tab('Notebook')
const list = await record('notebook-list')
await shoot('16-notebook-list-dark')
if (/Nothing saved yet/.test(list.routeText)) throw new Error('notebook list is empty after save')

await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] input')].find(i => i.placeholder === 'Search the notebook')
  if (!el) return 'missing'
  el.focus(); return 'focused'
})()`)
await cdp.type('separator')
await cdp.wait(1800)
const searched = await record('notebook-search')
await shoot('17-notebook-search-dark')
if (/No notes match/.test(searched.routeText)) throw new Error('search did not find the saved note')

await cdp.eval(`(() => {
  const el = [...document.querySelectorAll('[data-cb-route] input')].find(i => i.placeholder === 'Search the notebook')
  if (!el) return 'missing'
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, '')
  el.dispatchEvent(new Event('input', { bubbles: true }))
  return 'cleared'
})()`)
await cdp.wait(900)

const tagMenu = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === 'All tags')
  if (!b) return 'missing'
  b.click(); return 'clicked'
})()`)
if (tagMenu === 'clicked') {
  await cdp.wait(700)
  const menu = await cdp.json(`(() => [...document.querySelectorAll('[role="menu"] button, [role="menuitem"], [role="option"], [role="listbox"] button')].map(b => (b.innerText||'').trim()).filter(Boolean))()`)
  record('notebook-tag-menu', { menu })
  const picked = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[role="menu"] button, [role="menuitem"], [role="option"], [role="listbox"] button')].find(x => (x.innerText || '').trim() === 'register')
    if (!b) return 'missing'
    b.click(); return 'clicked'
  })()`)
  if (picked === 'clicked') {
    await cdp.wait(1800)
    const filtered = await record('notebook-tag-filter', { picked })
    await shoot('18-notebook-tag-filter-dark')
    if (/No notes match/.test(filtered.routeText)) throw new Error('tag filter lost the saved note')
  } else {
    record('notebook-tag-filter-skipped', { picked, menu })
  }
}

// --- 3. open the exact section from the notebook row
const jump = await cdp.eval(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const bs = [...root.querySelectorAll('button')].filter(x => /Open section|Go to section|Open this section/i.test((x.innerText || '').trim()))
  if (!bs.length) return 'missing'
  bs[0].click(); return 'clicked(' + bs[0].innerText.trim() + ')'
})()`)
if (jump !== 'missing') {
  await cdp.wait(2800)
  const landed = await record('notebook-open-section', { jump })
  await shoot('19-notebook-to-section-dark')
  const identity = await cdp.eval(`(() => {
    const t = document.querySelector('[data-cb-route]')?.innerText || ''
    return {
      hasLessonHeading: /Lesson 1/.test(t),
      hasCheck: /CURRENT CHECK|ATTEMPTS ON THIS SECTION/.test(t),
      attempts: (t.match(/ATTEMPTS ON THIS SECTION([\\s\\S]{0,260})/) || ['', ''])[1],
      question: (t.match(/Two lines are shown[^\\n]{0,160}/) || [''])[0]
    }
  })()`)
  record('notebook-section-identity', identity)
} else {
  record('notebook-open-section-skipped', { jump })
}

cdp.close()
writeFileSync(OUT, JSON.stringify(trace, null, 2))
console.log('wrote', OUT)
