# HARNESS-NEXT-CARDS — review index

Date: 2026-11-07. Board: `coursebook` (Kanban). Base for the first slice: `origin/master` @
`200e6d3` (M4 series; 1040 tests green before this slice). Base for **this** revision:
`origin/master` @ `f990cad` (`f990cadddeb2c44ed9d5b3b907d28862f452f909`), refreshed by H-31b
(`t_a8e017b5`). The previous revision was H-31 (`t_1c9d0ba6`) at `512c5f6` on base `f17ec54`; it is
merged at `fdecc9e` and this file supersedes its status tables.

Source for the first eleven cards: `docs/ADVERSARIAL-HARNESS-REVIEW.md` (NO-GO as a general
harness; P0-1…P0-7).

This is a **harness-completion** slice, not demo polish. The Japanese demo remains a fixture and
is not proof for any card here. Publication/tag/catalog/announcement remains hard-gated on the
operator's explicit sign-off (`docs/SUBMISSION.md` §0).

## 0. How to read a merge vs a card

Three things in this file are not the same, and the tables below are only useful if you keep them
apart:

- **Card state** (`running`, `todo`, `done`) is board bookkeeping. `done` means a worker stopped and
  reported. It does not mean the branch landed and it does not mean the defect is gone.
- **Merged** means the named commit is an ancestor of `master` at `f990cad`. Check it, never assume
  it: `git merge-base --is-ancestor <commit> f990cad; echo $?`. Every merged cell below was checked
  this way, not read off a card.
- **Re-audited** means an independent pass re-probed the defect against the merged commit. A merged
  implementation is *not* a re-audit. `docs/GENERIC-ACCEPTANCE-AUDIT.md` was run on `498b1da`, before
  blueprint v2 merged, so its P0 findings are **re-audit required** against `f990cad` and H-30b
  `t_9b6742f3` owns that.

A row that cannot name a commit is not evidence. The finding-level register lives in
`docs/AUDIT-INDEX.md`; this file is the board-shaped index.

## Board state at creation

Historical, kept for the record (this was the board on 2026-11-07 before the harness slice):

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
started; the board dispatcher enforces that. The "merged" column is the state at `f990cad`; see
§"Current wave" for the full table and the commit that justifies each cell.

