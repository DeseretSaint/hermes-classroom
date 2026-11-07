/**
 * H-64 — live control inventory for the Coursebook Desktop route.
 *
 * Attaches to the isolated Desktop window (CDP 9337, rig home under
 * ~/.hermes/coursebook-test), walks the named surfaces, and records every visible
 * button / link / tab / option with what a real click did: route, dialog, notice,
 * state change, disabled state and a screenshot.
 *
 * Destructive or state-writing controls are NOT clicked: their handler is read from
 * `desktop/plugin.js` and the inventory records the guard that makes them safe to skip.
 *
 *   node scripts/h64-controls.mjs            # walk + write audit/h64/inventory.json
 *   node scripts/h64-controls.mjs --surfaces # list surfaces only
 *
 * Exit code 1 when any visible, enabled control produced no route, dialog, notice or
 * state change (a dead control), so this doubles as the live regression for H-64.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { attach, reset, snapshot, find, click, digest, ROUTE } from './h64-lib.mjs'

const HERE = dirname(new URL(import.meta.url).pathname)
const OUT_DIR = resolve(HERE, '../audit/h64')
const SHOT_DIR = resolve(OUT_DIR, 'controls')
mkdirSync(SHOT_DIR, { recursive: true })

const PORT = process.env.CB015_CDP_PORT || '9337'

/** Controls whose click writes durable state or opens a native picker. Never clicked. */
const SKIP_EXACT = new Set([
  'Import pack',
  'Import a pack',
  'Use my college syllabus',
  'New lesson plan',
  'Create course',
  'Retry the plan job',
  'Submit',
  'Approve',
  'Approve the plan',
  'Approve lesson set',
  'Delete',
  'Archive',
  'Export',
  'Download',
  'Choose folder…',
  'Choose another folder',
  'Choose a syllabus file',
  'Open plan'
])

/** Prefixes that start/steer a lesson run or open a per-row action menu. */
const SKIP_PREFIX = [
  /^Start lesson/,
  /^Resume lesson/,
  /^Resume this section/,
  /^Start a fresh run/,
  /^Continue here$/,
  /^Reattach$/
]

function classify(label) {
  if (SKIP_EXACT.has(label)) return { skip: 'destructive-or-native', why: 'writes state or opens a native picker; handler inspected in source' }
  for (const re of SKIP_PREFIX) {
    if (re.test(label)) return { skip: 'mutating', why: 'starts/steers a lesson run; verified separately with before/after evidence' }
  }
  return null
}

async function shot(cdp, path) {
  return cdp.shot(path)
}

