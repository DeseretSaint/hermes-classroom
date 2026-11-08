# H-173 — course-quality review of generated courses

Status: review record, 2026-11-08. Card H-173 `t_c579dfa7`. Rubric:
`docs/COURSE-QUALITY-RUBRIC.md`. Packet: `scripts/course_quality_review.py`.

This record applies the eight-dimension course-quality rubric to three generated-course samples.
It is a quality lens beside the validator, not a validator verdict. No generation, validation,
grading, RPC or UI behavior changed.

## 1. What was reviewed and why it is not a live run

H-172 (`t_fe097fe7`, live single/short/full acceptance) was still `todo` when this review ran.
H-173 allows recorded fixtures until H-172 lands, so all three samples are the repository's
recorded generation fixtures. No provider call, fetched source, native-speaker review or live
learner use is claimed here.

| Sample | Scope | Plan / lesson / validator | Record |
|---|---|---|---|
| S1 | single, one-off procedure | `plan_one_off.json` / `lesson_one_off.json` / `validation_pass.json` | `docs/reviews/H173-S1-single-brake.md` |
| S2 | short, language | `plan_ja.json` / `lesson_ja.json` / `validation_reject_check.json` | `docs/reviews/H173-S2-short-japanese-cafe.md` |
| S3 | short, parent-led | `plan_parent.json` / `lesson_parent_unsafe.json` / `validation_reject_hazard.json` | `docs/reviews/H173-S3-parent-kitchen.md` |

The validator's recorded verdicts are echoed, not re-run and not altered: S1 `pass`, S2 `reject`
(`answer_uniqueness`, `alternative_coverage`), S3 `reject` (`hazard_age_appropriateness`). S2 and
S3 did not reach a learner and are not presented as if they did. S1's pass record is generic
template text, which is itself a weak evidence point and is stated in that record.

## 2. Verdicts by dimension

Scores are reviewer judgments on a 1-4 scale. 3 is the minimum for a course presented to a
learner; 4 is never required. They are not a mastery score, an engagement metric, a
time-to-complete promise or a badge, and no average or total is computed. Evidence for every cell
is in the linked record.

| Dimension | S1 single brake | S2 short Japanese | S3 parent kitchen |
|---|---|---|---|
| D1 capability_objective_fit | 3 | 2 | 2 |
| D2 sequencing_prerequisite_truth | 2 | 2 | 3 |
| D3 evidence_target_fit | 2 | 2 | 2 |
| D4 example_explanation_quality | 2 | 2 | 1 |
| D5 cognitive_load_session_arc | 2 | 2 | 3 |
| D6 source_grounding_citation_honesty | 2 | 2 | 2 |
| D7 media_necessity | 2 | 2 | 3 |
| D8 learner_agency_recoverability | 3 | 4 | 1 |

The pattern is the card's premise: S1 passes all ten validator criteria and still scores below 3
on six quality dimensions. S2 and S3 are already rejected structurally, and still carry quality
problems the structural criteria do not name.

## 3. Follow-up cards

Every dimension below 3 became a follow-up card with a concrete fix. No dimension was smoothed
into a pass and no score was invented.

| Sample | Dimensions below 3 | Follow-up card |
|---|---|---|
| S1 | D2, D3, D4, D5, D6, D7 | H-173a `t_c7fff5b4` |
| S2 | D1, D2, D3, D4, D5, D6, D7 | H-173b `t_73677244` |
| S3 | D1, D3, D4, D6, D8 | H-173c `t_48e72530` |

The fixes are enumerated in each card body against the record's dimension blocks. The cards are
gated on this card and must re-score the repaired fixture and the matching H-172 live output.

The independent check the rubric needs is H-173d `t_99f1cb89` (cbqa): re-score the same samples,
time one course against the 15-minute claim, and report where the rubric is undecidable.

## 4. Reviewer and independence

Reviewer named in all three records: `Quill (rubric author, author-run dry run)`.

That is an author-run dry run, not an independent review. It meets the card's "named reviewer"
requirement and does not meet the independence requirement on its own. The records say so. H-173d
exists because a rubric certified only by its author is the same failure the generation pipeline
refuses: generation never certifies itself.

The author-run protocol produced a record per sample, but no stopwatch measurement was taken, so
this record does not claim the 15-minute acceptance number. That is an author's experience, not
proof that a non-author reviewer can do it in 15 minutes. H-173d owns that proof.

## 5. What this record does not prove

- It does not prove any sample is a high-quality course. S1 is a weak course with a structural
  pass; S2 and S3 are rejected artifacts with quality defects on top.
- It does not prove the rubric catches every weak course. It proves the lens is usable on these
  three and that the below-3 rule produces specific fixes.
- It does not prove a learner learns better, a source was fetched for these fixtures, or a
  native speaker reviewed the Japanese sample.
- It does not change the validator's truth. The structural pass remains the gate, and the rubric
  is not a reason to block a course a human has approved.
- It does not replace H-172. When H-172 lands, the same packet must run on its live single, short
  and full outputs; a fixture score is not a live score.
