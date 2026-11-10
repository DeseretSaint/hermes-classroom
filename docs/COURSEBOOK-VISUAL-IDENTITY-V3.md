# Coursebook visual identity v3: Field Atlas

Status: contract proposal for review (CP-002). Read-only with respect to product code.
Date: 2026-11-10. Owner of the direction: DeseretSaint. Maker: `quill`, reviewer: `cbqa`.
Contract: `contracts/cb.tokens.v3.json` (this document explains it; the JSON is authoritative on
every value and every ratio).

This replaces the material bans of Atlas Lamp (`docs/COURSEBOOK-VISUAL-IDENTITY-V2.md`) for v3
surfaces only. It does not replace v2's honesty rules, its one-primary rule, its scoped-token seam
or its evidence vocabulary. v2 tests stay on disk and keep guarding v2 surfaces until CP-003
versions them.

---

## 1. The direction

**Field Atlas.** Coursebook is a field notebook for a place you are learning: a sheet of parchment
on a desk, a deep forest cover, a small brass instrument, a pressed specimen, a route someone has
already walked. The learning is the object on the page. The interface is the desk it sits on.

Three ideas carry it:

1. **A lit paper world.** The route is parchment (`canvas`), cards are cut from a slightly cooler
   card stock (`card-stock`), and one soft vignette darkens the edges. Every object sits *on* the
   paper with a short contact shadow, never floating in glass.
2. **Physical objects, one at a time.** A card is a card. A pill is a button. A wooden plank is
   wood. A medallion is a marked event. Nothing is an abstract box pretending to be an object, and
   nothing is decoration that does not encode something the learner can name.
3. **One warm primary on a quiet field.** Exactly one terracotta fill per surface does the work of
   "do this now". Everything else is paper, ink, a hairline rule, or the forest rail. That contrast
   is what makes the primary unmistakable.

Where the concept images are stronger than the product, v3 copies them: material, warmth, custom
type, a real illustrated world, physical collectibles. Where the concepts are wrong, v3 beats them:
no stars, no invented XP, no garbled labels, no cropped fox, no dead rail, no misaligned grid.

### 1.1 What was measured, not invented

| Thing | Reference | Contract value |
|---|---|---|
| Forest rail | R-SYS / R-DISC sampled `#0a271a`–`#0e281b`; PLAN §2 `#0d281b` | `forest` `#0d281b` |
| Parchment ground | R-HOME `#f3e5d5`, R-DISC `#f6e9d3`, PLAN §2 `#f5e3c8` | `canvas` `#f5e3c8` |
| Card stock | PLAN §2 `#f4ecd9` | `card-stock` `#f4ecd9` |
| Concept CTA | PLAN §2 `#db6c45` (white label 3.36:1, fails; ink label 5.31:1) | see §2 |
| Wood | R-HOME shelf `#957b57` / `#75593a` | `wood` `#a5763f`, `wood-edge` `#7d5529` |
| Scene warm mid | R-CLASS `#eac99f` | `terracotta-quiet` family |

The samples were taken by dominant-colour resampling of the committed reference PNGs. A value is
only in the contract if the contrast test computes it; no ratio in this document is a claim without
a gate behind it in `tests/test_tokens_v3_contract.py`.

---

## 2. The one decision: the primary fill

The concept's `#db6c45` fails as a white-label button (3.36:1). Two legal fixes were offered:

| Option | Label on fill | Fill on parchment | Verdict |
|---|---|---|---|
| A. keep `#db6c45`, put `ink` on it | 5.31:1 | 2.68:1 | label passes; the fill only *just* separates from the paper |
| B. deepen to `#b4532f`, cream label | **4.79:1** (pure white 4.98:1) | **3.96:1** | ships |

Both are drawn on the contract parchment in
`docs/coursebook-visual-identity-v3/cta-choice.png` (rendered by `scripts/cp-tokens-sheet.py`).

**v3 ships option B.** Reason: the primary has to do two jobs, and only B clears both. Its label
reaches the 4.5 text floor, and its fill reaches 3:1 against parchment so the button reads as a
physical object on the page even before you read it. Option A keeps the exact reference hue but
leaves the button visually merged with the paper, which is the failure mode the whole v3 pass
exists to fix. The reference hue is preserved in this document as the measurement it is, not as a
shipped value.

