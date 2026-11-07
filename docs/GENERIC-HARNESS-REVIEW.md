# Generic harness review — can Coursebook teach an arbitrary topic?

Date: 2026-11-07. Baseline: `origin/master` at `6779030` (H-02 learner create flow, H-03
blueprint design and H-13 policy threading merged; H-01/H-12/H-14 already merged). This review is
about **product behavior**, not the size of the vocabulary list. The question is whether a person
can type a topic that is not Japanese, choose a one-off lesson or a whole course, and receive a
usable course whose checks actually grade.

## Verdict

**Partially generic. Do not claim the harness is fully generic yet.** The contract now carries
arbitrary goals, scope, level and subject domain; the learner create flow sends them and starts a
real plan job; the policy can distinguish a Spanish brake-pad procedure from a Japanese math
lesson. Those are real advances.

Three structural limits remain on current master:

1. **The plan is still demo-shaped.** `PLAN_SCHEMA` requires 4–8 objectives and 2–8 sections, and
   the plan prompt still says "Produce 4 to 8 objectives." A one-off task cannot be one
   objective; a full course cannot exceed eight. H-03's blueprint design and H-21's implementation
   are the fix; H-21 is not merged.
2. **Generated checks are ungradable.** Generated checks store `reference_answer`,
   `accepted_answers` and `accepted_alternatives` without a reference `kind`, so the grader routes
   every generated check to the unconfigured open lane. A correct generated answer is saved and
   returned as `needs_retry`; it cannot complete the objective. This is the H-16 B-1 defect; it
   has no owning board card until H-23 is created by this review.
3. **The arbitrary-topic proof has not been run.** H-09 is still `todo`; the only complete course
   evidence is the prepared Japanese pack, which proves the kernel and demo, not generation. No
   non-Japanese one-off, short or full course has been generated through the product path and
   measured.

Student mode and a second import path also do not exist. The `companion` recipe and a research
query that mentions "syllabus learning objectives" are the only related code. There is no
syllabus upload, parser, mapping, alignment review or companion-course flow. That is a new product
area, not a small variation on pack import.

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
| one-off | "Walk me through replacing the inner tube on my road bike; I want to do it myself today." | exactly one objective and one authored lesson; verification checklist, no quiz/homework; plan approval; a launchable lesson; no 4-objective padding | **FAIL** — schema requires at least 4 objectives and 2 sections; the schema validator rejects a one-objective plan |
| short | "Six weeks of practical Spanish for a restaurant shift: ordering, allergies, complaints, closing." | 3–6 objectives, 1–3 units, 3–8 lessons; scope-appropriate research; checks grade; a path through the six weeks | **PARTIAL / UNPROVEN** — H-02 can carry `scope=short`, but the old caps and the ungraded generated-check lane remain; H-21 is not merged |
| full | "A first-year college statistics course: describing data, probability, sampling, inference; twelve weeks." | 12–40 objectives, 2–12 units, prerequisite edges, unit-scoped authoring, resume/cancel at unit boundaries, honest time/cost | **NOT POSSIBLE** — `PLAN_SCHEMA` max 8 objectives/8 sections; H-03 design only; H-21 not merged |

A fourth shape is the user's new student mode: a **syllabus-backed companion course**. It is not
the same as a full course because the external syllabus is the scope authority and Coursebook
aligns to it. That path has no card yet; H-25/H-26/H-27 are created by this review.

## Evidence

### G-01 — The one-off shape is schema-rejected on current master

On `6779030`, the plan validator rejects a valid one-objective, one-section plan:

```
PLAN_SCHEMA one-objective errors: 2
- ['objectives'] [...] is too short
- ['sections'] [...] is too short
```

The schema has `minItems: 4` for `objectives` and `minItems: 2` for `sections`, with maxima 8 and
8 (`coursebook/generation.py:645-646`). The prompt still says "Produce 4 to 8 objectives"
(`generation.py:1234`). H-03 correctly calls this the demo-shaped planner; H-21 is the
implementation card. Until H-21 lands, a bicycle-tube brief cannot become the single lesson the
user asked for.

### G-02 — Generated checks are saved, not graded

Reproduction from the H-16 probes on current master:

