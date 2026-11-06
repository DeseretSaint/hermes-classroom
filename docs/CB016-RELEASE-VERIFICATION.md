# CB-016 release verification on `e93b8c5`

> Superseded as the release record by `docs/CB017-RELEASE-VERIFICATION.md`, which re-derives the
> same gates on the CB-017 candidate. This file is kept for its two route condition captures (§3);
> its route conclusion (CB-QA-09 "verdict open") was superseded: Atlas reclassified the finding as
> P3-operational, a host gateway binding, in `docs/REVIEW_CB017-FINAL.md` §3.1.

Author: Harbor. Scope: release gates, a clean install and the Desktop route, on the commit this
release record pins. Everything below is a command or a capture that was run in this session;
nothing is restated from an earlier report. Evidence files are in `docs/cb016-verify/`.

Commit: `e93b8c5ad7ac642bc7da64832d8c5d53b539e599` (`origin/master` at the start of this run,
tree clean). Runner: Arch Linux host, Hermes client `v0.23.0`.

## 1. Gates on the pinned commit

```
bash scripts/validate-plugin.sh     # release gate, git-archive export of HEAD
bash scripts/validate.sh            # pre-merge gate, admission on an export of the tracked tree
```

Observed, verbatim ends of output:

| Gate | Result |
| --- | --- |
| `validate-plugin.sh` | `Release gate passed: 3/3 checks on e93b8c5ad7ac642bc7da64832d8c5d53b539e599 (787 files).` |
| admission (inside both) | `Validation passed.` (16 checks, 1 private-core warning) |
| `node --check desktop/plugin.js` | `desktop/plugin.js: syntax OK` |
| `python3 -m unittest` | `Ran 674 tests in 69.864s` — `OK` |
| `hermes plugins doctor .` | `registrations: 1 tool(s), 3 hook(s)` |
| `scripts/probe-backend.py` | `All 31 backend expectations passed against an isolated HERMES_HOME.` |
| `validate.sh` exit | `0` |

## 2. Fresh install, first-run answers

`scripts/install-local.sh --home ~/.hermes/cb016-verify/home` installed both halves into a
disposable home, enabled the plugin, and passed admission (`6/6`, `manifest: coursebook 0.1.0
(standalone)`, `1 tool(s), 3 hook(s)`, `Installed.`). The backend was started on
`127.0.0.1:44271` with `HERMES_COURSEBOOK_SINGLE_HOME=1` and answered:

```
GET /api/plugins/coursebook/runtime
  wire_contract   cb.rpc
  wire_version    7
  contract_methods 52   (implemented_methods: 52)
  plugin_root     .../.worktrees/t_9d06ae64
GET /api/plugins/coursebook/health
  ok: true, contract_version: 7, plugin_version: "0.1.0", db: {ready: true, schema_version: 4}
```

So on this commit the shipped contract is `cb.rpc` v7 over `cb.db` v4 (migration
`0004_sources_content_hash.sql`), not the v6/v3 pair the earlier README and INSTALL text quoted.

### 2.1 The same commit installed from a clean export

The run above installed the working tree. The release claim is about a checkout, so the pinned
commit was also exported with `git archive 32f67b8 | tar -x` into a directory with no `.git` and no
`.worktrees/` (793 files), then installed into a fresh home on a fresh port:

```
COURSEBOOK_TEST_HOME=<scratch>/state/home bash <export>/scripts/install-local.sh --home <scratch>/state/home
  6/6 admission gates, Validation passed., manifest: coursebook 0.1.0 (standalone), Installed.
GET /health   -> {plugin_version: 0.1.0, contract_version: 7, db: {ready: true, schema_version: 4}}
GET /runtime  -> wire_contract cb.rpc, wire_version 7, contract_methods 52, plugin_root <export>
```

The install path does not depend on the repository being a git checkout or on any sibling worktree.

## 3. The `#/coursebook` route, run twice under two conditions

The earlier release record (`docs/REVIEW_CB014.md`, CB-QA-09) says the route renders the session
home on an installed candidate. That was retested here, and it reproduces — but only in one of two
conditions. The difference matters, so both runs are recorded.

### 3a. Fresh home, Desktop window in local mode, gateway unavailable

A dedicated window (`HERMES_HOME=~/.hermes/cb016-verify/home`,
`HERMES_DESKTOP_USER_DATA_DIR=~/.hermes/cb016-verify/userdata`, CDP `9337`, dev server
`127.0.0.1:5174`) was opened without a remote connection. `window.log` fills with:

```
Error occurred in handler for 'hermes:connection:for': Error: Gateway inaccessible (runtime_exited).
the gateway exited with status 0 before it could serve:
```

Navigating to `#/coursebook` left the shell on the session list (`destination: null`); `#/capabilities`
did the same. This is the CB-QA-09 symptom.

### 3b. Same commit's Desktop half, window dialed to a reachable backend

The working CB-015 rig (`~/cb015-rig`, window on CDP `9345`, remote connection to
`127.0.0.1:44261`, dev server `127.0.0.1:5174`) had its Desktop half replaced with this commit's
`desktop/plugin.js` (sha256 `82903a52…5713d`) and the window relaunched. Navigating to
`#/coursebook`:

```
hash: #/coursebook
destination: courses
sidebarCoursebookItem: true
hasNewCourse: true
hasParentStudio: true
panePresent: true
```

The library, the `New course` action, the `Parent Studio` tab and a real course card
(`Japanese affection and register — an L0 demonstration classroom`, `0 independent · 4 objectives`,
`From a local pack · v1.0.0`) render. Captures: `docs/cb016-verify/route-mount-head-clean.json`
and `.png`. The chat connection in that window still reports `Backend offline` and the host shows
its `Hermes couldn't start` dialog, because this host already runs one gateway for the `default`
profile and refuses a second for any isolated home.

### What this changes

The route module is not what fails. In 3a the shell never got a gateway, and a shell without a
gateway renders no route page at all — host routes included. In 3b the same plugin.js mounts the
page. The release blocker named CB-QA-09 therefore has to be re-read as *the host gateway binding
fails on an isolated home, and the shell degrades to the session list instead of naming that
failure*. That is Vellum/Atlas territory, not a docs fix; this file records the evidence and does
not close the defect. Until one of them rules on it, the honest status is: **condition-dependent
mount, verdict open**.

Either way, the demo's chat shots stay unreachable on this host: a second gateway cannot start
while profile `default` owns the host gateway (`hermes gateway run --force` →
`Cannot reserve gateway profiles`), so there is no composer to bind a lesson to.

## 4. What this does not establish

- No demo was recorded. Gate 7 (Sentinel's U01-U04 on the release commit) has not been passed on
  this commit, and recording needs operator approval.
- No release tag, catalog pull request, publish or announcement. Atlas's operator gate holds all of
  those until DeseretSaint signs off in chat.
- A11y, keyboard, 200 % text and responsive rows are not re-driven here; they belong to
  `docs/REVIEW_CB015.md` and Sentinel's audit.
- `evidence.inspect` (CB-QA-10) and the disabled aux grader (CB-QA-11) are unchanged by this pass.
