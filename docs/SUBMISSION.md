# Submission checklist

Deadline: November 11, 2026, 5:00 PM EST. Submission is three things, not one: a catalog pull
request against `hermes-agent`, a public X post with the demo that tags @NousResearch, and the
contest form. A demo over 90 seconds fails regardless of quality.

Status key: `[x]` verified on the commit named in the row, `[ ]` open, `[~]` partial or blocked on
another owner. A gate is not `[x]` because code exists; it is `[x]` because a command ran against
this commit and passed.

Release tree: **`42fcd0f5`** — the tree this submission's catalog entry pins, measured 2026-11-11 at
the 14:05 MST freeze. `desktop/plugin.js` there is `71d940ce0398220fe1d25d1ec39b1e4bdfbc2a1c257eb7eb42292c628ac4d4b8`
(`python3 scripts/build_plugin.py --check` reports the match against `desktop/src`), `node --check
desktop/plugin.js` is clean, and `bash scripts/validate-plugin.sh` reports **4/4 runtime contracts:
PASS** with `Release gate passed: 4/4 checks`. The full suite measured on the commit below it,
`fc6ec7b7`, is `Ran 4031 tests in 1475.218s … OK (skipped=12)`, exit 0; the three commits between
`fc6ec7b7` and the release tree change only `docs/` and `coursebook/workshop.py`, and the workshop's
focused pair (`tests.test_workshop`, `tests.test_cp_021_workshop_v3`) is `Ran 26 tests in 17.373s …
OK` on the release tree itself. `python3 scripts/check-docs-truth.py` passes on it.

The **H-212 tree `b9f4a197e42e4f033298d94608fcb5b63640b094`** remains the previous record: the
H-210-R2 merge over `df052ea` (the live pack round trip that closed gate 4 plus its capture under
`audit/adversarial/h210r2-pack-roundtrip/`, a `docs/`-and-`audit/`-only diff from its parent).
`desktop/plugin.js` there is `cd862140…c516`. The earlier suite count `Ran 3523 tests in 951.634s …
OK (skipped=11)` at `b1913af7`, and the `2747` at `b9f4a19`, are kept as previous-record history, not
as this tree's numbers. Every current-tree number in this file is re-derived on the release tree and
checked by `python3 scripts/check-docs-truth.py`; what was measured, and what is branch-only, is
`docs/RELEASE-EVIDENCE.md`.

The tree carries `cb.rpc` v25 (93 declared methods, 93 handlers) and `cb.db` v14 (schema v14,
migrations `0001`-`0014`): v25 is one additive amendment over v24 — CP-005 makes seven `library_item`
shelf facts required (`sections_done`, `sections_total`, `checks_recorded`, `is_new`, `subject_label`,
`cover_artifact_id`, `last_studied_at`) so a v3 card renders every number, chip and cover from one
`library.list` read; no method moves. v24 is additive over v23 and appends ten methods — GM-004's
World Studio `world.read`, `world.style.preview`, `world.generate`, `world.approve` plus
`course.mode.set`, GM-007's away-from-screen `homework.read`, `homework.create`, `homework.complete`,
`homework.skip`, and GM-018's `takehome.html`. v23 is additive over v22 — the Parent Studio take-home pack family
appends six methods (`takehome.sources`, `takehome.preview`, `takehome.create`, `takehome.approve`,
`takehome.export`, `takehome.read`) whose print artifact is bound to the source course, objective,
lesson version and content hash, with the learner page and the parent-only answer guide as
separate artifacts — v22 added GM-011's lesson-bound tutor (`tutor.ask`, `tutor.history`), and
v21 added GM-009's game-only engagement methods (`engagement.read`,
`engagement.award`); v20 is additive over v19 — `parent.blueprint.read` returns the
`sections[]` identity a fine-tune call needs (section id, objective, ordinal, title, lesson
state/version, page hash) and both it and `course.outline`'s `outline_plan` return the optional
`plan.validation` approval provenance (the durable answer to "may this version be approved?"). v19
itself added the fine-tune commands
(`plan.edit`, `plan.undo`, `lesson.revise`, `lesson.regenerate`, `parent.review.read`,
`parent.final.approve`); v12 adds the two fine-tune ledgers (`plan_revisions`, `lesson_revisions`)
in migration `0012_fine_tune_revisions`, v13 adds GM-001's Game Mode storage — nullable
`courses.presentation_mode` plus eight play/homework/tutor tables — in migration
`0013_game_mode_contracts`, and v14 removes exactly one unique key from `takehome_packs` in
`0014_takehome_pack_revision_scope`, rebuilding that table in place with rows and indexes preserved,
additive only. The suite is `Ran 3523 tests in 951.634s … OK (skipped=11)` on `master` `b1913af7`
(the tree the `tests` block of `docs/release-evidence.json` names, 2026-11-10: the CP-052 route_anchors
merge over the docs-only gate 8 commit `eaf2d41` on `07976d8`, the CP-042 pack-shipping merge over the
CP-049 audit re-pin and CP-044 merge); the release tree
`b9f4a19` measured `Ran 2747 tests in 410.301s … OK (skipped=1)` in the H-212 pass.

