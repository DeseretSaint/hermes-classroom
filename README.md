# Coursebook

Coursebook is a Hermes Desktop learning workspace for adults and parents. It is designed to turn
a goal or a reusable course pack into a governed, resumable sequence of lessons: one objective at
a time, typed checks, bounded grading, transactional transitions, inspectable evidence, and
sourced visuals and audio. Parent mode prepares lesson packs that a parent teaches; children do
not chat with Coursebook.

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

Version 0.1.0. The release gates and the route evidence for this tree are in
`docs/CB017-RELEASE-VERIFICATION.md` (CB-017 candidate `67d6773`, the tree this record re-derives);
`docs/CB016-RELEASE-VERIFICATION.md` is the earlier record at `e93b8c5`, kept for its two
condition captures. The adversarial report on the previous candidate is `docs/REVIEW_CB014.md`
(candidate `f4a42f34`, NO-GO on the Desktop route, not on the backend).

Three states are used below. **Working** means a command was run against this build and passed.
**Implemented, unverified in the UI** means the backend path is implemented and tested, and the
Desktop surface exists, but this release pass did not drive it through the UI. **Absent** means
there is no code path at all.

| Surface | State in this build |
| --- | --- |
| One installable package (agent half plus Desktop half) | Working: `scripts/install-local.sh` installs both halves; `hermes plugins validate` and `hermes plugins doctor` pass |
| `coursebook_status` agent tool (read-only health) | Working: the single registered tool |
| Backend routes `/health`, `/schema`, `/rpc`, `/runtime`, `/packs/*`, `/artifacts/<handle>` | Working: 31/31 backend expectations pass in `scripts/probe-backend.py` |
| Frozen contracts: `cb.rpc` v7, `cb.db` v4, `cb.jobs` v2, `cb.errors` v2, `cb.pack` v1, `cb.projection` v1, `cb.vocabulary` v1 | Working: 52 declared methods, 52 handlers, no contract problems from `/runtime` |
| Profile-scoped SQLite schema and migrations `0001`-`0004` | Working: `health.get` answers `db.ready: true`, `schema_version: 4` on a fresh home |
| Desktop route `#/coursebook`, sidebar entry, pane, command palette, settings page | Working with a reachable backend: mounts the library, `New course`, Parent Studio and a course card (`docs/CB017-RELEASE-VERIFICATION.md` §2). A window with no gateway renders no route page for any hash — host shell degradation, reclassified P3-operational by Atlas (`docs/REVIEW_CB017-FINAL.md` §3.1) |
| Course creation, plans, lessons, grading, transitions, evidence | Implemented, unverified in the UI: 685-test suite, plus adversarial S01/S02/S10-S12 (duplicate submit, stale revision, invalid/hung/throwing grader) all pass |
| Replan of an approved plan, then lessons, then export | Implemented: the authored outline is carried onto the replanned version (`da99d8a`), Generate lessons is withheld for a version that cannot author (`6502e56`), and a lessons job now starts where it used to fail `INTERNAL_ERROR`. Proven through lesson-job start; the export half is re-driven before the demo (`docs/REVIEW_CB017-FINAL.md` §3.2) |
| Notebooks, quiz history, review queue, usage accounting | Implemented, unverified in the UI: `notebook.save/list/update/delete`, `quiz.history`, `review.queue/action` and `usage.summary` are in the mounted registry |
| Pack import and export, Parent Studio authoring | Implemented, unverified in the UI: `pack.import/export/preview/inspect/list/delete` and eight `parent.*` methods; P17/P18/P20 pass, and export reproduces the reviewed content hash |
| Research | Implemented inside plan jobs: bounded, query-capped and ledgered through the host `web_search`/`web_extract` seam; records `unavailable` rather than inventing a source. No standalone RPC |
| Image and speech generation | Absent: the media policy, content-addressed artifact store and text-fallback path ship, but no image or TTS provider is wired, and lesson generation emits declarative media specs, never generated media |
| Reminders | Absent: no RPC, no job runner, no storage |

