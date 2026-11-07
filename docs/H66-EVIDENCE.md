# H-66 liveness evidence

Recorded 2026-11-07 on `wt/h66-liveness-r2`. This file captures what was observed, how it was
reproduced, and what the fix reports. It is evidence, not a release record.

## 1. The live incident (as observed on the isolated backend)

`jobs.create(kind=plan)` returned `job_8404917e65334eb9982bbbf973dbe148` for course
`crs_c814…` (a repair one-off).

| Observation | Value |
| --- | --- |
| entered `running` | `2026-11-07T19:25:39Z` |
| still `running` at | `2026-11-07T19:34:38Z` (9 min 0 s later) |
| `lease_expires_at` | `2026-11-07T19:27:39Z` — already past |
| `updated_at` | `2026-11-07T19:25:39Z` — never moved |
| `progress_json` / `checkpoint_json` | `{}` / `{}` |
| heartbeat thread | no visible renewal (the `coursebook-job-tick` thread existed) |
| `jobs.cancel` | returned `cancel_requested`; no boundary was reached |

The gateway's own log shows the tick thread was created, so the job was not simply never started:

```
2026-11-07 10:54:00,830 WARNING coursebook.executor: coursebook job tick started on its own thread: kind=plan interval=5.0s limit=5
```

The row was later moved to `cancelled` at `2026-11-07T19:35:41Z`, which is why the current
database no longer shows a stuck `running` row:

```
job_8404917e65334eb9982bbbf973dbe148|plan|cancelled|…|2026-11-07T19:25:39Z|2026-11-07T19:35:41Z|{}|{}
```

## 2. Offline reproduction — `probes/h66-liveness.py`

The probe is finite by construction: each stalled call is watched for a fixed window and then
reported, so it terminates even on the broken tree. It uses a temp profile and never touches the
live backend.

### Before the fix

```
A. host tool: dispatch_tool calls = 1
A. host tool: HermesToolSearch.search still blocked after 2s = True
B. provider: declared deadline_s = 1.0
B. provider: _call_llm still blocked after 2s = True (elapsed 2.0s)
C. heartbeat: threads alive = ['MainThread', 'coursebook-job-tick', 'job-heartbeat-job_2bc6b5bf0767492f9248005fddd72f37']
C. heartbeat: lease at stage start = 2026-11-07T19:47:27Z
C. heartbeat: lease after 1.8s     = 2026-11-07T19:47:27Z
C. heartbeat: lease renewed during the stage = False
C. heartbeat: row at stage start = {
  "attempt_id": "att_193d6f350e954c5baae345dc5c399776",
  "id": "job_2bc6b5bf0767492f9248005fddd72f37",
  "lease_expires_at": "2026-11-07T19:47:27Z",
  "lease_owner": "worker-ea0b13cfa4ef",
  "progress_json": "{}",
  "state": "running",
  "updated_at": "2026-11-07T19:47:25Z"
}

RESULT host_seam_stall=True provider_stall=True heartbeat_not_renewed=True
```

Three independent faults, in the order the probe hits them:

1. `HermesToolSearch.search` handed the call straight to `ctx.dispatch_tool`; there was no deadline
   anywhere in the adapter. A host tool that blocks blocks the job stage.
2. `generation._call_llm` forwarded `timeout=` to the host and checked elapsed time only *after* the
   call returned. A host that ignores the argument is unbounded.
3. The heartbeat thread exists and is alive, but the lease never moved. The thread starts with an
   empty `contextvars.Context`; the probe carries the active profile as a context-local home
   override (as the gateway does) with `HERMES_HOME` pointing elsewhere, so every `renew` opened
   the wrong database, got `NOT_FOUND`, and was swallowed by `except Exception: continue`. The row
   stayed `running` with a past lease while the stage was blocked.

### After the fix

```
A. host tool: dispatch_tool calls = 1
A. host tool: declared deadline_s = 0.5, elapsed = 0.50s
A. host tool: unbounded (elapsed > 2s) = False
A. host tool: outcome = {
  "error": "ResearchTimeout: web_search exceeded its 0.5s deadline; research cannot wait"
}
B. provider: declared deadline_s = 0.5
B. provider: _call_llm elapsed = 0.50s, unbounded = False
B. provider: outcome = {
  "error": "ProviderTimeout: coursebook.plan.generate exceeded its 0.5s deadline"
}
C. heartbeat: threads alive = ['MainThread', 'coursebook-host-call-1', 'coursebook-host-call-2', 'coursebook-job-tick', 'job-heartbeat-job_37d02fc0aa014aa6a8d204ae39f40a36']
C. heartbeat: lease at stage start = 2026-11-07T20:02:59Z
C. heartbeat: lease after 1.8s     = 2026-11-07T20:03:00Z
C. heartbeat: lease renewed during the stage = True
C. heartbeat: row at stage start = {
  "attempt_id": "att_c09f514a2b78417293b60a8e4dbf19de",
  "id": "job_37d02fc0aa014aa6a8d204ae39f40a36",
  "lease_expires_at": "2026-11-07T20:02:59Z",
  "lease_owner": "worker-652b68d3198f",
  "progress_json": "{}",
  "state": "running",
  "updated_at": "2026-11-07T20:02:57Z"
}

RESULT host_seam_stall=False provider_stall=False heartbeat_not_renewed=False
```

The two `coursebook-host-call-*` threads are the capped pool's reused workers; the probe's two
stalled calls each abandoned one slot at their deadline and released it when the fake returned.
They are daemon threads from a fixed-size pool, not one thread per call.

## 3. Regression suite

`tests/test_h66_liveness.py` — 17 tests, all passing at the H-66 commit:

| Scenario | Test |
| --- | --- |
| stalled host tool, typed timeout | `HostToolDeadlineTest.test_stalled_web_search_returns_a_typed_timeout` |
| one timeout ends the research pass | `HostToolDeadlineTest.test_one_stalled_tool_does_not_burn_the_whole_query_budget` |
| stalled provider, typed timeout | `ProviderDeadlineTest.test_sync_only_host_is_cut_off_at_its_deadline` |
| async sibling cancelled, no thread parked | `ProviderDeadlineTest.test_async_sibling_is_preferred_and_cancelled_at_the_deadline` |
| pool reuse / capped capacity | `ProviderDeadlineTest.test_bounded_pool_reuses_one_worker_in_the_normal_path`, `…capacity_fails_fast…` |
| heartbeat renewal under a context-local home | `HeartbeatTest.test_lease_is_renewed_while_a_stage_runs_under_a_context_local_home` |
| cancel while running / at a deadline | `CancellationTest.test_cancel_that_times_out_a_provider_call_ends_cancelled_not_failed` |
| no cancel_requested left live | `CancellationTest.test_cancel_requested_job_is_never_left_in_a_live_state` |
| restart + live reconciliation | `ReconciliationTest` (3 tests) |
| reaper thread, no restart needed | `ReaperThreadTest` (2 tests) |
| end-to-end stalled plan job terminates | `EndToEndPumpTest` (2 tests) |

Full tree at the commit: `Ran 1590 tests in 170.360s` — `OK (skipped=1)`.

## 4. What this evidence does not claim

- No live backend run was performed after the fix: the isolated backend was left alone, and the
  probe uses synthetic host seams. The live incident row is shown above; the mechanism is
  reproduced offline.
- A synchronous host call that ignores its deadline is still not killed. It holds one capped pool
  slot until it returns; the bound is the pool size, not the call.
- The provider deadline bounds one call. A multi-call stage can take several deadlines.
