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
| H-14 | `t_031e287f` | Source-trust boundary and claim-level provenance lint | sable | H-10 | `wt/harness-source-trust` |
| H-15 | `t_d519643b` | Validator independence and the no-research factual waiver | atlas | H-10 | `wt/harness-validator-independence` |
| H-16 | `t_3c5d969c` | Assessment construct breadth decision (code/performance/artifact) | atlas | H-03 | `wt/harness-assessment-breadth` |
| H-17 | `t_9a8543ae` | Sized cost ceilings and CostCeilingExceeded recovery | cinder | H-10 | `wt/harness-cost-ceilings` |
| H-18 | `t_8407ea22` | Locale-aware scaffolds, direction/RTL, non-Japanese fixture | cinder | H-13 | `wt/harness-locale-scaffolds` |
| H-19 | `t_ec1d2c15` | Audit evidence index and reproducible provenance | quill | H-10 | `wt/harness-audit-index` |
| H-20 | `t_43ca17b8` | Prerequisite edges — conditional implementation from H-03 | atlas | H-03 | `wt/harness-prereq-edges` |

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

## Second wave — what the round-2 audit added

H-10 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`, 14 deterministic probes) found the next class of
failures. The report proposed its own H-11…H-18 labels; the board keys below are authoritative and
avoid those collisions:

| finding | severity | card | what it changes |
|---|---|---|---|
| P0-1 rejected plan is an approvable draft | P0 | **H-12** (already running) | validation binds approval; empty/rejected/edited plans fail closed |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **H-14** | untrusted-data envelope + claim-level provenance lint |
| P1-3 same model writes and validates; support self-upgrades | P1 | **H-15** | record/compare validator identity, cross-model path, no self-upgrade |
| P1-4 factual gate waives when research is unavailable | P1 | **H-15** | no-research is a visible approval/provenance state, not a silent pass |
| P1-5 code/performance/artifact cannot be collected or graded | P1 | **H-16** | decide in/out of scope; no fake check kind |
| P1-6 flat $0.75 ceiling fails mid-course with no recovery | P1 | **H-17** | plan-sized ceiling + preflight + resumable cost abort |
| P2-7 Japanese-only scaffold triple; no RTL/direction | P2 | **H-18** | locale-aware scaffolds + document direction + non-Japanese fixture |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **H-20** (conditional on H-03) | add real sequencing only if the blueprint puts it in mission |
| P2-10 round-1 review was untracked at audit time | P2 | **H-19** | committed audit index and hashes; correct the stale provenance line |

H-10's report is an audit artifact, not a fix. It explicitly says it changes no product policy. The
round-1 review was committed after H-10's snapshot (`2e3508f`), so H-19 must record "untracked at
audit time; committed in `2e3508f`" rather than repeating a present-tense defect.
`docs/AUDIT-INDEX.md` (H-19) is the register: every report's commit hash, the probe commands and
their results, the evidence class (live / fixture / prepared-pack), and the owning board card for
every finding above.


## Third wave — UX, generic proof, and student mode (2026-11-07)

The two adversarial reviews are committed at `2e57efa`:
`docs/ADVERSARIAL-UX-REVIEW.md` and `docs/GENERIC-HARNESS-REVIEW.md`. They add the following
reviewable cards. The existing cards are not renumbered; `B-1`/`B-2` are finding keys, not new
H-numbers, and they were renamed from two accidental duplicate H-20/H-21 labels created by Atlas.

| key | id | card | owner | parents | branch |
|---|---|---|---|---|---|
| B-1 | `t_673155b0` | Grading lane gap — generated checks store no reference kind | cinder | H-16 | `wt/...` (scratch) |
| B-2 | `t_74d99ca5` | Observation evidence is unreachable — expose recording | cinder | H-16 | scratch |
| H-21 | `t_2a2fc90c` | Implement the CourseBlueprint v2 | cinder | H-13, H-01 | `wt/t_2a2fc90c` |
| H-22 | `t_966d50f4` | Frozen breadth disclosure copy and evidence labels | vellum | H-16 | scratch |
| H-24 | `t_29e6647c` | Rubric registry extensibility decision | atlas | H-16 | `wt/harness-rubric-extensibility` |
| H-25 | `t_5535fc66` | Student syllabus import and alignment — design | atlas | H-03, H-02 | `wt/harness-student-mode-design` |
| H-26 | `t_da9e472c` | Student syllabus import — backend parse/map/companion course | cinder | H-25 | `wt/harness-student-import` |
| H-27 | `t_71ea55ee` | Student syllabus import — learner intake/anchors/alignment UI | vellum | H-25, H-26 | `wt/harness-student-ui` |
| H-28 | `t_271e19e7` | UX humanification — first run, create, import | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` |
| H-29 | `t_70686b14` | UX humanification — lesson index, results, progress | vellum | H-28 | `wt/harness-ux-learning` |
| H-30 | `t_178dc615` | Independent generic-harness acceptance audit | sentinel | H-09 | `wt/harness-generic-audit` |
| H-31 | `t_1c9d0ba6` | Refresh the audit index after merges and reviews | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` |
| H-32 | `t_69873d4c` | Conflict repair — rebase H-07 onto H-13/H-14 | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` |

**H-23 was seeded as a duplicate of B-1 and was closed without code.** Do not recreate it; the
B-1 owner is `t_673155b0`. The board currently has two H-20/H-21 labels from Atlas's earlier
seeding; `B-1` and `B-2` are the authoritative names for those two cards now.

