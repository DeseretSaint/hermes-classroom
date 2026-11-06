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

## 1. Gates in order

Each gate depends on the one above it. Do not start a later gate to save time; a failure there
invalidates the earlier evidence.

| # | Gate | Owner | Evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | Contracts frozen | Atlas | `contracts/*.json`, `docs/REVIEW_CB001.md` | [x] |
| 2 | Platform skeleton passes admission | Sable | `bash scripts/validate.sh` | [x] |
| 3 | Backend kernel with migrations | Cinder | `db.ready:true`, `schema_version: 3` from `/health`; migrations `0001`-`0003`; 636 tests | [x] |
| 4 | Packs import and export | Lattice | pack round-trip and export hash in the mounted trace; P17/P18/P20 PASS (`tests/adversarial/evidence/attack-packs.json`) | [x] |
| 5 | Desktop shell with real views | Vellum | `node --check` passes and every view is authored, but `#/coursebook` renders the session home, so no view is verified on a live backend | [~] CB-QA-09 |
| 6 | Probes answer the three open questions | Sentinel | `PROBES.md`: 7 probes run, `pre_llm_call` replay FAIL, compression and Desktop render segments BLOCKED | [~] |
| 7 | Demo scenarios pass on the release commit | Sentinel | `docs/ACCEPTANCE.md` rows for every demo shot | [ ] |
| 8 | Release docs match shipped behavior | Harbor | this file, `README.md`, `docs/INSTALL.md`, `docs/DEMO.md`, `docs/PRIVACY_EGRESS.md`, `docs/ARCHITECTURE.md` | [x] at `97fff42`+docs commit; `docs/REVIEW_CB014.md` registry line is Sentinel's card |
| 9 | License present | DeseretSaint | `LICENSE` at repository root | [ ] |
| 10 | Public repository pushed | DeseretSaint | pushed commit, approval required | [ ] |
| 11 | Catalog entry pins the release commit | Harbor | `catalog/coursebook.yaml`, validator output | [~] blocked on 5, 7 and 10 |
| 12 | Catalog PR merged | DeseretSaint | PR URL against `hermes-agent` | [ ] |
| 13 | Demo recorded and approved | Harbor, DeseretSaint | file under 90 seconds, approval | [ ] |
| 14 | X post published | DeseretSaint | post URL, tags @NousResearch | [ ] |
| 15 | Contest form submitted | DeseretSaint | confirmation | [ ] |

Gate 5 stays `[~]` for one reason and it is not missing code: on the installed candidate the
`/coursebook` route renders the session home instead of the page (CB-QA-09, retested on
`f4a42f3`, `docs/REVIEW_CB014.md`). Until it mounts, the course library, create/import, Parent
Studio and Activity cannot be checked as views, and gates 7 and 13 cannot start.

## 2. Release verification

Run on the exact commit that will be pinned. Nothing else counts as evidence.

```
bash scripts/validate.sh
hermes plugins validate . --install-deps
hermes plugins doctor .
hermes plugins doctor coursebook
```

Expected at 0.1.0 on the CB-014 tree: **636 tests pass** (`Ran 636 tests ... OK`),
`desktop/plugin.js` syntax OK, `hermes plugins validate .` passes all **16** admission checks with
one warning (private core imports, see section 3), doctor reports **1 tool and 3 hooks**, the
mounted backend trace passes **31/31** expectations, and the script ends `Validation passed.` with
exit 0.

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
| `sha` | exactly 40 lowercase hex characters | `e1f1cab…` — the **skeleton** commit, a placeholder that must be re-pinned to the release commit |
| `description` | non-empty; carries the disclosure lines | Rewritten for the 0.1.0 candidate (host seams, per-operation providers, local SQLite, no telemetry). It describes the candidate, not `e1f1cab`, so the pin and the text disagree until the re-pin |
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
  generation (absent), reminders (absent), or a working Desktop page (CB-QA-09 open).

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

Gate status: **NOT MET.** No shot can be recorded until CB-QA-09 is fixed and Sentinel passes the
demo scenarios on the exact build being recorded, and no recording happens without DeseretSaint's
approval.

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
| `#/coursebook` renders the session home (CB-QA-09) | The product's primary surface does not mount, so no UI view is verified, gates 5 and 7 stay open and the demo cannot be recorded honestly | Vellum (`t_bfe339b2`) |
| `evidence.inspect` returns an open check's reference answer (CB-QA-10) | The answer key crosses the client boundary while the check is open; the UI does not render it, the RPC does | Cinder |
| Auxiliary grader accepts a persuaded pass (CB-QA-11) | The open-response lane cannot distinguish an honest pass from an injected one, so the lane ships disabled | Cinder |
| Demo gate not met | Sentinel's demo scenarios have not passed on the release commit, and recording needs operator approval | Sentinel, DeseretSaint |
| License absent | Redistribution and catalog listing are unsafe without one | DeseretSaint |
| Repository not pushed | No commit sha to pin, no README at a public URL | DeseretSaint |
| Catalog pin is the skeleton commit | The entry's text describes 0.1.0; the sha still points at `e1f1cab`, so the entry must be re-pinned after the last code merge and the docs commit | Harbor, DeseretSaint |

Verified on this branch, so they are not blockers: 51/51 `cb.rpc` v6 methods mounted with no
contract problems, schema v3 from migrations `0001`-`0003`, 636 tests and 31/31 mounted backend
expectations under `scripts/validate.sh`, pack round-trip and export hash matching, and eight
`parent.*` methods. Those paths are implemented and tested; they are unreachable from the UI while
CB-QA-09 is open.
