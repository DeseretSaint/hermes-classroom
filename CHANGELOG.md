# Changelog

Coursebook is a Hermes Desktop plugin. Versions below are plugin versions; the `cb.rpc` and `cb.db`
contract versions move independently and are named wherever they changed.

## 0.2.0 — the aiming and trust pass (unreleased)

- **The end goal is asked, not inferred.** The create flow asks what the learner wants to be able
  to do; the answer is composed into the brief and shapes the plan.
- **The plan aims where they pointed.** Capability and exit performance are derived from the
  performance requirement, and a plan with no coverage for the stated capability is refused.
- **Media is decided by what the lesson has to teach**: need-based demand, pronunciation reference
  plus narration for language lessons, a textless illustration prompt built (not forwarded), and
  role geometry (4:3 illustration, 3:4 portrait).
- **The plan screen tells the truth** — stage, clock, cost band — and a learner can adjust a plan
  rather than only approve or abandon it.
- **The tutor is beside the check**, and "I used a hint" now answers.
- **Labels are drawn by the UI over a label-free figure** (`cb.rpc` v27).
- **A required cited reference is flagged, never silently replaced by text.**
- **The validator is told what each criterion means**; an honest unknown is a recorded waiver.
- **A truncated lesson is re-asked**, and attempt 2 repairs the draft instead of rewriting it.

Still unreleased: no tag, no catalog merge, no announcement.

## 0.1.0 — contest candidate (unreleased)

Not tagged, not merged into the catalog and not announced. A draft catalog pull request is open
(`NousResearch/hermes-agent#152920`, unmerged); Atlas's operator gate still holds every publication
step — merge, tag, announcement, contest form — until DeseretSaint signs off in chat. This section
records what the tree contains, not a released artifact.

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
- License: MIT, in `LICENSE` at the root (copyright 2026 DeseretSaint). The owner chose it on
  2026-11-10 in board card `t_6f2d2080`. The licence makes redistribution lawful; it does not
  authorise a tag, a catalog merge or an announcement, which stay closed under
  `docs/SUBMISSION.md` §0.

### Course portability and first-run wiring (CP-015g backend pass, 2026-11-11)

- **`cb.pack` v3** adds one optional root `presentation` block: the authored mode
  (`textbook`/`game`) and, for a Game course with an approved world, the world kit's identity and
  its plate files. It cannot represent XP, engagement, attempts, evidence, homework or tutor turns,
  and the GM contract test asserts the pack seam reads only `course_worlds`/`world_assets`.
  Import restores `courses.presentation_mode`, an approved world and its assets, with `kit_hash`
  re-derived from the importing database's own rows. v1 and v2 packs keep their exact shape.
- **`course.export` carries visuals.** A section's generated `visual`/`narration` artifacts are
  written as `media/<NN>-<role>-*.ext`, linked through the frozen v2 `media[]` with a text
  equivalent and a per-artifact licence. A missing artifact blocks the export instead of shipping a
  text-only lesson.
- **Pack import materialises checks.** `pack.import` wrote a `check_prompt` segment but no `checks`
  row, so every imported course had zero gradable checks and no attempt could be recorded. Each
  manifest check now becomes a real `checks` row through the deterministic import audit; a check
  that fails its own audit imports ungraded. This was the clean-seed blocker in
  `docs/HACKATHON-DEMO.md` §3.
- **Install provisioning check.** `python3 -m coursebook.install_check --source <checkout>
  --provisioning` reports bundled skills, declared tools/hooks, the contract set and current
  `cb.pack` version, dependency importability, bundled starter pack hashes and (with `--home`) the
  profile database schema; exit 1 on any error.

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
- CP-044 (job attempt deadline): a generation job had per-call deadlines but no deadline of its
  own, so calls that each finished "in time" still kept the row `running` past half an hour
  (CP-015 checkpoint 4: a 648 s plan attempt). Each job attempt now carries one wall-clock budget
  (`COURSEBOOK_JOB_DEADLINE_SECONDS`, default 1800 s); every bounded foreign call inside a stage is
  clamped to what is left of it, so the in-flight request is cancelled at whichever bound arrives
  first. On expiry the row is failed with the existing `HOST_UNAVAILABLE` shape (`details.job_deadline:
  true`, `deadline_s` = remaining budget) and the lease is released; plan jobs now record the
  `gen_call_waits` liveness rows the lesson stage already had. No contract or schema change.
  The 648 s CP-015 row was re-measured: its `coursebook.plan.generate` call answered in 469 s with
  22 256 output tokens inside its own 900 s bound — the defect was the missing job budget, not a
  deadline that failed to fire. (Both numbers are the `usage_events` row for
  `operation_id = job_659f1edba70d491b831dd9d263539db3`, `duration_ms 468992`,
  `output_tokens 22256`, `input_tokens 8123`; the host log line for that call reads `tokens=30379`,
  which is the same input+output sum.) The 1800 s default is policy above the slowest *completed*
  job measured across the disposable homes (`probes/cp044-job-duration-census.py`: 852 s, 45
  completed jobs, nothing above 1800 s), i.e. ~2.1x margin, and it is env-overridable.
  Evidence: `probes/cp044-job-deadline.py`, `probes/cp044-job-duration-census.py`,
  `tests/test_cp044_job_deadline_hanging_provider.py`, `docs/ARCHITECTURE.md` §8.1.

