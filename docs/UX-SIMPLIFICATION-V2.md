# UX simplification v2 — H-84 copy, hierarchy and interaction diet

Status: applied on top of H-82's token layer and H-83's Atlas Lamp lesson shell. Binding reference:
`docs/UX-RESEARCH-STANDARDS.md`. This pass changes language, label typography and dead decoration.
It does not change grading, evidence, permissions or any recorded fact.

Scope note: first-run onboarding, persistent wayfinding and New Course step guidance are owned by
H-86 (`t_d0498dd5`). Nothing here builds that; the copy below is written to sit under its start
plate.

## 1. Before / after copy

| Surface | Before | After | Why |
| --- | --- | --- | --- |
| Section shell, no chat | This lesson has no durable chat to resume yet. | This lesson has no chat to return to yet. | "Durable chat" is implementation detail; the limitation is unchanged. |
| Section shell, bound chat | This lesson's chat binding is active/paused/detached. | This lesson is not connected to a chat right now. | A stored status enum was printed at the learner. |
| Section shell, detached | This lesson's chat binding is detached. Submitting is disabled until it is rebound. | This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat. | What happened + what to do; the disabled control is explained and has a path. |
| Check verdict | This lesson's chat binding is detached. Submitting is disabled until it is reconciled. | Same plain sentence as above. | "Reconciled" is an internal repair word. |
| Section start | Lesson run ready. The section is open below; the lesson chat binds to the first message you send in it. | The lesson is ready. Your section is open below. The chat becomes this lesson's chat when you send your first message. | "Binds" replaced with the behaviour it describes. |
| Course detail | A fresh governed run is ready. Its chat binds after your first message. | A new lesson run is ready. Its chat connects when you send your first message. | "Governed run" is internal. |
| Lesson chat page | This chat is not attached to a lesson yet. Open Coursebook and start a run; the first message in its new chat binds the lesson. | This chat is not part of a lesson yet. Open Coursebook and start a lesson; the first message in its new chat connects it. | Plain words, same instruction. |
| Lesson chat page | This chat is the lesson chat for that run. Send the first message and Coursebook binds it to the run. | This chat belongs to that lesson. Send the first message and Coursebook connects it to the run. | Plain words. |
| New lesson chat | A new lesson chat is open. Send its first message to bind it to this run. | A new lesson chat is open. Send the first message to connect it to this lesson. | Plain words. |
| Chat header | This chat has no lesson binding. A bound chat shows its current objective and check here. | This chat is not part of a lesson yet. A lesson chat shows its current objective and check here. | "Binding" removed. |
| Course detail, mismatch | This chat is bound to an enrollment the library did not return. Nothing is guessed from that: reopen Coursebook to reconcile. | This chat is connected to a course the library did not return. Nothing is guessed: reopen Coursebook to check it. | "Enrollment"/"reconcile" removed. |
| Section gate | This lesson's chat binding is X; reconcile it first. | This lesson is not connected to its chat right now. Open it from the course page first. | Plain words + next action. |
| Errors | Could not read this course's binding. / Could not read this pack's lesson binding. | Could not read which chat belongs to this course / to this lesson. | Names the real object. |
| Evidence tab | Evidence criteria, attempt counts and dial edits need the objective read/write commands that this build does not publish yet; nothing is invented to fill the gap. | This build cannot edit evidence criteria, attempt counts or settings yet. Nothing is filled in to hide that. | Keeps the limitation, drops the API vocabulary. |
| Connection panel | The Desktop half is enabled but its Python backend is not answering for this profile. | Coursebook is turned on in Desktop, but its backend is not answering for this profile. | Same fact; "Desktop half" was internal. |
| Pack export | The link is the host route the backend named: the session is checked there, the handle… | The link points at the session the backend named. The handle… | Fewer clauses, same boundary. |
| Course path empty | The backend returned no objectives for this course, so there is no path to show yet. | This course has no objectives yet, so there is no path to show. Approve its plan to start one. | Empty state gains the next action. |
| Sources empty (section) | The backend recorded no sources for this section. | No sources are recorded for this section yet. | Same fact, no service name. |
| Sources empty (course) | The backend recorded no sources for this course. / The backend recorded no source rows for this course. Nothing is being presented as cited. | No sources are recorded for this course yet. / No sources are recorded for this course. Nothing here is presented as cited. | Same disclosure, plainer. |
| Contract error | The backend answered with something that is not a contract envelope. | Coursebook answered with data it could not read. | What happened, in the learner's terms. |
| Field Quest counts | Counts describe evidence the backend already recorded. They are not a score, nothing here is locked, and the checkpoint is the section's existing check. | Counts describe evidence already recorded. They are not a score, nothing here is locked, and the checkpoint is the section's own check. | Same honesty, fewer implementation words. |
| Procedure hazard | Do not proceed (all caps) | Do not continue (sentence case) | Sentence case for UI copy. |
| Procedure schematic | Deterministic schematic · structured facts / Deterministic schematic drawn from the structured facts below. / Deterministic schematic rendered from structured facts. | Drawing from the steps below / Drawing made from the steps below. / Drawing made from these steps. | "Deterministic" is an implementation claim, not learner language. |
| Teaching segments | TEACHING SEGMENTS with raw `segment.kind` (`check_prompt`, `orientation`, …) | Teaching segments with a plain word per kind (Check, Getting started, …) | No internal enums at the learner. |

