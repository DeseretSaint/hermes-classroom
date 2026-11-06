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
   live: the form closed, the new note rendered, DB row updated (`nbt_d2428445…` revision 0 → 1).

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

6. **The pane stayed pinned to the chat it first mounted with.** `useHostValue` used the host's
   `sdk.useValue`; in this Desktop build that did not re-render the pane when
   `host.state.focusedStoredSessionId` changed, so after switching chats the pane kept rendering the
   previous chat's binding (confirmed: hash `#/20261106_072357_ad7e67`, binding row active for that
   stored id, pane still drawing `20261106_070925_0df5fc`'s detached lesson). The hook now
   subscribes to the atom directly and keeps the value in local state, and the pane refuses to
   render a binding whose `stored_session_id` differs from the focused one. Verified both
   directions: `#/` → "No durable chat yet"; `#/20261106_072357_ad7e67` → pane attributes
   `data-cb-stored-id=20261106_072357_ad7e67`, `data-cb-binding-id=bind_eacdfd2382ed494582a00539e84b3465`.

7. **A cold window mount sent `contract_version: 1`.** The pane renders before the `/runtime` probe
   resolves, and `rpc()` used the module default. A v5 backend answered
   `VALIDATION_FAILED: contract_version: 5 was expected`, so a freshly reloaded window could not read
   its binding until a later re-render. `rpc()` now awaits the cached `ensureBackendWire()` probe
   before building the envelope. Verified: after a `Page.reload` the pane reads its binding on the
   first attempt.

`node --check desktop/plugin.js` → OK after each step. All seven defects are in the shipped
`desktop/plugin.js` of this branch; no Python, contract or pack file was changed.

## Bound chat + Coursebook context pane (this run's new evidence)

`scripts/cb009-pane-chat.mjs` (fresh run) and `scripts/cb009-pane-check.mjs` (resume), stills in
`docs/cb009-shots/pane-*.png`, traces `docs/REVIEW_CB009-pane-chat.json` /
`docs/REVIEW_CB009-pane-check.json`.

- `pane-02` / `pane-12`: a real chat with the right rail open, pane reading
  "This lesson is bound to this chat." and the course + current section + `CURRENT CHECK`.
- `pane-13`: answer typed into the **pane's** field; `pane-14`: the pane's own verdict
  (`Check v2`, `Hinted`, **Not yet**) and the "Hints and shown answers are recorded…" note.
  The committed row is `att_fe25ed63d461474383c4be5fc544e50c` on `chk_2ebc1f63…` (`not_yet`,
  `hinted`).
- One lineage, not a recency guess: the chat turn and the pane submission are the **same check** —
  `att_94f3351b…` (chat turn, `cold`), `att_fe25ed6…` (pane, `hinted`), `att_d050fbfb…` (keyboard,
  `hinted`) all on `chk_2ebc1f639d384a77874f4dece8303171` for `obj_2ec4b8ec075e459ab158f3f356717b68`.
  The section page's `ATTEMPTS ON THIS SECTION` list shows the same rows in order.
- `pane3-02`: the **detached** pane in a chat — banner names the state in text, Submit is disabled
  with its reason, and `Reattach` / `Start a new run` / `Abandon binding` are present.

## Keyboard-only and text-only path

`scripts/cb009-keyboard.mjs`, trace `docs/REVIEW_CB009-keyboard-trace.json`, stills
`31-keyboard-route` … `34-keyboard-submitted`. Every step is `Input.dispatchKeyEvent`
(Tab / Shift+Tab / Enter / ArrowDown) plus `Input.insertText`; no `.focus()` and no `.click()`
after the run starts, which begins with focus blurred to `document.body`.

- 27 Tabs reach the **Coursebook** nav entry; Enter opens the route (hash verified).
- 95 further Tabs cross the host session sidebar to **Open**; Enter opens the course.
- With the context pane open the route is narrower than 47.5rem, so the canonical tab strip is
  `display:none` and the labelled `Select` (`aria-label="Course view"`) is the control: 3 Tabs,
  Enter, then `ArrowDown` to **Textbook**, Enter.