```
generated reference: {"ok": true, "verdict": "needs_retry", "next_action": "retry_grading"}
closed control:      {"ok": true, "verdict": "pass", "next_action": "complete_objective"}
```

`_check_payloads` (`coursebook/generation.py:3518-3531`) writes no `reference.kind`. The grader
therefore cannot use the deterministic lane and the generated answer never advances. This is not a
UI issue and not a model-quality issue; it is a data-shape defect. It is the single most important
generic-harness defect after the plan cap, because it makes every generated course's checks
advisory. `docs/ASSESSMENT-BREADTH.md` B-1 records it; H-23 is the missing card.

### G-03 — Scope is real on the wire, but the plan shape is not

H-02 merged and H-13 merged. A learner can choose One lesson / Short course / Full course and the
value reaches the course row, the job brief, the plan prompt and the fingerprint. That is
necessary, not sufficient: the JSON Schema still caps the authored document, so `scope=single`
cannot produce a single-objective plan and `scope=full` cannot exceed eight. H-21 must replace the
schema with the v2 blueprint and remove the numeric caps before the three shapes are real.

### G-04 — Capability selection is better, but media and procedure are still incomplete

H-13 makes the policy read the declared level, subject domain and scope. H-05 (plan-time media
needs) and H-06 (procedure authoring) are still on the board. A technical topic can be described
and planned, but the lens that makes a head-gasket lesson a procedure — tools, hazards, ordered
steps, a deterministic schematic — is not yet a first-class authoring path. A generated
illustration is context, never a repair authority; that rule stays.

### G-05 — The only complete course is a prepared Japanese pack

`H-09` is the arbitrary-topic end-to-end proof. It is still `todo`, and the demo pack is not
evidence for generation. The board index already says this; the review repeats it because it is
the one claim most likely to be overstated in a demo. H-30 is an independent audit of H-09's
evidence, not a second generator.

### G-06 — The second import path and student mode do not exist

`pack.import` is the existing path for lessons someone else made. There is no syllabus path:
`research.py:298` appends "syllabus learning objectives" to a research query for the `companion`
recipe, but no file is uploaded, parsed or mapped. There is no `syllabus` table, no alignment
state, no student-facing "pair with my class" flow, and no contract method. This is not a gap in
the existing card bodies; it is new scope, and it needs a design card before code (H-25), a
backend slice (H-26), and a UI slice (H-27).

### G-07 — Rubric profiles are static

`coursebook/rubrics.py` owns six declarative profiles and validates them. That is a good
anti-generic-rubric design, but there is no mechanism to add or validate a new construct profile
without a code fork. H-24 is a decision card: either prove the six profiles cover the supported
constructs for 0.1.0 and record the refusal, or design the profile-creation gate. It is not an
excuse to generate a free-text rubric at runtime.

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

Until 1–3 are measured, "teaches anybody anything" is a design ambition, not a product claim. The
honest current sentence is: **Coursebook can plan and author a course for an arbitrary text-shaped
subject, but the plan is still small-course-shaped, generated checks are not yet graded, and only a
prepared Japanese pack has been run end to end.**

## Card mapping

| finding | card | owner | dependency |
|---|---|---|---|
| G-01 plan shape | H-03 design (merged) + H-21 implementation (running) | cinder | H-13 |
| G-02 ungraded generated checks | **H-23** | cinder | H-16 |
| G-03 scope vs shape | H-21 | cinder | H-13 |
| G-04 media/procedure | H-05/H-06 | cinder | H-03/H-04 |
| G-05 arbitrary-topic proof | H-09 + **H-30** audit | sentinel | H-02…H-08 |
| G-06 student mode / second import | **H-25** design, **H-26** backend, **H-27** UI | atlas/cinder/vellum | H-03/H-02 |
| G-07 rubric extensibility | **H-24** decision | atlas | H-16 |

## Limits

This review used deterministic probes and source inspection; it did not call a provider, did not
run a live Desktop session, and did not generate a course. The plan-shape probe is a JSON Schema
check on a fixture, not a claim about a model's output. The generated-check probe uses the real
kernel path with a fake provider, which is the correct evidence for a data-shape defect. No
publication, tag or catalog action was taken.
