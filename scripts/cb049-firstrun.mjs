/** First-run proof on the clean cb049 backend (44221): dark + light. */
import { connect, setMode } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.waitFor(`document.body.innerText.includes('Backend')`, { timeout: 30000, label: 'statusbar' })
let text = await cdp.eval(`document.body.innerText`)
for (let i = 0; i < 40 && !/Backend\\s*\\n?ready/.test(text) && !/ready/.test(text); i += 1) {
  await cdp.wait(1000)
  text = await cdp.eval(`document.body.innerText`)
}
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await cdp.reload()
await cdp.wait(4000)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(3500)
let first = await cdp.eval(`!!document.querySelector('[data-cb-route]')`)
if (!first) {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(3000)
}
await setMode(cdp, 'dark')
await cdp.wait(600)
const out = []
out.push(await cdp.shot('docs/cb049-shots/060-firstrun-dark.png'))
const body = await cdp.eval(`(document.querySelector('[data-cb-route]') || document.body).innerText.slice(0, 700)`)
const h = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const h2 = root && root.querySelector('h2')
  if (!h2) return null
  const cs = getComputedStyle(h2)
  const p = h2.nextElementSibling
  const ps = p ? getComputedStyle(p) : null
  return { text: h2.innerText, fontSize: cs.fontSize, fontWeight: cs.fontWeight, letterSpacing: cs.letterSpacing, pFont: ps && ps.fontSize, pLine: ps && ps.lineHeight, pMarginTop: ps && ps.marginTop }
})()`)
await setMode(cdp, 'light')
await cdp.wait(600)
out.push(await cdp.shot('docs/cb049-shots/061-firstrun-light.png'))
console.log(JSON.stringify({ body, h }, null, 2))
console.log(out)
cdp.close()
