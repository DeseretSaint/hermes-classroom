# GM subject-world reference board

Card: GM-013. Design authority for GM-003 (WorldPolicy, prompts, media job), GM-004 (World Studio)
and GM-016 (final parity). Bound by `docs/GM-VISUAL-SPEC.md` §8 and the plan's §4.3 subject
grammars.

Four worlds are specified here. They are the acceptance matrix's first four rows, not a catalogue:
a course that is none of them gets a grammar from the plan's table, and the same rules apply.

Boards live in `docs/gm-visual/boards/`; `docs/gm-visual/manifest.json` records their hashes,
provenance and the "no text" rule. Open `docs/gm-visual/boards/contact-sheet.html` to see all five
in one frame.

**Every plate in this document is host-composed, textless, flat, and orientation only.** No plate
is a procedure, a measurement, a safety instruction or a sourced figure.

---

## 0. The kit, per course

| Role | Master size | Crop shown on | Rule |
|---|---|---|---|
| `world_hero` | 1024×576 (16:9) | course home | type sits **below** the plate, never inside it |
| `world_cover` | 1024×576 → 864×576 (3:2) centre crop | library/shelf card, pack | one mechanical crop, never a second drawing |
| `world_section` | 640×480 (4:3) | section card, up to 6 | may reuse a hero motif at a different scale; must not be a duplicate of the hero |
| `lesson_scene` | 864×576 (3:2), optional | lesson header, at most 2 | place only; never instructional media |

Sizes match the shipped cover masters (`1024×576` master, `864×576` 3:2 crop) so the same pipeline
and cache key can carry a world plate.

**Allowed tokens in a plate: `paper`, `paper-raised`, `ink`, `ink-soft`, `rule`, `lamp`,
`lamp-soft`, plus at most one subject accent (`accent` *or* `field`).** `ochre`, `coral` and `plum`
are forbidden in art: they are due/attention/parent-identity hues, and a plate must never look like
a state. No gradients, no shadows, no glow, no grain, no watermark.

---

## 1. Japanese L0 — lantern district / cafe lesson

**Board:** `docs/gm-visual/boards/japanese-lantern-district.svg`
**Grammar:** `field_atlas` (lantern variant) · **domain:** language · **level:** L0 · **safety:** none
**Subject accent:** `lamp` only (lantern light)

| Motif | What it encodes | Must never become |
|---|---|---|
| Paper lantern: capsule body, ink cap, one horizontal rib | the district the lesson is set in; the course's place | a Japan-only skin for a non-language course; a source of kanji-like marks |
| Cafe counter edge with two stools | the lesson's actual situation (ordering) | a generic "restaurant" stock scene |
| Noren doorway panel with three slits | threshold/entering — the L0 social frame | a text-bearing shop sign (no shop names, no kana in art) |
| Cup with steam curls | the target act (ordering a drink) | a product shot or a menu |

**Composition.** Hero at 16:9: street ground on the lower third, lanterns on the upper left, noren
on the right, at least 35% quiet `paper` in the upper-right for the course title block that sits
*below* the plate. Cover uses the left two lanterns and the counter edge; the 3:2 crop must keep at
least one lantern and the counter.

**Anti-generic swap check.** Swap the *caption* to *head gasket*: the plate must become unacceptable.
A lantern + noren + steam plate cannot serve a service bay, so the swap is `rejected` and the plate
is doing real subject work. A reviewer rejects any plate where only the palette survives a swap — and
equally rejects a plate that keeps reading as Japanese when the course is not Japanese, because then
the motifs were decoration, not subject. The head-gasket board may not use a lantern, a noren, a
hanging cord or a warm street ground: those four marks are reserved to this world.

**Forbidden:** invented Japanese text, shop signs, menu boards, prices, "authentic" seals with
glyphs, geisha/temple/torii clichés not present in the lesson, any claim that the art depicts the
learner's own city.

---

## 2. Head gasket — service bay / workshop manual

**Board:** `docs/gm-visual/boards/head-gasket-service-bay.svg`
**Grammar:** `workshop_manual` · **domain:** technical_procedure · **level:** novice · **safety:** workshop
**Subject accent:** none (ink + `lamp-soft` only)

| Motif | What it encodes | Must never become |
|---|---|---|
| Two-post lift, crossbeam, vehicle on the lift | the workshop as a place and the object of work | a branded car; a specific make/model claim |
| Tool wall with wrench silhouettes | the trade and the tool list | a tool count, a part number, a brand logo |
| Component tray with a gasket ring | the part being replaced | a torque sequence, a bolt pattern with numbers, a clearance |
| Open shop manual, blank pages, ink spine | procedure lives in text; the manual is the authority | readable procedure text, a page of steps, a table of values |

**Composition.** Hero at 16:9: lift and vehicle occupy the left two thirds, tool wall upper right,
tray and manual on the bench along the bottom edge. The upper third stays quiet for the title block
that sits below the plate. Cover: vehicle silhouette plus tool wall; the gasket ring must be legible
at 240px.

