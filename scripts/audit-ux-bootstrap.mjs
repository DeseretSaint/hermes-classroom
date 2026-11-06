/** Enable the Coursebook package in the isolated window and open the route. */
import { connect, setMode } from '../scripts/cb015-lib.mjs'

const cdp = await connect()
await cdp.wait(2500)
await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
await cdp.reload()
await cdp.wait(5000)
await setMode(cdp, 'dark')
await cdp.eval(`location.hash = '#/coursebook'`)
await cdp.wait(3500)
if (!(await cdp.eval(`!!document.querySelector('[data-cb-route]')`))) {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(3000)
}
const state = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  if (!root) return { route: false, body: document.body.innerText.slice(0, 400) }
  return {
    route: true,
    destination: root.getAttribute('data-cb-destination'),
    text: root.innerText.slice(0, 900),
    controls: [...root.querySelectorAll('button, a, input, select, textarea, [role=button], [tabindex]')].length
  }
})()`)
console.log(JSON.stringify(state, null, 2))
await cdp.shot('docs/a11y-shots/000-bootstrap-dark.png')
cdp.close()
