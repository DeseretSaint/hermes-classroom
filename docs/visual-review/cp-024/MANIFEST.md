# CP-024 evidence manifest — the v3 course home (R-MAP)

Branch: `wt/cp-024-course-home`   Base: master `b09b65f` (carries CP-020b `131ec86`)
Maker: `lattice`   Reviewer: `cbqa` (must not be the maker)
Module: `desktop/plugin.js` sha256 `bb424a9d7b5346d047820e1efc09708de54da959f8619888789ec214686940f3`
(built by `python3 scripts/build_plugin.py` from 20 segments; `--check` reports the same bytes)

**Status: the code, tests and the M4 audit are green; the live frame matrix is BLOCKED by the
capture door's React-key gate, which fails on `ShelfDisclosure` in `desktop/src/30-home.js` — a file
this card does not own (CP-043 fixes it; it is uncommitted to master at the time of this packet).**
The one refusal kept in this directory is real and pins the final module:

`course-home--1049--light--100--default.refused.json`
> `the route render logged a React key warning: … Check the render method of `ShelfDiscl…``
> (`plugin.window_sha256` = `bb424a9d…40f3`)

A course home is shell state, not a URL: after the door's hard reload the window lands on Home, and
the only path to the course home is through Home → Courses → row, both of which render
`ShelfDisclosure`. No frame is claimed that a stamp does not back, and no stale-module frame from an
earlier build is kept here (the 13 frames produced on `d2a31549…1033` were deleted, not relabelled).

## What the code proves without a window

`tests/test_cp_024_course_home_v3.py` renders the shipped module (`desktop/plugin.js`, not the
segment) in a component preview and asserts the card's contracts:

| Test | Contract |
|---|---|
| `test_course_home_v3_nodes_are_dom_buttons` | every section is a `<button>` on its declared normalised anchor, `aria-current="step"` on the current one, disabled on a gated one, its title and state word as DOM text |
| `test_course_home_v3_anchor_fallback` | absent, malformed, partial (< all sections placed) and sub-900 px routes all fall back to the complete vertical `StampNode` route; 900 is the boundary |
| `test_course_home_v3_one_primary` | exactly one filled control per surface, labelled with the backend's own `next_step.label`, including the plan-review and course-complete steps |
| `test_course_home_v3_world_and_read_states` | world `running` says `Painting the scene.` and keeps the plate; `failed` shows the typographic field, `This scene was not approved` and the quiet `Open World Studio`; loading and a failed read each print their deck line and keep the recorded route |
| `test_course_home_v3_copy_and_facts_only` | every string is a `course.*` deck row or a backend field; no hex, viewport unit, inline shadow, banned metric or invented count |
| `test_course_home_v3_segment_carries_the_card_contract` | the segment names the decisions the tests measure |

A component preview loads neither the host shell nor the Tailwind utility CSS. It proves the DOM
contract, not the painted result.

## What landed in this round (on top of `060f5c9`)

- **World states on the plate.** `cb3CourseWorldPosture` maps the backend's own world state to
  `ready` / `running` / `rejected` / `none`. `world-running` keeps the last plate and prints
  `Painting the scene.`; `world-rejected` drops the refused art, prints `This scene was not
  approved`, and its one quiet action opens the shipped `WorldStudio` sheet from `97-world.js`
  (rendered from this segment, never a second editor). `data-cb-course-world-state` records the
  posture for reviewers and tests.
- **Read loading / error on the head.** `Opening this course.` while the outline is in flight; a
  failed read prints `This course could not be read` + `The route shows what was saved last. Try
  again.` with one quiet `Try again` that reloads outline, world and page — and never renders an
  empty course.
- **Anchor carriers.** `cb3CoursePlateAnchors` accepts the plate manifest, the asset row, the
  world brief's `plate.route_anchors`, the brief itself, and the world row — one shape, the same
  normalisation, the same refusal of a malformed entry. The brief is a forward-compatible carrier
  only; see the contract gap below.

## The map mode is NOT live in this tree — a contract gap, not a render bug

The card asks for nodes on anchors "stored as normalised coordinates in the plate manifest". No
field in `cb.rpc` v25 can carry them:

- `world.read` → `course_world.assets[]` is a closed projection (`role`, `section_id`,
  `section_key`, `artifact_id`, `style_hash`, `prompt_hash`, `textless`) — no manifest, no anchors;
- `course_world.brief` is the closed `world_brief` schema — adding `route_anchors` makes the
  handler's own result fail contract validation, which I reproduced live:
  `world.read` returned `INTERNAL_ERROR: … is not valid under any of the given schemas` for a row
  whose `brief_json` carried `route_anchors`;
- `artifact.get` → `provenance` is a closed five-field projection (`generator`, `model`,
  `prompt_hash`, `source_ids`, `notes`) — no anchors either.

So every shipped course renders the **vertical `StampNode` route** today; the map mode is proved by
the module test and the `world-running`/fixture cases, not by a live anchored plate. The fix is a
contract change (`course_world_asset` gains a `manifest` with `route_anchors`) owned by the
backend/generation lane, plus a real anchored plate in a world kit. Reported, not faked, and not
patched into a segment this card does not own.

## Cells and their status

Named reference: `docs/concept-parity/refs/map.png` (1344×768), crop to be taken from the mounted
plate when frames exist. Screen row `course-home.v3` in `docs/visual-review/MATRIX.md`.

