// U03 probe — which keyboard activation actually opens the route?
import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const out = { trials: [] }

const focusByName = (name) => cdp.eval(`(() => {
  const el = [...document.querySelectorAll('button, a, [role=tab], [role=link]')].find(e => ((e.innerText||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ')) === ${JSON.stringify(name)})
  if (!el) return null
  el.focus()
  return { tag: el.tagName, role: el.getAttribute('role'), hash: location.hash }
})()`)

await cdp.eval(`location.hash = '#/'`); await cdp.wait(1500)

for (const [name, key] of [['Coursebook', 'Enter'], ['Coursebook', 'Space'], ['Open Coursebook', 'Enter']]) {
  const focused = await focusByName(name)
  if (!focused) { out.trials.push({ name, key, found: false }); continue }
  await cdp.wait(120)
  await cdp.key(key)
  await cdp.wait(1800)
  const after = await cdp.json(`({ hash: location.hash, mounted: Boolean(document.querySelector('[data-cb-route]')), route: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-route') || null, active: (document.activeElement?.innerText||document.activeElement?.getAttribute('aria-label')||'').trim().slice(0,60), hash2: location.hash })`)
  out.trials.push({ name, key, found: true, focused, after })
  if (after.mounted) break
  await cdp.eval(`location.hash = '#/'`); await cdp.wait(1200)
}
out.consoleErrors = console_
save('u03b-activation.json', out)
console.log(JSON.stringify(out, null, 2))
cdp.close()
