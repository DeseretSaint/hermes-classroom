# Generic harness review — can Coursebook teach an arbitrary topic?

Date: 2026-11-07. Baseline: `origin/master` at `6779030` (H-02 learner create flow, H-03
blueprint design and H-13 policy threading merged; H-01/H-12/H-14 already merged). This review is
about **product behavior**, not the size of the vocabulary list. The question is whether a person
can type a topic that is not Japanese, choose a one-off lesson or a whole course, and receive a
usable course whose checks actually grade.

Status claims re-derived 2026-11-08 against `origin/master` `5aed108`; every finding and number
below is kept as measured on the reviewed tree.

## Verdict

**Partially generic. Do not claim the harness is fully generic yet.** The contract now carries
arbitrary goals, scope, level and subject domain; the learner create flow sends them and starts a
real plan job; the policy can distinguish a Spanish brake-pad procedure from a Japanese math
lesson. Those are real advances.

Three structural limits were measured on `master` at review time (`6779030`); the first two have
since been fixed on master and the third has been run:

1. **The plan was demo-shaped on the reviewed tree.** `PLAN_SCHEMA` required 4–8 objectives and
   2–8 sections, and the plan prompt still said "Produce 4 to 8 objectives." A one-off task could
   not be one objective; a full course could not exceed eight. H-03's blueprint design and H-21's
   implementation are the fix; H-21 completed 2026-11-07 and is merged on master at `f990cad`
   (`PLAN_SCHEMA` v2; `single` = 1 objective, `full` = 2–12 units / 12–40 objectives). The 4–8
   prompt band survives only for `blueprint=False` callers (`generation.py:2606-2608`).
2. **Generated checks were ungradable on the reviewed tree.** Generated checks stored
   `reference_answer`, `accepted_answers` and `accepted_alternatives` without a reference `kind`,
   so the grader routed every generated check to the unconfigured open lane. A correct generated
   answer was saved and returned as `needs_retry`; it could not complete the objective. This is the
   H-16 B-1 defect; its implementation card is B-1 `t_673155b0` (the card title still carries a
   stale "H-20" label), which completed 2026-11-07 and is merged at `4e709d3` (content `ce6c8c1`,
   `docs/GRADING-LANES.md`).
3. **The arbitrary-topic proof had not been run at review time.** H-09 `t_ebc196db` completed
   2026-11-07 (run 192, 02:04 MST) with three non-Japanese goals PASS on its own commit `111c7e9`,
   but that branch (`wt/harness-e2e-proof`) was never merged and H-30's audit measured it against a
   tree that does not ship. The proof that is in master is the H-40 re-run, current packet
   `audit/adversarial/harness-e2e/STATUS.md` (H-46b/H-49 line: overall PASS 3/3, packet FRESH)
   through `course.create` → plan job → kernel-digest approval → lessons job → `lesson.page` →
   `check.open` → `attempt.submit`, on recorded transcripts with zero provider calls. The prepared
   Japanese pack is still not evidence for generation; the non-Japanese runs are.

Student mode and a second import path did not exist on the reviewed tree. The `companion` recipe
and a research query that mentions "syllabus learning objectives" were the only related code: no
syllabus upload, parser, mapping, alignment review or companion-course flow. That was a new
product area, not a small variation on pack import, and it was carded as H-25/H-26/H-27: the design
merged at `3705a7a`, the intake backend (H-26a `t_faad26cf`) at `d0ca064` (`cb.rpc` v12 /
`cb.db` v8), the read projection (H-26b `t_855dbdf6`) at `21e62e5` and the UI (H-27 `t_71ea55ee`)
at `ca1ca4f`.

## What is genuinely generic now

- `cb.rpc` v10 accepts optional `level`, `subject_domain` and `scope` on `course.create` and
  `jobs.create`; unknown fields are rejected. The enum is `single | short | full`.
- H-02's `CreateCourseFlow` sends the goal, title, recipe, dials, level, subject domain, locale and
  scope to `course.create`, then creates the enrollment and one idempotent `jobs.create` plan job.
  It no longer stops at "generation is not wired in this build."
- H-13 threads the declared inputs into the plan prompt, research query derivation and the
  capability policy, and includes them in the request fingerprint. Its measured before/after:
  `es-MX` brake pads → `technical_procedure` with a required schematic; `ja-JP` maths → symbolic
  refusal rather than a language lesson.
- The capability policy is construct-driven, not topic-label-driven: it can refuse media when the
  lesson intent does not name a visual or spoken construct.
- The evidence vocabulary is honest about its ceiling: text/selection/checklist, plus practice-only
  pronunciation. Code, performance and submitted artifacts are frozen out of 0.1.0 with explicit
  gates (`docs/ASSESSMENT-BREADTH.md`).

## The acceptance matrix the harness must pass

