#!/usr/bin/env node
/** CB-015 residual: bootstrap probe. Navigates to /coursebook, dismisses the host provider
 *  overlay only through its own labelled control, and reports what the route actually mounts. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.send('Page.enable')
await cdp.send('Runtime.enable')

const overlay = await cdp.json(`(() => {
  const t = document.body.innerText || ''
  return {
    providerOverlay: /choose a provider|provider later|Set up a provider/i.test(t),
    text: t.slice(0, 900)
  }
})()`)
if (overlay.providerOverlay) {
  const clicked = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('button')].find(x => /choose a provider later|provider later/i.test(x.innerText || ''))
    if (!b) return false
    b.click(); return true
  })()`)
  await cdp.wait(800)
  console.log('provider overlay dismissed:', clicked)
}

await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(2500)
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return {
    hash: location.hash,
    destination: root?.getAttribute('data-cb-destination') || null,
    mode: document.documentElement.dataset.hermesMode,
    buttons: [...document.querySelectorAll('button')].map(b => (b.innerText || '').trim()).filter(Boolean).slice(0, 40),
    rightSidebar: !!document.querySelector('[aria-label="Hide right sidebar"]'),
    text: (document.body.innerText || '').replace(/\\n{2,}/g, '\\n').slice(0, 1400)
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
