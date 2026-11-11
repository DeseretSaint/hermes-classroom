// Rig shortcut (documented): surface the installed+enabled plugin via the decision key, reload.
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.wait(300)
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({coursebook:true}))`)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.eval(`location.reload()`)
await cdp.wait(6000)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(4000)
const st = await cdp.json(`(() => ({
  hash: location.hash,
  cbRoute: !!document.querySelector('[data-cb-route]'),
  text: document.querySelector('[data-cb-route]') ? document.querySelector('[data-cb-route]').innerText.slice(0,600) : document.body.innerText.slice(0,300),
  nav: [...document.querySelectorAll('button,a,[role="tab"]')].map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,20)
}))()`)
console.log(JSON.stringify(st, null, 1))
cdp.close()
