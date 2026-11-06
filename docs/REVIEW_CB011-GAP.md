# CB-011 Parent Studio — blocked on missing backend surface (evidence, not a claim)

Status: **BLOCKED / no UI shipped.** Owner: Vellum (Desktop UI). Base: `master` @ `ce7aded`.
Worktree: `wt/cb-011-vellum`.

This document records what I verified before writing any Desktop code. The Parent Studio card is
"end-to-end", and three of its four acceptance criteria depend on backend state that the frozen
`cb.rpc` v5 surface cannot produce and cannot persist. Building the screens anyway would produce a
static mock, which is exactly what this project's rules forbid.

## 1. What the card needs vs. what exists

`UX_SPEC.md` §10 (lines 424–453) requires: a parent brief; a draft → research/review → **plan
approval** → generation → **final approval** → export → reflection flow; editing with approval
invalidation; tabs for **parent guide / learner pages / answers / narration / sources**; a low-ink
printable export.

`docs/CONTRACTS.md:625` maps that screen to `course.create`, `jobs.create` (kind `research`/`plan`),
`jobs.get`, `plan.approve`, `pack.preview`, `pack.inspect`, `pack.export`, `artifact.get`. The mapping
is the intent; the following four things that mapping assumes do not exist.

### 1.1 Nothing executes plan/lesson jobs

`jobs.create` inserts a durable `queued` row (`coursebook/domain.py:1291`). The only driver of a
queued job is `coursebook/job_service.py:565 run_pending(resolvers)`, and the only callers of
`run_plan_job` / `run_lesson_job` are tests:

```
$ grep -rn "run_plan_job\|run_lesson_job\|run_pending" . --include=*.py --include=*.js --include=*.mjs \
    | grep -v "^./tests/"
./coursebook/generation.py:80:    "run_plan_job",
./coursebook/generation.py:81:    "run_lesson_job",
./coursebook/generation.py:1807:def run_plan_job(
./coursebook/generation.py:2233:def run_lesson_job(
./coursebook/job_service.py:565:def run_pending(
```

There is no resolver registration and no scheduler tick anywhere in `__init__.py`, `coursebook/hooks.py`
or `dashboard/plugin_api.py`. A `jobs.create(kind="plan")` from the Desktop stays `queued` forever, and
`jobs.cancel` is the only transition the user can reach. The existing shell already states this in
`CreateCourseFlow` ("objective generation is not wired in this build"). Therefore the card's
**draft / review / generation** states have no data source.

Consequence: **deliverable 2** (draft/review/plan approval/generation states) and the "plan generating"
row of the UX state matrix cannot be exercised.

### 1.2 Draft-plan editing has no RPC

`coursebook/domain.py:2601` (`record_objective`) and `:2645` (`record_observation`) exist precisely for
Parent Studio, but no handler, tool or host route calls them:

```
$ grep -rn "record_objective\|record_observation" coursebook/*.py dashboard/*.py | grep -v "def record"
(no output)
```

`plan.replan` (`domain.py:611`) only works *from an approved plan* and only expresses
keep/retitle/add/defer/remove. "Parent can edit all meaningful fields before approval" (UX §10) has no
command. Therefore **deliverable 3** (source/activity editing with approval invalidation and partial
regeneration) has no persistence path.

### 1.3 "Final approval" is not a state anywhere

`plans.state` is `draft | approved | superseded` (`contracts/db.v2.json:130-137`). There is no
lessons-level approval, no `parent_approvals` row, and no RPC verb. Acceptance "final approval is
distinct from plan approval" is unimplementable without a schema + contract change.

Consequence: **acceptance criteria 2 and 3** ("editing after approval blocks export until reapproval",
"final approval is distinct from plan approval") cannot be demonstrated.

### 1.4 An authored course cannot be exported, and no method produces a PDF

`pack.export` rebuilds a pack **only** for a pack-backed course:

```
$ sed -n '770,782p' coursebook/pack_flow.py
        if course is None or course["pack_id"] is None:
            raise RpcError.of(
                "POLICY_VIOLATION",
                "this course was not imported from a pack; package it from an authored export instead.",
                reason="course_not_pack_backed",
            )
```

No "authored export" exists. `coursebook/artifacts.py:365 make_pdf()` is a media-artifact helper with
no RPC caller. So a generated parent lesson cannot become a pack, a file list, or a PDF, and the
acceptance artifact "exported PDF" has no producer.

### 1.5 Blueprint tabs cannot read their own files

A parent blueprint pack *does* declare the right roles (`contracts/pack-manifest.v1.json:200`:
`parent_guide`, `answer_guide`, `learner_page`, `narration`). But:

* `pack.inspect` (`coursebook/pack_flow.py:981`) returns `pack`, `manifest`, `integrity`, `trust` —
  manifest **metadata** only, no file text or bytes;
* `lesson.page` for an imported parent pack materialises only each objective's section file plus the
  check prompt (`pack_flow.py:453 _write_lesson_page`); `parent-guide.md` and `answer-guide.md` are
  attached to no objective and are never served;
* there is no `pack.file.read` or role-scoped content method.

