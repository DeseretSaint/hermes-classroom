import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const b = await cdp.json(`(() => { const e=[...document.querySelectorAll('button')].find(x=>/^Reload$/.test((x.innerText||'').trim())); if(!e) return null; const r=e.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (b) { await cdp.click(b.x, b.y); await cdp.wait(8000) }
console.log(await cdp.eval(`JSON.stringify({ body: document.body.innerText.slice(0,300), route: !!document.querySelector('[data-cb-route]') })`))
cdp.close()
