import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'})
await new Promise(r=>setTimeout(r,2000))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-route]')
  const nav=[...root.querySelectorAll('button,a,[role=tab],[role=link]')].map(n=>({t:(n.textContent||'').trim().slice(0,24),attr:[...n.attributes].filter(a=>a.name.startsWith('data-')).map(a=>a.name).join(','),role:n.getAttribute('role')})).filter(x=>x.t).slice(0,22)
  return {nav, fonts:[...document.fonts].map(f=>`${f.family}|${f.status}`), ready:root.getAttribute('data-cb-destination')}
})
console.log(JSON.stringify(info,null,1))
await b.close()
