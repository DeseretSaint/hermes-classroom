// Open the Coursebook route from the sidebar and dump its first screen.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g-r2'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(600)
const nav = await cdp.json(`(() => {
  const els = [...document.querySelectorAll('button, a, [role="tab"], [role="button"]')].filter(e => (e.innerText||'').trim() === 'Coursebook')
  const el = els[els.length-1]; if (!el) return null
  const r = el.getBoundingClientRect(); return { x:r.x+r.width/2, y:r.y+r.height/2 }
})()`)
console.log('nav', JSON.stringify(nav))
if (nav) await cdp.click(nav.x, nav.y)
await cdp.wait(2500)
const state = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  return { hash: location.hash, route: route ? route.getAttribute('data-cb-route') : null,
    text: route ? route.innerText.slice(0,1200) : document.body.innerText.slice(0,600),
    buttons: [...document.querySelectorAll('button, a')].map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,25) }
})()`)
await cdp.shot(`${out}/00-home-cold.png`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
