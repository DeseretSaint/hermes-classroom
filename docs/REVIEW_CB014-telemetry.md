# CB-014 — tool telemetry only for bound lesson chats

Status: fixed on `wt/cb-014-telemetry-cinder` (task `t_842a2947`). Backend only; no Desktop file,
manifest or contract changed.

## What was measured before the fix

Read-only query of the operator's own store (`sqlite3 -readonly
~/.hermes/plugin-data/coursebook/data.db`, 2026-11-06T13:39Z):

| query | result |
|---|---|
| `SELECT COUNT(*) FROM usage_events` | **48** |
| rows with `enrollment_id` NULL | **48** |
| distinct `operation_id` | 5 (`20261106_055011_00373f`, `20261106_055800_dae9d9`, `20261106_061456_26a162`, `20261106_062333_4730b6`, `50e1d9d2-89e2-4993-91a8-9954e718da49`) |
| `provider` values | `tool:` + `terminal`, `read_file`, `skill_view`, `skills_list`, `skill_manage`, `execute_code`, `desktop_preview`, `read_window_below`, `tool_describe`, `viking_read`, `viking_search`, `vision_analyze` |
| `courses`, `enrollments`, `bindings`, `attempts`, `jobs` | 0, 0, 0, 0, 0 |

Root cause: `coursebook/hooks.py:post_tool_call` inserted one `usage_events` row for **every** tool
call of **every** session in the process, using `binding["enrollment_id"] if binding else None`.
The gateway-hosted root-profile copy therefore recorded 48 unattributable rows in a store with no
course in it. Nothing about the course data path was wrong; the telemetry write was unconditional.

## Decision

1. **An unbound session writes no usage event.** `usage_events.enrollment_id` exists to attribute
   a row to an enrollment; a NULL-enrollment row is not degraded data, it is noise in a store the
   session does not belong to. `cb.db` was not amended — no schema change, no new column.
2. **The write follows the same single-home scope as the data path.** The insert already went
   through `coursebook.db.transaction()` → `connect()`, which honours `single_home_pin()`
   (`SINGLE_HOME_FLAG`). That is now covered by a test so a later edit cannot bypass the seam.
3. **`task_id` is a correlation id, not an identity.** It is still stored as `operation_id`, but it
   can no longer stand in for a binding (`connection_id` matching is gone: a task id that happens
   to equal another chat's connection id must not attribute usage to that chat).

## What changed

`coursebook/hooks.py`

* `_GOVERNED` — a bounded (1024) in-process set of session ids `pre_llm_call` has decided are bound
  lesson chats. Written after `turn.reconcile_binding` answers a non-`unbound` status; cleared on
  `detached`/`branched`/`orphaned`, on an unbound reconcile, and on any gate exception. This is the
  whole reason an unbound session never reaches the storage seam: `post_tool_call` returns before
  opening a connection, so it cannot create or grow a database.
* `post_tool_call` now:
  1. requires a session id in `_GOVERNED` — otherwise returns `None` before `db.transaction()`;
  2. re-confirms inside the fence that a binding for **that stored session id** is still
     `active`/`paused` and that its enrollment row exists; a chat detached after the gate decided
     is dropped from `_GOVERNED` and writes nothing (no stale-callback write);
  3. inserts the row with the binding's real `enrollment_id`.
* removed the now-unused module-level `from . import bindings`.

`tests/test_hook_usage_telemetry.py` (new, 10 tests, real SQLite through the real hooks):

* unbound tool calls (`terminal`, `skill_view`, `read_file`) write **zero** rows **and do not create
  `plugin-data/` at all**;
* a `task_id` alone attributes nothing;
* a bound lesson chat writes exactly one row — `enrollment_id` set, `provider` `tool:<name>`,
  `operation_id` = task id, `duration_ms` kept, `tokens_json` `{}`;
* each tool call is its own row;
* a binding detached after the gate writes nothing and clears governance;
* a cwd change on the next turn clears governance (detach), so later tool calls write nothing;
* a foreign session id writes nothing;
* the governed set stays bounded;
* under `HERMES_COURSEBOOK_SINGLE_HOME=1` with an escaped `?profile=` scope, a bound chat's row
  lands in the launch home and the escaped (root-profile) home is never touched.

## Verification (real output)

```
$ python3 -m unittest tests.test_hook_usage_telemetry -v
Ran 10 tests … OK

$ python3 -m unittest discover -s tests -t .
Ran 578 tests in 66.759s
OK

$ bash scripts/validate.sh
…
Validation passed.
```

## Not closed by this card

* The 48 historical rows are **still in the operator's store**; deleting operator data needs an
  explicit go-ahead, so nothing was removed.
* `pre_llm_call` still calls `binding.get`, which runs `ensure_schema()` for every chat. On a home
  with **no** Coursebook database that first turn creates/migrates one. It is a lifecycle read, not
  a telemetry write, and it was verified by CB-013 as the gate's behaviour — filed separately rather
  than changed here.
* `job_service._record_usage` and `generation._record_usage` still write `enrollment_id = NULL` for
  paid provider calls inside a job. Those rows are job-scoped and only exist inside a home that
  already holds the job; they are not arbitrary agent-session telemetry. Left as-is.