**The tree is not shippable today.** The pane crash and library clipping that blocked H-85 are fixed
here (H-91, merged as `670de1b`), and the suite is green, but the demo gate is still not met, no
live Desktop window has driven this exact tree, and the operator publication gate
in §0 is closed. Open gates: 7, 12, 14, 15. Partial: 5, 6, 13. Gate 9 (license) closed on
2026-11-10: MIT, `LICENSE` at `0d17824`. Gate 10 (public repository) is met by measurement on
2026-11-10: the repository is public and an anonymous clone of `master` resolves.

## 0. Hard operator gate

**Do not submit to the plugin catalog or store, publish a release, create a public release tag,
open a catalog pull request, or announce Coursebook as installable until DeseretSaint gives
explicit final sign-off in chat.** GitHub commits and pushes to the source repository are
the authorized backup path; they are not publication, and they do not authorise a catalog merge, a
tag, an announcement or the contest form. Release verification and evidence collection
may continue, but every publication gate below stays closed until that sign-off.

Status of this section after the H-111 truth pass (2026-11-08): **unchanged and closed.** No gate
below moved, no tag, catalog pull request or announcement was made, and no green release is claimed.
This pass reconciled documents with measurements on the release candidate and recorded the
branch-only evidence. The earlier harness evidence (`docs/HARNESS-E2E.md`, branch
`wt/harness-e2e-proof` at `111c7e9`) remains unmerged engineering evidence and does not satisfy gates
7 or 13.

**What changed since that pass, all of it measured:** `LICENSE` exists (MIT, 2026-11-10, gate 9), the
repository is public and clones anonymously (gate 10, measured 2026-11-10), and the catalog entry is
submitted as a draft pull request (`NousResearch/hermes-agent#152920`, opened 2026-11-10, unmerged,
gate 12 still open). Section §0 itself is unchanged: merging that pull request, tagging, announcing
and submitting the contest form still need DeseretSaint's explicit sign-off.

## 1. Gates in order

Each gate depends on the one above it. Do not start a later gate to save time; a failure there
invalidates the earlier evidence.

