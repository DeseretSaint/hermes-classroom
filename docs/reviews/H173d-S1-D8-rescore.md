# Course quality review: S1

Reviewer: Cinder (fix author, not independent)
Sample: S1
Scope: single
Validator verdict: pass

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_one_off.json` sha256 `fcca64504652d4bf087c275350e2fb7bf746dec32aabc1efd45ead1e93ea400f`
- lesson: `tests/fixtures/generation/lesson_one_off.json` sha256 `22e88f7d676c469d96dcc420cb4befbca24ced3db86d0e1b5ed699dffb40fd3a`
- validation: `tests/fixtures/generation/validation_pass.json` sha256 `9da8cc1583094441fe790b10b58a0a1a5ec071b6bbb15337c615b28d53b19c90`

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Replace a bicycle brake pad
- Learner outcome: Replace one rim-brake pad on a bicycle, then verify the brake by hand before riding. The brake model is not identified in this course, so the learner fetches the manufacturer's manual for their own brake and takes the pad model, fastener and torque values from it.
- Delivery: self_study
- Time estimate: sessions_per_week=1, weeks=1, minutes_per_session=45, basis=none
- Session capacity: 1 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Identify the correct replacement pad for the brake model (target=procedure, support=unverified, criteria=1, source_ids=0)
  2. [unit -] Remove the worn pad without damaging the caliper (target=procedure, support=unverified, criteria=2, source_ids=0)
  3. [unit -] Seat and tighten the new pad to the manual's specification (target=procedure, support=unverified, criteria=2, source_ids=0)
  4. [unit -] Verify the brake by hand before riding (target=procedure, support=unverified, criteria=2, source_ids=0)
- Objective support: {'unverified': 4}; targets: {'procedure': 4}; objectives with no source_ids: 4/4
- Units: none (v1 document: one implicit unit)
- Sections (4):
  - section 1: Identify the pad (objective_refs=[1], media_need: image=required/schematic, audio=none/none, construct=The labelled parts diagram: pad model, pad slot and the single caliper mounting fastener)
    lesson_intent: Match the pad model and the caliper fastener to the manufacturer's labelled parts diagram before touching the brake.
  - section 2: Remove the worn pad (objective_refs=[2], media_need: image=required/schematic, audio=none/none, construct=The labelled diagram showing the sequence of steps that release the caliper fastener and free the pad)
    lesson_intent: Follow the labelled sequence for releasing the caliper fastener and sliding the worn pad out without damaging the caliper.
  - section 3: Seat and tighten (objective_refs=[3], media_need: image=required/schematic, audio=none/none, construct=The labelled parts diagram showing pad orientation and seating before the fastener is tightened)
    lesson_intent: Seat the new pad square in the caliper and tighten the fastener to the torque the manual prints for this brake model.
  - section 4: Verify by hand (objective_refs=[4], media_need: image=required/schematic, audio=none/none, construct=The labelled diagram of the parts that move when the brake lever is squeezed)
    lesson_intent: Run the manual's hand-verification steps and have a second person confirm the lever and the free wheel before any ride.
- Check plan entries: 4
  - objective 1: kind=verification, target=procedure, notes=The learner writes down the pad model read from their own manual; the photo the learner takes for objective 2 shows the same pad.
  - objective 2: kind=verification, target=procedure, notes=The checklist asks the learner to confirm the named fastener and the photo of the worn pad beside it. The attempt records that confirmation as self-reported; the photo stays the learner's own recor...
  - objective 3: kind=verification, target=procedure, notes=The torque value is read from the learner's manual; the course states none, and the checklist asks the learner to confirm the fastener was tightened to that printed value.
  - objective 4: kind=verification, target=procedure, notes=The checklist asks the learner to confirm a second person checked the lever and the free wheel. That confirmation is recorded as the learner's self-report, never as independent evidence.
- Exclusions:
  - Does not cite or supply a manufacturer manual; the learner must fetch the manual for their own brake model.
  - Does not state a pad model, fastener size or torque value as fact; the example's model and key are stand-ins for what the learner's manual prints.
  - Does not certify the procedure; the manufacturer's documentation and an expert check remain the authority.
  - No live-road test is part of this brief.
  - Not for hydraulic, disc or e-bike brake systems.
- Plan source_ids: none

### Lesson

- Section title: Replace one brake pad
- Segments: 4
  1. kind=model, heading=Read the manual before touching the brake
  2. kind=guided, heading=Loosen only the named fastener
  3. kind=guided, heading=Seat the new pad and tighten it
  4. kind=guided, heading=Verify the brake by hand
- Worked example: prompt=The manual for your brake lists a pad model and the hex key that fits the caliper fastener; this example uses pad BR-42 and a 5 mm key as stand-ins.; steps=4
    step 1: Lay out the new pad and the key the manual names
    step 2: Write down the pad model printed in the manual
    step 3: Loosen only the caliper fastener and slide the worn pad out
    step 4: Set the worn pad beside the loosened fastener for the photo
- Worked example answer present: yes (not reproduced here)
- Learner explanation: Work with your manual open: it, not this page, carries your brake's pad model, fastener and torque. Confirm each step only after you have done it, and take the photo and get the second person's confirmation: those are the evidence a reviewer could check, while this checklist records only what you confirm.
- Check: kind=verification, format=verification, target=procedure, accepted_answers=1, accepted_alternatives=0, rubric_criteria=3, stimulus_items=3
- Rubric criteria: ['checklist completed', 'model matched', 'listed tool used']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 1
- Parent notes: none
- Supervision notes: none

### Validator record

- Recorded verdict: pass
- Recorded criteria:
  - objective_alignment: pass (objective_alignment checked against the artifact and ledger)
  - source_support: pass (source_support checked against the artifact and ledger)
  - factual_correctness: pass (factual_correctness checked against the artifact and ledger)
  - answer_uniqueness: pass (answer_uniqueness checked against the artifact and ledger)
  - alternative_coverage: pass (alternative_coverage checked against the artifact and ledger)
  - rubric_consistency: pass (rubric_consistency checked against the artifact and ledger)
  - internal_contradiction: pass (internal_contradiction checked against the artifact and ledger)
  - answer_leakage: pass (answer_leakage checked against the artifact and ledger)
  - hazard_age_appropriateness: pass (hazard_age_appropriateness checked against the artifact and ledger)
  - evidence_target_fit: pass (evidence_target_fit checked against the artifact and ledger)
- Recorded rejections: 0
- Claim verdicts: 1

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 4
Evidence: plan_one_off.json learner_outcome names the capability and its transfer context (the learner fetches the manufacturer's manual for their own brake); all four objectives carry evidence_criteria with an observable act, and exclusions bound the claim (no hydraulic, disc or e-bike systems, no live-road test, no certification). The four objectives are steps of one procedure but each still names a stated criterion, so the D1 4-anchor is met.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_one_off.json objectives 1-4 run identify -> remove -> seat and tighten -> verify; each section's lesson_intent names the manual value the step consumes (pad model, fastener, torque), time_estimate 1 session x 45 minutes and its rationale put the four sections inside that session, and lesson_one_off.json walks the same four segments in the same order. The order is correct but no section states why, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: lesson_one_off.json check.kind and check.stimulus.format are verification with three tick items, so an attempt stores ticked ids with evidence_class=self_reported, while all four plan_one_off.json objectives declare evidence_target=procedure and the build has no attachment or observer lane. That is the rubric's own 0.1.0 D3 anchor 2 boundary for a checklist-only procedure course; the validator's evidence_target_fit pass answers a different question.
Follow-up: t_f770bf62

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_one_off.json worked_example.steps give four ordered actions on the same one-pad removal task as check.reference_answer, and learner_explanation names the rule that makes it work (the manual, not this page, carries the pad model, fastener and torque). The example stops at objective 2 and no near-miss for seating or hand verification is shown, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_one_off.json runs model then three guided segments then one check, one act per segment, in the same order as plan_one_off.json sections 1-4 and inside time_estimate.minutes_per_session=45; no segment needs material an earlier one has not modelled. Support does not fade and no closing segment returns the learner to their path, so 3 not 4.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_one_off.json objectives 1-4 all carry support=unverified with empty source_ids, evidence_note states that no manufacturer manual was fetched and that no pad model, fastener size or torque value is stated as fact, and lesson_one_off.json claims no source. Every load-bearing claim is either marked unverified or bounded by exclusions and no source id is invented.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_one_off.json sections 1-4 each declare media_need.image.level=required with a distinct construct (parts diagram, release sequence, seating and orientation, moving parts), but lesson_one_off.json media holds exactly one schematic and nothing in the lesson states why the other three required constructs have no artifact. Three constructs the plan calls required cannot be performed by what ships.
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_one_off.json check.learner_instructions now carries the hint the policy claims (assistance_policy.hint=available): 'Hint: if the fastener will not turn by hand, stop and re-read segment 2; if a value is missing, re-read segment 1', and a next move after a failed attempt: 'If you cannot tick an item, leave it unticked, write down which item and why, re-read the segment that covers it, and submit again: a retry records the same self-report, not a pass'. Segment 2 still states the hazard stop ('Stop if the caliper moves or the fastener will not turn by hand'). Hint, stop condition and retry move are all stated in the lesson copy, so D8 anchor 3.
Follow-up: none


## Reviewer notes

- **This is an author-run re-score, not an independent review.** Cinder made the D8 copy fix,
  so this record is not independent. `docs/reviews/H173d-S1-independent.md` (Sentinel, cbqa) is
  the independent verdict; it was not edited.
- **Only D8 moved.** D8 is 3 because the lesson copy now states the hint the policy claims and a
  next move after a failed attempt (see the D8 evidence). D1 4, D2 3, D3 2, D4 3, D5 3, D6 3 and
  D7 2 are unchanged from the independent record; D3 and D7 stay below 3, and their fixes are
  owned by `t_f770bf62` and `t_fc59d3c6`.
- **The fix is in the lesson copy, not this record.** `tests/fixtures/generation/lesson_one_off.json`
  sha256 `22e88f7d676c469d96dcc420cb4befbca24ced3db86d0e1b5ed699dffb40fd3a` changed only
  `check.learner_instructions`. The plan `tests/fixtures/generation/plan_one_off.json` is unchanged
  at sha256 `fcca64504652d4bf087c275350e2fb7bf746dec32aabc1efd45ead1e93ea400f`. No segment body,
  check item, accepted answer, reference answer, schema, generator, validator, rubric or grading
  code changed.
- **Validator verdict echoed, not re-run.** `validation_pass.json` is echoed as the recorded pass;
  no provider call was made, so no structural pass is claimed or overturned here.
- **Fixture, not a live output.** H-172 (`t_fe097fe7`) is blocked, so no live provider artifact
  exists and no learner has received these bytes.
- **Scope.** This record answers the D8 find in `t_a84d7ba3` only. A limit is not a pass.

