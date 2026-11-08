# H-149 evidence — the lesson player

Branch `wt/h149-lesson-player`, based on `66ac373` + H-148 (`wt/h148-path-truth` @ `a27231d`).
Plugin under test: `desktop/plugin.js` sha256 `e92039afba00843863f1a5a6b50c8c4994be7e42fc845e80d56076c66935975e`.

## What changed

- `LESSON_VIEWS` gains `player` (`Game`) as the first and default presentation view; Textbook, Guided
  and Field Quest stay selectable. Player + Textbook are always available; Guided/Field Quest keep
  their authored-document requirement and their plain-words reasons.
- `LessonPlayer` (new): header bar (`Section N` · `Game` · check count · `Step x of y` · `Exit`), one
  concept per step from the document's own blocks, the document's media/sources/notebook action, the
  section's one check on the block that carries it, and one footer primary — `Continue` → `Check` →
  `Continue`/`Try again` → `Finish` → close plate. Enter runs the footer action; a textarea keeps
  Enter for newlines.
- `PlayerVerdict` (new): two words only, `Correct` / `Not quite`, the learner's own answer, the
  backend's criterion text as the reason ("The part that did not hold: …"), and an explicit free
  retry. No colour-only signalling, no score, no percentage.
- `PlayerClose` (new): "You finished Section N", the enrollment row's own `independent` /
  `total_objectives` / `review_due`, one primary `Back to the path`.
- `AttemptControls`: optional `playerMode` / `playerController` / `onPlayerState`. In player mode the
  answer card paints no button of its own and reports its phase so the player footer is the only
  primary; the reference views are unchanged.
- `SectionPage`: `defaultLessonView = 'player'` prop (the seam the Home settings sheet will pass),
  the chat action demoted to secondary while the player is on screen, and the old page footer hidden
  in player mode (the player owns the one footer).

## Verified with real output

- `python3 -m unittest tests.test_desktop_h149_lesson_player` → **22 tests OK** (default surface,
  header copy, one concept per step, check placement incl. unattached check, one footer primary,
  Enter/text guard, Correct and Not quite copy, close facts, no score/XP/percentage words, no
  player-authored animation, Textbook retained).
- `python3 -m unittest tests.test_desktop_lesson_views tests.test_desktop_field_quest
  tests.test_desktop_procedure tests.test_locale_scaffolds` → OK after updating the view-set
  assertions to the new four-view contract.
- `python3 -m unittest tests.test_desktop_a11y_structure` → **11 tests OK** (the harness now exits the
  section through the player's `Exit`, since the page footer is gone in player mode).
- `python3 scripts/m4v-audit.py` → regenerated `audit/visual/m4-visual/audit.json` for the new plugin
  hash; **15 claims PASS, 0 not PASS**.
- Live isolated Desktop (`scripts/cb013-live-window.sh`, backend `127.0.0.1:44219` cb.rpc v14,
  `scripts/h149-capture.mjs`, state `~/.hermes/coursebook-test-h149`, CDP 9359):
  - the player is the mounted surface: `data-cb-lesson-view="player"`,
    document `doc_a1a4958c6d9d21aaf2bb`, bar `Section 2 | Game | 1 check in this section | Step 1 of 2 | Exit`;
  - step 1 shows one concept (58 chars) and the footer primary `Continue`; step 2 hosts the real
    check (`Check v2`, `comprehension`, the served prompt) with the footer primary `Check` disabled
    until an answer exists;
  - the same document id is served in `Game` and `Textbook`; `Guided` renders disabled with its
    authored reason;
  - measured 1049 / 900 / 459 CSS px in dark and light: `overflowPage 0`, `overflowRoute 0`; 200% text
    at 459 px: `overflowRoute 0`;
  - frames in `docs/h149-shots/` (`player-{dark,light}-{1049,900,460}.png`, `player-text200-460.png`,
    `player-reduced-motion-460.png`) plus `measurements.json`.

## Not verified (honest gaps)

- **Typed answer → verdict → close in the live window did not complete.** CDP `Input.insertText`
  never reached the focused `#cb-attempt-answer` (so while the page's own click moved focus, the
  controlled textarea stayed empty and `Check` stayed disabled). The verdict and close surfaces are
  therefore proven by render tests, not by a live graded attempt; the live session stops at the
  answer step. Next attempt: drive the field with real `Input.dispatchKeyEvent` key presses, or
  accept a fixture-backed render harness for the graded frame.
- **A human cold walkthrough of the complete loop is not done.** The loop's live half (answer →
  feedback → close) must be walked by a person or a fixed capture before this card is signed off.
- Reduced-motion measurement reports 38 elements with a non-zero transition *duration*; those are
  host SDK button/checkbox transitions, not player-authored (the source test asserts the player adds
  no transition/animation). H-152 owns the motion contract.
- The live course's section 2 serves `views.guided=false` and a `deep`-only document, so the live
  frame shows the clipped-prose path ("First paragraph of this step. The full text is in Textbook.")
  rather than an authored `short` step.
- Home's Game/Guided/Textbook default preference is a prop seam (`defaultLessonView`); the Home
  settings sheet that sets it is H-147 and is not in this tree.