| key | id | card | owner | parents | branch | merged |
|---|---|---|---|---|---|---|
| H-01 | `t_f4f5b26a` | cb.rpc v10 learner capability inputs and plan-job contract | atlas | — | `wt/harness-contract-v10` | **yes** `b1f2978` |
| H-02 | `t_867d3b52` | Learner goal → plan job → plan approval → lessons | vellum | H-01 | `wt/harness-create-flow` | **yes** `1bbd502` |
| H-03 | `t_577ed286` | Design a scope-aware CourseBlueprint before code | atlas | H-01 | `wt/harness-blueprint-design` | **yes** `54087de` |
| H-04 | `t_161d467f` | Research depth and source strategy — make the depth dial real | quill | H-01 | `wt/harness-research-depth` | **yes** `ce95836` |
| H-05 | `t_7baa29e2` | Plan-time media needs and capability declaration | cinder | H-03, H-04 | `wt/harness-media-plan` | **yes** `ce95836` |
| H-06 | `t_7a320d2f` | Procedure authoring path — make the technical lens reachable | cinder | H-05 | `wt/harness-procedure-author` | no (`00b502f`) |
| H-07 | `t_2f3cc647` | Parent brief fidelity — stop storing fields the plan never sees | cinder | H-01 | `wt/harness-parent-brief` | **yes** `ce95836` (content `8a6bedb`) |
| H-08 | `t_901c8310` | General authored export — a normal course can package itself | cinder | H-02, H-03 | `wt/harness-authored-export` | no (`c9c6cec`) |
| H-09 | `t_ebc196db` | Arbitrary-topic end-to-end proof (non-Japanese) | sentinel | H-02…H-08 | `wt/harness-e2e-proof` | no (`111c7e9`) |
| H-10 | `t_1efc158a` | Deep adversarial audit round 2 — trust, pedagogy, scale, breadth | sable | — | `wt/harness-adversarial-2` | **yes** `7af3bbd` |
| H-11 | `t_6f41e0b0` | Truth pass — docs/status after the harness slice | quill | H-09 | `wt/harness-docs` | no (`b2233ac`) |
| H-12 | `t_dba06898` | Fail-closed plan approval — empty, rejected, or edited plans cannot approve | cinder | — (hotfix) | `wt/harness-plan-approval` | **yes** `13480c4` |
| H-13 | `t_543c0767` | Thread level, subject_domain and scope into the plan runtime | atlas | H-01 | `wt/harness-policy-threading` | **yes** `6779030` |
| H-14 | `t_031e287f` | Source-trust boundary and claim-level provenance lint | sable | H-10 | `wt/harness-source-trust` | **yes** `a12176b` |
| H-15 | `t_d519643b` | Validator independence and the no-research factual waiver | atlas | H-10 | `wt/harness-validator-independence` | **no** — `833e335`, integration blocked (H-36) |
| H-16 | `t_3c5d969c` | Assessment construct breadth decision (code/performance/artifact) | atlas | H-03 | `wt/harness-assessment-breadth` | **yes** `fa316c5` (content `dd43d82`) |
| H-17 | `t_9a8543ae` | Sized cost ceilings and CostCeilingExceeded recovery | cinder | H-10 | `wt/harness-cost-ceilings` | **yes** `ce95836` (content `722f00f`) |
| H-18 | `t_8407ea22` | Locale-aware scaffolds, direction/RTL, non-Japanese fixture | cinder | H-13 | `wt/harness-locale-scaffolds` | no (`2aca201`) |
| H-19 | `t_ec1d2c15` | Audit evidence index and reproducible provenance | quill | H-10 | `wt/harness-audit-index` | **yes** `ce95836` (content `99da48a`) |
| H-20 | `t_43ca17b8` | Prerequisite edges — frozen contract, then conditional implementation | atlas | H-03 | `wt/harness-prereq-edges` | **yes** `d079b4c` (contract `516d161`); implementation `2252231` |

H-12 is a root card because the defect was live on the master of the time and did not need the
contract work. It touches plan approval, not the course-create fields.

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
  refuse; edits/replans invalidate; no transition/revision on refusal.
- **H-13**: runtime threading of `level`, `subject_domain`, `scope`; fingerprint includes them;
  locale ≠ subject domain; Spanish technical schematic and Japanese math protection; tests at the
  generation/domain boundary.

## Deeper adversarial findings found while seeding (2026-11-07)

These are beyond the first review. They are why H-12 exists now. **Status is not kept here** — it
lives in `docs/AUDIT-INDEX.md` §6, so the two files cannot drift apart. At `f990cad`: D-01, D-02,
D-02b, D-03 are FIXED; D-04 is OPEN and narrowed (sequencing merged, no dynamic re-plan); D-05 is
OPEN with H-15 unmerged and H-36 the recovery card; D-06 is OPEN with H-11 `done` but unmerged.

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

`coursebook/domain.py:plan_approve` checked only the recomputed kernel plan hash and the plan row
state. The generation digest in `gen_plan_documents.plan_hash` and the kernel digest in
`parent_authoring/domain.plan_hash` are different functions; the fix binds validation to the exact
kernel content hash rather than comparing the two hashes. H-12 fixed it (`13480c4`).

### D-02 (P0, test-quality) — the green suite encodes the defect

`tests/test_kernel_commands.py` approved an empty plan in
`test_approval_bumps_revision_and_writes_one_transition` and again in
`test_replan_unknown_objective_is_not_found`; the fixture helper `approve()` is used by many tests
with a seeded objective, but the empty-path approvals were asserted as success. A 1040-test green
run therefore could not be used as evidence that validation gates approval. H-12 changed those
tests; `903a606` asserts the refusal in the round-2 suite.

