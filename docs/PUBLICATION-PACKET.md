# Publication packet — gates 12, 14 and 15

**Draft text only.** Nothing in this file has been posted, tagged or submitted. Item 1's text was
used, revised, for the draft catalog pull request opened on 2026-11-10
(`NousResearch/hermes-agent#152920`, unmerged); see the addendum below the gate table. Publication
stays closed under `docs/SUBMISSION.md` §0.

- **Prepared:** 2026-11-09 11:33 MST by the kanban worker on card `t_f9668fe2`
  (branch `wt/gate-packet`).
- **Facts read at commit:** `56730476bd1d596e6835b7d9bd439695211523b1` — "docs: record game-mode
  engagement override for workers", the branch head at the time of writing. This packet is
  committed directly above that commit; the commit itself is not changed by it.
- **Gate verdicts were not touched.** Every status below is quoted from `docs/SUBMISSION.md` §1 at
  that commit. This packet reports; it does not grade.
- **Revised on the merge:** after `wt/gate-packet` reached `origin/master`, the supervisor
  re-measured the catalog entry at the merge commit and corrected two things that had gone stale in
  the branch's base — the `sha` paragraph described the pre-H-212 pin `1ba8ec6` (304 commits behind)
  and the capability defect note described `provides_tools` as still unfixed. The pin is `61cdb03`
  and gate 11 is `[x]`; the entry now declares both tools. No gate verdict changed.

## Gate state read at `5673047` (from `docs/SUBMISSION.md` §1, unmodified)

> **Addendum, 2026-11-10.** This snapshot is left as written on 2026-11-09. Three of its rows have
> since moved, all by measurement: gate 9 is closed (`LICENSE`, MIT, 2026-11-10); gate 10 is met —
> `gh repo view` reports the repository `PUBLIC` and an anonymous `git ls-remote` resolves `master`
> `3278bae`; and the catalog entry is submitted as a draft pull request
> (`NousResearch/hermes-agent#152920`, unmerged, pinned to `3278bae`, `docs_url` at the README's
> `#install-locally` heading). Gate 12 stays open until that pull request merges, and items 1-3 below
> are still **not sendable** — §0 sign-off, gates 7 and 13 remain open. The license placeholder in
> item 1 is also resolved: `LICENSE` exists at this branch head.

| Gate | Status as recorded | Meaning for this packet |
| --- | --- | --- |
| §0 operator publication gate | **closed** | Nothing here may be sent without DeseretSaint's explicit sign-off in chat |
| 5 Desktop shell with real views | `[~]` | No live Desktop window has driven the measured commit |
| 7 Demo scenarios pass on the release commit | `[ ]` | No Sentinel scenario has run and no video exists |
| 9 License present | `[ ]` owner decision | There is no `LICENSE` at the repository root |
| 10 Public repository pushed | `[~]` | The repository is private; the source backup is private |
| 11 Catalog entry pins the release commit | `[~]` | The entry is committed, not submitted |
| 12 Catalog PR merged | `[ ]` | Item 1 of this packet is the text for that PR |
| 13 Demo recorded and approved | `[ ]` | No demo file exists |
| 14 X post published | `[ ]` | Item 2 of this packet is the text for that post |
| 15 Contest form submitted | `[ ]` | Item 3 of this packet is the text for that form |

**No gate above is closed by this packet, and no gate above is claimed to be closed anywhere in
it.** The three items below are drafts that are all **NOT SENDABLE today**.

## Contingency header — what each item waits on, and the exact operator action

| Item | Gate it discharges | Contingent on (open today) | Exact operator action that unblocks it |
| --- | --- | --- | --- |
| 1. Catalog PR body | 12 | §0 sign-off; gates 5, 7, 9, 10 | DeseretSaint gives explicit sign-off in chat; a `LICENSE` file is added at the repository root (gate 9); the repository is made public (gate 10); Sentinel's demo scenarios pass on the release commit (gates 5, 7); then `plugin-catalog/coursebook.yaml` is copied from `catalog/coursebook.yaml`, the catalog validator is run on the directory, and the PR is opened. Gate 11 is already `[x]`: the entry pins `61cdb03` on `origin/master` and all seven raw URLs were fetched and hash-matched on 2026-11-09 |
| 2. X post | 14 | §0 sign-off; gate 10 (the linked URL must resolve for readers); claim limits while gates 7 and 13 are open | DeseretSaint makes the repository public, then posts the text in §2 from the account that tags `@NousResearch` and records the post URL |
| 3. Contest form answers | 15 | §0 sign-off; gate 9 (license), gate 10 (public repo URL), gates 7 and 13 (demo URL) | DeseretSaint records a license, makes the repository public, and either records and approves a demo under 90 seconds (gate 13) or confirms that the form's demo field accepts the gate-14 post URL once gate 14 is closed; then submits before 2026-11-11 17:00 EST |

