# HARNESS-NEXT-CARDS — review index

Date: 2026-11-07. Board: `coursebook` (Kanban). Base: `origin/master` @ `200e6d3` (M4 series;
1040 tests green before this slice). Source for the first eleven cards:
`docs/ADVERSARIAL-HARNESS-REVIEW.md` (NO-GO as a general harness; P0-1…P0-7).

This is a **harness-completion** slice, not demo polish. The Japanese demo remains a fixture and
is not proof for any card here. Publication/tag/catalog/announcement remains hard-gated on the
operator's explicit sign-off (`docs/SUBMISSION.md` §0).

## Board state at creation

| status | count | notes |
|---|---:|---|
| done | 103 | M0–M4 build-complete |
| blocked | 1 | `t_6a32ffe9` — operator gateway restart/demo gate |
| running | 2 | `H-01` contract, `H-10` adversarial round 2 |
| todo | 10 | the reviewable DAG below |
| review/ready | 0 | — |

## The DAG

All cards are `--workspace worktree`, `--max-retries 1`, model
`deepseek/deepseek-v4.1-flash-1017` / provider `nous`. Parents must be merged before a child is
started; the board dispatcher enforces that.

| key | id | card | owner | parents | branch |
|---|---|---|---|---|---|
| H-01 | `t_f4f5b26a` | cb.rpc v10 learner capability inputs and plan-job contract | atlas | — | `wt/harness-contract-v10` |
| H-02 | `t_867d3b52` | Learner goal → plan job → plan approval → lessons | vellum | H-01 | `wt/harness-create-flow` |
| H-03 | `t_577ed286` | Design a scope-aware CourseBlueprint before code | atlas | H-01 | `wt/harness-blueprint-design` |
| H-04 | `t_161d467f` | Research depth and source strategy — make the depth dial real | quill | H-01 | `wt/harness-research-depth` |
| H-05 | `t_7baa29e2` | Plan-time media needs and capability declaration | cinder | H-03, H-04 | `wt/harness-media-plan` |
| H-06 | `t_7a320d2f` | Procedure authoring path — make the technical lens reachable | cinder | H-05 | `wt/harness-procedure-author` |
| H-07 | `t_2f3cc647` | Parent brief fidelity — stop storing fields the plan never sees | cinder | H-01 | `wt/harness-parent-brief` |
| H-08 | `t_901c8310` | General authored export — a normal course can package itself | cinder | H-02, H-03 | `wt/harness-authored-export` |
| H-09 | `t_ebc196db` | Arbitrary-topic end-to-end proof (non-Japanese) | sentinel | H-02…H-08 | `wt/harness-e2e-proof` |
| H-10 | `t_1efc158a` | Deep adversarial audit round 2 — trust, pedagogy, scale, breadth | sable | — | `wt/harness-adversarial-2` |
| H-11 | `t_6f41e0b0` | Truth pass — docs/status after the harness slice | quill | H-09 | `wt/harness-docs` |
| H-12 | `t_dba06898` | Fail-closed plan approval — empty, rejected, or edited plans cannot approve | cinder | — (hotfix) | `wt/harness-plan-approval` |
| H-13 | `t_543c0767` | Thread level, subject_domain and scope into the plan runtime | atlas | H-01 | `wt/harness-policy-threading` |

H-12 is a root card because the defect is live on the current master and does not need the
contract work. It touches plan approval, not the course-create fields. If it collides with H-01 in
`coursebook/domain.py`/`migrations/`, the integrator resolves at merge; the card must stop and
report the collision rather than silently rebase.

## What each card must produce

- **H-01**: additive cb.rpc v10 contract; `level`, `subject_domain`, `scope` on
  `course.create`/`jobs.create`; a cb.db migration or documented course-brief storage; contract
  tests; no UI.
- **H-02**: `CreateCourseFlow` calls `jobs.create` (kind `plan`, stage default), polls, shows an
  honest time expectation, supports cancel/error, reviews a plan, calls `plan.approve`, starts the
  lessons job, links the first lesson. Reuses the Parent Studio components where genuinely
  reusable; no second engine, no fake percentage.
