# M4 procedure layout — evidence frames

Static render of the shipped `desktop/plugin.js` procedure lens in headless Chromium, driven by
`scripts/m4p-frames.py` + `scripts/m4p-shot.mjs`. The fixture is the validated head-gasket
lesson document from `tests/test_procedure_document.py`.

| frame | mode | width | text | motion |
|---|---|---|---|---|
| 01-light-wide | light | 1280 | 100% | full |
| 02-dark-wide | dark | 1280 | 100% | full |
| 03-light-460 | light | 460 | 100% | full |
| 04-dark-460 | dark | 460 | 100% | full |
| 05-dark-200pct | dark | 1280 | 200% | full |
| 06-dark-460-200pct | dark | 460 | 200% | full |
| 07-light-reduced-motion | light | 1280 | 100% | reduced |

`evidence.json` records the painted token values, step count, schematic rows, the hazard
callout's role and colour, the single verification node, and horizontal overflow for each frame.

Not a live-app capture: no backend, no RPC and no artifact bytes. The schematic's SVG preview
therefore shows "Loading media"; the typed rows are the authority and are fully painted.
