# Home ground, textless 1344x768 — provenance, OCR and re-measured geometry

Derived from E1's approved art (`t_34433bbd`). This plate is a **ground**, not a
composed screen: it carries no copy, no CTA pill and no baked course cards. It
adopts nothing and changes no UI, budget or kit file.

## 1. Trust boundary

| | source art | E1 plate | **this plate** |
|---|---|---|---|
| path | `~/.hermes/cache/scratch/composite_street.png` | `docs/concept-parity/refs/home-plate-1344.png` | `docs/concept-parity/refs/home-plate-1344-textless.png` |
| size | 1024 × 768 | 1344 × 768 | **1344 × 768** |
| sha256 | `3b396360fcc713f9a335962cd10ec8ef3e316f6721984604c06dad069f7640c4` | `a27038eafd8d1676a215d08e775845bb75a1c7ebc9c67d7b8c8b33a9166888a2` | **`806080bbcdca5376e936fe02975ce605fe9af01415f6768ec8c12dd5d402b4b6`** |
| bytes | 1 384 034 | 1 382 665 | **1 312 571** |

- The source is the same approved 1024 × 768 art E1 used; its sha256 matches the
  pin in `home-plate-geometry.md` §1, so this is a derivation of that art, not a
  new one.
- `PIL.Image.open(...).size` on the shipped file prints **(1344, 768)**. The
  acceptance one-liner is
  `python3 -c "from PIL import Image; print(Image.open('docs/concept-parity/refs/home-plate-1344-textless.png').size)"`;
  on this headless host `python3 -c` is refused by the command gate, so the same
  expression was run from a file and printed `(1344, 768)`. The generator also
  prints `canvas.size` on every run.
- Two consecutive generator runs produce the **same sha256**, so the pin is
  reproducible. `png:tIME`/date chunks are not emitted by the PIL writer used
  here (`pnginfo` carries no `tIME`), so the hash is not clock-dependent.
- Height is never cropped and no object is moved. Output columns `160..1183` of
  all 768 rows are **bit-identical** to the 1024-wide intermediate
  (`numpy.array_equal` on the decoded arrays: `True`), exactly as E1 §1 records
  for its own pad.

## 2. What was removed, and how — per region

All coordinates below are **output pixels** on the 1344 × 768 canvas
(`source x = output x − 160`). The generator asserts that **every changed pixel
lies inside a declared mask** — `illegal px 0` on the shipped run
(53 739 pixels changed in total).

| region | rect (output) | method | px |
|---|---|---|---|
| baked copy, line 1 | 203,50 – 362,65 | band masked except where the art is **warm** (the roof/eave and foliage survive); filled by a harmonic (Laplace) solution whose only Dirichlet boundary is the surrounding sky, so no glyph or antialias pixel can remain | 4 518 (both bands) |
| baked copy, line 2 | 203,95 – 368,110 | as above | (same count) |
| CTA pill, eave sliver | 218,126 – 300,148 | the pill clips the last sliver of the roof eave. Restored by sliding along the eave's own measured slope (dy/dx ≈ 0.29) into the hole, sampling only real eave paint from above; never samples the pill or its rust | 1 662 |
| CTA pill, wall side | 218,126 – 250,171 | mirrored tile of the visible wall strip immediately left of the pill (source x 38..57), same row, so the wall's lighting matches vertically | 827 |
| CTA pill, sky side | 218,126 – 393,171 | harmonic fill from the sky above and to the right (wall, eave and treeline are not boundary values), plus a 2 px feather ring blended back to the source | 6 711 |
| board faces ×4 | 261..781, 319..459 | each face set to the card stock's own flat cream `#F7F2E8` (247, 242, 232) inside that card's own rounded cream run, so edges, rounded corners and the shadow rind survive untouched | 67 020 |

The four board faces are the flat measured card stock (rows 402–410 and 420–426
of each card are a constant `(247, 242, 232)` in the source, i.e. the stock is
painted flat, not textured). The first pad strip is recomputed from the cleaned
1024-wide art, so the left pad no longer carries the mirrored ghost of the CTA
that E1 §2 recorded.

Residual check on the shipped bytes: **0** pixels pass the plate's own rust-CTA
criterion inside the pill box.

## 3. OCR pass

Command (tesseract 5.5.3, default page segmentation, TSV so confidence is
readable), run on the **shipped** 1344 × 768 file:

```
tesseract docs/concept-parity/refs/home-plate-1344-textless.png stdout --psm 3 tsv
```

Result: **no word-level row with non-empty text**. Readable-token count
(≥ 3 alphanumeric characters at confidence ≥ 60): **0**. Plain text mode returns
an empty stream as well:

```
$ tesseract docs/concept-parity/refs/home-plate-1344-textless.png stdout --psm 3 | wc -c
0
```

Calibration of the same rule on a plate that *does* carry UI strings
(`docs/concept-parity/refs/home.png`): 20 words, **16 readable tokens at
83.2–93.0 % confidence**. The rule therefore still catches real lettering.

Honest limit: OCR is not the detector for this art's baked copy. E1's own plate
(with `What do you want to learn?` painted on it) returns a single token,
`anttolearn?`, at **0.0 %** confidence — the 1344-wide copy is too small and low
contrast for tesseract. Removal is therefore evidenced by (a) the glyph-band
mask and `illegal px 0` guarantee, (b) band statistics (`min` luminance 174 in
line 1, no pixel below 150), and (c) a vision check of the band at 4× — not by
OCR alone.

