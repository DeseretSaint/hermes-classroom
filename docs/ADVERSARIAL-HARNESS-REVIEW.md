# Coursebook — adversarial harness review

Date: 2026-11-07 (checkpoint)
Reviewed tree: local `master` at `200e6d3` (M4 series merged; 1040 tests green)
Scope: the whole plugin as a course-generation harness, not the Japanese fixture and not the
polish of any one lesson.

## Verdict

**Coursebook is not yet a general harness.** It contains a strong authoring **kernel** and a real
capability-policy design, but the product path a normal learner actually reaches is a shell around
a **prepared pack**: the create flow writes an empty draft plan and explicitly says generation is
not wired. The generator is also structurally shaped for a small demo course (4–8 objectives,
2–8 sections, one section per objective), and the inputs that make the capability policy choose
images, audio and rubrics are not reachable from the product surface.

That is a failure against the stated mission: a user who launches the plugin and prompts an
arbitrary goal cannot yet get a comparable course out of it.

This is not a claim that the code is poor. The kernel, contracts, validation pass and pack
security are real. It is a claim that the **harness loop is incomplete and the evidence is
fixture-shaped**.

## Evidence baseline

- `python3 -m unittest discover -s tests -t .` — **1040 tests, OK (101.1 s)** on this tree.
- `node --check desktop/plugin.js` — OK.
- The green tests do not exercise the gaps below; several of them encode inputs that the frozen
  contract cannot carry. See §4.

## P0 — the loop does not exist from the product surface

### P0-1. The learner create flow never starts generation

`desktop/plugin.js:3404 CreateCourseFlow` calls exactly two mutations:

1. `course.create`
2. `enrollment.create`

It never calls `jobs.create`. After creating the course it tells the user:

> "The plan is a draft: objective generation is not wired in this build, so no lesson can start
> yet. Nothing was generated and no model was called."
> — `desktop/plugin.js:3474`

and

> "Nothing is generated until you approve a plan, and plan generation is not part of this build."
> — `desktop/plugin.js:3627`

`course.create` (`coursebook/domain.py:518`) inserts a `plans` row with `state='draft'` and no
objectives. There is no learner-side `jobs.create` anywhere in `desktop/plugin.js`; the only
`jobs.create` uses are in Parent Studio (`StudioBriefForm` / `StudioReview`). The job executor and
the plan/lesson pipelines exist (`coursebook/executor.py`, `coursebook/generation.py`), but the
normal learner cannot reach them.

Consequence: **goal → research → plan → approval → lesson → check → adaptation is not a product
flow.** It is a backend capability with a Parent-Studio-only door.

### P0-2. The plan schema hard-caps the course at eight sections and forces every recipe to four objectives

- `PLAN_SCHEMA` objectives: `minItems: 4`, `maxItems: 8` — `coursebook/generation.py:645`.
- Sections: `minItems: 2`, `maxItems: 8` — `:646`.
- Prompt: "Produce 4 to 8 objectives" — `:1148`.
- `enforce_plan_rules` requires **exactly one section per objective** — `:1308-1322`.

This applies to `one_off` as well: a one-off "replace this hose" brief is forced into a four-to-
eight-objective course. The bundled `tests/fixtures/generation/plan_one_off.json` indeed has four
objectives and four sections (brake pad work). A full course cannot exceed eight sections even
though `time_estimate.weeks` permits 104 weeks. The product promise includes long-term graded
courses; the document model cannot express one.

There is no `scope` field anywhere in the plan contract (single brief / short course / full course)
and no batching/continuation mechanism for a course longer than eight sections.

### P0-3. The capability policy's inputs are unreachable, and locale is mistaken for subject

The policy depends on `subject_domain`, `level` and `lesson_intent`. In the normal path:

- `course.create` dials are frozen to `pace`, `depth`, `assessment`, `autonomy`
  (`contracts/rpc.v9.json:532-561`, `additionalProperties: false`).
- `level` and `subject_domain` are **not in the contract** and not collected by
  `CreateCourseFlow`.
