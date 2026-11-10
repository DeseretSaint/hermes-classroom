# Game Mode contract (GM-001, frozen)

Status: **frozen for the Game Mode program**. Authority: this document plus
`coursebook/gm_contract.py` (executable constants) and `contracts/db.v13.json` (storage inventory).
The product plan is `docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`; where a name here differs from the
plan's earlier draft, **this document wins** and the difference is listed under "Naming decisions".

Source documents for this card were read from the operator checkout, where
`docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`, `docs/GAME-MODE-ADVERSARIAL-REVIEW.md` and
`docs/GAME-MODE-CARD-DAG.md` are still untracked at the time of writing. They are not part of this
branch; this contract is self-contained and does not depend on them at runtime.

Nothing in this card makes a provider call, renders a screen or registers a handler. This card
removes naming and data ambiguity before the six backend cards and five UI cards collide.

## 1. What is additive-only

A frozen name below may be **added to** but never renamed, retyped or reused for another meaning.
No existing method, type, table, column, error code, job kind, transition, evidence class or
vocabulary value moves.

| Layer | Frozen here | Deliberately unchanged |
|---|---|---|
| Storage | `cb.db` v13: `courses.presentation_mode` (nullable) and eight new tables via `0013_game_mode_contracts.sql` | Every v12 table, column, index and unique key; every lesson, attempt, transition and evidence row |
| Wire | 18 Game Mode method names plus `course.mode.set`, frozen in `GM_RPC_METHODS` | `cb.rpc` v20 itself: no method is added to the wire contract in GM-001. GM-009 adds two at v21, GM-011 adds the tutor pair at v22, GM-005 adds the six take-home methods at v23 and GM-007 adds the four homework methods (`homework.create`, `homework.read`, `homework.complete`, `homework.skip`) at v24 |
| Errors | The set of existing `cb.errors` v4 codes each method may return | `cb.errors` v4: no new code |
| Jobs | `world.generate` is `kind=media` with `brief.stage` `world_concepts` / `world_kit` | `cb.jobs` v5: no new kind, no new job field |
| Evidence | Nothing | The evidence store is not extended. There is no second evidence store. |

**Why `cb.rpc` is not bumped in GM-001.** The manifest is the freeze, not the wire. The first
implementation card that registers one of these names bumps `cb.rpc` past v20 (GM-009 did so at
v21, adding `engagement.read` and `engagement.award`; GM-011 did so at **v22**, adding `tutor.ask`
and `tutor.history` — both documented in `docs/CONTRACTS.md`); until then a handler for these names
cannot be registered (`api.register_handler` rejects a name that is not in `cb.rpc`), which is the
intended fence. The remaining Game Mode names land with their own handlers.

## 2. Course modes

`courses.presentation_mode` is the durable course mode. It is **nullable**, and a `NULL` or
unrecognised stored value **reads as `textbook`**:

| `PresentationMode` | Stored | Meaning |
|---|---|---|
| `game` | `game` | Plan plus an approved course world. Field Quest is the default lesson view; Guided and Textbook remain available views |
| `textbook` | `textbook` or `NULL` | Plan only. Textbook is the default view; Guided remains available. No generated world art; deterministic or sourced instructional media may still render |

Rules:

- No backfill. An existing course keeps `NULL` forever until the learner explicitly switches. The
  read fallback is `read_presentation_mode(stored)`, and it never writes the fallback back.
- Switching never rewrites objectives, checks, attempts, evidence or lesson text.
- Switching Game to Textbook is immediate and keeps the world and its assets hidden but intact.
- Switching Textbook to Game requires an **approved** world. Without one the command reports
  `requires_world=true` and a reason; it does not silently change the mode.
- `Guided` is a **lesson view**, not a third course mode and not a world.

## 3. World

### 3.1 Grammar

