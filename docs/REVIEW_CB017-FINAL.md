# CB-017 — final architecture review and winning-entry gate

Author: Atlas. Scope: one verdict on the tree that would be submitted, measured in this run on this
machine. Nothing here is restated from a sibling report; every number is a command or a live
artifact produced in this pass. Where a sibling's finding is reused it is named as theirs and the
document that carries it is cited.

Candidate measured: `wt/cb-017-atlas` at `6502e56` — master `b58679d` + the two replan merges
(`da99d8a` carry, `6502e56` UI guard). The release record Harbor pinned (`7f80f35`, branch
`wt/cb-016-harbor`) is **not** this tree and does not contain the replan fix.

## 1. Verdict

**NO-GO for submission today.** The plugin is technically sounder than at CB-014 and the P1s are
closed at the seam, but two of the card's acceptance lines are not satisfied on measured evidence:

* row 9 of the 19-row contest matrix has no completed end-to-end artifact — the lessons job the fix
  unblocks was **still `running`** when this run's budget expired, so the export half is unproven;
* no demo can be recorded on this host (one gateway per host, owned by profile `default`), and a
  contest entry without a recording is not an entry.

What is not in doubt: the backend, the pack pipeline, the state machine and the accessibility work
pass their gates, and the two defects that mattered most (route mount, replan dead end) are now
either explained or fixed with tests.

## 2. Gates on the candidate `6502e56`

| gate | command | result |
| --- | --- | --- |
| unit/integration | `python3 -m unittest discover -s tests` | **Ran 685 tests in 87.205s — OK** |
| pre-merge gate | `bash scripts/validate.sh` | **exit 0**, `Validation passed.`, `All 31 backend expectations passed against an isolated HERMES_HOME.` |
| ESM parse | `node --check desktop/plugin.js` | `syntax OK` |
| clean install | `scripts/install-local.sh --home <isolated>` | `6/6 admission`, `Validation passed.`, `1 tool(s), 3 hook(s)`, `Installed.` |
| live wire | `GET /runtime` on the installed backend | `cb.rpc` v7, 52 declared / 52 implemented, `contract_problems: []`, `plugin_root` = this worktree |

685 = 674 on master + 11 from the two replan branches (`tests/test_parent_studio.py` +
`tests/test_desktop_plan_guard.py`).

## 3. The two defects this gate had to settle

### 3.1 CB-QA-09 — route renders the session home (P1 on the CB-014 candidate)

Ruling: **not a plugin defect.** Harbor's two-condition run on the release tree
(`docs/CB016-RELEASE-VERIFICATION.md` §3) is the evidence, and it is consistent with what I saw
live: with a reachable backend at `127.0.0.1:44251` and this commit's `desktop/plugin.js`
(sha256 `c59ebc3c…8281fb`) in `<home>/desktop-plugins/coursebook/plugin.js`, the route mounted and
`data-cb-route` was present before the first click of this run's UI drive
(`docs/cb017-shots/row9r-01-plan-before-replan.png`). A window with **no** gateway renders no route
page for any hash, host routes included — that is the shell degrading, not the plugin failing.

Reclassified: **P3-operational, environment constraint**, not an open P1. Two consequences that must
be written down rather than worked around:

1. a shell with no gateway shows the session list instead of naming "no backend" — host-owned, out
   of this plugin's reach; the plugin's own `Backend off` / `Offline` states are proven separately
   (`docs/REVIEW_CB015-fault-*.json`);
2. the demo must run on the profile that owns this host's gateway (`default`), because
   `hermes gateway run --force` refuses a second one. That is an operator decision, and it is the
   single cheapest unblock for the recording.

### 3.2 Replan dead end — edited approved plan can never export (t_fc758da8)

Fixed, and the fix is what is being measured. Cinder's carry (`1ce7262`, `6337259`) copies the
authored document and sections onto a content-preserving new version and refuses when no faithful
remap exists; Vellum's guard (`78b57c3`, `b2567cd`, `dd644f9`, `3322c51`) withholds Generate lessons
for a version it has proven cannot author, and reads the plan digest at approve time.

Live evidence from this run (isolated home `~/.hermes/coursebook-test-t_fc758da8/home`, backend
`127.0.0.1:44251` serving **this** worktree, window CDP 9347):

