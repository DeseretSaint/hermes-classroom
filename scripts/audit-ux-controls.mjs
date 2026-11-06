/** List host chrome controls (right-rail / pane toggles) by accessible name. */
import { attach } from './audit-ux-lib.mjs'

const cdp = await attach()
const controls = await cdp.json(`(() => {
  const out = []
  for (const el of document.querySelectorAll('button, [role="button"], [role="tab"], [aria-label]')) {
    const r = el.getBoundingClientRect()
    if (r.width < 4 || r.height < 4) continue
    const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60)
    if (!name) continue
    if (!/pane|panel|sidebar|rail|toggle|coursebook|context|open/i.test(name)) continue
    out.push({ name, tag: el.tagName, role: el.getAttribute('role'), x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) })
  }
  return out.slice(0, 40)
})()`)
console.log(JSON.stringify(controls, null, 2))
cdp.close()
