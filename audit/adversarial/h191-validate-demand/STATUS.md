# H-191 follow-up — `plan.validate` output demand (choice **a**: smaller output demand per call)

Branch `wt/h191-validate-demand`, based on `wt/h190-plan-identity` @ `71f74e7` (which carries the
H-187 live-generation fixes). Product change is in `coursebook/generation.py`; the ten reviewed
criteria are **unchanged** — nothing was dropped to make the call fast.

Branch parent diagnosis: `audit/adversarial/h191-validate-stall/STATUS.md` (`wt/h191-validate-stall`
@ `af4b921`). This packet records the repair and its live measurement on the same reconstructed
request, same route (`nous` / `z-ai/glm-5.3-flash`), same schema name, same `max_tokens=2000`, and
the same deadline (180 s). No `FakeLLM`; no transcript edit.

## Decision

**(a) is the answer. (b) fails.**

- **(b) measured and refuted.** With `agent.auxiliary_client._forwards_max_tokens` patched `True` in
  memory (host file untouched), the exact 10-criterion request at `max_tokens=2000` returned in
  **38.3 s with exactly 2 000 completion tokens and 0 characters of content**
  (`evidence_cap_forwarded.json`): the reasoning budget is consumed before any JSON exists. The
  first attempt measured the same (39.1 s, 2 000 tokens, no content) and a schema-narrowed
  single-criterion pass (34.5 s, 2 000 tokens, no content). A forwarded cap truncates the verdict,
  which is the card's stated failure condition for (b).
- **Splitting into more calls does not pay.** Criteria-only (10 criteria, no claim verdicts,
  200-char reasons) 152.5 s / 11 020 tokens; claims-only (18 claim verdicts) 131.8 s / 11 567
  tokens. Five concurrent two-criterion passes: four returned at 48.5 / 61.6 / 75.5 / 87.2 s, the
  fifth missed the deadline; ~21 k aggregate tokens. The provider staggers concurrent calls, so the
  split converts into spend, not wall time.
- **Shipped repair:** one call, all ten criteria, the claim-verdict set bounded to the plan's own
  named claims, and one-sentence reasons. On the exact request this measured **145.0 s / 8 246**
  and **173.7 s / 9 521** completion tokens, both schema-valid, both inside the 180 s deadline —
  against the H-191 baseline of 243–286 s / 12.4–16.2 k.
- **Variance is real and stated, not hidden.** A third sample of the identical request hit the
  180 s deadline (`evidence_live_single.json`, attempt 2). Two of three draws fit; one did not. This
  is a material reduction in output demand (≈8–10 k vs 12–16 k tokens), not a guarantee. The
  remaining lever is a **host-level reasoning-effort control** (not a `max_tokens` cap) or a faster
  validator route; that is an Atlas decision, not something this card can settle by raising a
  deadline.

## Before / after request metadata (same reconstructed H-187 single-scope plan)

| field | before (H-191 baseline) | after (this branch) |
|---|---|---|
| calls | 1 | 1 (`VALIDATION_CRITERIA_PASSES` = one pass of all ten) |
| purpose | `coursebook.plan.validate` | same |
| prompt version | `validation-prompt.v3` | same (text and schema narrowed; the criteria set is identical) |
| schema name | `coursebook_validation_v1` | same |
| `max_tokens` | 2 000 (not forwarded by the host) | same (still not forwarded — deliberately not the fix) |
| criteria demanded | 10 verdicts, each reason ≤400 chars | 10 verdicts, each reason ≤200 chars, one sentence |
| claim verdicts | model enumerates the plan's claims | 3 deterministic labels: `objective:1`, `unit:1`, `plan:learner_outcome` |
| instructions | 1 320 B | 1 584 B |
| schema | 2 250 B | 2 291 B |
| `input_text` | 10 237 B | 10 237 B |
| **wire bytes** | **16 287 B** | **15 421 B** |
| declared deadline | 180 s | 180 s (unchanged) |

Request metadata for the after-shape: `evidence_live_single.json` → `requests[0]`; the same block is
in `evidence_live_single_more.json`. The before-shape is the H-191 packet's
`evidence_request_shape_single.json`.

