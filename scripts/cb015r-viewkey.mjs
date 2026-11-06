#!/usr/bin/env node
/** Move the studio view combobox by keyboard until the selected view matches argv[2]. */
import { connect } from './cb015-lib.mjs'
const wanted = process.argv[2] || 'Plan'
const cdp = await connect()
const current = () => cdp.eval(`(document.getElementById('cb-studio-view') || {}).innerText`)
const order = ['Brief', 'Plan', 'Pages', 'Export', 'Reflection']
let guard = 0
while ((await current()) !== wanted && guard < 8) {
  const now = await current()
  const from = order.indexOf(now)
  const to = order.indexOf(wanted)
  const key = to > from ? 'ArrowDown' : 'ArrowUp'
  await cdp.eval(`document.getElementById('cb-studio-view').focus()`)
  await cdp.wait(200)
  await cdp.key(key)
  await cdp.wait(300)
  await cdp.key('Enter')
  await cdp.wait(1200)
  guard += 1
}
const info = await cdp.json(`(() => ({
  view: (document.getElementById('cb-studio-view') || {}).innerText,
  text: (document.querySelector('[data-cb-route]') || document.body).innerText.replace(/\\n{2,}/g,'\\n').slice(0, 900)
}))()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
