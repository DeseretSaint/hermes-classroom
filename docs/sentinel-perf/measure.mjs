/**
 * Sentinel long-content + 50+ objective performance harness.
 *
 * Runs against the isolated window (CDP 9351) and the isolated backend (44241), both installed
 * from candidate b476738. Every number is read from the live renderer; nothing is simulated.
 *
 *   CB015_CDP_PORT=9351 node docs/sentinel-perf/measure.mjs --course legal
 *   CB015_CDP_PORT=9351 node docs/sentinel-perf/measure.mjs --course baseline
 */
import { connect } from '/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_19da8432/scripts/cb015-lib.mjs'
import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const which = process.argv.includes('--course')
  ? process.argv[process.argv.indexOf('--course') + 1]
  : 'legal'
const COURSES = {
  legal: { match: 'sixty situations', objectives: 60, longIndex: 0, lastIndex: 59 },
  baseline: { match: 'three-situation baseline', objectives: 3, longIndex: 0, lastIndex: 2 }
}
const course = COURSES[which]
if (!course) throw new Error(`unknown course ${which}`)

const cdp = await connect()
const rows = []
const OUT = resolve(`docs/sentinel-perf/results/raw-${which}.json`)
mkdirSync(resolve('docs/sentinel-perf/results'), { recursive: true })
const flush = () => writeFileSync(OUT, `${JSON.stringify({ course: which, rows }, null, 2)}\n`)

const now = () => Date.now()
const routeReady = `!!document.querySelector('[data-cb-route]')`
const routeText = `(document.querySelector('[data-cb-route]')?.innerText || '')`
const sleep = (ms) => cdp.wait(ms)

