# Course quality review: S3

Reviewer: Cinder (fix author, not independent)
Sample: S3
Scope: short
Validator verdict: no validation record supplied

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_parent.json` sha256 `9358219ceb158086d964a9fd756728ba47ac5a7b88c145c0fc79dd4676e963fd`
- lesson: `tests/fixtures/generation/lesson_parent_safe.json` sha256 `69e0c1409b57b5561ea836b2394e4a5689f8c60e9cb1afe89ca54cabceebea50`
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
- Parent notes: Keep your child within arm's reach for the whole activity, and keep the kettle unplugged and out of reach. The child sorts cards and names things; the child never fills or switches on the kettle. If the child reaches for the kettle, stop, move it further away and go back to the cards. If the chil...
- Supervision notes:
  - Adult stays within arm's reach for the whole activity
  - Kettle stays unplugged and out of reach

### Validator record

- Validation record: not supplied. The verdict above is unknown, not a pass.

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 4
Evidence: plan_parent.json learner_outcome names four performances the child does (names and sorts warm and cold things, says why the kettle is a grown-up job, explains one example in their own words); every objective's evidence_criteria states an observable act and exclusions bound the claim (no child chat, no heat or kettle operation by the child, no sourced safety claim, no developmental assessment).
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_parent.json time_estimate is sessions_per_week=2 x weeks=2 = 4 sessions against 4 authored sections and 4 check_plan entries; the order runs name (objective 1, section 1) -> sort (2) -> kettle rule (3) -> explain (4), and sorting consumes the naming taught in section 1. No section states why the order is what it is, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: lesson_parent_safe.json carries only objective 1's check; plan_parent.json check_plan[1..3] for discrimination, comprehension and production are bare observation entries with no criteria, notes or stimulus, so three of four checks cannot be read. The visible check also pairs check.kind=observation with check.stimulus.format=text and string accepted_answers, a lane mismatch on the one check that exists.
Follow-up: t_7f46fb7f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_parent_safe.json worked_example.steps vary the case (kettle card warm, fridge card cold) while holding the classification rule fixed, and learner_explanation names that rule ('Warm things get heat from an appliance such as the kettle, toaster or oven. Cold things come from the fridge or freezer'); the answer agrees with the explanation. No near-miss or boundary case is explained, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_parent_safe.json runs model ('Warm things', one concept) then guided ('Sort the cards') then the check, inside the 15 minutes per session that plan_parent.json time_estimate declares, with one act per segment; the naming-and-pointing task is modelled in segment 1 before the check asks it, so no step requires untaught material. Support does not fade and no close segment returns the child to a path, so 3 not 4.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 2
Evidence: plan_parent.json evidence_note calls the kettle rule a house rule the parent supplied and its exclusions say 'No sourced safety claim', but lesson_parent_safe.json segments[0].body states it as a general fact ('A grown-up is the only person who fills or switches on the kettle, because hot water can burn') with no unverified or house-rule mark in the lesson copy, and parent_notes repeat the rule unmarked. The honest mark exists in the plan and does not reach the reader.
Follow-up: t_f14d54f7

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_parent.json section 2's lesson_intent sorts 'four picture cards' and its context_needs and parent.setting_materials require them, yet every media_need is image=none/none with an empty construct and lesson_parent_safe.json media is empty. The four cards are the visual the discrimination objective depends on, their content is never specified, and the plan records the need as none.
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_parent_safe.json check.learner_instructions now carries the hint the policy claims (assistance_policy.hint=available): 'Hint: point at the card and say its name before asking the child to name it', and a next move after a failed attempt: 'If the child sorts a card wrong or cannot name one, put the cards back, name each card together, try the sort again, and write down the retry and what the child did the second time'. parent_notes state the same retry move, and the hazard recovery ('If the child reaches for the kettle, stop, move it further away and go back to the cards') is unchanged. Hint, stop condition and failed-attempt next move are stated on both parent-facing surfaces and agree, so D8 anchor 3.
Follow-up: none


## Reviewer notes

- **This is an author-run re-score, not an independent review.** Cinder made the D8 copy fix,
  so this record is not independent. `docs/reviews/H173d-S3-independent.md` (Sentinel, cbqa) is
  the independent verdict; it was not edited.
- **Only D8 moved.** D8 is 3 because `check.learner_instructions` and `parent_notes` now state
  both the hint the policy claims and the same next move after a failed sort or a missing word
  (see the D8 evidence). D1 4, D2 3, D3 2, D4 3, D5 3, D6 2 and D7 2 are unchanged from the
  independent record; D3, D6 and D7 stay below 3, and their fixes are owned by `t_7f46fb7f`,
  `t_f14d54f7` and `t_fc59d3c6`.
- **The fix is in the lesson copy, not this record.** `tests/fixtures/generation/lesson_parent_safe.json`
  sha256 `69e0c1409b57b5561ea836b2394e4a5689f8c60e9cb1afe89ca54cabceebea50` changed only
  `check.learner_instructions` and `parent_notes`. The plan `tests/fixtures/generation/plan_parent.json`
  is unchanged at sha256 `9358219ceb158086d964a9fd756728ba47ac5a7b88c145c0fc79dd4676e963fd`. The
  hazard stop, the arm's-reach rule, the unplugged-kettle rule and `lesson_parent_unsafe.json` (the
  validator's hazard fixture) are untouched; no schema, generator, validator, rubric or grading
  code changed.
- **Validator verdict unknown, not a pass.** No validation record exists for this pair and no
  provider call was made. The recorded reject in `validation_reject_hazard.json` belongs to
  `lesson_parent_unsafe.json`, which this record does not score.
- **Pre-existing answer-leak condition, unchanged.** `worked_example.steps` state "the kettle is
  warm" and "the fridge is cold", which are also `accepted_answers`; the baseline bytes have the
  same condition and this card does not touch it.
- **Fixture, not a live output.** H-172 (`t_fe097fe7`) is blocked, so no live provider artifact
  exists and no learner has received these bytes.
- **Scope.** This record answers the D8 find in `t_a84d7ba3` only. A limit is not a pass.

