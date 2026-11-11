# Adversarial review — can native-image DeepSeek plus Opus direction produce the studio UI?

## Verdict

For **layout and code**, yes. DeepSeek V4.1 Flash is a strong coding model and its vision is good
enough to read a spec, a diff and a crop. With Opus writing exact boxes, tokens, assets and states,
it can build the screens.

For **the art**, the question is already settled: the owner has approved the painted A1 fox, and the
660 px masters with 512/256/128/64 exports are in `assets/art/fox/` on master (CP-010). The art is
not missing and does not need another generation pass. The live product is simply still wired to the
procedural SVG placeholder: `scripts/build_cb_assets.py` encodes `assets/fox/*.webp` from
`assets/masters/fox/*.svg`, `cb3FoxSource` caps at 128, and Home asks for 128/112 while the reference
renders the painted fox at 208. That is the entire visual gap, and it is a one-card wiring fix.

So the quality ceiling is now **asset adoption**, then spec, then QA, then model choice. Not art.

## Evidence

- The approved references: `docs/concept-parity/art/fox-signoff-2up.png` (M1 + A1 seven poses) and
  `docs/concept-parity/art/home-reference.png`. The owner's 2026-11-10 message makes the painted A1
  set canonical.
- Canonical assets: `assets/art/fox/fox-<pose>.png` (660×660 RGBA) and the 512/256/128/64 exports.
  `git merge-base --is-ancestor 68da9251 master` returns 0; CP-010 is merged.
- Live path: `scripts/build_cb_assets.py:255,655-705` reads the SVG masters; `assets/fox/manifest.json`
  names `authored:assets/masters/fox/*.svg`; `desktop/cb-assets.generated.js:58,70` ships 128/64 WebP;
  `desktop/src/85-v3-primitives.js:73-80` caps at 128; `desktop/src/30-home.js:870,944` asks for
  128/112. The painted 512 is never requested.
- The 2-up `docs/concept-parity/art/fox-canonical-vs-live-2up.png` shows the difference: same pose,
  painted character on the left, flat procedural derivative on the right.
- DeepSeek V4.1 Flash is multimodal, but its vision caps an image at 1,024 tokens and its base
  MMMU-Pro is 56.5. It reads layout; it is not the art judge. The art is fixed, so that is acceptable
  for the build lane.
- The board's gates (CP-053, GM-016) measure tokens, geometry, capture and presence. They do not
  assert the fox's source or hash. A green board can still ship the placeholder.

## Findings against the plan

**1. The prompt's asset canon is inverted (fatal).** It calls the shipped fox sprites canonical and
calls the concept differences accepted divergences. The truth is the reverse: the A1 painted set is
canonical; `assets/fox/*.webp` and `assets/masters/fox/*.svg` are the placeholder. If this stands,
the writer will faithfully build around the wrong fox and call it parity.

**2. CP-020a's done stamp missed the fox source.** The card is done for scope, fonts and materials,
but the README still says wiring the painted fox is CP-020a's job, and the builder still reads SVG.
The gate measured the card's scope, not the segment's source. Fix: a source/hash test, not another
visual score.

**3. `FoxPose` caps at 128.** Even a perfect registry would still render 128 because
`cb3FoxSource` maps everything ≥128 to 128. Home's 208 reference is displayed at 112–128. This is why
the mascot looks small and soft, independent of the art.

**4. Presence checks pass the placeholder.** "A fox is present" is true of the flat SVG. The
acceptance list must require the painted source, natural size ≥ rendered, and the A1 feature check.

**5. The owner sign-off is already given; do not build an art-lock phase.** The A1 sheet is
approved. A plan that asks for another model sheet, pose generation or owner contact sheet wastes the
critical path and re-opens a closed decision.

**6. The pose map is now explicit.** `wave` Home trailhead, `point` Discover, `clock` Home/New
course, `read` Classroom, `cheer` correct, `think` wrong answer, `sleep` empty/offline. One pose per
surface, no repeat in a viewport, state-driven crossfade only; loops remain forbidden by the motion
tokens.

**7. The Home mockup's sitting fox is not the `clock` pose.** The mockup shows a sitting fox beside a
mantel clock; the A1 `clock` pose is standing with a pocket watch, and the sheet labels it for
Home/New course. Use the approved `clock` pose at 208 on the ledge and `wave` on the empty shelf. If
the owner later wants the exact sitting composition, that is a scene plate, not a UI asset; do not
invent a pose in the UI.

**8. Native vision is a layout tool, not an art judge.** DeepSeek sees thumbnails; review crops.
Opus can judge the crop against A1, but the character decision is closed. Do not let the writer
certify its own asset.

**9. The board needs a source gate.** Add to the Home/visual gate: the rendered fox's `currentSrc`
must resolve to a painted derivative under `assets/fox/` whose `source` is `assets/art/fox/...png`,
and no `assets/masters/fox` path may be reachable for the seven poses. A green CP-053 without that
is not a visual pass.

**10. The deadline is now feasible.** It is 23:55; CP-053's checkpoint is 03:00. Adoption is a build
+ registry + primitive + test change, not hours of art generation. If the adoption card lands first,
Home can ship with the correct fox; if it does not, Home drops rather than shipping the placeholder.

## Revised one-shot plan

**Phase A — Asset adoption (one card, first).**
A1. Switch the fox branch in `scripts/build_cb_assets.py` to `assets/art/fox/fox-<pose>.png` as the
master; encode 512/256/128/64 WebP/AVIF with alpha.
A2. Regenerate `assets/fox/manifest.json`, `desktop/cb-assets.generated.js`, `desktop/plugin.js`;
every fox `source` is the painted PNG, no SVG source.
A3. Lift `cb3FoxSource` to 512/256/128/64 with a 1x/2x `srcSet`; `FoxPose` accepts 208/512; Home
renders the `clock` pose at 208 and `wave` at 208 on the empty shelf.
A4. Add the source/hash/`currentSrc` test; no UI parity claim before it passes.

**Phase B — UI implementation (writer: DeepSeek; director: Opus).**
B1. Opus writes the exact spec: boxes, tokens, assets, states, pose per surface.
B2. DeepSeek implements; DOM geometry audit ±2 px; computed styles; gates; axe.
B3. Crop-level review; pose-map compliance; no CSS drawings; no upscaling; no repeats.
B4. Land each screen with the installed-build capture.

**Phase C — Quality gate.**
C1. Critical dimensions: character, typography, material; below 4 fails, no averaging.
C2. Character checklist against A1; asset hash; natural size; crop comparison; `currentSrc` source.
C3. Owner sees one final contact sheet; the character itself is already approved.

## The narrow answer

DeepSeek with native images plus Opus direction is sufficient for the build, and the art is already
approved and in the repo. The one-shot plan is realistic **once the painted fox is wired into the
segment and `FoxPose` stops capping at 128**. Without that adoption, the output will be a clean
layout around the flat placeholder — exactly the disappointment the owner has been seeing, and no
amount of model power will fix it.
