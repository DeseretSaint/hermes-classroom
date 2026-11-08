# Course quality review: S2 (re-score on the repaired model segment)

Reviewer: Sentinel (independent, cbqa)
Sample: S2
Scope: short
Validator verdict: reject

This record is not a mastery score, an engagement metric, a badge or a leaderboard. The eight 1-4 verdicts below are reviewer judgments about course design; they are never summed, averaged or shown to a learner. The validator's structural pass remains the gate (`docs/COURSE-QUALITY-RUBRIC.md`).

## Artifact provenance

- Scored commit: `bb6efd6d163489c28ac7836fa62c3628ad2321bf` ("H-173d follow-up: present the keyed greeting in the S2 model segment"), branch `wt/h173d-s2-taught` (based on `719e507`), not pushed.
- Working tree at scoring time was clean for the fixture; `git show bb6efd6:tests/fixtures/generation/lesson_ja.json` hashes to the same digest as the working file.
- Supersedes nothing. The pre-repair record `docs/reviews/H173d-S2-independent.md` (fixture `983a6cd7…`) stays as the score of the artifact it read.

## Inputs

- plan: `tests/fixtures/generation/plan_ja.json` sha256 `58865aec3544a4b2ddc72ed32918f90d756bf015f57ae9944e49e170754d55ca` (unchanged by the repair)
- lesson: `tests/fixtures/generation/lesson_ja.json` sha256 `4c2a65fe6e7fef899e6de86bf4e1fa5abedaa7117ddd4a32778df3401160a178`
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
  1. kind=model, heading=Four phrases at the counter
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
Evidence: plan_ja.json `learner_outcome` names four performances ("choose the greeting that opens the interaction, order one drink, pick out a menu item by its distance, and answer a written question about drink size"), each objective carries observable `evidence_criteria` ("Selects the greeting option when the interaction opens", "Names one drink", "Uses a polite request ending", "Answers with one of the offered sizes"), the transfer context is stated ("At a café"), and `exclusions` bound the claim ("No claim of native-speaker naturalness", "No pronunciation assessment from text or generic TTS", "No keigo beyond standard polite forms"). Objective 4's title says "Understand", but its two criteria make the act observable, so this is not a topic-only objective. Unchanged by the repair; re-derived from the plan, not copied from the earlier record.
Follow-up: none

### D2 sequencing_prerequisite_truth
Question: Does each objective arrive after what it needs, and are prerequisites real rather than decorative?
Score: 3
Evidence: plan_ja.json `time_estimate` is sessions_per_week=1 x weeks=4 = 4 sessions against 4 authored `sections` and 4 `check_plan` entries, so the arithmetic holds; sections run greeting (`objective_refs` [1]) -> polite request ([2]) -> demonstratives ([3]) -> written size question ([4]), and each section points at the one objective it teaches. There are no `units[]` in this v1 document, so no prerequisite edge can be verified as used, and no section states a reason for its position, which keeps this at 3 and not 4. Unchanged by the repair; the plan hash is identical to the pre-repair review.
Follow-up: none

### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 2
Evidence: lesson_ja.json `check.evidence_target` is "discrimination" and `check.stimulus.format` is "selection", so objective 1's label pair is consistent; but plan_ja.json objective 2 declares "production" while `check_plan[1].kind` is "quiz" with no stimulus recorded, and the supplied lesson covers objective 1 only, so the checks for objectives 2-4 cannot be read at all. The supplied check is also weaker than its own rubric: building the stored reference with the repo's own `generation._reference_payload(lesson["check"])` and grading it with `grading.grade_closed` gives kind `exact` over the union ["こんにちは", "konnichiwa"], so a typed "konnichiwa" returns verdict `pass`. The rubric criterion "script recognition" ("Matches the chosen phrase to Japanese script") is therefore not forced by the task, which is D3 anchor 2, not anchor 3. Unchanged by the repair: the check block is byte-identical and the repair author did not re-run the validator.
Follow-up: t_4c72297f

### D4 example_explanation_quality
Question: Do the worked example and explanation teach this case, or restate one generic example?
Score: 3
Evidence: lesson_ja.json `worked_example.steps` still show the identification reasoning step by step — "Set aside the thanks and the farewell, because neither one opens an interaction", then "Choose the remaining phrase: it is the standard daytime greeting" — and `learner_explanation` names the same rule. The example is the check's own case (`worked_example.prompt` equals `check.stimulus.prompt`), and its answer is "the remaining phrase, the standard daytime greeting": it states the elimination rule but never prints こんにちは or konnichiwa, so it does not hand over the keyed string. A leaf-by-leaf scan of the lesson JSON found no key occurrence anywhere under `worked_example`, `learner_explanation`, `learner_explanation_short`, the explain segment or the guided segment. Anchor 4 is not met because no second case, near-miss or boundary is explained; the example and the check are the same item. Unchanged by the repair (the worked example bytes did not move), re-read here rather than accepted from the repair record.
Follow-up: none

