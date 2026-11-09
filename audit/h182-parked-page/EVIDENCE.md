# t_3a3c6ea1 — a parked `needs_review` lesson must not be presented as learner content

Card: `t_3a3c6ea1` (H-182 follow-up, opened by `t_82572eb0`).
Branch: `wt/h182-parked-page`, base `0ee63d4` (local, unpushed).
Wire: **no change** — `cb.rpc` stays v20 and `cb.db` stays v12. Only two strings changed: the
`lesson.page` empty-document `view_note` for a parked section, and the display `title` of a parked
section's blueprint-tab files.

## The defect, restated against the durable rows

Disposable profile `~/.hermes/coursebook-test-h182d3`, plan `013730ca0f7b3397`, section
`024fd4bf69b32c60`, lesson `cff5e1dd74ab8064`, check `39af38aad5fa74fb`:

```
gen_lessons cff5e1dd74ab8064  state=needs_review  version=1  section=024fd4bf69b32c60
gen_plan_sections 024fd4bf69b32c60  objective_refs=[1]  ordinal=1
checks 39af38aad5fa74fb  state=closed  audit_state=failed
```

The refusal is correct (H-185/H-194: `_authored_lesson_page` never returns a `needs_review` row;
an empty document attaches no check because there is no block). The **copy** was false on both
surfaces: `lesson.page` said "This section has no teaching content yet." and Studio → Pages listed
the parked export as an ordinary learner page.

## What changed

1. `coursebook/domain.py`
   * `_authored_lesson_rows` — the `(plan → section → latest revisions)` join, now shared.
   * `_authored_lesson_page` — unchanged behaviour: it still serves only `validated`,
     `model_assessed` or `parent_approved`, newest first, so a parked edit falls back to the
     cleared revision and a section with no cleared revision is still refused.
   * `_parked_lesson_page` — read-only detection of a newest revision in `needs_review`; it never
     serves the page and never touches the check.
   * `lesson.page` — when the fallback document is empty **and** a parked authored revision
     exists, `view_note` becomes:
     > A generated lesson page exists for this section but is awaiting review, so it is not
     > served until it is approved. Its check stays closed until then.

     The document stays `state: "empty"`, `blocks: []`, `check_id: null`, `provenance: null`.
2. `coursebook/parent_authoring.py`
   * `blueprint_tabs` prefixes the tab file title with `Needs review · ` for a section whose
     `lesson_state` is `needs_review`, in every tab that shows that section's authored text
     (`learner_pages`, `parent_guide`, `answers`, `narration`). The title is display-only: the
     export paths and the content hash never read it, and the file's `sha256`/`bytes` are still
     over the full declared text. Served sections are unmarked.

Nothing weakens the serving rule: no `needs_review` page is served, no check is opened, and no
closed check is reopened as a side effect of reading the page.

## Verification

### RED on the base commit (`0ee63d4`), same test file

```
FAIL: test_a_parked_section_is_marked_in_the_pages_tab
  AssertionError: False is not true : 01 · A sharper first section
FAIL: test_a_parked_page_is_not_served_and_the_note_names_review
  AssertionError: 'awaiting review' not found in 'This section has no teaching content yet.'
Ran 6 tests ... FAILED (failures=2)
```

(The other four tests are guards that must also hold before the fix: the no-authored-page copy,
the cleared-revision fallback, and the closed check.)

### GREEN on `wt/h182-parked-page`

```
Ran 6 tests in 2.786s
OK
```

Tests (`tests/test_parked_lesson_page.py`):

* `test_a_parked_page_is_not_served_and_the_note_names_review` — empty document, no blocks, null
  check, null provenance, note names the review state, authored prose absent from the wire.
* `test_a_section_with_no_authored_page_keeps_the_empty_copy` — the generic empty copy is
  unchanged where it is true.
* `test_a_parked_edit_over_a_cleared_revision_still_serves_the_cleared_page` — H-194 fallback.
* `test_the_parked_check_cannot_be_opened_from_the_page` — no check reference; the stored check
  stays `closed`.
* `test_a_parked_section_is_marked_in_the_pages_tab` — real authoring pipeline, `lesson.revise`
  parks one section; `parent.blueprint.read` marks that section in every tab and leaves served
  sections unmarked.
* `test_the_parked_page_is_still_not_served_to_the_learner` — the parked version-2 edit never
  reaches `lesson.page`; the cleared version-1 page is still served.

Targeted regression set (lesson.page, H-194 fine-tune, Parent Studio, contracts, course export,
pack flow, H-191, H-182 plan repair, desktop lesson views):

```
Ran 320 tests in 60.177s
OK
```

Full suite (`python3 -m unittest discover -s tests -t .`, the same command `scripts/validate.sh`
step 1 runs; base `0ee63d4` is 2724 tests):

```
Ran 2730 tests in 412.087s

OK (skipped=1)
```

`scripts/validate.sh` (all five steps, on the committed tree): step 1 `Ran 2730 tests in 408.140s`
OK; step 2 `desktop/plugin.js: syntax OK`; step 3 catalog admission `Validation passed`; step 4
runtime contracts passed; step 5 `All 31 backend expectations passed against an isolated
HERMES_HOME` — `Validation passed.`

### Live re-read of the durable H-182/D3 rows (copy of the store, read-only source)

The source profile is never opened for writing: `data.db` (+ `-wal`/`-shm`) is copied into scratch
and every command runs with `db.use_store_scope(<copy>)`. Reproduce with
`PYTHONPATH=. python3 audit/h182-parked-page/live_read.py` from this worktree.

```
lesson.page ok: True
  document.state     : empty
  document.blocks    : 0
  document.check_id  : None
  document.view_note : A generated lesson page exists for this section but is awaiting review, so it is not served until it is approved. Its check stays closed until then.
  provenance         : null

parent.blueprint.read ok: True
  learner_pages Needs review · 01 · Green leaves and fading chlorophyll  (3381 B)
  parent_guide  Needs review · 01 · Green leaves and fading chlorophyll  (3795 B)
  answers       Needs review · 01 · Green leaves and fading chlorophyll  (1269 B)
  narration     Needs review · 01 · Green leaves and fading chlorophyll  (1629 B)
  sections: lesson_state=needs_review lesson_version=1 for 024fd4bf69b32c60;
            null for the two sections that were never authored
  export: {"ready": false, "blocked_reason": "no_final_approval"}
```

## Decision recorded

The Pages tab keeps showing a parked section (the parent needs to review the parked bytes before
approving or regenerating); what changes is that the tab no longer presents it as an ordinary
learner page. The marker lives in the file `title`, which the current desktop renders as the
section heading, so the surface is honest **without** a desktop edit and without a wire change.

If the desk later wants a distinct badge instead of a title prefix, `parent.blueprint.read`
already reports `sections[].lesson_state`; adding a `blueprint_file.state` field would be an
additive wire change and should be decided with Atlas (v20 is frozen).

Out of scope, untouched: the M4 re-pin, the request-bound fix on `t_82572eb0`, and any learner
serving rule.
