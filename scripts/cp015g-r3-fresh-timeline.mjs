// Timeline on a truly fresh Desktop userdata: does Coursebook appear in Capabilities -> Plugins, and when?
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 900)
const sample = async (t) => {
  const s = await cdp.json(`(() => {
    const switches = [...document.querySelectorAll('[role="switch"], input[type=checkbox]')]
    const rows = switches.map(sw => { let p=sw; for(let i=0;i<7&&p;i++){ if(/coursebook/i.test(p.innerText||'')) return 'COURSEBOOK'; p=p.parentElement } return null }).filter(Boolean)
    return {
      hash: location.hash,
      decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2'),
      switches: switches.length,
      coursebookInPane: rows.length > 0,
      bodyLen: document.body.innerText.length
    }
  })()`)
  console.log(t, JSON.stringify(s))
  return s
}
// screenshot before any interaction
await cdp.shot(`${out}/00-fresh-firstpaint.png`)
console.log('first paint:', JSON.stringify(await sample('t0')))
// go to capabilities, plugins tab once, then poll WITHOUT touching any switch
await cdp.eval(`location.hash='#/capabilities'`); await cdp.wait(2000)
const tab = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>(e.innerText||'').trim()==='Plugins'); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (tab) { await cdp.click(tab.x, tab.y) }
for (const t of [0, 5, 10, 20, 30, 45, 60]) {
  await cdp.wait(t === 0 ? 1500 : 5000)
  await sample(`t+${t}s`)
}
const final = await sample('final')
await cdp.shot(`${out}/00-fresh-capabilities-plugins.png`)
console.log('FINAL', JSON.stringify(final))
cdp.close()