`on-terracotta` is `#fffaf1`, a warm paper white, not pure `#ffffff`; the pure-white figure is
recorded because PLAN.md quotes it.

---

## 3. Roles in plain language

Every colour on a v3 surface is one of these eighteen roles. No raw hex, anywhere, ever. The JSON
carries the full rule for each; this is the readable version.

### Ground and paper

- **`canvas`** — the route ground. Parchment. One per surface, and never a card fill.
- **`canvas-edge`** — the dark edge of the vignette. Text may cross it; it is not a fill.
- **`card-stock`** — a paper card or sheet. It sits on canvas with either `elev-1` **or** a 1px
  `rule`, never both. Card stock is slightly cooler than canvas so a card reads without a border.

### Text

- **`ink`** — reading text and icons. 14.21:1 on parchment, 15.18:1 on card stock. AAA.
- **`ink-soft`** — captions, metadata, secondary labels. 6.00:1 on parchment. Never below 4.5.
- **`rule`** — hairlines, dividers, card outlines, the outline of a quiet pill. Non-text only;
  1.54:1 is enough to see a hairline, and it is never asked to carry a word.

### Forest

- **`forest`** — the left rail and, at narrow widths, the top band. A filled field, never text on
  paper.
- **`on-forest`** — every label and glyph on that rail. 12.50:1.

### The primary

- **`terracotta`** — the fill of the *one* primary action on the surface. Never a text colour,
  never a badge, never a decorative stripe.
- **`on-terracotta`** — the label on that primary.
- **`terracotta-quiet`** — a quiet warm field: a selected row, a tag blank, a soft aside panel. It
  carries `ink` and `ink-soft` text and is the correct place for a second warm surface when one is
  genuinely needed.

### Marks and evidence

- **`gold`** — a rim or a seal: a medallion edge, a completion stamp, a Game-mode XP chip border.
  It is a graphic, never a text background.
- **`sage`** — a soft evidence fill: the recorded-check tally, a progress ground. Also never a text
  background.

### Objects

- **`wood`** — the shelf plank and the evidence tray. Wood is a *prop*. It never becomes a page, a
  card, a panel, a header or a button, and a label never sits on it.
- **`wood-edge`** — the front lip and grain edge that give a wood object thickness.

### Identity and state

- **`plum`** — Parent Studio, and only Parent Studio. Text-safe on canvas at 6.54:1.
- **`alert`** — error and destructive text and icon. Never decoration, never a progress colour.
- **`focus`** — the focus ring, and nothing else. See §6.

---

## 4. Type

Two embedded OFL families, subset to Latin plus punctuation, plus a system CJK stack:

- **`CB Display`** — a Fraunces subset. Headlines and the one display line per surface.
- **`CB UI`** — a Source Sans 3 subset. Everything else, including labels, metadata and body.
- **`cjk`** — `Noto Serif JP`, `Hiragino Mincho ProN`, `Yu Mincho`, `Noto Serif CJK JP`. Japanese
  lesson lines set kana and kanji in this stack and romaji in `CB UI`.

Six steps, no seventh:

| Step | Value | Use |
|---|---|---|
| `caption` | `0.75rem` | the smallest label; never smaller |
| `meta` | `0.875rem` | metadata rows, timestamps, counts |
| `body` | `1rem` | reading text; 50–75ch measure |
| `lead` | `1.25rem` | one-sentence intros and lesson lines |
| `heading` | `clamp(1.5rem, 1.2rem + 1cqi, 2.25rem)` | section headings, ≤34ch |
| `display` | `clamp(2.5rem, 1.5rem + 3cqi, 4rem)` | one per surface, ≤20ch |

**The display step is measured against the route container, not the window.** `cqi` resolves
against `container-name: cb` on `[data-cb-v3]`. At a 460px route the headline shrinks to its floor
instead of overflowing or being clipped; at 1049 it reaches its ceiling. A headless window resize
must not fake this: the container is the only correct input.

