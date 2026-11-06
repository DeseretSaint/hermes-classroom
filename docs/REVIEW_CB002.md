# CB-002 review packet — authoritative backend kernel

| | |
|---|---|
| Branch | `wt/cb-002-cinder` |
| Base | `683201e` (CB-018 contract v2) |
| Card | t_c57f34ee |
| Contract versions implemented | `cb.rpc` 2, `cb.db` 2, `cb.jobs` 2, `cb.errors` 2, `cb.vocabulary` 1 |

## What shipped

| File | Role |
|---|---|
| `coursebook/migrations/0001_initial.sql` | cb.db v1: 17 tables, exact column/ref/unique/index inventory |
| `coursebook/migrations/0002_lesson_runs_segments_and_revisions.sql` | cb.db v2 delta: `lesson_runs`, `lesson_segments`, `bindings.lesson_run_id/objective_id`, `notebook_entries.revision`, `packs.state/revision` |
| `coursebook/db.py` | connection policy, `BEGIN IMMEDIATE` fence, migration runner with checksums, startup reconciliation |
| `coursebook/domain.py` | 29 command handlers (all v1 kernel methods + the 10 v2 methods) |
| `coursebook/grading.py` | closed-form gate + bounded aux adapter with fail-closed semantics |
| `coursebook/validators.py` | deterministic notation/number/unit/tolerance/selection grading |
| `coursebook/hooks.py` | one added wiring block: importing the package registers the kernel |
| `tests/kernel_support.py`, `tests/test_kernel_*.py`, `tests/test_kernel_v2.py`, `tests/test_jobs.py` | 128 new tests against real SQLite |

Not touched: `contracts/**`, `coursebook/contracts.py`, `coursebook/api.py`, `dashboard/**`,
`desktop/**`, `docs/CONTRACTS.md`, `docs/WORK_PACKAGES.md`, `plugin.yaml`, `__init__.py`.

### Cross-owner edits (three, each an obsolete assumption, all flagged on the card)

