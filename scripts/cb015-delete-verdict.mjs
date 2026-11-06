#!/usr/bin/env node
/**
 * Re-derive `REVIEW_CB015-delete-paths.json`'s verdict from its own recorded steps.
 *
 * The probe's original `archiveRecoverable` predicate tested the row's innerText for the word
 * "Unarchive", which is a menu item and never appears in the row — so a run whose recovery
 * genuinely worked still scored false. This recomputes every field from the steps that were
 * actually captured and records where each value came from, instead of re-driving a path that
 * already consumed its fixture.
 *
 *   node scripts/cb015-delete-verdict.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs'

const path = 'docs/REVIEW_CB015-delete-paths.json'
const data = JSON.parse(readFileSync(path, 'utf8'))
const step = (name) => data.steps.find((s) => s.step === name)

const archivedHidden = step('archived-hidden-by-default')
const restored = step('unarchived-back-in-all')
const preview = step('delete-preview')
const deleted = step('enrollment-deleted')
const packPreview = step('pack-delete-preview')
const libraryBefore = step('library-before-pack-delete')

const verdict = {
  archivedHiddenByDefault: archivedHidden.rows === 1,
  archiveRecoverable: restored.rows === 2 && /Japanese affection/.test(restored.text),
  deleteScopedPreview: Boolean(
    preview.dialogText &&
      /Course and plan kept/.test(preview.dialogText) &&
      /Hermes transcripts kept/.test(preview.dialogText)
  ),
  deleteRemovedRow: deleted.rows === 1 && !deleted.dialogOpen,
  packPreviewKeepsEvidence: Boolean(packPreview.text && /Evidence kept/.test(packPreview.text)),
  packDistinctFromEnrollment: Boolean(libraryBefore.text && libraryBefore.text.includes('Preview'))
}

data.verdict = verdict
data.verdictBasis = {
  note:
    'Recomputed from the steps captured in this file. The probe\'s inline archiveRecoverable ' +
    'predicate tested the row text for "Unarchive", which is a menu item and never in the row; ' +
    'the recovery proof is that "unarchived-back-in-all" shows 2 rows with both titles after the ' +
    'menu action. No step was re-driven or invented.',
  perField: {
    archivedHiddenByDefault: 'steps.archived-hidden-by-default.rows === 1',
    archiveRecoverable: 'steps.unarchived-back-in-all.rows === 2 && /Japanese affection/ in its text',
    deleteScopedPreview: 'steps.delete-preview.dialogText names kept course and kept transcripts',
    deleteRemovedRow: 'steps.enrollment-deleted.rows === 1 and no dialog open',
    packPreviewKeepsEvidence: 'steps.pack-delete-preview.text contains "Evidence kept"',
    packDistinctFromEnrollment: 'steps.library-before-pack-delete.text renders Preview (pack), not enrollment actions'
  }
}

writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`)
console.log(JSON.stringify(verdict, null, 2))