* course `crs_3ea89399…`, plan `7bb33ee2…` → after `plan.replan` + `plan.edit` + `plan.approve`
  the current version is `pln_d25b00bb…` **v10, state `approved`**, and it **has a
  `gen_plan_documents` row** (`created_at 2026-11-06T23:45:14Z`). The dead end is gone.
* `jobs.create` with `brief.stage = lessons` for that plan produced `job_2390ab7ac33d4bff9e62d8eae5649ee7`,
  which **started running** instead of failing `INTERNAL_ERROR plan … has no authored document`
  (the pre-fix failure is still in the same database as `job_842472a63be742b18721fc8b1830bed1`).
* That job had not reached a terminal state when this run's 1800 s budget expired. Screens through
  `lessons-started` are on disk; the export and lesson-set re-approval steps are **not**.

So: the defect is closed at the seam, the contest row stays **partial**, and the honest line for the
release notes is "replan → lessons → export is fixed and proven through lesson-job start; the export
half is re-driven before the demo".

## 4. Architecture rulings

**R1 — `PRAGMA user_version` as a data-repair marker, and `ensure_schema()` rewriting
`lesson_segments`: ACCEPTED, with the conditions already written into `docs/ARCHITECTURE.md` §6.**

It does not reopen what CB-014-R1 fenced. R1 fenced *lifecycle* paths (chat turns, hooks, imports)
provisioning or mutating the store; `ensure_schema()` is still reached only from an explicit
Coursebook command, and `_repair_lesson_segments_once()` is a no-op after the marker is set. The
repair is content-exact (`"".join(pieces) == original`), order-preserving, committed in the same
`BEGIN IMMEDIATE` transaction as the marker, and it skips on contention rather than failing the
caller. The marker is not a schema version: `schema_migrations` remains the authority and nothing
else may claim `user_version`. The cost is one `PRAGMA` read per command, which is acceptable.
Conditions that must hold, and are now in the doc: no second meaning for `user_version`; the repair
never runs outside a command; a skip must leave the marker unset so the next command retries.

**R2 — 8,000-character segment cap vs a 32 MB pack section: do not touch the wire; the pack side
gets an authoring bound.**

`cb.rpc` v7 keeps `segments[].text.maxLength = 8000` and `maxItems = 500`. The import path already
refuses pre-write what cannot fit and splits what can, byte-exactly. The manifest's
`max_single_file_bytes: 33554432` is a *decompression/security* bound, not a readability promise, so
it stays. What was missing is authoring: nothing told a pack author that a lesson section above
500 × 8,000 = 4,000,000 characters can never render. Decision: document the authoring bound
(4,000,000 characters per lesson section) in the pack contract notes and surface it in the pack
validator/export path as a warning; no v7 change, no manifest change. Assigned to Lattice.

**R3 — Cinder's "behaviour note, no wire bump" on `plan.replan`: ACCEPTED.** The response shape and
error codes are untouched; the change fills staging rows inside the existing transaction. A frozen
method may gain behaviour that makes an existing success path work, but not new fields, new codes or
new methods — which is what happened here. It stays v7.

## 5. Contest matrix, as measured (19 rows)

10 live · 6 partial · 2 boundary · 1 open, unchanged from `docs/REVIEW_CB015.md` except where noted:

| row | status | note |
| --- | --- | --- |
| 9 | **live** (fix verified §3.2; export tail driven §10) | replan → plan approve → lessons complete → lesson-set approve → export, UI and backend agreeing |
| 1, 10, 13 | partial / boundary | native folder picker not automatable in the rig (t_36679b90) |
| 4 | open | chat and pane answers race — not driven |
| 3, 5, 7, 8 | partial | each names its missing half in `REVIEW_CB015.md` §12 |
| 2, 6, 11, 12, 14, 15, 16, 17, 18, 19 | live | artifacts in `docs/REVIEW_CB015-*.json` |

## 6. Risks carried into submission

| # | risk | severity | owner |
| --- | --- | --- | --- |
| 1 | row 9 export half unproven end to end | P2 | Atlas/Vellum |
| 2 | demo unrecordable while profile `default` owns the host gateway | blocking (process) | DeseretSaint |
| 3 | no license chosen | blocking (legal) | DeseretSaint |
| 4 | catalog entry is a draft, pinned to `7f80f35` (a tree without these fixes) | blocking (release) | Harbor |
| 5 | row 4 chat/pane race undriven; `evidence.inspect` reference leak (CB-QA-10, P2) open on its card | P2 | Cinder |
| 6 | aux grader lane disabled (CB-QA-11) — open-response passes can be steered by learner text | P2, lane off | Cinder |
| 7 | release docs (README/CHANGELOG/SUBMISSION/catalog) describe `e93b8c5`/`7f80f35`, not this candidate | P1-docs | Harbor |

