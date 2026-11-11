import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({coursebook:true}))`)
// product affordance: command palette -> Reload desktop plugins
await cdp.key('k', { modifiers: 2 })
await cdp.wait(1200)
await cdp.type('Reload desktop plugins')
await cdp.wait(900)
const box = await cdp.json(`(() => { const els=[...document.querySelectorAll('[role="option"], [cmdk-item], li, button')].filter(e=>/Reload desktop plugins/i.test(e.innerText||'')); const el=els[els.length-1]; if(!el) return null; const r=el.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,label:el.innerText.slice(0,60)} })()`)
console.log('palette item', JSON.stringify(box))
if (box) await cdp.click(box.x, box.y)
await cdp.wait(4000)
const v = await cdp.eval(`JSON.stringify({
  hash: location.hash,
  hasRoute: !!document.querySelector('[data-cb-route]'),
  coursebookSwitch: [...document.querySelectorAll('[role="switch"], input[type=checkbox]')].some(e => {
    let p=e; for(let i=0;i<4&&p;i++) p=p.parentElement; return /coursebook/i.test((p&&p.innerText)||'')
  }),
  records: window.__cbRecords ?? null
})`)
console.log(v)
cdp.close()
