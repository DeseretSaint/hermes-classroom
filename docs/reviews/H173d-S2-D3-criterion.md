# Decision record: H-173d S2 D3 — the rubric names selection, not script recognition

| | |
|---|---|
| Kind | Decision record for a D3 finding, not a scored review record |
| Card | H-173d follow-up / `t_4c72297f` |
| Finding from | `docs/reviews/H173d-S2-rescore-repaired-model.md` on `wt/h173d-s2-rescore` (`00bf3a2`), scoring `lesson_ja.json` sha256 `4c2a65fe…` at `bb6efd6` |
| Author | Cinder (backend kernel; author of the S2 fixture repair, not of the finding) |
| Decision made by | Supervisor (`default` worker comment on `t_4c72297f`, 2026-11-08 10:09), applied here |
| Repair commit | `7aeba5f` on `wt/h173d-d3-criterion` |
| Fixture after repair | `tests/fixtures/generation/lesson_ja.json` sha256 `86a6db1a61358d23ec39a2dad957811047f78986338cf04bcc7ea7432a07d92e` |
| Action on prior records | None. `H173d-S2-independent.md`, `H173b-…-repaired.md` and `H173d-S2-rescore-repaired-model.md` are untouched; no score is changed here |

This record carries no D1-D8 verdicts, so `scripts/course_quality_review.py check` does not apply to
it as if it were an eight-dimension record. The decided artifact is the fixture, and the repair's
claims are pinned by `tests/test_course_quality_s2_repair.py`.

## The finding, reproduced

The stored reference is built by `generation._reference_payload(lesson["check"])`: kind `exact`
over the union of `reference_answer`, `accepted_answers` and every `accepted_alternatives` group.
Before the repair the fixture declared `accepted_alternatives: [["konnichiwa"]]`, so the union was
`["こんにちは", "konnichiwa"]`.

Reproduction at the repair commit (`7aeba5f`, the same behaviour the finding measured at `bb6efd6`):

```
reference kind: exact
reference answers: ['こんにちは', 'konnichiwa']
typed 'こんにちは' -> verdict=pass
typed 'konnichiwa' -> verdict=pass
typed 'ありがとうございます' -> verdict=not_yet
```

A learner could pass by typing the romaji string the model segment prints, so the old
`rubric[2]` — criterion `script recognition`, description `Matches the chosen phrase to Japanese
script` — named an act the answer set never forced.

## Decision: (b), keep romaji acceptance and rewrite the criterion

This is the L0 Japanese fixture. Romaji is a deliberate, fading scaffold for a learner who cannot
yet read kana — the same learner the D5 repair made the model segment serve. Dropping the romaji
group (option (a)) would re-create the D5 defect from the other side: the lesson presents the form,
then the check refuses the only string that learner can type. The defect is that the criterion
named an act the answer set never asks for, so the honest repair is the criterion's text, not a
narrower key.

`check.rubric[2]` is now:

```
criterion:   phrase selection
description: Selects the phrase the model presents as the greeting, out of the three options; the
             kana form and its printed romaji reading are both accepted, so this scores selection,
             not script reading.
```

`accepted_answers`, `accepted_alternatives`, `reference_answer`, `evidence_target`, the grading
lanes, the validator, the schema, the RPC and the rubric registry are unchanged. The reference is
still `exact` over both spellings; that is the behaviour the rewritten criterion now describes.

## Script recognition is not assessed at L0

The rewritten criterion deliberately drops the claim rather than the requirement. Script
recognition is **not assessed at L0** — a romaji-only answer is not script reading, as
`coursebook/rubrics.py`'s `language_production` limitation already states. A later level must add
script recognition as its own criterion, with a key that forces the kana form; it must not be
folded back into this selection criterion while `konnichiwa` remains a passing answer.

## Tests

Added to `tests/test_course_quality_s2_repair.py` (`CriterionAnswerSetFitTest`):

- the sealed reference is `exact` over `こんにちは` and `konnichiwa`;
- typing either spelling passes and `ありがとうございます` does not (`grading.grade_closed`);
- no rubric criterion claims `script recognition`, the record says `not script reading`, and a
  romaji answer is still accepted — the two facts must move together if anyone revisits this.

The 27 checker tests from H-173g (`2a5b5f6`, merged on master at `80eecce`) are untouched:
`tests.test_course_quality_s2_repair tests.test_locale_scaffolds tests.test_course_quality_rubric`
→ 56 tests OK.

## Legacy document hash pin, re-derived once

`wt/h173d-media` (`4217cb1`) also edits `lesson_ja.json` and `plan_ja.json` and re-derived the
`tests/test_locale_scaffolds.py` pin on its own base. To avoid a second derivation, that branch is
an ancestor of this repair (`bc71aca`), and the pin was re-derived on the combined tree at
`7aeba5f`:

```
document_from_page(lesson_ja) -> sha256:72e347aa8e6f7b08221f63efa2e7a2742c91d6af5f6fbe591f0c5e5dbeb2967e
document id                   -> doc_72e347aa8e6f7b08221f
```

The value is unchanged from `4217cb1`'s pin: rubric text never enters the learner document, so the
criterion rewrite does not move `content_hash` or `document_id`. The assertion the pin protects —
passing a locale must not move either — is unchanged and passes.
