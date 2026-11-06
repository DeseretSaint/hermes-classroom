#!/usr/bin/env node
/**
 * CB-015 proof 12 — the Desktop half: the stale-source banner and the retained evidence.
 *
 * Reads the live isolated window (CDP 9337) after `scripts/cb015-proof12-stale.py` has driven
 * `source.revalidate` against the same backend (44219). Every assertion here is a DOM read from
 * the rendered plugin; nothing is injected into React state and no control is added.
 *
 *   CB015_CDP_PORT=9337 node scripts/cb015-proof12-ui.mjs --enrollment enr_...
 */
import { connect, hardReload, writeJson } from './cb015-lib.mjs'

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, item, index) => {
    if (item.startsWith('--')) pairs.push([item.slice(2), process.argv[index + 3]])
    return pairs
  }, [])
)
const ENROLLMENT = args.enrollment
const OUT = args.out || 'docs/REVIEW_CB015-row12-ui.json'
const SHOTS = 'docs/cb015-shots'

let cdp = await connect()
const out = { proof: 12, at: new Date().toISOString(), enrollment_id: ENROLLMENT, steps: [], shots: [] }
const log = (m) => console.error(m)

const shoot = async (name) => {
  const path = await cdp.shot(`${SHOTS}/${name}.png`)
  out.shots.push(path)
  return path
}

const routeText = () =>
  cdp.eval(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return root ? root.innerText.replace(/\\n{2,}/g, '\\n') : ''
  })()`)

const record = async (step, extra = {}) => {
  const state = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const text = root ? (root.innerText || '') : ''
    const badge = [...document.querySelectorAll('[data-cb-route] *')].some(
      (n) => (n.innerText || '').trim() === 'Source stale'
    )
    return {
      hash: location.hash,
      destination: root ? root.getAttribute('data-cb-destination') : null,
      routeMounted: Boolean(root),
      staleBadge: badge,
      bannerSentence: /A source behind this course changed\\. Old evidence is kept/.test(text),
      otherBanner: /A source behind this course changed\\. Existing evidence is kept/.test(text),
      excerpt: text.replace(/\\n{2,}/g, '\\n').slice(0, 1800)
    }
  })()`)
  const entry = { step, at: new Date().toISOString(), ...state, ...extra }
  out.steps.push(entry)
  console.log(JSON.stringify({ step, hash: state.hash, destination: state.destination, staleBadge: state.staleBadge, banner: state.bannerSentence || state.otherBanner }))
  return entry
}

cdp = await hardReload(cdp)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 40000, label: 'route root' })
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'coursebook route' })
await cdp.wait(2500)

// ── 1. Library row carries the stale warning ────────────────────────────────
const rows = await cdp.json(`(() => {
  const opens = [...document.querySelectorAll('[data-cb-route] button')].filter(
    (b) => (b.innerText || '').trim() === 'Open'
  )
  return opens.map((button, index) => {
    let node = button
    let container = null
    for (let depth = 0; depth < 8 && node; depth += 1) {
      const text = (node.innerText || '')
      if (/Source stale/.test(text) && text.length < 2400) { container = node; break }
      node = node.parentElement
    }
    return {
      index,
      rowText: container ? container.innerText.replace(/\\n{2,}/g, '\\n') : '',
      hasStale: /Source stale/.test(container ? container.innerText : '')
    }
  })
})()`)
out.library_rows = rows
const target = rows.find((row) => row.hasStale && row.index === 0) || rows.find((row) => row.hasStale)
if (!target) throw new Error('no library row shows the Source stale badge')
await record('library-stale-row', { rowText: target.rowText })
await shoot('row12-01-library-stale')

// ── 2. Open that row's course (Overview) ────────────────────────────────────
await cdp.eval(`(() => {
  const opens = [...document.querySelectorAll('[data-cb-route] button')].filter(
    (b) => (b.innerText || '').trim() === 'Open'
  )
  const button = opens[${target.index}]
  if (!button) return false
  button.scrollIntoView({ block: 'center' })
  button.click()
  return true
})()`)
await cdp.waitFor(`/Source stale|source behind this course/.test(document.querySelector('[data-cb-route]')?.innerText || '')`, { timeout: 30000, label: 'course overview with banner' })
await cdp.wait(1500)
const overview = await record('course-overview-banner')
await shoot('row12-02-overview-banner')

// ── 3. Quizzes: the pre-transition attempt is still listed ──────────────────
const tab = async (label) => {
  const clicked = await cdp.eval(`(() => {
    const candidates = [...document.querySelectorAll('[data-cb-route] button, [data-cb-route] [role="tab"], [data-cb-route] [role="option"]')]
    const b = candidates.find((x) => (x.innerText || '').trim() === ${JSON.stringify(label)})
    if (!b) return false
    b.scrollIntoView({ block: 'center' })
    b.click()
    return true
  })()`)
  if (!clicked) throw new Error(`no tab control labelled ${label}`)
  await cdp.wait(1800)
  return clicked
}
await tab('Quizzes')
const quizzes = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  return {
    text: text.replace(/\\n{2,}/g, '\\n').slice(0, 2200),
    attemptRows: [...root.querySelectorAll('button')].map((b) => (b.innerText || '').trim()).filter((t) => /Pass|Not yet|Review|attempt/i.test(t)).slice(0, 12)
  }
})()`)
await record('quizzes-retained-attempt', { quizText: quizzes.text, attemptRows: quizzes.attemptRows })
await shoot('row12-03-quizzes-retained')

// ── 4. Sources: the changed source reads stale, no control beside it ───────
await tab('Sources')
const sources = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  const buttons = [...root.querySelectorAll('button')].map((b) => (b.innerText || '').trim()).filter(Boolean)
  return {
    text: text.replace(/\\n{2,}/g, '\\n').slice(0, 2200),
    staleRows: /stale/.test(text),
    buttons,
    checkForChanges: buttons.some((b) => /check for changes|revalidate|refresh source/i.test(b))
  }
})()`)
if (sources.checkForChanges) throw new Error('a source-revalidate control is present; the scope ruling forbids it')
await record('sources-stale-no-control', { sourceText: sources.text, buttons: sources.buttons })
await shoot('row12-04-sources-stale')

out.ok = Boolean(overview.staleBadge || overview.bannerSentence || overview.otherBanner)
out.summary = {
  libraryRowWarning: target.hasStale,
  overviewBanner: overview.staleBadge || overview.bannerSentence || overview.otherBanner,
  quizzesListed: /Pass|independent|Not yet|attempt/i.test(quizzes.text),
  sourcesReadStale: sources.staleRows,
  noRevalidateControl: !sources.checkForChanges
}
await writeJson(OUT, out)
console.log(JSON.stringify({ artifact: OUT, summary: out.summary }, null, 2))
cdp.close()
