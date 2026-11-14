# probes/legibility-2026-11 — cap height and contrast for every Home scene text run

Owner: `cbqa` (Sentinel). Result document: `docs/concept-parity/text-legibility-2026-11.json`.
Measured tree: `wt/t_6fc6a7bd` **abdbdc9d** (`desktop/plugin.js` sha256 `6129271b…68ad`, `design/home-scene.html`
sha256 `68e75fa6…8ddf`). The audit's original basis was `origin/master` **b7ed6cf0** (module `098e65d9…bd47`);
`subject.measured_files_identical_to_base` stays `false` because the module has moved since that tree, and
`subject.measured_against` in the document still names b7ed6cf0 as that basis — the run's own tree is
`subject.worktree_head`.

This probe answers two questions the CP-TEXT-GATE does not: how tall is each run's capital in
rendered pixels, and what colour is actually behind its glyphs. It reuses CP-TEXT-GATE's page,
unit inventory (`tests/fixtures/scene-text/scene.units.json`) and photographic method — the scene
is captured with a run's glyph paint killed (`color: transparent`) so backgrounds and boxes never
move — and adds:

* **cap probe** — while the run's own glyphs are transparent, one capital `H` in the run's computed
  font is painted as an absolutely positioned child at the run's own text-rect origin. An absolute
  child cannot reflow the scene, which a `textContent` swap does (it narrowed the hero panel and
  moved a card body, inflating the "cap" to a whole line box). Placement is solved through the
  element's local→viewport linear map, so a scaled (1200 px fit) or rotated (cards, tag) object is
  handled; the residual is recorded per run and was ≤ 0.02 px. The number reported is the face's
  cap ratio measured at 200 px (Chromium rounds `actualBoundingBox*` to whole px at small sizes)
  times the run's rendered font size, corroborated by the `H`'s pixel span at ≥ 50 % coverage.
* **contrast** — the run's declared colour, composited over the pixels of the glyph-less capture at
  the run's ink mask (glyph-core pixels, coverage ≥ 85 %), against WCAG 2.x relative luminance.
  `min` is the worst pixel behind a glyph, which is the honest measure of a text run over art.
* **floor-raise probe** — for each run under the 11 px cap floor, the run is set to the font size
  that would give it an 11 px cap (same face, same line-height ratio) and the page is re-measured:
  does the object absorb it, or does something clip? That is what decides "the object can grow"
  versus "the run must shorten".

## Run it

```sh
work=$(mktemp -d)
python3 scripts/gen-home-proof.py --width 1344 --height 768 --out "$work/pages/home-1344.html"
python3 scripts/gen-home-proof.py --width 1200 --height 768 --out "$work/pages/home-1200.html"
units="$(cat tests/fixtures/scene-text/scene.units.json)"
node probes/legibility-2026-11/measure.mjs "$work/pages/home-1344.html" "$units" "$work/run-1344" 1344 > "$work/run-1344.json"
node probes/legibility-2026-11/measure.mjs "$work/pages/home-1200.html" "$units" "$work/run-1200" 1200 > "$work/run-1200.json"
cp "$work/run-1344.json" "$work/run-1344/result.json"
cp "$work/run-1200.json" "$work/run-1200/result.json"
python3 probes/legibility-2026-11/analyse.py . "$work/run-1344" "$work/run-1200" docs/concept-parity/text-legibility-2026-11.json "$work/pages/home-1344.html" "$work/pages/home-1200.html"
```

`measure.mjs` prints its capture JSON to stdout; `analyse.py` reads it from `<dir>/result.json`, which is
why the two `cp` lines are part of the run. The two trailing page arguments are optional: pass them and
`subject.page_1344_sha256` / `page_1200_sha256` name the pages this run measured; omit them and the 1200
hash is `null` and the 1344 hash falls back to the committed `design/home-scene.html`.

`measure.mjs` writes its PNGs into the directory given as the third
argument (`base.png`, `base-again.png`, one `without-<n>.png` and `cap-<n>.png` per run,
`raised-<n>.png` for runs under the floor, and `restored.png`). Requirements: `node`, `chromium`,
`numpy`, `Pillow`, and React/React-DOM installed beside the desktop app (what `scripts/gen-home-proof.py`
already requires).

## Limits

* Cap height is a face metric, not per-glyph: a run whose letters are all lowercase still reports the
  face's cap height, because the floor is about the type size, not which letters happen to appear.
* Contrast is measured against the pixels behind the run as shipped. It cannot tell a dark shadow
  painted on the object from a dark object behind a transparent part of it — both are the same thing
  to a reader looking at that pixel.
* The 1200 px capture is the authored 1344 px plate transform-scaled by 1200/1344, which is what the
  product does (`--cb-home-scene-scale`); narrower Homes (the compact shelf) are out of scope.
* The floor-raise probe changes `font-size` and `line-height` only. A real fix may also re-flow
  cover art, change the shelf's geometry, or shorten copy; the probe measures whether the current
  object can hold the floor size, not which of those fixes is right.
