# Coursebook

Coursebook is a Hermes Desktop learning workspace for adults and parents. It is designed to turn
a goal or a reusable course pack into a governed, resumable sequence of lessons: one objective at
a time, typed checks, bounded grading, transactional transitions, inspectable evidence, and
generated lesson media with text equivalents and honest degraded states. Parent mode prepares lesson
packs that a parent teaches; children do not chat with Coursebook.

Coursebook is not a prompt. A chat prompt can answer a question; it cannot make the answer
change what happens next. In Coursebook the model teaches, while the plugin owns the objective,
the attempt, the rubric, the evidence, the next permitted transition, and the durable record.

This repository is the 0.1.0 contest candidate. The backend, the pack pipeline and the Parent
Studio authoring surface are implemented and tested. The Desktop route mounts when the window
reaches a backend that can serve the session. The route finding CB-QA-09 was reclassified by
Atlas as P3-operational — a host gateway binding, not a plugin defect: a window with no gateway
renders no route page for any hash, host routes included (`docs/REVIEW_CB017-FINAL.md` §3.1).
No demo has been recorded. Read the status table before installing.

## Status

Version 0.1.0. The release gates and the route evidence for the 0.1.0 tree are in
`docs/CB017-RELEASE-VERIFICATION.md` (CB-017 line, merged master `29bede7`); the adversarial
review and the contest matrix are `docs/REVIEW_CB017-FINAL.md`, including Vellum's row-9 export
tail in §10. `docs/CB016-RELEASE-VERIFICATION.md` is the earlier record at `e93b8c5`, kept for its
two condition captures. The adversarial report on the previous candidate is `docs/REVIEW_CB014.md`
(candidate `f4a42f34`, NO-GO on the Desktop route, not on the backend).

`master` has since advanced beyond `29bede7` with the M0 host-media slice (`3cead45`) and the
M1-M3 product line (`d28e7e3`). The 0.1.0 evidence above is still the `29bede7` record and has not
been re-run on the newer tree. The current release candidate is merged `master`
`b7c53e46ea468157d91127890de1435a00bf5f47` (the UI batch union — H-145 Home launcher, H-146 classroom
rail, H-147 Home settings, H-148 path truth, H-149 lesson player, H-150 library shelf, H-153 first run,
H-154 mastery policy, H-156 parent/child defaults, H-157 course detail and Field Quest — merged onto
the H-120b conversation-practice surface `625c939`, which sits on the H-105 + `cb.rpc` v16 union
`39659b7` and the H-155 engagement audit `ac301a1`); every count, pin and health row
in this README is measured there and recorded in `docs/RELEASE-EVIDENCE.md`, with
`python3 scripts/check-docs-truth.py` failing when a document drifts from that record. It is not a
green release: the demo gate `t_6a32ffe9` is still open and no live Desktop window has driven this
tree; publication remains gated by `docs/SUBMISSION.md` §0.

### Product line after 0.1.0

This tree also carries the post-0.1.0 product line from `docs/VISUAL_MEDIA_PLAN.md`: M0 on `master`
at `3cead45`, M1-M3 merged on `master` at `d28e7e3`, and the M4 visual/accessibility/media evidence
regenerated on the merged tree after H-91 (H-83's Atlas Lamp composition, H-84's plain-language pass,
H-86's wayfinding pass and H-91's gate fixes) and again on the `cb.rpc` v16 tree after the
P0 react-key sweep (`80b39b8`), H-144 (`14a6443`) and the H-105 + `cb.rpc` v16 union merge
(`39659b7`), the H-120b conversation-practice merge `625c939` and the H-158 UI batch union `b7c53e4`,
against `desktop/plugin.js` sha256
`8347331f…f096711d` — reproducibility is
checked with `python3 scripts/m4v-repro-check.py`, which reports 62/62 identical screenshots and an
identical `audit.json` (modulo `generated_at`) on two consecutive runs at this pin; that output is
pasted in `docs/M4-VISUAL-MEDIA-AUDIT.md`. Phase-to-commit mapping, per-phase evidence and the gated
remainder: `docs/PRODUCT-LINE-RELEASE-NOTES.md`.

The 0.1.0 rows below are the release record for `29bede7` and are deliberately not rewritten to
describe this tree. The product-line rows are separate, and they use two weaker words:

- **Rendered** — the shipped Desktop module was mounted and measured in headless Chromium against a
  stub host transport. Real paint, real layout and a real accessibility tree; no backend, no chat,
  no `lesson.page` RPC.
- **Working (live)** — a mounted Desktop window reached a real isolated backend and the state was
  read back from it. Neither word means "recorded as a demo", and neither is a release claim.

| Product-line surface | State on this tree | Evidence |
| --- | --- | --- |
| Contracts `cb.rpc` v16 and `cb.db` v11, with `cb.jobs` v4, `cb.errors` v4 and the v1 `cb.pack`, `cb.projection` and `cb.vocabulary` | Working at this commit: 68 declared methods and 68 handlers. `observation.record` was frozen by `cb.rpc` v14 in H-53 and wired by H-54, so the registry test allows no gap: any declared method that loses its handler fails the suite. Schema 11 from migrations `0001`-`0011` | `contracts/rpc.v16.json`, `contracts/db.v11.json`; parity asserted by the suite (`2168 tests OK, 1 skipped`); `coursebook/api.py` `implemented_methods()` returns all 68 declared methods |
| Textbook view | Working (live): a real document served over the real RPC; the frame set covers Textbook and Guided (13 frames) | `audit/visual/m1-guided-authoring/README.md` |
| Guided view | Working (live) on a newly authored document (`state=complete`, `views.guided=true`). The older demo course still reports `textbook_only` because its stored page predates `lesson-prompt.v5`; it was not rewritten | `audit/visual/m1-guided-authoring/` |
| Field Desk cockpit (Continue, path, stats, Field Notes, sources, all courses) | Working (live): the cockpit, its opened sources drawer, and its backend-off, empty and loading states were read from an isolated window at plugin sha `638e0f5e…` | `audit/visual/m2-field-desk/README.md`, `live-evidence.json` |
| Field Notes (save from a block, search, return to the exact block) | Working (live): 15 live frames including 460 px and exact-block return | `audit/visual/m2-field-notes/live-evidence.json` |
| Field Quest | Rendered: 14 static frames and 56 render/parity tests, plus a live availability capture. No live Quest frame exists, because the stored lessons in every reachable home predate authored `short` | `audit/visual/m2-field-quest/README.md`, `live-availability.json` |
| Procedure lens (typed header, numbered steps, hazard callout, schematic rows, source permission) | Authored and Rendered: the lesson schema and `lesson-prompt.v8` produce the typed `procedure` header, and `tests/test_procedure_authoring.py` drives the real lesson job with a fake model and asserts the served document renders the header, hazards, numbered steps, schematic rows and source card. The 7 visual frames and 28 validator/render tests remain fixture-based; no live provider run has authored one | `docs/M4-PROCEDURE-LAYOUT.md`, `docs/GENERATION.md`, `tests/test_procedure_authoring.py` |
| Pronunciation Studio (listen, record, compare, dispute) | Rendered: 14 frames and 15 jsdom interaction tests. It is inert on every existing section because none has a narration media child; no live attempt was walked | `docs/M3-PRONUNCIATION-UI.md`, `tests/test_desktop_pronunciation.py`, `audit/visual/m3-pronunciation/` |
| Media generation and preview | Working for the host adapter (one real PNG and one real MP3 through `docs/M0-MEDIA-PROBE.md`) and Rendered in the lesson (50 decoded images, 12 audio elements, 0 autoplay, text equivalent for each). The preview route is covered by tests, not driven live on this tree | `docs/M0-MEDIA-PROBE.md`, `docs/M4-VISUAL-MEDIA-AUDIT.md`, `audit/visual/m4-visual/audit.json` |
| M4 visual, contrast and accessibility gate | Rendered: 62 painted frames, 15/15 claims pass, 0 plugin-authored contrast failures over 2,416 text nodes (worst authored 5.93:1), 0 unnamed of 298 accessibility controls, no clipped text or horizontal overflow. Two consecutive `m4v-repro-check.py` runs at this module are identical: 62/62 screenshots and `audit.json` modulo `generated_at` | `audit/visual/m4-visual/audit.json` (pinned to plugin `8347331…` at the measured commit `b7c53e4`), `docs/M4-VISUAL-MEDIA-AUDIT.md`, `scripts/m4v-repro-check.py` |
| 460 px narrow width | Partial: the module itself reflows at 460 px with no horizontal overflow, but the shipped host still gives the route 101 px when the chat rail is docked. The host patch that fixes the grid is neither merged nor installed | `audit/visual/m1-narrow-width/DECISION.md` §Residuals; `audit/visual/m4-visual/*-460-*.png` |

