# A1 fox provenance — model sheet and seven poses

Card: CP-010 (`wt/cp-010-fox`). Owner `easel`, reviewer `quill`.
Machine record: `audit/cp010-fox/provenance.json` (written by `scripts/cp010-provenance.py`).
Exact prompts: `audit/cp010-fox/prompts.json`. Style authority: `docs/concept-parity/ART-BIBLE.md`.

Every hash below was printed by that script from the file on disk; no value here is typed from
memory. If a file changes, the script and `tests/test_cp010_fox_assets.py` fail together.

## Verdict up front

Eight plates were generated, keyed and checked: one model sheet (four views) and seven poses.
All eight pass a tesseract text check (no readable lettering), carry no pure-black contour
(≤ 0.078 % of opaque pixels), and are clean cutouts with zero magenta-contaminated pixels. Two
plates were regenerated once each (model sheet round 1, clock round 2). The model sheet has **not**
been signed by the owner yet — the pose set was produced against it so the family could be
reviewed in one pass, and any pose is regenerable from the same sheet if the sheet is rejected.

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
| `fox-point` | P-point | `cb666f33d068b721` | `e0e24d6833f50904` | 349,646 | no text | 1 |
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
| `fox-point` | `https://v3b.fal.media/files/b/0ab1e459/4JMuyVANjyWdwElO1Njf9_LbkEqGQJ.png` |
| `fox-clock` | `https://v3b.fal.media/files/b/0ab1e481/El3tQxJOOY2rYSioqiHzK_wdXAuU5A.png` |
| `fox-read` | `https://v3b.fal.media/files/b/0ab1e459/t_6ok0vA-5TXAi5aevYuS_jYsTN8xz.png` |
| `fox-cheer` | `https://v3b.fal.media/files/b/0ab1e45a/yW1WLeVmvSFdCJ8E_0kRA_ZCBZ8rPM.png` |
| `fox-think` | `https://v3b.fal.media/files/b/0ab1e45a/q4rdEPvlgq0csyXkK28rq_QVuAf320.png` |
| `fox-sleep` | `https://v3b.fal.media/files/b/0ab1e45a/JeH-8nGbJk0iu86TLgtLe_2V267dCJ.png` |

Rejected rounds are recorded in `prompts.json` (M1-r1, P-clock-r1) with their hashes and media
URLs; their bytes are not shipped.

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
2. **Owner signature is pending.** `fox-model-sheet-contact.png` and `fox-contact-sheet.png` carry
   unsigned approval lines. The reviewer can complete the card on the evidence; the *art* is
   approved only when the owner signs.
3. **Point gesture direction.** The generated point reads toward the fox's left. The bible's pose
   sentence asked for lower right. The surface may place or mirror the plate at layout time; a
   mirrored plate must be re-checked against the upper-left light, and no pose was mirrored here.
4. **Sock length is interpretive.** On a chibi figure with short arms, "to the elbow" is roughly
   half the arm. Clock round 2 was regenerated to reach it; the other poses cover the wrist and
   lower forearm without an explicit elbow break. Nothing in the set shows a bare upper-limb
   pattern that would read as a different character at 64 px, but a strict reading of the bible
   would ask for one more round.
5. **Think gesture is both paws, not one.** The plate holds both paws clasped below the chin and
   the head is only slightly tilted. The expression is open-eyed, relaxed and kind — no frown, no
   drooping brow, which is the property that matters for the wrong-answer state — but it does not
   literally match the bible's "one paw at the chin, head tilted 15°".
6. **Vision checks are model judgement, not measurement.** Each plate has a recorded vision
   comparison against the model sheet; that is a second opinion with an error rate, not a
   guarantee.

## What this document does not claim

- No human illustrator, native-speaker review or professional colour check exists, and none is
  claimed.
- A matching hash is not a rights verdict and not a quality verdict. The plates are model output;
  the provider terms and the repository's licence position for model-generated art apply
  (`docs/ASSET-PROVENANCE.md`).
- Nothing here says the fox reads well at 64 px. That is the contact sheet and the reviewer's eye.
