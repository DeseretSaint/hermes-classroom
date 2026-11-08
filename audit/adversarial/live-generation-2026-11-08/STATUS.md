# H-187 — live generation on the merged tree: single, short and full

Base: `origin/master` = `80eecce` (2026-11-08). Branch `wt/h187-live-gen`. Two deterministic
blockers were found live and fixed on this branch (154 tests pass); the three scopes did **not**
reach an approvable plan, because the second provider call of every plan job
(`coursebook.plan.validate`) does not return inside its declared deadline. This card is **not**
green: the per-scope table below says so plainly.

## What was run

Fresh, isolated homes with no demo pack and no recorded transcripts:
`~/.hermes/h187-live-gen/{single,short,full}/home`, each with its own SQLite store. The product
path was driven, not a fixture: `course.create` -> `enrollment.create` -> `jobs.create(stage=plan)`
-> the real `executor.pump_once` -> `plan.approve` -> `jobs.create(stage=lessons)` ->
`lesson.page`. Seams bound the same way `register(ctx)` binds them: `agent.plugin_llm.PluginLlm` as
`ctx.llm`, a second host route as the validator, and `coursebook.research.HermesToolSearch` over
the host `web_search`/`web_extract` tools. No transcript was edited and no `FakeLLM` was used.

| scope | recipe | author | validator | outcome |
|---|---|---|---|---|
| single | one_off | nous / `deepseek/deepseek-v4.1-flash-1017` | nous / `z-ai/glm-5.3-flash` | plan authored `draft` (344 s); `plan.approve` refused — the authored plan is stored under a different plan id than `course.plan_id` (finding 3) |
| short | committed | nous / `deepseek/deepseek-v4.1-flash-1017` | nous / `z-ai/glm-5.3-flash` | failed: `plan.validate` exceeded its 300 s deadline (job 644 s) |
| full | committed | nous / `deepseek/deepseek-v4.1-flash-1017` | nous / `z-ai/glm-5.3-flash` | failed first on the request bound (fixed here); after the fix, `plan.validate` exceeded its 180 s deadline (job 304 s) |

Research reached `ok` on the runs that got that far (real `web_search` results, real fetches; a
firecrawl 504 on some URLs is recorded as a fetch failure, not as a source). No scope reached
`plan.approve`, so `plan.approve` refused with `VALIDATION_FAILED: an empty plan cannot be
approved` — the refusal is the honest record, not a plan that was approved.

## Deterministic defects found live and fixed here

1. **The request-byte bound refused a legal full-scope plan before any model call.**
   `full` run 1 failed with `request payload is 28154 bytes compact, over the 24000-byte request
   bound` (`HOST_UNAVAILABLE`/internal, retryable). The bound is a local JSON-safety guard, not a
   provider limit, and a full-scope deep pass legitimately carries more research than a
   single-sitting plan. Fixed: `REQUEST_BYTES_BOUNDS` / `_request_bound(scope)` scale the guard
   with the declared scope (`single`/`short` 24 000, `full` 48 000); an absent scope keeps the
   historic bound. Pinned by
   `tests/test_generation.py::BoundedRequestInputTest::test_the_bound_scales_with_a_full_scope_brief`.

2. **The H-89 vocabulary rule was applied to non-language plans, with no legal path.**
   `short` run 1 (a cooking course, no locale) was refused twice — once, then again after the
   rule-feedback retry — with 18 reasons of the form
   `objective N declares target item '…' but no frequency inventory is available`. The plan prompt
   carries **no** vocabulary block for a non-language brief (`_frequency_block` returns `None`), so
   the author was never told not to set `target_items` and the rule could never be satisfied. The
   job ended `needs_review` / `rejected` without the validator ever being called
   (`validator.known=false`). Fixed: the rule runs only when the brief declares a language
   (`if locale:` at both call sites), so a language course keeps the rule exactly as strict.
   Pinned by `tests/test_h187_vocabulary_gate.py` (2 tests).

