# Generic acceptance audit 2 — after CourseBlueprint v2 (H-30b)

Date: 2026-11-07. Auditor: sentinel (independent). Base: `origin/master` **`f990cad`**
(`integration: carry parent supervision and media into the v2 plan prompt`), worktree
`.worktrees/t_9b6742f3`, branch `wt/harness-generic-audit-2`. No product code, merge, push, tag,
publish or demo. One provider call was spent by the upstream H-21c ceiling card; this audit spent
**zero** provider calls and used no credentials.

This document supersedes `docs/GENERIC-ACCEPTANCE-AUDIT.md` (H-30, base `498b1da`). Its `single`
and `full` failures were re-tested here against the landed blueprint; they no longer reproduce.

## What is fake and what is real

| part | status |
|---|---|
| model responses (plan, unit sections, lessons, validation) | **FAKE** — deterministic `ScriptedLLM` in `audit/adversarial/generic-harness-v2/generic_v2_e2e.py`, authored to the *contract* shape; no provider called |
| research fetch | **RECORDED** — one in-memory page through the real search seam (`https://example.invalid/recorded-page`); not the live web |
| `course.create` / `enrollment.create` / `jobs.create` / `plan.approve` / `course.outline` / `lesson.page` / `check.open` / `attempt.submit` | **REAL** — `coursebook.api.dispatch`, cb.rpc v11 |
| `run_plan_job`, `run_unit_sections_job`, `run_lesson_job`, migrations, schemas, deterministic rules, validation verdicts, plan hash, approval gate, check payloads, grading lanes and verdicts | **REAL** — the shipped code on `f990cad` |
| the `full` request's token/byte ceiling | **MEASURED upstream** — one real `nous/deepseek-v4.1-flash-1017` call recorded in `docs/PLAN-CEILING.md` and `t_6576b611`'s `plan-ceiling-probe.json`: 24 objectives / 6 units, 2,920 input / 5,859 output tokens, schema-valid and rules-passing. Not re-run here (no spend). |

The e2e proves what the *product* does with a contract-valid document and through the real grading
path. It does not claim a live model authors the `single` or `short` document; that remains a
model-quality question, and the one live measurement on record is the `full` blueprint above.

## Commands

```
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_9b6742f3
PYTHONPATH=. python3 audit/adversarial/generic-harness-v2/probe_shape_v2.py
PYTHONPATH=. python3 audit/adversarial/generic-harness-v2/generic_v2_e2e.py single short full
PYTHONPATH=. python3 -m unittest tests.test_prerequisite_gating tests.test_grading_lanes \
    tests.test_blueprint_units tests.test_plan_units tests.test_plan_approval -v
PYTHONPATH=. python3 -m unittest discover -s tests -t .
```

Raw evidence (all under `audit/adversarial/generic-harness-v2/evidence/`):

| file | sha256 |
|---|---|
| `probe_shape_v2.txt` | `1e53728a86dd6144427f6f3ca35e0fd206b13f198d53f89d220bb0b7b47b8e7a` |
| `single.json` | `4e1e7c5888e4a82686c439b2a105c233d00846ceeb9ea33ed8cbc1d9f92293ff` |
| `short.json` | `ab9c7a3ba9fe80d3d2cf4a05f367a430bc6249886e339f81177e23576d775e4c` |
| `full.json` | `2c98c4c1e3a1111abfc10b7c5cd62275b6c517e00e773c3c84f8258a01f37489` |
| `fail_closed_approval.json` | `fd136270ba079c3e1c4f332f5785de05554722aee7eeac87e524e118ab35e7f1` |
| `missing_required_step.json` | `2750254ecc13eed738a80b9496f63ead69c7909270e5c0739a97dd928f46b04c` |
| `legacy_projection.json` | `e19c392139b19b993828c96b45b4bd992de1322c62b8e94098c4ff9d4fbf9d85` |
| `e2e-run.txt` | `648d5b5bc272a6121036515245362ddad4e345c7e24645aa0561d45e6e825fa7` |
| `focused-tests.txt` | `ce5eea321a806c3509d3f0b6c40b3cc32b4dc2d46c5774ec3d6c80e2a5e86865` |
| `full-suite.txt` | `4cbcb11443cb0290f228ab41fb9b817f4e6c4cc332f9803e0d3cee00d6bad8d1` |

The JSON evidence contains run-specific ids (`plan_id`, `job_id`, attempt nonces), so the hashes
pin *this* run, not a byte-reproducible transcript; re-running the same commit changes the ids and
the hashes while the observed verdicts must stay the same.

## Shape verdicts

### 1. `single` — bicycle tube replacement one-off — **PASS**

Brief (exact): *"Walk me through replacing the inner tube on my road bike and checking the brakes
before I ride it today."* Recipe `one_off`, scope `single`, `en-US`, `beginner`, `repair`.

