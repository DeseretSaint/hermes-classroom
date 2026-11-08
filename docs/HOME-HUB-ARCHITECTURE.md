# Coursebook home hub — architecture brief and vertical slice

Status: design only, 2026-11-07. No code, contract, migration or `desktop/plugin.js` change.
Read with `docs/UX-RESEARCH-STANDARDS.md`, `docs/FIELD-DESK-RESEARCH.md`,
`docs/MASTERY-PATH-RESEARCH.md`, `docs/DUOLINGO-RESEARCH.md`,
`docs/COURSEBOOK-VISUAL-IDENTITY-V2.md`, `docs/CONTRACTS.md` and `docs/STUDENT-MODE.md`.

## 0. Verdict

The hub is a **read model over rows Coursebook already owns**, not a new product domain.

1. A classroom slot is an existing **course + its active enrollment**. `learner_label` is its
   name; `enrollment_id` is the handle every progress read already takes.
2. **One slot per course.** Two enrollments on one course are one classroom with two progress
   records, because objective state and evidence summaries are course-scoped in the kernel.
3. **One primary action:** Continue for the selected classroom. The slot rail selects; it never
   renders N Continue cards.
4. **Checkpoints are check events, not save points.** A section node carries its own
   `check_state`; a checkpoint is the cold check that writes evidence (gate, delayed, cumulative,
   per `docs/MASTERY-PATH-RESEARCH.md` §3). No unlocks, XP, streaks, levels, badges or
   percentages.

The Field Desk already implements Continue, a numbered route and real evidence counts. The hub
adds classroom selection and checkpoint detail without changing the honesty model.

## 1. What already exists

| Surface | Reads today | Already gives | Missing |
|---|---|---|---|
| Field Desk (`plugin.js:2130-3260`) | `library.list` (50, recent), `course.outline`, `lesson.page` when sources open, `notebook.list` | Continue, section position, state-word path, three real counts, shelf, Field Notes | classroom choice, checkpoint detail, slot name |
| Courses list | `library.list` filters/search/sort, `enrollment.update`, `enrollment.delete` | archive, pause, previewed delete, `empty_reason` | home-level grouping |
| Course Detail | overview, textbook, notebook, quizzes, plan, evidence, export; `review.queue`, `evidence.inspect`, `jobs.list` | every per-section surface | — |
| Parent Studio | `library.list?recipe=parent`, `parent.brief.get`, `parent.blueprint.read`, `parent.export`, `parent.reflection.list` | a parent-led authoring list | a learner classroom |
| Contract | 64 methods, `cb.rpc` v14 | `learner_label` on `enrollment.create` and every `library_item` | any method to create, list or rename a “profile” |

## 2. What a slot can mean without a new entity

Four things are routinely conflated and must stay separate:

- **Hermes profile** (`bindings.profile`, `?profile=`): the data-isolation boundary. Never a child,
  a login or a classroom.
- **Course** (`courses`, `plans`, `objectives`, `checks`): the content. Never progress.
- **Enrollment** (`enrollments`, `attempts`, `evidence`, `lesson_runs`, `bindings`): the progress
  container and its `learner_label` (≤80 chars). Never an account or an identity.
- **Slot**: the `library_item` pair `(course_id, enrollment_id)` as the hub presents it. Never a
  new stored row.

**The load-bearing finding.** `objectives.state` is a single column per objective
(`migrations/0001_initial.sql:67`), and `library.list` computes `evidence_summary` and
`current_objective_id` by joining plans on `course_id`, not `enrollment_id`
(`coursebook/domain.py:2300-2355`). `_library_next_step` counts review-due objectives per course
too, and `enrollment.create` has no duplicate guard. Two enrollments on one course would therefore
display **identical evidence counts, current section and review state**, while holding separate
attempts. Presenting them as two learners is exactly the invented progress the product forbids.

So the hub groups rows by `course_id` and renders one slot per course. If a course has more than
one non-archived enrollment, the slot uses the newest row (`updated_at`) and discloses “This course
has N progress records; showing the most recent.” A genuinely separate classroom must be a
**separate course**; `pack.import` with `mode: "fresh"` already does that
(`coursebook/pack_flow.py:840-905`). Authored courses have no equivalent command; that is a roadmap
item, not a slice-1 workaround.

| Slot element | Source | Copy rule |
|---|---|---|
| Name | `learner_label`, else course `title` | never “Learner 1”; no generated avatar, no title from `subtitle` |
| Position | `evidence_summary.current_objective_id` + `course.outline` | “Section 2 of 4”, not “Level 2” |
| Evidence and due | `independent`, `total_objectives`, `review_due` | “2 of 6 sections have evidence · 1 due”, never colour-only |
| Time | `updated_at`; `outline_objective.last_opened_at` | “Last active” and “Last opened”, each naming its clock |
| Authoring | `jobs.list` counts for the enrollment | “Writing lessons”, never a percentage |

