#!/usr/bin/env node
/** Watch what the shell does to the hash for a second after asking for #/coursebook. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.eval(`location.hash = '#/coursebook'`)
for (const delay of [0, 100, 300, 800, 1500, 3000]) {
  await cdp.wait(delay)
  const state = await cdp.json(`({ t: ${delay}, hash: location.hash, mounted: !!document.querySelector('[data-cb-route]') })`)
  console.log(state)
}
console.log('routes in DOM:', await cdp.json(`[...document.querySelectorAll('a[href*="coursebook"]')].map(a => a.getAttribute('href'))`))
cdp.close()
