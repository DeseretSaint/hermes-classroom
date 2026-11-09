# GM-013 evidence manifest

Card: GM-013 (visual direction, concept-parity rubric, print/art spec). Branch
`wt/gm-013-visual-spec`. This card ships **design authority and proofs**, not a product screen, so
the evidence is reference material plus a print proof — not UI screenshots.

Machine records: `docs/gm-visual/manifest.json` (boards) and `docs/gm-visual/print/proof.json`
(print). Hashes below are quoted from those two files; the test recomputes them.

## Reference plates

| File | Role | Viewport | Bytes | sha256 (first 16) |
|---|---|---|---|---|
| `docs/gm-visual/boards/japanese-lantern-district.svg` | orientation | 640×360 | 2232 | `05eb83c0d820914f` |
| `docs/gm-visual/boards/head-gasket-service-bay.svg` | orientation | 640×360 | 2372 | `87f7cfb069f345d3` |
| `docs/gm-visual/boards/astronomy-observatory.svg` | orientation | 640×360 | 2483 | `2670d8a2539b4e10` |
| `docs/gm-visual/boards/sourdough-kitchen-table.svg` | orientation | 640×360 | 1815 | `2e489b92bdb1eee3` |
| `docs/gm-visual/boards/anti-generic-swap.svg` | review instrument (labels allowed) | 640×430 | 2885 | `f80714e03fde69ea` |

Contact sheet for review: `docs/gm-visual/boards/contact-sheet.html` and `.png` (a rendering of the
five plates with captions; the captions are outside the plates).

Annotated composition diagram: `docs/gm-visual/diagrams/home-composition.svg` and `.png` — the Home
bands, shelf geometry and forbidden elements drawn 1:1 at a 1440 viewport. It is a diagram, so it
carries labels; the label rule applies to plates, not to review instruments.

## Print proof

| File | Page box | Pages | Sha256 (first 16) |
|---|---|---|---|
| `docs/gm-visual/print/pack-specimen-a4.pdf` | 594.96 × 841.92 pt (A4) | 5 | `9d58dd5d4c17f101` |
| `docs/gm-visual/print/pack-specimen-letter.pdf` | 612 × 792 pt (Letter) | 5 | `a8c5970b6b9bad50` |

Page renders at 110 dpi: `docs/gm-visual/print/page-1.png` … `page-5.png`.
Source: `docs/gm-visual/print/pack-specimen-a4.html` (sha256 `f20d3d41696e84af`), which also carries
the print stylesheet in its `<style>` block. Each page is printed from its own single-sheet HTML and
the five are merged with `qpdf`: Chromium's print flow carried a following sheet's 24 pt label into the
previous sheet's bottom margin (measured at y = 785 of 842 pt, outside the 18 mm margin), so the
builder removes the cross-page flow instead of fighting the break property.

Answer-key check: sentinel `⟨answer-key⟩` occurs on **page 3 only**, in both builds
(`proof.json.answer_key_separated = true`). Page 2 (learner page) carries no answer, no expected
response and no score line.

## What was actually run

```
python3 scripts/build_gm_visual_assets.py      # 5 SVGs + manifest.json
python3 scripts/build_gm_print_proof.py        # A4 + Letter PDFs, 5 PNGs, proof.json
chromium --headless --screenshot=…contact-sheet.png …
python3 -m unittest tests.test_gm_visual_spec tests.test_gm_print_spec
```

## Known gaps

- The four plates are **reference boards**, not approved course art. GM-004 renders its own plates
  and must carry its own provenance rows.
- The specimen PDF is not a tagged PDF; PDF/UA is not claimed. Tagged export is GM-014's proof.
- The concept-parity rubric has been applied in this card to reference material only
  (`SCORECARD.md`); no product screen exists yet to score.
