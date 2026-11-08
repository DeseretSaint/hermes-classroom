# Course quality review: H173c-S3-parent-kitchen

Reviewer: Cinder (fix author, not independent)
Sample: H173c-S3-parent-kitchen
Scope: short
Validator verdict: not run for the repaired pair (no live provider call); the recorded reject on the unfixed lesson is unchanged.

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_parent.json` sha256 `9358219ceb158086d964a9fd756728ba47ac5a7b88c145c0fc79dd4676e963fd`
- lesson: `tests/fixtures/generation/lesson_parent_safe.json` sha256 `9b59cf968a08d837498f872f8f4afa6355569f66011cd9dc76480e867cb2a908`
- validation: not supplied

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Kitchen science: warm and cold
- Learner outcome: With a parent, the child names and sorts warm and cold things, says why the kettle is a grown-up job, and explains one example in their own words.
- Delivery: parent_led
- Time estimate: sessions_per_week=2, weeks=2, minutes_per_session=15, basis=none
- Session capacity: 4 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Name one warm and one cold thing in the kitchen (target=recall, support=unverified, criteria=3, source_ids=0)
  2. [unit -] Sort picture cards into warm and cold (target=discrimination, support=unverified, criteria=1, source_ids=0)
  3. [unit -] Say why the kettle is a grown-up job (target=comprehension, support=unverified, criteria=1, source_ids=0)
  4. [unit -] Explain one example in their own words (target=production, support=unverified, criteria=1, source_ids=0)
- Objective support: {'unverified': 4}; targets: {'comprehension': 1, 'discrimination': 1, 'production': 1, 'recall': 1}; objectives with no source_ids: 4/4
- Units: none (v1 document: one implicit unit)
- Sections (4):
  - section 1: Warm things at home (objective_refs=[1], media_need: image=none/none, audio=none/none)
    lesson_intent: Parent names warm objects the child can see, one at a time, and the child says each word back.
  - section 2: Cold things at home (objective_refs=[2], media_need: image=none/none, audio=none/none)
    lesson_intent: Parent names cold objects, then sorts four picture cards into warm and cold together.
  - section 3: Why the kettle is a grown-up job (objective_refs=[3], media_need: image=none/none, audio=none/none)
    lesson_intent: Parent explains the kettle rule and the child says the safety reason back.
  - section 4: Explain one example (objective_refs=[4], media_need: image=none/none, audio=none/none)
    lesson_intent: Parent asks the child to explain one warm or cold example in their own words.
- Check plan entries: 4
  - objective 1: kind=observation, target=recall
  - objective 2: kind=observation, target=discrimination
  - objective 3: kind=observation, target=comprehension
  - objective 4: kind=observation, target=production
- Exclusions:
  - No child chat: the parent leads every step.
  - No heat, flame or kettle operation by the child; the kettle stays unplugged and out of reach.
  - No sourced safety claim: the kettle rule is a parent-supplied house rule for this home, not a general fact.
  - No claim of developmental assessment.
- Plan source_ids: none

### Lesson

- Section title: Warm things at home
- Segments: 2
  1. kind=model, heading=Warm things
  2. kind=guided, heading=Sort the cards
- Worked example: prompt=Which cards are warm, and which are cold?; steps=3
    step 1: Pick up the kettle card and say: the kettle is warm because a grown-up heats water in it.
    step 2: Pick up the fridge card and say: the fridge is cold because it keeps food cool.
    step 3: Put the kettle card in the warm pile and the fridge card in the cold pile.
- Worked example answer present: yes (not reproduced here)
- Learner explanation: Warm things get heat from an appliance such as the kettle, toaster or oven. Cold things come from the fridge or freezer. A grown-up always fills and switches on the kettle, and you sort the cards instead.
- Check: kind=observation, format=text, target=recall, accepted_answers=5, accepted_alternatives=0, rubric_criteria=3, stimulus_items=0
- Rubric criteria: ['names one of each', 'points before naming', 'cold example']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 0
- Parent notes: Keep your child within arm's reach for the whole activity, and keep the kettle unplugged and out of reach. The child sorts cards and names things; the child never fills or switches on the kettle. If the child reaches for the kettle, stop, move it further away and go back to the cards.
- Supervision notes:
  - Adult stays within arm's reach for the whole activity
  - Kettle stays unplugged and out of reach

### Validator record

- Validation record: not supplied. The verdict above is unknown, not a pass.

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 3
Evidence: plan_parent.json learner_outcome now names naming, sorting, the kettle rule and one explanation, which is the union of objectives 1-4; every objective title is a performance (name, sort, say why, explain) rather than a topic.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_parent.json orders naming (objective 1), sorting (2), the kettle rule (3) and explanation (4); sections 1-4 reference those objectives in order and 2 sessions/week x 2 weeks holds the four authored sections.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 3
Evidence: plan_parent.json objective 1 declares recall with three evidence_criteria; lesson_parent_safe.json check.rubric carries exactly those three criteria (names one of each, points before naming, cold example) and check.evidence_target is recall.
Follow-up: none

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_parent_safe.json segments[0] states the warm/cold rule and that only a grown-up works the kettle; segments[1] runs the card sort; worked_example.steps 1-3 show the reason for each card and the pile it goes in.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_parent_safe.json has two segments (model, then guided card sort), one worked example and one observation check in a 15-minute parent-led session; plan_parent.json allows 2 sessions/week for 2 weeks, so the arc fits.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_parent.json evidence_note and exclusions[2] mark the kettle rule as a parent-supplied house rule recorded unverified; objectives 1-4 keep support=unverified with no source_ids, so the safety rule is bounded rather than given an invented source.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: plan_parent.json sections 1-4 declare image=none/none and audio=none/none; the four physical picture cards named in context_needs and setting_materials carry the sorting construct, and no generated media artifact is claimed.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_parent_safe.json parent_notes repeat 'within arm's reach' and 'unplugged and out of reach', supervision_notes match plan_parent.json parent.supervision_notes, and a reach for the kettle has a stated stop-and-redirect move.
Follow-up: none


## Reviewer notes

Limits of this record: the reviewer is the author of the fix, not an independent reviewer
(H-173d `t_99f1cb89` owns independence); the repaired lesson has not been through the live
validator because that needs a provider call; H-172's live output does not exist yet, so this is
a fixture re-score and not a live score. A limit is not a pass. No live validator run is claimed
and no learner has received this fixture.

### Relation to the unfixed artifact

The unfixed artifact keeps its reject, and the hazard survived H-195: `lesson_parent_unsafe.json`
sha256 `b8461e8e67f194807e01d2893bf558a73e776701c826554831c65da81dd6f9a1` still says the child
fills the kettle at the sink and switches it on, and `validation_reject_hazard.json` still records
`hazard_age_appropriateness: fail` for `segment:2`. (The digest this record originally reviewed,
`0935dcb0f92866e4d229cb1e5c55da40ac7e56489b682c6b79fd98d338d7121a`, describes the pre-H-195 bytes;
H-195 lengthened the fixture so the *hazard* — not thin prose — is what fails the new teaching
floor, and re-derived the test pin once from the settled bytes rather than editing either.)
`tests/test_course_quality_s3_fixture.py` pins both hashes and fails if the hazard fixture is
softened, and the existing pipeline test
`tests.test_generation.GenerationTest.test_parent_hazard_is_rejected_by_validation` still drives
that reject through the real lesson pipeline. The repaired pair is a separate fixture; it is not
a replacement for the hazard fixture and it does not inherit a validator pass.

### What the repaired pair was checked against

The repaired pair was checked deterministically only: `plan_parent.json` validates against
`PLAN_SCHEMA_V1` and passes `generation.enforce_plan_rules(recipe="parent")`;
`lesson_parent_safe.json` validates against `LESSON_SCHEMA` and passes
`generation.enforce_lesson_rules` with section 1 and objective 1.

### Superseded bytes (H-173d D8 fix)

The lesson bytes this record scored are superseded. `tests/fixtures/generation/lesson_parent_safe.json`
now has sha256 `69e0c1409b57b5561ea836b2394e4a5689f8c60e9cb1afe89ca54cabceebea50` (the recorded
`9b59cf96...` is the pre-fix lesson). The change is `check.learner_instructions` and `parent_notes`:
they now state the hint text that `assistance_policy.hint = available` claims and the same next
move after a failed sort or a missing word, without touching the hazard stop or the supervision
rule. No score in this record is rewritten; the D8 re-score with new evidence is
`docs/reviews/H173d-S3-D8-rescore.md`.

### Scope

Fixtures and this record only. No RPC, schema, generation, validation, grading or UI behavior
changed. The only new prose claim is the restatement of the kettle rule already present in the
plan's exclusions; it is marked as a parent-supplied house rule and no source is claimed for it.

