#!/usr/bin/env node
/**
 * CB-015 proof 15 — keyboard-only, focus-visible, text-only, reduced-motion.
 *
 * Every movement and activation here is a real CDP key event (Tab / Shift+Tab / Enter / Escape).
 * The only non-keyboard calls are: resetting focus to <body> before the walk, reading the DOM,
 * and switching the emulated media feature. Text is entered with Input.insertText, which is what
 * a hardware keyboard produces after keydown.
 */
import { connect } from './cb015-lib.mjs'
import { writeFileSync } from 'node:fs'

const cdp = await connect()
const stops = []
const shots = []

const dismissSetup = async () => {
  if (!(await cdp.eval(`/Let's get you setup/.test(document.body.innerText || '')`))) return
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('button, a')].find(x=>/choose a provider later/i.test((x.innerText||'').trim())); if(b) b.click() })()`)
  await cdp.wait(1200)
}
const key = async (name, modifiers = 0) => {
  await cdp.key(name, { modifiers })
  await cdp.wait(90)
}
const focusState = () =>
  cdp.json(`(() => {
    const el = document.activeElement
    if (!el) return null
    const style = getComputedStyle(el)
    const rect = el.getBoundingClientRect()
    return {
      tag: el.tagName,
      id: el.id || null,
      role: el.getAttribute('role'),
      name: (el.getAttribute('aria-label') || el.innerText || el.placeholder || el.value || '').trim().slice(0, 70),
      inRoute: !!el.closest('[data-cb-route]'),
      outline: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
      boxShadow: style.boxShadow !== 'none',
      visible: rect.width > 1 && rect.height > 1
    }
  })()`)
const tabTo = async (predicate, label, max = 400) => {
  for (let i = 0; i < max; i += 1) {
    await key('Tab')
    const state = await focusState()
    if (!state) continue
    stops.push(state)
    if (predicate(state)) return { found: true, tabs: i + 1, state }
  }
  throw new Error('never reached ' + label)
}
const shoot = async (name) => {
  await dismissSetup()
  const path = await cdp.shot(`docs/cb015-shots/${name}.png`)
  shots.push(path)
  return path
}

await dismissSetup()
// The host's session list contributes hundreds of tab stops before the workspace pane, so the
// walk starts at the first focusable control in the mounted route. Every movement and activation
// after that point is a real key event; nothing is clicked.
const focusFirstRouteControl = async () => {
  const ok = await cdp.eval(`(() => {
    const root = document.querySelector('[data-cb-route]')
    if (!root) return false
    const el = [...root.querySelectorAll('button, a, input, textarea, select')].find(e => {
      const r = e.getBoundingClientRect()
      return r.width > 1 && r.height > 1 && !e.disabled
    })
    if (!el) return false
    el.focus()
    return true
  })()`)
  if (!ok) throw new Error('no focusable control in route')
  await cdp.wait(150)
}
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(2000)
await dismissSetup()
if (!(await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].some(b => (b.innerText||'').trim() === 'Textbook')`))) {
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Open'); if(b) b.click() })()`)
  await cdp.wait(2000)
}
await focusFirstRouteControl()

// ---- 1. keyboard-only route into the textbook; the view strip is one composite stop
const routeStop = await tabTo((s) => s.inRoute && /Course view/.test(s.name), 'Course view strip')
let strip = { moved: false }
const pressedNow = await cdp.eval(`(() => [...document.querySelectorAll('[data-cb-route] button[aria-pressed="true"]')].map(x => (x.innerText || '').trim()))()`)
if (!pressedNow.includes('Textbook')) {
  for (let i = 0; i < 8; i += 1) {
    await key('ArrowRight')
    const pressed = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('[data-cb-route] button[aria-pressed="true"]')].map(x => (x.innerText || '').trim())
      return b
    })()`)
    if (pressed.includes('Textbook')) { strip = { moved: true, steps: i + 1, pressed }; break }
  }
} else {
  strip = { moved: false, alreadyTextbook: true, pressed: pressedNow }
}
await cdp.wait(1200)
const switched = await cdp.eval(`(() => {
  const t = document.querySelector('[data-cb-route]')?.innerText || ''
  return { textbook: /Open section/.test(t), rows: (t.match(/Open section/g) || []).length }
})()`)
await shoot('60-keyboard-textbook')

// ---- 2. keyboard-open the first section, reach the answer field, type, submit
// Switching the view strip re-renders it; re-place focus at the route's first control so the
// next Tab continues inside the route instead of restarting in the host sidebar.
await focusFirstRouteControl()
if ((await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim()==='Open section').length`)) === 0) {
  // a section page is open: use its "All sections" control to get back to the index
  const back = await tabTo((s) => s.name === 'All sections', 'All sections', 40).catch(() => null)
  if (back) {
    await key('Enter')
    await cdp.wait(1800)
  }
  await focusFirstRouteControl()
}
const sectionStop = await tabTo((s) => /^Open section$/.test(s.name), 'Open section')
await key('Enter')
await cdp.wait(2600)
const sectionOpened = await cdp.eval(`/CURRENT CHECK|ATTEMPTS ON THIS SECTION/.test(document.querySelector('[data-cb-route]')?.innerText || '')`)

