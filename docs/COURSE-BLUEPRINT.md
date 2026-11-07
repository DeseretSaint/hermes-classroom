# CourseBlueprint: one-off, short and full courses

Status: design only, 2026-11-07. Owner: atlas. Branch: `wt/harness-blueprint-design`.
Amended by H-20 on `wt/harness-prereq-edges`: section 9 points at section 14, and section 13's
objective-level-edge bullet is closed. Section 14 freezes the prerequisite contract and records why
no edge, migration or contract version ships before the blueprint implementation.
Base: local `master` at `13480c4` (H-12 merged). Baseline suite on this tree: 1064 tests, 1
pre-existing failure in `tests/test_adversarial_round2.py`, a stale H-10 audit assertion that
still expects the pre-H-12 approval behavior. This card changes no code and adds no failure. H-01's
`cb.rpc` v10 and `cb.db` v6 live on `wt/harness-contract-v10` at `8cbaab3`; this branch does not
contain that commit, so every statement about `scope`, `level` and `subject_domain` below is a
dependency on H-01, not a description of this tree.

This document decides the data model and the rules for a course of any length. It is not a
shipped capability, it does not edit the contract, and it does not touch production code. The
implementing card must land the contract delta and migration described here before any of it is
true.

Read with: `docs/ADVERSARIAL-HARNESS-REVIEW.md` P0-2 and P1-3, `docs/GENERATION.md` section 5,
`docs/CONTRACTS.md` decision (e), `docs/PLAN-APPROVAL.md`.

## 1. The problem in one paragraph

The planner is shaped for a demo. `PLAN_SCHEMA` allows 4 to 8 objectives and 2 to 8 sections,
`SECTION_SCHEMA.objective_refs` holds exactly one integer, `enforce_plan_rules` refuses anything
but exactly one section per objective, and the prompt says "Produce 4 to 8 objectives"
(`coursebook/generation.py:645`, `:646`, `:1148`, `:1308`). A one-off "replace this hose" brief is
therefore forced into a four-objective course, and a 24-week course cannot exist at all even
though `time_estimate.weeks` allows 104. The pack path already proves the kernel can read 60
objectives (`docs/REVIEW_D1-section-cap.md`), so the limit is in generation, not in storage.

## 2. What the three scopes mean

Scope is a property of the course brief, stored once on `courses.scope` by H-01 and passed to the
plan job in `plan_brief.scope`. It describes the size and shape of the authored course, not the
difficulty of the subject. Recipe remains orthogonal, with one constraint: a `one_off` recipe
must be `single`, because a one-off brief is one verifiable task. A `single` course may still be
`casual` or `committed` if the subject is a single lesson rather than a task.

| scope | units | objectives | owner sections | review sections | authored lessons |
|---|---:|---:|---:|---:|---|
| `single` | 1 | exactly 1 | exactly 1 | 0 | exactly 1 |
| `short` | 1 to 3 | 3 to 6 | one per objective | 0 to 2 | 3 to 8 |
| `full` | 2 to 12 | 12 to 40 | one per objective | 0 to 2 per unit, at most 8 in the course | 12 to 48 |

The full range is a product cap, not a promise that 40 objectives fit one provider call. Section
6 below requires the implementing card to measure the real structured-output ceiling and lower
the cap in the contract if 40 does not fit. The design is sized so the acceptance matrix at 24
objectives works even if the measured cap lands below 40.

`full` also carries structure the shorter scopes do not need: a unit is an ordered group of 2 to
6 objectives with a title, a goal, a target lesson count and prerequisite unit edges. Units are
how a long course stays comprehensible, and they are the checkpoint boundary for generation and
for cancellation. A `short` course may use one to three units when the subject has natural
phases; it does not have to.

The three scopes replace the numeric caps. They do not change the evidence model: an objective is
still the evidence unit, a check still belongs to an objective, and no lesson or review section
can manufacture independent evidence.

## 3. The data model decision: one approved plan, units inside it

Three models were considered.

Flat plan with unbounded arrays. Cheapest in schema, but one plan job would have to author 24 to
40 objective titles, criteria and lesson intents in one call and persist them in one final
transaction. That job has one cost ceiling, one provider deadline and one failure domain. A
timeout on section 31 loses the whole authoring pass because `run_plan_job` writes the plan,
objectives, sections, research and validation in a single transaction at the end. It also has no
natural place to express unit prerequisites. Rejected.

Blueprint plus child plans, one plan row per unit. Semantically attractive, because each unit
could be approved and revised on its own. It does not fit the kernel. `_approved_plan` resolves a
single approved plan for a course; `plan.approve` supersedes every approved plan for the course;
`course.outline` enumerates one plan's objectives; `review.py` selects the current approved plan
with one subquery; `parent.blueprint.read`, `parent.export` and `plan.replan` all assume one
authority. Child plans would create several approved plans for one course, which is two
authorities for "the course outline" and would also allow unit 2 to be approved while its
prerequisite unit 1 is not. That is a kernel-wide rewrite for a benefit the next model already
provides. Rejected for this card.

