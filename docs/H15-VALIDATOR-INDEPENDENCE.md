# H-15: validator identity and the no-research factual waiver

Status: implemented on `wt/harness-validator-independence` (branch HEAD after this note). Parent:
`t_1efc158a` (`docs/ADVERSARIAL-AUDIT-ROUND2.md`, probes H10-3/H10-4). No provider was called and
no prepared pack was used as evidence.

## What was wrong

1. `assert_separate_pass()` compared a system prompt, a schema and a prompt version. It knew
   nothing about model or provider, so one injected callable served both the author and the
   validator and the pass was still called independent.
2. `apply_support_verdicts()` moved a source from `unverified` to `supported` on the validator's
   word alone, and the validator was the author model.
3. `validation_verdict()` allowed `source_support` and `factual_correctness` to be `unknown` when
   `research_status != "ok"` and still returned `verdict: pass`; the plan was stored as a draft
   presented as validated.
4. The sycophantic probe accepted "water boils at 50 C" because the same model wrote and passed it.

## What the code does now

| Concern | Implementation |
|---|---|
| Identity is recorded | `gen_validation_records` gains `generator_model`, `generator_provider`, `validator_provider`, `independence`, `facts_unverified`, `outcome`; `ensure_schema()` adds them to an older DB with `ALTER TABLE`, so old rows read as `unidentified`, never `independent` |
| Identity is classified | `validation_independence(generator, validator)` reads the identities the provider **reported**: same model name -> `same_model`; different known model names -> `independent`; missing on either side -> `unidentified` |
| A pass is typed | `validation_verdict()` returns `independence`, `independent`, `facts_unverified`, `waived_unknown`, `outcome` alongside `verdict`. `independently_validated` requires `independent` **and** `research_status == "ok"`; any other pass is `model_assessed` |
| Draft means validated | `run_plan_job` sets `generation_state = draft` only for `independently_validated`; `model_assessed`/`rejected` park it `needs_review`. `plans.state` keeps the frozen `draft/approved/superseded` enum (approval binding is H-12) |
| Cross-model path | `bind_validator_llm(ctx.llm, provider=..., model=...)` builds a `PluginLLMAdapter` that passes `provider`/`model` to `ctx.llm.complete_structured(...)`. Settings: `validator_model`, `validator_provider` in `plugins.entries.coursebook.settings`, read once in `register(ctx)` |
| Trust refusal | A host `PluginLlmTrustError` on an override becomes `GenerationRejected` naming `allow_model_override` / `allow_provider_override`, `allowed_models` / `allowed_providers`. No silent fallback to the author model |
| No second model | `validator_llm()` is `None`; validation still runs on the author model (different prompt/schema), the record says `same_model`, the artifact is `model_assessed`. A documented refusal, not a fake opinion |
| Support upgrades | `apply_support_verdicts(..., independent=False)` refuses every upgrade by default. With `independent=True` it also requires an `evidence_quote` that appears verbatim in the fetched excerpt after case/whitespace normalisation. `VALIDATION_SCHEMA.claim_verdicts[].evidence_quote` is the new optional field |
| Facts gate | `research_status != "ok"` means the best outcome is `model_assessed`, even if the validator answers every criterion `pass`. Waived unknowns are stored as `waived_unknown` and close the gate |
| Approval surface | Job result carries `validation` and `approval_provenance`; `plan_document()` returns `validation` and `approval.needs_review` / `approval.warning`. Warning text: `facts unverified, no sources: ...` |
| Learner surface | `learner_page()` serves a `model_assessed` lesson with `provenance = {outcome, independent: false, facts_unverified, check_enabled: false, warning}`; its check row is `closed` / `audit_state = pending`. `needs_review` lessons are still refused |
| Cost delta | `result["validation"]["cost"]` (`.validate` calls, known USD, `unknown_cost`) and `result["usage"]["by_purpose"]`; unknown cost stays `null` |

## Host seam evidence (live SDK source, read before coding)

`/home/deseretsaint/Projects/hermes-fork/agent/plugin_llm.py`

* `complete_structured(..., provider: Optional[str] = None, model: Optional[str] = None, ...)`
  (line 460) passes both into `_gate(...)`.
* `_TrustPolicy` (line 94) gates overrides with `allow_provider_override`, `allowed_providers`,
  `allow_model_override`, `allowed_models`, fail-closed (`_denied`, line 148).
* No other documented seam exposes a second model. The plugin never reads a provider key.

## Commands run on this branch

```
$ python3 -m unittest discover -s tests -t .
Ran 1051 tests in 155.9s
OK

$ python3 -m unittest tests.test_validator_independence -v
Ran 11 tests in 0.012s
OK
  IdentityTest (4): classification, override plumbing, trust refusal, no-config report
  SycophanticPassTest (3): same-model pass is model_assessed; same-model cannot upgrade support;
                           independent upgrade needs a verbatim quote
  NoResearchWaiverTest (3): waived unknowns close the gate; no-research plan is needs_review with
                            the warning; model_assessed lesson is readable, warned, check closed
  RecordedIdentityTest (1): cross-model pass records independent + cost delta

$ bash scripts/validate-plugin.sh --worktree
Release gate passed: 3/3 checks on b4da6d9 (1216 files)

$ bash scripts/validate-plugin.sh
Release gate passed: 3/3 checks on 312233e (1217 files)
  admission PASS; node --check desktop/plugin.js OK; 7 desktop contract tests OK
```

Baseline before this branch: 1040 tests on master (`b4da6d9`), same gate 3/3. The 11 new tests are
the net addition; `tests/test_generation.py` was updated where the old expectation encoded the
waiver (one-off plan with no search now expects `needs_review` + `facts unverified, no sources`).

## Deliberate non-changes and the missing wire seam

* `plans.state` was not widened: its CHECK constraint is `draft/approved/superseded`, and binding
  `plan.approve` to the validation record is H-12 (`wt/harness-plan-approval`). This card records
  the honest outcome and warning; it does not redefine approval.
* `rpc.v9` request/response schemas are frozen and strict (`additionalProperties: false`), so no
  new field was added to `plan.approve`, `course.outline` or `lesson.page`. The warning reaches the
  job result (already an open payload) and the plugin's own read functions. Surfacing it in the
  Desktop wire response needs the `rpc.v10` contract card (`wt/harness-contract-v10`); inventing a
  field on v9 would fail response validation.
* `coursebook/domain.py::_authored_lesson_page` still selects `state = 'validated'`, so a
  `model_assessed` lesson is not promoted into the RPC `lesson.page` payload. That is deliberate
  until the wire carries the warning: the plugin refuses to show an unmarked page rather than show
  one without provenance.
* No provider spend: every test uses a scripted fake or a fake host object. The cross-model test
  asserts the override keywords and the returned identity, not a real vendor call.

## Known residual risk

* A provider that reports the same model name for two genuinely different endpoints is classified
  `same_model`. That is the conservative failure: the artifact is under-claimed, never over-claimed.
* A model can still assert a false `evidence_quote` for a source it did not read; the quote must
  appear in the fetched excerpt, so the upgrade is tied to fetched bytes, but the excerpt itself is
  untrusted content (source-trust boundary is H-12).
* If the host's trust gate permits a validator override but routes it back to the author model, the
  observed identities make it `same_model`; the pass is model-assessed. Configuration is not proof.
