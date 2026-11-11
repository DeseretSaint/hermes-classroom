// Open the plan document surface and read any validator verdict + approve control.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(400)
const click = async (label) => {
  const b = await cdp.json(`(() => { const el=[...document.querySelectorAll('[data-cb-route] button,[data-cb-route] a')].find(e=>(e.innerText||'').trim()===${JSON.stringify(label)}); if(!el) return null; el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
  if (!b) return null
  await cdp.click(b.x, b.y); await cdp.wait(3000); return b
}
for (const label of ['Open the plan', 'Review and approve the plan']) {
  const r = await click(label)
  console.log(label, '->', JSON.stringify(r))
  const t = await cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,4500)`)
  console.log('TEXT:', JSON.stringify(t.slice(0, 3000)))
  console.log('buttons:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,30)`)))
  console.log('hash:', await cdp.eval(`location.hash`))
  await cdp.shot(`${out}/07-plan-verdict-panel.png`)
  if (/Approve/.test(t)) break
}
cdp.close()
