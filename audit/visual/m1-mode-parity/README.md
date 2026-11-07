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
| The old duplicate-checklist fixture prints each label once (was 3x) | `RepeatedChecklistRegressionTest.test_old_fixture_prints_each_label_once` | PASS |
| A prose sentence that merely contains a label is not stripped | `RepeatedChecklistRegressionTest.test_a_prose_line_that_merely_looks_like_a_label_is_kept` | PASS |
| `stimulus.items[]` survives `check.get`; unknown stored keys still do not | `StructuredCheckItemsSeamTest.test_check_get_projects_structured_items_and_drops_unknown_keys` | PASS |
| Duplicate and near-duplicate item labels are rejected with a reason | `StructuredCheckItemsSeamTest.test_a_near_duplicate_label_is_rejected_with_its_reason`, `...test_duplicate_or_repeated_instructions_are_rejected` | PASS |
| Instructions that only repeat the prompt are rejected | `StructuredCheckItemsSeamTest.test_instructions_that_only_repeat_the_prompt_are_rejected` | PASS |
| The check surface itself renders one label per item, once | `CheckSurfaceItemsTest.test_check_surface_renders_each_item_once` | PASS |

## The defects and their resolution

1. **Repeated checklist labels (closed).** A section whose prose carried a checklist and whose
   check prompt repeated it reached `lesson.page` as a teaching block *and* a `check_prompt`
   practice block, so the Textbook view printed every label three times (prose, practice block,
   check surface). The renderer now treats a prose line that normalises to a structured check
   item's label as check data: `withoutCheckLabels()` in `desktop/plugin.js` drops that whole line
   from the document block in both views, and the single check surface prints it once. The same
   normalisation rule (case, spacing and punctuation ignored) is applied by the backend validation,
   so the print-once rule and the reject-on-read rule cannot disagree. Measured:
   `label_counts_before` 3 → `label_counts` 1 for all four labels in `evidence.json`.
2. **No structured check items (closed).** `contracts/rpc.v8.json#/$defs/check_stimulus` now admits
   an optional `items[]` of `{id, label}` (max 24 items, 200-character labels, closed item object),
   and `coursebook/domain.py::_stimulus_view` projects and validates it. `check.get` refuses a
   duplicate/near-duplicate label (`VALIDATION_FAILED`, reason `duplicate_check_item_label`, with
   the offending `items[n].label` field) and `learner_instructions` that only repeat the prompt
   (`reason: instructions_repeat_prompt`). The addition is additive inside v8: no existing method
   schema moved, `items` is not a required stimulus key, and an older stored check is served with
   `items: []`. A smuggled `reference_answer` is still dropped.
3. **Rendering.** `AttemptControls` now renders the stimulus it reads (`check.get`: prompt,
   instructions, choices, and the item list with `data-cb-check-item` per item) once, and the pane
   fetches that read after `check.open` only when the build implements `check.get`. `SectionPage`
   passes the item labels to `LessonDocumentView`, which is how the document blocks know what not
   to reprint. `AttemptControls` is exported as a test seam so the surface is rendered by real
   React in a test, not asserted from source.

## Reproduce

```sh
python3 -m unittest tests.test_m1_mode_parity -v      # 13 tests, OK (no expected failures)
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
