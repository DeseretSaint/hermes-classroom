import { chromium } from 'playwright'
import { execSync } from 'node:child_process'
const before = JSON.parse(execSync('hyprctl clients -j',{encoding:'utf8'})).map(c=>c.address)
const b = await chromium.connectOverCDP('http://127.0.0.1:9371')
const p = b.contexts()[0].pages()[0]
const r = await p.evaluate(async ()=> await window.hermesDesktop.openWindow())
console.log('openWindow ->', JSON.stringify(r))
await new Promise(r=>setTimeout(r,2500))
const after = JSON.parse(execSync('hyprctl clients -j',{encoding:'utf8'})).filter(c=>!before.includes(c.address))
console.log('new windows:', after.map(c=>({addr:c.address, at:c.at, size:c.size, cls:c.class, title:c.title})))
console.log('pages:', b.contexts()[0].pages().map(x=>x.url().slice(0,60)))
await b.close()