const stats = async () => cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const scrollers = [...(root ? [root, ...root.querySelectorAll('*')] : [])]
    .filter((el) => el.scrollHeight > el.clientHeight + 8 && el.clientHeight > 200)
    .sort((a, b) => b.scrollHeight - a.scrollHeight)
  return {
    nodes: root ? root.querySelectorAll('*').length : 0,
    textChars: root ? root.innerText.length : 0,
    pres: root ? root.querySelectorAll('pre').length : 0,
    codes: root ? root.querySelectorAll('code').length : 0,
    ols: root ? root.querySelectorAll('ol').length : 0,
    lis: root ? root.querySelectorAll('li').length : 0,
    tables: root ? root.querySelectorAll('table').length : 0,
    h2: root ? root.querySelectorAll('h2').length : 0,
    scroll: scrollers[0]
      ? { tag: scrollers[0].tagName, cls: String(scrollers[0].className || '').slice(0, 60), scrollHeight: scrollers[0].scrollHeight, clientHeight: scrollers[0].clientHeight }
      : null
  }
})()`)

const installLongTasks = () => cdp.eval(`(() => {
  window.__cbLong = window.__cbLong || []
  window.__cbLong.length = 0
  if (!window.__cbLongObserver) {
    try {
      window.__cbLongObserver = new PerformanceObserver((list) => {
        for (const e of list.getEntries()) window.__cbLong.push(Math.round(e.duration))
      })
      window.__cbLongObserver.observe({ entryTypes: ['longtask'] })
    } catch (error) { window.__cbLongError = String(error) }
  }
  return true
})()`)
const readLongTasks = async () => {
  const tasks = await cdp.json(`(() => window.__cbLong || [])()`)
  return {
    longTasks: tasks,
    longTaskCount: tasks.length,
    longTaskMaxMs: tasks.length ? Math.max(...tasks) : 0,
    longTaskTotalMs: tasks.reduce((a, b) => a + b, 0)
  }
}

const startFrameLoop = () => cdp.eval(`(() => {
  window.__frames = []
  window.__frameStop = false
  const step = (t) => { window.__frames.push(t); if (!window.__frameStop) requestAnimationFrame(step) }
  requestAnimationFrame(step)
  return true
})()`)
const stopFrameLoop = async () => cdp.json(`(() => {
  window.__frameStop = true
  const f = window.__frames || []
  const deltas = []
  for (let i = 1; i < f.length; i += 1) deltas.push(Math.round(f[i] - f[i - 1]))
  return {
    frames: deltas.length,
    worstFrameMs: deltas.length ? Math.max(...deltas) : 0,
    over32ms: deltas.filter((d) => d > 32).length,
    over50ms: deltas.filter((d) => d > 50).length,
    medianMs: deltas.length ? deltas.slice().sort((a, b) => a - b)[Math.floor(deltas.length / 2)] : 0
  }
})()`)

const memory = async () => cdp.json(`(() => ({
  jsHeapUsedMb: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(2) : null,
  jsHeapTotalMb: performance.memory ? +(performance.memory.totalJSHeapSize / 1048576).toFixed(2) : null,
  domNodes: document.querySelectorAll('*').length
}))()`)
const rendererRssMb = () => {
  try {
    const line = execSync(
      `ps -eo pid,rss,args | grep -- '--type=renderer' | grep 'sentinel-perf/userdata' | grep -v grep | head -1`,
      { encoding: 'utf8' }
    ).trim()
    if (!line) return null
    const [pid, rssKb] = line.split(/\s+/)
    return { pid: Number(pid), rssMb: +(Number(rssKb) / 1024).toFixed(1) }
  } catch {
    return null
  }
}

const clickText = async (label, { exact = true } = {}) =>
  cdp.eval(`(() => {
    const wanted = ${JSON.stringify(label)}
    const all = [...document.querySelectorAll('[data-cb-route] button, [data-cb-route] [role="tab"]')]
    const el = all.find((e) => {
      const t = (e.innerText || '').trim()
      return ${exact ? 't === wanted' : 't.includes(wanted)'}
    })
    if (!el) return 'missing'
    el.click()
    return 'clicked'
  })()`)

const TAB_MARKERS = {
  Textbook: 'Open section',
  Notebook: 'All tags',
  Quizzes: 'All results',
  Overview: 'CURRENT OBJECTIVE',
  Plan: 'Challenge out',
  Evidence: 'CURRENT RECOMMENDATION',
  Sources: 'Reference 1'
}

/** Click a pane tab and time it inside the renderer: input → next paint, and input → content. */
const switchTabMeasured = async (name) =>
  cdp.eval(`(() => new Promise((resolve) => {
    const name = ${JSON.stringify(name)}
    const marker = ${JSON.stringify(TAB_MARKERS[name] || '')}
    const b = [...document.querySelectorAll('[data-cb-route] button[aria-pressed]')]
      .find((x) => (x.innerText || '').trim() === name)
    if (!b) return resolve({ ok: false, reason: 'tab-missing' })
    const t0 = performance.now()
    b.click()
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const paintMs = Math.round(performance.now() - t0)
      const poll = () => {
        const text = document.querySelector('[data-cb-route]')?.innerText || ''
        if (text.includes(marker)) {
          resolve({ ok: true, paintMs, contentMs: Math.round(performance.now() - t0) })
          return
        }
        if (performance.now() - t0 > 8000) {
          resolve({ ok: false, paintMs, contentMs: -1 })
          return
        }
        setTimeout(poll, 16)
      }
      poll()
    }))
  }))()`)


const openCourse = async () => {
  const outcome = await cdp.eval(`(() => {
    const wanted = ${JSON.stringify(course.match.toLowerCase())}
    const root = document.querySelector('[data-cb-route]')
    if (!root) return 'no-route'
    // The title's nearest leaf, then the first ancestor that owns exactly one "Open" button: the card.
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
  await cdp.waitFor(`/CURRENT OBJECTIVE/.test(${routeText})`, { timeout: 30000, label: 'course detail' })
}

const resetToCourses = async () => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await sleep(300)
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

const measure = async (id, label, fn) => {
  const started = now()
  let detail = {}
  let error = null
  try {
    detail = await fn()
  } catch (failure) {
    error = String(failure && failure.message ? failure.message : failure)
  }
  const row = { id, label, wallMs: now() - started, ...(detail || {}), ...(error ? { error } : {}) }
  rows.push(row)
  flush()
  console.log(JSON.stringify(row))
  return row
}

// ── 0. baseline memory ───────────────────────────────────────────────────────────────────────
await resetToCourses()
const memBefore = await memory()
const rssBefore = rendererRssMb()

// ── 1. cold mount: reload and time the Coursebook route ─────────────────────────────────────
await measure('cold-mount', 'reload on #/coursebook → route mounted with rows', async () => {
  await cdp.eval(`location.hash = '#/coursebook'`)
  const t0 = now()
  await cdp.send('Page.reload', { ignoreCache: false })
  await cdp.waitFor(`document.readyState === 'complete'`, { timeout: 30000, label: 'readyState' })
  const readyMs = now() - t0
  await cdp.waitFor(`${routeReady} && /${course.match}/i.test(${routeText})`, { timeout: 30000, label: 'route with rows' })
  const mountMs = now() - t0
  await sleep(500)
  const paint = await cdp.json(`performance.getEntriesByType('paint').map((e) => ({ name: e.name, startTime: Math.round(e.startTime) }))`)
  const nav = await cdp.json(`(() => {
    const n = performance.getEntriesByType('navigation')[0]
    return n ? { domContentLoaded: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd) } : null
  })()`)
  return {
    readyMs,
    mountMs,
    firstPaintMs: (paint.find((p) => p.name === 'first-paint') || {}).startTime ?? null,
    firstContentfulPaintMs: (paint.find((p) => p.name === 'first-contentful-paint') || {}).startTime ?? null,
    paint,
    nav
  }
})

// ── 2. course list ──────────────────────────────────────────────────────────────────────────
await measure('course-list', 'course list with 3 courses / 118 objectives', async () => {
  await resetToCourses()
  return await stats()
})

// ── 3. open the large course ────────────────────────────────────────────────────────────────
await installLongTasks()
await measure('course-detail', `open ${course.objectives}-objective course detail`, async () => {
  const t0 = now()
  await openCourse()
  return { renderMs: now() - t0, ...(await stats()) }
})
rows.push({ id: 'course-detail-longtasks', ...(await readLongTasks()) })
flush()

// ── 4. textbook index ───────────────────────────────────────────────────────────────────────
await installLongTasks()
await measure('textbook-index', `render ${course.objectives}-row textbook index`, async () => {
  const t0 = now()
  await switchTabMeasured('Textbook')

  await cdp.waitFor(
    `[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`,
    { timeout: 30000, label: 'all section rows' }
  )
  const renderMs = now() - t0
  return {
    renderMs,
    sectionRows: await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length`),
    ...(await stats())
  }
})
rows.push({ id: 'textbook-index-longtasks', ...(await readLongTasks()) })
flush()

// ── 5. open the long lesson (objective 1) ───────────────────────────────────────────────────
await installLongTasks()
const openSection = async (index) => {
  const outcome = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section')
    const b = bs[${index}]
    if (!b) return 'missing'
    b.click()
    return 'clicked(' + bs.length + ')'
  })()`)
  if (!String(outcome).startsWith('clicked')) throw new Error(`open section ${index}: ${outcome}`)
  return outcome
}
const firstLesson = await measure('lesson-long', `open objective 1 (long multi-segment lesson)`, async () => {
  const t0 = now()
  const clicked = await openSection(course.longIndex)
  await cdp.waitFor(`/TEACHING SEGMENTS/.test(${routeText})`, { timeout: 30000, label: 'teaching segments' })
  const segmentsAt = now() - t0
  // full content: the closing quote of the last segment
  await cdp.waitFor(`/Which register do you choose/.test(${routeText})`, { timeout: 30000, label: 'last segment text' })
  const fullAt = now() - t0
  return {
    clicked,
    segmentsMarkerMs: segmentsAt,
    fullRenderMs: fullAt,
    heading: await cdp.eval(`(() => {
      const t = document.querySelector('[data-cb-route]').innerText
      const m = t.match(/Objective \\d+: register in context \\d+/)
      return m ? m[0] : null
    })()`),
    ...(await stats())
  }
})
rows.push({ id: 'lesson-long-longtasks', ...(await readLongTasks()) })
flush()

// ── 6. scroll the long lesson ───────────────────────────────────────────────────────────────
await installLongTasks()
await measure('scroll-long', 'scroll the long lesson top→bottom→top', async () => {
  const scroller = await cdp.eval(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const all = [root, ...root.querySelectorAll('*')]
    const el = all.filter((e) => e.scrollHeight > e.clientHeight + 8 && e.clientHeight > 200)
      .sort((a, b) => b.scrollHeight - a.scrollHeight)[0]
    if (!el) return null
    el.dataset.cbPerfScroll = '1'
    window.__cbScroller = el
    el.scrollTop = 0
    return { scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }
  })()`)
  if (!scroller) return { scroller: null, note: 'no scrollable container' }
  await startFrameLoop()
  const sweep = await cdp.eval(`(() => new Promise((resolve) => {
    const node = window.__cbScroller
    const started = performance.now()
    const step = () => {
      node.scrollTop = Math.min(node.scrollHeight, node.scrollTop + 260)
      if (node.scrollTop + node.clientHeight < node.scrollHeight && performance.now() - started < 6000) {
        requestAnimationFrame(step)
      } else { resolve({ finalScrollTop: Math.round(node.scrollTop) }) }
    }
    requestAnimationFrame(step)
  }))()`)
  const frames = await stopFrameLoop()
  const back = await cdp.eval(`(() => new Promise((resolve) => {
    const node = window.__cbScroller
    const started = performance.now()
    const step = () => {
      node.scrollTop = Math.max(0, node.scrollTop - 400)
      if (node.scrollTop > 0 && performance.now() - started < 6000) requestAnimationFrame(step)
      else resolve({ finalScrollTop: Math.round(node.scrollTop) })
    }
    requestAnimationFrame(step)
  }))()`)
  return { scroller, sweep, back, ...frames }
})
rows.push({ id: 'scroll-long-longtasks', ...(await readLongTasks()) })
flush()

// ── 7. open the last objective (long title + long lesson) ──────────────────────────────────
await installLongTasks()
await measure('lesson-last', `open objective ${course.objectives} (long title)`, async () => {
  await switchTabMeasured('Textbook')

  await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`, { timeout: 20000, label: 'rows' })
  const t0 = now()
  await openSection(course.lastIndex)
  await cdp.waitFor(`/TEACHING SEGMENTS/.test(${routeText})`, { timeout: 30000, label: 'last lesson' })
  await cdp.waitFor(`/Which register do you choose/.test(${routeText})`, { timeout: 30000, label: 'last lesson body' })
  return {
    renderMs: now() - t0,
    headingPresent: await cdp.eval(`/deliberately long title/.test(${routeText})`),
    heading: await cdp.eval(`(() => {
      const t = document.querySelector('[data-cb-route]').innerText
      const m = t.match(/Objective \\d+: register in context \\d+/g)
      return m ? m[m.length - 1] : null
    })()`),
    ...(await stats())
  }
})
rows.push({ id: 'lesson-last-longtasks', ...(await readLongTasks()) })
flush()