Nothing in the product line changes install status. The catalog entry pins this release candidate,
no pull request has been opened, and no release tag exists.

### 0.1.0 surface table (release record, post-release changes named)

Three states are used in this table. **Working** means a command was run against that build and
passed.
**Implemented, unverified in the UI** means the backend path is implemented and tested, and the
Desktop surface exists, but this release pass did not drive it through the UI. **Absent** means
there is no code path at all. Unless a row names a later commit, the row describes `29bede7`.

| Surface | State in this build |
| --- | --- |
| One installable package (agent half plus Desktop half) | Working: `scripts/install-local.sh` installs both halves; `hermes plugins validate` and `hermes plugins doctor` pass |
| `coursebook_status` agent tool (read-only health) | Working: the single registered tool |
| Backend routes `/health`, `/schema`, `/rpc`, `/runtime`, `/packs/*`, `/artifacts/<handle>`, `/media/<artifact_id>` | Implemented: the first six were re-driven by `scripts/probe-backend.py` (31/31). `/media/<artifact_id>` is an M0 addition (`3cead45`), covered by `tests/test_manifest.py` and `tests/test_media_generation.py`; it does not exist at `29bede7` |
| Frozen contracts at `29bede7`: `cb.rpc` v7, `cb.db` v4, `cb.jobs` v2, `cb.errors` v2, `cb.pack` v1, `cb.projection` v1, `cb.vocabulary` v1 | Working in that build: 52 declared methods, 52 handlers, no contract problems from `/runtime`. This tree has moved to `cb.rpc` v16 and `cb.db` v11 with 68 declared methods and 68 handlers; the product-line row above carries the current numbers |
| Profile-scoped SQLite schema and migrations `0001`-`0004` at `29bede7` | Working: `health.get` answers `db.ready: true`, `schema_version: 4` on a fresh home. This tree ships migrations `0001`-`0011` and answers `db.ready: true`, `schema_version: 11` on a fresh home |
| Desktop route `#/coursebook`, sidebar entry, pane, command palette, settings page | Working with a reachable backend: mounts the library, `New course`, Parent Studio and a course card (`docs/CB017-RELEASE-VERIFICATION.md` §2). A window with no gateway renders no route page for any hash — host shell degradation, reclassified P3-operational by Atlas (`docs/REVIEW_CB017-FINAL.md` §3.1) |
| Course creation, plans, lessons, grading, transitions, evidence | Implemented, unverified in the UI: 685-test suite at `29bede7`, plus adversarial S01/S02/S10-S12 (duplicate submit, stale revision, invalid/hung/throwing grader) all pass in that build. The suite is 2168 tests on this tree (1 skipped) |
| Replan of an approved plan, then lessons, then export | Working end to end for this tree: replan → plan approve (v10) → lessons job start → 4 lessons authored → lesson-set approve → export, with the UI and the backend agreeing on the approved content hash (`sha256:ccf69462…e5a5`), `export.ready: true` and no `blocked_reason`. Evidence: `docs/REVIEW_CB017-row9-ui.json`, `docs/REVIEW_CB017-FINAL.md` §10 |
| Notebooks, quiz history, review queue, usage accounting | Implemented, unverified in the UI: `notebook.save/list/update/delete`, `quiz.history`, `review.queue/action` and `usage.summary` are in the mounted registry |
| Pack import and export, Parent Studio authoring | Implemented, unverified in the UI: `pack.import/export/preview/inspect/list/delete` and eight `parent.*` methods; P17/P18/P20 pass, and export reproduces the reviewed content hash |
| Research | Implemented inside plan jobs: bounded, query-capped and ledgered through the host `web_search`/`web_extract` seam; records `unavailable` rather than inventing a source. No standalone RPC |
| Image and speech generation | Implemented on `master` since `3cead45` (M0): the host's configured image/TTS providers are called through `ctx.dispatch_tool`; generated visuals and narration are stored as content-addressed artifacts with text equivalents and honest degraded states. Absent at the 0.1.0 release commit `29bede7`. Pronunciation scoring is not shipped yet |
| Reminders | Absent: no RPC, no job runner, no storage |

