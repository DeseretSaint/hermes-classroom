import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'
import { clickLabel } from './lib.mjs'
const cdp = await connect()
await cdp.eval(`(location.hash = '#/capabilities', true)`)
await cdp.wait(1500)
let clicked = null
try { clicked = await clickLabel(cdp, 'Plugins', { selector: 'button, [role=tab], a' }) } catch (e) { clicked = { error: e.message } }
await cdp.wait(2500)
const out = await cdp.json(`(() => {
  const main = document.querySelector('main') || document.body
  return {
    hash: location.hash,
    clicked: ${JSON.stringify(clicked)},
    mainText: (main.innerText || '').slice(0, 3000),
    buttons: [...main.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim().slice(0,60), aria: b.getAttribute('aria-label'), disabled: b.disabled })).filter(b => b.label || b.aria).slice(0, 60)
  }
})()`)
writeJson(rel('audit/demo-gate-5b0f124/probe-plugins-tab.json'), out)
console.log(JSON.stringify(out, null, 2).slice(0, 5000))
cdp.close()