| # | Gate | Owner | Evidence (frozen tree `b9f4a19` unless a row names another commit) | Status |
| --- | --- | --- | --- | --- |
| 1 | Contracts frozen | Atlas | `contracts/rpc.v25.json` (93 declared methods), `contracts/db.v14.json`, `docs/REVIEW_CB001.md` | [x] |
| 2 | Platform skeleton passes admission | Sable | `bash scripts/validate-plugin.sh` on `b9f4a19`: admission PASS, `node --check` PASS, desktop contract tests PASS, runtime contracts PASS — 4/4 on 2786 files | [x] |
| 3 | Backend kernel with migrations | Cinder | At `b9f4a19`: `cb.db` v12 / `DB_SCHEMA_VERSION = 12`, migrations `0001`-`0012`; suite `Ran 2747 tests in 410.301s … OK (skipped=1)` | [x] |
| 4 | Packs import and export | Lattice | Re-driven live on `df052eaeced56ddd7238e4fb5804110ea7b36e95` (the merged release tree: the H-210-R1 `artifact.get` repair `160c522` folded in as `8fd4ec2`; `desktop/plugin.js` still `cd862140…`) through the mounted HTTP `cb.rpc` v20 route against two isolated backends: `pack.preview` → `pack.import` for `japanese-affection-context-l0` 2.1.0 and `technical-demo-pack` 2.0.0, `pack.export` twice on the same store with byte-identical results (`content_hash` `sha256:5343526d…`, archive sha256 `sha256:4aefd708…`; demo `sha256:ff5594a8…` / `sha256:747c61fd…`; the exported archive equals the imported archive byte-for-byte), then a fresh-store re-import with the same objectives / sections / checks (Japanese 4 / 4 / 4, demo 2 / 2 / 2) and the same media bytes. The step that answered `INTERNAL_ERROR` on `bc9f607` now passes: `artifact.get` resolves **every** media segment of both packs on both stores — four media links, ten live calls, six distinct digests including the two export archives — each response contract-valid with a single-prefixed `sha256:<64 hex>` matching the manifest and a download handle whose fetched bytes hash to that same digest. The legacy bare spelling was reproduced in an isolated store: a bare row reads back labelled and a later labelled import dedupes into it instead of adding a row. Evidence: `audit/adversarial/h210r2-pack-roundtrip/` (39/39 assertions PASS). The round trip ran on `df052ea`; the frozen tree `b9f4a19` is that commit plus the H-210-R2 merge, whose diff is `docs/` and `audit/` only — no product, test or contract file moved, so the capture still describes this tree | [x] |
| 5 | Desktop shell with real views | Vellum | The H-85 blockers are fixed here: `670de1b` removes the null-runtime section crash and the Library clipping that failed the gate at `7d0f9cf`. No live Desktop window has driven this exact commit; the chat composer still needs the gateway-owning profile (CB-QA-09, P3-operational) | [~] |
| 6 | Probes answer the three open questions | Sentinel | Re-run on `bc9f607` (code tree `ab6dc7e`, module `cd862140`), not carried forward: probes 1, 3, 4, 6, 7 PASS; probe 1's compression segment is now PASS in place (34 → 12 messages, `post_compaction` fired, `session_id` kept) because `compression.in_place` is on; probe 5 seam PASS with the Desktop render BLOCKED (no Electron window on this host); probe 2 stays FAIL — `pre_llm_call` injection is persisted and replayed, a host/doc mismatch, not a Coursebook defect. `PROBES.md` §"Re-run on the release candidate"; docs-truth PASS; suite `Ran 2724 tests in 541.893s … OK` | [~] |
| 7 | Demo scenarios pass on the release commit | Sentinel | `docs/ACCEPTANCE.md`; no Sentinel scenario has run on `b9f4a19` and no video exists. Gate 5 and the recording path must close first | [ ] |
| 8 | Release docs match shipped behavior | Harbor | this file, `README.md`, `docs/INSTALL.md`, `docs/M4-VISUAL-MEDIA-AUDIT.md`, `docs/RELEASE-EVIDENCE.md`; `python3 scripts/check-docs-truth.py` (full) passes on `master` `b1913af7` after the 2026-11-10 suite re-measurement (`3523 tests`, `OK (skipped=11)`) and the `cb.rpc` v26 / 93-method re-assertion, and its doc/contract/pin checks pass against the `b9f4a19` record they describe | [x] |
| 9 | License present | DeseretSaint | `LICENSE` ships MIT (copyright 2026 DeseretSaint) at `0d17824`, the owner's decision on `t_6f2d2080`; this row, README §License, `CHANGELOG.md` and the catalog `known_issues` were reconciled in the same docs commit | [x] |
| 10 | Public repository pushed | DeseretSaint | Measured 2026-11-10: `gh repo view DeseretSaint/hermes-classroom` reports `"visibility": "PUBLIC"` and an anonymous `git ls-remote https://github.com/DeseretSaint/hermes-classroom.git refs/heads/master` resolves `3278bae`. The visibility change itself has no recorded decision and no date in this repository — GitHub exposes no visibility-change timestamp for a user-owned repository — so this row records the measurement, not an approval | [x] |
| 11 | Catalog entry pins the release commit | Harbor | `catalog/coursebook.yaml` pins the H-212 docs commit `61cdb03` (one commit above the frozen code commit `b9f4a19`) and the pin is on `origin/master`; validator `OK: 1 file(s) valid`. All seven raw URLs (`docs_url`, `image` and the six `screenshots`) were fetched on 2026-11-09: HTTP 200 each, and every PNG body hashes to the same sha256 as `docs/assets/<name>.png` at `61cdb03`. The draft pull request exists: `NousResearch/hermes-agent#152920`, opened 2026-11-10, pinned to `3278bae` with `docs_url` at the README's `#install-locally` heading, and it stays draft until gates 5 and 7 close | [x] |
| 12 | Catalog PR merged | DeseretSaint | PR URL against `hermes-agent` | [ ] |
| 13 | Demo recorded and approved | Harbor, DeseretSaint | `docs/launch/coursebook-walkthrough.mp4` — the file the post attaches, measured at `origin/master` at the freeze: 42.400000 s, 1920x1080, 30/1 CFR, h264 High, yuv420p, 1272 frames, 3,025,839 B, AAC LC 48 kHz stereo, integrated **−14.8 LUFS (PASSES the `VIDEO-PLAN.md` §9.3 window of −15.0 to −13.0)**, true peak −4.2 dBTP, sha256 `9b6eed5eb6b17e17d6b0982b4f084e7571fe9090be3fe2e2c4b117486f17e620`; film of record in `docs/launch/QC.md`, provenance and licences in `docs/launch/CREDITS.md`. Recorded and measured; **the owner's approval block in QC.md is empty** | [~] |
| 14 | X post published | DeseretSaint | post URL, tags @NousResearch; copy, alt text and the 258-character count (241 weighted) are in `docs/launch/POST.md` §1. Nothing has been posted | [ ] |
| 15 | Contest form submitted | DeseretSaint | confirmation; the answer table for `https://form.typeform.com/to/FwJLvOln` is in `docs/launch/POST.md` §2 | [ ] |

