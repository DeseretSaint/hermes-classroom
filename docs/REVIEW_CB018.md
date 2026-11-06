# Review packet — CB-018 contract amendment (cb.rpc v2)

Status: **merge-ready on `wt/cb-018-atlas-contract-v2`**. Not merged; the operator merges.
Owner: Atlas. Scope: contracts, `coursebook/contracts.py`, `tests/test_contracts.py`,
`.test_rpc` version helper, contract docs. No handler, UI or database implementation changed.

## Commit

| | |
|---|---|
| Contract amendment | `683201ef2c09d95be3a0252d2e4ddc8dda1d4d56` |
| Parent | `0c323be` (Merge CB-001 frozen contracts and plugin scaffold) |
| Branch | `wt/cb-018-atlas-contract-v2` |
| Files added | `contracts/rpc.v2.json`, `contracts/errors.v2.json`, `contracts/db.v2.json`, `contracts/jobs.v2.json` |
| Files changed | `coursebook/contracts.py`, `tests/test_contracts.py`, `tests/test_rpc.py`, `docs/CONTRACTS.md` |
| Files intentionally untouched | every `contracts/*.v1.json`, `contracts/pack-manifest.v1.json`, `contracts/vocabulary.v1.json`, `coursebook/api.py`, `coursebook/db.py`, `dashboard/plugin_api.py`, `desktop/plugin.js` |

`git status` after the amendment commit showed no modified v1 file: the freeze history is
byte-identical, and `tests/test_contracts.py::test_v1_documents_are_preserved_on_disk` asserts every
one of the 24 v1 method payloads still matches the v2 copy.

## Test output

Command: `python3 -m unittest discover -s tests -t .`

```
Ran 59 tests in 0.102s

OK
```

46 pre-existing tests + 13 new CB-018 tests. The new tests fail if a v2 method, its request/response
schema, the `$id`/version links, the error code, the db v2 tables/migration plan, or the
`docs/CONTRACTS.md` UX mapping disappears. `audit_contracts()` now also rejects:

* a `$ref` that targets a superseded contract version (`errors/v1` left behind after the v2 bump);
* a method in the enum without payload schemas, or schemas without an enum entry;
* a `$id` that disagrees with `x-contract-version`;
* a `WIRE_CONTRACT_VERSION` constant that disagrees with the contract file.

## Plugin validation

Command: `hermes plugins validate .`

```
✓ manifest — plugin.yaml parses
✓ loadable — entry: __init__.py, desktop/plugin.js
✓ capability probe — register() ran in isolation
✓ declared tools — matches registrations
✓ declared hooks — matches registrations
✓ security scan — safe
✓ desktop surface — stays inside the plugin SDK surface
Validation passed.
```

## Methods added (10; 24 → 34)

| Method | Screen need it closes |
|---|---|
| `library.list` | Library after restart; search/filter/sort; empty and filtered-empty states |
| `lesson.page` | Durable Textbook section page: segments, sources, artifacts, checks, notebook saves, attempts, run state |
| `lesson.begin` | Resume/fresh lesson run with runtime/stored session ids and stale/detached behavior |
| `enrollment.update` | Archive/unarchive/pause/resume a row (reversible, not delete) |
| `enrollment.delete` | Delete one enrollment's learning data with previewed, hash-fenced scope |
| `pack.delete` | Delete one imported pack's content while preserving evidence |
| `artifact.get` | Metadata + authenticated, expiring download handle (no filesystem path) |
| `jobs.list` | Activity/recovery list, bounded and filterable |
| `notebook.update` | Edit note/tags in place without changing provenance or duplicating |
| `binding.abandon` | Retire a detached/branched/orphaned binding (§8 banner) |

Contract-wide changes: `cb.errors` v2 adds `DELETE_SCOPE_STALE`; `cb.db` v2 adds `lesson_runs`,
`lesson_segments`, `bindings.lesson_run_id/objective_id`, `notebook_entries.revision`,
`packs.state/revision` with migration `0002_lesson_runs_segments_and_revisions.sql`;
`cb.jobs` v2 adds `$defs.job_state`. `cb.vocabulary` and `cb.pack` stay at v1.

## UX screen → method mapping

Full table lives in `docs/CONTRACTS.md` ("UX screen → method mapping"). Summary of the governing
sections:

