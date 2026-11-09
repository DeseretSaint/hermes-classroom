# H-192 — three-scope live acceptance on the repaired tree

Status: **FAIL (0/3 scopes reached an approvable plan)** on base `7916ade` = `origin/master`
`127cce1` (the H-191 union: `6798e47` item-label repair + `a0fa6e0` one-bounded-validation-pass,
plus H-195's quality contract) with this card's evidence packet on top.
Auditor: sentinel. Date: 2026-11-08. Product code changed: **none**.

## Base

| requirement | state |
|---|---|
| H-190 plan identity | on base (`796ec07` is an ancestor) |
| H-187 fix 1: scope-scaled request bound | on base (`0957ca6` ancestor via `796ec07`) |
| H-187 fix 2: H-89 vocabulary rule gated on declared language | on base (same merge) |
| H-191 item-label repair (t_244cdbf7) | merged here as `cde101d`, carried to master by `6263b58` |
| H-191 validate-demand (t_027b48f4) | merged here as `008f5d9`, carried to master by `6263b58` |
| H-195 quality contract | on base (`4e23855`) |
| `git merge-base --is-ancestor origin/master HEAD` | **yes** (`127cce1`) |

Merge note: `wt/h191-validate-demand` and `wt/h191-item-label` both edit
`coursebook/generation.py`. The conflict was the `_Usage.record` body: the demand branch had moved
the ledger write under the new `_lock`; the item-label branch added the `outcome` field
(`returned` / `schema_rejected`). Resolution keeps the lock and the field
(`cde101d`). The `audit/adversarial/harness-e2e/` evidence conflicts were resolved by re-deriving
the packet on the merged tree (later superseded by master's own re-derivation `127cce1`).

Test-only integration defect found by the union and fixed on this branch (`f79d225`, now on
master): `tests/test_validation_shape_repair.py`'s recorded fixtures carried an empty
`claim_verdicts`, which the narrowed pass schema now rejects (`[] is too short`, `minItems = 5`).
The fixture claim set is now derived from the request's narrowed pass schema, so the shape under
test is still the measured 81-char `item`. Suite on the merged base before the master merge:
`Ran 2467 tests in 449.351s` -> `OK (skipped=1)`.

## Method

Fresh isolated `HERMES_HOME` per scope (`/home/deseretsaint/.hermes/h192-live-acceptance/<scope>`),
seeded with a `config.yaml` only — no demo pack, no recorded transcripts, its own SQLite store.
Real product path: `course.create` -> `enrollment.create` -> `jobs.create(stage=plan)` ->
`executor.pump_once` (real bounded tick) -> `plan.approve` -> `jobs.create(stage=lessons)` ->
`lesson.page`. `ctx.llm` is the host `agent.plugin_llm.PluginLlm`; the validator is a second host
route (`nous / z-ai/glm-5.3-flash`) bound through `generation.bind_validator_llm`; research is the
host's own `web_search`/`web_extract` through `coursebook.research.HermesToolSearch`. No transcript
was edited and no fixture model was used.

Command (serial driver; the parallel driver is committed for reference and was used for the
concurrent samples):

```
./audit/adversarial/live-generation-2026-11-08-h192/run_scopes.sh
PYTHONPATH=. python3 audit/adversarial/live-generation-2026-11-08-h192/build_evidence.py
```

Deadlines are the documented operator knob (`PROVIDER_TIMEOUT_ENV`), not a rule change. Three
settings were used and each attempt is retained: 420/300 s, then 600/600 s serial, then 600/600 s
concurrent. The per-job stop in the worker was 900 s, then 1100 s.

## Per-scope table (latest capture per scope, all on `127cce1`)

| scope | recipe | rerun | plan job | research | objectives | units | validation.outcome | independence | rejections | approve | lessons | page |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| single | one_off | 1 (420/300 s) | failed 642.3 s, `HOST_UNAVAILABLE` plan.validate >300 s | ok, 4 sources | 0 (no document) | 0 | — | — | none written | refused (`plan_empty`) | not started | none |
| single | one_off | 2 (600/600 s serial) | failed 648.3 s, `HOST_UNAVAILABLE` plan.validate >600 s | n/a (no document) | 0 | 0 | — | — | none written | refused (`plan_empty`) | not started | none |
| short | committed | 1 (600/600 s concurrent) | not terminal when the run was stopped | — | — | — | — | — | — | — | — | none |
| full | committed | 1 (600/600 s concurrent) | failed 598.3 s, `INTERNAL_ERROR` (validator answer violated `claim_verdicts`) | real pages fetched, some extract failures | 0 (no document) | 0 | — | — | none written | refused (`plan_empty`) | not started | none |

Measured provider facts from the usage ledger (`usage_events`, tokens redacted in the packet,
raw counts quoted here):

- single rerun 1: `plan.generate` 324 965 ms / 7 727 completion tokens; the validate call never
  returned before its 300 s deadline.
- single rerun 2: `plan.generate` 40 454 ms; the validate call exceeded **600 s** with no answer.
- full (concurrent): `plan.generate` 131 245 ms / 16 747 tokens; `plan.validate`
  **376 896 ms / 29 386 completion tokens**, and the answer then **violated the validation
  schema** at `claim_verdicts` (first stored reasons show per-objective verdicts for
  `objective:1`, `objective:2`, `objective:3`, ...).
- Models: author `nous / deepseek/deepseek-v4.1-flash-1017`, validator
  `nous / z-ai/glm-5.3-flash` — genuinely different, and recorded in every validation binding.
  Cost is unknown on this route (`cost_usd: null`), recorded as `unknown_cost: true`, never zero.

## What this establishes (and what it does not)

- Approvable plan: **0/3**. `plan.approve` never ran against an authored plan on the card's base,
  because no scope produced a plan document. There is no `independently_validated` sample from this
  run to report; that is a result, not a gap in measurement.
- Lesson page: **0/3**. A `lesson.page` cannot be served when the plan stage never completes.
- Research: never `unavailable`; the runs fetched real pages, with individual extract failures
  recorded (one firecrawl 504, one "Website Not Supported") and the research seam continued.
- The H-191 demand narrowing is present (`validation-prompt.v4`, one pass, ten criteria, claim
  labels bounded to the plan's own claims) and it is **not sufficient**: on this base the full
  scope's bounded claim set scales with plan size (13+ labels for a 12–40-objective plan) and the
  validator produced 29 386 tokens in 377 s before failing its own schema, while single scope
  exceeded a 600 s deadline twice with no answer.

## Deterministic causes (each named, none softened)

1. **`plan.validate` is still unbounded in wall time and in total output.** The bounding added by
   H-191 is per claim label, not in the number of labels; a `full` plan carries one verdict per
   objective (12–40) plus units and the learner outcome. Measured: 29 386 completion tokens in
   377 s, schema-invalid; single scope: >600 s with no answer. The route still does not forward
   `max_tokens`, so no cap applies.
2. **The full-scope validator answer violates `claim_verdicts`.** The job records
   `INTERNAL_ERROR` ("plan validation violates its schema at claim_verdicts") and loses the whole
   call; the operator sees a generic internal error for an output-shape problem. `cb.errors` has
   `VALIDATION_FAILED` for exactly this and the H-191 item-label work already reports shape
   violations that way — the plan-stage claim-set violation does not.
3. **A content rejection is reported as an internal retryable error.** Separate observation from a
   cross-check run on `11640bb` (knife-sharpening single scope): the unit-sections validator
   refused an unsafe delivery with a concrete reason, and the job surfaced
   `INTERNAL_ERROR / retryable: true` because `GenerationRejected` carries no contract code. A
   validator rejection is not a backend failure.
4. **Harness bug found and fixed here (not product):** the H-187-era worker sent
   `plans.plan_hash` (the generation digest) to `plan.approve`, which fences on the kernel digest
   recomputed from the plan rows. The desktop reads `parent.blueprint.read` at approve time
   (`desktop/plugin.js` `approvePlan`); the worker now does the same and records both digests. This
   is why the first capture was refused `VALIDATION_FAILED: the approved hash does not match`.

## Honest limits of this packet

- `short` has no terminal capture on `127cce1`: the concurrent run and the serial run were both
  stopped at the card's wall-clock limit while the plan stage was still running. Nothing about
  `short` is claimed.
- The evidence captures are the worker's own records of stored rows plus RPC answers; the raw
  provider responses are not kept (the host returns text to the plugin only). Token counts are
  redacted in `evidence/summary.json`, `/home/...` paths are replaced with `<ISOLATED_HOME>`;
  the per-attempt raw captures are kept outside the tree (they carry real home paths and token
  counts) and are **not** covered by the manifest.
- Three scopes ran concurrently in one sample, so that sample's latency is concurrent, not serial.
  The `single` rerun 2 and the deadline figures quoted above are serial.

## Files

- `worker.py` — the real-path driver (one scope, one home), with the kernel-digest fix.
- `run_scopes.sh` — serial driver, 600 s operator deadlines.
- `run_scopes_parallel.sh` — concurrent driver, same deadlines.
- `build_evidence.py` — redacts, checks the card's acceptance predicates, writes
  `evidence/summary.json` + `evidence/manifest.json`.
- `evidence/{single,full}.json` — latest capture per scope (raw worker output).
- `evidence-attempt1..4/` — earlier captures, kept so every quoted number is reproducible.
