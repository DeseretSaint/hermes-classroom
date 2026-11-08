# H-68 — isolated serve could not read profile provider secrets

Status: **fixed, tested, committed as source backup. Nothing pushed, tagged or published.**

- Host repo: `~/.hermes/hermes-agent`
- Branch: `wt/h68-serve-secret-scope` (detached base `2bd378ed1b`)
- Commit: `c02e6e0180`
- Repro rig: `~/.hermes/harbor-h68-1794085688` (`home` = isolated HERMES_HOME, `plugins/h68probe`)

## 1. Reproduction (real `hermes serve --isolated`, no mock)

`hermes serve --isolated --port 45168 --skip-build` with `HERMES_HOME=<rig>/home`, a probe plugin
whose `register(ctx)` starts a worker under `contextvars.copy_context()` — the exact shape
Coursebook's job tick uses — then calls `ctx.dispatch_tool("web_search"/"web_extract")`.

Before the fix (`probe-pre-fix` observation, same script):

| step | result |
|---|---|
| `web_search` | ok, real results (brave-free, keyless) |
| `get_provider_env("FIRECRAWL_API_KEY")` | `UnscopedSecretError`: "Hermes could not read this profile's FIRECRAWL_API_KEY (an internal profile-scoping bug on the multiplexed gateway…)" |
| `web_extract` | failed with that same error → 0 documents |
| scope state at register | `multiplex_active=false, scope_bound=false` |
| scope state at call | `multiplex_active=true, scope_bound=false` |

This matches `audit/adversarial/h63-live-generation/H63F-evidence.json` (H-63F, D-H63-3) — the
same error the live RPC plan hit, reproduced here at the host seam without the plugin.

## 2. Root cause

`hermes serve` loads plugins during boot, then runs `activate_multi_profile_hosting_eagerly()` as
its **last** boot step (`hermes_cli/web_server.py`). Activation flips `get_secret` to fail closed for
unscoped contexts. A plugin worker started from `register()` copied a context **before** the flip,
so it carries no profile secret scope and every credential read in it raised after activation. In a
plain CLI process multiplexing never flips, so the same call resolved `os.environ` / `.env` and
worked — exactly the reported asymmetry.

## 3. Fix (host, 4 files + 1 test)

- `hermes_cli/plugins_loader.py` — `_plugin_launch_body_scope()`: mark discovery/registration as a
  launch-profile body via the existing `launch_profile_policy.launch_body()` seam. Nothing is bound
  while single-profile; after a mid-life flip, an unscoped read resolves the launch profile's own
  frozen mapping (`launch_secret_scope`) instead of raising. A secondary profile's bound scope
  still wins.
- `hermes_cli/plugins.py` — `discover_and_load()` runs under that scope.
- `agent/secret_scope.py` — `secret_scope_available()`: a launch-body fallback counts as a
  credential source.
- `agent/web_search_provider.py` — `_secret_scope_state()` uses it, so a genuinely absent key is
  `""` (keyless routing) instead of an "internal profile-scoping bug" accusation.
- `tests/hermes_cli/test_plugin_load_launch_secret_scope.py` — regression test.

Not changed: the per-profile secret boundary. The fallback is the launch profile's own mapping
(`launch_secret_scope`: frozen launch env + `<home>/.env`), never a live `os.environ` read from
another profile, and an unscoped context under multiplexing still raises (asserted in the test).
No secret is copied into the plugin and no secret value is printed.

## 4. Test results (exact)

- `tests/hermes_cli/test_plugin_load_launch_secret_scope.py`: **1 passed**. With the one-line
  `discover_and_load` scope removed it **fails** (`UnscopedSecretError` in the captured context),
  so it is a true regression test.
- Suites run together: `test_plugin_load_launch_secret_scope.py`, `tests/agent/test_secret_scope.py`,
  `tests/gateway/test_launch_profile_scope_fallback.py`,
  `tests/gateway/test_multiplex_background_task_scope.py`, `tests/tools/test_web_tools_perplexity.py`,
  `tests/tools/test_web_free_fast_search.py` → **54 passed**.
- `ruff check` on all changed files: clean.
- Runner note: the repo ships no pytest in its runtime venv; tests ran with a scratch venv
  (`pytest 9.2.0`, `pytest-asyncio 1.4.1`) layered on the runtime interpreter. Two async tests in
  `test_launch_profile_scope_fallback.py` fail only without `pytest-asyncio`; they pass with it.

## 5. Live acceptance after the fix

`hermes serve --isolated --port 45168` with the same isolated home:

`audit/h68/probe-fixed.json` — worker context after activation:
`web_search` ok (3 real results, `seriouseats.com`), `web_extract` ok (**1 document, 4523 chars**,
`lodgecastiron.com`), `get_provider_env(FIRECRAWL_API_KEY)` → `non_empty: false` (no key in this
profile → keyless route), no error. No secret value appears in the probe or the serve log.

Coursebook H-63F acceptance re-run over the real RPC path (same serve, `HERMES_DASHBOARD_SESSION_TOKEN`,
coursebook plugin enabled):

- `course.create` → `enrollment.create` → `jobs.create` (`audit/h68/create-h68.json`)
- job `job_18e2916bd1684036b1ee0df26c8e950c`: `completed` at 165 s, `plan authored (needs_review)`
  (`audit/h68/plan-job.json`)
- research ledger `114a08e40b09c49a`: `status: "ok"`, 2 queries, 5+5 results, **4 fetched sources**
  (`extension.umaine.edu`, `extension.msstate.edu`, `polk.ces.ncsu.edu`, `lodgecastiron.com`), each
  with `fetched_at` and a content hash, `failures: []` (`audit/h68/research-run.json`)
- no `gen_validation_records` row was produced for this run (`audit/h68/validation-records.json`),
  so there is no validator verdict to report. Plan `752bb7935176cbdc` sits at `draft` awaiting human
  review — the product's normal terminal-for-the-job, approvable-by-a-human state.

That closes the H-63F deferred acceptance: `research.status` is no longer `unavailable` on the live
RPC path, and the job reaches a terminal state that is reviewable.

## 6. Honest limits

- One live plan run; not a statistical claim about plan quality. The plan itself was authored with
  no usable procedure text from the fetched pages (its own exclusions say so) — grounding worked,
  authoring quality is a separate Coursebook concern.
- The isolated home has no provider API keys, so search/extract exercised the keyless tiers. The
  key-present path is proved by the regression test (profile `.env` value resolved in a serve-owned
  context), not by a live paid call.
- Nothing pushed to GitHub, no tag, no catalog publication.
