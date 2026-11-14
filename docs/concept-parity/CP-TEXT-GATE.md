# CP-TEXT-GATE — scene lettering is contained by the object it is painted on

Date: 2026-11-13 (MST). Owner: `cbqa`. Tree: `origin/master` **b7ed6cf0**,
`desktop/plugin.js` sha256 `098e65d9…bd47` (the module the shipped proof names).
Gate: `tests/test_desktop_scene_text_containment.py`.

## 1. What was wrong with the existing gate

`tests/test_desktop_home_scene_parity.py` proves the committed proof page
(`design/home-scene.html`) is a fresh render of `desktop/plugin.js`. That tie is necessary and it is
not a layout statement: it proves *the proof matches the code*, not that a label sits inside the
board it is painted on. A run can overhang its object by a fifth of its ink and every existing check
still passes, because no other test compares drawn glyphs with the scene's own geometry.

This gate closes that hole for the wide Home scene.

## 2. Method

`tests/fixtures/scene-text/measure.mjs` (Chromium over CDP, 1344x768, deviceScaleFactor 1):

1. **Ink is a difference, not a segmentation.** The page is photographed with the scene intact
   (`base.png`) and again with exactly one run's glyph paint killed (`color: transparent`). The
   object's background, its shadows and every box stay where they were, so the changed pixels are
   exactly what that run drew. `color` is used instead of `visibility` so no layout or background
   moves between the pair.
2. **Reference geometry is the object's own box, in its own frame.** Chromium does not implement
   `Element.getBoxQuads`, so four zero-size absolutely positioned probes at 0/100 % of the object's
   padding box report its four corners after every self and ancestor transform. The tag
   (`rotate(-3deg)`) and the four cards (`rotate(±0.6–1.6deg)`) are measured through the homography
   those four points define: a local `(u,v)` frame of `0..width x 0..height`. A tilted object's
   axis-aligned bounding box cannot hide spill, because spill is evaluated in the object's frame.
3. **The mask is restricted to the run's painted rects.** `Range.getClientRects()` on the run's text
   contents gives the area the run paints; the diff mask is intersected with it (2 px pad). A style
   mutation can re-raster a rotated layer's antialiased edge by a subpixel; those edge pixels are
   not lettering and must not enter the mask. Two captures of an unchanged page are byte-identical
   (verified: 0 differing pixels over four captures), so the pair itself is deterministic.
4. **Clipped overflow is measured in layout, not paint.** A card clips with `overflow: hidden`, so
   glyphs that leave it are simply absent from the pixels. The driver walks each run and its
   ancestors up to the object and reports any box whose `scrollWidth` exceeds `clientWidth` by more
   than 1 px. Width only: `scrollHeight` routinely exceeds `clientHeight` by a few px of descender
   and leading, which is not clipping.

The metric values for the shipped scene, at the tree named above, are in §4.

## 3. Metric contract

Measured per run and per object (one "unit" = one object plus the lettering painted on it):

| metric | limit | why |
| --- | --- | --- |
| ink outside the object in its local frame | `spill_pixels == 0` (0.5 px edge tolerance) | the defect this gate exists for |
| run layout rects inside the object | no corner outside (0.5 px) | catches spill that clipping hides |
| `scrollWidth - clientWidth` of the run and its ancestors | `<= 1 px` | catches text the object clips away |
| `|left - right|` (centred units) | `<= 4 %` of object width | a centred label that drifted |
| `|top - bottom|` (centred units) | `<= 7 %` of object height | side bearing / descender slack |
| ink floor | `>= 300` ink px and `>= 8 px` ink height | a blank mask must not pass as a measurement |

**Which units are centring-checked, and why.** The gate does not assume every label is centred. The
units file (`tests/fixtures/scene-text/scene.units.json`) declares `centre: true` only where the
scene's CSS centres the type: the hero panel (`text-align: center`, three runs — question, subline
and the two CTA labels) and the tag plate (`display: grid; place-items: center`). Card titles and
cover marks are left-aligned in the card's body, so their centring margins are **reported** in the
evidence but not asserted; their containment is asserted unconditionally. A left-aligned run that
leaves its card still fails on `spill`, on the layout rects or on the scroll-overflow signal.

The floor is deliberately far below the measured values (§4: smallest ink 586 px, smallest ink
height 12.4 px), so it only fires when a run stopped painting — it cannot excuse a real defect.

## 4. The shipped scene passes

`python3 -m unittest tests.test_desktop_scene_text_containment -v` (exit 0, `Ran 3 tests … OK`).
Twelve runs across six objects, all `spill = 0`, all layout boxes inside, no scroll overflow:

| unit | object | centre | ink px | l / r | t / b | dx | dy | spill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hero-lettering | 645.2x242.8 | yes | 14399 | 34.13 / 34.12 | 27.50 / 40.30 | 0.00 % | 5.27 % | 0 |
| tag-lettering | 148.0x148.0 | yes | 601 | 20.70 / 20.49 | 67.70 / 65.44 | 0.14 % | 1.53 % | 0 |
| card-1-lettering | 176.0x175.0 | no | 1491 | 9.80 / 64.31 | 38.57 / 27.56 | (30.97 %) | (6.29 %) | 0 |
| card-2-lettering | 176.0x175.0 | no | 729 | 10.80 / 39.18 | 117.00 / 45.62 | (16.12 %) | (40.78 %) | 0 |
| card-3-lettering | 176.0x175.0 | no | 868 | 10.00 / 68.11 | 38.60 / 45.67 | (33.02 %) | (4.04 %) | 0 |
| card-4-lettering | 176.0x175.0 | no | 949 | 11.12 / 66.45 | 38.70 / 44.91 | (31.44 %) | (3.55 %) | 0 |

Per-run ink: question 8437, subline 4694, CTA labels 682 / 586, tag 601, card titles 918 / 729 /
377 / 407, cover marks 573 / (card 2 has none) / 491 / 542. Values in parentheses are measured but
not asserted (left-aligned runs, §3).

Hero vertical slack (5.27 %) is the tightest asserted number in the shipped scene: the panel has
18 px top padding against 24 px bottom padding, and the threshold is 7 %.

## 5. The gate has teeth

**Fixture fail (paste):** `tests/fixtures/scene-text/overhanging.html` is a rotated board whose label
is deliberately wider and taller than the board (plus a passing control board in the same page).
Running the *scene* assertions on it fails:

```
CB_SCENE_TEXT_TARGET=overhanging python3 -m unittest tests.test_desktop_scene_text_containment -v
...
FAIL: test_the_shipped_scene_lettering_stays_inside_its_object
AssertionError: Lists differ: ["board-fail: the layout box of (self) ('O[484 chars].57'] != []
board-fail: the layout box of (self) ('Overhanging board label') leaves the object (2 corners outside)
board-fail: (self) ('Overhanging board label') overflows its box (DIV +162px wider than its client area)
board-fail: 1602 ink px (43.31% of the run) fall outside the object (220.0x110.0); margins l=11.67 r=-160.43 t=13.91 b=63.57
board-fail: horizontally off-centre by 78.22% of width (limit 4%); margins l=11.67 r=-160.43
board-fail: vertically off-centre by 45.15% of height (limit 7%); margins t=13.91 b=63.57

measured:
board-pass  object 220.0x110.0 centre=True ink=504  l=71.51 r=71.39 t=46.94 b=49.57 dx=0.06%  dy=2.39%  spill=0 (0.00%)
board-fail  object 220.0x110.0 centre=True ink=3699 l=11.67 r=-160.43 t=13.91 b=63.57 dx=78.22% dy=45.15% spill=1602 (43.31%)
Ran 3 tests in 15.073s
FAILED (failures=1)
```

Then the shipped scene passes (exit 0) — fail-then-pass, in that order, in the same tree.

**Permanent regression coverage** (`test_the_overhanging_fixture_is_caught`,
`test_a_text_regression_in_the_shipped_scene_is_caught`) keeps both directions in a green suite:
the fixture defect is asserted to be caught (spill and overflow reported, control board clean), and
two injected regressions in a *fresh render of the real scene* are asserted to be caught:

* `tag-label-too-large` — tag type at 60 px nowrap: caught on spill (the tag does not clip).
* `card-title-overflows-its-clip` — card title at 32 px nowrap: caught on scroll overflow even though
  the card's `overflow: hidden` means no ink pixel leaves the card. This is the case a pixel-only
  gate would miss.

## 6. How to run

```bash
python3 -m unittest tests.test_desktop_scene_text_containment -v
CB_SCENE_TEXT_TARGET=overhanging python3 -m unittest tests.test_desktop_scene_text_containment -v
```

Requirements: `node`, `chromium`, `numpy` and `Pillow` (the suite skips with a named reason when
they are absent; the desktop render suites already require the first three of the environment).

The gate regenerates the proof page with `scripts/gen-home-proof.py` and asserts it is byte-identical
to the committed `design/home-scene.html` before measuring, so it cannot measure a stale artifact.

## 7. Limits, stated

- The gate measures the **wide Home scene at 1344x768**, the frame the proof and the reference are
  authored at. It does not measure the 1200–1344 fitted scale or the narrower Homes; at scale < 1
  the pixel mask is still valid but its 1 px floors and 2 px rect pad would need rescaling, so that
  is a separate measurement (the legibility card covers cap height and contrast at both widths).
- It measures **visible** text runs declared in `scene.units.json`. The visually-hidden section pair
  (`[data-cb-home-scene-meta]`, `clip-path: inset(50%)`) is deliberately not measured: it paints
  nothing, and the floor would report it as a blank run. Its accessibility is covered by the copy
  oracles, not by this gate.
- The run inventory is explicit. A new text run added to the scene without adding it to
  `scene.units.json` will not be measured; the counts asserted here (`6` objects, `12` runs) make a
  silent disappearance fail, but not a silent addition. Reviewers should require an inventory update
  with any scene type change.
- Subpixel rendering is deterministic for the same pair in one Chromium build, but a Chromium
  upgrade can move antialiasing; the layout and scroll-overflow signals are insensitive to that.