| # | Cell | Status |
|---|---|---|
| 1 | `course-home--1049--light--100--default` | **REFUSED** — key warning, `ShelfDisclosure`; refusal JSON kept |
| 2 | `course-home--1049--dark--100--default` | not captured — same gate; appearance set through the app (`set-appearance.mjs`), not `--color-scheme` |
| 3 | `course-home--900--light--100--default` | not captured — same gate |
| 4 | `course-home--900--dark--100--default` | not captured — same gate |
| 5 | `course-home--460--light--100--default` | not captured — same gate |
| 6 | `course-home--460--dark--100--default` | not captured — same gate |
| 7 | `course-home--1349--light--100--default` | not captured — same gate |
| 8 | `course-home--1049--light--100--forced-colors` | not captured — same gate |
| — | `plan-in-review` | not captured — same gate (`drive-course-plan.js` opens the rig's real `review_plan` course) |
| — | `no-world` | not captured — same gate |
| — | `world-running` | not captured — same gate; rig row is a real `course_worlds` row in state `kit_generating`, contract-valid brief |
| — | `world-rejected` | not captured — same gate; rig row is state `failed` + `error.missing_roles` |
| — | `text-200` (460) | not captured — same gate |
| — | `course-end` | not captured — no rig course has full independent evidence; a seeded completion would fabricate learner evidence |
| — | `loading` / `error` | component-proven only: a deep-screen in-flight/failed read cannot survive the door's reload, and `--no-reload` cannot start from a course home that the caller has not already driven |

## Capture tooling delivered (needed by every v3 deep screen)

`scripts/cp-capture.mjs` gained four **opt-in** flags; with none of them the door behaves exactly as
before, and every stamp records what was used:

| Flag | Why |
|---|---|
| `--after-reload <file>` | runs a real-click driver after the reload and before measurement (a course home is shell state; the reload lands on Home) |
| `--after-reload-wait <selector>` | holds the probe until the driven surface is on screen; a driver that never arrives refuses the frame |
| `--no-reload` | captures the live window as driven (stamp records `capture.reloaded: false`); the module-sha gate still reads the source the window evaluates |
| `--root-font 32px` | the 200 % text cell is a root font size, not page zoom; `route.text_scale_root_px` records it |

Also in `docs/visual-review/cp-024/`: `drive-course-home.js`, `drive-course-plan.js`,
`set-appearance.mjs` (the v3 route follows the host appearance attribute, not
`prefers-color-scheme`, so `--color-scheme` alone is refused by the door's own gate), and
`capture.sh` — the whole matrix in one command, with the world-state fixtures and their cleanup.

## Command shape (one cell)

```bash
docs/visual-review/cp-024/capture.sh default-1049-light        # or no argument = every cell
# equivalent to:
node scripts/cp-capture.mjs --name course-home--1049--light--100--default \
  --out docs/visual-review/cp-024 --cdp-port "$CB013_CDP_PORT" \
  --state "$COURSEBOOK_TEST_STATE" --plugin desktop/plugin.js \
  --backend-url "$CB013_BACKEND_URL" --token "$CB013_TOKEN" \
  --route-width 1049 --require-v3 --no-reload \
  --after-reload docs/visual-review/cp-024/drive-course-home.js \
  --after-reload-wait '[data-cb-course-home-v3]'
```

Every cell must pass the door's own refusals: module sha equal to the checkout, `[data-cb-route]`
with no render-error marker, fonts loaded, every route `img` decoded, no host element over the
route, the pixel veto, 100 % zoom, `[data-cb-v3-ready]` with textures `ready`, and no React
duplicate/missing-`key` console error.

## Side-by-side boards (to produce once frames exist)

```bash
python3 scripts/cp-sbs.py --concept docs/concept-parity/refs/map.png --crop X,Y,W,H \
  --product docs/visual-review/cp-024/course-home--1049--light--100--default.png \
  --out docs/visual-review/cp-024/sbs-1049-light.png
```

The concept is an AI still with garbled labels and invented data; the board compares material, type
and density only, and claims no parity of text.

## Known gaps to record in the review

1. **Map mode is not live** (contract gap above). Every course renders the vertical route; a
   contract change and an anchored plate are needed. The renderer already accepts the anchors.
2. **Capture matrix is blocked by CP-043** (`ShelfDisclosure` key warnings in `30-home.js`). The
   refusal is recorded with the final module sha; re-running `capture.sh` after CP-043 merges should
   fill every cell without a code change here.
3. **`loading` / `error` live frames** need shell-state persistence or an in-flight/failed read the
   door can freeze; both are component-proven and the surfaces exist.
4. **`course-end`** has no honest rig course (no full independent evidence). Seeding evidence rows
   would fabricate learner progress on a frame that claims completion.
5. The aside's other-course rows read `library.list` (`limit: 20`) with a client-side filter; a
   sibling course can be missing on a very large library. Narrowing that read is a backend change.
6. `world.read` cannot carry anchors without a contract change (see 1).

## Verification run on the final tree

- `python3 scripts/build_plugin.py --check` → `desktop/plugin.js` matches `desktop/src`
  (`bb424a9d…40f3`).
- `tests.test_plugin_build` + `tests.test_cp_024_course_home_v3` → 17 tests OK.
- `tests.test_m4_visual_audit` → 14 tests OK; `scripts/m4v-audit.py` regenerated on this module
  (15/15 claims PASS, `plugin_sha256` pinned to `bb424a9d…40f3`).
- Targeted regression group and `scripts/validate-plugin.sh` are run on the final commit and their
  numbers are in the review summary.
