#!/usr/bin/env node
/** Open the first course from the Courses list and print the resulting view. */
import { connect } from './cb015-lib.mjs'

const cdp = await connect()
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.waitFor(`!!document.querySelector('[data-cb-route]')`, { label: 'route' })
await cdp.wait(1500)
console.log('courses:', await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return { text: root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 400) }
})()`))
await cdp.clickText('Open')
await cdp.wait(2500)
console.log('after open:', await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  return { text: root.innerText.replace(/\\n{2,}/g, '\\n').slice(0, 900) }
})()`))
cdp.close()