Blueprint with unit-scoped authoring batches, one plan row per course (chosen). The plan row and
its objectives are the approvable artifact. Units are child rows of that one plan. The blueprint
stage authors units, objectives, check plan and time estimate and goes through deterministic
rules and the independent validator. After approval, section detail and lessons are authored unit
by unit in separate jobs, each with its own budget, checkpoint, retry and cancel boundary.

This keeps the kernel's single approved plan per course, keeps the H-12 fail-closed approval
binding intact, and gives the cost and resume behavior of child plans without a second authority.

The important split is this: the plan approval covers units, objectives, evidence criteria and
the check plan. Section detail is authoring output under that contract and is not part of the
kernel plan hash. That is why sections can arrive after approval without invalidating it, and why
the lesson author cannot quietly change what the learner approved.

## 4. Storage shape

Additions are additive to `cb.db` v6. One migration, `0007_plan_units.sql`, owned by the
implementing card. H-01 owns v6; this is the next number.

```
plan_units (
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  title TEXT NOT NULL,
  goal TEXT NOT NULL,
  prereq_unit_ordinals_json TEXT NOT NULL DEFAULT '[]',
  target_lessons INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(plan_id, ordinal)
)

objectives ADD COLUMN unit_id TEXT NULL

gen_plan_sections ADD COLUMN unit_id TEXT NULL
gen_plan_sections ADD COLUMN section_role TEXT NOT NULL DEFAULT 'owner'
```

`section_role` is `owner` or `review`. The existing `objective_refs_json` keeps its meaning: an
owner section holds exactly one ref, its owner objective; a review section holds one to four
refs to earlier objectives it reinforces. No new ref column is needed, and the old 1:1 rule
becomes a rule about owner sections only. At the model boundary the schema names the owner ref
`primary_objective_ref` and the review refs `reinforces`; on disk an owner section stores
`[primary_objective_ref]` and a review section stores `reinforces`, so there is still one list
column and no second source of truth.

Legacy rows keep `unit_id = NULL` and `section_role = 'owner'`. A NULL unit means the implicit
single unit that every pre-blueprint plan already is. There is no backfill, and no row is
rewritten. Pack-backed courses keep NULL units and remain flat: the pack manifest is their
structure, and this design does not impose units on imported packs.

The plan hash must include units, because a prerequisite change or a unit retitle changes what
the learner approved. `parent_authoring.plan_hash` adds a `units` array to its payload only when
at least one `plan_units` row exists, and adds `unit` to an objective entry only when that
objective has a non-NULL `unit_id`. A legacy plan therefore hashes exactly as it does today, so
every stored `result_json.plan_content_hash` from H-12 remains valid. This is a hard migration
invariant and needs its own test: every pre-migration plan's kernel hash is byte-identical after
0007. The generation digest `generation.plan_hash(document)` needs no change, because the
document itself now carries units.

## 5. Plan schema v2: the blueprint

The blueprint replaces `PLAN_SCHEMA` in `coursebook/generation.py` only for new generation. The
schema name becomes `coursebook_plan_v2` and `PLAN_PROMPT_VERSION` becomes `plan-prompt.v2`. A
plan document stores the schema version so old documents are interpretable.

Required top-level fields: `plan_schema`, `scope`, `title`, `learner_outcome`, `delivery`,
`time_estimate`, `units`, `objectives`, `check_plan`, `context_needs`, `source_ids`, `exclusions`,
`spaced_review`. `evidence_note` and `parent` remain optional as today. `sections` is removed from
the plan schema; sections are authored by the unit stage against a separate schema.

`plan_schema` is the literal string `coursebook.plan.v2`. It exists so a stored document can never
be read under the wrong rules.

Unit schema, exact fields:

| field | type and bounds | invariant |
|---|---|---|
| `ordinal` | integer 1 to 12 | contiguous from 1; matches array position |
| `title` | string 3 to 200 | unique within the plan, case and spacing ignored |
| `goal` | string 10 to 400 | states what the unit makes possible |
| `prereq_unit_ordinals` | array of 0 to 11 integers, each 1 to 12 | every ref is lower than this ordinal; no duplicates; no self ref; unit 1 has none |
| `target_lessons` | integer 1 to 8 | equals the owner sections plus review sections that will be authored for this unit |

Objective schema, exact fields:

