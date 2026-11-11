import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9371')
const p = b.contexts()[0].pages()[0]
await p.evaluate(()=>{location.hash='#/coursebook'})
await new Promise(r=>setTimeout(r,1800))
const before = await p.evaluate(()=>{const r=document.querySelector('[data-cb-route]');return {w:r?.clientWidth,h:r?.clientHeight,scope:r?.getAttribute('data-cb-scope'),win:innerWidth}})
await p.setViewportSize({width:1344,height:768}).catch(e=>console.log('viewport err',e.message))
await new Promise(r=>setTimeout(r,800))
const after = await p.evaluate(()=>{const r=document.querySelector('[data-cb-route]');return {w:r?.clientWidth,h:r?.clientHeight,scope:r?.getAttribute('data-cb-scope'),win:innerWidth}})
console.log(JSON.stringify({before,after}))
await b.close()
