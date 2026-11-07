# GENERIC-ACCEPTANCE-AUDIT — can an arbitrary topic become a real course?

Task: `h30` / `t_178dc615`. Auditor: Sentinel (independent verification; no product code changed).
Date: 2026-11-07T09:19Z. Branch: `wt/harness-generic-audit`.
Base product tree: local `master` at `498b1daeae946d988072bb7852c07b4cfbddeb8e`.
Evidence packet audited: `wt/harness-e2e-proof` at `111c7e9315d924a8e6aa4b7575db38a07ef7465f`
(content commit `4dd0f1801baa8b2dd2635e6fb722778df77325b6`).
Grading fix audited for comparison: `wt/harness-grading-lanes` at `ce6c8c1db37e9cfa75431b2f8d325871b875faa1`
(generated checks grade deterministically). Neither H-09 nor this grading branch is merged.

This document is evidence, not a product claim. It records what was executed, on which commit,
with which evidence class, and what could not be executed.

## 1. Verdict in one paragraph

The harness produces a course from a free-form non-Japanese goal and packages it, but it does not
yet produce **the shape the learner asked for**. `single` is hard-padded to 4 objectives by the
plan schema and the plan prompt; `full` is hard-truncated at 8 objectives and has no units,
prerequisite edges or unit-boundary resume. On the shipped tree a generated check cannot reach a
verdict: a correct and a wrong answer both return `needs_retry`. The H-09 packet is genuine and
reproducible on its own commit, but its "scope matches documented bounds" assertion checks the
code's own `SCOPE_EXPECTATIONS`, so it passes while the product requirement fails.

## 2. What was run, and on what

| # | Command | Tree | Evidence class | Result |
|---|---|---|---|---|
| R1 | `PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py` | `111c7e9` clean worktree | recorded model + recorded page through the live pipeline | `bicycle_single: PASS`, `music_short: PASS`, `soldering_full: PASS` |
| R2 | `python3 -m unittest tests.test_harness_e2e -v` | `111c7e9` | as R1 | `Ran 9 tests … OK` |
| R3 | `python3 -m unittest discover -s tests -t .` | `111c7e9` | unit suite | `Ran 1052 tests … FAILED (failures=3, skipped=15)` |
| R4 | `PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_shape.py <plan.json>` | `498b1da` (`master`) | deterministic code probe, no model | see §4 |
| R5 | `PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_grading.py <harness> <home>` | `111c7e9` | live RPC (`check.open`, `attempt.submit`) over a recorded-transcript course | see §5 |
| R6 | `python3 -m unittest tests.test_grading_lanes -v` | `ce6c8c1` | unit suite of the unmerged fix | `Ran 15 tests … OK` |
| R7 | focused seam suite (`test_generation`, `test_capability_policy`, `test_policy_integration`, `test_policy_threading`, `test_media_plan`, `test_procedure_document`, `test_lesson_document`, `test_kernel_grading`) | `498b1da` | unit suite | `Ran 209 tests … OK` |

Environment for R1/R2/R3/R5: throwaway `HERMES_HOME` under the sentinel scratch root, never the
operator profile. No provider was called; `labels.provider_calls = 0`, `provider_spend_usd = 0.0`,
and the recorded pipeline reports `cost_usd = 0.0` for the plan job.

Raw outputs are in `audit/adversarial/generic-harness/evidence/`.

### R3 discrepancy — the parent's test count is not reproducible here

`audit/adversarial/harness-e2e/STATUS.md` reports **1230 tests**. A clean checkout of the same
commit reports **1052 tests, 15 class-level skips**. The 15 skips are the desktop renderer suites
(`test_desktop_*`, `test_m1_mode_parity`), skipped because `react`/`react-dom` are not installed
beside `desktop/` in a fresh worktree. The 3 failures are the known H-17 × v10 cost-ceiling failures
tracked by `t_d50cb007`; their failure text is a cb.rpc contract mismatch (`brief.budget_usd`,
`brief.plan_id`), not a shape failure. The 1230 figure is therefore environment-dependent and
**UNVERIFIED** here; the auditable statement is "1052 pass/fail-accounted tests with 3 known
failures in this environment".

## 3. H-09 evidence packet — what it proves and what it does not

Reproduced independently from the packet's own commands on the exact commit. Re-derived from the
freshly generated `evidence/*.json`, not from the packet's assertion table.

