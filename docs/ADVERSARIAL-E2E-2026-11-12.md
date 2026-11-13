# Adversarial end-to-end review — 2026-11-12

Question asked: does Coursebook take a learner from a stated goal to a lesson they can actually do,
at every length, with a coherent, straightforward, visually consistent surface — and what are at
least twenty ways to make it better?

Method: three live generations on the real host route (one per scope, isolated homes, independent
validator), then a hop-by-hop trace of the learner path and an audit of the learner surfaces. The
quality bar is `docs/QUALITY-RUBRIC.md` (L1–L12); a structural pass is reported separately from a
learning-quality pass. Findings are **[ran]** when a live run produced the evidence, **[read]** when
the code says so, **[probe]** when a targeted probe reproduced it.

## Verdict

**There is no clean path from goal to lesson today, and the break is different at every length.**

| scope | plan | sections | lesson | servable | wall |
|---|---|---|---|---|---|
| `single` — poach an egg, `one_off` | 1 objective, 1 unit, independent `pass` in 106 s | 1 | authored 3×, **rejected** each time on `rubric_consistency` | **0** | 7m52s |
| `short` — printing press, `casual` | never completed: plan call stalled, job left `running` | 0 | — | 0 | >18m |
| `full` — risk/probability, `committed` | 12 objectives, 4 units, `spaced_review`, 8 weeks, independent `pass` in 300 s | **0** | **failed in 2 s before the first model call** | 0 | 5m05s |

What is genuinely strong: the plan stage. It asks for an outcome, states exclusions with reasons,
cites a quote per sourced objective, estimates time without inventing attainment hours, and the
independent validator is a different model with a real `pass`. The failure is everything after the
plan — where the artifact is turned into lessons and served.

## Generation path

### G1 [ran] A full-scope course cannot author a single lesson
`jobs.create` for `stage=lessons` fails in 2 s, both units:

```
VALIDATION_FAILED  retryable=false
request payload is 25786 bytes compact, over the 24000-byte request bound
```

`REQUEST_BYTES_BOUNDS` scales with scope (`{"single":24000,"short":24000,"full":48000}`,
`generation.py:8518`) and the plan stage applies it. The unit-sections author and its validator call
`_bounded_input(payload)` with no limit (`generation.py:11873`, `11953`), so a legal full blueprinted
plan plus its six-source ledger is refused at the default. The comment at 8513 says the bound "scales
with the scope the brief declared" — true only for the plan stage. The full plan itself was 14,535
bytes; the unit-sections payload was 25,786.

**Fix:** pass `limit=_request_bound(plan.get("scope"))` in the unit-sections author, its validator,
and the lesson request where the ledger travels; add a 6-source full-plan fixture.

### G2 [read] A multi-unit course stops at unit 1, and a failed lessons job replays forever
`generateLessons` keys `jobs.create` as `cb-lessons-${plan_id}` (`95-studio.js:5871`) and the job line
has no `onRunAgain` (`6192`), while the executor authors exactly one resolved unit per job
(`executor.py:150-168`) and `jobs.create` replays a stored job for the same key (`domain.py:2599`).
`docs/CONTRACTS.md:1119` says the client must post a fresh key per unit. No desktop code reads
`next_unit_ordinal`. So a 4-unit course can only ever write unit 1, and a failed job can never be
retried.

**Fix:** key by plan + next unit ordinal, read `next_unit_ordinal` from the settled job, expose Run
again; keep the same-unit idempotency.

### G3 [read] The plan answer has one 12 000-token cap for every scope and no cut repair
`max_tokens=12000 if blueprint else 4000` (`:9029`); the plan answer is parsed with
`_parse_structured` and no `.cut` re-ask, unlike unit sections and lessons which both have
`_stage_answer_with_repair`. The schema's own maxima for `objectives` are far above 12 k tokens, and
the design estimates 25–35 KiB for a full plan. A cut answer dies as `plan is not valid JSON`, not as
a repairable truncation.

**Fix:** size the cap from the scope's objective band and route the plan through the same `.cut`
re-ask the other stages use.

### G4 [read] The plan job budget is flat while validation fan-out scales 2 → 14
`CostBudget(max_calls=32, max_cost_usd=0.75)` (`:1199`) against `_validation_pass_plan`: 1 objective →
2 passes, 40 objectives/12 units → 14 passes, each reserving a call slot. Attempt 1 = 15 calls;
attempt 2 reserves 14 more; the dollar ceiling trips at call 19 at the declared $0.04/call. A full
plan refused once by the validator dies of "budget exhausted", not of a verdict.

