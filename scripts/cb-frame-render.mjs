#!/usr/bin/env node
/**
 * cb-frame-render — mount one route destination from the SHIPPED `desktop/plugin.js`.
 *
 * `scripts/cb-frame.py --all` renders every destination in the plugin, but the lesson and classroom
 * components it already framed are pure: props in, markup out. A route destination is not pure. It
 * reads its data through `ctx.rest` / `ctx.rpc`, keeps a namespaced `ctx.storage`, and settles on
 * effects. A server render would photograph only the loading skeleton.
 *
 * So this harness does what the Desktop does: it builds a stub plugin context (rest, rpc, storage,
 * timers, register/onDispose), hands it to the module's real `register(ctx)`, mounts the *exported*
 * destination component in a real jsdom DOM with `react-dom/client`, lets effects and clicks run,
 * then serialises the painted subtree. `scripts/cb-frame.py` screenshots that markup in Chromium.
 *
 * What is real: the module, the components, the hooks, the event handling, and every fixture that
 * `cb_frame_fixtures.py` read from the real backend. What is stubbed: the transport, which replays
 * recorded payloads instead of opening a socket. Every fixture's origin is written into the frame
 * manifest; nothing here invents product data.
 *
 * Input: JSON case path in argv[2]. Output: JSON {html, notes, requests, unmapped} on stdout.
 */
import { readFileSync } from 'node:fs'
import { JSDOM } from 'jsdom'

const CASE = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const WIDTH = Number(CASE.width) || 1344
const MODE = CASE.mode === 'dark' ? 'dark' : 'light'
const MOTION = CASE.motion === 'reduced' ? 'reduce' : 'no-preference'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://coursebook.invalid/',
  pretendToBeVisual: true
})
for (const key of [
  'window', 'document', 'navigator', 'HTMLElement', 'Element', 'Node', 'Event', 'FocusEvent',
  'KeyboardEvent', 'MouseEvent', 'CustomEvent', 'MutationObserver', 'getComputedStyle',
  'requestAnimationFrame', 'cancelAnimationFrame'
]) {
  const value = key === 'getComputedStyle' ? dom.window.getComputedStyle.bind(dom.window) : dom.window[key]
  if (value === undefined) continue
  try {
    Object.defineProperty(globalThis, key, { value, configurable: true, writable: true })
  } catch (error) {
    // navigator is read-only on some Node versions; the module only reads userAgent/language.
  }
}
dom.window.matchMedia = (query) => ({
  matches: /prefers-reduced-motion/.test(query) ? MOTION === 'reduce' : false,
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {}
})
globalThis.matchMedia = dom.window.matchMedia
globalThis.requestAnimationFrame = (cb) => dom.window.setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => dom.window.clearTimeout(id)
dom.window.requestAnimationFrame = globalThis.requestAnimationFrame
dom.window.cancelAnimationFrame = globalThis.cancelAnimationFrame
globalThis.__CB_WIDTH__ = WIDTH
globalThis.__CB_TEST_WIDTH__ = String(WIDTH)
globalThis.__CB_TEST_MODE__ = MODE
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = (await import('react')).default
const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const mod = await import('./plugin.js')
const h = React.createElement

/* ── the transport: recorded payloads, never a socket ─────────────────────────────────────── */
const REST = CASE.rest || {}
const RPC = CASE.rpc || {}
const requests = []
const unmapped = []
let catalogOverride = null

function rpcEnvelope(method, body) {
  const recorded = RPC[method]
  if (recorded) return recorded
  unmapped.push(method)
  return {
    ok: false,
    contract_version: (body && body.contract_version) || 1,
    operation_id: (body && body.operation_id) || 'frame',
    error: {
      code: 'NOT_IMPLEMENTED',
      category: 'contract',
      message: `the frame harness has no recorded ${method}`
    }
  }
}

async function replay(path, options) {
  const raw = String(path)
  const base = raw.split('?')[0]
  const body = options && options.body
  const method = body && typeof body === 'object' ? body.method : null
  requests.push(method ? `${base} ${method}` : base)
  if (base === '/runtime') {
    return REST['/runtime'] || {
      ok: true,
      wire_version: 25,
      implemented_methods: CASE.implemented || [],
      single_home_host: false
    }
  }
  if (base === '/health') {
    return REST['/health'] || {
      ok: true,
      result: {
        db: { ready: true },
        plugin_version: 'frame',
        contract_version: 25,
        wire_version: 25
      }
    }
  }
  if (base === '/workshop/catalog') {
    if (catalogOverride) return catalogOverride
    return REST['/workshop/catalog'] || { ok: false, code: 'WORKSHOP_UNAVAILABLE', message: 'no recorded catalogue' }
  }
  if (base === '/workshop/install') {
    if (CASE.catalogAfterInstall) catalogOverride = CASE.catalogAfterInstall
    return REST['/workshop/install'] || { ok: false, code: 'PACK_REJECTED', message: 'no recorded install' }
  }
  if (base === '/rpc') return rpcEnvelope(method, body)
  if (Object.prototype.hasOwnProperty.call(REST, base)) return REST[base]
  unmapped.push(base)
  return { ok: false, code: 'NOT_FOUND', message: `the frame harness has no recorded ${base}` }
}

