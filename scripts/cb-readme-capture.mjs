/**
 * README/demo capture set for the polished Coursebook build.
 *
 * Every frame is the real Desktop window on the isolated rig (backend 127.0.0.1:44310, window
 * CDP 9382, HERMES_HOME ~/.hermes/cb-readme/home), driven only through the app's own controls.
 * Raw frames land at 2x in CB_README_RAW; `scripts/cb-readme-optimize.py` resizes and optimizes
 * them into docs/assets/screenshots.
 *
 *   CB015_CDP_PORT=9382 CB_README_RAW=~/.hermes/cb-readme/raw node scripts/cb-readme-capture.mjs [stage]
 *
 * Stages: `dark` (default) and `light`. Each stage appends to raw/manifest.json so a retry does
 * not throw away the frames already taken.
 */
import { attach, gotoCoursebook, openCourse, clickExact, tab, openSectionByIndex, ensureSidebar, makeLog } from './cb-loops-lib.mjs'
import { setMode, writeJson } from './cb015-lib.mjs'
import { mkdirSync, readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

const RAW = resolve(process.env.CB_README_RAW || `${process.env.HOME}/.hermes/cb-readme/raw`)
mkdirSync(RAW, { recursive: true })
const MANIFEST = `${RAW}/manifest.json`
const stage = process.argv[2] || 'dark'
const cdp = await attach()
const log = makeLog()

const COURSE = 'Japanese affection and register — an L0 demonstration classroom'
const W = 1600
const H = 1000

await cdp.send('Emulation.setDeviceMetricsOverride', {
  width: W,
  height: H,
  deviceScaleFactor: 2,
  mobile: false
})
await cdp.wait(800)

/** The window under test is narrow by default; every frame uses one collapsed-sidebar layout. */
const collapseSidebar = async () => {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const left = await cdp.eval(`(() => { const r = document.querySelector('[data-cb-route]'); return r ? Math.round(r.getBoundingClientRect().left) : -1 })()`)
    if (left === 0) return true
    const clicked = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('button')].find(e => /hide sidebar/i.test((e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')))
      if (!b) return false
      b.click(); return true
    })()`)
    if (!clicked) {
      // The shell only shows the collapse control while the pointer is over its header strip.
      await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 12, y: 12 })
      await cdp.wait(300)
      continue
    }
    await cdp.wait(700)
  }
  return false
}

const clearOverlays = async () => {
  const dismissed = await cdp.eval(`(() => {
    if (/Let's get you setup/.test(document.body.innerText || '')) {
      const b = [...document.querySelectorAll('button, a')].find(x => /choose a provider later/i.test((x.innerText || '').trim()))
      if (b) { b.click(); return 'setup' }
    }
    const toast = [...document.querySelectorAll('[data-sonner-toast], [role=status], [role=alert]')]
      .find(el => /error|failed|couldn|inference unavailable|backend off/i.test(el.innerText || ''))
    if (toast) {
      const x = [...toast.querySelectorAll('button')].find(b => /dismiss|close/i.test((b.getAttribute('aria-label') || '') + (b.innerText || '')))
      if (x) { x.click(); return 'toast' }
      toast.remove()
      return 'toast-removed'
    }
    return 'none'
  })()`)
  if (dismissed !== 'none') await cdp.wait(900)
  return dismissed
}

/**
 * A section page can arrive with its chat binding detached (no run bound yet). A README frame must
 * show the working state, so the page's own recovery action is taken - never a fabricated banner.
 */
const ensureBinding = async () => {
  const routeTextNow = async () => cdp.eval(`(document.querySelector('[data-cb-route]')?.innerText || '')`)
  const text = await routeTextNow()
  if (!/detached|Start a fresh run|Reattach/i.test(text)) return 'bound'
  for (const label of ['Reattach', 'Start a fresh run']) {
    const clicked = await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText || '').trim() === ${JSON.stringify(label)} && !x.disabled)
      if (!b) return false
      b.scrollIntoView({ block: 'center' }); b.click(); return true
    })()`)
    if (clicked) {
      await cdp.wait(2800)
      const after = await routeTextNow()
      if (!/detached/i.test(after)) return label
    }
  }
  return 'still-detached'
}