Today `learner_label` is NULL for pack imports and the course title for learner-created courses
(`plugin.js:4245`), so the rail reads as a course switcher until rename lands. That is honest; do
not invent “Learner 1” to make it look like profiles. `subtitle` is not the name either: for
blueprint courses it is the current unit label, which hides `learner_label` (`domain.py:2331`).

## 3. Modes

- **Learner hub:** `recipe != parent`, including `companion` syllabus courses and pack courses.
- **Parent Studio:** `recipe == parent`, its own destination and list. Parent enrollments have
  `learner_label = NULL` and are parent-led; they never become save slots or get a Continue. A home
  with only parent courses names Parent Studio and links there.
- **Hermes profile:** unchanged. A slot switch must not change `?profile=`, call
  `host.profileRoutes()`, or read another profile's rows. A cross-profile hub is a host feature,
  out of scope.
- **Navigation:** the hub replaces the desk *inside* Courses; the three destinations stay. A fourth
  “Home” destination is a later decision, not the slice.

## 4. Architecture

1. **Read layer.** One `library.list` (`filter: all`, `sort: recent`, `limit: 50`) feeds a pure
   `hubSlots(rows)` projection: drop `recipe === 'parent'`, group by `course_id`, keep the newest
   enrollment, sort by `updated_at`, cap the rail at four visible slots. `total` counts enrollment
   rows, not classrooms, so it is only a truncation signal: when it exceeds the returned rows the
   hub says “More classrooms on this profile” and links to Courses.
2. **Selection layer.** `selectedCourseId` lives in shell state (beside `openCourse`), not in the
   backend and not in localStorage. Existing reads are re-keyed from `rows[0].enrollment_id` to
   the selected slot's `enrollment_id`; returning from Course Detail restores the selection.
3. **Presentation layer.** Slot rail → Continue → checkpoint path → secondary shelf. The rail is
   navigation, not a card grid: up to four text tabs at ≥44px with `aria-current` and a
   weight/underline cue; above four, one labelled “Classroom” select. This is the single “Switch”
   in `docs/DUOLINGO-RESEARCH.md`: the active classroom is named, alternatives are visible, and no
   dashboard appears. No avatars, per-slot cover art or equal-weight cards.

**Continue** stays exactly one control and reads the selected row's `next_step.kind` and `label`
(`start_lesson`, `resume_lesson`, `resolve_review_due`, `rebind_session`, `review_plan`,
`review_pack`). The existing `mainlineObjective` rule is reused unchanged: due review wins, then
`current_objective_id`, then the first section without independent evidence.

**Checkpoints.** A path node is an `outline_objective`: ordinal, title, state, `check_state`,
`attempt_count`, `last_opened_at`, optional `unit`. The marker shows `check_state`, not a
decorative milestone. A checkpoint is the cold check event that writes evidence: a **gate check**
is the section's own check; a **delayed check** is the node reaching `review_due` and being
answered cold; a **cumulative check** over several nodes has no per-node representation today, so
the hub must not draw one. Its accessible name is “Checkpoint 3: <title>, Started”. Expanding it
may show the evidence target in learner words, the committed attempt count and the last-opened
time. It may not show a lock, star, percentage or “0/3 complete”. `overridden` is its own word and
is never counted as evidence; `settled` already excludes it.

## 5. Data and contract implications

**Slice 1: none.** Every field is already on the wire. No method, schema, enum, migration or
version change; `cb.rpc` stays v14, `cb.db` v10. The only new artifact is a pure function and a
render path.

| Later ask | Change | Risk |
|---|---|---|
| Rename a classroom | Add `rename` to `enrollment.update`, or a revision-fenced `enrollment.rename`, writing the existing nullable `learner_label` | Low. No migration; the fence exists. Must not touch evidence. |
| New classroom from an authored course | `course.duplicate`/`plan.fork` copying plan, objectives and checks with objective state reset | High. State must reset to `not_started`; new check rows and ids; approval hashes; a half-copy is worse than none. |
| True multi-learner profiles on shared content | Move objective state to a per-enrollment projection, then update `attempt.submit`, review derivation, `library.list`, `course.outline`, `evidence.inspect` and L2 | Highest. Migration, backfill, every state reader/writer. |

No `learner_label` filter is needed at hub scale: `library.list.query` matches it (`domain.py:2267`).

## 6. Migration risk

No migration in the slice. The risks are behavioural, each with a guard:

- **Duplicate-enrollment illusion** → one slot per course, plus the disclosure above.
- **Profile confusion** → “classroom” only for enrollments; `profile` reserved for the host scope;
  a test asserts slot changes never alter `?profile=`.
