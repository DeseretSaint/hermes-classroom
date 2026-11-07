// Read-only state probe of the isolated demo-gate window (5b0f124 rig).
import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'

const cdp = await connect()
await cdp.wait(2000)
const state = await cdp.json(`(() => ({
  href: location.href,
  hash: location.hash,
  title: document.title,
  ready: document.readyState,
  bodyText: document.body.innerText.slice(0, 2000),
  sidebarItems: [...document.querySelectorAll('[data-cb-sidebar-item], nav [role="link"], nav button, aside a, aside button')]
    .map(e => (e.innerText || e.getAttribute('aria-label') || '').trim()).filter(Boolean).slice(0, 60),
  routeEl: !!document.querySelector('[data-cb-route]'),
  routeName: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-route') || null,
  paneEl: !!document.querySelector('[data-cb-pane], [data-cb-coursebook-pane]'),
  coursebookNodes: document.querySelectorAll('[class*="coursebook"], [data-cb]').length,
  connText: (document.body.innerText.match(/Backend (online|offline|off)|Connecting|Offline|Waking up/gi) || []).slice(0,6),
  sdkRevealPane: !!(window.__HERMES_PLUGIN_SDK__ && window.__HERMES_PLUGIN_SDK__.host && window.__HERMES_PLUGIN_SDK__.host.revealPane),
  sdkPaneVisibility: !!(window.__HERMES_PLUGIN_SDK__ && window.__HERMES_PLUGIN_SDK__.host && window.__HERMES_PLUGIN_SDK__.host.paneVisibility),
  paneVisibility: (() => { try { return window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get() } catch (e) { return 'ERR:' + e.message } })(),
  sdkKeys: Object.keys((window.__HERMES_PLUGIN_SDK__ && window.__HERMES_PLUGIN_SDK__.host) || {})
}))()`)
writeJson(rel('audit/demo-gate-5b0f124/probe-00-state.json'), state)
console.log(JSON.stringify(state, null, 2))
cdp.close()
