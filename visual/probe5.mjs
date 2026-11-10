import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'})
await new Promise(r=>setTimeout(r,2000))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-route]')
  const h=[...root.querySelectorAll('h1,h2,h3,[class*=display]')][0]
  const faces=[]
  for (const ss of document.styleSheets) { try { for (const r of ss.cssRules) if (r.constructor.name==='CSSFontFaceRule') faces.push(r.cssText.slice(0,160)) } catch {} }
  return {
    fonts:[...document.fonts].map(f=>({fam:f.family,status:f.status,weight:f.weight})).filter(f=>/CB|Fraunces|Source/i.test(f.fam)),
    faces:faces.filter(f=>/CB|Fraunces|Source/i.test(f)).slice(0,6),
    h1: h ? {tag:h.tagName, text:(h.textContent||'').slice(0,40), family:getComputedStyle(h).fontFamily, size:getComputedStyle(h).fontSize} : null
  }
})
console.log(JSON.stringify(info,null,1).slice(0,2200))
await b.close()
