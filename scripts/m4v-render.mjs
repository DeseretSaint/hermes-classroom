/**
 * M4-V1 render harness: run the SHIPPED `desktop/plugin.js` components in a real DOM.
 *
 * jsdom + `react-dom/client` (not `renderToStaticMarkup`) so effects run: the media preview
 * loader (`useArtifactPreview`) actually reaches a stubbed `ctx.rest` and the shipped
 * `<img>` / `<audio>` players are mounted, exactly as the Desktop mounts them. The resulting DOM
 * is serialized to standalone HTML for Chromium to paint, measure and screenshot.
 *
 * The transport is stubbed here and only here. No provider, no backend, no network.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const payload = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const outDir = resolve(process.argv[3])
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
  // Node exposes a read-only navigator; jsdom's is not required for this render.
}
globalThis.HTMLElement = win.HTMLElement
globalThis.Element = win.Element
globalThis.Node = win.Node
globalThis.Event = win.Event
globalThis.MutationObserver = win.MutationObserver
globalThis.getComputedStyle = win.getComputedStyle.bind(win)
globalThis.requestAnimationFrame = (cb) => win.setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => win.clearTimeout(id)
// jsdom keeps `navigator` read-only on window; React only reads userAgent/language.
win.matchMedia = (query) => ({
  media: query,
  matches: payload.reducedMotion === true && String(query).includes('prefers-reduced-motion'),
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {}
})
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const React = (await import('react')).default
const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
// The SDK stub reads these at import time: the host viewport atom and the painted theme mode.
globalThis.__CB_TEST_WIDTH__ = String(payload.width || 1280)
globalThis.__CB_TEST_MODE__ = (payload.frames && payload.frames[0] && payload.frames[0].mode) || 'light'
const mod = await import('./plugin.js')

/* ── the stubbed host context ─────────────────────────────────────────────────────────────── */
const mediaAnswers = payload.media || {}
const noMedia = payload.mediaState === 'unavailable'
const calls = []
const ctx = {
  profile: 'default',
  rest: async (path) => {
    calls.push(String(path))
    if (String(path).startsWith('/runtime')) {
      return { wire_version: 9, implemented_methods: payload.implemented || [], single_home_host: false }
    }
    const match = /^\/media\/(.+)$/.exec(String(path))
    if (match) {
      const id = decodeURIComponent(match[1])
      if (noMedia) {
        return {
          ok: false,
          message: `This media could not be previewed (MEDIA_UNAVAILABLE); the text equivalent remains.`,
          code: 'MEDIA_UNAVAILABLE'
        }
      }
      const answer = mediaAnswers[id]
      if (answer) return { ok: true, ...answer }
      return { ok: false, message: 'This media could not be previewed; the text equivalent remains.' }
    }
    return { ok: false, error: { code: 'HOST_UNAVAILABLE', message: 'stub has no answer' } }
  },
  register: () => {},
  onDispose: () => {},
  log: () => {},
  notify: () => {},
  dispatchTool: async () => ({ ok: false, error: { code: 'STUB' } }),
  registerSettingsPage: () => {}
}
if (typeof mod.default.register === 'function') mod.default.register(ctx)

/* ── the surfaces, built from contract-shaped fixtures ───────────────────────────────────── */
const h = React.createElement
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const checkNode = h('div', { 'data-cb-audit-check': '', style: { padding: '0.4rem 0' } }, 'VERIFICATION-CHECKLIST')

function surfaceNode(name) {
  switch (name) {
    case 'textbook':
    case 'textbook-unavailable':
    case 'textbook-textonly':
      return h(mod.LessonDocumentView, {
        document: payload.document,
        view: 'textbook',
        sources: index,
        checkSlot: checkNode,
        checkLabels: ['Correct answer'],
        onSaveBlock: () => {},
        pronunciation: null
      })
    case 'guided':
      return h(mod.LessonDocumentView, {
        document: payload.document,
        view: 'guided',
        sources: index,
        checkSlot: checkNode,
        checkLabels: ['Correct answer'],
        focusBlockId: payload.focusBlockId || null,
        onSaveBlock: () => {}
      })
    case 'quest':
      return h(mod.FieldQuestView, {
        document: payload.document,
        sources: index,
        checkSlot: checkNode,
        checkLabels: ['Correct answer'],
        progress: payload.evidence || null,
        unattached: null,
        onOpenBlock: () => {},
        onSaveBlock: () => {}
      })
    case 'procedure':
      return h(mod.LessonDocumentView, {
        document: payload.procedure,
        view: 'textbook',
        sources: index,
        checkSlot: checkNode,
        checkLabels: ['Verified'],
        onSaveBlock: () => {}
      })
    case 'field-desk':
      return h(mod.FieldDeskHome, {
        desk: mod.buildDeskModel({
          library: payload.library,
          outline: payload.outline,
          estimate: payload.estimate || null
        }),
        notes: payload.notes || [],
        libraryStatus: 'ready',
        libraryError: null,
        stale: false,
        busy: false,
        notice: null,
        onRetry: () => {},
        onCreate: () => {},
        onPrimary: () => {},
        onOpenSection: () => {},
        onOpen: () => {},
        onShowAll: () => {},
        sourcesOpen: false,
        onToggleSources: () => {},
        sourcesStatus: 'idle',
        sourcesError: null,
        sources: payload.sources || null,
        onRetrySources: () => {},
        implemented: new Set(['library.list', 'course.outline', 'lesson.page', 'parent.brief.get'])
      })
    default:
      throw new Error(`unknown surface ${name}`)
  }
}

function shellHtml(section, mode) {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="color-scheme" content="light dark" />
<title>Coursebook M4-V ${mode}</title>
<style>
  html, body { margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  .cb-audit { padding: 1.5rem clamp(1rem, 4vw, 3rem); min-height: 100vh; box-sizing: border-box; }
  *, *::before, *::after { box-sizing: border-box; }
</style></head>
<body><div class="cb-audit">${section}</div></body></html>`
}

const manifest = []
for (const frame of payload.frames) {
  const container = win.document.getElementById('root')
  container.innerHTML = ''
  const root = createRoot(container)
  const mode = frame.mode
  const tree = h(
    'div',
    {
      'data-cb-scope': mode,
      'data-cb-motion': frame.reducedMotion ? 'reduced' : 'full',
      'data-cb-audit-surface': frame.surface,
      style: { ...mod.cbScopeStyle(mode), minHeight: '100%' }
    },
    surfaceNode(frame.surface)
  )
  await act(async () => {
    root.render(tree)
  })
  // Let the media loader's promise chain settle (two ticks + a macrotask).
  await act(async () => {
    await new Promise((done) => setTimeout(done, 0))
    await new Promise((done) => setTimeout(done, 0))
    await new Promise((done) => setTimeout(done, 10))
  })
  const markup = container.innerHTML
  const file = resolve(outDir, `${frame.id}.html`)
  writeFileSync(file, shellHtml(markup, mode))
  const mediaReady = (markup.match(/data-cb-media="/g) || []).length
  manifest.push({ id: frame.id, surface: frame.surface, mode, file, bytes: markup.length, media_nodes: mediaReady })
  await act(async () => {
    root.unmount()
  })
}

writeFileSync(resolve(outDir, 'manifest.json'), JSON.stringify({ frames: manifest, rest_calls: calls.slice(0, 40) }, null, 2))
process.stdout.write(JSON.stringify({ frames: manifest.length, path: resolve(outDir, 'manifest.json') }))
