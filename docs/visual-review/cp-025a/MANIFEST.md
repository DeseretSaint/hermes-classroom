# CP-025a — review packet (Game band, homework action/sheet/notebook list, homework studio)

Maker: `vellum`. Reviewer: `quill` (see `SCORECARD.md`, left blank).
Branch `wt/cp-025a-adopt`. Module under review: `desktop/plugin.js`
sha256 `e9fd149a5375bb638a9c4d20c420ce117f32858f4409efa90bddd8236e840bfb`
(20 segments, rebuilt by `scripts/build_plugin.py`). Every stamp in this folder pins that sha.

Scope of this card: the GM-010 Game header/journal and the GM-008 homework action, sheet and
notebook list, rebuilt on the v3 contract. The take-home/homework paint in `desktop/src/95-studio.js`
had already landed with CP-025b, so this card's studio delta is verification plus the v3 markers and
the parts CP-025b did not own (sheet card/actions/record/list/empty state, the move off `sdk.Button`,
`CbAction` and `sdk.Badge`).

## Frames (all live, all stamped by `scripts/cp-capture.mjs`)

| frame | route · destination | route box (CSS px) | scope | primary claim |
| --- | --- | --- | --- | --- |
| `game--course-home--1049--light--100` | `#/coursebook` → course `crs_b4b56fc2…` | 1049×1166 | light | Game band above the trail: `25 XP` in a gold-edged ink-text chip, `Level 1 Curious - cosmetic`, `0 of 4 steps`, `Play progress, not evidence.` |
| `game--course-home--1049--dark--100` | same | 1049×1166 | dark | same band and journal on the dark scope |
| `game--course-home--900--light--100` | same | 900×1166 | light | band and trail at the middle breakpoint |
| `game--course-home--460--light--100` | same | 460×1166 | light | band wraps to a single column, no horizontal overflow |
| `game--course-home--1349--light--100` | same | 1349×1166 | light | wide composition |
| `game--course-home--1049--forced-colors` | same | 1049×1166 | forced colours | band survives forced-colours mode |
| `game--journal--1049--light--100` | same, scrolled to the journal | 1049×1166 | light | the Field journal is one paper object with a hairline list and the honest line "No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page." |
| `game--textbook--1049--light--100` | same course, Textbook view | 1049×1166 | light | no Game band, no XP on the Textbook view |
| `homework--studio--1049--light--100` | `#/coursebook` → studio → Homework tab | 1049×1166 | light | Parent Studio → Homework: one row per recorded task, paper state chip, quiet `Show the sheet` |
| `homework--sheet--1049--light--100` | studio → Homework → `Show the sheet` | 1049×1166 | light | one-page field card (target + romaji + meaning, Where and when, Do this, Done when, sources) with three quiet actions and "Local only. Nothing is sent." |
| `homework--sheet--460--light--100` | same | 460×1166 | light | the card and its quiet actions stack at the narrow width with no clipping |

PNGs are 2× device pixels (2098×2332 for a 1049-wide route). Commands: the cells were produced with
`scripts/cp-capture.mjs --destination "#/course/<id>"` (Game) and
`--destination studio --click "[data-cb3-tab=\"homework\"]" [--click "[data-cb-homework-record-action=\"toggle-sheet\"]"]`
(homework). `--require-v3` was passed on every cell.

Side-by-side boards (render | reference | diff) are committed beside the frames:
`sbs-game-course-home-1349-vs-map.png`, `sbs-homework-studio-1049-vs-system.png`,
`sbs-studio-314-vs-system.png`, `sbs-courses-314-vs-classroom.png`. Read the caveat below before
scoring them.

## Binding visual gate (`docs/concept-parity/VISUAL-GATE.md`)

`cd visual && node find-cdp.mjs` → `9371` (this window) and `9381` (a second rig on the host).
`node audit.mjs --port 9371` → **PASS**, exit 0, `visual/report.json` written at
`2026-11-10T23:54:26Z`:

