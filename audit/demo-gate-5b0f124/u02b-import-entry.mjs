// U02b — what the "Import pack" control actually opens on 29bede7.
import { connectWithConsole, clickLabel, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const before = await cdp.eval('document.body.innerText.length')
try {
  await clickLabel(cdp, 'Import pack', { selector: 'button, a, [role=button]' })
} catch (e) {
  console.log(JSON.stringify({ error: e.message }))
  cdp.close(); process.exit(0)
}
await cdp.wait(1500)
const after = await cdp.json(`(() => {
  const dialogs = [...document.querySelectorAll('[role=dialog], [aria-modal=true], dialog')].map(d => ({
    label: d.getAttribute('aria-label'),
    text: (d.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0,1200),
    inputs: [...d.querySelectorAll('input,textarea')].map(i => ({ type: i.type, placeholder: i.placeholder, label: i.getAttribute('aria-label') })),
    buttons: [...d.querySelectorAll('button')].map(b => (b.innerText||'').trim()).filter(Boolean)
  }))
  return { hash: location.hash, dialogs, bodyTail: document.body.innerText.slice(-900), active: document.activeElement?.tagName + ':' + (document.activeElement?.getAttribute('aria-label')||document.activeElement?.innerText||'').slice(0,60) }
})()`)
save('u02b-import-entry.json', { before, after, consoleErrors: console_ })
console.log(JSON.stringify({ after, consoleErrors: console_ }, null, 2))
cdp.close()