Body is `1rem`, so a 200 percent root scales every step. Furigana is deliberately smaller than the
body step; it is a scaffold on a Japanese line, not a seventh authored size.

Fonts load with `font-display: swap`. If a face fails, the system fallback paints and the route
stays legible. A missing font never blanks a route, and a texture that fails to decode falls back
to flat canvas.

---

## 5. Materials, elevation and radii

**Materials.** Three tiles per theme, named so the asset pipeline (CP-004) and the texture card
(CP-011) can match them by id:

| Material | Light tile | Dark tile | Opacity |
|---|---|---|---|
| `grain` | `cb-grain-paper` | `cb-grain-night` | 0.10 / 0.14 |
| `vignette` | `cb-vignette-parchment` | `cb-vignette-night` | 0.55 / 0.65 |
| `wood` | `cb-wood-plank` | `cb-wood-plank-night` | 1.0 |

Rules: grain and vignette are `aria-hidden` and `pointer-events: none`; they sit above the canvas
and below all content. Grain opacity may never exceed the **0.18 ceiling** over a text run — the
ceiling exists because a texture that raises local luminance can quietly break the `ink` ratio the
test just proved. Wood is a tile on the plank and the tray only. All tiles are seamless 3×3 and at
most 60 KB each.

**Elevation.** Three levels, per theme: `elev-1` (a card resting on paper), `elev-2` (a sheet lifted
for a decision), `inset-1` (a pressed or recessed field — tray, input, selected slot).

- Contact shadow, never a glow. A shadow says "this object touches the desk".
- A card uses `elev-1` **or** a `rule` outline. Never both; that is a second border on an object
  that already has one.
- No elevation on text, rules, the rail, the ground or the forest band.

**Radii.** Four, and no fifth: `0` plates and frames, `6px` inputs and chips, `12px` cards and
sheets, `999px` actions only. A pill is never a card; a card is never a pill.

---

## 6. Focus and state

- **Focus ring**: 2px `focus`, 2px offset, solid. It is drawn *outside* the control, on the ground
  the control sits on, which is why every focus gate is measured against a ground: canvas,
  card-stock, canvas-edge, forest, terracotta-quiet. Light `#2a813f` and dark `#f2c56a` each clear
  3:1 on all five (lowest: 3.23 light, 8.96 dark).
- Focus is the one place a cool hue appears in the light theme. That is the job: an indicator that
  is unmistakably not the brand.
- **State is always a word plus a mark.** A selected row has `terracotta-quiet` *and* its label; an
  error has `alert` *and* its sentence. Colour alone never carries a state.
- **Motion**: press 120, lift 150, route 240, verdict 300, complete 600; ceiling 600; no loops.
  `transform` and `opacity` only. Reduced motion removes transitions rather than shortening them,
  and the state change still lands on the next frame.

---

## 7. Dark mode: the night atlas

Dark mode is the same desk under one lamp, not an inverted theme.

- `canvas` `#14110c` warm near-black; `card-stock` `#1e1a13` a lifted paper brown.
- `forest` stays the rail (`#0e2a1c`); the rail is a little lighter than the ground so it still
  reads as a place.
- `terracotta` becomes a lit clay (`#e0794f`) with an `ink` label (5.97:1) — the primary glows on
  the dark page the way the light-mode button sits on parchment.
- `gold` and `sage` stay marks; `plum` lightens to `#cda0d8`; `alert` softens to `#f0a08c`.
- Paper textures switch to their night tiles at slightly higher opacity (grain 0.14).
- Every dark gate is computed in the same test as its light twin; dark is not "close enough".

Anti-goals for night atlas: muddy brown-on-brown, a glow around the primary, grey text that reads
as disabled, or a dark mode that turns the fox and the plates into silhouettes.

---

## 8. Forced colours

`@media (forced-colors: active)` is a supported mode, not an edge case to survive:

- Hide grain, vignette and wood tiles. The ground becomes the system `Canvas`.
- Cards and pills take `border: 1px solid CanvasText`; the primary keeps its border and its label
  uses `CanvasText`/`HighlightText` from the system, not the brand ink.
