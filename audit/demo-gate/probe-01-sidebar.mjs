// Locate the Coursebook sidebar entry and its DOM identity.
import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const out = await cdp.json(`(() => {
  const hits = []
  for (const el of document.querySelectorAll('*')) {
    const t = (el.innerText || '').trim()
    if (t === 'Coursebook' && el.children.length === 0) {
      const r = el.getBoundingClientRect()
      hits.push({
        tag: el.tagName, cls: el.className?.toString().slice(0,120),
        role: el.getAttribute('role'), label: el.getAttribute('aria-label'),
        x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2),
        parent: el.parentElement?.tagName + '.' + el.parentElement?.className?.toString().slice(0,100)
      })
    }
  }
  return { hits }
})()`)
console.log(JSON.stringify(out, null, 2))
cdp.close()