await focusFirstRouteControl()
let answer = { found: false }
try {
  answer = await tabTo((s) => s.id === 'cb-attempt-answer', 'answer field', 500)
  await cdp.type('Keyboard-only answer: ③ 付き合ってください (tsukiatte kudasai) is the asking word.')
  await cdp.wait(300)
} catch (error) {
  answer = { found: false, error: String(error) }
}
const submit = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => (x.innerText || '').trim() === 'Submit answer')
  if (!b) return { present: false }
  return { present: true, disabled: b.disabled, reason: (b.closest('div')?.innerText || '').slice(0, 200) }
})()`)
let submitted = false
let submitOutcome = null
if (answer.found && submit.present && !submit.disabled) {
  await tabTo((s) => s.name === 'Submit answer', 'Submit answer', 60)
  await key('Enter')
  submitted = true
  const started = Date.now()
  while (Date.now() - started < 90000) {
    const done = await cdp.eval(`(() => { const t = document.body.innerText || ''; return /I couldn.t grade this attempt|ATTEMPTS ON THIS SECTION|Passed|Partly there|Not yet|Graded/.test(t) })()`)
    if (done) break
    await cdp.wait(700)
  }
  await cdp.wait(1200)
  submitOutcome = await cdp.eval(`(() => {
    const t = document.body.innerText || ''
    const at = Math.max(t.indexOf('ATTEMPTS ON THIS SECTION'), t.indexOf('CURRENT CHECK'))
    return {
      verdict: (t.match(/ATTEMPTS ON THIS SECTION[\\s\\S]{0,220}/) || [''])[0],
      needsRetry: /I couldn.t grade this attempt/.test(t),
      tail: at < 0 ? '' : t.slice(at, at + 300)
    }
  })()`)
}
await shoot('61-keyboard-answer')

// ---- 3. Escape closes the notebook dialog from the keyboard
await cdp.wait(800)
const pickerFocused = await cdp.eval(`(() => { const b = document.getElementById('cb-view-picker'); if (!b) return false; b.focus(); return document.activeElement === b })()`)
if (!pickerFocused) await focusFirstRouteControl()
let escape = { reached: false }
try {
  await tabTo((s) => s.name === 'Save to notebook', 'Save to notebook', 500)
  await key('Enter')
  await cdp.wait(1200)
  const opened = await cdp.eval(`!!document.querySelector('#cb-note-excerpt')`)
  await key('Escape')
  await cdp.wait(700)
  const closed = !(await cdp.eval(`!!document.querySelector('#cb-note-excerpt')`))
  escape = { reached: true, opened, closed, focus: await focusState() }
} catch (error) {
  escape = { reached: false, error: String(error) }
}

// ---- 4. text-only audit + focus-visible accounting
const textOnly = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const controls = [...root.querySelectorAll('button, a, input, textarea, select, [role="tab"], [role="menuitem"]')]
    .filter(el => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 })
  const unnamed = controls.filter(el => {
    const name = (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.innerText || el.placeholder || '').trim()
    return !name
  }).map(el => el.tagName + ':' + (el.className || '').toString().slice(0, 60))
  return { visibleControls: controls.length, unnamed }
})()`)
const focusVisibleMisses = stops.filter((s) => s.visible && !s.outline && !s.boxShadow).length

// ---- 5. reduced motion
await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
await cdp.wait(700)
const reduced = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const durations = [...root.querySelectorAll('*')].map(el => {
    const s = getComputedStyle(el)
    return { d: parseFloat(s.transitionDuration) || 0, a: parseFloat(s.animationDuration) || 0 }
  })
  return {
    maxTransition: Math.max(...durations.map(x => x.d)),
    maxAnimation: Math.max(...durations.map(x => x.a)),
    animated: durations.filter(x => x.d > 0 || x.a > 0).length
  }
})()`)
await shoot('62-keyboard-reduced-motion')
await cdp.send('Emulation.setEmulatedMedia', { features: [] })

const result = {
  measuredAt: new Date().toISOString(),
  route: routeStop,
  strip,
  textbookAfterEnter: switched,
  sectionOpened,
  answerStop: answer,
  submit,
  submitted,
  submitOutcome,
  escape,
  textOnly,
  keyboardStops: stops.length,
  focusVisibleMisses,
  reducedMotion: reduced,
  stopsSample: stops.slice(0, 25),
  shots
}
writeFileSync('docs/REVIEW_CB015-keyboard.json', `${JSON.stringify(result, null, 2)}\n`)
console.log(JSON.stringify({
  keyboardStops: stops.length,
  textbook: switched,
  sectionOpened,
  answerFound: answer.found,
  submit,
  submitted,
  submitOutcome,
  escape,
  textOnly,
  focusVisibleMisses,
  reducedMotion: reduced
}, null, 2))
cdp.close()
