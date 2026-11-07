/**
 * M3-U1 evidence: paint the shipped Pronunciation Studio in every state it can hold.
 *
 * The studio is a stateful component, so a server render can only show its first frame. This
 * harness mounts the real exported component from `desktop/plugin.js` in jsdom with a stub
 * `@hermes/plugin-sdk`, a fake `MediaRecorder` and a fake `ctx.rest`, drives the exact actions the
 * card names (Record, Stop, Compare, Save, Delete) and prints the resulting markup plus the scoped
 * token style. `scripts/m3p-frames.py` wraps that markup in the frame shell and
 * `scripts/m2fn-shot.mjs` screenshots it.
 *
 * What this is: renderer evidence of the shipped component's states, produced by the component
 * itself. What it is not: a live-window capture — `scripts/m3p-live.mjs` is the live run.
 */
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const scenario = JSON.parse(process.env.CB_PRONUNCIATION_STATE || '{"name":"available"}')
const mode = process.env.CB_TEST_MODE || 'light'
const motion = process.env.CB_TEST_MOTION || 'full'

class FakeRecorder {
  static isTypeSupported() { return true }
  constructor(stream, options) {
    this.stream = stream
    this.mimeType = (options && options.mimeType) || 'audio/webm'
    this.state = 'inactive'
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    if (this.ondataavailable) this.ondataavailable({ data: new dom.window.Blob([new Uint8Array([26, 69, 223, 163])], { type: this.mimeType }) })
    if (this.onstop) this.onstop()
  }
}
class FakeFileReader {
  readAsDataURL() {
    this.result = 'data:audio/webm;base64,GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYEC'
    setTimeout(() => { if (this.onload) this.onload() }, 0)
  }
}
Object.defineProperty(dom.window.navigator, 'mediaDevices', {
  configurable: true,
  value: { getUserMedia: async () => ({ getTracks: () => [{ stop: () => {} }] }) }
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.MediaRecorder = scenario.noRecorder ? undefined : FakeRecorder
globalThis.FileReader = FakeFileReader

const TARGET = 'こんにちは。今日はいい天気ですね。'
const MEDIA = {
  kind: 'audio',
  role: 'narration',
  artifact_id: 'art_0123456789abcdef',
  purpose: 'Reference pronunciation of the target phrase',
  text_equivalent: TARGET,
  label: 'Model phrase',
  degraded: false,
  reason: null
}

const AVAILABLE = { ok: true, provider: 'coursebook_local_whisper', model: 'small', available: true, reason: null, model_cached: true, local_only: true }
const UNAVAILABLE = { ok: true, provider: 'coursebook_local_whisper', model: 'small', available: false, reason: 'stt_dependency_missing', model_cached: false, local_only: true }
const ASSESSMENT = {
  transcript: 'こんにちは。今日はいい天気ですね。',
  target: TARGET,
  locale: 'ja',
  provider: 'coursebook_local_whisper',
  model: 'small',
  language: 'ja',
  unit: 'character',
  word_accuracy: 0.7778,
  phoneme_accuracy: null,
  confidence: 0.7526,
  words: [
    { expected: 'こ', heard: 'こ', match: true, confidence: 0.91 },
    { expected: 'ん', heard: 'ん', match: true, confidence: 0.72 },
    { expected: 'に', heard: 'に', match: true, confidence: 0.66 },
    { expected: 'ち', heard: 'ち', match: true, confidence: 0.8 },
    { expected: 'は', heard: 'わ', match: false, confidence: null },
    { expected: '今', heard: '今', match: true, confidence: 0.77 },
    { expected: '日', heard: '日', match: true, confidence: 0.71 },
    { expected: '天', heard: 'て', match: false, confidence: null },
    { expected: '気', heard: '気', match: true, confidence: 0.69 }
  ],
  verdict: 'close',
  evidence_class: 'model_assessed'
}

const responses = {
  '/runtime': { wire_version: 9, implemented_methods: ['pronunciation.attempt', 'notebook.save'], single_home_host: false },
  '/pronunciation/status': scenario.status === 'error' ? { __throw: 'backend offline' } : (scenario.name === 'unavailable' ? UNAVAILABLE : AVAILABLE),
  '/media/art_0123456789abcdef': { ok: true, data_url: 'data:audio/mpeg;base64,AAAA', mime: 'audio/mpeg', bytes: 4, label: 'Model phrase', text_equivalent: TARGET },
  '/rpc': { ok: true, result: { entry_id: 'nbe_0123456789abcdef', revision: 8 } },
  '/pronunciation/attempt': scenario.attempt || { ok: true, result: { status: 'assessed', recorded: true, attempt_id: 'prn_0123456789abcdef0123', revision: 7, assessment: ASSESSMENT, reason: null } }
}

const mod = await import('./plugin.js')
const calls = []
mod.default.register({
  rest: async (path, options) => {
    calls.push({ path: String(path).split('?')[0], method: (options && options.method) || 'GET', body: options && options.body })
    const key = Object.keys(responses).find((candidate) => String(path).split('?')[0] === candidate)
    if (!key) throw new Error('unexpected rest path ' + path)
    const value = responses[key]
    if (value && value.__throw) throw new Error(value.__throw)
    return value
  },
  register: () => {},
  onDispose: () => {}
})

const React = (await import('react')).default
const { act } = await import('react')
const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const props = {
  enrollmentId: 'enr_0123456789abcdef',
  objectiveId: 'obj_0123456789abcdef',
  revision: 7,
  locale: 'ja',
  block: { id: 'blk_practice01', headline: 'Try it', source_ids: ['src_affection01'], media: [MEDIA] },
  media: MEDIA,
  implemented: new Set(['pronunciation.attempt', 'notebook.save']),
  onSaved: () => {}
}
const flush = async (ms = 30) => { await act(async () => { await new Promise((done) => setTimeout(done, ms)) }) }
const byText = (text) => [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === text) || null
const click = async (node) => {
  if (!node) throw new Error('button not found for scenario ' + scenario.name)
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
}

await act(async () => { root.render(React.createElement(mod.PronunciationStudio, props)) })
await flush()

// Focus order: every action is a native button, so Tab reaches Listen then Record. Measure it
// rather than claiming it.
const order = [...document.querySelectorAll('[data-cb-pronunciation] button')].map((node) => (node.textContent || '').trim())

if (scenario.name === 'recording') {
  await click(byText('Record'))
} else if (scenario.name === 'assessed' || scenario.name === 'saved') {
  await click(byText('Record'))
  await click(byText('Stop'))
  if (scenario.name === 'saved') await click(byText('Save result to notebook'))
} else if (scenario.name === 'refusal') {
  await click(byText('Record'))
  await click(byText('Stop'))
} else if (scenario.name === 'empty') {
  await click(byText('Record'))
  await click(byText('Stop'))
} else if (scenario.name === 'no-recorder') {
  await click(byText('Record'))
}

const section = document.querySelector('[data-cb-pronunciation]')
if (!section) throw new Error('no studio rendered')
process.stdout.write(JSON.stringify({
  markup: section.outerHTML,
  style: mod.cbScopeStyle(mode),
  motion,
  mode,
  phase: section.getAttribute('data-cb-pronunciation-phase'),
  availability: section.getAttribute('data-cb-pronunciation-availability'),
  buttons: order,
  text: (section.textContent || '').replace(/\s+/g, ' ').trim(),
  calls: calls.map((call) => ({ path: call.path, method: call.method }))
}))
