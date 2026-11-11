// Step 1-2: Coursebook home -> Start a new course -> goal -> Continue -> shape step.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const goal = 'Learn to greet people and introduce yourself in Japanese before a first trip to Japan'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(600)

const clickLabel = async (label, opts = {}) => {
  const box = await cdp.json(`(() => {
    const want = ${JSON.stringify(label)}
    const exact = ${opts.exact === false ? 'false' : 'true'}
    const els = [...document.querySelectorAll('button, a, [role="button"], [role="option"], [role="radio"], [data-cb-action], [data-cb-home-primary], [data-cb-scope-option]')]
    const el = els.find(e => { const t = (e.innerText || '').trim(); return exact ? t === want : t.includes(want) })
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width/2, y: r.y + r.height/2, t: (el.innerText||'').trim().slice(0,60) }
  })()`)
  if (!box) return null
  await cdp.click(box.x, box.y)
  return box
}
const routeText = () => cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,2000)`)

if (!(await cdp.eval(`!!document.querySelector('[data-cb-route]')`))) {
  await cdp.eval(`location.hash='#/coursebook'`); await cdp.wait(3000)
}
await cdp.shot(`${out}/01-home-cold.png`)
console.log('HOME:', JSON.stringify(await routeText()))

console.log('start:', JSON.stringify(await clickLabel('Start a new course')))
await cdp.wait(2500)
await cdp.shot(`${out}/02-create-goal.png`)
console.log('STEP1:', JSON.stringify(await routeText()))
console.log('textareas:', JSON.stringify(await cdp.json(`[...document.querySelectorAll('textarea')].map(t=>({ph:t.placeholder,label:t.getAttribute('aria-label')}))`)))

const ta = await cdp.json(`(() => { const t=document.querySelector('textarea'); if(!t) return null; t.focus(); const r=t.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (!ta) throw new Error('no goal textarea')
await cdp.click(ta.x, ta.y)
await cdp.type(goal)
await cdp.wait(600)
console.log('goal value:', JSON.stringify(await cdp.eval(`document.querySelector('textarea').value`)))
console.log('continue:', JSON.stringify(await clickLabel('Continue')))
await cdp.wait(2500)
await cdp.shot(`${out}/03-create-shape.png`)
console.log('STEP2:', JSON.stringify(await routeText()))
cdp.close()