- window width **1440**; the four audited routes (`home`, `courses`, `workshop`, `studio`) each
  `ready=true` with the route pane measured at **314×900** (the session/chat pane was open, so the
  pane is not the reference breakpoint — see the caveat below);
- fonts: **CB Display loaded true, CB UI loaded true, present true** on all four routes;
- axe: **0 violations** on all four routes (`violations: []`), so no serious/critical ids;
- `data-cb-scope`: the audited frames are **light**; the stamps of the dark cells record
  `theme: dark` inside `[data-cb-route]`;
- pixel diff against baseline: `baseline: created` on all four routes (first run of this audit on
  this tree — there is no earlier baseline to diff, `diff=n/a`), which is recorded rather than
  claimed as a zero diff.

`scripts/compare-ref.sh` (sheet paths under `visual/compare/`):

| render | reference | similarity | sheet |
| --- | --- | --- | --- |
| `docs/visual-review/cp-025a/game--course-home--1349--light--100.png` (1041×900 crop) | `docs/concept-parity/refs/map.png` | **0.6881** (rmse 0.311864) | `visual/compare/game-1349-sheet.png` |
| `docs/visual-review/cp-025a/homework--studio--1049--light--100.png` (810×900 crop) | `docs/concept-parity/refs/system.png` | **0.7198** (rmse 0.280175) | `visual/compare/homework-studio-sheet.png` |
| `visual/frames/courses.png` (314×900) | `docs/concept-parity/refs/classroom.png` | 0.6699 (rmse 0.330124) | `visual/compare/courses-sheet.png` |
| `visual/frames/studio.png` (314×900) | `docs/concept-parity/refs/system.png` | 0.7186 (rmse 0.281436) | `visual/compare/studio-sheet.png` |

**Caveat the reviewer must apply (gate rule 1 and 2):** none of the approved references is a Game
band, a take-home sheet or a Parent Studio homework list — there is no per-surface reference for
these three surfaces in `docs/concept-parity/refs/`. `map.png` and `system.png` were used as the
nearest approved system frames, so the similarity numbers are indicative of palette/material and
composition family only; they are **not** a parity verdict. The card's own frames are also captured
at 1049/900/460/1349 route widths, not the reference's 1344-wide landscape, and three of the eleven
are composite crops from the door. The parity verdict therefore belongs to CP-040
(`t_5403e4a1`), which owns the union capture matrix.

## What the code claims, and where it is proven

| claim | evidence |
| --- | --- |
| The Game band and journal read only v3 roles/type, name no role or step the contract does not define, and the band owns no filled control | `tests/test_cp_025a_homework_game_v3.py::test_game_surfaces_read_the_v3_contract_only`; frame `game--course-home--1049--light--100` |
| The band is honest: real XP, cosmetic level, `Play progress, not evidence.`, one progressbar capped at the assigned steps, `No steps assigned yet` when nothing is assigned, and no mastery/grade/score/star word | `::test_game_header_keeps_the_honesty_contract` (also proves the 3 of 3 cap and the empty case) |
| The band keeps a loading and an error state with one quiet action instead of collapsing | `::test_game_header_states_keep_the_band` |
| The journal is one `PaperCard` with a hairline list, `data-cb-game-card` per section, and an earned/total count from recorded evidence only | `::test_game_journal_is_one_paper_object_with_real_stamps`; frame `game--journal--1049--light--100` |
| `data-cb-game*` markers, counts and aria are unchanged from GM-010, and the band mounts only in Game mode with a real engagement row | `tests/test_desktop_gm010_engagement_ui.py` (10 tests, incl. the 2-mount / 3-reader guard and the `mode === 'game'` gate) |
| The homework action stays one quiet control in the shared section footer with `data-variant="text"` and `aria-expanded`, and no dialog | `tests/test_desktop_gm008_homework_ui.py`; `::test_homework_action_is_one_quiet_control`; frame `homework--sheet--1049--light--100` shows the placed panel |
| The sheet is one page: one target, one context, at most three steps, one `Done when`, marked Japanese, three quiet actions and no filled control | `::test_homework_sheet_keeps_one_task_and_the_v3_material`; frames `homework--sheet--1049--light--100`, `…--460--light--100` |
| A take-home card claims no XP, grade, score, mastery or answer | `::test_homework_sheet_keeps_one_task_and_the_v3_material` (forbidden-word scan) |
| The homework list has an authored empty state, and the studio/list/record carry their v3 markers | `::test_homework_list_empty_state_is_authored`, `::test_studio_and_notebook_lists_carry_v3_markers`; frame `homework--studio--1049--light--100` |
| No v2 token, `sdk.Button`, `CbAction` or `sdk.Badge` survives in the rebuilt regions; no raw colour, gradient, shadow or `vw` | `::test_game_surfaces_read_the_v3_contract_only`, `::test_homework_surfaces_read_the_v3_contract_only` (both call the shared `assert_v3_only` scan) |
| The homework surfaces use three quiet actions and no primary inside the sheet actions | `::test_homework_surfaces_read_the_v3_contract_only` (`variant: 'quiet'` ×3, no `'primary'`) |

