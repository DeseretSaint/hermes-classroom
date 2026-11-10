# CP-024 evidence manifest — the v3 course home (R-MAP)

Branch: `wt/cp-024-course-home`   Commit: `57f0fea` (rebased onto master `b09b65f`, which carries
CP-020b `131ec86`; this evidence packet is the commit that follows it)
Maker: `lattice`   Reviewer: `cbqa` (must not be the maker)
Module: `desktop/plugin.js` sha256 `314e62e4659ec013e0c86858ab7b478c6ff351d2db79440d7796d71fc525fd6a`
(built with `python3 scripts/build_plugin.py` from 20 segments; `tests.test_plugin_build` green)

**Status: the live frame matrix is NOT captured yet.** This manifest is the packet skeleton and the
exact capture plan. It is committed under the supervisor's partial-build ruling of 2026-11-10, which
defers *the capture matrix and the review* to CP-040 (`t_5403e4a1`), the merge seam that owns the
six-branch union and the full seven-destination matrix. This branch is now rebased onto the merged
CP-020b primitives (master `b09b65f`), so the module sha below is the post-rebase module. No PNG in
this directory is a placeholder and no cell claims a pass: a frame
without a `cp-capture.mjs` stamp is not evidence, and a stamp whose `plugin_sha256` differs from the
commit under review is invalid.

## What the code proves without a window

`tests/test_cp_024_course_home_v3.py` renders the shipped module (`desktop/plugin.js`, not the
segment) in a component preview and asserts the card's three named contracts:

| Test | Contract |
|---|---|
| `test_course_home_v3_nodes_are_dom_buttons` | every section is a `<button>` on its declared normalised anchor, `aria-current="step"` on the current one, disabled on a gated one |
| `test_course_home_v3_anchor_fallback` | absent, malformed, partial (< all sections placed) and sub-900 px routes all fall back to the complete vertical `StampNode` route |
| `test_course_home_v3_one_primary` | exactly one filled control per surface, labelled with the backend's own `next_step.label`, including the plan-review and course-complete steps |

A component preview loads neither the host shell nor the Tailwind utility CSS. It proves the DOM
contract, not the painted result; the journey below is still owed.

## Cells owed (eight baseline + named states)

Screen row: `course-home.v3` (`docs/visual-review/MATRIX.md`), card CP-024, concept reference
`docs/concept-parity/refs/map.png` (crop to be chosen against the mounted plate, then recorded here).

Baseline — 1049 / 900 / 460 × light / dark = six cells, plus the 1349 wide cell and one forced-colors
cell = **eight**:

| # | File | Viewport | Mode | Scale | Notes |
|---|---|---|---|---|---|
| 1 | `course-home--1049--light--100--default.png` | 1049 | light | 100 | map mode expected (`data-cb-course-home-v3="map"`) |
| 2 | `course-home--1049--dark--100--default.png` | 1049 | dark | 100 | same composition on the dark token table |
| 3 | `course-home--900--light--100--default.png` | 900 | light | 100 | boundary: still map, aside measure 268 px |
| 4 | `course-home--900--dark--100--default.png` | 900 | dark | 100 | |
| 5 | `course-home--460--light--100--default.png` | 460 | light | 100 | list mode: no node sits on the art; fox hidden (< 620) |
| 6 | `course-home--460--dark--100--default.png` | 460 | dark | 100 | |
| 7 | `course-home--1349--light--100--default.png` | 1349 | light | 100 | wide cell |
| 8 | `course-home--1049--light--100--forced-colors.png` | 1049 | light | 100 | `--forced-colors`, one ring must survive |

Named states (each also owed as a stamp, at 1049 light unless the state changes the layout):

- `plan-in-review` — a real draft course whose recorded next step is plan review; one filled control,
  its label the backend's, heading `The plan is waiting for you`
- `no-world` — a course whose plate carries no usable anchors: complete vertical route, `No scene yet`
- `world-running` — a plate with a full anchor set: every section placed, none clipped by the plate
- `world-rejected` — a malformed anchor entry: the offending section still appears in the list route
- `course-end` — every section has evidence: `Course complete`, evidence line reads `n of n`
- `loading` — real in-flight `library.list`/`course.outline`, never a fabricated spinner
- `error` — a real `ok:false` envelope from the backend, with its one next action
- `text-200` — 200 % text at 460: no clipped label, no page-level horizontal scroll

