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
60.2 s against an 8 s assertion bound. `full-suite-51d9fb4.log`: `Ran 3425 tests in 1226.195s
OK (skipped=11)`.

## Known limits, not fixed here

* A **synchronous-only** host seam (`complete_structured` without `acomplete_structured`) still runs
  through the capped worker pool, where a timed-out call's worker is abandoned rather than
  interrupted: Python cannot cancel a thread, and only the host's own `timeout=` closes that socket.
  The live host exposes `acomplete_structured`, so this is not the shipped path.
* `tests/test_cp015_excerpt_grounding.py` lives on `wt/cp-015-demo-courses` and is not on this base
  (`b09b65f`), so it could not be run from this worktree. The generation, jobs, job-service,
  job-progress, H-66 and H-199 groups are green here (see the full-suite log).
