import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
const info = await p.evaluate(()=>{
  const k=Object.keys(window.hermesDesktop||{})
  return {reload:k.filter(x=>/reload|plugin/i.test(x)), all:k.slice(60)}
})
console.log(JSON.stringify(info,null,1).slice(0,1500))
await b.close()
