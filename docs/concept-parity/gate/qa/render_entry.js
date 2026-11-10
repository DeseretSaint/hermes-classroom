/**
 * GM-015 probe renderer: mounts the shipped `desktop/plugin.js` in a real Chromium page.
 *
 * This is a *component preview*, not a live Desktop capture: it runs the real module with React
 * 19 and the harness-owned SDK stub, and it does not load the host window chrome or its theme.
 * That is deliberate — the probes measure the product surface's own DOM, geometry, focus order
 * and media-query posture. `--live` mode is the separate check that the same facts hold inside a
 * running Desktop.
 *
 * esbuild bundles this entry with `desktop/plugin.js`; each frame is the same bundle plus a
 * `window.__CB_FRAME__` payload, so one build serves every probe.
 */
import React from 'react'
import { createRoot } from 'react-dom/client'
import * as mod from './plugin.js'

const h = React.createElement
const F = window.__CB_FRAME__ || { kind: 'shelf' }

window.__CB_MODULE__ = {
  id: mod.default && mod.default.id,
  hasRegister: Boolean(mod.default && typeof mod.default.register === 'function'),
  exports: Object.keys(mod).length
}

window.__CB_ERRORS__ = []
window.addEventListener('error', (event) => {
  window.__CB_ERRORS__.push(`error: ${(event && event.message) || 'unknown'}`)
})
window.addEventListener('unhandledrejection', (event) => {
  const reason = event && event.reason
  window.__CB_ERRORS__.push(`unhandledrejection: ${(reason && (reason.message || String(reason))) || 'unknown'}`)
})

const ROWS = [
  {
    enrollment_id: 'enr_0123456789abcdef',
    course_id: 'crs_0123456789abcdef',
    title: 'Small-engine maintenance',
    subtitle: 'Keep a two-stroke engine running through the season.',
    recipe: 'committed',
    level_label: null,
    locale: null,
    learner_label: null,
    enrollment_status: 'active',
    course_status: 'active',
    provenance: { source: 'authored', pack_id: null, pack_version: null },
    next_step: { kind: 'resolve_review_due', label: 'Review 1 objective(s)' },
    evidence_summary: { independent: 1, review_due: 1, total_objectives: 4, current_objective_id: 'obj_0000000000000003' },
    warning: null,
    updated_at: '2026-11-06T18:00:00.000000+00:00',
    revision: 7
  },
  {
    enrollment_id: 'enr_bbbbbbbbbbbbbbbb',
    course_id: 'crs_bbbbbbbbbbbbbbbb',
    title: 'Japanese greetings (L0)',
    subtitle: 'あいさつと自己紹介',
    recipe: 'casual',
    level_label: 'L0',
    locale: 'ja',
    learner_label: 'Learner',
    enrollment_status: 'active',
    course_status: 'active',
    provenance: { source: 'pack', pack_id: 'pack_japanese_l0', pack_version: '1.0.0' },
    next_step: { kind: 'start_lesson', label: 'Start あいさつと自己紹介' },
    evidence_summary: { independent: 0, review_due: 0, total_objectives: 6, current_objective_id: null },
    warning: null,
    updated_at: '2026-11-04T09:00:00.000000+00:00',
    revision: 3
  },
  {
    enrollment_id: 'enr_cccccccccccccccc',
    course_id: 'crs_cccccccccccccccc',
    title: 'Reading a schematic',
    subtitle: null,
    recipe: 'one_off',
    level_label: null,
    locale: null,
    learner_label: null,
    enrollment_status: 'active',
    course_status: 'active',
    provenance: { source: 'authored', pack_id: null, pack_version: null },
    next_step: { kind: 'review_plan', label: 'Review the plan' },
    evidence_summary: { independent: 0, review_due: 0, total_objectives: 5, current_objective_id: null },
    warning: null,
    updated_at: '2026-11-03T09:00:00.000000+00:00',
    revision: 1
  }
]

const library = (rows) => ({
  items: rows,
  next_cursor: null,
  total: rows.length,
  empty_reason: null,
  applied_filter: 'all'
})

const noop = () => {}

const BLOCK_INDEX = {
  blk_explain001: { id: 'blk_explain001', role: 'explain', headline: 'The mechanism' },
  blk_orient0001: { id: 'blk_orient0001', role: 'orient', headline: 'Start here' }
}
const SOURCE_INDEX = {
  src_affection01: { source_id: 'src_affection01', title: 'Affection and register — field notes' }
}
const TURNS = [
  {
    id: 'ttr_learner01',
    ordinal: 1,
    role: 'learner',
    text: 'Why is です used here?',
    block_id: 'blk_orient0001',
    selected_text: 'Affection and register',
    citations: []
  },
  {
    id: 'ttr_tutor01',
    ordinal: 2,
    role: 'tutor',
    text: 'です marks the polite register of the statement.',
    block_id: null,
    selected_text: null,
    citations: [{ kind: 'block', id: 'blk_explain001', label: 'The mechanism' }]
  }
]
const GLOSSARY = [
  { term: 'ですか', gloss: 'Question particle: turns a statement into a question.', reading: 'desu ka' },
  { term: '敬語', gloss: 'Polite register.', reading: 'keigo' }
]

