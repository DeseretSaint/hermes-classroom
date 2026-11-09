# Submission checklist

Deadline: November 11, 2026, 5:00 PM EST. Submission is three things, not one: a catalog pull
request against `hermes-agent`, a public X post with the demo that tags @NousResearch, and the
contest form. A demo over 90 seconds fails regardless of quality.

Status key: `[x]` verified on the commit named in the row, `[ ]` open, `[~]` partial or blocked on
another owner. A gate is not `[x]` because code exists; it is `[x]` because a command ran against
this commit and passed.

Current measurement commit: **`ab6dc7e3e769dcfa8c8ce5bb2b9425dffb3de815`** (merged `master`, the settled
H-209 union: H-208's H-183/H-189/H-192c/H-199 integration with H-206 and the H-182/D1-D3 renderer
work, the H-182/D8 residual learner copy, the H-182/D6 reaper/pump store scope, the validator-reject
fix, and the private test `node_modules` isolation).
Every current-tree number in this file is re-derived there and checked by
`python3 scripts/check-docs-truth.py`; what was measured, and what is branch-only, is
`docs/RELEASE-EVIDENCE.md`.

The tree carries `cb.rpc` v20 (73 declared methods, 73 handlers) and `cb.db` v12 (schema v12,
migrations `0001`-`0012`): v20 is additive over v19 — `parent.blueprint.read` now returns the
`sections[]` identity a fine-tune call needs (section id, objective, ordinal, title, lesson
state/version, page hash) and both it and `course.outline`'s `outline_plan` return the optional
`plan.validation` approval provenance (the durable answer to "may this version be approved?") — and
adds no method — and v19 itself added the fine-tune commands
(`plan.edit`, `plan.undo`, `lesson.revise`, `lesson.regenerate`, `parent.review.read`,
`parent.final.approve`); v12 adds the two fine-tune ledgers (`plan_revisions`, `lesson_revisions`)
in migration `0012_fine_tune_revisions`. The suite is `Ran 2724 tests in 533.270s … OK` at the
measured commit `ab6dc7e`.

**The tree is not shippable today.** The pane crash and library clipping that blocked H-85 are fixed
here (H-91, merged as `670de1b`), and the suite is green, but the demo gate is still not met, no
license exists, no live Desktop window has driven this exact tree, and the operator publication gate
in §0 is closed. Open gates: 7, 9, 12, 13, 14, 15. Partial: 4, 5, 6, 10, 11.

## 0. Hard operator gate

**Do not submit to the plugin catalog or store, publish a release, create a public release tag,
open a catalog pull request, or announce Coursebook as installable until DeseretSaint gives
explicit final sign-off in chat.** GitHub commits and pushes to the private source repository are
the authorized backup path; they are not publication. Release verification and evidence collection
may continue, but every publication gate below stays closed until that sign-off.

Status of this section after the H-111 truth pass (2026-11-08): **unchanged and closed.** No gate
below moved, no tag, catalog pull request or announcement was made, and no green release is claimed.
This pass reconciled documents with measurements on the release candidate and recorded the
branch-only evidence. The earlier harness evidence (`docs/HARNESS-E2E.md`, branch
`wt/harness-e2e-proof` at `111c7e9`) remains unmerged engineering evidence and does not satisfy gates
7 or 13.

## 1. Gates in order

Each gate depends on the one above it. Do not start a later gate to save time; a failure there
invalidates the earlier evidence.

