import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const raw = await cdp.eval(`(async () => {
  const host = window.__HERMES_PLUGIN_SDK__.host
  const s = host.state || {}
  let gw = null
  try { gw = await host.getGateway() } catch (e) { gw = { err: String(e && e.message || e) } }
  return JSON.stringify({
    connectionId: s.connectionId,
    profile: s.profile,
    activeSessionId: s.activeSessionId,
    gateway: s.gateway,
    getGatewayKeys: gw && typeof gw === 'object' ? Object.keys(gw) : typeof gw,
    getGatewayId: gw && gw.id, getGatewayUrl: gw && gw.url, getGatewayKind: gw && gw.kind, getGatewayErr: gw && gw.err,
    connectionsValue: host.connections,
    decisionsValue: host.pluginDecisions,
    localSessionsHint: document.body.innerText.split('\\n').slice(0, 12)
  })
})()`)
console.log(raw)
cdp.close()
