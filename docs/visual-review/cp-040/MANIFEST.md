# MANIFEST — CP-040 merge seam (six-branch union, route mount, capture matrix)

```text
Card: CP-040 (t_5403e4a1)     Branch: wt/cp-040-seam
Owner: harbor                  Reviewer: atlas
Union head: 0a2c4c8 (six branches merged), seam commit b5b9002e, audit re-pin c86b46a8
Module sha256: c52b864bb3bd43b3b4110cd2d9e59e24e4eec1aa1f4b731e22e555c71e744c02
Frames produced: 4 stamped cells + 1 stamped refusal (of the 7 destinations the card names)
Freeze: nothing pushed, nothing published, no catalog entry touched
```

## 1. The union

Merged, in this order, each with `--no-ff` so the seam history is readable:

| Branch | Tip merged | Note |
|---|---|---|
| `wt/cp-022-home` | `78ae068` | Home v3 |
| `wt/cp-023-classroom` | `30d78b1` | Classroom v3 |
| `wt/cp-025b-adopt` | `5fb74f7` | World Studio + Parent Studio v3 |
| `wt/cp-024-course-home` | `8f3522e` | Course home v3 |
| `wt/cp-021-discover` | `5f51a66` | Discover/Workshop v3 (carries the CP-038 capture door) |
| `wt/cp-025a-adopt` | `2fe06c4` | Homework/Game v3 (its history already contains 022, 023 and 025b) |

The only conflict in every merge was `audit/visual/m4-visual/audit.json` — the generated M4 pin.
It was taken from the branch and **regenerated** on the merged tree (`scripts/m4v-audit.py`, 15
claims PASS, pin `c52b864b…4c02`); no pin was hand-edited. `desktop/plugin.js` auto-merged and was
rebuilt from the 20 segments (`scripts/build_plugin.py`).

`wt/cp-025a-homework-game` and `wt/cp-025b-world-studio` do not exist in this repository; the wave
branches are `wt/cp-025a-adopt` and `wt/cp-025b-adopt` (the card's names were the pre-adoption
labels). That is the only naming deviation.

## 2. Seam work in this card

- **Export seam.** 49 names the wave declared but never exported are now in the module's single
  `export {}` block (`desktop/src/99-tutor.js`), grouped by the segment that owns them: Home v3,
  Classroom v3 (`ClassroomV3`, `ClassroomV3Surface`, `ClassroomCheckCard`, `ClassroomScene`, the
  pure helpers), Course home v3, Discover, World Studio. `tests/test_cp_023_classroom.py` no longer
  appends a duplicate export for a name the module already exports (that is a SyntaxError).
- **Route mount.** `ClassroomV3Surface` is mounted in the route composition (`desktop/src/98-page.js`):
  a section opened with no explicit view follows the learner's presentation mode — **Game and
  Guided** render the v3 classroom, **Textbook** keeps the reader workspace that owns document
  blocks, pronunciation, the tutor rail and take-home, and an explicit `openCourse.view` (Plan, a
  citation handoff) is never overridden. Its no-chat action arms the exact run with `lesson.begin`
  before opening the chat, so the learner lands in the pending binder rather than a bare new chat.
- **Elevation.** `96-workshop.js` no longer paints an inline `boxShadow` (the token gate forbids
  it); the featured plate and the state plate carry the `.cb3-elev-1` class whose rule now lives
  beside `.cb3-shelf` in `76-v3-scope.js`.
- **Mount-count test.** `tests/test_desktop_gm010_engagement_ui.py` now states the measured
  invariant instead of the stale claim: **2 `GameHeader` mounts, 3 `engagement.read` readers**. The
  classroom is the third reader and is not a mount — its Game chrome is the aside's challenge card
  and XP line, so mounting the course-list band there would print the same play layer twice on one
  screen. The card body's "update 2 → 3" assumed the classroom mounts the header; the merged module
  does not, and the comment now says why.
- **Five stale v2 gates** the wave invalidated (GM-002 Home ×4, H-151 primary ×1) were migrated to
  the v3 deck with the accepted migration already recorded in `t_847e5b1b` / `t_3edffaa6`
  (`docs/concept-parity/GATE-MIGRATION.md`), applied as a test-only patch on this tree.

## 3. Capture matrix — what was actually photographed