## 7. Shortest path to GO

1. Let `job_2390ab7a…` settle; re-drive `scripts/cb015r-row9-replan-ui.mjs` to completion and commit
   the JSON + stills. (Vellum, ~1 generation cycle.) **Done — §10.**
2. Harbor re-derives README/CHANGELOG/SUBMISSION/ARCHITECTURE and re-pins the catalog on the merged
   commit, then re-runs `validate-plugin.sh --ref`.
3. Operator: approve the demo path (install into the gateway-owning profile, or stop that gateway and
   start the isolated one) and the license; approve push, tag and catalog PR.
4. Re-run this gate on the re-pinned commit; the matrix rows that remain partial stay partial and are
   printed in the release notes as such.

## 8. Evidence hashes (this run)

| file | sha256 |
| --- | --- |
| `desktop/plugin.js` | `c59ebc3c937385f1119787a5522acda09fb852f8180c06e3d3f4615e3c8281fb` |
| `coursebook/generation.py` | `3b87b305df5b1e67b0652caf2802d6916b740e64c7e181b34c0c65e7dd773437` |
| `coursebook/domain.py` | `eb4aa0e0e7ae5fb61e7bc70bf1d05c1e0849894f8213611df2498bdd40026058` |
| `coursebook/db.py` | `416e3f3ddb654cb3a821909c78f6b29a42092a622e8816c58e3e368bd9aed4a2` |
| `docs/cb017-shots/row9r-01-plan-before-replan.png` | `eb007e5c286a88a88fb407b2105c41d7a1d5624908ca0175def00ef6c77fd239` |
| `docs/cb017-shots/row9r-02-replanned-editor.png` | `91a45bd911d7301da2ae89acdc1f0d65d2e58e981390b15f7b33613000c7eebc` |
| `docs/cb017-shots/row9r-03-plan-saved.png` | `4afbf273809c55ec2ef59ea00af2facc39dbb935b3dca917beb68298cbc394c6` |
| `docs/cb017-shots/row9r-04-plan-approved.png` | `61a2e7df6913b33589bc63fd24db60b4c0ceb051de982f6d280ab8e47813a5a7` |
| `docs/cb017-shots/row9r-05-lessons-started.png` | `c31ad5af2109f0f7044ff08d50bf3514d67eca81633318f3400c41a769cb0fd1` |

Candidate commit: `6502e56090cb5cf5755d1ebd7af8202bca481897`.

## 9. Known limitations to print in the release notes

* A window with no reachable gateway renders no route page; the plugin's own degraded states are
  separate and proven.
* A structural objective `add` after a plan is authored yields a version with no covering outline:
  lessons are deliberately withheld, and the course must be started from a new brief.
* A lesson section above 4,000,000 characters cannot render in one page; imports refuse it pre-write.
* Rows 1/3/4/5/7/8/10/13 of the contest matrix are partial or open, as tabulated in
  `docs/REVIEW_CB015.md` §12. Row 9's export half was driven after this gate (§10).

# Appended after the gate verdict.

## 10. Row 9 export tail — driven (Vellum, t_1ad9e4a1)

This section is post-gate evidence appended to §3.2. It changes no other row and does not reopen the
gate verdict; it closes the one item §7 step 1 left outstanding.

**Environment.** The same isolated rig as §3.2: home `~/.hermes/coursebook-test-t_fc758da8/home`,
backend `127.0.0.1:44251` serving `wt/cb-017-atlas` at `67d6773` (`plugin_root` reported by
`/runtime`), `desktop/plugin.js` sha256 `c59ebc3c…8281fb`, window CDP **9347**.

**1 — the lessons job settled.** `job_2390ab7ac33d4bff9e62d8eae5649ee7` reached `state: completed`
at `2026-11-06T23:54:11Z` with `checkpoint.lessons = 4`, `progress.message = "4 lessons authored"`,
`error: null`. It did not fail on a missing authored document; the §3.2 fix held all the way through
generation.

