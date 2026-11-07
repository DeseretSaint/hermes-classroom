# Submission checklist

Deadline: November 11, 2026, 5:00 PM EST. Submission is three things, not one: a catalog pull
request against `hermes-agent`, a public X post with the demo that tags @NousResearch, and the
contest form. A demo over 90 seconds fails regardless of quality.

Status key: `[x]` verified on this branch, `[ ]` open, `[~]` blocked on another owner or on an open
defect. A gate is not `[x]` because code exists; it is `[x]` because a command ran against this
commit and passed.

## 0. Hard operator gate

**Do not submit to the plugin catalog or store, publish a release, create a public release tag,
open a catalog pull request, or announce Coursebook as installable until DeseretSaint gives
explicit final sign-off in chat.** GitHub commits and pushes to the private source repository are
the authorized backup path; they are not publication. Release verification and evidence collection
may continue, but every publication gate below stays closed until that sign-off.

Status of this section after the harness slice (H-11, 2026-11-07): **unchanged and closed.** No gate
below moved. The arbitrary-topic end-to-end evidence (`docs/HARNESS-E2E.md`, branch
`wt/harness-e2e-proof` at `111c7e9`) is engineering evidence with recorded transcripts, not
publication evidence: it is unmerged, it used no provider, and it does not satisfy gate 7 (demo
scenarios on the release commit) or gate 13 (a recorded demo). No tag, catalog PR or announcement
was made. Current claim-by-claim state: `docs/HARNESS-STATUS.md`.

## 1. Gates in order

Each gate depends on the one above it. Do not start a later gate to save time; a failure there
invalidates the earlier evidence.

| # | Gate | Owner | Evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | Contracts frozen | Atlas | `contracts/*.json`, `docs/REVIEW_CB001.md` | [x] |
| 2 | Platform skeleton passes admission | Sable | `bash scripts/validate.sh` | [x] |
| 3 | Backend kernel with migrations | Cinder | `db.ready:true`, `schema_version: 4` from `/health`; migrations `0001`-`0004`; 685 tests | [x] |
| 4 | Packs import and export | Lattice | pack round-trip and export hash in the mounted trace; P17/P18/P20 PASS (`tests/adversarial/evidence/attack-packs.json`) | [x] |
| 5 | Desktop shell with real views | Vellum | `node --check` passes; with a reachable backend `#/coursebook` mounts the library, `New course`, Parent Studio and a course card (`docs/CB017-RELEASE-VERIFICATION.md` §2) | [~] chat composer only on the gateway-owning profile (P3-operational, not this plugin) |
| 6 | Probes answer the three open questions | Sentinel | `PROBES.md`: 7 probes run, `pre_llm_call` replay FAIL, compression and Desktop render segments BLOCKED | [~] |
| 7 | Demo scenarios pass on the release commit | Sentinel | `docs/ACCEPTANCE.md` rows for every demo shot | [ ] |
| 8 | Release docs match shipped behavior | Harbor | this file, `README.md`, `docs/INSTALL.md`, `docs/DEMO.md`, `docs/PRIVACY_EGRESS.md`, `docs/ARCHITECTURE.md`, `docs/CB017-RELEASE-VERIFICATION.md` | [x] on the release commit; gates re-run in §2 |
| 9 | License present | DeseretSaint | `LICENSE` at repository root | [ ] owner decision — no license chosen yet |
| 10 | Public repository pushed | DeseretSaint | source backup is pushed to the private `DeseretSaint/hermes-classroom` remote; making it public is publication and stays closed | [~] 0.1.0 source pushed |
| 11 | Catalog entry pins the release commit | Harbor | `catalog/coursebook.yaml`, validator output | [~] blocked on 5, 7 and 10 |
| 12 | Catalog PR merged | DeseretSaint | PR URL against `hermes-agent` | [ ] |
| 13 | Demo recorded and approved | Harbor, DeseretSaint | file under 90 seconds, approval | [ ] |
| 14 | X post published | DeseretSaint | post URL, tags @NousResearch | [ ] |
| 15 | Contest form submitted | DeseretSaint | confirmation | [ ] |

Gate 5 stays `[~]` for one reason, and it is neither missing code nor a plugin defect: this host
runs one gateway, profile `default` owns it, and `hermes gateway run --force` refuses a second, so a
window on an isolated home has no gateway and no composer. Atlas reclassified CB-QA-09 as
P3-operational on that evidence (`docs/REVIEW_CB017-FINAL.md` §3.1). The views themselves mount and
were captured (`docs/CB017-RELEASE-VERIFICATION.md` §2). Gates 7 and 13 still cannot start until
the operator unblocks the recording path.

## 2. Release verification

Run on the exact commit that will be pinned. Nothing else counts as evidence.

```
bash scripts/validate-plugin.sh          # the release gate: a clean export of the commit
bash scripts/validate.sh                 # the pre-merge gate: admission on an export of the tree
hermes plugins doctor .
hermes plugins doctor coursebook
```

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
| `capabilities` | must match what `register()` does | `coursebook_status` plus the three hooks |
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

Verified on this branch, so they are not blockers: 52/52 `cb.rpc` v7 methods mounted with no
contract problems, schema v4 from migrations `0001`-`0004`, 685 tests and 31/31 mounted backend
expectations under `scripts/validate.sh`, pack round-trip and export hash matching, eight
`parent.*` methods, the replan carry with the Parent Studio plan guard, and the full
replan → lessons → export loop on contest row 9 (export `exp_2e068c56`, content hash
`sha256:ccf69462…e5a5` matching the approved hash, `export.ready: true`). The UI halves beyond the
row-9 drive are unverified until the gateway condition in the first row is resolved for the
recording.

## 8. Review packet (as of 2026-11-06)

| Item | Value |
| --- | --- |
| Repository | `https://github.com/DeseretSaint/hermes-classroom` (private; source backup only) |
| Release branch | `wt/cb-017-harbor-release` (local only; push is operator-gated and did not happen in this run) |
| Release commit (pinned) | `29bede7643403cd9d608499232125e6347c680dd` — merged master: master + `da99d8a` replan carry + `6502e56` plan guard + `67d6773` CB-017 review + `26e782f` row-9 export tail |
| Gates on the pinned commit | `validate-plugin.sh` 3/3 on 802 files; 685 tests OK; clean `git archive` install 6/6, `Installed.`; live `cb.rpc` v7 / 52 methods, `contract_problems []` (`docs/CB017-RELEASE-VERIFICATION.md` §1, §1.1) |
| Tag | none. Publication gate closed; a tag is forbidden until sign-off |
| Demo | none. `docs/DEMO.md` is the script; gate 7 unmet |
| Verification evidence | `docs/CB017-RELEASE-VERIFICATION.md`, `docs/REVIEW_CB017-FINAL.md` (§2, §10), `docs/REVIEW_CB017-row9-ui.json`, `docs/cb017-shots/` |
| Catalog draft | `catalog/coursebook.yaml` pinned to `29bede7`, validator `OK: 1 file(s) valid`; not submitted |
| Checklist | sections 1-7 of this file: six gates open (`[ ]`: 7, 9, 12, 13, 14, 15) and four partial (`[~]`: 5, 6, 10, 11) |

One gap is recorded rather than hidden: the pin is the code commit `29bede7`, and this release
record is a docs-only commit above it, because the catalog cannot describe a commit it is not on.
At `29bede7` the README still carries the pre-re-pin wording (674 tests, route "verdict open"), so
the release-record commit must land on master before a catalog pull request is opened, and `sha`
and `docs_url` move to that merge in the same change. The catalog comment says the same. The
installed tree at `29bede7` is the one the gates ran on.
