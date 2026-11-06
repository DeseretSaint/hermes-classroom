# Upstream report draft — review lane dies when the assignee disables `sdlc-review`

Status: **draft, operator-gated.** Atlas (Coursebook architect) wrote this from live evidence on
this host. Nothing has been filed or published. Target: `NousResearch/hermes-agent` issues.

Reproduces on `2bd378ed1b` (running host) and still present in `origin/HEAD` `90d6b98fd8`
(209 commits ahead), so it is not fixed upstream as of 2026-11-06.

## Summary

`kanban.review_dispatch` (default `true`) force-loads the `sdlc-review` skill into any card claimed
from the `review` column. If the assignee profile lists `sdlc-review` under `skills.disabled`, the
managed worker raises `ValueError('kanban_skills_unavailable')` before its first model turn and
exits 1. The dispatcher then retries; `failure_limit` (default 2) auto-blocks the card. Nothing in
the card, the run error, or the operator-facing text names the actual cause — and one of the
surfaces reports it as `Kanban owner refused: ...`, which points operators at permissions and stale
claims.

The combination is reachable by configuration alone: `config_defaults.py` documents
`review_dispatch` as "disable where every review is done manually from the dashboard" and the
dispatcher comments describe operators disabling the skill for human-only review boards. Doing the
second without the first produces a silent crash loop.

## Code path

- `hermes_cli/kanban_db_dispatch.py:2146-2149` — on `lane == "review"`, task skills get
  `sdlc-review` appended unconditionally.
- `gateway/session_kanban.py:45-48` — the admission policy does the same for a review-lane run.
- `gateway/session_kanban.py:385-388` — `build_preloaded_skills_prompt(...)`; if nothing loaded and
  anything is missing, `raise ValueError('kanban_skills_unavailable')`.
- `agent/skill_commands.py:953-980` — `build_preloaded_skills_prompt` calls `_load_skill_blocks`
  with `disabled_as_missing=True`, so an operator-disabled skill is reported as *missing* and the
  caller cannot tell a config choice from a packaging error.
- `agent/skill_utils.py:281-293` — `get_disabled_skill_names()` reads the **current process** home,
  which at dispatch time is the owner's profile, not the assignee's. Any gate written here must
  resolve the assignee's profile config explicitly.
- `hermes_cli/kanban_worker_client.py:188-190` — `except (KeyError, ValueError, OSError)` prints
  `Kanban owner refused: {exc}`, so any local config error is reported as an owner refusal.
  (In the in-process managed-worker path the failure instead appears as
  `managed worker lost` / `exited with code 1`.)

## Reproduction observed (live board, not a reduced harness)

Coursebook board, 8 runs across 3 cards, 3 profiles:

```
run  card        assignee  result
8    t_3eb83beb  harbor    crashed, exit 1, worker_result.last_output = ""
9    t_3eb83beb  harbor    crashed, exit 1, worker_result.last_output = ""
12   t_cd2a83f7  atlas     crashed, exit 1
13   t_cd2a83f7  atlas     crashed, exit 1
29   t_80b6b5cd  cbqa      crashed, exit 1
30   t_80b6b5cd  cbqa      crashed, exit 1
39   t_80b6b5cd  cbqa      crashed, exit 1
40   t_80b6b5cd  cbqa      crashed, exit 1
```

Each run has exactly one `owner_admitted` and one `worker_bound` event — the owner admitted every
request — and the worker log carries:

```
File ".../gateway/session_kanban.py", line 388, in _run_task_turns
    raise ValueError('kanban_skills_unavailable')
ValueError: kanban_skills_unavailable
```

Removing the single `sdlc-review` entry from the assignee's `skills.disabled` made the same card
succeed on the next attempt (`worker_result.exit_code = 0`), which isolates the trigger to that
config entry rather than to the card, profile, or board.

Minimal repro recipe:

1. Profile `p` with `kanban.review_dispatch: true` (default) and `skills.disabled: [sdlc-review]`.
2. Create a card, assign it to `p`, run it to `review`, request review (or move it to `review`).
3. The dispatcher claims it, spawns a worker, and the run crashes in `_run_task_turns` with empty
   `last_output`; after `failure_limit` attempts the card auto-blocks with no cause named.

## Proposed fix

1. **Gate the claim.** In the review lane, resolve the *assignee* profile's `skills.disabled`
   before spawning (not the dispatcher's own config — see `skill_utils.py:281`). If
   `sdlc-review` is disabled there, do not spawn: record a typed failure such as
   `review_skill_disabled:<profile>` and block the card once with a message naming the profile and
   both remedies (enable the skill for the profile, or set `kanban.review_dispatch: false`).
2. **Stop flattening disabled into missing.** Pass `disabled_as_missing=False` at the kanban call
   site, or raise a typed error that carries `missing` and `disabled` separately, so
   `kanban_skills_unavailable` stops describing a configuration choice as an execution failure.
3. **Narrow "owner refused".** `kanban_worker_client.py:188-190` should use that wording only for
   admission/claim/permission errors; other exceptions should print their own message.

Do **not** degrade silently to "omit the review skill and continue". `sdlc-review` carries the
approve / request-changes discipline, and a review-lane worker keeps the `kanban` toolset, so an
omitted review skill lets a worker close a card it was meant to review. Refusing to dispatch is the
safe degradation; continuing without the protocol is not.

## Suggested test

A review-lane card whose assignee has `sdlc-review` disabled must not spawn a worker and must not
crash: it should settle with the typed reason above (`tests/hermes_cli/test_kanban_review_lifecycle.py`
currently has no disabled-skill case; `grep -rn kanban_skills_unavailable tests/` is empty).
