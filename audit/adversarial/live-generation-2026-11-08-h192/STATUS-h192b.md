# H-192b — bounded plan validation, measured on the repaired tree

Status: **PARTIAL**. The three named defects are fixed and proven by the suite; a live three-scope
run on this branch shows the plan stage recovered (single reached `plan.approve` ok) but the card's
full acceptance is not met, for reasons outside the three named defects (recorded below).

Branch: `cb/t_958c3f23` @ `432e8a0`, base `127cce1` (the H-192 packet `7e4cb84` cherry-picked on
top). Product code changed here: `coursebook/generation.py` only (plus docs and tests).

## What changed

1. **Claim verdicts are batched per pass.** The criteria pass takes at most
   `CLAIM_VERDICTS_PER_PASS = 6` claim labels; the rest go to claim-only passes in fixed batches of
   `CLAIM_ONLY_VERDICTS_PER_PASS = 12`. A claim-only pass has its own narrowed schema carrying
   `claim_verdicts` only — no `criteria`, no `rejections`, no artifact `verdict` — so it can never
   reject the artifact or widen the review. `merge_validation_reports` merges the ten criteria from
   the owning pass and every claim verdict exactly once. `validation_pass_criteria` returns `()`
   for a claim-only pass.
2. **A validator answer that violates its own narrowed schema is `VALIDATION_FAILED`.**
   `_parse_validation_answer` re-raises the parse violation as `ModelOutputInvalid` at the plan,
   unit-sections and lesson stages (`retryable: false`, `purpose` and `schema_name` in details).
   The old plan-stage path surfaced it as `INTERNAL_ERROR` / retryable.
3. **A content rejection is `VALIDATION_FAILED`.** `GenerationRejected` now carries
   `code = "VALIDATION_FAILED"`, so a validator refusal (e.g. `self_study` contradiction) is a
   non-retryable validation outcome carrying its reasons, not `INTERNAL_ERROR` / retryable.

Suite: `Ran 2506 tests in 415.466s` → `OK` (includes the regenerated `harness-e2e` recorded packet
for the new pass layout).

## Live measurement (same packet, same provider routes, fresh homes)

Driver: `run_scopes.sh`, operator deadlines 600 s (unchanged from the H-192 packet; no rule, bound
or cap widened). Author `nous/deepseek-v4.1-flash-1017`, validator `nous/z-ai/glm-5.3-flash`.

| scope | recipe | plan job | plan.generate | plan.validate calls | approve | lessons | page |
|---|---|---|---|---|---|---|---|
| single | one_off | completed 388.2 s | 36.7 s / 5 679 + 38.5 s / 6 218 (2 attempts) | 200.9 s / 12 726 + 103.5 s / 13 429 | **ok** (`independently_validated`, draft) | 406.2 s, 1 lesson `needs_review` | none |
| short | committed | completed 686.3 s, `needs_review` | 69.1 s / 12 234 + 55.2 s / 9 145 | 62.0 s / 10 739 + **539.3 s / 22 325** | refused `plan_not_validated` | not started | none |
| full | committed | **failed 754.4 s**, `HOST_UNAVAILABLE` | 71.1 s / 11 699 (attempt 1); attempt 2 exceeded the 600 s deadline | none | refused `plan_empty` | not started | none |

What the numbers establish:

- The full-scope 29 386-token / 376.9 s single answer that broke `claim_verdicts` is gone. Every
  validation answer on this run was schema-valid and no job reported a shape violation. The
  criteria pass is now at most ten criteria plus six claims; claim support is a separate bounded
  pass.
- `single` reached `plan.approve` ok with `independently_validated` provenance — impossible on the
  H-192 base, where 0/3 scopes produced a plan document.
- Residual risk: the criteria pass can still emit a large reasoning answer on a contested plan
  (short: 22 325 tokens / 539.3 s under the 600 s operator deadline). Verdict count is bounded; the
  provider's reasoning length is not, because `max_tokens` is still not forwarded on this route.

## Why the card's acceptance is still not met

These are **not** the three named defects and are not repaired here:

- `single`: plan approved and lessons authored, but the lesson was parked `needs_review` by the
  deterministic text-completeness gate: `blocks[1].short introduces '3:00.', which its deep text
  does not contain`. No `lesson.page` is served for a parked lesson (by design).
- `short`: the plan generator broke a deterministic rule on its second attempt
  (`committed courses need graded checks`), and the first attempt's validation had already
  rejected; `plan.approve` therefore refused `plan_not_validated`.
- `full`: plan generation itself exceeded its 600 s deadline on the retry attempt
  (`HOST_UNAVAILABLE`, `deadline_s: 600`), so no validation ran and no document was written.
  A diagnostic rerun is recorded separately (`full-rerun.json`) if it completed.

The packet is the H-192 packet; H-192 re-runs it after this branch lands.

## Second measurement — bounded passes (`0bd5cf2` + `f0be341`)

Same packet, fresh isolated homes, operator deadlines unchanged (600 s generate / 600 s validate,
job stop 1100 s), author `nous/deepseek-v4.1-flash-1017`, validator `nous/z-ai/glm-5.3-flash`.
Layout on this run: two criteria passes of five, at most six claims on a criteria pass, twelve on
a claim-only pass. Raw per-call numbers below; the redacted captures are in `evidence/`.

| scope | plan.generate | plan.validate calls (duration / output tokens) | plan.approve | lessons |
|---|---|---|---|---|
| single | 32.4 s / 7 189 | 43.8 s / 3 004 + **344.8 s / 9 881** (total 12 885) | **ok** | unit_sections 5.8 s / 1 138 + 4.7 s / 996; unit validate **320.6 s / 23 096** + 214.5 s / 16 051; lesson 64.0 s + 54.6 s; job stopped at 666 s |
| short | 348.2 s / 10 300 | 49.6 s / 4 361 + **542.4 s / 18 740** | ok (plan approved) | unit_sections 12.8 s / 1 462; unit validate 135.3 s / 17 232; lesson 58.6 s / 9 016; job still running at the 1 100 s stop |
| full | 83.0 s / 17 006 | 31.7 s / 2 388 + 183.9 s / 11 893 + 258.6 s / 2 868 + **927.0 s / 19 739** | refused `plan_empty` (job `HOST_UNAVAILABLE`, `plan.validate` deadline) | not started |

What changed relative to the first measurement:

- The single-scope validation answer fell from one unbounded demand to two bounded passes
  (3 004 + 9 881 = 12 885 completion tokens against the 29 386-token full-scope answer H-192
  measured), and `single` reached `plan.approve` ok for the first time on this branch.
- The full-scope claim answer no longer breaks its schema: every returned answer was
  schema-valid, and no job reported a shape violation.
- **Defect 1 is not closed for `full`.** A pass that was asked for five criteria and six claims
  still emitted **19 739 completion tokens in 927 s**, past its own 600 s deadline, and the job
  failed `HOST_UNAVAILABLE`. Bounding the *demand* does not bound the validator's own reasoning;
  `max_tokens` is still not forwarded on this route, so no cap bites. The measured remedy left is
  a provider-side output cap or a validator route that stops at the schema, not a wider deadline.
- Defects 2 and 3 are closed and proven by the suite (`tests/test_h192_validation_bounds.py`,
  `tests/test_validation_shape_repair.py`): a shape violation at plan stage and a content
  rejection are both `VALIDATION_FAILED`, non-retryable, with the reasons.
- The plan prompt now states the graded-check rule the kernel enforces; `short`'s committed plan
  was authored and approved on the first attempt in this run (the first measurement lost both
  attempts to `committed courses need graded checks`).
- The unit-stage validation request is now unit-sized (the whole plan document used to make a
  short course's request 26 799 bytes against the 24 000-byte bound).
- The lesson short-claim gate no longer treats sentence-final punctuation as a new claim (the
  first measurement's single-scope page was parked on `'3:00.'`).

Remaining work is named, measured and out of this branch's rule surface: validator output is
uncapped on the nous route (927 s / 19 739 tokens for a five-criterion pass), and the lesson-stage
validation has the same shape (23 096 and 16 051-token answers in `single`).
