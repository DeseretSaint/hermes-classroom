import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const raw = await cdp.eval(`(async () => {
  const out = { hasDesktopApi: !!window.hermesDesktop, keys: window.hermesDesktop ? Object.keys(window.hermesDesktop).slice(0, 60) : [] }
  try {
    if (window.hermesDesktop?.desktopPluginsRoot) {
      const root = await window.hermesDesktop.desktopPluginsRoot()
      out.root = root
      if (root && window.hermesDesktop.readDir) {
        out.entries = (await window.hermesDesktop.readDir(root)).entries.map(e => ({ name: e.name, isDirectory: e.isDirectory }))
      }
    }
  } catch (e) { out.err = String(e && e.message || e) }
  try { out.appApiKeys = window.__hermesApp ? Object.keys(window.__hermesApp).slice(0,40) : null } catch (e) {}
  return JSON.stringify(out)
})()`)
console.log(raw)
cdp.close()
