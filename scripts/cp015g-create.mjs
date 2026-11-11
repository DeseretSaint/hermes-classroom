// CP-015g: press Create course once, then poll the visible progress for up to ~9 minutes.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const box = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Create course')
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (!box) throw new Error('no Create course button')
await cdp.click(box.x, box.y)
await cdp.wait(4000)
const first = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return { hash: location.hash, text: route ? route.innerText.slice(0, 1200) : '' }
})()`)
await cdp.shot(`${out}/04-after-create.png`)
console.log('after create', JSON.stringify(first, null, 2))

const deadline = Date.now() + 9 * 60 * 1000
let last = ''
while (Date.now() < deadline) {
  await cdp.wait(15000)
  const state = await cdp.json(`(() => {
    const route = document.querySelector('[data-cb-route]')
    return {
      hash: location.hash,
      text: route ? route.innerText.slice(0, 1200) : '',
      approve: [...document.querySelectorAll('[data-cb-plan-approve]')].map((el) => el.getAttribute('data-cb-plan-approve'))
    }
  })()`)
  if (state.text !== last) {
    console.log(`[${new Date().toISOString()}]`, JSON.stringify(state).slice(0, 900))
    last = state.text
  }
  if (state.approve.length && state.approve[0] === 'approvable') break
  if (/failed|could not|error/i.test(state.text) && !/no error/i.test(state.text)) {
    console.log('possible failure text; continuing to watch', JSON.stringify(state).slice(0, 900))
  }
}
await cdp.shot(`${out}/05-plan-state.png`)
console.log('final', JSON.stringify(await cdp.json(`(() => ({ hash: location.hash, text: (document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 2000) }))()`), null, 2))
cdp.close()
