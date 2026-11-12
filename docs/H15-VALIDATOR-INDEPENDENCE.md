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
| Identity is classified | `validation_independence(generator, validator)` reads the identities the provider **reported** and compares their **canonical** models through `MODEL_ALIASES`: one canonical model -> `same_model`; two different canonical models -> `independent`; missing on either side -> `unidentified`. A name absent from the table is its own canonical identity, and no prefix or suffix is stripped by pattern (CB-independence). `validation_independence_detail()` returns the same state plus the `canonical {generator, validator}` pair the verdict carries |
| A pass is typed | `validation_verdict()` returns `independence`, `independent`, `facts_unverified`, `waived_unknown`, `outcome` alongside `verdict`. `independently_validated` requires `independent` **and** `research_status != "unavailable"`; any other pass is `model_assessed` |
| Draft means validated | `run_plan_job` sets `generation_state = draft` only for `independently_validated`; `model_assessed`/`rejected` park it `needs_review`. `plans.state` keeps the frozen `draft/approved/superseded` enum (approval binding is H-12) |
| Cross-model path | `bind_validator_llm(ctx.llm, provider=..., model=...)` builds a `PluginLLMAdapter` that passes `provider`/`model` to `ctx.llm.complete_structured(...)`. Settings: `validator_model`, `validator_provider` in `plugins.entries.coursebook.settings`, read once in `register(ctx)` |
| Trust refusal | A host `PluginLlmTrustError` on an override becomes `GenerationRejected` naming `allow_model_override` / `allow_provider_override`, `allowed_models` / `allowed_providers`. No silent fallback to the author model |
| No second model | `validator_llm()` is `None`; validation still runs on the author model (different prompt/schema), the record says `same_model`, the artifact is `model_assessed`. A documented refusal, not a fake opinion |
| Support upgrades | `apply_support_verdicts(..., independent=False)` refuses every upgrade by default. With `independent=True` it also requires an `evidence_quote` that appears verbatim in the fetched excerpt after case/whitespace normalisation. `VALIDATION_SCHEMA.claim_verdicts[].evidence_quote` is the new optional field |
| Facts gate | `research_status == "unavailable"` means the best outcome is `model_assessed`, even if the validator answers every criterion `pass`. Waived unknowns are stored as `waived_unknown` and close the gate |
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

## Integration onto the blueprint-v11 line (H-36)

H-15 was authored on `b4da6d9`, before H-13/H-14/H-20/H-21/H-35. It was merged onto `f990cad`
(`cb.rpc` v11, `cb.db` v7). The merge conflicted in five files and 21 hunks; each was resolved as a
semantic union, never `ours`/`theirs`:

| File | Hunks | Resolution |
|---|---|---|
| `coursebook/generation.py` | 12 | Union. `_Usage.summary()` keeps the cost-ceiling keys (`unknown_calls`, `estimated_cost_usd`, `budget`) **and** gains `by_purpose` plus `cost_for()`; `validation_verdict()` takes both `ledger` and `independence`, keeps the H-14 provenance lint and adds the H-15 facts gate and typed outcome in one return dict; `ensure_schema()` keeps the v6/v7 migrations **and** the validator-identity ALTERs; `plan_document()` returns the declared v10 inputs **and** `validation`/`approval`; `run_plan_job` keeps H-21's blueprint `units`/`sections` split **and** H-15's `draft`-only-for-independent rule; the result carries `plan_schema` **and** `validation`/`approval_provenance`; `_plan_warnings` keeps the unavailable/degraded sentences and adds the `facts unverified, no sources` sentence; the lesson insert keeps H-35's `review_target` guard and uses H-15's `audit_state = pending` for `model_assessed` |
| `coursebook/research.py` | 3 | One gate, not two. H-14's `claim_verdict_link_problem` (12-character floor, verbatim match) stays the single link rule and now reads `evidence_quote` first with `excerpt` as the older alias; H-15's `independent` precondition stays in `apply_support_verdicts`. H-15's `_normalize_evidence` was removed rather than left dead: H-14's `_normalize_quote` is the stricter (case-sensitive) comparison |
| `docs/GENERATION.md` | 2 | Both §4 bullets and §4a kept; §5a (declared inputs) kept and §5.1 (approval/learner provenance) appended |
| `tests/fixtures/generation/validation_pass.json` | 1 | `evidence_quote` (the schema's field) with the full sentence, which satisfies the 12-character floor |
| `tests/test_generation.py` | 3 | One union test keeps every H-14 link assertion and adds the same-model refusal; the untracked-source and rejected-plan fixtures use `evidence_quote` |

Two union decisions changed behaviour rather than only text:

* **The quote test is the union of both rules.** H-14 requires at least 12 characters; H-15's own
  fixtures quoted a five-character word (`こんにちは`). The floor wins, because it is the defence
  against a one-word "quote", so the H-15 test and fixture quotes were widened to a verbatim span
  from the fetched excerpt. No assertion was dropped: a verbatim quote still upgrades and an
  invented or same-model one still does not.
* **`needs_review` is the human review, not a permanent refusal.** H-15's `docs/CONTRACTS.md` text
  (written before H-12 landed) said a `model_assessed` plan may still be approved by a human, while
  H-12's `domain._plan_validation_source` refused any `generation_state != "draft"` — which, on this
  line, is every plan generated without a configured second model. The spec makes plan approval a
  human event (`PREBUILD_SPEC.md` §5, §7), so the gate now refuses only a `rejected` or unvalidated
  artifact and returns `model_assessed_pass` for a durable passing record whose validator was not
  independent. `plans.state` and the wire are unchanged; an independently validated plan is still
  `generated_validated`. `tests/test_plan_approval.py::test_model_assessed_pass_is_approvable_by_a_human_with_its_warning`
  pins it.

The H-21 unit-sections stage (`run_unit_sections_job`) postdates H-15, so it had none of the
identity plumbing. It now binds the same `validator_llm() or llm` route, computes
`validation_independence` from the two responses, passes `generation_response` to
`_record_validation`, and stores `state = validated` only for `independently_validated`.

### Merged-line evidence

```
$ python3 -m unittest discover -s tests -t .
Ran 1276 tests in 325.6s
OK

$ node --check desktop/plugin.js
syntax OK            (desktop/plugin.js is untouched by this merge)

$ bash scripts/validate-plugin.sh --worktree
Release gate passed: 3/3 checks (1278 files)

$ bash scripts/validate-plugin.sh            # clean `git archive` export of the merge commit
Release gate passed: 3/3 checks on the 1280-file HEAD export
```

Master was 1264 tests; H-15's 11 regressions plus one new approval regression make 1276.

## Deliberate non-changes and the missing wire seam

* `plans.state` was not widened: its CHECK constraint is `draft/approved/superseded`, and binding
  `plan.approve` to the validation record is H-12's work. H-12 has since landed; the integration
  section above records how the two rules were reconciled without a new kernel state.
* `rpc.v9` request/response schemas are frozen and strict (`additionalProperties: false`), so no
  new field was added to `plan.approve`, `course.outline` or `lesson.page`. The warning reaches the
  job result (already an open payload) and the plugin's own read functions. Surfacing it in the
  Desktop wire response needs a later contract card; inventing a field on a frozen version would
  fail response validation. (Merged line: `cb.rpc` v11 is current and still carries no such field;
  the exact additions a future version needs are listed in `docs/CONTRACTS.md`.)
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
