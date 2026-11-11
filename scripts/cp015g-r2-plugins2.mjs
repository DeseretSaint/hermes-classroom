// Precise query: is there a Coursebook row/switch/packagerow anywhere in the Plugins pane?
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.wait(500)
// ensure we're on the plugins tab
const plug = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>/^plugins$/i.test((e.innerText||'').trim())); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (plug) { await cdp.click(plug.x, plug.y); await cdp.wait(1500) }
const v = await cdp.json(`(() => {
  const hits = []
  const walk = (el) => {
    if (el.children.length === 0 && /coursebook/i.test(el.textContent || '')) {
      let p = el, chain = []
      for (let i=0;i<5 && p;i++){ chain.push(p.tagName + (p.getAttribute('data-testid')?('['+p.getAttribute('data-testid')+']'):'') + ':' + (p.textContent||'').trim().slice(0,60)); p = p.parentElement }
      hits.push(chain)
    }
    for (const c of el.children) walk(c)
  }
  walk(document.body)
  const pane = [...document.querySelectorAll('*')].find(e => /Discover Plugins/i.test(e.textContent||'') && e.children.length>0)
  const rowTexts = [...document.querySelectorAll('[role="switch"], input[type=checkbox]')].map(e => {
    let p = e; for (let i=0;i<4 && p;i++) p = p.parentElement
    return (p ? p.innerText : '').trim().split('\\n').slice(0,3)
  })
  return {
    hits: hits.slice(0, 10),
    switchCount: rowTexts.length,
    switchRows: rowTexts,
    packageRows: [...document.querySelectorAll('[data-package-key], [data-plugin-id]')].map(e=>({k:e.getAttribute('data-package-key')||e.getAttribute('data-plugin-id'), t:(e.innerText||'').trim().slice(0,60)}))
  }
})()`)
console.log(JSON.stringify(v,null,2))
cdp.close()
