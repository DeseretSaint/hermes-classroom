// Capture the fully-loaded fresh Plugins pane from its top, with the row count measured in the same call.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 900)
await cdp.wait(500)
await cdp.json(`(() => {
  const pane = [...document.querySelectorAll('*')].find(e => /Auto-update/.test(e.textContent||'') && e.children.length>0)
  window.scrollTo(0,0)
  document.querySelectorAll('*').forEach(e => { if (e.scrollTop > 0) e.scrollTop = 0 })
  return true
})()`)
await cdp.wait(800)
const n = await cdp.json(`(() => ({
  switches: document.querySelectorAll('[role="switch"], input[type=checkbox]').length,
  coursebookRow: [...document.querySelectorAll('[role="switch"], input[type=checkbox]')].some(sw => { let p=sw; for(let i=0;i<7&&p;i++){ if(/coursebook/i.test(p.innerText||'')) return true; p=p.parentElement } return false }),
  decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2')
}))()`)
console.log(JSON.stringify(n))
await cdp.shot(`${out}/00-fresh-capabilities-plugins.png`)
cdp.close()