- 1 Tab to the first `Open section`, Enter; 5 Tabs to `#cb-attempt-answer`; `Input.insertText`
  types the answer; 1 Tab to **Submit answer**, Enter.
- Result: verdict rendered (`Not yet`, `Needs review`, `Hinted`) and a committed attempt
  `att_d050fbfb1e8e43129cc1dab90c635b77` — produced by keyboard input, not by a click.
- 147 recorded focus stops in total. The 95-stop crossing exists because the host restores focus to
  the sidebar nav when a route re-renders and the sidebar holds ~40 operator sessions; that is shell
  behaviour outside this plugin (no Coursebook control is skipped or traps focus).

Text-only audit from the same run: 119 visible controls, **1** without any text or accessible
name, and it is the host's `data-slot="tooltip-trigger"` pane-header control, not a Coursebook
control.

## Layout at narrow width and 200% text

`scripts/cb009-layout-probe.mjs`, `docs/REVIEW_CB009-layout-probe.json`:

| viewport | document overflow-x | pane box | composer |
|---|---|---|---|
| 944×688 | 0 px | 294×496, on screen | on screen |
| 460×900 | 0 px | 340×666, on screen (pane tab labelled with the session title) | on screen |
| 944×688 @ 200% root (32px) | 0 px | 163×460, on screen | on screen |

No horizontal overflow at any of the three; the pane's own labels wrap/scroll instead of clipping
the route. At 460px the right rail overlays the transcript rather than shrinking it, and the rail's
own tab strip names the pane ("Casual vs polite affection difference", "Terminal").

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
| 31–34-keyboard-* | keyboard-only walk: route, section, typed answer, submitted verdict |
| pane-01…07, pane3-*, pane-17/18 | bound chat + pane, pane verdict, detached pane, measured narrow/200% |

Traces: `docs/REVIEW_CB009-ui-trace.json` (25 steps), `docs/REVIEW_CB009-pane-chat.json`,
`docs/REVIEW_CB009-pane-check.json`, `docs/REVIEW_CB009-keyboard-trace.json`,
`docs/REVIEW_CB009-layout-probe.json`.

## Accessibility notes

- 95 visible buttons, 2 visible fields, 0 unlabelled fields in the route capture; the one nameless
  button in the wider audit is the **host session-tab overflow control** (outside this plugin,
  `data-slot="tooltip-trigger"`).
- Focus ring: `focus-visible:ring-[0.1875rem]` present on SDK buttons; the reduced-motion rules and
  token-only styling are unchanged from CB-005.
- Tab order inside the plugin walks view picker → section rows → answer field → Submit; the detached
  state disables Submit rather than hiding it, and the banner names the reason in text.
- The keyboard run above is the complete keyboard path; its only compromise is that the host
  sidebar (40 operator sessions, 95 stops) precedes the route in tab order.

## Known limits (honest)

- **The pane shows the enrollment's current section, not always the chat's own section.** `lesson.page`
  is keyed on `row.evidence_summary.current_objective_id` because `binding.get` does not return
  `objective_id`/`lesson_run_id` (its response schema is an open object; the DB has both columns).
  A chat bound to section 3 therefore displays section 1's page and section 1's run status. The
  desktop half already prefers `binding.objective_id` when present; the gap is the binding payload.
  Filed as a follow-up card for the backend owner rather than guessed around in the UI.
- "Try a new version" answers `VALIDATION_FAILED: no unused, audited variant of this check exists`
  for the seeded course: three objectives are already at check v2 and every remaining check has one
  audited variant. The refusal is rendered in place; a success capture needs a pack with an unused
  variant.
- Percent-scaled text was measured on Textbook/Quizzes and on the chat+pane; Plan/Evidence/Sources
  were captured at default scale only.
