#!/usr/bin/env node
/** Reload the isolated window and report the rendered route. */
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.reload()
await cdp.wait(3000)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(1500)
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return {
    hash: location.hash,
    destination: root?.getAttribute('data-cb-destination') || null,
    routeText: (root?.innerText || '(none)').replace(/\\n{2,}/g, '\\n').slice(0, 1200)
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
