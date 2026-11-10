# RUBRIC-V3 — the concept-parity scoring instrument for v3 screens

Card: CP-028. Scored by `atlas` at GM-016 and by the reviewer of each v3 screen card
(CP-020b, CP-021, CP-022, CP-023, CP-024).

This file does not introduce a standard. It is a **measurement layer** over
`docs/GM-CONCEPT-PARITY-RUBRIC.md` §7 and `docs/concept-parity/SPEC-V3.md`: every line below
resolves to a value in `contracts/cb.tokens.v3.json`, a box in SPEC §5, or a cell in
`docs/visual-review/matrix.json`. If a line cannot be measured on the submitted captures, it is not
scored — the submission is refused (rubric §6) rather than graded by impression.

Read order before scoring: SPEC-V3 §2 (measured anchors), §3 (shared system), §5 (the screen),
§6 (honesty table); then this file; then the captures and their `.stamp.json` siblings.

---

## 0. Pass rule (unchanged, restated so it cannot drift)

- Ten dimensions, each scored 1–5. **Every dimension ≥ 4.**
- All five composition anchors present (§3 below). Anchors are binary per screen.
- No auto-fail present (§4 below).
- A single 3 is `request-changes`. Three loops maximum; the fourth escalates to `atlas`, who splits
  the screen rather than lowering a threshold.
- The score is of the artifact. No score is raised after a verbal explanation, and no dimension is
  waived because "the backend limits it" (rubric §6).
- The reviewer writes `remaining differences even on pass`. "Close enough" is not a verdict.

---

## 1. Evidence the reviewer is scoring (refusal conditions)

A submission is refused, not scored, when any of these fails:

| # | Condition | How it is checked |
|---|---|---|
| E1 | The capture came from `scripts/cp-capture.mjs` and has a sibling `.stamp.json` with `ok: true` | file pair exists; `jq -e '.ok == true' <capture>.stamp.json` |
| E2 | The stamp's plugin sha equals the commit under review | `git show <commit>:desktop/plugin.js \| sha256sum` vs stamp `plugin.window_sha256`; the reviewer also re-captures **three** cells live from that commit (rubric §7.4) |
| E3 | Every cell in `matrix.json` for that screen id exists, with the cell's viewport, mode, text scale and state | compare the screen's `cells[]` list against the capture filenames; one missing cell = refused |
| E4 | The frame is route-only, not the whole host window | stamp `crop_mode == "route"` (or `"content"` with the overlay geometry recorded) and stamp `clip.width` ≈ the requested route width |
| E5 | The concept comparison exists as a board produced by §2 of `BOARD-TEMPLATE.md` | board PNG present, equal width, both sides from the named refs crop |

A frame whose stamp sha differs from the commit is refused outright (rubric §7.4). A generated
image, a mockup, an upscaled capture or a screenshot of another build is a Truth auto-fail.

---

## 2. The ten dimensions, measured

Columns: **pass condition** (the 5 anchor, made numeric), **measurement** (what the reviewer reads
and where), **fail trigger** (the 3 anchor made numeric). 2 and 4 are interpolations. The 1 anchor is
the fail trigger plus an additional gross defect named in the last column.

### 1 — Focal hierarchy
- **Pass:** exactly one filled control on the surface (`terracotta` fill, or the one backend-labelled
  Continue plate on course home / the banner primary on Discover), and its `top` is above the first
  shelf card or grid row in reading order. No second element carries a filled identity hue.
- **Measurement:** count of elements whose computed `background-color` equals the `terracotta` role
  (or `on-terracotta` text on it) = **1**; the primary's box `top` < first card `top`; eye-travel
  check on the board: the first fixation lands on the course/pack/check title, not on chrome.
- **Fail trigger:** count ≥ 2, or a filled card that acts as a button, or the primary below the fold
  at 1049.
- **1 anchor:** several equal-weight blocks, or the eye lands on a stat strip.

### 2 — Composition
- **Pass:** the SPEC §5 region map for that screen is reproduced within the stated tolerance, and at
  least one region is deliberately off the equal-column track (see A2).
- **Measurement:** for every region id in the screen's §5 table, compare rendered box (from CDP
  geometry recorded in the stamp or a live probe) against the table's 1049 value: **±4 px** on each
  of `left`, `width`, `top`, `height`; ratios in §2 anchors within **±1.0 %**.
