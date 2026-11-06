# Review packet — CB-011 Parent Studio (t_4255b696)

Status: **implemented and wired; end-to-end certification is partial — the lesson-generation stage is
where it stops, for backend reasons recorded below.** Nothing pushed to GitHub.

Branch `wt/cb-011-vellum`, worktree `/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_4255b696`,
built on `master` @ `adedf47` (cb.rpc v6 / cb.db v3, Cinder's executor).

## What is in the Desktop half

`desktop/plugin.js` (single module, `@hermes/plugin-sdk` only, `jsx()`/`jsxs()`, theme tokens only):

* **Destination**: Parent Studio is the third destination (`Courses · Library · Parent Studio`) with
  two palette entries (“Open Parent Studio”, “Write a parent lesson brief”) and route intents
  `studio` / `studio-new`. Imported packs stay in Library; authored courses are listed by
  `library.list{recipe:"parent"}` and open into the studio.
* **Brief** (`StudioBriefForm`): every field `cb.rpc#/$defs/parent_brief` requires — title, goal,
  starting point, age band, reading level, duration, setting, materials, exclusions, supervision,
  desired pages/visuals/narration — plus the provider/egress disclosure. Submit is impossible until
  `egress_acknowledged` is ticked, with the reason printed; client-side limits mirror the contract
  (title 200, goal 2000, 20 materials/exclusions, 5–600 min, 1–40 pages). `parent.brief.create` is
  sent with an idempotency key. The stored brief is then read back with `parent.brief.get`; **Duplicate
  brief** refills the form from that typed value (the disclosure is shown and re-acknowledged).
* **Plan** (`StudioPlanView`): split working view — outline/activities left (ordinal, title, evidence
  target, objective/check state), sources and review notes right (real `sources[]` from
  `parent.blueprint.read`, support verdict, the car-safety note when `setting=car`). Draft plans are
  editable (title, evidence target, add, remove, reorder, fenced on `expected_plan_hash` +
  `expected_revision`); `plan.approve` is a **separately labelled** action with copy saying it
  approves the outline, not one generated page; approved plans offer *Generate lessons*, *Generate
  missing lessons* (the lesson stage reuses every lesson already authored at this plan version) and
  *Start a new plan version* (`plan.replan`, which is the only way to change an approved plan).
* **Pages** (`StudioBlueprintView`): the five §10 tabs — Parent guide, Learner pages, Answers,
  Audio & visuals, Sources — as declared text with role badge, bytes, sha256 and a `clipped` badge.
  The Learner pages tab states “No answer key is included here”; the Answers tab states the opposite
  and why (addressed by `course_id` only, kept out of `LEARNER_FACING_ROLES`).
* **Export** (`StudioExportPanel`): gated on `parent.blueprint.read.export` (`ready` +
  `blocked_reason`), showing the approved vs current content hash, format checkboxes (pack, PDF),
  then the exact file list with roles `parent_guide / learner_page / answer_guide`, artifact kind,
  mime, bytes, hash and per-artifact download links from `artifact.get` (session-bound host route).
  Refusals render `details.reason` and, for `export_not_exportable`, the `details.problems` list —
  no retry loop, no padding. Narration is deliberately not a text file: the copy says the script is
  the narration tab and part of the parent guide.
* **Reflection** (`StudioReflectionView`): easy/about right/too hard + revisit note +
  “offer to my next draft”, explicitly parent-reported and excluded from packs; the history list and
  the “start the next brief from this note” path (which opens the duplicate form with the note shown
  as a proposal, never applied silently).
* **Two gates, visibly distinct**: `PlanStateBadge` (Plan draft/approved/superseded · vN) and
  `ApprovalBadge` (Lesson set not approved / approved / Changes need review) in the header, plus the
  “Changes need review” banner derived from the approval row’s `state` + `invalidated_reason`.

## Live evidence (real backend, real Desktop window)

Isolated backend `127.0.0.1:44219` (own home `~/.hermes/coursebook-test/home`, plugin symlink → this
worktree), contract v6 / 51 methods; isolated Electron window with CDP 9337. The operator’s gateway
was not touched.

* `docs/cb011-shots/01-studio-list.png` — Parent Studio destination with authored courses.
* `docs/cb011-shots/02-brief-form.png` — the §10 brief with the egress disclosure and gated submit.
* `docs/cb011-shots/03-studio-brief.png` — read-back brief + plan job line.
* `docs/cb011-shots/04-studio-plan.png` — **Plan approved · v2**, **Lesson set not approved**,
  “You are the operator · revision 2”, 8 generated objectives with evidence targets, sources column.
* `docs/cb011-shots/05-studio-pages.png`, `06-studio-export.png`, `07-studio-reflection.png`.
* `docs/REVIEW_CB011-ui-trace.json` — the text trace the capture script recorded per step.
* `scripts/cb011-studio-shots.mjs` — the driver (CDP, real clicks, no injected state).
* `scripts/cb011-parent-probe.py` — the same sequence at the wire level, printing every refusal:

```
parent.brief.create  → course_id, enrollment_id, job_id, state=queued
jobs.get (plan)      → queued → running → completed  (message: plan authored (needs_review))
course.outline       → plan v1 draft
parent.plan.edit     → ok (objective retitled)         [fenced on expected_plan_hash + revision]
plan.approve         → approved
jobs.create(lessons) → queued → running → interrupted_requires_retry  ← stops here
parent.blueprint.read→ plan v2 approved, content_hash, approval.state=none,
                       export={ready:false, blocked_reason:"no_generated_content"}, all tabs empty
```

`docs/REVIEW_CB011-flow-trace.json` holds the request/response of every call above.

Gates: `node --check desktop/plugin.js` OK; `tests.test_desktop_contracts` 6/6;
`hermes plugins doctor` `OK: 1 tool(s), 3 hook(s)`; `hermes plugins validate` passed.

## Backend defects found (and what I changed vs what still blocks)

Three defects were **fixed** because the card cannot advance without them; two are in Cinder’s files
and are wiring/caching scope only, commented as cross-owner edits:

1. `coursebook/executor.py` — the job tick never started in a real agent process. `ctx.spawn_task`
   needs a running asyncio loop, but `register(ctx)` is called synchronously, so the plugin raised
   `no running event loop`, `plugins doctor` reported `registrations: 0`, and every `plan` job sat
   `queued` forever. Now: `spawn_task` when a loop is running, otherwise a daemon thread with its own
   loop calling the same bounded `_tick_loop`. **Cinder: please ratify or replace with a host-owned
   startup seam.**
2. `coursebook/generation.py` — the plan-document reuse cache was looked up by request fingerprint
   *before* the course was resolved, so a duplicate brief returned the first course’s plan, wrote
   nothing for the new course, and reported success. Now scoped to `course_id + fingerprint`; a
   retried job for the same course is still idempotent and free.
3. **Not fixed (reported):** `course.outline.plan.plan_hash` is **not** the fence value.
   `plan.approve` / `parent.plan.edit` compare `parent_authoring.plan_hash` recomputed from the plan
   rows; the outline returns the digest generation stored with the plan document. Every approval sent
   from that read is refused with `field: expected_plan_hash, current_plan_hash: …`.
   `parent.blueprint.read.plan.plan_hash` *is* the fence value, so the studio (and the probe) send
   that. Atlas: the `outline_plan` description claims otherwise — one of the two should change.

**Still blocking full certification (Cinder / Atlas):**

* The `lessons` stage ends `interrupted_requires_retry` in this environment: the job is leased, the
  provider calls run per section, and the lease is not renewed across a multi-section run, so the tick
  reclaims it mid-flight. Re-queuing reuses the checkpoint, but I could not get a complete lesson set,
  so `parent.final.approve` and `parent.export` could not be exercised with real content.
* Atlas’s export-panel decision (`docs/DECISION-AUTHORED-PACK-POLICY.md`) records that `parent.export`
  is dead for real generated content on `master` @ `adedf47` (multi-objective sections,
  `accepted_alternatives`, rubric minima) pending t_66b486a5. The panel renders those refusals
  (`export_not_exportable` + `details.problems`) rather than retrying.

## Acceptance status

| Criterion | State |
|---|---|
| Brief with age/level/setting/materials/exclusions/egress disclosure | **Verified live** |
| Draft / review / plan approval / generation / final approval / export / reflection states | Draft, review, plan approval, generation queued/running verified live; **final approval + export not reachable** because the lesson stage never completed |
| Source/activity editing with approval invalidation and partial regeneration | Editing + fence verified live; invalidation banner is wired to the approval row (not yet observed because no approval existed); partial-regeneration copy/behaviour is the kernel’s reuse path |
| Parent guide / learner pages / answers / narration tabs; low-ink printable export | Tabs render live (empty until content); PDF export **not produced** |
| No answer key on learner page | Enforced by role separation in the UI copy and by `packs.LEARNER_FACING_ROLES` + the v6 answer-text exception; verified as a structural property, not yet on generated content |
| Editing after approval blocks export until reapproval | Wired (`blocked_reason` + banner); needs a complete lesson set to demonstrate |
| Final approval distinct from plan approval | **Verified live**: two badges and two actions, revision 2 with plan approved and lesson set not approved |
| No child chat/persona; parent is the operator | **Verified**: no chat surface in the studio, copy on the brief and every header |
| Review packet: screenshots, exported PDF, tests, privacy note | Shots + trace + tests present; **no exported PDF**; privacy/egress note below |

## Privacy / egress note

* The brief is sent to the model provider configured for the Hermes profile that serves the backend;
  Coursebook stores no provider key. `egress_acknowledged` is `const: true` in the contract, so an
  unacknowledged paste cannot create a course. `redaction_requested` is recorded and surfaced.
* `parent.blueprint.read` serves the answer guide **by `course_id` only** — no enrollment, binding or
  session — so a learner surface cannot reach it; exported packs carry `answer_guide` outside
  `LEARNER_FACING_ROLES`, so it never lands in a learner page.
* Reflections are parent-reported, carry no evidence class, and are in `packs.PRIVATE_FIELDS`, so
  neither the table nor a rendered reflection can enter an export. The export panel states that
  attempts, notebook notes, reflections, transcripts and provider settings are never included.