**2 — the export half was driven on the real Desktop UI.** Because the gate is a separate approval,
the run picked up at `Plan approved · v10` / `Lesson set approval: Changes need review`
(approved content hash `22dae2d0…`, current `ccf69462…`, `Export the approved files` disabled), then:
`Approve this lesson set` → gate shows `Lesson set approved`, export enabled → `Export the approved
files` → exported.

> **Export exp_2e068c56b9a04ced96b872aaccb98ad0 · just now · content hash
> sha256:ccf69462cb8073a5115b01571879fd232b76af9386e919c90c89a79dc94eb5a5**

**3 — backend and disk corroborate the screen.** `parent.blueprint.read` afterwards returns
`approval.state = active` with `content_hash` equal to the approved hash above and
`export.ready = true`, `blocked_reason = null`; the plan is `pln_d25b00bb…` v10 `approved`. The
export produced real files in
`~/.hermes/coursebook-test-t_fc758da8/home/plugin-data/coursebook/pack-exports/`:
`…-9fb8dda5e750c34c.zip` (17,843 B — 13 entries: 4 parent-guide, 4 learner-page, 4 answer-guide
markdown plus `pack.json`) and `…-9fb8dda5e750c34c.pdf` (11,776 B, PDF 1.4, 7 pages).

**Artifact.** `docs/REVIEW_CB017-row9-ui.json` — UI steps and verdicts, plus a `corroboration` block
holding the backend records, export-file hashes and shot hashes. Driver:
`scripts/cb017-row9-tail.mjs` (tail-only; `node --check` OK).

| shot | sha256 |
| --- | --- |
| `docs/cb017-shots/row9r-06-export-gate-blocked.png` | `e674b02f36a521cea95d3e40d56ef7460309a47d543cc24bb7a6a9cea7bf2e6c` |
| `docs/cb017-shots/row9r-07-lesson-set-approved.png` | `ce933e643b7c0f5803692e4e31bccde50dceda8c178f29edbe96bec60ed8689a` |
| `docs/cb017-shots/row9r-08-exported-files.png` | `3fe3e227f142b2b58e5b83a4027b3283623dd5d3764b7aa7b50a8fb2f3bdb117` |
| `docs/cb017-shots/row9r-09-exported-files-detail.png` | `e8e1194b3605088e7d9bc5b62905b443fe92b2210ea4b824107e85ad60def592` |

Shots `row9r-01..05` were not re-captured; their sha256 values still match §8 exactly.

**Consequence for the matrix.** Row 9 is now live end to end for this tree — replan → plan approve →
lessons job start → lessons complete → lesson-set approve → export — with the UI and the backend
agreeing on the approved content hash. The remaining pre-submission items are the other rows, the
demo path and the re-pin, not this row.

# Appended after the fan-in.

## 11. Re-verdict on the re-pinned commit (t_45b4dcfe)

Candidate measured: `wt/cb-017-reverdict` at merge `bb6a0d8` — master `29bede7` plus the two CB-017
follow-ups, `wt/cb-017-lattice-bound` `8e05178` (the 4,000,000-character authoring bound) and
`wt/cb-017-harbor-release` `6eb93c2` (the release record re-derived and the catalog re-pinned to
`29bede7`). Both merges were clean; nothing was rewritten by hand.

`master` is still `29bede7`: neither follow-up has been merged or pushed, so this verdict is on a
local integration candidate, not on a published commit. Every number below was produced in this
pass on that candidate.

**Verdict: NO-GO for submission, with one bullet fewer than §1.** Row 9 is no longer a reason to
hold. The demo recording is now the only acceptance line that fails, and it fails on a host binding
plus an unrun measurement, not on code. §1 is left exactly as it was issued; this section is the
verdict it makes now.

### 11.1 The §1 bullet that is now satisfied

§1, bullet 1 — "row 9 of the 19-row contest matrix has no completed end-to-end artifact … the export
half is unproven" — **satisfied**. I re-read the artifact and re-hashed its evidence on disk rather
than taking the producing card's word:

* `docs/REVIEW_CB017-row9-ui.json`, sha256
  `61dcb47c4f55b803a5acc5bd741fc129f8e99b46ffc1350d18ca578934c1906b`. Its `verdicts` block records
  the three states in order: `gateBlockedBeforeApproval` (approved hash `22dae2d0…`, current hash
  `ccf69462…`, `exportDisabled: true`), `afterLessonSetApproval` (approved hash = current hash
  `ccf69462…`, `exportDisabled: false`), `afterExport` (`exportedFiles: true`) with the export
  sentence `Export exp_2e068c56b9a04ced96b872aaccb98ad0 · just now · content hash
  sha256:ccf69462cb8073a5115b01571879fd232b76af9386e919c90c89a79dc94eb5a5`.
* Its `corroboration` block is backend state, not screen-scraping: `approval.state = active`,
  `invalidated_reason = null`, `export.ready = true`, `blocked_reason = null`, plan
  `pln_d25b00bbebd442089f31e00c97e3f353` v10 `approved`; and the lessons job
  `job_2390ab7ac33d4bff9e62d8eae5649ee7` `state: completed`, `progress.message: "4 lessons authored"`,
  `error: null`.
* All four new stills hash to the values the artifact records and to the sizes it records, checked
  byte-for-byte in this pass:

| shot | bytes | sha256 |
| --- | --- | --- |
| `docs/cb017-shots/row9r-06-export-gate-blocked.png` | 199335 | `e674b02f36a521cea95d3e40d56ef7460309a47d543cc24bb7a6a9cea7bf2e6c` |
| `docs/cb017-shots/row9r-07-lesson-set-approved.png` | 193049 | `ce933e643b7c0f5803692e4e31bccde50dceda8c178f29edbe96bec60ed8689a` |
| `docs/cb017-shots/row9r-08-exported-files.png` | 215056 | `3fe3e227f142b2b58e5b83a4027b3283623dd5d3764b7aa7b50a8fb2f3bdb117` |
| `docs/cb017-shots/row9r-09-exported-files-detail.png` | 236786 | `e8e1194b3605088e7d9bc5b62905b443fe92b2210ea4b824107e85ad60def592` |

* `row9r-01..05` were not re-captured and still match §8 exactly (`eb007e5c…`, `91a45bd9…`,
  `4afbf273…`, `61a2e7df…`, `c31ad5af…`), so §8's pre-export chain is intact.
* The export itself is on disk in the rig home, and its bytes match the artifact's `export_files`
  block: `parent-crs-3ea89399…-1.0.0-9fb8dda5e750c34c.zip` 17,843 B sha256 `90cf9d20…` and
  `…9fb8dda5e750c34c.pdf` 11,776 B sha256 `638080b9…`.

§1, bullet 2 — "no demo can be recorded on this host … and a contest entry without a recording is
not an entry" — **not satisfied.** See 11.3.

### 11.2 Gates on the re-pinned candidate `bb6a0d8`

| gate | command | result |
| --- | --- | --- |
| unit/integration | `python3 -m unittest discover -s tests` | **Ran 691 tests in 69.468s — OK** |
| pre-merge gate | `bash scripts/validate.sh` | **exit 0**, `All 31 backend expectations passed against an isolated HERMES_HOME.`, `Validation passed.` |
| ESM parse | `node --check desktop/plugin.js` | `node: syntax OK` |
| release gate | `bash scripts/validate-plugin.sh` (HEAD, clean `git archive`) | **`Release gate passed: 3/3 checks on bb6a0d8a232025c4c8abfd6b2f7f87e79ad8af64 (811 files).`** |

691 = 685 at `29bede7` + 6 in `tests/test_pack_authoring_bound.py`. `desktop/plugin.js` is unchanged
by both follow-ups and still hashes `c59ebc3c937385f1119787a5522acda09fb852f8180c06e3d3f4615e3c8281fb`,
the file installed at `~/.hermes/desktop-plugins/coursebook/plugin.js`. Lattice's claimed hashes
verify on this tree: `coursebook/segments.py` `ab64b176…`, `coursebook/packs.py` `57f20f84…`,
`coursebook/pack_flow.py` `fb41741f…`, `contracts/pack-manifest.v1.json` `ca0c5e44…`.

### 11.3 What still blocks GO

**1 — the demo recording (the remaining §1 bullet).** This is not a guess about the gateway table:
the host runs exactly one gateway, owned by profile `default` — pid 360123,
`python3 -m hermes_cli.main --profile default gateway run --quiet`,
`HERMES_HOME=/home/deseretsaint/.hermes`, listening on `127.0.0.1:43829`; `hermes gateway status`
reports "✓ Gateway is running via the default-profile multiplexer" with `✓ default — PID 360123`. On this
machine `default` **is** the root home `~/.hermes`; there is no `~/.hermes/profiles/default`.

