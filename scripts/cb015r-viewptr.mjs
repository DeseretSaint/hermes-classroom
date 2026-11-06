#!/usr/bin/env node
/** Choose a studio view through the Radix popup using real pointer events on the option. */
import { connect } from './cb015-lib.mjs'
const wanted = process.argv[2] || 'Plan'
const cdp = await connect()
await cdp.eval(`document.getElementById('cb-studio-view').click()`)
await cdp.wait(500)
const result = await cdp.eval(`(() => {
  const opt = [...document.querySelectorAll('[role="option"]')].find(o => (o.innerText || '').trim() === ${JSON.stringify(wanted)})
  if (!opt) return 'no-option'
  const rect = opt.getBoundingClientRect()
  const init = { bubbles: true, cancelable: true, composed: true, pointerId: 1, isPrimary: true, button: 0, buttons: 1,
                 clientX: rect.x + rect.width / 2, clientY: rect.y + rect.height / 2 }
  opt.dispatchEvent(new PointerEvent('pointerover', init))
  opt.dispatchEvent(new PointerEvent('pointerenter', init))
  opt.dispatchEvent(new PointerEvent('pointermove', init))
  opt.dispatchEvent(new PointerEvent('pointerdown', init))
  opt.dispatchEvent(new PointerEvent('pointerup', { ...init, buttons: 0 }))
  opt.click()
  return 'dispatched'
})()`)
await cdp.wait(1800)
const view = await cdp.eval(`(document.getElementById('cb-studio-view') || {}).innerText`)
console.log(JSON.stringify({ result, view }))
cdp.close()
