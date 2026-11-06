#!/usr/bin/env node
/** Read renderer console errors/exceptions, then click the sidebar's Coursebook entry. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
const messages = []
cdp.on((message) => {
  if (message.method === 'Runtime.consoleAPICalled') {
    const { type, args } = message.params
    if (type === 'error' || type === 'warning') {
      messages.push(`${type}: ${args.map((a) => a.value ?? a.description ?? a.type).join(' ').slice(0, 400)}`)
    }
  }
  if (message.method === 'Runtime.exceptionThrown') {
    messages.push(`exception: ${message.params.exceptionDetails.exception?.description?.slice(0, 600)}`)
  }
  if (message.method === 'Log.entryAdded') {
    const entry = message.params.entry
    if (entry.level === 'error') messages.push(`log: ${entry.text.slice(0, 400)}`)
  }
})
await cdp.send('Runtime.enable')
await cdp.send('Log.enable')
await cdp.reload()
await cdp.wait(5000)
console.log('hash after reload:', await cdp.eval('location.hash'))
console.log('route:', await cdp.eval(`document.querySelector('[data-cb-route]')?.getAttribute('data-cb-destination') || 'not mounted'`))

// Click the sidebar Coursebook nav entry the way a user would.
const box = await cdp.json(`(() => {
  const el = [...document.querySelectorAll('button, a, [role="button"], [role="link"]')]
    .find((e) => (e.innerText || '').trim() === 'Coursebook')
  if (!el) return null
  el.scrollIntoView({ block: 'center' })
  const r = el.getBoundingClientRect()
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
})()`)
console.log('nav entry box:', box)
if (box) await cdp.click(box.x, box.y)
await cdp.wait(4000)
console.log('hash:', await cdp.eval('location.hash'))
console.log('route:', await cdp.eval(`document.querySelector('[data-cb-route]')?.getAttribute('data-cb-destination') || 'not mounted'`))
console.log('console errors:', messages.length ? messages : 'none')
cdp.close()
