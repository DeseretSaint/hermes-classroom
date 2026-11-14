# Taught targets and the answer-leak rule

| | |
|---|---|
| Card | `H-173d` finding 1 / `t_fdf16735` (from the independent re-score `t_99f1cb89`) |
| Branch | `wt/h173d-answer-leak-rule` (rule), `wt/h173d-pack-rule` (pack-path follow-up `t_61171ca0`, branched from `719e507`) |
| Base | `4358249` (master at pickup) |
| Author | Atlas (architecture), 2026-11-08 |
| Status | **Decided.** The gate forbids *announcing* the key, not *teaching* the form. The model segment is the presentation surface and is exempt from the key scan; every other learner surface stays scanned. |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no validator criterion change, no new field. |
| Code delta | `coursebook/generation.py` (`_narrative_text`, `assert_no_answer_leak`), `coursebook/lesson_document.py` (`narrative_text` gains two optional skip predicates), `coursebook/parent_authoring.py` (`_learner_scan_text`, `_assert_no_answer_leak`), `tests/test_lesson_document.py` (5 tests), `tests/test_course_export.py` (5 tests, `AuthoredAnswerLeakGateTest`). |
| Score delta | **None.** No fixture, rubric or author record is edited here, so S2 D5 stays 2. |

---

## 1. The contradiction this card resolves

`generation.assert_no_answer_leak` refused any accepted answer, accepted alternative or reference
answer string anywhere in the learner narrative. On the S2 fixture (`tests/fixtures/generation/lesson_ja.json`,
sha256 `983a6cd7…`) the consequence was:

| Surface | What it carried |
|---|---|
| `segments[0]` (`kind: model`) | お願いします / ありがとうございます / さようなら in script, with functions and readings |
| `segments[1]`, `segments[2]` | the target only as "the standard daytime greeting" |
| `check.stimulus.choices` | ありがとうございます / こんにちは / さようなら |
| `check.reference_answer`, `accepted_answers` | こんにちは |