| `WorldGrammar` | Best fit | Cannot do |
|---|---|---|
| `field_atlas` | languages, humanities, general learning | pretend a map is a geography lesson |
| `workshop_manual` | auto repair, trades, engineering procedures | show a torque value, clearance or sequence as art |
| `observatory` | astronomy, physics, natural science | use an AI sky image as a measurement |
| `kitchen_table` | cooking, home skills, food | present a generated dish as a tested recipe |
| `archive_desk` | history, law, business, research | invent a source or a quotation |
| `studio_bench` | art, music, design | present generated art as a technique authority |
| `lab_bench` | biology, chemistry, lab safety | use art as a safety or measurement reference |
| `instrument_board` | mathematics, logic, symbolic work | make an AI illustration a required lesson visual |

`DEFAULT_WORLD_GRAMMAR = field_atlas`, because it is the house style. It is a starting point, not
permission to put lanterns on a head-gasket course. A technical-procedure course cannot select a
decorative-only grammar, and a symbolic course cannot make an AI illustration a lesson visual.
The selection is deterministic and testable (`WorldPolicy`, GM-003); the anti-generic swap test is
mandatory.

### 3.2 Roles and budget

| `WorldRole` | Cardinality per world | Purpose |
|---|---|---|
| `hero` | 1 | course-home image |
| `cover` | 1 | library card image |
| `section` | ≤ 6 | one card per section |
| `lesson_scene` | ≤ 2 | one scene for a lesson that genuinely needs place |

The budget is enforced by the backend (`WORLD_ROLE_LIMITS`) and by the
`UNIQUE (world_id, role, section_key)` key, not by UI discipline. A retry reuses the cache key
`style_hash + course_hash + role + section_id`; it never pays twice for the same plate.

Every plate is textless. `WORLD_PROMPT_FORBIDDEN` names the hard negatives every prompt carries:
text, letters, labels, numbers, logos, watermarks, UI chrome, invented measurements, depicted
safety procedure. Real text is DOM.

### 3.3 World state machine

This is a **state diagram, not a production mock**:

```
not_requested -> concepts_generating -> concepts_ready -> style_selected
              -> kit_generating -> kit_ready -> approved
                    |                  |
                    +--> failed        +--> stale  (plan's subject/section set changed)
unavailable (provider not configured)
```

`approved` is the only state that permits Game-mode lesson build. `stale` keeps the existing
approved art visible and readable. `failed` and `unavailable` leave the course in Textbook
presentation; no fake world is ever created and no silent lesson build happens.

### 3.4 Approval is hash-fenced

`world.approve` takes `stage=style|final` and the caller's `approved_hash`. Style approval
records the selected concept; final approval accepts the actual kit and freezes `approved_hash` on
`course_worlds`. A kit that changed after preview cannot reuse the earlier approval. Plan approval
and world approval are **separate facts**; neither silently approves the other.

`world.generate` is a **media job**, never a lesson job: `kind=media`,
`brief.stage=world_concepts|world_kit`. Artifact bytes are staged before the row is written, so a
retry resumes on the cache key instead of double-spending.

## 4. Take-home

`takehome_packs` is a rendered print artifact, **not** a course and **not** a `cb.pack`.

| Field | Meaning |
|---|---|
| `source_course_id` | the course the content came from; never cloned, never mutated |
| `source_objective_id` | the objective the pack teaches |
| `source_lesson_version` | the validated lesson document version the pack renders |
| `content_hash` | hash of the exact source lesson content; approval is fenced on it |

| `TakeHomeAudience` | Who reads it |
|---|---|
| `learner` | the learner page: one activity, one target, one success criterion, **no answer key** |
| `parent` | parent guide and the separate answer guide |

| `TakeHomeKind` | Deliverable |
|---|---|
| `print_pack` | parent guide + learner page + separate answer guide + sources |
| `activity_plan` | a short parent-led activity |
| `homework_sheet` | one-page sheet carrying one task |