### D-02b (P0, API) — two plan digests, one approval

`run_plan_job` stores `generation.plan_hash(document)` in `plans.plan_hash` and
`gen_plan_documents.plan_hash`; `course.outline` returns that generation digest as
`plan.plan_hash`. `plan.approve` recomputes `parent_authoring.plan_hash(connection, plan)` — the
kernel digest — and requires that value. The Parent Studio path worked around this by reading
`parent.blueprint.read.plan.plan_hash`; the learner `CreateCourseFlow` path had no documented
equivalent.

H-12 adds a durable validation binding and a learner-safe approval-hash projection; H-02 uses it.
This is not a reason to compare the two digests directly — both are real and serve different
consumers.

### D-03 (P1) — the plan job drops the inputs the contract collects

`run_plan_job` read `goal`, `recipe`, `dials`, `locale` only, so the new `level`, `subject_domain`
and `scope` fields would have been ignored and the reuse fingerprint could reuse a plan across a
changed subject/level/scope. H-13 fixed threading; H-04 needs the scope value for a real full-course
budget and now has it.

### D-04 (P1) — the "adaptation" claim is a state transition

`review.py` is a real, honest scheduling heuristic, but the learner loop has no dynamic re-plan, no
choice among remediation/examples/next objective, and no attempt-driven content change. The only
adaptations are evidence-state transitions (`needs_review`, `review_due`) and a fixed ladder.
H-20's frozen contract and H-21c's implementation now give the loop real prerequisite edges and
unit gating; that narrows the finding but does not close it. Do not market the heuristic as
adaptive teaching.

### D-05 (P1) — validation independence is structural only

`assert_separate_pass` guarantees a different prompt and schema, not a different model or an
external check; the generator and validator are the same host model. `validation_verdict` trusts
the validator's `criteria` and `claim_verdicts`. H-15 measured this and built the guard at
`833e335`; the branch is not on master and conflicts in five files with the blueprint/checklist
lines. H-36 is the integration-recovery card. Until it lands, independence is structural only.

### D-06 (P2, docs) — stale defect claims survive in the README

`README.md` still lists `CB-QA-10` (answer key in `evidence.inspect` L2) as open, while
`coursebook/evidence.py` now projects only `PUBLIC_CRITERION_FIELDS` and
`tests/test_review_evidence.py` asserts `check_spec` is absent. H-11 delivered the truth pass at
`b2233ac`; it is not merged. This is a truth pass, not a code change.

## Second wave — what the round-2 audit added

H-10 (`docs/ADVERSARIAL-AUDIT-ROUND2.md`, 14 deterministic probes) found the next class of
failures. The report proposed its own H-11…H-18 labels; the board keys below are authoritative and
avoid those collisions:

| finding | severity | card | what it changes | merged at `f990cad` |
|---|---|---|---|---|
| P0-1 rejected plan is an approvable draft | P0 | **H-12** | validation binds approval; empty/rejected/edited plans fail closed | **yes** `13480c4` |
| P0-2 fetched excerpt is raw prompt content; invented prose URLs pass | P0 | **H-14** | untrusted-data envelope + claim-level provenance lint | **yes** `a12176b` |
| P1-3 same model writes and validates; support self-upgrades | P1 | **H-15** | record/compare validator identity, cross-model path, no self-upgrade | **no** — H-36 recovery |
| P1-4 factual gate waives when research is unavailable | P1 | **H-15** | no-research is a visible approval/provenance state, not a silent pass | **no** — H-36 recovery |
| P1-5 code/performance/artifact cannot be collected or graded | P1 | **H-16** → B-1/B-2/B-3 | decide in/out of scope; no fake check kind | decision + B-1 yes; B-2/B-3 no |
| P1-6 flat $0.75 ceiling fails mid-course with no recovery | P1 | **H-17** | plan-sized ceiling + preflight + resumable cost abort | **yes** `ce95836` |
| P2-7 Japanese-only scaffold triple; no RTL/direction | P2 | **H-18** | locale-aware scaffolds + document direction + non-Japanese fixture | **no** (`2aca201`) |
| P2-8 no prerequisite edges; adaptation is a state label | P2 | **H-20** | add real sequencing only if the blueprint puts it in mission | **yes** `2252231` |
| P2-10 round-1 review was untracked at audit time | P2 | **H-19** | committed audit index and hashes; correct the stale provenance line | **yes** `ce95836` |

