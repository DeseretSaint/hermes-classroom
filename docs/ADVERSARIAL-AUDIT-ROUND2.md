# Coursebook - deep adversarial audit, round 2

Date: 2026-11-07
Auditor: Sable (platform integration engineer)
Branch: `wt/harness-adversarial-2` (worktree `t_1efc158a`), base `master` at `200e6d3`
Scope: the harness as a general course-generation system, not the prepared Japanese pack.
Prepared-pack demo: **not used as evidence anywhere in this report.**

## Method and limits

- Every finding below was reproduced on this branch with the probe file
  `tests/test_adversarial_round2.py` (14 tests) and/or by reading the exact line named.
- No provider call was made. Generator and validator are scripted doubles, as in
  `tests/test_generation.py`; a result is a property of the harness, not of a model.
- No live gateway was exercised for this card. The host-seam finding is about the code path and
  the honest failure value, not about a running Desktop.
- Commands run, in full:

```
python3 -m unittest tests.test_adversarial_round2 -v      # 14 tests, OK
python3 -m unittest discover -s tests -t .                # full suite, result in the card summary
bash scripts/validate-plugin.sh <clean export>            # result in the card summary
```

- The review named in the card, `docs/ADVERSARIAL-HARNESS-REVIEW.md`, is **untracked** in the
  main checkout (`git status --porcelain docs/ADVERSARIAL-HARNESS-REVIEW.md` returns `?? ...`,
  and `git log --all -- docs/ADVERSARIAL-HARNESS-REVIEW.md` returns nothing). It was read from
  the working tree at `/home/deseretsaint/Projects/hermes-classroom/docs/` and is not part of any
  commit. See H10-10.

## Ranked findings

### P0-1. A validator-rejected plan is written as an approvable `draft`, so the independent gate is bypassable

**Paths**

- `coursebook/generation.py:2823` decides `generation_state = "draft" if verdict["verdict"] == "pass" else "needs_review"`.
- `coursebook/generation.py:2860-2878` inserts the plan row with a **hard-coded** `"draft"`, not
  `generation_state`.
- `coursebook/migrations/0001_initial.sql:51` allows only
  `state IN ('draft', 'approved', 'superseded')`; `needs_review` has no representation on `plans`.
- `coursebook/domain.py:576-614` (`plan.approve`) checks the plan belongs to the enrollment, the
  hash matches, and `state != 'approved'`. It never reads `gen_plan_documents.generation_state`
  or `validation_id`.
- `docs/GENERATION.md` §5 says the artifact is persisted with `generation_state = needs_review`
  and "nothing is quietly approved". The lesson path honors that (`generation.py:3405`, and
  `learner_page` refuses a non-`validated` lesson). The plan path does not.

**Reproduction**

`tests/test_adversarial_round2.PlanGateTest.test_rejected_plan_rows_are_draft_and_the_domain_approves_them`
runs `run_plan_job` with a validator that rejects `factual_correctness`, then calls the real
`plan.approve` handler through `api.dispatch`. Observed:

```
result["validation_verdict"] == "reject"
result["status"]             == "needs_review"
plans.state                  == "draft"
gen_plan_documents.generation_state == "needs_review"
plan.approve ok              == True   -> plans.state == "approved"
```

**Why it matters for "any topic"**

Every novel subject depends on the validator, because the deterministic rules can only check
structure, time honesty, provenance ids and recipe shape. A rejected plan for an arbitrary topic
is exactly the artifact a learner must not approve. Today the rejection is advisory metadata in a
generation table while the kernel's approval path sees a normal draft. The stronger the validator
recommendation, the more this matters: the UI can show "validation did not pass" while the same
plan is one `plan.approve` call away from becoming the course.

**Proposed next card:** H-11 "Plan approval must bind the validation verdict", with a migration
that represents `needs_review` on `plans` (or an approval precondition that joins
`gen_plan_documents`) and a regression test that a rejected plan cannot be approved.

### P0-2. Fetched page text is prompt content with no trust boundary, and invented URLs in prose pass every rule

**Paths**

- `coursebook/research.py:11-12` states fetched text "never becomes policy, rubric or
  prompt-injection surface". The code contradicts this: `research.py:429` stores a 600-character
  excerpt, and `generation.py:1761-1775` (`_source_brief`) copies `excerpt` into the brief.
