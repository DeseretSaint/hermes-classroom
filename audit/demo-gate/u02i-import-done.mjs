// Complete the import and read back the created course in UI and backend.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const steps = []
await clickLabel(cdp, 'Import and start learning', { selector: 'button, [role=button]' })
let done = false
try {
  await cdp.waitFor("/Fresh classroom|Course created|Classroom ready|objectives|Open|Enroll/i.test(document.querySelector('[data-cb-route]')?.innerText||'')", { timeout: 30000, label: 'import result' })
  done = true
} catch (e) { steps.push({ step: 'result-wait', error: e.message }) }
await cdp.wait(1500)
const state = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  return {
    hash: location.hash,
    text: text.replace(/\\n{2,}/g,'\\n').slice(0, 2200),
    buttons: root ? [...root.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled })).filter(b=>b.label) : [],
    storedIds: [...document.querySelectorAll('[data-cb-stored-id],[data-cb-binding-id],[data-course-id]')].map(e => e.getAttribute('data-cb-stored-id')||e.getAttribute('data-cb-binding-id')||e.getAttribute('data-course-id'))
  }
})()`)
save('u02i-import-done.json', { steps, done, state, consoleErrors: console_ })
console.log(JSON.stringify({ steps, done, state, consoleErrors: console_ }, null, 2))
cdp.close()
