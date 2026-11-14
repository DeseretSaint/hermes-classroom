# Home plate, 1344x768 — geometry and legibility

Measured against `origin/master` **b7ed6cf0** (2026-11-13). This file prepares a
measurement. It adopts nothing: no `desktop/`, `design/`, `tests/` or existing
reference file is touched, and no UI is changed by this card.

## 1. Trust boundary

| | source | output |
|---|---|---|
| path | `~/.hermes/cache/scratch/composite_street.png` | `docs/concept-parity/refs/home-plate-1344.png` |
| size | **1024 × 768** (1.333) | **1344 × 768** (1.750) |
| sha256 | `3b396360fcc713f9a335962cd10ec8ef3e316f6721984604c06dad069f7640c4` | `a27038eafd8d1676a215d08e775845bb75a1c7ebc9c67d7b8c8b33a9166888a2` |
| bytes | 1 384 034 | 1 382 665 |

The output is derived, not fetched. The centre band is **bit-identical** to the
source: output columns `160..1183`, all 768 rows, compare equal to source columns
`0..1023` (verified with `numpy.array_equal` on the decoded PNG). No row of the
source is removed or resampled, so the street foreground survives to y=767.

## 2. How the width was extended

Height is never cropped. The 320 px of extra width is split evenly and filled by
**mirrored, blurred edge strips**, then feathered against the source's own edge
column:

| | value |
|---|---|
| pad left | **160 px** (output x `0..159`) |
| pad right | **160 px** (output x `1184..1343`) |
| pad total | 320 px |
| mirror bands | left: source x `0..159` flipped; right: source x `864..1023` flipped |
| blur | Gaussian, radius **14.0 px** |
| blur ramp | 0 at the seam → full at **48 px** out |
| construction | `out = blurred_mirror · α + sharp_mirror · (1−α)`, `α = clip(d/48, 0, 1)`, `d` = distance from the seam |

Why the ramp blends against the *unblurred mirror* rather than against black or a
replicated column: a horizontal mirror is already continuous at the seam (the
flip puts source column 0 next to output column 160, which is also source column
0), so the blend only controls how much defocus is applied. Two rejected variants
are recorded here because both were tried on this plate and both are wrong:

| variant | defect |
|---|---|
| RGBA strip over a black canvas (α→0 at seam) | 1 px **zero-luminance seam** at x=159 and x=1184; mean-luminance step 95.6 and 115.8 |
| feather against a replicated edge column | horizontal streaking across the 48 px ramp |

Accepted variant, measured on the delivered PNG:

| check | value |
|---|---|
| seam luminance step x=159→160 | **0.43** |
| seam luminance step x=1183→1184 | **0.00** |
| zero-luminance columns | none |
| centre-band identity | true |

The pads read as out-of-focus continuation. They do carry soft mirrored ghosts of
the baked CTA (left) and the pole (right); neither is legible as text or as a
second object at 1:1. **No text should ever be laid on a pad** (see §6).

## 3. Canvas grid

| region | x range | content |
|---|---|---|
| left pad | 0..159 | mirrored + blurred, no layout use |
| source band | 160..1183 | all measured geometry below |
| right pad | 1184..1343 | mirrored + blurred, no layout use |

Every coordinate in this document is a pixel coordinate on the 1344 × 768
output, with `(0,0)` at the top-left and inclusive-exclusive rects.

## 4. Lines

Fitted with least squares plus iterative outlier rejection (residual > 2 px
dropped). "Samples" is the number of columns that survived the fit.

| line | role | y at x₀ | y at x₁ | slope | samples (dropped) | residual mean / max | criterion |
|---|---|---|---|---|---|---|---|
| wall coping top | wall skyline datum | 309.6 (x=165) | 311.6 (x=880) | 0.00273 | 118 (37) | 0.65 / 1.95 | top of the low-chroma grey tile band above the plaster |
| board-row baseline | the "shelf" line | **458.9** (x=261) | **458.9** (x=781) | 0.0 | 4 quads, 117–139 edge points each | ≤ 1.0 | bottom edge of all four cream cards |
| bench seat top | **ledge** | 488.8 (x=250) | 489.6 (x=614) | 0.00237 | 85 (7) | 0.27 / 0.80 | first warm-wood row (r−b ≥ 45, lum ≤ 155) under the plaster |
| stone skirting top | **ledge** (wall plinth) | 503.7 (x=620) | 503.9 (x=860) | 0.00093 | 39 (11) | 0.39 / 1.13 | plaster (12-row mean lum ≥ 168) → stone (lum < 152) |
| street curb | ground-plane break | 670.6 (x=250) | 670.7 (x=800) | 0.00029 | 72 (9) | 0.51 / 1.39 | bright walkway (lum ≥ 160) → street shadow (lum ≤ 130) |