| field | type and bounds | invariant |
|---|---|---|
| `ordinal` | integer 1 to 40 | contiguous from 1 across the whole course |
| `unit_ref` | integer 1 to 12 | names an existing unit |
| `title` | string 3 to 200 | observable, not a topic label |
| `evidence_target` | enum: recall, comprehension, production, discrimination, procedure, transfer | unchanged vocabulary |
| `evidence_criteria` | array 1 to 6 of strings 5 to 300 | each criterion observable |
| `support` | enum: sourced, unverified | sourced requires a ledger source |
| `source_ids` | array 0 to 8 identifiers | every id exists in the ledger |

Section schema, exact fields, authored by the unit stage rather than the plan stage:

| field | type and bounds | invariant |
|---|---|---|
| `ordinal` | integer 1 to 48 | contiguous within the plan, assigned in unit order |
| `unit_ref` | integer 1 to 12 | names the unit being authored |
| `role` | enum: owner, review | one owner section per objective; review sections only reinforce earlier objectives |
| `primary_objective_ref` | integer 1 to 40, or null | required and non-null for role owner; must be null for role review |
| `reinforces` | array 0 to 4 integers | required for role review, each ref is a lower ordinal in this or an earlier unit; must be empty for role owner |
| `title` | string 3 to 200 | |
| `lesson_intent` | string 10 to 400 | names the construct the lesson has to carry |
| `context_needs` | array 0 to 6 strings | |
| `source_ids` | array 0 to 6 identifiers | |

The media and construct declaration belongs to H-05. This schema reserves the slot: H-05 adds
`media_needs` (or an equivalent typed construct) to the section schema and to the lesson policy
consumption. This design does not invent that field and does not let prose in `lesson_intent`
stand in for it.

Lesson schema delta. Everything in `LESSON_SCHEMA` stays as it is except the check source, which
must distinguish an owner lesson from a review lesson:

| field | type and bounds | invariant |
|---|---|---|
| `check_mode` | enum: `new`, `reuse` | required; `new` on an owner section, `reuse` on a review section |
| `check` | the existing check object | required when `check_mode` is `new`; forbidden when it is `reuse` |
| `reuse_objective_ref` | integer 1 to 40 or null | required when `check_mode` is `reuse`; must be one of the section's `reinforces` refs |

A review lesson authors no new check. It presents the existing owner check of the objective it
reinforces, so a cold pass there is the delayed retrieval evidence the kernel already records,
and a hinted or answer_shown pass stays non-independent. This is how a section can serve more
than one objective without inventing a second check authority or a practice-only evidence class.

Check plan v2 removes `count` and `independent_evidence`. Both were decorative: the lesson
pipeline writes exactly one check per owner section and independence is an evidence-class
property, not a plan promise. The v2 entry is `objective_ref`, `kind`, `evidence_target`,
optional `notes`. The invariant is one new check per owner section, and therefore one check per
objective; a review section reuses an owner check and adds none. A future card that wants several
distinct checks per objective must add a real `checks[]` array plus grading support; it must not
reintroduce a number the pipeline ignores.

Deterministic plan rules, replacing the current `enforce_plan_rules` body:

1. Scope bounds hold: single has 1 unit and 1 objective; short has 1 to 3 units and 3 to 6
   objectives; full has 2 to 12 units and 12 to 40 objectives.
2. Unit ordinals are contiguous; objective ordinals are contiguous; objective `unit_ref` and
   section `unit_ref` name existing units.
3. Every unit has 2 to 6 objectives for full, 1 to 6 for short, exactly 1 for single.
4. Every objective is named by exactly one owner section; a review section never owns an
   objective; every review ref is a lower objective ordinal.
5. Every objective appears in the check plan; no check entry names an objective twice; the
   check kind is permitted by the recipe.
6. Prerequisite edges point backwards, are unique and are not self references.
7. `target_lessons` equals the number of owner plus review sections authored for the unit; a unit
   with zero owner sections is refused.
8. Every unit-level prerequisite is reflected in schedule arithmetic: the sum of
   `target_lessons` across units fits `time_estimate.weeks` at the declared sessions and minutes.
9. Existing rules survive unchanged: time honesty, source grounding, unsupported claims labelled
   unverified, one-off has no quiz and no spaced review and needs a verification checklist,
   committed needs spaced review and graded checks, casual labels its evidence, parent stays
   parent-led with supervision and hazards, locale scaffolds are task-mandated.

## 6. Token limits, cost and stage boundaries

The blueprint call is one structured call with `max_tokens` raised from 4000 to 12000 and the
same 240 second deadline. The schema bounds keep the artifact under the existing 48 KiB
`MAX_PLAN_BYTES`: 40 objectives with short criteria and units fit in roughly 25 to 35 KiB. The
implementing card must measure the real output on the provider in use, record input and output
tokens, and if 40 objectives do not fit, lower the full cap in the contract to the measured
number. It must never truncate a blueprint. A plan job that cannot fit its own scope refuses with
a typed reason that names the scope, the measured bytes and the cap.

