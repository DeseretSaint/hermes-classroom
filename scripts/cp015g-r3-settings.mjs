// Fresh-userdata check: does Capabilities -> Plugins inventory Coursebook?
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.wait(1500)

// Try the settings route by hash; the shell owns routing.
for (const h of ['#/settings', '#/capabilities', '#/settings/capabilities']) {
  await cdp.eval(`location.hash = ${JSON.stringify(h)}`)
  await cdp.wait(1200)
  const t = await cdp.eval(`document.body.innerText.slice(0,200)`)
  console.log(h, '=>', JSON.stringify(t.slice(0,120)))
}

const state = await cdp.json(`(() => ({
  hash: location.hash,
  bodyLen: document.body.innerText.length,
  head: document.body.innerText.slice(0, 500),
  tabs: [...document.querySelectorAll('[role="tab"],button,a')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,50),
  decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2')
}))()`)
console.log(JSON.stringify(state, null, 1))
await cdp.shot(`${out}/00-fresh-window.png`)
cdp.close()