- The focus ring uses `Highlight` (or `CanvasText` where `Highlight` is invisible).
- Elevation is dropped; a shadow is meaningless in a forced palette.
- No information may be carried by the brand palette alone: state words stay, icons stay, and the
  one primary is still the only filled control in the system palette.
- The route must render with zero images decoded and zero custom fonts loaded — that is the same
  fallback path §4 requires.

---

## 9. What each surface may use

| Surface | Ground | Allowed roles | Notes |
|---|---|---|---|
| Global Home (`home.global`) | canvas + grain + vignette | canvas, card-stock, ink, ink-soft, rule, forest, on-forest, terracotta, on-terracotta, terracotta-quiet, wood, wood-edge, gold, focus | one primary pill; wood only on the shelf plank; fox and tag are DOM-labelled |
| Discover / Workshop | canvas + grain | canvas, card-stock, ink, ink-soft, rule, forest, on-forest, terracotta, on-terracotta, gold, sage, focus | covers are media, not tokens; trust labels sit on card stock |
| Classroom | canvas + section plate | canvas, card-stock, ink, ink-soft, rule, forest, on-forest, terracotta, on-terracotta, terracotta-quiet, sage, gold, focus | one primary = choose the check answer; XP chip only in Game mode |
| Course home | map plate + canvas | canvas, card-stock, ink, ink-soft, rule, terracotta, on-terracotta, terracotta-quiet, gold, focus | nodes are DOM buttons on a plate; the plate never carries labels |
| Component lab | canvas | all roles | a labelled preview of every primitive × state; never presented as a live screen |
| Parent Studio | canvas | canvas, card-stock, ink, ink-soft, rule, plum, focus | plum only here; no game chrome; no terracotta primary competing with the learner's course |
| Evidence tray / print sheet | card-stock | card-stock, ink, ink-soft, rule, sage, wood (tray only) | print and take-home stay paper: no forest rail, no primary fill |

A surface may use a subset; it may never use a colour that is not in this table. A screen with
`forest` and `plum` and `alert` and `terracotta` at once has four jobs on one viewport and is a
palette defect, not richness.

---

## 10. What stays banned

These bans survive the move to v3. They are not softened by the new material language:

- `backdrop-filter`, blur and glass.
- Rainbow or decorative gradients. The **only** gradient is the named vignette, and it is a paper
  edge, not a colour story.
- Raw hex outside the token table. A colour that is not a role does not exist.
- A second identity hue on one screen; a state hue used as decoration; a fill used as a text
  background when the role forbids it.
- Shadow on text, rules, the rail or the ground; shadow as glow.
- Looping, pulsing, shimmering or infinite animation of any kind.
- Wood behind text; gold or sage behind text; a card that is also a pill.
- Stars, ratings, review counts, learner counts, mastery percentages, invented XP, invented counts,
  streaks, and "NEW"/"Life" badges with no backing fact.
- AI text inside art, generated screenshots used as UI, and any screenshot without a CP-000 stamp
  whose plugin sha matches the commit under review.
- A decorative mark that needs an explanation. If a first-time user cannot name it, it is removed.

---

## 11. How this contract is checked

`tests/test_tokens_v3_contract.py` reads only `contracts/cb.tokens.v3.json`:

- schema and required sections; version 3;
- the role list is exactly the eighteen required roles, each with a rule;
- both modes define every role as a six-digit hex, with full light/dark parity;
- elevation has three levels per mode; radii are exactly 0, 6, 12, 999;
- the display step is the pinned container clamp, with no `vw` anywhere in a fluid step;
- two embedded families plus a system CJK stack;
- grain/vignette/wood name a tile and an opacity per theme, and grain respects the ceiling;
- motion beats, no loops, no duration above the ceiling;
- **every gate is computed in both modes and must pass**, text gates at or above 4.5, and
  wood/gold/sage carry no text gate.

Downstream cards own the rest: CP-003 versions the v2 material tests and adds the module-level v3
gates, CP-004 embeds fonts and textures, CP-020a paints the scope and proves the tokens reach the
route. This card proves the contract file; it does not claim a single pixel of product has changed.
