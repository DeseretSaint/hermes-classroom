import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.wait(300)
const v = await cdp.json(`(() => {
  const route = document.querySelector('[data-cb-route]')
  const attrs = new Set()
  ;[...document.querySelectorAll('*')].forEach(e => { for (const a of e.attributes) if (a.name.startsWith('data-cb-')) attrs.add(a.name) })
  return {
    hash: location.hash,
    text: route ? route.innerText.slice(0, 2500) : document.body.innerText.slice(0,800),
    buttons: [...document.querySelectorAll('button, a, [role="radio"], [role="option"]')].map(e => ({ t: (e.innerText||'').trim().slice(0,90), dis: e.disabled ?? null, role: e.getAttribute('role') })).filter(x=>x.t).slice(0, 30),
    dataAttrs: [...attrs].sort()
  }
})()`)
console.log(JSON.stringify(v, null, 2))
cdp.close()
