/**
 * Sentinel extras: display cadence, repeat-navigation leak test, and the over-cap UI capture.
 *
 *   CB015_CDP_PORT=9371 node docs/sentinel-perf/extras.mjs --course legal
 */
import { connect } from '/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_19da8432/scripts/cb015-lib.mjs'
import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const which = process.argv.includes('--course')
  ? process.argv[process.argv.indexOf('--course') + 1]
  : 'legal'
const COURSES = {
  legal: { match: 'sixty situations', objectives: 60 },
  overcap: { match: 'fifty-five situations', objectives: 55 }
}
const course = COURSES[which]
const cdp = await connect()
const rows = []
const OUT = resolve(`docs/sentinel-perf/results/extras-${which}.json`)
mkdirSync(resolve('docs/sentinel-perf/results'), { recursive: true })
const flush = () => writeFileSync(OUT, `${JSON.stringify({ course: which, rows }, null, 2)}\n`)
const routeText = `(document.querySelector('[data-cb-route]')?.innerText || '')`
const sleep = (ms) => cdp.wait(ms)

const push = (row) => {
  rows.push(row)
  flush()
  console.log(JSON.stringify(row))
}

const clickText = async (label) =>
  cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button')].find((x) => (x.innerText || '').trim() === ${JSON.stringify(label)})
    if (!b) return 'missing'
    b.click()
    return 'clicked'
  })()`)

const tab = async (label) =>
  cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find((x) => (x.innerText || '').trim() === ${JSON.stringify(label)})
    if (!b) return 'missing'
    b.click()
    return 'clicked'
  })()`)

const openCourse = async () => {
  const outcome = await cdp.eval(`(() => {
    const wanted = ${JSON.stringify(course.match.toLowerCase())}
    const root = document.querySelector('[data-cb-route]')
    if (!root) return 'no-route'
    const leaf = [...root.querySelectorAll('*')].find(
      (e) => e.children.length === 0 && (e.textContent || '').toLowerCase().includes(wanted)
    )
    if (!leaf) return 'no-title'
    let node = leaf
    for (let depth = 0; depth < 8 && node; depth += 1) {
      const opens = [...node.querySelectorAll('button')].filter((b) => (b.innerText || '').trim() === 'Open')
      if (opens.length === 1) { opens[0].click(); return 'clicked' }
      if (opens.length > 1) return 'ambiguous-card'
      node = node.parentElement
    }
    return 'no-card'
  })()`)
  if (outcome !== 'clicked') throw new Error(`open course: ${outcome}`)
  await cdp.waitFor(`/CURRENT OBJECTIVE/.test(${routeText})`, { timeout: 30000, label: 'detail' })
  await tab('Textbook')
  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`,
    { timeout: 30000, label: 'rows' }
  )
}

const openSection = async (index) => cdp.eval(`(() => {
  const bs = [...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section')
  if (!bs[${index}]) return 'missing'
  bs[${index}].click()
  return 'clicked'
})()`)

const resetToCourseList = async () => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await sleep(300)
  // The top-level "Courses" tab always returns to the library grid, even from a lesson page.
  await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[data-cb-route] button[aria-pressed]')]
      .find((x) => (x.innerText || '').trim() === 'Courses')
    if (b) b.click()
    return !!b
  })()`)
  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open').length > 0`,
    { timeout: 30000, label: 'course grid' }
  )
  await sleep(300)
}

await resetToCourseList()

// ── A. display cadence: 1s of idle rAF with no work ─────────────────────────────────────────
const idle = await cdp.eval(`(() => new Promise((resolve) => {
  const stamps = []
  const started = performance.now()
  const step = (t) => {
    stamps.push(t)
    if (performance.now() - started < 1000) requestAnimationFrame(step)
    else {
      const deltas = []
      for (let i = 1; i < stamps.length; i += 1) deltas.push(stamps[i] - stamps[i - 1])
      deltas.sort((a, b) => a - b)
      resolve({
        frames: deltas.length,
        medianFrameMs: +deltas[Math.floor(deltas.length / 2)].toFixed(2),
        p95FrameMs: +deltas[Math.floor(deltas.length * 0.95)].toFixed(2),
        worstFrameMs: +deltas[deltas.length - 1].toFixed(2),
        impliedHz: Math.round(1000 / deltas[Math.floor(deltas.length / 2)])
      })
    }
  }
  requestAnimationFrame(step)
}))()`)
push({ id: 'idle-cadence', label: 'idle requestAnimationFrame cadence (1s)', ...idle })

// ── B. repeat-navigation leak test with GC (legal pack only: its lesson renders) ───────────
if (which === 'legal') {
  await openCourse()
  await cdp.send('HeapProfiler.enable')
  await cdp.send('HeapProfiler.collectGarbage')
  const series = []
  const heapNow = async () => cdp.json(`(() => ({
    usedMb: +(performance.memory.usedJSHeapSize / 1048576).toFixed(2),
    nodes: document.querySelectorAll('[data-cb-route] *').length
  }))()`)
  series.push({ cycle: 0, ...(await heapNow()) })
  for (let cycle = 1; cycle <= 10; cycle += 1) {
    await openSection(0)
    await cdp.waitFor(`/Which register do you choose/.test(${routeText})`, { timeout: 20000, label: 'lesson body' })
    await clickText('All sections')
    await cdp.waitFor(
      `[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`,
      { timeout: 20000, label: 'index again' }
    )
    await sleep(120)
    await cdp.send('HeapProfiler.collectGarbage')
    await sleep(120)
    series.push({ cycle, ...(await heapNow()) })
    flush()
  }
  const first = series[0].usedMb
  const last = series[series.length - 1].usedMb
  const peak = Math.max(...series.map((s) => s.usedMb))
  push({
    id: 'leak-repeat-nav',
    label: '10 × open long lesson → return to index, heap after forced GC',
    series,
    growthMb: +(last - first).toFixed(2),
    peakMb: peak,
    growthPerCycleMb: +((last - first) / 10).toFixed(3)
  })
}

// ── C. over-cap lesson: the UI error state (D1 evidence) ──────────────────────────────────
if (which === 'overcap') {
  await openCourse()
  await openSection(0)
  await sleep(1500)
  const state = await cdp.json(`(() => ({
    text: (document.querySelector('[data-cb-route]')?.innerText || '').slice(0, 700),
    pres: document.querySelectorAll('[data-cb-route] pre').length,
    hasRetry: [...document.querySelectorAll('[data-cb-route] button')].some((b) => (b.innerText || '').trim() === 'Try again')
  }))()`)
  const shot = await cdp.shot(resolve('docs/sentinel-perf/shots/overcap-lesson-error.png'))
  push({ id: 'overcap-ui', label: 'section > 8000 chars in the lesson pane', ...state, shot })
}

console.log(`\nwrote ${OUT}`)
cdp.close()
