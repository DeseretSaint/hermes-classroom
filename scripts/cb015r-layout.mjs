#!/usr/bin/env node
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const info = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const sel = document.getElementById('cb-studio-view')
  const r = sel ? sel.getBoundingClientRect() : null
  return {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    rootWidth: root ? root.getBoundingClientRect().width : null,
    studioSelect: sel ? { tag: sel.tagName, role: sel.getAttribute('role'), x: r.x, y: r.y, w: r.width, h: r.height, text: (sel.innerText||'').trim() } : null,
    selects: [...root.querySelectorAll('[role="combobox"], select')].map(e => ({ id: e.id, label: e.getAttribute('aria-label'), text: (e.innerText||'').trim().slice(0,40) }))
  }
})()`)
console.log(JSON.stringify(info, null, 2))
cdp.close()
