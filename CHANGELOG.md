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
- H-66 (job liveness): a live `plan` job could sit `running` with an expired lease and no way to
  cancel. Three foreign calls had no real deadline — the host `web_search`/`web_extract` seam, the
  host model call, and the media tools — and the heartbeat renewed on a bare thread that lost the
  gateway's context-local profile, so every renewal silently failed. Deadlines now raise typed
  `ResearchTimeout`/`ProviderTimeout`/`MediaTimeout`; the heartbeat runs under the caller's context;
  a live reaper moves expired leases to `interrupted_requires_retry` / `cancelled` without a
  restart; and cancellation is checked at every provider and tool boundary. No contract or schema
  change. Evidence: `docs/H66-EVIDENCE.md`, `docs/ARCHITECTURE.md` §8, `probes/h66-liveness.py`,
  `tests/test_h66_liveness.py`.
- H-192c (validator output bound): bounding the validation *demand* left the validator's own
  reasoning uncapped — the host does not forward `LLMRequest.max_tokens` on the nous
  chat-completions route, and a live five-criteria/six-claim pass emitted 19 739 completion tokens
  in 927 s past its 600 s deadline. `register(ctx)` now declares one plugin-owned auxiliary task
  (`cb_validate`, `reasoning_effort: low`, `extra_body.max_tokens: 4000`) and every validation call
  passes its key, on the configured second-model route and the author-model fallback alike; a host
  without the seam is reported as unbounded instead of silently uncapped. No contract or schema
  change. Evidence: `docs/GENERATION.md` §2, `tests/test_h192c_validator_output_bound.py`,
  `audit/adversarial/live-generation-2026-11-08-h192/STATUS-h192c.md`.

- H-194e: a page-title revision of a section lost its check and became unexportable. `lesson.revise`
  now copies the previous revision's `gen_lesson_checks` binding to the new `gen_lessons` row (the
  check belongs to the objective, not to a page version; a pre-fix checkless revision inherits the
  newest binding in its section on the next edit) and refuses a page payload that rewrites the
  page's `check` projection; `parent_export_status` and `parent.export` now run one shared gate
  (`parent_authoring.export_gate`) in one order, so the review surface cannot answer `ready` for a
  content set the export refuses. No wire change; `cb.rpc` stays v20 and `cb.db` stays v12. Evidence:
  `docs/CONTRACTS.md` "H-194e correction", `tests/test_h194_fine_tune.py::ExportedPageRevisionTest`.

### Known limitations at 0.1.0

Verbatim from `docs/REVIEW_CB017-FINAL.md` §9:

- A window with no reachable gateway renders no route page; the plugin's own degraded states are
  separate and proven.
- A structural objective `add` after a plan is authored yields a version with no covering outline:
  lessons are deliberately withheld, and the course must be started from a new brief.
- A lesson section above 4,000,000 characters cannot render in one page; imports refuse it pre-write.
- Rows 1/3/4/5/7/8/10/13 of the contest matrix are partial or open, as tabulated in
  `docs/REVIEW_CB015.md` §12. Row 9's export half was driven after this gate (§10).

Also at 0.1.0:

- Contest row 9 is closed end to end on this tree: plan v10 approved after replan, lessons job
  `job_2390ab7a` completed with 4 lessons, lesson set re-approved, and export `exp_2e068c56`
  produced with content hash `sha256:ccf69462…e5a5` matching the approved hash (backend export
  ready, no `blocked_reason`). Evidence: `docs/REVIEW_CB017-row9-ui.json`, `docs/REVIEW_CB017-FINAL.md` §10.
- The CB-QA-09 route finding is P3-operational (host gateway binding), not a plugin defect: one
  gateway per host, owned by profile `default` (`docs/REVIEW_CB017-FINAL.md` §3.1).
- `evidence.inspect` returned an open check's reference answer in the L2 projection (CB-QA-10) at
  `29bede7`; this tree closes it: criteria are projected through `PUBLIC_CRITERION_FIELDS` with a
  `check_spec_withheld` marker, and `tests/adversarial/attack_state.py` S07 passes.
- The auxiliary open-response grader lane is disabled: it cannot distinguish an honest pass from a
  persuaded one (CB-QA-11).
- Image and speech generation were absent at `29bede7`; this tree implements them on `master` since
  `3cead45` (M0) through the host's configured image/TTS providers, with text equivalents and honest
  degraded states. Reminders remain absent.
- No license file. The repository may not be redistributed until DeseretSaint adds one.

### Verification at the release commit `29bede7`

`scripts/validate-plugin.sh` 3/3 checks on a clean `git archive` export of the release commit (802
files); `Ran 685 tests in 72.181s` — `OK`; `node --check` OK; `git archive` of the commit installed
into a fresh home (`6/6` admission, `Installed.`) and answered `cb.rpc` v7 with 52 methods,
`contract_problems []`, schema 4. `docs/CB017-RELEASE-VERIFICATION.md` carries the commands, the
commit, the verbatim output and the install transcript. 685 = 674 on master before CB-017 + 11 from
the two replan branches.

## After 0.1.0 — product line (not a release)

M0-M4 of `docs/VISUAL_MEDIA_PLAN.md` are implemented and measured across master and product-line
branches. They are **not** a version bump, not a release, and not a catalog entry: no tag, no pull
request, no submission, and the gate in `docs/SUBMISSION.md` §0 is unchanged. The phase-to-commit
map with per-phase evidence and the gated remainder is `docs/PRODUCT-LINE-RELEASE-NOTES.md`.
