#!/usr/bin/env node
/** Smoke test for the CB-015 harness: connect, read the route, toggle the real theme action. */
import { connect, setMode } from './cb015-lib.mjs'

const cdp = await connect()
const before = await cdp.eval('document.documentElement.dataset.hermesMode')
console.log('mode before:', before)
console.log('route:', await cdp.eval(`document.querySelector('[data-cb-route]')?.getAttribute('data-cb-destination') || 'not mounted'`))
await setMode(cdp, 'light')
console.log('mode after:', await cdp.eval('document.documentElement.dataset.hermesMode'))
console.log('bg:', await cdp.eval(`getComputedStyle(document.body).backgroundColor`))
await cdp.shot('docs/cb015-shots/_wip-light.png')
await setMode(cdp, 'dark')
console.log('mode final:', await cdp.eval('document.documentElement.dataset.hermesMode'))
cdp.close()
