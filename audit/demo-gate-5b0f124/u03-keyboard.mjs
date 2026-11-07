// U03 (final) — keyboard-only route entry, focus visibility, accessible names, keyboard activation.
import { connectWithConsole, save, press } from './lib.mjs'
const { cdp, console_ } = await connectWithConsole()

const focusState = () => cdp.json(`(() => {
  const el = document.activeElement
  if (!el) return null
  const s = getComputedStyle(el)
  const r = el.getBoundingClientRect()
  return {
    tag: el.tagName, role: el.getAttribute('role'),
    name: (el.getAttribute('aria-label') || el.innerText || el.placeholder || '').trim().replace(/\\s+/g,' ').slice(0,90),
    inRoute: !!el.closest('[data-cb-route]'),
    focusVisible: el.matches(':focus-visible'),
    outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0,
    shadow: s.boxShadow !== 'none',
    visible: r.width > 1 && r.height > 1
  }
})()`)

// 1. Keyboard-only entry: Tab from the shell to the Coursebook entry, Enter to open.
await cdp.eval(`location.hash = '#/'`); await cdp.wait(1800)
await cdp.eval(`document.body.focus()`)
const walk = []
let reached = null
for (let i = 0; i < 200; i += 1) {
  await cdp.key('Tab'); await cdp.wait(110)
  const s = await focusState()
  if (!s) continue
  walk.push(s)
  if (/^(Open Coursebook|Coursebook)$/.test(s.name)) { reached = { tabs: i + 1, state: s }; break }
}
const beforeHash = await cdp.eval('location.hash')
let keyboardRoute = { reached: Boolean(reached), beforeHash }
if (reached) {
  await press(cdp, 'Enter')
  await cdp.wait(1800)
  const afterHash = await cdp.eval('location.hash')
  const mounted = await cdp.eval("Boolean(document.querySelector('[data-cb-route]'))")
  keyboardRoute = { ...keyboardRoute, afterHash, mounted, activatedBy: 'Enter', tabs: reached.tabs, focusAfter: (await focusState()) }
}

// 2. Tab through the route (starting at its first control) and record every stop.
const focusedFirst = await cdp.eval(`(() => {
  const root = document.querySelector('[data-cb-route]')
  if (!root) return false
  const el = [...root.querySelectorAll('button, a, input, textarea, select, [tabindex]')]
    .find(e => { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1 && !e.disabled && e.tabIndex >= 0 })
  if (!el) return false
  el.focus(); return true
})()`)
const routeWalk = []
for (let i = 0; i < 18; i += 1) {
  const s = await focusState()
  if (s) routeWalk.push({ tab: i, ...s })
  await cdp.key('Tab'); await cdp.wait(110)
}

// 3. Keyboard activation inside the route: open the imported course with Enter.
let activation = null
if (focusedFirst) {
  const target = await cdp.eval(`(() => {
    const root = document.querySelector('[data-cb-route]')
    const el = [...root.querySelectorAll('button, a')].find(e => { const r = e.getBoundingClientRect(); return r.width>1 && r.height>1 && !e.disabled && /^(Resume lesson|Open|Preview)$/.test((e.innerText||'').trim()) })
    if (!el) return null
    el.focus(); return (el.innerText||'').trim()
  })()`)
  await cdp.wait(150)
  const textBefore = await cdp.eval("(document.querySelector('[data-cb-route]')?.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0,300)")
  await press(cdp, 'Enter')
  await cdp.wait(2000)
  const after = await cdp.json(`(() => { const r=document.querySelector('[data-cb-route]'); return { hash: location.hash, text: (r?r.innerText:'').replace(/\\n{2,}/g,'\\n').slice(0,600), route: r?r.getAttribute('data-cb-route'):null } })()`)
  activation = { target, textBefore, hashAfter: after.hash, route: after.route, textAfter: after.text }
}

// 4. AX names for interactive controls.
const ax = await cdp.send('Accessibility.getFullAXTree')
const roles = ['button', 'link', 'textbox', 'checkbox', 'tab', 'radio', 'combobox']
const unnamed = ax.nodes.filter((n) => roles.includes(n.role?.value) && !(n.name?.value || '').trim()).slice(0, 12).map((n) => ({ role: n.role?.value, backend: n.backendDOMNodeId }))
const namedCount = ax.nodes.filter((n) => roles.includes(n.role?.value) && (n.name?.value || '').trim()).length

const result = {
  scenario: 'U03', name: 'keyboard-only route path, focus, names',
  sidebarWalkTabs: walk.length, sidebarReached: reached, keyboardRoute,
  focusedFirstRouteControl: focusedFirst, routeWalk, activation,
  ax: { namedControls: namedCount, unnamedControls: unnamed.length, unnamedSample: unnamed },
  consoleErrors: console_
}
save('u03-keyboard.json', result)
console.log(JSON.stringify({ sidebarReached: reached, keyboardRoute, focusedFirst, routeWalk, activation, ax: result.ax, consoleErrors: console_ }, null, 2))
cdp.close()
