# CB-017 release verification on merged master `29bede7`

Author: Harbor. Scope: the release gates, a clean-export install and the release record on the
commit the catalog pins. Everything below is a command or an artifact produced in this session;
sibling findings are named as theirs and cited where they are used.

Release commit: `29bede7643403cd9d608499232125e6347c680dd` — the merge of the CB-017 line into
master (plan.replan carry `da99d8a`, Parent Studio plan guard `6502e56`, Atlas's review `67d6773`,
Vellum's row-9 export tail `26e782f`). Atlas's review is `docs/REVIEW_CB017-FINAL.md` (§2 gates the
pre-tail tree, §10 appends the row-9 export proof). The catalog's `sha` and `docs_url` point here.

This file is committed one docs-only commit above `29bede7`, because it describes that commit's
gates and the pin. `docs/SUBMISSION.md` §8 states that gap explicitly: at the pinned tree the
README still carries the pre-record wording, so the release-record commit has to land on master
before a catalog pull request is opened.

Runner: Arch Linux host, Python 3.14.9, Hermes client `v0.23.0`. The gates below ran in a clean
worktree checked out at `29bede7` (no dirty tracked files), not in the editing checkout.

## 1. Gates on the pinned commit

| Gate | Command | Result |
| --- | --- | --- |
| unit/integration | `python3 -m unittest discover -s tests` | `Ran 685 tests in 72.181s` — `OK` |
| release gate | `bash scripts/validate-plugin.sh` (at `29bede7`) | `Release gate passed: 3/3 checks on 29bede7643403cd9d608499232125e6347c680dd (802 files).` |
| pre-merge gate | `bash scripts/validate.sh` (at `29bede7`) | exit 0, `Validation passed.`, `All 31 backend expectations passed against an isolated HERMES_HOME.` |
| admission (inside the release gate) | `hermes plugins validate <export>` | `Validation passed.` (16 checks, 1 private-core warning) |
| ESM parse | `node --check desktop/plugin.js` | `desktop/plugin.js: syntax OK` |
| desktop contract tests (inside the release gate) | `python3 -m unittest tests.test_desktop_contracts` | `Ran 7 tests in 0.004s` — `OK` |
| clean install | `git archive 29bede7 \| tar -x`, then `scripts/install-local.sh --home <fresh>` | `6/6 admission gates`, `Installed.` |

685 = 674 on master before CB-017 + 11 from the two replan branches (`tests/test_parent_studio.py`,
`tests/test_desktop_plan_guard.py`). The wall-clock time moves with machine load (Atlas measured
87.205 s on `6502e56`, this run 72.181 s on the merged tree); the count is what the record claims.

## 1.1 The same commit installed from a clean export

`git archive 29bede7 | tar -x` into a directory with no `.git` and no `.worktrees/` (802 files),
installed into a fresh, empty home:

```
COURSEBOOK_TEST_HOME=<fresh>/home bash <export>/scripts/install-local.sh --home <fresh>/home
== 6/6 admission gates ==
Validation passed.
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 3 hook(s)
Installed.
```

The backend was started from that home on `127.0.0.1:44779` with the single-home flag the installer
writes, and answered (with the dashboard session token this run minted):

```
GET /api/plugins/coursebook/health
{"ok":true,"contract_version":7,...,"result":{"plugin_version":"0.1.0","contract_version":7,
 "db":{"ready":true,"schema_version":4},"backend":"python"}}
GET /api/plugins/coursebook/runtime
wire_contract cb.rpc   wire_version 7   contract_methods 52   contract_problems []
plugin_root <export>/src
```

The install path does not depend on the repository being a git checkout or on any sibling worktree.

## 2. The route mounts; CB-QA-09 is a host binding (P3-operational)

The plugin's route is not what fails. With a reachable backend, `#/coursebook` renders the library,
`New course` and Parent Studio; `data-cb-route` was present before the first click of the CB-017 UI
drive (`docs/cb017-shots/row9r-01-plan-before-replan.png`), and the earlier two-condition run on
`e93b8c5` shows the same module mounting against a backend and the shell rendering no route page at
all in a window without a gateway (`docs/CB016-RELEASE-VERIFICATION.md` §3).

Atlas's ruling, `docs/REVIEW_CB017-FINAL.md` §3.1: **not a plugin defect**; reclassified
**P3-operational, environment constraint**. A window with no gateway renders no route page for any
hash, host routes included — the shell degrades, the plugin never runs. Two consequences the docs
carry instead of working around:

1. a shell with no gateway shows the session list instead of naming "no backend" — host-owned, out
   of this plugin's reach; the plugin's own `Backend off` / `Offline` states are proven separately
   (`docs/REVIEW_CB015-fault-*.json`);
2. the demo must run on the profile that owns this host's gateway (`default`), because
   `hermes gateway run --force` refuses a second one. That is an operator decision and it is the
   single cheapest unblock for the recording.

## 3. Row 9 is closed end to end

Vellum drove the tail after the CB-017 gate; the record is `docs/REVIEW_CB017-FINAL.md` §10 and the
UI artifact is `docs/REVIEW_CB017-row9-ui.json` (with a corroboration block holding the backend
records, export-file hashes and shot hashes).

- The lessons job the fix unblocks settled: `job_2390ab7ac33d4bff9e62d8eae5649ee7` reached
  `state: completed` at `2026-11-06T23:54:11Z` with `checkpoint.lessons = 4`,
  `progress.message = "4 lessons authored"`, `error: null` — it did not fail on a missing authored
  document.
- The export half was driven on the real Desktop UI: `Approve this lesson set` → the gate showed
  `Lesson set approved`, export enabled → `Export the approved files` →
  `Export exp_2e068c56b9a04ced96b872aaccb98ad0 · just now · content hash
  sha256:ccf69462cb8073a5115b01571879fd232b76af9386e919c90c89a79dc94eb5a5`.
- Backend and disk corroborate the screen: `parent.blueprint.read` returns `approval.state = active`
  with a `content_hash` equal to the approved hash, `export.ready = true`, `blocked_reason = null`;
  the plan is `pln_d25b00bb…` v10 `approved`. The export produced a 13-entry zip (17,843 B) and a
  7-page PDF (11,776 B) in `pack-exports/`.
- Shots `row9r-06..09` are committed with their sha256 values in `REVIEW_CB017-FINAL.md` §10.

So the contest row is **live end to end for this tree**. The release notes say so, and they no
longer carry the "proven through lesson-job start" caveat.

## 4. What this does not establish

- No demo was recorded. Gate 7 (Sentinel's U01-U04 on the release commit) has not been passed and
  recording needs operator approval; the chat composer is unreachable on this host while profile
  `default` owns the only gateway (§2).
- No release tag, catalog pull request, publish or announcement. The operator gate holds all of
  those until DeseretSaint signs off in chat. The catalog entry is a draft and is not submitted.
- Row 4 (chat/pane answer race) is still open; `evidence.inspect`'s reference leak (CB-QA-10) and
  the disabled auxiliary grader lane (CB-QA-11) are unchanged by this pass.
- A11y, keyboard, 200 % text and responsive rows are not re-driven here; they belong to
  `docs/REVIEW_CB015.md` and Sentinel's audit.
- No new Desktop session was driven for this record. The route and row-9 captures are Atlas's and
  Vellum's stills from the CB-017 gate and its tail; this pass re-ran the command-line gates and the
  clean install on the pinned commit.
