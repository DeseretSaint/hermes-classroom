// U01 — /coursebook route live. Click the sidebar entry the way a user does, then read the route.
import { connectWithConsole, clickLabel, save } from './lib.mjs'

const { cdp, console_ } = await connectWithConsole()
const steps = []

// 1. Prove we start on a non-coursebook route.
const before = await cdp.json(`({ hash: location.hash, route: document.querySelector('[data-cb-route]')?.getAttribute('data-cb-route') || null })`)
steps.push({ step: 'start', ...before })

// 2. Click the sidebar Coursebook entry (a real pointer click on its geometry).
const clicked = await clickLabel(cdp, 'Coursebook', { selector: 'button, a, [role=link]' })
steps.push({ step: 'click-sidebar-coursebook', ...clicked })

// 3. Wait for the route element CB-QA-09 says never mounted.
let mounted = false
let waited = null
try {
  waited = await cdp.waitFor("document.querySelector('[data-cb-route]')", { timeout: 20000, label: 'data-cb-route' })
  mounted = true
} catch (error) {
  steps.push({ step: 'route-wait', error: error.message })
}

await cdp.wait(1200)
const state = await cdp.json(`(() => {
  const root = document.querySelector('[data-cb-route]')
  const text = root ? (root.innerText || '') : ''
  const headings = root ? [...root.querySelectorAll('h1,h2,h3,[role=heading]')].map(h => (h.innerText||'').trim()).filter(Boolean) : []
  const buttons = root ? [...root.querySelectorAll('button')].map(b => ({ label: (b.innerText||b.getAttribute('aria-label')||'').trim(), disabled: b.disabled })).filter(b => b.label) : []
  const cards = root ? [...root.querySelectorAll('[data-cb-course-id], [data-course-id], [data-cb-course-card], li, [role=listitem]')].map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,20) : []
  const emptyCopy = (text.match(/(No courses[^\\n]*|Nothing here[^\\n]*|No packs[^\\n]*|Start[^\\n]*)/i) || [null])[0]
  return {
    hash: location.hash,
    route: root ? root.getAttribute('data-cb-route') : null,
    destination: root ? root.getAttribute('data-cb-destination') : null,
    routeText: text.replace(/\\n{2,}/g, '\\n').slice(0, 2000),
    headings,
    buttons: buttons.slice(0, 30),
    cards,
    emptyCopy,
    routeBox: root ? (() => { const r = root.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) } })() : null,
    bodyHasCoursebookWords: /Coursebook|Course library|Packs|Enroll/i.test(document.body.innerText)
  }
})()`)

const result = {
  scenario: 'U01',
  name: '/coursebook route live',
  startedAt: new Date().toISOString(),
  mounted,
  waitedMs: waited,
  steps,
  state,
  consoleErrors: console_
}
save('u01-route.json', result)
console.log(JSON.stringify(result, null, 2))
cdp.close()
