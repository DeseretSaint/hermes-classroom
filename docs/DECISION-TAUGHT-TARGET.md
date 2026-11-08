# Taught targets and the answer-leak rule

| | |
|---|---|
| Card | `H-173d` finding 1 / `t_fdf16735` (from the independent re-score `t_99f1cb89`) |
| Branch | `wt/h173d-answer-leak-rule` |
| Base | `4358249` (master at pickup) |
| Author | Atlas (architecture), 2026-11-08 |
| Status | **Decided.** The gate forbids *announcing* the key, not *teaching* the form. The model segment is the presentation surface and is exempt from the key scan; every other learner surface stays scanned. |
| Contract / DB delta | **None.** No `cb.rpc` bump, no `cb.db` migration, no validator criterion change, no new field. |
| Code delta | `coursebook/generation.py` (`_narrative_text`, `assert_no_answer_leak`), `coursebook/lesson_document.py` (`narrative_text` gains two optional skip predicates), `tests/test_lesson_document.py` (5 tests). |
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
| `coursebook/generation.py:4455` `assert_no_answer_leak` | Docstring states the rule. Behaviour follows `_narrative_text`; no other logic changed. |
| `coursebook/lesson_document.py:995` `narrative_text` | Two optional keyword predicates, `skip_block` and `skip_media`; defaults scan the whole document, so every other caller (`leaks_answer`, the tests) is unchanged. |
| `tests/test_lesson_document.py` `TaughtTargetLeakRuleTest` | 5 tests: the model segment may present the keyed form end to end (page + document); the same string in an explain step, in the guided practice, in the worked example answer and in an illustration media item is still refused; narration is permitted. |

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

## 7. Open items

| Item | Owner | Why it is not in this card |
|---|---|---|
| Repair `lesson_ja.json` so the model segment presents こんにちは, then re-run the S2 re-score | cinder | Artifact work; this card moves no score without it |
| Apply the same presenting-surface predicate to `coursebook/parent_authoring.py:772` `_assert_no_answer_leak`, which renders the learner page to flat text and would still refuse a parent pack whose lesson teaches its answer | cinder | Separate export path, needs its own fixture and test |
| Decide the exemption for a pack-supplied *authored* `document`: its blocks carry no segment kind, so `document_from_page` cannot tell a model block from the rest and the gate scans all of them. Generated lessons are unaffected (the projection is built from `segments[]`), but a hand-authored pack that teaches its key is still refused | cinder | Same pack path as the row above; one ruling should cover both |
| Word the D5 rubric note: a model segment that prints the target with reading and function is presentation; naming only the function is not | quill | Rubric wording is Quill's |

## 8. Evidence

```
$ python3 -m unittest tests.test_lesson_document tests.test_generation tests.test_course_quality_s2_repair
Ran 127 tests in 0.563s
OK
```

Full-suite result and the exact commands are in the card's completion record. The S2 fixture is
still admitted by the gate (`tests/test_course_quality_s2_repair.py` passes unchanged), which is the
point: the rule change does not retroactively bless the unmodelled target.
