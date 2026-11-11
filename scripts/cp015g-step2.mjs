// CP-015g: fill step 1 (goal) through the visible form and open step 2.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const goal = 'Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night'
await cdp.eval(`(() => {
  const ta = document.querySelector('textarea')
  ta.focus()
  return true
})()`)
await cdp.type(goal)
await cdp.wait(400)
await cdp.clickText('Continue')
await cdp.wait(1500)
const state = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return {
    step: (document.querySelector('[data-cb-create-step]') || { innerText: null }).innerText,
    text: route ? route.innerText.slice(0, 2200) : '',
    radios: [...document.querySelectorAll('[role="radio"], [role="option"], input[type="radio"]')].map((el) => ({
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 120),
      checked: el.getAttribute('aria-checked') || el.checked || null,
      value: el.getAttribute('value')
    })),
    markers: [...document.querySelectorAll('[data-cb-create-mode], [data-cb-create-mode-selected], [data-cb-create-shape]')].map((el) => ({
      t: el.getAttribute('data-cb-create-mode') || el.getAttribute('data-cb-create-shape'),
      sel: el.getAttribute('data-cb-create-mode-selected')
    }))
  }
})()`)
await cdp.shot(`${out}/02-create-step2.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
