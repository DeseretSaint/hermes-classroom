#!/usr/bin/env node
import { connect } from './cb015-lib.mjs'
const cdp = await connect(); const e = (x) => cdp.eval(x)
await cdp.send('Runtime.enable', {})
console.log('state', await e("document.querySelector('[data-cb-takehome-pack]')?.getAttribute('data-cb-takehome-pack-state')"))
console.log('error', await e("document.querySelector('[data-cb-takehome-error]')?.innerText || document.querySelector('[data-cb-takehome-export-error]')?.innerText || null"))
console.log('exported', await e("document.querySelector('[data-cb-takehome-exported]')?.innerText || null"))
console.log('gate', (await e("document.querySelector('[data-cb-takehome-gate]')?.innerText || ''")).replace(/\s+/g,' ').slice(0,600))
cdp.close()
