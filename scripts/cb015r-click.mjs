#!/usr/bin/env node
/** Click one labelled control and dump the studio route after it. */
import { connect } from './cb015-lib.mjs'
const label = process.argv[2] || 'Plan'
const cdp = await connect()
await cdp.clickText(label)
await cdp.wait(Number(process.env.CB015_WAIT || 2500))
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return {
    text: (root.innerText || '').replace(/\\n{2,}/g, '\\n').slice(0, 1200),
    buttons: [...root.querySelectorAll('button')].map(b => (b.innerText || '').trim()).filter(Boolean),
    tabs: [...root.querySelectorAll('[role="tab"]')].map(t => ({ label: (t.innerText||'').trim(), selected: t.getAttribute('aria-selected') }))
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