| Claim | Independent check | Verdict |
|---|---|---|
| the three goals are not the Japanese fixture | goal strings read from the packet; 0 Japanese codepoints anywhere in the regenerated packet | PASS |
| one section per objective | `4/4`, `5/5`, `6/6` objectives/sections on the fresh run | PASS |
| every section declares `media_need` | all sections carry a typed need; all three plans declared `none/none` for every section | PASS |
| technical goal gets a typed procedure, music does not | bicycle objective 1 and soldering objective 3 carry `procedure`; music carries none | PASS |
| no answer key in the served page | check payloads carry `stimulus`/`learner_instructions`/`scaffolds` only — no `reference_answer`, `accepted_answers` or rubric; the page does carry `worked_example.answer`, which is the worked example's own answer, not the graded item's key (music check key `"7"` vs worked-example answer "Three semitones, a minor third") | PASS |
| every lesson `validated`, export ready, archive written | fresh run: all rows `validated`, `export_review.ready = true`, ZIP written (13/16/19 entries) | PASS |
| planted private notebook row never exports | marker absent from every archive entry | PASS |
| no fake mastery or percentage claim | no mastery/fluency/certificate words and no `N%` claims in plan or served pages | PASS |
| model is a recorded transcript, not live | `labels.model`, 0 provider calls, 0 spend, injected replay LLM object | PASS (labelled) |
| research is a recorded page, not live | `labels.research`; the page is `https://example.org/...` synthetic content | PASS (labelled) |

Packet integrity findings:

- **The packet is a verdict snapshot, not a byte-reproducible artifact.** Re-running R1 on the same
  commit rewrites all three evidence JSON files (minted ids and timestamps differ). The packet's
  freshness test only compares `verdict`, `assertions` and `scenario`
  (`tests/test_harness_e2e.py:97-103`), so "current" means "same verdict", not "same bytes".
- **No claim in the packet names its commit.** Neither `STATUS.md` nor `docs/HARNESS-E2E.md` names
  `111c7e9`/`4dd0f18`; the only commit named is the export-gate content commit. The commit identity
  lives in the task handoff metadata, not in the evidence document.
- **`scope_matches_documented_bounds` is tautological.** It compares the generated objective count
  to `generation.SCOPE_EXPECTATIONS[scope]` — the same table the generator is built from. It cannot
  fail for a shape defect. This is why a 6-objective plan labelled `full` reports PASS.
- **The branch is not integrated.** Merging `wt/harness-e2e-proof` into `master` at `498b1da`
  conflicts in `coursebook/generation.py`, `docs/CONTRACTS.md` and `tests/test_adversarial_round2.py`
  (merge aborted; no product file was edited). On its own commit the plan prompt still carries
  `objective_count: [4, 8]` for a `single` course; on `master` the H-13 threading changes that to
  `4 to 5`. The packet therefore does not describe the tree that would ship.

## 4. Three-shape matrix

"Objectives" counts come from the freshly generated plan documents (R1). "Required" comes from
`docs/COURSE-BLUEPRINT.md` §2 and this card's brief.

| Shape | Evidence run | Scope / recipe | Objectives | Required | Verdict |
|---|---|---|---:|---|---|
| **one-off** | `bicycle_single` ("Replace the inner tube on a bicycle rear wheel and check the brakes.") | `single` / `one_off` | **4** objectives, 4 lessons, 4 verification checklists, no quiz/homework | exactly **1** objective, 1 lesson | **FAIL** |
| **short** | `music_short` ("Understand intervals, triads and the circle of fifths…") | `short` / `committed` | **5** objectives, 5 lessons, 5 quiz checks | 3–6 objectives, usable path, **checks that grade** | **FAIL** — shape and path pass; checks do not grade (§5) |
| **full** | `soldering_full` ("Prepare for a first soldering repair on a through-hole PCB.") | `full` / `committed` | **6** objectives, 6 lessons, one implicit unit | **12+** objectives, units, a prerequisite edge, unit-boundary resume/cancel, honest cost/time | **BLOCKED** by H-21 |

### Why one-off is FAIL (not "small but acceptable")

`probe_shape.py` on `master` (`evidence/probe_shape_master.txt`):

```text
SCOPE_EXPECTATIONS['single']: {'objectives': (4, 5), …}
PLAN_SCHEMA.objectives.minItems: 4
PLAN_SCHEMA.objectives.maxItems: 8
prompt[single]: Produce 4 to 5 objectives, … each with a stable ordinal, an evidence target …
1-objective plan: REJECTED — /objectives: [...] is too short | /sections: [...] is too short
4-objective plan: ACCEPTED
enforce_plan_rules[1, single]: ACCEPTED   # the rule layer has no count rule at all
```

A one-objective brief cannot reach the learner: the artifact validator refuses fewer than four
objectives, the prompt asks for 4–5, and the deterministic rule layer does not enforce any count
(so it cannot compensate). The H-09 bicycle course is exactly the padding this card forbids. The
shipped contract is explicit about what `single` means — `contracts/rpc.v10.json`, `course.create`
scope description: "`single` (one lesson)" — and the runtime delivers 4–5 objectives. Contract and
implementation disagree.

