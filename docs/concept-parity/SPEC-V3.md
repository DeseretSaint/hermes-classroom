# SPEC-V3 — concept parity, measured

Status: **binding build spec** for v3 screens (CP-020a to CP-025b) and the scoring reference for
GM-016. Written by CP-001 from the owner-ratified concept pack. Amends nothing outside v3:
v2 surfaces keep `docs/GM-VISUAL-SPEC.md` and `contracts/cb.tokens.v2.json`.

Reviewer: `atlas`. A screen that cannot meet this spec goes back for changes; it is not
downgraded to "close enough". Every dimension of `docs/GM-CONCEPT-PARITY-RUBRIC.md` §7 and every
anchor A1–A5 must pass, and the reviewer must be able to score from this document plus the
captures without asking the builder a question.

Sources, in precedence order:

1. `docs/concept-parity/PLAN.md` — owner decisions D1–D10, accepted 2026-11-10 03:05 MST.
2. `docs/concept-parity/refs/REFS.md` — the six pinned frames and their sha256.
3. `docs/EXPERIENCE-QUALITY-BAR.md` — Q1–Q12 and the v3 owner amendment appended by this card.
4. `contracts/cb.tokens.v3.json` + `docs/COURSEBOOK-VISUAL-IDENTITY-V3.md` (CP-002) — every
   colour, elevation, radius, material and type value. **This document names roles and never
   carries a colour value, a radius or a type size of its own**; a hex, a px radius or a rem size
   written here as authority is a second contract. A value this document renders from the
   contract is labelled as a rendering and never presented as authored here.
5. The shipped backend fields named per string in `docs/concept-parity/COPY.md`.

Where this document and a concept frame disagree, this document wins and the disagreement is
listed under "better than the concept" for that screen.

---

## 1. What the concepts are

Six frames, 1344×768, AI stills of one product direction (Atlas Lamp). They are references, not
screenshots. Measured facts about them:

- Every frame is textured paper with soft painted illumination and contact shadows under objects.
  The material is the direction; the v2 contract banned exactly this (§2.4 of GM-VISUAL-SPEC).
- Labels are frequently garbled (`Asttomamy`, `Repir Fundamentas`, `Soursoung`, `Sutaalo`,
  `Preveveu`, `Tinh the face thang`). Garbled text is never copied; `COPY.md` is the copy source.
- Every card row carries stars, invented progress bars, `NEW`/`Life` badges or `240 XP`. All of it
  is removed or replaced by a real field (§6, honesty table).
- The composition is consistently authored: a threshold band, an anchored shelf, a framed scene,
  a route on a painted field. That composition is what we keep.
