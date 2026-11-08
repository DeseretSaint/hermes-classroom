# Course quality review: S2

Reviewer: Sentinel (independent, cbqa)
Sample: S2
Scope: short
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Inputs

- plan: `tests/fixtures/generation/plan_ja.json` sha256 `58865aec3544a4b2ddc72ed32918f90d756bf015f57ae9944e49e170754d55ca`
- lesson: `tests/fixtures/generation/lesson_ja.json` sha256 `983a6cd7ae3761b530ed3c5bf9916798590808d93fdc14ee63404e950ff33e15`
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
Score: 4
Evidence: plan_ja.json learner_outcome names four observable capabilities (choose the greeting that opens the interaction, order one drink, pick a menu item by distance, answer a written question about drink size) and every objectives[].evidence_criteria states the act ('Selects the greeting option when the interaction opens', 'Rejects the thanks and farewell options for the same moment'); exclusions bound the claim (no native-speaker naturalness, no pronunciation assessment from generic TTS, no keigo beyond standard polite forms) and the transfer context is named ('At a cafe'). I score the artifact, not the author's reason for 3.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_ja.json time_estimate is sessions_per_week=1 x weeks=4 = 4 sessions against 4 authored sections and 4 check_plan entries, so the schedule arithmetic holds; order runs greeting (section 1) -> polite request (section 2) -> demonstratives (section 3) -> written size question (section 4), and each sections[].objective_refs points at the objective it teaches. No units[] exist in a v1 document and no section states a reason for the order, which keeps this at 3 not 4.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: plan_ja.json objective 2 still declares evidence_target: production while check_plan[1] is kind: quiz with no stimulus format recorded, and the only check supplied is the single format: selection item in lesson_ja.json, which belongs to objective 1. Checks for objectives 2-4 cannot be read in the supplied artifact, so D3 cannot reach 3 for the course; and a selection lane for 'Order one drink using a polite request form' is the D3 anchor-1 mismatch (selection quiz for production) unless a typed response is intended and merely unstated.
Follow-up: t_7f46fb7f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_ja.json worked_example.steps apply the identification rule step by step ('Set aside the thanks and the farewell, because neither one opens an interaction' then 'Choose the remaining phrase') and learner_explanation names that rule; worked_example.prompt equals check.stimulus.prompt, so the example and the check are the same task. The example's answer is 'the remaining phrase, the standard daytime greeting' and never the script form the check keys, so the example teaches the rule but cannot show the answer it is judged on.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 2
Evidence: The target form is never presented in the lesson: lesson_ja.json segments[0].body teaches the request, thanks and farewell phrases in script, segments[1] and segments[2] call the target only 'the standard daytime greeting', and the script form appears first in check.stimulus.choices and accepted_answers. A learner must therefore recognise a script form the session never modelled - an unstated prerequisite. The arc itself (model -> explain -> guided -> check, three segments, 25 minutes) is sound, which is why this sits between D5 anchor 1 and anchor 2 rather than at 1.
Follow-up: t_fdf16735

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_ja.json objective 1 is support: sourced with source_ids [SRC_ALPHA], objectives 2-4 are explicitly unverified, evidence_note names what is unverified ('Objectives 2-4 and the request and thanks phrases are unverified in this recorded sample') and says a teacher must check them, and exclusions state what is not claimed. Ambiguous: SRC_ALPHA cannot be resolved to a fetched source from the supplied artifacts - validation_reject_check.json carries no source ledger, and the only ledger entry for SRC_ALPHA in the tree is in validation_pass.json, a different record. 3 is the most the supplied artifact supports, and 4 is not reachable without the ledger.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: lesson_ja.json segments[2] (the guided 'Tell the greeting apart' segment) instructs 'Say each phrase aloud with the romaji visible; the romaji is a scaffold, not evidence of reading', but plan_ja.json sections 1-4 all declare media_need.audio.level = none with media_need.construct = '' and lesson_ja.json media is empty. A speaking act is assigned with no model recording, and the audio decision carries no construct or stated reason, which is D7 anchor 2 ('the need is real but the plan leaves it undecided').
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_ja.json check.scaffolds enables romaji, furigana and english_meaning, segment 2 states the fade ('the romaji is a scaffold, not evidence of reading'), and check.assistance_policy is hint=after_attempt with answer_marks_evidence_class=hinted; delivery is self_study so there is no parent copy to contradict. Anchor 4 is not met because the policy names no hint text the learner ever sees and nothing says what evidence a retry produces, so 3 rather than the 4 in the repair record.
Follow-up: none


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
- **Artifact provenance defect.** The handoff comment for this sample names `plan_ja.json` sha256
  `160f8c7e...`. No committed version of that file has ever had that hash: master 4358249 and
  branch `wt/h173b-s2-quality` both carry `58865aec3544a4b2ddc72ed32918f90d756bf015f57ae9944e49e170754d55ca`,
  and `git log --all -S160f8c7e` finds nothing. I scored the committed artifact (`58865aec`), as
  `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md` also does. The comment is wrong, not the
  fixture.
- **Coverage.** The plan authors four sections but the supplied lesson covers objective 1 only, so
  objectives 2-4's checks cannot be read; D3 = 2 rests on that plus the `production`-with-a-quiz
  pairing in `check_plan[1]`. D4/D5 are read from the one supplied lesson.
- **Ambiguity.** D6: `SRC_ALPHA` cannot be resolved to a fetched ledger from the supplied
  artifacts (`validation_reject_check.json` carries no source ledger), so 4 is not reachable and 3
  is the maximum the artifact supports. D5: the artifact sits between anchor 1 (the check requires
  a script form the lesson never models) and anchor 2 (the arc itself is sound); I chose 2.
- **Disagreements with `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md`:** D1 = 4 vs 3,
  D3 = 2 vs 3 (objective 2 still pairs `production` with `kind: quiz`; the repair record's evidence
  only covers objective 1), D5 = 2 vs 3 (naming the function is not presenting the form — this is
  the point cinder's comment asked me to name if I disagreed), D7 = 2 vs 3 (the lesson instructs
  saying phrases aloud while every `media_need.audio.level` is `none` with an empty construct),
  D8 = 3 vs 4 (no hint text exists and no retry evidence is stated).
- **The validator verdict stays `reject`.** This record does not overturn it: the recorded
  `answer_uniqueness`/`alternative_coverage` rejection is on the pre-repair artifact, and the
  repaired pair was never sent to the validator. D3 = 2 is consistent with that.