Budget is per stage, not per course:

| stage | provider calls, worst case | reason |
|---|---:|---|
| blueprint (`plan`) | 4 | one generate and one validate, two attempts |
| unit sections (`unit_sections`, one unit) | 4 | one generate and one validate, two attempts |
| unit lessons (`lessons`, one unit) | 2 calls per section times 2 attempts, over the unit's sections | unchanged lesson pipeline |

A unit job uses `lesson_cost_budget` sized to that unit's section count, not the whole course.
The blueprint uses a four-call budget. H-17 owns the dollar ceiling; this design only splits the
work so one ceiling never covers an entire 24-lesson course.

This split is also the token limit answer. The plan call carries units and objectives only. Each
unit call carries that unit's objectives plus the shared source ledger, never the whole course
outline. Each lesson call carries one section, as today. No call grows with course length except
the blueprint, and the blueprint has a declared cap.

## 7. Job stages, continuation, resume, cancel

`jobs.kind` stays `plan`. `cb.vocabulary#job_kind` is referenced by every pack manifest and adding
a kind would force a pack schema revision. The stage selects the work, as decision (e) already
established.

| stage | brief fields | writes | completion checkpoint |
|---|---|---|---|
| `plan` | `goal`, `recipe`, `dials`, `locale`, `level`, `subject_domain`, `scope`, `course_id`, `enrollment_id` | `plans`, `objectives`, `plan_units`, `gen_plan_documents`, research and validation rows | `plan_id`, `plan_hash`, `plan_version`, `generation_state`, `units`, `objectives` |
| `unit_sections` | the plan brief plus `plan_id` and `unit_ordinal` | `gen_plan_sections` for that unit | `plan_id`, `plan_hash`, `unit_ordinal`, `sections`, `owners`, `reviews` |
| `lessons` | the plan brief plus `plan_id` and `unit_ordinal` | `gen_lessons` for that unit's sections | `plan_id`, `plan_hash`, `unit_ordinal`, `lessons`, `media` |

The contract change is small and belongs to the implementing card: `plan_brief` gains
`unit_ordinal` (integer 1 to 12) and `stage` gains `unit_sections`. That is `cb.rpc` v11,
additive over v10. This card does not edit the contract.

Continuation is explicit. The blueprint job ends with every unit known and no lesson authored.
The learner or parent then starts a `unit_sections` job for unit 1, sees the outline, and starts a
`lessons` job for unit 1. Unit 2 is a second, real job with its own id, budget, checkpoint and
cancel state. The executor must not enqueue the next unit inside the previous job: a silent chain
would hide cost, hide failure and make cancellation a lie. The completion checkpoint carries
`units_complete` and `next_unit_ordinal`, which is enough for the client to offer the next step.
Enqueueing the next unit is a user action, matching PREBUILD_SPEC section 5: moving past the
current unit is explicit, never inferred. A `single` course uses the same three stages with one
unit, so there is one code path and one place for the rules; the extra job is cheap.

The unit stage assigns global section ordinals after the highest ordinal already stored for that
plan hash, in unit order. Only one `unit_sections` job and one `lessons` job may be active for a
plan at a time. The job service leases one job, not a plan, so the implementing card must enforce
that rule explicitly, either with a plan-level guard before enqueue or a partial unique index on
the active authoring job for a plan. Two concurrent unit jobs would otherwise race for ordinals
and section ownership.

Idempotency and resume reuse existing mechanisms. A retried job keeps its brief. Section rows are
unique on `(plan_id, plan_hash, ordinal)`; lesson rows are unique on
`(section_id, plan_hash, version)`. Re-running a failed unit job reuses every row already
authored and spends only on the missing ones. The checkpoint names how many sections or lessons
were completed so a retry message is concrete.

Cancel is honored at stage boundaries through `job_service.request_cancel` and
`begin_cancelling`. The unit boundary is the natural place to observe it: a cancelled unit job
leaves its already authored sections and lessons durable, so the learner can resume later. A
cancelled blueprint job leaves nothing approvable, because the plan bundle is written only after
validation.

Partial failure that is not a cancel keeps the same shape. A provider timeout or a cost ceiling
mid-unit raises a typed failure; finished sections stay durable; the job view names the completed
count and the action that continues without re-authoring. The lesson pipeline already does this
for sections (`ProviderTimeout.with_recovery`); the unit stage must do the same.

## 8. Approval granularity

Approval stays at the blueprint, one plan per course. This is a deliberate decision, not an
oversight.

