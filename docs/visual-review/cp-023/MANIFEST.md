# MANIFEST — CP-023 Classroom v3

**Status: partial build under the owner's 2026-11-10 partial-build ruling. No screenshot is
claimed, because the surface is not yet reachable on the route.**

```text
Card: CP-023 (R-CLASS)      Branch: wt/cp-023-classroom
Base: wt/cp-020b-primitives (556a6fb, merged at 76d691a; carries CP-020a scope and CP-013 assets)
Commit under review: ec9dd47
Maker (did not review): cinder       Reviewer: cbqa
plugin.js sha256: 97d13c6a6f3fee11ee5f8f7a85e367fa2e3f2cd974151cab37abe043ebbe314e
70-learning.js sha256: 9afbdd99e383ef721a92f0229130ad696b98fda218466629451b078cc35b8b4d
Captures: 0 / 8 required cells — deferred, see §5
```

## 1. What was built (this card's file ownership: `desktop/src/70-learning.js` only)

One composition and one check surface, appended to the learning segment between the
`// CB-V3-BEGIN — CP-023` / `// CB-V3-END — CP-023` markers, built from the CP-020b primitives:

| Piece | Component | Reads (prop-fed in the pure layer) |
|---|---|---|
| stepper | `ClassroomV3` stepper, `StampNode` per section | `course.outline.objectives[]` |
| framed scene | `ClassroomScene` | `world.read` plates → this section's plate, else typographic field |
| lesson line | `ClassroomScene` + `DialogueBubble` | the pack's authored teaching line (`lesson.page.segments[].text`) |
| check card | `ClassroomCheckCard` | `lesson.page.checks[]` + served `check.stimulus` |
| evidence | `EvidenceTray` | counted from `lesson.page.checks[]` / `lesson.page.attempts[]` |
| aside | tutor door, quiet `PillAction` | — |
| Game layer | `ChallengeCard` + XP chip + practice rows | `engagement.read` (Game mode only) |
| wired container | `ClassroomV3Surface` | `useRpcQuery` for outline, page, world, engagement; `useOpenCheck` for the stimulus |

The state machine, fences and commands in the check card mirror `AttemptControls`: one
`attempt_nonce` per answer, `expectedRevision` from the page, a fresh nonce only on `Try again`,
`needs_retry` reads as *not a pass*, and the verdict prints only an observation the backend
returned. It is a separate component because `AttemptControls` is pinned by H-149/H-178 and still
mounted on two v2 surfaces; changing it would move those tests.

## 2. Named tests (all green at ec9dd47)

`python3 -m unittest tests.test_cp_023_classroom` — 10 tests:

```text
test_classroom_v3_answer_is_primary          OK
test_classroom_v3_no_xp_outside_game         OK
test_classroom_v3_stepper_matches_outline    OK
test_classroom_v3_ruby_on_japanese_line      OK
test_classroom_v3_evidence_counts_real_checks OK
test_classroom_v3_states_keep_geometry_and_one_action OK
test_classroom_v3_narrow_hides_the_mascot_and_stacks  OK
test_classroom_v3_scene_uses_only_this_sections_plate OK
test_classroom_v3_copy_is_the_deck           OK
test_classroom_v3_paints_only_v3_tokens      OK
```

Neighbour gates re-run on the same commit, 138 tests: `test_plugin_build`, the H-149 and H-178
lesson tests, `test_v3_scope`, `test_v3_primitives`, `test_desktop_tokens_v3`,
`test_desktop_gate_scope`, `test_desktop_h183_copy_inventory`, `test_desktop_breadth_copy` — OK
(skipped=2). Full suite: see §4.

The render test imports a **copy** of the built module with one extra `export { … }` appended
(`tests/test_cp_023_classroom.py`), because this card may not edit the segment that owns the
module's export seam. The copy is a test artifact; `tests.test_plugin_build` remains the authority
on `desktop/plugin.js`, and the generated module in this commit is `build_plugin.py` output only.

## 3. State coverage in the render harness (not captures)

