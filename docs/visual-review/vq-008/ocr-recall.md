# OCR recall behind `ocr_policy.limitation` (VQ-008 round 3)

The seven kit manifests carry `ocr_policy` verbatim from `OCR_POLICY` in `scripts/vq008-kits.py`,
and `--check` refuses a kit whose policy drifts. The limitation sentence states what the detector
actually misses, because a clean OCR run is **not** evidence that a plate is textless.

## Method

Liberation Sans Bold text burned onto the shipped `lab_bench` hero
(`assets/visual-kits/lab_bench/hero/lab-bench.png`, 1344x768) at `+120+300`, then the kit's own
`ocr_tokens()` (`scripts/vq002-kit-audit.py`) — tesseract TSV, default page segmentation, readable
= token of >= 3 alphanumeric characters at confidence >= 60.

```
magick assets/visual-kits/lab_bench/hero/lab-bench.png \
  -font Liberation-Sans-Bold -pointsize <pt> -fill black \
  -annotate +120+300 "<text>" burn-<pt>.png
tesseract burn-<pt>.png stdout tsv            # then the kit's readable-token rule
```

## Measured (2026-11-11, this branch)

| burned text | psm 3 (default) | psm 6 | psm 11 | psm 12 |
|---|---|---|---|---|
| 120 pt `TORQUE 45 Nm` | no tokens at all | none | none | none |
| 120 pt `CAUTION` | `i` @ 32.1 | `i` @ 32.1 | `i` @ 32.1 | `i` @ 32.1 |
| 72 pt `TORQUE 45 Nm` | `7` @ 82.3, `4` @ 59.4, `U` @ 51.2, `S~` @ 42.1 | same | same | same |
| 48 pt `TORQUE 45 Nm` | no tokens | none | none | none |
| 32 pt `TORQUE 45 Nm` | no tokens | none | none | none |
| no burn (shipped plate) | no readable token | — | — | — |

No cell produces a readable token: the 120 pt line is plainly legible to a human and scores zero,
and the 72 pt fragments are single characters below the 3-character floor. An independent review
probe at 72 pt recovered one three-character fragment (`RQU` @ 90.9), which is why the sentence
says recall does not rise with type size rather than "large type always scores zero".

## Consequence recorded in the manifests

The primary textless control is the recorded per-plate vision pass, not OCR:

- every accepted row in `generation.json` carries a `vision` and a `residual` verdict, and
  `--check` refuses an accepted row without either;
- `hero`, the 3:2 cover, `section` and `lesson_scene` must each have an accepted row behind the
  plate they mount.

Detector hardening is carded separately (`t_585209d8`, cinder); this record only fixes the claim
the manifests make about the detector's recall.