/** Open section 0 and make sure it is bound; a binding recovery resets the route, so reopen it. */
const openLesson = async () => {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await openCourse(cdp, COURSE)
    await openSectionByIndex(cdp, 0)
    await cdp.waitFor(
      `document.querySelector('[data-cb-route]') && (!!document.querySelector('#cb-attempt-answer') || /CURRENT CHECK/.test(document.querySelector('[data-cb-route]').innerText))`,
      { timeout: 20000, label: 'lesson section' }
    )
    const binding = await ensureBinding()
    console.log('binding', binding)
    if (binding === 'bound') return true
    await cdp.wait(1200)
  }
  throw new Error('lesson section stayed detached')
}

const settle = async () => {
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1590, y: 990 })
  await cdp.eval(`(() => { const a = document.activeElement; if (a && a.blur) a.blur(); return true })()`)
  await cdp.wait(500)
}

const shots = []
const shoot = async (name, section, caption) => {
  await clearOverlays()
  await settle()
  const path = await cdp.shot(`${RAW}/${name}.png`)
  const meta = await cdp.json(`(() => {
    const r = document.querySelector('[data-cb-route]')
    return {
      name: ${JSON.stringify(name)},
      file: ${JSON.stringify(path)},
      mode: document.documentElement.dataset.hermesMode,
      destination: r ? r.getAttribute('data-cb-destination') : null,
      viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
      heading: (r?.querySelector('h1,h2,h3')?.innerText || '').trim(),
      text: (r?.innerText || '').slice(0, 700),
      activeElement: (() => { const a = document.activeElement; return a ? a.tagName + ':' + (a.getAttribute('id') || '') : null })(),
      errorText: /VALIDATION_FAILED|INTERNAL|HOST_UNAVAILABLE|couldn.t grade|Backend off/.test(r?.innerText || '') ? true : false,
      toast: !!document.querySelector('[data-sonner-toast]')
    }
  })()`)
  Object.assign(meta, { section, caption })
  shots.push(meta)
  log.add(cdp, `shot:${name}`, section, caption, { mode: meta.mode, destination: meta.destination })
  console.log('shot', name, meta.mode, meta.destination, meta.errorText ? 'ERROR-TEXT' : '')
}

const flush = async () => {
  const prior = existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, 'utf8')) : { shots: [], steps: [] }
  const merged = {
    capturedAt: new Date().toISOString(),
    stage,
    rig: { cdpPort: process.env.CB015_CDP_PORT || '9382', viewport: { w: W, h: H, dpr: 2 } },
    shots: [...prior.shots.filter((s) => !shots.some((n) => n.name === s.name)), ...shots],
    steps: [...(prior.steps || []), ...log.steps]
  }
  await writeJson(MANIFEST, merged)
  console.log('manifest', MANIFEST, merged.shots.length, 'shots')
}

await gotoCoursebook(cdp)
await ensureSidebar(cdp)
await collapseSidebar()

