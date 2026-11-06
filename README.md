# Coursebook

Coursebook is a Hermes Desktop learning workspace for adults and parents. It turns a goal or a
reusable course pack into a governed, resumable sequence of lessons: one objective at a time,
typed checks, bounded grading, transactional transitions, inspectable evidence, and sourced
visuals and audio. Parent mode prepares lesson packs that a parent teaches; children do not chat
with Coursebook.

Coursebook is not a prompt. A chat prompt can answer a question; it cannot make the answer
change what happens next. In Coursebook the model teaches, while the plugin owns the objective,
the attempt, the rubric, the evidence, the next permitted transition, and the durable record.

This repository is a pre-release skeleton. Read the status table before installing.

## Status

Version 0.1.0, baseline commit recorded in `docs/REVIEW_CB001.md`. One vertical slice exists:
the package loads, the backend answers, and the Desktop pane reports exactly what is real. No
course can be created, graded, exported or scheduled yet.

| Surface | State in this build |
| --- | --- |
| One installable package (agent half plus Desktop half) | Working |
| `coursebook_status` agent tool (read-only health) | Working |
| Backend routes `/health`, `/schema`, `/rpc`, `/runtime` | Working |
| Frozen v1 contracts in `contracts/` | Working |
| Desktop route, sidebar entry, pane, command palette, settings page | Working |
| Profile-scoped SQLite schema | Not migrated (no migrations ship yet) |
| Course creation, plans, lessons, grading, transitions, evidence | Not implemented |
| Research, images, audio, notebooks, reminders, usage accounting | Not implemented |
| Pack import and export, Parent Studio | Not implemented |

Every command in the frozen wire contract that has no handler answers `NOT_IMPLEMENTED`. That is
deliberate: there is no code path that returns a plausible success for work the backend cannot
do. The pane shows `Database: not migrated` and `Courses: none yet`, and it labels the empty
state as empty rather than as sample data.

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

Then enable the Desktop half in the app: Capabilities, Plugins, Coursebook, on. The two halves
are enabled separately; the pane detects the mismatch and says so.

Verify:

```
hermes plugins doctor coursebook
bash scripts/validate.sh
```

Install from the plugin catalog (`hermes plugins install coursebook`) is TODO. The entry is
drafted in `catalog/coursebook.yaml` but cannot be submitted until the release commit is pushed
and the pin is final. Owner: Harbor.

Cloning from GitHub is also TODO: the public repository does not exist yet, and pushing needs
operator approval. Until then, install from a local checkout as above.

## First run

Open Coursebook in the Desktop sidebar. The pane shows three rows and nothing else:

- Backend: `cb.rpc v1`, plugin 0.1.0
- Database: `not migrated`, with the note that no course data can be stored yet
- Courses: `none yet`, with the note that this is not sample data

Ask the agent to run `coursebook_status` to get the same health block as JSON. If the backend is
not mounted, the pane names the enable path and offers Check again instead of showing an empty
course list.

Step-by-step install, uninstall and troubleshooting: `docs/INSTALL.md`.

## Privacy and egress

Coursebook makes no network requests of its own in this build. It stores nothing yet: the
database path is defined but no schema has been created. The status tool reads local health and
returns it to the agent.

The planned behavior is disclosed per operation, not as one generic sentence. Lesson chat may
reach the selected chat provider and any configured external memory provider; planning and
grading may reach their auxiliary provider; research reaches search and fetch services plus the
named sites; image and speech reach their respective providers; state and artifacts persist
locally; community export releases only the reviewed pack and performs no upload. "Local"
describes storage, not automatic local inference.

Full text, including what Coursebook refuses to do with schoolwork and what it cannot control at
the host level: `docs/PRIVACY_EGRESS.md`.

## Limitations

This baseline deliberately does not contain course creation, plan generation, grading,
transitions, evidence UI, research, media, pack import or export, Parent Studio, reminders, or
usage accounting. Each lands in its own work package against the frozen contracts, with the
owning specialist named in `docs/WORK_PACKAGES.md`.

There is no learning-style diagnosis, no "2 sigma" claim, no guaranteed mastery, no child safety
or COPPA certification, and no efficacy claim. Educational research motivates the design;
Coursebook has not established that it improves learning. Parent observations, when they exist,
are labeled `parent_reported` and are never combined with automated mastery.

## Documentation

- `docs/INSTALL.md`: install, enable, verify, uninstall, troubleshooting.
- `docs/ARCHITECTURE.md`: verified SDK seams, spec to SDK corrections, failure states.
- `docs/CONTRACTS.md`: the six frozen contracts and their open questions.
- `docs/WORK_PACKAGES.md`: file ownership and merge order.
- `docs/PRIVACY_EGRESS.md`: per-operation disclosure.
- `docs/DEMO.md`: the demo script skeleton and its precomputed/live split.
- `docs/SUBMISSION.md`: submission checklist, owners and gates.
- `docs/REVIEW_CB001.md`: verbatim gate output for the baseline.
- `PREBUILD_SPEC.md`, `UX_SPEC.md`, `PLAN.md`: the frozen design, interface contract and plan.
- `AUDIT.md`: adversarial audit, including the product and demo corrections.
- `VAULT_LEARNING.md`: research leads behind the design.

## Development

```
bash scripts/test.sh       # 46 unit tests, then node --check desktop/plugin.js
bash scripts/validate.sh   # tests, syntax, hermes plugins validate, hermes plugins doctor
```

Run `scripts/validate.sh` before any merge into master. It is the admission gate.

`desktop/plugin.js` is a single ES module with no relative imports and no JSX, because the
Desktop runtime loader refuses everything else. It is a single-writer file; see
`docs/WORK_PACKAGES.md`.

## License

No license file is present yet. Do not redistribute this repository until one is added. Owner:
DeseretSaint.
