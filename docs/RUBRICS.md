# Rubric angles

A rubric is a **scoring guide**, never a claim of mastery, a certificate or a fact about a
person. Nothing in this document or in `coursebook/rubrics.py` may be published as one.

Source of truth: `docs/VISUAL_MEDIA_PLAN.md` §4 ("Rubrics are selected by construct, not one
generic template"). This document records the registry and the validator that implement §4, the
rules the validator can prove, and the rules it explicitly cannot.

## Why a registry

One generic rubric for every subject measures the wrong thing. A head-gasket procedure is scored
on ordered steps, a safety stop condition and verification; a Japanese greeting on the target
phrase, pronunciation or fluency, meaning and register; a history source analysis on claim,
evidence, provenance and contradiction handling; a parent lesson on what the child actually did.
The profile is a **construct selector**, not a template: the aspects are fixed, the wording of
each criterion belongs to the check.

`coursebook/policy.py` (M1-P1) records the selected profile on every `LessonCapabilityPlan`
(`rubric_profile`). `coursebook/rubrics.py` (M1-P2) owns the criteria for those profiles and the
rules that judge a supplied rubric. Labels are copied verbatim from
`coursebook.policy.RUBRIC_PROFILE_CRITERIA`; `rubrics.registry_problems()` and
`tests/test_rubrics.py` fail if the copy drifts, so the plan, the prompt and the validator cannot
disagree about what an angle is.

## The six profiles

Each profile carries 3-6 criteria. Every criterion is an **observable aspect** with a one-sentence
note on what a scorer watches for; `rubrics.rubric_template(profile)` returns them as declarative
records for a prompt or a reviewer's checklist.

| Profile | Construct | Criteria | Evidence targets it may score |
| --- | --- | --- | --- |
| `concept_explanation` | The learner explains a concept in their own words. | accurate claim, mechanism, example, limits | comprehension, transfer |
| `procedural` | The learner performs or verifies a procedure. | ordered steps, safety stop condition, verification | procedure, transfer |
| `language_production` | The learner produces a spoken or written target phrase. | target phrase, pronunciation or fluency, meaning, register | production, transfer |
| `recall_accuracy` | The learner retrieves the answer without the key in view. | correct answer, accepted alternatives, no cue leakage | recall, discrimination |
| `source_analysis` | The learner analyses a source's claim, evidence and provenance. | claim, evidence, provenance, contradiction handling | comprehension, transfer |
| `observation` | A parent records what a child actually did, without grading the child. | observable behaviour, context, note, follow-up | recall, comprehension, production, discrimination, procedure, transfer |

`observation` is a mode (parent-led), not a subject construct, so it is allowed for any declared
evidence target. It still never scores a child: its criteria record behaviour, context, the limit
of what was seen, and one follow-up.

## Selecting a profile

The **declared evidence target is the authority**. The capability policy's construct is advisory:

* `resolve_profile(preferred, evidence_target)` keeps the advisory profile only when that profile
  can score the target; otherwise it uses the target's default
  (`rubrics.DEFAULT_PROFILE_BY_EVIDENCE_TARGET`).
* `profile_for_lesson(recipe=..., evidence_target=..., lesson_intent=..., locale=...)` asks
  `plan_lesson_capability` for the advisory construct and then resolves it.
* A pack manifest carries no authored construct, so the pack validator uses
  `rubrics.default_profile_for(check["evidence_target"])` directly. When the pack contract next
  versions, an authored `rubric_profile` field can replace that derivation; until then the
  evidence target is the only construct a pack declares.

Defaults by target: `recall`/`discrimination` → `recall_accuracy`; `comprehension`/`transfer` →
`concept_explanation`; `production` → `language_production`; `procedure` → `procedural`.

## The validator

`validate_rubric(profile, criteria, evidence_target)` returns every problem it finds; an empty
list means the rubric may be used. `assert_valid_rubric(...)` raises `RubricRejected` with all of
them. Criteria may be pack strings or generated `{criterion, weight, description}` records; the
description is the scored sentence.

Rules it **proves**:

1. the profile and the evidence target are in the plan's vocabulary;
2. the profile can score that evidence target — an off-profile construct is rejected
   (`recall_accuracy` cannot score a `production` target);
3. there are at least 3 and at most 6 criteria (the plan's floor and a scoring guide's ceiling;
   the pack schema's own minimum of three is unchanged and is never weakened);
4. every criterion is non-empty and no criterion is a mental-state claim: "understands", "knows",
   "appreciates", "is aware", "grasps", "is familiar with", "mastery" and their relatives are
   rejected. Beyond that the validator does not police wording — a synthetic pack may use
   placeholder criteria, and judging prose is the reviewer's job, not a regex's;
5. no two criteria restate the same criterion after case, whitespace and trailing-punctuation
   normalisation.

Where it is used:

* **Pack validator** — `coursebook.packs._minima_problems` runs the rules on every imported or
  audited pack check, with the profile derived from the check's evidence target.
* **Lesson generation** — `coursebook.generation.enforce_lesson_rules` resolves the profile, runs
  the same rules on the generated check, and the lesson prompt names the profile and its aspects
  (`coursebook.generation._lesson_instructions`). A rejected rubric costs one regeneration and then
  parks the lesson for review; it never becomes graded evidence.

## What the validator cannot prove

A clean verdict is **not** a safety badge, a truth badge or a native-speaker review. Specifically:

* it cannot prove the prose is true, well sourced or appropriate;
* it cannot prove a criterion is the best wording for this response;
* it cannot prove a scored response is correct, or that a learner has "mastered" anything;
* it says nothing about licensing, media rights or provenance — those live in the pack manifest
  audit (`docs/PACK-AUTHORING.md`), not here.

## Answer keys

Nothing here invents, stores or places an answer key. `rubric_template` returns aspects, not
answers; the pack audit still rejects a learner-facing page that carries reference answers, accepted
answers or rubric text (`coursebook.packs.audit_bundle`, `coursebook.generation.assert_no_answer_leak`).
A criterion says what to look for in a response, never what the response must be.