## Command shape (one cell)

```bash
node scripts/cp-capture.mjs --name course-home--1049--light--100--default \
  --out docs/visual-review/cp-024 --cdp-port "$CB015_CDP_PORT" \
  --state "$COURSEBOOK_TEST_STATE" --plugin desktop/plugin.js \
  --backend-url "$CB013_BACKEND_URL" --token "$CB013_TOKEN" \
  --route-width 1049 --color-scheme light --require-v3
# forced colors: add --forced-colors
# reduced motion: add --reduced-motion
```

Every cell must pass the script's own refusals: module sha equal to the checkout, `[data-cb-route]`
present with no render-error marker, fonts loaded, every route `img` decoded, no host element painted
above the route box, the pixel veto, 100 % zoom, `[data-cb-v3-ready]` with textures `ready`, and no
React duplicate/missing-`key` console error. A refused capture writes `<name>.refused.json` and is
reported as a renderer fault, not as a pass.

## Side-by-side boards

```bash
python3 scripts/cp-sbs.py --concept docs/concept-parity/refs/map.png --crop X,Y,W,H \
  --product docs/visual-review/cp-024/course-home--1049--light--100--default.png \
  --out docs/visual-review/cp-024/sbs-1049-light.png
```

The concept is an AI still with garbled labels and invented data; the board compares material, type
and density only, and claims no parity of text.

## Known gaps to record in the review, not to paper over

1. `world.read` asset rows in this tree declare no `route_anchors`, so the shipped default course
   renders the vertical route. The map mode is proved by the module-level test and by the
   `world-running` fixture; a real course with declared anchors is still needed for a live map frame.
2. The aside's other-course rows read the existing `library.list` shelf with a client-side filter
   (`course_id !== row.course_id`, `recipe !== 'parent'`). If the shipped library page is capped below
   20 items a sibling course can be missing; a `library.list` narrowing is a backend change and is
   reported, not made here.
3. On the `world-rejected` path the section stays reachable in the list route but its plate position is
   lost; whether the plate should show a visible "route not placed" mark is a design call for the
   reviewer.

## Post-rebase verification (the unblock condition on the card)

The branch was rebased onto master `b09b65f` (which carries CP-020b `131ec86`) on 2026-11-10 after
the supervisor's partial-build ruling lifted. What was re-run on the rebased tree:

- `python3 scripts/build_plugin.py` → `desktop/plugin.js` sha256 `314e62e4…fd6a` from 20 segments,
  and a second run is byte-identical (`git status` empty afterwards).
- `tests.test_plugin_build` — 11 tests, OK.
- `tests.test_cp_024_course_home_v3` — 5 tests, OK (the three card-named contracts plus the
  copy/facts sweep and the segment-contract guard).
- `tests.test_desktop_tokens_v3`, `test_v3_primitives`, `test_desktop_a11y_structure`,
  `test_desktop_home_hub`, `test_desktop_gate_scope`, `test_cp_shelf_facts`,
  `test_desktop_lesson_views` — 121 tests, OK (2 skipped).
- The segment binds only primitives that exist in the merged `85-v3-primitives.js`; its new code
  reads `cb3Type`/`cb3Lead`/`cb3Role` and no raw hex, no viewport unit, no inline shadow.

Ownership note: the module export seam in `desktop/src/99-tutor.js` is CP-040's step 2, so this card
does not edit that file. The test reaches `CourseHomeV3` and its helpers through a test-only export
block appended to the *staged copy* of `desktop/plugin.js`; the repo module exports none of them,
so the shim cannot mask a missing symbol (an unknown name throws at import).

Still red, deliberately: `tests.test_m4_visual_audit.test_evidence_is_not_stale_against_the_shipped_module`
pin (`audit.json` still records master's `1aa11577…aed2`). Regenerating it on this branch would fight
the parallel CP-021/022/023 branches that rewrite the same file; CP-040 replays the matrix and re-pins
on the union. The capture matrix and the `cbqa` scorecard remain CP-040's, per the ruling.
