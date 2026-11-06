# Submission checklist

Deadline: November 11, 2026, 5:00 PM EST. Submission is three things, not one: a catalog pull
request against `hermes-agent`, a public X post with the demo that tags @NousResearch, and the
contest form. A demo over 90 seconds fails regardless of quality.

Status key: `[x]` verified on this branch, `[ ]` open, `[~]` blocked on another owner.

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
| 3 | Backend kernel with migrations | Cinder | `db.ready:true` from `/health`, migration tests | [ ] |
| 4 | Packs import and export | Lattice | pack round-trip tests, export allowlist test | [ ] |
| 5 | Desktop shell with real views | Vellum | `node --check`, pane states on a live backend | [ ] |
| 6 | Probes answer the three open questions | Sentinel | `PROBES.md` | [~] |
| 7 | Demo scenarios pass on the release commit | Sentinel | `docs/ACCEPTANCE.md` rows for every demo shot | [ ] |
| 8 | Release docs match shipped behavior | Harbor | this file, `README.md`, `docs/INSTALL.md`, `docs/DEMO.md` | [x] for the skeleton, re-run at release |
| 9 | License present | DeseretSaint | `LICENSE` at repository root | [ ] |
| 10 | Public repository pushed | DeseretSaint | pushed commit, approval required | [ ] |
| 11 | Catalog entry pins the release commit | Harbor | `catalog/coursebook.yaml`, validator output | [~] blocked on 3 to 8 |
| 12 | Catalog PR merged | DeseretSaint | PR URL against `hermes-agent` | [ ] |
| 13 | Demo recorded and approved | Harbor, DeseretSaint | file under 90 seconds, approval | [ ] |
| 14 | X post published | DeseretSaint | post URL, tags @NousResearch | [ ] |
| 15 | Contest form submitted | DeseretSaint | confirmation | [ ] |

## 2. Release verification

Run on the exact commit that will be pinned. Nothing else counts as evidence.

```
bash scripts/validate.sh
hermes plugins validate . --install-deps
hermes plugins doctor .
hermes plugins doctor coursebook
```

Expected at 0.1.0: 46 tests pass, `desktop/plugin.js` syntax OK, `validate` passes all 16 checks,
doctor reports 1 tool and 3 hooks. At release, the test count changes and the doctor output must
still show declared capabilities matching registrations.

Fresh install path, in a throwaway `HERMES_HOME`:

```
HERMES_HOME=$(mktemp -d) bash scripts/install-dev.sh
HERMES_HOME=<same dir> hermes plugins enable coursebook
HERMES_HOME=<same dir> hermes plugins doctor coursebook
```

Then uninstall and confirm the checkout is intact. This was run for 0.1.0; repeat it at release.

## 3. Catalog entry requirements

The entry is judged by the catalog validator and by a human reviewer. The rules below come from
`plugin-catalog/README.md` in `hermes-agent` and are the current contract, not a summary.

| Field | Requirement | State in `catalog/coursebook.yaml` |
| --- | --- | --- |
| `name` | `[a-z0-9_-]{1,64}` | `coursebook` |
| `repo` | `https://` URL | Set; repository not pushed yet |
| `sha` | exactly 40 lowercase hex characters | Placeholder pin, must be re-pinned at release |
| `description` | non-empty; carries the disclosure lines | Drafted for the skeleton |
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
| No course, grading, export or Parent Studio code | Gates 3 to 7 cannot pass, so there is nothing to demo | Cinder, Lattice, Vellum |
| Three open architecture questions | Pack staging, aux grader lane and workspace topology are unresolved | Sentinel, Atlas |
| No license file | Redistribution and catalog listing are unsafe without one | DeseretSaint |
| Repository not pushed | No commit sha to pin, no README at a public URL | DeseretSaint |
| Catalog pin is a placeholder | Re-pinning must happen after the last code merge | Harbor |
