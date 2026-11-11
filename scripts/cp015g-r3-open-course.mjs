// Open the course and read the plan verdict panel.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(500)
// Click the course row/plate that carries the goal title.
const box = await cdp.json(`(() => {
  const els = [...document.querySelectorAll('[data-cb-route] button, [data-cb-route] a, [data-cb-course], [role="link"]')]
  const el = els.find(e => /Learn to greet people/i.test(e.innerText || ''))
  if (!el) return null
  el.scrollIntoView({block:'center'}); const r = el.getBoundingClientRect()
  return {x:r.x+r.width/2,y:r.y+r.height/2,t:(el.innerText||'').trim().slice(0,60)}
})()`)
if (!box) throw new Error('no course plate')
await cdp.click(box.x, box.y)
await cdp.wait(4000)
const t = await cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,3500)`)
console.log('COURSE:', JSON.stringify(t))
console.log('buttons:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,25)`)))
console.log('hash:', await cdp.eval(`location.hash`))
await cdp.shot(`${out}/06-plan-verdict.png`)
cdp.close()
