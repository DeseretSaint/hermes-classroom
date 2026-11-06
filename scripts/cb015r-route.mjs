#!/usr/bin/env node
/** CB-015 residual: print the mounted Coursebook route only (not the host sidebar). */
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return {
    hash: location.hash,
    destination: root?.getAttribute('data-cb-destination') || null,
    routeText: (root?.innerText || '').replace(/\\n{2,}/g, '\\n'),
    buttons: [...(root?.querySelectorAll('button') || [])].map(b => (b.innerText || '').trim()).filter(Boolean),
    rightSidebar: !!document.querySelector('[aria-label="Hide right sidebar"]'),
    leftSidebar: !!document.querySelector('[aria-label="Hide left sidebar"]')
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