- `locale` exists at the top level of `course.create` but `CreateCourseFlow` never sends it.
- `plan`/`section` schemas have `additionalProperties: false` and no `subject_domain` field, so a
  model-authored plan cannot supply one either.

The policy's fallback then does this (`coursebook/policy.py:333`):

```
_normalise_domain(None, locale) -> "language" if locale else "general"
```

Probe on this tree:

```
locale=None  -> subject_domain=general   image=required schematic  audio=none
locale=es-ES -> subject_domain=language  image=none               audio=none
```

A Spanish-language technical procedure ("replace the brake pads and torque the caliper") is
therefore classified as a language lesson and **loses the deterministic schematic**. A Japanese
math lesson would be classified as language too, bypassing the symbolic-domain protection. The
policy is only correct when a caller hand-supplies `subject_domain`, which the product cannot do.

The same gap makes the L0 language scaffold unreachable: `_scaffold_policy`
(`coursebook/generation.py:1255`) checks `dials.level`, but the contract rejects `level`. The
Japanese L0 fixture is an internal test input, not a product path.

### P0-4. Deep research is a no-op and the budget is demo-sized

`ResearchBudget` defaults to 4 queries, 5 results/query, 6 pages, 6 sources, 6000 chars/page
(`coursebook/research.py:91`). `derive_queries` recognizes only `depth in {"overview","thorough"}`
(`:283-305`), while the UI/contract uses `survey`, `working`, `deep`
(`desktop/plugin.js:86-93`, `contracts/rpc.v9.json:541-551`).

Measured on this tree:

```
depth=survey   -> 2 queries
depth=working  -> 2 queries
depth=deep     -> 2 queries
depth=thorough -> 4 queries  (not accepted by the contract)
```

So the depth dial is effectively **not connected to research**, and even the maximum reachable
path is two search queries and at most six pages. That is not "deep and thorough" research for a
full course; it is a sample pass. There is no source-authority ranking, no primary-source
requirement, no per-objective search, and no expansion as the plan grows.

### P0-5. A normal course cannot export itself

`pack.export` refuses a course with no `pack_id`:

> "this course was not imported from a pack; package it from an authored export instead."
> — `coursebook/pack_flow.py:790-793`, reason `course_not_pack_backed`

The only authored export is `parent.export` (`pack_flow.py:1001`), which requires Parent Studio's
`final_approvals` row and is exposed only in the Parent Studio surface. A normal `course.create`
course — the one the learner is supposed to build from a goal — has no export action and no
general authored-export command in the contract. "Packages the result for reuse" is therefore not
true for the main learner path.

### P0-6. A technical procedure lesson cannot carry the procedure lens

The renderer, document validator and tests exist, but no generation path authors a procedure:

- `LESSON_SCHEMA` (`coursebook/generation.py:715-980`) has no `procedure` property and is
  `additionalProperties: false`.
- `_build_learner_page` (`:3022-3094`) copies an allowlist that does not include `procedure`.
- The product docs admit it: `docs/PRODUCT-LINE-RELEASE-NOTES.md` M4 — "No lesson prompt authors a
  `procedure` header yet, so the lens is validator-and-renderer proof against a contract-valid
  fixture." `README.md` says the same.

A goal such as "replace a head gasket" or "hook up a washer" can get a generic text lesson and
possibly a schematic media spec, but cannot get the typed header, ordered step references, hazard
callout or procedure source card. The one UI lens built specifically for technical work is
unreachable from a model-generated course.

### P0-7. No live arbitrary-topic generation exists

The only demonstrated "course" is a **prepared Japanese pack**:
`bundled/packs/japanese-affection-context-l0`, imported by `scripts/seed-demo-course.py`.
`docs/DEMO.md` says the script "proves a governed loop on one prepared pack" and "does not prove
behavior with other packs". The demo is not recordable: the isolated backend has no inference
provider, the default-profile gateway still has not loaded the plugin Python half
(`t_6a32ffe9`), and the M1–M4 evidence is fixture, static render or precomputed media.

