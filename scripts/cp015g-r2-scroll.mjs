import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const plug = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>/^plugins$/i.test((e.innerText||'').trim())); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (plug) { await cdp.click(plug.x, plug.y); await cdp.wait(1800) }
// find the scrollable pane
const info = await cdp.eval(`JSON.stringify([...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+40 && /Plugins/.test(e.innerText||'')).map(e=>({t:e.tagName,c:String(e.className).slice(0,60),sh:e.scrollHeight,ch:e.clientHeight})).slice(0,8))`)
console.log('scrollables', info)
// scroll each candidate to bottom, rescan
await cdp.eval(`(() => { document.querySelectorAll('*').forEach(e => { if (e.scrollHeight > e.clientHeight + 40) e.scrollTop = e.scrollHeight }); return true })()`)
await cdp.wait(1500)
const v = await cdp.eval(`JSON.stringify({
  hits: [...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /coursebook/i.test(e.textContent||'')).map(e=>(e.textContent||'').trim().slice(0,80)),
  switches: document.querySelectorAll('[role="switch"], input[type=checkbox]').length,
  bodyLen: document.body.innerText.length
})`)
console.log(v)
cdp.close()
