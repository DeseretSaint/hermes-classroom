import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
const p = b.contexts()[0].pages()[0]
const info = await p.evaluate(()=>({
  keys: Object.keys(window.hermesDesktop||{}),
  plugins: window.hermesDesktop && window.hermesDesktop.plugins ? Object.keys(window.hermesDesktop.plugins) : null,
  version: window.hermesDesktop && window.hermesDesktop.app ? Object.keys(window.hermesDesktop.app) : null
}))
console.log(JSON.stringify(info,null,1).slice(0,1200))
await b.close()