Rendered with `renderToStaticMarkup` at 1049 and 460 CSS px, light: `guided`, `game`, `textbook`,
`error`, `offline`, `no-chat`, `complete`, no-authored-line, `verification` stimulus, `text`
stimulus. Each asserted for: one filled control, XP only in Game, stepper states from the outline,
`aria-current="step"` + the word `Now`, `disabled` only on the plan's own gate, ruby over kanji,
plain kana line, romaji line, evidence count and integrity classes, one next action per
empty/loading/error state, mascot hidden under 620 px.

## 4. Full suite

`python3 -m unittest discover -s tests -t .` is running on ec9dd47 and is recorded on the card
comment when it lands. It does not gate this partial handoff, but its result belongs to the review.

## 5. Deferred to the merge — what the manager must do (do not read this as a pass)

The partial-build ruling defers the last 10%: the surface is **not mounted**, so a capture would be
a photograph of an unreachable component and would fail evidence rule 1 (from the running app).

1. **Export seam.** `ClassroomV3` and `ClassroomV3Surface` are declared in the learning segment but
   the module's `export {}` lives in the last segment, which this card may not edit. Add both names
   (plus, for tests, `ClassroomCheckCard`, `classroomStepNodes`, `classroomLineFromPage`,
   `classroomEvidence`, `classroomSceneFromWorld`, `CB3_CLASSROOM_COPY`).
2. **Route mount.** Replace the v2 lesson pane's central reading column with `ClassroomV3Surface` in
   the route composition (98/99 segment, not this card), passing the row, enrollment, objective,
   mode and the four navigation callbacks. `ClassroomV3` is pure and stays the render target.
3. **Capture.** Run `scripts/cp-capture.mjs` from the merged commit with the eight baseline cells,
   every named state, forced colors and the 1349 cell, then build the side-by-sides with
   `scripts/cp-sbs.py` against the concept's classroom crop.
4. **Review.** `cbqa` scores §1–§9 on the captures; this MANIFEST currently supports no score.

## 6. Requests and gaps reported, not fixed (file ownership)

- **Deck row needed (`COPY.md`).** `SPEC-V3 §5.3 C7` requires an answer label for the `text`
  stimulus; the deck has no classroom row for it. The component uses the literal `Your answer` and
  the test pins it, but the durable fix is a `classroom.answer.label` row, then the constant swaps
  to a deck read. Two smaller strings used only as state words — `Selected` and
  `Nothing selected yet.` — need rows too (or are absorbed by C7).
- **No `locked` field in the outline projection.** `course.outline.objectives[]` today carries no
  prerequisite flag, so `ClassroomV3` reads `objective.locked === true` and otherwise never pads a
  node with a lock. If the plan gate is meant to be visible, the projection must expose it; until
  then the stepper shows evidence, not a guessed gate.
- **`next_step` label.** The aside's `Next up:` reads `row.next_step.label` from the course row; if
  the row carries only an id, the line is omitted rather than invented.
- **Audio door.** `DialogueBubble`'s play action is wired to `onPlayLine` only; the pack has no
  recorded audio artifact for these lines yet, so the route must pass nothing and the button is
  absent (never a dead control).
- **Primitive props relied on, unmodified:** `StampNode(state, label, stateWord, index, onClick)`,
  `DialogueBubble(segments, romaji, en, onPlay, playLabel)`, `EvidenceTray(countLabel, recorded,
  emptyLabel, events)`, `ChallengeCard(title, prompt, recordNote, actionLabel, onStart)`,
  `PillAction(variant, label, icon, disabled, busy, onClick)`, `FoxPose(pose, size)`. If CP-020b's
  final branch renames any of them, this segment is the call site the manager rebases.

## 7. Known non-blocking observations

- The stepper's wide column is 96 px and the aside 268 px at ≥1000 px route width; below that the
  composition stacks (stepper strip → scene → line → check → aside), which is what the 460 px render
  test asserts. Route width comes from `useCbViewportWidth()`, never the window.
- `classroomSceneFromWorld` prefers a plate whose `section_id` equals the section's objective id and
  never falls back to *some other* section's plate; an unmatched kit yields the typographic field.
- The fox is the host pet's pose primitive (`read`/`think`/`cheer`), hidden below 620 px; it is not
  a second mascot and carries no progress meaning.
