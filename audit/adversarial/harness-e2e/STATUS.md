# H-40 evidence packet — arbitrary-topic end-to-end proof, re-run on blueprint v2

Status: **3/3 scenarios PASS** on `wt/h09-e2e-rerun`, base `origin/master` **`c588e4a`**.
Auditor: sentinel (independent). Date: 2026-11-07.

This packet replaces H-09's `wt/harness-e2e-proof` packet, which measured a harness three
generations old (`00b502f`-era: before H-21 blueprint v2 units, before H-36 validator independence,
before H-19's review queue and before H-27/H-26b). Nothing from that branch was merged; this packet
is authored against the shipped tree and adapts the runner to the current
plan → unit sections → lesson → check.open → attempt.submit path instead of reverting it.

Scope: harness completion, not demo polish. No prepared Japanese pack, no Japanese fixture, no
Japanese content in any generated plan, lesson or served page. No product code changed. No
provider was called, no credential was used and no network request was made.

## What is live and what is recorded

| half | status | evidence |
|---|---|---|
| cb.rpc envelope + `coursebook.api.dispatch` (contract v13) | **live** | every step in `evidence/*.json` is an RPC response |
| SQLite migrations, kernel, plan/unit/section/lesson rows | **live** | throwaway `HERMES_HOME` per scenario |
| `generation.run_plan_job` (research seam, blueprint rules, independent validation, preflight) | **live** | prompts, rules and results captured |
| `plan.approve` with the kernel digest (H-12 fail-closed) | **live** | early + stale-hash refusals captured |
| `generation.run_unit_sections_job`, `generation.run_lesson_job` per unit | **live** | one job per unit, no executor chaining |
| `course.outline`, `lesson.page`, `check.open`, `attempt.submit` | **live** | two attempts per committed course |
| model responses | **RECORDED TRANSCRIPT**, hand-authored | `transcripts/*.json`, `labels.model` |
| validator identity | **RECORDED TRANSCRIPT**, a distinct recorded identity (`recorded-validator-h40`) | H-36 compares the reported model names; a same-name validator can only ever be `same_model` |
| research pages | **RECORDED PAGE**, fetched through the real search seam | `research` in each transcript |
| provider calls / spend | **none** | `labels.provider_calls = 0`, `provider_spend_usd = 0.0` |

The replay engine reads every property of the *request* (schema constant, capability policy, rubric
profile, unit ordinals, objective titles) from the live payload and takes only authored content
from the recording; a request the recording cannot answer is a hard failure, never a fallback. Each
`evidence/*.json` stores the plan document, the per-unit results, the plan request rules, every
lesson row state, the check lanes and the grading verdicts it actually read.

## Scenarios

| id | scope / recipe | goal | units | objectives | checks | lessons | grading |
|---|---|---|---|---|---|---|---|
| `bicycle_single` | `single` / `one_off` | "Walk me through replacing the inner tube on my road bike and checking the brakes before I ride it today." | 1 | 1 | 1 `verification` (`rubric_only`) | 1 validated | all 3 items ticked → `pass`, `self_reported`, `review_objective` |
| `music_short` | `short` / `committed` | "Understand intervals, triads and the circle of fifths well enough to analyse a pop song." | 2 | 4 | 4 `quiz` (`exact`) | 4 validated | correct → `pass`/`cold`/`complete_objective`; wrong → `not_yet`/`cold`/`retry_attempt` |
| `soldering_full` | `full` / `committed` | "Prepare for a first soldering repair on a through-hole PCB: safety, component placement, joints, inspection and desoldering." | 6 | 12 | 12 `quiz` (`exact`) | 12 validated | correct → `pass`; wrong → `not_yet` |

All three are subjects the Japanese fixture never saw. `soldering_full` declares prerequisite edges
unit *n* → unit *n−1*; `course.outline` projects a `prerequisite_state` for every unit and the
later units are `unmet` until the earlier objectives are independently shown.

### Plan ceiling, accepted and rejected at the declared bound

`SCOPE_EXPECTATIONS["full"]["blueprint_units"] = (2, 12)` and
`["blueprint_objectives"] = (12, 40)`; the schema pins the same maxima (`objectives.ordinal`
max 40, `check_plan` maxItems 40).

* **at bound** — 12 units / 40 objectives: schema-valid, every deterministic rule passes,
  independently validated (`pass`), plan state `draft` and therefore approvable.
* **over bound** — 12 units / 41 objectives: `GenerationRejected` —
  `plan violates its schema at check_plan: [...] is too long`.

Recorded in `evidence/soldering_full.json` under `ceiling_probe`.

## Assertions actually checked (all PASS)

Common to all three:

- no Japanese characters in the plan document, the lessons, or the run record;
- the plan is **independently validated** (`validation.outcome = independently_validated`,
  `independence = independent`) and `validation_verdict = pass` *before* approval;
- `plan.approve` with the correct digest succeeds (state `approved`); a wrong revision and a stale
  digest are both refused and the plan stays `draft`;
- one owner section per objective; every `gen_lessons` row is `validated`;
- prerequisite edges point strictly backwards and the outline projects a state for every unit;
- every unit/lesson stage is **user-enqueued**: no stage created a follow-on job;
- the served `lesson.page` never contains a check reference answer.

Per shape:

- `single`: exactly 1 unit, 1 objective, 1 check; the check is `verification` +
  `rubric_only` (the confirmation lane) and **no exact-lane quiz exists**; the tick-list grades
  `pass` with `evidence_class = self_reported`.
- `short`: 2 units, 4 objectives; every check is an `exact`-lane `text` quiz; the correct answer
  grades `pass` and the wrong answer `not_yet` — neither is `needs_retry`.
- `full`: multi-unit with declared prerequisite edges; every check is graded on the exact lane;
  both grading verdicts observed; the plan bound accepted at 40 objectives and rejected at 41.

## Differences from the pre-blueprint-v2 (H-09) run, and why

| H-09 (`111c7e9`, `00b502f`-era) | this run (`c588e4a`) | why |
|---|---|---|
| plan document had `sections`; 1 section = 1 lesson | plan document has `units` + `objectives` + `check_plan`; sections are authored by a per-unit stage **after approval** | H-21 blueprint v2 made units the authoring, budget and cancel checkpoint |
| `bicycle_single` = 4 objectives / 4 lessons | **1 unit / 1 objective / 1 lesson**, `verification` check | v2 `single` contract is exactly one unit and one objective; a 4-objective single is now refused by the rules |
| `music_short` = 5 objectives / 5 sections | **2 units / 4 objectives** | v2 `short` bounds are 1–3 units, 3–6 objectives, 1–6 per unit |
| `soldering_full` = 6 objectives / 6 sections | **6 units / 12 objectives**, prerequisite edges | v2 `full` requires 2–12 units, 12–40 objectives, 2–6 per unit |
| checks were document-level only; H-09 explicitly did **not** submit an attempt | `check.open` + `attempt.submit` through the real grading lanes, for every course | the lane split (H-34) and the check store landed after H-09; this was H-09's largest honest gap |
| validation identity was not a claim | author and validator report **different** recorded models; independence is read from the verdict | H-36 requires a real cross-model pass before anything may be called independently validated |
| export (`course.export.read` / `course.export`) was asserted | **not exercised in this packet** | export moved (H-08b authored export at v13); it is covered by `tests/test_course_export.py` and the authored-export packet, and re-running it here would need a different approval surface. This is a deliberate scope reduction, not a pass |

## H-30b's four P3 findings, re-checked on `c588e4a`

| id | finding | status here | evidence observed this run |
|---|---|---|---|
| D1 | a unit stage that fails its own rules persists a partial batch with `state: needs_review` | **open** — reproduced | `evidence/partial_unit_batch.json`: unit 2 authored 1 of 2 owner sections; job state `needs_review` with reasons `objective 4 has no owner section; author exactly one owner section per objective` and `unit 2 targets 2 lesson(s); this batch would leave 1 section(s)`; the lesson stage refuses (`unit 2 owner sections cover objectives [3] but the unit has objectives [3, 4]`); `course.outline` reports `check_state: none`; `lesson.page` returns `state: not_started` with `check_id: null` (H-30b saw `empty`; the state name changed, the behaviour did not). Nothing imperfect is served, but the partial row is durable. |
| D2 | the one-off verification check completes as `evidence_class: self_reported` / `next_action: review_objective`, not independent evidence | **open by design** — reproduced | `evidence/bicycle_single.json`: grading result `verdict: pass`, `evidence_class: self_reported`, `next_action: review_objective`. This is the honest H-34 confirmation lane (a tick-list is self-report); the acceptance prose must not call it independent. |
| D3 | the `full` prompt still says "a full course; the standard objective range stands" beside the v2 `12 to 40` band | **open** — reproduced | `SCOPE_EXPECTATIONS["full"]["note"]` at `coursebook/generation.py:214`, rendered into the v2 prompt by `_plan_instructions_v2`; the captured plan request rules on `soldering_full` read `objective_count [12, 40]`. Numbers correct, sentence stale. |
| D4 | `SCOPE_EXPECTATIONS[scope]["objectives"]` still carries v1 ranges (4–5 / 4–6 / 4–8) beside `blueprint_objectives` | **open** — reproduced | `coursebook/generation.py:193-215`: `single.objectives = (4, 5)` while `single.blueprint_objectives = (1, 1)`. Only the v1 prompt path reads it, but any audit that reads `objectives` instead of `blueprint_objectives` reports the wrong contract. |

No P0/P1/P2 defect was found. All four remain P3 honesty/clarity items; D1 is owned by H-21 and
is worth a follow-up card because a retry could misread the partial batch as authored.

## Not exercised / honest gaps

1. **Live provider.** No spend was authorised for this card. The model half is a recorded
   transcript; this proves the pipeline path, not model quality or how often a live model authors a
   contract-valid plan.
2. **Live web research.** The search seam is recorded; the budget arithmetic, ledger and failure
   handling around it are real.
3. **Course export.** Deliberately out of scope here (see the differences table). H-09's export row
   is not re-established by this packet.
4. **A language goal's audio/pronunciation path.** None of the three goals is a language goal.
5. **Thirty-nine of the forty ceiling objectives.** Only plan acceptance is proven at the bound;
   no 40-objective course was authored end to end.
6. **Desktop renderer, accessibility, responsive layout.** Covered by other cards, not run here.

## Reproduce

```bash
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_e32900ef   # base c588e4a
python3 audit/adversarial/harness-e2e/build_transcripts.py              # regenerate the recording
PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py       # drive all three shapes
PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v              # same runner + packet guard
PYTHONPATH=. python3 -m unittest discover -s tests -t .                 # full suite
```

Expected runner output (`evidence/run-output.txt`):

```text
bicycle_single: PASS  scope=single units=1 objectives=1 checks=1 lessons=1 validation=independently_validated
music_short: PASS  scope=short units=2 objectives=4 checks=4 lessons=4 validation=independently_validated
soldering_full: PASS  scope=full units=6 objectives=12 checks=12 lessons=12 validation=independently_validated
overall: PASS  (3/3 scenarios)
```

Focused test run: **11 tests OK** (`tests.test_harness_e2e`).
Full suite on `c588e4a` + this branch: **1422 tests OK** in 218.674s
(`evidence/full-suite.txt`; the 11 tests above are included).
