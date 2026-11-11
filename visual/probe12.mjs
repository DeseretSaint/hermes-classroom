import { chromium } from 'playwright'
import { execSync } from 'node:child_process'
const out = execSync("ss -ltnp 2>/dev/null | grep electron", {encoding:'utf8'})
const ports=[...new Set(out.split('\n').map(l=>(l.match(/127\.0\.0\.1:(\d+)/)||[])[1]).filter(Boolean).map(Number))]
for (const port of ports.sort((a,b)=>b-a)) {
  try {
    const b = await chromium.connectOverCDP(`http://127.0.0.1:${port}`)
    const s = await b.newBrowserCDPSession()
    for (const ctx of b.contexts()) for (const p of ctx.pages()) {
      const has = await p.evaluate(()=>Boolean(document.querySelector('[data-cb-route]'))).catch(()=>false)
      let bounds=null
      try {
        const {windowId} = await s.send('Browser.getWindowForTarget')
        bounds = (await s.send('Browser.getWindowBounds',{windowId})).bounds
      } catch(e) { bounds={err:String(e.message).slice(0,40)} }
      console.log(port, p.url().slice(0,42), 'route=',has, JSON.stringify(bounds))
    }
    await b.close()
  } catch(e){ console.log(port,'ERR',String(e).slice(0,50)) }
}
