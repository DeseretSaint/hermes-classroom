import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const raw = await cdp.eval(`(async () => {
  const host = window.__HERMES_PLUGIN_SDK__.host
  let decisions = null, pluginsList = null, err = null
  try { decisions = await host.pluginDecisions() } catch (e) { err = String(e && e.message || e) }
  try { pluginsList = await host.plugins?.() } catch (e) { pluginsList = 'ERR:' + (e && e.message || e) }
  return JSON.stringify({
    decisions, pluginsList,
    sdkPlugins: typeof window.__HERMES_PLUGIN_SDK__.plugins,
    stateKeys: Object.keys(host.state || {}),
    pluginState: host.state && host.state.plugins,
    desktopPlugins: host.state && host.state.desktopPlugins,
    err
  })
})()`)
const out = JSON.parse(raw)
console.log(JSON.stringify(out, null, 2).slice(0, 4000))
cdp.close()
