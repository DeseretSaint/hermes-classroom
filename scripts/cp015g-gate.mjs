// CP-015g: open the draft plan from Courses and record whether the product's gate allows approval.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const box = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const el = [...route.querySelectorAll('button, a')].find((e) => (e.innerText || '').trim() === 'Open')
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
console.log('open target', JSON.stringify(box))
if (box) await cdp.click(box.x, box.y)
await cdp.wait(3500)
const state = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return {
    hash: location.hash,
    approve: [...document.querySelectorAll('[data-cb-plan-approve]')].map((el) => ({ v: el.getAttribute('data-cb-plan-approve'), disabled: el.disabled })),
    text: (route || document.body).innerText.slice(0, 2500)
  }
})()`)
await cdp.shot(`${out}/11-plan-gate.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