### D5 cognitive_load_session_arc
Question: Can a learner finish the session, in the stated order, without a jump or an unstated prerequisite?
Score: 3
Evidence: The repair cures the anchor-1 defect. `segments[0]` (`kind: model`, heading "Four phrases at the counter") now prints the keyed form with script, reading and function in one place: "こんにちは (konnichiwa) is the standard daytime greeting you give when you enter a shop." Its `short` repeats the pairing ("konnichiwa greets"). It sits before `segments[1]` (explain) and `segments[2]` (guided "At the check you will see three phrases. Two of them are functions you already know from this section: the thanks and the farewell. Set those two aside. The remaining phrase is the standard daytime greeting for entering, so that is the one to choose."), and before `check.stimulus.choices` ["ありがとうございます", "こんにちは", "さようなら"]. A learner who cannot read kana can therefore solve the check from the lesson alone: match the choice's kana string こんにちは to the model's "こんにちは (konnichiwa)", and confirm the function "greeting you give when you enter a shop" against the prompt "Which phrase opens the interaction politely?". The accepted romaji form is also a passing typed answer (`grading.grade_closed` passes "konnichiwa"), so answerability is not in doubt; whether that counts as script recognition is D3's question, not D5's. The unstated script-recognition prerequisite that produced the previous score of 2 is gone; the arc model -> explain -> guided -> check is one concept per step inside the plan's 25-minute session. Anchor 4 is not met: the guided step keeps romaji visible rather than fading support, and there is no close that returns the learner to the path with a recorded result, so 3 and not 4. This is a discrimination-from-presentation claim, not a production claim.
Follow-up: none

### D6 source_grounding_citation_honesty
Question: Is each load-bearing claim traceable to a fetched source or honestly marked unverified?
Score: 3
Evidence: plan_ja.json objective 1 is `support: sourced` with `source_ids` ["SRC_ALPHA"], objectives 2-4 are explicitly "unverified", and `evidence_note` names the gap and the remedy: "SRC_ALPHA is tied to the greeting wording and register in objective 1. Objectives 2-4 and the request and thanks phrases are unverified in this recorded sample: no fetched source is attached, so a teacher must check them before a learner relies on them." `exclusions` also bound the claim. Anchor 4 is not reachable: `validation_reject_check.json` carries no source ledger, so SRC_ALPHA cannot be resolved to a fetched page from the supplied artifacts. Unchanged by the repair; the plan and validation hashes are identical.
Follow-up: none

### D7 media_necessity
Question: Does each image or audio artifact carry a job the construct requires, or is it decoration?
Score: 2
Evidence: lesson_ja.json `segments[2]` assigns a speaking act — "Say each phrase aloud with the romaji visible; the romaji is a scaffold, not evidence of reading" — while every `plan_ja.json` section declares `media_need.construct` "" and `media_need.audio.level` "none", and `lesson.media` is empty. The need is real but the plan leaves it undecided with no construct or reason, which is D7 anchor 2. The model segment now gives the reading in romaji, but a romaji gloss is not a pronunciation model; nothing about the repair changes the media decision. Unchanged by the repair.
Follow-up: t_fc59d3c6

### D8 learner_agency_recoverability
Question: Can the learner see, choose and recover from their own path without a hidden failure?
Score: 3
Evidence: lesson_ja.json `check.scaffolds` enables romaji, furigana and english_meaning; `segments[2]` and `check.learner_instructions` state the fade ("the romaji is a scaffold, not evidence of reading", "stays visible as a scaffold, not as evidence of reading"); `check.assistance_policy` is hint=after_attempt with answer_marks_evidence_class=hinted; delivery is self_study, so no parent copy exists to contradict. Anchor 4 is not met because no hint text the learner will actually see is authored and nothing states what evidence a retry produces. Unchanged by the repair.
Follow-up: none

## Reviewer notes

