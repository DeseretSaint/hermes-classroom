#!/usr/bin/env node
/** Capture the CB-015 gallery: courses list in both appearances. */
import { connect, setMode } from './cb015-lib.mjs'

const cdp = await connect()
await setMode(cdp, 'dark')
await cdp.wait(400)
console.log(await cdp.shot('docs/cb015-shots/01-courses-dark.png'))
await setMode(cdp, 'light')
await cdp.wait(400)
console.log(await cdp.shot('docs/cb015-shots/02-courses-light.png'))
await setMode(cdp, 'dark')
console.log('mode:', await cdp.eval('document.documentElement.dataset.hermesMode'))
cdp.close()
