# CB-012 review packet — research, source ledger, artifacts and durable jobs

Owner: Cinder. Branch: `wt/cb-012-cinder` (this worktree). Base: `master` `df224b8` + a merge of
the CB-002 kernel branch (`wt/cb-002-cinder`), because this package implements behaviour on top of
the kernel tables and the kernel was not yet merged to `master` when the worktree was created.

## 1. What landed

| Deliverable | Module | What is actually enforced |
|---|---|---|
| Durable job service | `coursebook/job_service.py` | Random job ids; `operation_id` de-duplication; leases with `(job_id, attempt_id, lease_owner)` fencing; `BEGIN IMMEDIATE` claims/renewals/checkpoints/finishes; real-stage progress; `cancel_requested → cancelling → cancelled`; `completed` that races a cancel becomes `completed_late`; failed retry is a new attempt with the persisted checkpoint; startup reconciliation. |
| Governed research | `coursebook/workers.py` (research stages) | Executable `ResearchBudget`; a cancel check at every provider-call boundary; cancellation propagates through `research.run_research` instead of being swallowed as a "failed fetch"; search/extract calls are counted in `usage_events` with real durations and null tokens. No research path is reachable from `pre_llm_call`. |
| Source ledger | `coursebook/sources.py` | URL/title/source type/fetch/publication dates and support status from the frozen vocabulary; refresh compares content hashes against the immutable `gen_research_runs` snapshots; a changed source becomes `stale`; unreachable sources stay historical and become `unreachable`; impact resolves dependent objectives/checks/lessons/artifacts; `attempt.submit` refuses a stale check with `CHECK_STALE` and creates no attempt or transition. |
| Artifact cache + media policy | `coursebook/artifacts.py` | Content-addressed store (`<root>/objects/<hash[:2]>/<hash>`); unique `(content_hash, kind)` reuse with `ref_count`; spec-hash + source-hash cache lookup; staged write → fsync → atomic rename → DB commit; startup reconciliation of stale staging and unreferenced objects; allowlisted SVG subset; safe exclusive-subset PDF template with selectable text; magic-byte MIME sniffing; illustration label; text-equivalent requirement; narration transcript/voice/language requirement. |
| Media jobs + fallback | `coursebook/workers.py` (media stages) | Cache hit before any provider call; provider failure returns the complete text lesson with `degraded`, reason and triage (`keep_cached_original` / `use_text_fallback` / `choose_new_voice`); no silent voice substitution; renderer manifest carries inert MIME, hash, description and `active_content: false`; `MEDIA:` marker only for render-safe MIME. |
| Wiring | `coursebook/domain.py`, `coursebook/hooks.py`, `coursebook/generation.py` | `jobs.create` uses the service and keeps idempotent replay; `attempt.submit` calls the staleness gate; startup reconciliation runs once at plugin load on an already-migrated DB; generation's research persistence marks changed sources stale before inserting the new run snapshot. |

## 2. State machine (as implemented)

```
queued ──claim──► running ──finish──► completed
  │                  │  ├──────────► completed_late   (cancel raced the result)
  │                  │  ├──────────► failed ──resume──► queued (new attempt_id, same checkpoint)
  │                  │  └──────────► interrupted_requires_retry ──resume──► queued
  ├──cancel──► cancelled (nothing ran, no usage row, no artifact)
  └──cancel while running──► cancel_requested ──boundary──► cancelling ──► cancelled
```

Fence: every write matches `attempt_id` **and** `lease_owner`. An expired lease can be reclaimed;
the old worker's next checkpoint/finish raises `JobLeaseLost` and cannot touch the row.

## 3. Evidence

### 3.1 Tests (all against real SQLite, real migrations, real content-addressed files)

```
python3 -m unittest discover -s tests -t .
Ran 389 tests ... OK
```

New suites:

* `tests/test_job_service.py` — 17 cases: operation-id de-dup, idempotency replay/conflict, live
  lease refusal, expiry reclaim + stale-worker fence, renew fence, queued cancel spends nothing,
  cancel at a stage boundary stops the next stage, `completed_late`, cancel+restart→cancelled,
  durable failure, restart→`interrupted_requires_retry` with checkpoint, resume with stage skip,
  terminal job refusal, usage nulls, usage summary.
* `tests/test_artifacts.py` — 28 cases: SVG script/on*/foreignObject/external-href/doctype
  rejection, deterministic schematic, PDF header/EOF/selectable text/no JavaScript, MIME sniffing,
  spec policy (illustration authority, sourced permission, narration transcript, schematic facts),
  cache roundtrip/dup bytes/spec+source lookup, orphan reconciliation, text fallback, cached
  original reuse, renderer refusal, media job cache hit (0 second provider call), crash after
  adoption → retry reuses (1 call, 1 row, 1 file).
* `tests/test_sources.py` — 7 cases: ledger dates/status, unreachable, changed→stale with impact,
  stale check refuses grading with no attempt/transition, unchanged source still grades, uncited
  source does not pause the check, `apply_run` marks changed sources stale.
* `tests/test_workers.py` — 8 cases: ledger+usage write, budget caps live calls, cancel before
  start spends nothing, cancel mid-research records the search that happened and stops the fetch,
  unavailable search is honest, reconnect does not duplicate the ledger, hooks never run research.

### 3.2 Review trace

