#!/usr/bin/env node
/** Reload the window, land on #/coursebook, and report what the route renders. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.reload()
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { timeout: 25000, label: 'route after reload' })
await cdp.wait(2500)
console.log(await cdp.eval(`document.querySelector('[data-cb-route]').innerText.replace(/\\n{2,}/g, '\\n').slice(0, 700)`))
cdp.close()