So **Parent guide / Answers / Audio & visuals** tabs have no data for either an authored or an
imported parent course. The only tab that can render is Learner pages, and only for imported sections.

### 1.6 Reflection and duplicate-brief persistence

There is no reflection type: `notebook_entries.kind` is
`lesson_segment | artifact | source_passage | personal_note | quiz_moment`
(`contracts/db.v2.json:905-916`). A parent reflection can be stored honestly as a `personal_note` with
tags, but "reflection proposals for next draft" needs the reflection to feed the next brief — a read
path and a brief write path that do not exist. "Duplicate brief" needs the brief itself to be readable;
the brief lives in `jobs.brief_json` / `gen_plan_documents.brief_json` and is not exposed by `jobs.get`
(which returns `job`, a view without `brief`).

## 2. Acceptance matrix under the current base

| Acceptance | Status | Why |
|---|---|---|
| no answer key on learner page | **PASSABLE** | `learner_page()` re-checks stored pages against checks (`generation.py:2156`); for parent blueprints the answer guide is a separate file role. This one is UI-provable on an imported blueprint. |
| editing after approval blocks export until reapproval | **BLOCKED** | no draft-edit command (§1.2); no authored export (§1.4) to gate |
| final approval distinct from plan approval | **BLOCKED** | no state or verb (§1.3) |
| no child chat/persona; parent is the operator | **PASSABLE** | pure UI: no chat surface in the studio, recipe guard already exists in the shell |

## 3. Why I did not ship partial screens

A brief form and a list of `queued` jobs can be drawn today, but every screen after the brief reads
state that no method can produce. The project standard is "implement, not merely describe, these
states" (`UX_SPEC.md` §13) and "never use a fake data fixture to claim an integration works". Shipping
screens that never advance past `queued` would misrepresent the product in exactly the demo flow
(`docs/DEMO.md` 47–62s) this card feeds.

## 4. Minimal surface needed (proposal for Atlas, contract owner)

Nothing here is implemented; this is the request, so a retry is mechanical.

1. **`parent.brief.create`** — create course (`recipe: parent`) + enrollment + queued `plan` job in one
   fenced call, carrying the full UX §10 brief: goal, age band, reading level, duration, setting,
   materials, exclusions, supervision constraints, desired pages/visuals/narration, egress/redaction
   acknowledgement. Returns `{course_id, enrollment_id, job_id}`. A read form
   `parent.brief.get({course_id})` returns the same brief so "duplicate brief" is a real copy.
2. **`parent.plan.edit`** — draft-only field edits (objective title/criteria, section text, activity
   instructions, exclusions, parent block), reusing `record_objective`; bump `plans.version` and
   return the new `plan_hash` + `changes_need_review: true`.
3. **`parent.final.approve`** — approve the exact generated content set by hash; record a distinct
   `final_approval` (new column/row + vocabulary value). `plan.approve` stays the plan-level gate.
   Any edit after either approval invalidates both (`export_blocked_reason: "changes_need_review"`).
4. **`parent.generation.start`** (or a `lesson` job kind) + **an agent-side executor** that resolves
   `plan`/`lesson` job kinds to `generation.run_plan_job` / `run_lesson_job` through `job_service`
   leases. This is the only genuinely missing runtime piece; the pipeline itself is complete.
5. **`parent.export`** — build a parent pack from an authored course using
   `packs.export_allowlist`, with `parent_guide` / `learner_page` / `answer_guide` / `narration` roles,
   plus a low-ink selectable-text PDF document artifact (reuse `artifacts.make_pdf`) and an exact file
   list. Must refuse when either approval is stale.
6. **`pack.file.read({pack_id, pack_version, path})`** (or a role-scoped tab payload in
   `lesson.page`) — serve declared file **text** under the already-validated manifest, so the five
   tabs render real content without a filesystem path crossing the wire.
7. **`parent.reflection.record`** — parent-reported easy/about-right/too-hard + revisit note, stored
   outside the exported pack (`packs.PRIVATE_FIELDS` already excludes `reflection`), readable to seed
   the next brief.

Items 1–4 are Atlas (contract) + Cinder (executor/export) work. Items 5–7 are Atlas + Lattice/Cinder.
Items 2–5 are Desktop-consumable only after the contract lands.

## 5. Re-verification

```
cd /home/deseretsaint/Projects/hermes-classroom/.worktrees/t_4255b696
grep -o '"[a-z_]*\.[a-z_]*"' contracts/rpc.v5.json | sort -u      # no parent.* verb
grep -rn "run_pending\|run_plan_job\|run_lesson_job" --include=*.py . | grep -v tests/  # declaration only
sed -n '770,782p' coursebook/pack_flow.py                          # course_not_pack_backed
sed -n '905,916p' contracts/db.v2.json                             # no reflection kind
node --check desktop/plugin.js && hermes plugins validate .        # base is green
```

## 6. Not done, stated plainly

No Desktop file was changed by this run. No screenshot, PDF, or test is claimed. The blockers and the
proposed surface are filed as board cards for Atlas and Cinder, and this card is blocked rather than
completed so the release dependency is visible on the board.
