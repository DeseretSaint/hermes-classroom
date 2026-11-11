// CP-015g: one product-driven retry ("Try again") and watch the visible state for up to 8 minutes.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const box = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Try again')
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
console.log('retry target', JSON.stringify(box))
if (!box) throw new Error('no Try again control')
await cdp.click(box.x, box.y)
await cdp.wait(5000)
await cdp.shot(`${out}/08-retry-running.png`)
const deadline = Date.now() + 8 * 60 * 1000
let last = ''
while (Date.now() < deadline) {
  const state = await cdp.json(`(() => ({
    text: (document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 900),
    approve: [...document.querySelectorAll('[data-cb-plan-approve]')].map((el) => el.getAttribute('data-cb-plan-approve'))
  }))()`)
  if (state.text !== last) {
    console.log(`[${new Date().toISOString()}]`, JSON.stringify(state).slice(0, 700))
    last = state.text
  }
  if (state.approve.includes('approvable')) break
  if (/Planning stopped|Try again/.test(state.text)) break
  await cdp.wait(12000)
}
await cdp.shot(`${out}/09-retry-state.png`)
cdp.close()
