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
- Replan of an approved plan (`da99d8a`, `6502e56`): `plan.replan` carries the authored document and
  sections onto a content-preserving new version and refuses when no faithful remap exists, and the
  Parent Studio withholds Generate lessons for a version it has proven cannot author. A lessons job
  that used to fail `INTERNAL_ERROR plan … has no authored document` now starts
  (`docs/REVIEW_CB017-FINAL.md` §3.2). No wire change; `cb.rpc` stays v7 (ruling R3).

### Known limitations at 0.1.0

Verbatim from `docs/REVIEW_CB017-FINAL.md` §9:

- A window with no reachable gateway renders no route page; the plugin's own degraded states are
  separate and proven.
- A structural objective `add` after a plan is authored yields a version with no covering outline:
  lessons are deliberately withheld, and the course must be started from a new brief.
- A lesson section above 4,000,000 characters cannot render in one page; imports refuse it pre-write.
- Rows 1/3/4/5/7/8/9/10/13 of the contest matrix are partial or open, as tabulated in
  `docs/REVIEW_CB015.md` §12.

Also at 0.1.0:

- Contest row 9 status: replan → lessons → export is fixed and proven through lesson-job start; the
  export half is re-driven before the demo.
- The CB-QA-09 route finding is P3-operational (host gateway binding), not a plugin defect: one
  gateway per host, owned by profile `default` (`docs/REVIEW_CB017-FINAL.md` §3.1).
- `evidence.inspect` returns an open check's reference answer in the L2 projection (CB-QA-10).
- The auxiliary open-response grader lane is disabled: it cannot distinguish an honest pass from a
  persuaded one (CB-QA-11).
- Image and speech generation are absent; lessons emit declarative media specs and text
  equivalents. Reminders are absent.
- No license file. The repository may not be redistributed until DeseretSaint adds one.

### Verification at the CB-017 candidate

`scripts/validate-plugin.sh` 3/3 checks on a clean `git archive` export of the release commit;
`scripts/validate.sh` exit 0 with 685 tests, `node --check` OK, 16 admission checks, 1 tool / 3
hooks registered, 31/31 mounted backend expectations; `git archive` of the commit installed into a
fresh home (`6/6` admission, `Installed.`). `docs/CB017-RELEASE-VERIFICATION.md` carries the
commands, the commit and the evidence files. 685 = 674 on master + 11 from the two replan branches.
