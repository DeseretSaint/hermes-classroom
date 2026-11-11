// One DOM-adaptive driver: Coursebook home -> goal -> Short course -> Review -> Create course.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g-r2'
const goal = 'Set up a small backyard telescope and find and observe the moons of Jupiter on a clear night'
const cdp = await connect()
await cdp.setViewport(1344, 768)

const clickLabel = async (label, { exact = true } = {}) => {
  const box = await cdp.json(`(() => {
    const want = ${JSON.stringify(label)}
    const els = [...document.querySelectorAll('button, a, [role="button"], [role="option"], [role="radio"], [data-cb-action], [data-cb-home-primary], [data-cb-scope], [data-cb-scope-option]')]
    const el = els.find(e => { const t = (e.innerText || '').trim(); return ${exact ? 't === want' : 't.includes(want)'} })
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const r = el.getBoundingClientRect()
    return { x: r.x + r.width/2, y: r.y + r.height/2, t: (el.innerText||'').trim().slice(0,60) }
  })()`)
  if (!box) throw new Error(`no control labelled ${JSON.stringify(label)}`)
  await cdp.click(box.x, box.y)
  return box
}

// 1. Coursebook home
if (!(await cdp.eval(`!!document.querySelector('[data-cb-route]')`))) {
  const nav = await cdp.json(`(() => { const e=[...document.querySelectorAll('button,a,[role="tab"]')].filter(x=>(x.innerText||'').trim()==='Coursebook').pop(); if(!e) return null; const r=e.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
  if (nav) { await cdp.click(nav.x, nav.y); await cdp.wait(2500) }
}
await cdp.shot(`${out}/00-home-cold.png`)
console.log('home', await cdp.eval(`document.querySelector('[data-cb-route]').innerText.slice(0,200)`))

// 2. Start a new course
console.log('start', JSON.stringify(await clickLabel('Start a new course')))
await cdp.wait(2000)
await cdp.shot(`${out}/01-create-step1.png`)
console.log('step1', JSON.stringify(await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { text:r?r.innerText.slice(0,900):'', textareas:[...document.querySelectorAll('textarea')].map(t=>t.placeholder) } })()`)))

// 3. Type the goal
const ta = await cdp.json(`(() => { const t=document.querySelector('textarea'); if(!t) return null; t.focus(); const r=t.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (!ta) throw new Error('no textarea for goal')
await cdp.click(ta.x, ta.y)
await cdp.type(goal)
await cdp.wait(600)
console.log('typed goal; continue', JSON.stringify(await clickLabel('Continue')))
await cdp.wait(1800)

// 4. Step 2: Short course
await cdp.shot(`${out}/02-create-step2.png`)
const step2 = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { text:r?r.innerText.slice(0,1400):'', scope:[...document.querySelectorAll('[data-cb-scope-option],[data-cb-scope]')].map(e=>({v:e.getAttribute('data-cb-scope-option')||e.getAttribute('data-cb-scope'),sel:e.getAttribute('data-cb-scope-selected')})), mode:[...document.querySelectorAll('[data-cb-create-mode]')].map(e=>({m:e.getAttribute('data-cb-create-mode'),sel:e.getAttribute('data-cb-create-mode-selected')})) } })()`)
console.log('step2', JSON.stringify(step2))
const shortBox = await cdp.json(`(() => { const e=[...document.querySelectorAll('[data-cb-scope-option],[data-cb-scope]')].find(x=>/short/i.test(x.getAttribute('data-cb-scope-option')||x.getAttribute('data-cb-scope')||'') || /^Short course/i.test((x.innerText||'').trim())); if(!e) return null; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
if (!shortBox) throw new Error('no Short course option')
await cdp.click(shortBox.x, shortBox.y)
await cdp.wait(900)
console.log('short selected; continue', JSON.stringify(await clickLabel('Continue')))
await cdp.wait(2000)

// 5. Review
await cdp.shot(`${out}/03-create-review.png`)
const review = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { text:r?r.innerText.slice(0,1600):'', buttons:[...document.querySelectorAll('button')].map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,15) } })()`)
console.log('review', JSON.stringify(review))

// 6. Create course
console.log('create', JSON.stringify(await clickLabel('Create course')))
await cdp.wait(4000)
await cdp.shot(`${out}/04-after-create.png`)
console.log('after', JSON.stringify(await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { hash:location.hash, text:r?r.innerText.slice(0,1200):'' } })()`)))
cdp.close()
