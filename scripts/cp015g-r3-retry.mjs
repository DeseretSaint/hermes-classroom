// The one allowed press of the product's own "Try again", then follow the plan stage to a verdict.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(400)
const routeText = () => cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,2500)`)

const box = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]') || document.body
  const el = [...root.querySelectorAll('button,[role="button"]')].find(e => (e.innerText||'').trim() === 'Try again')
  if (!el) return null
  el.scrollIntoView({block:'center'})
  const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}
})()`)
if (!box) { console.log('NO RETRY CONTROL:', JSON.stringify(await routeText())); cdp.close(); process.exit(2) }
console.log('retry press at', JSON.stringify(box))
await cdp.click(box.x, box.y)
await cdp.wait(4000)
console.log('after press:', JSON.stringify((await routeText()).slice(0,500)))

// Poll the visible panel until the stage stops saying it is working.
let last = ''
for (let i = 0; i < 40; i++) {
  await cdp.wait(12000)
  const t = await routeText()
  const busy = /being researched|being written|Working on it/i.test(t)
  console.log(`${new Date().toISOString().slice(11,19)} busy=${busy} :: ${JSON.stringify(t.slice(0,160))}`)
  if (t !== last) last = t
  if (!busy) break
}
const final = await routeText()
console.log('FINAL PANEL:', JSON.stringify(final))
console.log('buttons:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,20)`)))
await cdp.shot(`${out}/06-plan-verdict.png`)
cdp.close()
