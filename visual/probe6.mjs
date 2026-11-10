import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'}); await new Promise(r=>setTimeout(r,1800))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-route]')
  const h=[...root.querySelectorAll('h1,h2')].slice(0,3).map(x=>({tag:x.tagName,style:(x.getAttribute('style')||'').slice(0,160),cls:(x.className||'').toString().slice(0,80),fam:getComputedStyle(x).fontFamily.slice(0,60)}))
  return h
})
console.log(JSON.stringify(info,null,1))
await b.close()