| `TakeHomeState` | Meaning |
|---|---|
| `draft` | being edited; approval is not possible |
| `previewed` | pages rendered and `preview_hash` recorded |
| `approved` | `approval_hash` frozen over the previewed pages |
| `exported` | finished artifact recorded on `artifact_id` |
| `superseded` | a newer revision replaced it; the row is kept |

Rules: the pack uses the source lesson's exact text and check content; it does not regenerate the
lesson to print it. A parent edit invalidates the pack approval, never the source course. Export
requires an explicit preview and approval of the actual pages. The learner page never contains the
answer key or a fake score. Print output uses selectable text, real margins, alt text and no
color-only meaning. World art in a pack is captioned orientation only.

## 5. Homework

`homework_tasks` is a **one-task object**, not a course, not a chat thread and not a check.

| `HomeworkKind` | Task shape |
|---|---|
| `real_world_use` | use the target in a real interaction |
| `observe` | notice the target in context |
| `label` | label real objects with the target |
| `practice` | rehearse the target aloud |
| `make` | build something that uses the target |
| `teach_back` | explain the target to someone |

| `HomeworkState` | Meaning |
|---|---|
| `proposed` | generated, not accepted |
| `assigned` | the learner or parent accepted it |
| `self_reported_done` | the learner reports completion |
| `parent_reported_done` | the parent reports completion |
| `skipped` | declined honestly; no penalty |
| `expired` | the window passed; no guilt copy |

Every task carries exactly one `target`, one `context`, at most three steps and one observable
`success_criterion`. `estimated_minutes` is CHECK-bound to **3..10**; "practise for ten minutes"
is not a task and is refused. `homework_events` is append-only and records the actor
(`learner` | `parent`).

**Completion is never a pass.** `HOMEWORK_COMPLETION_STATES` is exactly
`self_reported_done`, `parent_reported_done`. No homework command writes a verdict, an evidence
class, a transition or a mastery claim; a retrieval check in the course is a separate act.

## 6. Game engagement

`game_engagement` is the play layer. It is separate from attempts and evidence and is **excluded
from parent, pack and export reads**.

| `EngagementAction` | Awarded for |
|---|---|
| `lesson_step` | a completed lesson step |
| `check_submitted` | a submitted check |
| `review` | a completed review |
| `homework_completed` | a reported-complete homework task |
| `returned` | returning after an interval |

One row per real action: `UNIQUE (enrollment_id, action_kind, action_id)` makes a replay
idempotent. No XP for opening a page, clicking a button or idle time. XP is not mastery, not
proficiency and not evidence; no screen may call it any of those, no core lesson is gated behind
it, and Textbook/Guided/Parent Studio never render it. A course switching Game to Textbook keeps
the rows and hides them.

## 7. Tutor

`tutor_threads` binds to a **lesson run** (`lesson_run_id`, `UNIQUE`), never to a host chat session.
`tutor_turns` is append-only, `role` in `learner | tutor`.

| `TutorMode` | Meaning |
|---|---|
| `ask` | lesson Q&A in the rail |
| `practice` | the existing `practice.*` scene rendered in the same thread |

A turn is never an attempt, a transition or evidence; the grader never reads tutor prose; tutor
turns are excluded from pack and course export. The tutor has no shell, browser, file or authoring
tools, and its context envelope excludes answer keys, checks, rubric and learner attempts. While a
check is open it does not reveal the answer; a hint is recorded through the existing assist path.

**Implementation (GM-011, `cb.rpc` v22).** `coursebook/tutor.py` registers `tutor.ask` and
`tutor.history`; `tutor.ask` fences on the enrollment revision and its context is built from the
served lesson document, the authored glossary, the objective and the learner's recent turns. A
reference-answer match while a check is open returns `state: "answer_withheld"` and persists only a
safe message; a provider failure returns `state: "provider_failure"` with `turn: null` and nothing
written. `mode: "practice"` appends to the existing `practice_turns` log and never calls the
grader — only learner turns can produce a verdict.