Every method declared by `cb.rpc` v7 has a handler in this build, so there is no command that
answers a plausible success for work it cannot do. A method outside the contract is refused with
`VALIDATION_FAILED`; a handler that cannot answer returns a contract error rather than a
fabricated result. Two backend defects are open and recorded in `docs/REVIEW_CB014.md`:
`evidence.inspect` carries an open check's reference answer in the L2 projection (CB-QA-10), and
the optional auxiliary grader cannot yet distinguish a persuaded pass from an honest one
(CB-QA-11).

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

Install from the plugin catalog (`hermes plugins install coursebook`) is not available: the entry is
still a draft and no pull request has been opened. `catalog/coursebook.yaml` validates against
`hermes-agent`'s catalog validator and carries a real release pin, but gates 5, 7, 9 and 10 of
`docs/SUBMISSION.md` are open, so submitting it is on hold. Owner: Harbor and DeseretSaint.

Cloning from GitHub is not a supported install path yet: the repository is private, and making it
public is publication, which needs DeseretSaint's sign-off. Until then, install from a local
checkout as above.

## First run

Open Coursebook in the Desktop sidebar. The plugin loads: the sidebar item, the pane and the
command-palette entries register, and the settings page registers when the host exposes a
settings-page seam. With no chat bound to an enrollment, the pane offers `Open Coursebook` and
reports that no durable chat is bound yet. The backend it reads answers `health.get` with
`db.ready: true` and `schema_version: 4`.

The route is condition-dependent, and one of the two conditions is not shippable. In a window that
reaches a gateway-backed backend, `#/coursebook` mounts the course library, the `New course` action
and Parent Studio (`docs/CB016-RELEASE-VERIFICATION.md` §3b). In a window whose isolated home cannot
start a gateway, the shell renders the session home for every hash instead (CB-QA-09, §3a). A demo
that shows the chat side needs the second condition fixed, because a lesson binds to a chat.

Ask the agent to run `coursebook_status` to get the health block as JSON. If the backend is not
mounted, the pane names the enable path and offers Check again instead of showing an empty
course list.

Step-by-step install, uninstall and troubleshooting: `docs/INSTALL.md`.

## Privacy and egress

Coursebook holds no vendor credentials and makes no direct outbound HTTP request of its own.
Every provider call goes through a seam the Hermes profile already configures:

- lesson chat uses the selected chat provider and any configured external memory provider;
- plan and lesson generation use the host plugin LLM route; the optional auxiliary grader uses
  the same route and is disabled in this build;
- research uses the host `web_search` and `web_extract` tools, so the user's configured backend,
  egress rules and SSRF checks apply;
- pack import and export are local files and perform no upload, and there is no telemetry.

State lives in profile-scoped SQLite at `$HERMES_HOME/plugin-data/coursebook/data.db` and
migrates on first use. Usage rows are recorded locally, and only for a session this process
observed as bound to an enrollment. "Local" describes storage, not inference.

Full text, including what Coursebook refuses to do with schoolwork and what it cannot control at
the host level: `docs/PRIVACY_EGRESS.md`.

## Limitations

This candidate is not shippable as a Desktop product.

- CB-QA-09 is a host gateway binding, not a plugin defect (P3-operational, Atlas ruling in
  `docs/REVIEW_CB017-FINAL.md` §3.1). This host runs one gateway for profile `default` and refuses
  a second, so an isolated window has no composer; the plugin's own `Backend off` / `Offline`
  states are proven separately. The demo's chat surface therefore needs the operator to record on
  the gateway-owning profile, or to stop that gateway first.
- Row 9 of the contest matrix is partial: replan → lessons → export is fixed and proven through
  lesson-job start; the export half is re-driven before the demo.
- Image and speech generation, and reminders, are absent. Research runs only inside plan jobs.
- The auxiliary open-response grader is disabled. Closed checks are graded against a stored
  reference; with the lane enabled, an answer that persuades an obedient grader is accepted
  (CB-QA-11).
- `evidence.inspect` returns an open check's reference in the L2 projection (CB-QA-10). The UI
  does not render it; the RPC boundary does.

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
- `docs/CB017-RELEASE-VERIFICATION.md`: gates, clean install, the clean-export run and the route
  finding as reclassified (CB-017 candidate `67d6773`).
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

Run `scripts/validate.sh` before any merge into master. It is the pre-merge gate, and it passes
on this tree: 685 tests OK, node check OK, 31/31 backend expectations. Its admission step validates
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