Rig (disposable, nothing of the operator's touched):

```text
state    ~/.hermes/coursebook-test-cp040  (home, userdata, connections.json remote)
backend  hermes serve --isolated --port 44319   (wire v25, plugin_root = this worktree)
window   apps/desktop dev Electron, CDP 127.0.0.1:9377
opt-in   localStorage hermes.desktop.pluginDecisions.v2 = {"coursebook": true}
```

Every frame is stamped by `scripts/cp-capture.mjs`; each stamp records
`window_sha256 = c52b864b…4c02`, `destination.match = true`, `v3_ready`, fonts loaded and the image
decode count.

| Destination | Cell | Result |
|---|---|---|
| home | `cp040-home-empty-1049` | **captured** — v3 empty Home, 1049, dark, 1/1 image, sha `c52b864b…` |
| discover | `cp040-workshop-1049` | **captured** — Workshop/Discover v3, 1049, dark, 1/1 image |
| workshop | `cp040-workshop-1049` | **captured** (same route: Discover is the head of the Workshop surface) |
| courses | `cp040-courses-1049` | **captured** — Courses destination, empty catalogue |
| parent studio | `cp040-studio-1049` | **captured** — Parent Studio v3 |
| course | `cp040-course-refused` | **refused by the door** — no addressable control: the rig has zero courses |
| classroom | — | **not produced**: `#/learn/<objective_id>` needs a course row; none exists |
| game | — | **not produced**: the Game band is on a course home; none exists |
| world.studio | — | **not produced**: the studio sheet opens from a course; none exists |

The refusal is returned by the door itself, not by this packet:

```text
REFUSED (cp040-course-refused): requested destination course/crs_none has no addressable control
on the current surface ([data-cb-home-card-action="crs_none"], …)
```

### Why the deep four are open, measured

- `library.list` on the rig answers `{"items": [], "total": 0, "empty_reason": "no_courses"}`.
- `pack.list` answers `{"items": [], "total": 0}`. The three bundled packs are a **staged upload**
  in this build: `pack.preview` / `pack.import` take a `staged_id` produced by the import flow's
  file picker, and `desktop/src/96-workshop.js` has no bundled one-click install control
  (`grep 'pack.import\|staged_id' desktop/src/96-workshop.js` → no match). So the demo shelf cannot
  be seeded from the UI, and no script in `scripts/` stages them either.
- A synthetic course is not a substitute: `course.create` starts a plan job whose approval and
  lesson pages are generation work (spend + minutes), and the atlas ruling on this wave forbids
  claiming authored courses that do not exist.

**Operator action that unblocks the remaining four destinations** (one line): install the three
bundled packs into the CP-040 rig home (stage + `pack.import`) — or point the matrix at a
default-profile Desktop that already holds courses — then re-run the five open cells with:

```bash
node scripts/cp-capture.mjs --name cp040-course-1049 --out docs/visual-review/cp-040 \
  --cdp-port 9377 --state "$HOME/.hermes/coursebook-test-cp040" --plugin desktop/plugin.js \
  --backend-url http://127.0.0.1:44319 --token cb013-test-token --route-width 1049 --require-v3 \
  --destination course/<course_id>
```

## 4. Gates on the union head

| Gate | Result |
|---|---|
| `python3 -m unittest discover -s tests` | **Ran 3528 tests in 984.094s — FAILED (failures=24, errors=4, skipped=11)** on `8f5c4df2`. The failures are the v2 UI/accessibility gates the v3 wave replaced and never migrated (headings/landmarks/skip-link/wordmark/Home-title cases across the a11y, H-14x and home-hub modules) plus `test_lesson_skills` and `test_conversation_practice` errors and two `setUpClass` errors; they are not the seam's own tests, which are green (below) |
| targeted seam suites | `test_plugin_build`, `test_cp_021_workshop_v3`, `test_cp_022_home_v3`, `test_cp_022_geometry`, `test_cp_023_classroom`, `test_cp_025a_homework_game_v3`, `test_cp_025b_v3_studio`, `test_desktop_h149_lesson_player`, `test_desktop_h178_field_stop`, `test_desktop_contracts`, `test_desktop_h151_action_type`, `test_desktop_h147_home_settings`, `test_desktop_field_quest`, `test_desktop_lesson_views`, `test_desktop_h174_empty_textbook`, `test_desktop_gm002_home`, `test_desktop_gm010_engagement_ui`, `test_desktop_tokens_v3`, `test_v3_scope`, `test_v3_primitives` → **278 OK** (67 s) |
| `bash scripts/validate-plugin.sh` | **Release gate passed: 4/4** on `c86b46a8…` (4222 files) |
| `python3 scripts/check-docs-truth.py --skip-tests` | **docs-truth: PASS** |
| `python3 -m unittest tests.test_m4_visual_audit` | 14 OK, pin `c52b864b…` |

## 5. What this packet does not claim

- It does not claim the six-branch union is fully photographed. Four of the seven destinations are
  unphotographed and the reason is measured above, with the exact operator action.
- It does not claim the product authored four courses, a COPPA posture, verified safety or
  native-speaker review. Nothing here is pushed, published or submitted.