- **Fail trigger:** any region drifts more than ±4 px at 1049, or a region is a repeated box with no
  weight difference (e.g. the shelf rendered as a bordered panel inside a bordered page).
- **1 anchor:** header + equal boxes in a grid; centred dashboard.

### 3 — Type
- **Pass:** six steps only; each rendered size equals the contract value at the route width.
- **Measurement:** `getComputedStyle().fontSize` / `lineHeight` per type role, compared with
  `contracts/cb.tokens.v3.json` `type.scale` resolved through `cqi` at the measured route width:
  caption 12 / meta 14 / body 16 / lead 20 / heading `clamp(1.5rem,1.2rem+1cqi,2.25rem)` /
  display `clamp(2.5rem,1.5rem+3cqi,4rem)`; tolerance **±0.5 px** per size and **±0.5 px** per
  line-height. Distinct rendered sizes ≤ **6**. `h1` count = **1**; no skipped heading levels.
- **Fail trigger:** a 7th size, a card title outside `heading`, a heading rendered uppercase, prose
  measure outside **50–75ch**, display > **20ch** or section heading > **34ch**.
- **1 anchor:** mixed families, tiny unexplained labels, > 6 sizes.

### 4 — Palette, material and texture
- **Pass:** every painted colour is a role in the contract; every text-on-ground pair is a gate.
- **Measurement:** scan the shipped module for raw hex/rgb/hsl outside `contracts/cb.tokens.v3.json`
  (a literal colour in the route block is a finding); recompute every used text pair against the
  `gates[]` row for that pair: `ink`/`canvas` ≥ 7.0, `ink-soft`/`canvas` ≥ 4.5,
  `on-forest`/`forest` ≥ 7.0, `on-terracotta`/`terracotta` ≥ 4.5, `alert`/`canvas` ≥ 4.5,
  `plum`/`canvas` ≥ 4.5; non-text `terracotta`/`canvas` ≥ 3.0, `wood`/`canvas` ≥ 3.0,
  `wood-edge`/`wood` ≥ 1.5, `gold`/`canvas` ≥ 3.0, `sage`/`canvas` ≥ 1.5,
  `focus` vs each ground ≥ 3.0.
- **Fail trigger:** a local (non-contract) pair, a pair below its gate, two identity hues competing in
  one viewport, a decorative gradient/glass/blur, or a state hue with no word beside it.
- **1 anchor:** raw hex, decorative gradient, coloured card fills.

### 5 — Illustration
- **Pass:** ≥ 2 subject motifs from the course's own plan across hero/cover/section; one kit (light
  direction, line weight); textless plates; a reserved quiet field exists where type sits.
- **Measurement:** count distinct motifs ≥ 2; the plate's flat region under the title has non-text
  pixels only (crop the title box, assert contrast of the plate there is uniform within ΔE ≤ 3 and
  carries no glyph ink before the DOM text is drawn — checked on the art asset, not the capture);
  master-vs-render scale ≤ **1.0** (never upscaled); art textless = OCR of the shipped plate returns
  no lettering (the CP-010 pattern).
- **Fail trigger:** one motif only, two light directions, any word inside the art, a plate upscaled
  above its master.
- **1 anchor:** stock-like or generic fantasy; text in the art; wrong subject.

### 6 — Card / object system
- **Pass:** one paper object and one metadata pattern, on every shelf.
- **Measurement:** card radius = **12 px**, border = **1 px** `rule`, and elevation = `elev-1`
  **or** the rule — never both; card art ratio **3:2** (crop, never stretched: rendered
  `naturalWidth/naturalHeight` ratio within ±2 % of 1.5); every card in a shelf has the same three
  lines in the same order (`title` / one subject line / one evidence line) at the same sizes and the
  same separator; card tops and bottoms in one row share a baseline **±1 px**; shelf scrolls instead
  of shrinking (card width stays at the §3.3 value when a 5th course is added).
- **Fail trigger:** a second badge row, mixed metadata order, card-in-card nesting, a chip with no
  recorded fact behind it, XP outside Game mode, a progress bar.
- **1 anchor:** invented ratings, XP on Home, progress bars, fake credential.

### 7 — State coverage
- **Pass:** every `matrix.json` cell for the screen id renders, keeps the default geometry, names
  what was read, and offers exactly one next action.
- **Measurement:** cell-by-cell presence (E3); for each state, diff its region box against the
  default state's box: **±4 px** (no reflow); count next actions = **1**; loading has no shimmer
  (`animation-name: none` on skeletons) and keeps the previous shelf for one frame; error/offline
  never renders as empty; forced-colors and reduced-motion cells exist.
