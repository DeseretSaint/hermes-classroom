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
| 9 | partial → **partial (fix verified, export half pending)** | §3.2 |
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
   the JSON + stills. (Vellum, ~1 generation cycle.)
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
* Rows 1/3/4/5/7/8/9/10/13 of the contest matrix are partial or open, as tabulated in
  `docs/REVIEW_CB015.md` §12.
