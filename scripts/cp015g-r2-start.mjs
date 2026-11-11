import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g-r2'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.clickText('Start a new course')
await cdp.wait(2000)
const v = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const attrs = new Set(); [...document.querySelectorAll('*')].forEach(e=>{for(const a of e.attributes) if(a.name.startsWith('data-cb-')) attrs.add(a.name)})
  return { hash: location.hash, text: route ? route.innerText.slice(0,1800) : '', attrs: [...attrs].sort(),
    buttons: [...document.querySelectorAll('button,[role="radio"],[role="option"]')].map(e=>({t:(e.innerText||'').trim().slice(0,70)})).filter(x=>x.t) }
})()`)
await cdp.shot(`${out}/01-create-step1.png`)
console.log(JSON.stringify(v,null,2))
cdp.close()
