// Read the plan-stage panel after the job ended; capture whatever verdict/failure is shown.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(500)
const st = await cdp.json(`(() => ({
  hash: location.hash,
  text: (document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,2500),
  buttons: [...document.querySelectorAll('button,[role="button"]')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,25)
}))()`)
console.log(JSON.stringify(st, null, 1))
await cdp.shot(`${out}/06-plan-stage.png`)
cdp.close()
