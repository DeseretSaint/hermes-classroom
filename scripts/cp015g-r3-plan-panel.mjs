// Open the plan review panel and read the verdict + any approve control.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(400)
const click = async (label) => {
  const b = await cdp.json(`(() => { const el=[...document.querySelectorAll('[data-cb-route] button,[data-cb-route] a')].find(e=>(e.innerText||'').trim()===${JSON.stringify(label)}); if(!el) return null; el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
  if (!b) return null
  await cdp.click(b.x, b.y); await cdp.wait(2500); return b
}
console.log('review click:', JSON.stringify(await click('Review the plan')))
let t = await cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,4000)`)
console.log('PLAN PANEL:', JSON.stringify(t))
console.log('buttons:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,30)`)))
await cdp.shot(`${out}/07-plan-verdict-panel.png`)
cdp.close()
