// Recapture Capabilities -> Plugins at a fixed viewport with the plugin list scrolled into view.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.eval(`location.hash='#/capabilities'`)
await cdp.wait(2500)
const b = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>(e.innerText||'').trim()==='Plugins'); if(!el) return null; el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (b) { await cdp.click(b.x, b.y); await cdp.wait(1800) }
const inv = await cdp.json(`(() => {
  const rows = [...document.querySelectorAll('[role="switch"], input[type=checkbox]')].map(e => { let p=e; for(let i=0;i<5&&p;i++) p=p.parentElement; return (p?p.innerText:'').trim().split('\\n').slice(0,2).join(' | ') })
  const text = document.body.innerText
  return { switchCount: rows.length, rows, hasCoursebookRow: /coursebook/i.test(text), bodyLen: text.length, decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2') }
})()`)
console.log(JSON.stringify(inv, null, 1))
await cdp.shot(`${out}/00-fresh-capabilities-plugins.png`)
cdp.close()