## 8. Method manifest

`coursebook/gm_contract.py::GM_RPC_METHODS` is normative. Field tuples are **closed** key sets: a
handler accepting or returning a key outside them is a contract bug. `kind` is `read` or `mutate`.
Every `mutate` is idempotent and returns the existing error shape; `engagement.award` is the only
mutation without `expected_revision` because it is an append-only event keyed by the real action.

| Method | Kind | Fence | Provider | Request | Response |
|---|---|---|---|---|---|
| `world.read` | read | — | no | `course_id` | `course_id`, `presentation_mode`, `world`, `fallback`, `revision` |
| `world.style.preview` | read | — | no | `course_id`, `world_id` | `course_id`, `world_id`, `concepts`, `selected_concept_id`, `revision` |
| `world.generate` | mutate | revision + key | **yes** | `course_id`, `stage`, `style_id`, `brief_patch`, `expected_revision` | `job_id`, `state`, `world_id` |
| `world.approve` | mutate | revision + key + hash | no | `course_id`, `world_id`, `stage`, `approved_hash`, `expected_revision` | `world`, `state`, `style_hash`, `kit_hash`, `approved_hash`, `assets` |
| `takehome.sources` | read | — | no | `course_id`, `query` | `course_id`, `objectives`, `presentation_mode` |
| `takehome.preview` | read | — | no | `course_id`, `objective_id`, `source_lesson_version`, `audience`, `kind` | `content_hash`, `preview_hash`, `pages`, `sources` |
| `takehome.create` | mutate | revision + key | no | `course_id`, `objective_id`, `source_lesson_version`, `audience`, `kind`, `title`, `expected_revision` | `pack_id`, `state`, `revision`, `content_hash` |
| `takehome.approve` | mutate | revision + key + hash | no | `pack_id`, `preview_hash`, `expected_revision` | `pack_id`, `state`, `approval_hash`, `approved_at` |
| `takehome.export` | mutate | revision + key | no | `pack_id`, `expected_revision` | `pack_id`, `state`, `artifact_id`, `exported_at` |
| `takehome.read` | read | — | no | `pack_id` | `pack` |
| `homework.create` | mutate | revision + key | **yes** | `course_id`, `enrollment_id`, `objective_id`, `audience`, `source_lesson_version`, `context`, `expected_revision` | `task_id`, `task`, `state`, `revision` |
| `homework.read` | read | — | no | `task_id` | `task`, `events` |
| `homework.complete` | mutate | revision + key | no | `task_id`, `actor`, `note`, `expected_revision` | `task`, `state`, `completed_at` |
| `homework.skip` | mutate | revision + key | no | `task_id`, `actor`, `expected_revision` | `task`, `state` |
| `engagement.read` | read | — | no | `course_id`, `enrollment_id` | `xp_total`, `level`, `progress`, `recent_events` |
| `engagement.award` | mutate | key only | no | `course_id`, `enrollment_id`, `action_kind`, `action_id` | `awarded`, `points`, `xp_total`, `level` |
| `tutor.ask` | mutate | revision + key | **yes** | `course_id`, `enrollment_id`, `objective_id`, `lesson_run_id`, `question`, `block_id`, `selected_text`, `mode`, `expected_revision` | `turn`, `thread_id`, `citations`, `assist`, `state` |
| `tutor.history` | read | — | no | `course_id`, `enrollment_id`, `objective_id`, `lesson_run_id` | `thread_id`, `turns`, `context` |
| `course.mode.set` | mutate | revision + key | no | `course_id`, `mode`, `expected_revision` | `mode`, `world_state`, `requires_world` |

### 8.1 Error codes

No new error code is introduced in this card; every method returns a subset of the existing
`cb.errors` v4 catalog. Where two refusals share a code, the response's `details.reason` is the
discriminator (recorded here so a later card does not invent a code):