### Why short is FAIL despite a working shape

The shape is right: 5 objectives, one section per objective, a comprehension→production ramp, a
verification of no answer leak, export ready. The named criterion "checks that actually grade"
fails on the shipped tree — see §5. The restaurant-Spanish variant named in the brief was **not
run end to end** (see UNVERIFIED).

### Why full is BLOCKED (not "six objectives is a full course")

`master` has no unit model at all:

```text
PLAN_SCHEMA has 'units': False
PLAN_SCHEMA has 'plan_schema': False
12-objective plan: REJECTED — /check_plan/8/objective_ref: 9 is greater than the maximum of 8 …
```

There is no `plan_units` table and no migration `0007` (`coursebook/migrations/` ends at `0006`).
`wt/h21a-contract-migration`, `wt/h21b-unit-stages` and `wt/h21c-prereq-gating` point at `498b1da`
— they contain no commits. H-21 is genuinely unimplemented (board status `blocked`). A 6-objective
soldering course is a short course; it is not evidence for the full shape, and this audit does not
treat it as such. Unit-boundary resume/cancel is consequently **UNVERIFIED**.

## 5. Generated checks do not reach a verdict on the shipped tree

R5 drives `check.open` then `attempt.submit` on two generated music objectives: the transcript's
correct answer (`"7"`) and a wrong answer (`"D major"`; reference is `"D minor"`). Both are accepted
as RPC calls and both return the same verdict (`evidence/probe_grading_h09.txt`):

```text
attempt.submit[correct-answer]: {"verdict": "needs_retry", "next_action": "retry_grading", …}
attempt.submit[wrong-answer]:   {"verdict": "needs_retry", "next_action": "retry_grading", …}
attempt_rows[0].grading_provenance_json: {"failure": "GradingUnavailable: the open-response aux
  grader is not configured; this build fails closed to needs_retry", "grader": "unavailable"}
```

Cause, read from `coursebook/generation.py:_check_payloads` on `master`: the stored reference is
`{"reference_answer", "accepted_answers", "accepted_alternatives"}` — no `kind`. `grading.grade`
routes a reference without a `kind` to the open lane, which fails closed. Correct and wrong answers
are indistinguishable; no evidence is collected. This is the defect `B-1`/H-23 exists to fix.

The fix is real and green, but **unmerged**: `ce6c8c1` (`wt/harness-grading-lanes`) adds the lane to
every stored check and deterministic grading. Its suite passes on its own branch (R6):

```text
test_selection_quiz_grades_the_typed_choice ... ok
test_text_quiz_right_answer_passes_cold_and_completes ... ok
test_text_quiz_wrong_answer_is_not_yet_and_advances_nothing ... ok
test_a_self_report_answer_is_not_graded_and_advances_nothing ... ok
Ran 15 tests … OK
```

Open/self-report checks on that branch stay saved-not-graded (`verdict=needs_retry`,
`next_action=retry_grading`, revision unchanged). On the shipped tree every generated check behaves
that way, so "open checks remain saved-not-graded" holds only degenerately: there is no graded lane
to contrast it with.

## 6. Generic failure modes — checklist

| Requirement | Probe | Verdict |
|---|---|---|
| a one-objective plan is not padded to four | schema `minItems=4`, prompt `4 to 5`, H-09 bicycle = 4 objectives | **FAIL** |
| a full plan is not truncated at eight | schema `maxItems=8`, `check_plan.objective_ref.maximum=8`, prompt `4 to 8`, H-09 full = 6 | **FAIL** |
| generated closed-reference checks reach a real verdict | R5: correct and wrong both `needs_retry` | **FAIL** (fix exists unmerged at `ce6c8c1`) |
| open checks remain saved-not-graded | H-23 branch tests; shipped tree only has the degenerate case | **PASS** (on `ce6c8c1`), **UNVERIFIED** as a contrast on `master` |
| non-language topic + locale is not routed to language | `music` + `es-MX` → domain `music`, rubric `concept_explanation`, audio none | **PASS** |
| language topic without a locale is not silently general | goal "Order a meal at a restaurant in Spanish", no locale, no domain → domain `general`, rubric `concept_explanation`, audio none | **FAIL** (silently general) |
| media appears only where intent earns it | pronunciation intent + `es-MX` → `audio=required`, role `pronunciation_reference`; labelled-parts intent → `image=optional`, role `schematic`; unearned intents → `none` | **PASS** |
| an illustration never claims procedural authority | required illustration on a technical procedure → `CapabilityPolicyError: an AI illustration is context only and can never be a required visual need` | **PASS** |
| procedure content has a deterministic schematic or honest text fallback | served bicycle/soldering pages: `procedure.steps` reference real segments 1..2 with per-step checks, `tools`, `stop_condition`, `hazards`, cited `source`, `schematic=null` (no fabricated diagram; the text is the authority) | **PASS** |
| no step writes to `master` | all work on `wt/harness-generic-audit`; `master` and `origin/master` both `498b1da`; no push | **PASS** |
| no provider key is read | the pipeline takes an injected `LLM`; `coursebook/generation.py` reads only timeout/cost env vars, no API-key variable; spend 0 | **PASS** |
| no fake percentage or mastery claim | scan of plan + served pages: no mastery/fluency/certificate words, no `N%`; desktop copy explicitly refuses a progress percentage before the plan exists | **PASS** |

