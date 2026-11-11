import { chromium } from 'playwright'
import { execSync } from 'node:child_process'
const out = execSync("ss -ltnp 2>/dev/null | grep electron", {encoding:'utf8'})
const ports=[...new Set(out.split('\n').map(l=>(l.match(/127\.0\.0\.1:(\d+)/)||[])[1]).filter(Boolean).map(Number))]
for (const port of ports.sort((a,b)=>b-a)) {
  try {
    const b = await chromium.connectOverCDP(`http://127.0.0.1:${port}`)
    const pages = b.contexts().flatMap(c=>c.pages())
    console.log(port, pages.map(p=>p.url().slice(0,50)))
    for (const p of pages) {
      const u = p.url()
      if (u.includes('peer=1') || u.endsWith('#/')) {
        await p.evaluate(()=>window.close()).catch(()=>{})
        await p.close().catch(()=>{})
        console.log('closed', u.slice(0,50))
      }
    }
    await b.close()
  } catch(e){ console.log(port,'ERR',String(e).slice(0,40)) }
}