function tutorProps() {
  return {
    state: 'ready',
    width: 900,
    courseTitle: 'Japanese, first steps',
    objectiveTitle: 'Affection and register',
    contextChip: 'Section 2',
    turns: TURNS,
    blockIndex: BLOCK_INDEX,
    sourceIndex: SOURCE_INDEX,
    glossary: GLOSSARY,
    checkOpen: true,
    hint: { available: true, used: false },
    mode: 'ask',
    quote: { text: '敬語 is polite register.', blockId: 'blk_explain001' },
    draft: '',
    busy: false,
    practiceAvailable: false,
    onRemoveQuote: noop,
    onTermQuote: noop,
    onCitation: noop,
    onModeChange: noop,
    onDraftChange: noop,
    onSend: noop,
    onAskHint: noop,
    onStartPractice: noop,
    onEndPractice: noop
  }
}

function documentFixture() {
  return {
    schema_version: 1,
    document_id: 'doc_0123456789abcdef0123',
    content_hash: 'sha256:' + 'a'.repeat(64),
    section_title: 'Affection and register',
    objective_id: 'obj_0123456789abcdef',
    state: 'complete',
    view_note: null,
    views: { textbook: true, guided: true, field_quest: false, field_notes: false },
    blocks: [
      {
        id: 'blk_orient0001',
        role: 'orient',
        headline: 'Start here',
        short: 'Short orient.',
        deep: 'Deep orient prose that must stay readable at a doubled text size.',
        check_id: null,
        media: [],
        source_ids: ['src_affection01']
      },
      {
        id: 'blk_media00001',
        role: 'explain',
        headline: 'The mechanism',
        short: 'Short explain.',
        deep: 'A diagram would sit here. The text equivalent must survive an image that cannot load.',
        check_id: null,
        media: [
          {
            artifact_id: 'art_probe_media_0001',
            kind: 'visual',
            text: 'A diagram of the cycle.',
            purpose: 'Illustrates the cycle'
          }
        ],
        source_ids: ['src_affection01']
      }
    ],
    check_id: null,
    source_ids: ['src_affection01']
  }
}

// Register the module once so its hooks always have a context. In `page-null` mode `rest` rejects
// (no host runtime at all); in every other frame it answers a handled "no backend" envelope so a
// media preview settles into its authored text fallback instead of throwing inside an effect.
const registered = []
const pageNull = F.kind === 'page-null'
const ctx = new Proxy(
  {
    register(entry) {
      registered.push(entry)
    }
  },
  {
    get(target, key) {
      if (key in target) return target[key]
      if (key === 'rest') {
        if (pageNull) {
          return async () => {
            throw new Error('no host runtime')
          }
        }
        if (F.kind === 'lesson-ready') {
          // A served artifact, so the lesson renders a real <img> the image-failure probe can break.
          return async (path) => {
            if (String(path).startsWith('/media/')) {
              const svg = encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#e6dcc8"/><circle cx="160" cy="90" r="52" fill="#7a2e1e"/></svg>'
              )
              return {
                ok: true,
                data_url: `data:image/svg+xml;charset=utf-8,${svg}`,
                mime: 'image/svg+xml',
                label: 'Illustration',
                text_equivalent: 'A flat plate with one broad ink form.',
                bytes: 180
              }
            }
            return { ok: false, message: 'No backend in the preview.' }
          }
        }
        return async () => ({ ok: false, message: 'The preview host has no backend; the text equivalent remains.' })
      }
      return () => undefined
    }
  }
)
try {
  mod.default.register(ctx)
} catch (error) {
  window.__CB_BOOT_ERROR__ = `register: ${error && (error.stack || error.message || error)}`
}

function pageFrame() {
  const page = registered.find((entry) => entry && entry.data && entry.data.path === '/coursebook')
  if (!page) return h('div', { 'data-cb-boot': 'no-route' }, 'No Coursebook route was registered.')
  return page.render()
}

let body
switch (F.kind) {
  case 'shelf':
  case 'cold': {
    const rows = F.kind === 'cold' ? [] : ROWS
    body = h(mod.CoursebookHome, {
      library: { status: 'ready', data: library(rows), error: null, stale: false },
      modes: {},
      modesSupported: true,
      online: true,
      canCreate: true,
      onStartCreate: noop,
      onBrowseLibrary: noop,
      onOpenCourse: noop,
      onShowAll: noop,
      onOpenStudio: noop,
      onRetry: noop
    })
    break
  }
  case 'tutor': {
    body = h(mod.TutorRail, tutorProps())
    break
  }
  case 'lesson':
  case 'lesson-ready': {
    body = h(mod.LessonDocumentView, {
      document: documentFixture(),
      view: F.view || 'textbook',
      sources: SOURCE_INDEX,
      checkSlot: null
    })
    break
  }
  case 'page-null': {
    body = pageFrame()
    break
  }
  default: {
    body = h('div', { 'data-cb-boot': 'unknown-frame' }, `Unknown frame ${F.kind}`)
  }
}

const mode = F.mode === 'dark' ? 'dark' : 'light'
const root = h(
  'div',
  { 'data-cb-scope': mode, 'data-cb-motion': F.motion || 'full', style: mod.cbScopeStyle(mode) },
  h(
    'div',
    {
      'data-cb-route': '/coursebook',
      'data-cb-frame': F.kind,
      style: { padding: '1.25rem clamp(1rem, 4vw, 4rem) 2rem', minHeight: '100vh', boxSizing: 'border-box' }
    },
    body
  )
)

const container = document.getElementById('root')
createRoot(container).render(root)
// A stable readiness flag the browser probe waits for: React 19 commits synchronously for this
// tree, but one animation frame keeps the check free of a partial commit.
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    window.__CB_READY__ = true
  })
})