Therefore there is no empirical evidence that a prompt for an arbitrary subject produces a
comparable-quality course. The green tests prove the kernel's rules, not the harness's output.

## P1 — real but less immediately fatal

### P1-1. The parent brief is stored but mostly ignored by the planner

`parent.brief.create` stores the full typed brief (`coursebook/domain.py:3060-3110`) but sets
`"dials": {}` and passes the brief to `job_service.create("plan", stored_brief)`. `run_plan_job`
(`coursebook/generation.py:2677-2710`) extracts only `goal`, `recipe`, `dials`, `locale`.
`build_plan_request` (`:1780-1810`) sends only those fields plus research.

So `age_band`, `reading_level`, `duration_minutes`, `setting`, `materials`, `exclusions`,
`supervision`, `desired_pages`, `desired_visuals` and `narration` never reach the model. Parent
Studio's form promises inputs that the plan never sees.

### P1-2. The planner does not plan media; lesson policy guesses from prose

`PLAN_SCHEMA` has no media/visual/audio field. `_plan_instructions` explicitly says "media is not
the default and this plan does not assign any." The lesson policy is then computed from
`section.lesson_intent` (`coursebook/generation.py:1080-1115`), a free-text sentence the planner is
not required to write with a named visual or oral construct.

The six-row matrix in `tests/test_policy_integration.py` works because each row hand-authors an
intent such as "Follow the torque sequence", "say it aloud" or "analyse a poster". The generator
has no obligation to produce those constructs. A generated course can therefore have no
image or audio even when the subject needs them, and no validator can call that a defect because
the plan never declared the need.

### P1-3. Check-plan count and independent-evidence flag are decorative

`CHECK_PLAN_SCHEMA` allows `count` 1–4 and `independent_evidence` (`generation.py:562-568`), but
`enforce_plan_rules` only checks that every objective appears in the check plan. The lesson
pipeline writes exactly one check per section (`_author_section`, `:3265-3335`). `count` and
`independent_evidence` are never consumed. A plan that promises three checks per objective
silently produces one.

### P1-4. The authoring schemas are Japanese-shaped

`LESSON_SCHEMA.check.scaffolds` is required for every lesson and has exactly
`romaji`, `furigana`, `english_meaning` (`generation.py:846-860`). `_scaffold_policy` only enables
them for `ja` at L0/L1/beginner (`:1255-1268`). Other languages have no equivalent level/scaffold
path, and non-language lessons must still carry a Japanese-language scaffold object. This is a
clear fixture-shaped schema.

### P1-5. Assessment breadth is narrow for "anything"

Check kinds are only `quiz | verification | observation`; reference kinds are `exact | numeric |
selection | rubric_only`; rubric profiles are six fixed labels. There is no code execution, no
project/artifact check, no oral interview, no performance recording, and no experimental or
lab-report construct. Open responses can be rubric-scored, but the harness cannot collect or
verify a program, a performance or a physical artifact. That is a product limit, not a bug, but it
contradicts "whatever may be thrown at it" if taken literally.

### P1-6. The six-profile rubric registry is static

The profiles (`concept_explanation`, `procedural`, `language_production`, `recall_accuracy`,
`source_analysis`, `observation`) are well-designed and validated, but there is no mechanism for
the harness to synthesize and validate a new construct profile for a new subject. A discipline
that does not fit one of the six is forced into the nearest angle. A general harness should be able
to propose a rubric, validate its observability, and gate it — not only choose from a fixed list.

## P2 — evidence and test-design risks

### P2-1. The test matrix proves policy, not generation

`tests/test_policy_integration.py` is a six-row matrix (head gasket, Japanese, algebra, history,
wiring, parent reading) with hand-written intents and `dials={"subject_domain": ...}`. It is useful
as a policy test, but it does not show that `run_plan_job` produces those intents from a goal. The
only plan fixtures are `plan_one_off`, `plan_parent`, `plan_ja`; the default goal in
`tests/test_generation.py` is "Order coffee in Japanese".

