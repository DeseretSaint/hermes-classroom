# H-157 evidence — Course Detail and Field Quest composition

Card: `t_821f0924`. Branch `wt/h157-detail-quest` (H-148 merged in at `6d96263`).
Product half: `desktop/plugin.js`. Tests: `tests/test_desktop_h157_detail_quest.py`,
`tests/test_desktop_field_quest.py`.

## What changed

**Course Detail is four primary surfaces.** `Overview`, `Learn`, `Notebook`, `Evidence`. `Learn` is
the reading surface; the section page keeps the Textbook / Guided / Field Quest switch over the same
document, so the three reading modes are one way in rather than three peer tabs. Everything that is
reference or administration sits under one `More` disclosure: `Attempts`, `Plan`, `Sources`,
`Export` (Export only when the backend advertises `course.export.read`). Every legacy view id still
resolves through `primarySurfaceFor()`, so a direct link lands where it names, `More` opens itself
for that view, and back behaviour is unchanged.

**Field Quest is a path.** The section title is the `h2`; `N missions, N checkpoints` is a caption;
one evidence line follows it; the "What these counts mean" disclosure is gone. Each mission is the
number node, a serif title, a one-sentence brief (`nowrap` + ellipsis) and one way into Textbook.
The full prose, the media and the audio studio stay in Textbook; the notebook save and pronunciation
controls stay at the block because every lesson view offers them there (H-79/H-96 parity). The
checkpoint keeps the section's single real check — it is the only prose block left on the page
because it is the interaction, not the lesson text.

**Copy defects the engagement audit assigned to this card.** `EvidenceView` now says *What to do
next*, *What the evidence shows*, *Your attempts*; the raw `basis:` predicate moved inside a closed
*Technical detail* panel; "layer 2 / persona claim" prose is gone. A single `plural(n, one, many)`
helper replaced `file(s)`, `check(s)`, `page(s)`, `command(s)`, `N objectives` and the syllabus
"N of M items have a decision" template.

No new data, no new tab, no second lesson view, no XP/level language, no change to the lesson
document, the check contract, evidence states or count semantics.

## Q1–Q6

| Q | Claim | Evidence |
|---|---|---|
| Q1 First-screen grasp | The course title is the `h2`, `Learn` is the current surface, and one primary action (`Start a fresh run` / `Resume the lesson`) sits in the hero. The tab row names four places, not eight. | `docs/h157-shots/detail-1049.png`, `detail-460.png`; measured `h1Count 1`, `headingTag H2`, `primaryLabels [Overview, Learn, Notebook, Evidence]`, `selected [Learn]` at 1049/900/460 |
| Q2 One primary action | The hero keeps one filled action; `More` is a disclosure of text buttons, never a second primary. | `tabs-1049.png`, `more-1049.png`; `more.after.visible [Attempts, Plan, Sources, Export]` with the summary still reading `More` |
| Q5 Authored visual | The tab row is a 2px accent underline on the current surface; `More` is a quiet text disclosure; Field Quest keeps the numbered ochre spine and one lamp checkpoint field. | `tabs-900.png`, `quest-light-1049.png`, `quest-dark-1049.png` |
| Q6 Lesson loop | Learn → section page → Textbook/Guided/Field Quest over the same document; the checkpoint still holds the document's own check node once. | `parity-textbook-light-1049.png`; `test_quest_and_textbook_render_the_same_block_id_set`, `test_the_check_node_sits_on_the_checkpoint_once` |

## Live capture (isolated Electron rig, not the operator window)

Harness `scripts/h157-capture.mjs`, rig `~/.hermes/coursebook-test-h157-002738`, CDP 9348, plugin
copy `sha256 1c46d6dfc86283dbee9150591eda39a1b7f7b11740704b9c7ff3e8fa87694852` (identical to the file
the tests read), backend `127.0.0.1:44219`.

| width | inner | route | view | tabs | More items | tab row | page overflow | route overflow |
|---|---|---|---|---|---|---|---|---|
| 1049 | 1049 | 789 | textbook (Learn) | 4 | 4 | 45 px | 0 | 0 |
| 900 | 900 | 640 | textbook (Learn) | 4 | 4 | 45 px | 0 | 0 |
| 460 | 460 | 460 | textbook (Learn) | 4 | 4 | 45 px | 0 | 0 |

200% text at 460: 4 tabs, `tabRowHeight 176`, `tabRowScroll 0`, page/route/More overflow 0.

Keyboard: real `ArrowRight` presses move the selection and the focus through
`overview → learn → notebook → evidence`; the focused tab paints `2px solid` accent
(`rgb(168, 192, 242)`) with a 2px offset (`data-cb-tab-focus="ring"`). Roving tabindex: one tab stop.

`More` behaviour: opening the summary at 1049 paints `Attempts / Plan / Sources / Export`; choosing
`Plan` leaves `data-cb-course-detail="plan"`, `More` open with summary `More · Plan`, the notice
*"You are reading plan from More…"*, and `Learn`/`Overview` still one click away. Evidence shows the
three plain labels, `hasL3 false`, `hasLayer false`, `technicalOpen false`.

## Field Quest (renderer frames, and why)

The live demo profile serves **no** Field Quest document: `lesson.page` for the Japanese classroom
returns `views {"textbook":false,"guided":false,"field_quest":false,"field_notes":false}` (same
answer as H-96 recorded). Claiming a live Field Quest capture would be inventing a surface, so the
frames come from the shipped `FieldQuestView` through the M2-U2 frame pipeline
(`scripts/h157-quest-frames.py` → `scripts/m2fq-shot.mjs`): real React, the real `AttemptControls`
checkpoint, at 1049 / 900 / 460 plus dark and 200% text. Measured `missions=4 checkpoints=1
overflow=false` at every width, `font=32px` at 200%.

Frames: `quest-light-1049.png`, `quest-light-900.png`, `quest-light-460.png`,
`quest-dark-1049.png`, `quest-light-460-200pct.png`, `parity-textbook-light-1049.png`.

## Tests

- `tests.test_desktop_h157_detail_quest` — 11 OK: four primary surfaces, Learn is one surface,
  More contents, Export gating, legacy-view mapping, `plural` branches, no plural placeholder,
  plain Evidence labels, `basis` inside the closed panel, one summary line.
- `tests.test_desktop_field_quest` — 67 OK: section title is the `h2`, counts are a caption, no
  hero facts, no count disclosure, one evidence line, one-line brief + one Textbook action, no row
  trap, media/prose in Textbook, all previous parity/check/lock guarantees intact.
- Desktop suite `test_desktop_*.py` — 509 OK. Full suite — 1971 tests, only the M4 pin failed, and
  `scripts/m4v-audit.py` was regenerated at this module (`15 PASS / 0 not PASS`, 21 frames).
- `scripts/validate-plugin.sh --worktree` — 4/4 PASS.

## Open, honest limits

- The live backend's own recommendation text still contains `1 objective(s) have no cold independent
  evidence yet.` That string is produced in Python (`coursebook/evidence.py`), not in the pane; the
  Desktop half cannot rewrite it without changing backend copy, which is outside this card.
- Field Quest remains renderer-proven until a backend authors `short` prose; the same limitation H-96
  recorded.
