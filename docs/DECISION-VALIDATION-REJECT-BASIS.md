# A declared `reject` must name something the pass judged

| | |
|---|---|
| Card | `t_0affea08`, found during H-208 while integrating H-182/D1–D3 (`502051d`) with H-192b/c (`d9b1f3c`, `wt/h208-integration`) |
| Author | Atlas (architecture), 2026-11-08 |
| Status | **Decided.** A declared `reject` that fails none of its own criteria and names no rejection is a contract violation (`ModelOutputInvalid` → `VALIDATION_FAILED`, non-retryable), not a refusal. A grounded `reject` remains the H-182/D1 repairable refusal, unchanged. |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no criterion added or removed. |
| Code delta | `coursebook/generation.py` (`_declared_reject_problem`, `_parse_validation_answer`, `_refusal_reasons`, `_feedback`, `_DECLARED_VERDICT_RULE` in both prompt builders, `VALIDATION_PROMPT_VERSION` → `validation-prompt.v5`); `tests/blueprint_support.py` (`narrowed_validation_answer` re-derives the per-pass verdict); `tests/test_validation_reject_basis.py` (10 tests); `tests/test_validation_shape_repair.py` (label assertion follows the instruction text); `docs/GENERATION.md` §1 and the prompt table. |

---

## 1. The shape this resolves

H-192b split plan validation into two passes of five criteria, each with its own narrowed schema
(`validation_pass_schema`). A recorded ten-criterion validator answer that declares

```
verdict: "reject"
  … rejection: {item, criterion: "evidence_target_fit", …}
```

was narrowed for pass 1 by removing the rejection, because pass 1 does not own
`evidence_target_fit`. What reached `validation_verdict` was therefore

```
declared = "reject"; failed = []; unknown = []; rejections = []
```