1. `tests/test_rpc.py` — asserted `course.create` answers `NOT_IMPLEMENTED`; it is implemented now.
   The assertion moved to `pack.preview` (Lattice's, still unimplemented). The dispatch contract
   is unchanged.
2. `tests/test_contracts.py` — (a) asserted `library.list` has no handler, (b) popped
   `library.list` from `METHOD_HANDLERS` in `finally`, which would have unregistered the real
   handler for the rest of the process. Replaced both with a save/restore around the fake handler
   and a still-unimplemented method for the `NOT_IMPLEMENTED` case.
3. `coursebook/hooks.py` — appended the registration import. `docs/WORK_PACKAGES.md` marks this
   file shared with Sable; the hook bodies are untouched and this block must merge in one commit
   per that note.

## Schema diagram (cb.db v2)

```
packs ──< courses ──< plans ──< objectives ──< checks ──< attempts
  │          │          │            │             │           │
  │          │          │            │             ├──< transitions (UNIQUE enrollment, to_revision)
  │          │          │            │             ├──< evidence   (layer 1..3, evidence_class)
  │          │          │            │             └──< lesson_segments ──< lesson_runs
  │          │          │            └──< notebook_entries (revision)
  │          │          └──< enrollments ──< bindings (status, revision, lesson_run_id)
  │          └──< sources
  └──< artifacts

jobs · usage_events · idempotency_keys · schema_migrations   (independent tables)
```

* `transitions` has `UNIQUE(enrollment_id, to_revision)` — the database, not a handler, is what
  makes two transitions for one answer impossible.
* Every aggregate that is fenced has its own `revision`: courses, enrollments, bindings, lesson
  runs, notebook entries, packs.
* `schema_migrations(version, checksum, applied_at)` — one transaction per migration.

## Command surface

| Method | Handler | Fence |
|---|---|---|
| `health.get`, `schema.get` | Sable (skeleton) | read-only |
| `course.create`, `course.get` | kernel | course revision 0 |
| `enrollment.create` | kernel | n/a |
| `enrollment.update`, `enrollment.delete` | kernel | enrollment revision |
| `plan.approve`, `plan.replan` | kernel | enrollment revision + plan hash |
| `check.open`, `progression.challenge_out` | kernel | enrollment revision |
| `attempt.submit` | kernel | enrollment revision + idempotency key |
| `attempt.override`, `attempt.dispute` | kernel | enrollment revision (override) |
| `notebook.save/list/delete/update` | kernel | entry revision on update |
| `quiz.history`, `library.list`, `lesson.page` | kernel | read-only |
| `lesson.begin`, `binding.get`, `binding.abandon` | kernel | run revision / binding revision |
| `jobs.create/get/cancel/list`, `usage.summary` | kernel | job state machine |
| `artifact.get` | kernel (metadata + handle) | read-only |
| `pack.delete` | kernel (freeze + scope) | pack revision |
| `pack.preview`, `pack.import`, `pack.export` | Lattice — `NOT_IMPLEMENTED` | — |

Registration is registry-driven (`domain.ensure_registered()` reads `cb.rpc` method names), so a
v3 amendment adds methods without editing `domain.py`; a handler for a method the contract does
not contain is never registered.

## Attempt lifecycle (the acceptance core)

```
submit(payload, expected_revision, idempotency_key)
  ├─ idempotency key + matching payload hash        -> persisted result, no re-grade
  ├─ idempotency key + different payload hash       -> IDEMPOTENCY_CONFLICT, nothing written
  ├─ attempt_nonce already seen                     -> original attempt, ignored as late/dup
  ├─ check.version != payload.check_version         -> CHECK_STALE, no attempt created
  ├─ check.state != open                            -> CHECK_STALE, no attempt created
  ├─ check.audit_state != passed                    -> POLICY_VIOLATION, no attempt created
  ├─ enrollment binding present and not active      -> BINDING_NOT_ACTIVE, no attempt created
  ├─ expected_revision != enrollment.revision       -> STALE_REVISION + current_revision
  ├─ grade (no transaction open, no network in one)
  │    ├─ closed reference  -> deterministic validators
  │    ├─ open reference    -> aux adapter, deadline-bounded, JSON validated locally
  │    └─ failure/timeout/invalid output -> GradingUnavailable
  └─ BEGIN IMMEDIATE
       ├─ re-read revision/check (second CAS)       -> STALE_REVISION / CHECK_STALE
       ├─ needs_retry: attempt state=failed, no transition, no evidence, revision unchanged
       └─ committed: attempt, ONE transitions row, evidence L1 (+L2 only for cold pass),
                     objective state, check close on pass, idempotency row — one commit
```

Evidence classes: `cold` by default; a second answer to the same check follows feedback that was
shown, so it is `hinted`; overrides are `override` with verdict `not_yet` (access, never a pass);
`self_reported`/`parent_reported` are layer-1 observations and can never produce layer-2
independent evidence. Only `cold` + `pass` sets `objective.state = independent_evidence`.

## Sample RPC calls and responses (real output)

Loaded exactly the way `dashboard/plugin_api.py` loads the package (by path, isolated
`HERMES_HOME`), then dispatched through `coursebook.api.dispatch`.

```json
{"contract":"cb.rpc","contract_version":2,"method":"health.get","operation_id":"smoke-health-get-0001","payload":{}}
→ {"ok":true,"contract_version":2,"revision":0,
   "result":{"plugin_version":"0.1.0","contract_version":2,
             "db":{"ready":false,"schema_version":null},"backend":"python"}}
```

```json
{"method":"course.create","payload":{"title":"Braising Fundamentals","recipe":"committed",
  "goal":"Braise short ribs confidently","locale":"en-US"},"idempotency_key":"smoke-create-0001"}
→ {"ok":true,"revision":0,
   "result":{"course_id":"crs_189427d5d1804f519a9aa4dd314b0a7a",
             "plan_id":"pln_7e32661eb92243e691965191cd0535ed","revision":0}}
```

```json
{"method":"attempt.submit","expected_revision":2,"idempotency_key":"smoke-submit-0001",
 "payload":{"enrollment_id":"enr_6daf...","check_id":"chk_7f2a...","check_version":1,
            "attempt_nonce":"nonce-smoke-0001","answer":{"kind":"text","text":"salt"}}}
→ {"ok":true,"revision":3,
   "result":{"attempt_id":"att_349c...","verdict":"not_yet","evidence_class":"cold",
             "criteria":[{"id":"c1","observed":"does not match an accepted answer","met":false}],
             "next_action":"retry_attempt","revision":3}}
```

```json
{"method":"attempt.submit","expected_revision":0,"idempotency_key":"smoke-submit-0002", "...":"same check"}
→ {"ok":false,"error":{"code":"STALE_REVISION","category":"conflict","retryable":false,
   "message":"the enrollment moved on before this answer was graded.",
   "details":{"current_revision":3},"current_revision":3}}
```

Retry after feedback (correct answer): `verdict: pass`, `evidence_class: hinted`,
`next_action: review_objective`, revision 4, and **no** layer-2 evidence row.

```json
{"method":"lesson.begin","payload":{"enrollment_id":"enr_6daf...","objective_id":"obj_377b...","mode":"resume"},
 "idempotency_key":"smoke-begin-0001"}
→ {"ok":true,"revision":0,
   "result":{"lesson_run_id":"run_7409...","run_state":"created","binding":null,
             "resume":{"available":false,"reason":"no_binding"},"revision":0}}
```

`library.list` after that lesson:

```json
{"items":[{"enrollment_id":"enr_6daf...","title":"Braising Fundamentals","recipe":"committed",
  "enrollment_status":"active","course_status":"draft",
  "provenance":{"source":"authored","pack_id":null,"pack_version":null},
  "next_step":{"kind":"resolve_review_due","label":"Review 1 objective(s)"},
  "evidence_summary":{"independent":0,"review_due":1,"total_objectives":1,
                      "current_objective_id":"obj_377b..."},
  "warning":null,"updated_at":"2026-11-06T08:45:20.658658+00:00","revision":4}],
 "next_cursor":null,"total":1,"empty_reason":null,"applied_filter":"all"}
```

Row counts after the run: 1 course, 1 enrollment, 1 objective, 1 check, 2 attempts, 4
transitions (approve, open, not_yet, pass), 2 evidence rows (L1 only), 1 lesson run, 6
idempotency keys.

## Evidence

```
$ bash scripts/validate.sh
python3 -m unittest discover -s tests -t .   →  Ran 174 tests ... OK
node --check desktop/plugin.js              → syntax OK
hermes plugins validate .                   → Validation passed (16/16 checks)
hermes plugins doctor .                     → OK: discovery, manifest, import, registration
```

Test files and what they prove:

| File | Cases | Proves |
|---|---|---|
| `test_kernel_schema.py` | 12 | migration DDL == `cb.db` inventory (tables, columns, types, nullability, defaults, FKs, uniques, indexes); WAL/FK/busy_timeout; checksum drift refused; fresh profile honestly not ready, then migrates on first command |
| `test_kernel_commands.py` | 30 | create/get/enroll/approve/replan/check.open/challenge-out/notebook/jobs/usage/binding incl. refusal shapes, idempotency replay/conflict, 500-row page bounds |
| `test_kernel_grading.py` | 17 | notation folding, units, tolerance, equivalent forms, multiple answers, aux invalid JSON/exception/deadline, no fabricated pass |
| `test_kernel_transitions.py` | 24 | one transition per answer, duplicate nonce ignored, idempotency replay, stale revision/check, hinted vs cold evidence, override, paused binding, needs_retry advances nothing, grader runs with zero open transactions (and a concurrent write succeeds), two concurrent submits → one win + one STALE_REVISION, restart reconciliation, evidence-class constraints |
| `test_kernel_v2.py` | 29 | library filters/paging/empty reasons, lesson run create/resume/fresh, durable page, notebook revision fence, jobs list counts/bounds, binding abandon, enrollment lifecycle + scoped delete with `DELETE_SCOPE_STALE`, pack freeze keeps evidence, artifact handle never exposes a path, full registry coverage |
| `test_jobs.py` (appended) | 3 | cancel targets are contract edges; non-cancellable states refused |

## Known limits / open questions

1. **Aux grader lane (Sentinel probe #4).** `attempt.submit` is registered; open-response checks
   fail closed to `needs_retry` because `grading.configure_aux_grader()` has no host adapter yet.
   Closed forms are fully graded. This is deliberate: no verdict is fabricated and no provider
   call is invented. When the probe names the task lane, one deployment call enables the lane; no
   kernel change is needed.
2. **`attempt.dispute` has no table in `cb.db`.** v1/v2 list 17/19 tables and none holds a dispute
   state machine (`open|accepted|kept_original|withdrawn`). The kernel appends disputes to
   `attempts.grading_provenance_json` (the attempt aggregate the dispute is about) and returns
   `state: "open"`. Flagged to Atlas for a v3 table if dispute resolution is to be queryable.
3. **`artifact.get` returns a handle, not bytes.** The URL shape is contract-legal; the gateway
   route `/api/plugins/coursebook/artifacts/<handle>` is Sable's (CB-018 open question 4).
4. **Pack content operations** (`pack.preview/import/export`, and the actual content removal inside
   `pack.delete`) are Lattice's. `pack.delete` freezes the pack row and reports the exact scope;
   it does not delete files.
5. **`check.open` requires an audited check spec.** Objectives are authored by the plan job (or
   `domain.record_objective`) inside `objectives.evidence_criteria_json`; an objective without an
   audited `check_spec` is refused with `VALIDATION_FAILED / objective_not_checkable` rather than
   grading an unaudited question.
6. **Destructive scope.** `enrollment.delete` and `pack.delete` require `dry_run` preview and the
   matching `data_scope_hash`; a changed scope answers `DELETE_SCOPE_STALE` and writes nothing.
   The kernel never deletes on the operator's live profile as part of this card — tests only.
