// CP-015g: open the plan review from the course home and record the gate state.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const box = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const el = [...route.querySelectorAll('button, a')].find((e) => /Open the plan|Review and approve the plan/i.test((e.innerText || '').trim()))
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2, label: el.innerText.trim() }
})()`)
console.log('target', JSON.stringify(box))
if (box) await cdp.click(box.x, box.y)
await cdp.wait(3500)
const state = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const approve = [...document.querySelectorAll('[data-cb-plan-approve]')].map((el) => ({
    v: el.getAttribute('data-cb-plan-approve'),
    disabled: Boolean(el.disabled),
    text: (el.innerText || '').trim()
  }))
  return { hash: location.hash, approve, text: (route || document.body).innerText.slice(0, 3000) }
})()`)
await cdp.shot(`${out}/12-plan-review.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
