#!/usr/bin/env node
/** Find every control labelled like `label` and report geometry; optionally click by index. */
import { connect } from './cb015-lib.mjs'
const label = process.argv[2] || 'Plan'
const index = process.argv[3] === undefined ? null : Number(process.argv[3])
const cdp = await connect()
const found = await cdp.json(`(() => {
  const all = [...document.querySelectorAll('button, a, [role="tab"], [role="option"], [role="menuitem"]')]
  const wanted = ${JSON.stringify(label)}
  return all.map((el, i) => {
    const t = (el.innerText || '').trim()
    if (t !== wanted) return null
    const r = el.getBoundingClientRect()
    return { i, tag: el.tagName, role: el.getAttribute('role'), x: r.x, y: r.y, w: r.width, h: r.height,
             hidden: r.width === 0 || r.height === 0, text: t }
  }).filter(Boolean)
})()`)
console.log(JSON.stringify(found, null, 2))
if (index !== null) {
  const target = found[index]
  if (!target) throw new Error('no control at index')
  await cdp.click(target.x + target.w / 2, target.y + target.h / 2)
  await cdp.wait(1500)
  const text = await cdp.eval(`(document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 400)`)
  console.log('after click:', text.replace(/\n{2,}/g, '\n'))
}
cdp.close()