Notes that matter for layout:

- **There is no physical shelf in this art.** The boards hang flat on the wall;
  the only horizontal datum across the board row is their shared baseline at
  y = 458.9, and it is exact (all four bottom edges land on the same row).
- The ledge lines are y ≈ 489 (bench seat) and y ≈ 504 (wall plinth). The bench
  occludes the plinth between x = 250 and x = 614; the plinth is measurable on
  the right run (`620..860`) and at x = 196..216 on the left (y = 503 at x = 196
  and 216, one 497 outlier at x = 208).
- The curb is 1 px flat across 550 px; treat it as horizontal at y = 671.
- The wall's right end is at **x = 867** (plaster → street transition at 868–870).

## 5. Object quads

Corner order is top-left, top-right, bottom-right, bottom-left. "Short side" is
the smaller of the fitted width and height, in px.

| object | quad (TL, TR, BR, BL) | W × H | short side | how it was measured | confidence |
|---|---|---|---|---|---|
| board1 | (261.0, 319.1) (379.0, 319.1) (379.0, 458.9) (261.0, 458.9) | 118.0 × 139.8 | **118.0** | cream card stock (r ≥ 218, r−b ≤ 34) against plaster (r−b ≈ 88); 4 edges fitted independently | high (≤1 px) |
| board2 | (395.0, 319.1) (513.0, 319.1) (513.0, 458.9) (395.0, 458.9) | 118.0 × 139.8 | **118.0** | as board1 | high |
| board3 | (529.0, 319.1) (647.0, 319.1) (647.0, 458.9) (529.0, 458.9) | 118.0 × 139.8 | **118.0** | as board1 | high |
| board4 | (663.0, 319.1) (781.0, 319.1) (781.0, 458.9) (663.0, 458.9) | 118.0 × 139.8 | **118.0** | as board1 | high |
| cta_button | (218, 126) (392, 126) (392, 170) (218, 170) | 174 × 44 | **44** | rust fill mask (r−g ≥ 55, r−b ≥ 65) | high |
| fox | (868, 506) (967, 506) (967, 683) (868, 683) | 99 × 177 | **99** | rust-orange silhouette mask (r−g ≥ 45, r−b ≥ 70) | high |
| pot | (989, 545) (1079, 545) (1079, 652) (989, 652) | 90 × 107 | **90** | 5× grid read + vertical profiles at x = 1000/1035/1070 (rim highlight y = 545–549, lit base y = 650–656) | **±5 px** (masks contaminated, see below) |
| pole_sky_extent | (1061, 0) (1109, 0) (1109, 150) (1061, 150) | 48 × 150 | **48** | dark-wood edges on 33 sky-backed rows, y = 20..150 | high above y = 150; **no full-height claim** |
| bench_seat | (250, 488.8) (614, 489.6) (614, 499.4) (250, 498.6) | 364.0 × 9.8 | **9.8** | top edge fitted on 85 columns; front edge = first row under lum 110 (its cast shadow) | high |

Baked copy block (not an object, but it occupies pixels): **x 210..354, y 54..124**
— the two existing lines of copy on the plate. The CTA button sits at y 126..170,
immediately below it.

### Rejected / qualified readings

- **Pot.** Two automatic readings were rejected and are recorded so nobody
  re-derives them: a terracotta mask gave `985..1079 × 585..671` (top 42 px low,
  left 4 px off, because the pot's shaded side fails the mask), and a per-row
  count bbox gave `979..1067 × 550..670` (both edges contaminated — the left edge
  ran into pavement, the right into the pole). The delivered quad is the grid
  read, ±5 px.
- **Pole.** Its silhouette is only separable against sky. Below y ≈ 150 it is in
  front of foliage and buildings; below y ≈ 672 it merges into pavement shadow
  with no usable edge (rows 672..720 read as flat pavement grey across
  x 1060..1140, and at y = 560/600/640 the column through the pot and the pole is
  dark end to end). The quad therefore records the measured sky-backed extent only.
  **No lean and no full-height footprint are claimed** — either would have to be
  re-measured, not extrapolated from this table.
- **Bench.** The quad above is the **seat slab** (its lit top face). Below it the
  bench's shadowed front face and legs run dark to y ≈ 565 (luminance < 100 at
  x = 300/420/600 through y = 555, pavement brightening at 570–580); those are
  not separate quads here.

## 6. Sky and the heading zone

| | value |
|---|---|
| largest contiguous open-sky rect | **x 603..1019, y 0..105** (417 × 106) |
| sky median RGB in that rect | `(163, 192, 210)` |
| the rect is bounded by | roofs/treeline below it; buildings close it on the right at x ≈ 1020. The pole stands further right, at x 1061..1109, outside this rect |