Every method declared by `cb.rpc` v7 had a handler in the `29bede7` build. On this tree all 68 of
`cb.rpc` v16's declared methods have handlers, `observation.record` included — frozen by H-53 and
wired by H-54, with the H-53→H-54 registry allowance removed. The count comes from
`coursebook/api.py`'s `implemented_methods()` after importing `coursebook.domain` and
`coursebook.pack_flow` (the modules that register handlers), not from a text search, and
`tests/test_kernel_v2.py` asserts the registry covers every declared method. So there is no command that answers a plausible success for work it cannot do. A method
outside the contract is refused with `VALIDATION_FAILED`; a declared method with no handler answers
`NOT_IMPLEMENTED`; a handler that cannot answer returns a contract error rather than a fabricated
result. `evidence.inspect` no longer carries an open check's reference answer: criteria
are projected through `PUBLIC_CRITERION_FIELDS` with a `check_spec_withheld` marker, so the
`check_spec` that holds the reference never leaves the backend. That closes CB-QA-10 on the wire
(`docs/HARNESS-STATUS.md` §4; S07 passes in `tests/adversarial/attack_state.py`). One backend
defect remains open and is recorded in `docs/REVIEW_CB014.md`: the optional auxiliary grader cannot
yet distinguish a persuaded pass from an honest one (CB-QA-11).

## Requirements

- Hermes Agent 0.23.0 or newer, with the Desktop app.
- Python 3.11 or newer (the repository tests run on the interpreter Hermes ships).
- Node.js, only for the `node --check` syntax gate. The plugin itself needs no build step.

## Install from a local checkout

These commands were run against this checkout before they were written down. Run them from the
repository root.

```
bash scripts/install-dev.sh
hermes plugins enable coursebook
hermes gateway restart
```

`scripts/install-dev.sh` symlinks this checkout into `$HERMES_HOME/plugins/coursebook` and prints
the next steps. It refuses to replace a real directory and refuses to run outside a Coursebook
checkout. It does not enable anything.

`scripts/install-local.sh` is the scripted equivalent: it installs both halves into one dedicated
home, enables the plugin, and verifies the install with `hermes plugins validate` and
`hermes plugins doctor`.

Then enable the Desktop half in the app: Capabilities, Plugins, Coursebook, on. The two halves
are enabled separately; the pane detects the mismatch and says so.

Verify:

```
hermes plugins doctor coursebook
bash scripts/validate.sh
```

Install from the plugin catalog (`hermes plugins install coursebook`) is not available: no catalog
pull request has been opened. `catalog/coursebook.yaml` validates against `hermes-agent`'s catalog
validator and pins this release candidate, but gates 5, 7, 9 and 10 of `docs/SUBMISSION.md` are
open, so submitting it is on hold. Owner: Harbor and DeseretSaint.

Cloning from GitHub is not a supported install path yet: the repository is private, and making it
public is publication, which needs DeseretSaint's sign-off. Until then, install from a local
checkout as above.

## First run

Open Coursebook in the Desktop sidebar. The plugin loads: the sidebar item, the pane and the
command-palette entries register, and the settings page registers when the host exposes a
settings-page seam. With no chat bound to an enrollment, the pane offers `Open Coursebook` and
reports that no durable chat is bound yet. The backend it reads answers `health.get` with
`db.ready: true` and `schema_version: 11`.

In a window that reaches a gateway-backed backend, `#/coursebook` mounts the course library, the
`New course` action and Parent Studio (`docs/CB017-RELEASE-VERIFICATION.md` §2). A window whose
isolated home has no gateway shows the session home for every hash instead — that is the shell,
not the plugin, and Atlas reclassified CB-QA-09 as P3-operational on exactly that evidence
(`docs/REVIEW_CB017-FINAL.md` §3.1). A demo that shows the chat side still needs a composer, which
means recording on the profile that owns this host's gateway.

Ask the agent to run `coursebook_status` to get the health block as JSON. If the backend is not
mounted, the pane names the enable path and offers Check again instead of showing an empty
course list.

Step-by-step install, uninstall and troubleshooting: `docs/INSTALL.md`.

## Privacy and egress

Coursebook holds no vendor credentials and reads no provider key. Provider calls go through a
seam the Hermes profile already configures:

- lesson chat uses the selected chat provider and any configured external memory provider;
- plan and lesson generation use the host plugin LLM route; the optional auxiliary grader uses
  the same route and is disabled in this build;
- research uses the host `web_search` and `web_extract` tools, so the user's configured backend,
  egress rules and SSRF checks apply;
