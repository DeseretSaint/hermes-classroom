/** H-64 live-control inventory helpers (isolated Desktop window, CDP 9337). */
import { connect } from './cb015-lib.mjs'

export const ROUTE = '[data-cb-route]'

export async function attach(port = '9337') {
  return connect(port)
}

export async function waitRoute(cdp, timeout = 20000) {
  await cdp.waitFor(`!!document.querySelector('${ROUTE}')`, { timeout, label: 'coursebook route' })
  await cdp.wait(700)
}

export async function reset(cdp) {
  await cdp.eval(`location.hash = '#/coursebook'`)
  await cdp.wait(400)
  await waitRoute(cdp).catch(() => {})
  await cdp.wait(600)
  // Leave a course detail / create flow if one is open.
  for (const label of ['All courses', 'Cancel']) {
    const box = await find(cdp, label)
    if (box && !box.disabled) {
      await cdp.click(box.x, box.y)
      await cdp.wait(900)
    }
  }
  const seg = await find(cdp, 'Courses')
  if (seg) {
    await cdp.click(seg.x, seg.y)
    await cdp.wait(900)
  }
}

export function findExpr(label, { exact = true, selector = null } = {}) {
  const cmp = exact ? 'l === wanted' : 'l.includes(wanted)'
  const list = selector || `${ROUTE}`
  return `(() => {
    const root = document.querySelector(${JSON.stringify(list)}) || document.body
    const wanted = ${JSON.stringify(label)}
    const nodes = [...root.querySelectorAll('button,a[href],[role="tab"],[role="option"],[role="menuitem"],[role="switch"],summary,label[for]')]
    const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 1 && b.height > 1 }
    const el = nodes.find((e) => { if (!vis(e)) return false; const l = (e.getAttribute('aria-label') || e.innerText || '').replace(/\\s+/g, ' ').trim(); return ${cmp} })
    if (!el) return null
    el.scrollIntoView({ block: 'center' })
    const b = el.getBoundingClientRect()
    return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: Math.round(b.width), h: Math.round(b.height),
      label: (el.getAttribute('aria-label') || el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
      tag: el.tagName, role: el.getAttribute('role'), disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true' }
  })()`
}

export async function find(cdp, label, opts = {}) {
  return cdp.json(findExpr(label, opts))
}

export async function click(cdp, label, opts = {}) {
  const box = await find(cdp, label, opts)
  if (!box) throw new Error(`control not found: ${label}`)
  if (box.disabled) return { ...box, skipped: 'disabled' }
  await cdp.click(box.x, box.y)
  await cdp.wait(opts.wait ?? 1000)
  return box
}

export function snapshotExpr() {
  return `(() => {
    const r = document.querySelector('${ROUTE}')
    const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 1 && b.height > 1 }
    const controls = r ? [...r.querySelectorAll('button,a[href],[role="tab"],[role="option"],[role="menuitem"],[role="switch"],input,select,textarea')].filter(vis)
      .map((e, i) => ({
        index: i,
        tag: e.tagName,
        role: e.getAttribute('role'),
        label: (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('placeholder') || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
        disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true' || (e.closest('fieldset[disabled]') !== null),
        pressed: e.getAttribute('aria-pressed'),
        selected: e.getAttribute('aria-selected'),
        x: Math.round(e.getBoundingClientRect().x + e.getBoundingClientRect().width / 2),
        y: Math.round(e.getBoundingClientRect().y + e.getBoundingClientRect().height / 2)
      })) : []
    return {
      hash: location.hash,
      mounted: !!r,
      destination: r ? r.getAttribute('data-cb-destination') : null,
      text: r ? r.innerText.replace(/\\s+/g, ' ').slice(0, 4000) : document.body.innerText.replace(/\\s+/g, ' ').slice(0, 1200),
      controls,
      dialogs: [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].filter(vis).map((d) => d.innerText.replace(/\\s+/g, ' ').slice(0, 400)),
      notices: [...document.querySelectorAll('[role="alert"],[role="status"],[aria-live]')].filter(vis).map((d) => (d.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean)
    }
  })()`
}

export async function snapshot(cdp) {
  return cdp.json(snapshotExpr())
}

export function digest(text) {
  let h = 0
  for (let i = 0; i < text.length; i += 1) { h = (h * 31 + text.charCodeAt(i)) | 0 }
  return String(h)
}
