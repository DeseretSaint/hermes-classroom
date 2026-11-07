// Click "Choose folder…" and report.
import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const box = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Choose folder…')
  if (!el) return null
  const r = el.getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }
})()`)
if (!box) { console.log('no choose button'); process.exit(1) }
await cdp.click(box.x, box.y)
console.log('clicked choose-folder', JSON.stringify(box))
cdp.close()
