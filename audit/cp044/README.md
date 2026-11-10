# CP-044 — job attempt deadline evidence

Branch `wt/cp-044-job-deadline`, base `b09b65f`, fix `51d9fb4`. Everything here is offline: the
provider is a local socket that accepts the connection and never answers, so no call is spent.

## What the card claimed, and what re-measurement showed

The card said a plan job hung ~650 s and "the job's deadline stops waiting but does not cancel the
hanging provider call". Re-measured against the CP-015 disposable backend's own database
(`~/.hermes/coursebook-test-cp015/home/plugin-data/coursebook/data.db`, job
`job_659f1edba70d491b831dd9d263539db3`):

| fact | value |
| --- | --- |
| job created / closed | `2026-11-10T22:25:03Z` → `2026-11-10T22:34:00Z` (537 s, closed `cancelled`) |
| `coursebook.plan.generate` (plan-prompt.v13) | **468 992 ms**, 22 256 output tokens — it *answered*, inside its 900 s declared bound |
| two `coursebook.plan.validate` calls | 39 410 ms and 53 687 ms, both answered (180 s bound) |

Provenance for that row (added in review round 2, because the figures were challenged as
unreproducible). All three rows are in `usage_events`, keyed by the **job id**, not by the
idempotency key of the request that created it:

```
sqlite3 -readonly ~/.hermes/coursebook-test-cp015/home/plugin-data/coursebook/data.db \
  "select operation_id, json_extract(tokens_json,'$.purpose'),
          json_extract(tokens_json,'$.input_tokens'), json_extract(tokens_json,'$.output_tokens'),
          duration_ms, recorded_at
     from usage_events where operation_id='job_659f1edba70d491b831dd9d263539db3';"
```

| purpose | input | output | duration_ms | recorded_at |
| --- | --- | --- | --- | --- |
| `coursebook.plan.generate` | 8 123 | 22 256 | 468 992 | `2026-11-10T22:34:00Z` |
| `coursebook.plan.validate` | 7 400 | 6 042 | 39 410 | `2026-11-10T22:34:00Z` |
| `coursebook.plan.validate` | 7 480 | 8 000 | 53 687 | `2026-11-10T22:34:00Z` |

Two independent cross-checks: the host log line for that call
(`logs/agent.log:1564`, `15:33:06` local / `22:33:06Z`) reports `tokens=30379`, which is exactly
8 123 input + 22 256 output; and `gen_call_waits` has 0 rows for the job because plan jobs only
started writing those liveness rows with this fix. A query on `operation_id =
cp015-jobs-create-51d593ab9a` returns 0 rows — that string is an idempotency key for the create
call, which is why the figures looked unattributable on the first pass.

So the 648 s row was not a call the deadline failed to cut; the per-call deadline already cancels on
the host's async seam (proved by `probes/cp044-job-deadline.py` scenario A and by
`tests/test_cp044_job_deadline_hanging_provider.py::...purpose_deadline...`). What did not exist was
any **job attempt** deadline: bounded calls each finishing "in time" still leave the row `running`
for as long as the attempt chains them.

A second, older archived row (`pre-cp015-fix/data.1794347713.db`, job
`job_ec3769bfe3cc426595f183ae06854911`) shows the shape the card described: `running`, lease
`worker-f111a2e9333e` expiring `2026-11-10T21:52:41Z`, `updated_at` 21:50:41Z — a live worker holding
the row. That row's calls were held by the same missing job budget, not by a liveness failure.

## Before / after, same probe, same stub

`probes/cp044-job-deadline.py`, purpose deadline 8 s, job deadline 1.5 s. Both runs report
`base_commit: b09b65f` because they were captured before the fix was committed: the "before" run
stashed the three source files, the "after" run was the working tree that became `51d9fb4`.

