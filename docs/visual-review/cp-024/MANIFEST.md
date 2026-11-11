# CP-024 evidence manifest — the v3 course home (R-MAP)

Branch: `wt/cp-024-course-home`
Base: master `ef7ec52` (merged; carries CP-020b primitives, CP-038's capture door, CP-043's keys, the
visual-gate tools `docs/concept-parity/VISUAL-GATE.md`, `visual/find-cdp.mjs`,
`scripts/compare-ref.sh`)
Maker: `lattice`   Reviewer: `cbqa` (must not be the maker)
Module: `desktop/plugin.js` sha256 `6aaa9c3909bd75a8791347ac9f5f53c5b619c20aecf16b6f19421384c846b3c0`
(built by `python3 scripts/build_plugin.py` from 20 segments; `--check` reports the same bytes)

**Status: the 13-cell live matrix is captured on this module (0 refusals), the assembled-screen
composition is asserted in a mounting test, and the visual gate has been run. One gap remains
honest: no live frame can show the anchored *map* mode, because no `cb.rpc` v25 field carries a
plate's `route_anchors` (see "Map mode" below) — every shipped course renders the vertical route.**

## What changed in review round 1 (cbqa, live at `bb424a9d`)

| Defect | Fix in this round |
|---|---|
| P1: `CourseDetail` mounted `CourseHomeV3` **and** the legacy `OverviewView` on `view === 'overview'` — two filled primaries, two route containers, the title twice | the legacy body is retired from that route (`desktop/src/90-course.js`, `body = null`); `OverviewView` stays defined for its other callers. Live: exactly one filled control, one route container, one course heading |
| P2: 900–999 route px kept the 268 px aside because the column and the map shared one 900 px breakpoint | two breakpoints, per SPEC-V3 §5.4: map from 900 px (nodes 48, plate 3:1) and the right column only at ≥ 1000 px (nodes 56, fox 96); `data-cb-course-body="split\|stacked"` exposes the decision |
| P2: the one-primary test mounted `CourseHomeV3` alone and could not see the second body | new `CourseDetailOverviewCompositionTest` mounts `CourseDetail` on `view: 'overview'` in jsdom against a stubbed `ctx.rest` and counts **both** filled-control dialects across the whole route, plus route containers, the course heading and the node dot sizes at 1049/900 |
| Acceptance: 0/13 frames | 13/13 frames, each with a stamp; see the matrix below |

The composition test was verified to **fail** on the reviewed module before the fix (harness run
against `bb424a9d`: 2 primaries — `Continue Say what you want` + `Resume the lesson`; 1
`data-cb-overview-route`; 2 course-title headings; 56 px nodes at 900; no `data-cb-course-body`) and
to pass on this module (1 primary, 0 legacy routes, 1 heading, 48 px nodes at 900, `stacked` at 900
and `split` at 1049). A test that cannot fail is not evidence.

## Capture door fix (why the earlier matrix produced 0 frames and then a wrong-width frame)

`scripts/cp-capture.mjs`, CP-024 additions on top of CP-038's door:

- `--after-reload <file>` + `--after-reload-wait <selector>`: a course home is shell state, not a
  URL, so the door runs the screen's own real-click driver (`drive-course-home.js`) and refuses
  unless `[data-cb-course-home-v3]` arrives.
- `--no-reload`, `--root-font 32px`, and stamps record `capture.driver` / `capture.reloaded` /
  `route.text_scale_root_px`.
- **`settleLayout()`**: `Emulation.setDeviceMetricsOverride` resizes the viewport but delivers no
  ResizeObserver frame in this host, so a v3 surface that measures its own route kept the width it
  was mounted at. One frame was stamped `1049` while the composition was the 460 layout; the route
  rect was right and the pixels were not. Dispatching `resize` and waiting two frames before every
  measurement fixes it (verified against the live hook: `data-cb-course-home-width` now tracks the
  emulated route width). This affects every v3 deep screen, not only this card.

## The matrix — 13 cells, every stamp `plugin.window_sha256 = 6aaa9c39…b3c0`

Verified by `cp024_verify_stamps.py` (name ↔ route width ↔ theme ↔ gates ↔ sha): **13 stamps, 0
problems**. Each frame passed the door's gates: plugin sha, route present, no render error, fonts
loaded, images decoded, no host overlay, no unpainted region, 100 % zoom, `[data-cb-v3-ready]` with
textures `ready`, no React duplicate/missing-key warning.

