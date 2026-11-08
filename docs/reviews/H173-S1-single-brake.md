# Course quality review: H173-S1-single-brake

Reviewer: Quill (rubric author, author-run dry run)
Sample: H173-S1-single-brake
Scope: single (recorded v1 fixture; scope not declared)
Validator verdict: pass

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_one_off.json` sha256 `8c0b753ea5d44f9472fac9ac1211b98301b04703dabc6802dcb0a7aa91af5af7`
- lesson: `tests/fixtures/generation/lesson_one_off.json` sha256 `fe07ff3764b59f551975fd57ebb407d40c392a7d5ff569332f012a6feaee1d98`
- validation: `tests/fixtures/generation/validation_pass.json` sha256 `9da8cc1583094441fe790b10b58a0a1a5ec071b6bbb15337c615b28d53b19c90`

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Replace a bicycle brake pad
- Learner outcome: Replace one rim-brake pad on a bicycle, then verify the brake by hand before riding, following the manufacturer's manual.
- Delivery: self_study
- Time estimate: sessions_per_week=1, weeks=1, minutes_per_session=45, basis=none
- Session capacity: 1 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Identify the correct replacement pad for the brake model (target=procedure, support=unverified, criteria=1, source_ids=0)
  2. [unit -] Remove the worn pad without damaging the caliper (target=procedure, support=unverified, criteria=1, source_ids=0)
  3. [unit -] Seat and tighten the new pad to the manual's specification (target=procedure, support=unverified, criteria=2, source_ids=0)
  4. [unit -] Verify the brake by hand before riding (target=procedure, support=unverified, criteria=2, source_ids=0)
- Objective support: {'unverified': 4}; targets: {'procedure': 4}; objectives with no source_ids: 4/4
- Units: none (v1 document: one implicit unit)
- Sections (4):
  - section 1: Identify the pad (objective_refs=[1], media_need: image=none/none, audio=none/none)
    lesson_intent: Match the pad model to the manufacturer's manual before touching the brake.
  - section 2: Remove the worn pad (objective_refs=[2], media_need: image=none/none, audio=none/none)
    lesson_intent: Remove the worn pad with the fastener the manual names, without damaging the caliper.
  - section 3: Seat and tighten (objective_refs=[3], media_need: image=none/none, audio=none/none)
    lesson_intent: Seat the new pad square and tighten the fastener to the manual's specification.
  - section 4: Verify by hand (objective_refs=[4], media_need: image=none/none, audio=none/none)
    lesson_intent: Run the manual's hand-verification checklist before any ride.
- Check plan entries: 4
  - objective 1: kind=verification, target=procedure
  - objective 2: kind=verification, target=procedure
  - objective 3: kind=verification, target=procedure
  - objective 4: kind=verification, target=procedure
- Exclusions:
  - Does not certify the procedure; authoritative manufacturer documentation and an expert check are required.
  - No live-road test is part of this brief.
  - Not for hydraulic, disc or e-bike brake systems.
- Plan source_ids: none

### Lesson

- Section title: Identify and remove
- Segments: 2
  1. kind=model, heading=Read the manual first
  2. kind=guided, heading=Remove with the listed tool
- Worked example: prompt=The manual lists pad model BR-42 and a 5 mm hex key.; steps=3
    step 1: Lay out the new pad and the 5 mm key
    step 2: Confirm the pad model matches BR-42
    step 3: Loosen the fastener and slide the worn pad out
- Worked example answer present: yes (not reproduced here)
- Learner explanation: Work through the checklist with the manual open. This is a verification list, not a quiz: you confirm each step honestly.
- Check: kind=verification, format=verification, target=procedure, accepted_answers=1, accepted_alternatives=0, rubric_criteria=3, stimulus_items=3
- Rubric criteria: ['checklist completed', 'model matched', 'listed tool used']
- Assistance policy: hint=available, answer_marks_evidence_class=none
- Scaffolds enabled: none
- Reference answer present: yes (not reproduced here)
- Lesson sources: none
- Lesson media artifacts: 0
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
Evidence: plan_one_off.json learner_outcome names a capability ('Replace one rim-brake pad ... verify the brake by hand before riding') and all four objectives name observable acts with criteria. Objective 3's criterion 'Fastener tightened to the manual's torque' is observable. The four objectives are steps of one procedure rather than separate capabilities, which is coherent for a single-scope task but keeps this at 3.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 2
Evidence: plan_one_off.json objectives run identify (1), remove (2), seat/tighten (3), verify (4), which is the right order, but time_estimate is sessions_per_week=1 x weeks=1 = 1 session for 4 authored sections. The declared sequence cannot fit the declared schedule; section 3 depends on the removal in section 2 and no schedule holds that sequence.
Follow-up: t_c7fff5b4

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_one_off.json declares evidence_target=procedure on all four objectives. lesson_one_off.json check is kind=verification with format=verification and three self-ticked items; learner_instructions say 'Tick what is true'. A tick attests completion, it does not evidence a performed procedure, so the check is weaker than the target it claims.
Follow-up: t_c7fff5b4

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 2
Evidence: lesson_one_off.json worked_example.answer is 'Worn pad removed with the listed key', matching its three steps. check.reference_answer is 'Both pads replaced, wheel seated, lever firm with 2 mm clearance', a different task (both pads, seating, clearance). The example teaches removal while the reference answer describes a full replacement; a reviewer cannot tell which task the lesson assesses.
Follow-up: t_c7fff5b4

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 2
Evidence: lesson_one_off.json section_title is 'Identify and remove' with 2 segments and a 3-item check, covering plan objectives 1-2. plan_one_off.json authors 4 sections in one 45-minute session and sections 3-4 (seat/tighten, verify by hand) are never modelled in this lesson, so the session arc stops before the plan's own outcome.
Follow-up: t_c7fff5b4

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 2
Evidence: plan_one_off.json objectives all carry support=unverified with 0/4 having source_ids; plan source_ids and lesson source lists are empty. learner_outcome requires 'following the manufacturer's manual' and objective 3 cites a torque specification, so a load-bearing safety claim has no fetched source. The unverified marks are honest, which is why this is 2 and not 1.
Follow-up: t_c7fff5b4

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_one_off.json sections 1-4 all declare media_need image=none/none and audio=none/none. Objective 1 asks the learner to identify the correct replacement pad and section 2 asks them to find the caliper fastener, both visual discrimination tasks carried only by prose. The absence is honest, but a procedure manual's diagram is exactly the construct-carrying media D7 asks for.
Follow-up: t_c7fff5b4

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_one_off.json assistance_policy hint=available, and the guided segment states a stop condition: 'Stop if the caliper moves or the fastener will not turn by hand'. plan_one_off.json exclusions refuse hydraulic/disc/e-bike systems and require an expert check. There is no retry path after a failed step beyond the stop rule, so 3 rather than 4.
Follow-up: none


## Reviewer notes

- This is a recorded fixture, not an H-172 live output. H-172 (`t_fe097fe7`) was still `todo` on
  2026-11-08, so the card's fixture fallback applies. No live provider call is claimed.
- The validator record supplied is `validation_pass.json`, a generic recorded pass whose criterion
  reasons are template text, not claim-specific. It is echoed here as recorded and its truth is
  not changed; its evidence strength is itself weak.
- The reviewer is the rubric author. This is an author-run dry run, not an independent review.
  H-173d (`t_99f1cb89`) owns the independent re-score and the 15-minute usability check.
- Follow-up card for every dimension below 3: H-173a `t_c7fff5b4`. Dimensions D1 and D8 scored 3
  and carry no follow-up.
