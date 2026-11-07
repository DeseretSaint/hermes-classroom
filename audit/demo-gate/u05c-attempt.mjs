// Try to submit one wrong attempt on this build (in-route Textbook).
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const out = { steps: [] }
const clickText = async (text) => {
  const box = await cdp.json(`(() => { const el=[...document.querySelectorAll('[data-cb-route] button, [data-cb-route] a')].find(b=>(b.innerText||'').trim()===${JSON.stringify(text)}); if(!el) return null; el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,disabled:el.disabled} })()`)
  if (!box) return { found: false }
  await cdp.click(box.x, box.y); await cdp.wait(1500); return { found: true, ...box }
}
out.steps.push({ startFresh: await clickText('Start a fresh run') })
out.afterStart = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { hash: location.hash, mounted: !!r, text: (r?r.innerText:'').replace(/\\n{2,}/g,'\\n').slice(0,700), submitDisabled: (()=>{const b=r?[...r.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='Submit answer'):null; return b?b.disabled:null})() } })()`)
// Type a deliberately wrong answer and submit if enabled
const typed = await cdp.eval(`(() => { const t=document.querySelector('[data-cb-route] textarea'); if(!t) return false; t.focus(); return true })()`)
if (typed) { await cdp.type('This is my deliberately wrong answer for the gate test.'); await cdp.wait(400) }
out.steps.push({ typed })
out.steps.push({ submit: await clickText('Submit answer') })
await cdp.wait(3000)
out.afterSubmit = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { hash: location.hash, mounted: !!r, text: (r?r.innerText:'').replace(/\\n{2,}/g,'\\n').slice(0,1400) } })()`)
out.consoleErrors = console_
save('u05c-attempt.json', out)
console.log(JSON.stringify(out, null, 2))
cdp.close()