/* The host context the module expects. `storage` is the namespaced JSON store the real host
   exposes (VS Code globalState's analog); it is where Home prefs and the homework id index live. */
const store = { ...(CASE.storage || {}) }
const ctx = {
  rest: (path, options) => replay(path, options),
  rpc: (method, payload, options) => {
    const body = { method, payload, ...(options || {}) }
    return replay('/rpc', { method: 'POST', body })
  },
  storage: {
    get: (key, fallback) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : fallback),
    set: (key, value) => {
      store[key] = value
    },
    remove: (key) => {
      delete store[key]
    },
    keys: () => Object.keys(store)
  },
  setTimeout: (fn, ms) => {
    const handle = dom.window.setTimeout(fn, ms)
    return () => dom.window.clearTimeout(handle)
  },
  clearTimeout: (handle) => dom.window.clearTimeout(handle),
  setInterval: (fn, ms) => {
    const handle = dom.window.setInterval(fn, ms)
    return () => dom.window.clearInterval(handle)
  },
  clearInterval: (handle) => dom.window.clearInterval(handle),
  register: () => {},
  onDispose: () => {},
  log: () => {},
  notify: () => {},
  runAction: () => ({ ok: false, error: { code: 'STUB' } }),
  dispatchTool: async () => ({ ok: false, error: { code: 'STUB' } }),
  registerSettingsPage: () => {}
}
mod.default.register(ctx)
// `register()` starts the `/runtime` probe. A route mounted in the same tick would read the
// registry before it lands and disable every query it gates on `backendSupports(...)`; the real
// page mounts after the host has answered. Let the probe settle first.
await new Promise((done) => setTimeout(done, 120))

/* ── the route frame: the module's real CbV3Scope, which injects the product stylesheet ──────
   A hand-built wrapper with only the CSS variables would photograph the destination without
   `CB_V3_CSS`: every class-based rule (gutter, plate, shelf, type scale) would be missing. The
   route mounts CbV3Scope, so the frame mounts it too. */
const routeHost = dom.window.document.getElementById('root')
const root = createRoot(routeHost)
const scopeAttributes = {
  'data-cb-destination': CASE.destination || 'frame',
  'data-cb-route': '/coursebook',
  'data-cb-scope': MODE,
  'data-cb-motion': MOTION === 'reduce' ? 'reduced' : 'full'
}

/* ── the destinations ────────────────────────────────────────────────────────────────────── */
const P = CASE.props || {}
const implemented = new Set(CASE.implemented || [])
const noop = () => {}
const ref = () => React.createRef()

function surfaceNode(name) {
  switch (name) {
    case 'WorkshopView':
      return h(mod.WorkshopView, {
        implemented,
        createOpen: false,
        canSyllabus: true,
        canImport: true,
        onStartSyllabus: noop,
        onStartImport: noop,
        onOpenCourse: noop,
        onEmptyChange: noop
      })
    case 'WorkshopDetail':
      return h(mod.WorkshopDetail, {
        item: P.item,
        layout: mod.cbLayoutFor(WIDTH),
        motion: mod.cbMotionFor(MOTION === 'reduce' ? 'reduced' : 'full'),
        onBack: noop,
        onInstall: noop,
        onContinue: noop,
        busy: false,
        favorite: false,
        onFavorite: noop,
        userCategory: null,
        onCategory: noop
      })
    case 'CoursesView':
      return h(mod.CoursesView, {
        implemented,
        createOpen: false,
        onStartCreate: noop,
        onStartSyllabus: noop,
        onBrowseLibrary: noop,
        onOpen: noop,
        onShowDesk: noop,
        onEmptyChange: noop
      })
    case 'CourseDetail':
      return h(mod.CourseDetail, {
        row: P.row,
        implemented,
        profile: 'default',
        prefs: { ...mod.CB_HOME_PREF_DEFAULTS },
        focusObjectiveId: null,
        focusBlockId: null,
        focusView: 'overview',
        defaultLessonView: 'textbook',
        reloadSignal: 0,
        onBack: noop,
        onChanged: noop,
        onChangeGoal: noop,
        onNewSyllabus: noop,
        onOpenLibrary: noop
      })
    case 'CreateCourseFlow':
      return h(mod.CreateCourseFlow, {
        seed: P.seed || null,
        onCancel: noop,
        onCreated: noop
      })
    case 'SyllabusIntakeFlow':
      return h(mod.SyllabusIntakeFlow, { onCancel: noop, onCreated: noop })
    case 'SyllabusParseReview':
      return h(mod.SyllabusParseReview, {
        parsed: P.parsed,
        blocks: P.blocks || [],
        busy: false,
        onContinue: noop,
        onBack: noop,
        onReparse: noop
      })
    case 'SyllabusAlignmentReview':
      return h(mod.SyllabusAlignmentReview, {
        alignment: P.alignment,
        busy: false,
        onDecision: noop,
        onApprove: noop,
        onRealign: noop
      })
    case 'StudioList':
      return h(mod.StudioList, {
        implemented,
        reloadSignal: 0,
        sessionMinutes: 25,
        onCreate: noop,
        onOpen: noop,
        onOpenSettings: noop,
        triggerRef: ref()
      })
    case 'StudioBriefForm':
      return h(mod.StudioBriefForm, {
        initial: P.initial || null,
        note: null,
        supported: true,
        onCancel: noop,
        onCreated: noop
      })
    case 'StudioDetail':
      return h(mod.StudioDetail, {
        course: P.course,
        implemented,
        revision: Number(P.revision || 0),
        onRevision: noop,
        onBack: noop,
        onChanged: noop,
        onDuplicate: noop
      })
    case 'TakeHomeStudio':
      return h(mod.TakeHomeStudio, {
        implemented,
        sessionMinutes: 25,
        onOpenSettings: noop,
        triggerRef: ref()
      })
    case 'HomeworkStudio':
      return h(mod.HomeworkStudio, { implemented, onOpenSource: noop })
    case 'HomeSettingsSheet':
      return h(mod.HomeSettingsSheet, {
        open: true,
        prefs: { ...mod.CB_HOME_PREF_DEFAULTS, ...(P.prefs || {}) },
        classroom: P.classroom || null,
        onUpdate: noop,
        onReset: noop,
        onClose: noop
      })
    default:
      throw new Error(`cb-frame-render does not know the ${name} destination`)
  }
}