There is no golden test that:
- takes a free-form non-Japanese goal,
- runs plan generation (real or recorded model),
- approves it,
- generates a lesson,
- asserts the procedure/media/rubric decisions,
- exports a pack.

That is the missing acceptance test for the mission.

### P2-2. The depth dial and locale are not tested through the product surface

The tests call `derive_queries` with `overview`/`thorough` directly and use a `locale` passed
internally. The product's actual `survey/working/deep` and missing locale are not covered. A
contract-level test should create a course through `course.create` with the exact UI payload and
assert the resulting plan's research and policy inputs.

### P2-3. The procedure and media evidence is static/fixture

Known from the project's own docs, but relevant to the review:
- M1 narrow-width host patch not merged/installed (`wt/host-narrow-rail`, operator-owned).
- M2 Field Quest has no live frame; only a live-availability capture.
- M3 Pronunciation Studio has no live walkthrough; no existing section has a narration child.
- M4 procedure lens is fixture-only; the visual audit is a static render in a stubbed host.

These do not prove a generated lesson renders or that media works in the ordinary learner flow.

## What is genuinely strong

These are not consolation prizes; they are the reason this can become a real harness:

- The **kernel** is serious: strict contracts, SQLite authority, revision fences, idempotency,
  fail-closed grading, pre-turn gate, answer separation, evidence classes and durable transitions.
- **Generation ≠ validation** is implemented structurally, not by convention:
  `assert_separate_pass` rejects a validator that reuses the generator prompt/schema/version.
- The **capability policy** itself is a good idea: a typed, deterministic decision with explicit
  "no media" defaults, symbolic-domain protection and media-role honesty (an illustration is
  never a procedure authority).
- The **rubric registry** encodes real construct differences and refuses mental-state criteria.
- **Pack security** is allowlist-first; private fields are excluded by construction; trust labels
  are separate; export is rebuilt, not copied.
- **Media and local pronunciation** are real seams: host-owned image/TTS dispatch, ffmpeg→PCM
  local Whisper, `model_assessed` evidence, practice-only when unavailable.
- The **presentation work** (Ink & Field Notes, Textbook/Guided/Field Quest, procedure renderer)
  is a real foundation once the authoring path reaches it.

## What must be true before this is a harness

1. **Wire the learner path**: `CreateCourseFlow` → `course.create` + `enrollment.create` +
   `jobs.create(kind=plan)`; poll the job; show the honest time range; approve the draft plan.
   Without this, nothing else matters.
2. **Make the planner inputs first-class**: `locale`, `level`, `subject_domain` (or a brief
   classifier), and `scope` must be contract fields the UI can send, not test-only dials.
3. **Replace the demo-shaped bounds**: one-off = one section; full course = a scoped, batched plan
   with a real continuation path; stop forcing one section per objective; let a course have more
   than eight lessons.
4. **Make media a plan-time requirement**: the plan must declare per-lesson visual/audio needs
   (or a construct) and the policy must consume it; do not rely on a model's incidental prose in
   `lesson_intent`.
5. **Add a procedure authoring schema** and a generation prompt that can emit it. Until then,
   remove the unreachable procedure lens or label it explicitly as fixture-only.
6. **Pass the parent brief through** to the plan request, or remove the fields the planner does
   not honor.
7. **Add the end-to-end arbitrary-topic test**: goal → plan → approve → lessons → check → export,
   with an explicit non-Japanese subject and a fixture that is not hand-authored from the same
   template. A recorded real run is preferable; if provider spend is not approved, a recorded
   model transcript is the minimum.
8. **Fix research depth**: align the dial values, make `deep` actually deep, and size the budget
   to the course scope. Six pages is a demo budget.

## Decision point

Do **not** treat the Japanese pack, the M4 frames or the green suite as evidence that the harness
is ready. The next work should be a **P0 harness slice**:

- learner create → plan job → plan approval,
- contract inputs for locale/level/subject/scope,
- one arbitrary subject generated end to end,
- one real procedure or language lesson produced from that job (not a fixture),
- one authored export of that course.

Only after that slice is live should the team spend more time on demo polish.