| run | scenario | wall clock | job row | lease | error | stub socket | coroutine |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before (`b09b65f`) | A: no job budget | 8.33 s | `failed` | NULL | `HOST_UNAVAILABLE`, `deadline_s 8.0`, `job_deadline false` | closed | cancelled |
| before (`b09b65f`) | B: job 1.5 s | **8.31 s** | `failed` | NULL | `HOST_UNAVAILABLE`, `deadline_s 8.0`, `job_deadline false` | closed | cancelled |
| after (`51d9fb4`) | A: no job budget | 8.35 s | `failed` | NULL | `HOST_UNAVAILABLE`, `deadline_s 8.0`, `job_deadline false` | closed | cancelled |
| after (`51d9fb4`) | B: job 1.5 s | **1.77 s** | `failed` | NULL | `HOST_UNAVAILABLE`, `deadline_s 1.425`, `job_deadline true` | closed | cancelled |

Scenario B is the defect: the 1.5 s job deadline was ignored before the fix (the call ran to its own
8 s bound) and is enforced after it, with the socket closed and the lease released.

`test-red-b09b65f.log` is the new test on the pre-fix source (source files stashed): the job ran
60.2 s against an 8 s assertion bound. `test-red-round2-b09b65f.log` re-proves RED with the
**current** test file (thread-snapshot version) on a fresh `git archive b09b65f`: `Ran 2 tests in
62.490s / FAILED (failures=1)`, `AssertionError: 60.161664971965365 not less than 8.0`.
`full-suite-51d9fb4.log`: `Ran 3425 tests in 1226.195s OK (skipped=11)`.
`full-suite-round2.log` is the round-2 suite after the test-order fix.

## Test ordering (review round 2)

The first version of the new test asserted that **no** `coursebook-async-*` thread existed anywhere
in the process (`_async_threads() == []`). That is process-global, so it read another module's
housekeeping as its own failure: `tests/test_h199_lesson_deadline` deliberately leaves five such
threads winding down for ~5.5 s after it finishes (a thread blocked inside its own event loop cannot
be interrupted), so running H-199 **before** CP-044 failed deterministically (`Ran 11 …
FAILED (failures=2)`) while the reverse order passed. `discover` only passed because `test_cp044…`
sorts before `test_h199…`.

The test now snapshots the set of live `coursebook-async-*` **thread objects** before the job and
asserts that no *new* thread survives it (bounded grace of 10 s, then the survivors are named). That
is the actual claim — this job must not leak a worker — and it no longer depends on what another
module is doing.

`focused-both-orders.log`: the seven focused modules run twice, H-199 first and CP-044 first, both
`Ran 89 tests … OK`. Six H-199/CP-044 orderings (both orders, twice each) are also green:
`Ran 11 tests … OK` ×4.

## The 1800 s default

The default is policy, not a measured requirement, and the docstring says so. `probes/cp044-job-duration-census.py`
read-only census of every job in the disposable test homes
(`audit/cp044/job-duration-census.txt`): **77 distinct job rows, 45 completed, slowest completed
852 s** (`job_ee3f99b00c904664a8a1d9db8635ee94`, `2026-11-06T23:10:23Z` → `23:24:35Z`), **0 rows
above 1800 s**. That is ~2.1× margin over the worst observed legitimate run. A unit with many more
sections, or a much slower route, has to raise `COURSEBOOK_JOB_DEADLINE_SECONDS` — the budget is a
backstop for a stuck attempt, not a target.

## Known limits, not fixed here

* A **synchronous-only** host seam (`complete_structured` without `acomplete_structured`) still runs
  through the capped worker pool, where a timed-out call's worker is abandoned rather than
  interrupted: Python cannot cancel a thread, and only the host's own `timeout=` closes that socket.
  The live host exposes `acomplete_structured`, so this is not the shipped path.
* `tests/test_cp015_excerpt_grounding.py` lives on `wt/cp-015-demo-courses` and is not on this base
  (`b09b65f`), so it could not be run from this worktree. The generation, jobs, job-service,
  job-progress, H-66 and H-199 groups are green here (see the full-suite log).
