// Does Enter (vs Space) produce a click on a focused plugin button, and does a text payload change it?
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const trials = []
await cdp.eval(`location.hash = '#/coursebook'`); await cdp.wait(1500)

const setup = await cdp.eval(`(() => {
  window.__cbClicks = []
  document.addEventListener('click', (e) => { window.__cbClicks.push((e.target?.innerText||e.target?.getAttribute?.('aria-label')||e.target?.tagName||'').trim().slice(0,40)) }, true)
  return true
})()`)

const focus = (name) => cdp.eval(`(() => {
  const el = [...document.querySelectorAll('button,a,[role=button]')].find(e => ((e.innerText||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ')) === ${JSON.stringify(name)})
  if (!el) return null
  el.focus(); return el.tagName
})()`)

for (const [key, params] of [
  ['Enter', {}],
  ['Enter', { text: '\r', unmodifiedText: '\r' }],
  ['Space', {}]
]) {
  await focus('Import pack')
  await cdp.wait(120)
  await cdp.eval('window.__cbClicks = []')
  await cdp.send('Input.dispatchKeyEvent', {
    type: 'keyDown', key, code: key === 'Space' ? 'Space' : 'Enter',
    windowsVirtualKeyCode: key === 'Space' ? 32 : 13, nativeVirtualKeyCode: 0, ...params
  })
  await cdp.send('Input.dispatchKeyEvent', {
    type: 'keyUp', key, code: key === 'Space' ? 'Space' : 'Enter',
    windowsVirtualKeyCode: key === 'Space' ? 32 : 13, nativeVirtualKeyCode: 0
  })
  await cdp.wait(800)
  const clicks = await cdp.eval('window.__cbClicks')
  const panel = await cdp.eval("/Choose a pack archive|Choose a different file/.test(document.querySelector('[data-cb-route]')?.innerText||'')")
  trials.push({ key, params: Object.keys(params), clicks, panelOpen: panel })
  if (panel) { // close the panel before the next trial
    await cdp.eval(`(() => { const b=[...document.querySelectorAll('[data-cb-route] button')].find(x=>(x.innerText||'').trim()==='Close'); if(b) b.click() })()`)
    await cdp.wait(800)
  }
}
save('u03c-enter-vs-space.json', { setup, trials, consoleErrors: console_ })
console.log(JSON.stringify({ trials, consoleErrors: console_ }, null, 2))
cdp.close()