H-10's report is an audit artifact, not a fix. It explicitly says it changes no product policy. The
round-1 review was committed after H-10's snapshot (`2e3508f`), so H-19 records "untracked at audit
time; committed in `2e3508f`" rather than repeating a present-tense defect.
`docs/AUDIT-INDEX.md` (H-19) is the register: every report's commit hash, the probe commands and
their results, the evidence class (live / fixture / prepared-pack), and the owning board card for
every finding above.

## Third wave — UX, generic proof, student mode, and the blueprint implementation (2026-11-07)

The two adversarial reviews are committed at `2e57efa`:
`docs/ADVERSARIAL-UX-REVIEW.md` and `docs/GENERIC-HARNESS-REVIEW.md`. They added the following
reviewable cards. Existing cards are not renumbered; `B-1`/`B-2` are finding keys, not new
H-numbers, and they were renamed from two accidental duplicate H-20/H-21 labels created by Atlas.

| key | id | card | owner | parents | branch |
|---|---|---|---|---|---|
| B-1 | `t_673155b0` | Grading lane gap — generated checks store no reference kind | cinder | H-16 | `wt/harness-grading-lanes` |
| B-2 | `t_74d99ca5` | Observation evidence is unreachable — expose recording | cinder | H-16 | `wt/harness-observation-record` |
| H-21 | `t_2a2fc90c` | Implement the CourseBlueprint v2 (original card, split) | cinder | H-13, H-01 | `wt/t_2a2fc90c` |
| H-21a | `t_27867486` | cb.rpc v11 + cb.db v7 plan_units contract and migration | cinder | H-21 | `wt/h21a-contract-migration` |
| H-21b | `t_fb8b9622` | Plan schema v2 + unit-scoped plan/lesson stages | cinder | H-21a | `wt/h21b-unit-stages` |
| H-21c | `t_6576b611` | Prerequisite gating R1–R9, §14.4 tests, measured ceiling | cinder | H-21b | `wt/h21c-prereq-gating` |
| H-22 | `t_966d50f4` | Frozen breadth disclosure copy and evidence labels | vellum | H-16 | `wt/harness-breadth-copy` |
| H-24 | `t_29e6647c` | Rubric registry extensibility decision | atlas | H-16 | `wt/harness-rubric-extensibility` |
| H-25 | `t_5535fc66` | Student syllabus import and alignment — design | atlas | H-03, H-02 | `wt/harness-student-mode-design` |
| H-26 | `t_da9e472c` | Student syllabus import — backend parse/map/companion course (timed out; superseded) | cinder | H-25 | `wt/harness-student-import` |
| H-26a | `t_faad26cf` | Finish the salvaged H-26 syllabus intake WIP on blueprint v11 | cinder | H-26, H-25 | `wt/harness-student-import` |
| H-27 | `t_71ea55ee` | Student syllabus import — learner intake/anchors/alignment UI | vellum | H-25, H-26a | `wt/harness-student-ui` |
| H-28 | `t_271e19e7` | UX humanification — first run, create, import | vellum | H-02, H-22, H-21 | `wt/harness-ux-first-run` |
| H-29 | `t_70686b14` | UX humanification — lesson index, results, progress | vellum | H-28 | `wt/harness-ux-learning` |
| H-30 | `t_178dc615` | Independent generic-harness acceptance audit (on `498b1da`) | sentinel | H-09 | `wt/harness-generic-audit` |
| H-30b | `t_9b6742f3` | Re-audit the generic harness after blueprint v2 | sentinel | H-30, H-21c | `wt/harness-generic-audit` |
| H-31 | `t_1c9d0ba6` | Refresh the audit index after merges and reviews | quill | H-12, H-14, H-02, H-03 | `wt/harness-audit-refresh` |
| H-31b | `t_a8e017b5` | Refresh the audit index after H-21/H-35/H-25 merges | quill | H-31, H-21c, H-35 | `wt/harness-audit-refresh-2` |
| H-32 | `t_69873d4c` | Conflict repair — rebase H-07 onto H-13/H-14 | cinder | H-07, H-13, H-14 | `wt/harness-parent-brief-rebase` |
| H-32b | `t_71f53265` | Port the parent-brief × H-13 × H-14 regression onto master | cinder | H-32 | `wt/h32-parent-brief-regression` |
| H-33 | `t_6aafc7f2` | Checklist confirmation — frozen decision | atlas | H-20 | `wt/harness-checklist-confirmation` |
| H-34 | `t_82c24349` | Checklist confirmation lane — item ids graded `self_reported` | cinder | H-33 | `wt/harness-checklist-ui` |
| H-35 | `t_65e7d83a` | Checklist confirmation surface — checkboxes, selection payload | vellum | H-34 | `wt/harness-checklist-ui` |
| H-35b | `t_db0b76f8` | Live checklist DOM capture on a fresh rig | vellum | H-35 | — (evidence only) |
| H-36 | `t_48645f63` | Integrate H-15 validator independence onto blueprint v11 + checklist | atlas | H-15, H-21c, H-35 | `wt/harness-validator-integration` |

