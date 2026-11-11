import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const logs = []
cdp.on((m) => {
  if (m.method === 'Runtime.consoleAPICalled') {
    const a = (m.params.args || []).map(x => x.value ?? x.description ?? x.type).join(' ')
    if (/plugin|coursebook|runtime/i.test(a)) logs.push(`[${m.params.type}] ${a.slice(0,400)}`)
  }
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXC ' + JSON.stringify(m.params.exceptionDetails?.text || '').slice(0,200))
})
await cdp.send('Runtime.enable')
await cdp.send('Page.enable')
await cdp.send('Page.reload', { ignoreCache: true })
await cdp.wait(9000)
// open plugins pane
for (let i=0;i<20;i++){ const ok = await cdp.eval(`!![...document.querySelectorAll('button')].find(b=>/^Capabilities$/.test((b.innerText||'').trim()))`); if (ok) break; await cdp.wait(500) }
const cap = await cdp.json(`(() => { const el=[...document.querySelectorAll('button')].find(b=>(b.innerText||'').trim()==='Capabilities'); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (cap) { await cdp.click(cap.x, cap.y); await cdp.wait(1200) }
const plug = await cdp.json(`(() => { const el=[...document.querySelectorAll('[role="tab"],button,a')].find(e=>/^plugins$/i.test((e.innerText||'').trim())); if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (plug) { await cdp.click(plug.x, plug.y); await cdp.wait(2500) }
const v = await cdp.eval(`JSON.stringify({
  switchCount: document.querySelectorAll('[role="switch"], input[type=checkbox]').length,
  coursebookRows: [...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /coursebook/i.test(e.textContent||'')).map(e=>(e.textContent||'').trim().slice(0,80)),
  bodyHasCoursebook: /coursebook/i.test(document.querySelector('[data-testid="plugins-pane"]')?.innerText || '')
})`)
console.log(v)
console.log('LOGS:', JSON.stringify(logs.slice(0,30), null, 1))
cdp.close()
