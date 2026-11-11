// Precise: which plugin rows (role=switch) exist, and is any of them Coursebook?
import { connect } from './cb015-lib.mjs'
const cdp = await connect()
await cdp.wait(800)
const out = await cdp.json(`(() => {
  const pane = [...document.querySelectorAll('*')].find(e => /Plugins/i.test(e.textContent||'') && e.children.length>0 && /Auto-update/.test(e.textContent||''))
  const switches = [...document.querySelectorAll('[role="switch"], input[type=checkbox]')]
  const rows = switches.map(sw => {
    // walk up until the container text grows to include a version/author line
    let p = sw, best = sw.parentElement
    for (let i=0;i<6 && p;i++) { const t=(p.innerText||'').trim(); if (t && t.length < 400) best = p; p = p.parentElement }
    const r = best ? best.getBoundingClientRect() : null
    return { text: ((best && best.innerText)||'').trim().split('\\n').slice(0,3).join(' | '), y: r ? Math.round(r.y) : null }
  })
  // element-level Coursebook mentions with geometry
  const mentions = []
  const walk = (el) => {
    if (el.children.length === 0 && /coursebook/i.test(el.textContent||'')) {
      const r = el.getBoundingClientRect()
      mentions.push({ t:(el.textContent||'').trim().slice(0,60), x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width) })
    }
    for (const c of el.children) walk(c)
  }
  walk(document.body)
  return {
    switchCount: switches.length,
    rows,
    mentions: mentions.slice(0,10),
    panePresent: !!pane,
    scrollableDoc: document.documentElement.scrollHeight,
    viewport: { w: innerWidth, h: innerHeight },
    decisions: localStorage.getItem('hermes.desktop.pluginDecisions.v2')
  }
})()`)
console.log(JSON.stringify(out, null, 1))
cdp.close()
