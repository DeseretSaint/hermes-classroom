// Put the plan refusal itself in frame, and prove no approve control exists.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 900)
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({coursebook:true}))`)
await cdp.eval(`location.reload()`)
await cdp.wait(6000)
await cdp.eval(`location.hash='#/coursebook'`)
await cdp.wait(4000)

const clickText = async (label, exact = true) => {
  const b = await cdp.json(`(() => {
    const want = ${JSON.stringify(label)}, exact = ${exact}
    const root = document.querySelector('[data-cb-route]') || document.body
    const els = [...root.querySelectorAll('button,a,[role="button"],[role="link"]')]
    let el = els.find(e => { const t=(e.innerText||'').trim(); return exact ? t === want : t.includes(want) })
    if (!el) el = els.find(e => (e.innerText||'').includes(want))
    if (!el) return null
    el.scrollIntoView({block:'center'})
    const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,t:(el.innerText||'').trim().slice(0,50)}
  })()`)
  if (!b) return null
  await cdp.click(b.x, b.y); await cdp.wait(2500); return b
}
console.log('plate:', JSON.stringify(await clickText('Learn to greet people', false)))
console.log('review:', JSON.stringify(await clickText('Review the plan')))
console.log('plan:', JSON.stringify(await clickText('Open the plan')))
console.log('plan2:', JSON.stringify(await clickText('Open the plan')))

// Scroll the refusal paragraph into view inside whatever scroll container holds it.
const scrolled = await cdp.json(`(() => {
  const nodes = [...document.querySelectorAll('*')].filter(e => e.children.length===0 && /could not show where its facts came from/i.test(e.textContent||''))
  const el = nodes[0]
  if (!el) return {found:false}
  el.scrollIntoView({block:'center'})
  const r = el.getBoundingClientRect()
  return {found:true, y:Math.round(r.y), text:(el.closest('section')||el.parentElement||el).innerText.slice(0,700)}
})()`)
console.log('refusal:', JSON.stringify(scrolled))
await cdp.wait(600)
const btns = await cdp.json(`[...document.querySelectorAll('[data-cb-route] button')].map(b=>(b.innerText||'').trim()).filter(Boolean)`)
console.log('buttons:', JSON.stringify(btns))
console.log('approve buttons:', JSON.stringify(btns.filter(b => /approve/i.test(b))))
console.log('route text tail:', JSON.stringify(await cdp.eval(`document.querySelector('[data-cb-route]').innerText.slice(-1600)`)))
await cdp.shot(`${out}/07-plan-verdict-panel.png`)
cdp.close()
