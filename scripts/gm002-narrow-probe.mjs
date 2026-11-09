import { connect } from './cb015-lib.mjs'
import { writeFileSync } from 'node:fs'
const cdp = await connect()
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const send = (m, p = {}) => cdp.send(m, p)
await send('Emulation.setDeviceMetricsOverride', { width: 460, height: 900, deviceScaleFactor: 1, mobile: false })
await wait(400)
let override = 460
for (let i = 0; i < 12; i += 1) {
  await send('Emulation.setDeviceMetricsOverride', { width: override, height: 900, deviceScaleFactor: 1, mobile: false })
  await wait(280)
  const measured = await cdp.eval('window.innerWidth')
  if (measured === 460) break
  override = Math.max(200, override + (460 - measured))
}
await cdp.eval(`document.documentElement.style.setProperty('font-size','32px','important')`)
await cdp.eval(`location.hash='#/courses'`); await wait(400)
await cdp.eval(`location.hash='#/coursebook'`); await wait(1500)
await cdp.eval(`document.querySelectorAll('[data-cb-home-card] button')[0].click()`); await wait(1600)
const facts = await cdp.json(`(() => {
  const plate = document.querySelector('[data-cb-continue]')
  if (!plate) return { found: false }
  plate.scrollIntoView({ block: 'center' })
  const rect = plate.getBoundingClientRect()
  return { found: true, text: (plate.innerText || '').replace(/\\s+/g,' ').slice(0,200),
    rect: { top: Math.round(rect.top), left: Math.round(rect.left), right: Math.round(rect.right), bottom: Math.round(rect.bottom), width: Math.round(rect.width), height: Math.round(rect.height) },
    innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    clippedX: rect.left < 0 || rect.right > window.innerWidth + 1,
    textOverflow: plate.scrollWidth > plate.clientWidth + 1 }
})()`)
await wait(500)
const png = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
writeFileSync('docs/visual-review/gm-002/home.course--460--light--200--continue.png', Buffer.from(png.data, 'base64'))
console.log(JSON.stringify(facts, null, 2))
cdp.close()
