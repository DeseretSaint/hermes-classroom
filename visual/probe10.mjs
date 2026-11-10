import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/'}); await new Promise(r=>setTimeout(r,1200))
await p.evaluate(()=>{location.hash='#/coursebook'}); await new Promise(r=>setTimeout(r,2600))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-v3]')
  if(!root) return {route:false}
  const h=root.querySelector('h1,h2')
  return {route:true, fam:getComputedStyle(h).fontFamily.slice(0,60), fonts:[...document.fonts].filter(f=>/CB /.test(f.family)).map(f=>`${f.family}|${f.status}`), hStyle:(h.getAttribute('style')||'').slice(0,90)}
})
console.log(JSON.stringify(info,null,1))
await b.close()