**H-23 was seeded as a duplicate of B-1 and was closed without code.** Do not recreate it; the
B-1 owner is `t_673155b0`.

**H-21 was split, not duplicated.** The original card `t_2a2fc90c` is closed with
"superseded by H-21a `t_27867486` (`8eb83d8`), H-21b `t_fb8b9622` (`7f46e17`), H-21c `t_6576b611`
(`bcd545e`)". Its own branch tip `5ba4e4c` is history and must not be cited as merged. The three
slices merged together at `2252231`.

**H-26 is not implemented.** The original card timed out after 150 iterations; the WIP was salvaged
and committed at `2d7ecde` (27 syllabus tests OK in the worktree) and the card was closed as
*superseded*. H-26a `t_faad26cf` owns the continuation: rebase/renumber the salvage onto cb.rpc v11
(the salvage describes a v12), finish parse → map → companion course, and run the full suite. Any
statement that student import "shipped" because H-26 is `done` is wrong.

### Current wave — verified status at `master` = `f990cad`

Card state is the Kanban board read at the start of H-31b. "Merged" means the named commit is an
ancestor of `f990cad` (`git merge-base --is-ancestor <commit> f990cad`), checked file by file. A
`done` card with an unmerged branch is not merged evidence — see §0.

| key | id | card | card state | branch tip | merged at `f990cad` | commit that lands it |
|---|---|---|---|---|---|---|
| B-1 | `t_673155b0` | Grading lane gap — generated checks store no reference kind | done | `ce6c8c1` | **yes** | `3368c96` → `4e709d3` |
| B-2 | `t_74d99ca5` | Observation evidence is unreachable — expose self/parent report | done | `423908f` | no | — (its cb.rpc v12 is not on master) |
| H-21 | `t_2a2fc90c` | CourseBlueprint v2 (original card) | done, **superseded** | `5ba4e4c` | no | split into H-21a/b/c |
| H-21a | `t_27867486` | cb.rpc v11 + cb.db v7 contract and migration | done | `8eb83d8` | **yes** | `2252231` |
| H-21b | `t_fb8b9622` | Plan schema v2 + unit-scoped stages | done | `7f46e17` | **yes** | `2252231` |
| H-21c | `t_6576b611` | Prerequisite gating R1–R9 + measured ceiling | done | `bcd545e` | **yes** | `2252231` |
| H-22 | `t_966d50f4` | Frozen breadth disclosure copy and labels (B-3) | done | `47e152c` | no | — |
| H-23 | `t_132531da` | Generated checks are ungradable — closed duplicate of B-1 | done (duplicate) | — | — | no code |
| H-24 | `t_29e6647c` | Rubric registry extensibility decision | done | `491443a` | **yes** | `4f42c3c` |
| H-25 | `t_5535fc66` | Student syllabus import and alignment — design | done | `3705a7a` | **yes** | `e978441` |
| H-26 | `t_da9e472c` | Student import backend (original) | done, **superseded** | `2d7ecde` (salvage) | no | H-26a owns it |
| H-26a | `t_faad26cf` | Finish the salvaged syllabus intake on blueprint v11 | running | — | no | — |
| H-27 | `t_71ea55ee` | Student import — learner intake/alignment UI | running | — | no | — |
| H-28 | `t_271e19e7` | UX humanification — first run, create, import | running | — | no | — |
| H-29 | `t_70686b14` | UX humanification — lesson index, results, progress | todo | — | no | — |
| H-30 | `t_178dc615` | Independent generic-harness acceptance audit (**of `498b1da`**) | done | `ddc71fc` | **yes** (audit doc only) | `090e755` |
| H-30b | `t_9b6742f3` | Re-audit the generic harness after blueprint v2 | running | — | no | — |
| H-31 | `t_1c9d0ba6` | Refresh the audit index after merges and reviews | done | `512c5f6` | **yes** | `fdecc9e` |
| H-31b | `t_a8e017b5` | This refresh | running | — | no (this card) | — |
| H-32 | `t_69873d4c` | Conflict repair — rebase H-07 onto H-13/H-14 | done | `bc508ce` | no (its tip) | union landed as `afac32c` |
| H-32b | `t_71f53265` | Port the conflict regression onto master | done | `8d018e4` | **yes** | `c7461fc` |
| H-33 | `t_6aafc7f2` | Checklist confirmation — frozen decision | done | `da53ec1` | **yes** | `3d46988` → `4e709d3` |
| H-34 | `t_82c24349` | Checklist confirmation lane (kernel) | done | `78c6019` | **yes** | `4e709d3` |
| H-35 | `t_65e7d83a` | Checklist confirmation surface | done | `a498969` | **yes** | `4e709d3` |
| H-35b | `t_db0b76f8` | Live checklist DOM capture on a fresh rig | running | — | no | — |
| H-36 | `t_48645f63` | Integrate H-15 onto blueprint v11 + checklist | running | — | no | — |