The isolated rig cannot stand in for it, and the demo card's D1 is re-attributed here rather than
accepted as written. `desktop/plugin.js` never writes `location.hash` (no occurrence in 8,061 lines);
both lesson-start paths hand the shell `host.newChat` / `host.openSession`, and the Desktop SDK
navigates by design (`apps/desktop/src/sdk/index.ts:1271` `window.location.hash = '#/'` for
`newChat`; the `openSession` navigate helper sets the hash at `:646` / `:993`). So the jump from
`#/coursebook` to `#/` is SDK behaviour, not a plugin route bug. What follows it — `mounted: false`,
`text: ""` in `audit/demo-gate/u05-resume-trace.json` — is a shell with no reachable gateway, the
same host condition §3.1 reclassified, and the demo-gate doc says so itself in its rig table
("Gateway inaccessible (runtime_exited)"). The plugin does register the lesson pane that the demo's
8-34 s shots need (`desktop/plugin.js:7991`, id `pane`, area `panes`), scoped to the focused chat's
stored id.

What is **not** measured: whether chat and pane render together on the gateway-owning profile.
Nobody has run U01-U04 or the demo shots there. So the demo gate stays **NOT MET**, and it will stay
NOT MET until that run exists on the recorded commit.

Coursebook is already installed and enabled in the gateway's home — `~/.hermes/plugins/coursebook` →
`/home/deseretsaint/Projects/hermes-classroom` (at `29bede7`) and the Desktop half at sha
`c59ebc3c…`, with `coursebook` in that `config.yaml`'s `plugins.enabled`. The demo card's operator
line (`scripts/install-local.sh --home ~/.hermes/profiles/default`) points at a directory this host
does not have and would create a second, ungated profile instead of touching the gateway owner. The
correct one-line action is:

```
hermes gateway restart
```

…followed by launching Desktop normally (the `default` profile, not the isolated rig) and driving
`docs/DEMO.md`'s shots there, with the demo gate re-run on that profile and that commit. That is
DeseretSaint's call, not the gate's.

**2 — release mechanics.** `catalog/coursebook.yaml` pins `29bede7` while the record that describes
it is one commit above; the figures in `README.md` / `docs/SUBMISSION.md` / `docs/INSTALL.md` /
`docs/CB017-RELEASE-VERIFICATION.md` (685 tests, 802 files) are true of `29bede7` and will not be
true of the final pin (691 / 811). The pin and those figures must move in the same change that lands
this record, or the catalog advertises a tree it does not describe. No push, tag or catalog PR is
made or claimed here.

**3 — license.** No license file is present. That is a legal blocker on redistribution and it is
DeseretSaint's decision, unchanged from §6 risk 3.

§6 risk 1 ("row 9 export half unproven") is **closed** by 11.1; §6 risk 2 (demo/gateway binding)
stands as item 1 above.

### 11.4 Release-note limitations, verbatim from §9

These are quoted, not paraphrased. They are the four bullets of §9 and they are what the release
notes must print:

> * A window with no reachable gateway renders no route page; the plugin's own degraded states are
>   separate and proven.
> * A structural objective `add` after a plan is authored yields a version with no covering outline:
>   lessons are deliberately withheld, and the course must be started from a new brief.
> * A lesson section above 4,000,000 characters cannot render in one page; imports refuse it pre-write.
> * Rows 1/3/4/5/7/8/10/13 of the contest matrix are partial or open, as tabulated in
>   `docs/REVIEW_CB015.md` §12. Row 9's export half was driven after this gate (§10).

The third bullet is the bound Lattice implemented in this candidate: `8,000` characters per segment
× `500` segments per `lesson.page` = **4,000,000** characters per lesson section, read from the
contract through `coursebook.segments.lesson_section_char_bound()` and never stored as a second
constant; documented in `docs/PACK-AUTHORING.md` and in the `cb.pack` description (text only — no
schema change, `max_single_file_bytes: 33554432` unchanged, `cb.rpc` v7 untouched); surfaced as a
`PackAuthoringWarning` naming file and measured length from the pack validator and the export
paths; import still refuses pre-write. `691` tests and the 31/31 backend expectations above are the
proof it holds.