3. **A live-authored plan is stored under a different plan id than `course.create` returns.**
   Measured on the `single` run that did finish: `course.create` returned
   `plan_id = pln_f91cb3ef…` (the course's own `draft` row, created 17:39:11Z) while the plan job
   persisted the authored document and its objective under **`24edbf47fbf71ba7`** (created
   17:44:55Z). `gen_plan_documents` points at `24edbf47…`, so `plan.approve(plan_id=pln_f91cb3ef…)`
   — the id the Desktop uses — reads an empty plan and refuses with
   `VALIDATION_FAILED: an empty plan cannot be approved; it has no objectives`. The Desktop's
   `planJobBrief` sends `{stage, course_id, enrollment_id, goal, recipe, dials, …}` and no
   `plan_id`, so the product path has the same shape as this harness. Not fixed on this branch:
   it changes which plan row a generation writes, which needs its own tests and a decision about
   the pre-existing `pln_…` row.

## The remaining blocker (why this card is not green)

Every plan job that got past generation died in `coursebook.plan.validate`:

| run | first call | second call | job end |
|---|---|---|---|
| single 10:24 | generate OK | `plan.validate` 180 s deadline | `failed` at 236 s |
| short 10:21 | `plan.generate` 240 s deadline | — | `failed` at 244 s |
| short 10:28 | generate OK (deadline raised to 420 s) | `plan.validate` 300 s deadline | `failed` at 644 s |
| full 10:21 | generate OK | `plan.validate` 180 s deadline | `failed` at 304 s |

The provider itself is healthy: a 16 004-byte structured validation request answered on the bound
validator in **13.4 s** (`z-ai/glm-5.3-flash`), 4.9 s (`moonshotai/kimi-k3`) and 12.8 s
(`qwen/qwen3.8-flash`), and the v2 plan *schema* with a small input answered in 11.2 s. So neither
the schema nor the model route explains a 300 s stall on the real request. What is measured is the
stall, not its mechanism: the deadline is enforced by the caller while the abandoned provider call
keeps running (the H-66 / D-H63-3 class), so the next call in the same job can also starve its
worker slot. Instrumenting the exact validation request bytes and the worker-pool occupancy is the
next step; it is not something this card can claim.

## Reproduce

```bash
# one scope, isolated home, real path (validator + author model bound as above)
HERMES_HOME=~/.hermes/h187-live-gen/short/home \
  HERMES_DISABLE_LAZY_INSTALLS=1 HERMES_AGENT_ROOT=~/.hermes/hermes-agent \
  COURSEBOOK_SOURCE=<this worktree> H187_VALIDATOR_PROVIDER=nous \
  H187_VALIDATOR_MODEL=z-ai/glm-5.3-flash \
  ~/.hermes/installs/4d8bf4040d63cdfa/environments/12913d7d436b4c0fb0877aaefcb88e69/venv/bin/python \
  audit/adversarial/live-generation-2026-11-08/worker.py --tag repro \
  --title "Plan and cook a high-protein week" \
  --goal "Plan and cook a week of high-protein meals without repeating a dish" \
  --recipe committed --scope short --subject-domain general --depth working \
  --units 1 --max-seconds 900 --result /tmp/h187-repro.json
```

`run_scopes.sh` and `run_single_after_short.sh` are the exact drivers used for the serial runs
(they only raise the documented per-purpose deadline env knobs; no rule, cap or bound changes).

## Files

- `worker.py` — the harness (real seams, real dispatcher, real `pump_once`, approve, lessons, page).
- `build_evidence.py` — per-scope packet + `manifest.json` of sha256 hashes (tokens redacted,
  absolute paths redacted).
- `evidence/{single,short,full}.json` — raw captures (timeline, job view, error, usage).
- `evidence/summary.json`, `evidence/manifest.json` — redacted packet and hashes.

## Tests

`python -m unittest tests.test_h187_vocabulary_gate tests.test_frequency
tests.test_plan_prose_caps tests.test_generation tests.test_blueprint_units
tests.test_learner_plan_flow` → `Ran 154 tests in 9.223s` / `OK`.
