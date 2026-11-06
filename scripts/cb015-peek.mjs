#!/usr/bin/env node
/** Probe one state at a time while the harness is being built: read the Coursebook DOM. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return {
    hash: location.hash,
    destination: root?.getAttribute('data-cb-destination') || null,
    mode: document.documentElement.dataset.hermesMode,
    text: (root?.innerText || '(no route root)').replace(/\\n{2,}/g, '\\n').slice(0, 1500)
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
