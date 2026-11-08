# Course quality review: H173d-D7-S2-media

Reviewer: Cinder (backend kernel, author-run media re-score)
Sample: H173d-D7-S2-media
Scope: short
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_ja.json` sha256 `4654c8baa158056e104faf45abd82e5b0be2b49705477573dadbccd54189a74d`
- lesson: `tests/fixtures/generation/lesson_ja.json` sha256 `6b806e940238fa77087ecae9ce4fd3838ebe14312e7aca1289c0f42718243c24`
- validation: `tests/fixtures/generation/validation_reject_check.json` sha256 `e152c05a71b45999c83a253f719e830da5ba8289e3af2778dfbfd8147c5da359`

## Observed facts

Facts are extracted mechanically. They are not scores and they do not replace the
reviewer's reading.

- Plan schema: coursebook.plan.v1 (no plan_schema)
- Scope: not declared (v1 document)
- Title: Japanese café basics
- Learner outcome: At a café, choose the greeting that opens the interaction, order one drink, pick out a menu item by its distance, and answer a written question about drink size in Japanese, with romaji and furigana available as scaffolds.
- Delivery: self_study
- Time estimate: sessions_per_week=1, weeks=4, minutes_per_session=25, basis=model
- Session capacity: 4 session(s) available for 4 authored section(s) and 0 declared unit(s)
- Objectives (4):
  1. [unit -] Choose the greeting that opens a café interaction (target=discrimination, support=sourced, criteria=2, source_ids=1)
  2. [unit -] Order one drink using a polite request form (target=production, support=unverified, criteria=2, source_ids=0)
  3. [unit -] Distinguish これ / それ / あれ by the item's distance from the speaker (target=discrimination, support=unverified, criteria=1, source_ids=0)
  4. [unit -] Understand a written staff question about drink size (target=comprehension, support=unverified, criteria=2, source_ids=0)
- Objective support: {'sourced': 1, 'unverified': 3}; targets: {'comprehension': 1, 'discrimination': 2, 'production': 1}; objectives with no source_ids: 3/4
- Units: none (v1 document: one implicit unit)
- Sections (4):
  - section 1: Greeting and opening (objective_refs=[1], media_need: image=none/none, audio=none/none)
    lesson_intent: Contrast the request, thanks and farewell phrases, teach the register rule, then have the learner choose the greeting that opens the interaction.
  - section 2: Ordering a drink (objective_refs=[2], media_need: image=none/none, audio=none/none)
    lesson_intent: Model one polite request form, then have the learner order a single drink with it.
  - section 3: This, that and over there (objective_refs=[3], media_need: image=none/none, audio=none/none)
    lesson_intent: Describe three menu items at different distances and have the learner choose これ / それ / あれ for each.
  - section 4: Drink size and follow-up (objective_refs=[4], media_need: image=none/none, audio=none/none)
    lesson_intent: Read a written staff question about drink size, then answer with one of the offered sizes.
- Check plan entries: 4
  - objective 1: kind=quiz, target=discrimination, notes=Selection check on the opening phrase; the three script options are the stimulus, and two of them are the thanks and farewell taught in the section.
  - objective 2: kind=quiz, target=production
  - objective 3: kind=quiz, target=discrimination
  - objective 4: kind=quiz, target=comprehension
- Exclusions:
  - No claim of native-speaker naturalness: wording and usage still need fresh sourcing.
  - No pronunciation assessment from text or generic TTS, and no model recording is shipped in this sample: the checks are typed selections and romaji is a reading scaffold, not a pronunciation target.
  - No keigo beyond standard polite forms.
- Plan source_ids: ['SRC_ALPHA']

### Lesson

- Section title: Greeting and opening
- Segments: 3
  1. kind=model, heading=Three phrases at the counter
  2. kind=explain, heading=Why register and timing matter
  3. kind=guided, heading=Tell the greeting apart
- Worked example: prompt=You walk into a café and the staff look up. Which phrase opens the interaction politely?; steps=3
    step 1: Notice the moment: you are entering and greeting, before ordering or leaving
    step 2: Set aside the thanks and the farewell, because neither one opens an interaction
    step 3: Choose the remaining phrase: it is the standard daytime greeting
- Worked example answer present: yes (not reproduced here)
- Learner explanation: At the check, three phrases are shown. You already know the thanks and the farewell, so set them aside; the remaining phrase is the standard daytime greeting for entering a shop. Romaji stays available as a scaffold until you no longer need it.
- Check: kind=quiz, format=selection, target=discrimination, accepted_answers=1, accepted_alternatives=1, rubric_criteria=3, stimulus_items=0
- Rubric criteria: ['polite greeting', 'register', 'script recognition']
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
Score: 4
Evidence: plan_ja.json learner_outcome names four observable capabilities (choose the greeting that opens the interaction, order one drink, pick a menu item by its distance, answer a written question about drink size) and every objectives[].evidence_criteria states the act ('Selects the greeting option when the interaction opens', 'Rejects the thanks and farewell options for the same moment'); exclusions bound the claim (no native-speaker naturalness, no pronunciation assessment, no keigo beyond standard polite forms) and the transfer context is named ('At a cafe').
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_ja.json time_estimate is sessions_per_week=1 x weeks=4 = 4 sessions against 4 authored sections and 4 check_plan entries, so the schedule arithmetic holds; order runs greeting (section 1) -> polite request (section 2) -> demonstratives (section 3) -> written size question (section 4), and each sections[].objective_refs points at the objective it teaches. No units[] exist and no section states a reason for the order, so 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_ja.json objective 2 still declares evidence_target=production while check_plan[1] is kind=quiz with no stimulus format recorded, and the only check supplied is the single format=selection item in lesson_ja.json, which belongs to objective 1; checks for objectives 2-4 cannot be read in the supplied artifact, and a selection lane for 'Order one drink using a polite request form' is the rubric's D3 anchor-1 mismatch unless a typed response is intended and merely unstated.
Follow-up: t_7f46fb7f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_ja.json worked_example.steps apply the identification rule step by step ('Set aside the thanks and the farewell, because neither one opens an interaction' then 'Choose the remaining phrase') and learner_explanation names that rule; worked_example.prompt equals check.stimulus.prompt, so example and check are the same task. The answer is 'the remaining phrase, the standard daytime greeting' and never the script form the check keys, so 3 not 4.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 2
Evidence: The target form is never presented in lesson_ja.json: segments[0].body teaches the request, thanks and farewell phrases in script, segments[1] and segments[2] call the target only 'the standard daytime greeting', and the script form first appears in check.stimulus.choices and accepted_answers. A learner must recognise a script form the session never modelled, which is D5 anchor 2's unstated prerequisite; the model -> explain -> guided -> check arc is otherwise sound.
Follow-up: t_fdf16735

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_ja.json objective 1 is support=sourced with source_ids [SRC_ALPHA], objectives 2-4 are explicitly unverified, evidence_note names what is unverified ('Objectives 2-4 and the request and thanks phrases are unverified in this recorded sample') and says a teacher must check them, and exclusions state what is not claimed. SRC_ALPHA cannot be resolved to a fetched ledger from the supplied artifacts, so 3 is the most the artifact supports and 4 is not reachable.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: plan_ja.json sections 1-4 declare image=none/none and audio=none/none with construct '', and lesson_ja.json media is empty. The old say-it-aloud line is replaced by 'Read each phrase silently with the romaji visible; no recording ships with this sample', lesson_ja.json says the romaji is a scaffold rather than evidence, and plan exclusions state the checks are typed selections with no pronunciation target - so no spoken act is assigned, the none decision has a stated reason, and D7 anchor 3 is met.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_ja.json check.scaffolds enables romaji, furigana and english_meaning, segment 3 states the fade ('the romaji is a scaffold, not evidence of reading'), and check.assistance_policy is hint=after_attempt with answer_marks_evidence_class=hinted; delivery is self_study so there is no parent copy to contradict. Anchor 4 is not met because the policy names no hint text the learner ever sees and no retry evidence is stated, so 3 not 4.
Follow-up: none


## Reviewer notes

- **This is a recorded fixture re-score, not a live provider run.** H-172 (`t_fe097fe7`) is still
  blocked, so no live short-scope output is claimed and this record must not be cited as one.
- **Reviewer is the engineer who edited the fixtures.** Cinder (backend kernel) made the media
  repair in this branch, so this is an author-run re-score, not an independent review. The
  independent D7 finding in `docs/reviews/H173d-S2-independent.md` and the earlier author record
  `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md` are not edited.
- **What changed.** `plan_ja.json` and `lesson_ja.json`. The say-it-aloud instruction in
  `lesson_ja.json` segments[2] is gone; it now reads "Read each phrase silently with the romaji
  visible; no recording ships with this sample". Lesson `media` stays empty and every section
  keeps `audio=none/none` with an empty construct, while the plan exclusions now state that no
  model recording ships because every check is a typed selection and romaji is a reading
  scaffold, not a pronunciation target.
- **Why no recording was added.** The alternative fix — declaring a required model recording —
  was probed and rejected: the generation rules pair one lesson with every section, and sections
  2-4 have no spoken target, so a lesson audio item is refused for those sections. Removing the
  spoken act leaves no construct-requiring audio need, which is the honest `none`.
- **The validator verdict stays `reject`.** It belongs to the pre-repair artifact; the repaired
  pair was never re-sent to the validator and this record claims no new structural pass.
- **Limits.** D3 stays at 2 (objective 2 still pairs `production` with a quiz, and objectives 2-4
  have no readable check) and D5 stays at 2 (the lesson never models the こんにちは script form the
  check keys). Those follow-ups (`t_7f46fb7f`, `t_fdf16735`) remain open and are not repaired
  here.
