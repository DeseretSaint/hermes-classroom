# Named comment: H-173a's S1 D3 score reads 3, the rubric's D3 reads 2

| | |
|---|---|
| Kind | Named comment on a review record, not a scored review record |
| Record commented on | `docs/reviews/H173a-S1-single-brake-rescored.md:113-117` on `wt/h173a-s1-single-brake` (tip `5092f92`, unmerged) |
| Commenting card | H-173f / `t_f770bf62` |
| Author | Quill (course-quality rubric author) |
| Date | 2026-11-08 |
| Rubric base | `docs/COURSE-QUALITY-RUBRIC.md` on `wt/h173-course-quality-rubric`, base `e69746c`, plus the D3 ceiling added by this card |
| Decision applied | `docs/DECISION-PROCEDURE-EVIDENCE.md` section 5 and `docs/ASSESSMENT-BREADTH.md` section 5 (H-173e decision) |
| Action on the record | None. H-173a's record, score and fixtures are not edited here. |

This is a comment under the conventions of `scripts/course_quality_review.py`, not an
eight-dimension record. It does not carry D1, D2, D4-D8 verdicts, so `check` does not apply to it
as if it were a record; the records it comments on and the rubric remain the artifacts that are
checked.

## What H-173a recorded

`docs/reviews/H173a-S1-single-brake-rescored.md` lines 113-117 (line breaks added here; wording
unchanged):

```
### D3 evidence_target_fit
Question: Does the check measure the evidence target the objective declares?
Score: 3
Evidence: plan_one_off.json check_plan for objectives 2 and 4, and lesson_one_off.json stimulus
items 2 and 3, ask the learner to confirm a photo of the worn pad beside the loosened fastener and
a second person's check of the lever and free wheel. The criteria are the objectives' criteria in
observable form and the learner instructions label the result a self-report, so the check no longer
presents a tick alone as procedure evidence; the build has no attachment lane, which keeps this at
3 rather than 4.
Follow-up: none
```

The load-bearing clause is "the check no longer presents a tick alone as procedure evidence". The
record's own notes (lines 180-181) close the door that clause opens: "this build has no attachment
or observer lane, so the attempt's evidence class stays self-reported".

## What the artifact records

All paths are on `wt/h173a-s1-single-brake` at `5092f92`, the tree that record reviewed.

- `tests/fixtures/generation/plan_one_off.json:130-163`: all four `check_plan[]` entries are
  `kind=verification` with `evidence_target=procedure` and each carries
  `"independent_evidence": false` (lines 136, 144, 152, 160). The plan states the limit itself.
- `tests/fixtures/generation/lesson_one_off.json:47-60`: `check.stimulus.items` are three labels
  to tick. Item 2 is "Worn pad removed with the named fastener, and a photo of the worn pad beside
  the loosened fastener taken" (line 54). Item 3 is "Second person confirmed the pad seated
  square, the lever firm and the wheel spinning free" (line 58). Both name an act; neither is an
  input the learner submits.
- `tests/fixtures/generation/lesson_one_off.json:62`: `learner_instructions` says "Tick what is
  true. This is a self-report: ticking the photo and second-person items records that you say you
  did them, and no tick here is presented as independently verified."
- `coursebook/grading.py:157-195`: the confirmation lane reads the answer's `selection` of item
  ids, grades membership only, and writes `evidence_class=CONFIRMATION_EVIDENCE_CLASS`
  (`:194`), which is `"self_reported"` (`:40`). Nothing in that path accepts a file.

So the repair changed the labels and named the observable acts. It did not change what the
attempt collects: still a `selection` of ticked item ids, still stored `self_reported`.

## Score this comment reads from the rubric

**D3 = 2.**

Rubric lines relied on (`docs/COURSE-QUALITY-RUBRIC.md`, D3):

- Anchor 2: "the target is plausible but the task is weaker than claimed (self-ticked checklist
  for a procedure, recognition for transfer)". A checklist of ticked item ids for a `procedure`
  objective is that case by name.
- The 0.1.0 ceiling paragraph under the anchors: a course that declares `evidence_target:
  procedure` and collects only a checklist scores at most 2 here, whatever its labels say, because
  the attempt still stores a `selection` with `evidence_class = self_reported`.

Why not 1: the declared target is plausible and the check's criteria are the objectives'
criteria in observable form; the check does not measure a different target.

Why not 3: anchor 3 requires the check's task to match the declared target. A tick attests that
the learner says the act happened. It does not observe the act, and the plan's own
`independent_evidence: false` says so. Honest labelling is an improvement over a bare tick, and it
is why anchor 2 applies rather than anchor 1, but it is not new evidence.

Why the validator's pass does not lift it: the `evidence_target_fit` criterion is named at
`coursebook/generation.py:188`, and the question it answers is stated in
`docs/DECISION-PROCEDURE-EVIDENCE.md` section 5: "Is this the strongest lane this build can give
the declared target?" In 0.1.0 the checklist is, so it passes. D3 asks whether the task is as
strong as the target the course claims, and it is not. The two answers are pass and 2, and that is
not a contradiction to reconcile.

## What this comment does not do

- It does not edit H-173a's record, its score, its follow-up, or either fixture. The fixture
  repair is not in question here; only the D3 score's support is.
- It is not an independent re-score of D1, D2 or D4-D8. H-173d (`t_99f1cb89`) owns the
  independent review with its own evidence.
- It does not withdraw H-173a's fixture repair. The plan and lesson are more honest than the
  pre-repair pair, which the H-173 record scored D3 = 2 on at
  `docs/reviews/H173-S1-single-brake.md:108-112` for the same underlying reason: "A tick attests
  completion, it does not evidence a performed procedure".
- If a reviewer reads anchor 3 differently, the evidence to cite is a captured artifact in the
  attempt record: an upload, an observer record, or a grader that inspects the object. None
  exists at `5092f92`; `coursebook/grading.py:157-195` accepts only a selection of item ids.