- **H-03**: design doc only. `single` = exactly one objective/section; `short` = 3–6; `full` =
  multi-unit with prerequisite structure and a continuation job. Includes migration, token/cost,
  approval granularity, partial generation, three examples, and explicit out-of-scope.
- **H-04**: depth values differ (`survey`/`working`/`deep`), scope-aware budget, locale-aware
  queries, source-type recording, honest degraded behavior, tests. No invented authority.
- **H-05**: plan sections declare bounded media/construct needs; policy consumes them; validator
  enforces required/forbidden; generated-plan tests across six subjects; no decorative media.
- **H-06**: `procedure` authored lesson schema (tools/parts/hazards/stop/steps/schematic/source);
  prompt, projection, deterministic validation; generated procedure fixture; old pages still
  render; an illustration is never the authority.
- **H-07**: parent brief fields actually reach `build_plan_request`; desired pages bound the plan;
  desired visuals/narration feed H-05; parent observation-only; no child chat.
- **H-08**: general authored export for a non-pack course; allowlisted rebuild; approved-plan and
  validated-page gate; hash change blocks; export action on the normal course surface.
- **H-09**: three non-Japanese goals (single/short/full), product path, evidence packet with
  live/fixture labels, procedure/audio/export assertions, no Japanese. This is the card that
  decides whether the harness claim is real.
- **H-10**: second adversarial audit: source trust/injection, validator independence, pedagogy and
  adaptation, assessment breadth, scale/cost/concurrency, privacy/exports, localization/a11y, host
  seam, tests that supply impossible inputs. Report + probes; no policy rewrite.
- **H-11**: docs truth pass; status table separates harness code complete, authored E2E, live UI
  proof, prepared-pack demo and product 1.0; §0 stays closed.
- **H-12**: fail-closed plan approval. A generated plan needs a durable pass record at the exact
  current hash; manual nonempty plans may approve without claiming validation; empty plans always
  refuse; edits/replans invalidate; no transition/revision on refusal. Tests update the existing
  empty-plan approvals.
- **H-13**: runtime threading of `level`, `subject_domain`, `scope`; fingerprint includes them;
  locale ≠ subject domain; Spanish technical schematic and Japanese math protection; tests at the
  generation/domain boundary.

## Deeper adversarial findings found while seeding (2026-11-07)

These are beyond the first review. They are why H-12 exists now.

### D-01 (P0) — plan approval is advisory, not fail-closed

Real probe through `coursebook.api.dispatch` against a migrated cb.db:

```
course.create -> empty plan (0 objectives, 0 sections)
plan.approve(plan_hash, expected_revision=0) -> ok: true, revision 1
plans.state -> approved
```

A real integrated `run_plan_job` with a deterministic reject-validation fixture returned
`status='needs_review'`, `validation_verdict='reject'`, `validation_id=null`, and
`warnings=['independent validation did not pass: the plan is not approvable as-is']`. The plan row
stayed `draft`; `plan.approve` with the kernel `domain.plan_hash(plan_id)` then returned
`ok: true`, revision 1, `plans.state='approved'`.

`coursebook/domain.py:plan_approve` checks only the recomputed kernel plan hash and the plan row
state; it never reads the validation record, never requires an objective/section, and
`course.create` always inserts an empty draft plan. The generation digest in
`gen_plan_documents.plan_hash` and the kernel digest in `parent_authoring/domain.plan_hash` are
different functions; a fix must bind validation to the exact kernel content hash, not compare the
two hashes.

Consequence: a rejected or empty plan becomes the course's approved plan. Every downstream
operation that asks "is there an approved plan?" (lesson authoring, `check.open`, Parent final
approval, export) treats it as real. This directly contradicts "generation ≠ validation" and makes
the independent validator a suggestion, not a gate. H-12 fixes it.

### D-02 (P0, test-quality) — the green suite encodes the defect