| fact | value |
|---|---|
| plan request | schema `coursebook_plan_v2`, prompt `plan-prompt.v4`, `max_tokens` 12000, rules `objective_count [1,1]`, `unit_count [1,1]` |
| authored/stored document | `plan_schema: coursebook.plan.v2`, `scope: single`, **1 unit / 1 objective / 1 check entry** |
| check plan | exactly one entry, kind `verification` (no quiz); `spaced_review: false` |
| validation | verdict **pass**; plan row `draft`, generation record `draft` |
| approval | wrong hash → `VALIDATION_FAILED`, plan stays `draft`; correct hash after validation → approved |
| lessons | **1** section, **1** lesson, `needs_review: []` |
| check storage | 1 check, reference kind **`rubric_only`**, stimulus format `verification` |
| grading route/verdict | `provider-free:confirmation`; all 3 declared items → **`pass`**, evidence class **`self_reported`**, `next_action: review_objective` |
| evidence | `evidence/single.json` |

The old 4-objective padding is gone end to end: a 4-objective `single` plan is now refused by the
deterministic rules (`scope 'single' requires 1 to 1 objective(s); the plan has 4`), not silently
accepted (`probe_shape_v2.txt`). The one verification check is routed deterministically and never
claimed as independent evidence (`self_reported` is the honest class).

### 2. `short` — three-week practical cooking — **PASS**

Brief (exact): *"Three weeks of practical weeknight cooking: knife skills, pan heat, seasoning and
a repeatable dinner plan I can cook without a recipe."* Recipe `committed`, scope `short`,
`en-US`, `beginner`, `general`.

| fact | value |
|---|---|
| plan request | rules `objective_count [3,6]`, `unit_count [1,3]`, `unit_objective_count [1,6]` |
| document | `coursebook.plan.v2`, 2 units / 4 objectives / 4 quiz checks, `spaced_review: true` |
| validation | **pass**; approval after validation only |
| unit stages | unit 1 → 2 sections, offers `next_unit_ordinal: 2`; unit 2 → 2 sections, offers `null` |
| user-enqueued next unit | no job row was created by either stage (`chained_a_job: false` for both) |
| lessons | 4 of 4 authored, `needs_review: []`, no truncation |
| outline | 2 units, 4 objectives; unit 2 `prereq_unit_ordinals [1]`, `prerequisite_state: unmet` (2 objectives not independently shown) |
| checks | 4 checks, reference kind **`exact`** |
| grading | correct answer → **`pass`**, `cold`, `complete_objective`; wrong answer → **`not_yet`**, `cold`, `retry_attempt` — neither is `needs_retry` |
| evidence | `evidence/short.json` |

### 3. `full` — 12+ unit college-style course — **PASS**

Brief (exact): *"A first-year college introduction to data structures: arrays, lists, stacks,
queues, trees, hashing and graphs, with assessments and prerequisites."* Recipe `committed`,
scope `full`, `en-US`, `beginner`, `general`.

| fact | value |
|---|---|
| plan request | rules `objective_count [12,40]`, `unit_count [2,12]`, `unit_objective_count [2,6]`; `max_tokens` 12000 |
| document | `coursebook.plan.v2`, **6 units / 24 objectives / 24 quiz checks**, `spaced_review: true` |
| prerequisites | unit *n* names unit *n−1*; all refs strictly lower |
| validation | **pass**; approval after validation only |
| unit stages | 6 unit-section stages, 4 sections each; each offers the next ordinal and creates no job |
| lessons | **24** of 24 authored, `needs_review: []` |
| outline | 6 units, 24 objectives; units 2–6 `prerequisite_state: unmet` with 4 unmet objectives each until the previous unit is independently shown |
| checks/grading | 24 checks, all `exact`; correct → `pass` / `cold` / `complete_objective`; wrong → `not_yet` / `cold` / `retry_attempt` |
| evidence | `evidence/full.json` |

The measured ceiling is honoured, not merely asserted: `probe_shape_v2.txt` shows a **40-objective**
full plan accepted by both schema and rules, and a **41-objective** plan rejected by the schema
(`/check_plan ... is too long`, `/objectives ... is too long`,
`/check_plan/40/objective_ref: 41 is greater than the maximum of 40`). >8 objectives are no longer
rejected by the old cap: 12, 24 and 40 all pass; the 9-objective case that the old H-30 probe
called "rejected" was a v1 read, and a 9-objective **full** plan is still refused by the *scope
minimum* (`12 to 40`), which is the contract, not the old cap.

## Must-prove / refute