* **§6 Courses home** — `library.list` rows (`next_step`, `evidence_summary`, `warning`,
  `empty_reason`, `provenance`), `enrollment.update`, `enrollment.delete`, `pack.delete`,
  `artifact.get`, `binding.get` + `lesson.begin`.
* **§7 Course detail** — Textbook → `lesson.page` + `lesson.begin`; Notebook → `notebook.list` /
  `notebook.update` / `notebook.delete`; Quizzes → `quiz.history` / `attempt.dispute` /
  `check.open`; Plan/Evidence/Sources → `course.get` `course` payload, documented field-by-field in
  `docs/CONTRACTS.md` (v1's open object is kept for payload compatibility rather than tightened).
* **§8 Lesson workspace** — `lesson.page`, `check.open`, `attempt.submit`, `attempt.override`,
  `binding.get`, `lesson.begin` (`resume`/`fresh`), `binding.abandon`.
* **§10 Parent Studio** — `course.create` (`recipe: parent`), `jobs.create` (research/plan brief),
  `jobs.get`, `plan.approve`, `pack.preview`, `pack.export`, `artifact.get`.
* **§11 Activity/jobs/recovery** — `jobs.list`, `jobs.get`, `jobs.cancel`, `usage.summary`.

## Independent behaviour check (beyond the unit suite)

A throwaway verification script built contract-legal payloads for every new response and exercised
the schema seams. Real output:

```
PASS health.get answers v2
PASS schema.get reports the v2 set
PASS library.list response validates
PASS lesson.page response validates
PASS lesson.begin response validates
PASS lesson.begin stale binding is nameable
PASS enrollment.delete response validates
PASS pack.delete response validates
PASS artifact.get response validates
PASS artifact.get rejects a filesystem path
PASS jobs.list response validates
PASS jobs.list rejects an invented state
PASS notebook.update response validates
PASS notebook.update rejects provenance edits
PASS enrollment.update response validates
PASS binding.abandon response validates
PASS envelope requires idempotency for lesson.begin

RESULT: ALL PASS
```

`schema.get` reports `{vocabulary:1, errors:2, rpc:2, db:2, jobs:2, pack:1}` and `health.get` answers
`contract_version: 2`.

## What other owners must rebase

| Owner | Files / actions |
|---|---|
| **Cinder** | Rebase on `683201e`. `coursebook/contracts.py` (`CONTRACT_FILES` now points `cb.rpc/errors/db/jobs` at `.v2.json`, `WIRE_CONTRACT_VERSION = 2`). Register handlers for the ten new methods; add migration `0002_lesson_runs_segments_and_revisions.sql` matching `contracts/db.v2.json`. Do not edit `rpc.v2.json`; propose schema changes through Atlas. |
| **Vellum** | Rebase on `683201e`. Build the shell against `cb.rpc v2`; `desktop/plugin.js` already reads `result.contract_version` dynamically. Screen mapping is the contract; no client-side state may substitute for `library.list`, `lesson.page`, `lesson.begin`, `jobs.list`. |
| **Lattice** | No contract change for packs (still v1) except that `pack.delete` and `artifact.get` now frame import/export lifecycle. Pack export must return an `artifact_id` that `artifact.get` can resolve. |
| **Sentinel** | Add adversarial probes for: `data_scope_hash` fencing (`DELETE_SCOPE_STALE`), detached/stale binding resume, artifact handle without session, jobs.list filter bounds, notebook.update provenance immutability. |
| **Harbor** | Docs/README may cite v2 as the current wire version; catalog metadata unchanged. |

## Open questions (blocking features, not this amendment)

1. **Aux grader task lane** (`ctx.llm` task name / `llm.task_override`) — Sentinel probe #4.
2. **Workspace topology** — Sentinel probe #3; `TOPOLOGY_UNSUPPORTED` remains the honest answer.
3. **`pack.import` staging transport** — backend upload route vs. explicit local file grant.
4. **`artifact.get` streaming transport** — Sable must confirm the gateway can stream a bounded
   artifact through `/api/plugins/coursebook/artifacts/<handle>`; otherwise the contract needs a
   short-lived signed handle. A filesystem path is forbidden either way.
5. **Reattach after process restart** — `lesson.begin mode=resume` is the reattach path; if the host
   cannot re-enter a stored session, §8's banner degrades to **Start a fresh run** only.
