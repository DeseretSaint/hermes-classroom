import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const label = process.argv[2] || 'Resume lesson'
await cdp.eval(`(location.hash = '#/coursebook', true)`)
await cdp.wait(1200)
const before = await cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return { hash: location.hash, text: r ? r.innerText.slice(0,900) : null } })()`)
let clicked = null
try { clicked = await clickLabel(cdp, label, { selector: 'button, a' }) } catch (e) { clicked = { error: e.message } }
await cdp.wait(4000)
const after = await cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return {
  hash: location.hash,
  routeMounted: !!r,
  text: r ? r.innerText.slice(0,1200) : null,
  pane: (() => { try { return window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get() } catch(e) { return 'ERR:'+e.message } })(),
  notices: [...document.querySelectorAll('[role=status], [role=alert], .notice')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,6),
  bodySnippet: document.body.innerText.slice(0, 300)
} })()`)
save('u05-click-detail.json', { label, clicked, before, after, consoleErrors: console_ })
console.log(JSON.stringify({ label, clicked, before, after, consoleErrors: console_ }, null, 2).slice(0, 5000))
cdp.close()
