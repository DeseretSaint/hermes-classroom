#!/usr/bin/env node
/**
 * H-196 — mount the shipped Workshop in jsdom with real effects and real clicks.
 *
 * Why jsdom and then Chromium: the Workshop's one hard requirement is that a card's cover is the
 * pack's own visual artifact, and that image arrives through `useArtifactPreview` → `rest()` →
 * `GET /media/:id`, i.e. in an effect after mount. A server render cannot show it. So this harness
 * mounts the real `desktop/plugin.js` in jsdom (effects run, clicks run), then serialises the
 * painted subtree. `scripts/h196-workshop-shot.mjs` screenshots that markup in Chromium at the
 * required widths, modes, text scale and reduced-motion posture.
 *
 * What is real: the module, the components, the hooks, the click handling, the data. Every RPC
 * envelope and every media payload is recorded from the real backend by
 * `scripts/h196-workshop-frames.py` against a real migrated profile database. What is stubbed: the
 * transport (`ctx.rest`), which replays those recorded payloads instead of opening a socket. No
 * claim in a frame is invented; nothing is re-rendered by hand.
 */
import { readFileSync } from 'node:fs'
import { JSDOM } from 'jsdom'

const CASE = JSON.parse(readFileSync(process.env.CB196_CASE, 'utf8'))
const WIDTH = Number(CASE.width) || 1049
const MODE = CASE.mode === 'dark' ? 'dark' : 'light'
const MOTION = CASE.motion === 'reduced' ? 'reduce' : 'no-preference'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true
})
for (const key of [
  'window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'Event', 'FocusEvent',
  'KeyboardEvent', 'MouseEvent', 'CustomEvent', 'getComputedStyle', 'requestAnimationFrame',
  'cancelAnimationFrame', 'matchMedia'
]) {
  const value = key === 'matchMedia' ? undefined : dom.window[key]
  if (value === undefined) continue
  Object.defineProperty(globalThis, key, { value, configurable: true, writable: true })
}
// The one media query the module asks about. The frame's own posture decides the answer, exactly
// as the live renderer decides it from the reader's setting.
dom.window.matchMedia = (query) => ({
  matches: /prefers-reduced-motion/.test(query) ? MOTION === 'reduce' : false,
  media: query,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {}
})
globalThis.matchMedia = dom.window.matchMedia
globalThis.__CB_WIDTH__ = WIDTH
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = (await import('react')).default
const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const mod = await import('./plugin.js')

/* ── the transport: recorded payloads, never a socket ─────────────────────────────────────── */
const RPC = CASE.rpc || {}
const REST = CASE.rest || {}
let installedOnce = false
const requests = []

function replay(path, options) {
  const body = options && options.body
  requests.push(`${path}${body && body.method ? ` ${body.method}` : ''}`)
  if (path === '/runtime?profile=' || path === '/runtime') return REST['/runtime']
  if (path === '/workshop/catalog') {
    return installedOnce && CASE.catalogAfterInstall ? CASE.catalogAfterInstall : CATALOG
  }
  if (path === '/workshop/install') {
    installedOnce = true
    return REST['/workshop/install']
  }
  if (path === '/rpc' && body && body.method) {
    const envelope = RPC[body.method]
    if (envelope) return envelope
    return {
      ok: false,
      contract_version: body.contract_version,
      operation_id: body.operation_id,
      error: { code: 'NOT_IMPLEMENTED', category: 'contract', message: `no recorded ${body.method}` }
    }
  }
  if (Object.prototype.hasOwnProperty.call(REST, path)) return REST[path]
  return { ok: false, code: 'NOT_FOUND', message: `no recorded route ${path}` }
}

const ctx = {
  rest: async (path, options) => replay(String(path), options),
  register: () => {},
  onDispose: () => {}
}
mod.default.register(ctx)

