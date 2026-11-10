# MANIFEST — CP-023 Classroom v3

**Status: partial build under the owner's 2026-11-10 partial-build ruling. No screenshot is
claimed, because the surface is not yet reachable on the route.**

```text
Card: CP-023 (R-CLASS)      Branch: wt/cp-023-classroom
Base: master f7ad3cd (merged at ce93efb; carries the deck rows) on top of
      wt/cp-020b-primitives (556a6fb, merged at 76d691a; CP-020a scope and CP-013 assets)
Commit under review: 1dff23a (build frozen at ec9dd47 + the six deck group labels)
Maker (did not review): cinder       Reviewer: cbqa
plugin.js sha256: 2beaf778b8fe1b82ca4c78536745c1604808453bac86a7b3058c285544c82327
70-learning.js sha256: f7f86c6f45c319cab39a1cf44a484e0b5c924fa98e91e6386ebdba46db13286d
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

## 2. Named tests (all green at 1dff23a)

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

Neighbour gates re-run on the same commit: `test_plugin_build` 11, the H-149 and H-178 lesson
tests, `test_v3_scope`, `test_v3_primitives`, `test_desktop_tokens_v3`, `test_tokens_v3_contract`
(119 OK together), `test_desktop_gate_scope`, `test_desktop_h183_copy_inventory`,
`test_desktop_breadth_copy` (46 OK, skipped=2), `test_m4_visual_audit` 14 OK, `test_cp_spec` 33 OK.
Full suite: see §4.

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

## 4. Full suite at 1dff23a — 3416 tests, 1196.781 s, one failure (the known, deferred one)

```text
Ran 3416 tests in 1196.781s
FAILED (failures=1, skipped=11)
```

**`test_desktop_gm010_engagement_ui.test_game_header_only_in_game` — OPEN by instruction.** It
asserts

```python
self.assertEqual(self.source.count("useRpcQuery(\n    'engagement.read'"), 2)
```

with the comment "There is no third mount a textbook surface could reach". This card makes that
comment stale *by design*: SPEC-V3 §5.3 puts a `ChallengeCard` and the XP chip in the classroom's
rail in Game mode, so `ClassroomV3Surface` reads `engagement.read` gated on `mode === 'game'` —
a legitimate third mount, and the reason the read sits in my segment rather than in the manager's
mount code. It is not reachable from a textbook surface: `test_classroom_v3_no_xp_outside_game`
renders Guided and Textbook and asserts no `data-cb3-xp`, no `XP` string and no challenge.
The manager's 2026-11-10 ruling assigns this file and its third-mount assertion to **CP-040** (the
merge seam), which updates it when the mount actually lands. It is outside this card's ownership,
so it is reported, not changed. **This failure is the only red test on the branch; the M4 pin is
green again** (regenerated at 1dff23a: 15 claims PASS, pin `2beaf778…2327`).

## 5. Deferred to the merge — now owned by CP-040 (card `t_5403e4a1`, branch `wt/cp-040-seam`)

The manager created CP-040 as the merge seam and linked it behind this card; the items below are
its scope, not this card's. The partial-build ruling defers this last 10%: the surface is **not
mounted**, so a capture would be a photograph of an unreachable component and would fail evidence
rule 1 (from the running app). This card therefore claims zero frames and no score.

1. **Export seam.** `ClassroomV3` and `ClassroomV3Surface` are declared in the learning segment but
   the module's `export {}` lives in the last segment, which this card may not edit. Add both names
   (plus, for tests, `ClassroomCheckCard`, `classroomStepNodes`, `classroomLineFromPage`,
   `classroomEvidence`, `classroomSceneFromWorld`, `CB3_CLASSROOM_COPY`).
2. **The gm010 count (§4).** CP-040 (merge seam) owns `tests/test_desktop_gm010_engagement_ui.py`
   and updates the third-mount expectation when the mount lands; no product file changes for it.
3. **Route mount.** Replace the v2 lesson pane's central reading column with `ClassroomV3Surface` in
   the route composition (98/99 segment, not this card), passing the row, enrollment, objective,
   mode and the four navigation callbacks. `ClassroomV3` is pure and stays the render target.
4. **Capture.** Run `scripts/cp-capture.mjs` from the merged commit with the eight baseline cells,
   every named state, forced colors and the 1349 cell, then build the side-by-sides with
   `scripts/cp-sbs.py` against the concept's classroom crop.
5. **Review.** `cbqa` scores §1–§9 on the captures; this MANIFEST currently supports no score.

## 6. Requests and gaps reported, not fixed (file ownership)

- **Group labels: resolved at 1dff23a, by ruling.** The 2026-11-10 ruling added six deck rows —
  `classroom.check.choices` / `.checklist` / `.answers` / `.criteria`,
  `classroom.practice.expressions` / `.practice.transcript` — to `COPY.md` §4 and `SPEC-V3 §5.3`
  C7/C8. Every hard-coded group name and aria-label in the learning segment now reads
  `CB3_CLASSROOM_COPY`; the visible words are unchanged, and `test_classroom_v3_copy_is_the_deck`
  fails if a literal comes back. `tests.test_cp_spec` 33/33 OK at that commit.
- **One deck gap remains (reported, not fixed).** The `text` stimulus needs a visible answer label
  and no deck row governs it (`classroom.answer.label` was proposed but is not in SPEC C7 and was
  not added by the ruling). The constant is a literal `Your answer`, declared as such in the copy
  block; the durable fix is a deck row, then the constant becomes a deck read. `Selected` and
  `Nothing selected yet.` are still literals for the same reason.
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

## 8. Handoff notes for CP-040

- **CP-022 is not merged here, deliberately.** The card template names CP-022 as a branch to merge,
  but CP-022 is this card's sibling (the card's real parent is CP-013) and the manager's later base
  ruling pins the base to `wt/cp-020b-primitives` at `556a6fb`. A trial merge
  (`git merge-tree --write-tree HEAD wt/cp-022-home`) conflicts only on the generated
  `audit/visual/m4-visual/audit.json`; merging it here would produce a duplicate Home wave and a
  re-pin this card cannot score. CP-040 is the six-branch union merge and owns that merge plus the
  rebuild and re-pin.
- **Build the union, do not take either side of a conflict.** `desktop/plugin.js` and the M4 audit
  are generated: resolve by `python3 scripts/build_plugin.py` and `scripts/m4v-audit.py`, then
  confirm `tests.test_plugin_build` and `tests.test_m4_visual_audit` on the merged tree.
- **The one red test is the seam's to flip.** `tests/test_desktop_gm010_engagement_ui.py` expects 2
  `engagement.read` mounts; this segment adds the Game-gated third. Update it in the same commit that
  mounts the surface, so the record never shows a red it cannot explain.