Open gates: 7, 12, 14, 15. Partial: 5, 6, 13. Gate 9 (MIT license) and gate 10 (repository measured
public, anonymous clone of `master` resolves) are closed as of 2026-11-10.

Gate 5 moved back from `[ ]` to `[~]` on this tree because the plugin defect underneath it is
fixed: H-85's gate failed `7d0f9cf` on a P0 null-runtime crash in the course → section path and on
Library header clipping, and `670de1b` (merged through `494a540`) removes both. What remains is
CB-QA-09: this host runs one gateway owned by profile `default`, so a window on an isolated home has
no composer (`docs/REVIEW_CB017-FINAL.md` §3.1), plus the absence of a live drive of this commit.
Gates 7 and 13 still cannot start until the operator decides which gateway the recording runs
against.

## 2. Release verification

Run on the exact commit that will be pinned. Nothing else counts as evidence.

```
python3 -m unittest discover -s tests -t .   # Ran 2747 tests in 410.301s, OK (skipped=1)
bash scripts/validate-plugin.sh --ref <sha>  # the release gate: a clean export of the commit
bash scripts/validate.sh                     # pre-merge gate: tests, syntax, admission, doctor, probe
python3 scripts/check-docs-truth.py          # docs quote the measured values
```

Observed by this pass on `b9f4a197e42e4f033298d94608fcb5b63640b094`:

```
Ran 2747 tests in 410.301s

OK (skipped=1)
```

The release gate (`validate-plugin.sh`) was re-run in this pass on `b9f4a19`: 4/4 checks PASS on a
2786-file export. The mounted backend trace (`validate.sh` step 5) and `hermes plugins doctor` against
a live gateway were **not** re-run in this docs pass; the rows above that cite the mounted trace cite
the `29bede7` record in `docs/CB017-RELEASE-VERIFICATION.md` or mark the gap. `docs/RELEASE-EVIDENCE.md`
lists exactly what was and was not measured here.

`scripts/validate-plugin.sh` is the admission gate. It exports the commit with `git archive` into a
temporary directory outside the repository, runs `hermes plugins validate <export>`,
`node --check desktop/plugin.js` and `python3 -m unittest tests.test_desktop_contracts` against that
export, removes the export, and exits non-zero if any of the three fails. It refuses to run when
tracked files differ from `HEAD`, because the gate pins a commit; `--worktree` gates the uncommitted
edits instead, and `--ref <commit>` gates another commit.

If the capability probe fails on a fresh machine, the one declared dependency is missing:
`hermes plugins validate . --install-deps`, as `docs/INSTALL.md` describes. The gate does not install
anything.

It exports because the validator reads every directory it is given. From the checkout root,
`hermes plugins validate .` walks `.worktrees/` (one worktree per kanban task, 358 MB, gitignored)
and reports `dangerous` for adversarial fixtures and review notes that are in no version of this
package. Measured at `caa7cde`, same commit, same minute:

| Command | Result |
| --- | --- |
| `hermes plugins validate .` at the repository root, 43 worktrees present | `✗ security scan — dangerous: destructive_home_rm (REVIEW_CB003.md:32)`, `Validation failed.`, exit 1 |
| `bash scripts/validate-plugin.sh`, 443 files exported | `✓ security scan — safe`, `Validation passed.`, exit 0 |

Observed gate output at `bc4b2f9` (the commit that adds the script and this section):

```
validate-plugin: gate bc4b2f963fda82238d2047cb928b177f9e18c3fb (head, 444 files)
validate-plugin: export <temp dir> (removed on exit)
...16 admission check lines, 1 warning...
Validation passed.
desktop/plugin.js: syntax OK
Ran 7 tests in 0.004s
OK
Release gate passed: 3/3 checks on bc4b2f963fda82238d2047cb928b177f9e18c3fb (444 files).
```

The same gate at `caa7cde` reports 3/3 on 443 files; the extra file is the script itself.

`scripts/validate.sh` uses the same export for its admission step: step 3 exports the tracked working
tree with `scripts/lib/gate-export.sh` and validates that copy, so a populated `.worktrees/` farm no
longer changes the verdict, while an uncommitted edit to a tracked file still fails the step. Steps
1, 2, 4 and 5 (tests, `node --check`, doctor, mounted backend trace) run against the checkout as
before.

Expected at 0.1.0 on the CB-017 release commit (`29bede7`): **685 tests pass** (`Ran 685 tests ...
OK`; 674 on master before CB-017, 685 = 674 + 11 from the two replan branches), `desktop/plugin.js`
syntax OK, `hermes plugins validate` passes all **16** admission checks with one warning (private
core imports, see section 3), doctor reports **1 tool and 3 hooks**, the mounted backend trace
passes **31/31** expectations, and `validate.sh` ends `Validation passed.` with exit 0.
`validate-plugin.sh` on that commit ends `Release gate passed: 3/3 checks on
29bede7643403cd9d608499232125e6347c680dd (802 files).`; §1 and §1.1 of
`docs/CB017-RELEASE-VERIFICATION.md` carry the verbatim output and the clean-export install.

Fresh install path, in a throwaway home:

```
bash scripts/install-local.sh --home /tmp/coursebook-home
```

Observed: `6/6 admission gates`, `registrations: 1 tool(s), 3 hook(s)`, then `Installed.` Doctor
against that home reports `manifest: coursebook 0.1.0 (standalone)` and the same registration
count. Teardown is `bash scripts/uninstall-local.sh --home /tmp/coursebook-home`, which disables,
unlinks both halves, leaves the checkout intact and **keeps** `plugin-data/coursebook`.

An equivalent linked dev install (`HERMES_HOME=<tmp> bash scripts/install-dev.sh`, then
`hermes plugins enable coursebook`) was run for 0.1.0 as well; `scripts/install-dev.sh` does not
enable anything.

## 3. Catalog entry requirements

The entry is judged by the catalog validator and by a human reviewer. The rules below come from
`plugin-catalog/README.md` in `hermes-agent` and are the current contract, not a summary.

| Field | Requirement | State in `catalog/coursebook.yaml` |
| --- | --- | --- |
| `name` | `[a-z0-9_-]{1,64}` | `coursebook` |
| `repo` | `https://` URL | Set; repository not pushed yet |
| `sha` | exactly 40 lowercase hex characters | Pinned to this documents commit, one commit above the measured code commit `b9f4a19`; the value is in `catalog/coursebook.yaml` at branch head |
| `description` | non-empty; carries the disclosure lines | Rewritten for the 0.1.0 candidate (host seams, per-operation providers, local SQLite, no telemetry). It describes the pinned code, so text and pin agree |
| `maintainer` | non-empty | `DeseretSaint` |
| `tier` | `official`, `verified`, `community` | `community`; only Nous sets the other two |
| `category` | one of the nine shelves | `desktop` |
| `requires_hermes` | SemVer floor, not newer than current release, same as `plugin.yaml` | `">=0.23.0"` in both |
| `version` | quoted label matching the pinned code | `"0.1.0"` |
| `readme` | `true` renders the README at the pinned sha | `true`; the pinned commit must contain the README |
| `capabilities` | must match what `register()` does | `coursebook_status` and `coursebook_due`, plus the three hooks |
| `platforms` | list from linux, macos, windows | empty means all |