---

## 1. Catalog PR body — gate 12

**Status: SUPERSEDED — this text was used, revised, for the draft pull request opened 2026-11-10
(`NousResearch/hermes-agent#152920`, unmerged, pinned to `3278bae`).** Gate 11 is closed: the
submitted entry pins a commit on `origin/master` and its raw URLs were fetched and hash-matched on
2026-11-09 for the in-repo copy. **The license line is no longer a placeholder: `LICENSE` (MIT)
exists at the repository root.** Merging that pull request remains a §0 step and gates 5, 7 and 12
stay open.

### Title

```
plugin-catalog: add coursebook 0.1.0 (desktop, community)
```

### What the PR adds

`plugin-catalog/coursebook.yaml`, taken from `catalog/coursebook.yaml` at the commit this PR is
opened from (`docs/SUBMISSION.md` §4 step 3). The entry as committed today carries:

- `name: coursebook`, `maintainer: DeseretSaint`, `tier: community`, `category: desktop`,
  `requires_hermes: ">=0.23.0"`, `version: "0.1.0"`, `readme: true`, `platforms: []`
  (`catalog/coursebook.yaml:21-59`);
- `sha: 61cdb03ee3e58294098829adbd453207957de604` — the H-212 docs commit one above the frozen
  code tree `b9f4a19`, and it **is on `origin/master`** (merged and pushed 2026-11-09). Re-measured
  at the commit this packet sits on: `git rev-list --count 61cdb03..HEAD` → **8** commits, every
  one of them `docs/` after H-212, so the pin still describes the code it names. Gate 11 is `[x]`
  in `docs/SUBMISSION.md` §1 for that reason: all seven raw URLs (`docs_url`, `image` and the six
  `screenshots`) were fetched on 2026-11-09, each returned HTTP 200, and each PNG body hashes to
  `docs/assets/<name>.png` at `61cdb03`. The earlier `1ba8ec6` pin, then 304 commits behind, was
  replaced by that re-pin; nothing needs re-pinning before the PR unless a later commit changes
  code rather than docs.

### Description paragraph (one paragraph, pasted from `catalog/coursebook.yaml:24-42`, verbatim)

```
A native Hermes Desktop learning workspace where a lesson is governed state rather than chat:
one objective at a time, typed checks, bounded grading, transactional transitions, inspectable
evidence, and sourced visuals and audio, plus parent-prepared lesson packs. Coursebook 0.1.0
holds no vendor credentials and declares no required environment variables: provider calls go
through seams the Hermes profile already configures. Disclosure - lesson chat reaches the
selected chat provider and any configured external memory provider; plan and lesson generation,
and Parent Studio planning, reach the host plugin LLM route with the goal or parent brief, dials,
locale, bounded research queries and source excerpts; research reaches the host web_search and
web_extract tools, so the configured search backend and the named sites; closed checks are
graded locally against a stored reference; the auxiliary open-response grader lane is disabled,
so an open answer is sent nowhere; image and speech generation call the host's configured
image/TTS providers through ctx.dispatch_tool, and two direct outbound requests exist of
Coursebook's own - downloading the provider's image artifact bytes from an allowlisted fal host,
and a first-use download of faster-whisper model weights from Hugging Face (weights only, no
audio or learner data sent); state persists in profile-scoped SQLite under $HERMES_HOME; pack
import reads a local file and pack export writes a local downloadable archive, and neither
uploads; parent briefs require an acknowledged egress disclosure before a course is created. No
telemetry, no usage reporting, no credential storage, no self-update.
```