### Current wave — verified status at `master` = `f17ec54` (H-31 refresh)

Card state is the Kanban board; "merged" means the branch tip is an ancestor of `master` at
`f17ec54` (`git merge-base --is-ancestor <tip> f17ec54`). A `done` card with an unmerged branch is
not merged evidence — see `docs/AUDIT-INDEX.md` §0.

| key | id | card | owner | parents | branch | card state | merged |
|---|---|---|---|---|---|---|---|
| B-1 | `t_673155b0` | Grading lane gap — generated checks store no reference kind (H-16 B-1) | cinder | H-16 | — (scratch) | running | — |
| B-2 | `t_74d99ca5` | Observation evidence is unreachable — expose self/parent report (H-16 B-2) | cinder | H-16 | `wt/harness-observation-record` @ `423908f` | running | no |
| H-21 | `t_2a2fc90c` | Implement the CourseBlueprint v2 — plan_units, unit stages, structure | cinder | H-13, H-01 | `wt/t_2a2fc90c` @ `5ba4e4c` | ready | no |
| H-22 | `t_966d50f4` | Frozen breadth disclosure copy and evidence-class labels (H-16 B-3) | vellum | H-16 | `wt/harness-breadth-copy` @ `002a82b` | running | no |
| H-23 | `t_132531da` | Generated checks are ungradable — **closed duplicate of B-1, no code** | cinder | H-16 | — | done (duplicate) | — |
| H-24 | `t_29e6647c` | Rubric registry extensibility — decide the gate for new construct profiles | atlas | H-16 | `wt/harness-rubric-extensibility` (no commits) | running | no |
| H-25 | `t_5535fc66` | Student syllabus import and alignment — design | atlas | H-03, H-02 | `wt/harness-student-mode-design` | ready | no |
| H-26 | `t_da9e472c` | Student syllabus import — backend parse/map/companion course | cinder | H-25 | `wt/harness-student-import` | todo | — |
| H-27 | `t_71ea55ee` | Student syllabus import — learner intake/anchors/alignment UI | vellum | H-25, H-26 | `wt/harness-student-ui` | todo | — |
| H-28 | `t_271e19e7` | UX humanification — first run, create, import | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` | todo | — |
| H-29 | `t_70686b14` | UX humanification — lesson index, results, progress | vellum | H-28 | `wt/harness-ux-learning` | todo | — |
| H-30 | `t_178dc615` | Independent generic-harness acceptance audit | sentinel | H-09 | `wt/harness-generic-audit` | todo | — |
| H-31 | `t_1c9d0ba6` | Refresh the audit index after merges and reviews | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` | running | no |
| H-32 | `t_69873d4c` | Conflict repair — rebase H-07 parent brief onto H-13/H-14 | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` | ready | no |

Merge status of the earlier cards, for the same reason (a done card is not a merge):

| key | id | card state | land commit | merged at `f17ec54` |
|---|---|---|---|---|
| H-12 | `t_dba06898` | done | merge `13480c4` (content `4b5f3b1`); round-2 assertion `903a606` | **yes** |
| H-14 | `t_031e287f` | done | merge `a12176b` (content `0ba4dc6`) | **yes** |
| H-01 | `t_f4f5b26a` | done | merge `b1f2978` (content `8cbaab3`) | **yes** |
| H-02 | `t_867d3b52` | done | merge `1bbd502` (content `5b74233`) | **yes** |
| H-03 | `t_577ed286` | done | merge `54087de` (content `f465a4d`, design doc) | **yes** |
| H-13 | `t_543c0767` | done | merge `6779030` (content `ee976ea`) | **yes** |
| H-04 | `t_161d467f` | done | `cee1749` | no |
| H-05 | `t_7baa29e2` | done | `986190f` | no |
| H-07 | `t_2f3cc647` | done | `8a6bedb` | no |
| H-15 | `t_d519643b` | done | `833e335` | no |
| H-16 | `t_3c5d969c` | done | `dd43d82` | no |
| H-17 | `t_9a8543ae` | done | `722f00f` | no |
| H-19 | `t_ec1d2c15` | done | `99da48a` | no |
| H-20 | `t_43ca17b8` | done | `516d161` | no |
| H-06, H-08, H-18 | — | running | — | — |
| H-09, H-11 | — | todo | — | — |

### What these cards must prove

- **H-24** is a decision, not a runtime rubric generator. It must either show the six profiles
  cover the supported constructs or design a declarative, validated extension gate. No free-text
  rubrics.
- **H-25** is design only. Student mode is a companion course aligned to an uploaded syllabus; the
  syllabus remains the scope authority, is untrusted data, and is stored locally. No LMS scraping,
  grade import, assignment submission, official-enrollment claim or child mode.
- **H-26/H-27** are the backend and UI halves of that design. They must not bypass plan approval or
  create a second course/job engine.
- **H-28/H-29** are copy and composition, not capability. They must keep the M4 contrast/keyboard
  gate and never fake progress, mastery or encouragement that contradicts the verdict.
- **H-30** is an independent audit of H-09. A prepared Japanese pack or a Japanese-only run is a
  failure; the three shapes are one-off, short and full, all non-Japanese.
- **H-31** updates the index; it does not rewrite historical findings.

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
