/**
 * H-120b live rig proof: the conversation-practice surface in one isolated Electron window.
 *
 * The window talks to a disposable backend (`scripts/cb013-live-backend.sh`) whose practice was
 * seeded through the backend's own commands (`scripts/audit-ux-practice-seed.py`). Nothing here
 * injects DOM or CSS: the capture attaches over CDP, clicks the controls the plugin rendered and
 * reads computed styles, geometry and focus from the live renderer.
 *
 *   CB015_CDP_PORT=9341 node scripts/audit-ux-practice.mjs            # capture
 *   CB015_CDP_PORT=9341 node scripts/audit-ux-practice.mjs discover   # print the route text
 *
 * Writes `audit/ux/practice-live.json`, `audit/ux/practice-manifest.json` (viewport, seed inputs,
 * plugin sha256 and one row per frame) and PNGs under `audit/ux/practice-shots/`.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { attach, measure, setMode, setRootText, clearRootText, setReducedMotion, tabWalk, focusNow, esc, ROUTE, setViewportCss } from './audit-ux-lib.mjs'

const PORT = process.env.CB015_CDP_PORT || '9341'
const OUT = 'audit/ux/practice-live.json'
const MANIFEST = 'audit/ux/practice-manifest.json'
const SHOTS = 'audit/ux/practice-shots'
const SEED = 'audit/ux/practice-seed.json'
const PLUGIN = 'desktop/plugin.js'
const COMMAND = 'CB015_CDP_PORT=9341 node scripts/audit-ux-practice.mjs capture'
const mode = process.argv[2] || 'capture'

const pluginSha256 = createHash('sha256').update(readFileSync(PLUGIN)).digest('hex')

mkdirSync(SHOTS, { recursive: true })
const seed = existsSync(SEED) ? JSON.parse(readFileSync(SEED, 'utf8')) : null
const results = { rig: { cdp: PORT, plugin: PLUGIN, plugin_sha256: pluginSha256, command: COMMAND, seed: seed ? { course_id: seed.course_id, objective_id: seed.objective_id, check_id: seed.check_id, session_id: seed.session_id } : null, at: new Date().toISOString() }, variants: {} }

function writeManifest() {
  const frames = Object.values(results.variants).map((v) => ({
    variant: v.variant,
    shot: v.shot,
    footShot: v.footShot || null,
    viewport: v.viewport,
    rootFont: v.rootFont,
    practiceState: v.practiceState,
    controls: v.controls,
    feedback: v.feedback
  }))
  const manifest = {
    generated_by: 'scripts/audit-ux-practice.mjs capture',
    command: COMMAND,
    at: results.rig.at,
    plugin: PLUGIN,
    plugin_sha256: pluginSha256,
    cdp: PORT,
    seed: results.rig.seed,
    seed_inputs: seed ? {
      course_title: seed.course_title,
      objective_title: seed.objective_title,
      turns_said: seed.turns_said,
      check_id: seed.check_id,
      session_id: seed.session_id
    } : null,
    frames
  }
  writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`)
}


const cdp = await attach(PORT)
const wait = (ms) => cdp.wait(ms)
const text = async () => cdp.eval(`((document.querySelector('${ROUTE}') || document.body).innerText || '').replace(/\\s+/g, ' ').trim()`)
const hasPractice = () => cdp.eval(`!!document.querySelector('[data-cb-practice]')`)
const practiceState = () => cdp.eval(`(() => { const n = document.querySelector('[data-cb-practice]'); return n ? n.getAttribute('data-cb-practice-state') : null })()`)

async function waitFor(expression, label, timeout = 12000) {
  await cdp.waitFor(expression, { timeout, label, interval: 150 })
}

async function gotoRoute() {
  await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
  await cdp.eval(`location.hash = '#/coursebook'`)
  await wait(2000)
  if (!(await cdp.eval(`!!document.querySelector('${ROUTE}')`))) {
    await cdp.eval(`location.hash = '#/coursebook'`)
    await wait(1800)
  }
  // A previous run may have left a course page open: the desk is the list this capture opens from.
  if (await clickExact('All courses')) await wait(1200)
}

async function clickExact(label) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return false
    const el = [...root.querySelectorAll('button, a, [role="tab"]')].find((x) => (x.innerText || '').replace(/\\s+/g, ' ').trim() === ${JSON.stringify(label)})
    if (!el) return false
    el.click()
    return true
  })()`)
}

/** Click the "Open" of the card whose own text names `needle`. */
async function openCourse(needle) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return false
    const nodes = [...root.querySelectorAll('*')].filter((el) => {
      const own = (el.innerText || '').trim()
      return own.includes(${JSON.stringify(needle)}) && ![...el.children].some((c) => (c.innerText || '').includes(${JSON.stringify(needle)}))
    })
    let node = nodes[nodes.length - 1]
    for (let depth = 0; depth < 10 && node; depth += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Open')
      if (b) { b.click(); return true }
    }
    return false
  })()`)
}

/** On the course page, open the section whose heading names `needle`. */
async function openSection(needle) {
  return cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return false
    const button = [...root.querySelectorAll('button, a, [role="button"]')].find((x) => (x.innerText || '').replace(/\\s+/g, ' ').trim().includes(${JSON.stringify(needle)}))
    if (button) { button.click(); return true }
    return false
  })()`)
}

