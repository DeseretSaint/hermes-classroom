// Read the plan verdict after the job completed; force a refetch by leaving and re-entering the route.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.eval(`location.hash='#/courses'`); await cdp.wait(1500)
await cdp.eval(`location.hash='#/coursebook'`); await cdp.wait(4000)
const t = await cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,3000)`)
console.log('PANEL:', JSON.stringify(t))
console.log('buttons:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,25)`)))
console.log('approve-ish:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('[data-cb-route] *')].filter(e=>e.children.length===0 && /approve/i.test(e.textContent||'')).map(e=>(e.textContent||'').trim().slice(0,80)).slice(0,10)`)))
await cdp.shot(`${out}/06-plan-verdict.png`)
cdp.close()
