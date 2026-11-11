// Fresh-userdata check: Capabilities -> Plugins inventory, Coursebook present?
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.wait(500)
await cdp.eval(`location.hash = '#/capabilities'`)
await cdp.wait(2500)

const clickTab = async (name) => {
  const b = await cdp.json(`(() => {
    const els = [...document.querySelectorAll('[role="tab"],button,a')]
    const el = els.find(e => (e.innerText||'').trim().toLowerCase() === ${JSON.stringify(name)}.toLowerCase())
    if (!el) return null
    el.scrollIntoView({block:'center'})
    const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}
  })()`)
  if (!b) return false
  await cdp.click(b.x, b.y); await cdp.wait(1800); return true
}

console.log('plugins tab clicked', await clickTab('Plugins'))
const inv = await cdp.json(`(() => {
  const rows = [...document.querySelectorAll('[role="switch"], input[type=checkbox]')].map(e => {
    let p = e; for (let i=0;i<5 && p;i++) p = p.parentElement
    return (p ? p.innerText : '').trim().split('\\n').slice(0,2).join(' | ')
  })
  const walk = (el, acc) => { if (el.children.length===0 && /coursebook/i.test(el.textContent||'')) acc.push((el.textContent||'').trim().slice(0,80)); for (const c of el.children) walk(c, acc); return acc }
  return {
    hash: location.hash,
    switchCount: rows.length,
    switchRows: rows,
    coursebookHits: walk(document.body, []).slice(0,5),
    bodyLen: document.body.innerText.length,
    decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2')
  }
})()`)
console.log(JSON.stringify(inv, null, 1))
await cdp.shot(`${out}/00-fresh-capabilities-plugins.png`)
cdp.close()
