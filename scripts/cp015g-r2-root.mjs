import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const raw = await cdp.eval(`(async () => {
  const bridge = !!window.hermesDesktop
  let root = null, err = null
  try { root = await window.hermesDesktop?.desktopPluginsRoot?.() } catch (e) { err = String(e) }
  let entries = null
  try { const r = await window.hermesDesktop?.readDir?.(root); entries = r && (r.entries ? r.entries.map(e=>e.name) : r) } catch (e) { entries = 'ERR ' + e }
  return JSON.stringify({ bridge, root, err, entries })
})()`)
console.log(raw)
cdp.close()
