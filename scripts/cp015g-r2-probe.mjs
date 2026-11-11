// Probe the live renderer: dump visible route text, nav items, and the plugin inventory.
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.setViewport(1344, 768)
await cdp.wait(1500)
const state = await cdp.json(`(() => {
  const t = (el) => (el ? (el.innerText || '').trim().slice(0, 300) : null)
  return {
    hash: location.hash,
    title: document.title,
    body: document.body.innerText.slice(0, 2500),
    controls: [...document.querySelectorAll('button, a, [role="tab"], [role="menuitem"], [data-cb-route]')].map((el) => ({ tag: el.tagName, text: t(el), role: el.getAttribute('role'), cb: el.getAttribute('data-cb-route'), href: el.getAttribute('href') })).filter((x) => x.text || x.cb).slice(0, 80)
  }
})()`)
console.log(JSON.stringify(state, null, 2))
cdp.close()
