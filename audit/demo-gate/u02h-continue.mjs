// Continue past preview, choose import mode, and complete the import.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const steps = []

const snap = () => cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  return {
    text: text.replace(/\\n{2,}/g,'\\n').slice(0, 2200),
    buttons: root ? [...root.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled })).filter(b=>b.label) : [],
    radios: root ? [...root.querySelectorAll('[role=radio], input[type=radio]')].map(r => ({ label: (r.getAttribute('aria-label')||r.parentElement?.innerText||'').trim().slice(0,80), checked: r.getAttribute('aria-checked')||r.checked })) : []
  }
})()`)

steps.push({ step: 'before-continue', ...(await snap()) })
await clickLabel(cdp, 'Continue', { selector: 'button, [role=button]' })
await cdp.wait(1200)
const afterContinue = await snap()
steps.push({ step: 'after-continue', ...afterContinue })
save('u02h-after-continue.json', { steps, consoleErrors: console_ })
console.log(JSON.stringify({ steps, consoleErrors: console_ }, null, 2))
cdp.close()
