#!/usr/bin/env node
/**
 * GM-012 evidence: render the SHIPPED TutorRail into standalone HTML frames.
 *
 * This is component evidence, not a live Desktop capture: the pane's host chrome is absent. The
 * rail's own layout is inline styles on the module's token contract, so these frames measure the
 * shipped component's hierarchy, contrast, target size, clipping and overflow at the card's
 * required widths. The MANIFEST states this limit.
 *
 *   node scripts/gm012-rail-render.mjs <frames.json>
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as mod from './plugin.js'

const payload = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const outDir = resolve(payload.outDir)
mkdirSync(outDir, { recursive: true })

const css = (style) =>
  Object.entries(style)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}:${value}`)
    .join(';')

const BLOCK_INDEX = {
  blk_f36dfe1cee3b6f590096: { id: 'blk_f36dfe1cee3b6f590096', role: 'orient', headline: 'Lesson' },
  blk_d39fdfbbd9a83b1a56a9: { id: 'blk_d39fdfbbd9a83b1a56a9', role: 'practice', headline: 'Check' }
}
const TURNS = [
  {
    id: 'ttr_gm012a0001', ordinal: 1, role: 'learner',
    text: 'Why does the line change when the listener changes?',
    block_id: 'blk_f36dfe1cee3b6f590096',
    selected_text: 'There is no single Japanese line that means “I love you”.',
    citations: []
  },
  {
    id: 'ttr_gm012a0002', ordinal: 2, role: 'tutor',
    text: 'Because the same feeling is carried by a different line depending on the addressee, your closeness to them, and the setting. The lesson opens with exactly that point.',
    citations: [{ kind: 'block', id: 'blk_f36dfe1cee3b6f590096', label: 'Lesson' }]
  },
  {
    id: 'ttr_gm012a0003', ordinal: 3, role: 'learner',
    text: 'So which line fits a first confession to someone I respect?',
    citations: []
  },
  {
    id: 'ttr_gm012a0004', ordinal: 4, role: 'tutor',
    text: 'Work from the check: an adult speaker, an adult addressee you respect but do not know well, a private setting, standard polite register. Compare the four authored lines against those conditions.',
    citations: [{ kind: 'block', id: 'blk_d39fdfbbd9a83b1a56a9', label: 'Check' }]
  }
]
const GLOSSARY = [
  { term: 'です', gloss: 'Polite copula: marks the statement as standard polite.', reading: 'desu' },
  { term: '敬語', gloss: 'Polite register, including honorific and humble forms.', reading: 'keigo' }
]
const PRACTICE = {
  declaration: { scenario: 'You are asking a colleague for a pen.', learner_role: 'student', tutor_role: 'colleague', opening: 'こんにちは。何が必要ですか。' },
  state: 'active',
  transcript: [
    { ordinal: 1, speaker: 'tutor', text: 'こんにちは。何が必要ですか。' },
    { ordinal: 2, speaker: 'learner', text: 'ペンをお願いします。' },
    { ordinal: 3, speaker: 'tutor', text: 'はい、どうぞ。' }
  ],
  remaining: 2, verdict: null, criteria: [], feedback: null
}

function railProps(frame) {
  const base = {
    width: frame.railWidth,
    courseTitle: 'Japanese affection and register',
    objectiveTitle: 'Choose the polite expression for a first confession',
    contextChip: 'Section 2',
    blockIndex: BLOCK_INDEX,
    sourceIndex: {},
    turns: TURNS,
    glossary: GLOSSARY,
    checkOpen: true,
    hint: { available: true, used: false },
    mode: 'ask',
    draft: '',
    busy: false
  }
  if (frame.surface === 'practice') {
    return { ...base, mode: 'practice', practiceAvailable: true, practice: PRACTICE, checkOpen: true }
  }
  if (frame.surface === 'no-lesson') {
    return { ...base, state: 'no-lesson', turns: [], glossary: [] }
  }
  if (frame.surface === 'quote') {
    return { ...base, quote: { text: 'There is no single Japanese line that means “I love you”.', blockId: 'blk_f36dfe1cee3b6f590096' } }
  }
  return base
}

for (const frame of payload.frames) {
  const props = railProps(frame)
  const body = renderToStaticMarkup(React.createElement(mod.TutorRail, props))
  const scope = css(mod.cbScopeStyle(frame.mode))
  const host = css(mod.cbHostVars(frame.mode))
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>GM-012 ${frame.id}</title>
<style>
html, body { margin: 0; padding: 0; background: ${frame.mode === 'dark' ? '#101214' : '#f4f1ea'}; }
body { font-family: ui-sans-serif, system-ui, sans-serif; }
[data-cb-scope] { padding: 16px; min-height: 100vh; box-sizing: border-box; }
</style></head>
<body><div data-cb-scope="${frame.mode}" style="${scope};${host}">
<div style="width:${frame.railWidth}px;max-width:100%">${body}</div>
</div></body></html>`
  writeFileSync(resolve(outDir, `${frame.render}.html`), html)
}
console.log(JSON.stringify({ renders: payload.frames.length, outDir }))
