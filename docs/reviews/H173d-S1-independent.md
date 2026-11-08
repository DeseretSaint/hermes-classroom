# Course quality review: S1

Reviewer: Sentinel (independent, cbqa)
Sample: S1
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
Score: 4
Evidence: plan_one_off.json learner_outcome promises a capability ('Replace one rim-brake pad on a bicycle, then verify the brake by hand before riding') and names the transfer context (the learner fetches the manual for their own brake model); every objectives[].evidence_criteria states an observable act ('The pad model printed in the manual for this brake is written down') and exclusions bound the claim (no hydraulic/disc/e-bike, no live-road test, no certification). The author-run record's stated reason for 3 ('the four are steps of one procedure rather than separate capabilities') is not a condition of the D1 4-anchor, which asks for a stated criterion per objective, a transfer context and exclusions.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_one_off.json objectives run ordinal 1 identify -> 2 remove -> 3 seat and tighten -> 4 verify, and each section's lesson_intent names the manual value that step consumes ('the torque value the manual prints for the caliper fastener'). The schedule arithmetic holds: time_estimate says 1 session x 45 minutes and its rationale states the four sections are steps inside that one session, which lesson_one_off.json mirrors with four segments in the same order. No units[] exist in a v1 document, so no prerequisite edge is decorative, but nothing names a reason for the sequence, which keeps this at 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: All four plan_one_off.json objectives declare evidence_target: procedure while every check_plan[] entry is kind: verification with independent_evidence: false, and lesson_one_off.json check.kind and check.stimulus.format are both verification with three tick items. The attempt therefore stores ticked item ids with evidence_class = self_reported (coursebook/grading.py:40). Rubric D3 lines 147-153 set the 0.1.0 ceiling at 2 for exactly this case; the validator's evidence_target_fit pass answers a different question. The record at docs/reviews/H173a-S1-single-brake-rescored.md scores 3 and its own text says 'the build has no attachment lane'.
Follow-up: t_20a8d28c

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_one_off.json worked_example.steps show four ordered actions and its answer ('The worn pad is out: the model matches the manual, the fastener was loosened with the named key, and the pad is photographed beside it') is the same one-pad removal task as check.reference_answer; learner_explanation names the rule that makes it work (the manual, not this page, carries the pad model, fastener and torque). Ambiguous evidence: 'the model matches the manual' cannot be shown because no manual exists in the artifact, and the example stops at objective 2, so nothing demonstrates the seating or hand-verification judgement the later objectives ask for.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: lesson_one_off.json segments run model ('Read the manual before touching the brake') then three guided segments (loosen only the named fastener, seat and tighten, verify by hand) then one check, one act per segment, in the same order as the four plan sections and inside time_estimate.minutes_per_session = 45. No step calls for material an earlier segment has not modelled. Support does not fade across the three guided segments and no closing segment returns the learner to a path, so 3 rather than 4.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_one_off.json objectives 1-4 all carry support: unverified with empty source_ids, evidence_note states that no manufacturer manual was fetched and that no pad model, fastener size or torque value is stated as fact, and exclusions state what is not claimed. Ambiguous: D6 anchor 2 ('most objectives are unverified') and anchor 3 ('an explicit unverified mark') both describe this same artifact, because 4 of 4 objectives are unverified; 3 is taken because every claim carries an explicit mark and no source id is invented, and a reviewer who applied anchor 2 would score 2 on identical evidence.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_one_off.json sections 1-4 each declare media_need.image.level = required with a distinct construct ('The labelled parts diagram showing pad orientation and seating before the fastener is tightened'), but lesson_one_off.json media contains exactly one visual schematic and no segment or note states why the release-sequence, seating and moving-parts diagrams are absent. The packet prints the mismatch itself: 'Lesson media artifacts: 1' against four required needs. Three of four constructs that the plan calls required have no artifact that can perform them.
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 2
Evidence: lesson_one_off.json check.assistance_policy.hint = available but no hint text exists anywhere in the lesson, and no segment or check field says what the learner does after an item they cannot honestly tick: segment 2 offers only a hazard stop ('Stop if the caliper moves or the fastener will not turn by hand') and check.stimulus.prompt says 'Tick each step only after you have done it'. A failed attempt therefore has no stated next move, which is D8 anchor 2 ('a failure path exists only in the author's head').
Follow-up: t_a84d7ba3


## Reviewer notes

- **This is a recorded fixture, not a live output.** H-172 (`t_fe097fe7`) is still blocked (its
  live three-scope run waits on H-184 `t_742c3242` and H-185 `t_77dbd582`), so no live provider
  artifact exists. Nothing here is a live claim, and this record must not be cited as one. The
  live re-score is a separate follow-up when H-172 lands.
- **Reviewer is independent.** Sentinel (cbqa, adversarial QA) did not author the fixture, the
  rubric, the packet or any of the author-run records this one is compared against. Scores were
  decided from the raw JSON before the author records were opened.
- **Mechanical facts come from the packet; every score cites the raw fixture.** The packet printed
  the deterministic facts (hashes, plan shape, counts, validator verdict), but the fields the
  verdicts actually turn on — `check_plan[].kind`, `check.stimulus.format`, `media_need`
  constructs, `evidence_criteria` text, `exclusions`, segment bodies — were read from the fixture
  JSON, not from the packet summary.
- **The record checker is not self-certifying.** `scripts/course_quality_review.py check` passes
  this record, but the checker has holes found in the same run (a blank `Reviewer:` line passes; a
  score below 3 with `Follow-up: none` passes; an aggregate line such as "Aggregate score: 24 out
  of 32" outside a dimension block passes). See `docs/reviews/H173d-INDEPENDENT-REVIEW.md`
  §"Checker acceptance". A PASS is a format check, not a review.
- **The recorded validator verdict is echoed, not re-run.** No provider call was made, so no
  structural pass is claimed or overturned here.
- **Coverage.** `lesson_one_off.json` covers all four objectives, so D3/D4/D5/D7/D8 were scorable
  from the supplied lesson. D3 = 2 is the rubric's own 0.1.0 ceiling (rubric D3 lines 147-153),
  recorded as decided in `t_20a8d28c`; it is a released limitation, not an open fix.
- **Ambiguity.** D6: anchors 2 ("most objectives are unverified") and 3 ("an explicit unverified
  mark") both describe this artifact, so two reviewers can honestly score 2 and 3 on the same
  evidence. D4: the example's "model matches the manual" cannot be shown because no manual exists.
- **Disagreements with `docs/reviews/H173a-S1-single-brake-rescored.md` (all 3):** D1 = 4 (the
  author's reason for 3 is not a condition of the D1 4-anchor), D3 = 2 (procedure ceiling), D7 = 2
  (four required schematics, one delivered artifact), D8 = 2 (failed attempt has no stated next
  move; hint=available with no hint text).
- **Timing.** One course, packet to checker-PASS record: 3.9 minutes wall clock (see the summary
  doc for the per-step timestamps and the caveat that this is an agent's clock, not a human's).

