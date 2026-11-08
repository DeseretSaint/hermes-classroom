# Course quality review: H173b-S2-short-japanese-cafe-repaired

Reviewer: Cinder (repair author, author-run dry run)
Sample: H173b-S2-short-japanese-cafe-repaired
Scope: short
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_ja.json` sha256 `58865aec3544a4b2ddc72ed32918f90d756bf015f57ae9944e49e170754d55ca`
- lesson: `tests/fixtures/generation/lesson_ja.json` sha256 `983a6cd7ae3761b530ed3c5bf9916798590808d93fdc14ee63404e950ff33e15`
- validation: `tests/fixtures/generation/validation_reject_check.json` sha256 `e152c05a71b45999c83a253f719e830da5ba8289e3af2778dfbfd8147c5da359`

The plan and lesson hashes are the repaired artifacts. The validation hash is unchanged from
`docs/reviews/H173-S2-short-japanese-cafe.md`; that record is the pre-repair review and stays as
history. This record supersedes its dimension scores for S2, not its validator reading.

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
  - No pronunciation assessment from text or generic TTS.
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
Score: 3
Evidence: `plan_ja.json` learner_outcome now names only what the four objectives deliver: choose the greeting that opens the interaction, order one drink, choose a demonstrative by distance, and answer a written size question. The price promise is gone. Objective 1's title and `evidence_criteria` ("Selects the greeting option when the interaction opens", "Rejects the thanks and farewell options for the same moment") are observable acts, and the exclusions bound the claim (no native-speaker naturalness, no keigo beyond standard polite forms).
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: `plan_ja.json` `time_estimate` is now sessions_per_week=1 x weeks=4 = 4 sessions for the 4 authored sections and 4 `check_plan` entries, so the schedule arithmetic holds. Each section's `objective_refs` points at exactly the objective it teaches, and the order runs greeting (section 1) -> polite request (section 2) -> demonstratives (section 3) -> written size follow-up (section 4); the size question lands after the request and the menu-item work it depends on.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 3
Evidence: Objective 1 and `check_plan[0]` and `lesson_ja.json` `check.evidence_target` all declare `discrimination`; the label `production` on a `stimulus.format=selection` item is gone. The check is a three-phrase selection, and its rubric criteria ("Chooses the phrase that opens the interaction", "Sets aside the thanks and farewell options", "Matches the chosen phrase to Japanese script") are objective 1's criteria in observable form: the learner selects among visible options and the record does not claim a typed production.
Follow-up: none

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: `lesson_ja.json` `worked_example.prompt` is now the same task as `check.stimulus.prompt` ("Which phrase opens the interaction politely?"), not the old menu request. Its three steps apply the rule the explain segment names — the opening phrase is neither the request, thanks nor farewell — and the guided segment rehearses the same elimination. The example answer, the explanation and the check all point at the same discriminated phrase.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: The arc is model (three function phrases: request, thanks, farewell) -> explain (greeting comes first, register rule, identification rule) -> guided (set aside the thanks and farewell, choose the remainder) -> check (same three-phrase choice). Two of the check's three options are taught by script and gloss in the model segment, and the third is identified by the rule the guided segment rehearses, so no phrase is required cold; three segments, one worked example and one check fit the 25-minute session.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: `plan_ja.json` `evidence_note` now ties SRC_ALPHA to the greeting wording and register of objective 1, and marks objectives 2-4 plus the request, thanks and farewell phrases `unverified` with the consequence stated (a teacher must check them before a learner relies on them). The explain segment repeats that the register rule is unverified in this recorded sample, and the exclusions state what is not claimed. SRC_ALPHA is the fixture's source id and no fetched ledger exists here, which this record states rather than claiming a fetch.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 3
Evidence: Every `plan_ja.json` section declares a typed `media_need` with image=none/none and audio=none/none, and that is now honest: objective 4 is restated as comprehension of a written staff question, section 3 describes item distances in text, and section 1 asks for a selection over written phrases, so no construct requires audio or a visual and no media decision is left undecided. The lesson claims no media artifact and `lesson_ja.json` `media` is empty.
Follow-up: none

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 4
Evidence: `lesson_ja.json` `check.scaffolds` enables romaji, furigana and english_meaning; the guided segment states the fade ("the romaji is a scaffold, not evidence of reading"); `assistance_policy` is hint=after_attempt with answer_marks_evidence_class=hinted; and the plan exclusions bound the claim. A learner who needs support sees it, the support is labelled as support, and a failed attempt produces a hinted retry rather than a hidden advance.
Follow-up: none

## Reviewer notes

- This is the repaired S2 fixture, not an H-172 live output. H-172 (`t_fe097fe7`) was still `todo`
  and blocked on its integration parents on 2026-11-08, so no live short-scope output exists to
  re-check. H-172 and H-173d (`t_99f1cb89`) must run this packet on the live short course when it
  lands; a fixture score is not a live score.
- The validator record is unchanged and still reads `reject` (`answer_uniqueness`,
  `alternative_coverage`). It is the recorded verdict on the pre-repair artifact. The repaired
  artifact was not sent to the validator in this card, so this record claims no structural pass
  and does not overturn the rejection.
- The reviewer is the repair author. This is an author-run dry run, not an independent review.
  H-173d owns the independent re-score and the 15-minute timing measurement.
- A constraint the repair had to respect: `generation.assert_no_answer_leak` (and
  `tests/test_generation.py:1243`) refuses any accepted answer or accepted alternative string in
  the learner narrative, so a generated lesson cannot print the phrase its closed check keys. The
  section therefore teaches the three function phrases and the identification rule, and the
  greeting's own script is met among the check's visible choices. If the leak rule is ever relaxed
  for a taught target item, D4 and D5 can be raised further; this record does not pretend the
  greeting is modelled in the narrative.
- No source was fetched, no native-speaker review was invented, and no provider call was made.
  The fixture's SRC_ALPHA is a recorded sample id, not a fetched page.
- The unchanged validator record still describes the pre-repair choice set, while the repaired
  check keeps the same three choices; the record's fix_hint (name the moment, accept both openers)
  was not applied, because doing so would resolve the structural rejection this card must leave in
  place.