/**
 * Get the practice card on screen. The desk puts the most recently touched course in a Continue
 * hero whose own button opens its section; the full list has one "Open" per card. Both are real
 * controls, so the capture tries the hero first and falls back to the card that names the course.
 */
async function enterPractice(needle, sectionNeedle) {
  if (await clickExact('All courses')) await wait(1200)
  const viaHero = await cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return false
    if (!(root.innerText || '').includes(${JSON.stringify(needle)})) return false
    const b = [...root.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Open the section')
    if (!b) return false
    b.click()
    return true
  })()`)
  if (viaHero) {
    await wait(1800)
    if (await hasPractice()) return 'hero'
  }
  if (await clickExact('All courses')) await wait(1200)
  const opened = await openCourse(needle)
  await wait(1800)
  const section = await openSection(sectionNeedle)
  await wait(1800)
  return { opened, section, practice: await hasPractice() }
}

async function snapshot(variant, viewport) {
  await clearRootText(cdp)
  await cdp.clearViewport()
  await setReducedMotion(cdp, false)
  await setMode(cdp, 'dark')
  if (viewport) {
    await setViewportCss(cdp, viewport.width, viewport.height)
    await wait(400)
  }
  // After the viewport override, so a resize-driven re-render cannot drop the 200% root size.
  if (variant.startsWith('text200')) {
    await setRootText(cdp, 32)
    await wait(500)
  }
  // The shot is viewport-only: put the practice card in the frame, not below the fold.
  await cdp.eval(`(() => { const n = document.querySelector('[data-cb-practice]'); if (n) n.scrollIntoView({ block: 'center', inline: 'nearest' }); return !!n })()`)
  await wait(400)
  const metrics = await measure(cdp)
  metrics.variant = variant
  metrics.at = new Date().toISOString()
  if (variant.startsWith('text200') && metrics.rootFont !== '32px') {
    throw new Error(`${variant}: root font is ${metrics.rootFont}, not 32px - the 200% frame is not real`)
  }
  metrics.practiceState = await practiceState()
  metrics.practiceText = await text()
  metrics.feedback = await cdp.eval(`(() => { const n = document.querySelector('[data-cb-practice-feedback]'); return n ? n.textContent.trim() : null })()`)
  metrics.controls = await cdp.eval(`[...document.querySelectorAll('[data-cb-practice] button')].map((b) => b.innerText.trim())`)
  const shot = `${SHOTS}/practice-${variant}.png`
  await cdp.shot(shot)
  metrics.shot = shot
  // A viewport frame at 200% text cannot hold the whole card; a second frame scrolled to the card's
  // foot puts the controls in evidence instead of below the fold.
  const footShot = `${SHOTS}/practice-${variant}-foot.png`
  await cdp.eval(`(() => { const bs = document.querySelectorAll('[data-cb-practice] button'); const last = bs[bs.length - 1]; if (last) last.scrollIntoView({ block: 'end', inline: 'nearest' }); return !!last })()`)
  await wait(300)
  await cdp.shot(footShot)
  metrics.footShot = footShot
  results.variants[variant] = metrics
  writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
  console.log(`captured ${variant}: state=${metrics.practiceState} controls=${JSON.stringify(metrics.controls)} clipped=${(metrics.clipped || []).length} small=${(metrics.smallTargets || []).length}`)
  return metrics
}

await gotoRoute()
if (mode === 'enable') {
  // The decision is read at shell start: set it, then restart the window (scripts/cb013-live-window.sh
  // --restart) so the plugin loads enabled instead of inert.
  await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
  const stored = await cdp.eval(`localStorage.getItem('hermes.desktop.pluginDecisions.v2')`)
  console.log('decision stored:', stored)
  process.exit(0)
}
if (mode === 'probe') {
  if (await clickExact('All courses')) await wait(1200)
  console.log('DESK:', (await text()).slice(0, 700))
  const opensScript = `(() => {
    const root = document.querySelector('${ROUTE}')
    return JSON.stringify([...root.querySelectorAll('button')].filter((b) => /^(Open|Open the section|Resume the lesson)$/.test((b.innerText||'').trim())).map((b) => {
      const card = b.closest('section, article, li, div')
      return { label: (b.innerText||'').trim(), card: (card ? card.innerText : '').replace(/\\s+/g, ' ').slice(0, 160) }
    }), null, 1)
  })()`
  console.log('OPENS:', await cdp.eval(opensScript))
  const hero = await cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const b = [...root.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Open the section')
    if (!b) return false
    b.click()
    return true
  })()`)
  await wait(2000)
  console.log('HERO CLICKED:', hero, 'practice?', await hasPractice())
  console.log('AFTER:', (await text()).slice(0, 3000))
  console.log('CHECK NODES:', await cdp.eval(`JSON.stringify({ practice: !!document.querySelector('[data-cb-practice]'), stimulus: !!document.querySelector('[data-cb-check-stimulus]'), answer: !!document.querySelector('[data-cb-answer-kind]'), checkOpen: !!document.querySelector('[data-cb-check-open]') })`))
  console.log('CHECK AREA:', await cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const nodes = [...root.querySelectorAll('*')].filter((el) => (el.innerText || '').trim() === 'Current check' || (el.innerText || '').includes('could not be opened') || (el.innerText || '').includes('Opening the current check'))
    return JSON.stringify(nodes.slice(0, 4).map((el) => ({ tag: el.tagName, text: (el.innerText || '').slice(0, 300) })), null, 1)
  })()`))
  process.exit(0)
}
if (mode === 'discover') {
  console.log('ROUTE:', (await text()).slice(0, 900))
  const neighbourScript = `(() => {
    const root = document.querySelector('${ROUTE}')
    if (!root) return 'no route'
    const needle = ${JSON.stringify(seed ? seed.course_title : 'Buy a train ticket (practice)')}
    const leaf = [...root.querySelectorAll('*')].filter((el) => {
      const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim()
      return own.includes(needle)
    })
    return JSON.stringify(leaf.map((el) => {
      const chain = []
      let node = el
      for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
        chain.push({
          tag: node.tagName,
          cls: (node.className && String(node.className).slice(0, 80)) || '',
          buttons: [...node.querySelectorAll('button')].map((b) => (b.innerText || '').trim()).slice(0, 6)
        })
      }
      return chain
    }).slice(0, 2), null, 1)
  })()`
  console.log('NEIGHBOURS:', await cdp.eval(neighbourScript))
  const opened = await openCourse(seed ? seed.course_title : 'Buy a train ticket (practice)')
  await wait(1800)
  console.log('OPENED COURSE:', opened)
  console.log('COURSE:', (await text()).slice(0, 1600))
  if (seed) {
    const section = await openSection(seed.objective_title)
    await wait(1800)
    console.log('OPENED SECTION:', section, 'practice?', await hasPractice())
    console.log('SECTION:', (await text()).slice(0, 1600))
  }
  process.exit(0)
}

if (!seed) {
  console.error('no audit/ux/practice-seed.json; run scripts/audit-ux-practice-seed.py first')
  process.exit(2)
}
const openedCourse = await enterPractice(seed.course_title, seed.objective_title)
await waitFor(`!!document.querySelector('[data-cb-practice]')`, 'practice surface').catch(() => {})
const stateBefore = await practiceState()
results.navigation = { how: openedCourse, practiceState: stateBefore }
if (stateBefore === null) {
  console.error('the practice surface did not mount:', (await text()).slice(0, 800))
  process.exit(3)
}

// The live surface, in the two widths the card names and at 200% text.
await snapshot('desktop-1049', { width: 1049, height: 900 })
await snapshot('narrow-460', { width: 460, height: 900 })
await snapshot('text200-1049', { width: 1049, height: 900 })
await snapshot('text200-460', { width: 460, height: 900 })

// Keyboard: every practice control is reachable with Tab from the route.
await clearRootText(cdp)
await cdp.clearViewport()
await setViewportCss(cdp, 1049, 900)
await wait(300)
await cdp.eval(`document.activeElement && document.activeElement.blur && document.activeElement.blur()`)
const walk = await tabWalk(cdp, 60)
const reached = walk.stops.filter((stop) => stop.inRoute && /End practice|Cancel practice|Refresh transcript|Start practice/.test(stop.name))
results.keyboard = {
  stops: walk.stops.length,
  practiceStops: reached.map((stop) => `${stop.tag}:${stop.name}`),
  trap: walk.trap || null,
  escape: await esc(cdp)
}

// End practice: the real route grades the seeded transcript, and the compact line is captured.
const endClicked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-practice] button')].find((x) => (x.innerText || '').trim() === 'End practice')
  if (!b) return false
  b.click()
  return true
})()`)
await waitFor(`!!document.querySelector('[data-cb-practice-feedback]')`, 'practice feedback', 15000).catch(() => {})
await wait(600)
const graded = await snapshot('graded-1049', { width: 1049, height: 900 })
results.end = {
  clicked: endClicked,
  state: await practiceState(),
  feedback: graded.feedback,
  criteriaPresent: await cdp.eval(`!!document.querySelector('[data-cb-practice-criteria]')`),
  bodyHasPercent: (await text()).includes('%')
}
const reviewClicked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('[data-cb-practice] button')].find((x) => (x.innerText || '').trim() === 'Review grading')
  if (!b) return false
  b.click()
  return true
})()`)
await wait(500)
results.end.reviewClicked = reviewClicked
results.end.criteriaCount = await cdp.eval(`document.querySelectorAll('[data-cb-practice-criterion]').length`)
await snapshot('graded-review-1049', { width: 1049, height: 900 })

writeFileSync(OUT, `${JSON.stringify(results, null, 2)}\n`)
writeManifest()
console.log('wrote', OUT, 'and', MANIFEST)
process.exit(0)