| # | Cell | Route (w × h) | Theme |
|---|---|---|---|
| 1 | `course-home--1049--light--100--default` | 1049 × 1166 | light |
| 2 | `course-home--1049--dark--100--default` | 1049 × 1126 | dark |
| 3 | `course-home--900--light--100--default` | 900 × 1166 | light |
| 4 | `course-home--900--dark--100--default` | 900 × 1166 | dark |
| 5 | `course-home--460--light--100--default` | 460 × 1166 | light |
| 6 | `course-home--460--dark--100--default` | 460 × 1166 | dark |
| 7 | `course-home--1349--light--100--default` | 1349 × 1166 | light |
| 8 | `course-home--1049--light--100--forced-colors` | 1049 × 1166 | light, forced-colors |
| 9 | `plan-in-review` | 1049 × 1166 | light |
| 10 | `no-world` | 1049 × 1166 | light |
| 11 | `world-running` | 1049 × 1166 | light |
| 12 | `world-rejected` | 1049 × 1166 | light |
| 13 | `text-200` (460, root 32 px) | 460 × 1126 | light |

Rerun: `docs/visual-review/cp-024/capture.sh` (no argument = all 13; each cell is listed by name).
Every cell is `capture.reloaded: false` on a window restarted on this module, so the stamp names the
module the window evaluated.

**Rig left live for the reviewer** (disposable state, not the operator's): state
`~/.hermes/coursebook-test-cp024-r2` (`home/`, `userdata/`), backend `hermes serve --isolated` on
`127.0.0.1:44427` (token `cp024-test-token`), window CDP `127.0.0.1:9361` (dev Electron, class
`hermes`, installed module = checkout = `6aaa9c39…b3c0`). Rerun with:

```bash
COURSEBOOK_TEST_STATE=$HOME/.hermes/coursebook-test-cp024-r2 \
CB013_CDP_PORT=9361 CB013_BACKEND_URL=http://127.0.0.1:44427 \
  docs/visual-review/cp-024/capture.sh
```

Teardown: `scripts/cb013-live-window.sh --stop` and `scripts/cb013-live-backend.sh --stop` with
`COURSEBOOK_TEST_STATE`/`COURSEBOOK_TEST_HOME` pointing at that state. The older
`coursebook-test-cp024` state was taken over by another profile's Desktop run (its installed module
became `6b9d0818…` at 17:22), so this card moved to a fresh copy of the same home rather than
fighting it for the window.

## Map mode: NOT live in this tree — a contract gap, not a render bug

The card asks for nodes on anchors "stored as normalised coordinates in the plate manifest". No
`cb.rpc` v25 field can carry them:

- `world.read` → `course_world.assets[]` is a closed projection (`role`, `section_id`,
  `section_key`, `artifact_id`, `style_hash`, `prompt_hash`, `textless`) — no manifest, no anchors;
- `course_world.brief` is the closed `world_brief` schema — adding `route_anchors` makes the
  handler's own result fail contract validation; reproduced live as
  `world.read` → `INTERNAL_ERROR: … is not valid under any of the given schemas`;
- `artifact.get` → `provenance` is a closed five-field projection — no anchors either.

So the 13 live frames all show the **complete vertical `StampNode` route** (the no-anchor fallback
SPEC-V3 §5.4 requires), and the map mode is proved by the module tests (`test_course_home_v3_nodes_are_dom_buttons`,
`..._anchor_fallback`) and the brief-carrier logic, not by a live anchored plate. The fix is a
contract change (`course_world_asset` gains a `manifest` with `route_anchors`) owned by the
backend/generation lane, plus a real anchored plate in a world kit. Reported, not faked.

## Visual gate (binding — `docs/concept-parity/VISUAL-GATE.md`)

Run on this module on the CP-024 rig (`CDP 9357`, state `~/.hermes/coursebook-test-cp024`):

```
cd visual && node find-cdp.mjs          → 9371, 9357   (9357 = the CP-024 rig; 9371 untouched)
node audit.mjs --port 9357              → frames/, diffs/, report.html, report.json
scripts/compare-ref.sh <frame> docs/concept-parity/refs/map.png docs/visual-review/cp-024/compare course-home-1049-light
```

Results — full detail in `docs/visual-review/cp-024/VISUAL-GATE.md`:

- **course-home route**: 1515 × 1889 as rendered at the audit's 1440 viewport (the capture cells
  above are the width-controlled frames); `data-cb-scope = light`; `CB Display` **true**, `CB UI`
  **true**; **axe serious/critical: none** on the course-home subtree.
- **pixel diff vs baseline**: not measurable on this rig — the stored baseline is 1101 × 1336 and
  this window renders 1517 × 1891 (`ratio 1.0`, reason `size 1101x1336 -> 1517x1891`), so the diff
  is a geometry mismatch, not content drift. Recorded as such, not as a pass.
- **similarity vs the approved reference** (`map.png`, 1344 × 768): **0.6830** (RMSE 0.316998) on
  the 1049-light frame, scaled to equal height. The reference is landscape concept art and the
  frame is a portrait route crop, so this is a composition/material comparison, not parity.
- **Other destinations** (Courses, Workshop, Parent Studio) show pre-existing serious axe findings
  whose targets are all outside `[data-cb-course-detail]` (shelf `summary` nodes, studio tab
  buttons, workshop card buttons) — recorded, not this card's file, not fixed here.
- Sheets: `compare/course-home-1049-light-sheet.png` (render | approved reference),
  `compare/sbs-course-home-1049-light.png` (`scripts/cp-sbs.py`, full 1344×768 crop),
  `compare/course-home-1049-light.txt` (RMSE + similarity).

## Files

- `desktop/src/90-course.js` — the composition, breakpoints, `data-cb-course-body`.
- `desktop/plugin.js` — generated (never hand-edited).
- `tests/test_cp_024_course_home_v3.py` — pure-render contracts + the new composed `CourseDetail` test.
- `scripts/cp-capture.mjs` — the deep-screen flags and `settleLayout()`.
- `docs/visual-review/cp-024/` — this file, `SCORECARD.md` (blank for the reviewer),
  `VISUAL-GATE.md`, `capture.sh`, the drivers, 13 `.png` + 13 `.stamp.json`, `compare/`.

## Known gaps to record in the review

1. **Map mode is not live** (contract gap above). The renderer accepts anchors; the wire does not
   carry them.
2. **`course-end`** has no honest rig course — no course has full independent evidence, and seeding
   evidence rows would fabricate learner progress on a frame that claims completion. Uncaptured.
3. **`loading` / `error` live frames**: an in-flight or failed read cannot survive the door's
   reload and `--no-reload` cannot start from a course home the caller has not driven. Both are
   component-proven (`test_course_home_v3_world_and_read_states`) and are the two named states with
   no live cell.
4. The aside's other-course rows read `library.list` (`limit: 20`) with a client-side filter; a
   sibling course can be missing on a very large library. Backend narrowing reported, not made.
5. The legacy `OverviewView`'s "Recent evidence" list is retired from the overview; the Evidence tab
   remains the record and M7 carries the recorded count (`0 of 4 sections have evidence`). If the
   owner wants attempts summarized on the home, that is a new M-region in SPEC-V3, not a silent
   addition here.

## Verification run on this tree

- `python3 scripts/build_plugin.py --check` → matches `desktop/src` (`6aaa9c39…b3c0`).
- `tests.test_plugin_build` + `tests.test_visual_gate_tools` + `tests.test_cp_024_course_home_v3`
  → 23 tests OK.
- `tests.test_m4_visual_audit` → 14 tests OK; `scripts/m4v-audit.py` regenerated on this module
  (15/15 claims PASS, pin = `6aaa9c39…b3c0`).
- Targeted regression group (tokens_v3, v3_primitives, a11y_structure, home_hub, gate_scope,
  cp_shelf_facts, lesson_views, gm010, cp_capture_stamp) → 136 tests OK (skipped=2).
- **Full suite on `73aa29c`: `Ran 3491 tests in 1267.604s` — OK (skipped=11).** A first run of the
  same suite on this commit reported 4 failures that were all one generated file: `desktop/plugin.js`
  had been replaced with master's build (`4087908c…03b7`) mid-run. Restored with
  `git checkout -- desktop/plugin.js`, the four named tests passed (25 OK), and the full rerun above
  held the file at `6aaa9c39…b3c0` for the whole run. No test in the tree writes the repo module;
  the cause was not reproducible.
- `bash scripts/validate-plugin.sh` → **release gate passed 4/4** on `73aa29c` (4092 files).
