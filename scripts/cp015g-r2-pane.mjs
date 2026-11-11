import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const plug = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>/^plugins$/i.test((e.innerText||'').trim())); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (plug) { await cdp.click(plug.x, plug.y); await cdp.wait(2000) }
const v = await cdp.eval(`(() => {
  const all = [...document.querySelectorAll('div,section,main')]
  const pane = all.filter(e => /Update all/.test(e.innerText||'')).sort((a,b)=>a.innerText.length-b.innerText.length)[0]
  const before = document.querySelectorAll('*').length
  return JSON.stringify({ len: pane ? pane.innerText.length : -1, text: pane ? pane.innerText.slice(0, 4000) : '' })
})()`)
console.log(v)
cdp.close()
