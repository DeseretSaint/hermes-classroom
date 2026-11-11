// CP-015g: open the create flow and dump step 1 (goal) fields.
import { connect } from './cb015-lib.mjs'

const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(800)
await cdp.shot(`${out}/00-home-cold.png`)
await cdp.clickText('Start a new course')
await cdp.wait(1800)
const state = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const fields = [...document.querySelectorAll('input, textarea, select, [role="radio"], [role="option"], [role="combobox"]')].map((el) => ({
    tag: el.tagName,
    name: el.getAttribute('name'),
    type: el.getAttribute('type'),
    label: el.getAttribute('aria-label'),
    placeholder: el.getAttribute('placeholder'),
    value: el.value ?? null,
    role: el.getAttribute('role')
  }))
  return {
    hash: location.hash,
    step: (document.querySelector('[data-cb-create-step]') || { innerText: null }).innerText,
    heading: route ? (route.querySelector('h1, h2') || {}).innerText : null,
    text: route ? route.innerText.slice(0, 1800) : '',
    fields
  }
})()`)
await cdp.shot(`${out}/01-create-step1.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
