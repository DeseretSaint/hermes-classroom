#!/usr/bin/env node
/**
 * CB-015 performance proof — a real imported pack with 55 objectives, 55 long bilingual sections
 * and 9 sources. Measures route mount, tab render, last-section mount, long tasks, DOM size and
 * overflow at 200% text / 460px. No synthetic rows: the pack went through grant -> preview ->
 * import on the live backend.
 */
import { connect } from './cb015-lib.mjs'
import { writeFileSync } from 'node:fs'

const cdp = await connect()
const rows = []
const shotPaths = []
const now = () => Date.now()

const measure = async (id, label, fn) => {
  const started = now()
  const detail = await fn()
  const wall = now() - started
  const entry = { id, label, wallMs: wall, ...detail }
  rows.push(entry)
  console.log(JSON.stringify({ id, wallMs: wall, ...detail }))
  return entry
}
const shoot = async (name) => {
  const path = await cdp.shot(`docs/cb015-shots/${name}.png`)
  shotPaths.push(path)
  return path
}
const installLongTasks = () =>
  cdp.eval(`(() => {
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
  return { longTasks: tasks, longTaskMaxMs: tasks.length ? Math.max(...tasks) : 0, longTaskTotalMs: tasks.reduce((a, b) => a + b, 0) }
}

// ---- 0. cold route mount
await cdp.eval(`location.hash = '#/coursebook'`)
const mountStart = now()
await cdp.send('Page.reload', { ignoreCache: false })
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 30000, label: 'route after reload' })
await cdp.wait(1500)
rows.push({ id: 'cold-mount', label: 'cold #/coursebook mount after reload', wallMs: now() - mountStart })
await shoot('30-perf-courses-dark')

// ---- 1. filter to the 55-objective course and open it
await measure('course-list', 'filter the list to the long course', async () => {
  await cdp.eval(`(() => {
    const el = [...document.querySelectorAll('[data-cb-route] input')].find(i => i.placeholder === 'Search courses')
    if (!el) return 'missing'
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, 'fifty-five')
    el.dispatchEvent(new Event('input', { bubbles: true }))
    return 'set'
  })()`)
  await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].some(b => (b.innerText||'').trim() === 'Open')`, { label: 'filtered row' })
  await cdp.waitFor(`/fifty-five/.test(document.querySelector('[data-cb-route]')?.innerText || '')`, { label: 'filtered copy' })
  await cdp.wait(800)
  return { rows: await cdp.eval(`[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open').length`) }
})

await installLongTasks()
const detail = await measure('course-detail', 'open the 55-objective course detail', async () => {
  let attempts = 0
  let opened = false
  const t0 = Date.now()
  while (attempts < 4 && !opened) {
    attempts += 1
    await cdp.eval(`(() => {
      const b = [...document.querySelectorAll('[data-cb-route] button')].find(x => (x.innerText||'').trim() === 'Open')
      if (b) b.click()
      return !!b
    })()`)
    try {
      await cdp.waitFor(`/CURRENT OBJECTIVE/.test(document.querySelector('[data-cb-route]')?.innerText || '')`, { timeout: 5000, label: 'detail' })
      opened = true
    } catch {
      await cdp.wait(500)
    }
  }
  if (!opened) throw new Error('detail never opened after ' + attempts + ' clicks')
  const stats = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return { nodes: root.querySelectorAll('*').length, text: root.innerText.length }
  })()`)
  return { ...stats, renderMs: Date.now() - t0, attempts }
})
rows.push({ id: 'course-detail-longtasks', ...(await readLongTasks()) })
await shoot('31-perf-course-detail-dark')

// ---- 2. Textbook tab with 55 sections
await installLongTasks()
const textbook = await measure('textbook-55', 'render 55-row textbook index', async () => {
  const t0 = Date.now()
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()==='Textbook'); if(b) b.click(); })()`)
  await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open section').length >= 55`, { timeout: 15000, label: '55 rows' })
  const renderMs = Date.now() - t0
  return await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return {
      renderMs: ${renderMs},
      sectionRows: [...root.querySelectorAll('button')].filter(b => (b.innerText||'').trim() === 'Open section').length,
      nodes: root.querySelectorAll('*').length,
      scrollHeight: root.scrollHeight,
      clientHeight: root.clientHeight
    }
  })()`)
})
rows.push({ id: 'textbook-longtasks', ...(await readLongTasks()) })
await shoot('32-perf-textbook-55-dark')

// ---- 3. scroll the index to the end and measure frames + long tasks
await cdp.eval(`(() => { const r = document.querySelector('[data-cb-route]'); r.scrollTop = 0; return true })()`)
await installLongTasks()
const scroll = await measure('textbook-scroll', 'scroll the 55-row index to the end', async () => {
  const target = await cdp.eval(`(() => {
    const all = [document.documentElement, ...document.querySelectorAll('*')]
    const el = all.filter(e => e.scrollHeight > e.clientHeight + 8 && e.clientHeight > 200).sort((a, b) => b.scrollHeight - a.scrollHeight)[0]
    if (!el) return null
    el.dataset.cbPerfScroll = '1'
    return { tag: el.tagName, cls: (el.className || '').toString().slice(0, 80), scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }
  })()`)
  if (!target) return { scroller: null, note: 'no scrollable container; index fits the pane' }
  const frames = await cdp.eval(`(() => new Promise((resolve) => {
    const el = document.querySelector('[data-cb-perf-scroll]') || document.querySelector('[data-cb-route] [data-cb-perf-scroll]')
    const node = el || [...document.querySelectorAll('[data-cb-route] *')].find(e => e.scrollHeight > e.clientHeight + 8)
    if (!node) return resolve({ frames: [], note: 'no scroller found' })
    const deltas = []
    let last = performance.now()
    const started = last
    const step = () => {
      const t = performance.now()
      deltas.push(Math.round(t - last))
      last = t
      node.scrollTop = Math.min(node.scrollHeight, node.scrollTop + 240)
      if (node.scrollTop + node.clientHeight < node.scrollHeight && performance.now() - started < 2500) requestAnimationFrame(step)
      else resolve({ frames: deltas.length, worstFrameMs: Math.max(...deltas), over32ms: deltas.filter(d => d > 32).length, finalScrollTop: node.scrollTop })
    }
    requestAnimationFrame(step)
  }))()`)
  return { scroller: target, ...frames }
})
rows.push({ id: 'textbook-scroll-longtasks', ...(await readLongTasks()) })
await shoot('33-perf-textbook-bottom-dark')

// ---- 3b. the Plan view lists every objective too; measure its 55-row render
await installLongTasks()
const plan = await measure('plan-55', 'render the 55-objective plan view', async () => {
  const t0 = Date.now()
  await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()==='Plan'); if(b) b.click(); })()`)
  await cdp.waitFor(`[...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Challenge out').length >= 55`, { timeout: 15000, label: 'plan rows' })
  const renderMs = Date.now() - t0
  return await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return {
      renderMs: ${renderMs},
      rows: [...root.querySelectorAll('button')].filter(b => (b.innerText||'').trim() === 'Challenge out').length,
      nodes: root.querySelectorAll('*').length,
      text: root.innerText.length
    }
  })()`)
})
rows.push({ id: 'plan-longtasks', ...(await readLongTasks()) })
await shoot('37-perf-plan-55-dark')
await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button[aria-pressed]')].find(x=>(x.innerText||'').trim()==='Textbook'); if(b) b.click(); })()`)
await cdp.wait(900)

