#!/usr/bin/env node
/** GM-010 probe: read the live route state before capturing. */
import { connect } from './cb015-lib.mjs'

const wait = (ms) => new Promise((done) => setTimeout(done, ms))
const cdp = await connect()
await cdp.send('Page.enable')
await cdp.send('Runtime.enable')
await wait(2500)
const out = await cdp.eval(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const cards = [...document.querySelectorAll('[data-cb-home-card]')].map((n) => n.innerText.replace(/\\s+/g, ' ').slice(0, 80))
  return {
    hash: location.hash,
    decision: localStorage.getItem('hermes.desktop.pluginDecisions.v2'),
    route: Boolean(root),
    routeText: root ? root.innerText.replace(/\\s+/g, ' ').slice(0, 300) : null,
    cards,
    nav: [...document.querySelectorAll('nav a, nav button')].map((n) => (n.innerText || '').trim()).filter(Boolean).slice(0, 12),
    game: document.querySelector('[data-cb-game]')?.getAttribute('data-cb-game') || null,
    desk: document.querySelector('[data-cb-desk]')?.getAttribute('data-cb-desk') || null
  }
})()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
