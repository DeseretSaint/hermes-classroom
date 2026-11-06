#!/usr/bin/env node
/** List host chrome controls (aria-labels, titles) so pane hide/reopen/split can be driven natively. */
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const info = await cdp.json(`(() => {
  const all = [...document.querySelectorAll('button, [role="button"], [role="tab"], [role="menuitem"]')]
  return {
    labels: all.map(el => ({
      label: (el.getAttribute('aria-label') || el.getAttribute('title') || (el.innerText || '').trim()).slice(0, 60),
      testid: el.getAttribute('data-testid') || null,
      cls: (el.className || '').toString().slice(0, 60)
    })).filter(x => x.label && !/^(New session|Capabilities|Messaging|Artifacts|Scheduled jobs|Coursebook)$/.test(x.label)).slice(0, 120),
    splitish: all.map(el => (el.getAttribute('aria-label') || el.getAttribute('title') || '')).filter(s => /split|pane|sidebar|layout/i.test(s))
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
