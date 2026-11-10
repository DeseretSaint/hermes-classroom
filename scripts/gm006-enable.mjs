#!/usr/bin/env node
/* Enable the plugin in this fresh rig once, reload, and land on the route. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
const evalx = (expression) => cdp.eval(expression)
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
await cdp.send('Runtime.enable', {})
await cdp.send('Page.enable', {})
const before = await evalx("localStorage.getItem('hermes.desktop.pluginDecisions.v2')")
if (!before || !JSON.parse(before).coursebook) {
  await evalx("localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))")
  await cdp.send('Page.reload', { ignoreCache: false })
  await wait(5000)
}
console.log('decision', await evalx("localStorage.getItem('hermes.desktop.pluginDecisions.v2')"))
console.log('nav items after', await evalx("document.querySelectorAll('[data-cb-nav-item]').length"))
await evalx("location.hash = '#/coursebook'")
await wait(3000)
console.log('hash', await evalx('location.hash'))
console.log('route', await evalx("!!document.querySelector('[data-cb-route]')"))
console.log('nav', await evalx("[...document.querySelectorAll('[data-cb-nav-item]')].map(b=>b.getAttribute('data-cb-nav-item')).join(',')"))
cdp.close()
