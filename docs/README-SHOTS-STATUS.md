# README/demo capture set — rig, what exists, and the blocker

Status: **complete under option (b).** Nine README/demo frames are committed under
`docs/assets/`, with captions and provenance in `docs/README-SHOTS.md`. The lesson-pane and quiz
frames reuse the merged CB-009/CB-015 live evidence; the detached-binding behavior in this rig is
recorded below as a rig limitation, not claimed as a product defect.

## Rig (built for this card, from this worktree's HEAD 22a9180)

| Piece | Command | Notes |
| --- | --- | --- |
| Install both halves into a disposable home | `COURSEBOOK_TEST_HOME=$HOME/.hermes/cb-readme/home bash scripts/install-local.sh` | validation passed, 1 tool + 3 hooks registered |
| Isolated backend on 44310 | `COURSEBOOK_TEST_HOME=$HOME/.hermes/cb-readme/home CB013_PORT=44310 bash scripts/cb013-live-backend.sh` | `/api/plugins/coursebook/runtime` 200, `wire_version: 6`, `plugin_root` this worktree |
| Demo pack, real import path | `python3 scripts/seed-demo-course.py --base-url http://127.0.0.1:44310 --token cb013-test-token` | course `crs_d6c633fe…`, enrollment `enr_1e5e6476…`, content hash `sha256:638ce371…` |
| Desktop window, own userdata | `CB_README_USERDATA=$HOME/.hermes/cb-readme/userdata2 CB_README_CDP_PORT=9382 bash scripts/cb-readme-window.sh` | renderer from the dev server, CDP 9382 |
| Capture | `CB015_CDP_PORT=9382 node scripts/cb-readme-capture.mjs dark` | fixed 1600x1000 viewport at dpr 2, raw frames + per-frame manifest |

The Desktop half is opt-in for a unified package (`defaultEnabled: false` in the scanner), so the
window only mounts `#/coursebook` after the app's own decision store says so —
`localStorage['hermes.desktop.pluginDecisions.v2'] = {"coursebook":true}`, the same key the
Capabilities → Plugins toggle writes. With that set, the route mounts at 1340x946 on a
1600x1000 viewport and `data-cb-destination="courses"`.

## What was captured (`~/.hermes/cb-readme/raw`, 2x, not committed)

- `00-courses-dark` — course list, one real imported pack, `0 independent · 4 objectives`
- `00b-overview-dark` — course detail overview
- `01-library-dark` — Library, one pack, recorded provenance

Each frame carries mode, destination, viewport, heading and text in `raw/manifest.json`.

## The blocker

Section 0 of the seeded course arrives with its chat binding **detached**:

> This section's chat binding is detached. Submit stays disabled until it is reconciled.

Measured behaviour:

1. `Reattach` returns the route to the course list (`data-cb-route` unmounts, hash stays
   `#/coursebook`) and the next visit to the section reports detached again — 3 of 3 attempts.
2. `Start a fresh run` navigates out of the route entirely (`location.hash` → `#/`, no
   `[data-cb-route]`, no `#cb-attempt-answer` in the document). The new session opens at the
   session home, and the Coursebook pane does not render there, so the check cannot be answered
   from the pane either.

Consequences: `quiz in progress` and `quiz results` cannot be captured, the lesson frame carries a
detached banner that must not ship as README art, and the required light/dark pair cannot be taken
on a lesson surface. The three frames above are clean (no toast, no focus ring, no placeholder row),
but they are not the deliverable.

## What to decide before the next pass

- Whether `Reattach` returning to the course list is the intended behaviour or a defect worth a card
  (the audit's F-06 already records the pane as hard to drive headlessly).
- Whether the lesson-pane frame may be captured from the CB-009/CB-011 pane evidence already merged
  on master, captioned with that provenance, instead of re-driving the binding here.
