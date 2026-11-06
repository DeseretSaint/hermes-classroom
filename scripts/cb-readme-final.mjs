/**
 * Finish the README capture set: the lesson pane in a bound lesson chat (which is where the check
 * lives once 'Start a fresh run' binds this section), plus the binding-free surfaces and the light
 * pair. Raw 2x frames only; scripts/cb-readme-optimize.py produces the shipped files.
 */
import { attach, gotoCoursebook, openCourse, clickExact, tab, openSectionByIndex, ensureSidebar, makeLog } from './cb-loops-lib.mjs'
import { setMode, writeJson } from './cb015-lib.mjs'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const RAW = resolve(process.env.CB_README_RAW || `${process.env.HOME}/.hermes/cb-readme/raw`)
mkdirSync(RAW, { recursive: true })
const cdp = await attach()
const log = makeLog()
const COURSE = 'Japanese affection and register — an L0 demonstration classroom'

await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 2, mobile: false })
await cdp.wait(700)

const cleanup = async () => {
  await cdp.eval(`(() => {
    for (const el of document.querySelectorAll('[data-sonner-toast], [role=alert]')) {
      if (/inference unavailable|error|failed/i.test(el.innerText || '')) {
        const b = [...el.querySelectorAll('button')].find(x => /dismiss|close/i.test((x.getAttribute('aria-label') || '') + (x.innerText || '')))
        if (b) b.click(); else el.remove()
      }
    }
    return true
  })()`)
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1595, y: 985 })
  await cdp.eval(`(() => { const a = document.activeElement; if (a && a.blur) a.blur(); return true })()`)
  await cdp.wait(400)
}

const shots = []
const shoot = async (name, note) => {
  await cleanup()
  const path = await cdp.shot(`${RAW}/${name}.png`)
  const meta = await cdp.json(`(() => {
    const r = document.querySelector('[data-cb-route]')
    return {
      name: ${JSON.stringify(name)},
      mode: document.documentElement.dataset.hermesMode,
      destination: r ? r.getAttribute('data-cb-destination') : null,
      hash: location.hash,
      viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
      errorText: /VALIDATION_FAILED|INTERNAL|HOST_UNAVAILABLE|couldn.t grade/.test(document.body.innerText || ''),
      detached: /binding is detached/.test(document.body.innerText || ''),
      text: (document.body.innerText || '').slice(0, 500)
    }
  })()`)
  Object.assign(meta, { note, file: path })
  shots.push(meta)
  log.add(cdp, `shot:${name}`, note, meta.mode || '', meta)
  console.log('shot', name, meta.mode, meta.destination, meta.errorText ? 'ERRTEXT' : '', meta.detached ? 'DETACHED' : '')
}

// ── A. the lesson pane in the bound lesson chat that 'Start a fresh run' opened ─────────────
await setMode(cdp, 'dark')
await cdp.wait(1200)
await shoot('09-lesson-pane-dark', 'Lesson chat with the Coursebook pane after a fresh run')

const paneInfo = await cdp.json(`(() => {
  const field = document.querySelector('#cb-attempt-answer')
  const pane = field ? field.closest('[data-pane], aside, section') : null
  return {
    field: !!field,
    submit: [...document.querySelectorAll('button')].filter(b => (b.innerText || '').trim() === 'Submit answer').length,
    paneText: pane ? (pane.innerText || '').slice(0, 300) : null,
    bodyHasCheck: /CURRENT CHECK/.test(document.body.innerText || '')
  }
})()`)
console.log('pane probe', JSON.stringify(paneInfo))

if (paneInfo.field) {
  const box = await cdp.json(`(() => { const el = document.querySelector('#cb-attempt-answer'); el.scrollIntoView({ block: 'center' }); const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })()`)
  await cdp.click(box.x, box.y)
  await cdp.wait(200)
  await cdp.type('B')
  await cdp.wait(500)
  await shoot('10-quiz-in-progress-dark', 'Check answered in the lesson pane, not yet submitted')
  await clickExact(cdp, 'Submit answer')
  await cdp.waitFor(`!document.querySelector('#cb-attempt-answer') && /(Passed|Partly there|Not yet|Grading failed)/.test(document.body.innerText || '')`, { timeout: 90000, interval: 250, label: 'pane verdict' })
  await cdp.wait(800)
  await shoot('11-quiz-result-dark', 'Graded verdict returned in the lesson pane')
}

// ── B. light pair, and the binding-free surfaces ────────────────────────────────────────────
await setMode(cdp, 'light')
await cdp.wait(500)
await shoot('12-lesson-pane-light', 'The same lesson pane in the light theme (pairs with 09)')

await setMode(cdp, 'dark')
await gotoCoursebook(cdp)
await ensureSidebar(cdp)
await openCourse(cdp, COURSE)
await tab(cdp, 'Textbook')
await cdp.wait(1500)
await shoot('13-textbook-dark', 'Textbook index')
await tab(cdp, 'Notebook')
await cdp.wait(1500)
await shoot('14-notebook-dark', 'Notebook')
await clickExact(cdp, 'All courses')
await clickExact(cdp, 'Parent Studio')
await cdp.wait(1800)
await shoot('15-parent-studio-dark', 'Parent Studio')

await writeJson(`${RAW}/manifest-final.json`, { capturedAt: new Date().toISOString(), rig: { cdp: process.env.CB015_CDP_PORT || '9382' }, shots, steps: log.steps })
console.log('shots', shots.length)
cdp.close()