- **Fail trigger:** a missing cell, a state that moves the layout, an empty state standing in for a
  failed read, a spinner without a text line, two next actions.
- **1 anchor:** happy path only.

### 8 — Responsiveness and access
- **Pass:** 1049 / 900 / 460 preserve the composition; 200 % text clips nothing; keyboard reaches
  every control; focus is visible.
- **Measurement:** at each of the three route widths: `document.documentElement.scrollWidth <=
  clientWidth` (no horizontal overflow); card grid count at 460 = **0**; rail present at ≥ 920 and
  absent below (tab strip 56 px instead); at 200 % root scale no element's `scrollWidth >
  clientWidth + 1` and no primary is clipped; tab order is reading order; every focusable element
  shows the **2 px** `focus` ring at **2 px** offset; authored targets ≥ **24 px**, primary learning
  actions ≥ **44 px** (SPEC §3.10 uses 48 px, which satisfies it).
- **Fail trigger:** overflow at any width, a card grid at 460, a rail below 920, a focusable control
  with no ring, a target < 24 px, a clipped primary at 200 %.
- **1 anchor:** clipped primary at 460 or 200 %; no focus ring.

### 9 — Truth
- **Pass:** every visible string is DOM text from real state or `COPY.md`; no invented numeric.
- **Measurement:** extract visible text; every string maps to a `COPY.md` id or to a served backend
  field named in SPEC §6; every number on screen is reproducible from the capture's recorded state
  (evidence counts, section counts, step index); OCR of every art plate returns no lettering; no
  `NEW`/`Life`/star/XP/progress-bar element exists outside Game mode; a missing fact renders as an
  honest empty, never as `0`.
- **Fail trigger:** any string with no id, any number not traceable to a field, a decorative mark
  implying progress or a credential, provenance missing on a plate.
- **1 anchor:** any invented label, score, XP, percentage or generated screenshot.

### 10 — Craft (the dimension this card exists to make checkable)
Craft is not taste. Each clause below is a binary measurement; a 5 needs all of them, a 3 means one
clause breaks.

| C1 | Clause | Pass condition | Measurement |
|---|---|---|---|
| C1a | One material | one paper field, one wood object set, one shadow model | count distinct `box-shadow` values on route surfaces ≤ **3** (the contract's `elev-1`, `elev-2`, `inset-1`); grain/vignette applied only through their named tiles at ≤ **0.18** opacity |
| C1b | One light | every contact shadow falls the same way and sits under its object | for each elevated object, shadow `x`/`y` offset sign matches the contract's elevation, and the object's bottom edge is within **±1 px** of the surface line it rests on |
| C1c | Three tracks | every region edge lands on one of three measured tracks | collect `left` and `width` of every §5 region + every card at one width; the set of distinct left edges must be ≤ **3** per column of the screen (rail, gutter track, inner measure) and each pair within **±1 px** |
| C1d | Shared edges | banner and grid share both edges; shelf cards share top and bottom | `abs(banner.left − grid.left) ≤ 1` and `abs(banner.right − grid.right) ≤ 1`; card top/bottom spread **≤ 1 px** |
| C1e | No resampling | no plate is drawn above its master; no capture is upscaled in evidence | rendered plate ≤ master pixels; board product side never upscaled above 1.0 |
| C1f | Radius discipline | every radius is one of 0 / 6 / 12 / 999 | distinct computed `border-radius` values on the screen ⊆ `{0px, 6px, 12px, 999px}` |
| C1g | Clean edges at 200 % and forced-colors | no hairline loss, no double edge, no clipped ring | at 200 % text and forced-colors: 1 px rules still paint (≥ 1 device px), focus ring fully visible, no element overflows its parent by > 1 px |

- **Fail trigger (3):** material and illustration consistent, but one alignment breaks at one
  breakpoint or an edge degrades at 200 %.
- **1 anchor:** visible seams, mixed illustration styles, resampled art, a control that jumps.

---

## 3. Composition anchors, measured

All five must be present for every submitted screen. Binary per anchor.

| Anchor | Pass condition | Measurement |
|---|---|---|
| **A1 Threshold** | one entry point with one action before any list or grid | the one primary's box `top` is above the first card/grid row; exactly one filled control (§2.1); at 460 the order holds in DOM and visually |
| **A2 Anchored asymmetry** | at least one region breaks the equal-column rhythm on purpose | a region's `left` or `width` differs from the screen's base column track by > **8 px** (shelf overhang, route spine, offset aside, plate bleeding), and the §5 region map names it |
| **A3 Material surface (v3)** | lit paper world with physical objects and contact shadows | grain tile present ≤ 0.18; ≥ 1 `elev-1` object with its contact partner (object bottom on a surface line ±1 px); wood object has a `wood-edge` lip; no shadow without an object; no photograph-of-texture reading (tile repeat period visible = fail) |
| **A4 Subject mark** | at least one mark only this course's subject could own | a course-bound screen carries one plate/seal/motif whose subject is traceable to the course's plan; a first-time viewer can name its meaning without help (5-second test Q3, `FIVE-SECOND-TEST.md`) |
| **A5 Quiet field** | ≥ 35 % of the first viewport is quiet paper carrying the type | on the route capture, over the first **768 px** of route height (or the whole route if shorter): count pixels whose RGB is within **12** per channel of `canvas` or `canvas-edge`; divide by total sampled pixels; require ≥ **0.35**. Type and objects are excluded automatically because they are far from both grounds |

A6 does not exist. A new decorative mark does not become an anchor by being added.

---

## 4. Auto-fail regardless of score

Copied from rubric §7.2 and SPEC §5, each with its detector so it cannot be argued:

| Auto-fail | Detector |
|---|---|
| A card grid as the primary composition on Home | first grid region `top` < threshold band bottom, or ≥ 3 equal cards above the shelf heading |
| A decorative gradient or glass | any `linear-gradient`/`radial-gradient` other than the named vignette tile; any `backdrop-filter` |
| A second mascot | count of rendered fox/mascot canvases/images > 1, or a non-fox animal asset |
| A second filled primary | filled identity-hue control count ≥ 2 |
| XP, level or a streak on a non-Game screen | presence of `classroom.game.xp` / flame glyph outside Game mode |
| Text inside a plate | OCR of the plate asset returns lettering |
| A fabricated score, percentage, crowd opinion or credential | any number/label not traceable to a recorded field; any rating, review, learner count, price |
| Duplicate course/pack in one shelf | repeated `library_item.id` / `pack.id` in one shelf |
| A reviewer who built the screen | reviewer profile differs from the card's maker; reviewer is not the same chat |

---

## 5. Scorecard (copy per screen)

```
Card: CP-___            Screen id (matrix): ____________  Loop: 1 / 2 / 3
Branch/commit: ______________________  Plugin sha256 (stamp): ______________________
Reviewer: _____________ Date: __________  Reviewer profile != maker: YES / NO
Cells submitted / required: ____ / ____   Refused (E1-E5)? YES / NO
Board(s) scored (paths): _______________________________________________

