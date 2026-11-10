import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9337')
for (const ctx of b.contexts()) for (const p of ctx.pages()) for (const f of p.frames()) {
  try {
    const has = await f.evaluate(() => Boolean(document.querySelector('[data-cb-route]')))
    if (!has) continue
    const info = await f.evaluate(() => ({
      hash: location.hash,
      routeAttrs: Object.fromEntries([...document.querySelector('[data-cb-route]').attributes].map(a=>[a.name,a.value])),
      nav: [...document.querySelectorAll('a[href], [role=tab], nav button')].slice(0,12).map(n=>({t:(n.textContent||'').trim().slice(0,18),h:n.getAttribute('href')})),
      fonts: [...document.fonts].map(f=>`${f.family} ${f.status}`).slice(0,8)
    }))
    console.log(JSON.stringify(info,null,1).slice(0,1800))
  } catch {}
}
await b.close()