/* ── mount ────────────────────────────────────────────────────────────────────────────────── */
const scopeStyle = mod.cbScopeStyle(MODE)
const scope = document.createElement('div')
scope.setAttribute('data-cb-scope', MODE)
scope.setAttribute('data-cb-motion', MOTION === 'reduce' ? 'reduced' : 'full')
for (const [name, value] of Object.entries(scopeStyle)) {
  if (name.startsWith('--')) scope.style.setProperty(name, String(value))
  else scope.style[name] = value
}
const route = document.createElement('div')
route.setAttribute('data-cb-route', '/coursebook')
Object.assign(route.style, {
  padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem',
  minHeight: '0',
  boxSizing: 'border-box'
})
scope.appendChild(route)
document.body.appendChild(scope)

const IMPLEMENTED = new Set(CASE.implemented || [])
const CATALOG = CASE.catalog
const prefs = CASE.prefs || { favorites: [], categories: {} }

const item = (packId) => (CATALOG.items || []).find((entry) => entry.pack_id === packId) || null

function view() {
  if (CASE.view === 'workshop') {
    return React.createElement(mod.WorkshopView, {
      implemented: IMPLEMENTED,
      createOpen: false,
      canSyllabus: true,
      canImport: true,
      onStartSyllabus: () => {},
      onStartImport: () => {},
      onOpenCourse: () => {},
      onEmptyChange: () => {}
    })
  }
  if (CASE.view === 'detail') {
    return React.createElement(mod.WorkshopDetail, {
      item: item(CASE.pack_id),
      layout: mod.cbLayoutFor(WIDTH),
      motion: mod.cbMotionFor(MOTION === 'reduce' ? 'reduced' : 'full'),
      onBack: () => {},
      onInstall: () => {},
      onContinue: () => {},
      busy: false,
      favorite: (prefs.favorites || []).indexOf(CASE.pack_id) >= 0,
      onFavorite: () => {},
      userCategory: (prefs.categories || {})[CASE.pack_id] || null,
      onCategory: () => {}
    })
  }
  if (CASE.view === 'library') {
    return React.createElement(mod.LibraryView, {
      implemented: IMPLEMENTED,
      createOpen: false,
      onOpen: () => {},
      onStartSyllabus: () => {},
      onStartImport: () => {}
    })
  }
  throw new Error(`unknown view ${CASE.view}`)
}

const root = createRoot(route)
await act(async () => {
  root.render(view())
})
// Effects that resolve after the first paint (the catalogue read, the media preview).
for (let pass = 0; pass < 4; pass += 1) {
  await act(async () => {
    await new Promise((done) => setTimeout(done, 40))
  })
}

/* ── the frame's own interaction, performed on the shipped controls ───────────────────────── */
const notes = []
const click = async (selector, note) => {
  const node = document.querySelector(selector)
  if (!node) {
    notes.push(`missing: ${selector}`)
    return false
  }
  await act(async () => {
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  for (let pass = 0; pass < 3; pass += 1) {
    await act(async () => {
      await new Promise((done) => setTimeout(done, 40))
    })
  }
  notes.push(note || `clicked ${selector}`)
  return true
}

/** Press a shipped control by its visible label, the way a reader finds it. */
const clickText = async (label, note) => {
  const wanted = String(label).trim()
  const node = Array.from(document.querySelectorAll('button')).find(
    (candidate) => (candidate.textContent || '').replace(/\s+/g, ' ').trim() === wanted
  )
  if (!node) {
    notes.push(`missing label: ${wanted}`)
    return false
  }
  await act(async () => {
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  for (let pass = 0; pass < 3; pass += 1) {
    await act(async () => {
      await new Promise((done) => setTimeout(done, 40))
    })
  }
  notes.push(note || `pressed "${wanted}"`)
  return true
}

for (const action of CASE.actions || []) {
  if (action.click) await click(action.click, action.note)
  if (action.clickText) await clickText(action.clickText, action.note)
  if (action.wait) await act(async () => { await new Promise((done) => setTimeout(done, action.wait)) })
}

const painted = scope.outerHTML
process.stdout.write(JSON.stringify({ html: painted, notes, requests }))
