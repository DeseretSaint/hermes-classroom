# Changelog

Coursebook is a Hermes Desktop plugin. Versions below are plugin versions; the `cb.rpc` and `cb.db`
contract versions move independently and are named wherever they changed.

## 0.1.0 — contest candidate (unreleased)

Not published, not tagged and not submitted. Atlas's operator gate holds every publication step
until DeseretSaint signs off in chat; this section records what the tree contains, not a released
artifact.

### Shipped surface

- One package, two halves: a Python agent plugin (`plugin.yaml`, `coursebook/`, `dashboard/`) and a
  single ES-module Desktop plugin (`desktop/plugin.js`) that the host lifts into
  `$HERMES_HOME/desktop-plugins/coursebook/`.
- Backend routes under `/api/plugins/coursebook/`: `health`, `schema`, `rpc`, `runtime`, pack
  intake/export and artifact download.
- `cb.rpc` v7 with 52 methods over `cb.db` v4 (migrations `0001`-`0004`); seven frozen contract
  files with per-file sha256 pins in `docs/CONTRACTS.md`.
- Governed lessons: objectives, typed checks, bounded grading, one permitted transition per attempt,
  attempt/evidence records, notebook, quiz history, review queue, usage accounting.
- Pack pipeline: import, preview, inspect, export, delete, plus eight `parent.*` authoring methods;
  imports are validated against the pack manifest and refused before any write when they fail.
- Research inside plan jobs only, ledgered through the host `web_search`/`web_extract` seam, and
  recorded as `unavailable` rather than invented.
- Source revalidation (`source.revalidate`) with a nullable `sources.content_hash` baseline, so a
  changed source returns `CHECK_STALE` without touching learner evidence.

### Fixed during the candidate

Each item below is recorded with its own evidence in the commit that landed it; this changelog
summarises those records and does not re-verify them.

- D1 (`e3d6770`): pack sections over 8,000 characters imported and were then unreadable. Imports now
  split at semantic boundaries with byte-exact concatenation, refuse a section that cannot fit 500
  segments before writing, and repair already-stored text once per database (the `PRAGMA
  user_version = 1` repair marker, documented in `docs/ARCHITECTURE.md` §6).
- `enrollment.delete`'s dry run sent no idempotency key, so the delete confirmation never opened.
- Focus return from the notebook dialog; the view picker's accessible name now carries the selected
  view; an Offline state was added.
- `pack.export` of unchanged content no longer fails with an `IntegrityError`.

### Known limitations at 0.1.0

- The Desktop route is condition-dependent. It mounts against a reachable backend; on an isolated
  home whose gateway cannot start, the shell renders the session list for every route. The chat side
  of the demo cannot be recorded until this is fixed or explained.
  Evidence: `docs/CB016-RELEASE-VERIFICATION.md` §3.
- `evidence.inspect` returns an open check's reference answer in the L2 projection (CB-QA-10).
- The auxiliary open-response grader lane is disabled: it cannot distinguish an honest pass from a
  persuaded one (CB-QA-11).
- Image and speech generation are absent; lessons emit declarative media specs and text
  equivalents. Reminders are absent.
- Editing an approved plan does not produce a new authored lesson document, so a course must be
  rebuilt from a new brief after a replan (`t_fc758da8`, `t_9bdcc54f`).
- No license file. The repository may not be redistributed until DeseretSaint adds one.

### Verification at `e93b8c5`

`scripts/validate-plugin.sh` 3/3 checks on a 787-file export; `scripts/validate.sh` exit 0 with 674
tests, `node --check` OK, 16 admission checks, 1 tool / 3 hooks registered, 31/31 mounted backend
expectations. `docs/CB016-RELEASE-VERIFICATION.md` carries the commands and the evidence files.