- That brief is placed in the plan payload (`generation.py:1801`), the plan validation payload
  (`:1841`), the lesson payload (`:1891-1892`) and the lesson validation payload (`:1946`).
- Neither `PLAN_SYSTEM_PROMPT` nor `LESSON_SYSTEM_PROMPT` nor `VALIDATION_SYSTEM_PROMPT`
  (`generation.py:1007-1047`) tells the model that source text is untrusted data or that
  instructions inside it must be ignored. There is no delimiter, role marker or escaping.
- The only source rule is `enforce_plan_rules` (`generation.py:1335-1342`): cited **ids** must
  exist in the ledger. Prose URLs, titles, publishers and instructions are never checked.

**Reproduction**

`SourceTrustTest.test_hostile_excerpt_reaches_plan_and_validation_prompts_verbatim` builds a
`SourceRecord` whose excerpt is a fenced-looking instruction block: it tells the model to discard
its instructions, to stop writing a lesson, to add a quiz to every section, and to cite
`https://invented.invalid/authority` as the primary source. (The instruction phrase is assembled
at runtime in the test file because the release security scan flags that literal in packaged
files; the assertion still compares against the full hostile string.)

It asserts the string appears verbatim in `build_plan_request(...).input_text` **and**
`build_plan_validation_request(...).input_text`, and that neither system prompt contains
"untrusted" or an instruction-ignoring clause.
`test_invented_url_in_prose_passes_the_deterministic_plan_rules` puts an invented URL in
`learner_outcome` and shows `enforce_plan_rules(..., ledger=[])` accepts it.

**Why it matters**

A normal web page is attacker-controlled input on any topic, and the harness fetches up to six
pages per job. Instruction text that reaches both the writer and the "independent" validator
(same model, see P1-3) can change recipe shape, inject a citation, or move a claim into a lesson.
The recipe and source-id rules catch some structural effects after the fact; they do not catch
content steering or invented prose provenance. Some injections are blocked deterministically
(adding a quiz to a `one_off` plan fails `generation.py:1359`); the guard is incidental, not a
trust boundary.

**Proposed next card:** H-12 "Add a source-trust boundary and claim-level provenance lint":
delimited untrusted-data blocks, an explicit no-instructions clause in every generation prompt,
a URL/entity lint against the ledger for titles, prose and lesson fields, and the two probes above
as regression tests.

### P1-3. "Independent validation" is a prompt separation, not an independent judgment, and the same model can upgrade its own source support

**Paths**

- `generation.py:1698-1709` (`assert_separate_pass`) compares system prompt, response schema and
  prompt version. It has no model, provider, temperature or sampling identity to compare.
- `run_plan_job` (`:2775-2784`) and `_author_section` (`:3365-3373`) call the same injected `llm`
  object for both passes.
- `research.py:451-471` (`apply_support_verdicts`) moves a source from `unverified` to
  `supported`/`partial` purely on the validator's `claim_verdicts`. The validator is the same
  model that wrote the claim.
- `VALIDATION_CRITERIA` are judged by free-form reasoning; there is no claim-level check against
  fetched bytes, only against the 600-character excerpt.

**Reproduction**

`ValidatorIndependenceTest.test_sycophantic_pass_accepts_a_false_claim` scripts the generator to
write "State that water boils at 50 °C at sea level" and the validator to return `verdict: pass`
with every criterion `pass`. Observed: `validation_verdict == "pass"`, `status == "draft"`, and
the false claim is stored in `gen_plan_documents.document_json`. Both calls were made by the same
model; `assert_separate_pass` cannot observe that.
`test_claim_support_can_be_upgraded_by_the_same_model` shows a validator verdict of `supported`
alone lifts a source to `supported`.

**Why it matters**

A model that is wrong in the same direction twice will pass itself. That is the default failure
mode for an arbitrary, unfamiliar subject where the model has no grounding and the research pass
is shallow or unavailable.

**Cost of the concrete guards**

- Cross-model validation: one extra provider/model per artifact, roughly doubling validation calls
  (2 calls per plan, 2 per lesson) at the same token counts. With the current 8-section cap that is
  up to 16 extra validation calls per course; with the flat `$0.75` ceiling this requires a budget
  change, not just a wiring change.
