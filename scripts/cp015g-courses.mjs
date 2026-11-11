// CP-015g: open the plugin's Courses tab by geometry and capture the draft course row.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
// Return to the Coursebook route first.
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(2500)
const target = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const els = [...route.querySelectorAll('button, a, [role="tab"], [role="link"]')]
  const el = els.find((e) => (e.innerText || '').trim() === 'Courses')
  if (!el) return { found: false, labels: els.map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 20) }
  const r = el.getBoundingClientRect()
  return { found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, tag: el.tagName, role: el.getAttribute('role') }
})()`)
console.log('target', JSON.stringify(target))
if (target.found) await cdp.click(target.x, target.y)
await cdp.wait(2500)
const state = await cdp.json(`(() => ({
  hash: location.hash,
  text: (document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 1400)
}))()`)
await cdp.shot(`${out}/10-courses-draft.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