- The frames are inconsistent with each other on navigation (Home has a top header; Discover,
  Classroom and the sheet have a forest rail) and on the grid (Home's shelf gap is 32 px;
  Discover's is 12 px; the Discover banner is 80 px wider than its own grid each side). One system
  replaces all of it (D3, §3.3).

Ratification scope, owner words: *"outside of the home page, these images were ratified."* Home is
`refs/home.png` (R-HOME). `refs/map.png` (R-MAP) is the course-home frame only.

---

## 2. Measured anchors

Measured from the pinned PNGs at 1344×768. Route-relative share is the measured box divided by
1344. These anchors justify the numbers in §3–§5; they are not the build values.

| Frame | Element | Measured box (x1–x2, y1–y2) | Size | Share of route width |
|---|---|---|---|---|
| all rail frames | forest rail | 0–103 / 0–105 | 104 wide | 7.7% |
| R-HOME | four shelf cards | 272–1038 | 767, gap 32 | 57.1% |
| R-HOME | card art | 272–443 (172), 476–645 (170), 678–843 (166), 876–1038 (163) | 106 tall | 12.7% each |
| R-HOME | hero title + sub + actions | 180–330 | action pills 46 tall, 166/159 wide | — |
| R-HOME | upper shelf, lower ledge | y 500–560, 560–601 | 42 ledge | full content |
| R-HOME | fox + brass clock | x 1155–1294, y 681–765 | 85 tall | 10.4% |
| R-DISC | feature banner | 241–1102, y 117–320 | 862 × 204 (4.23:1) | 64.1% |
| R-DISC | card grid | 321–1042 | 721, 4 cols 172/170/171/173, gaps 11–13 | 53.6% |
| R-DISC | card art | y 368–474 | 107 tall (1.60:1) | — |
| R-DISC | fox | x 1156–1284, y 600–740 | ~130 × 150 | 9.5% |
| R-CLASS | stepper column | 176–284 | 108 wide, 4 stamps | 8.0% |
| R-CLASS | scene frame | 385–945, y 273–446 | 560 × 174 (3.2:1) | 41.7% |
| R-CLASS | aside card | 1003–1305 | 302 wide | 22.5% |
| R-CLASS | evidence tray | 442–877, y 688–723 | 36 tall | — |
| R-CLASS | fox | 1214–1343 | touches the route's right edge | — |
| R-MAP | hero plate | 214–1067, y 219–491 | 853 × 273 (3.1:1) | 63.5% |
| R-MAP | shelf cards | 171–1223, y 533–643 | six, 140–145 wide, gaps 25–30, 111 tall | 78.3% |
| R-SYS | content column | 182–1276 | left 182–711, right 922–1276 | — |
| R-SYS | medallion row | 189–857, y 614–711 | six, 98–105 wide | — |

Defects this measurement exposes, each fixed in §5:

| Defect | Where | Fix |
|---|---|---|
| Grid narrower than its own banner by 80 px each side | R-DISC | banner and grid share one column track |
| 241 px dead margin right of the grid | R-DISC | content is centred on one measure, no dead band |
| Two cards named `Public Speaking`, one card duplicated artwork | R-DISC, R-MAP | one card per real course; no duplicates |
| Fox clipped by the route edge | R-CLASS, R-MAP | safe area (§3.8) |
| Rail is icon-only, so every destination needs a hover guess | R-DISC, R-CLASS, R-MAP, R-SYS | Codicon + visible label |
| Two identical filled pills | R-HOME | one filled primary, one quiet outline |
| Stars, XP, progress bars, `NEW`/`Life` badges on card rows | all | removed; real fields (§6) |
| User names and a leaderboard in the lesson aside | R-CLASS | removed; the aside is evidence and the next section |
| Painted words inside art (`LANTERN DISTRICT`, `DENNIS GARAGE`, `LIGNE 14`) | art plates | art is textless; every word is DOM text |
| Progress bars on Home cards | R-HOME | evidence tally, not a bar |

---

## 3. The shared system

### 3.1 Measurement is route-relative, never viewport-relative

The route is `[data-cb-route]`. All shell and grid values below are expressed against the **route
width**, obtained by `useCbViewportWidth()` (a `ResizeObserver` on that element), not `vw`. A
Desktop window of 1050 px can hold a 407 px route with the chat pane and explorer open; `4vw`
there would be 42 px, not the intended 16 px. Container query units (`cqi`) are acceptable where
the builder uses `container-type: inline-size` on the route; a `vw` or `clamp(…vw…)` value on a v3
surface is a defect for the reviewer.

Widths named in this document (`1049`, `900`, `460`) are **route widths**, matching
`docs/visual-review/matrix.json`.

### 3.2 Breakpoints

| Name | Route width | Shell |
|---|---|---|
| wide | ≥ 1000 | forest rail, 80 px, full route height |
| mid | 920–999 | forest rail, 72 px |
| narrow | < 920 | rail is replaced by a top tab strip, 56 px tall |
| compact | < 620 | tab strip, single-column rows, mascot hidden |

`1049` exercises wide, `900` exercises narrow, `460` exercises compact. There is no third shell.

### 3.3 Shell and gutters

| Value | 1049 | 900 | 460 | Rule |
|---|---|---|---|---|
| rail width | 80 (7.63cqi) | 0 (tab strip 56) | 0 (tab strip 56) | rail is inside the route, never a host sidebar |
| page gutter, each side | 32 (3.05cqi) | 24 | 16 | measured from the rail's inner edge on wide |
| content width | 905 (86.3%) | 852 (94.7%) | 428 (93.0%) | `route − rail − 2 × gutter` |
| top padding | 32 | 24 | 16 | below the tab strip on narrow |
| content max-width | 1000 | 1000 | — | prose columns obey the 75ch cap separately |
| column count | 4 | 3 | 1 (rows) | grid only for heterogeneous cards |
| column gap | 16 (1.53cqi) | 16 | 12 | 12 px is the compact row gap |
| card width | 214 (20.4%) | 273 (30.3%) | 428 (row) | `(content − (n−1) × gap) / n` |
| card art | 214 × 143 | 273 × 182 | 88 × 59 | 3:2, mechanical crop, never stretched |
| card text block | 68 | 68 | row text 56 | one metadata pattern (§3.6) |

The percentages are the route-relative unit to hold in the head: a rail is about a thirteenth of
the route, a gutter about a thirtieth, a wide card about a fifth. When the route resizes, the px
values change and the ratios do not. Scaling gaps with the route is fine; scaling a **type size**
or a **tap target** with the route is not, because 16 px body and 44 px primary survive to 200%
text and to 460 px.

Vertical budget at 1049 for a page that must not scroll (Home): about 780 px of route height, made
of top padding 32, threshold band 216, a 20 px gap, the 48 px action row, another 20 px, the 24 px
shelf heading, the 227 px shelf, 16 px, and the 176 px lower ledge and fox box. If the route is
shorter than that, the lower ledge and the fox zone are dropped first; the shelf and the one primary
action never are.

A fifth course at wide or a fourth at mid does **not** shrink the columns. The shelf scrolls
horizontally inside its own frame with a 32 px edge mask on the right, and the frame keeps focus
and keyboard order. A card grid must not appear at 460 (rubric §7 dimension 8).

### 3.4 Type roles

Six steps, from the v3 contract: `caption`, `meta`, `body`, `lead`, `heading`, `display`. There is
no seventh step and no second system.

The contract's six step names replace the six names this section used to carry, and the mapping is
not one-to-one: `title` → `heading`; `section` → `heading`; `label` → `meta`; `micro` → `caption`;
`body` → `body`; `display` → `display`. `lead` is a new step with no predecessor (one-sentence
intros and lesson lines). The consequence is explicit: there is no 32 px card title in v3 — a card
title is `heading`, 29.69 px at route width 1049. Copy ids such as `home.title` and
`discover.shelf.title` are copy keys, not type steps, and are not renamed; only step citations
change.

Route-container value, derived from `contracts/cb.tokens.v3.json` at route width W; the contract
governs, this table is a rendering. `cqi` resolves against the route container, so a display
placed in a narrower column renders at that column's width, not the table's number.

| Step | 1049 | 900 | 460 | Contract step | Use |
|---|---|---|---|---|---|
| caption | 12/16.2 | 12/16.2 | 12/16.2 | `0.75rem`, line-height 1.35 | stamp labels, plate credits, ratio |
| meta | 14/19.6 | 14/19.6 | 14/19.6 | `0.875rem`, line-height 1.4 | controls, chips, metadata |
| body | 16/24 | 16/24 | 16/24 | `1rem`, line-height 1.5 | prose, 50–75ch, never below 16 |
| lead | 20/27 | 20/27 | 20/27 | `1.25rem`, line-height 1.35 | one-sentence intros, lesson lines |
| heading | 29.69/34.14 | 28.20/32.43 | 24.00/27.60 | `clamp(1.5rem, 1.2rem + 1cqi, 2.25rem)`, line-height 1.15 | screen, shelf and card titles, ≤34ch |
| display | 55.47/56.58 | 51.00/52.02 | 40.00/40.80 | `clamp(2.5rem, 1.5rem + 3cqi, 4rem)`, line-height 1.02 | one per screen, ≤20ch |

Families: `CB Display` for `display` and `heading`, `CB UI` for `lead`, `body`, `meta` and
`caption`, the system CJK stack for Japanese. One uppercase element per region at most, and never
a decorative kicker above a heading.

### 3.5 Colour roles

Referenced here, defined only in `contracts/cb.tokens.v3.json`:
`canvas`, `canvas-edge`, `card-stock`, `ink`, `ink-soft`, `rule`, `forest`, `on-forest`,
`terracotta`, `on-terracotta`, `terracotta-quiet`, `gold`, `sage`, `wood`, `wood-edge`, `plum`,
`alert`, `focus`.

Rules that this spec enforces independently of the values:

- At most two identity hues plus `alert` in one viewport. State hues always sit beside their word.
- `terracotta` carries the one primary action; no other filled control uses it.
- Labels never sit on `wood`. Text on art sits on the plate's reserved quiet field, not on a scrim
  and not on a gradient.
- Every text-on-surface pair is a contract contrast pair; a local pair is a defect.
- Forced-colors: the route survives with system colours, keeps its 2 px `focus` ring, and every
  painted plate degrades to `canvas` with its DOM text intact.

### 3.6 Physical objects, not floating cards

- A card is a **paper object**: `card-stock` field, 1 px `rule` edge, radius `round` (12 px in the contract's
  `radii`; identical at every breakpoint — never restated per breakpoint), `elev-1` contact shadow
  (one soft edge, no glow, no drop shadow on text).
- A shelf is a **wood ledge**: `wood` face 12 px tall, `wood-edge` 1 px rule beneath, `elev-1`.
  Cards sit on it; they do not float above it.
- The scene frame is a mounted plate: 8 px inner mat of `canvas-edge`, 1 px `ink` rule, `elev-1`.
- Glass, blur, inner glow, rainbow or multi-stop gradients, card-in-card nesting and a second
  shadow model are banned. Grain and vignette are material tiles from the contract, not gradients.
- One metadata pattern for every card in a shelf: `title / one subject line / one evidence line`,
  with the same order, same sizes and the same separator. A card that adds a second badge row is a
  defect.

### 3.7 Icons

`sdk.Codicon` only, 16 px inline and 20 px on a medallion, `currentColor`. The rail pairs every
glyph with a visible label. Medallion and stamp centres are Codicon glyphs placed on painted
blanks; the blank is art, the glyph is the icon, and the label is DOM text. The concept's custom
line icons are **not** a second icon set and may not be redrawn as SVG.

Codicon choices (name → job):

| Glyph | Job |
|---|---|
| `home` | rail: Home |
| `library` | rail: Courses |
| `compass` | rail: Workshop; Discover tab |
| `person` | rail: Parent Studio |
| `settings-gear` | Home settings |
| `arrow-left` | back path, top-left |
| `play` | current lesson step; play the line |
| `check` | correct verdict; recorded evidence |
| `close` | wrong verdict |
| `chevron-right` | next step on a node |
| `book` | section / textbook mode |
| `flame` | Game mode only, beside the XP word |
| `shield` | a trust label that a pack passed checks |
| `warning` | rejected pack, failed read |

### 3.8 The fox

One mascot: the first-party red fox. Seven poses (A1): `wave`, `point`, `clock`, `read`, `cheer`,
`think`, `sleep`. Master 512 px tall; exports 128 and 64. Read-only: the fox is never an avatar,
never a progress metric, never editable, and never a second animal.

**Safe area.** A fox box is placed inside the content box, never over a card, never over type,
never clipped by the route edge:

- clearance to the route edge: ≥ 24 px at wide, ≥ 16 px mid and compact;
- clearance to any interactive target: ≥ 16 px;
- the box includes the prop (clock, tag) and the pose's widest frame, not just the body;
- the ground contact sits on the ledge or the plate edge it is drawn standing on;
- the mascot is `aria-hidden`; adjacent visible text carries any meaning it has.

**Size and placement per screen** (route width 1049 / 900 / 460):

| Screen | Pose (default) | Box | Placement |
|---|---|---|---|
| Home | `clock` | 128 / 112 / hidden | standing on the lower ledge, right end, feet on the ledge line |
| Home first-use | `wave` | 128 / 112 / hidden | same, no clock; holds the tag line |
| Discover | `point` | 96 / 88 / hidden | foot of the grid block, right edge, pointing into the grid |
| Classroom | `read` | 96 / 88 / hidden | bottom corner of the aside, inside the gutter |
| Classroom check correct | `cheer` | 96 / 88 / 64 | same box; the pose changes, the box does not |
| Classroom wrong answer | `think` | 96 / 88 / hidden | same box |
| Course home | `point` | 96 / 88 / hidden | beside the Continue plate, outside the hero's quiet field |
| Lab | all seven | 128 / 112 / 96 | specimens in a 160 px cell with the pose name under each |
| any empty or offline state | `sleep` | as screen | same box, no new layout |

Pose changes are a frame swap inside the existing box: no reflow, no jump, no second element.
Under `prefers-reduced-motion` (or the settings toggle) the fox renders frame 0 and never loops.

### 3.9 Motion

| Beat | Duration | Property |
|---|---|---|
| press | 120 ms | transform, opacity |
| lift | 150 ms | transform, shadow token |
| route change | 240 ms | opacity only |
| verdict | 300 ms | opacity, the stamp scale |
| completion | 600 ms | one authored beat, then still |

No loops, no idle float, no parallax, no confetti, no shimmer. A screen with no state change does
not move. Reduced motion strips movement and keeps the state change.

### 3.10 One primary action per screen

| Screen | The one primary | Secondary (quiet) | Never |
|---|---|---|---|
| Home | `Start a course` — filled `terracotta`, 48 px tall, radius 999 | `Browse library` — 1 px `rule` outline, `ink` label, same height | two filled pills; a filled card that acts as a button |
| Discover | `Preview this pack` — filled, in the banner's quiet field | tab strip, shelf scroll, trust label as text | a filled control on every card |
| Classroom | `Check answer` — filled, in the check card | `Play the line` as a quiet text action; `Try again` after a wrong verdict | `Audio Play` as an answer option; a second filled action in the aside |
| Course home | the backend's `library_item.next_step.label` rendered as the filled plate | route nodes; evidence tray | a second filled Continue |
| Lab | none; `Back` is the only navigation, quiet | none | inventing a primary to satisfy a gate |

A read-only sheet is the one documented N/A for Q2; the reviewer accepts "no filled control" and
rejects "two filled controls".

### 3.11 Navigation (D3)

One system on every screen: the forest rail at ≥ 920 route px, the top tab strip below it. The
rail carries the four shipped destinations, Codicon plus visible label, in this order:

| Rail / tab | Label | Destination id | On-forest treatment |
|---|---|---|---|
| `home` | Home | `home` | `aria-current="page"` when the route is `#/coursebook` |
| `library` | Courses | `courses` | — |
| `compass` | Workshop | `workshop` | — |
| `person` | Parent Studio | `studio` | — |

Current destination: 3 px `terracotta` marker on the rail's inner edge, `on-forest` label at full
contrast, and `aria-current="page"`. It is not colour alone; the marker is a shape.

Concept names map onto shipped destinations and are **not** added as new destinations:
`Discover` → Workshop (Discover tab); `Studio` → Parent Studio; `Classroom` → the course-scoped
screen reached from Home or Courses; `Home` → Home. No fifth destination is created.

Deep screens (classroom, course home, lab) carry `Back to <parent>` at the top-left as the first
focusable element, `arrow-left` plus visible label. The rail's current entry on a course screen is
`Courses`.

The Home settings sheet stays one sheet opened by `settings-gear`, never a destination.

### 3.12 State contract

Every screen implements, with the same geometry as its default state (no reflow into a different
composition): `default`, `loading`, `empty`, `error`, `offline`, plus its own named states in §5.
Each state names what was read, what is preserved, and exactly one next action. A failed read never
renders as an empty shelf, an empty course, or "not started".

Loading uses the route's own skeleton: the real region boxes, `card-stock` at 40% opacity, no
shimmer, no spinner without a text line, and the last good content stays visible for one frame
before the skeleton replaces it.

---

## 4. Copy

Every string on every v3 screen lives in `docs/concept-parity/COPY.md` with an id. This document
references those ids per region and per state; a screen may not render a string that has no id,
and an id that no screen uses is deleted rather than kept.

Plain language: 6th–8th grade, sentence case, no internal enums (`resolve_review_due`), no
"governed", "runtime", "binding", "projection", no exclamation marks, no self-congratulation.
Course subject matter keeps its register; the chrome does not.

Japanese at L0 carries the pack's own line — kana, `romaji` and the English meaning, read from the
pack's section content or its media `text_equivalent` — plus a `furigana` ruby over kanji that this
deck authors. The pack carries no reading, so the ruby is deck-owned and is omitted when a pack has
none; a reading is never derived from kana. Romaji fades as a scaffold; it is never the only form
offered and never evidence of reading. The worked example in COPY.md is the bundled L0 pack's own
line, not invented.

---

## 5. Screens

### 5.1 R-HOME — Home (card CP-022)

**Question it answers:** which course do I open next, and how do I start a new one?
**One primary:** `Start a course` (`home.primary`). **Pose:** `clock`, `wave` on first use.
**Frame:** `docs/concept-parity/refs/home.png`.

Measured concept composition to keep: a threshold band that is type only, one action pair, a
wooden shelf with painted card art, one lower ledge holding a fox with a brass alarm clock and a
paper tag. What changes: the top header becomes the rail (D3); the two filled pills become one
filled plus one outline (D1); stars and progress bars become an evidence tally.

**Region map**

| # | Region | 1049 | 900 | 460 | Copy ids |
|---|---|---|---|---|---|
| H1 | rail / tab strip | 80 wide, full height | tab strip 56 tall | tab strip 56 tall | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` |
| H2 | threshold band | content 905, top 32, 216 tall | 852, top 24, 200 tall | 428, top 16, 184 tall | `home.title`, `home.sub` |
| H3 | action row | 2 × 48 tall, gap 16, starts 24 under the sub | same | stacked, 48 each, gap 12, full width | `home.primary`, `home.secondary` |
| H4 | shelf heading | 24 tall, 32 under the action row | 24, 24 under | 24, 24 under | `home.shelf.label` |
| H5 | shelf frame | 905 × 227 (art 143 + text 68 + ledge 16), 4 × 214, gap 16 | 852 × 266, 3 × 273, gap 16 | rows 428 × 88, gap 12 | `home.card.meta`, `home.card.new`, `home.card.next` |
| H6 | lower ledge + fox box | ledge 16 tall, fox box 176 × 160 at the right end | 160 × 144 | hidden | `home.tag.firstuse` (first use only) |
| H7 | settings entry | 44 × 44, top-right of H2 | same | same | `home.settings` |

Vertical order is fixed: H2, H3, H4, H5, H6. H6 is never above the shelf; the shelf's wood face is
the ground line the fox stands on. The shelf never renders as a bordered box: no card-in-card.

**States**

| State | Shows | One next action | Copy ids |
|---|---|---|---|
| default | 1–4 real courses on the shelf, each with title, subject line, evidence line; newest or most urgent first | the top card's own next step — activating the card opens the course; the filled primary stays `Start a course` | `home.card.meta`, `home.card.new`, `home.card.next` |
| first-use | empty shelf geometry preserved; fox `wave` holding the tag; one short line says what starting does | `Start your first course` (same filled control, longer label) | `home.firstuse.title`, `home.firstuse.sub`, `home.firstuse.primary`, `home.tag.firstuse` |
| overflow | 5+ courses at wide / 4+ at mid; shelf scrolls inside its frame with a 32 px right mask, keyboard order intact | scroll or `Browse library` | `home.overflow.hint` |
| empty | no courses match this filter, or everything is archived | `See archived courses` (quiet) | `home.empty.title`, `home.empty.body`, `home.empty.action` |
| loading | H2–H5 boxes as skeletons; no shimmer; the previous shelf stays visible for one frame | none (reads in flight); the band says so | `home.loading` |
| error | H2–H5 keep geometry; one sentence says the read failed and nothing saved was lost; fox `sleep` | `Try again` | `home.error.title`, `home.error.body`, `home.error.action` |
| offline | same as error with the offline cause; settings and existing lessons still open | `Try again` | `home.offline.title`, `home.offline.body`, `home.offline.action` |

**Better than the concept**

1. One filled primary, one quiet outline — the concept shows two identical filled pills.
2. No stars, no `NEW`/`Life` badges, no progress bar: `2 of 5 sections done` plus the real next-step
   label, from `evidence_summary` and `next_step`.
3. Cards align to the shelf's own width and share one metadata pattern; the concept's fourth card
   is narrower than the first.
4. The fox and the clock sit fully inside the safe box; the tag exists only in first-use and is not
   a second create control.
5. The shelf is a real scroll region with a named overflow state, so a fifth course never shrinks
   the cards.
6. Loading, empty, error and offline all keep the shelf's geometry, so the first screen never
   collapses into a blank page.

### 5.2 R-DISC — Discover / Workshop (card CP-021)

**Question it answers:** which pack can I learn from, and what is inside it?
**One primary:** `Preview this pack` (`discover.feature.primary`). **Pose:** `point`.
**Frame:** `docs/concept-parity/refs/discover.png`.

Measured concept composition to keep: a forest rail, a painted feature banner, a shelf heading, a
grid of painted pack cards, a fox at the grid's foot. What changes: the banner and grid share one
track; the rail is labelled; every card uses one metadata pattern; stars and `NEW` circles become
trust labels and real section counts.

**Region map**

| # | Region | 1049 | 900 | 460 | Copy ids |
|---|---|---|---|---|---|
| D1 | rail / tab strip | 80 wide | tab strip 56 | tab strip 56 | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` (as H1) |
| D2 | page head | heading 29.69/34.14 + body 16/24, top 32 | heading 28.20/32.43 + body 16/24, top 24 | heading 24.00/27.60 + body 16/24, top 16 | `discover.title`, `discover.sub` |
| D3 | surface tabs | 44 tall, gap 24, 24 under D2 | 44, gap 16 | 44, horizontally scrollable | `discover.tab.discover`, `discover.tab.library`, `discover.tab.provenance` |
| D4 | feature banner | 905 × 226 (4:1), radius `round`, 24 under D3 | 852 × 213 | 428 × 171 (2.5:1 crop) | `discover.feature.title`, `discover.feature.body`, `discover.feature.primary` |
| D5 | banner quiet field | left 40% (362 / 341 / full width above the fold), inner pad 32 | 28 | 20 | — |
| D6 | shelf heading row | 24 tall, 32 under D4, count at the right | 24 under | 16 under | `discover.shelf.title`, `discover.shelf.count` |
| D7 | pack grid | 905, 4 × 214, gap 16, row gap 24 | 852, 3 × 273 | rows 428 × 88 | `discover.card.meta`, `discover.card.trust.integrity`, `discover.card.trust.checks`, `discover.card.trust.human`, `discover.card.trust.model` |
| D8 | fox box | 96 × 120, right edge of D7's last row, 24 inside the gutter | 88 | hidden | — |
| D9 | provenance strip | one 48-tall row at the foot when a pack's checks did not pass | same | same | `discover.rejected.banner` |

D4 and D7 share **one** left and right edge at every width. A banner wider than the grid, or a
grid narrower than the banner, is the concept's defect and a reviewer finding.

**States**

| State | Shows | One next action | Copy ids |
|---|---|---|---|
| default | banner for the featured installed pack; `All packs` grid of every installed pack with title, one subject line, one trust label and section count when known | `Preview this pack` | `discover.feature.title`, `discover.feature.body`, `discover.feature.primary`, `discover.card.meta`, `discover.card.trust.integrity`, `discover.card.trust.checks`, `discover.card.trust.human`, `discover.card.trust.model` |
| empty | no packs installed; geometry preserved; banner region becomes a quiet plate with one line | `Import a pack` (quiet) | `discover.empty.title`, `discover.empty.body`, `discover.empty.action` |
| loading | tabs and banner boxes as skeletons; grid rows as card skeletons; no shimmer | none; the head line says the read is running | `discover.loading` |
| error | grid region keeps size, one sentence names the failed read and says installed packs are unchanged | `Try again` | `discover.error.title`, `discover.error.body`, `discover.error.action` |
| offline | catalogue reads fail, installed packs still list from the local store | `Try again` | `discover.offline.title`, `discover.offline.body`, `discover.offline.action` |
| rejected | a pack whose integrity or automated checks did not pass stays listed, marked, and its preview names what failed | `Open Provenance` | `discover.rejected.title`, `discover.rejected.body`, `discover.rejected.action`, `discover.rejected.banner` |

**Better than the concept**

1. **Grid aligned to the banner edges** — one track, measured 905/905 at wide.
2. **No dead zone right of the grid** — the content column is centred on one measure; the concept's
   grid stops 241 px short of its own banner's right edge.
3. **Labelled rail** — Codicon plus visible text, `aria-current`, 44 px targets; the concept's rail
   is unlabelled glyphs.
4. **Fox inside the safe area** — offset 24 px from the grid corner, clear of the last card; the
   concept's fox overlaps the grid's margin.
5. **One metadata pattern for every card** — title, one subject line, one trust label, one count.
   The concept mixes stars, `NEW`, `Life`, `Hands-on` and `Creative` across cards with no rule.
6. No invented trust: every label is a real `trust_labels()` value, including
   `model_assessed_support`, which is never rendered as approval.
7. No duplicate course appears twice in the same shelf.

### 5.3 R-CLASS — Classroom lesson (card CP-023)

**Question it answers:** what is this line, and can I answer the check?
**One primary:** `Check answer` (`classroom.check.primary`). **Pose:** `read`.
**Frame:** `docs/concept-parity/refs/classroom.png`.

Measured concept composition to keep: forest rail, a vertical stamp stepper, a framed painted scene,
a dialogue bubble with a real Japanese line, a check card, an aside, an evidence tray at the foot.
What changes: the aside loses XP, flames, names and a leaderboard; the second filled button becomes
a quiet text action; the stepper current stamp is marked by shape plus word; the fox stops
touching the edge.

**Region map**

| # | Region | 1049 | 900 | 460 | Copy ids |
|---|---|---|---|---|---|
| C1 | rail / tab strip | 80 wide | tab strip 56 | tab strip 56 | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` |
| C2 | back path | 40 tall row, top 24 | 40, top 16 | 40, top 12 | `classroom.back` |
| C3 | stepper | column 96 wide, stamp 48, connector 2 px dotted, label 12 under | horizontal strip 56 tall, stamp 40, labels beside | strip 64, 4 stamps 40 in a row | `classroom.stepper.label`, `classroom.step.current`, `classroom.step.done`, `classroom.step.next` |
| C4 | lesson head | heading 29.69/34.14 + body 16/24, above the scene | same | same | `classroom.title`, `classroom.section` |
| C5 | scene frame | 493 × 164 (3:1), mat 8, 1 px rule, `elev-1` | 852 × 284 | 428 × 143 | `classroom.scene.credit` |
| C6 | dialogue | max 44ch, pad 16, tail 12, 16 under C5 | same | same | `classroom.line.jp`, `classroom.line.romaji`, `classroom.line.en`, `classroom.line.play` |
| C7 | check card | 493 wide, pad 20, question `lead` 20/27, answer surface per format below, primary 48 | 852 | 428 | `classroom.check.question`, `classroom.check.option`, `classroom.check.item`, `classroom.check.primary`, `classroom.check.edit`, `classroom.check.clear_choice`, `classroom.check.clear_ticks`, `classroom.check.correct`, `classroom.check.wrong`, `classroom.check.retry`, `classroom.check.next` |
| C8 | aside | 268 wide, right column, 24 gap from C7 | below C7, full width, 32 gap | below C7, 24 gap | `classroom.evidence.title`, `classroom.evidence.count`, `classroom.evidence.empty`, `classroom.aside.next`, `classroom.aside.tutor` |
| C9 | evidence tray | aside foot: real counts and recorded events, 72 tall | aside foot | below the check | `classroom.evidence.count`, `classroom.evidence.empty` |
| C10 | fox box | 96 × 120 in the aside's bottom corner, 16 inside the gutter | 88 | 64 beside the evidence tray | — |
| C11 | game rail | Game mode only: XP chip in the lesson head, Field Challenge card in the aside | same | same | `classroom.game.xp`, `classroom.challenge.title`, `classroom.challenge.primary` |

Lesson column width at wide = `content − stepper − gaps − aside` = 905 − 96 − 24 − 268 − 24 = 493.

**C7 answer surfaces (`check.get.stimulus.format`).** One card, three answer surfaces. The card box
and the question line are identical in all three; only the answer region changes. The served
`format` decides it, never the pane: `selection` with declared `choices[]` is a choice check, every
other format keeps the written answer. A parent-led lesson is observed through the observation
control and paints no answer surface at all.

| Format | Served fields | Answer region at 493 / 852 / 428 | Focus order | One next action |
|---|---|---|---|---|
| `text` | `prompt`; `choices[]` empty | meta `Your answer` 14/19.6, then a textarea 3 rows (5 in the player view), full card width, min 44 tall; one helper line under it | question → textarea → primary → quiet secondary | `Check answer`; quiet `Edit answer` |
| `selection` | `prompt`; `choices[]` 2–8 | radio rows: one choice per row, 44 tall, 8 gap, number + choice text + the word `Selected`; a live summary line `Selected: {n}. {choice}` or `Nothing selected yet.` replaces no control | question → first row (roving tabIndex, arrows and 1–8 move) → primary | `Check answer`; quiet `Clear choice` |
| `verification` | `prompt`; `items[]` 1–24 | checklist rows: one 24 px checkbox + its `label` per row, 44 target, 8 gap; one helper line under the list; no text field | question → first checkbox → primary | `Check answer`; quiet `Clear ticks` |

Each format's primary stays 48 tall and is the only filled control in C7. The submitted answer
differs and is frozen elsewhere: `text` sends the typed string, `selection` sends the chosen served
choice, `verification` sends the ticked item ids (never labels and never typed text). A wrong
verdict moves the primary to `Try again`; a correct one moves it to `Next section`. The verdict
line is `That is right. {why}` / `Not quite. {why}`, where `{why}` is a criterion's `observed` text
from the graded result; when the result carries no observation the sentence ends after the first
clause and no reason is invented.

If v3 does not build all three in CP-023, it may ship `text` and `selection` and defer
`verification` to the card that owns checklists — the deferral must be written in that card, and
the deferred format must not render a half-built surface in the meantime.

**States**

| State | Shows | One next action | Copy ids |
|---|---|---|---|
| default | scene, the pack's real line with kana, romaji, the deck ruby and the meaning, the served check in its own format, one filled primary | `Check answer` | `classroom.check.primary`, `classroom.line.jp`, `classroom.line.furigana`, `classroom.line.romaji`, `classroom.line.en` |
| correct | stamp lands on the verdict beat; correct option marked by shape and word; the evidence count updates | `Next section` | `classroom.check.correct`, `classroom.check.next` |
| wrong | no stamp loss, no red flood; the option is marked, the correction names the rule | `Try again` (primary moves here) | `classroom.check.wrong`, `classroom.check.retry` |
| no-chat | scene and line still render; one sentence says this section has no chat yet | `Start a fresh run` | `classroom.nochat.title`, `classroom.nochat.body`, `classroom.nochat.action` |
| complete | evidence recorded, aside closed with one authored beat, no confetti | `Back to the path` | `classroom.complete.title`, `classroom.complete.body`, `classroom.complete.action` |
| loading | scene and check as skeletons; the stepper already shows the real path | none; the head line says the page is opening | `classroom.loading` |
| error | scene frame keeps its size, one sentence names what failed, the attempt is untouched | `Try again` | `classroom.error.title`, `classroom.error.body`, `classroom.error.action` |
| offline | the same, naming the lost connection | `Try again` | `classroom.offline.title`, `classroom.offline.body`, `classroom.offline.action` |

**Better than the concept**

1. One filled primary (`Check answer`); `Play the line` is a quiet text action, not a second filled
   button, and never an answer option.
2. The aside carries evidence and the real next section, not XP, flames, invented names or a
   leaderboard.
3. Current step is marked by a 3 px ring **and** the word `Now`; the concept marks it by a glow only.
4. Evidence reads `2 of 5 checks recorded`, not `215 proofs collected`.
5. The fox sits inside the gutter; the concept's fox is clipped by the route edge.
6. The Japanese line shows kana, furigana and romaji together; the bubble's text is the lesson's
   real line, not a decorative quote.
7. Stepper count is the section count from the plan, not a fixed four.

### 5.4 R-MAP — Course home (card CP-024)

**Question it answers:** where am I in this course, and what is the next section?
**One primary:** the backend's `library_item.next_step.label` rendered as the filled plate.
**Pose:** `point`. **Frame:** `docs/concept-parity/refs/map.png` (F2 for the Japanese course).

Measured concept composition to keep: a painted route field with a winding path and stamp nodes,
a hero plate, a Continue aside, a shelf of other courses. What changes: the route nodes are DOM
buttons with words; the shelf is honest and small; the header's search box and the `Start a new`
fragment are removed (search is not shipped and a truncated duplicate action is a defect).

**Region map**

| # | Region | 1049 | 900 | 460 | Copy ids |
|---|---|---|---|---|---|
| M1 | rail / tab strip | 80 wide | tab strip 56 | tab strip 56 | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` |
| M2 | back path | 40 tall, top 24 | 40, top 16 | 40, top 12 | `course.back` |
| M3 | course head | heading 29.69/34.14, subject body 16/24, 24 under M2 | same | same | `course.title`, `course.subject` |
| M4 | hero plate | 613 × 204 (3:1) at wide, mat 8, radius 12 | 852 × 284 | 428 × 214 | `course.hero.credit` |
| M5 | route | nodes 56 dia on a spine inside M4, 88 apart, current 56 with 3 px ring, all labels 12 | same, nodes 48 | vertical list below M4, node 44 | `course.route.label`, `course.node.current`, `course.node.done`, `course.node.next`, `course.node.locked` |
| M6 | aside Continue | 268 wide, first child of the right column, pad 16 | below M4 | below M5 | `course.continue.title`, `course.next.label` |
| M7 | aside evidence | 268, under M6 | full width | full width | `course.evidence.title`, `course.evidence.count` |
| M8 | other courses | 3 rows 428 × 72 or 3 × 273 cards, 24 below the hero block | 3 rows | 2 rows max | `course.others.title`, `course.others.row` |
| M9 | fox box | 96 × 120 beside M6, outside M4's quiet field | 88 | hidden | — |

Lesson-column width at wide with the aside = 613. The aside is a right column only at ≥ 1000
route px; below that it moves under the route and keeps its order (Continue, evidence, others).

**States**

| State | Shows | One next action | Copy ids |
|---|---|---|---|
| default | hero plate, route with current/done/next, Continue aside, evidence | `Continue <section>` (the backend's own label) | `course.continue.title`, `course.next.label`, `course.evidence.count` |
| plan-in-review | route reads as prepared but not started; the Continue plate is replaced by the review plate | `Review the plan` | `course.plan.review.title`, `course.plan.review.body`, `course.plan.review.action` |
| no-world | plate region becomes a quiet paper field with the course title; everything else unchanged | `Continue <section>` — the lesson does not need the art | `course.noworld.title`, `course.noworld.body` |
| world-running | plate shows the in-flight state with the last approved plate kept underneath | `Continue <section>` | `course.world.running` |
| world-rejected | plate falls back to the typographic field and says so | `Open World Studio` (quiet) | `course.world.rejected.title`, `course.world.rejected.action` |
| course-end | every node marked done; one authored complete beat; evidence total is the close | `Review the plan` | `course.end.title`, `course.end.body`, `course.end.action` |
| loading | head and plate boxes as skeletons; the route spine already draws | none; the head says it is opening | `course.loading` |
| error | plate keeps size; the route shows the last recorded state, not an empty path | `Try again` | `course.error.title`, `course.error.body`, `course.error.action` |

**Better than the concept**

1. Route nodes are real buttons with visible labels and `aria-current`; the concept's numbers are
   unlabelled ornaments.
2. No search box and no truncated second create action; one primary, one back.
3. The shelf below is small and honest (other courses only), not six duplicate cards.
4. The fox does not overlap the route or the type field.
5. The plate's text sits in a reserved quiet field painted for it, not on a scrim.

### 5.5 R-SYS — Design-system lab (card CP-020b)

**Question it answers:** what are the product's parts, and what may a screen use?
**One primary:** none; `Back` is the only navigation (documented N/A for Q2).
**Frame:** `docs/concept-parity/refs/system.png`.

Measured concept composition to keep: a two-column sheet of specimens — fox poses, card anatomy
with numbered callouts, a medallion row, a palette chip grid. What changes: every label is DOM
text, every chip names its role and measured ratio, every medallion is a Codicon on a painted
blank, and nothing on the sheet is a fake credential.

**Region map**

| # | Region | 1049 | 900 | 460 | Copy ids |
|---|---|---|---|---|---|
| S1 | rail / tab strip | 80 wide | tab strip 56 | tab strip 56 | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` |
| S2 | sheet head | display 55.47/56.58 + body 16/24 line, top 32 | display 51.00/52.02 | display 40.00/40.80 | `lab.title`, `lab.sub`, `lab.readonly` |
| S3 | left column | 588 wide, sections stacked, 32 apart | 852 | 428 | `lab.section.fox`, `lab.section.card`, `lab.section.medals` |
| S4 | right column | 297 wide, 20 gap | below S3 | below S3 | `lab.section.palette`, `lab.section.type`, `lab.section.materials` |
| S5 | fox specimens | 7 cells 160 tall, 128 fox, pose name 12 | 6 per row | 2 per row | `lab.pose.wave`, `lab.pose.point`, `lab.pose.clock`, `lab.pose.read`, `lab.pose.cheer`, `lab.pose.think`, `lab.pose.sleep` |
| S6 | card anatomy | one real `paper` card 214 × 211 with 6 numbered callouts, numbers 12 | 273 | 428 row | `lab.anatomy.plate`, `lab.anatomy.title`, `lab.anatomy.subject`, `lab.anatomy.evidence`, `lab.anatomy.next`, `lab.anatomy.cover` |
| S7 | medallions | 4 painted blanks 64 dia with Codicon centres and event names | 4 | 2 per row | `lab.medal.first_check`, `lab.medal.first_review`, `lab.medal.first_takehome`, `lab.medal.course_complete` |
| S8 | palette | chips 64 × 64, role name 12, ratio 12 | 4 per row | 2 per row | `lab.palette.ratio`, `lab.palette.role` |
| S9 | type | six rows in contract order — `caption`, `meta`, `body`, `lead`, `heading`, `display` — each with name, size and a sample line | same | same | `lab.type.micro`, `lab.type.label`, `lab.type.body`, `lab.type.lead`, `lab.type.title`, `lab.type.display` |
| S10 | materials | grain, wood face, three elevations, radius 0/6/12/999 | same | same | `lab.material.grain`, `lab.material.wood`, `lab.material.elevation`, `lab.material.radius` |

S2's sheet-head box was drawn for a 40 px display with a 48 px line-height, which is not the
contract's display step at any route width; the 1049 rendering is 55.47/56.58, so its height and
baseline are re-measured by CP-020b. No other §5 geometry changed in this reconciliation.

S9's six rows are the v3 deck rows in contract order, and their sizes are the 1049 column of §3.4,
never an authored number. The deck also keeps one v2-only row, `lab.type.section`, for v2 surfaces:
v2 keeps the v2 spec, so that row is not one of S9's six v3 rows and S9 paints no `section` step.

**States**

| State | Shows | One next action | Copy ids |
|---|---|---|---|
| default | the six sections with real values read from the contract at render time | none; `Back` | `lab.back` |
| reduced-motion | identical sheet, no transitions; the fox shows frame 0 | none | `lab.motion.static` |
| forced-colors | system colours; plates become `canvas`; every label and ratio still readable | none | `lab.forced` |
| text-200 | two columns collapse to one, chips wrap, nothing clips, ratios stay visible | none | `lab.text200` |

**Better than the concept**

1. Every callout label is real text at 12 px with a real meaning, not decorative script.
2. Palette chips carry the role name and the computed contrast ratio; the concept's chips are
   unlabelled paint.
3. Medallions are one Codicon on one blank, mapped to one recorded event, with no invented ribbon
   text.
4. The sheet states it is read-only and where its values come from, so no one mistakes it for a
   settings page.

---

## 6. Honesty table (binding for every v3 screen)

Every element in the five refs, with what ships and where the value comes from. A screen that
renders an element not listed here is not covered by this spec and must not ship.

| Concept element | Frame | Ship instead | Source field | Copy id |
|---|---|---|---|---|
| Star row on each card | HOME, DISC, MAP | nothing; the evidence line replaces it | `library_item.evidence_summary` / CP-005 `sections_done`,`sections_total` | `home.card.meta` |
| `NEW` circle on cards | DISC, MAP | `New` only when the course has no attempts yet | `evidence_summary.independent == 0` and `next_step.kind == "start_lesson"`; CP-005 `is_new` | `home.card.new` |
| `Life` / `Hands-on` / `Creative` circles | DISC | one subject line, from the course's subject label | `world_brief.subject_domain` or `recipe`; CP-005 `subject_label` | `home.card.subject` |
| Progress bar on every card | HOME, MAP | evidence tally `2 of 5 sections done` | `sections_done`/`sections_total`; today `evidence_summary.independent`/`total_objectives` | `home.card.meta` |
| `240 XP` and flame row outside Game | CLASS | XP chip and Game bar only on the Game layer | `engagement.read.xp_total`, `level`, `xp_into_level` | `classroom.game.xp` |
| Streak flames beside the header | MAP | nothing in this slice | none | — |
| `215 proofs collected` / `2 of 5 proofs` | CLASS | `2 of 5 checks recorded` | counted from recorded checks (`evidence.inspect`) | `classroom.evidence.count` |
| Gold seals and rosettes | CLASS, SYS | one medallion per recorded event: first check, first review, first take-home task, course complete | `engagement` recent events | `lab.medal.first_check`, `lab.medal.first_review`, `lab.medal.first_takehome`, `lab.medal.course_complete` |
| Padlock on proofs | CLASS | `Opens after the check` only where the plan really gates it | course plan | `classroom.step.locked` |
| User names and leaderboard in the aside | CLASS | nothing; the aside carries evidence and the next section | `library_item.next_step.label`, evidence counts | `classroom.aside.next` |
| `Try it yourself` challenge card with invented reward | CLASS | Field Challenge in Game mode only, with a real check behind it | `check.get` stimulus + `engagement.read` | `classroom.challenge.primary` |
| Japanese bubble text (garbled) | CLASS | the pack's real line: kana + romaji + meaning read from pack content, plus a deck-authored furigana ruby omitted when the pack has no reading | pack section content / `text_equivalent` for kana, romaji and meaning; `deck` for the ruby | `classroom.line.jp`, `classroom.line.furigana`, `classroom.line.romaji`, `classroom.line.en` |
| `Audio Play` as an answer option | CLASS | speaker button on the dialogue only; answers are the check's own served choices or items | `check.get` `stimulus.choices[]` (`selection`) / `stimulus.items[].label` (`verification`) | `classroom.line.play` |
| Ticket, passport tray, `LIGNE 14` | CLASS | evidence tray with real counts and event names | `engagement` events, evidence counts | `classroom.evidence.count` |
| Painted words inside art (`LANTERN DISTRICT`, `DENNIS GARAGE`) | DISC, HOME, MAP | art is textless; title and subject are DOM text | `pack.inspect` / `library_item.title` | `discover.card.meta` |
| Search field | MAP | not shipped; no search control | — | — |
| Truncated second create action (`Start a new`) | MAP | one primary only | — | `home.primary` |
| Duplicate course card | DISC, MAP | one card per course | `library.list` ids | — |
| Currency, price, learner counts | DISC | nothing | — | — |
| Rating count and review text | DISC, HOME | nothing | — | — |
| `Achievements` badge row on the header | MAP | removed from the header; medallions live in evidence and the lab | `engagement` events | — |
| Clock hands | HOME | fixed to 10:10 as a prop; `aria-hidden`; not a time claim | art asset | — |
| Grid mismatch (banner vs cards) | DISC | one shared track | layout rule §3.3 | — |
| Fox cut by the route edge | CLASS, MAP | safe area §3.8 | layout rule | — |
| Garbled headings anywhere | all | `COPY.md` only | copy deck | — |

---

## 7. Review hook

The reviewer scores `docs/GM-CONCEPT-PARITY-RUBRIC.md` §7 (the v3 section) on captures from
`scripts/cp-capture.mjs`, one cell per screen and state in `docs/visual-review/matrix.json`, and
files a finding naming:

- the region id from §5 that failed,
- the measured value that failed (route width, size, gap, ratio),
- the test or capture that closes it.

Three loops maximum. A fourth failure goes to `atlas`, who splits the screen.

---

## 8. Not decided here

- Exact colour values, shadow recipes and font files: CP-002 (`contracts/cb.tokens.v3.json`).
- Whether the module is split into segments for parallel screen work: D9 / CP-006.
- Print and take-home page anatomy: `docs/GM-PRINT-SPEC.md` (unchanged by v3 beyond materials).
- Any new gamified mechanic: none is introduced. Game mode's existing rules stand
  (`docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md`).
