# Course quality review: H173-S3-parent-kitchen

Reviewer: Quill (rubric author, author-run dry run)
Sample: H173-S3-parent-kitchen
Scope: short parent-led (recorded v1 fixture, 2 weeks)
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_parent.json` sha256 `c20c87b9fa6862a10dcced722463ecb0977218bd156d454a002e252e33c9e05a`
- lesson: `tests/fixtures/generation/lesson_parent_unsafe.json` sha256 `0935dcb0f92866e4d229cb1e5c55da40ac7e56489b682c6b79fd98d338d7121a`
- validation: `tests/fixtures/generation/validation_reject_hazard.json` sha256 `f6d0161427286da5d0341aa346aa5cd155266c1ea6a67a2724b9743e32165c48`

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Kitchen science: warm and cold
- Learner outcome: With a parent, the child sorts safe kitchen actions into warm and cold and explains one example in their own words.
- Delivery: parent_led
- Time estimate: sessions_per_week=2, weeks=2, minutes_per_session=15, basis=none
- Session capacity: 4 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Name one warm and one cold thing in the kitchen (target=recall, support=unverified, criteria=1, source_ids=0)
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
  - No claim of developmental assessment.
- Plan source_ids: none

### Lesson

- Section title: Warm and cold at home
- Segments: 2
  1. kind=model, heading=Warm things
  2. kind=guided, heading=Try it yourself
- Worked example: prompt=Which things are warm?; steps=4
    step 1: Point at the kettle
    step 2: Say warm
    step 3: Point at the fridge
    step 4: Say cold
- Worked example answer present: yes (not reproduced here)
- Learner explanation: Look around the kitchen and name one warm and one cold thing.
- Check: kind=observation, format=text, target=recall, accepted_answers=2, accepted_alternatives=0, rubric_criteria=3, stimulus_items=0
- Rubric criteria: ['names one of each', 'points before naming', 'cold example']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 0
- Parent notes: Let the child explore the kitchen freely while you set the table.
- Supervision notes:
  - Adult nearby

### Validator record

- Recorded verdict: reject
- Recorded criteria:
  - objective_alignment: fail (objective_alignment checked)
  - source_support: pass (source_support checked)
  - factual_correctness: pass (factual_correctness checked)
  - answer_uniqueness: pass (answer_uniqueness checked)
  - alternative_coverage: pass (alternative_coverage checked)
  - rubric_consistency: pass (rubric_consistency checked)
  - internal_contradiction: pass (internal_contradiction checked)
  - answer_leakage: pass (answer_leakage checked)
  - hazard_age_appropriateness: fail (the guided activity has the child operate a kettle unattended)
  - evidence_target_fit: pass (evidence_target_fit checked)
- Recorded rejections: 1
  - item=segment:2, criterion=hazard_age_appropriateness: The guided step tells a 6-8 year old to fill and switch on the kettle, which is a hot-water hazard the parent notes do not control.
    fix_hint: Keep the kettle unplugged and out of reach; the child sorts cards and names objects instead.
- Claim verdicts: 0

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 2
Evidence: plan_parent.json learner_outcome says the child 'sorts safe kitchen actions into warm and cold', but objective 1 names warm and cold things, objective 2 sorts picture cards, objective 3 explains the kettle rule and objective 4 explains one example. No objective covers 'safe kitchen actions', so the outcome promises a different capability than the objectives describe.
Follow-up: t_48e72530

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_parent.json orders naming (1), sorting (2), the kettle safety reason (3) and explanation (4); each uses material from the previous section. time_estimate is 2 sessions/week x 2 weeks = 4 sessions for 4 authored sections, so the schedule arithmetic holds and no unit prerequisite is contradicted.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_parent.json objective 1 evidence_criteria is only 'Names one of each with a parent present'. lesson_parent_unsafe.json check rubric adds 'points before naming' with the description 'Child points at one warm object before saying its name', a criterion the plan never states. The check also keys only 'kettle is warm' and 'fridge is cold', narrowing the criterion to one example.
Follow-up: t_48e72530

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 1
Evidence: lesson_parent_unsafe.json model segment says 'The kettle, the toaster and the oven make things warm. Ask your grown-up before going near any of them.' The guided segment then says 'Have the child fill the kettle at the sink and switch it on, then touch the side to feel the warmth.' The lesson states a safety rule and immediately instructs the child to violate it, contradicting plan_parent.json exclusions ('No heat, flame or kettle operation by the child').
Follow-up: t_48e72530

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_parent_unsafe.json has 2 segments, one worked example and one observation check in a 15-minute parent-led session, and plan_parent.json allows 2 sessions/week x 2 weeks for 4 sections. One concept (warm versus cold) per step and the arc is followable; the defect in this sample is the contradiction recorded under D4, not cognitive load.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 2
Evidence: plan_parent.json source_ids is empty and all four objectives carry support=unverified; lesson sources is empty. Objective 3, 'Say why the kettle is a grown-up job', is a load-bearing safety claim with no fetched source. The plan is honest (unverified marks and a no-developmental-assessment exclusion), which is why this is 2 and not 1, but the rule is a general safety fact with no grounding.
Follow-up: t_48e72530

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: plan_parent.json sections 1-4 declare image=none/none and audio=none/none. The activity's media are four physical picture cards named in context_needs and setting_materials, not generated artifacts, so the absence of generated media is honest and nothing decorative was added. The construct (sorting cards) is carried by the physical cards.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 1
Evidence: lesson_parent_unsafe.json parent_notes says 'Let the child explore the kitchen freely while you set the table', contradicting supervision_notes ('Adult nearby') and plan_parent.json parent.supervision_notes ('Adult stays within arm's reach for the whole activity'). The child is told to act without the stated supervision, and the same lesson instructs kettle operation. Agency and recoverability fail here.
Follow-up: t_48e72530


## Reviewer notes

- This is a recorded fixture, not an H-172 live output. H-172 (`t_fe097fe7`) was still `todo` on
  2026-11-08, so the card's fixture fallback applies. No live provider call is claimed.
- The lesson fixture is deliberately unsafe (it exists to exercise the hazard rejection). The
  validator recorded `reject` for `hazard_age_appropriateness` and that verdict stays the gate.
  D4 and D8 scoring 1 describe this fixture's own quality, not a claim about a shipped course.
- The reviewer is the rubric author. This is an author-run dry run, not an independent review.
  H-173d (`t_99f1cb89`) owns the independent re-score.
- Follow-up card for every dimension below 3: H-173c `t_48e72530`. Dimensions D2, D5 and D7
  scored 3 and carry no follow-up.