if (stage === 'dark') {
  await setMode(cdp, 'dark')

  // 00 — the page as it opens: the learner's course list.
  await clickExact(cdp, 'Courses')
  await cdp.wait(1500)
  const all = await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='All'); if(b){b.click();return true} return false })()`)
  if (all) await cdp.wait(1000)
  await shoot('00-courses-dark', 'Coursebook root, Courses', 'The course list with a real imported pack and its next action.')

  // 01 — Library: the packs installed on this profile.
  await clickExact(cdp, 'Library')
  await cdp.wait(1800)
  await shoot('01-library-dark', 'Coursebook root, Library', 'Library: the pack the course came from, with its recorded provenance.')

  // 02 — the lesson itself: a teaching section with its check panel.
  await openCourse(cdp, COURSE)
  await shoot('00b-overview-dark', 'Course detail, Overview', 'Course detail: next objective, review state and the section entry points.')
  await openLesson()
  await shoot('02-lesson-dark', 'Course detail, section page', 'One lesson: teaching text, objectives and the check that gates progress.')

  // 03 — Textbook index.
  await tab(cdp, 'Textbook')
  await cdp.wait(1500)
  await shoot('03-textbook-dark', 'Course detail, Textbook', 'Textbook: the course outline as sections with their teaching status.')

  // 04 — Notebook with a real saved entry, written from this section.
  await openLesson()
  const saved = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => /save to notebook/i.test((x.innerText || '').trim()))
    if (!b) return false
    b.scrollIntoView({ block: 'center' }); b.click(); return true
  })()`)
  if (saved) {
    await cdp.wait(1200)
    const typed = await cdp.eval(`(() => {
      const f = document.querySelector('[role=dialog] textarea, [role=dialog] input[type=text]')
      if (!f) return false
      f.focus(); return true
    })()`)
    if (typed) {
      await cdp.type('Casual register reads as closeness between peers; the polite form is the same line with distance added.')
      await cdp.wait(400)
    }
    const saveLabel = await cdp.eval(`(() => {
      const d = document.querySelector('[role=dialog]')
      if (!d) return null
      const b = [...d.querySelectorAll('button')].find(x => /^Save/i.test((x.innerText || '').trim()) && !x.disabled)
      return b ? (b.innerText || '').trim() : null
    })()`)
    if (saveLabel) {
      await clickExact(cdp, saveLabel)
      await cdp.wait(1800)
    } else {
      console.log('notebook dialog save control missing')
    }
  }
  await tab(cdp, 'Notebook')
  await cdp.wait(1800)
  await shoot('04-notebook-dark', 'Course detail, Notebook', 'Notebook: the note saved from the lesson, kept with its section and tags.')

  // 05 + 06 — a check answered and then graded (deterministic closed-form lane; no provider call).
  await openLesson()
  await cdp.waitFor(`!!document.querySelector('#cb-attempt-answer')`, { timeout: 20000, label: 'check field' })
  const box = await cdp.json(`(() => {
    const el = document.querySelector('#cb-attempt-answer')
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  })()`)
  await cdp.click(box.x, box.y)
  await cdp.wait(200)
  await cdp.type('B')
  await cdp.wait(500)
  await shoot('05-quiz-question-dark', 'Course detail, section check', 'A check in progress: the answer is typed, submit is enabled and the attempt is not yet recorded.')

  await clickExact(cdp, 'Submit answer')
  await cdp.waitFor(
    `(() => {
      const t = document.querySelector('[data-cb-route]').innerText
      const formGone = !document.querySelector('#cb-attempt-answer')
      return formGone && /(Passed|Partly there|Not yet|Grading failed|couldn.t grade this attempt)/.test(t)
    })()`,
    { timeout: 120000, interval: 200, label: 'graded verdict' }
  )
  await cdp.wait(900)
  await shoot('06-quiz-result-dark', 'Course detail, graded attempt', 'The graded result: verdict, the criteria it was judged on and the next permitted action.')

  // 07 — Parent Studio.
  await clickExact(cdp, 'All courses')
  await cdp.wait(1200)
  await clickExact(cdp, 'Parent Studio')
  await cdp.wait(2000)
  await shoot('07-parent-studio-dark', 'Coursebook root, Parent Studio', 'Parent Studio: a parent-authored pack brief, with the approval gate before anything is taught.')
}

if (stage === 'light') {
  await setMode(cdp, 'light')
  await openCourse(cdp, COURSE)
  await openSectionByIndex(cdp, 0)
  await cdp.waitFor(`/CURRENT CHECK/.test(document.querySelector('[data-cb-route]').innerText)`, { timeout: 20000, label: 'lesson section light' })
  await shoot('08-lesson-light', 'Course detail, section page', 'The same lesson in the light theme (pairs with 02-lesson-dark).')
}

await flush()
cdp.close()