These are the three shapes the user named: a one-off lesson, a short course, and a whole course.
Each has a non-Japanese subject so the prepared pack cannot stand in for the result.

| shape | prompt example | what must be true | current status |
|---|---|---|---|
| one-off | "Walk me through replacing the inner tube on my road bike; I want to do it myself today." | exactly one objective and one authored lesson; verification checklist, no quiz/homework; plan approval; a launchable lesson; no 4-objective padding | **FAIL at review baseline** — schema required at least 4 objectives and 2 sections; the schema validator rejected a one-objective plan (H-21 v2 now allows `single` = 1) |
| short | "Six weeks of practical Spanish for a restaurant shift: ordering, allergies, complaints, closing." | 3–6 objectives, 1–3 units, 3–8 lessons; scope-appropriate research; checks grade; a path through the six weeks | **PARTIAL / UNPROVEN at review baseline** — H-02 could carry `scope=short`, but the old caps and the ungraded generated-check lane remained; H-21 was not merged then (now `f990cad`) and B-1 was not merged then (now `4e709d3`; H-30b measures short = 2 units / 4 objectives / 4 exact-lane quizzes) |
| full | "A first-year college statistics course: describing data, probability, sampling, inference; twelve weeks." | 12–40 objectives, 2–12 units, prerequisite edges, unit-scoped authoring, resume/cancel at unit boundaries, honest time/cost | **NOT POSSIBLE at review baseline** — `PLAN_SCHEMA` max 8 objectives/8 sections then; H-03 design only; H-21 not merged then (now `f990cad`: 2–12 units, 12–40 objectives) |

A fourth shape is the user's new student mode: a **syllabus-backed companion course**. It is not
the same as a full course because the external syllabus is the scope authority and Coursebook
aligns to it. That path had no card until this review; H-25/H-26/H-27 are now the design, backend and
UI cards.

## Evidence

### G-01 — The one-off shape is schema-rejected on current master

On `6779030`, the plan validator rejects a valid one-objective, one-section plan:

```
PLAN_SCHEMA one-objective errors: 2
- ['objectives'] [...] is too short
- ['sections'] [...] is too short
```

The schema has `minItems: 4` for `objectives` and `minItems: 2` for `sections`, with maxima 8 and
8 (`coursebook/generation.py:671-672` on the reviewed tree). The prompt said "Produce 4 to 8
objectives" in the default branch (`generation.py:1312` then). H-03 correctly calls this the
demo-shaped planner; H-21 was the implementation card and is merged at `f990cad` (`PLAN_SCHEMA`
v2), so a bicycle-tube brief can now become the single lesson the user asked for on the v2 path.

### G-02 — Generated checks are saved, not graded

Reproduction from the H-16 probes on current master:

```
generated reference: {"ok": true, "verdict": "needs_retry", "next_action": "retry_grading"}
closed control:      {"ok": true, "verdict": "pass", "next_action": "complete_objective"}
```

`_check_payloads` (`coursebook/generation.py:3717-3735` then) wrote no `reference.kind`. The grader
therefore could not use the deterministic lane and the generated answer never advanced. This is not a
UI issue and not a model-quality issue; it is a data-shape defect. It is the single most important
generic-harness defect after the plan cap, because it made every generated course's checks
advisory. `docs/ASSESSMENT-BREADTH.md` B-1 records it; B-1 `t_673155b0` (the title carries a stale
"H-20" label) is the owning card, completed 2026-11-07 and merged at `4e709d3` (`ce6c8c1`).

### G-03 — Scope is real on the wire, but the plan shape is not

H-02 merged and H-13 merged. A learner can choose One lesson / Short course / Full course and the
value reaches the course row, the job brief, the plan prompt and the fingerprint. That is
necessary, not sufficient: the JSON Schema still caps the authored document, so `scope=single`
cannot produce a single-objective plan and `scope=full` cannot exceed eight. H-21 must replace the
schema with the v2 blueprint and remove the numeric caps before the three shapes are real.

### G-04 — Capability selection is better, but media and procedure are still incomplete

H-13 makes the policy read the declared level, subject domain and scope. At review time H-05
(`t_7baa29e2`, plan-time media needs) and H-06 (`t_7a320d2f`, procedure authoring) were still on
the board; both completed 2026-11-07, and H-06b `t_6cd9e57c` landed the procedure lens on the v11
line at `acb20f7`. On the reviewed tree a technical topic could be described and planned, but the
lens that makes a head-gasket lesson a procedure — tools, hazards, ordered steps, a deterministic
schematic — was not yet a first-class authoring path. A generated illustration is context, never a
repair authority; that rule stays.

### G-05 — The only complete course at review time was a prepared Japanese pack

