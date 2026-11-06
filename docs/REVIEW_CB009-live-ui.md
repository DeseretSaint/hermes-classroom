# CB-009 live UI evidence — learning workspace (pane, Textbook, Notebook, Quizzes)

Run: isolated backend `127.0.0.1:44219` (own home `~/.hermes/coursebook-test/home`, plugin symlink
pointed at this worktree) + isolated Electron window (CDP 9222). Real seeded Japanese L0 course
`Japanese affection and register — an L0 demonstration classroom`, enrollment
`enr_544f0aba033e4fc0a2f50fb61aceda25`, contract v5 / 43 methods / `lesson.page`, `notebook.*` and
`review.*` all registered. The operator's gateway (PID 360123) was never touched.

## Defects found by driving the real UI, and fixed

1. **A section opened from the Textbook index never loaded its own `lesson.page`.**
   `TextbookView` kept the open-section id in local state while the `lesson.page` query was keyed on
   `CourseDetail.objectiveId`, so any section that was not the *current* objective rendered an
   endless "Reading this section" loader — the exact "go back to that section" path the spec calls
   the primary answer. Open-section state now lives in `CourseDetail` (`openSectionId`), so the
   Textbook list, Overview "Open this section", Notebook "Continue from here" and Quizzes "Review
   lesson" all aim the same request at the section being shown.

2. **`notebook.update` always failed.** The Desktop half sent `{entry_id, note, tags}` with no
   envelope `expected_revision`, so the backend answered
   `VALIDATION_FAILED: 'expected_revision' is a required property`. Edit note/tags is now fenced on
   the *entry's* revision (`notebook.list` already returns it) with an idempotency key. Verified
   live: the form closed, the new note rendered, DB row updated.

3. **A saved notebook entry erased section titles in the index.** `sectionRows()` merged sources
   with `{...existing, ...entry}`; a notebook row carries `title: null`, so saving a note renamed
   that section to "Saved section" in Textbook/Plan. Merge is now field-by-field and a null never
   overwrites a real label.

4. **Empty states silently dropped their action.** `sdk.EmptyState` accepts only `title` and
   `description`; every `children:` action in this module was discarded by React, so the
   filtered-empty Notebook (and the same pattern elsewhere) had no "Clear search and tag" button.
   A local `EmptyState` wrapper renders the action beneath the canonical component. Verified live:
   button present, click restores all rows.

5. **A failed `lesson.page` was an endless spinner.** `SectionPage` now renders
   `ErrorState` + "Try again" when the page query is in error, instead of a loader that never ends.

`node --check desktop/plugin.js` → OK after each step. All five defects are in the shipped
`desktop/plugin.js` of this branch; no Python, contract or pack file was changed.

## Captured states (`docs/cb009-shots`)

| shot | state |
|---|---|
| 01-course-detail-overview | course detail, Overview, real enrollment + review row |
| 02-textbook-objectives | Textbook index, four objectives with state + last-opened |
| 03-section-page-detached | section page for a non-current objective (defect 1 fixed), CURRENT CHECK, detached binding banner, Submit disabled |
| 04-notebook-save-dialog | Save to notebook: prefilled excerpt (2,457 chars), note, tags |
| 05/12-notebook-list | saved entry with tags + Open in textbook / Continue from here / Edit / Remove |
| 06/13-notebook-edit | edit form prefilled from the entry |
| 07/14-notebook-edited | edit saved, new note + `reviewed` tag rendered (defect 2 fixed) |
| 15-notebook-tag-menu, 16-notebook-tag-filter | tag filter → 1 of 4 rows |
| 17-notebook-filtered-empty | filtered-empty + working "Clear search and tag" (defect 4 fixed) |
| 18-continue-from-here | Continue from here lands on the exact section page |
| 19-quizzes-list, 20-quiz-review | 6 attempts; read-only review copy, criteria, provenance, dispute field |
| 21-quiz-dispute | dispute recorded, "DISPUTE HISTORY" rendered, original verdict unchanged |
| 22-quiz-new-version | `progression.challenge_out` refusal rendered honestly (no unused audited variant exists for this check) |
| 23-narrow-quiz-review, 24-narrow-textbook | 460×900: one labelled view picker (`#cb-view-picker`) instead of a clipped strip |
| 25-text-200 | root font-size 200% (32px) with the route still laid out |
| 08/09-view-* | all seven views (Overview, Textbook, Notebook, Quizzes, Plan, Evidence, Sources) |

Trace: `docs/REVIEW_CB009-ui-trace.json` (25 steps, DOM text after each action).

## Accessibility notes

- 95 visible buttons, 2 visible fields, 0 unlabelled fields; one nameless button in the capture is
  the **host session-tab overflow control** (outside this plugin, `data-slot="tool"`), not a
  Coursebook control.
- Focus ring: `focus-visible:ring-[0.1875rem]` present on SDK buttons; the reduced-motion rules and
  token-only styling are unchanged from CB-005.
- Tab order inside the plugin walks tab strip → section rows → answer field → Submit; the detached
  state disables Submit rather than hiding it, and the banner names the reason in text.
- Honest limit: the full keyboard-only run (Tab/Enter from the shell into the route, typing with
  `Input.insertText`, submit) is scripted in `scripts/cb009-keyboard.mjs` but did not finish inside
  this run's budget — it stalls walking the operator's ~40-session sidebar before reaching the pane
  (~120 focusables). What *is* proven: real `Input.dispatchKeyEvent` Tab moves focus through the
  shell and route controls (`scripts/cb009-tabtest.mjs` output), every control above is a native
  button/textarea with a text label, and the filtered-empty and edit paths were driven end to end.

## Known backend constraints (not UI defects)

- "Try a new version" answers `VALIDATION_FAILED: no unused, audited variant of this check exists`
  for this seeded course; the UI renders that refusal in place instead of pretending to succeed.
- `percent`-scaled text and narrow width were exercised on the Quizzes/Textbook views only.

## Reproduce

```
scripts/cb013-live-backend.sh          # isolated backend on 44219
scripts/cb013-live-window.sh           # isolated window (CDP 9222; the app's own renderer port)
CB009_CDP_PORT=9222 node scripts/cb009-ui-evidence.mjs
CB009_CDP_PORT=9222 node scripts/cb009-keyboard.mjs
```