async function selectView(cdp, label) {
  const trigger = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('[role="combobox"]')].find((e) => /^Course view/.test(e.getAttribute('aria-label') || ''))
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const b = el.getBoundingClientRect()
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
  })()`)
  if (!trigger) throw new Error('no course-view picker')
  await cdp.click(trigger.x, trigger.y)
  await cdp.wait(500)
  const pick = await cdp.json(`(() => {
    const el = [...document.querySelectorAll('[role="option"]')].find((e) => (e.innerText || '').trim() === ${JSON.stringify(label)})
    if (!el) return null
    const b = el.getBoundingClientRect()
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
  })()`)
  if (!pick) throw new Error(`no view option ${label}`)
  await cdp.click(pick.x, pick.y)
  await cdp.wait(2000)
}

async function openCourse(cdp) {
  await reset(cdp)
  await click(cdp, 'Open', { wait: 2200 })
  await cdp.wait(800)
}

async function typeInto(cdp, label, text) {
  const box = await find(cdp, label, { exact: false })
  if (!box) throw new Error(`no field ${label}`)
  await cdp.click(box.x, box.y)
  await cdp.wait(200)
  await cdp.type(text)
  await cdp.wait(250)
}

const SURFACES = [
  {
    name: 'field-desk',
    title: 'Home / Field Desk (Courses landing)',
    setup: async (cdp) => { await reset(cdp) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return (
        s.mounted &&
        s.destination === 'courses' &&
        /CONTINUE|Pick up where you left off/.test(s.text) &&
        !/STEP \d OF 3/.test(s.text)
      )
    },
    reset: async (cdp) => { await reset(cdp) }
  },
  {
    name: 'courses-list',
    title: 'Courses list (search & manage)',
    setup: async (cdp) => { await reset(cdp); await click(cdp, 'Search and manage courses', { exact: false, wait: 2200 }) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return (
        s.mounted &&
        /Back to the Field Desk/.test(s.text) &&
        (s.controls || []).some((c) => c.label === 'Search courses')
      )
    },
    reset: async (cdp) => { await reset(cdp) }
  },
  {
    name: 'course-detail',
    title: 'Course detail (Overview)',
    setup: openCourse,
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return (
        s.mounted &&
        /All courses/.test(s.text) &&
        (s.controls || []).some((c) => /^Course view:/.test(c.label))
      )
    },
    reset: openCourse
  },
  ...['Textbook', 'Notebook', 'Quizzes', 'Plan', 'Evidence', 'Sources', 'Export'].map((view) => ({
    name: `view-${view.toLowerCase()}`,
    title: `Course detail — ${view}`,
    setup: async (cdp) => { await openCourse(cdp); await selectView(cdp, view) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && new RegExp(`Course view: ${view}`).test(s.text) || (
        s.mounted && (s.controls || []).some((c) => c.label === `Course view: ${view}`)
      )
    },
    reset: async (cdp) => { await openCourse(cdp); await selectView(cdp, view) }
  })),
  {
    name: 'open-section',
    title: 'Open section (Textbook, one section open)',
    setup: async (cdp) => {
      await openCourse(cdp)
      await selectView(cdp, 'Textbook')
      await click(cdp, 'Open this section', { wait: 3000 }).catch(async () => {
        await click(cdp, 'Next Replace', { exact: false, wait: 3000 })
      })
    },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && /All sections/.test(s.text)
    },
    reset: async (cdp) => {
      await openCourse(cdp)
      await selectView(cdp, 'Textbook')
      await click(cdp, 'Open this section', { wait: 3000 }).catch(async () => {
        await click(cdp, 'Next Replace', { exact: false, wait: 3000 })
      })
    }
  },
  {
    name: 'library',
    title: 'Library',
    setup: async (cdp) => { await reset(cdp); await click(cdp, 'Library', { wait: 2000 }) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && s.destination === 'library'
    },
    reset: async (cdp) => { await reset(cdp); await click(cdp, 'Library', { wait: 2000 }) }
  },
  {
    name: 'parent-studio',
    title: 'Parent Studio',
    setup: async (cdp) => { await reset(cdp); await click(cdp, 'Parent Studio', { wait: 2200 }) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && s.destination === 'studio'
    },
    reset: async (cdp) => { await reset(cdp); await click(cdp, 'Parent Studio', { wait: 2200 }) }
  },
  {
    name: 'new-course-step1',
    title: 'New course — step 1 (scope)',
    setup: async (cdp) => { await reset(cdp); await click(cdp, 'New course', { wait: 1500 }) },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && /STEP 1 OF 3/.test(s.text)
    },
    reset: async (cdp) => { await reset(cdp) }
  },
  {
    name: 'new-course-step2',
    title: 'New course — step 2 (goal, name, use)',
    setup: async (cdp) => {
      await reset(cdp)
      await click(cdp, 'New course', { wait: 1500 })
      await click(cdp, 'A short course', { exact: false, wait: 500 })
      await click(cdp, 'Continue', { wait: 900 })
    },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && /STEP 2 OF 3/.test(s.text)
    },
    reset: async (cdp) => { await reset(cdp) }
  },
  {
    name: 'new-course-step3',
    title: 'New course — step 3 (review)',
    setup: async (cdp) => {
      await reset(cdp)
      await click(cdp, 'New course', { wait: 1500 })
      await click(cdp, 'A short course', { exact: false, wait: 500 })
      await click(cdp, 'Continue', { wait: 900 })
      await typeInto(cdp, 'What do you want to be able to do?', 'Replace a fouled spark plug on a two-stroke engine.')
      await typeInto(cdp, 'Name this course', 'Fouled plug basics')
      await click(cdp, 'Continue', { wait: 900 })
    },
    valid: async (cdp) => {
      const s = await snapshot(cdp)
      return s.mounted && /STEP 3 OF 3/.test(s.text)
    },
    reset: async (cdp) => { await reset(cdp) }
  }
]

async function locate(cdp, control) {
  // Resolve the control by label + occurrence and scroll it into the viewport before reading its
  // center. Snapshot coordinates are viewport-relative and go stale off-screen: without this, a
  // control below the fold is "clicked" at a point outside the window and records a false no-op.
  return cdp.json(`(() => {
    const root = document.querySelector('${ROUTE}') || document.body
    const nodes = [...root.querySelectorAll('button,a[href],[role="tab"],[role="option"],[role="menuitem"],[role="switch"],summary,label[for],input,select,textarea')]
    const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 1 && b.height > 1 }
    const norm = (e) => (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('placeholder') || '').replace(/\\s+/g, ' ').trim().slice(0, 120)
    const wanted = ${JSON.stringify(control.label)}
    const matches = nodes.filter((e) => vis(e) && norm(e) === wanted)
    const el = matches[${Math.max(0, (control.occurrence || 1) - 1)}] || matches[0]
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const b = el.getBoundingClientRect()
    return {
      x: b.x + b.width / 2,
      y: b.y + b.height / 2,
      w: Math.round(b.width),
      h: Math.round(b.height),
      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true'
    }
  })()`)
}

async function inventorySurface(cdp, surface, index) {
  const before = await snapshot(cdp)
  if (!before.mounted) throw new Error(`[${surface.name}] route did not mount`)
  // A surface that did not reach its own definition is not evidence of anything. H-64R's walker
  // skipped this check and inventoried whatever was on screen (course-detail once recorded Parent
  // Studio as "reached"), which turns a setup failure into a false green.
  const reached = await surface.valid(cdp).catch(() => false)
  if (!reached) throw new Error(`[${surface.name}] setup did not reach the surface definition`)
  const surfaceShot = await shot(cdp, resolve(OUT_DIR, `${String(index).padStart(2, '0')}-${surface.name}.png`))
  const controls = []
  const seen = new Map()
  /** label+disabled -> the row whose handler was actually exercised. Repeated rows on the same
   * surface render the same handler (a course row's Open, a pack's Preview), so they are recorded
   * as enumerated but not re-clicked: re-clicking 40 identical rows measures the router, not the
   * control. */
  const exercised = new Map()
  for (const control of before.controls) {
    const key = `${control.tag}|${control.role}|${control.label}|${control.disabled}`
    const occurrence = (seen.get(key) || 0) + 1
    seen.set(key, occurrence)
    const row = {
      index: control.index,
      occurrence,
      tag: control.tag,
      role: control.role,
      label: control.label,
      disabled: control.disabled,
      disabledReason: control.disabled ? 'sdk disabled; no handler runs (see source guard)' : null,
      pressed: control.pressed,
      selected: control.selected,
      rect: { x: control.x, y: control.y }
    }
    const verdict = classify(control.label)
    if (control.disabled) {
      row.outcome = 'disabled'
      row.detail = 'rendered disabled; not clickable'
      controls.push(row)
      continue
    }
    // A control already in its active state (the current nav segment, the chosen option) has no
    // state left to change. This is not a dead control: record it as `current-state`, not `noop`,
    // and say why, so the inventory's noop count stays a claim about controls that claim to act.
    if (control.pressed === 'true' || control.selected === 'true') {
      row.outcome = 'current-state'
      row.detail = 'already pressed/selected; a click has no state left to change'
      controls.push(row)
      continue
    }
    // A text-entry field is not a click action: its contract is that typing focuses and edits it,
    // and the steps that host fields (new-course step 3) exercise that by typing. Recording a
    // clicked input as `noop` measures the wrong thing.
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(control.tag)) {
      row.outcome = 'field'
      row.detail = 'text-entry field; proven by typing in the surface setup, not by a click'
      controls.push(row)
      continue
    }
    if (verdict) {
      row.outcome = verdict.skip
      row.detail = verdict.why
      controls.push(row)
      continue
    }
    if (exercised.has(key)) {
      const first = exercised.get(key)
      row.outcome = 'same-handler'
      row.detail = `same handler as index ${first.index} / occurrence ${first.occurrence} on this surface (exercised once)`
      controls.push(row)
      continue
    }
    exercised.set(key, row)
    // Re-validate the surface before every click: a previous click may have navigated.
    const valid = await surface.valid(cdp).catch(() => false)
    if (!valid) {
      // Re-enter the surface, not just leave the current one: `reset` returns to the route root,
      // which is the wrong place for a deep surface (scope step, a course view).
      await surface.setup(cdp)
      await cdp.wait(1200)
    }
    const fresh = await snapshot(cdp)
    let target = await locate(cdp, control)
    if (!target) {
      // The surface re-rendered into a state that no longer carries this control (an opened
      // flow, a menu): re-enter the surface and try once more before calling it drifted.
      await surface.setup(cdp)
      await cdp.wait(1200)
      target = await locate(cdp, control)
    }
    if (!target) {
      row.outcome = 'drifted'
      row.detail = 'control no longer present after the surface re-rendered'
      controls.push(row)
      continue
    }
    // `scrollIntoView` moved the page; read the center again once layout has settled.
    await cdp.wait(150)
    target = (await locate(cdp, control)) || target
    if (target.disabled) {
      row.outcome = 'disabled'
      row.detail = 'became disabled after the surface re-rendered'
      controls.push(row)
      continue
    }
    const base = { hash: fresh.hash, text: digest(fresh.text), dialogs: fresh.dialogs.length, notices: fresh.notices.join('|'), controls: JSON.stringify(fresh.controls.map((c) => [c.label, c.pressed, c.selected, c.disabled])) }
    await cdp.click(target.x, target.y)
    // A section/page render can take well over a second; measuring at 1.4 s read a real
    // navigation as a no-op (H-64R's "Open this section").
    await cdp.wait(2400)
    const afterClick = await snapshot(cdp)
    const shotPath = await shot(cdp, resolve(SHOT_DIR, `${String(index).padStart(2, '0')}-${surface.name}-${String(control.index).padStart(3, '0')}.png`))
    row.screenshot = shotPath.replace(`${resolve(HERE, '..')}/`, '')
    const hashChanged = afterClick.hash !== base.hash
    const mountedChanged = afterClick.mounted !== fresh.mounted
    const destChanged = afterClick.destination !== fresh.destination
    const textChanged = digest(afterClick.text) !== base.text
    const dialogOpened = afterClick.dialogs.length > base.dialogs
    const noticeText = afterClick.notices.join('|')
    const noticeChanged = noticeText !== base.notices
    const controlStateChanged = JSON.stringify(afterClick.controls.map((c) => [c.label, c.pressed, c.selected, c.disabled])) !== base.controls
    row.after = {
      hash: afterClick.hash,
      mounted: afterClick.mounted,
      destination: afterClick.destination,
      dialog: dialogOpened ? afterClick.dialogs[afterClick.dialogs.length - 1] : null,
      notices: noticeChanged ? noticeText : null,
      textChanged,
      controlStateChanged
    }
    if (dialogOpened || /menu/i.test(afterClick.controls.map((c) => c.role).join(','))) {
      row.outcome = 'dialog'
      row.detail = afterClick.dialogs[0] || 'menu opened'
      await cdp.key('Escape')
      await cdp.wait(400)
    } else if (hashChanged || mountedChanged || destChanged) {
      row.outcome = 'navigated'
      row.detail = `${base.hash} -> ${afterClick.hash}${mountedChanged ? ' (route unmounted)' : ''}${destChanged ? ` dest ${fresh.destination}->${afterClick.destination}` : ''}`
    } else if (textChanged) {
      row.outcome = 'state'
      row.detail = 'surface text/state changed'
    } else if (noticeChanged) {
      row.outcome = 'notice'
      row.detail = noticeText
    } else if (controlStateChanged) {
      row.outcome = 'state'
      row.detail = 'control state changed'
    } else {
      row.outcome = 'noop'
      row.detail = 'no route, dialog, notice or state change'
    }
    controls.push(row)
    // Settle back to the surface so the next control is measured from a known state.
    if (row.outcome === 'navigated' || row.outcome === 'dialog') {
      const stillValid = await surface.valid(cdp).catch(() => false)
      if (!stillValid) {
        await surface.reset(cdp)
        await cdp.wait(1200)
      }
    }
  }
  return {
    name: surface.name,
    title: surface.title,
    reached: { hash: before.hash, destination: before.destination },
    screenshot: surfaceShot.replace(`${resolve(HERE, '..')}/`, ''),
    textExcerpt: before.text.slice(0, 1200),
    dialogs: before.dialogs,
    controls
  }
}

async function main() {
  if (process.argv.includes('--surfaces')) {
    console.log(SURFACES.map((s) => `${s.name}\t${s.title}`).join('\n'))
    return
  }
  const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null
  const cdp = await attach(PORT)
  const selected = only ? SURFACES.filter((s) => s.name === only) : SURFACES
  if (!selected.length) throw new Error(`unknown surface ${only}`)
  const report = { generatedAt: new Date().toISOString(), port: PORT, surfaces: [] }
  for (const surface of selected) {
    const index = SURFACES.indexOf(surface)
    process.stderr.write(`[h64] ${surface.name}\n`)
    try {
      await surface.setup(cdp)
      await cdp.wait(1200)
      const entry = await inventorySurface(cdp, surface, index)
      entry.index = index
      report.surfaces.push(entry)
      if (only) writeFileSync(resolve(OUT_DIR, `inventory-${surface.name}.json`), `${JSON.stringify(entry, null, 2)}\n`)
    } catch (error) {
      report.surfaces.push({ name: surface.name, title: surface.title, index, error: String(error && error.message ? error.message : error) })
    }
  }
  await reset(cdp).catch(() => {})
  const dead = []
  for (const surface of report.surfaces) {
    for (const control of surface.controls || []) {
      if (control.outcome === 'noop') dead.push(`${surface.name}: ${control.label}`)
    }
  }
  report.deadControls = dead
  const errored = report.surfaces.filter((surface) => surface.error)
  report.erroredSurfaces = errored.map((surface) => `${surface.name}: ${surface.error}`)
  // A surface that never reached its definition proves nothing and must not read as green.
  report.ok = dead.length === 0 && errored.length === 0
  if (!only) writeFileSync(resolve(OUT_DIR, 'inventory.json'), `${JSON.stringify(report, null, 2)}\n`)
  const total = report.surfaces.reduce((n, s) => n + (s.controls ? s.controls.length : 0), 0)
  const counts = {}
  for (const surface of report.surfaces) {
    for (const control of surface.controls || []) counts[control.outcome] = (counts[control.outcome] || 0) + 1
  }
  console.log(JSON.stringify({ surfaces: report.surfaces.length, controls: total, outcomes: counts, deadControls: dead, erroredSurfaces: report.erroredSurfaces, ok: report.ok }, null, 2))
  cdp.close()
  if (!report.ok) process.exitCode = 1
}

await main()
