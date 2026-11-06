#!/usr/bin/env node
/** Dismiss the host setup overlay by its own "I'll choose a provider later" action, then verify. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
const before = await cdp.eval(`/Let's get you setup/.test(document.body.innerText || '')`)
const clicked = await cdp.eval(`(() => {
  const b = [...document.querySelectorAll('button, a')].find(x => /choose a provider later|set up later|later/i.test((x.innerText || '').trim()))
  if (!b) return 'missing:' + [...document.querySelectorAll('button')].map(x => (x.innerText || '').trim()).filter(Boolean).slice(0, 20).join('|')
  b.click(); return 'clicked:' + (b.innerText || '').trim()
})()`)
await cdp.wait(2500)
const after = await cdp.eval(`/Let's get you setup/.test(document.body.innerText || '')`)
console.log(JSON.stringify({ setupBefore: before, clicked, setupAfter: after, route: await cdp.eval(`!!document.querySelector('[data-cb-route]')`) }, null, 1))
cdp.close()