## Known gaps (honest, not hidden)

1. **200% text has no stamped frame.** The CP-038 door normalises the root text size to 16 px
   (`text_scale_root_px: "16px"` in every stamp), and a `--200` cell produced that way is not a
   200% frame. It was deleted rather than shipped mislabelled. 200% text for these surfaces is
   covered by the render harness and by CP-029's `text.200.*` probes; CP-040 must produce the
   stamped 200% cell.
2. **The lesson-surface take-with-you action has no frame.** The CP-038 door can only reach
   `#/learn/<objective>` through `[data-cb-section-row]`, which the v2 FieldDesk course home on
   this tree does not render; the door refuses with
   `docs/visual-review/cp-025a/homework--lesson--1049--light--100.refused.json`:
   *"requested destination #/learn/obj_abd7964162db49ad892ee1b3a63adf21 has no addressable control
   on the current surface ([data-cb-section-row=…])"*. The footer's DOM contract, its quiet variant
   and its no-dialog behaviour are proven by `tests/test_desktop_gm008_homework_ui.py`, and the
   placed-instance frame is CP-040's (it owns the union course page that renders section rows).
3. **State frames (loading, error, blocked, empty, offline) are harness-proven, not stamped.** The
   door has no `--state` hook; CP-040 owns forcing them.
4. **Dark scope is captured for the Game band only** (`game--course-home--1049--dark`); the
   homework sheet and studio frames are light scope.
5. **The `cp-capture` backend probe reports `HTTP 401`.** The door's direct API probe uses a token
   the isolated backend refuses; the frames are still live product state because the window loads
   its data through its own authenticated connection (the sheet shows the rig's real recorded task,
   `いただきます`, and the journal's earned count matches `game_engagement`). Recorded so the
   reviewer does not read the 401 as a fixture.
6. **Attendance at the reference breakpoint is CP-040's.** The gate audit ran with the chat pane
   open (314 px route); the frames here are 1049/900/460/1349 route boxes with the door's own
   emulation, not a 1344×768 full-window frame.
7. **Primitive/token requests:** none. Nothing in this card needed a change outside
   `desktop/src/30-home.js` and `desktop/src/95-studio.js`.

## Reproduce

```
python3 scripts/build_plugin.py && sha256sum desktop/plugin.js   # e9fd149a…
python3 -m unittest tests.test_cp_025a_homework_game_v3 tests.test_desktop_gm008_homework_ui \
  tests.test_desktop_gm010_engagement_ui tests.test_plugin_build tests.test_m4_visual_audit
cd visual && node audit.mjs --port <cdp> && cd ..
scripts/compare-ref.sh docs/visual-review/cp-025a/game--course-home--1349--light--100.png \
  docs/concept-parity/refs/map.png visual/compare game-1349
```
