# Course quality review: H173-S2-short-japanese-cafe

Reviewer: Quill (rubric author, author-run dry run)
Sample: H173-S2-short-japanese-cafe
Scope: short (recorded v1 fixture, 6 weeks)
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_ja.json` sha256 `1792e24d645741ebcb3b8d69fb06227725c904d30b68216d24de77099c769a90`
- lesson: `tests/fixtures/generation/lesson_ja.json` sha256 `b190e9307e8710f702f9bc8e9ab12820dc702a0608fb9e827dc90cb11d101b92`
- validation: `tests/fixtures/generation/validation_reject_check.json` sha256 `e152c05a71b45999c83a253f719e830da5ba8289e3af2778dfbfd8147c5da359`

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Japanese café basics
- Learner outcome: At a café, greet the staff, order one drink, ask a price and answer a simple follow-up question in Japanese using standard polite forms, with romaji and furigana available as scaffolds.
- Delivery: self_study
- Time estimate: sessions_per_week=3, weeks=6, minutes_per_session=25, basis=model
- Session capacity: 18 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Greet café staff and open the interaction politely (target=production, support=sourced, criteria=2, source_ids=1)
  2. [unit -] Order one drink using a polite request form (target=production, support=unverified, criteria=2, source_ids=0)
  3. [unit -] Distinguish これ / それ / あれ when pointing at menu items (target=discrimination, support=unverified, criteria=1, source_ids=0)
  4. [unit -] Understand a staff follow-up question about drink size (target=comprehension, support=unverified, criteria=2, source_ids=0)
- Objective support: {'sourced': 1, 'unverified': 3}; targets: {'comprehension': 1, 'discrimination': 1, 'production': 2}; objectives with no source_ids: 3/4
- Units: none (v1 document: one implicit unit)
- Sections (4):
  - section 1: Greeting and opening (objective_refs=[1], media_need: image=none/none, audio=none/none)
    lesson_intent: Model one polite greeting, then have the learner produce it cold before seeing romaji removed.
  - section 2: Ordering a drink (objective_refs=[2], media_need: image=none/none, audio=none/none)
    lesson_intent: Model one polite request form, then have the learner order a single drink with it.
  - section 3: This, that and over there (objective_refs=[3], media_need: image=none/none, audio=none/none)
    lesson_intent: Point at three menu items at different distances and choose これ / それ / あれ each time.
  - section 4: Price and follow-up (objective_refs=[4], media_need: image=none/none, audio=none/none)
    lesson_intent: Ask a price, then recognise and answer a size question.
- Check plan entries: 4
  - objective 1: kind=quiz, target=production, notes=Selection check on a greeting, no romaji in the stimulus.
  - objective 2: kind=quiz, target=production
  - objective 3: kind=quiz, target=discrimination
  - objective 4: kind=quiz, target=comprehension
- Exclusions:
  - No claim of native-speaker naturalness: wording and usage still need fresh sourcing.
  - No pronunciation assessment from text or generic TTS.
  - No keigo beyond standard polite forms.
- Plan source_ids: ['SRC_ALPHA']

### Lesson

- Section title: Greeting and opening
- Segments: 3
  1. kind=model, heading=Two phrases you will hear
  2. kind=explain, heading=Why register matters
  3. kind=guided, heading=Say it with romaji visible
- Worked example: prompt=You want to ask for a menu politely.; steps=3
    step 1: Say お願いします with a small bow
    step 2: Wait for the staff member to respond
    step 3: Thank them with ありがとうございます
- Worked example answer present: yes (not reproduced here)
- Learner explanation: Pick the phrase that fits entering a shop and speaking to staff for the first time. Script is shown; romaji is available as a scaffold until you no longer need it.
- Check: kind=quiz, format=selection, target=production, accepted_answers=1, accepted_alternatives=1, rubric_criteria=3, stimulus_items=0
- Rubric criteria: ['polite greeting', 'target script', 'register']
- Assistance policy: hint=after_attempt, answer_marks_evidence_class=hinted
- Scaffolds enabled: ['english_meaning', 'furigana', 'romaji']
- Reference answer present: yes (not reproduced here)
- Lesson sources: ['SRC_ALPHA']
- Lesson media artifacts: 0
- Parent notes: none
- Supervision notes: none

### Validator record

- Recorded verdict: reject
- Recorded criteria:
  - objective_alignment: pass (objective_alignment checked)
  - source_support: pass (source_support checked)
  - factual_correctness: pass (factual_correctness checked)
  - answer_uniqueness: fail (two choices both satisfy the prompt)
  - alternative_coverage: fail (two choices both satisfy the prompt)
  - rubric_consistency: pass (rubric_consistency checked)
  - internal_contradiction: pass (internal_contradiction checked)
  - answer_leakage: pass (answer_leakage checked)
  - hazard_age_appropriateness: pass (hazard_age_appropriateness checked)
  - evidence_target_fit: pass (evidence_target_fit checked)
- Recorded rejections: 1
  - item=check:1, criterion=answer_uniqueness: The stimulus asks for a polite opener but both こんにちは and ありがとうございます are acceptable openers, so the key is ambiguous.
    fix_hint: Make the stimulus name the moment (entering, not leaving) and accept both openers as alternatives.
- Claim verdicts: 0

## Dimension verdicts

### D1 capability_objective_fit
Question: Does the course promise a capability, and do the objectives name observable performances rather than topics?
Score: 2
Evidence: plan_ja.json learner_outcome promises 'greet the staff, order one drink, ask a price and answer a simple follow-up question', but the four objectives cover greeting, ordering, demonstratives and understanding a size question. No objective or check covers 'ask a price', so the outcome is broader than the objectives.
Follow-up: t_73677244

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 2
Evidence: plan_ja.json time_estimate is 3 sessions/week x 6 weeks = 18 sessions, while the plan authors 4 sections (one per objective) and check_plan has 4 entries. The authored content is about a quarter of the declared schedule. Order itself is sound: greeting before ordering before the size follow-up.
Follow-up: t_73677244

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_ja.json objective 1 declares evidence_target=production and the criterion 'Produces a greeting in Japanese script'. lesson_ja.json check is kind=quiz, stimulus.format=selection with three choices, so the learner selects rather than produces. The check's rubric adds 'target script' but a selection item cannot demonstrate production.
Follow-up: t_73677244

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 2
Evidence: lesson_ja.json section_title is 'Greeting and opening', but worked_example.prompt asks for a menu and worked_example.answer is the request phrase お願いします. The check asks for an opener and keys こんにちは, a phrase the model segment never introduces (it teaches お願いします and ありがとうございます). Example and explanation do not teach the case the check assesses.
Follow-up: t_73677244

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 2
Evidence: lesson_ja.json has 3 segments (model, explain, guided), one worked example and one check in a 25-minute session, so the load is plausible. The jump is untaught material: the check expects こんにちは, which appears in no segment, so the learner meets an unstated prerequisite at the assessment.
Follow-up: t_73677244

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 2
Evidence: plan_ja.json objective 1 has support=sourced with source_ids=[SRC_ALPHA]; objectives 2-4 are unverified. lesson_ja.json sources=[SRC_ALPHA] with no indication of which claim the source supports, and the register rule in the explain segment ('standard polite forms are the safe default') carries no source. exclusions honestly refuse a native-speaker naturalness claim, so the honesty is real but the grounding is thin.
Follow-up: t_73677244

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: plan_ja.json sections 1-4 all declare audio=none/none and image=none/none. Objective 4 is 'Understand a staff follow-up question about drink size', a listening target, and section 4's lesson_intent is 'recognise and answer a size question'. Text alone cannot carry that construct. plan exclusions refuse pronunciation assessment from generic TTS, which does not exclude a model audio recording for comprehension.
Follow-up: t_73677244

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 4
Evidence: lesson_ja.json scaffolds declare romaji, furigana and english meaning; the guided segment makes the fade explicit ('cover the romaji and repeat once more; the romaji is a scaffold, not evidence of reading'). hint=after_attempt, and plan exclusions refuse keigo beyond standard polite forms. The learner has a stated scaffold, a fade rule and a bounded claim.
Follow-up: none


## Reviewer notes

- This is a recorded fixture, not an H-172 live output. H-172 (`t_fe097fe7`) was still `todo` on
  2026-11-08, so the card's fixture fallback applies. No live provider call, native-speaker review
  or fetched source is claimed.
- The validator recorded `reject` for `answer_uniqueness` and `alternative_coverage`: two choices
  both satisfy the prompt. That verdict stays the gate and is unchanged by this record. The
  dimension scores are quality findings beside that rejection, not a reversal of it.
- The reviewer is the rubric author. This is an author-run dry run, not an independent review.
  H-173d (`t_99f1cb89`) owns the independent re-score.
- Follow-up card for every dimension below 3: H-173b `t_73677244`. Dimension D8 scored 4 and
  carries no follow-up.