- **This is a recorded fixture, not a live output.** H-172 (`t_fe097fe7`) is still blocked, so no live provider artifact exists and none is claimed. This is a re-score of the committed fixture at `bb6efd6`; the live re-score remains a separate follow-up when H-172 lands. Nothing here may be cited as a live run.
- **Independence.** Sentinel (cbqa, adversarial QA) authored none of the following: the fixture, the repair commit `bb6efd6`, `docs/DECISION-TAUGHT-TARGET.md`, the rubric, the packet, the validator record, or `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md`. I read the raw JSON and decided the scores before opening the repair author's handoff claims. The repair author's summary (`gate_evidence`, `kana_answerable`) was treated as a claim to falsify, not as evidence.
- **What was actually executed.** `scripts/course_quality_review.py packet` regenerated the deterministic facts from the three fixtures; that is the source of the observed-facts block above. Separately I walked the lesson JSON leaf by leaf and found the key (こんにちは / konnichiwa) only in `segments[0].body`, `segments[0].short`, `check.stimulus.choices[1]`, `check.accepted_answers[0]`, `check.accepted_alternatives[0][0]` and `check.reference_answer`; nothing under `worked_example`, `learner_explanation`, `learner_explanation_short`, `parent_notes`, `segments[1]` or `segments[2]`. I then built the learner page with the repo's own `_build_learner_page` + `lesson_document.document_from_page` and ran `generation.assert_no_answer_leak`: it admits the committed fixture, the key appears in document block[0] (role=example, the model projection) and in no other block, and canaries that move the key into the explain body, the explain short, the guided body, the worked-example answer or `learner_explanation` are each still refused with `_RuleViolation`. The gate therefore has teeth on every surface the ruling scans. I also built the stored reference with `generation._reference_payload(lesson["check"])` and ran `grading.grade_closed` on three typed answers: こんにちは -> pass, konnichiwa -> pass, ありがとうございます -> not_yet; that is the measured basis of the D3 evidence, not an inference from the field names.
- **Checker acceptance is a format check, not acceptance.** `scripts/course_quality_review.py check` returns no errors for this record, but PASS proves only structure. The four holes found in `t_99f1cb89` still apply, and two of them reproduce against this record in this run: a copy with `D5` set to `2` but `Follow-up: none` still returns no errors, and a copy with the `Reviewer:` value blanked still returns no errors — the `\s*` in `REVIEWER_RE` swallows the newline and captures the next line as the reviewer. A copy with `D4` evidence shortened under 40 characters is correctly rejected, so the checker is not vacuous, only incomplete. Nothing in this record should be read as the checker endorsing the scores.
- **One record per course.** This is a second record for S2 because it scores a different artifact (the repaired model segment). It does not edit, replace or re-interpret `docs/reviews/H173d-S2-independent.md` or `docs/reviews/H173b-S2-short-japanese-cafe-repaired.md`; both keep their bytes and their scores stand for the artifacts they read.
- **The validator verdict stays `reject`.** The repair was never sent to the validator, so this record echoes the recorded rejection and does not overturn it. The rejection reason is about `answer_uniqueness` on the stimulus, which is a check-level ambiguity the model-segment repair does not address; D3 = 2 is consistent with it.
- **Residual defects not moved by this repair.** D3 = 2 (objective 2 pairs `production` with `kind: quiz`; checks 2-4 unreadable; a typed romaji answer passes, so "script recognition" is not forced) and D7 = 2 (a speaking act with no audio decision). D3 now carries `t_4c72297f` for the romaji/script-recognition gap, alongside the coverage decision `t_7f46fb7f`; D7 keeps `t_fc59d3c6`, which is repaired on `wt/h173d-media` and absent here. Neither is allowed to block the D5 move: D5 asks whether the session is followable, and it now is.
- **Cross-branch state at scoring time.** Two sibling repairs exist and are not in this artifact, so they cannot move its scores here: `wt/h173d-media` (`4217cb1`) re-decides S2 media and would change D7's evidence, and `wt/h173d-lesson-coverage` (`72a8ea5`) makes the checker demand a stated coverage limit, which would change the record format for D3/D4/D5. `wt/h173d-s2-taught` is based on `719e507` and carries neither. This record scores `bb6efd6` as it stands; a later merge must re-score rather than inherit these verdicts.
- **The checker version scored with is the branch's.** `bb6efd6`'s `scripts/course_quality_review.py` predates H-173g (`2a5b5f6`), which closes the reviewer and sub-3-follow-up holes on a separate branch. That is why the two holes above reproduce here; the finding is about the checker this record was validated with, not a claim that H-173g failed.
- **Coverage.** The plan authors four sections; the supplied lesson covers objective 1 only, so objectives 2-4's checks cannot be read and D3 rests on that plus the `production`-with-a-quiz pairing. D4 and D5 are read from the one supplied lesson.
- **Score movement from the H-173d independent scores** (D1 4, D2 3, D3 2, D4 3, D5 2, D6 3, D7 2, D8 3): only D5 moved, 2 -> 3. D1, D2, D3, D4, D6, D7 and D8 did not move, because the repair touched `segments[0]` only and D4 was re-read against the repaired artifact rather than assumed.
