import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const out = await cdp.json(`(() => ({
  width: window.innerWidth,
  height: window.innerHeight,
  buttons: [...document.querySelectorAll('button')].map(b => ({
    label: (b.innerText || '').trim().slice(0, 60),
    aria: b.getAttribute('aria-label'),
    title: b.getAttribute('title')
  })).filter(b => b.label || b.aria || b.title).slice(0, 80),
  navTexts: [...document.querySelectorAll('nav, aside, [role="navigation"]')].map(n => (n.innerText || '').trim().slice(0, 400)).slice(0, 5),
  pluginNav: [...document.querySelectorAll('[data-plugin], [data-contribution], [data-cb-sidebar-item]')].length,
  hash: location.hash
}))()`)
writeJson(rel('audit/demo-gate-5b0f124/probe-sidebar.json'), out)
console.log(JSON.stringify(out, null, 2))
cdp.close()