Dimension                         Score 1-5   Measured value that decided it
1  Focal hierarchy                ____        filled controls = __ ; primary top = __ px
2  Composition                    ____        max region drift = __ px (±4)
3  Type                           ____        distinct sizes = __ ; max size delta = __ px
4  Palette, material, texture     ____        failing pairs = __ ; non-contract colours = __
5  Illustration                   ____        motifs = __ ; plates upscaled = __
6  Card / object system           ____        metadata variants = __ ; radius set = ______
7  State coverage                 ____        cells present = __/__ ; reflow = __ px
8  Responsiveness and access      ____        overflow at 1049/900/460 = __/__/__ ; rings = __
9  Truth                          ____        un-sourced strings = __ ; invented numbers = __
10 Craft                          ____        clauses passed = __/7

Composition anchors   A1 __  A2 __  A3 __  A4 __  A5 __   (quiet-field share = ____)
All dimensions >= 4?  YES / NO        All anchors present?  YES / NO
Auto-fail present?    YES (name it) / NO
Verdict: PASS / REQUEST CHANGES
Smallest fix if not passing: _________________________________________
Remaining differences even on pass: __________________________________
```

A scorecard with a blank measured value is not a scorecard; it is a refusal (E1–E5).

---

## 6. What this rubric still refuses

Unchanged from rubric §6: no pass without 1049/900/460, light/dark and 200 %; no pass by the maker;
no generated image as a screenshot; no 4 for "close enough"; no re-score after an explanation; no
waiver for a backend limit. Added for v3: no pass on a capture without a stamp, no pass on a board
built from a different commit, and no pass whose Craft clauses were not individually counted.
