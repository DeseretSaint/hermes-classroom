# CP-024 — visual gate results (binding, `docs/concept-parity/VISUAL-GATE.md`)

Run on branch `wt/cp-024-course-home` at module `6aaa9c3909bd75a8791347ac9f5f53c5b619c20aecf16b6f19421384c846b3c0`,
against the CP-024 rig only (`CDP 9357`, state `~/.hermes/coursebook-test-cp024`). Port `9371` also
answered `find-cdp.mjs`; it is not this card's window and was not opened, driven or captured.

```
cd visual
node find-cdp.mjs                 # 9371, 9357
node audit.mjs --port 9357        # frames/, diffs/, report.html, report.json
cd ..
scripts/compare-ref.sh <frame> docs/concept-parity/refs/map.png \
  docs/visual-review/cp-024/compare course-home-1049-light
python3 scripts/cp-sbs.py --concept docs/concept-parity/refs/map.png --crop 0,0,1344,768 \
  --product <frame> --out docs/visual-review/cp-024/compare/sbs-course-home-1049-light.png
```

## The card's surface — course home v3

| Fact | Value |
|---|---|
| Route as rendered (audit viewport 1440) | **1515 × 1889** (route box, light scope) |
| Capture cells (width-controlled) | 1049 × 1166, 900 × 1166, 460 × 1166, 1349 × 1166 |
| `data-cb-scope` | **light** (dark cells: `course-home--1049--dark`, `course-home--900--dark`, `course-home--460--dark`) |
| `CB Display` loaded | **true** |
| `CB UI` loaded | **true** |
| axe serious/critical on `[data-cb-course-detail]` | **none** (0 violations) |
| Filled primaries on the assembled screen | **1** (`Review 3 objective(s)`) |
| `data-cb-course-body` at 1515 route px | `split` |

## Pixel diff against the baseline

Not measurable on this rig: the stored baseline frame is **1101 × 1336** and this window renders
**1517 × 1891**, so `audit.mjs` reports `diff ratio 1.0 — size 1101x1336 -> 1517x1891`. That is a
geometry mismatch between two differently sized rigs, not content drift, and it is recorded as
unmeasurable rather than as a pass. The width-controlled capture cells above are the frames whose
geometry is known.

## Similarity against the approved reference

`docs/concept-parity/refs/map.png` — 1344 × 768 landscape concept art; the frame is a 1049 × 1166
portrait route crop.

```
render:    course-home--1049--light--100--default.png (810x900 after equal-height scaling)
reference: docs/concept-parity/refs/map.png (1575x900 after equal-height scaling)
rmse:      0.316998
similarity: 0.6830
sheet:     docs/visual-review/cp-024/compare/course-home-1049-light-sheet.png
diff:      docs/visual-review/cp-024/compare/course-home-1049-light-diff.png
```

`scripts/cp-sbs.py` board: `compare/sbs-course-home-1049-light.png` (2059 × 768; concept 1344 px,
product 691 px at equal height).

## Composition differences a reviewer must weigh (not parity claims)

- The reference paints an illustrated landscape with a winding route and numbered nodes; this frame
  renders the **typographic plate** ("No scene yet / The lesson works without art.") and the
  **vertical route list**, because the rig's course has no approved world plate and the wire cannot
  carry `route_anchors` yet (MANIFEST "Map mode"). The map composition is proved by tests, not by
  this frame.
- The reference's shelf of cards is replaced by the honest three-row `Your other courses` aside,
  and its header search / second create button are removed (SPEC-V3 §5.4 "better than the concept").
- Palette, material and type are the product's own v3 contract; the concept is an AI still with
  invented text, so the board compares material, type and density only.

## Other destinations (audit route list) — pre-existing, outside this card

| Route | Fonts | axe serious/critical | Targets (all outside `[data-cb-course-detail]`) |
|---|---|---|---|
| Home | true / true | none | — |
| Courses | true / true | `color-contrast`, `label-content-name-mismatch` | shelf `summary` nodes, course-cover disclosures |
| Workshop | true / true | `label-content-name-mismatch` | `button[data-cb-workshop-open=…]`, favourite toggle, card action |
| Parent Studio | true / true | `color-contrast`, `label-content-name-mismatch` | studio tab buttons, `summary` |

These live in `30-home.js` / `40-courses.js` / `95-studio.js` / `96-workshop.js`, which CP-024 does
not own. Recorded for the owning cards; not fixed here.