and `validation_verdict` honoured the declared verdict: `verdict: "reject"` with no failed
criterion, no unknown criterion and no rejection. H-182/D1 then treated that as a repairable
refusal and called `coursebook.plan.generate` a second time on `_feedback`'s generic sentence
("rejected the previous attempt without itemised reasons; fix the objective/source alignment and
try again"). Whether it happened was decided by thread order, because the two validation passes run
concurrently: `tests.test_validation_shape_repair` failed 2 runs in 3 and passed 1 in 3 on
identical code.

The H-208 fixture fix (serve the recorded answer to the pass that owns its rejection) makes that
test deterministic. It does not decide the semantics, which is this document. On the real route the
narrowing only matters for replays: the host rejects an out-of-pass answer against the narrowed
schema before it reaches the pipeline. What remains on the live route is a validator that
genuinely declares `reject` while marking every criterion it was given `pass` and naming no
rejection.

## 2. Decision

**A declared `reject` is a verdict about the artifact, and a verdict must name something the pass
judged.** For a criteria pass, a `reject` is grounded when either

* at least one criterion of that pass is not `pass` — `fail` (a rule was broken) or `unknown` (the
  answer genuinely cannot tell, with a reason); or
* at least one rejection names an item, a criterion the pass owns, and a reason.

An answer that declares `reject` with every own criterion `pass` and an empty rejection list is
typed as `ModelOutputInvalid` (`code = "VALIDATION_FAILED"`, `retryable: false`). It is **not** a
refusal: no second authoring call runs, no validation record is written, no plan document is
stored, and no refusal is projected to the review surface.

`unknown` counts as a ground deliberately. It is a stated answer with a reason, and a conservative
validator that cannot verify a criterion is rejecting on record rather than on silence. Gating only
on `fail` would have typed honest `unknown`-based refusals as contract failures.

## 3. Why this rather than trusting the declared reject

The two candidate rules behave differently in exactly one place: what happens to an answer that
carries no rule.

| | Trust the declared `reject` (before) | Require a ground (decided) |
|---|---|---|
| Artifact approvable | never | never — the declared `reject` is only reachable with a ground, so every reachable refusal is still closed |
| Spend | one extra authoring call, plus a second research-to-plan cycle (`research_status`/reuse rules permitting) | none; the validator answer already arrived |
| Repair input | a generic sentence that names no rule (`_feedback`'s "without itemised reasons" branch) | not applicable: there is nothing to repair |
| Reviewer sees | `rejection_reasons = ["criteria failed: "]` — an empty reason when the reject rested on `unknown` rather than `fail` | nothing: no refusal record exists for an answer that is not a verdict |
| Validator field means | "a verdict" when grounded, "please resample" when not | one meaning: a verdict |
| Determinism | outcome depended on which pass thread answered first | independent of thread order by construction |

The cost of the decision is that a validator which answers incoherently fails the job with a
non-retryable `VALIDATION_FAILED` instead of producing a plan. That is the honest trade:

1. **The old behaviour did not actually honour the refusal.** After the re-author, a passing second
   answer became the plan. A declared `reject` that grounds nothing was used as a retry trigger and
   then discarded. One field cannot mean "a verdict" and "a resample request" depending on whether
   it can be checked.
2. **A blind re-author is not a repair.** H-182/D1's repair loop feeds the validator's rejection
   list to the author. With an empty list the loop cannot repair anything; it resamples at
   authoring-plus-research cost.
3. **The failure class already exists.** H-191/H-192 established that an answer which arrived while
   the host was healthy, and which violates the frozen contract, is `ModelOutputInvalid` →
   `VALIDATION_FAILED` (non-retryable) — never an outage label, never a verdict, and never a
   re-run that spends the same call to get the same malformed answer. This is the same class: the
   payload violated the contract.
4. **The rule is stated before the answer, not implied by the schema.** H-191's measured defect was
   a schema bound (`maxLength: 80`) the prompt never stated. The rule therefore lives in
   `validation_pass_instructions` (bumped to `validation-prompt.v5`) and is enforced in
   `_parse_validation_answer`, not as a JSON-Schema `if/then` whose failure would be reported to the
   model as one opaque "not valid under any of the given schemas". Enforcing in Python also means a
   seam that does not run the schema gate cannot wave the incoherent answer through.
5. **No second call is spent establishing it.** The alternative — one validator re-ask in the shape
   of the H-191 repair — was rejected: it is the same resample, one model call smaller, and it
   would need the repair loop moved out of `_call_llm` (where it is keyed to the host gate) into
   three call sites. The rule is stated up front instead.

## 4. What does not change

* A grounded `reject` is still a refusal, and H-182/D1 still re-authors it once with the
  validator's own reasons. `tests/test_h182_plan_repair.py` and
  `tests/test_validation_reject_basis.py::test_a_grounded_refusal_still_re_authors_once` pin that.
* `validation_verdict` still refuses to pass an artifact whose declared verdict is `reject`, whose
  criteria failed, whose criteria are unknown (unless waived), or that carries rejections. The
  declared `reject` is never converted into `pass`.
* `merge_validation_reports` still makes any pass's grounded `reject` a `reject` for the whole
  review, and a claim-only pass still carries no verdict.
* The ten criteria, the schema bounds and the `unknown` waiver rule are untouched.

## 5. One adjacent defect fixed in the same change

The three refusal branches built their stored reasons as

```python
[f"{entry.get('item')}: {entry.get('reason')}" for entry in verdict["rejections"]] \
  or [f"criteria failed: {', '.join(verdict['failed'])}"]
```

so a refusal grounded in `unknown` (no failed criterion, no itemised rejection) stored the literal
string `criteria failed: ` with nothing after it. The branches now share
`_refusal_reasons(verdict)`: rejections, then failed criteria, then the unverifiable criteria, and
`_feedback(verdict)` feeds the same reasons to the repair loop — a refusal that failed a criterion
without itemising a rejection is now repairable with that criterion's own reason instead of the
generic hint.

## 6. Evidence

* `tests/test_validation_reject_basis.py` — 10 tests: the ungrounded shape is typed (code,
  retryability, purpose, violation text); the three grounded shapes parse and read back as refusals
  with non-empty reasons; a claim-only pass is unaffected; both prompt builders (the narrowed plan
  passes and the wide lesson/unit passes) state the rule; the plan job spends exactly one authoring
  call and persists no plan or validation record on the ungrounded shape; a grounded refusal still
  re-authors once; and the H-208 narrowed recorded answer is a typed failure of the non-owning pass
  on 10 consecutive runs while the owning pass keeps its measured 81-character violation.
* `tests/test_validation_shape_repair.py`, `tests/test_h182_plan_repair.py`,
  `tests/test_plan_approval.py`, `tests/test_h192_validation_bounds.py`,
  `tests/test_h192c_validator_output_bound.py` — the validator, refusal and merge suites around the
  change.
* `scripts/check-docs-truth.py --skip-tests` — `docs/GENERATION.md` now quotes
  `validation-prompt.v5`, which is the constant the module emits.
* The full suite on `wt/h208-integration` is re-run after this change; the count and result are
  recorded in the card's completion handoff, not asserted here.
