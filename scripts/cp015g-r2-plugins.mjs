// First-run check: fresh userdata -> Capabilities -> Plugins inventory. No decision key written.
import { connect } from './cb015-lib.mjs'
const out = process.env.CP015G_OUT || 'docs/concept-parity/demo/cp015g-r2'
const cdp = await connect()
await cdp.setViewport(1344, 768)
// wait for backend to report connected
for (let i = 0; i < 60; i++) {
  const txt = await cdp.eval(`document.body.innerText`)
  if (!/CONNECTING|checking/i.test(txt)) break
  await cdp.wait(1000)
}
await cdp.wait(1000)
const before = await cdp.eval(`document.body.innerText.slice(0,400)`)
const btn = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('button')].find((b) => (b.innerText || '').trim() === 'Capabilities')
  if (!el) return null
  const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
})()`)
if (!btn) throw new Error('no Capabilities button')
await cdp.click(btn.x, btn.y)
await cdp.wait(1500)
const cap = await cdp.json(`(() => ({
  body: document.body.innerText.slice(0, 1500),
  tabs: [...document.querySelectorAll('[role="tab"], button')].map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 40)
}))()`)
// find a Plugins tab/row
const plug = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('[role="tab"], button, a')].find((e) => /^plugins$/i.test((e.innerText || '').trim()))
  if (!el) return null
  const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2, text: el.innerText }
})()`)
let pluginsText = null
if (plug) {
  await cdp.click(plug.x, plug.y)
  await cdp.wait(2000)
  pluginsText = await cdp.json(`(() => {
    const root = document.querySelector('[data-cb-route]') || document.body
    const switches = [...document.querySelectorAll('[role="switch"], input[type="checkbox"]')].map((e) => ({
      name: e.getAttribute('aria-label') || (e.closest('label,li,div') || {}).innerText || '',
      checked: e.getAttribute('aria-checked') || e.checked
    }))
    return { body: root.innerText.slice(0, 3000), switches, coursebookMentioned: /coursebook/i.test(document.body.innerText) }
  })()`)
}
await cdp.shot(`${out}/00-fresh-capabilities-plugins.png`)
console.log(JSON.stringify({ before, cap, plug, pluginsText }, null, 2))
cdp.close()