Every limitation that was there is still there: no chat means no resume, a detached lesson means
Submit is off, parent reports are not independent evidence, counts are not a score, and an
unreviewed export is not exported.

## 2. Label typography and decoration (lesson-shell conformance)

| Rule | Before | After | Location (desktop/plugin.js) |
| --- | --- | --- | --- |
| No all-caps UI labels | `textTransform: 'uppercase'` on 8 label sites (desk label, stat captions, plate label, rail label, workspace eyebrow, hazard label, schematic caption, unit label) | 0 occurrences of `textTransform: 'uppercase'` | `deskLabel`, `DeskStats`, `PlateHead`, `FieldRail`, `WorkspaceShell`, procedure hazard, schematic caption, guided unit label |
| Label floor 0.75rem | 0.6875rem / 0.66rem / 0.65rem / 0.63rem labels | 0.75rem at every one of those sites | same sites |
| No decorative kicker above a heading | `eyebrow` block above the workspace `h2` (no caller passed one) | removed | `WorkspaceShell` header |
| No thick decorative edges | three `borderTop: '3px'` rules and one `borderLeft: '3px solid coral'` | 1px rules (the coral edge is now a 1px functional state rule) | continue card, hero field, parent plum band, procedure hazard |
| Hero facts stay a line | already a single line at 1rem value / 0.8125rem caption | unchanged; verified in the live capture | `HeroFacts` |

`PanelSectionLabel` (host component, renders uppercase via host CSS) is replaced by a local
`CbLabel` at 0.75rem sentence case across 53 call sites, so the uppercase was not just renamed.

## 3. Live captures

`audit/ux/round3/h84-live/` holds nine real CDP captures from the isolated window on port 9337 with
the repo plugin symlinked in: field desk, course detail and a section in Textbook, each at
1049/900/460 CSS width (1048/899/459 measured innerWidth). Every one reports `overflowX: 0` on the
route at 1049 and 900, no computed `text-transform: uppercase` inside `[data-cb-route]`, no border
above 1px, and one `h1` on the course detail and section routes.

At 460 the host itself does not reflow: it leaves the Coursebook route a 214px pane between its own
sidebars, so the route's content overflows that pane by 15px while the document body overflow is 0.
That is host chrome, matching H-83's finding, and it is not fixed here. The `<aside>` navigation
labels ("Courses", "Library", "Parent Studio") are the host's own 11px chrome.

Host `sdk.Badge` chips ("Textbook only", "Plan update") still render at 9.6–10.4px from host CSS;
they are chips rather than labels, but they are below the 0.75rem floor and are listed here as
remaining debt, not as fixed.

## 4. What was checked, and what was not

Checked with real output: `node --check desktop/plugin.js`; the full Python suite; M4 visual audit
regenerated and re-pinned to the new plugin hash (15/15 claims PASS); `validate-plugin.sh` on the
committed HEAD; live CDP captures in `audit/ux/round3/h84-live/`.

Not changed here, by design: grading, evidence classes, permission prompts, export gates, pack
schema, the host's own chrome, and H-86's onboarding surfaces. The word "objective" stays: the plan
review and the evidence list both use it as the course's own unit, and it is labelled where it
appears.
