#!/usr/bin/env node
/** From inside the renderer, ask both candidate backends what they hold. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
for (const port of [44220, 44219]) {
  const out = await cdp.eval(`fetch('http://127.0.0.1:${port}/api/plugins/coursebook/rpc?profile=', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer cb013-test-token' },
    body: JSON.stringify({ contract: 'cb.rpc', contract_version: 6, method: 'library.list',
      operation_id: 'probe-${port}', payload: { filter: 'all', limit: 50, sort: 'title' } })
  }).then(r => r.json()).then(j => JSON.stringify({ ok: j.ok, total: j.result && j.result.total, err: j.error && j.error.code })).catch(e => 'ERR ' + e.message)`)
  console.log(port, out)
}
console.log('origin:', await cdp.eval('location.origin'))
console.log('stored rows:', await cdp.eval(`Object.keys(localStorage).filter(k => /cb|course/i.test(k)).slice(0, 20).join(',')`))
cdp.close()