- H-194e: a page-title revision of a section lost its check and became unexportable. `lesson.revise`
  now copies the previous revision's `gen_lesson_checks` binding to the new `gen_lessons` row (the
  check belongs to the objective, not to a page version; a pre-fix checkless revision inherits the
  newest binding in its section on the next edit) and refuses a page payload that rewrites the
  page's `check` projection; `parent_export_status` and `parent.export` now run one shared gate
  (`parent_authoring.export_gate`) in one order, so the review surface cannot answer `ready` for a
  content set the export refuses. No wire change; `cb.rpc` stays v20 and `cb.db` stays v12. Evidence:
  `docs/CONTRACTS.md` "H-194e correction", `tests/test_h194_fine_tune.py::ExportedPageRevisionTest`.

- H-182 follow-up (lesson request bound): a legal 3-page parent plan's plan-wide lessons job failed
  in 31 s with `INTERNAL_ERROR request payload is 25081 bytes compact, over the 24000-byte request
  bound`, while a one-section regeneration succeeded. The lesson-validation request carried the
  authored lesson **and** its learner-facing page (a projection of the same lesson) and the whole
  research ledger, instead of the section's own sources. Neither is serialised now: the lesson is
  sent once, and both lesson passes receive `_lesson_ledger` (the section's cited sources, else the
  first four. `REQUEST_BYTES_BOUNDS` is unchanged. Measured on the live rows: 24 240 bytes compact
  before, 13 265 after. The recorded-transcript harness-e2e packet was regenerated (per-lesson
  `usage.input_tokens` estimates and manifest hashes only; every verdict and scenario unchanged). No
  wire or schema change. Evidence:
  `audit/visual/h182-repair-live-followup/EVIDENCE.md`, `tests/test_generation.py::LessonRequestBoundTest`,
  `tests/test_generation.py::PlanWideLessonBoundTest`.
- CREATE-2 (the starting level is a question): it was an optional free-text box inside "Help me
  tune it", so the placeholder "complete beginner" was never a value and the plan brief carried no
  `level` at all — the beginner rule had nothing to read. The first create screen now asks
  "Where are you starting from?" with three one-tap choices (None / Some / Confident) that send the
  rule's own vocabulary (`none`, `some`, `confident`), the trailhead states the answer before
  Create, and the value travels unchanged through `course.create` and the plan brief into
  `enforce_plan_rules(level=…)`. The contract already accepted `level`; no wire or schema change.
  Evidence: `tests/test_desktop_create_flow.py::CreateFormInteractionTest`,
  `tests/test_learner_plan_flow.py::test_the_one_tap_level_reaches_the_plan_rule`.
- CREATE-5 ("Change the goal"): the create result screen's plan review had no create-form handler,
  so the one repair control for an empty plan answered with a sentence instead of a door. The same
  screen now hosts that return: the control reopens the form on the goal step with the brief the
  plan actually ran (goal, title, recipe, dials, locale, level, subject) prefilled and a fresh
  idempotency key, and a surface that cannot host it is never offered the action — its refusal gets
  `try_again` instead. No wire or schema change. Evidence:
  `tests/test_desktop_create_flow.py::CreateFormInteractionTest::test_change_the_goal_returns_to_the_prefilled_form`,
  `tests/test_desktop_plan_reject.py::PlanRejectModelTest::test_a_learner_surface_without_a_create_form_is_offered_try_again`.
- CREATE-7 (subject in the learner's own words): the declared subject resolved by exact alias only,
  so "auto repair", "Spanish" and "electrical safety" all fell to the generic domain profile. One
  bounded stem table plus normalisation (case, a plural, word order with the phrase's head last)
  now answers them as `technical_procedure`, `language` and `technical_procedure`, while a subject
  no profile names ("astronomy", "poetry") still resolves to `general`. No wire or schema change.
  Evidence: `tests/test_cp015g_domain_default.py::DeclaredSubjectInOwnWordsTest`.

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
- ~~No license file~~ — closed 2026-11-10: MIT, `LICENSE` at the root (owner decision
  `t_6f2d2080`). Redistribution is lawful from that commit on; publication stays closed.

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