| # | Gate | Owner | Evidence on `ab6dc7e` | Status |
| --- | --- | --- | --- | --- |
| 1 | Contracts frozen | Atlas | `contracts/rpc.v20.json` (73 declared methods), `contracts/db.v12.json`, `docs/REVIEW_CB001.md` | [x] |
| 2 | Platform skeleton passes admission | Sable | `bash scripts/validate-plugin.sh` on `ab6dc7e`: admission PASS, `node --check` PASS, desktop contract tests PASS, runtime contracts PASS — 4/4 on 2742 files | [x] |
| 3 | Backend kernel with migrations | Cinder | At `ab6dc7e`: `cb.db` v12 / `DB_SCHEMA_VERSION = 12`, migrations `0001`-`0012`; suite `Ran 2724 tests in 533.270s … OK` | [x] |
| 4 | Packs import and export | Lattice | Re-driven live on `bc9f607` (the H-203 docs merge over `ab6dc7e`; `desktop/plugin.js` is still `cd862140…`) through the mounted HTTP `cb.rpc` v20 route: `pack.preview` → `pack.import` for `japanese-affection-context-l0` 2.1.0 and `technical-demo-pack` 2.0.0, `pack.export` twice on the same store with byte-identical results (`content_hash` `sha256:5343526d…`, archive sha256 `sha256:4aefd708…`; the exported archive equals the imported archive byte-for-byte), then a fresh-store re-import with the same objectives / sections / checks (Japanese 4 / 4 / 4, demo 2 / 2 / 2) and the same media bytes. **Still open, now only in evidence:** a pack's linked media could not be fetched on `bc9f607` — `artifact.get` answered `INTERNAL_ERROR` for all three Japanese media rows because the row stores an unprefixed digest and the contract requires `sha256:<64 hex>`. That defect was repaired in `160c522` and merged here as `8fd4ec2` (`artifact.get` labels the stored hash at every read boundary; new rows written labelled, legacy bare rows normalised on read). Gate stays `[~]` until `t_a7761dfc` re-drives this same round trip on the merged tree and proves every media segment resolves — the repair landing is not the gate | [~] |
| 5 | Desktop shell with real views | Vellum | The H-85 blockers are fixed here: `670de1b` removes the null-runtime section crash and the Library clipping that failed the gate at `7d0f9cf`. No live Desktop window has driven this exact commit; the chat composer still needs the gateway-owning profile (CB-QA-09, P3-operational) | [~] |
| 6 | Probes answer the three open questions | Sentinel | Re-run on `bc9f607` (code tree `ab6dc7e`, module `cd862140`), not carried forward: probes 1, 3, 4, 6, 7 PASS; probe 1's compression segment is now PASS in place (34 → 12 messages, `post_compaction` fired, `session_id` kept) because `compression.in_place` is on; probe 5 seam PASS with the Desktop render BLOCKED (no Electron window on this host); probe 2 stays FAIL — `pre_llm_call` injection is persisted and replayed, a host/doc mismatch, not a Coursebook defect. `PROBES.md` §"Re-run on the release candidate"; docs-truth PASS; suite `Ran 2724 tests in 541.893s … OK` | [~] |
| 7 | Demo scenarios pass on the release commit | Sentinel | `docs/ACCEPTANCE.md`; no Sentinel scenario has run on `ab6dc7e` and no video exists. Gate 5 and the recording path must close first | [ ] |
| 8 | Release docs match shipped behavior | Harbor | this file, `README.md`, `docs/INSTALL.md`, `docs/M4-VISUAL-MEDIA-AUDIT.md`, `docs/RELEASE-EVIDENCE.md`; `python3 scripts/check-docs-truth.py` (full) passes on `ab6dc7e` | [x] |
| 9 | License present | DeseretSaint | No `LICENSE` at repository root; the decision is `t_6f2d2080`, blocked on DeseretSaint | [ ] owner decision |
| 10 | Public repository pushed | DeseretSaint | source backup is pushed to the private `DeseretSaint/hermes-classroom` remote; making it public is publication and stays closed | [~] |
| 11 | Catalog entry pins the release commit | Harbor | `catalog/coursebook.yaml` pins this documents commit (one commit above the code candidate `b33a42f`); validator `OK: 1 file(s) valid`. The pull request stays closed until gates 5, 7, 9 and 10 close | [~] |
| 12 | Catalog PR merged | DeseretSaint | PR URL against `hermes-agent` | [ ] |
| 13 | Demo recorded and approved | Harbor, DeseretSaint | file under 90 seconds, approval | [ ] |
| 14 | X post published | DeseretSaint | post URL, tags @NousResearch | [ ] |
| 15 | Contest form submitted | DeseretSaint | confirmation | [ ] |