- **Parent leakage** → filter `recipe: parent` in the projection, not the template.
- **Paging and archived slots** → dedupe before counting; `total` is an enrollment count, used
  only as a truncation signal. `filter: all` already excludes archived; `empty_reason:
  all_archived` explains a home that only has archived work.
- **Stale selection** → a slot deleted or archived between read and open returns `NOT_FOUND`;
  reload, keep the other slots, say the classroom is gone.

## 7. Empty, loading, error, offline

A first load shows a loader in the Continue card's shape, never the first-run plate.

| State | Hub shows | Action |
|---|---|---|
| Failed, no rows | “This hub will not show an empty classroom in place of a failed read.” | Try again, Open Capabilities |
| Failed with cached rows | keep slots, stale banner, no clearing | Try again |
| No courses | existing first-run plate | Start with a goal |
| Only parent courses | “Parent Studio holds your lesson plans.” | Open Parent Studio |
| All archived | “Every classroom here is archived.” | Open archived courses |
| Selected slot's outline fails | Continue still works from the row's `next_step`; the path shows its own error | Try again |
| Plan is a draft | the path says the plan needs approval; primary is Review the plan | Approve |
| Offline | existing `useOnline` badge and “paused” sentence; reads may be stale | none; no writes |

A failed read never renders as an empty course; an unrecorded value says “not recorded”, never a
derived number.

## 8. Vertical slice

**Card:** “Home hub: classroom rail, Continue, checkpoints”. Desktop only.

1. `hubSlots(rows)` pure projection, exported for tests.
2. `SlotRail` above Continue, with tabs/select and selected state in words.
3. Selected-slot state in the shell; every desk read re-keyed; selection survives Course Detail.
4. `CheckpointPath` replacing `PathPreview` in place: accessible names, state words, `check_state`
   on the marker, expandable evidence target and committed attempt count.
5. Parent exclusion and the empty/error table above.
6. Narrow layout: rail wraps or becomes a select; titles wrap; no overflow at 460.

Out: renaming, creating a classroom, persisting selection, per-child profiles, unit chapters, job
badges, avatars, new chrome. **Files:** `desktop/plugin.js` (one block) and
`tests/test_desktop_home_hub.py`; no backend, contract or migration file.

**Acceptance tests (proposed):**

1. `test_one_slot_per_course_and_duplicate_enrollments_are_disclosed_not_split`
2. `test_slot_name_uses_learner_label_then_course_title_and_never_invents_one`
3. `test_parent_recipe_rows_never_appear_as_learner_slots`
4. `test_continue_reads_the_selected_slots_next_step`
5. `test_selection_survives_course_detail_and_back`
6. `test_library_failure_is_not_an_empty_hub`
7. `test_slot_count_uses_deduped_rows_and_total_only_as_truncation`
8. `test_checkpoint_marker_reads_check_state_and_never_invents_a_gate`
9. `test_checkpoint_copy_has_no_lock_star_xp_streak_or_percentage`
10. `test_slot_switch_never_changes_the_profile_scope`
11. `test_narrow_hub_has_no_horizontal_overflow_and_44px_targets`
12. `test_hub_paints_only_token_layer_values`

Existing suites that must stay green: `test_desktop_field_desk.py`, `test_desktop_tokens.py`,
`test_desktop_contracts.py` and `test_single_home_scope.py`.

**Evidence to capture:** 1280/900/460, light/dark, 200% text, reduced motion, keyboard order and axe
`wcag22aa`; the RPC trace, not a screenshot, proves the counts.

## 9. Roadmap

- **Slice 2 — naming and a real second classroom.** Rename (low-risk contract add); “Start a new
  classroom from this pack” via `pack.import` fresh; a per-slot `jobs.list` line so “writing
  lessons” is visible before the slot opens. An authored-course fork only if a household asks.
- **Slice 3 — chapters and review.** Group path nodes by `outline_objective.unit` (≤12, already on
  the wire); a delayed checkpoint opens `review.queue`; a quiet `evidence.inspect` peek, L1/L2 only.
  A cumulative checkpoint needs unit-scoped checks that do not exist: a contract and storage card.
- **Slice 4 — true multi-learner.** Only after the per-enrollment objective-state decision in §5.
  That is when “profile slot” becomes honest, and it is a data-model card, not a UI card.

## 10. Refusals

The hub will not: invent a learner profile, account or avatar; show two slots for one course;
count override as evidence; show a mastery percentage, ring, streak, XP, level or badge; lock a
section; draw a cumulative checkpoint the backend cannot record; call the newest row “last played”;
persist a selection as progress; move a parent course into the learner rail; or switch the Hermes
profile.
