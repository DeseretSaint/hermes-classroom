# CP-024 — visual gate results (binding, `docs/concept-parity/VISUAL-GATE.md`)

Run on branch `wt/cp-024-course-home` at module
`1f29b0ac6a2f36f0e22f13792fa8f4bb6bb1fb2cb180c6ce2aa849bcdc973ff9`, against the CP-024 rig only:
state `~/.hermes/coursebook-test-cp024-r2`, backend `127.0.0.1:44427`, window **CDP 9361**.
`find-cdp.mjs` also answers `9395`; that window belongs to another profile's run and was not opened,
driven or captured.

```bash
cd visual
node find-cdp.mjs                 # 9395, 9361   (9361 = this card's rig)
node audit.mjs --port 9361        # frames/, diffs/, report.html, report.json  (copied here)
cd ..
scripts/compare-ref.sh docs/visual-review/cp-024/course-home--1049--light--100--default.png \
  docs/concept-parity/refs/map.png docs/visual-review/cp-024/compare course-home-1049-light
python3 scripts/cp-sbs.py --concept docs/concept-parity/refs/map.png --crop 0,0,1344,768 \
  --product docs/visual-review/cp-024/course-home--1049--light--100--default.png \
  --out docs/visual-review/cp-024/compare/sbs-course-home-1049-light.png
node docs/visual-review/cp-024/measure-course-home.mjs --port 9361 --width 1440
```

## The card's surface — course home v3

The course home is a **deep screen** (shell state under `#/coursebook`), so `visual/audit.mjs` — which
scores the four destination routes — cannot reach it. `measure-course-home.mjs` attaches to the same
rig, drives the same real clicks, emulates the audit viewport, and measures the route. Raw record:
`gate-course-home-1440.json` (and `-1049`, `-900`, `-460`).

| Fact | Value |
|---|---|
| Route as rendered @ 1440 × 900 emulated viewport | **1412 × 846** |
| `data-cb-scope` | **light** (`motion: full`) |
| `CB Display` loaded | **true** |
| `CB UI` loaded | **true** |
| axe serious/critical on `[data-cb-course-detail]` | **none** (0 serious/critical; 0 violations) |
| Filled primaries on the assembled course home | **1** |
| Route mode / body | `list` (no anchored plate in this rig) / `split` at 1440 and 1049, `stacked` at 900 and 460 |
| DOM order | `plate → route → aside` at **1440, 1049, 900 and 460** |
| Horizontal overflow | **false** at 1440, 1049, 900 and 460 |
| Title word splits (live, per-word line boxes) | **none** at 1440, 1049, 900 and 460 |

## Pixel diff against the baseline

**Not applicable for this route**: `visual/baselines/` holds `home`, `courses`, `workshop` and
`studio` only — there is no stored course-home baseline to diff against, and inventing one on the
same run that renders it would be self-certification. Recorded as not-applicable, not as a pass.

The audit run itself reports the four destination routes as `frame size changed` against their
baselines because this rig's window is tiled to 941 × 662 while the baselines were recorded in a
larger window — a geometry mismatch, recorded rather than claimed as drift or as a pass.

## Similarity against the approved reference

`docs/concept-parity/refs/map.png` — 1344 × 768 landscape concept art; the frame is a 1049 × 1166
portrait route crop.

```
render:    course-home--1049--light--100--default.png (810x900 after equal-height scaling)
reference: docs/concept-parity/refs/map.png (1575x900 after equal-height scaling)
rmse:      0.31669
similarity: 0.6833
sheet:     docs/visual-review/cp-024/compare/course-home-1049-light-sheet.png
diff:      docs/visual-review/cp-024/compare/course-home-1049-light-diff.png
```

`scripts/cp-sbs.py` board: `compare/sbs-course-home-1049-light.png` (2059 × 768; concept 1344 px,
product 691 px at equal height).

## Composition differences a reviewer must weigh (not parity claims)

- The reference paints an illustrated landscape with a winding route and numbered nodes; this frame
  renders the **typographic plate** ("No scene yet / The lesson works without art."), the
  **vertical route list under the plate**, and the aside to its right at 1049. The rig's course has
  no approved world plate and the wire cannot carry `route_anchors` yet (MANIFEST "Map mode"). The
  map composition is proved by tests, not by this frame.
- The reference's shelf of cards is replaced by the honest three-row `Your other courses` aside,
  and its header search / second create button are removed (SPEC-V3 §5.4 "better than the concept").
- Palette, material and type are the product's own v3 contract; the concept is an AI still with
  invented text, so the board compares material, type and density only.

## Other destinations (audit route list) — pre-existing, outside this card

From this round's `gate-report.json` (port 9361):

| Route | Fonts | serious/critical | Targets (all outside `[data-cb-course-detail]`) |
|---|---|---|---|
| Home | true / true | none | — |
| Courses | true / true | `color-contrast` | shelf rows / cover disclosures in `30-home.js`, `40-courses.js` |
| Workshop | true / true | none | — |
| Parent Studio | true / true | `color-contrast` | studio controls in `95-studio.js` |

These live in files CP-024 does not own. Recorded for the owning cards; not fixed here.
