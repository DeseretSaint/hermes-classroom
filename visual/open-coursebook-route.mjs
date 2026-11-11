import { chromium } from 'playwright'
const b = await chromium.connectOverCDP('http://127.0.0.1:9391')
const p = b.contexts()[0].pages()[0]
await p.waitForTimeout(7000)
await p.evaluate(() => {
  const cur = JSON.parse(localStorage.getItem('hermes.desktop.pluginDecisions.v2') || '{}')
  cur['coursebook'] = true
  localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify(cur))
  location.hash = '#/coursebook'
})
await p.waitForTimeout(10000)
const s = await p.evaluate(() => ({
  href: location.href,
  route: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-route') || null,
  v3: !!document.querySelector('[data-cb-v3]'),
  scope: document.querySelector('[data-cb-scope]')?.getAttribute('data-cb-scope') || null
}))
console.log('PRIME', JSON.stringify(s))
await b.close()