The kernel's `plan.approve` supersedes the previous approved plan, bumps the enrollment revision
and binds one content hash. `course.outline`, the review queue, `plan.replan`, `parent.export` and
`parent.blueprint.read` each resolve one approved plan. Per-unit approval would need several
approved plans for one course, which breaks that single authority and lets a later unit be
approved while its prerequisite is not.

What the learner does get per unit is a visible gate and a stop point, not an approval command.
The blueprint is approved once. After that, each unit's sections and lessons are separate jobs the
learner starts, sees and can cancel. Unit lessons are independently validated as today. A parent
who wants per-unit sign-off can use the existing `parent.final.approve` surface once a unit's
lessons exist; that row binds the plan hash and content hash. If the product later needs a
durable per-unit approval command, the seam is a `unit_approvals` table bound to
`(plan_hash, unit_ordinal, content_hash)`, analogous to `final_approvals`. That is out of scope
here and would be its own contract delta.

## 9. Adaptation, honestly

The current claim is a state transition, not adaptive teaching. `review.py` is a real scheduling
heuristic: it derives a due date from the last cold pass and a per-target ladder. The lesson loop
maps verdicts to actions with a fixed table (`domain._next_action_for`). Neither looks at why an
answer failed, neither chooses among remediation types, and neither changes content. The review
ladder must not be called adaptive teaching.

This design defines adaptation as three separate things, with the deterministic scheduler owning
the route and the model owning only content.

First, outcome classification is deterministic. It comes from the grader verdict and the
evidence class the attempt already records:

| outcome | evidence written | objective state | next step |
|---|---|---|---|
| pass with cold evidence | layer-2 independent or delayed evidence | independent_evidence, or delayed_evidence when it was review_due | offer the next unblocked objective in unit and prerequisite order |
| pass with hinted or answer_shown evidence | layer-1 attempt only | introduced, or unchanged, but never independent | say plainly that independence was not shown; keep the objective open |
| partial | layer-1 attempt | needs_review | choose a remediation route |
| not_yet | layer-1 attempt | needs_review | choose a remediation route, reteach first |
| clarification | no evidence | unchanged | show the clarification; re-present the same check |
| grading error or provider outage | needs_retry, no verdict | unchanged | retry grading; never blame the learner and never write evidence |
| override | override evidence | overridden | unlock access, label not independently demonstrated |

Second, remediation routing is deterministic and bounded. The scheduler chooses the route from
the attempt count and what has already been shown:

1. One failed attempt and no worked example has been shown: show the worked example, same
   objective, same check.
2. One failed attempt after a worked example: reteach the objective with a different
   representation, same objective, then the same check.
3. Two failed attempts: reteach with a different representation, and when a prerequisite unit's
   objectives are not yet independent, offer that unit's owner section as the repair route. The
   scheduler reads this from unit edges only; it does not infer a prerequisite from the failed
   criteria. This follows PREBUILD_SPEC section 5: two unsuccessful attempts trigger a different
   explanation, not louder repetition.
4. Three failed attempts: stop retrying. Surface a decision to the learner or parent: replan the
   objective, accept an override that is labelled not independently demonstrated, or leave it
   for review. No infinite loop.

An easier check is admissible only when it tests the same construct and the same evidence target
with reduced language or complexity. If the harness cannot show that, the route is not offered,
because a keyed-down check that passes would otherwise claim an evidence target it never tested.
A cold pass on a check that tests less than the objective is recorded as `introduced`, never as
independent evidence.

Third, the model writes content only. It writes the reteach variant, the worked example and the
clarification inside the route's constraints. It never selects the route, never changes the
evidence target, never decides that an objective is mastered, and never writes evidence.

Remediation artifacts are content, not evidence. A reteach page, a worked example shown before an
attempt, or an answer shown is recorded on the attempt as a hint or answer_shown event, and it
degrades that attempt's evidence class. A remediation row is stored under the objective and the
attempt that caused it. It has no evidence row and cannot move an objective to
independent_evidence. Only a later `attempt.submit` graded `pass` with class `cold` writes layer-2
evidence. That is the line that keeps "I showed them the answer" from becoming "they learned it".

Prerequisite edges are structural, not a mastery gate. Unit `prereq_unit_ordinals` decides
authoring order, the default presentation order and which unit the scheduler offers next. By
default a learner can still open a later unit; the library shows the unmet prerequisite as a
warning, not a lock. A strict mode that refuses access until prerequisite objectives reach
independent evidence is a policy choice for a later card, not part of this design.

Section 14 freezes the exact edge rules, the gating semantics, the learner-visible copy and the
acceptance tests for this. It also records why the edge is not added to the v1 plan schema, and
why that implementation belongs to the blueprint card rather than to H-20.

## 10. Migration of existing plans

Existing courses keep working unchanged.

