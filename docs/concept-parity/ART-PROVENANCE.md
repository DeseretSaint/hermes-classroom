# A1 fox provenance — model sheet and seven poses

Card: CP-010 (`wt/cp-010-fox`). Owner `easel`, reviewer `quill`.
Machine record: `audit/cp010-fox/provenance.json` (written by `scripts/cp010-provenance.py`).
Exact prompts: `audit/cp010-fox/prompts.json`. Style authority: `docs/concept-parity/ART-BIBLE.md`.

Every hash below was printed by that script from the file on disk; no value here is typed from
memory. If a file changes, the script and `tests/test_cp010_fox_assets.py` fail together.

## Verdict up front

Eight plates were generated, keyed and checked: one model sheet (four views) and seven poses.
All eight pass a tesseract text check (no readable lettering), carry no pure-black contour
(≤ 0.078 % of opaque pixels), and are clean cutouts with zero magenta-contaminated pixels. Four
generations were discarded before shipping: model sheet round 1, clock round 1, point round 1
(quadruped) and point round 2 (bipedal, but both arms hung at the side so the plate carried no
gesture). The model sheet has **not** been signed by the owner yet, and the poses were produced
against it before approval — that order is recorded as a defect of this card, not hidden. Any pose
is regenerable from the same sheet if the sheet is rejected.

## How each plate was made

1. Text prompt from the ART-BIBLE template family, recorded verbatim in `prompts.json`.
2. Generated through the host image tool (`image_generate`), which answers through the nous image
   gateway and serves the media from `v3b.fal.media`.
3. Poses were generated with the model sheet's **provider media URL** in `reference_image_urls` —
   never a local file, never another pose. Each row below records the exact URL used.
4. Chroma key on the file's own sampled corner colour at `-fuzz 30%`, trim, pad to a square
   transparent canvas (`scripts/cp010-fox-prep.py`), then one deterministic colour temper
   (`-modulate 92,72,100`) so every plate sits in the same muted gouache family.
5. Exports at 512, 256, 128 and 64 px tall, alpha preserved.
6. Checks: fringe audit (`scripts/cp010-fringe-audit.py`), pigment audit
   (`scripts/cp010-art-audit.py` → `audit/cp010-fox/art-audit.json`), tesseract default page
   segmentation (`audit/cp010-fox/ocr-<plate>-final.txt` and `-tsv`), and a vision pass against
   the model sheet.

## Rows

| plate | prompt | prompt_hash (16) | asset sha256 (16) | bytes | OCR | round |
|---|---|---|---|---|---|---|
| `fox-model-sheet` | M1 | `198848189f4a34ab` | `cfb21ca10a260a82` | 793,363 | no text | 2 |
| `fox-wave` | P-wave | `24aeaa0c886f9564` | `ac90df33a0eb7736` | 309,372 | no text | 1 |
| `fox-point` | P-point-r3 | `294655d99986de05` | `dbf6fbd37cdf83e3` | 293,761 | no text | 3 |
| `fox-clock` | P-clock | `c49332b40c83cf65` | `716215b41e25d4be` | 271,453 | no text | 2 |
| `fox-read` | P-read | `034b689cf832c2ee` | `b17e9c1662dd9e01` | 367,317 | no text | 1 |
| `fox-cheer` | P-cheer | `28a6b1863db35df2` | `267c5a069848f57b` | 298,043 | no text | 1 |
| `fox-think` | P-think | `ada420ab9fd19c3d` | `e30dff2a7c7e837a` | 247,249 | no text | 1 |
| `fox-sleep` | P-sleep | `7ed2e6daf6b5d5af` | `41688208a0013eca` | 529,928 | no text | 1 |

Full prompt hashes, provider media URLs, raw-input hashes and generation timestamps are in
`audit/cp010-fox/provenance.json`. Media URLs are the provider's returned URLs; no plate was
re-hosted.

| plate | provider media URL |
|---|---|
| `fox-model-sheet` | `https://v3b.fal.media/files/b/0ab1e43f/xI8gdRiXDTbElHbufPIMq_VkEbNmYP.png` |
| `fox-wave` | `https://v3b.fal.media/files/b/0ab1e459/CTNaUZb4lKDRjdBUYWMiW_451cFOdV.png` |
| `fox-point` | `https://v3b.fal.media/files/b/0ab1e5c3/Y6GjyR4O5N1rY42dz1gRq_OxDrbQpK.png` |
| `fox-clock` | `https://v3b.fal.media/files/b/0ab1e481/El3tQxJOOY2rYSioqiHzK_wdXAuU5A.png` |
| `fox-read` | `https://v3b.fal.media/files/b/0ab1e459/t_6ok0vA-5TXAi5aevYuS_jYsTN8xz.png` |
| `fox-cheer` | `https://v3b.fal.media/files/b/0ab1e45a/yW1WLeVmvSFdCJ8E_0kRA_ZCBZ8rPM.png` |
| `fox-think` | `https://v3b.fal.media/files/b/0ab1e45a/q4rdEPvlgq0csyXkK28rq_QVuAf320.png` |
| `fox-sleep` | `https://v3b.fal.media/files/b/0ab1e45a/JeH-8nGbJk0iu86TLgtLe_2V267dCJ.png` |