| claim | verdict | evidence |
|---|---|---|
| `PLAN_SCHEMA` v2 accepts one objective/one unit for `single` | **PROVEN** | schema `objectives.minItems 1`, `units.minItems 1`; 1-objective plan ACCEPTED by schema and rules (`probe_shape_v2.txt`) |
| v2 accepts >8 objectives for `full` | **PROVEN** | 12-, 24- and 40-objective plans ACCEPTED; 41 rejected by the declared cap |
| `course.outline` projects units | **PROVEN** | 2 units in `short`, 6 in `full`, key set `ordinal/title/goal/prereq_unit_ordinals/prerequisite_state/unmet/objectives` |
| legacy plans project one implicit unit | **PROVEN** | unscoped v1 brief → `coursebook_plan_v1`, `plan_units` rows **0**, outline returns one unit titled with the course, 4 objectives, `no_edges` (`legacy_projection.json`) |
| H-12 approval remains fail-closed | **PROVEN** | wrong `plan_hash` → `VALIDATION_FAILED`, plan stays `draft`; failed independent validation → `needs_review`, `plan.approve` → `VALIDATION_FAILED` / `plan_not_validated` (`fail_closed_approval.json`) |
| plan hash invariance for legacy plans | **PROVEN** | `plan_content_hash` identical before approval, after approval and after 4 lessons (`legacy_projection.json`: `hash_unchanged: true`); `test_legacy_plan_hash_unchanged_after_0007` passes |
| generated checks carry a closed reference lane (B-1) | **PROVEN** | every generated quiz check stores `reference.kind = exact`; the one-off verification check stores `rubric_only` with a confirmation-shaped stimulus; `check.open` refuses a reference with no kind (code gate) |
| correct generated answer no longer returns `needs_retry` | **PROVEN** | `pass` / `complete_objective` in `short` and `full`; H-30's defect does not reproduce on `f990cad` |
| a required step that cannot be generated is refused/hidden, not promised | **PASS with a recorded caveat** | a unit section batch missing one objective: job returns `state: needs_review` with typed reasons (`objective 4 has no owner section`, `targets 2 lesson(s) ... leave 1`), the lesson stage **refuses** (`owner sections cover objectives [3] but the unit has objectives [3, 4]`), `course.outline` reports `check_state: none`, and `lesson.page` serves an **empty** document (`state: empty`, `view_note: "This section has no teaching content yet."`, `check_id: null`) — no fake lesson and no check. Caveat D1 below. |

## Findings (none blocking; all are honesty/clarity, not shape failures)

| id | severity | owner | finding |
|---|---|---|---|
| D1 | P3 | H-21 | A unit stage that fails its own rules **persists the partial batch** with `state: needs_review` instead of writing nothing (1 of 2 sections in `missing_required_step.json`). The imperfect unit is not served (lesson job refuses, `lesson.page` empty, no check), so it does not promise content, but the durable partial row is a replay/repair hazard: a later retry must not treat it as authored. |
| D2 | P3 | H-34/H-21 | The one-off verification check completes with `evidence_class: self_reported` and `next_action: review_objective`, not `complete_objective`. That is the honest H-34 design (a tick-list is self-report), but the acceptance prose must not describe it as independent evidence. |
| D3 | P3 | H-21 | The `full` scope prompt line still reads *"a full course; the standard objective range stands"* while the numbers around it are the v2 `12 to 40` band. The numbers are correct; the sentence is stale and invites a reader to think the v1 4–8 range applies. |
| D4 | P3 | H-21 | `SCOPE_EXPECTATIONS[scope]["objectives"]` still carries the v1 ranges (4–5 / 4–6 / 4–8) beside the v2 `blueprint_objectives`. It is only read by the v1 prompt path, but the stale H-30 `probe_shape.py` reads exactly this key and still reports "schema min 4/max 8" on `f990cad`. Any audit must read `blueprint_objectives`/`PLAN_SCHEMA_V2`, as `probe_shape_v2.py` does. |

No P0/P1/P2 defect was found in this re-audit.

## Regression evidence

```
python3 -m unittest tests.test_prerequisite_gating tests.test_grading_lanes \
  tests.test_blueprint_units tests.test_plan_units tests.test_plan_approval -v
-> Ran 62 tests in 21.063s, OK

python3 -m unittest discover -s tests -t .
-> Ran 1264 tests in 199.415s, OK
```

The suite is 1264 tests on `f990cad`; H-21c recorded 1223 on `bcd545e`, and the H-30 audit
recorded 1052 on its base. The counts differ by base, not by failure.

## Verdict

**Generic harness: PASS, for the three required shapes, on `f990cad`.**

- `single`: **PASS** — one unit, one objective, one verification check, no quiz/homework, approval
  only after validation, one lesson, deterministic `rubric_only` confirmation route.
- `short`: **PASS** — 2 units / 4 objectives within the short bounds, unit-scoped authoring,
  user-enqueued next unit, 4 lessons, generated checks grade `pass`/`not_yet` instead of
  `needs_retry`.
- `full`: **PASS** — 6 units / 24 objectives with prerequisite edges and assessments, 24 lessons,
  deterministic grading, cap honoured at the measured 40-objective ceiling.

The H-30 result ("not yet fully generic — one-off cannot be one objective; full cannot exceed
eight; generated checks do not grade") is **stale** and must not be cited as current. The remaining
limits are model-quality (no live `single`/`short` authoring was measured here), the fake/recorded
labels above, and the four P3 findings; none of them blocks the generic-harness claim.

## Not verified (do not infer)

- Live provider authoring of a `single` or `short` plan (only the upstream `full` probe exists).
- Live web research; the research page here is a recording.
- A 40-objective course authored end to end; only its schema/rule acceptance is proven.
- Desktop renderer, accessibility and responsive surfaces (covered by other cards; not run here).
- Spanish/language-goal end-to-end authoring.
- Cancelled jobs, resume at a unit boundary and concurrent unit stages.
