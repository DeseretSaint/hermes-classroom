/**
 * Gap pass 3 — DOM-only, no screenshot dependency.
 *
 * The shared audit window reports "tile memory limits exceeded" and has crashed its renderer
 * once, so painting is unreliable while the DOM stays correct. Focus, roles, copy, layout
 * boxes and text overflow are all readable without a frame buffer; screenshots are recorded
 * here as best-effort and marked invalid when blank.
 *
 * Usage: CB015_CDP_PORT=9351 node scripts/audit-ux-gaps3.mjs
 */
import { writeFileSync, mkdirSync, statSync } from 'node:fs'
import { attach, measure, setMode, setRootText, clearRootText, setForcedColors, setViewportCss, tabWalk, esc, ROUTE } from './audit-ux-lib.mjs'

const PORT = process.env.CB015_CDP_PORT || '9351'
const SHOTS = 'docs/a11y-shots'
mkdirSync(SHOTS, { recursive: true })
const setFault = (obj) => writeFileSync('audit/ux/fault.json', `${JSON.stringify(obj, null, 2)}\n`)
const out = { port: PORT, at: new Date().toISOString(), methods: 'DOM only; screenshots best-effort' }
const wait = (cdp, ms) => cdp.wait(ms)
const race = (p, ms) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms))])

