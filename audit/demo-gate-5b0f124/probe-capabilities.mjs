import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'
import { clickLabel } from './lib.mjs'
const cdp = await connect()
await cdp.eval(`(location.hash = '#/', true)`)
await cdp.wait(800)
let clicked = null
try { clicked = await clickLabel(cdp, 'Capabilities', { selector: 'button, a, [role=link]' }) } catch (e) { clicked = { error: e.message } }
await cdp.wait(2500)
const out = await cdp.json(`(() => ({
  hash: location.hash,
  bodyText: document.body.innerText.slice(0, 2500),
  tabs: [...document.querySelectorAll('button, [role=tab], a')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 60),
  headings: [...document.querySelectorAll('h1,h2,h3,[role=heading]')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 30)
}))()`)
writeJson(rel('audit/demo-gate-5b0f124/probe-capabilities.json'), { clicked, ...out })
console.log(JSON.stringify({ clicked, ...out }, null, 2).slice(0, 4000))
cdp.close()