**Fix:** size the plan budget from the pass plan, as `lesson_cost_budget` already does for lessons.

### G5 [probe] Scope bands leave 2 objectives and 9–11 lessons unrepresentable, and a band violation parks a plan
`SCOPE_EXPECTATIONS` (`:560`) accepts single {1}, short {3–6}, full {12–40}; 2 and 7–11 objectives
have no legal scope, and 9–11 sections likewise. A 10-objective plan is refused at short ("requires 3
to 6") and at full ("requires 12 to 40") with no suggestion. On the second violation the plan is
parked `needs_review` and written, which `plan.approve` then refuses — a dead artifact instead of a
typed refusal that names the legal scope.

**Fix:** make the bands contiguous (short 3–8, full 9–48) or derive the band from
`time_estimate.weeks`; on a violation after the last attempt, refuse with `SCOPE_BAND` naming the
legal scopes and write no plan row.

## Serving and learning path

### L1 [read] A passed generated section can never be checked again
`check.open` resolves an existing check row first; once the check is closed, it falls back to
`_check_spec(objective)` (`domain.py:367`), which only reads a `check_spec` object out of
`evidence_criteria_json`. Generated lessons write plain-string criteria and put the real check in the
`checks` table, so a revisit raises `objective_not_checkable` and `progression.challenge_out` refuses
identically. Spaced review is therefore impossible for every generated course.

**Fix:** when the objective has an authored check row, clone the newest one as a revisit
(`revisit: true`, no second XP, no second independent-evidence transition).

### L2 [probe] `check.open`'s new revision is dropped, so the first submit after an on-demand check is `STALE_REVISION`
`check.open` bumps the enrollment and returns `revision` (`domain.py:1594`); the surface computes
`revision = max(page.revision, modelRevision(row), revisionFloor)` (`70-learning.js:4749`) and only
`lesson.assist` feeds `revisionFloor`. The submit then fences on the older value.

**Fix:** adopt `check.open`'s revision into `revisionFloor` before the check renders.

### L3 [read] The prerequisite acknowledgment is never sent
Both callers (`00-header.js:921`, `70-learning.js:517`) omit `acknowledge_prerequisites`, though the
contract documents it and the refusal text says "You can start now". The section opens, then no check
card appears and a warning lands, with no "Start anyway" control.

**Fix:** render the refusal as a Start anyway control that retries with the acknowledgment.

### L4 [ran] Finishing every section returns the learner to "Review the plan"
`_library_next_step` returns `review_plan` when no objective is `not_started`
(`domain.py:2843`); there is no completion state or RPC. The learner finishes the last check, gets no
"course complete", and the only primary opens an approved plan with "Start a new plan version".

**Fix:** a terminal completion step (and panel) when zero objectives are current or due.

### L5 [ran] `needs_review` reads as "Review needed" — the same words as spaced review
`70-learning.js:223-224` maps `review_due` and `needs_review` to the same key, label and icon;
`30-home.js:62` treats both as due. A validation rejection therefore looks like a review card, and
opens a lesson whose page is `null` (`servable_objectives: []`). The repair verbs
(`lesson.regenerate`, `lesson.revise`) are reachable only in Studio (`95-studio.js:5058`), so a solo
learner has no path at all.

**Fix:** own state word ("Could not be written"), a learner-facing reason, and a Repair action that
calls `lesson.regenerate` with the validator's reasons.

### L6 [read] A model-assessed page never tells the learner
`lesson.page.provenance.warning` is served (`domain.py:3544`) and no desktop surface reads it
(`grep page.provenance desktop/src` → 0). Only Studio does. A page that failed independence reads
exactly like an independent one.

**Fix:** render the warning in the section header when `provenance.independent === false`.

### L7 [read] XP is paid only in the desk classroom
`awardCheck` lives only in `ClassroomV3Surface` (`70-learning.js:4768`); the reader and Field player
commit without awarding (`80-components.js:4674`, `4700`), and `CourseDetail` opens sections in
`view='textbook'` (`90-course.js:3909`). The same passing check pays from the desk and nothing from
the course page.

**Fix:** move the award into the shared commit path.

### L8 [probe] A detached binding on one section refuses submits on every other section
`_binding_refusal` queries the whole enrollment (`domain.py:1909`) although its docstring means "no
binding yet"; a detached binding on objective 1 blocks a submit on objective 2.

**Fix:** scope the refusal to the check's objective/run.

## Assessment quality

### A1 [ran] A verification lesson is rejected for a rubric band the check cannot elicit — and the grader never uses the rubric
The one-off lesson was authored three times and refused each time, finally:

```
answer_key.rubric[2]: The 'Safety stop' criterion (weight 0.25) requires confirming a
heat-lowering or withheld-egg action at a rolling boil, but the check's seven items contain
no such step, so learners cannot earn that band from the check as posed.
```

A `verification` check is graded by the confirmation lane, which reads `rubric.pass_rule` only
(`grading.py:100-150`); the weighted criteria are never used for it. The validator is enforcing an
earnability property the grader does not implement, and it blocks a good lesson over a band no
learner could see. Three attempts, ~39 k output tokens, no servable lesson.

**Fix:** `rubric_consistency` is not applicable to a verification checklist (it is scored by items and
pass rule); waive it, and require the author to put every safety obligation into the items.

### A2 [ran] No deterministic rubric↔check coverage rule
`rubrics.validate_rubric` checks count, mental state, duplicates and profile fit (`rubrics.py:471`),
not whether each criterion can be earned from the check's items. The mismatch is only caught by the
expensive validator, and only after a full generation.

**Fix:** a deterministic pre-validation check for item-shaped checks: every rubric criterion must
match at least one item's label, or the lesson is repaired before any validator call.

### A3 [read] The answer-leak scan is exact containment, so a paraphrase evades it
`assert_no_answer_leak` normalises and tests substring containment (`:7469`). "Gentle simmer" in the
key and "simmer gently" in the page is not a leak by that test. Word-order and morphology changes are
the normal way prose restates an answer.

**Fix:** add a token-set overlap test (content words, ≥0.8) alongside containment, with the label and
choice fields exempt as today.

### A4 [read] There is only a 120-character floor on a segment, no ceiling
`MIN_SINGLE_SEGMENT_CHARS = 120` (`:7117`) refuses an outline; nothing refuses a 2 500-character wall
in one heading. L6 (cognitive load) has no enforcement.

**Fix:** a per-segment ceiling sized to the lesson budget (with a named reason and a split hint).

## Shape at length

### S1 [read] `terminal_performance` is write-only, and a full course can end anywhere
The field is declared (`:2715`), demanded in the prompt (`:4935`), and never read outside the schema
and the plan rules — the lesson payload carries neither `exit_performance` nor `terminal_performance`
(`:9210-9245`). The rule only requires an objective in the last *unit* to be procedure/transfer, not
the last section, and not an integrative task.

**Fix:** carry both into the lesson payload, and require the last owner section of a `full` course to
be the declared exit performance.

### S2 [read] Units add no lesson-level context, so "full" is more of the same
The lesson payload carries `plan_title`, `learner_outcome`, `through_line`, and a single
`previous_section` title; `unit` is a bare `unit_id` and there is no list of what was already taught
(`:9210`, `:12669`). Section 30's authoring inputs are the same kind as section 2's.

**Fix:** add `unit` (title, goal, prereqs) and `taught_so_far` (earlier objective titles) to the
payload; require the section to build on them.

### S3 [read] `spaced_review` is a plan word, not a schedule; a review re-presents the identical check
The flag is validated only for recipe consistency (`:6385`); `review.py` schedules from evidence, never
from the flag. A review lesson copies the owner's `stimulus`/`reference`/`rubric` verbatim
(`:13605`), so the learner re-answers byte-identical items — and if the owner check is closed, the
review page cannot be served.

**Fix:** when `spaced_review` is true require a review per N owner sections, and require the review to
be a different form of the same target (new items, same evidence).

### S4 [read] Prerequisite edges never gate anything at runtime
`run_lesson_job` accepts any `unit_ordinal` (`:13051`) and checks no prerequisite; the edges are
enforced only as shape (backwards, unique, acyclic). Authoring unit 3 before unit 1 is legal, and its
review then fails the whole unit job because the unit-1 checks do not exist yet.

**Fix:** gate the lesson job on `prereq_unit_ordinals` completion with a typed refusal before any
provider call, and park a review whose target is unwritten instead of failing the unit.

### S5 [read] The full objective floor pads narrow goals
The floor is a count (`:6610`), and `_duplicate_performance_reasons` only refuses objectives with the
same quote + target + criteria. A goal the ledger supports with five capabilities must be
manufactured into twelve as "recognise the parts" → "identify the parts with support" → "name the
parts".

**Fix:** tie the floor to the ledger's distinct capability count, and disclose the shortfall in
`exclusions` instead of splitting one capability into three lessons.

### S6 [read] Research support per objective collapses ~10× from single to full
`_BUDGET_MATRIX` gives single/working 4 sources, short/working 8, full/deep 16 (`research.py:97`),
against 1 / 3–6 / 12–40 objectives: 4.0, 1.3, 0.4 sources per objective. Every `sourced` objective
needs a verbatim quote from a cited excerpt, so most of a 40-objective course must be `unverified`.

**Fix:** bind the objective ceiling to the research cell (objectives ≤ 2 × sources) or raise the full
source budget.

## UX and visual coherence

### U1 [read] The wide Home's course cards cannot be reached by keyboard
At ≥1200 the scene card is an `<article>` with only `onClick` (`30-home.js:690`), while the same card
below 1200 is a real `sdk.RowButton`. Keyboard access disappears exactly when the window is wider.

### U2 [read] One unconfirmed low-emphasis click permanently downgrades the attempt
"I saw the answer" is a text-weight button beside Submit (`70-learning.js:2500`); it fires
`lesson.assist(kind:'answer_shown')` immediately with no confirm or undo, and the next committed
attempt can never be independent.

### U3 [read] The lesson header prints a section number over a step count
`stopTotal = steps.length` but `ordinal = section.ordinal` (`80-components.js:3909`), so section 7 of
a 5-block lesson reads "STOP 7 OF 5", beside "Step 1 of 5".

### U4 [read] The course overview calls every next step "Start a fresh run"
A binary label (`90-course.js:103`) maps `resolve_review_due` and `review_plan` to "Start a fresh run"
and then calls `onResume(objective_id)` — the wrong action for a due review.

### U5 [read] A live player sits under a live "Start a fresh run" strip
`80-components.js:4824` renders "This section has no lesson chat yet… Start a fresh run" while the
player is already open on step 1 of 5; the button arms a new run and abandons the player.

### U6 [read] One noun, four names; one state, three words
A section is "Section 2 of 6" (`30-home.js:1552`), "Checkpoint 3" in the accessible name (`3427`),
"STOP 7" (`80-components.js:3915`) and "Objective title" in Studio (`95-studio.js:5229`);
`independent_evidence` is "Evidence", "Independent evidence" and "Complete".

### U7 [read] The create flow asks the goal twice and repeats its own label
Step 1's heading is "What do you want to be able to do?" and its field label is the same sentence
60 px below (`50-create.js:897`, `967`); step 3 asks "…when this is done?" (`181`).

### U8 [read] Learner copy still speaks pipeline
"This run will author… the exact preflight — a cost band and a call band — arrives with the plan job;
nothing here is priced before the backend has sized the run" (`50-create.js:1558`); the tutor pane
prints a skill slug and a routing apology (`99-tutor.js:1736`).

### U9 [read] The wide Home is a fixed 1344×768 stage that clips its own art
`76-v3-scope.js:223` fixes the scene at 1344×768 with `overflow:hidden` and is selected for every
width ≥1200; at 1250 the fox (left 1110 + 208) is cut by more than half, and the scene has no
See all for a fifth course.

### U10 [read] The print sheet prints captions for figures it never prints
`95-studio.js:2191` emits one `.caption` per media child and `cbLessonPrintHtml` emits no `<img>`, so
paper says "A cutaway of the brake caliper" with no cutaway and no omission note.

## The improvements

Each item below passed the adversarial check: it is not already implemented (the evidence shows the
seam), it does not contradict an existing invariant (the conflict is named where one exists), and it
has an acceptance test that fails today.

| # | improvement | evidence | adversarial note | acceptance |
|---|---|---|---|---|
| 1 | Scope-scaled request bound in unit-sections and lesson requests | G1 | 48 kB is a local JSON guard, not a provider limit; the plan stage already uses it | 6-source full fixture reaches the model |
| 2 | Per-unit lessons job, Run again, `next_unit_ordinal` | G2 | keeps idempotency within a unit; fixes double-spend by keying plan+unit | 2-unit plan authors both units |
| 3 | Plan completion cap by scope + `.cut` repair | G3 | same helper the other stages use; no schema change | cut answer produces a re-ask |
| 4 | Plan budget sized from the validation pass plan | G4 | mirrors `lesson_cost_budget`; no new ceiling policy | 40-objective fixture ≥ 2(1+14)+4 calls |
| 5 | Typed `SCOPE_BAND` refusal naming a legal scope | G5 | must not park a plan; refusal happens after the last attempt | 1-objective full → refusal names `short`, no row |
| 6 | Contiguous scope bands (short 3–8, full 9–48) | G5 | changes a designed table; the design doc's own 10-week case is the reason | 10-objective plan accepted at short |
| 7 | Revisit a passed objective by cloning its authored check | L1 | `revisit: true`, no second XP, no second independent transition | pass then `check.open` returns a check |
| 8 | Adopt `check.open`'s revision into the fence | L2 | same value the backend just returned; no new field | first submit after open carries R+1 |
| 9 | "Start anyway" sends `acknowledge_prerequisites` | L3 | contract already documents it; the UI already promises it | check opens with `unmet_acknowledged` |
| 10 | Terminal completion state and panel | L4 | a new state, not a new plan; no RPC break | finished course → `complete`, not `review_plan` |
| 11 | `needs_review` gets its own state, reason and Repair | L5 | separates two conditions the backend already distinguishes | rejected lesson shows reason + Repair |
| 12 | Model-assessed warning in the lesson header | L6 | the warning is already served; only the read is missing | DOM contains the warning when `independent=false` |
| 13 | Award XP in the shared commit path | L7 | idempotent by attempt id already; game-mode gate stays | reader pass raises `xp_total` |
| 14 | Scope the binding refusal to the check's objective | L8 | matches the docstring's intent; no new state | detached A, submit B succeeds |
| 15 | `rubric_consistency` waived for verification checklists | A1 | the confirmation lane never reads weights; the waiver names why | one-off with a safety note passes |
| 16 | Deterministic rubric↔item coverage before the validator | A2 | item-shaped checks only; free-response keeps the validator | uncovered criterion repairs before a provider call |
| 17 | Paraphrase answer-leak scan (token overlap) | A3 | exempts choices/items exactly as containment does | "simmer gently" flagged against "gentle simmer" |
| 18 | Per-segment ceiling sized to the lesson budget | A4 | keeps the 120-char floor; names the split in the repair | 2 500-char segment refused with a split hint |
| 19 | `terminal_performance` reaches the lesson payload and the last section | S1 | applies to new plans; existing courses unaffected | full plan's last owner section is the exit |
| 20 | `unit` + `taught_so_far` in the lesson payload | S2 | payload-only; no schema change | two units produce different `unit` blocks |
| 21 | `spaced_review` requires a review per N owners and a different form | S3 | does not change `review.py`'s evidence scheduling | 0-review committed plan refused |
| 22 | Prerequisite gate on the lesson job, typed before spend | S4 | refusal before the first provider call, not after | unit 3 before unit 1 refused with a typed reason |
| 23 | Full objective floor tied to sourced capabilities | S5 | the shortfall is disclosed, not hidden | 5-capability full plan accepted with exclusions |
| 24 | Keyboard-operable wide Home cards | U1 | reuse the `sdk.RowButton` already used below 1200 | Tab reaches the card, Enter opens |
| 25 | "I saw the answer" gets a consequence confirm | U2 | keeps the honest record, removes the misclick | no RPC until the confirm |
| 26 | "STOP n OF m" uses one denominator | U3 | section number vs course total, not block count | header never reads "STOP 7 OF 5" |
| 27 | One primary-label map for the course page | U4 | `DESK_PRIMARY_LABEL` already exists on Home | review due → "Start the review" |
| 28 | Hide the start strip while the player is mounted | U5 | one exit stays in the player footer | no "Start a fresh run" under a live player |
| 29 | One noun ("section") and one word per state | U6 | derive every surface from one map | a copy test asserts the single source |
| 30 | Create asks the goal once; step 3 asks what would prove it | U7 | keeps the outcome field, changes the question | steps 1 and 3 are not near-identical |
| 31 | Learner copy without pipeline words | U8 | diagnostic strings move behind settings | shipped-copy scan finds none of the banned words |
| 32 | Wide Home scales to the route and offers See all | U9 | gate on width and height; below 1200 unchanged | fox's right edge ≤ scene width at 1250 |
| 33 | Print an omission note, never an orphan caption | U10 | print spec already omits art; the note makes it honest | sheet says the figure is not printed |

Thirty-three, not twenty; items 1–24 are committed to this wave, 25–33 are carded behind them.

## What held up

- Plan honesty: exclusions with reasons, a quote per sourced objective, `attainment_hours: null` with
  a stated basis, and a warning naming the one-off's self-reported completion.
- Independent validation is real: different model (`z-ai/glm-5.3-flash`), recorded `independent`, and
  a `pass` that is not the author's own.
- No raw hex in the eight learner files; colour comes from the `--cb-*` token tables.
- No fake progress: the plan wait shows elapsed time and the job's own stage, never a percentage.
- Honest failed reads: Home, Courses and the section page render a typed failure with a retry.
- Plan reorder is keyboard-operable (Move up/down plus `Alt+Arrow` with `aria-keyshortcuts`).