Merge status of the earlier cards, for the same reason (a done card is not a merge):

| key | id | card state | land commit | merged at `f990cad` |
|---|---|---|---|---|
| H-12 | `t_dba06898` | done | merge `13480c4` (content `4b5f3b1`); round-2 assertion `903a606` | **yes** |
| H-14 | `t_031e287f` | done | merge `a12176b` (content `0ba4dc6`) | **yes** |
| H-01 | `t_f4f5b26a` | done | merge `b1f2978` (content `8cbaab3`) | **yes** |
| H-02 | `t_867d3b52` | done | merge `1bbd502` (content `5b74233`) | **yes** |
| H-03 | `t_577ed286` | done | merge `54087de` (content `f465a4d`, design doc) | **yes** |
| H-13 | `t_543c0767` | done | merge `6779030` (content `ee976ea`) | **yes** |
| H-04 | `t_161d467f` | done | content `cee1749`, merged at `341cc18` inside `ce95836` | **yes** |
| H-05 | `t_7baa29e2` | done | content `986190f`, merged at `a30487e` inside `ce95836` | **yes** |
| H-07 | `t_2f3cc647` | done | content `8a6bedb`, merged at `afac32c` inside `ce95836`; regression `8d018e4` | **yes** |
| H-16 | `t_3c5d969c` | done | `dd43d82`, merged at `fa316c5` | **yes** |
| H-17 | `t_9a8543ae` | done | `722f00f`, merged at `4dd68cb` inside `ce95836` (+ `fbf96fe` v10 brief fix) | **yes** |
| H-19 | `t_ec1d2c15` | done | `99da48a`, merged inside `ce95836` | **yes** |
| H-20 | `t_43ca17b8` | done | contract `516d161` at `d079b4c`; implementation `bcd545e` at `2252231` | **yes** |
| H-06 | `t_7a320d2f` | done | `00b502f` | no |
| H-08 | `t_901c8310` | done | `c9c6cec` | no |
| H-09 | `t_ebc196db` | done | `111c7e9` | no |
| H-11 | `t_6f41e0b0` | done | `b2233ac` | no |
| H-15 | `t_d519643b` | done | `833e335` | no — blocked, H-36 |
| H-18 | `t_8407ea22` | done | `2aca201` | no |

