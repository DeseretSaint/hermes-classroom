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