- pack import and export are local files and perform no upload, and there is no telemetry.

Two operations do make a direct outbound HTTP request of Coursebook's own, both outside that seam:

- **Provider image download.** When the host binds `ctx.dispatch_tool` and `image_generate`
  returns an artifact URL, Coursebook downloads the bytes itself from an allowlisted
  `*.fal.media` / `*.fal.run` host (`coursebook/media.py`). The URL is the provider's own
  artifact URL, never one supplied by the model or a learner; the redirect target is re-checked
  against the same allowlist, and a provider or download failure degrades to the text equivalent.
- **First-use speech-model download.** The first pronunciation attempt with an empty cache
  downloads `faster-whisper` model weights from Hugging Face into `<plugin data>/stt-models`
  (`coursebook/stt.py`). Weights only: no audio or learner data is sent, and the take is deleted
  after local scoring.

Neither request carries a schoolwork payload, and neither uses a credential Coursebook holds.

State lives in profile-scoped SQLite at `$HERMES_HOME/plugin-data/coursebook/data.db` and
migrates on first use, through migrations `0001`-`0011` (schema v11) on this tree. Usage rows are
recorded locally, and only for a session this process observed as bound to an enrollment. "Local"
describes storage, not inference.

Full text, including what Coursebook refuses to do with schoolwork and what it cannot control at
the host level: `docs/PRIVACY_EGRESS.md`.

## Limitations

This candidate is not shippable as a Desktop product.

- CB-QA-09 is a host gateway binding, not a plugin defect (P3-operational, Atlas ruling in
  `docs/REVIEW_CB017-FINAL.md` §3.1). This host runs one gateway for profile `default` and refuses
  a second, so an isolated window has no composer; the plugin's own `Backend off` / `Offline`
  states are proven separately. The demo's chat surface therefore needs the operator to record on
  the gateway-owning profile, or to stop that gateway first.
- Row 9 is closed on this tree (replan → lessons → export, §"Status"); the demo still cannot be
  recorded on this host for the gateway reason above, and that is a process blocker, not a product
  one.
- Image and speech generation now use the host's configured providers through the plugin seam;
  pronunciation scoring and reminders remain absent.
- The auxiliary open-response grader is disabled. Closed checks are graded against a stored
  reference; with the lane enabled, an answer that persuades an obedient grader is accepted
  (CB-QA-11).
- `evidence.inspect` withholds an open check's reference on the wire (CB-QA-10 closed). The L2
  projection carries `id`, `description`, `check_id` and a `check_spec_withheld` marker from
  `coursebook/evidence.py`'s `PUBLIC_CRITERION_FIELDS`, so the spec that holds the reference never
  reaches the caller; `tests/test_review_evidence.py:378,384` assert its absence and S07 passes;
  the state matrix on this candidate is `SUMMARY total=23 fail=0 pass=23` with S13 `BLOCKED`
  (auxiliary grader lane disabled).

The product line adds surfaces with limits of their own; these are not the 0.1.0 rows above.

- Narrow width is a host gap, not a plugin claim. At 460 px the shipped host gives the Coursebook
  route 101 px while the chat rail is docked. The fix (`narrowLeavesGrid`) lives on
  `DeseretSaint/hermes-agent` branch `wt/host-narrow-rail` (`5900b6e7a0`), is neither merged nor
  installed, and the M4 frames measure the module in a 460 px viewport rather than through the host
  grid (`audit/visual/m1-narrow-width/DECISION.md`).
- Field Quest has no live frame. Stored lessons predate authored `short`, so `views.field_quest` is
  false on every section a window reached; the lens is proven by render and parity tests
  (`audit/visual/m2-field-quest/README.md`).
- The procedure lens has no authoring path. The validator, contract and renderer are proven against
  a contract-valid fixture; the lesson prompt does not emit `procedure` yet
  (`docs/M4-PROCEDURE-LAYOUT.md`).
- The Pronunciation Studio is inert until a section carries narration media, and no existing section
  does. With no recogniser configured it says "Practice only, not graded" and records nothing; a
  take is `model_assessed` evidence, never verified pronunciation or mastery
  (`docs/M3-PRONUNCIATION-UI.md`).
- Media proof is split. Generation is real (one host PNG and one host MP3 in
  `docs/M0-MEDIA-PROBE.md`); the lesson renderer is measured statically, and audio is checked for
  attributes and decode, not audibility (`docs/M4-VISUAL-MEDIA-AUDIT.md`).