A stored plan with no `plan_units` rows is one implicit unit. Its objectives keep
`unit_id = NULL`. `course.outline` groups NULL objectives under a single unit whose title is the
plan title and whose ordinal is 1. The kernel plan hash is unchanged, so H-12 validation
bindings and approvals stay valid.

`courses.scope` may be NULL for rows created before H-01. Display derives an effective scope
from the objective count when the stored value is NULL: one objective is single, three to six is
short, more than six is full. That derived label is display only. Generation always uses the
explicit scope from the brief; it never guesses a scope from an old plan.

`plan.replan` must carry units. When objectives are kept, retitled or deferred, their unit
membership is copied and section ordinals are remapped. A `remove` that empties a unit drops that
unit and refuses the replan if another unit's prerequisite edge now points at the dropped
ordinal. A structural add has no authored section and is refused by the existing outline carry
rule, as today.

New plans from `plan-prompt.v2` always have at least one `plan_units` row. The plan stage writes
units, objectives and the document in one transaction, exactly as the current plan stage writes
the bundle, so a plan never exists without its units.

## 11. Acceptance matrix

Three concrete examples fix the counts. They are design targets for the implementing card's
tests, not fixtures that already exist.

| example | scope | units | objectives | owner sections | review sections | check kinds | evidence targets | scheduled time |
|---|---|---:|---:|---:|---:|---|---|---|
| Bicycle tube replacement | single | 1 | 1 | 1 | 0 | 1 verification | procedure | 1 session x 45 min, 1 week |
| Home electrical safety | short | 2 | 6 | 6 | 1 | 4 quiz, 2 verification | 2 comprehension, 2 procedure, 1 discrimination, 1 transfer | 2 sessions x 45 min, 6 weeks |
| Conversational Japanese, survival level | full | 6 | 24 | 24 | 6 | 18 quiz, 6 observation | 8 recall, 6 comprehension, 6 production, 4 discrimination | 2 sessions x 45 min, 24 weeks |

Bicycle tube replacement is a `one_off` recipe. The learner replaces a 700c inner tube, checks
bead seating, confirms the tyre is not pinching the tube, inflates to the sidewall pressure and
closes the quick release. One objective, one owner section, one verification checklist. There is
no quiz, no homework and no spaced review. Completion is instruction_complete plus a
self-reported verification checklist; it never claims independently verified physical work. The
existing `plan_one_off.json` fixture, with four objectives, is the exact defect this example
replaces.

Home electrical safety is a committed short course. Unit 1 covers conductors, insulation and
Isolation; unit 2 covers wiring a plug, testing a socket and the isolation procedure. Six
objectives produce six owner sections; one review section at the end of unit 2 reinforces the two
unit 1 objectives that the practical work depends on. Spaced review is required. The practical
checks are verification checklists; the two comprehension checks are quizzes. A quiz on a
procedure that has not been performed is not accepted as procedure evidence.

Conversational Japanese is a full course and is not the bundled pack. Six units of four
objectives: sounds and kana, first exchanges, needs and requests, directions and transport,
numbers and time, and a short transactional conversation. Twenty four owner sections plus six
unit review sections. Eight recall targets for kana and vocabulary, six comprehension, six
production and four discrimination. The six production checks are observations by a parent, an
instructor, or a local recording seam; whether a recording can carry production evidence is
H-16's decision, and this design only requires that the plan declares the need. At two sessions
a week for 24 weeks the scheduled time is 48 sessions, 36 hours; attainment is not claimed unless
a real benchmark is supplied with its limits.

## 12. What the implementing card must build, in order

1. `cb.rpc` v11: `plan_brief.unit_ordinal` and `stage = unit_sections`, additive over v10.
2. `cb.db` v7 migration 0007 with the three additive columns and `plan_units`.
3. Plan hash extension with the legacy-hash invariance test.
4. `PLAN_SCHEMA` v2, `UNIT_SECTIONS_SCHEMA`, `plan-prompt.v2`, the rule set in section 5, and
   the removal of `count` and `independent_evidence`.
5. Blueprint stage and per-unit section and lesson stages in `run_plan_job`, `run_lesson_job` and
   the executor resolver, with stage-sized budgets and checkpoints.
6. `course.outline` unit projection, additive response field, and the library label.
7. Tests: scope boundary matrix, one-off with exactly one objective, legacy hash stability,
   unit-scoped lesson coverage, partial unit resume, cancel at a unit boundary, prerequisite
   rejection and replan carry.
8. A measured statement of the real provider output ceiling and the resulting full-scope cap.

Do not start with the UI. The learner create flow (H-02) can send `scope` with H-01's contract,
but a full course is not reachable until the stages above exist, and the UI must not promise a
count the generator cannot author.

## 13. Out of scope

This design does not include, and the implementing card must not smuggle in:

