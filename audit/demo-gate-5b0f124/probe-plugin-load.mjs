import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await cdp.wait(1500)
const out = await cdp.json(`(() => {
  const html = document.documentElement.innerHTML
  return {
    bodyText: document.body.innerText.slice(0, 1200),
    hasCoursebookWord: /Coursebook/i.test(document.body.innerText),
    coursebookEls: [...document.querySelectorAll('*')].filter(e => /coursebook/i.test(e.getAttribute && (e.getAttribute('data-plugin-id') || e.getAttribute('data-contribution') || e.id || e.className || ''))).slice(0,10).map(e => e.tagName + '.' + (e.className||'').slice(0,60)),
    pluginSdkPluginIds: (() => { try { return Object.keys(window.__HERMES_PLUGIN_SDK__.plugins || {}) } catch(e) { return 'ERR' } })(),
    sdkRootKeys: Object.keys(window.__HERMES_PLUGIN_SDK__ || {}),
    routeEl: !!document.querySelector('[data-cb-route]'),
    rightSidebar: [...document.querySelectorAll('[data-pane-id], [data-pane]')].map(e => e.getAttribute('data-pane-id') || e.getAttribute('data-pane')).slice(0,20)
  }
})()`)
save('probe-plugin-load.json', { ...out, consoleErrors: console_ })
console.log(JSON.stringify({ ...out, consoleErrors: console_ }, null, 2))
cdp.close()
