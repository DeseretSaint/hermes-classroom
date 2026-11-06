/** Discover theme options and verify chat/session isolation of this window. */
import { connect } from '../scripts/cb015-lib.mjs'

const cdp = await connect()
const before = await cdp.eval(`document.body.innerText.includes('Shift-click a chat to pin')`)
console.log('empty session list:', before)
console.log('mode attr:', await cdp.eval(`document.documentElement.dataset.hermesMode`))
console.log('theme attrs:', await cdp.eval(`JSON.stringify({...document.documentElement.dataset})`))
console.log('localStorage theme keys:', await cdp.json(`Object.keys(localStorage).filter(k => /theme/i.test(k))`))
console.log('theme state:', await cdp.json(`(() => {
  const out = {}
  for (const k of Object.keys(localStorage)) {
    if (/theme/i.test(k)) out[k] = localStorage.getItem(k)?.slice(0, 200)
  }
  return out
})()`))
cdp.close()