`tests/test_kernel_commands.py` approves an empty plan in
`test_approval_bumps_revision_and_writes_one_transition` and again in
`test_replan_unknown_objective_is_not_found`; the fixture helper `approve()` is used by many tests
with a seeded objective, but the empty-path approvals are asserted as success. A 1040-test green
run therefore cannot be used as evidence that validation gates approval. H-12 must change those
tests to seed a real manual objective or assert the refusal, and report the new count.

### D-02b (P0, API) — two plan digests, one approval

`run_plan_job` stores `generation.plan_hash(document)` in `plans.plan_hash` and
`gen_plan_documents.plan_hash`; `course.outline` returns that generation digest as
`plan.plan_hash`. `plan.approve` recomputes `parent_authoring.plan_hash(connection, plan)` — the
kernel digest — and requires that value. The Parent Studio path works around this by reading
`parent.blueprint.read.plan.plan_hash`; the learner `CreateCourseFlow` path has no documented
equivalent. A caller that follows `course.outline` gets `VALIDATION_FAILED: the approved hash does
not match the current plan content` even on a valid generated plan; a caller that uses the kernel
hash can approve a rejected plan because validation is not checked.

H-12 adds a durable validation binding and a learner-safe approval-hash projection; H-02 must use
it. This is not a reason to compare the two digests directly — both are real and serve different
consumers.

### D-03 (P1) — the plan job drops the inputs the contract collects

`run_plan_job` reads `goal`, `recipe`, `dials`, `locale` only. Even after H-01 adds `level`,
`subject_domain` and `scope` to the contract, the runtime will ignore them unless H-13 lands. Its
reuse fingerprint is `(goal, recipe, dials, locale)`, so two different courses can reuse a plan
across a changed subject/level/scope. H-13 exists for this; H-04 also needs the scope value for a
real full-course budget.

### D-04 (P1) — the "adaptation" claim is a state transition

`review.py` is a real, honest scheduling heuristic, but the learner loop has no prerequisite graph,
no dynamic re-plan, no choice among remediation/examples/next objective, and no attempt-driven
content change. The only adaptations are evidence-state transitions (`needs_review`,
`review_due`) and a fixed ladder. H-03's design must include prerequisite/unit structure and a
continuation path; H-10 must quantify whether any stronger "adapts" claim is defensible. Do not
market the heuristic as adaptive teaching.

### D-05 (P1) — validation independence is structural only

`assert_separate_pass` guarantees a different prompt and schema, not a different model or an
external check; the generator and validator are the same host model. `validation_verdict` trusts
the validator's `criteria` and `claim_verdicts`. H-10 must measure a plausible-but-wrong candidate
and a sycophantic validator, then propose a concrete guard and its cost.

### D-06 (P2, docs) — stale defect claims survive in the README

`README.md` still lists `CB-QA-10` (answer key in `evidence.inspect` L2) as open, while
`coursebook/evidence.py` now projects only `PUBLIC_CRITERION_FIELDS` and
`tests/test_review_evidence.py` asserts `check_spec` is absent. Either the defect was fixed without
closing its public record, or the current code does not match the claim. H-11 must reconcile the
README, `docs/PRIVACY_EGRESS.md`, `docs/ACCEPTANCE.md` and `REVIEW_CB014` rather than repeating a
stale defect. This is a truth pass, not a code change.

## Execution rules

- A card's branch is merged by the integrator only after the merged tree passes the frozen gate:
  full Python suite, `node --check desktop/plugin.js` when touched, and
  `bash scripts/validate-plugin.sh` on a clean export. A branch's own claim is not the gate.
- Workers do not touch `master`, do not publish, tag, or record a demo. The board dispatcher
  enforces parents and one retry; the supervisor cron remains bounded.
- No card may use the prepared Japanese pack as proof of arbitrary-topic generation. H-09 is the
  only card that can establish that claim, and only for the goals it actually runs.
- The operator-only block `t_6a32ffe9` is unchanged: the default-profile gateway must be restarted
  by the operator before the demo gate can be measured. H-02 is the learner-path card; do not
  confuse it with the operator demo gate.

## Current decision

Build the harness, not the demo. If H-09 cannot produce a non-Japanese course from the product
path, the next step is a card against the failing layer, not another prepared pack.
