# Homework — away-from-screen tasks (GM-007)

Homework is a small object, not a hidden chat request and not a second course. `coursebook/homework.py`
owns the whole backend path and `cb.rpc` v24 carries it on the wire.

## The object

One task names **one target, one context, one observable success criterion**, at most three steps and
3–10 minutes. The target carries its display text, reading, romaji, meaning, register and the
`source_ids` of the entries that support it; the task carries `audience` (`learner` or `parent`) and
an authored `completion_record` (`breakfast / lunch / dinner`, `Day 1 / Day 2`, or one plain tick).

`homework_tasks` and `homework_events` are the tables GM-001 froze in migration 0013; nothing here
adds a column, and nothing here writes an attempt, a transition, evidence, a notebook entry or an
engagement row. `game_engagement` is `engagement.award`'s business.

## The four commands (`cb.rpc` v24, additive over v23)

| Method | What it does | What it cannot do |
|---|---|---|
| `homework.create` | Proposes one task from the lesson's authored `page["homework"]` block, after the policy accepts it. Dedupes a second proposal for the same enrollment/objective/audience/kind. | Create a task from a generic duration, two targets, a photo/recording/geolocation request, a graded criterion, an unsourced phrase, or an objective that is not transfer/production/procedure (or an observation check). |
| `homework.read` | Returns the task, its append-only events, its cited sources and the one-page sheet — the notebook and Parent Studio view. | Return attempts, notes, tutor turns, engagement, a chat thread or a course. |
| `homework.complete` | Writes `self_reported_done` (learner) or `parent_reported_done` (parent) plus one event. A second report is the same state, never a second basis. | Write a pass, a score, mastery, a verdict, XP, or `independent_verification: true`. A parent report is not independent verification; a later retrieval check is a separate object. |
| `homework.skip` | Records `skipped` with one event. | Penalise, break a streak, or overwrite an existing report. |

Policy refusals are `POLICY_VIOLATION` with a discriminating `details.reason`:
`generic_task`, `multiple_targets`, `no_transfer_target`, `no_homework_proposal`,
`unsourced_target`, `surveillance`, `graded_completion`, `context_missing`,
`multiple_contexts`, `too_many_steps`, `criterion_not_observable`, `minutes_out_of_range`,
`task_closed`, `already_reported`.

## The Japanese demo fixtures

`bundled/homework/japanese-l0-mealtime/proposals.v1.json` holds **no Japanese of its own** for the
three lesson tasks. They are derived at load time from the reviewed L0 lesson fixture
(`bundled/homework/japanese-l0-mealtime/fixture.json`, GM-014, approved): pre-meal
`いただきます` / *itadakimasu*, post-meal `ごちそうさまでした` / *gochisōsamadeshita*, and a label
set `ドア・まど・いす` from the lesson's six labels. Task copy, target, reading, romaji, meaning,
register and source ids are copied, not re-typed, so the homework cannot drift from the lesson a
reviewer approved. The fixture's register note is carried across unchanged: `いただきます` has no
dictionary register label and "polite (ます form)" is the fixture author's analysis, not a
dictionary claim; `ごちそうさまでした` is labelled Polite (teineigo) by Jisho.

One task is authored here: the **optional** cafe question `これはいくらですか` / *kore wa ikura desu
ka* ("How much is this?"), cited to Jisho's これ ("this; this one") and いくら ("how much") entries,
both accessed 2026-11-10. Skipping it is explicitly offered as honest. No cultural claim is made;
no native-speaker review is recorded or claimed.

## The one-page sheet

`homework.sheet_html(task)` is a field card, not a worksheet: eyebrow, title, target, reading,
gloss, one context, up to three steps, the authored tick row, the success criterion, the minutes,
a source line and a footer. Every colour is a grey value (`#111`, `#333`, `#555`, `#fff`), there is
no grid, no red pen, no grade and no streak, and every Japanese run carries `lang="ja"` in the
HTML. Printing is local (Chromium → PDF, A4 or Letter); nothing is sent anywhere.

`scripts/gm007_homework_proof.py` renders and measures the committed proof under
`docs/visual-review/gm-007/`: 7 PDFs (4 A4, 3 Letter), 7 page PNGs and 4 grayscale proofs, with
page count, page size, extracted Japanese text and measured ink coverage in the manifest. A failed
measurement raises before the manifest is written.

## Wire publication

`cb.rpc` **v24** = v23 (GM-005 take-home) + exactly `homework.create`, `homework.read`,
`homework.complete`, `homework.skip` (87 declared methods). `contracts/rpc.v23.json` stays
byte-identical (`sha256:b8988994…3182`); `scripts/gm007_rpc_v24.py` rebuilds v24 deterministically
from it. `tests/test_contracts.py::V24AmendmentTest` pins the additive diff, the closed payloads and
a `homework_task` definition that cannot express a grade, score, mastery, verdict, XP, points or
streak.

Not done here, by design: a native-speaker review (not claimed), any external send, any second
course, any learner-facing answer key, and any XP in the artifact.
