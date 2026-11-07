// Renders the shipped Field Desk through the real React module at the three audit widths and
// writes self-contained HTML (tokens painted inline, no external asset) for headless Chromium.
import { writeFileSync } from 'node:fs'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { FieldDeskHome, buildDeskModel, cbScopeStyle } from './plugin.js'

const widths = [1049, 900, 460]
const modes = ['light', 'dark']

const library = {
  items: [
    {
      enrollment_id: 'enr_0000000000000001',
      course_id: 'crs_small_engine',
      title: 'Small-engine maintenance',
      recipe: 'weekly',
      revision: 3,
      updated_at: '2026-11-06T18:00:00.000000+00:00',
      next_step: { kind: 'resume_lesson', label: 'Continue section 2' },
      evidence_summary: { independent: 1, total_objectives: 4, due: 1 },
      provenance: { source: 'authored' }
    },
    {
      enrollment_id: 'enr_0000000000000002',
      course_id: 'crs_japanese',
      title: 'Japanese greetings',
      recipe: 'weekly',
      revision: 1,
      updated_at: '2026-11-05T18:00:00.000000+00:00',
      next_step: { kind: 'resume_lesson', label: 'Start あいさつ' },
      evidence_summary: { independent: 0, total_objectives: 5, due: 1 },
      provenance: { source: 'bundled' }
    }
  ],
  total: 2
}

const outline = {
  objectives: [
    { objective_id: 'obj_0000000000000001', ordinal: 1, title: 'Name the four strokes', state: 'independent_evidence', last_opened_at: '2026-11-06T17:00:00.000000+00:00' },
    { objective_id: 'obj_0000000000000002', ordinal: 2, title: 'Diagnose a no-start', state: 'review_due', last_opened_at: '2026-11-06T17:30:00.000000+00:00' },
    { objective_id: 'obj_0000000000000003', ordinal: 3, title: 'Trace the fuel path', state: 'introduced', last_opened_at: null },
    { objective_id: 'obj_0000000000000004', ordinal: 4, title: 'Replace a plug', state: 'not_started', last_opened_at: null }
  ]
}

const desk = buildDeskModel({ library, outline, estimate: { status: 'ready', minutes: 20, source: 'pack' } })

for (const mode of modes) {
  for (const width of widths) {
    globalThis.__CB_TEST_WIDTH__ = String(width)
    globalThis.__CB_TEST_MODE__ = mode
    const html = renderToStaticMarkup(
      React.createElement('div', {
        'data-cb-scope': mode,
        'data-cb-motion': 'full',
        style: { ...cbScopeStyle(mode), padding: '24px', minHeight: '100vh', fontFamily: 'ui-sans-serif, system-ui, sans-serif' }
      }, React.createElement('div', { style: { width: `${width}px`, maxWidth: '100%', margin: '0 auto' } },
        React.createElement(FieldDeskHome, {
          desk,
          notes: [
            { entry_id: 'ent_1', excerpt: 'A no-start is fuel, air or spark. Check the plug first.', section_title: 'Diagnose a no-start' },
            { entry_id: 'ent_2', excerpt: 'Compression should be above 90 psi on this engine.', section_title: 'Trace the fuel path' }
          ],
          libraryStatus: 'ready',
          libraryError: null,
          stale: false,
          busy: false,
          notice: null,
          onRetry: () => {},
          onCreate: () => {},
          onSyllabus: () => {},
          onPrimary: () => {},
          onOpenSection: () => {},
          onOpen: () => {},
          onShowAll: () => {},
          onShowNotebook: () => {},
          sourcesOpen: false,
          onToggleSources: () => {},
          sourcesStatus: 'idle',
          sourcesError: null,
          sources: [],
          onRetrySources: () => {},
          implemented: new Set(['library.list', 'course.outline', 'pack.inspect', 'pack.import', 'course.create', 'jobs.create']),
          onEmptyChange: () => {}
        })
      ))
    )
    const doc = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:${mode === 'dark' ? '#131210' : '#f7f1e4'};} *{box-sizing:border-box;} button{font:inherit;}</style></head><body>${html}<script>requestAnimationFrame(()=>{const d=document.documentElement;const w=document.querySelector("[data-cb-route],[data-cb-desk]")||document.body;const out={viewport:innerWidth,docScroll:d.scrollWidth,docClient:d.clientWidth,nodeScroll:w.scrollWidth,nodeClient:w.clientWidth,overflowX:Math.max(0,d.scrollWidth-d.clientWidth)};const tag=document.createElement("pre");tag.id="overflow-report";tag.textContent="OVERFLOW "+JSON.stringify(out);document.body.appendChild(tag)})</script></body></html>`
    writeFileSync(`field-desk-${mode}-${width}.html`, doc)
    process.stdout.write(`wrote field-desk-${mode}-${width}.html\n`)
  }
}
