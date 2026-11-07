# M1 mode parity, structured check items and answer-leak proof

Card: `t_ff6ce87a`. Branch: `wt/m1-mode-parity` (base `4a33f2d`, parent `wt/m1-textbook-guided`
merged as `9d4d380`).

## What this proves

`tests/test_m1_mode_parity.py` runs the real kernel (SQLite migrations, RPC dispatcher) and the
real `desktop/plugin.js` through React (`react-dom/server`), not a copy of it.

| Claim | Test | Result |
| --- | --- | --- |
| Textbook and Guided keep the same document id, block ids, role order and objective id | `ParityTest.test_textbook_and_guided_keep_the_same_blocks_check_and_sources` | PASS |
| The one check attaches to the same practice block in both views, with one check surface per view | same test (`data-cb-block-check`, `data-cb-check-surface`) | PASS |
| The block's source id renders as its course source chip in both views | same test | PASS |
| A view switch bumps no revision, opens no attempt and moves no check | `ParityTest.test_a_view_switch_changes_no_revision_or_attempt` | PASS |
| The reference answer and rubric text never appear in `check.get`, `lesson.page`, or either rendered view, before or across a switch | `AnswerLeakTest` (with a negative control that proves the detector is not vacuous) | PASS |
| The structured checklist fixture prints each label once in both views | `RepeatedChecklistRegressionTest.test_structured_fixture_prints_each_label_once` | PASS |
| The old duplicate-checklist fixture prints each label once | `RepeatedChecklistRegressionTest.test_old_fixture_prints_each_label_once` | **expected failure — open defect** |
| `stimulus.items[]` survives `check.get` and duplicates are rejected | `StructuredCheckItemsSeamTest` | **expected failure — seam missing** |

## The open defects (measured, not inferred)

1. **Repeated checklist labels.** A section whose prose carries a checklist and whose check prompt
   repeats it reaches `lesson.page` as a teaching block *and* a `check_prompt` practice block, so
   the Textbook view prints every label three times (prose, practice block, check surface).
   Measured by `test_old_fixture_duplicates_labels_today`: 3 occurrences per label, contract is 1.
2. **No structured check items.** `contracts/rpc.v8.json#/$defs/check_stimulus` admits only
   `prompt`, `format`, `choices`, `learner_instructions`; `coursebook/domain.py:_stimulus_view`
   projects that closed allowlist. A stored `items[]` is dropped (`items_served: null` in
   `evidence.json`), so no view can render one label per item and no duplicate/near-duplicate
   rejection can exist. Owner: UI (`vellum`); the contract change is `cinder`.

The two `@unittest.expectedFailure` tests are deliberately strict: they turn into an unexpected
success (and fail the suite) the moment the seam lands, so the gate cannot rot.

## Reproduce

```sh
python3 -m unittest tests.test_m1_mode_parity -v      # OK (expected failures=3)
python3 -m unittest tests.test_desktop_lesson_views -v # parent renderer suite must stay green
```

`evidence.json` is written by the run (parity ids, attempt state, duplicate counts, seam output).
Ids are minted by each test run, so re-running the suite rewrites the file with fresh ids; the
structure and the measured counts are what the artifact asserts.

## Not measured

* A live Guided page: no writer authors block `short`, so every live `lesson.page` is
  `textbook_only` (`t_7890cf1f`). Guided is proven at the renderer over a validated v8 document.
* Live rig frames or a graded chat turn: no isolated backend/Electron window was mounted for this
  card, and no screenshot or chat shot is claimed.
* Horizontal overflow / 200 % text: not measured here (no browser window); the parent card's
  six route-gated frames remain the only such evidence and are not re-asserted.
