import { connectWithConsole, save } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()
const pane = () => cdp.eval(`(() => { try { return window.__HERMES_PLUGIN_SDK__.host.paneVisibility('coursebook:pane').get() } catch (e) { return 'ERR:' + e.message } })()`)

async function clickVisible(label) {
  const box = await cdp.json(`(() => {
    const hits = [...document.querySelectorAll('button, a, [role=tab]')].filter(e => ((e.innerText || '').trim() === ${JSON.stringify(label)}))
    const vis = hits.map(e => ({ e, r: e.getBoundingClientRect() })).filter(x => x.r.width > 0 && x.r.height > 0)
    if (!vis.length) return { error: 'no visible control', count: hits.length }
    const { r } = vis[0]
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, visibleCount: vis.length }
  })()`)
  if (box.error) throw new Error(JSON.stringify(box))
  await cdp.click(box.x, box.y)
  return box
}

const before = { pane: await pane(), hash: await cdp.eval('location.hash'), route: await cdp.eval("!!document.querySelector('[data-cb-route]')") }
let clicked = null
try { clicked = await clickVisible('Start a fresh run') } catch (e) { clicked = { error: e.message } }
const samples = []
for (let i = 0; i < 14; i += 1) {
  await cdp.wait(700)
  samples.push({
    t: (i + 1) * 700,
    pane: await pane(),
    hash: await cdp.eval('location.hash'),
    route: await cdp.eval("!!document.querySelector('[data-cb-route]')"),
    composer: await cdp.eval("!!document.querySelector('textarea, [contenteditable=true]')")
  })
}
const shot = await cdp.shot('audit/demo-gate-5b0f124/shots/u08-fresh-start.png')
const after = await cdp.json(`(() => ({
  hash: location.hash,
  routeMounted: !!document.querySelector('[data-cb-route]'),
  bodyText: document.body.innerText.slice(0, 800),
  notice: [...document.querySelectorAll('[role=status],[role=alert]')].map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,5)
}))()`)
save('u08-fresh-start.json', { before, clicked, samples, after, shot, consoleErrors: console_ })
console.log(JSON.stringify({ before, clicked, samples, after, shot, consoleErrors: console_ }, null, 2).slice(0, 6000))
cdp.close()
