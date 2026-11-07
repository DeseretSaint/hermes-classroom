// U02 exploration — Library surface and the import entry point.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await clickLabel(cdp, 'Library', { selector: 'button, a, [role=tab]' })
await cdp.wait(1500)
const lib = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  const buttons = root ? [...root.querySelectorAll('button')].map(b => (b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean) : []
  return { hash: location.hash, text: text.replace(/\\n{2,}/g,'\\n').slice(0,2500), buttons: buttons.slice(0,40) }
})()`)
save('u02a-library.json', { lib, consoleErrors: console_ })
console.log(JSON.stringify({ lib, consoleErrors: console_ }, null, 2))
cdp.close()
