# CP-015c-ja — Japanese Cafe Basics: review packet

Status at this commit: **the plan is approved and independently validated; the course is not
authorable to export.** No pack, no Workshop entry, no install proof and no lesson visual exist,
because no lesson page reached a validated state. This is a red result, not a demonstration.

## 1. Commit and branch

| | |
|---|---|
| Branch | `wt/cp-015c-ja` |
| Commit | `a848b55d` (record + tests); kernel merges below |
| Lineage | CP-015b `ddf32b52` + master `c054f977` + CP-015e `3dd1665a` + CP-015f `8ba13d52`/`39450d2e` + CP-015g `e55d8156` (merged `650bc605`) + CP-015h (integrated from cinder's `t_26b4dc77` working tree, `24897ed3`) |
| Pushed | no |
| Published | no |

`coursebook/*.py` in this branch changes only by merging cinder's CP-015g commit and applying
cinder's CP-015h diff; nothing in the kernel was authored here.

## 2. The plan — approved

| | |
|---|---|
| Plan | `pln_5dde08c973f94cc0a444caa77a09d53c` (`sha256:4be51aac992e5…` — full value in `cp015-run.json`) |
| Validation | `b0c0c6d0c01e97e1`, verdict **pass**, 11/11 criteria |
| Independence | `independent` — validator `z-ai/glm-5.3-flash` (nous) judging `deepseek/deepseek-v4.1-flash-1017` |
| Course | `crs_44880979e34f45a9926512c0bf24c098` — `ja-JP`, `L0`, `language`, presentation `game` |
| Shape | 2 units, 5 objectives, 10 stored sources |

The plan's promises are grounded: unit 1 entrance phrases (objectives 1–3), unit 2 snack words and
omotenashi (objectives 4–5), each with stored sources.

## 3. Unit 1 sections — approved

`coursebook.unit_sections.generate` / `.validate` for `…:1`, verdict **pass**, `independent`,
`unit-sections-prompt.v2` / `validation-prompt.v8`. Four sections stored: three owner sections and
one review section that reinforces objectives 1–3.

Two kernel defects had to be fixed to get this far, both authored by cinder and integrated here:

* **CP-015g** (`t_332351b0`, `e55d8156`) — the unit brief carried the whole-course
  `learner_outcome`, so `objective_alignment` rejected unit 1 for promises owned by unit 2.
* **CP-015h** (`t_26b4dc77`) — the unit-sections prompt never stated the shape the deterministic
  audio gate requires, so three sections were refused twice for a `pronunciation_reference`
  construct that named only the target phrase.

## 4. Lessons — authored, none validated (the blocker)

Six `coursebook.lesson.generate` calls (two attempts per owner section), three
`coursebook.lesson.validate` calls. Every page was parked `needs_review`; none is exportable.

| Section | Rejections (verbatim from `gen_lessons.rejection_reasons_json`) |
|---|---|
| 1 Party Size: 二人です | `blocks[3].short [text_completeness] dangling_terminal_word: ends on 'not'`; `blocks[5].deep [text_completeness] dangling_terminal_word: ends on 'not'`; `learner-facing narrative contains the check reference answer or a keyed answer` |
| 2 Table Request: テーブル席でお願いします | validator `reject`, `criteria failed: source_support` |
| 3 Seating-Order Question: 先に席を取ったほうがいいですか | `blocks[0..3].short introduces '“first,”', '“seat,”', '“take.”' … which its deep text does not contain` (four blocks) |

The prose itself is plausible L0 material (romaji and gloss scaffolds, a contrastive check), but
these are real rule violations, not validator noise: section 1 truncates a clause and prints the
answer to its own check in the narrative; section 3's short lines paraphrase rather than derive;
section 2 asserts a fact the source ledger does not carry.

**Stop rule.** Each section was attempted twice. Section 3 alone hit the same criterion class
(`short` not derivable from `deep`) four times in one attempt and twice overall, so the run stopped
rather than iterating the prompt.

## 5. Review section — refused, unit stranded

Job `job_57a89f823d274b2ba7d769edd81eee0c` ended:

> review section 4 reinforces objectives [1, 2, 3] but none has an open owner check; author the
> owner lessons for those objectives first

The owner lessons *were* authored first, in ordinal order; each was parked `needs_review`, which
closes its check. The review section therefore cannot be authored in the same run, and a re-run
re-authors the owners from scratch. Filed as **CP-015j** (`t_da5f3c6a`) for cinder — this is a
structural coupling, not a content verdict.

## 6. What does not exist

| Acceptance item | Result |
|---|---|
| Approved world | **absent** — never reached (no validated pages) |
| Rendered lesson page (validated) | **absent** — three pages exist as `needs_review` |
| Pack accepted by `packs.validate_manifest` | **absent** — `course.export` refuses (`lessons_not_validated`) |
| Workshop entry with real hash | **absent** — no pack to hash |
| Fresh library empty, then installed | **not exercised** — `scripts/cp015c-workshop-install-proof.py` is written and unrun for want of a pack |
| Home/Discover card, lesson capture | **absent** — nothing is on a shelf |
| Run record regenerates byte-identically | **pass** — `scripts/cp015_record.py`, `sha256` stable across two runs, `tests.test_cp015_run_record` 10 OK |

No visual result was produced. Nothing here may be described as high quality: there is no lesson
plate, so neither the "real plate, not a flat text panel" test nor the rejected-kit question
(`field_atlas@1` must not ship) ever arises.

## 7. Cost

21 provider calls, ≈95,286 output tokens on this backend home (`usage_events`), across three
authoring passes (r1 rejected by CP-015g, r2 by CP-015h, r3 by lesson quality). No image spend.

## 8. Tests

* `tests.test_cp015_run_record` — 10 OK (record regenerates from the backend rows).
* `tests.test_cp015h_media_construct_shape`, `test_capability_policy`, `test_blueprint_units`,
  `test_cp015e_unit_budget`, `test_cp015f_lesson_budget` — 67 OK.
* `tests.test_harness_e2e` — 26 OK after regenerating the harness packet for
  `validation-prompt.v8` + `unit-sections-prompt.v2` (`a3fd76d7`).

## 9. Reproduction

```bash
export HERMES_HOME=$HOME/.hermes/coursebook-test-cp015c/home
hermes serve --isolated --port 44601 &
CB013_BASE=http://127.0.0.1:44601 CB013_TOKEN=… CP015_HOME=$HERMES_HOME \
  python3 scripts/cp015-demo-courses.py --only japanese-cafe
python3 scripts/cp015_record.py          # byte-identical to docs/concept-parity/demo/*.json
python3 scripts/cp015c-workshop-install-proof.py   # once a pack exists
```
