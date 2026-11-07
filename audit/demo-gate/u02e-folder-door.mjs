// Drive the folder grant: click "Choose folder…" and read what the host door returns.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
await clickLabel(cdp, 'Choose folder…', { selector: 'button, a, [role=button]' })
await cdp.wait(2000)
const after = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? root.innerText : ''
  const btns = [...document.querySelectorAll('button')].map(b => (b.innerText||b.getAttribute('aria-label')||'').trim()).filter(Boolean)
  const dialogs = [...document.querySelectorAll('[role=dialog],[aria-modal=true]')].map(d => ({ role: d.getAttribute('role'), label: d.getAttribute('aria-label'), text: (d.innerText||'').slice(0,1500) }))
  return {
    routeText: text.replace(/\\n{2,}/g,'\\n').slice(0,2500),
    dialogCount: dialogs.length,
    dialogs,
    buttons: btns.filter(t => /zip|folder|choose|grant|import|cancel|preview/i.test(t)).slice(0,25),
    fileTree: /Show gitignored files|Refresh tree/.test(document.body.innerText)
  }
})()`)
save('u02e-folder-door.json', { after, consoleErrors: console_ })
console.log(JSON.stringify({ after, consoleErrors: console_ }, null, 2))
cdp.close()
