# Component lab — evidence for CP-020b

These files are the product version of R-SYS (`docs/concept-parity/refs/system.png`): every Field
Atlas v3 primitive, in every state, at the values the token contract ships.

**They are component previews, not live Desktop captures.** There is no host, no backend, no chat
and no `[data-cb-v3-ready]` settle marker on a lab cell. Live evidence for a screen is
`scripts/cp-capture.mjs` only, with its own stamp.

| File | What it is |
|---|---|
| `contact-sheet.png` | Owner checkpoint: light/dark × 100 %/200 % text, each cell captioned |
| `anatomy-vs-rsys.png` | The card anatomy (SPEC-V3 §5.5 S6) from the shipped primitives, beside the same region of R-SYS |
| `lab-<mode>-<cell>.png` | One full-page cell at route width 1049, device scale 2 |
| `lab.json` | The stamp index: plugin sha256, per-cell geometry, media posture, page and png hashes |

Cells: `light-100`, `dark-100`, `light-200`, `dark-200`, `light-reduced-motion` (emulated
`prefers-reduced-motion: reduce`), `dark-forced-colors` (emulated `forced-colors: active`).

## Regenerate

```bash
python3 scripts/cp-lab-frames.py                  # render every cell, then both sheets
python3 scripts/cp-lab-frames.py --contact-only    # rebuild the sheets from committed cells
```

The script refuses to compose sheets from cells whose plugin sha differs from the checkout's
`desktop/plugin.js`, so a stale frame cannot be filed as this commit's evidence.

## What the sheet is checked for

`tests/test_v3_primitives.py` asserts the same claims on the module: one filled control per surface
(and none on the lab), four real-button stamp states, a fox that is `aria-hidden` and absent below a
620 px route, a card with no ratings or invented progress, ruby plus romaji on the lesson line, and
`var(--cb3-*)` as the only paint. The frames show what those assertions cannot: that the shipped
stylesheet, the embedded faces and the painted objects actually render.
