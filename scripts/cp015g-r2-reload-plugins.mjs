// Use the app's own palette action "Reload desktop plugins" (product affordance, not a key hack).
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.key('k', { modifiers: 2 })
await cdp.wait(1200)
const open = await cdp.eval(`document.body.innerText.includes('Reload desktop plugins') ? 'already' : (document.querySelector('[role="dialog"], [cmdk-root], input[placeholder]') ? 'palette?' : 'no')`)
await cdp.type('Reload desktop plugins')
await cdp.wait(1000)
const found = await cdp.eval(`document.body.innerText.includes('Reload desktop plugins')`)
await cdp.key('Enter')
await cdp.wait(4000)
const v = await cdp.eval(`JSON.stringify({
  found: ${JSON.stringify(found)}, open: ${JSON.stringify(open)},
  switchCount: document.querySelectorAll('[role="switch"], input[type=checkbox]').length,
  coursebookRows: [...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /coursebook/i.test(e.textContent||'')).map(e=>(e.textContent||'').trim().slice(0,80))
})`)
console.log(v)
cdp.close()
