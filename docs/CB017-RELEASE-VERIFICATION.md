# CB-017 release verification on the CB-017 release commit

Author: Harbor. Scope: the release gates, a clean-export install and the route finding on the tree
that would be submitted. Everything below is a command or a capture run in this session; nothing is
restated from a sibling report except where that report is named as the author of a ruling.

Candidate: `wt/cb-017-atlas` at `67d6773` — master `b58679d` + `da99d8a` (plan.replan carry) +
`6502e56` (Parent Studio plan guard) + Atlas's review commit. Atlas's review of the same tree is
`docs/REVIEW_CB017-FINAL.md`; this file re-derives the release half of it and re-pins the catalog.
Runner: Arch Linux host, Python 3.14.9, Hermes client `v0.23.0`.

The release commit is `d142a1e23ceeab6ceec13c457e4f41ac1508cf6c` (the commit that carries this
file). Its sha is pinned in `catalog/coursebook.yaml`; a catalog file cannot contain its own sha, so
the re-pin commit on top of the release commit is where the number is written down. Everything in
§1 was measured before the commit; §1.1 is the same commit gated and installed afterwards.

## 1. Gates on this tree

| Gate | Command | Result |
| --- | --- | --- |
| unit/integration | `python3 -m unittest discover -s tests` | `Ran 685 tests in 74.216s` — `OK` |
| pre-merge gate | `bash scripts/validate.sh` | exit 0, `Validation passed.`, `All 31 backend expectations passed against an isolated HERMES_HOME.` |
| ESM parse | `node --check desktop/plugin.js` | `syntax OK` |
| release gate (pre-commit) | `bash scripts/validate-plugin.sh --worktree` | `Release gate passed: 3/3 checks on 67d67730fc5c2bbc42add24c9cbf8cbd54d2a621 (796 files).` |
| admission (inside both gates) | `hermes plugins validate <export>` | `Validation passed.` (16 checks, 1 private-core warning) |

685 = 674 on master + 11 from the two replan branches (`tests/test_parent_studio.py`,
`tests/test_desktop_plan_guard.py`). The `--worktree` run is what a pre-commit gate can do: it
exports the tracked working tree. The `--ref` run on the commit itself, and the clean-export
install, are in §1.1 and were produced after this file was committed.

## 1.1 The committed tree: release gate and a clean-export install

`bash scripts/validate-plugin.sh --ref d142a1e23ceeab6ceec13c457e4f41ac1508cf6c`, verbatim end:

```
validate-plugin: gate d142a1e23ceeab6ceec13c457e4f41ac1508cf6c (head, 803 files)
validate-plugin: export <temp dir> (removed on exit)
== 1/3 plugin admission: PASS ==
Validation passed.
== 2/3 desktop module: PASS ==
desktop/plugin.js: syntax OK
== 3/3 desktop contract tests: PASS ==
Ran 7 tests in 0.004s
OK
Release gate passed: 3/3 checks on d142a1e23ceeab6ceec13c457e4f41ac1508cf6c (803 files).
```

The same commit was exported with `git archive` into a directory with no `.git` and no
`.worktrees/` (803 files) and installed into a fresh, empty home:

```
COURSEBOOK_TEST_HOME=<fresh>/home bash <export>/scripts/install-local.sh --home <fresh>/home
== 6/6 admission gates ==
Validation passed.
  manifest: coursebook 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 1 tool(s), 3 hook(s)
Installed.
```

The backend was started from that home on `127.0.0.1:44778` with the single-home flag the installer
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

The plugin's route is not what fails. On this tree, with a reachable backend, `#/coursebook` renders
the library, `New course` and Parent Studio; the state `data-cb-route` was present before the first
click of Atlas's UI drive (`docs/cb017-shots/row9r-01-plan-before-replan.png`), and Harbor's earlier
two-condition run on `e93b8c5` shows the same module mounting against a backend and the shell
rendering no route page at all in a window without a gateway
(`docs/CB016-RELEASE-VERIFICATION.md` §3).

Atlas's ruling, `docs/REVIEW_CB017-FINAL.md` §3.1: **not a plugin defect**; reclassified
**P3-operational, environment constraint**. A window with no gateway renders no route page for any
hash, host routes included — the shell degrades, the plugin never runs. Two consequences the docs
now carry instead of working around:

1. a shell with no gateway shows the session list instead of naming "no backend" — host-owned, out
   of this plugin's reach; the plugin's own `Backend off` / `Offline` states are proven separately
   (`docs/REVIEW_CB015-fault-*.json`);
2. the demo must run on the profile that owns this host's gateway (`default`), because
   `hermes gateway run --force` refuses a second one. That is an operator decision and it is the
   single cheapest unblock for the recording.

## 3. Row 9 of the contest matrix: partial, and the line it gets

The replan dead end is fixed and measured: after `plan.replan` + `plan.edit` + `plan.approve` the
plan is at `pln_d25b00bb…` **v10, state `approved`**, it has a `gen_plan_documents` row, and
`jobs.create` with `brief.stage = lessons` produced `job_2390ab7ac33d4bff9e62d8eae5649ee7`, which
started running instead of failing `INTERNAL_ERROR plan … has no authored document` — the pre-fix
failure is still in the same database as `job_842472a63be742b18721fc8b1830bed1`
(`docs/REVIEW_CB017-FINAL.md` §3.2).

That job had not reached a terminal state when the gate's 1800 s budget expired, so the export and
lesson-set re-approval steps were not driven. Screens through `lessons-started` are on disk in
`docs/cb017-shots/`. The release notes therefore carry, verbatim:

> replan → lessons → export is fixed and proven through lesson-job start; the export half is
> re-driven before the demo

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
- The route captures referenced here are Atlas's stills from the CB-017 gate and Harbor's captures
  from the CB-016 run; no new Desktop session was driven for this record.