Provenance: copied from the catalog entry itself, so the PR text and the shipped field cannot
drift. It describes the pinned code; if the pin moves, re-check the media and Parent Studio
sentences against the new pin rather than carrying them forward.

### Disclosure lines the PR body must list (`docs/SUBMISSION.md` §4 step 5)

- Local SQLite storage under `$HERMES_HOME`; nothing is uploaded by pack import or export.
- Provider calls happen per operation, through seams the Hermes profile configures.
- No telemetry and no usage reporting.
- No credential storage; the plugin declares no `requires_env`.
- No self-update; the plugin never fetches its own files.

### `hermes plugins validate` output this PR must quote

Measured on `5673047` by `bash scripts/validate-plugin.sh` (exit 0), which exports the commit with
`git archive` and runs `hermes plugins validate` on the export. Quoted from the admission section
of that run, including both warning lines and the isolation notes. Line wrapping is normalised to
this document's width; the wording and the paths are unchanged. The long private-import list is
reproduced in full because truncating it is exactly the softening this packet exists to avoid:

```
== 1/4 plugin admission (hermes plugins validate) ==

✓ manifest — plugin.yaml parses
✓ manifest fields — name, version, description present
✓ requires_hermes — spec '>=0.23.0' parses
✓ config schema — shape valid
✓ requires_env — all entries UPPER_SNAKE
✓ oauth — not declared
✓ loadable — entry: __init__.py, desktop/plugin.js
✓ python dependencies — 3 requirements from manifest
✓ capability probe — register() ran in isolation
✓ declared tools — matches registrations
✓ declared hooks — matches registrations
✓ declared middleware — matches registrations
✓ built-in tool collisions — no collisions
✓ security scan — caution
✓ no core override — no runtime rebinds of Hermes core
✓ desktop surface — stays inside the plugin SDK surface
⚠ security scan caution: encoded_exfil (frames.json:12), encoded_exfil
(frames.json:23), encoded_exfil (frames.json:34), encoded_exfil (frames.json:45)
⚠ private core imports (catalog rule 9: public surfaces only; these can break on
any release): audit/adversarial/h190-plan-identity/worker.py:73
tools.web_tools.web_extract_tool;
audit/adversarial/h191-validate-demand/probe_batches.py:318
agent.auxiliary_client;
audit/adversarial/live-generation-2026-11-08-h192/worker.py:92
hermes_cli.plugins;
audit/adversarial/live-generation-2026-11-08-h192/worker.py:93
hermes_cli.plugins_manifest.PluginManifest; coursebook/db.py:137
hermes_cli.sqlite_util; probes/p8_stt_seam.py:65 agent.transcription_registry;
probes/p8_stt_seam.py:101 tools.transcription_tools; probes/p8_stt_seam.py:123
hermes_cli.plugins; probes/p8_stt_seam.py:146 model_tools;
probes/p8_stt_seam.py:170
hermes_cli.plugin_validate_private_imports.private_import_findings; and 15 more.
Use ctx.* / documented plugin APIs, or open an issue for the seam you need.
◇ Isolation — in-process only:
audit/adversarial/h191-validate-demand/probe_batches.py:149 patches
agent.plugin_llm._resolve_trust_policy (a Hermes module attribute; the host's
copy is not the one Hermes runs);
audit/adversarial/h191-validate-demand/probe_batches.py:321 patches
agent.auxiliary_client._forwards_max_tokens (a Hermes module attribute; the
host's copy is not the one Hermes runs); probes/p8_stt_seam.py:93 calls
agent.transcription_registry.register_provider() directly instead of through ctx
(registers in the host, not in Hermes); probes/p8_stt_seam.py:97 calls
agent.transcription_registry.register_provider() directly instead of through ctx
(registers in the host, not in Hermes)
  · dashboard backend API is served through the plugin host (buffered responses)
  · ctx.register_cli_command() is skipped in the host (`hermes <command>`
subcommands are wired into the local CLI parser)

Validation passed.
```

Two facts about this output are worth stating plainly rather than smoothing:

- It is **two** warning lines — a `security scan — caution` for `encoded_exfil` in four
  adversarial `frames.json` fixtures, and the private core imports. `docs/SUBMISSION.md` §3
  ("Known warning, disclosed") describes one warning, the private imports; the measured output at
  `5673047` carries both. The PR body quotes the measured output, not the older summary.
