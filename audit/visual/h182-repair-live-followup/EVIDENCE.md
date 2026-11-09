# H-182 follow-up — measured correction and fix record

Read-only reconstruction of the live H-182/D1–D3 re-walk plus the fix landed on this branch.
No live generation was run for this record; every number below comes from the durable test-profile
database the walk left behind and from the real request builders.

| Field | Value |
|---|---|
| Evidence being corrected | `audit/visual/h182-repair-live/EVIDENCE.md`, commit `964de83` on `wt/h182-plan-repair` (not on `master`) |
| Code base for this record | `bc9f607` (`origin/master`), branch `wt/t_82572eb0` |
| Test profile read | `~/.hermes/coursebook-test-h182d3/home/plugin-data/coursebook/data.db` (opened `mode=ro`) |
| Plan / enrollment | `013730ca0f7b3397` / `enr_1690af0794f9426cba6486bf5b765236` |
| Plan digest at authoring time | `sha256:ce6335d077b42927485ce5b80048d9212025b13636de33dadf1d2403dda6197f` |
| Sections | `024fd4bf69b32c60` (obj 1), `89fe843751148c3e` (obj 2), `c5c6f1288404e3a0` (obj 3) |
| Sources in the ledger | 7, each with a 662-byte excerpt field |
| Live failing job | `job_ad2fbc9efef34cf1b0d3f93cb3dff8bd`, created `04:38:51Z`, failed `04:39:22Z` |

## Defect 1 — confirmed, and fixed

The live failure is reproduced from the same rows. `_author_section` builds the lesson-validation
payload with **both** the authored `lesson` and its learner-facing `page` (a projection of the same
lesson), and validation used to receive the **whole** research ledger while authoring received only
the section's cited sources. Rebuilding the live section through the pre-fix builder measures:

| Payload | Compact bytes | Bound |
|---|---|---|
| Pre-fix builder, live rows (lesson + page + 7 sources) | **24 240** | 24 000 |
| Live attempt-1 candidate (recorded in the job error) | **25 081** | 24 000 |
| Patched builder, same live rows | **13 265** | 24 000 |

The live number differs from the rebuild because the rebuild uses the stored attempt-2 page while
the live failure was attempt 1's candidate; the payload shape is the same and both are over the
bound. Both the duplication and the unfiltered ledger are gone in the fix:

- `build_lesson_validation_request` no longer serialises `learner_facing_page`; the lesson already
  carries every field the page publishes, plus the answer key the criteria need.
- lesson authoring and lesson validation now receive the same ledger slice — the section's cited
  sources, else the first four — via `_lesson_ledger` (`coursebook/generation.py`).

No bound was raised. `REQUEST_BYTES_BOUNDS` is unchanged (`single`/`short` 24 000, `full` 48 000).
The request now grows with the section, not with the course's research.

Tests (both RED on `bc9f607` before the fix; GREEN after):

- `tests/test_generation.py::LessonRequestBoundTest::test_the_validation_request_carries_the_lesson_once_and_the_section_ledger`
  — pre-fix: `GenerationRejected: request payload is 26804 bytes compact, over the 24000-byte request
  bound`; post-fix: the same payload is under the bound and carries only the section's two cited
  sources.
- `tests/test_generation.py::PlanWideLessonBoundTest::test_a_three_page_plan_wide_job_builds_every_request_inside_the_bound`
  — a real 3-page parent brief (`desired_pages: 3`), a 5-row research ledger, and a page-sized
  authored lesson; the plan-wide lessons job authors 3 sections and every lesson request is
  asserted under 24 000 bytes.
- `tests/test_generation.py::LessonRequestBoundTest::test_an_uncited_section_falls_back_to_four_ledger_rows`.

## Consequence: the recorded-transcript harness-e2e packet was regenerated

The packet's per-lesson `usage.input_tokens` is an estimate of the request text, so a smaller
validation request changes it. Regenerating the packet (`PYTHONPATH=. python3
audit/adversarial/harness-e2e/harness_e2e.py`) changed only those estimates and the manifest hashes:

| Scenario | lesson `usage.input_tokens` before → after |
|---|---|
| `bicycle_single` | 2 993 → 2 359 |
| `music_short` | 5 370 → 4 330 and 5 430 → 4 404 (its two lesson jobs) |
| `soldering_full` | e.g. 10 416 → 8 313 (six lesson jobs moved) |

No verdict, page, check, assertion or scenario outcome changed — the runner still prints
`overall: PASS (3/3 scenarios)`. `tests.test_harness_e2e` is 26 tests OK. This is recorded-transcript
evidence regenerated deterministically, not live generation.

## Defect 2 — intended behaviour; the evidence wording is wrong

`lesson.page` returned `document.state:"empty"` because the one authored lesson for that section is
**parked for review**, not because a servable page was dropped. The durable rows say so:

```
gen_lessons cff5e1dd74ab8064
  section_id        024fd4bf69b32c60   (objective 1)
  state             needs_review
  rejection_reasons
    lesson document: blocks[5].short [text_completeness] dangling_terminal_word:
      ends on 'through', so the sentence lost its complement
    learner-facing narrative contains the check reference answer or a keyed answer
```

- `_authored_lesson_page` (`coursebook/domain.py`) serves only `validated`, `model_assessed` and
  `parent_approved`; a `needs_review` row is refused by design (H-185/H-194), and the reader falls
  back to the durable segment projection, which is empty for a generated section.
- The check row `39af38aad5fa74fb` is `state:"closed"`, `audit_state:"failed"`. `_author_section`
  inserts a check `open` only when the lesson reached `validated`/`model_assessed`
  (`coursebook/generation.py`, the check insert beside the lesson insert). A closed check is
  therefore the correct record of a parked lesson, and `document.check_id:null` is correct: no open
  check exists.
- The `checks:[{...}]` array in the same response is a read of stored check rows, not a claim that a
  check is servable. It is honest that the row exists and is closed.

So the walk's sentence "the generated section page is not projected into the learner document" is
wrong. The page was authored and **refused** by two gates; serving it would have breached the
H-185/H-194 rule that no unapproved authored content reaches a learner. This card takes the
"reasoned decision" branch: no product change for Defect 2. The correction the original evidence doc
needs is in the next section.

### Correction to `audit/visual/h182-repair-live/EVIDENCE.md`

Replace the paragraph beginning "**Opening the lesson does not show the check.**" with:

> **Opening the lesson shows no page because the authored page was parked, not because a projection
> was lost.** `lesson.begin` (`mode:"resume"`) created `run_810cce0f…`, and the re-read
> `lesson.page` returns `document.state:"empty"`, `document.blocks:[]`, `document.check_id:null`,
> `view_note:"This section has no teaching content yet."`. The durable rows explain it: the one
> `gen_lessons` row for that section (`cff5e1dd74ab8064`) is `state:"needs_review"` with two
> recorded rejection reasons (a short that ends on "through" and a learner-facing narrative that
> carries the check's reference answer). A `needs_review` lesson is refused by `_authored_lesson_page`
> by design, and its check row `39af38aad5fa74fb` is stored `closed` (`audit_state:"failed"`), so
> `check_id:null` is accurate: there is no open check to attach. The response still lists the stored
> check row, which is a read of the row, not a servable check. **"Open one lesson and confirm its
> check renders" was not demonstrated** — the lesson was parked, so no servable page existed to
> render.

Replace verdict bullet 2 with:

> 2. the authored section page was parked `needs_review` (two recorded gate reasons) and is therefore
>    not served in `lesson.page` (`state:"empty"`, `check_id:null`, check row closed). This is the
>    designed refusal for unapproved content, not a projection defect; the page that Studio → Pages
>    lists is the parked file. The learner-facing wording for a parked page is tracked separately.

## Files changed on this branch

- `coursebook/generation.py` — `_lesson_ledger`; both lesson builders use it; the validation payload
  no longer duplicates the learner page.
- `tests/test_generation.py` — the three tests named above.
- `audit/adversarial/harness-e2e/evidence/*.json` + `manifest.json` — regenerated packet; only the
  per-lesson `usage.input_tokens` estimates and hashes moved.
- `docs/GENERATION.md` — the ledger row builder is named for lesson passes.
- `CHANGELOG.md` — one entry under "Fixed during the candidate".