- any UI, create-flow or Parent Studio change;
- the plan-time media field or policy consumption (H-05 owns it);
- procedure authoring or the procedure lens (H-06 owns it);
- parent brief fidelity (H-07 owns it);
- general authored export (H-08 owns it);
- assessment constructs beyond quiz, verification and observation (H-16 decides);
- cost ceilings and their recovery (H-17 owns it);
- locale scaffolds, RTL and non-Japanese fixtures (H-18 owns it);
- per-unit approval commands;
- objective-level prerequisite edges. Unit edges are the v1 structure and H-20 ruled against
  extending the flat plan schema (section 14.1); an objective edge without a unit has no sequence
  to project and would be a decorative field;
- dynamic re-planning from an attempt, a learner model, style inference or any claim of adaptive
  teaching;
- units for pack-backed courses, which keep the manifest's flat structure;
- converting an existing long pack into a blueprint;
- cross-course or community prerequisite graphs;
- provider or model changes, and any claim that this design has been run against a live
  arbitrary-topic course.

The design is a contract for implementation. It is not evidence that Coursebook can yet author a
full course.

## 14. Prerequisite edges: the frozen contract (H-20, 2026-11-07)

Status: **decided and frozen here, not implemented in this tree.** Owner: atlas. Branch
`wt/harness-prereq-edges`. Base: `master` at `903a606` plus this document at `f465a4d`.

### 14.1 The decision

Sequencing is in scope for this product. It is unit-level, structural and non-blocking, exactly as
section 9 states: `prereq_unit_ordinals` decides authoring order, the default presentation order and
which unit is offered next; a learner may still start a later unit after being told which
prerequisites are unmet.

H-20 does **not** add a `prerequisites` field to `PLAN_SCHEMA`, and does **not** land a contract
version or a schema migration for one. Three facts, each checked on this tree, force that:

1. The v1 plan has no units. `PLAN_SCHEMA` is a flat list with `enforce_plan_rules` requiring one
   section per objective in ordinal order (`coursebook/generation.py:624-665`, `:1280-1321`). An
   edge there would reorder nothing, gate nothing and project nothing: the same ordinal order
   already is the only order the outline can show. That is the decorative field the card forbids.
2. Every surface that could carry a prerequisite fact is contract-versioned and closed.
   `outline_objective` and the `lesson.begin` response are `additionalProperties: false`
   (`contracts/rpc.v9.json`), and `WIRE_CONTRACT_VERSION` is `9`
   (`coursebook/contracts.py:42`). H-01 has already taken v10 on `wt/harness-contract-v10`
   (`cb.rpc` v10, `cb.db` v6, `migrations/0006_courses_plan_brief_inputs.sql`), and section 7 above
   already reserves v11's content (`plan_brief.unit_ordinal`, `stage = unit_sections`). A third new
   wire version minted here would fork the contract that H-01 and H-13 are landing.
3. The last applied migration on this base is `0005_pronunciation_attempts.sql`; 0006 is H-01's and
   0007 is this design's `plan_units`. There is no free number that does not collide.

So the edge model is in scope, and its implementation is the blueprint card of section 12, which
owns v11, `cb.db` v7, `PLAN_SCHEMA` v2 and the unit stages. That card is `t_2a2fc90c` (cinder),
gated on H-01 (`cb.rpc` v10) and H-13 (scope threading). H-20's deliverable is the frozen contract
those rules must satisfy, so the implementing card cannot invent a weaker one.

### 14.2 Frozen edge rules

These are the rules the implementing card must enforce and test. They are normative.

