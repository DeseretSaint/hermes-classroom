import { connect, rel, writeJson } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const raw = await cdp.eval(`(async () => {
  const host = window.__HERMES_PLUGIN_SDK__.host
  let status = null, gw = null, err = null
  try { status = await host.status() } catch (e) { err = String(e && e.message || e) }
  try { gw = await host.getGateway() } catch (e) { gw = 'ERR:' + (e && e.message || e) }
  return JSON.stringify({
    activeConnectionId: host.activeConnectionId,
    connections: host.connections,
    status,
    gateway: gw,
    statusError: err,
    href: location.href,
    hash: location.hash
  })
})()`)
const out = JSON.parse(raw)
writeJson(rel('audit/demo-gate-5b0f124/probe-connection.json'), out)
console.log(JSON.stringify(out, null, 2))
cdp.close()
