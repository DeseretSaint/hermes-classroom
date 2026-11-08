import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
await cdp.clearViewport(); await cdp.wait(400)
await cdp.eval(`(() => { const b=document.querySelector('[data-cb-course-back]'); if(b) b.click(); return true })()`)
await cdp.wait(900)
await cdp.eval(`(() => {
  const rows=[...document.querySelectorAll('*')].filter(e=>e.children.length<4 && (e.innerText||'').trim()==='Unapproved draft, H-121')
  let n=rows[0]; for(let i=0;i<8&&n;i++){ const b=[...n.querySelectorAll('button')].find(x=>/Open/i.test(x.innerText)); if(b){b.click(); return true} n=n.parentElement }
  return false })()`)
await cdp.wait(1200)
await cdp.eval(`(() => { const el=[...document.querySelectorAll('button,[role=option],[role=tab]')].find(e=>(e.innerText||'').trim()==='Export'); if(el) el.click(); return true })()`)
await cdp.waitFor(`Boolean(document.querySelector('[data-cb-export-blocked]'))`, {label:'blocked export'})
await cdp.eval(`document.querySelector('[data-cb-export-blocked]').scrollIntoView({block:'center'})`)
await cdp.wait(300)
console.log(await cdp.shot('audit/h121/shots/export-blocked-repair.png'))
console.log(JSON.stringify(await cdp.json(`(() => { const b=document.querySelector('[data-cb-export-blocked]'); const r=document.querySelector('[data-cb-export-repair]'); return {blocked:b.getAttribute('data-cb-export-blocked'), repair:r&&r.getAttribute('data-cb-export-repair'), buttons:r?[...r.querySelectorAll('button')].map(x=>x.innerText):[]} })()`)))
cdp.close()