**Anti-generic swap check.** Swap to *sourdough*: a vehicle on a lift cannot pass as a kitchen table,
and a dough dome cannot pass as a wheel. A plate that keeps only "warm flat shapes" after the swap is
rejected. Separately, **no lantern, no map, no compass, no parchment street** may appear: the
generic atlas is banned for a technical course.

**Forbidden:** torque values, bolt numbers, clearances, "official service manual" labels, safety
pictograms invented by the image model, hands doing a procedure, a depicted completion. The
procedure renders as numbered text steps, tool/part lists, hazards and a stop condition; the
sequence and part orientation are deterministic SVG from structured facts or a sourced figure with
permission.

---

## 3. Astronomy — observatory

**Board:** `docs/gm-visual/boards/astronomy-observatory.svg`
**Grammar:** `observatory` · **domain:** natural_science · **level:** novice · **safety:** none
**Subject accent:** `accent` (night field) — the one blue band

| Motif | What it encodes | Must never become |
|---|---|---|
| Dome slit and telescope on a pier | the observing site and instrument | a specific observatory or telescope brand |
| Plotted star-chart grid with dots and one circle mark | the practice of recording positions | a real sky, a constellation figure, a coordinate readout, a magnitude |
| Horizon line | orientation (up/level/ground) | a landscape, a skyline, a "journey" metaphor |

**Composition.** Hero at 16:9: `accent` night band across the top ~42% with a hard edge, dome and
telescope on the left, chart panel lower right, paper ground elsewhere. Cover: chart panel plus one
dome arc. 4:3 section cards may use the chart grid alone at a different density.

**Anti-generic swap check.** Swap to *head gasket*: a plotted grid with a circle must not read as a
bolt pattern, and a dome must not read as a wheel arch. If a reviewer can swap the caption without
noticing, the plate fails. **The AI sky image is never a measurement source**: charts, magnitudes and
coordinates come from lesson facts, deterministic SVG or a cited catalogue.

**Forbidden:** constellations drawn as animals or figures, axis labels, ticks with numbers, "NASA"
or any institution mark, a photograph-like sky used as data.

---

## 4. Sourdough — kitchen table

**Board:** `docs/gm-visual/boards/sourdough-kitchen-table.svg`
**Grammar:** `kitchen_table` · **domain:** cooking/home_skill · **level:** novice · **safety:** food
**Subject accent:** `field` (one herb-green band, optional)

| Motif | What it encodes | Must never become |
|---|---|---|
| Coiled banneton with three concentric arcs | the shaping stage and the tool | a basket brand, a "handmade" seal |
| Scored dough dome with three slashes | the target outcome of shaping | a baked loaf presented as the tested recipe result |
| Bench scraper, linen fold, stoneware jars | the bench and its scale | a styled product still life with labels |

**Composition.** Hero at 16:9: `lamp-soft` table plane across the lower 45% with a hard ink edge,
banneton left, dough centre, scraper and jars right, linen folded between. Cover: dough dome plus
banneton arc. At 240px the scoring slashes must still read.

**Anti-generic swap check.** Swap to *Japanese L0*: a dough dome must not read as a lantern and a
bench scraper must not read as a noren. A kitchen plate that still works as a "warm cafe" plate is
rejected. **No generated dish is a tested recipe**: temperatures, timings, hydration and flour
ratios are lesson text with sources, never art.

**Forbidden:** any number, timer, scale readout, oven dial, recipe card with text, "artisan" badge,
a finished loaf implying the recipe was tested.

---

## 5. The mechanical policy (what GM-003 must implement)

The board is evidence that a deterministic selector can produce these four and reject the swaps. The
selector is pure and testable:

```
world_brief(subject_domain, evidence_target, safety_class, motifs[], title)
  -> grammar  (from the plan's §4.3 table; unknown -> field_atlas)
  -> palette_path (one subject accent or none; state hues never)
  -> motif_contract (>= 2 motifs from plan/sources; each with a "must never become")
  -> hard_negatives (text, letters, digits, logos, UI chrome, watermark,
                     invented measurements, depicted procedure, false ratings)
  -> roles (hero 16:9, cover 16:9->3:2, section 4:3 x<=6, scene 3:2 x<=2)
```

Acceptance for GM-003: for each row above, the selector returns the named grammar, the motif set
contains at least two of that world's motifs, and `swap_test(brief, unrelated_subject)` returns
`rejected` with the reason "grammar and motifs unchanged". A prose prompt that merely asks the model
nicely is not this policy.

**Anti-generic swap test, both directions.** For every pair of worlds in this document, swapping the
subject must change the grammar **and** at least two motifs. The test is symmetric: it also proves
the Japanese world does not steal the workshop's marks.

**One-default rule.** `field_atlas` is the fallback for an unknown subject. It is a starting point,
not permission: the fallback may not be used for `technical_procedure`, `natural_science`,
`cooking` or `mathematics`, where the grammar is mandatory.
