// CP-015g: choose Short course (data-cb-scope-option), continue to Review, capture, and press Create.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)

const box = await cdp.json(`(() => {
  const el = document.querySelector('[data-cb-scope-option="short"]')
  if (!el) return null
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
if (!box) throw new Error('no short scope option')
await cdp.click(box.x, box.y)
await cdp.wait(900)
const chosen = await cdp.json(`(() => ({
  selected: [...document.querySelectorAll('[data-cb-scope-option]')].map((el) => ({ s: el.getAttribute('data-cb-scope-option'), sel: el.getAttribute('data-cb-scope-selected') })),
  mode: [...document.querySelectorAll('[data-cb-create-mode]')].map((el) => ({ m: el.getAttribute('data-cb-create-mode'), sel: el.getAttribute('data-cb-create-mode-selected') }))
}))()`)
console.log('chosen', JSON.stringify(chosen))
await cdp.clickText('Continue')
await cdp.wait(1800)
const review = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return {
    text: route.innerText.slice(0, 2000),
    shape: (document.querySelector('[data-cb-create-shape]') || {}).getAttribute ? document.querySelector('[data-cb-create-shape]').getAttribute('data-cb-create-shape') : null,
    preview: (document.querySelector('[data-cb-create-preview]') || { innerText: null }).innerText
  }
})()`)
await cdp.shot(`${out}/03-create-review.png`)
console.log('review', JSON.stringify(review, null, 2))
cdp.close()
