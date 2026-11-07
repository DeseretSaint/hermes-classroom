// After import: confirm the course appears in the Courses list (UI) and opens.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const steps = []
const text = () => cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return { hash: location.hash, text: r ? r.innerText.replace(/\\n{2,}/g,'\\n').slice(0,1500) : '', buttons: r ? [...r.querySelectorAll('button')].map(b=>(b.innerText||'').trim()).filter(Boolean) : [] } })()`)
await clickLabel(cdp, 'Back to the library', { selector: 'button, [role=button]' })
await cdp.wait(1000)
await clickLabel(cdp, 'Courses', { selector: 'button, [role=tab], a' })
await cdp.wait(1200)
const courses = await text()
steps.push({ step: 'courses-list', ...courses })
save('u02j-courses-list.json', { steps, consoleErrors: console_ })
console.log(JSON.stringify({ steps, consoleErrors: console_ }, null, 2))
cdp.close()
