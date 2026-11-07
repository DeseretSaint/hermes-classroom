// Read-only state probe of the isolated demo-gate window (29bede7 rig).
import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'

const cdp = await connect()
const state = await cdp.json(`(() => ({
  href: location.href,
  hash: location.hash,
  title: document.title,
  ready: document.readyState,
  bodyText: document.body.innerText.slice(0, 1500),
  sidebarItems: [...document.querySelectorAll('[data-cb-sidebar-item], nav [role="link"], nav button, aside a')]
    .map(e => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(Boolean).slice(0, 40),
  routeEl: !!document.querySelector('[data-cb-route]'),
  routeName: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-route') || null,
  paneEl: !!document.querySelector('[data-cb-pane], [data-cb-coursebook-pane]'),
  coursebookNodes: document.querySelectorAll('[class*="coursebook"], [data-cb]').length,
  connText: (document.body.innerText.match(/Backend (online|offline|off)|Connecting|Offline/gi) || []).slice(0,4),
  errors: window.__cbErrors || null
}))()`)
writeJson(rel('audit/demo-gate/probe-00-state.json'), state)
console.log(JSON.stringify(state, null, 2))
cdp.close()
