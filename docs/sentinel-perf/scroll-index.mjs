/**
 * Scroll the 60-row textbook index with continuous small steps and record main-thread frames.
 *   CB015_CDP_PORT=9371 node docs/sentinel-perf/scroll-index.mjs
 */
import { connect } from '/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_19da8432/scripts/cb015-lib.mjs'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const cdp = await connect()
const rows = []
const routeText = `(document.querySelector('[data-cb-route]')?.innerText || '')`

const openCourse = async () => cdp.eval(`(() => {
  const leaf = [...document.querySelectorAll('[data-cb-route] *')].find(
    (e) => e.children.length === 0 && (e.textContent || '').toLowerCase().includes('sixty situations')
  )
  if (!leaf) return 'no-title'
  let node = leaf
  for (let d = 0; d < 8 && node; d += 1) {
    const opens = [...node.querySelectorAll('button')].filter((b) => (b.innerText || '').trim() === 'Open')
    if (opens.length === 1) { opens[0].click(); return 'clicked' }
    if (opens.length > 1) return 'ambiguous'
    node = node.parentElement
  }
  return 'no-card'
})()`)

await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(600)
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()==='Courses'); if(b) b.click(); return !!b })()`)
await cdp.wait(1200)
console.log('open course:', await openCourse())
await cdp.waitFor(`/CURRENT OBJECTIVE/.test(${routeText})`, { timeout: 20000, label: 'detail' })
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()==='Textbook'); if(b) b.click(); return !!b })()`)
await cdp.waitFor(
  `[...document.querySelectorAll('[data-cb-route] button')].filter((b) => (b.innerText || '').trim() === 'Open section').length >= 60`,
  { timeout: 20000, label: '60 rows' }
)
await cdp.wait(400)

await cdp.eval(`(() => {
  window.__cbLong = []
  try {
    window.__cbObserver = new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__cbLong.push(Math.round(e.duration)) })
    window.__cbObserver.observe({ entryTypes: ['longtask'] })
  } catch (e) { window.__cbErr = String(e) }
  return true
})()`)

const result = await cdp.eval(`(() => new Promise((resolve) => {
  const root = document.querySelector('[data-cb-route]')
  const scroller = [root, ...root.querySelectorAll('*')]
    .filter((e) => e.scrollHeight > e.clientHeight + 8 && e.clientHeight > 200)
    .sort((a, b) => b.scrollHeight - a.scrollHeight)[0]
  if (!scroller) return resolve({ note: 'no scroller' })
  const started = performance.now()
  const stamps = []
  const step = (t) => {
    stamps.push(t)
    scroller.scrollTop = Math.min(scroller.scrollHeight, scroller.scrollTop + 40)
    if (performance.now() - started < 3000 && scroller.scrollTop + scroller.clientHeight < scroller.scrollHeight) {
      requestAnimationFrame(step)
    } else {
      const deltas = []
      for (let i = 1; i < stamps.length; i += 1) deltas.push(stamps[i] - stamps[i - 1])
      deltas.sort((a, b) => a - b)
      resolve({
        scrollHeight: scroller.scrollHeight,
        clientHeight: scroller.clientHeight,
        frames: deltas.length,
        medianFrameMs: +deltas[Math.floor(deltas.length / 2)].toFixed(2),
        p95FrameMs: +deltas[Math.floor(deltas.length * 0.95)].toFixed(2),
        worstFrameMs: +deltas[deltas.length - 1].toFixed(2)
      })
    }
  }
  requestAnimationFrame(step)
}))()`)
const long = await cdp.json(`(() => window.__cbLong || [])()`)
const row = { id: 'scroll-textbook-index-60', label: '3s continuous 40px-step scroll of the 60-row index', ...result, longTasks: long }
rows.push(row)
console.log(JSON.stringify(row))
writeFileSync(resolve('docs/sentinel-perf/results/scroll-index.json'), `${JSON.stringify({ rows }, null, 2)}\n`)
cdp.close()
