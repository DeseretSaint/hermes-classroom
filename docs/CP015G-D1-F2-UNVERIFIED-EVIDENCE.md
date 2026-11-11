# CP-015g/D1-F2 — the validation contract for claims a plan declares unverified

(Merged from `wt/cp-015g-d1-f2-unverified`; the domain half of D1-F2 is recorded in
`docs/CP015G-D1-F2-EVIDENCE.md`. The label this note names as `validation-prompt.v7` is
`validation-prompt.v12` on the merged tree.)

Status: implemented and tested on branch `wt/cp-015g-d1-f2-unverified`
(base `wt/cp-015g-d1-f1-authoring` @ `e728fbe9`; unpushed, nothing published).
Owner of the contract: Cinder (backend kernel). Authoring side is **not** re-opened: D1-F1
(`t_285529c8`) already fixed it.

## The defect, restated from the record

`docs/cp015g-d1-f1/run-f1-live-r2.json`, job `job_c3a5f5ca512a4d518e7b06c924e53eed`. The plan
marked objective 2 (setup/aim procedure) and objective 4 (orbital explanation)
`support: "unverified"` with empty `source_ids` — the authoring contract's own instruction when no
supplied excerpt carries the claim (§5b of `docs/GENERATION.md`). The independent validator refused:

```
objective:2: The setup/aim procedure is unsourced and must not be presented to a learner as verified content.
objective:4: The orbital-explanation objective is unsourced and must not be presented to a learner as verified content.
```

Neither objective presents itself as verified. The validator was refusing the plan's honesty, not
an unsupported assertion. The pipeline then spent a second authoring cycle on feedback the author
could not act on without inventing a citation.

## Decision 1 — does `source_support` refuse an honestly unverified claim?

**No.** `source_support` judges claims, not declarations. It refuses exactly three things:

1. a claim marked `sourced` that the excerpt it cites does not carry (the over-citation D1-F1
   removed on the authoring side);
2. a claim presented to the learner as established fact with no support;
3. a claim the supplied excerpts contradict — which is also a `factual_correctness` defect.

A claim the artifact itself marks `support: "unverified"` with no source ids is a **declared gap**.
It is recorded and disclosed at approval; it is never a refusal. The alternative reading (refuse
`unverified` outright) would make the `unverified` support value unusable and would mean no plan
for an under-sourced topic could ever pass, which is the defect this card is about.

The rule is now stated to the validator before it answers: `_PLAN_SUPPORT_RULE`, appended to every
plan-validation pass, under **`validation-prompt.v7`** (v6 → v7 because the instruction text
changed, and the label is recorded in stored validation bindings and the idempotency fingerprint).

## Decision 2 — what the pipeline does instead

**Pause the plan with a sourcing note; never re-author for a gap; never refuse the learner the
plan.**

* `plan_declared_gaps(plan)` reads the plan's own `support: "unverified"` / no-ids objectives.
* `validation_verdict(..., declared_gaps=...)` moves a `source_support` rejection naming one of
  those claims out of `rejections` and into `sourcing_notes` (`{item, claim, validator_reason}` —
  the validator's own words kept beside it). No pass is invented: a declared `reject` stays a
  `reject` and the plan stays `needs_review`.
* `gap_only_refusal` is true when the refusal rested *only* on declared gaps. The plan stage then
  parks the document `needs_review` on the first attempt instead of spending a second authoring
  and research cycle — regenerating cannot supply a source that was never fetched.
* The plan job result carries `sourcing_notes` and two warnings: one per gap naming the next step
  (re-research the claim, narrow the objective, or approve the lesson with it labelled unverified),
  and one saying the plan was parked rather than re-authored.
* `_refusal_reasons` states the gap and the next action instead of a bare
  `criteria failed: source_support`; `_feedback` adds the one rule that keeps a repair honest —
  do not invent a citation to satisfy a support complaint.

Re-research is a research-stage decision (the page-chrome defect is `t_41f23b3e`); narrowing is the
author's; the plan stage's job is to stop mislabelling the gap and stop paying to re-roll it.

## What changed

| File | Change |
|---|---|
| `coursebook/generation.py` | `_claim_item_key`, `plan_declared_gaps`; `validation_verdict` gains `declared_gaps`, reclassifies declared-gap rejections into `sourcing_notes`, reports `gap_only_refusal`; `_refusal_reasons` and `_feedback` state the gap; `_PLAN_SUPPORT_RULE` in both plan prompt builders; `VALIDATION_PROMPT_VERSION` v6 → v7; plan stage passes the gaps and parks on a gap-only refusal; plan result gains `sourcing_notes`; `_plan_warnings` discloses the gap and the next action |
| `docs/GENERATION.md` | §1 prompt table v6 → v7 and the label rationale; new **§5c** fixes the contract, the pipeline behaviour and the stated limits |
| `tests/test_cp015g_d1_f2_unverified.py` | 19 tests: gap detection, reclassification (live items verbatim, locator spellings, sourced control, mixed refusal, other criteria untouched, no-plan artifacts untouched), refusal text, repair feedback, the plan stage parking without a second authoring call, and the prompt label/rule |
| `tests/test_validation_shape_repair.py` | the label assertion follows the instruction text |

## Verified (real output)

* `python3 -m unittest tests.test_cp015g_d1_f2_unverified` → 19 tests, OK.
* `python3 -m unittest tests.test_validation_shape_repair tests.test_cp015g_d1_f2_unverified` →
  29 tests, OK.
* `python3 -m unittest tests.test_generation tests.test_cp015g_d1_f1_authoring
  tests.test_cp015g_d1_validation_repair tests.test_validation_reject_basis
  tests.test_h191_validation_demand tests.test_h192_validation_bounds
  tests.test_validation_shape_repair tests.test_adversarial_round2
  tests.test_executor_plan_checkpoint tests.test_cp015g_d1_f2_unverified` → **209 tests, OK**.
  The first run of this set had exactly one failure, the v6→v7 label assertion, which was updated
  in `tests/test_validation_shape_repair.py` and is green in the 209 above.
* The suite runs against an in-memory SQLite database built by `generation.ensure_schema`, through
  the real `run_plan_job` path — not a mock of it.
* `PYTHONPATH=. python3 audit/adversarial/harness-e2e/harness_e2e.py` → `overall: PASS (3/3
  scenarios)`, packet re-sealed (the three scenario JSONs gained `sourcing_notes: []` because the
  plan result now carries the field; `manifest.json` re-hashed).
* `python3 scripts/check-docs-truth.py --skip-tests` → `docs-truth: PASS`, including
  `GENERATION.md prompt labels match the generation constants (… validation-prompt.v7)`.

The contract decision itself is written up in `docs/DECISION-DECLARED-SOURCE-GAPS.md` (card, base,
status, the two questions answered as decision tables, and the limits).

## Not verified / limits stated

* **No live provider run was made for this change.** The evidence for the defect is the two live
  runs in `docs/cp015g-d1-f1/`; a v7 live re-run costs a second-model route and was not part of
  this card. What is proven is the contract and the kernel rule, not that deepseek obeys the new
  paragraph on the wire.
* A validator that fails `source_support` with **no itemised rejection at all** keeps its refusal:
  the criterion verdict is the validator's, not the kernel's, and the reader sees
  `criteria failed: source_support`. The kernel does not rewrite a criterion verdict to pass.
* Lesson page-level disclosure for an objective marked unverified is the lesson stage's contract
  and is unchanged here. This card decides the plan-validation contract only.