- The other three release-gate checks from the same run, for completeness: `node --check
  desktop/plugin.js` → `desktop/plugin.js: syntax OK`; desktop contract tests → `Ran 26 tests …
  OK`; `hermes plugins doctor` on the export → `manifest: coursebook 0.1.0 (standalone)`, `OK:
  runtime discovery, manifest parsing, import, and registration passed`, `registrations: 2
  tool(s), 3 hook(s)`, and `Release gate passed: 4/4 checks on
  56730476bd1d596e6835b7d9bd439695211523b1 (2789 files)`.

### Catalog validator result (measured 2026-11-09)

```
python3 /home/deseretsaint/.hermes/hermes-agent/scripts/validate_plugin_catalog.py catalog/coursebook.yaml
OK: 1 file(s) valid
```

Run against the current `hermes-agent` checkout's validator, exit 0. The directory form
(`docs/SUBMISSION.md` §4 step 4) must be run on the fork before the PR is opened; this packet did
not write to any fork.

### License line (placeholder — gate 9 is open)

```
License: none recorded. There is no LICENSE file in this repository at the pinned commit or at the
commit this PR is opened from; the choice (MIT, Apache-2.0, or ship without) is the owner's and is
open on board card t_6f2d2080 (docs/SUBMISSION.md gate 9, docs/STORY-GAPS.md G1). Do not merge or
distribute this entry until a license is recorded.
```

**NOT SENDABLE until `LICENSE` exists and the owner records the decision.** The PR body above must
not be opened with a license claim it cannot support.

### Known issues, copied from `known_issues` verbatim (`catalog/coursebook.yaml:60-63`) — nothing softened

```
- No license: there is no LICENSE file in this repository. The decision is open with the owner
  (board card t_6f2d2080: MIT, Apache-2.0, or ship without) and no license is claimed here. Do not
  redistribute until it is recorded.
- No demo video and no release tag. The demo gate (board card t_6a32ffe9) is open: this host runs
  one gateway, so an isolated window cannot drive chat beside the pane, and the bundled demo pack
  imports its objectives but zero checks, so the graded attempt and evidence row cannot be shown
  yet. The 88-second shot list is docs/HACKATHON-DEMO.md; the open rows are docs/STORY-GAPS.md.
- The frames in image and screenshots are real captures from the pinned 0.1.0 asset set, not the
  current Home. The Home has since been rebuilt as the Trailhead (H-176, 2b0324e, unmerged), and
  two frames show a demonstration course title and a developer status strip. Replacement frames
  are blocked on the clean seed and the gateway binding (docs/STORY-GAPS.md G2, G3, G5).
```

One entry defect found while drafting this packet was fixed in the same commit rather than left for
a reviewer to find: `capabilities.provides_tools` listed only `coursebook_status`, which was correct
for the old `1ba8ec6` pin (`coursebook/tools.py` there has exactly one tool) but wrong for
`61cdb03` — `coursebook_due` was added by H-180 at `564821a` and is registered on the pinned tree
(`git show 61cdb03:coursebook/tools.py` declares both `STATUS_TOOL_NAME` and `DUE_TOOL_NAME`;
`hermes plugins doctor` reports 2 tools, 3 hooks). The catalog entry now lists both, so the entry
and the code it pins agree. If the pin moves forward, re-check `provides_tools` the same way.

---

## 2. X post — gate 14

**Status: NOT SENDABLE today.** Contingent on §0 sign-off and the demo gates: gates 7 and 13 are
`[ ]` and no video exists, and the post may not claim installability, adaptiveness or a demo video.
The repository URL in the text does resolve for a reader — the repository is public (measured
2026-11-10) — but posting remains a §0 publication step.

<!-- X-POST-START -->
Coursebook — a learning workspace plugin for @NousResearch Hermes Desktop where a lesson is governed state, not chat: one objective at a time, typed checks, and exactly one transition per committed answer. Source: https://github.com/DeseretSaint/hermes-classroom
<!-- X-POST-END -->

**Character count: 262 characters** — `len()` of the exact string between the markers above,
measured 2026-11-09, under the 280 limit. It is a single post; no thread is needed.

