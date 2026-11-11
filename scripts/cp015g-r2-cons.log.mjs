import { connect } from './cb015-lib.mjs'
const cdp = await connect()
const logs = []
cdp.on((m) => {
  if (m.method === 'Runtime.consoleAPICalled') {
    const a = (m.params.args || []).map(x => x.value ?? x.description ?? x.type).join(' ')
    logs.push(`[${m.params.type}] ${a.slice(0, 300)}`)
  }
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXC ' + JSON.stringify(m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text || '').slice(0, 400))
  if (m.method === 'Log.entryAdded') logs.push(`[log:${m.params.entry.level}] ${m.params.entry.text.slice(0, 300)}`)
})
await cdp.send('Runtime.enable')
await cdp.send('Log.enable')
await cdp.send('Page.enable')
await cdp.send('Page.reload', { ignoreCache: false })
await cdp.wait(9000)
console.log(logs.slice(0, 25).join('\n---\n') || 'no console messages')
console.log('BODY:', (await cdp.eval('document.body.innerText.slice(0,200)')))
cdp.close()
