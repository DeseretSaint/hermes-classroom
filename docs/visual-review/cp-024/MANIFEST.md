# CP-024 evidence manifest — the v3 course home (R-MAP)

Branch: `wt/cp-024-course-home`
Base: master `ef7ec52` (carries CP-020b primitives, CP-038's capture door, CP-043's keys, the
visual-gate tools `docs/concept-parity/VISUAL-GATE.md`, `visual/find-cdp.mjs`,
`scripts/compare-ref.sh`), with `origin/master` merged three times on top: `9c769e7` (CP-044,
CP-049, CP-051), `acf5ab2` (Gate 8 docs/release-evidence only) and `07976d8` (CP-042 bundled-pack
shipping and its evidence). None of the three merges touched `desktop/src/` or `desktop/plugin.js`;
the module stayed `31c8bc94…42dc`, so the 15 stamps still name the shipped bytes.
Maker: `lattice`   Reviewer: `cbqa` (must not be the maker)
Module: `desktop/plugin.js` sha256 `31c8bc9484dbfb09d73a2d6b9019c4386d27910eeadb9aed36ba8d9bfbd942dc`
(built by `python3 scripts/build_plugin.py` from 20 segments; `--check` reports the same bytes)

**Status: review round 4 (evidence-scale repair).** Round 3's code was verified good by the
reviewer; its packet was not. The 15-cell live matrix has been **re-shot from a restarted window**
after fixing the capture door and the verifier, so every `--100--` cell now really is a 16 px root
and the `--200--` cell really is 32 px. 15/15 frames stamped on this module, 0 refusals,
`verify_stamps.py` → 15 stamps / 0 problems (now with per-cell root-font assertions, frame-byte
re-hashing and duplicate-frame rejection). One gap remains honest and unchanged: no live frame can
show the anchored **map** mode, because no `cb.rpc` v25 field carries a plate's `route_anchors`
(see "Map mode" below).

## What changed in review round 4 (cbqa, contract lens at `6313723`)

| Defect (round 3) | Fix in this round |
|---|---|
| P1 evidence integrity: 14 of 15 frames were shot at a 32 px root while every name said `--100--`; `course-home--460--light--100--default.png` and `--200--text-200.png` were byte-identical (sha256 `2106344f…`) | `scripts/cp-capture.mjs` now sets the root font **explicitly for every live cell** — shared default `16px`, `32px` only where declared — records the requested value in `capture.root_font`, and restores the page's prior inline value in the same `finally` that restores zoom. Repeated flags now resolve **last-wins**, so the matrix's shared `--root-font 16px` cannot swallow a cell's `--root-font 32px` (this was the second half of the bug: the first re-shoot still produced a 16 px text-200 cell until the flag precedence was fixed) |
| P1: `verify_stamps.py` checked the root font only when the name's scale was not 100, so it printed 0 problems on a packet where 14 frames contradicted their names | the verifier now asserts the root font for **every** cell, compares it with the capture's own `root_font.requested`, re-hashes each PNG against `capture.sha256`, and fails two cells that share one frame hash. `tests/test_cp_024_capture_scale.py` proves each rule with a negative fixture (a 100 % cell at 32 px, a 200 % cell at 16 px, a duplicate hash, a mismatched frame, and a clean pass) |
| Evidence hygiene: gate JSONs (16 px) and shipped frames (32 px) described different renders | all four `gate-course-home-{1440,1049,900,460}.json` re-measured on the re-shot rig at 16 px, `VISUAL-GATE.md` / `MANIFEST.md` / `capture.sh` all describe this round's rig and matrix |

## What changed in review round 3 (cbqa, live at `59ee6ba` / `6aaa9c39`)