Additional admission rules that apply to this plugin:

- No self-updating code. Coursebook never fetches its own files.
- No compiled binaries, no committed `.pyc`. `.gitignore` already excludes bytecode.
- The Desktop half stays inside the plugin SDK. `hermes plugins validate` enforces this.
- No core overrides. The plugin uses hooks and the documented registration APIs only.
- Credentials come through Hermes. Coursebook declares no `requires_env` and stores no secrets.
- Risky behavior is disclosed in the description and in `docs/PRIVACY_EGRESS.md`.
- **Known warning, disclosed:** `hermes plugins validate .` prints one warning for private core
  imports — `coursebook/db.py` opens SQLite through `hermes_cli.sqlite_util.open_db`, and the
  `probes/scripts/` harnesses import `hermes_bootstrap` and `agent.plugin_llm` helpers. It is a
  warning, not a rejection, and it can break on a Hermes upgrade.
- Metadata gates disclosure rather than behavior: the entry must not claim image or speech
  generation (absent), reminders (absent), or a working chat composer on an isolated home
  (P3-operational, `docs/REVIEW_CB017-FINAL.md` §3.1).

Validate the entry with the current catalog validator from a `hermes-agent` checkout:

```
python3 scripts/validate_plugin_catalog.py /path/to/hermes-classroom/catalog/coursebook.yaml
```

Observed result for the draft on this branch:

```
OK: 1 file(s) valid
```

## 4. Catalog pull request

1. Bump `sha` to the release commit and bump `version` in the same change. The pin and the label
   must describe the same code.
2. Confirm `readme: true` will render: the pinned commit must contain `README.md`.
3. Add `plugin-catalog/coursebook.yaml` to a fork of `hermes-agent`.
4. Run the validator on the directory, not only the file.
5. Open the PR. The body lists the disclosure lines: local SQLite storage, provider calls per
   operation, no telemetry, no credentials, no self-update.
6. A maintainer merges. Only Nous maintainers set `tier` above `community`.

## 5. Demo gates

Gate status: **NOT MET.** The route mounts against a reachable backend; what remains is the host
gateway binding (P3-operational, `docs/REVIEW_CB017-FINAL.md` §3.1), which is an operator decision,
and Sentinel passing the demo scenarios on the exact build being recorded. Row 9 is closed end to
end on this tree (replan → lessons → export, `docs/REVIEW_CB017-FINAL.md` §10), so it no longer
holds the demo back. No recording happens without DeseretSaint's approval.

- Every shot in `docs/DEMO.md` has a passing Sentinel scenario on the release commit.
- Two precomputed segments are captioned on screen: Parent Studio pages and cached lesson media.
- Total runtime under 90 seconds, measured on the exported file, not the edit timeline.
- Claims pass: no efficacy, mastery, 2 sigma, COPPA or child safety statement anywhere in the
  video or the post.
- DeseretSaint approves the cut before upload.

## 6. Post and form

- X post tags @NousResearch and links the repository at the pinned commit.
- Post text uses the same claim limits as the README.
- Form submitted before 5:00 PM EST on November 11, 2026. Do not schedule it to the last hour.
- After submission, keep the pinned commit immutable. A later fix is a new commit and a new
  catalog PR, never a force-push over the pin.

## 7. What is blocked right now

| Blocker | Why it blocks | Owner |
| --- | --- | --- |
| No composer on an isolated home (CB-QA-09) — P3-operational, host gateway binding | One gateway per host: `hermes gateway run --force` is refused while profile `default` owns it. This is not a plugin defect: `desktop/plugin.js` mounts the library and Parent Studio whenever the window reaches a backend (`docs/REVIEW_CB017-FINAL.md` §3.1). The unblock is an operator decision on the recording path (record on the gateway-owning profile, or stop that gateway first) | DeseretSaint / Atlas |
| `evidence.inspect` returned an open check's reference answer (CB-QA-10, **fixed**) | The answer key crossed the client boundary while the check was open. Re-derived on `master` at `498b1da`: the S07 probe passes (`open_check_reference_leaks=[]`, `secret_present=False`) and `coursebook/evidence.py` projects only `PUBLIC_CRITERION_FIELDS` (`docs/HARNESS-STATUS.md` §4). The historical review at `f4a42f3` is unchanged | Cinder — no card claims this fix |
| Auxiliary grader accepts a persuaded pass (CB-QA-11) | The open-response lane cannot distinguish an honest pass from an injected one, so the lane ships disabled | Cinder |
| Demo gate not met | Sentinel's demo scenarios have not passed on the release commit, and recording needs operator approval | Sentinel, DeseretSaint |
| ~~License absent~~ (closed 2026-11-10) | MIT `LICENSE` at `0d17824`; redistribution is lawful now, publication stays closed under §0 | DeseretSaint |
| Public listing not authorised | The source repository is public (gate 10 met by measurement 2026-11-10), but a catalog merge, a tag and an announcement are publication under the operator gate, and none of them is authorised | DeseretSaint |
| No release tag | Atlas's operator gate forbids publishing a release or tag until DeseretSaint signs off in chat | Atlas, DeseretSaint |