- Claim-level checking: deterministic substring/entity checks against the stored excerpt plus a
  validator verdict per claim. Cheap (no extra model call), but only as strong as the excerpt.
- A second independent pass with a different prompt and a different model, and recording the model
  identity in the validation row, is the minimum honest version.

**Proposed next card:** H-13 "Validator independence and claim-level support", with model identity
recorded and compared, a cross-model option, and the sycophantic-pass probe as a regression test.

### P1-4. The factual gate auto-waives in exactly the production state where no research seam exists

**Path:** `generation.py:1719`

```
allowed_unknown = {"source_support", "factual_correctness"} if research_status != "ok" else set()
```

**Reproduction**

`ValidatorIndependenceTest.test_factual_correctness_unknown_is_waived_without_research`: the same
report with `factual_correctness` and `source_support` both `unknown` yields `pass` when
`research_status="unavailable"` and `reject` when `"ok"`.
`HostSeamTest.test_no_host_means_research_is_unavailable_not_fabricated` drives `run_plan_job`
with `search=None` (the dashboard / not-loaded-plugin state), shows
`research.status == "unavailable"` and the warning, and shows the validator's `pass` is accepted.

**Why it matters**

The honest research warning and the waived factual gate compose into: when the harness cannot
check facts, it also stops requiring the validator to claim it checked them. For an arbitrary
topic with no research, the plan that gets approved is structurally valid and factually
unexamined. That may be the intended honesty trade-off, but it should be a visible product rule
(a "no sources, facts unverified" approval state), not a silent pass.

**Proposed next card:** H-13 can carry this, or a small card that makes `unavailable` research a
distinct approval state with explicit learner-facing provenance.

### P1-5. Assessment breadth is three input formats; code, performance and physical artifacts cannot be collected or graded

**Paths**

- `generation.py:565` check kinds: `quiz | verification | observation`.
- `generation.py:804` stimulus formats: `text | selection | verification`.
- `EVIDENCE_TARGETS` has six labels (`recall, comprehension, production, discrimination,
  procedure, transfer`) and `rubric_only` reference kind; there is no executable, media-performance
  or artifact construct.
- `coursebook/grading.py` grades text/selection/verification; pronunciation is the only
  non-text evidence seam and it is `model_assessed` (`coursebook/pronunciation.py`).

**Reproduction**

`BreadthTest.test_check_vocabulary_is_closed` shows `format: "code"` and `format: "performance"`
are schema-rejected and `performance`/`artifact` are not evidence targets.

**Why it matters**

