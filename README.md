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
Studio authoring surface are implemented and tested. The Desktop page does not mount yet
(CB-QA-09), so the UI is not shippable. Read the status table before installing.

## Status

Version 0.1.0. The release candidate and its gate results are in `docs/REVIEW_CB014.md`
(candidate `f4a42f34`). That report is a NO-GO on the Desktop route, not on the backend.

Three states are used below. **Working** means a command was run against this build and passed.
**Implemented, unreachable** means the backend path is implemented and tested but cannot be
reached from the Desktop while `#/coursebook` renders the session home (CB-QA-09). **Absent**
means there is no code path at all.

| Surface | State in this build |
| --- | --- |
| One installable package (agent half plus Desktop half) | Working: `scripts/install-local.sh` installs both halves; `hermes plugins validate` and `hermes plugins doctor` pass |
| `coursebook_status` agent tool (read-only health) | Working: the single registered tool |
| Backend routes `/health`, `/schema`, `/rpc`, `/runtime`, `/packs/*`, `/artifacts/<handle>` | Working: 31/31 backend expectations pass in `scripts/probe-backend.py` |
| Frozen contracts: `cb.rpc` v6, `cb.db` v3, `cb.jobs` v2, `cb.errors` v2, `cb.pack` v1, `cb.projection` v1, `cb.vocabulary` v1 | Working: 51 declared methods, 51 handlers, no contract problems from `/runtime` |
| Profile-scoped SQLite schema and migrations `0001`-`0003` | Working: `health.get` answers `db.ready: true`, `schema_version: 3` on a fresh home |
| Desktop route `#/coursebook`, sidebar entry, pane, command palette, settings page | Not working: every registration exists, but the route renders the session home instead of the page (CB-QA-09, open) |
| Course creation, plans, lessons, grading, transitions, evidence | Implemented, unreachable: 636-test suite, plus adversarial S01/S02/S10-S12 (duplicate submit, stale revision, invalid/hung/throwing grader) all pass |
| Notebooks, quiz history, review queue, usage accounting | Implemented, unreachable: `notebook.save/list/update/delete`, `quiz.history`, `review.queue/action` and `usage.summary` are in the mounted registry |
| Pack import and export, Parent Studio authoring | Implemented, unreachable: `pack.import/export/preview/inspect/list/delete` and eight `parent.*` methods; P17/P18/P20 pass, and export reproduces the reviewed content hash |
| Research | Implemented inside plan jobs: bounded, query-capped and ledgered through the host `web_search`/`web_extract` seam; records `unavailable` rather than inventing a source. No standalone RPC |
| Image and speech generation | Absent: the media policy, content-addressed artifact store and text-fallback path ship, but no image or TTS provider is wired, and lesson generation emits declarative media specs, never generated media |
| Reminders | Absent: no RPC, no job runner, no storage |

Every method declared by `cb.rpc` v6 has a handler in this build, so there is no command that
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

Install from the plugin catalog (`hermes plugins install coursebook`) is TODO. The entry in
`catalog/coursebook.yaml` is still pinned to the skeleton commit and marked not submitted; it
must be re-pinned to the release commit before submission. Owner: Harbor.

Cloning from GitHub is also TODO: the public repository does not exist yet, and pushing needs
operator approval. Until then, install from a local checkout as above.

## First run

Open Coursebook in the Desktop sidebar. The plugin loads: the sidebar item, the pane and the
command-palette entries register, and the settings page registers when the host exposes a
settings-page seam. With no chat bound to an enrollment, the pane offers `Open Coursebook` and
reports that no durable chat is bound yet. The backend it reads answers `health.get` with
`db.ready: true` and `schema_version: 3`.

The route itself does not mount on this candidate: `#/coursebook` renders the session home
instead of the Coursebook page (CB-QA-09). Until that is fixed, the course library, the create
and import flows, Parent Studio and Activity cannot be reached from the UI.

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

- `#/coursebook` renders the session home instead of the page (CB-QA-09). Every UI surface is
  unverified until it mounts, and nothing in this README is a UI acceptance claim.
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
- `docs/ARCHITECTURE.md`: verified SDK seams, spec to SDK corrections, failure states.
- `docs/CONTRACTS.md`: the seven frozen contracts and their open questions.
- `docs/GENERATION.md`: the plan and lesson pipeline, research ledger and validation pass.
- `docs/WORK_PACKAGES.md`: file ownership and merge order.
- `docs/PRIVACY_EGRESS.md`: per-operation disclosure.
- `docs/DEMO.md`: the demo script and its precomputed/live split.
- `docs/SUBMISSION.md`: submission checklist, owners and gates.
- `docs/REVIEW_CB014.md`: the release-gate report on this candidate.
- `PREBUILD_SPEC.md`, `UX_SPEC.md`, `PLAN.md`: the frozen design, interface contract and plan.
- `AUDIT.md`: adversarial audit, including the product and demo corrections.
- `VAULT_LEARNING.md`: research leads behind the design.

## Development

```
bash scripts/test.sh            # 636 unit tests, then node --check desktop/plugin.js
bash scripts/validate.sh        # tests, syntax, doctor, backend probe (from the checkout)
bash scripts/validate-plugin.sh # release gate: admission on a git archive export of HEAD
```

Run `scripts/validate.sh` before any merge into master. It is the pre-merge gate, and it passes
on this tree: 636 tests OK, node check OK, 31/31 backend expectations. Its admission step points
`hermes plugins validate` at the checkout root, which also scans the gitignored `.worktrees/` tree
and can report `dangerous` for files that are in no version of the package; the admission verdict
comes from `scripts/validate-plugin.sh`, which exports the commit first.

`desktop/plugin.js` is a single ES module with no relative imports and no JSX, because the
Desktop runtime loader refuses everything else. It is a single-writer file; see
`docs/WORK_PACKAGES.md`.

## License

No license file is present yet. Do not redistribute this repository until one is added. Owner:
DeseretSaint.
