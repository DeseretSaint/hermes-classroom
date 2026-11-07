// In-route lesson surface: Textbook → Open this section → read the check UI.
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const out = { steps: [] }
await cdp.eval(`location.hash = '#/coursebook'`); await cdp.wait(1800)
const clickText = async (text, sel = 'button, a, [role=tab]') => {
  const box = await cdp.json(`(() => { const el=[...document.querySelectorAll(${JSON.stringify(sel)})].find(b=>(b.innerText||'').trim()===${JSON.stringify(text)}); if(!el) return null; el.scrollIntoView({block:'center'}); const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,disabled:el.disabled} })()`)
  if (!box) return false
  await cdp.click(box.x, box.y); await cdp.wait(1200); return true
}
out.steps.push({ open: await clickText('Open') })
out.steps.push({ textbook: await clickText('Textbook') })
const textbookText = await cdp.eval(`(document.querySelector('[data-cb-route]')?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0,1400)`)
out.steps.push({ textbookText })
out.steps.push({ openSection: await clickText('Open this section') })
await cdp.wait(2200)
out.after = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { hash: location.hash, mounted: !!r, text: (r?r.innerText:'').replace(/\\n{2,}/g,'\\n').slice(0,2400), inputs: r?[...r.querySelectorAll('input,textarea,[role=textbox]')].map(i=>({tag:i.tagName,type:i.type||null,label:i.getAttribute('aria-label'),ph:i.placeholder})):[], buttons: r?[...r.querySelectorAll('button')].map(b=>(b.innerText||'').trim()).filter(Boolean):[] } })()`)
out.consoleErrors = console_
save('u05b-textbook.json', out)
console.log(JSON.stringify(out, null, 2))
cdp.close()