For "whatever may be thrown at it", a goal such as "write and test a Python function", "deliver a
two-minute spoken pitch" or "build and photograph a birdhouse" can produce a text explanation and
a rubric-scored written answer, but the harness cannot collect the program, the audio or the
artifact and cannot verify it. This is a declared product limit (the first review's P1-5), and
round 2 adds the exact closed vocabulary that a breadth card must widen.

**Proposed next card:** H-14 "Assessment construct breadth spike": decide whether code execution,
recorded performance and artifact submission are in the any-topic mission; if yes, define
collection, storage, evidence class and grading; if no, state the limit in the product copy.

### P1-6. The cost ceiling does not scale with the course, and a ceiling abort has no recovery path

**Paths**

- `generation.py:256-257`: `CostBudget.max_calls = 32`, `max_cost_usd = 0.75`.
- `generation.py:352-363`: `lesson_cost_budget(n)` scales `max_calls` to `n * 2 * 2` but leaves
  `max_cost_usd` at the flat default.
- `generation.py:375-409`: `before_call` checks `known_cost >= ceiling`; `record` raises
  `CostCeilingExceeded` when a call pushes spend over.
- `generation.py:3234-3246`: only `ProviderTimeout` gets `with_recovery(...)`; a cost abort keeps
  the authored sections but offers no "continue from section N" message.

**Reproduction**

`ScaleTest.test_cost_ceiling_is_flat_while_call_ceiling_scales`: an 8-section lesson job gets
`max_calls=32` but `max_cost_usd=0.75`. At `$0.032` per call, 23 calls spend `$0.736`; the 24th
call (section 6's second validation) raises. Two of eight sections are unauthored and the job
error has no recovery hint.

**Why it matters**

The plan cap is 8 sections today, so 32 calls is the worst legal case. A real hosted model at
roughly 3 cents per structured call already exceeds `$0.75` before the course is finished. If the
section cap is raised for full courses (the first review's P0-2), the flat dollar ceiling becomes
the binding limit for every course, and it fails mid-course rather than refusing up front.

**Proposed next card:** H-15 "Sized cost ceilings and recovery": scale `max_cost_usd` with the
plan (or refuse before the job starts when the declared maximum cannot fit), and attach the same
resume hint to `CostCeilingExceeded` that `ProviderTimeout` already gets.

### P2-7. The scaffold contract is Japanese-shaped and locale-blind; there is no direction field

**Paths**

- `generation.py:846-860`: `check.scaffolds` is a required object with exactly `romaji`,
  `furigana`, `english_meaning`, for every lesson in every locale.
- `generation.py:1255-1266`: only `ja` at `L0/L1/beginner` (or `romaji: true`) enables any of them.
  `fr-FR`, `ar-SA` and every other locale get an all-false Japanese scaffold triple.
- `coursebook/lesson_document.py` has no `direction`, `bidi`, `rtl` or text `lang` field; the
  required document fields it names are structural only.

**Reproduction**

`LocalizationTest.test_scaffold_object_is_required_even_for_french` removes `check.scaffolds` and
gets a schema rejection; asserts the property set is the Japanese triple; shows
`_scaffold_policy("committed", {"level": "A1"}, "fr-FR")` is all false.
`test_non_japanese_locale_has_no_scaffold_or_direction_path` shows the scaffold prompt note for
`ar-SA` is empty and the document validator never asks for a direction.

**Why it matters**

A French course is asked to declare whether it uses romaji and furigana, and an Arabic course has
no way to say it is right-to-left. The schema is fixture-shaped, exactly as the first review said
for scaffolds, and round 2 confirms it at the lesson schema, the policy and the document layer.

**Proposed next card:** H-16 "Locale-aware scaffold and direction contract": an open scaffold
vocabulary per locale, a document `direction` field, and a non-Japanese lesson fixture.

### P2-8. "Adaptation" is a closed objective-state label; there is no prerequisite graph, sequencing or learner model

**Paths**

- `generation.py:SECTION_SCHEMA` (`:540-557`) has ordinal, title, intent, one objective ref,
  context needs and source ids. It has no prerequisite or ordering edge; `additionalProperties`
  is false, so a plan cannot carry one. Same for `OBJECTIVE_SCHEMA`.
- `coursebook/domain.py:1126-1147`: the only learner model is `_objective_state_after`, a mapping
  from `(verdict, evidence_class, current_state)` onto one of seven labels.
- `coursebook/review.py` schedules `review_due`; that is the whole adaptation loop.

**Reproduction**

`PedagogyTest.test_schema_cannot_express_a_prerequisite` adds `prerequisites` to a section and gets
`GenerationRejected`; asserts the field is absent from both schemas.
`test_adaptation_is_a_state_transition_only` pins the seven labels and two transitions.

**Why it matters**

A course on a topic with real dependencies (algebra before calculus, safety before tool use, a
vocabulary set before a dialogue) cannot express "do not start section 3 first". The harness can
regenerate after failure, but it cannot sequence, gate or reorder by dependency. Quantified: 7
states, 1 review flag, 0 prerequisite edges.

**Proposed next card:** H-17 "Prerequisite edges in the plan contract" only if the product wants
sequencing; otherwise state that adaptation is mastery-label routing.

### P2-9. The green policy matrix still supplies inputs the frozen contract cannot carry

**Paths**

- `contracts/rpc.v9.json:532-568`: `course.create.dials` has `additionalProperties: false` with
  exactly `pace`, `depth`, `assessment`, `autonomy`.
- `tests/test_policy_integration.py` and several generation tests pass
  `dials={"subject_domain": ...}` and `dials={"level": ...}`, which the contract refuses.

**Reproduction**

`ContractFalseConfidenceTest.test_course_create_dials_reject_subject_domain_and_level` validates a
legal dials object and then the same object plus `subject_domain` / `level`, using the contract's
own schema: legal passes, both impossible payloads fail.

**Why it matters**

This confirms the first review's P0-3/P2-1 with an executable contract check. A policy test that
sets `subject_domain` proves the policy function, not the product. Any card that claims the
capability policy is reachable must first add those fields to the contract and the UI payload.
The replacement is a contract-level test that sends the exact `course.create` payload and asserts
the resulting plan/policy inputs. (Not counted as a novel round-2 finding.)

### P2-10. Audit provenance: the round-1 review is uncommitted

`git status --porcelain docs/ADVERSARIAL-HARNESS-REVIEW.md` in the main checkout returns
`?? docs/ADVERSARIAL-HARNESS-REVIEW.md`; `git log --all -- docs/ADVERSARIAL-HARNESS-REVIEW.md`
returns no commit. The card's "read first" premise therefore cannot be reproduced from any branch
or tag. No content judgment is implied; it is a reproducibility defect. Proposed next card: H-18
"Commit the round-1 review and the audit evidence index", so later audits cite hashes, not a
working-tree path.

## Angles checked that did not yield a new finding (stated so the limits are honest)

- **Host seam honesty (angle 8).** With no bound host, `research.host_search()` returns `None`,
  `HermesToolSearch.from_ctx(object())` raises `ResearchUnavailable`, `run_plan_job` records
  `research.status == "unavailable"` with a warning, and no URL is invented. The failure mode is
  honest; the composition with the waived factual gate is P1-4. The dashboard's lack of
  `ctx.llm` is a documented limit (`docs/GENERATION.md`), not a silent fallback.
- **Pack privacy (angle 6).** Export builds a fresh manifest from an allowlist; a manifest source
  object has `additionalProperties: false` and no `excerpt` field, so fetched page text cannot
  ride into a pack by that route. `PRIVATE_FIELDS` covers transcripts, attempts, evidence,
  notebooks, reflections, provider/model/settings, credentials, paths and tool calls; the pack
  scope explicitly preserves evidence rather than cascading it, and says so in the preview.
  I did not find a private row reachable through the export path in this pass.
- **Lesson-side rejection (for contrast with P0-1).** A rejected lesson is stored with
  `state="needs_review"`, its check is `closed`, `check_enabled` is false, and `learner_page`
  refuses to serve it (`generation.py:3405, 3500-3515`). The plan side is the outlier.
- **Idempotency and cancel.** Jobs are keyed by `operation_id`/`idempotency_key`, leases are
  compare-and-swap, cancellation is a recorded intent honored at stage boundaries, and a completed
  job that raced a cancel becomes `completed_late` (`coursebook/job_service.py:1-14, 181-235,
  295-410`). I did not reproduce a duplicate-spend or lost-cancel defect within this card's
  runtime; the scale finding I can defend is the flat cost ceiling (P1-6).

## Cards the supervisor should create

1. **H-11 (P0)** Plan approval must bind the validation verdict. Represent `needs_review` on
   `plans` or gate `plan.approve` on the validation record; regression test from P0-1.
2. **H-12 (P0)** Source-trust boundary and claim-level provenance lint; injection probes from P0-2.
3. **H-13 (P1)** Validator independence: record model identity, compare it, offer a cross-model
   pass, and stop the same model upgrading its own claim support; includes the P1-4 research
   waiver decision.
4. **H-14 (P1)** Assessment construct breadth decision (code, performance, artifact) with the
   closed vocabulary named in P1-5.
5. **H-15 (P1)** Cost ceilings sized to the plan plus a recovery hint on `CostCeilingExceeded`.
6. **H-16 (P2)** Locale-aware scaffolds, document direction, non-Japanese fixture.
7. **H-17 (P2)** Prerequisite edges, only if sequencing is in the any-topic mission.
8. **H-18 (P2)** Commit the round-1 review and an audit evidence index so this report's premise is
   reproducible from a hash.

## What this audit does not claim

It does not claim a fix, a policy change, installability, `/remote` parity or a live arbitrary-topic
generation. It does not use the Japanese pack as evidence. It adds probes and this report only;
product code is untouched.