Note on the language-without-locale case: the contract lets the caller omit both `subject_domain`
and `locale`, and the policy then has nothing to route on. It is not a shape failure and not in this
card's named owner list; it is a P2 contract/routing gap (closest owners H-13/H-18, decision to
Atlas).

## 7. Defects, with owning cards

| id | Severity | Defect | Owner |
|---|---|---|---|
| D1 | P0 | `single` scope cannot produce one objective; schema/prompt force 4–5, so a one-off task is padded | H-21 (blocked) |
| D2 | P0 | `full` scope cannot exceed 8 objectives, has no units/prerequisite edges, no unit-boundary resume | H-21 (blocked) |
| D3 | P0 | generated checks store no reference lane; correct and wrong answers both return `needs_retry` | H-23 (fix `ce6c8c1` unmerged) |
| D4 | P1 | a language goal with no declared locale and no subject domain is silently treated as `general` | H-13 / H-18 — not in this card's owner list; Atlas to route |
| D5 | P2 | H-09 evidence docs do not name the evidence commit; the reported 1230-test count is environment-dependent (1052 here) | H-09 / H-11 |
| D6 | P2 | H-09's `scope_matches_documented_bounds` assertion cannot fail for a shape defect (compares the code to itself) | H-09 |
| D7 | P3 | evidence packet is not byte-reproducible; the freshness guard compares only verdict/assertions/scenario | H-09 |
| D8 | P3 | the lesson validator accepted truncated authored short texts (bicycle "…, not."; soldering "…board repair..") | H-09 / lesson validator owner |

No product code was changed by this card. No merge, push, tag, publish or demo was produced.

## 8. Not exercised — UNVERIFIED

1. **Live provider.** All model output is a recorded transcript. Live model quality and a live
   spend number are **UNVERIFIED**. No spend was approved for this card.
2. **Live web research.** The page is a recorded `example.org` page through the real seam.
   Research relevance, source trust and depth for an arbitrary topic are **UNVERIFIED**.
3. **A language goal end to end.** The restaurant-Spanish shape was probed at the policy/routing
   layer only. A generated Spanish course (audio/pronunciation, locale scaffolds) is **UNVERIFIED**;
   no packet contains one.
4. **A 12+ objective / multi-unit course.** Not implemented (H-21). **BLOCKED**, not merely unrun.
5. **Unit-boundary resume and cancel.** No units exist; **UNVERIFIED**.
6. **Grading on the shipped tree with a live aux grader.** The open lane's configured behaviour is
   **UNVERIFIED**; only fail-closed was observed.
7. **Desktop renderer suites.** 15 classes skipped without `react`/`react-dom`; **UNVERIFIED** in
   this environment.
8. **The 1230-test count** claimed by H-09: **UNVERIFIED**; 1052 observed.

## 9. Reproduce

```bash
# product tree (this branch, based on master 498b1da)
PYTHONPATH=. python3 audit/adversarial/generic-harness/probe_shape.py \
  <checkout-of-111c7e9>/audit/adversarial/harness-e2e/transcripts/bicycle_single.json

# H-09 packet (clean checkout of 111c7e9, throwaway HOME)
cd <checkout-of-111c7e9>
HOME=<scratch>/home PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py
HOME=<scratch>/home PYTHONPATH=. python3 -m unittest tests.test_harness_e2e -v

# generated-check grading probe (same checkout)
HOME=<scratch>/home PYTHONPATH=. python3 <this-branch>/audit/adversarial/generic-harness/probe_grading.py \
  audit/adversarial/harness-e2e/harness_e2e.py <scratch>/probe-home

# the unmerged fix, for comparison
cd <checkout-of-ce6c8c1>
PYTHONPATH=. python3 -m unittest tests.test_grading_lanes -v
```

## 10. Final sentence

**Not yet fully generic — blocked by Y: H-21 (one-off cannot be one objective; full cannot exceed
eight objectives and has no units, prerequisite edges or unit-boundary resume) and H-23 (a
generated closed-reference check returns `needs_retry` for both a correct and a wrong answer on the
shipped tree, with the fix present but unmerged at `ce6c8c1`).**
