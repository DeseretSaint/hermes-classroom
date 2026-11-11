// Probe the fresh-userdata window: what nav exists, what does the root route show?
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.wait(800)
const info = await cdp.json(`(() => {
  const nav = [...document.querySelectorAll('button,a,[role="tab"],[role="link"]')]
    .map(e => (e.innerText || '').trim()).filter(Boolean)
  return {
    hash: location.hash,
    title: document.title,
    bodyLen: document.body.innerText.length,
    bodyHead: document.body.innerText.slice(0, 600),
    nav: [...new Set(nav)].slice(0, 60),
    pluginDecisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2'),
    cbRoute: !!document.querySelector('[data-cb-route]')
  }
})()`)
console.log(JSON.stringify(info, null, 1))
cdp.close()
