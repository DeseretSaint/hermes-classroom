import { connect } from '../../scripts/cb015-lib.mjs'
const cdp = await connect()
const logs = []
cdp.on((m) => {
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails
    logs.push({ kind: 'exception', text: (d.exception?.description || d.text || '').slice(0, 1200) })
  }
  if (m.method === 'Runtime.consoleAPICalled' && (m.params.type === 'error' || m.params.type === 'warning')) {
    logs.push({
      kind: 'console.' + m.params.type,
      text: m.params.args.map((a) => a.value ?? a.description ?? a.type).join(' ').slice(0, 1200)
    })
  }
  if (m.method === 'Log.entryAdded' && ['error', 'warning'].includes(m.params.entry.level)) {
    logs.push({ kind: 'log.' + m.params.entry.level, text: (m.params.entry.source + ': ' + m.params.entry.text).slice(0, 1200) })
  }
})
await cdp.send('Runtime.enable')
await cdp.send('Log.enable')
await cdp.send('Page.enable')
await cdp.send('Page.reload', { ignoreCache: true })
await cdp.wait(9000)
const state = await cdp.json(`({
  hasCoursebookWord: /Coursebook/i.test(document.body.innerText),
  buttons: [...document.querySelectorAll('button, a')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 25),
  routeEl: !!document.querySelector('[data-cb-route]')
})`)
console.log(JSON.stringify({ logs, state }, null, 2))
cdp.close()
