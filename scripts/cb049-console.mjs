/** Capture renderer console/exceptions across a reload and a #/coursebook visit. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
const errors = []
cdp.on((msg) => {
  if (msg.method === 'Runtime.exceptionThrown') {
    errors.push('EXC ' + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text))
  }
  if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
    errors.push(msg.params.type.toUpperCase() + ' ' + msg.params.args.map((a) => a.value ?? a.description).join(' '))
  }
})
await cdp.send('Runtime.enable')
await cdp.reload()
await cdp.wait(3500)
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(3000)
const state = await cdp.json(`(() => ({
  hash: location.hash,
  hasRoute: !!document.querySelector('[data-cb-route]'),
  body: document.body.innerText.slice(0, 700)
}))()`)
console.log(JSON.stringify({ state, errors: errors.filter((e) => !/Content-Security-Policy/.test(e)).slice(0, 15) }, null, 2))
cdp.close()