Verified, so they are not blockers: 93/93 `cb.rpc` v26 methods mounted with no
contract problems, schema v14 from migrations `0001`-`0014`, 3523 tests on `master` `b1913af7`
(2747 on the release tree `b9f4a19`), pack round-trip and export
hash matching, eight `parent.*` methods, the replan carry with the Parent Studio plan guard, and the
full replan → lessons → export loop on contest row 9 at `29bede7` (export `exp_2e068c56`, content
hash `sha256:ccf69462…e5a5` matching the approved hash, `export.ready: true`). The UI halves beyond
the row-9 drive are unverified on this commit until the gateway condition in the first row is
resolved for the recording.

## 8. Review packet (as of 2026-11-09)

| Item | Value |
| --- | --- |
| Repository | `https://github.com/DeseretSaint/hermes-classroom` (public; `master` is pushed and clones anonymously) |
| Release branch | `master` (pushed to `origin/master`; tags, catalog PR and publication remain operator-gated) |
| Release candidate commit | `b9f4a197e42e4f033298d94608fcb5b63640b094` — frozen master: the H-210-R2 merge over `df052ea` (the live pack round trip that closed gate 4 plus its capture); the diff from `df052ea` is `docs/` and `audit/` only, and `desktop/plugin.js` is still `cd862140…c516` |
| Measured on that commit | suite `Ran 2747 tests in 410.301s … OK (skipped=1)`; `cb.rpc` v20 / 73 methods / 73 handlers; `cb.db` v12; `desktop/plugin.js` sha256 `cd862140…c516`; M4 62 frames, 15/15 claims PASS (audit measured on `ab6dc7e`, plugin pin unchanged, not regenerated) |
| Tag | none. Publication gate closed; a tag is forbidden until sign-off |
| Demo | none. `docs/DEMO.md` is the script; gate 7 unmet |
| Verification evidence | `docs/RELEASE-EVIDENCE.md`, `docs/CB017-RELEASE-VERIFICATION.md`, `docs/REVIEW_CB017-FINAL.md` (§2, §10), `docs/REVIEW_CB017-row9-ui.json`, `docs/cb017-shots/` |
| Catalog entry | Submitted as `plugin-catalog/coursebook.yaml` in `NousResearch/hermes-agent#152920` (open draft, unmerged), pinned to `3278bae` with `docs_url` at the README's `#install-locally` heading; the in-repo review copy `catalog/coursebook.yaml` pins `61cdb03`, validator `OK: 1 file(s) valid` |
| Checklist | sections 1-7 of this file: five gates open (`[ ]`: 7, 12, 13, 14, 15) and two partial (`[~]`: 5, 6) |

One gap is recorded rather than hidden: the catalog pins this documents commit, keeping the measured
code commit `b9f4a19` one below it, because an entry cannot carry its own hash. The numbers above are
measurements of `b9f4a19`, and the catalog pin was moved to the matching documents commit on the same
branch. That documents commit `61cdb03` is on `origin/master`, so its `docs_url` and the six
screenshot URLs resolve; they were fetched for 200 and hash-matched on 2026-11-09, as H-181 requires.
The catalog pull request was opened as a draft on 2026-11-10 (`NousResearch/hermes-agent#152920`)
and moves `sha`, `docs_url` and the docs record together; merging it, tagging and announcing stay
gated by §0 and by gates 5 and 7. The tree at `b9f4a19` is the one the gates ran on.
