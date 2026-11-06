# Review packet — CB-022 contract amendment (cb.rpc v3)

Task: `t_37b9f9f8` — *Contract v3 gap: review queue actions and evidence inspection methods*.
Owner: Atlas (contract). Follow-on implementer: Cinder (handler registration only).
Branch: `wt/cb-022-atlas-rpc-v3`, based on `master` @ `b536e2f`.

## Why this amendment exists

CB-008 (`wt/cb-008-cinder`, `4217f44`) implemented and proved the learning loop's backend semantics,
but three surfaces the Desktop half needs were absent from the frozen `cb.rpc` v2 method set, so the
review queue and the Evidence tab had no command path:

* `coursebook/review.py` — derived queue (`queue`, `refresh_due`) and learner actions
  (`apply_action`: snooze / stretch / drop / resume, recorded as layer-1 `self_reported` evidence).
* `coursebook/evidence.py` — `layer1` / `layer2` / `layer3` / `disputes` / `bundle`.

v3 is additive: four methods, no storage change, no new error code. Nothing from v1 or v2 changed.

## Files

| File | State | Note |
|---|---|---|
| `contracts/rpc.v3.json` | **new** | sha256 `006232ae71b642fd44d6461ce0e0f83f7fd40cf6dfeb4b0730fc4283cb6aad9a`; `$id .../rpc/v3`, `x-contract-version 3`, `x-supersedes .../rpc/v2` |
| `contracts/rpc.v2.json` | untouched | sha256 `4afc3c5fe0248c32733884dc68295f4a3aff916df7782f437945a8862e4352f4` (unchanged from master) |
| `contracts/db.v2.json`, `errors.v2.json`, `jobs.v2.json`, `pack-manifest.v1.json`, `vocabulary.v1.json` | untouched | no storage or error change means no bump |
| `coursebook/contracts.py` | modified | `CONTRACT_FILES["cb.rpc"] = "rpc.v3.json"`, `WIRE_CONTRACT_VERSION = 3` |
| `tests/test_contracts.py` | modified | v1+v2 preservation test generalised; `V3AmendmentTest` (8 new tests) |
| `scripts/proof_contract_v3.py` | **new** | branch-dependent proof against the real CB-008 backend; skips with a stated reason where the kernel is absent |
| `docs/CONTRACTS.md` | modified | status v3, contract table, envelope rules, full v3 delta section, UX mapping rows, decision log |

## The four methods

| Method | Request | Response |
|---|---|---|
| `review.queue` | `enrollment_id`, `cap?` (1–50, default 10), `include_upcoming?` | `enrollment_id`, `items[]`, `total_due`, `total_overdue`, `total_scheduled`, `upcoming_hidden`, `now`, `cap` |
| `review.action` | `enrollment_id`, `objective_id`, `action` ∈ snooze/stretch/drop/resume; envelope requires `idempotency_key` + `expected_revision` | `objective_id`, `action`, `recorded_at`, `state`, `due_at` |
| `evidence.inspect` | `enrollment_id`, `objective_id?`, `limit?` (1–200) | `l1`, `l2`, `l3`, `disputes` |
| `evidence.disputes` | `enrollment_id`, `attempt_id?`, `limit?` (1–200) | `enrollment_id`, `disputes[]`, `count`, `truncated` |

## Decisions (and the reason)

1. **v3 is the learning-loop surfaces only.** An unowned draft `rpc.v3.json` carrying `pack.list`
   existed on `.worktrees/t_atlas_v3` (branch `wt/cb-020-rpc-v3`, no board card, no backend function,
   no handler, no consumer). It was **not** adopted. `pack.list` is a v4 amendment with its own owner
   and backend proof. Documented in `docs/CONTRACTS.md` §Version numbering so nobody extends v3 in
   place.
2. **Revision fence lives in the envelope, not the payload.** The card asked for `expected_revision`
   in the request and `revision` in the response. The frozen contract already fences every learner
   command at envelope level (`$defs.envelope_request` `allOf` rules → `STALE_REVISION` +
   `current_revision`). Putting a copy in the payload or result would create a second authority for
   the same fact, so `review.action` gets an `allOf` rule requiring `idempotency_key` and
   `expected_revision`, and its payload/result deliberately carry neither.
3. **No `review_schedule` table.** The queue is derived from committed L2 evidence plus layer-1
   learner action events; a stored copy of "what is due" would be a competing authority (AUDIT R5).
   `review.refresh_due` is not an RPC method either — it already runs as a scheduler tick inside
   `library.list`, so objective staleness is the backend's problem, not a client call.