Open gates: 7, 9, 12, 13, 14, 15. Partial: 4, 5, 6, 10, 11.

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
python3 -m unittest discover -s tests -t .   # Ran 2724 tests in 533.270s, OK
bash scripts/validate-plugin.sh --ref <sha>  # the release gate: a clean export of the commit
bash scripts/validate.sh                     # pre-merge gate: tests, syntax, admission, doctor, probe
python3 scripts/check-docs-truth.py          # docs quote the measured values
```

Observed by this pass on `ab6dc7e3e769dcfa8c8ce5bb2b9425dffb3de815`:

```
Ran 2724 tests in 533.270s

OK
```

The release gate (`validate-plugin.sh`) was re-run in this pass on `ab6dc7e`: 4/4 checks PASS on a
2742-file export. The mounted backend trace (`validate.sh` step 5) and `hermes plugins doctor` against
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
| `sha` | exactly 40 lowercase hex characters | Pinned to the CB-017 release commit; the value is in `catalog/coursebook.yaml` at branch head and in `docs/CB017-RELEASE-VERIFICATION.md` §1 |
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
| License absent | Redistribution and catalog listing are unsafe without one | DeseretSaint |
| Public listing not authorised | The private source backup is pushed; making the repository public, tagging and announcing are publication under the operator gate | DeseretSaint |
| No release tag | Atlas's operator gate forbids publishing a release or tag until DeseretSaint signs off in chat | Atlas, DeseretSaint |

Verified on this candidate, so they are not blockers: 73/73 `cb.rpc` v20 methods mounted with no
contract problems, schema v12 from migrations `0001`-`0012`, 2,724 tests, pack round-trip and export
hash matching, eight `parent.*` methods, the replan carry with the Parent Studio plan guard, and the
full replan → lessons → export loop on contest row 9 at `29bede7` (export `exp_2e068c56`, content
hash `sha256:ccf69462…e5a5` matching the approved hash, `export.ready: true`). The UI halves beyond
the row-9 drive are unverified on this commit until the gateway condition in the first row is
resolved for the recording.

## 8. Review packet (as of 2026-11-08)

| Item | Value |
| --- | --- |
| Repository | `https://github.com/DeseretSaint/hermes-classroom` (private; source backup only) |
| Release branch | `master` (pushed to `origin/master`; tags, catalog PR and publication remain operator-gated) |
| Release candidate commit | `ab6dc7e3e769dcfa8c8ce5bb2b9425dffb3de815` — merged master: the settled H-209 union (H-208's H-183/H-189/H-192c/H-199 integration with H-206 and the H-182/D1-D3 renderer work, the H-182/D8 residual learner copy, the H-182/D6 reaper/pump store scope, the validator-reject fix, and the private test `node_modules` isolation) |
| Measured on that commit | suite `Ran 2724 tests in 533.270s … OK`; `cb.rpc` v20 / 73 methods / 73 handlers; `cb.db` v12; `desktop/plugin.js` sha256 `cd862140…c516`; M4 62 frames, 15/15 claims PASS |
| Tag | none. Publication gate closed; a tag is forbidden until sign-off |
| Demo | none. `docs/DEMO.md` is the script; gate 7 unmet |
| Verification evidence | `docs/RELEASE-EVIDENCE.md`, `docs/CB017-RELEASE-VERIFICATION.md`, `docs/REVIEW_CB017-FINAL.md` (§2, §10), `docs/REVIEW_CB017-row9-ui.json`, `docs/cb017-shots/` |
| Catalog draft | `catalog/coursebook.yaml` pins this documents commit, validator `OK: 1 file(s) valid`; not submitted |
| Checklist | sections 1-7 of this file: six gates open (`[ ]`: 7, 9, 12, 13, 14, 15) and five partial (`[~]`: 4, 5, 6, 10, 11) |

One gap is recorded rather than hidden: the catalog pins this documents commit, keeping the measured
code commit `ab6dc7e` one below it, because an entry cannot carry its own hash. The numbers above are
measurements of `ab6dc7e`; the catalog update after this file only corrects what the documents say
about them. The catalog
pull request moves `sha`, `docs_url` and the docs record together once gates 5, 7, 9 and 10 close.
The installed tree at `ab6dc7e` is the one the gates ran on.
