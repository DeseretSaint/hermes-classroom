// Open the imported course from the Courses list (UI) and read the lesson surface.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await cdp.eval(`location.hash = '#/coursebook'`); await cdp.wait(1800)
const steps = []
// Go to Courses destination
try { await clickLabel(cdp, 'Courses', { selector: 'button, [role=tab], a' }) } catch (e) { steps.push({ step: 'courses-tab', error: e.message }) }
await cdp.wait(1000)
// Open the course
let opened = null
try { opened = await clickLabel(cdp, 'Open', { selector: 'button, a' }) } catch (e) { steps.push({ step: 'open', error: e.message }) }
await cdp.wait(2500)
const state = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  const obj = root ? root.querySelector('[data-cb-objective]') : null
  return {
    hash: location.hash, text: text.replace(/\\n{2,}/g,'\\n').slice(0,2200),
    objective: obj ? obj.getAttribute('data-cb-objective') : null,
    buttons: root ? [...root.querySelectorAll('button')].map(b=>({label:(b.innerText||'').trim(),disabled:b.disabled})).filter(b=>b.label) : [],
    inputs: root ? [...root.querySelectorAll('input,textarea,select,[contenteditable=true]')].map(i=>({tag:i.tagName,type:i.type,role:i.getAttribute('role'),label:i.getAttribute('aria-label'),ph:i.placeholder})) : []
  }
})()`)
save('u02k-open-course.json', { steps, opened, state, consoleErrors: console_ })
console.log(JSON.stringify({ steps, opened, state, consoleErrors: console_ }, null, 2))
cdp.close()
