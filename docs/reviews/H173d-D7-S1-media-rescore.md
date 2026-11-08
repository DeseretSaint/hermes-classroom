# Course quality review: H173d-D7-S1-media

Reviewer: Cinder (backend kernel, author-run media re-score)
Sample: H173d-D7-S1-media
Scope: single
Validator verdict: pass

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_one_off.json` sha256 `fcca64504652d4bf087c275350e2fb7bf746dec32aabc1efd45ead1e93ea400f`
- lesson: `tests/fixtures/generation/lesson_one_off.json` sha256 `c79488926a6954ab1d7ebc7a26a1fc0c7626915dce0e4e6e43c7355f8a845782`
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
- Learner explanation: Work with your manual open: it, not this page, carries your brake's pad model, fastener and torque. This page ships four labelled schematics: the caliper parts, the release sequence, the pad seating and the parts that move; your manual's own diagrams remain the authority for your brake model. Confirm each step only after you have done it, and take the photo and get the second person's confirmation: those are the evidence a reviewer could check, while this checklist records only what you confirm.
- Check: kind=verification, format=verification, target=procedure, accepted_answers=1, accepted_alternatives=0, rubric_criteria=3, stimulus_items=3
- Rubric criteria: ['checklist completed', 'model matched', 'listed tool used']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 4
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
Evidence: plan_one_off.json learner_outcome names the transfer context ('Replace one rim-brake pad on a bicycle, then verify the brake by hand before riding') and every objectives[].title plus evidence_criteria states an observable act ('The pad model printed in the manual for this brake is written down'); exclusions bound the claim (no manufacturer manual supplied, no model, fastener size or torque stated as fact, not for hydraulic, disc or e-bike systems).
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_one_off.json objectives run identify -> remove -> seat and tighten -> verify, each later step consuming what the earlier one produces; sections[].objective_refs pair each section with its own objective; time_estimate is 1 session x 1 week and its rationale states the four sections are steps of one 45-minute session, so the schedule arithmetic holds. No units[] exist and no section states a reason for the order, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_one_off.json objectives 1-4 and all four check_plan entries declare evidence_target=procedure, and lesson_one_off.json check.kind=verification with stimulus.format=verification collects only ticked item ids, which grading.py:40 stores as self_reported; docs/COURSE-QUALITY-RUBRIC.md lines 147-153 cap a checklist-only procedure course at 2 whatever its labels say.
Follow-up: t_20a8d28c

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_one_off.json worked_example has four ordered steps and an answer ('The worn pad is out: the model matches the manual, the fastener was loosened with the named key, and the pad is photographed beside it') that names the same one-pad removal task as check.reference_answer and the objective set; learner_explanation names the rule that makes it work (the manual, not the page, carries the values). No near-miss case is explained, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_one_off.json walks model -> guided -> guided -> guided -> one verification check, one concept per segment (read the manual, remove the worn pad, seat and tighten, verify by hand), matching the four plan sections in the same order inside the 45-minute estimate; no segment calls for material an earlier segment has not modelled.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: all four plan_one_off.json objectives carry support=unverified with no source_ids; evidence_note states no manufacturer manual was fetched and no pad model, fastener size or torque is stated as fact; exclusions state the brake model is unknown and the learner must fetch the manual. No citation is invented, and the lack of per-claim source mapping keeps this at 3.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: plan_one_off.json sections 1-4 each declare image=required/schematic with a distinct construct, and lesson_one_off.json media now carries four visual/schematic items - caliper parts, release sequence, seated-pad orientation and moving parts - each with structured facts and a text equivalent. Segment 2 points at the release-sequence diagram, segment 4 at the moving-parts diagram, and learner_explanation names all four; the schematics support the procedure rather than grade it, so 3 not 4.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 2
Evidence: lesson_one_off.json check.assistance_policy.hint=available but no hint text appears anywhere in the lesson, and check.stimulus.prompt says 'Tick each step only after you have done it' while no field states what the learner does after an item they cannot honestly tick; segment 2 offers only the hazard stop 'Stop if the caliper moves or the fastener will not turn by hand', so a failed attempt has no stated next move.
Follow-up: t_a84d7ba3


## Reviewer notes

- **This is a recorded fixture re-score, not a live provider run.** H-172 (`t_fe097fe7`) is still
  blocked, so no live single-scope output is claimed and this record must not be cited as one.
- **Reviewer is the engineer who edited the fixtures.** Cinder (backend kernel) made the media
  repair in this branch, so this is an author-run re-score, not an independent review. The
  independent D7 finding in `docs/reviews/H173d-S1-independent.md` and the earlier author record
  `docs/reviews/H173a-S1-single-brake-rescored.md` are not edited; they stay as the record of what
  was found before this repair.
- **What changed.** `tests/fixtures/generation/lesson_one_off.json` only; `plan_one_off.json` is
  byte-identical (sha256 `fcca6450...`) and its four `image=required/schematic` declarations are
  unchanged. The lesson now ships four `visual/schematic` media items — caliper parts, release
  sequence, pad seating and moving parts — each with structured `facts.rows` and a text
  equivalent. Segment 2 points at the release-sequence diagram, segment 4 at the moving-parts
  diagram, and `learner_explanation` names all four. No validator, grading, RPC, schema or rubric
  behavior changed.
- **The structural gate now sees four, not one.** `enforce_plan_rules` and `enforce_lesson_rules`
  pass for every section, the answer-leak gate passes, and the packet prints
  `Lesson media artifacts: 4` against the four required constructs.
- **The validator verdict is echoed, not re-run.** `validation_pass.json` is a recorded generic
  template pass; it is not re-run here and is not presented as claim-level evidence.
- **Limits.** The four drawings are generic rim-brake schematics, not the learner's model-specific
  manual. D3 stays at 2 under the rubric's own procedure/checklist ceiling, and D8 stays at 2
  because `hint=available` names no hint text and a failed attempt has no stated next move; those
  follow-ups (`t_20a8d28c`, `t_a84d7ba3`) remain open and are not repaired here.
