import { chromium } from 'playwright'
for (const port of [9371, 9357]) {
  try {
    const b = await chromium.connectOverCDP(`http://127.0.0.1:${port}`)
    let found = false
    for (const ctx of b.contexts()) for (const p of ctx.pages()) {
      const url = p.url()
      const has = await p.evaluate(()=>Boolean(document.querySelector('[data-cb-route]'))).catch(()=>false)
      console.log(port, url.slice(0,60), 'route=', has)
      if (has) found = true
    }
    await b.close()
    if (!found) console.log(port, 'no route')
  } catch (e) { console.log(port, 'ERR', String(e).slice(0,60)) }
}