| code | Used by | Meaning |
|---|---|---|
| `VALIDATION_FAILED` | all | closed request shape, bad enum value, minutes outside 3..10, generic homework task |
| `NOT_FOUND` | all | course / world / pack / task / thread / lesson run does not exist in scope |
| `STALE_REVISION` | every revisioned mutation | `expected_revision` is not current; reconcile against `current_revision` |
| `IDEMPOTENCY_CONFLICT` | every mutation | the key was reused with a different payload |
| `POLICY_VIOLATION` | world/take-home/homework/tutor | `reason` is one of `world_not_approved`, `partial_world`, `answer_key_on_learner_page`, `generic_task`, `not_completable`, `answer_reveal_while_check_open` |
| `HOST_UNAVAILABLE` | `world.generate`, `takehome.export`, `homework.create`, `tutor.ask` | image provider, artifact host or model is not configured; nothing is fabricated |
| `NOT_IMPLEMENTED` | dispatcher | the name is frozen but no handler is registered yet (true for every method in this card) |

## 9. Naming decisions (plan draft -> frozen)

| Plan draft | Frozen here | Why |
|---|---|---|
| `visual.world.read` / `.generate` / `.approve` | `world.read` / `world.generate` / `world.approve` | The GM-001 card enumerates these names; one namespace, no `visual.` prefix |
| (no style preview method) | `world.style.preview` | The UI needs to read stored concept boards without re-generating |
| `course_visual_worlds` / `course_visual_assets` | `course_worlds` / `world_assets` | Card-named tables; shorter, and "visual" is implied by `world` |
| `final_approved_hash` | `approved_hash` | One field, one meaning: the fence `world.approve` freezes |
| `course.mode.set` (plan §9.3, not in the card list) | kept as the 19th frozen name | A durable mode switch is required by plan §3.3 and no card owns it otherwise; `GM-002` calls it |
| take-home `source_lesson_version` | stored `TEXT` (validated lesson version id) | A version must be comparable and hashable; recency is never identity |
| homework `completed_at` + state | plus `homework_events` | One task can be proposed, edited, skipped and completed; the trail is the fact |

`engagement.award` has no `expected_revision`; the plan's own fence for XP is the real action id,
and an append that cannot move an aggregate must not claim a revision fence it does not use.

## 10. Storage summary (`cb.db` v13)

| Table | Rows | Never |
|---|---|---|
| `course_worlds` | one per world revision | read by grading or evidence |
| `world_assets` | one per role per world | carry an evidence class |
| `takehome_packs` | one per source lesson/audience/kind/revision | mutate the source course |
| `homework_tasks` | one task | store a grade, verdict or mastery |
| `homework_events` | append-only trail | be overwritten |
| `game_engagement` | one per real action | be joined by evidence/parent/pack/export reads |
| `tutor_threads` | one per lesson run | bind to a host chat session |
| `tutor_turns` | append-only | be graded, exported or written as an attempt |

`GM_FORBIDDEN_COLUMNS` (`evidence_class`, `evidence_id`, `verdict`, `passed`, `score`, `mastery`,
`grade`, `rating`, `stars`) must never appear on a Game Mode table; the test asserts it.

## 11. Verification

- `python3 -m unittest tests.test_gm_contract` — 20 tests: manifest names/closure/fences, enum
  values, the `db.v12 -> db.v13` additive diff, SQL that contains no `UPDATE`/`DELETE`/`INSERT`/
  `DROP`/rename, absence of evidence keys/columns, and a real v12-to-v13 round trip on a disposable
  database (legacy course reads Textbook; attempt, evidence and check rows byte-identical).
- `python3 -m unittest tests.test_kernel_schema` — the migrated database equals `db.v13.json`
  table by table (columns, types, nullability, defaults, foreign keys, unique keys, indexes).
- `python3 -m unittest tests.test_contracts` — the contract set audit, `$ref` coherence and the
  historical amendments still hold with `cb.db` v13 as current.

No provider call, image spend, screen or publication happened in this card.