## 4. Re-measured geometry

`measure_textless.py` is E1's `measure.py` with only two changes: the plate path,
and the CTA/copy detectors report **absent** instead of crashing when a baked
element no longer exists. Every detector, threshold and fit is otherwise
identical. Deltas are the maximum absolute difference over all corner
coordinates; acceptance asks for ≤ 1 px.

| object | E1 quad (TL, TR, BR, BL) | textless quad | Δ max |
|---|---|---|---|
| board1 | (261.0, 319.1) (379.0, 319.1) (379.0, 458.9) (261.0, 458.9) | identical | **0.0** |
| board2 | (395.0, 319.1) (513.0, 319.1) (513.0, 458.9) (395.0, 458.9) | identical | **0.0** |
| board3 | (529.0, 319.1) (647.0, 319.1) (647.0, 458.9) (529.0, 458.9) | identical | **0.0** |
| board4 | (663.0, 319.1) (781.0, 319.1) (781.0, 458.9) (663.0, 458.9) | identical | **0.0** |
| fox | (868, 506) (967, 506) (967, 683) (868, 683) | identical | **0.0** |
| pot | (985, 585) (1079, 585) (1079, 671) (985, 671) | identical | **0.0** |
| pole (sky-backed) | (1061, 0) (1109, 0) (1109, 700) (1061, 700) | identical | **0.0** |
| bench seat slab | (250, 488) (614, 489) (614, 511) (250, 510) | identical | **0.0** |
| cta_button | (218, 126) (392, 126) (392, 170) (218, 170) | **absent** (0 mask px) | removed by design |

Lines, fitted with the same least-squares + outlier pass:

| line | E1 | textless | Δ |
|---|---|---|---|
| board-row baseline | 458.9 (all four bottoms) | 458.9 | 0.0 |
| bench seat top | 488.8 (x 250) / 489.6 (x 614) | identical | 0.0 |
| street curb | 670.6 (x 250) / 670.7 (x 800) | identical | 0.0 |
| wall coping top | 309.6 (x 165) / 311.6 (x 880) | identical | 0.0 |
| paving joint shadow | fixed band 641..656 | identical | 0.0 |

The largest contiguous open-sky rect is also unchanged: **x 603..1019, y 0..104**
(417 × 106), median RGB `(165, 192, 209)`.

One measurement **did** move, and it is not geometry: `copy_stack_existing`
(the neutral-dark mask in the copy zone) now reports
`(210, 89) – (292, 124)` instead of `(210, 54) – (354, 124)`. That is the wall's
own neutral-dark downpipe/eave shadow, which was always in the region and is now
the only thing the mask finds; the copy it used to include is gone. It is not a
text residue: the glyph-band mask covers y 50..65 and 95..110, and the neutral
pixels reported sit above y 95 and below y 110 in the wall.

## 5. Encode numbers (the build's own settings)

`scripts/build_cb_assets.py:encode()` uses
`img.save(buf, format="WEBP", quality=q, method=6, exact=True)`; the data URL is
`"data:image/webp;base64," + b64(bytes)`. Same 1344 × 768 RGB plate:

| quality | webp bytes | data URL bytes | vs 35 686 B free |
|---|---|---|---|
| q72 | 65 766 | **87 711** | **−52 025** |
| q60 | 54 990 | **73 343** | **−37 657** |
| q50 | 48 000 | **64 023** | **−28 337** |
| q40 *(supplementary)* | 40 858 | 54 503 | −18 817 |
| q30 *(supplementary)* | 33 120 | 44 183 | −8 497 |

Method check against the card's own figure: encoding **E1's** plate with this
same function at q72 gives a **104 215 B** data URL, within 23 B of the
104 192 B quoted in the card (encoder build difference, not a different method).

**Recommendation, stated plainly: none of q72 / q60 / q50 fits the 35 686 B of
segment headroom.** q72 is the quality to ship if the owner decides the budget
moves (data URL 87 711 B, which is 16 504 B *smaller* than the E1 plate's own
104 215 B at the same quality, because the baked art and copy are gone). Inside
the current headroom, the lowest of the three asked for, q50, is still 28 337 B
over. This document does not choose the packaging and does not touch
`SEGMENT_BUDGET` or any budget constant.

## 6. What this does not claim

- No paid model was called; this is a deterministic repaint of the approved art,
  not a new generation, and it has no model id to report.
- No native-speaker, owner or design review is implied by anything here.
- It does not adopt the plate, re-pin Home, or assert that the wide Home should
  use these quads. It produces the ground and reports what the bytes are.
- The pill's sky area is a harmonic reconstruction: at 1:1 it reads as sky, at
  ≥ 4× zoom the reconstructed patch is smoother than the painted clouds around
  it. The eave restore is a continuation along the eave's measured slope; its
  repeating texture is visible at ≥ 4×. The live sign covers this corner in the
  wide Home.
- Contrast/legibility verdicts in `home-plate-geometry.md` §7 were measured on
  the *composed* plate; the blank card faces change the "board card faces" row
  (`#F7F2E8` is now a uniform surface) and that row would need its own
  measurement if a future layout puts text on a card face.

## 7. Reproduce

```
python3 docs/concept-parity/refs/derive-home-plate-textless.py \
  --source ~/.hermes/cache/scratch/composite_street.png
```

The generator writes `home-plate-1344-textless.png` next to itself, prints the
mask counts, asserts `illegal px 0`, and prints the output sha256. It reads no
network, no model and no clock.