// ---- 4. open the last (55th) section: longest text path
await installLongTasks()
const lastSection = await measure('last-section', 'open the 55th section and render its lesson', async () => {
  const t0 = Date.now()
  const clicked = await cdp.eval(`(() => {
    const bs = [...document.querySelectorAll('[data-cb-route] button')].filter(b => (b.innerText||'').trim() === 'Open section')
    const b = bs[bs.length - 1]
    if (!b) return 'missing'
    b.click(); return 'clicked(' + bs.length + ')'
  })()`)
  await cdp.waitFor(`/CURRENT CHECK/.test(document.querySelector('[data-cb-route]')?.innerText || '')`, { timeout: 20000, label: 'last section' })
  const renderMs = Date.now() - t0
  const stats = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]')
    return {
      renderMs: ${renderMs},
      clicked: ${JSON.stringify(clicked)},
      nodes: root.querySelectorAll('*').length,
      text: root.innerText.length,
      scrollHeight: root.scrollHeight,
      hasJapanese: /[\\u3040-\\u30ff]/.test(root.innerText),
      heading: (root.innerText.match(/Objective 55[^\\n]{0,120}/) || [''])[0]
    }
  })()`)
  return stats
})
rows.push({ id: 'last-section-longtasks', ...(await readLongTasks()) })
await shoot('34-perf-last-section-dark')

// ---- 5. 200% text and 460px on the long section page
await cdp.eval(`document.documentElement.style.fontSize = '32px'`)
await cdp.wait(700)
await measure('text200', 'long section at 200% text', async () =>
  cdp.json(`(() => {
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
)
await shoot('35-perf-text200-dark')
await cdp.eval(`document.documentElement.style.fontSize = ''`)

await cdp.setViewport(460, 900)
await cdp.wait(800)
await measure('narrow460', 'long section at 460px', async () =>
  cdp.json(`(() => ({
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    headingVisible: /Objective 55/.test(document.querySelector('[data-cb-route]')?.innerText || '')
  }))()`)
)
await shoot('36-perf-narrow-dark')
await cdp.clearViewport()

const summary = {
  measuredAt: new Date().toISOString(),
  pack: {
    pack_id: 'cb015-perf-long-l0',
    course_id: 'crs_e83157235ab14c7e9c1ef731c37ab1af',
    enrollment_id: 'enr_007dd38142904b4694af3b9ae5d61039',
    objectives: 55,
    files: 55,
    sources: 9,
    content_hash: 'sha256:2b0523c174e891606dae1003fcfa1c44629806ddf71a450056fd61b15740c6af'
  },
  rows,
  shots: shotPaths
}
writeFileSync('docs/REVIEW_CB015-perf.json', `${JSON.stringify(summary, null, 2)}\n`)
console.log('wrote docs/REVIEW_CB015-perf.json')
cdp.close()
