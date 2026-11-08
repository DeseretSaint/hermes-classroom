# Course quality review: H173d-S3-house-rule-copy

Reviewer: Cinder (fix author, not independent)
Sample: H173d-S3-house-rule-copy
Scope: short
Validator verdict: no validation record supplied

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_parent.json` sha256 `9358219ceb158086d964a9fd756728ba47ac5a7b88c145c0fc79dd4676e963fd`
- lesson: `tests/fixtures/generation/lesson_parent_safe.json` sha256 `df8e2c06b996d6ece12c89c7307bddb6d8bbbe9e50f6f9a4d2bc4ba42d978fcd`
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
- Learner explanation: Warm things get heat from an appliance such as the kettle, toaster or oven. Cold things come from the fridge or freezer. A grown-up always fills and switches on the kettle, and you sort the cards instead. That is our house rule for this kitchen, not a general fact we have checked against a source.
- Check: kind=observation, format=text, target=recall, accepted_answers=5, accepted_alternatives=0, rubric_criteria=3, stimulus_items=0
- Rubric criteria: ['names one of each', 'points before naming', 'cold example']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 0
- Parent notes: Keep your child within arm's reach for the whole activity, and keep the kettle unplugged and out of reach. The child sorts cards and names things; the child never fills or switches on the kettle. The kettle rule is our own house rule for this kitchen, not a general safety fact we have checked aga...
- Supervision notes:
  - Adult stays within arm's reach for the whole activity
  - Kettle stays unplugged and out of reach

### Validator record

- Validation record: not supplied. The verdict above is unknown, not a pass.

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 4
Evidence: plan_parent.json learner_outcome names four performances ('names and sorts warm and cold things, says why the kettle is a grown-up job, and explains one example in their own words'), each of objectives 1-4 carries a stated evidence_criteria ('Points at the warm object before naming it', 'Sorts four cards with no more than one prompt'), the outcome names the transfer context ('with a parent', in the kitchen) and exclusions state what is not claimed (no child chat, no heat or kettle operation, no sourced safety claim, no developmental assessment). Scored from the artifact; I do not adopt the author record's 3.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_parent.json time_estimate is 2 sessions/week x 2 weeks = 4 sessions against 4 authored sections and 4 check_plan entries, so the schedule arithmetic holds. The order is name (objective 1, section 1) -> sort cards (2) -> kettle rule (3) -> explain (4), and section 2's sort consumes the naming taught in section 1. No units[] exist in a v1 document and no section justifies its position, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: lesson_parent_safe.json contains only objective 1's check; plan_parent.json check_plan[1..3] for discrimination, comprehension and production are bare observation entries with no criteria, stimulus or notes, so three of four checks cannot be read against their targets. The one visible check also pairs check.kind: observation with check.stimulus.format: text and string accepted_answers ('kettle is warm'), so the stored lane is a typed answer while the record claims an observation: the format cannot carry what the kind declares.
Follow-up: t_7f46fb7f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_parent_safe.json worked_example.steps vary the case (kettle card warm, fridge card cold) while holding the classification rule fixed, learner_explanation names that rule ('Warm things get heat from an appliance such as the kettle, toaster or oven. Cold things come from the fridge or freezer'), and worked_example.answer ('kettle and toaster in the warm pile; fridge and ice in the cold pile') agrees with the explanation. No near-miss or boundary case is explained, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_parent_safe.json runs model ('Warm things', one concept) -> guided ('Sort the cards') -> check inside the 15 minutes per session that time_estimate declares, with one act per segment; the check's naming-and-pointing task is modelled in segment 1 before it is asked. Support does not fade and no close segment returns the child to the path with the recorded result, so 3 not 4.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: The load-bearing safety claim is the kettle rule. It now carries an explicit unverified/house-rule mark in every place the reader meets it: lesson_parent_safe.json segments[0].body ends 'That is our house rule for this kitchen, not a general fact we have checked against a source', segments[0].short says 'our house rule, not a general fact', learner_explanation and learner_explanation_short repeat the same qualifier, and parent_notes says 'The kettle rule is our own house rule for this kitchen, not a general safety fact we have checked against a source'. plan_parent.json matches: evidence_note calls it 'a house rule the parent supplied ... recorded as unverified', exclusions state 'No sourced safety claim ... not a general fact', all four objectives keep support=unverified, and plan and lesson source_ids and lesson sources are empty, so no id names a page that was never fetched. That is D6 anchor 3: every load-bearing claim has either a tied source id or an explicit unverified mark, and the exclusions state what is not claimed. Not 4: no claim is attributed per sentence to a source and the plan names no fetch that would upgrade the rule.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_parent.json section 2's lesson_intent has the parent 'sort four picture cards into warm and cold', and both sections[].context_needs and parent.setting_materials require the four picture cards and crayons, yet every media_need is image=none/none with construct '' and lesson_parent_safe.json media is empty. The cards are the visual the discrimination objective depends on, their content is never specified, and the plan records the need as none: D7 anchor 2, a real need the plan leaves undecided.
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 2
Evidence: lesson_parent_safe.json parent_notes give a recovery move for the hazard ('If the child reaches for the kettle, stop, move it further away and go back to the cards') but no next move for a failed attempt: the check says 'Parent writes down what the child said and did; no grade is given', and check.assistance_policy.hint is available while no hint text exists anywhere in the lesson. A wrong sort or a missing word has no stated recovery, so D8 anchor 2: a failure path exists only in the author's head.
Follow-up: t_a84d7ba3

## Reviewer notes

- **Fixture, not a live output.** H-172 (`t_fe097fe7`) is still blocked, so no live provider
  artifact exists. Nothing here is a live claim; this record must not be cited as one.
- **Author of the fix, not an independent reviewer.** Cinder wrote this copy change. H-173d
  (`t_99f1cb89`) owns independence. `docs/reviews/H173d-S3-independent.md` is unchanged and its
  D6 = 2 stands for the bytes it scored (lesson sha256 `9b59cf96...`).
- **This record scores different bytes.** The lesson is now sha256
  `df8e2c06b996d6ece12c89c7307bddb6d8bbbe9e50f6f9a4d2bc4ba42d978fcd`; the plan is unchanged at
  `9358219c...`. Hash pins in `docs/reviews/H173c-S3-parent-kitchen-rescore.md` describe the older
  lesson and are left as history.
- **What changed and what did not.** Only the places in `lesson_parent_safe.json` that state the
  kettle rule as learner/parent-facing copy (`segments[0].body`, `segments[0].short`,
  `learner_explanation`, `learner_explanation_short`, and `parent_notes`) gained the house-rule /
  unverified qualifier ("not a general fact we have checked against a source"). The rule itself,
  `supervision_notes`, the arm's-reach and
  unplugged-kettle requirements, the reach-for-the-kettle recovery move, and the hazard fixture
  `lesson_parent_unsafe.json` were not touched. `tests/test_course_quality_s3_fixture.py` pins the
  unsafe lesson and the recorded hazard reject by hash and both still pass.
- **No validator pass is claimed.** No provider call was made. `lesson_parent_safe.json` was
  checked deterministically only: it validates against `LESSON_SCHEMA` and passes
  `generation.enforce_lesson_rules` with section 1 and objective 1.
- **D6 is 3, not 4.** The mark is now where the claim is made, but no claim is attributed per
  sentence to a fetched source and the plan names no fetch that would upgrade the rule. D3, D7 and
  D8 stay at 2 on this fixture; their existing follow-up cards are cited, not re-created.
- **This record does not weaken the hazard gate.** The safety framing and the exclusions are
  unchanged, and the fix carries the house-rule wording into the lesson copy rather than removing
  the rule.
