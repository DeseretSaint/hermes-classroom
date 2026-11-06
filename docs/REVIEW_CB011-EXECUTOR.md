# Review packet — CB-011 executor + authored parent export (t_a356c8a8)

Status: **implemented locally, nothing pushed**. Branch `wt/cb-011-cinder-executor` cut from the
frozen contract branch `wt/cb-011-atlas-contract-v6` @ `ebf1ecf` (which is rebased onto `master`
`8335b5c`). Owner: Cinder. Consumes `cb.rpc` v6 / `cb.db` v3; implements the two gaps the contract
freeze named for this card.

## What changed

| File | Change |
|---|---|
| `coursebook/executor.py` | **new**. One resolver under the key `plan`, dispatching on `brief.stage` (`plan` / `lessons`), a bounded `pump_once`, and an asyncio tick started from `register(ctx)`. Reuses `job_service.run_pending` — no second job engine. |
| `coursebook/parent_authoring.py` | **new**. One implementation of the plan digest, the served tab text, the v6 `content_hash`, the authored `cb.pack` document and the handout PDF lines. Shared by `parent.blueprint.read`, `parent.final.approve` and `parent.export`. |
| `coursebook/domain.py` | Seven v6 handlers (`parent.brief.create/get`, `parent.plan.edit`, `parent.final.approve`, `parent.blueprint.read`, `parent.reflection.record/list`) plus the `parent.export` dispatcher; `_plan_hash` now delegates to `parent_authoring.plan_hash` (one digest, no drift); `record_objective`'s insert extracted so `parent.plan.edit` writes objectives through the same code path inside its own transaction. |
| `coursebook/pack_flow.py` | `parent_export` builder: refusal on stale approval, pack + PDF staged outside any transaction, atomic artifact adoption with a hash re-check inside the fenced write. |
| `coursebook/research.py` | `bind_host_seam(ctx)` / `host_search()`: the agent half binds the host once; the executor uses the host's own `web_search`/`web_extract` (unavailable is recorded honestly, never replaced by an invented source). |
| `__init__.py` | Binds the research seam and calls `executor.start_tick(ctx)`. |
| `tests/test_kernel_v2.py` | `pending_v6` allowance shrunk to empty, as Atlas required. |
| `tests/test_parent_studio.py` | **new**, 17 offline tests. |

## The executor seam

* `jobs.create({kind: "plan", brief: {...}})` — plan stage. The brief must carry `goal`,
  `recipe`, optional `dials`/`locale`; `parent.brief.create` stores a full parent brief with
  `stage: "plan"`.
* `jobs.create({kind: "plan", brief: {stage: "lessons", plan_id: "pln_..."}})` — lesson stage. The
  plan must be `approved`; `generation.run_lesson_job` refuses otherwise.
* The tick is bounded: `MAX_JOBS_PER_TICK = 5` (same number as `run_pending`'s default),
  `TICK_SECONDS = 5` overridable with `COURSEBOOK_JOB_TICK_SECONDS`. It starts only when the host
  exposes `ctx.spawn_task` and is stopped by `ctx.on_unload`. `pump_once()` is the synchronous unit
  a test or a doctor calls.
* State machine is the existing one: `queued → running → completed | failed | cancelled |
  completed_late`, lease/checkpoint rows unchanged, `jobs.cancel` on a queued job spends nothing,
  a cancel that arrives during a provider call closes as `completed_late` with the real usage rows,
  and a dead worker becomes `interrupted_requires_retry` with its checkpoint at the next startup
  reconciliation.
* Usage is recorded once by the generation pipeline against the job id (`usage_events.operation_id`);
  the stage returns an empty `StageResult.usage` on purpose, so nothing is double-counted.

## The export seam for Vellum

`parent.export({enrollment_id, formats?: ["pack","pdf"]})` with an envelope `idempotency_key`.
Response: `export_id`, `pack {pack_id, pack_version, manifest_hash}`, `files[]`
(`role|name|sha256|bytes|mime`), `artifacts[]` (`artifact_id|kind|mime|bytes|content_hash` for
`pack`, `pdf`, `export`), `content_hash`, `exported_at`. Fetch bytes with `artifact.get`; the
download handle is session-bound and no path is returned.

Refusals are `POLICY_VIOLATION` with `details.reason`:
`plan_not_approved` / `no_final_approval` / `changes_need_review` / `no_generated_content` /
`course_pack_backed` (imported pack → use `pack.export`) / `export_not_exportable` (pack minima) /
`export_write_failed`. The same reasons are derived in `parent.blueprint.read`'s
`export.blocked_reason`, so the panel can disable the button from storage.

`parent.blueprint.read({course_id})` returns the five tabs as declared text, the current
`content_hash`, the `approval` status and `export` status; it never emits a `path` property.

## Two contract nuances found while implementing (for Atlas)

1. **`narration` cannot be a text pack file.** `cb.pack` requires `audio/*` MIME for the
   `narration` role (`packs._role_mime_mismatch`), and media MIME also requires a per-artifact
   license plus a text equivalent. An authored course has a narration **script**, not audio. The
   builder therefore emits `parent_guide`, `learner_page`, `answer_guide` text files (the three
   roles the pack can legally carry) and puts the script in the `narration` tab of
   `parent.blueprint.read` and in the parent guide. No file claims a role/MIME pair the pack
   policy would reject, and `narration` is still in `packs.LEARNER_FACING_ROLES`, so a future audio
   export is a data addition, not a contract change.
2. **The pack teaching minima are stricter than generated lesson rubrics.** 
   `packs.validate_minima` requires at least three rubric criteria per check; a generated lesson
   currently carries one rubric criterion plus the plan's declared evidence criteria. The export
   composes the check rubric from **declared** criteria only (check rubric, plan evidence criteria,
   the lesson's supervision notes) and never pads; when the total is below three the export refuses
   with `export_not_exportable` and the minima problems. A follow-up card asks Atlas whether
   generated parent lessons should emit three criteria or whether the parent-observation check
   deserves a minima exemption; until then a course that does not meet the floor is refused rather
   than padded.

## Evidence

```
$ python3 -m unittest tests.test_parent_studio
Ran 17 tests in 2.9s
OK

$ python3 -m unittest discover -s tests -t .
Ran 625 tests in 57.7s
OK

$ node --check desktop/plugin.js
OK

$ hermes plugins validate .
Validation passed.
```

The 17 new tests cover: queued → completed plan through the pump with a fake LLM and fake search;
a cancelled queued job calling no provider; cancel during a stage → `completed_late` with real
usage; a killed worker → `interrupted_requires_retry` with the checkpoint and a resume that keeps
it; the one resolver dispatching the lessons stage; an unmigrated profile left unprovisioned;
`register(ctx)` starting exactly one tick only where `spawn_task` exists; brief idempotency; the
`lesson` job kind refused by payload validation; draft-only hash-then-revision plan edits; final
approval refusal before generation exists; a valid pack + PDF export with exact roles/file list,
zip re-hash, `%PDF-` header, `%%EOF` trailer, `Tj` text operators and reused artifacts on a repeat
export; `changes_need_review` after a page edit; and notebook/reflection text absent from every
pack entry.
