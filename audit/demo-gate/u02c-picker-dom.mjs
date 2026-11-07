// Inspect the pack import picker DOM.
import { connect, writeJson, rel } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const info = await cdp.json(`(() => {
  const candidates = [...document.querySelectorAll('div,section')].filter(e => (e.innerText||'').includes('DESERETSAINT') && (e.innerText||'').includes('cb015-packs'))
  const el = candidates[candidates.length - 1]
  if (!el) return { found: false }
  const inputs = [...el.querySelectorAll('input')].map(i => ({ type: i.type, placeholder: i.placeholder, value: i.value, label: i.getAttribute('aria-label') }))
  const buttons = [...el.querySelectorAll('button')].map(b => ({ label: (b.innerText||b.getAttribute('aria-label')||'').trim(), disabled: b.disabled })).filter(b=>b.label)
  return { found: true, tag: el.tagName, cls: (el.className||'').toString().slice(0,200), role: el.getAttribute('role'), inputs, buttons, text: (el.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0,900) }
})()`)
writeJson(rel('audit/demo-gate/u02c-picker-dom.json'), info)
console.log(JSON.stringify(info, null, 2))
cdp.close()
