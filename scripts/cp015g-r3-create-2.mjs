// Step 2-3: select Short course (Game already selected) -> Continue -> Review -> Create course.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_R3_OUT || 'docs/concept-parity/demo/cp015g-r3'
const cdp = await connect()
await cdp.setViewport(1344, 768)
const routeText = () => cdp.eval(`(document.querySelector('[data-cb-route]')||document.body).innerText.slice(0,2500)`)
const clickLabel = async (label, mode = 'exact') => {
  const box = await cdp.json(`(() => {
    const want = ${JSON.stringify(label)}; const mode = ${JSON.stringify(mode)}
    const els = [...document.querySelectorAll('button, a, [role="button"], [role="option"], [role="radio"], [data-cb-action], [data-cb-scope-option]')]
    const el = els.find(e => { const t=(e.innerText||'').trim(); return mode==='exact' ? t===want : t.startsWith(want) })
    if (!el) return null
    el.scrollIntoView({block:'center'})
    const r = el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,t:(el.innerText||'').trim().slice(0,40)}
  })()`)
  if (!box) return null
  await cdp.click(box.x, box.y); return box
}

// Pick Short course: click the Short course card (contains "Short course" + "Choose").
let picked = await cdp.json(`(() => {
  const cards = [...document.querySelectorAll('button,[role="button"],li,article,div')].filter(e => /^Short course/.test((e.innerText||'').trim()))
  const card = cards.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length)[0]
  if (!card) return null
  card.scrollIntoView({block:'center'})
  const r = card.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,t:(card.innerText||'').trim().slice(0,50)}
})()`)
if (!picked) throw new Error('no Short course card')
// The card's own Choose button may be the click target; click the card body instead.
await cdp.click(picked.x, picked.y)
await cdp.wait(1200)
console.log('short click:', JSON.stringify(picked))
console.log('STEP2-after:', JSON.stringify((await routeText()).slice(0,700)))

console.log('continue:', JSON.stringify(await clickLabel('Continue')))
await cdp.wait(2500)
await cdp.shot(`${out}/04-create-review.png`)
const review = await routeText()
console.log('REVIEW:', JSON.stringify(review))

const create = await clickLabel('Create course')
console.log('create:', JSON.stringify(create))
if (!create) throw new Error('no Create course control on review')
await cdp.wait(5000)
await cdp.shot(`${out}/05-after-create.png`)
console.log('AFTER:', JSON.stringify((await routeText()).slice(0,1200)))
console.log('hash:', await cdp.eval(`location.hash`))
cdp.close()
