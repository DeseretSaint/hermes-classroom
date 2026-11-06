#!/usr/bin/env node
/** Open the studio view combobox and choose one option through the real popup. */
import { connect } from './cb015-lib.mjs'
const label = process.argv[2] || 'Plan'
const cdp = await connect()
const opened = await cdp.eval(`(() => { const el = document.getElementById('cb-studio-view'); if (!el) return false; el.click(); return true })()`)
await cdp.wait(600)
const options = await cdp.json(`(() => [...document.querySelectorAll('[role="option"]')].map(o => {
  const r = o.getBoundingClientRect()
  return { text: (o.innerText||'').trim(), x: r.x, y: r.y, w: r.width, h: r.height, state: o.getAttribute('data-state') }
}))()`)
console.log('opened:', opened, 'options:', JSON.stringify(options))
const target = options.find(o => o.text === label)
if (target) {
  await cdp.click(target.x + target.w / 2, target.y + target.h / 2)
  await cdp.wait(2200)
}
const text = await cdp.eval(`(document.querySelector('[data-cb-route]') || document.body).innerText.replace(/\\n{2,}/g,'\\n').slice(0, 1000)`)
console.log(text)
cdp.close()