async function info(cdp) {
  return cdp.json(`(() => {
    const r = document.querySelector('${ROUTE}')
    return { hash: location.hash, route: !!r, text: (r ? r.innerText : '').slice(0, 2500), font: getComputedStyle(document.documentElement).fontSize }
  })()`)
}
async function waitFor(cdp, needle, ms = 12000) {
  const t0 = Date.now(); let s = null
  while (Date.now() - t0 < ms) {
    s = await info(cdp)
    if (s.route && s.text.includes(needle)) return s
    await wait(cdp, 300)
  }
  return s
}
async function ensure(cdp, needle) {
  for (let i = 0; i < 4; i += 1) {
    const s = await info(cdp)
    if (s.route && s.text.includes(needle)) return s
    await cdp.eval(`localStorage.setItem('hermes.desktop.pluginDecisions.v2', JSON.stringify({ coursebook: true }))`)
    await cdp.eval(`location.hash = '#/coursebook'`)
    await wait(cdp, 700)
    const t = await waitFor(cdp, needle, 3000)
    if (t.route && t.text.includes(needle)) return t
  }
  return null
}
const click = (cdp, label) => cdp.eval(`(() => {
  const root = document.querySelector('${ROUTE}') || document.body
  const el = [...root.querySelectorAll('button,a,[role="tab"],[role="option"],[role="menuitem"]')]
    .find((e) => (e.innerText||'').replace(/\\s+/g,' ').trim() === ${JSON.stringify(label)})
  if (!el) return false
  el.click(); return true
})()`)
async function shot(cdp, name) {
  try {
    const d = await race(cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: false }), 9000)
    const path = `${SHOTS}/${name}.png`
    writeFileSync(path, Buffer.from(d.data, 'base64'))
    const size = statSync(path).size
    return { path, size, valid: size >= 5000 }
  } catch (e) { return { path: null, size: 0, valid: false, error: e.message } }
}
async function fill(cdp, text) {
  return cdp.eval(`(() => {
    const input = document.querySelector('#cb-attempt-answer')
    if (!input) return false
    const proto = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, ${JSON.stringify(text)})
    input.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  })()`)
}
async function openSection(cdp) {
  await ensure(cdp, 'All courses')
  await wait(cdp, 400)
  await cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const title = [...root.querySelectorAll('*')].find((el) => (el.innerText||'').includes('Japanese affection'))
    let node = title
    for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
      const b = [...node.querySelectorAll('button')].find((x) => (x.innerText||'').trim() === 'Open')
      if (b) { b.click(); return true }
    }
    return false
  })()`)
  await wait(cdp, 1500)
  await ensure(cdp, 'Textbook')
  await click(cdp, 'Textbook')
  await wait(cdp, 800)
  await click(cdp, 'Open section')
  return waitFor(cdp, 'CURRENT CHECK', 10000)
}

const cdp = await attach(PORT)
setForcedColors(cdp, false)
setFault({})
await setMode(cdp, 'dark')
await clearRootText(cdp)
await setViewportCss(cdp, 1280, 900)
await wait(cdp, 400)

// ── A. grader unavailable ──────────────────────────────────────────────────────────────────
setFault({ rpc: { 'attempt.submit': { __error: {
  code: 'GRADER_UNAVAILABLE', category: 'capability',
  message: 'The grader is unavailable, so nothing was recorded. Retry, edit, or override.',
  retryable: true, details: { check_id: 'audit' }
} } } })
let s = await openSection(cdp)
out.graderReached = !!(s && s.text.includes('CURRENT CHECK'))
out.graderBefore = await cdp.json(`(() => {
  const r = document.querySelector('${ROUTE}')
  const submit = [...r.querySelectorAll('button')].find(b => (b.innerText||'').trim() === 'Submit answer')
  const block = (r.innerText.split('ATTEMPTS ON THIS SECTION')[1] || '')
  return { submitDisabled: submit ? submit.disabled : null, rows: (block.match(/Cold attempt/g) || []).length }
})()`)
out.graderFilled = await fill(cdp, 'A failing grader attempt (DOM pass).')
await wait(cdp, 250)
out.graderClicked = await click(cdp, 'Submit answer')
const t0 = Date.now(); let g = null
while (Date.now() - t0 < 12000) {
  g = await cdp.json(`(() => {
    const r = document.querySelector('${ROUTE}')
    if (!r) return { route: false }
    const block = (r.innerText.split('ATTEMPTS ON THIS SECTION')[1] || '')
    return {
      route: true,
      text: r.innerText.slice(0, 2000),
      buttons: [...r.querySelectorAll('button')].map(b => (b.innerText||'').replace(/\\s+/g,' ').trim()).filter(Boolean),
      submitDisabled: (() => { const b = [...r.querySelectorAll('button')].find(x => (x.innerText||'').trim() === 'Submit answer'); return b ? b.disabled : null })(),
      rows: (block.match(/Cold attempt/g) || []).length,
      alerts: [...r.querySelectorAll('[role="alert"], [role="status"], [aria-live]')].map(e => (e.innerText||'').slice(0, 200))
    }
  })()`)
  if (g.route && /couldn.t grade|grader is unavailable|needs_retry|Retry grading|Move on/i.test(g.text)) break
  await wait(cdp, 400)
}
out.graderAfter = g
out.graderShot = await shot(cdp, 'attempt-grader-unavailable-dark')
console.log('A grader:', out.graderReached, 'clicked', out.graderClicked, 'matched', !!(g && /couldn.t grade|needs_retry|Retry/i.test(g.text || '')), 'rows', out.graderBefore.rows, '->', g && g.rows)
setFault({})
await wait(cdp, 400)

// ── B. delete-confirmation dialog ─────────────────────────────────────────────────────────
async function openDelete(cdp) {
  await ensure(cdp, 'All courses')
  await wait(cdp, 500)
  const trigger = await cdp.eval(`(() => {
    const root = document.querySelector('${ROUTE}')
    const menu = [...root.querySelectorAll('button')].find((b) => /^actions for/i.test((b.getAttribute('aria-label')||'').trim()))
    if (!menu) return null
    menu.focus()
    const before = { name: menu.getAttribute('aria-label'), focused: document.activeElement === menu }
    menu.click()
    return before
  })()`)
  await wait(cdp, 900)
  const items = await cdp.json(`[...document.querySelectorAll('[role="menuitem"], [role="menu"] button')].map(b => (b.innerText||'').trim()).filter(Boolean)`)
  const clicked = await cdp.eval(`(() => {
    const b = [...document.querySelectorAll('[role="menuitem"], [role="menu"] button, button')]
      .find((x) => /^delete enrollment/i.test((x.innerText||'').replace(/\\s+/g,' ').trim()))
    if (!b) return null
    b.click(); return (b.innerText||'').trim()
  })()`)
  await wait(cdp, 1200)
  return { trigger, items, clicked }
}
out.deleteFlow = await openDelete(cdp)
const dialogExpr = `(() => {
  const d = [...document.querySelectorAll('[role="dialog"], dialog')].find(x => x.getBoundingClientRect().width > 0)
  if (!d) return { open: false }
  const f = document.activeElement
  return {
    open: true, tag: d.tagName, role: d.getAttribute('role'), modal: d.getAttribute('aria-modal'),
    label: d.getAttribute('aria-label'), labelledby: d.getAttribute('aria-labelledby'), descby: d.getAttribute('aria-describedby'),
    text: (d.innerText||'').slice(0, 900),
    focusInside: d.contains(f),
    focus: { tag: f.tagName, name: (f.getAttribute('aria-label') || f.innerText || '').trim().slice(0, 70) },
    buttons: [...d.querySelectorAll('button')].map(b => (b.innerText||'').replace(/\\s+/g,' ').trim()).filter(Boolean),
    routeAriaHidden: document.querySelector('${ROUTE}')?.getAttribute('aria-hidden') ?? null,
    tabbables: [...d.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter(e => e.getBoundingClientRect().width > 0).length
  }
})()`
out.dialog = await cdp.json(dialogExpr)
out.dialogShot = await shot(cdp, 'delete-confirm-dark')
const walk = await tabWalk(cdp, 14)
out.dialogWalk = {
  stops: walk.stops.map(x => `${x.tag}:${x.name}`),
  trap: walk.trap,
  endInside: await cdp.eval(`(() => { const d = [...document.querySelectorAll('[role="dialog"], dialog')].find(x => x.getBoundingClientRect().width > 0); return d ? d.contains(document.activeElement) : null })()`)
}
const escRes = await esc(cdp)
await wait(cdp, 700)
out.escape = {
  before: escRes.before, after: escRes.after,
  dialogStillOpen: await cdp.eval(`!![...document.querySelectorAll('[role="dialog"], dialog')].find(x => x.getBoundingClientRect().width > 0)`),
  focusReturnedToTrigger: await cdp.eval(`/^actions for/i.test((document.activeElement.getAttribute?.('aria-label')||'').trim())`),
  activeName: await cdp.eval(`(document.activeElement.getAttribute?.('aria-label') || document.activeElement.innerText || '').trim().slice(0,70)`)
}
out.escapeShot = await shot(cdp, 'delete-after-escape-dark')
console.log('B dialog:', JSON.stringify(out.dialog), 'walk', JSON.stringify(out.dialogWalk), 'escape', JSON.stringify(out.escape))

// ── C. dialog at 200% text ────────────────────────────────────────────────────────────────
await setRootText(cdp, 32)
await wait(cdp, 400)
out.deleteFlow200 = await openDelete(cdp)
out.dialog200 = await cdp.json(dialogExpr)
const dm = await measure(cdp)
out.dialog200Measure = { rootFont: dm.rootFont, viewport: dm.viewport, overflowX: dm.overflowX, clipped: dm.clipped, smallTargets: dm.smallTargets }
out.dialog200Shot = await shot(cdp, 'delete-confirm-text200')
await esc(cdp)
await clearRootText(cdp)
setFault({})
console.log('C dialog200:', out.dialog200.open, 'focusInside', out.dialog200.focusInside, 'clipped', dm.clipped.length, 'ovX', dm.overflowX)

writeFileSync('audit/ux/attempt-dialog.json', `${JSON.stringify(out, null, 2)}\n`)
console.log('wrote audit/ux/attempt-dialog.json')
cdp.close()