## Live samples (real provider, real host seam)

| sample | wall time | completion tokens | outcome |
|---|---|---|---|
| H-191 baseline 1 | 242.955 s | 12 356 | completed (over 180 s deadline) |
| H-191 baseline 2 | 283.606 s | 16 060 | completed |
| H-191 baseline 3 | 286.065 s | 15 499 | completed |
| H-191 historical | 282.507 s | 16 188 | completed |
| after, attempt 1 | **144.964 s** | **8 246** | schema-valid, 10 criteria, 3 claim verdicts, `pass` |
| after, attempt 2 | 180.101 s | — | `ProviderTimeout` (deadline fired) |
| after, attempt 3 | **173.679 s** | **9 521** | schema-valid, 10 criteria, 3 claim verdicts, `pass` |

Artifacts: `evidence_live_single.json`, `evidence_live_single_more.json`,
`evidence_cap_forwarded.json`. The earlier five-pass layout measured in `evidence_live_after.json`
is superseded and kept only as the record of why splitting was rejected.

## Semantics preserved

**Why the prompt-version string stays `validation-prompt.v3`:** the reviewed criteria set and the
schema name are unchanged, and the sibling H-191 follow-up (`t_244cdbf7`, item-label bound) already
advances this shared constant to `v4` on its own branch. Advancing it here too would fork the label
on a line the merge must reconcile; the narrowed instruction text and schema are recorded instead in
this packet and in each live sample's request metadata.

- `validation_verdict` is computed exactly as before, from the merged report; the merged report is
  the full `VALIDATION_CRITERIA` list in the canonical order, and `merge_validation_reports` raises
  `GenerationRejected("validator omitted criteria: …")` rather than accepting a smaller review.
- Recorded outcome in every passing sample: `model_assessed`, `independent: false`,
  `independence: unidentified` (the stored home does not record the author model, so no same-model
  claim is made), never upgraded. `verdict_outcome_is_not_upgraded` = true.
- `enforce_plan_rules`, the answer-leak rule and `assert_separate_pass` are untouched;
  `assert_separate_pass` now runs against **every** validation pass before any is sent.
- A lost or timed-out pass fails the whole validation (`needs_retry`); a partial criteria set is
  never merged or recorded as a review.
- `COURSEBOOK_PLAN_VALIDATE_TIMEOUT_SECONDS` / `PROVIDER_TIMEOUT_SECONDS` are unchanged.

## Tests

`python3 -m unittest discover -s tests -t .`

```
Ran 2457 tests in 446.297s

FAILED (failures=8, skipped=1)
```

The 8 failures are **pre-existing on this branch's base** (`wt/h190-plan-identity` @ `71f74e7`),
not introduced by this change. Reproduced in a clean checkout of that commit:

```
Ran 189 tests in 12.212s

FAILED (failures=8)
```

They are `tests.test_contracts.V3AmendmentTest.test_v3_payloads_are_validated_before_any_handler`
(`review.queue` / `evidence.inspect` / `evidence.disputes` return `INTERNAL_ERROR` where the
contract test expects `NOT_FOUND`) and 4 ×
`tests.test_harness_e2e.PacketManifestTest.test_fresh_evidence_reproduces_the_committed_bytes`
(stale committed harness-e2e evidence digests). Both are outside this card's file scope.

Suite with the two classes that carry those pre-existing failures excluded (13 tests: the 8 failing
plus 5 that pass inside the same classes), so this branch's own coverage is proven green:

```
Ran 2444 tests in 365.280s

OK (skipped=1)
```

Focused coverage for the new shape: `tests/test_h191_validation_demand.py` (13 tests) pins the
partition, the narrowed schema's ownership refusal, the full ten-criterion merge, the
lost-pass-fails-all rule, the shared call-ceiling reservation and the parallel runner.


## Residual risk (escalate, do not paper over)

The validator route's reasoning length varies run to run: two of three post-change draws returned
inside 180 s, one did not. A hard fit needs a host-level reasoning-effort control for the
`chat_completions` route (the `max_tokens` cap is not it, proven above) or a faster validator
route. This should go to Atlas before the three-scope acceptance (H-192) treats `plan.validate` as
bounded.