`docs/REVIEW_CB012-trace.json` is produced by `python3 -m tests.trace_cb012` against a throwaway
migrated `HERMES_HOME`. Observed values:

* jobs: `research/completed`, `media/completed`, `export/interrupted_requires_retry` after a
  simulated dead worker;
* `restart_reconciliation = {interrupted: 1, cancelled: 0, artifacts: {staging: 0, objects: 0}}`;
* artifact: `image/svg+xml`, 792 bytes,
  `sha256:871a2ceaa5bb67a736ffdfad89f38a82e036c3a5a3a61ffc04ba8260b5c3e6c7`, and
  `artifact_hashes_match_db: true` (hash recomputed from the file, compared to the DB row);
* usage ledger: 2 × `web_search`, 1 × `web_extract` (model null, real durations), 1 ×
  `deterministic.schematic` with `artifact_count: 1`;
* ledger: `https://example.test/source-0`, `support_status: unassessed`, real fetch date;
* fallback: `degraded: true`, reason `voice ja-voice-a is not installed`, triage options
  `[keep_cached_original, use_text_fallback, choose_new_voice]`.

### 3.3 Gates

```
bash scripts/validate.sh      -> Validation passed (unit tests, node --check, admission,
                                 runtime contracts, mounted backend trace, 9/9 expectations)
python3 -m unittest ...       -> 389 tests OK
```

## 4. Acceptance mapping

| Acceptance criterion | Proof |
|---|---|
| cancel/reconnect/restart do not duplicate spend or artifacts | lease/fence tests; cancel-at-boundary test; restart→resume->skip test; media cache-hit test (1 provider call across two jobs); crash-after-adoption test (1 call, 1 row, 1 file); research reconnect keeps one ledger row per URL. |
| source updates mark dependent checks stale | `test_changed_source_marks_dependent_check_stale`, `test_stale_check_refuses_grading_and_creates_no_attempt`, `test_apply_run_marks_changed_sources_stale`. |
| generated illustrative media never claims technical authority | `test_illustration_may_not_claim_technical_authority` (spec is refused when `technical=True`); `honesty_label()` is stored in every artifact's provenance; sourced references require a cited source and a non-unknown permission. |
| no active/untrusted rendering | SVG allowlist rejects script/event/foreignObject/external refs/doctype; PNG/JPEG/WebP/GIF/audio/PDF magic checks; `assert_render_safe` before adoption; renderer manifest only lists inert MIME with `active_content: false`; PDF template has no JavaScript or embedded files. |

## 5. Renderer integration (for Sable / Vellum)

The backend half is complete and deliberate:

* a media job's final checkpoint contains `renderer` (manifest entries:
  `artifact_id, mime, content_hash, description, label, active_content`) and `media_marker`
  (`MEDIA: <adopted path>`) for `TOOL_MEDIA_RENDERER_AREA`;
* `artifact.get` already returns a session-bound handle for the authenticated download route;
  the filesystem path never leaves the backend for that route;
* the Desktop must render only the listed inert types and must show `description` as the text
  equivalent; it must not fetch remote images or execute SVG/HTML.

No Desktop file was touched by this package.

## 6. Cross-owner edits (declared, not silent)

* `tests/test_platform_binding.py` — the pre-kernel stub expectations were updated to the merged
  kernel handler: `binding.get` now migrates on first use, resolves stored or live runtime ids,
  returns `binding_id`, and refuses two identifiers with `VALIDATION_FAILED`.
* `coursebook/domain.py` — `binding.get` now refuses ambiguity (both identifiers) instead of
  silently preferring one.
* `scripts/probe-backend.py` — two expectations referenced the pre-kernel behaviour
  (`binding.get` NOT_IMPLEMENTED on an unmigrated DB; `library.list` unimplemented). Updated to
  the kernel truth (fresh DB migrates and returns an explicit null binding; `pack.preview` is the
  honest unimplemented example).
* `coursebook/generation.py` — one call added in `_persist_research` so a changed source marks
  dependent checks stale before the new immutable run snapshot is written.
* `coursebook/research.py` — added `ResearchCancelled` and two re-raise points so a cancel is not
  swallowed by the fetch-failure handler.
* `coursebook/hooks.py` — startup reconciliation call appended after the kernel registration line.
* Merge commit of `wt/cb-002-cinder` into this branch (kernel was an unsatisfied parent).

## 7. Known limits / open questions

* The `cb.db` v2 contract has no staleness column/table. Staleness is therefore **derived** from
  the frozen vocabulary plus the recorded research/plan links; no schema was invented. If Atlas
  wants a first-class `stale_at`/`source_link` table, that is a v3 contract question.
* `jobs.create` stores `attempt_id = NULL` until a worker claims; the RPC view reports
  `"unassigned"` so the contract's `minLength: 2` holds without inventing an attempt.
* Media "generation" in this package is deterministic (SVG/PDF) plus an injected provider for
  images/audio. No real image/TTS vendor call is made by tests or by the trace.
* The renderer view itself is Sable/Vellum's; this packet specifies its input contract.
* Startup reconciliation currently runs when `coursebook.hooks` is imported by the plugin host
  (once per process, only on an already-migrated DB). If the host ever needs an explicit
  `on_load` hook, `job_service.ensure_startup_reconciled()` is the entry point.