- No user-facing text-only or reduced-data preference ships. The text-only path exercised is the
  no-artifact fallback.
- Reduced motion is satisfied by construction: the module paints no transition or animation, so the
  audit cannot claim to have suppressed one.
- Accessibility names come from the Chromium accessibility tree, not from a screen reader.
- A failed audio preview is typed `visual` in the internal `data-cb-media-kind` attribute while its
  visible label and transcript stay correct (`t_acd97416`, low, open).
- The product line is not demo evidence and not a release: no video exists, the demo gate is NOT
  MET (`docs/DEMO.md`), and no catalog PR, tag or submission was made (`docs/SUBMISSION.md` §0).

There is no learning-style diagnosis, no "2 sigma" claim, no guaranteed mastery, no child safety
or COPPA certification, and no efficacy claim. Educational research motivates the design;
Coursebook has not established that it improves learning. Parent observations are labeled
`parent_reported` and are never combined with automated mastery.

## Documentation

- `docs/INSTALL.md`: install, enable, verify, uninstall, troubleshooting.
- `docs/ARCHITECTURE.md`: verified SDK seams, spec to SDK corrections, failure states, and the
  stored-lesson-text repair marker.
- `docs/CONTRACTS.md`: the seven frozen contracts and their open questions.
- `docs/GENERATION.md`: the plan and lesson pipeline, research ledger and validation pass.
- `docs/WORK_PACKAGES.md`: file ownership and merge order.
- `docs/PRIVACY_EGRESS.md`: per-operation disclosure.
- `docs/DEMO.md`: the demo script and its precomputed/live split.
- `docs/PRODUCT-LINE-RELEASE-NOTES.md`: phase-to-commit map for the post-0.1.0 product line and what
  is still gated.
- `docs/VISUAL_MEDIA_PLAN.md`: the product-line direction that M0-M4 implement.
- `docs/M0-MEDIA-PROBE.md`, `docs/M4-VISUAL-MEDIA-AUDIT.md`, `docs/M4-PROCEDURE-LAYOUT.md`,
  `docs/M3-PRONUNCIATION-UI.md`: measured evidence for media, the visual/a11y gate, the procedure
  lens and the pronunciation studio.
- `docs/CB017-RELEASE-VERIFICATION.md`: gates, clean install, the clean-export run and the route
  finding as reclassified (CB-017 line, merged master `29bede7`).
- `docs/CB016-RELEASE-VERIFICATION.md`: the earlier record at `e93b8c5`, including the two route
  condition captures.
- `CHANGELOG.md`: what 0.1.0 contains and what it does not.
- `docs/SUBMISSION.md`: submission checklist, owners and gates.
- `docs/REVIEW_CB014.md`: the release-gate report on this candidate.
- `PREBUILD_SPEC.md`, `UX_SPEC.md`, `PLAN.md`: the frozen design, interface contract and plan.
- `AUDIT.md`: adversarial audit, including the product and demo corrections.
- `VAULT_LEARNING.md`: research leads behind the design.

## Development

```
bash scripts/test.sh            # unit tests, then node --check desktop/plugin.js
bash scripts/validate.sh        # pre-merge gate: tests, syntax, admission on an export, doctor, probe
bash scripts/validate-plugin.sh # release gate: admission on a git archive export of HEAD
```

Run `scripts/validate.sh` before any merge into master. It is the pre-merge gate; it passed on the
0.1.0 commit with 685 tests, node check OK and 31/31 backend expectations. On this tree the suite
is 2168 tests (`python3 -m unittest discover -s tests -t .`, `Ran 2168 tests`, `OK (skipped=1)`). Its admission step validates
an export of the tracked tree (`scripts/lib/gate-export.sh`), not the checkout root, so the
gitignored `.worktrees/` farm is never scanned and an uncommitted edit to a tracked file still fails
that step. `scripts/validate-plugin.sh` is the release gate for one pinned commit.

`desktop/plugin.js` is a single ES module with no relative imports and no JSX, because the
Desktop runtime loader refuses everything else. It is a single-writer file; see
`docs/WORK_PACKAGES.md`.

## License

No license file is present yet. Do not redistribute this repository until one is added. The choice
of license is DeseretSaint's, not a maintainer default, so this repository ships without one rather
than asserting terms nobody approved.
