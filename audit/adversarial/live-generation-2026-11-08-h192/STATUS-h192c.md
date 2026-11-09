# H-192c — the validator's output is bounded on the nous route

Status: **DECIDED AND IMPLEMENTED**. Branch `wt/h192c-output-cap`, base `cb/t_958c3f23` @
`c58c05a`. Product code: `coursebook/generation.py`, `coursebook/tools.py`, `__init__.py`, plus
the H-192 audit driver (`audit/.../worker.py`). Tests:
`tests/test_h192c_validator_output_bound.py` (new, 8) and `tests/test_platform_config.py` (status
contract updated). No contract, schema or RPC change.

## The decision

The measured defect is **route-level, not demand-level**. H-192b bounded what a pass asks for
(five criteria, at most six claims on a criteria pass, twelve on a claim-only pass) and every
answer in the run was schema-valid — yet one five-criteria pass still emitted 19 739 completion
tokens in 927 s. What was unbounded was the validator's own reasoning, because the host drops
`LLMRequest.max_tokens` on the nous chat-completions route
(`agent/auxiliary_client._forwards_max_tokens` deliberately lists only routes where the parameter
is mandatory or proven honoured).

Two ways out were named on the card. **Forwarding `max_tokens` in the host was rejected**: it
requires patching the runtime the plugin ships into, and the earlier measurement already showed a
forwarded 2 000-token cap consumed entirely by reasoning and returning *no* content. A cap alone
truncates the answer without bounding the reasoning.

**Chosen: a provider-level reasoning budget plus a completion cap, delivered through the host's
documented plugin seam.** A plugin may declare its own auxiliary task with
`ctx.register_auxiliary_task(key, defaults=...)`; `reasoning_effort` and `extra_body` in those
defaults are merged into the provider body by the host's own code
(`hermes_cli/plugins_aux_tasks.py` → `agent/auxiliary_task_config.py` →
`agent/auxiliary_client._get_task_extra_body` → `_build_call_kwargs`), on the same route that
drops the `max_tokens` argument. No private import, no host patch.

- `VALIDATION_AUX_TASK = "cb_validate"` — declared at register time (before the validator adapter
  is bound) with `reasoning_effort: "low"` and `extra_body: {"max_tokens": 4000}`.
- Every validation call passes `task="cb_validate"` — the configured second-model route *and* the
  author-model fallback (`validation_llm()`), because an unbounded answer is the same defect on
  either route. Authoring calls do not carry the key.
- A host without `register_auxiliary_task`, or one that refuses the key, leaves validation
  uncapped **and says so**: `validator_config()["output_bound"]["registered"]` is `false` and
  `coursebook_status` reports it. No silent “bounded” claim.
- `LLMRequest.max_tokens` for all three validation requests now declares the same 4 000, so the
  request and the wire agree.

## Evidence

### Live wire probe (nous / z-ai/glm-5.3-flash)

Identical demand — five criteria, six claims, the real `VALIDATION_SYSTEM_PROMPT` — through the
real `PluginLlm`, with `cb_validate` registered by the host's own
`PluginContext.register_auxiliary_task`:

| call | elapsed | completion tokens | answer |
|---|---|---|---|
| no task key (pre-H-192c) | 105.7 s | 6 114 | 5 criteria + 6 claims |
| `task="cb_validate"` | 11.6 s | 566 | 5 criteria + 6 claims, schema-valid |

9.1× less wall time, 10.8× fewer completion tokens, same schema-valid answer. The route accepts
both fields (no reasoning-field rejection, no fallback to the author model).

### Deadline enforcement probe

`PluginLLMAdapter` still raises `ProviderTimeout` at the declared bound on both invoke paths
(async sibling and sync-only host), measured at 1.00 s against a 1.0 s deadline. The live 927 s
overrun therefore happened *inside* the host call, not in the adapter; the cap removes the
unbounded answer that produced it, and the adapter's own bound remains the outer stop for a call
that returns.

### Live pipeline probe (real plan, real orchestrator)

The H-192c single-scope live run wrote a real plan document (`pln_dc2fa957…`, 5 249 bytes) but
the plan job was parked `needs_review` by the deterministic note-length gate
(`check_plan.notes is 300 characters, at its 300-character cap`) **before** any validator call,
so that run measured no validation. The same plan document was then driven through the plugin's
own validation path — `build_plan_validation_requests` → `_run_validation_passes` →
`cb_validate` → nous / z-ai/glm-5.3-flash:

| pass | criteria | provider/model | completion tokens | text |
|---|---|---|---|---|
| 1 | 5 | nous / z-ai/glm-5.3-flash | 403 | 1 376 chars |
| 2 | 5 | nous / z-ai/glm-5.3-flash | 280 | 1 125 chars |

Both passes together: **11.2 s wall**. The H-192b live run's equivalent single-scope validation
was 3 004 + 9 881 tokens over 43.8 s + 344.8 s. `output_bound.registered` was `true` in the run's
own seam log (`cb_validate`, low, 4 000).

### Suite

- New: `tests/test_h192c_validator_output_bound.py` — 8 tests, **OK**.
- Updated: `tests.test_platform_config.ValidatorStatusTest` — **OK** (4 tests).
- Full suite on this tree: `Ran 2504 tests … failures=26, errors=132`.
- Same suite on the untouched base `c58c05a`: `Ran 2496 tests … failures=23, errors=132`.

The +8 tests are the new file; the 23 failures and 132 errors are **pre-existing on the base
tree in this environment** (scripted-fake mismatches such as
`test_syllabus_import` reporting `VALIDATION_FAILED` for a scripted answer). No new failure is
attributable to this change. The parent's recorded `Ran 2506 tests … OK` was produced under a
different runner environment; the honest statement here is base-vs-branch parity, not green.

## Residual risk

- **Truncation is a hard failure, not a soft cap.** A pass that exceeds 4 000 completion tokens is
  cut by the provider (`finish_reason=length`), and the shape gate reports `VALIDATION_FAILED`
  (non-retryable). At measured low-effort reasoning (~300 tokens) a full ten-verdict answer is
  ~1 500 tokens, so the margin is over 2×; a pathological answer fails loudly rather than silently
  overrunning.
- **Unit and lesson validation still ask ten criteria in one pass.** They now carry the same cap,
  but the measured 23 096-token answer on `unit_sections.validate` shows that demand is the next
  thing to split if a pass ever hits the cap. That is a demand change, not a route change; it is
  not in this card.
- **The budget is a default, not a pin.** An operator who configures
  `auxiliary.cb_validate.reasoning_effort` / `extra_body` in the profile can override it, which is
  the host's documented precedence (user config over plugin defaults).
- **Host coverage.** The bound needs a host that exposes `register_auxiliary_task` — verified on
  `~/.hermes/hermes-agent` @ `c02e6e0180`. Older hosts are reported as unbounded rather than
  failing.