Rejected rounds are recorded in `prompts.json` (M1-r1, P-clock-r1, P-point, P-point-r2) with their
hashes and media URLs; their bytes are not shipped. `P-point` — the round-1 plate — was the
quadruped the reviewer rejected: its silhouette measured 669×622, an aspect of 1.076, wider than
tall, which is the signature of a four-legged figure standing on a ground line. The stance guard in
`tests/test_cp010_fox_assets.py` now asserts that every standing plate is taller than it is wide.

## Measured facts

- **Text**: tesseract 5.5.3 default page segmentation returned an empty string for all eight
  plates, and no word of two or more characters at ≥ 70 confidence in the TSV for any of them.
  `--psm 6` (force one uniform text block) does return contour noise on line art; that segmentation
  assumes text exists and is not a text detector, so it is recorded as raw evidence and not used as
  the pass criterion.
- **Contour**: pure black is 0.000 %–0.078 % of opaque pixels per plate; the drawn contour sits in
  the warm-brown family the bible names. 0.078 % is the clock's eye/nose dots, which the bible
  assigns to `#241812`, not the contour.
- **Cutout**: zero semi-transparent pixels and zero pixels within the magenta signature after the
  key. The matte is binary on purpose; a blurred matte is a halo on parchment.
- **Palette drift**: the provider returns a more saturated rust (`#e34c03` measured on the raw
  sheet) than the bible's `#b7643d`. The temper step brings the fur to about `#b14d1e` and the
  cream to about `#e3cb9c`, which is the family the shipped set now shares. The bible's pigment
  table states the intent; this paragraph states the measured outcome.

## Known gaps

1. **No model id in the provenance row.** The host `image_generate` tool returns the media URL and
   nothing else; neither config nor the gateway response names the model. The row says
   `not reported by the host tool` rather than guessing an id. Closing this needs the host to
   return the model name (or an operator to record the configured image model in `hermes config`).
2. **Owner signature is pending, and the order was wrong.** `fox-model-sheet-contact.png` and
   `fox-contact-sheet.png` carry unsigned approval lines, and the poses were generated before the
   sheet was approved — which `ART-BIBLE.md` §7.3 and the card body forbid. The reviewer can verify
   the evidence; the *art* is accepted only when the owner signs the sheet and then the pose sheet.
3. **The sock rule is resolved, and the bible moved to the art, not the reverse.** §3 required dark
   socks "to the elbow" and the M1 prompt asked for them. No plate carries that, including the
   sheet. Measured on the sheet's front view with `scripts/cp010-marking-audit.py` (`marking-audit`
   json beside `vision.json`), the solid dark band is 60–61 px on the arms and 68–70 px on the feet
   against a 607 px figure — 9.9–10.0 % and 11.2–11.5 % of figure height — with the arm band's top
   edge at 65.1–65.7 % of the figure and fur above it. §3 now states that cuff as the rule, per the
   supervisor ruling of 2026-11-10, as reversible amendment `D-CP010-A`. This is a document repair:
   no plate was regenerated and the recorded M1 prompt is untouched.
4. **Point gesture.** Round 3 points down-right at roughly 30°, matching the pose sentence. An
   earlier draft of this document and of `vision.json` said the pointing hand's fingers separate. A
   500 % nearest-neighbour crop of the shipped master refutes that: the paw is a mitten with a
   thumb and a single internal line, which is what the sheet's paws are. The earlier claim was a
   vision read written down as fact; it is corrected in both places. Rounds used: 3 of 3.
5. **Think gesture matches the gesture, not the angle.** The plate raises one paw to the chin with
   the other arm bent across the chest, which is the bible's gesture; the head tilt is slight and
   was never measured against the stated 15°. Recorded as `OI-4` / `D-CP010-B`. Corrected here after
   a reviewer catch: an earlier draft of this document said "both paws clasped below the chin",
   which is not what shipped.
6. **The vision check is now recorded, and it is model judgement with an error rate.**
   `audit/cp010-fox/vision.json` holds one row per shipped plate: stance, markings, colour family,
   lettering and verdict, plus the silhouette numbers from `audit/cp010-fox/shape-audit.json` that
   the geometry claims are cross-checked against. Vision reported a "thin magenta fringe on dark"
   during review; a pixel count refuted it (zero magenta-signature pixels, binary alpha). A vision
   read is evidence, never a verification.
7. **The 45 % head is now a target with a stated band.** §3 gives 45–55 % of standing height, with
   45 % as the design target. The only plate where a silhouette neck pinch is meaningful (`wave`,
   arms down) measures 53.3 % and is inside the band; the other six are not measurable by that
   method and are accepted as-is for this submission. Resolved as reversible amendment `D-CP010-B`
   by the supervisor ruling of 2026-11-10.

## What this document does not claim

- No human illustrator, native-speaker review or professional colour check exists, and none is
  claimed.
- A matching hash is not a rights verdict and not a quality verdict. The plates are model output;
  the provider terms and the repository's licence position for model-generated art apply
  (`docs/ASSET-PROVENANCE.md`).
- Nothing here says the fox reads well at 64 px. That is the contact sheet and the reviewer's eye.
