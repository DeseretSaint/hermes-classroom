// Reproduce: what does "Resume lesson" do to the route, step by step?
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const trace = []
const snap = async (label) => {
  const s = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { label: ${JSON.stringify(label)}, hash: location.hash, mounted: !!r, text: (r?r.innerText:'').replace(/\\n{2,}/g,'\\n').slice(0,180) } })()`)
  trace.push(s); return s
}
await cdp.eval(`location.hash = '#/coursebook'`); await cdp.wait(2000)
await snap('route')
// open course via Open
const box = await cdp.json(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Open'); if(!b) return null; const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (box) { await cdp.click(box.x, box.y) } else { trace.push({ label: 'no Open button' }) }
await cdp.wait(2200); await snap('after-open')
// click Resume lesson and poll hash/mount for 6s
const rl = await cdp.json(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Resume lesson'); if(!b) return null; const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (rl) {
  await cdp.click(rl.x, rl.y)
  for (let i = 0; i < 12; i += 1) { await cdp.wait(500); await snap(`t+${(i+1)*0.5}s`) }
} else trace.push({ label: 'no Resume lesson button' })
save('u05-resume-trace.json', { trace, consoleErrors: console_ })
console.log(JSON.stringify({ trace, consoleErrors: console_ }, null, 2))
cdp.close()
