import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const steps = []
await cdp.eval(`(location.hash = '#/coursebook', true)`)
await cdp.wait(1200)
try { steps.push({ step: 'open', ...(await clickLabel(cdp, 'Open', { selector: 'button, a' })) }) } catch (e) { steps.push({ step: 'open', error: e.message }) }
await cdp.wait(2500)
const state1 = await cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return {
  hash: location.hash, text: r ? r.innerText.slice(0,1800) : null,
  buttons: r ? [...r.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled })).filter(b=>b.label) : []
} })()`)
try { steps.push({ step: 'textbook-tab', ...(await clickLabel(cdp, 'Textbook', { selector: 'button, [role=tab], a' })) }) } catch (e) { steps.push({ step: 'textbook-tab', error: e.message }) }
await cdp.wait(1800)
const state2 = await cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return {
  hash: location.hash, text: r ? r.innerText.slice(0,2200) : null,
  buttons: r ? [...r.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled })).filter(b=>b.label) : []
} })()`)
save('u06-open-course.json', { steps, state1, state2, consoleErrors: console_ })
console.log(JSON.stringify({ steps, state1, state2, consoleErrors: console_ }, null, 2).slice(0, 6000))
cdp.close()