| Defect (round 2) | Fix in this round |
|---|---|
| P2: in list mode the route rendered **after** the aside at every width (`plate → aside → route`), contradicting SPEC-V3 §5.4 "below M5" and "the aside moves under the route" | the vertical route now lives in the main column directly under the plate, so the DOM order is `plate → route → aside` at 1049/900/460; the map route stays inside the plate. Proved in the pure-render harness (`out.order` on every case at every width), in the mounted `CourseDetail` harness (`domOrder`), and measured live (`gate-course-home-{1440,1049,900,460}.json`: `dom_order: plate -> route -> aside`, no horizontal overflow) |
| P2: at 460 / 200 % text the plate title broke mid-word (`"demonstration"`, `"an classroom"`) because `[data-cb-course-plate-title]` set `overflow-wrap: anywhere` | the plate's type field and the course `h2` now wrap **between** words (`overflow-wrap: break-word; word-break: normal; hyphens: none`). `test_course_home_v3_titles_wrap_between_words` asserts the rule in the composed screen; `cp-capture.mjs` gained a live **word-wrap probe** (per-word line boxes for the course title and the plate title) that is stamped on every cell, and `verify_stamps.py` fails on a split word. All 15 stamps: `word_wraps: []` |
| P2 (found while capturing `course-end`): a completed course still marked its last opened section `You are here`, so one node was not `Done` on the completion beat | `cb3CourseNodes` takes `complete`; at the close every independent node reads `Done`, including the page's last-opened section. Asserted in `test_course_home_v3_one_primary` (5/5 done, no `aria-current`), and the live `course-end` frame shows `Course complete` + 4/4 with every node done |
| Acceptance: `course-end`, `loading`, `error` had no stamped cell | all three now have live cells on this module (`course-end`, `read-error`, `loading` — see below). 15/15 cells stamped, every door gate true |
| Evidence hygiene: MANIFEST/VISUAL-GATE named `CDP 9357` / state `coursebook-test-cp024` while the packet was shot on `9361` / `…-cp024-r2`; `gate-report.json` predated the r2 run | every doc and script now names the r2 rig (`9361`, backend `44427`, `~/.hermes/coursebook-test-cp024-r2`); `gate-report.json` is this round's `visual/report.json` (port 9361) |
| Evidence hygiene: `no-world` was byte-identical to `default` (the rig's course has no world row at all) | the duplicate cell is **retired**: `default` carries the no-world state and `capture.sh` says so. A cell that repeats another cell is coverage theatre |
| `capture.sh` prerequisites still said `9357 / 44417` | corrected to the r2 rig and made env-overridable in one place |

## The matrix — 15 cells, every stamp `plugin.window_sha256 = 31c8bc94…42dc`

Verified by `verify_stamps.py` on this module: **15 stamps, 0 problems** (sha, name ↔ width ↔ theme,
the root font on every cell and the capture's own requested size, frame bytes against the stamp, no
two cells sharing a frame hash, all door gates true, course home in `overview`, no word split). Each
frame passed the door's gates: plugin sha, route present, no render error, fonts loaded, images
decoded, no host overlay, no unpainted region, 100 % zoom, `[data-cb-v3-ready]` with textures
`ready`, no React key warning.

| # | Cell | Route (w × h) | Theme | Root font |
|---|---|---|---|---|
| 1 | `course-home--1049--light--100--default` | 1049 × 1166 | light | 16 px |
| 2 | `course-home--1049--dark--100--default` | 1049 × 1166 | dark | 16 px |
| 3 | `course-home--900--light--100--default` | 900 × 1530 | light | 16 px |
| 4 | `course-home--900--dark--100--default` | 900 × 1530 | dark | 16 px |
| 5 | `course-home--460--light--100--default` | 460 × 1466 | light | 16 px |
| 6 | `course-home--460--dark--100--default` | 460 × 1466 | dark | 16 px |
| 7 | `course-home--1349--light--100--default` | 1349 × 1166 | light | 16 px |
| 8 | `course-home--1049--light--100--forced-colors` | 1049 × 1166 | light, forced-colors | 16 px |
| 9 | `course-home--1049--light--100--plan-in-review` | 1049 × 1166 | light | 16 px |
| 10 | `course-home--1049--light--100--world-running` | 1049 × 1166 | light | 16 px |
| 11 | `course-home--1049--light--100--world-rejected` | 1049 × 1166 | light | 16 px |
| 12 | `course-home--1049--light--100--course-end` | 1049 × 1166 | light | 16 px |
| 13 | `course-home--1049--light--100--read-error` | 1049 × 1166 | light | 16 px |
| 14 | `course-home--1049--light--100--loading` | 1049 × 1166 | light | 16 px |
| 15 | `course-home--460--light--200--text-200` | 460 × 2980 | light | 32 px |

The heights are the true 100 %-text heights from this round's re-shoot; round 3's listed heights
(1811/2516/2980) were the 32 px-root heights, which is exactly the defect this round repairs. The
dark and named-state cells render the same course home at the same widths; their frame hashes are
distinct (the verifier rejects duplicates).

Rerun: `docs/visual-review/cp-024/capture.sh` (no argument = all 15; each cell is listed by name).
Every cell is `capture.reloaded: false` on a window restarted on this module, so the stamp names the
module the window evaluated. `verify_stamps.py` re-checks the whole packet in one command.

### What makes the three new states honest

- **`read-error`** — a stored `course_worlds` row whose `brief_json` does not satisfy the contract
  makes `world.read` answer `INTERNAL_ERROR` (`scripts/cb013-rpc.py world.read` reproduces it in one
  call). One read fails; the backend and every other read are healthy. The frame shows the surface's
  own error sentence and its `Try again`, with the route kept. No page-level interception, no
  injected script.
- **`loading`** — `course.outline` is held open by `forward-proxy.mjs`, a forwarding proxy on the
  port the window is already connected to; every other request passes through to the same backend
  unchanged, including the `/api/ws` upgrade (tunnelled) the host needs before it mounts any plugin
  route. The frame says `Opening this course.` and keeps the plate and route. The window is
  restarted on the proxy so main's cached connection health is the proxy's, not a dead port's.
- **`course-end`** — a documented **fixture**: a course with no evidence rows has its four recorded
  objective states set to `independent_evidence` for the frame, then restored. No attempt, check or
  evidence row is fabricated; the fixture course has none, so the review scheduler has nothing to
  demote. This proves the completed state renders, not that a learner finished a course. The shelf
  row is made reachable by bumping that enrollment's `updated_at` (bookkeeping), which is restored
  too.

## Rig

Disposable state `~/.hermes/coursebook-test-cp024-r2` (`home/`, `userdata/`), backend
`hermes serve --isolated` on `127.0.0.1:44427` (token `cp024-test-token`), window CDP
`127.0.0.1:9361` (dev Electron, class `hermes`), installed module = checkout = `31c8bc94…42dc`.
The older `coursebook-test-cp024` state belongs to another profile's run and is not used here.

```bash
COURSEBOOK_TEST_STATE=$HOME/.hermes/coursebook-test-cp024-r2 \
CB013_CDP_PORT=9361 CB013_BACKEND_URL=http://127.0.0.1:44427 \
  docs/visual-review/cp-024/capture.sh
python3 docs/visual-review/cp-024/verify_stamps.py
node docs/visual-review/cp-024/measure-course-home.mjs --port 9361 --width 1049
```

Teardown: `scripts/cb013-live-window.sh --stop` and `scripts/cb013-live-backend.sh --stop` with
`COURSEBOOK_TEST_STATE` / `COURSEBOOK_TEST_HOME` at that state.

## Map mode: NOT live in this tree — a contract gap, not a render bug

The card asks for nodes on anchors "stored as normalised coordinates in the plate manifest". No
`cb.rpc` v25 field can carry them:

- `world.read` → `course_world.assets[]` is a closed projection (`role`, `section_id`,
  `section_key`, `artifact_id`, `style_hash`, `prompt_hash`, `textless`) — no manifest, no anchors;
- `course_world.brief` is the closed `world_brief` schema — adding `route_anchors` makes the
  handler's own result fail contract validation; reproduced live as
  `world.read` → `INTERNAL_ERROR: … is not valid under any of the given schemas`;
- `artifact.get` → `provenance` is a closed five-field projection — no anchors either.

So every live frame shows the **complete vertical `StampNode` route** (the no-anchor fallback
SPEC-V3 §5.4 requires), and map mode is proved by the module tests
(`test_course_home_v3_nodes_are_dom_buttons`, `..._anchor_fallback`) and the brief-carrier logic,
not by a live anchored plate. The fix is a contract change (`course_world_asset` gains a `manifest`
with `route_anchors`) owned by the backend/generation lane, plus a real anchored plate in a world
kit. Reported, not faked.

## Visual gate (binding — `docs/concept-parity/VISUAL-GATE.md`)

Numbers and the paste are in `VISUAL-GATE.md`; raw records:
`gate-course-home-{1440,1049,900,460}.json`, `gate-report.json` (this round's `visual/report.json`,
port 9361), `compare/course-home-1049-light-sheet.png`,
`compare/sbs-course-home-1049-light.png`.

## Files

- `desktop/src/90-course.js` — the composition, breakpoints, `data-cb-course-body`, the route's DOM
  order, the title wrap rule, the completion precedence in `cb3CourseNodes`.
- `desktop/plugin.js` — generated (never hand-edited).
- `tests/test_cp_024_course_home_v3.py` — pure-render contracts, the composed `CourseDetail` test
  (one primary / one route / one heading / dot sizes / DOM order / title wrap / completion).
- `scripts/cp-capture.mjs` — the deep-screen flags, `settleLayout()`, the word-wrap probe, the
  explicit per-cell root font (set + record + restore) and last-wins flag precedence.
- `tests/test_cp_024_capture_scale.py` — negative fixtures for the verifier (100 % cell at 32 px,
  200 % cell at 16 px, duplicate frame hash, mismatched frame bytes) and the capture door's
  set/restore contract.
- `docs/visual-review/cp-024/` — this file, `SCORECARD.md` (blank for the reviewer), `VISUAL-GATE.md`,
  `capture.sh`, `verify_stamps.py`, `measure-course-home.mjs`, `forward-proxy.mjs`, `list-shelf.py`,
  the drivers (`drive-course-home.js`, `drive-course-plan.js`, `drive-course-end.js`),
  `set-appearance.mjs`, 15 `.png` + 15 `.stamp.json`, `compare/`.

## Known gaps to record in the review

1. **Map mode is not live** (contract gap above). The renderer accepts anchors; the wire does not
   carry them.
2. **`course-end` is a labelled fixture** (see above): the state renders, the learner history behind
   it does not exist.
3. **`loading` / `read-error` use a transport double / a deliberately invalid stored brief.** Both
   exercise the shipped code path with the app's real reads, but neither is a natural rig state; the
   scripts that produce them are in the packet and are rerunnable.
4. The aside's other-course rows read `library.list` (`limit: 20`) with a client-side filter; a
   sibling course can be missing on a very large library. Backend narrowing reported, not made.
5. The legacy `OverviewView`'s "Recent evidence" list is retired from the overview; the Evidence tab
   remains the record and M7 carries the recorded count. If the owner wants attempts summarized on
   the home, that is a new M-region in SPEC-V3, not a silent addition here.
6. The visual gate has **no stored baseline** for the course-home route (`visual/baselines/` holds
   Home, Courses, Workshop, Studio only), so the gate's pixel-diff field is recorded as
   not-applicable rather than as a pass.
7. Frame-reading note: the disposable rig holds two Japanese courses with near-identical titles
   ("…an L0 demonstration classroom" and "…a Sample L0 classroom"). They are **different course
   ids**, and the aside filters by id — verified live on the rig, current `crs_6500…`, others
   `crs_97ee…`, `crs_9fa5…`, `crs_a96e…`. A frame whose aside appears to list "the course you are
   on" is showing the twin course, not a self row.

## Verification run on this tree (review round 4)

- `python3 scripts/build_plugin.py --check` → matches `desktop/src` (`31c8bc94…42dc`); `node --check
  desktop/plugin.js` OK.
- `tests.test_plugin_build` + `tests.test_cp_024_course_home_v3` + `tests.test_cp_024_capture_scale`
  + `test_m4_visual_audit` + `test_visual_gate_tools` + `test_cp_capture_stamp` → **Ran 56, OK**
  (the three card-named tests, the composed overview, the DOM-order/title-wrap/completion tests, and
  the seven new capture-scale/verifier tests).
- Targeted regression group (`plugin_build`, `cp_024` ×2, `m4_visual_audit`, `visual_gate_tools`,
  `cp_capture_stamp`, `desktop_tokens_v3`, `v3_primitives`, `a11y_structure`, `home_hub`,
  `gate_scope`, `cp_shelf_facts`, `lesson_views`) → **Ran 177, OK (skipped=2)**.
- Full suite on the merged round-4 tree → **Ran 3517 tests in 959.639s, OK (skipped=11)** (includes
  CP-042's pack-shipping tests brought in by the `07976d8` merge).
- `docs/visual-review/cp-024/verify_stamps.py` → **15 stamps, 0 problems** (per-cell root font,
  requested size, frame bytes, duplicate-frame rejection).
- `scripts/m4v-audit.py` regenerated on this module (15/15 claims PASS) + `test_m4_visual_audit` → 14 OK.
- `bash scripts/validate-plugin.sh` on `b15931c` → **release gate passed 4/4** (4148 files).
