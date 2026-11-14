// Sentinel UI probe: mount the SHIPPED Coursebook desktop module in jsdom and dump the DOM
// after effects settle. The backend responses come from real product output captured in
// ui_payload.json: the served lesson.page and the /media/ preview for each artifact.
//
// Usage: node ui_probe.mjs ui_payload.json
import fs from 'node:fs'

const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

const { JSDOM } = await import('jsdom')
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', {
  value: dom.window.navigator,
  configurable: true,
  writable: true
})
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.MutationObserver = dom.window.MutationObserver
globalThis.getComputedStyle = dom.window.getComputedStyle
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)

const React = (await import('react')).default
const { createRoot } = await import('react-dom/client')
const mod = await import('./plugin.js')

const restCalls = []
async function rest(path) {
  restCalls.push(String(path))
  if (String(path).startsWith('/runtime')) {
    return {
      wire_version: 14,
      implemented_methods: ['artifact.get', 'lesson.page', 'check.open', 'notebook.save'],
      single_home_host: false
    }
  }
  const media = String(path).match(/^\/media\/(.+)$/)
  if (media) {
    const id = decodeURIComponent(media[1])
    const preview = (payload.previews || {})[id]
    if (preview) return preview
    return { ok: false, code: 'NOT_FOUND', message: 'artifact not found' }
  }
  return { ok: true, result: {} }
}

const ctx = {
  rest,
  register: () => {},
  onDispose: () => {},
  dispose: () => {},
  host: {
    state: {
      focusedSessionId: { get: () => null },
      focusedStoredSessionId: { get: () => null },
      focusedSessionProfile: { get: () => 'default' },
      profile: { get: () => 'default' },
      viewport: { get: () => ({ width: 1280, height: 900, narrow: false }) }
    },
    notify: () => {},
    navigate: () => {},
    openSession: async () => ({ ok: true }),
    newChat: async () => ({ ok: true })
  }
}
mod.default.register(ctx)

const page = payload.page
const container = document.createElement('div')
document.body.appendChild(container)
const root = createRoot(container)
root.render(
  React.createElement(mod.SectionPage, {
    row: { enrollment_id: payload.enrollment_id, profile: 'default', title: payload.title || 'Lesson' },
    objectiveId: payload.objective_id,
    page,
    pageStatus: 'ready',
    pageError: null,
    onRetryPage: () => {},
    implemented: new Set(['artifact.get', 'notebook.save']),
    onBack: () => {},
    onChanged: () => {},
    review: null,
    defaultLessonView: 'textbook'
  })
)

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
await sleep(250)
await sleep(250)

process.stdout.write(
  JSON.stringify({
    html: container.innerHTML,
    text: container.textContent,
    rest_calls: restCalls
  })
)
