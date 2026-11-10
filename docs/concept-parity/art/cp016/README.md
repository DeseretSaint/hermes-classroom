# CP-016 live world proof

Two topics that are **not** in the demo set, run through the shipping
`coursebook.world` prompt builder (`world.build_style_boards` + `world.build_kit_prompts`)
and the host's own `image_generate` tool. No test double, no re-hosted art.

| Topic | Grammar | Plates | Contact sheet |
|---|---|---|---|
| Bleed a bicycle hydraulic brake (technical) | `workshop_manual` | 3 style boards, hero, cover, 2 sections | `technical-brake-bleed/contact-sheet.png` |
| Fingerpicking patterns for acoustic guitar (creative) | `studio_bench` | 3 style boards, hero, cover, 2 sections | `creative-fingerpicking/contact-sheet.png` |

- Prompt version: `world-prompt-v2`.
- Provider: the host's `image_generate` tool over the managed Nous tool gateway (`fal-queue`).
- Model: `fal-ai/flux-2-pro`. The catalog's fast default (`flux-2/klein/9b`) rendered flat
  vector and pseudo-text on the first pass, so it is not used for this proof. The model is
  recorded per plate; the runtime uses whatever model the profile selects.
- Aspect: the host clamps to `landscape` / `square` / `portrait`; the plate's own ratio (3:2,
  16:9, 4:5, 1:1) is recorded in the prompt and in `provenance.json`, and the contact sheet
  applies the mechanical crop the layout uses. Nothing is stretched.
- Lettering check: CP-010 standard — a word of two or more characters at >= 70 Tesseract
  confidence (psm 11). **Thirteen of fourteen** plates are clean. The section title had reached the
  prompt as prose; it now travels only as a suppression instruction.
- Open lettering residual (not cleared): `technical-brake-bleed/04-hero-authored.png`
  (repair round 1) returns one token, `/‘I_I`, at confidence 75.9 in a 579x73 band at
  `+176+477`. The band is structured painted detail (Canny edge density 0.052 against 0.009 in
  a known quiet field), so it is not a smooth-gradient artefact; the author judged it bench
  texture, not lettering, but the gate did not clear it and no second repair round was spent.
  Reviewer: one crop at that box decides it. If it reads as a glyph it is a textless defect
  and the plate needs one more repair pass.

- Medium/light verification: one vision pass on each final hero and on the repaired section
  frame. Both heroes read as opaque gouache on warm paper with a dark-brown ink contour and an
  upper-left key; no glyphs. Two repair frames are noted in `provenance.json`
  (`repair_round: 1`).
- Known limit: brush work is carried more by paper tooth and ink line than by heavy impasto;
  the reviewer (easel) is the art judge on that dimension.

`provenance.json` per topic carries the brief, grammar, selected style, and for every plate the
full prompt, negative prompt, prompt hash, aspect, provider source (inline data-URL hash), file
sha256, byte count, OCR words and timestamp. `probe/` is a throwaway diagnostic frame and is
not evidence.