| rule | requirement |
|---|---|
| R1 bound | `prereq_unit_ordinals` is an array of 0 to 11 integers, each 1 to the plan's unit count; no duplicates; no self reference; unit 1 has none |
| R2 acyclicity | every ref is a strictly lower ordinal, so a cycle is unrepresentable at the writer. A reader still refuses a document that carries one (imported, hand-edited or a future forward-ref extension) with reason `prerequisite_cycle` and the cycle listed, because unrepresentability is a property of the writer, not of the reader |
| R3 in-plan | every ref names a unit that exists in this plan version. `plan.replan` refuses when a removed unit leaves a surviving edge pointing at its ordinal |
| R4 legacy invariance | a plan with no `plan_units` rows is one implicit unit with no edges; `parent_authoring.plan_hash` stays byte-identical for every stored pre-0007 plan, so every `result_json.plan_content_hash` written under H-12 still binds. This is the migration bug that would invalidate approvals, and it needs its own test |
| R5 gating is disclosure | the gate lives on `lesson.begin` and `check.open`, the two commands that start learner work. Per objective it computes `prerequisite_state`: `no_edges` (legacy or flat plan, response unchanged), `satisfied`, or `unmet` |
| R5a satisfied means | every objective of every prerequisite unit is in `independent_evidence`, `delayed_evidence` or `overridden`. `overridden` satisfies access only and stays labelled *not independently demonstrated*. It is never inferred from criteria, timing, attempt count, model opinion or a score |
| R6 no silent skip | with `unmet`, the command refuses with `PREREQUISITE_UNMET` and the unmet list, and writes no `lesson_runs` or `checks` row, unless the request carries `acknowledge_prerequisites: true`. With the flag it proceeds and echoes `prerequisite_state: unmet_acknowledged` plus the same list. The acknowledgment is a learner decision recorded in the response; it is never evidence and never moves an objective |
| R7 no mastery claim | no score, probability, readiness number or learner vector is stored or returned. The only prerequisite fact exposed is the objective-state list, the same seven labels the kernel already has |
| R8 strict mode reserved | `prerequisite_policy: warn \| require` is the flag name a later card uses for a hard lock. It is not in v11 and must not ship under another name |
| R9 presentation projection | `course.outline` gains an additive `units` array: `ordinal`, `title`, `goal`, `prereq_unit_ordinals`, `prerequisite_state`, `unmet[]`, `objectives[]` (existing `outline_objective` objects). A legacy plan projects one unit titled with the plan title, matching section 10. `independent` remains the objective's own state; no derived boolean is added that a client could read as ready or mastered |

### 14.3 What the learner sees

The refusal is not the message. The message is the point:

> Unit 3 assumes you can *<unit 2 goal>*. 2 of 4 objectives there have not been shown
> independently yet: *<titles>*. You can start now; the course will not count the prerequisite as
> met.

Two actions, **Start anyway** and **Go to unit 2**. The initial view offers the prerequisite unit.
A parent-led course shows the same facts with the prerequisite route as the default action. No
surface may render a lock icon, a percentage, a "mastery" bar or the word *ready*; the honest
label for an overridden prerequisite is *not independently demonstrated*.

### 14.4 Acceptance tests the implementing card must carry

Every test is named so it can be found, and every one is a refusal or a projection fact, not a
prose check.

1. `test_prerequisite_cycle_refused` — unit 2 to 3 to 2 refused with `prerequisite_cycle`.
2. `test_prerequisite_forward_ref_refused`.
3. `test_prerequisite_self_ref_refused`.
4. `test_prerequisite_duplicate_ref_refused`.
5. `test_prerequisite_missing_unit_refused`, plus the replan variant: dropping a depended-on unit
   refuses the replan.
6. `test_lesson_begin_refuses_unmet_prerequisite` — assert **no** `lesson_runs` row was created and
   the error carries the unmet list.
7. `test_lesson_begin_acknowledged_prerequisite_proceeds` — run created, `unmet_acknowledged`
   echoed, no attempt or evidence row written.
8. `test_check_open_refuses_unmet_prerequisite` — no check row created.
9. `test_legacy_plan_hash_unchanged_after_0007` — byte-identical kernel hash for every
   pre-migration plan.
10. `test_legacy_outline_projects_one_unit`.
11. `test_algebra_before_calculus` — a `full` course of two units, unit 2 requires unit 1; asserts
    the edge order, the gating copy and that an algebra objective in `needs_review` leaves the
    calculus unit `unmet`.
12. `test_safety_before_power_tool` — parent-led, unit 1 hazard and lockout procedure, unit 2 the
    power tool; asserts the gate and that a quiz-only pass in unit 1 does **not** satisfy the edge
    (only independent evidence does), which is the case the design exists for.
13. `test_projection_has_no_mastery_field` — the outline unit object's key set equals R9 exactly.

### 14.5 What H-20 refuses to do

- Add `prerequisites` to `OBJECTIVE_SCHEMA` or `SECTION_SCHEMA`, or delete
  `additionalProperties: false` to make room for one.
- Add a migration, a contract file or a version bump ahead of the blueprint card.
- Call a flat ordinal list sequencing, or claim that the seven objective-state labels plus a review
  ladder are adaptive teaching. They are not; section 9 is the whole of the honest claim.
- Edit core Hermes, or reach a prerequisite decision through any seam other than the plugin's own
  contract.

The v1 stance is unchanged and correct: `tests/test_adversarial_round2.py::PedagogyTest`
`test_schema_cannot_express_a_prerequisite` keeps passing because the v1 plan genuinely cannot
express an edge. Its companion `test_adaptation_is_a_state_transition_only` is currently a
tautology (it compares the seven-state set with itself, `tests/test_adversarial_round2.py:303-308`)
and therefore pins nothing beyond the two `_objective_state_after` assertions that follow it; the
implementing card must replace it with the R5/R7 assertions above rather than treat it as coverage.