4. **No `disputes` table.** Disputes stay inside `attempts.grading_provenance_json` (`cb.db` v2 has
   one writer, `attempt.dispute`, inside the attempt transaction). `evidence.disputes` is the
   storage-independent read view; `count` = all matching rows, `truncated` = the bounded list omitted
   some. If course-wide dispute filtering/indexing is ever needed it is a `cb.db` v3 migration with a
   backfill, not a quiet field addition.
5. **One read method plus one filtered view**, not a split `evidence.summary`/`evidence.disputes`
   pair with duplicated layer schemas: `evidence.inspect` returns the whole bundle the pane renders,
   `evidence.disputes` serves the dispute section's attempt filter with real paging semantics.
6. **`now` is returned, never accepted.** A client cannot age its own queue into looking overdue; all
   schedule arithmetic is against the backend clock.
7. **Cap bounds rows, never counts.** `total_due` / `total_overdue` / `total_scheduled` /
   `upcoming_hidden` are always full counts, so a hidden backlog cannot look like an empty queue.
8. **No attainment/percentage/persona field.** `review_item` carries `interval_days`, `step` and
   `ladder_days` (a declared heuristic), and `evidence_l3.is_persona` is `const: false`.

## Handlers Cinder must register

On a branch that contains `coursebook/review.py` and `coursebook/evidence.py`:

| Method | Backing code | Handler work |
|---|---|---|
| `review.queue` | `review.queue(connection, enrollment_id, cap=..., include_upcoming=...)` | pass through; result is already contract-shaped |
| `review.action` | `review.apply_action(connection, enrollment_id=..., objective_id=..., action=...)` | one transaction: `_require_revision(envelope)` → `_bump_enrollment(connection, enrollment_id, expected)` → apply → re-read objective `state`; return `{objective_id, action, recorded_at, state, due_at}` with `(revision, result)`; persist the key with `_remember` |
| `evidence.inspect` | `evidence.bundle(connection, enrollment_id, objective_id=...)` | map payload `limit` onto `layer1(limit=...)` |
| `evidence.disputes` | `evidence.disputes(connection, enrollment_id, attempt_id=...)` | slice to `limit`, `count` = full length, `truncated` = `count > limit` |

Full text and rationale: `docs/CONTRACTS.md` §*v3 delta (CB-022)*.

## Evidence from real runs

* `python3 -m unittest tests.test_contracts` → **31 tests OK** (8 new in `V3AmendmentTest`).
* `python3 -m unittest discover -s tests -t .` → **222 tests OK** on this branch (no v2 regression
  from the wire bump).
* `contracts.audit_contracts()` → `[]` (method enum ↔ payload schemas ↔ `$defs` ↔ `$ref` versions).
* Preservation, asserted mechanically: every v1 and v2 method schema is byte-identical in
  `rpc.v3.json` except the `health.get` wire constant (1 → 3, 2 → 3); `rpc.v2.json` is unmodified.
* **Contract ↔ backend proof** (`scripts/proof_contract_v3.py`, run in a throwaway copy of
  `wt/cb-008-cinder` with the frozen v3 contract files swapped in, real SQLite, real migrations):
  **5 tests OK**. It established:
  * `review.queue` output validates **as returned**, including the `cap` case;
  * `review.apply_action` validates for all four actions once the handler adds `state` (and `due_at`
    from the queue) — raw output has neither;
  * `evidence.bundle` is exactly `{l1, l2, l3, disputes}` and its three layers validate as returned;
  * the raw bundle's `disputes` is `{enrollment_id, disputes, count}` and **fails** the contract until
    the handler adds `truncated` — i.e. the documented delta is the only delta;
  * a real `attempt.dispute` produces an 8-field dispute record that validates against
    `$defs/evidence_dispute`, `count` and the empty case included.
* On this contract-only branch the same proof module reports **5 skipped** with an explicit reason
  (no silent pass).

## Intentionally not verified here

* The four handlers do not exist on this branch — they are Cinder's work after the freeze. Until they
  are registered, `dispatch` answers `NOT_IMPLEMENTED` (asserted in `tests/test_contracts.py`).
* `cb.db` migration work is **not** required by this amendment; no table, column or index is added,
  and `db.py` schema version stays 2.
* The Desktop half was not exercised: Vellum consumes the methods after Cinder wires them. v3 changes
  the wire constant, and `desktop/plugin.js` already reads `result.contract_version` dynamically
  (`desktop/plugin.js:76,101,125,344`), so no client edit is implied — but that is a read of the
  code, not a run.

## Gates and rollback

* `scripts/test.sh` / `validate.sh` unchanged; this amendment touches no runtime path except
  `coursebook/contracts.py`'s file map and wire constant.
* Rollback is one line each: `CONTRACT_FILES["cb.rpc"] = "rpc.v2.json"` and
  `WIRE_CONTRACT_VERSION = 2`; the v3 file can stay on disk as history.
