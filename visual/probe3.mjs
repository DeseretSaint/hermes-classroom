import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'})
await new Promise(r=>setTimeout(r,2500))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-route]')
  if(!root) return {route:false, body:document.body.innerText.slice(0,120)}
  return {
    route:true,
    attrs:Object.fromEntries([...root.attributes].map(a=>[a.name,a.value])),
    nav:[...root.querySelectorAll('button, a, [role=tab], [role=link]')].slice(0,25).map(n=>({t:(n.textContent||'').trim().slice(0,22), role:n.getAttribute('role'), test:n.getAttribute('data-testid'), cls:(n.className||'').toString().slice(0,30)})).filter(x=>x.t),
    fonts:[...document.fonts].map(f=>`${f.family}|${f.status}`)
  }
})
console.log(JSON.stringify(info,null,1).slice(0,2600))
await b.close()
