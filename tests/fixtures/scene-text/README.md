# `tests/fixtures/scene-text/`

Assets for **CP-TEXT-GATE** (`tests/test_desktop_scene_text_containment.py`): the measurement of
whether every text run in the wide Home scene sits inside the object it is painted on. The gate,
the metric contract and the evidence are in `docs/concept-parity/CP-TEXT-GATE.md`.

| file | role |
| --- | --- |
| `measure.mjs` | Chromium/CDP driver. Photographs a page once with all lettering, then once per run with only that run's glyph paint killed (`color: transparent`), and reports each object's corner quad, each run's text rects and its scroll overflow. Built-in Node modules only; no `npm install`. |
| `scene.units.json` | The runs the gate measures in the shipped scene: object selector, run selectors (`""` = the object's own text) and whether the object centres its type. |
| `overhanging.html` | The deliberate defect: two rotated boards, one with a centred label inside it (`#board-pass`, the control) and one whose label is wider and taller than the board (`#board-fail`). No `overflow: hidden`, so the pixels show the spill. |
| `overhanging.units.json` | Units for that fixture, in the same schema as `scene.units.json`. |
| `legibility-exceptions.json` | The five runs the LEG-01 audit still lists under the 11 px cap floor, one entry per run: the widths, why the object cannot absorb an 11 px cap, and the probe's measured clip px. `tests/test_desktop_home_legibility_pins.py` requires its run ids to equal the audit's `summary.runs_under_cap_floor` exactly, so a new under-floor run cannot pass by quoting an old exception. |

Unit schema:

```json
{"name": "unique-unit-name", "object": "css selector", "centre": true, "runs": ["css selector", ""]}
```

- `object` — the box the lettering is painted on; its four corners define the local frame in which
  margins and spill are measured (a rotated object is measured in its own frame).
- `runs` — selectors resolved *inside* the object. `""` means the object element's own text node.
- `centre` — `true` only when the object's CSS centres the type (the evidence reports centring
  margins for every unit but asserts them only here). See §3 of the doc.

Usage:

```bash
node tests/fixtures/scene-text/measure.mjs <page.html> '<units-json>' <out-dir>
```

It prints one JSON object: the units it resolved (object quad, run rects, computed alignment, scroll
overflow) plus the `base.png` and `without-<n>.png` paths it wrote. The Python side turns that into
the metric rows; the mask, homography and limits live in the test module so the fixture stays
data-only.
