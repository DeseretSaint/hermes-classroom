import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'}); await new Promise(r=>setTimeout(r,2200))
const info = await p.evaluate(()=>{
  const root=document.querySelector('[data-cb-v3]') || document.querySelector('[data-cb-route]')
  const h=root.querySelector('h1,h2')
  const cs=getComputedStyle(h)
  return {
    displayVar: getComputedStyle(root).getPropertyValue('--cb3-font-display'),
    uiVar: getComputedStyle(root).getPropertyValue('--cb3-font-ui'),
    fam: cs.fontFamily.slice(0,80),
    fonts: [...document.fonts].filter(f=>/CB /.test(f.family)).map(f=>`${f.family}|${f.status}`)
  }
})
console.log(JSON.stringify(info,null,1))
await b.close()