What the text does and does not say, against the claim limits in `docs/SUBMISSION.md` §6 and the
evidence in `README.md`:

- Names what the thing is: a learning workspace plugin for Hermes Desktop, a lesson as governed
  state rather than chat (`README.md` lines 3-7, `catalog/coursebook.yaml:24-27`).
- One concrete capability: exactly one transition per committed answer — asserted by
  `tests/test_kernel_transitions.py` (37 tests) and listed as proof point 1 in `README.md`
  §"Three things this tree can be held to".
- Tags `@NousResearch` and links the repository URL.
- Does **not** say installable, does not say catalog-available, does not say adaptive, does not
  mention a demo or a video, and makes no learning-outcome, mastery or efficacy claim.

---

## 3. Contest form answers — gate 15

**Status: NOT SENDABLE.** Contingent on §0 sign-off; three of the six values are gates that are
still open and are written as `BLOCKED: gate N` rather than invented.

| Field | Value to enter | Traceable to |
| --- | --- | --- |
| Project name | `Coursebook` | `README.md:1` (heading); `catalog/coursebook.yaml:44` (`title: Coursebook`) |
| One-line pitch | `Coursebook is a Hermes Desktop learning workspace where a lesson is governed state, not chat.` | `README.md:3-4`, first sentence, verbatim |
| Description | `Coursebook is a Hermes Desktop learning workspace where a lesson is governed state, not chat: one objective at a time, typed checks, bounded grading, exactly one permitted transition per committed answer, and an evidence row you can inspect, export and resume. It is for an adult learning a real skill, and for a parent preparing a lesson pack that the parent then teaches: children do not chat with Coursebook.` | `README.md:3-7`, verbatim opening paragraph |
| Repo URL | `https://github.com/DeseretSaint/hermes-classroom` (public; gate 10 met by measurement 2026-11-10) | `docs/SUBMISSION.md` gate 10 row; `README.md` §Status; `gh repo view` + an anonymous `git ls-remote` |
| Demo URL | `BLOCKED: gate 13` — no demo file exists; gate 7 (demo scenarios on the release commit) must close first | `docs/SUBMISSION.md:63` (gate 7 `[ ]`), `:69` (gate 13 `[ ]`), `:285` ("Demo | none"); `README.md:50-52` ("No demo video is recorded yet") |
| License | `MIT` — `LICENSE` at the repository root, copyright 2026 DeseretSaint (gate 9 closed 2026-11-10 on `t_6f2d2080`) | `LICENSE`; `docs/SUBMISSION.md` gate 9 row; `README.md` §License |

The description is deliberately the README paragraph and not the catalog disclosure paragraph: the
form asks for a description of the project, and the disclosure paragraph (`catalog/coursebook.yaml`
`description`) is already carried by the catalog entry and by PR item 1 above. Neither text claims
a license, a demo, an install path or a learning outcome.

One form-shape caveat, stated rather than hidden: this packet has not seen the contest form itself —
only the field list in the task card (project name, one-line pitch, description, repo URL, demo URL,
license). If the live form asks for other required fields (team, category, contact), they are not
answered here and must be filled from the operator's own details, not from this document.

---

## Provenance summary

| Fact | Source read at `5673047` |
| --- | --- |
| Gate verdicts and owners | `docs/SUBMISSION.md` §1, §8 |
| Publication sign-off requirement | `docs/SUBMISSION.md` §0 |
| Catalog entry fields, pin, description, `known_issues` | `catalog/coursebook.yaml` |
| Product description and limitations | `README.md` |
| License decision state and demo gaps | `docs/STORY-GAPS.md` G1, G2, G3, G5, G6, G7 |
| Claim limits for the post and form | `docs/SUBMISSION.md` §6; `docs/JUDGE-SCAN.md` |
| `hermes plugins validate` output | `bash scripts/validate-plugin.sh` on `5673047`, exit 0, 2026-11-09 |
| Docs-truth gate | `python3 scripts/check-docs-truth.py --skip-tests` → `docs-truth: PASS` on `5673047` |

This file drafts text. It does not publish, post, tag, open a PR, submit a form, or write the
catalog, and it changes no gate verdict.
