# Course quality review: H173d-D7-S3-media

Reviewer: Cinder (backend kernel, author-run media re-score)
Sample: H173d-D7-S3-media
Scope: short
Validator verdict: no validation record supplied

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_parent.json` sha256 `c2f75590fa21bce5766480c3f4696f194326d98c4ac5d18526a15910a0434e22`
- lesson: `tests/fixtures/generation/lesson_parent_safe.json` sha256 `295a9d3e9c305cd8859b798f884efd5d80b7def40143bb3b0da9bd2f5fe029dd`
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
    lesson_intent: Parent names cold objects, then sorts four picture cards - a kettle, a toaster, a fridge and an ice tray - into warm and cold together; the cards are parent-supplied props, so the lesson declares no media artifact of its own.
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
Score: 4
Evidence: plan_parent.json learner_outcome names four performances the child does ('names and sorts warm and cold things, says why the kettle is a grown-up job, and explains one example in their own words') and every objective's evidence_criteria states the observable act ('Points at the warm object before naming it', 'Sorts four cards with no more than one prompt'); exclusions bound the claim (no child chat, no heat or kettle operation by the child, no sourced safety claim, no developmental assessment).
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_parent.json time_estimate is sessions_per_week=2 x weeks=2 = 4 sessions against 4 authored sections and 4 check_plan entries, so the schedule arithmetic holds. Order runs name (objective 1, section 1) -> sort (2) -> kettle rule (3) -> explain (4), and sorting consumes the naming taught in section 1. No units[] exist and no section states why the order is what it is, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: Only objective 1's check exists in lesson_parent_safe.json; check_plan[1..3] for discrimination, comprehension and production are bare observation entries with no criteria, notes or stimulus, so three of four checks cannot be read. The visible check pairs check.kind=observation with check.stimulus.format=text and string accepted_answers ('kettle is warm'), a typed lane rather than an observation, so the format cannot carry what the kind claims.
Follow-up: t_7f46fb7f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_parent_safe.json worked_example.steps vary the case (kettle card warm, fridge card cold) while holding the classification rule fixed, and learner_explanation names that rule ('Warm things get heat from an appliance such as the kettle, toaster or oven. Cold things come from the fridge or freezer'); the answer ('kettle and toaster in the warm pile; fridge and ice in the cold pile') agrees with the explanation. No near-miss or boundary case is explained, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_parent_safe.json runs model ('Warm things', one concept) -> guided ('Sort the cards') -> check inside the 15 minutes per session that time_estimate declares, with one act per segment; the check's naming-and-pointing task is modelled in segment 1 before it is asked, so no step requires untaught material. Support does not fade and no close segment returns the child to the path, so 3 not 4.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 2
Evidence: plan_parent.json evidence_note calls the kettle rule 'a house rule the parent supplied' and exclusions say 'No sourced safety claim', but the learner-facing copy in lesson_parent_safe.json segments[0].body states it as a general fact - 'A grown-up is the only person who fills or switches on the kettle, because hot water can burn' - with no unverified or house-rule mark in the lesson, and parent_notes repeat the rule unmarked. The honest mark exists in the plan and does not reach the reader, which is D6 anchor 2.
Follow-up: t_f14d54f7

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: plan_parent.json now names the cards' content in sections 1-2 context_needs ('four picture cards: a kettle, a toaster, a fridge and an ice tray (parent-supplied props, not lesson media)'), in section 2's lesson_intent and in parent.setting_materials, and lesson_parent_safe.json segment 2 lists the same four objects before the sort. Every media_need stays honestly none because the cards are physical parent-supplied props, and the objective-2 visual the activity depends on is specified rather than left to improvise - D7 anchor 3.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 2
Evidence: lesson_parent_safe.json parent_notes give a recovery move for the hazard ('If the child reaches for the kettle, stop, move it further away and go back to the cards') but no next move for a failed attempt: the check says 'Parent writes down what the child said and did; no grade is given' and check.assistance_policy.hint is available while no hint text exists in the lesson. A wrong sort or a missing word has no stated recovery, so D8 anchor 2.
Follow-up: t_a84d7ba3


## Reviewer notes

- **This is a recorded fixture re-score, not a live provider run.** H-172 (`t_fe097fe7`) is still
  blocked, so no live short-scope output is claimed and this record must not be cited as one.
- **Reviewer is the engineer who edited the fixtures.** Cinder (backend kernel) made the media
  repair in this branch, so this is an author-run re-score, not an independent review. The
  independent D7 finding in `docs/reviews/H173d-S3-independent.md` and the earlier author record
  `docs/reviews/H173c-S3-parent-kitchen-rescore.md` are not edited.
- **What changed.** `plan_parent.json` names the four picture cards' content — a kettle, a
  toaster, a fridge and an ice tray — in sections 1-2 `context_needs`, in section 2's
  `lesson_intent` and in `parent.setting_materials`; `lesson_parent_safe.json` segment 2 lists the
  same four objects before the sort. Every `media_need` stays `none` because the cards are
  physical parent-supplied props: no generated artifact is declared or claimed.
- **No validation record exists for the repaired pair.** The packet echoes "no validation record
  supplied. The verdict above is unknown, not a pass." The recorded `reject` in
  `validation_reject_hazard.json` belongs to `lesson_parent_unsafe.json`, which this record does
  not score and whose hash-pinned bytes are untouched.
- **Limits.** D3 stays at 2 (three of four checks unreadable; `check.kind=observation` paired with
  `stimulus.format=text`), D6 at 2 (learner copy states the kettle house rule as general fact) and
  D8 at 2 (failed attempt has no next move and `hint=available` names no hint text). Those
  follow-ups (`t_7f46fb7f`, `t_f14d54f7`, `t_a84d7ba3`) remain open and are not repaired here.