### What these cards must prove

- **H-21a/b/c** — merged. `cb.rpc` v11 and `cb.db` v7 are additive (`contracts/rpc.v11.json`,
  `contracts/db.v7.json`), the migration is `coursebook/migrations/0007_plan_units.sql`,
  `PLAN_SCHEMA_V2` is `coursebook.plan.v2` with `objectives` `minItems: 1` / `maxItems: 40` and
  `units` `minItems: 1` / `maxItems: 12`, and the §14.4 tests are
  `tests/test_prerequisite_gating.py`. The measured ceiling is `docs/PLAN-CEILING.md`. What the
  merged code has **not** had is an independent re-run: H-30b does that.
- **B-1 / H-20** — merged. `docs/GRADING-LANES.md` plus `tests/test_grading_lanes.py` (15 tests).
  Its own card states explicitly: no `cb.rpc` bump, no migration, no new check kind. The fix is a
  lane declaration on every stored check, not a new contract.
- **H-33/H-34/H-35** — merged. `docs/CHECKLIST-CONFIRMATION.md` is the frozen decision;
  `tests/test_checklist_confirmation.py` (12 tests) is the kernel; `a498969` is the surface. The
  live DOM capture is **not** done — H-35b is a separate evidence card, and no test count here
  substitutes for it.
- **H-24** is a decision, not a runtime rubric generator. `docs/RUBRIC-EXTENSIBILITY.md` must show
  either that the six profiles cover the supported constructs or a declarative, validated extension
  gate. No free-text rubrics.
- **H-25** is design only. Student mode is a companion course aligned to an uploaded syllabus; the
  syllabus remains the scope authority, is untrusted data, and is stored locally. No LMS scraping,
  grade import, assignment submission, official-enrollment claim or child mode. `docs/STUDENT-MODE.md`
  is on master; nothing in it is implemented.
- **H-26a/H-27** are the backend and UI halves of that design. They must not bypass plan approval,
  create a second course/job engine, or silently renumber the contract past v11 without saying so.
- **H-28/H-29** are copy and composition, not capability. They must keep the M4 contrast/keyboard
  gate and never fake progress, mastery or encouragement that contradicts the verdict.
- **H-30** is an independent audit of H-09 and it is done — but on `498b1da`. Its verdict is a
  snapshot of a tree that is now three merges old. **H-30b** re-audits single/short/full against
  `f990cad`; its result, not H-30's, is the current claim.
- **H-31/H-31b** update the index; they do not rewrite findings.
- **H-35b** is evidence only. It may not change product code, and if it cannot produce a live
  capture it must say so rather than infer one from fixtures.
- **H-36** is integration recovery for H-15. It resolves the five conflicted files as a semantic
  union (validator identity + blueprint plan path + checklist/grading lanes + H-14 envelope), keeps
  both sides' tests, and must not force a green tree that drops validator independence.

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
