// H-121 layout + capture probe for the export surface on the isolated Desktop window.
//   CB015_CDP_PORT=9361 node audit/h121/probe-export-layout.mjs
import { connect } from '../../scripts/cb015-lib.mjs'

const cdp = await connect()

async function openApprovedExport() {
  await cdp.eval(`(() => { const b = document.querySelector('[data-cb-course-back]'); if (b) b.click(); return true })()`)
  await cdp.wait(900)
  const opened = await cdp.eval(`(() => {
    const rows = [...document.querySelectorAll('*')].filter((e) => e.children.length < 4 && (e.innerText || '').trim() === 'Braising at home, H-121')
    if (!rows.length) return false
    let n = rows[0]
    for (let i = 0; i < 8 && n; i += 1) {
      const b = [...n.querySelectorAll('button')].find((x) => /Open/i.test(x.innerText))
      if (b) { b.click(); return true }
      n = n.parentElement
    }
    return false
  })()`)
  if (!opened) throw new Error('could not open the approved course')
  await cdp.wait(1200)
  const clicked = await cdp.eval(`(() => {
    const el = [...document.querySelectorAll('button,[role=option],[role=tab]')].find((e) => (e.innerText || '').trim() === 'Export')
    if (!el) return false
    el.click(); return true
  })()`)
  if (!clicked) throw new Error('could not open the export view')
  await cdp.waitFor(`Boolean(document.querySelector('[data-cb-export-hash]'))`, { label: 'export review' })
}

const measure = `(() => {
  const root = document.querySelector('[data-cb-route]')
  const detail = document.querySelector('[data-cb-course-detail]')
  const inner = window.innerWidth
  const overflowX = document.documentElement.scrollWidth - document.documentElement.clientWidth
  const clipped = [...document.querySelectorAll('[data-cb-course-detail] *')].filter((el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && (r.right > document.documentElement.clientWidth + 1 || r.left < -1)
  }).map((el) => (el.tagName + ' ' + (el.innerText || '').trim().slice(0, 40))).slice(0, 8)
  return {
    innerWidth: inner,
    rootFont: getComputedStyle(document.documentElement).fontSize,
    overflowX,
    routeWidth: root ? Math.round(root.getBoundingClientRect().width) : null,
    detailWidth: detail ? Math.round(detail.getBoundingClientRect().width) : null,
    hash: (document.querySelector('[data-cb-export-hash]') || {}).getAttribute && document.querySelector('[data-cb-export-hash]').getAttribute('data-cb-export-hash'),
    stays: Boolean(document.querySelector('[data-cb-export-stays]')),
    leaves: Boolean(document.querySelector('[data-cb-export-leaves]')),
    clipped
  }
})()`

async function calibrated(target) {
  await cdp.clearViewport()
  await cdp.wait(300)
  let guess = target
  for (let i = 0; i < 6; i += 1) {
    await cdp.setViewport(guess, 900)
    await cdp.wait(350)
    const inner = await cdp.eval('window.innerWidth')
    if (Math.abs(inner - target) <= 2) break
    guess = Math.round((guess * target) / inner)
  }
  await cdp.wait(300)
  return guess
}

await openApprovedExport()
const frames = []
for (const width of [1049, 460]) {
  await calibrated(width)
  const plain = await cdp.json(measure)
  frames.push({ label: `export-${width}`, ...plain })
  await cdp.shot(`audit/h121/shots/export-${width}.png`)
  // 200% text: the document root size, the way the earlier cards set it.
  await cdp.eval(`document.documentElement.style.setProperty('font-size', '32px', 'important')`)
  await cdp.wait(400)
  const scaled = await cdp.json(measure)
  frames.push({ label: `export-${width}-200pct`, ...scaled })
  await cdp.shot(`audit/h121/shots/export-${width}-200pct.png`)
  await cdp.eval(`document.documentElement.style.removeProperty('font-size')`)
  await cdp.wait(250)
}
await cdp.clearViewport()

console.log(JSON.stringify({ frames }, null, 2))
cdp.close()
