import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()

async function clickVisible(label) {
  const box = await cdp.json(`(() => {
    const all = [...document.querySelectorAll('button, a, [role=tab]')]
    const hits = all.filter(e => ((e.innerText || '').trim() === ${JSON.stringify(label)}))
    const visible = hits.map(e => { const r = e.getBoundingClientRect(); return { e, r } }).filter(x => x.r.width > 0 && x.r.height > 0)
    if (!visible.length) return { error: 'no visible control', count: hits.length }
    const { r } = visible[0]
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, visibleCount: visible.length, total: hits.length }
  })()`)
  if (box.error) throw new Error(JSON.stringify(box))
  await cdp.click(box.x, box.y)
  return box
}

await cdp.eval(`(location.hash = '#/coursebook', true)`)
await cdp.wait(1000)
// ensure on overview of the course
try { await clickVisible('Open') } catch (e) {}
await cdp.wait(1800)
const steps = []
for (const label of ['Open this section']) {
  try { steps.push({ label, ...(await clickVisible(label)) }) } catch (e) { steps.push({ label, error: e.message }) }
  await cdp.wait(2500)
}
const state = await cdp.json(`(() => { const r = document.querySelector('[data-cb-route]'); return {
  hash: location.hash,
  text: r ? r.innerText.slice(0,2600) : null,
  buttons: r ? [...r.querySelectorAll('button')].map(b => ({ label: (b.innerText||'').trim(), disabled: b.disabled, w: Math.round(b.getBoundingClientRect().width) })).filter(b=>b.label) : []
} })()`)
save('u07-section.json', { steps, state, consoleErrors: console_ })
console.log(JSON.stringify({ steps, state, consoleErrors: console_ }, null, 2).slice(0, 6000))
cdp.close()