// ── 8. rapid navigation: textbook → notebook → quizzes → overview × N ──────────────────────
await installLongTasks()
const memPreNav = await memory()
await measure('rapid-nav', 'rapid pane switches with the large course loaded', async () => {
  const sequence = ['Textbook', 'Notebook', 'Quizzes', 'Overview', 'Textbook', 'Plan', 'Textbook']
  await switchTabMeasured('Textbook')

  await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`, { timeout: 20000, label: 'rows before nav' })
  await startFrameLoop()
  const latencies = []
  for (let cycle = 0; cycle < 5; cycle += 1) {
    for (const name of sequence) {
      const outcome = await switchTabMeasured(name)
      latencies.push({ tab: name, cycle, ...outcome })
      await sleep(40)
    }
  }
  const frames = await stopFrameLoop()
  const contentTimes = latencies.filter((l) => l.contentMs >= 0).map((l) => l.contentMs).sort((a, b) => a - b)
  const paintTimes = latencies.filter((l) => typeof l.paintMs === 'number').map((l) => l.paintMs).sort((a, b) => a - b)
  return {
    switches: latencies.length,
    failedSwitches: latencies.filter((l) => !l.ok).length,
    medianContentMs: contentTimes[Math.floor(contentTimes.length / 2)],
    p95ContentMs: contentTimes[Math.floor(contentTimes.length * 0.95)],
    worstContentMs: contentTimes[contentTimes.length - 1],
    medianPaintMs: paintTimes[Math.floor(paintTimes.length / 2)],
    worstPaintMs: paintTimes[paintTimes.length - 1],
    perTabMedian: Object.fromEntries(
      sequence.map((name) => {
        const list = latencies.filter((l) => l.tab === name && l.contentMs >= 0).map((l) => l.contentMs).sort((a, b) => a - b)
        return [name, list.length ? list[Math.floor(list.length / 2)] : null]
      })
    ),
    ...frames
  }
})
const navLong = await readLongTasks()
const memPostNav = await memory()
rows.push({ id: 'rapid-nav-longtasks', ...navLong })
rows.push({
  id: 'memory-nav',
  label: 'JS heap across 35 pane switches',
  before: memPreNav,
  after: memPostNav,
  deltaHeapMb: memPostNav.jsHeapUsedMb != null && memPreNav.jsHeapUsedMb != null
    ? +(memPostNav.jsHeapUsedMb - memPreNav.jsHeapUsedMb).toFixed(2)
    : null
})
flush()

// ── 9. 200% text and 460px on the long lesson ───────────────────────────────────────────────
await switchTabMeasured('Textbook')
await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= ${course.objectives}`, { timeout: 20000, label: 'rows' })
await openSection(course.longIndex)
await cdp.waitFor(`/Which register do you choose/.test(${routeText})`, { timeout: 30000, label: 'long lesson again' })

await measure('text200', 'long lesson at 200% text', async () => {
  await cdp.eval(`document.documentElement.style.fontSize = '32px'`)
  await sleep(700)
  const detail = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const clipped = [...root.querySelectorAll('*')].filter((el) => el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflowX === 'visible').length
    return {
      rootFontPx: getComputedStyle(document.documentElement).fontSize,
      overflowX: document.documentElement.scrollWidth - window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      clippedNodes: clipped
    }
  })()`)
  await cdp.eval(`document.documentElement.style.fontSize = ''`)
  await sleep(400)
  return detail
})

await measure('narrow460', 'long lesson at 460px', async () => {
  await cdp.setViewport(460, 900)
  await sleep(800)
  const detail = await cdp.json(`(() => ({
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    headingVisible: /register in context/.test(document.querySelector('[data-cb-route]')?.innerText || '')
  }))()`)
  await cdp.clearViewport()
  await sleep(400)
  return detail
})

// ── 10. memory after all work ──────────────────────────────────────────────────────────────
const memAfter = await memory()
const rssAfter = rendererRssMb()
rows.push({
  id: 'memory-session',
  label: 'JS heap and renderer RSS across the whole run',
  before: { ...memBefore, rss: rssBefore },
  after: { ...memAfter, rss: rssAfter },
  deltaHeapMb: memAfter.jsHeapUsedMb != null && memBefore.jsHeapUsedMb != null
    ? +(memAfter.jsHeapUsedMb - memBefore.jsHeapUsedMb).toFixed(2)
    : null,
  deltaRssMb: rssAfter && rssBefore ? +(rssAfter.rssMb - rssBefore.rssMb).toFixed(1) : null
})
flush()

console.log(`\nwrote ${OUT} (${rows.length} rows)`)
cdp.close()