The plate already carries baked copy at x 210..354, y 54..124. A Home scene that
lays a heading over this plate must not place a second heading beside it; the
free sky is the block **to the right** of the baked copy, not above it.

## 7. Where a text run can and cannot live

Method: each zone is a rect lying on a single painted surface. Contrast is WCAG
2.x, computed from per-pixel relative luminance. `worst` is the 5th-percentile
luminance for dark ink `#2B2B2B` and the 95th-percentile for white `#FFFFFF`,
taken on a 9×9 box-filtered luminance so that a 1–2 px painted seam does not
decide the verdict. `median` is the same ink against the zone's median luminance.
WCAG AA needs **4.5:1** for body text and **3:1** for large text. An 11 px cap
height implies a ≈16 px font and a ≈15 px minimum clean band for one line; the
"band" column applies that, not 11 px of ink.

| surface | rect | free W × H | dark worst / median | white worst | texture (grad p95) | verdict at ≥ 11 px cap |
|---|---|---|---|---|---|---|
| **open sky** | 603,8 – 1020,105 | 417 × 97 | **6.23 / 7.44** | 1.62 | 0.0136 (quiet) | **YES**, dark ink; up to 4 lines of 20 px; full sentences fit |
| **plaster, right of board4** | 790,350 – 864,486 | 74 × 136 | **6.55 / 7.95** | 1.68 | 0.049 | **YES**, dark ink, but only a short label: 74 px ≈ 9 characters at 11 px cap |
| **plaster band under the board row** | 620,462 – 862,502 | 242 × 40 | **5.77 / 6.73** | 1.85 | 0.057 | **YES**, dark ink, one 20 px line (40 px band); two lines only if leading is cut |
| stone skirting (right run) | 621,505 – 858,550 | 237 × 45 | 2.26 / 2.81 | 3.70 | 0.059 | **NO** at 11 px: dark fails AA, white 3.70 < 4.5. White is acceptable only at ≥ 24 px |
| pavement (upper terrace) | 170,585 – 840,660 | 670 × 75 | 2.52 / 6.00 | 1.90 | 0.092 (joints) | **NO** as an unbroken run — the median passes but paving joints and cast shadows drop it to 2.52. Passes only for a run confined inside one slab and re-checked locally |
| street below curb | 170,700 – 1040,760 | 870 × 60 | 1.24 / 2.11 | 2.62 | 0.079 | **NO** — white passes on the median (6.69) but the curb highlight drops it to 2.62 |
| bench seat slab | 256,490 – 610,499 | 354 × **9** | 3.10 / 4.45 | 2.47 | 0.122 | **NO** — band is 9 px, shorter than one 11 px cap, and both inks fail |
| board card faces | e.g. 261..379 × 319..459 | free strip only **13 px** tall | 9.75 / 12.69 on cream | 1.12 | 0.368 (baked art) | **NO** — every face is committed to the baked mini-art, `Lesson N`, progress bar and `% done`; the only clean cream strip is 110 × 13, under the 15 px band |
| left pad | 4,40 – 156,740 | 152 × 700 | 1.32 / 2.74 | 1.98 | 0.015 | **NO** — neither ink clears 4.5; blurred content behind |
| right pad | 1188,40 – 1340,740 | 152 × 700 | 1.28 / 1.93 | 1.64 | 0.017 | **NO** — neither ink clears 4.5 |
| sky left of the baked copy | 165,8 – 200,120 | 35 × 112 | 1.02 / 5.74 | 2.04 | 0.077 | **NO** — only 35 px wide and the house roof cuts the median |

Summary, plainly:

- **One wide, quiet, high-contrast text surface exists: the open sky at
  x 603..1019, y 0..105, for dark ink only.**
- **Two plaster patches can take an 11 px cap run in dark ink**: 74 × 136 right
  of board4 (short label only) and 242 × 40 under the board row (one line).
- **Everything else cannot carry an 11 px cap run**: skirting, pavement, street,
  bench, board faces and both pads all fail on either height or worst-case
  contrast, or are already occupied by baked content.

## 8. What this document does not claim

- It does not adopt the plate, change the Home scene, or assert that the wide
  layout should use these zones. It reports what the pixels support.
- Contrast is computed against the plate's pixels, not against a future overlay
  treatment. A scrim, card or solid fill changes the answer and would need its own
  measurement.
- The pot (±5 px) and the pole (top 150 px only) are not survey-grade. The four
  boards, the CTA, the fox, the bench seat, and all five lines are.
- No native-speaker, owner, or design review is implied by any number here.