`H-09` is the arbitrary-topic end-to-end proof. It is no longer `todo` (`t_ebc196db` completed
2026-11-07, run 192), but its own branch was never merged, so it is not shipped evidence either: see
the status line under item 3 above. The demo pack is still not evidence for generation; the review
repeats that because it is the one claim most likely to be overstated in a demo. H-30 is an
independent audit of H-09's evidence, not a second generator: it reproduced the packet 3/3 on
`111c7e9` but measured a tree that would not ship, and H-30b re-audited the merged blueprint-v2
line at `f990cad` with all three shapes PASS.

### G-06 — The second import path and student mode did not exist at review time

`pack.import` is the existing path for lessons someone else made. At review time there was no
syllabus path: `research.py:298` appended "syllabus learning objectives" to a research query for
the `companion` recipe, but no file was uploaded, parsed or mapped; there was no `syllabus` table,
no alignment state, no student-facing "pair with my class" flow, and no contract method. This was
not a gap in the existing card bodies; it was new scope, and it became H-25 `t_5535fc66` (design,
`3705a7a`), H-26a `t_faad26cf` (backend, `d0ca064`), H-26b `t_855dbdf6` and H-27 `t_71ea55ee`
(UI, `21e62e5` / `ca1ca4f`).

### G-07 — Rubric profiles are static

`coursebook/rubrics.py` owns six declarative profiles and validates them. That is a good
anti-generic-rubric design, but there is no mechanism to add or validate a new construct profile
without a code fork. H-24 was the decision card: either prove the six profiles cover the supported
constructs for 0.1.0 and record the refusal, or design the profile-creation gate; it completed
2026-11-07 and merged at `4f42c3c`. It is not an excuse to generate a free-text rubric at runtime.

## What would let us say "fully generic"

The claim is earned by evidence, not by adding a topic field. The minimum gate is:

1. **Three non-Japanese shapes** (one-off, short, full) generated through the product path, with
   live/fixture labels; no prepared pack may appear in the evidence.
2. **Every generated check that claims a closed reference grades deterministically** on the real
   `attempt.submit` path; open answers remain honestly "saved, not graded" and cannot advance.
3. **Plan shape matches intent**: one objective for one-off, 3–6 for short, 12–40 across 2–12 units
   for full; no silent padding; no truncation.
4. **A unit-scoped full course resumes and cancels at a boundary**, with a plan-sized cost ceiling
   and no lost completed units.
5. **A student syllabus** imports as untrusted input, parses with page/section anchors, maps weeks
   and assessments to units/objectives, and shows an alignment review before any course is
   created. The external syllabus remains the scope authority; Coursebook does not claim to be the
   official course.
6. **The demo is optional**: a clean profile, no bundled pack, a non-Japanese topic, and a complete
   first lesson prove the harness can start from zero.
7. **The language is generic**: default copy and examples are not Japanese-only, and locale is
   never used as a proxy for subject domain.

At review time, until 1–3 were measured, "teaches anybody anything" was a design ambition, not a
product claim. The honest review-time sentence was: **Coursebook can plan and author a course for
an arbitrary text-shaped subject, but the plan is still small-course-shaped, generated checks are
not yet graded, and only a prepared Japanese pack has been run end to end.** Re-derived on
2026-11-08 against master, the plan cap and the grading lane are fixed (`f990cad`, `4e709d3`) and
the three non-Japanese shapes run end to end (`audit/adversarial/harness-e2e/STATUS.md`, H-30b),
so 1–3 are now measured for text-shaped subjects; code, performance and artifact breadth stays
open (`docs/ASSESSMENT-BREADTH.md` P1-5).

## Card mapping

| finding | card | owner | dependency |
|---|---|---|---|
| G-01 plan shape | H-03 design (merged) + H-21 implementation (merged `f990cad`) | cinder | H-13 |
| G-02 ungraded generated checks | B-1 `t_673155b0` (merged `4e709d3`; title still says "H-20") | cinder | H-16 |
| G-03 scope vs shape | H-21 (merged `f990cad`) | cinder | H-13 |
| G-04 media/procedure | H-05/H-06 (both merged; H-06b `acb20f7`) | cinder | H-03/H-04 |
| G-05 arbitrary-topic proof | H-09 `t_ebc196db` (done, **unmerged**) + **H-30** audit (merged) + H-40/H-46b packet (merged) | sentinel | H-02…H-08 |
| G-06 student mode / second import | **H-25** design, **H-26** backend, **H-27** UI (all merged: `3705a7a`, `d0ca064`, `ca1ca4f`) | atlas/cinder/vellum | H-03/H-02 |
| G-07 rubric extensibility | **H-24** decision (merged `4f42c3c`) | atlas | H-16 |

## Limits

This review used deterministic probes and source inspection; it did not call a provider, did not
run a live Desktop session, and did not generate a course. The plan-shape probe is a JSON Schema
check on a fixture, not a claim about a model's output. The generated-check probe uses the real
kernel path with a fake provider, which is the correct evidence for a data-shape defect. No
publication, tag or catalog action was taken.
