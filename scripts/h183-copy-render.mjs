/**
 * H-183 copy frames: render one shipped module (before or after) to standalone HTML.
 *
 *   node scripts/h183-copy-render.mjs <plugin-dir> <payload.json> <out-dir>
 *
 * jsdom + react-dom/client so effects run. The transport is stubbed here and only here: no backend,
 * no provider, no network. Every frame is the shipped component tree, not a mock of it.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const pluginDir = resolve(process.argv[2])
const payload = JSON.parse(readFileSync(process.argv[3], 'utf8'))
const outDir = resolve(process.argv[4])
mkdirSync(outDir, { recursive: true })

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><html><head></head><body><div id="root"></div></body></html>', {
  url: 'http://coursebook.invalid/',
  pretendToBeVisual: true
})
const win = dom.window
globalThis.window = win
globalThis.document = win.document
try {
  Object.defineProperty(globalThis, 'navigator', { value: win.navigator, configurable: true })
} catch (error) {
  // Node's navigator is read-only; React only reads userAgent/language.
}
globalThis.HTMLElement = win.HTMLElement
globalThis.Element = win.Element
globalThis.Node = win.Node
globalThis.Event = win.Event
globalThis.MutationObserver = win.MutationObserver
globalThis.getComputedStyle = win.getComputedStyle.bind(win)
globalThis.requestAnimationFrame = (cb) => win.setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => win.clearTimeout(id)
win.requestAnimationFrame = globalThis.requestAnimationFrame
win.cancelAnimationFrame = globalThis.cancelAnimationFrame
win.matchMedia = (query) => ({
  media: query,
  matches: false,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {}
})
globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.__CB_TEST_WIDTH__ = '1049'
globalThis.__CB_TEST_MODE__ = 'light'

const React = (await import('react')).default
const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const mod = await import(resolve(pluginDir, 'plugin.js'))

const ctx = {
  profile: 'default',
  rest: async (path) => {
    if (String(path).startsWith('/runtime')) {
      return { wire_version: 9, implemented_methods: payload.implemented || [], single_home_host: false }
    }
    return { ok: false, error: { code: 'HOST_UNAVAILABLE', message: 'render stub has no answer' } }
  },
  register: () => {},
  onDispose: () => {},
  log: () => {},
  notify: () => {},
  dispatchTool: async () => ({ ok: false, error: { code: 'STUB' } }),
  registerSettingsPage: () => {}
}
if (typeof mod.default.register === 'function') mod.default.register(ctx)

const h = React.createElement
const noop = () => {}
const h183 = payload
const framePayload = h183.frame

function surfaceNode(frame) {
  switch (frame.surface) {
    case 'first-run':
      return h(mod.FirstRun, {
        implemented: new Set(['course.create', 'pack.import', 'syllabus.intake.create']),
        onCreate: noop,
        onSyllabus: noop,
        onBrowseLibrary: noop,
        onRetry: noop,
        companionEnabled: true
      })
    case 'home': {
      const desk = mod.buildDeskModel({
        library: framePayload.library || payload.library,
        outline: framePayload.outline || payload.outline,
        estimate: null,
        selectedCourseId: 'crs_0123456789abcdef'
      })
      return h(mod.FieldDeskHome, {
        desk,
        notes: [],
        libraryStatus: 'ready',
        libraryError: null,
        stale: false,
        busy: false,
        notice: null,
        onRetry: noop,
        onCreate: noop,
        onPrimary: noop,
        onOpenSection: noop,
        onOpen: noop,
        onShowAll: noop,
        sourcesOpen: false,
        onToggleSources: noop,
        sourcesStatus: 'idle',
        sourcesError: null,
        sources: null,
        onRetrySources: noop,
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'parent.brief.get'])
      })
    }
    case 'lesson-empty':
    case 'lesson-failed':
    case 'lesson-incomplete': {
      const state = frame.surface.replace('lesson-', '')
      const readinessCase = framePayload.readiness[state]
      return h(mod.SectionPage, {
        row: { enrollment_id: 'enr_0123456789abcdef', profile: 'default', title: 'Order at a counter' },
        objectiveId: 'obj_0123456789abcdef',
        page: readinessCase.page,
        pageStatus: readinessCase.pageStatus,
        pageError: null,
        onRetryPage: noop,
        implemented: new Set(['check.open', 'notebook.save']),
        onBack: noop,
        onChanged: noop,
        review: null,
        outline: readinessCase.outline,
        planStatus: readinessCase.planStatus,
        jobs: readinessCase.jobs,
        onOpenPlan: noop,
        onRetryLessonsJob: noop,
        embedded: false
      })
    }
    case 'settings':
      return h(mod.HomeSettingsSheet, {
        open: true,
        prefs: {
          appearance: 'system',
          defaultMode: 'game',
          sound: false,
          companion: true,
          reducedMotion: 'system',
          sessionMinutes: 15,
          classrooms: {}
        },
        classroom: null,
        onUpdate: noop,
        onReset: noop,
        onClose: noop
      })
    default:
      throw new Error(`unknown surface ${frame.surface}`)
  }
}

const shell = (markup, mode, fontPx) => `<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
<title>Coursebook copy frame</title>
<style>
  html { font-size: ${fontPx}px; }
  html, body { margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  .cb-frame { padding: 1.25rem clamp(1rem, 4vw, 4rem) 2rem; min-height: 100vh; box-sizing: border-box; }
  *, *::before, *::after { box-sizing: border-box; }
</style></head>
<body><div class="cb-frame">${markup}</div></body></html>`

const container = win.document.getElementById('root')
container.innerHTML = ''
const root = createRoot(container)
const mode = framePayload.mode
const tree = h(
  'div',
  {
    'data-cb-scope': mode,
    'data-cb-motion': 'full',
    'data-cb-h183-surface': framePayload.surface,
    style: { ...mod.cbScopeStyle(mode), minHeight: '100%' }
  },
  surfaceNode(framePayload)
)
await act(async () => {
  root.render(tree)
})
let previous = ''
for (let attempt = 0; attempt < 60; attempt += 1) {
  await act(async () => {
    await new Promise((done) => setTimeout(done, 5))
  })
  if (container.innerHTML === previous) break
  previous = container.innerHTML
}
const html = shell(container.innerHTML, mode, framePayload.fontPx || 16)
writeFileSync(resolve(outDir, 'frame.html'), html)
process.stdout.write(JSON.stringify({ bytes: html.length }))
