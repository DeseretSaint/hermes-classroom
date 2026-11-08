# Course quality review: H173a-S1-single-brake-rescored

Reviewer: Cinder (backend kernel, author-run re-score of the repaired fixture)
Sample: H173a-S1-single-brake-rescored
Scope: single
Validator verdict: pass

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_one_off.json` sha256 `fcca64504652d4bf087c275350e2fb7bf746dec32aabc1efd45ead1e93ea400f`
- lesson: `tests/fixtures/generation/lesson_one_off.json` sha256 `a96a65595bd094fe01abdbd91da1006d2bb8e08f614fe8a7c05133aee944fc2c`
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
Score: 3
Evidence: plan_one_off.json learner_outcome names a capability ('replace one rim-brake pad ... verify the brake by hand before riding') and all four objectives name observable acts with evidence_criteria; the four are steps of one procedure rather than separate capabilities, which keeps this at 3.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_one_off.json objectives run identify (1) -> remove (2) -> seat and tighten (3) -> verify (4); each later step consumes the earlier one, each section's lesson_intent names the manual value that step needs, and time_estimate plus its rationale hold the four steps inside one 45-minute session. lesson_one_off.json walks the same four steps in that order, so the schedule arithmetic holds for a single-scope task.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 3
Evidence: plan_one_off.json check_plan for objectives 2 and 4, and lesson_one_off.json stimulus items 2 and 3, ask the learner to confirm a photo of the worn pad beside the loosened fastener and a second person's check of the lever and free wheel. The criteria are the objectives' criteria in observable form and the learner instructions label the result a self-report, so the check no longer presents a tick alone as procedure evidence; the build has no attachment lane, which keeps this at 3 rather than 4.
Follow-up: none

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_one_off.json worked_example has four ordered steps and an answer ('the worn pad is out: the model matches the manual, the fastener was loosened with the named key, and the pad is photographed beside it') that names the same one-pad removal task as check.reference_answer and the objective set. learner_explanation names the rule that makes it work: the manual, not the page, carries the values.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_one_off.json section_title 'Replace one brake pad' walks model -> guided -> guided -> guided -> one verification check, one concept per segment (read the manual, remove, seat and tighten, verify), and the four plan sections appear in the same order inside the 45-minute estimate. No step calls for material an earlier segment has not modelled.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: all four plan_one_off.json objectives carry support=unverified with no source_ids; evidence_note states no manufacturer manual was fetched and no pad model, fastener size or torque value is stated as fact; exclusions state that the brake model is unknown and that the learner must fetch the manual. No citation was invented; the lack of per-claim source mapping keeps this at 3.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: each of the four plan_one_off.json sections declares media_need with a construct and image=required/schematic (pad and fastener, release sequence, seating orientation, moving parts) while audio is honestly none/none; lesson_one_off.json media carries one visual/schematic item with structured facts and a text equivalent, so the visual discrimination step has the media it needs. The schematic supports rather than grades the work, so 3.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_one_off.json assistance_policy sets hint=available; the segment 'Loosen only the named fastener' states the stop condition ('stop if the caliper moves or the fastener will not turn by hand'); plan exclusions refuse hydraulic, disc and e-bike systems and require an expert check. There is no retry path beyond the stop rule, so 3 rather than 4.
Follow-up: none


## Reviewer notes

- This record is a re-score of the repaired recorded fixture, not a live provider run. H-172
  (`t_fe097fe7`) was still running when this was written, so no live single-scope output is
  claimed here. The live re-check of these same dimensions belongs to H-173d (`t_99f1cb89`),
  which re-scores H-172's single, short and full outputs independently.
- The reviewer is the engineer who made the fixture repair (Cinder, backend kernel). This is an
  author-run re-score, not an independent review. The original author-run record
  `docs/reviews/H173-S1-single-brake.md` is not edited; it stays as the record of the sample
  before the repair.
- The validator record supplied is `tests/fixtures/generation/validation_pass.json`, a recorded
  generic template pass. It is echoed as recorded and its truth is neither changed nor
  strengthened here; its `claim_verdicts` entry is unrelated template text, so the pass is weak
  evidence and is not presented as a claim-level check of the brake procedure.
- What changed: `tests/fixtures/generation/plan_one_off.json` and
  `tests/fixtures/generation/lesson_one_off.json` only. The plan keeps the four objectives and
  four sections, states that the four sections are steps inside one 45-minute session, adds the
  manual-is-unknown / no-value-claimed note and exclusions, declares a required labelled
  schematic per section, and asks the checklist to confirm the photo and the second person's
  check. The lesson now walks all four steps (model, remove, seat, verify) with one check and
  carries the schematic media item. No validator, grading, RPC, schema or rubric behavior
  changed.
- The repaired pair passes the deterministic generation rules (`enforce_plan_rules` and
  `enforce_lesson_rules`) in the test suite, including the required-media rule that the lesson
  must produce the required schematic. The independent model validator was not re-run, so this
  record adds no new structural pass of its own.
- Verification run at commit time: `python3 -m unittest discover -s tests -t .` ran 2259 tests
  with 4 pre-existing failures in `tests.test_contracts.V3AmendmentTest` (the same 4 fail on
  master 38ecc22 and on this branch's base e69746c, and none touch this work); every other test
  passes, 1 skipped. `python3 scripts/check-docs-truth.py --skip-tests` is PASS.
- The checklist records the photo and second-person items as the learner's own confirmation; this
  build has no attachment or observer lane, so the attempt's evidence class stays self-reported.
  Nothing in the plan, lesson or this record claims the photo or the confirmation reached the
  backend.
- Limits that keep the scores at 3 rather than 4: no fetched manufacturer manual and therefore no
  per-claim source, no second check sampling the same procedure, no retry arc beyond the stop
  rule, and the schematic supports the procedure rather than being its graded evidence.
- The v1 plan document still describes one lesson per authored section in the live pipeline. This
  record reviews the fixture pair as a single-scope course sample (one session, one lesson arc
  over the four steps) and does not claim the live pipeline already produces that shape. H-173d
  and H-172 own the live claim.
- No dimension was moved to a score of 3 to make the sample pass, and the rubric was not edited.
  D2 was the one dimension the old fixture could not reach 3 on, because a v1 one-off plan can
  only author two or more sections; the repair states the four sections as steps of one session
### Superseded bytes (H-173d D8 fix)

The lesson bytes this record scored are superseded. `tests/fixtures/generation/lesson_one_off.json`
now has sha256 `22e88f7d676c469d96dcc420cb4befbca24ced3db86d0e1b5ed699dffb40fd3a` (the recorded
`a96a6559...` is the pre-fix lesson). The change is `check.learner_instructions` only: it now
states the hint text that `assistance_policy.hint = available` claims and the next move after an
item the learner cannot honestly tick. No score in this record is rewritten; the D8 re-score with
new evidence is `docs/reviews/H173d-S1-D8-rescore.md`.


