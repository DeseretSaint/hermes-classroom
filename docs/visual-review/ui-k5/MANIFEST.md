# VQ-006 installed capture manifest

Generated 2026-11-11T18:51:36+00:00 by `scripts/vq-manifest.py`.
Commit: `40a846c6a80aa122296c40dc5ebc24b832e0f71d`  
Module sha256: `09f63984d5243e98cf45c56df28a41c3ce2a843d8215922212588a1804522792`
Capture run: **unrecorded**

Cells: **0 passed / 1 failed / 0 never captured** (1 of 1 matrix cells have a frame)

## Matrix

| destination | 1344 |
|---|---|
| course-home | fail |

## Never captured

None — every matrix cell has a frame.

## Failed cells

### course-home--1344

- image [data-cb3-fox="point"] [data-cb3-fox-safe="24px"] > img: natural 256px is below 2x rendered 208.00px
- background [data-cb-destination="home"] [data-cb-scope="light"] > div: natural 96x96px is below 2x rendered 1344.00x714.00px (both axes)


## Images per cell

**course-home--1344** — 2 image(s), 4 background layer(s)

| selector | kind | natural | rendered | ratio | sha256 | evidence |
|---|---|---|---|---|---|---|
| `[data-cb-course-plate-art] [data-cb-course-plate="art"] > img` | scene_plate | 2688x1536 | 952.03x305.34 | 2.823 | `8f3f81c875a355b6dc9041aca55ae0297b65359dda3de464fa75c36b08531481` | verified |
| `[data-cb3-fox="point"] [data-cb3-fox-safe="24px"] > img` | fox_pose | 256x256 | 208x208 | 1.231 | `b152e628b826a563538ea1b696e86bc9e3c95468a17e710489fb6741b29a0b33` | not required |

Background layers (judged for placeholder, data URI stand-in, Press Plate and, unless the layer tiles at its natural size, 2x):

| selector | repeat | size | natural | rendered | ratio | 2x judged | sha256 | problems |
|---|---|---|---|---|---|---|---|---|
| `[data-cb-destination="home"] [data-cb-scope="light"] > div` | repeat | auto | 96x96 | 1344x714 | 0.071 | no (tiles at natural size) | `0058897dc5aca76a52a6d2230c8b13832cafdfeddd2613312a284910db4821f4` | none |
| `[data-cb-destination="home"] [data-cb-scope="light"] > div` | no-repeat | cover | 96x96 | 1344x714 | 0.071 | x, y | `7ecca423831eb4ee7a5e2bab77d138fb89d743d35fb1e26c999880dc44ef7cd6` | natural 96x96px is below 2x rendered 1344.00x714.00px (both axes) |
| `[data-cb3-stamp="current"] [data-cb3-stamp-index="1"] > span` | no-repeat | contain | 256x256 | 48x48 | 5.333 | x, y | `9d270478dcd526d2838d893805cbb85206cec45265581ff24f7e4d264b920dc4` | none |
| `[data-cb3-stamp="upcoming"] [data-cb3-stamp-index="2"] > span` | no-repeat | contain | 256x256 | 48x48 | 5.333 | x, y | `9d270478dcd526d2838d893805cbb85206cec45265581ff24f7e4d264b920dc4` | none |