The check asks the learner to pick the script form that opens the interaction, and its rubric
criterion is "script recognition". Under the old rule the lesson could not print こんにちは
anywhere, so it could not teach the form it keyed, and a learner who did not already read that
script could not answer from the lesson. The repair author recorded the constraint honestly
(`docs/reviews/H173b-S2-short-japanese-cafe-repaired.md`, reviewer notes: "a generated lesson
cannot print the phrase its closed check keys"), and the independent re-score scored D5 = 2
("the lesson requires a step the lesson never models", `docs/COURSE-QUALITY-RUBRIC.md` D5 anchor 1).

Two rules of this repository collided: **a check must test what the lesson teaches**, and **the
learner page must not announce the answer**. The old gate resolved the collision by forbidding the
teaching.

## 2. Decision

**The answer-leak gate protects the key, not the vocabulary.** Its invariant is the one its own
docstring already stated for selection choices — "the *key* is not announced — not that a correct
string cannot exist among the options" — applied one surface further back: a lesson may *present*
the item it checks, on exactly one authored surface.

| Surface | Keyed string |
|---|---|
| `segments[]` with `kind: model` (body, heading, short) | **Permitted.** This is the presentation surface: form, function and reading together. |
| Media with `role: narration` (the audio that reads the model) | **Permitted** for the same reason. |
| The model segment's projected document block | **Permitted**; the block is identified by its `deep` text matching a model body, never by role (`example` also holds the worked example). |
| `segments[]` with `kind: explain`, `guided`, `retrieval` (body, heading, short) | **Refused.** |
| `worked_example` prompt, steps, answer, short | **Refused.** |
| `learner_explanation`, `learner_explanation_short` | **Refused.** |
| `parent_notes`, non-narration media text | **Refused.** |
| Every other document block | **Refused.** |
| `check.rubric[].description` | **Refused, unchanged.** |

"Refused" means the draft never reaches the validator: the generation job retries with the reason
and the second attempt parks the lesson `needs_review`, exactly as before.

The explain/guided surface keeps the teeth that matter. A lesson that says "the answer you should
pick is こんにちは" in an explain step, a guided short or the recap is still stopped — those are the
existing tests at `tests/test_generation.py` `test_reference_answer_copy_pasted_into_the_explanation_is_parked`
and `test_a_short_that_announces_the_answer_never_reaches_validation`, both unchanged and still
passing.

## 3. Why not the other two options

**Option 1 — key the check on the function with the script forms in the stimulus.** That is what
the S2 check already does: `stimulus.prompt` reads "Which phrase opens the interaction politely?"
and the answer is a script form among three script choices. Re-labelling the prompt cannot create
the knowledge the learner is missing: mapping form to function requires recognising the form.
Adopting it would have left the artifact untouched and moved the score, which this card forbids,
and would have made "script recognition" a criterion nothing observes.

**Option 3 — declare recognition of unseen script an accepted prerequisite.** This makes the
defect honest instead of removing it. D5 anchor 1 names precisely "a step the lesson never
models", and the product's Japanese track is L0: a lesson may not assume script recognition it
never teaches. Writing the prerequisite into the copy would still leave the check unanswerable from
the session and the score at 2.

## 4. Where the rule lives

| File | Change |
|---|---|
| `coursebook/generation.py:4391` `_narrative_text` | Skips `kind: model` segments and `role: narration` media; skips the projected document block whose `deep` equals a model body. Everything else is scanned as before. |
| `coursebook/generation.py:4457` `assert_no_answer_leak` | Docstring states the rule. Behaviour follows `_narrative_text`; no other logic changed. |
| `coursebook/lesson_document.py:995` `narrative_text` | Two optional keyword predicates, `skip_block` and `skip_media`; defaults scan the whole document, so every other caller (`leaks_answer`, the tests) is unchanged. |
| `tests/test_lesson_document.py` `TaughtTargetLeakRuleTest` | 5 tests: the model segment may present the keyed form end to end (page + document); the same string in an explain step, in the guided practice, in the worked example answer and in an illustration media item is still refused; narration is permitted. |
| `coursebook/parent_authoring.py:772` `_assert_no_answer_leak` | The authored pack path (`parent.export`, `course.export`, `course.export.read`) scans the page's `segments[]` through `_learner_scan_text` instead of the rendered learner page: `kind: model` segments and `role: narration` media are exempt, every other segment, the worked example, the explanation, non-narration media and every authored document block are scanned. The narration export file is a reading of those segment bodies, so it is a presenting surface and is not scanned separately. |
| `tests/test_course_export.py` `AuthoredAnswerLeakGateTest` | 5 tests through the real export commands: the key in the model segment exports and the archive carries it; the same string in the explanation, in a guided segment, or in an authored document's `example` block refuses with `answer_leak_in_learner_page`; an authored document without the key still exports. |
| `tests/test_course_quality_s2_repair.py` | 2 tests on the real S2 fixture: the model segment amended to present こんにちは is admitted, and the same string added to `segments[1]` (explain) is still refused. |

Both call sites of the gate — authoring (`run_lesson_job`) and read (`learner_page`) — use the same
`_narrative_text`, so a stored page is served under the same rule it was admitted under.

## 5. What this does to S2

Nothing, yet. The artifact is unchanged, so:

- `lesson_ja.json` at `983a6cd7…` still never presents こんにちは, and **D5 stays 2**.
- The rule change removes the *reason* the repair could not fix it. A repaired fixture must put the
  target in `segments[0]` (the model) with its script, its reading and its function — e.g.
  こんにちは (konnichiwa) is the standard daytime greeting when you enter — and leave the explain
  and guided steps pointing at it. On that artifact the check's "script recognition" criterion
  becomes observable and D5 can be re-scored.
- The rubric line that the independent reviewer and the repair author disagreed about — "naming the
  function is not presenting the form" — is now the boundary the gate enforces: the function-only
  wording (`segments[1]`–`[2]` as they stand) is not presentation.

## 6. What does not change

- The `answer_leakage` validator criterion (`validators.py`, `validation-prompt.v3`) is untouched.
  This card rules on the deterministic authoring gate only.
- No fixture, rubric text, review record or score is edited. The S2 fixture, its plan and the two
  review records keep their bytes.
- The `lessons` prompt payload (`rules.reference_answer` in `build_lesson_request`) still says the
  *field* is stored separately and never inside segments, explanation or worked example. It does not
  forbid the taught string; the payload text is left alone so no stored idempotency fingerprint or
  prompt label changes.

## 7. Open items and closed follow-ups

| Item | Owner | Outcome |
|---|---|---|
| Repair `lesson_ja.json` so the model segment presents こんにちは, then re-run the S2 re-score | cinder | Open. Artifact work; this card moves no score without it (`t_364eafe1`, re-score gate `t_8280268a`) |
| Apply the presenting-surface predicate to `coursebook/parent_authoring.py:772` `_assert_no_answer_leak`, which rendered the learner page to flat text and still refused a parent pack whose lesson teaches its answer | cinder | **Closed (`t_61171ca0`, `wt/h173d-pack-rule`).** The gate scans the page's `segments[]` (`_learner_scan_text`) instead of the rendered file, so `kind: model` segments and `role: narration` media are exempt while explain/guided/retrieval segments, the worked example, the explanation, non-narration media and every document block are still scanned. The `narration` export file is a reading of those segment bodies, so it is a presenting surface and is not scanned separately. `tests/test_course_export.py` `AuthoredAnswerLeakGateTest` proves the export and the refusals through the real commands |
| Decide the exemption for a pack-supplied *authored* `document`: its blocks carry no segment kind, so `document_from_page` cannot tell a model block from the rest and the gate scans all of them | cinder | **Closed: strict reading (`t_61171ca0`).** `lesson_document.BLOCK_ROLES` has no `model` role and the projection maps `model` to `example`, so no document block can be identified as presenting without also exempting the worked example. Under the strict reading every authored document block is scanned, and a pack whose only presentation is an `example` block carrying the key is refused with `answer_leak_in_learner_page`. A presenting marker on the document contract is not adopted: it would need its own contract review, not this card |
| Word the D5 rubric note: a model segment that prints the target with reading and function is presentation; naming only the function is not | quill | Open. Rubric wording is Quill's (`t_8f7689e2`) |

## 8. Evidence

```
$ python3 -m unittest discover -s tests -t .
Ran 2355 tests in 624.238s

OK (skipped=1)
```

Before the full run, the three touched modules alone:

```
$ python3 -m unittest tests.test_lesson_document tests.test_generation tests.test_course_quality_s2_repair
Ran 127 tests in 0.563s

OK
```

The S2 fixture is still admitted by the gate (`tests/test_course_quality_s2_repair.py` passes unchanged), which is the
point: the rule change does not retroactively bless the unmodelled target.

Follow-up `t_61171ca0` (pack export gate), same command in a clean `HERMES_HOME`:

```
$ python3 -m unittest discover -s tests -t .
Ran 2360 tests in 410.717s

OK (skipped=1)
```

The new module on its own, after the change:

```
$ python3 -m unittest tests.test_course_export.AuthoredAnswerLeakGateTest -v
Ran 5 tests in 1.788s

OK
```

The 5 new tests fail against `719e507` before the change: the model-segment pack is refused and
the authored document's key is not scanned at all.

## 9. Follow-up: the prompt now states the rule (CP-015c, `t_a0bcacdd`)

Section 6 recorded that the lesson payload said the *field* was stored separately but did not
forbid the taught string, so no prompt label changed. CP-015c measured the cost of that omission on
the approved Japanese Cafe plan: the lesson stage re-authored all three owner sections and each
parked `needs_review` on the answer-leak family — the author taught the target in the model segment
and then restated it verbatim in `learner_explanation` and the worked example, because the prompt
never said which surfaces are scanned or that the model segment is the one presentation surface.

Two changes, both verified by `tests/test_cp015c_answer_leak_surfaces.py`:

| Surface | Change |
|---|---|
| `lesson-prompt.v11` | states the scanned surfaces, the `model`/narration exemption, the legal shape (target form, reading and function in the model segment; referred to by function elsewhere) and one passing example |
| `lesson.check.reference_answer` | the check's `stimulus.prompt` and `learner_instructions` are scanned deterministically under that named reason; the stored key stays in the answer key and the page projection still never carries it |
| `validation-prompt.v9` | the lesson validation payload carries the stored key in an `answer_key` block marked `learner_facing: false`, and the pass states that `answer_leakage` judges the learner-facing surfaces, not the key's existence |

The rule is unchanged; only its statement and the key's placement in the validation request moved.
The exemption for `kind: model` segments and `role: narration` media is the one decided in §2.

## 10. The other half: the check must pose a new case (Upgrade 12, `t_80d69a67`)

§2 decided which surfaces may *print* the target. It said nothing about which *case* the check may
ask about, and the gap was measured: an author taught "your host asks 何人ですか — answer 二人です"
in the model segment and then keyed the check on the same host question. Neither existing gate saw
it — `assert_no_answer_leak` scans narrative surfaces and the prompt is not one, and
`assert_check_payload_does_not_announce_answer` refuses the *key* in the prompt, which the reused
half of the sentence (the question) does not contain. The learner reproduced a line read minutes
earlier; a recall-family check measured look-up plus short-term copying.

**Decision.** Every check states a case the page has not already solved: a different interlocutor,
setting or object whose answer is the taught form. `generation.assert_check_states_a_new_case`
enforces it deterministically on the authoring path, before the independent validator, under the
named reason `lesson.check.model_sentence_reuse`.

| Test | Refuses |
|---|---|
| Verbatim | the model sentence appears word for word in `stimulus.prompt`, `learner_instructions` or a stored answer string |
| Order | four or more of the model sentence's content words appear in the model's own reading order in that surface (`wording`'s stems and CJK handling) |

The target form's own words are removed from both sides first: the check is *asking* for the form,
so repeating it is not reuse — the answer-leak rule already owns the key. A new case changes the
frame words (interlocutor, setting, object) and keeps the form, so it passes; the measured passing
draft asks how many are coming to a dinner rather than how many are in the party.

**The adversarial bound, stated rather than hidden.** A hard new-case rule can make a check unfair
when its frame uses vocabulary the lesson never taught, and a token fold is easy to defeat with
synonyms. `lesson-prompt.v19` therefore states the fairness half in the same directive — the new
case must use only vocabulary and grammar this lesson already taught — and this decision accepts
both residuals: a synonym paraphrase of the model sentence can pass, and a close paraphrase of the
frame can be refused. One repair pass is cheaper than a check that keys a sentence the learner just
read, and the gate never claims to be a judge.

The read path (`learner_page`) does **not** run this gate. A stored page already passed the
authoring gate it was written under; refusing on read would unserve packs authored before this
rule without repairing anything. The authoring pass is where a draft is refused, and the prompt
label (`lesson-prompt.v19`) is what an operator can audit for a page's vintage.

Evidence: `tests/test_upgrade_new_case_check.py` (15 tests) — the acceptance case, the passing
varied case, the older gates' measured gap, the accepted-answer and learner-instructions halves, the
form-only exemption, the no-model-page scope, and both halves through the real lesson job.


