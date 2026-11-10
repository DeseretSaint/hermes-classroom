import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
for (const ctx of b.contexts()) for (const p of ctx.pages()) {
  console.log('PAGE', p.url().slice(0,90))
  for (const f of p.frames()) {
    try {
      const s = await f.evaluate(() => ({
        url: location.href.slice(0,90),
        hash: location.hash,
        route: !!document.querySelector('[data-cb-route]'),
        pane: !!document.querySelector('[data-cb-pane], [data-coursebook], #coursebook'),
        body: document.body ? document.body.innerText.slice(0,80).replace(/\n/g,' | ') : ''
      }))
      console.log(' FRAME', JSON.stringify(s))
    } catch(e) { console.log(' FRAME err', String(e).slice(0,60)) }
  }
}
await b.close()