const tree = h(mod.CbV3Scope, {
  mode: MODE,
  className: 'relative flex h-full min-h-0 flex-col',
  contentClassName: 'cb3-gutter',
  // `CbV3Scope` defines the v3 `--cb3-*` contract. Several shipped surfaces still paint from the
  // legacy `--cb-*` contract (CbAction's fills, body ink), and in the live app both exist at once:
  // `cbScopeStyle()` supplies the legacy set on the same route root. Without it those surfaces
  // render with unresolved colours — a frame artifact, not a product state.
  // The route's gutter is `clamp(1.25rem, 3.05cqi, 4rem)`, i.e. it resolves against the route's
  // own container. A frame without a container measured 0px and every destination painted flush to
  // the page edges — a harness artifact that made rhythm look missing. Declare the container here.
  style: { ...mod.cbScopeStyle(MODE), containerType: 'inline-size' },
  attributes: scopeAttributes,
  children: surfaceNode(CASE.surface)
})
await act(async () => {
  root.render(tree)
})
// The live page re-renders once the health/runtime reads land; a route that gates a query on the
// registry (`backendSupports`) would otherwise keep the first render's answer forever. Re-render
// the same tree after the probe settles, exactly as that second pass does.
await act(async () => {
  await new Promise((done) => setTimeout(done, 160))
})
await act(async () => {
  root.render(tree)
})
const settle = async (ms = 60) => {
  await act(async () => {
    await new Promise((done) => setTimeout(done, ms))
  })
}
for (let pass = 0; pass < 4; pass += 1) await settle(80)

/* ── the frame's own interaction, performed on the shipped controls ───────────────────────── */
const notes = []
const clickNode = async (node, note) => {
  await act(async () => {
    node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  })
  for (let pass = 0; pass < 3; pass += 1) await settle(80)
  notes.push(note)
}

for (const action of CASE.actions || []) {
  if (action.click) {
    const node = dom.window.document.querySelector(action.click)
    if (!node) {
      notes.push(`missing selector: ${action.click}`)
    } else {
      await clickNode(node, action.note || `clicked ${action.click}`)
    }
  }
  if (action.clickText) {
    const wanted = String(action.clickText).trim()
    const node = Array.from(dom.window.document.querySelectorAll('button,[role="tab"],[role="link"]')).find(
      (candidate) => (candidate.textContent || '').replace(/\s+/g, ' ').trim() === wanted
    )
    if (!node) notes.push(`missing control labelled: ${wanted}`)
    else await clickNode(node, action.note || `pressed "${wanted}"`)
  }
  if (action.wait) await settle(action.wait)
}

const painted = routeHost.innerHTML
const answer = JSON.stringify({
  html: painted,
  notes,
  requests,
  unmapped: Array.from(new Set(unmapped))
})
// A destination can leave a host interval or animation timer live; the render is finished, so the
// process exits on its own output rather than waiting for an event loop the frame does not need.
process.stdout.write(answer, () => process.exit(0))
