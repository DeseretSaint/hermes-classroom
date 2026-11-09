# GM visual spec — composition, tokens, card anatomy and states

Status: **design authority** for GM-002, GM-004, GM-006, GM-008, GM-010, GM-012, GM-014 and the
final visual card GM-016. Frozen by GM-013 on 2026-11-09.
Reviewer: `atlas`. A screen that cannot meet this spec goes back for changes; it does not get
downgraded to a generic card grid.

This document does not restate the product plan. It translates four owner-approved concept frames
into numbers an implementer can build and a reviewer can score:

| Frame | File | Authority for |
|---|---|---|
| **F1** global Home | `~/Pictures/coursebook-direction-a/home-generic-first-open.png` | shelf/launcher composition, invitation band, shelf geometry |
| **F2** Japanese course home | `~/Pictures/coursebook-direction-a/japanese-classroom-reference.png` | course-bound hero, route spine, course-only scene |
| **F3** refined classroom | `~/Pictures/coursebook-direction-a/refined-classroom.png` | three-column course page, type over art, aside card |
| **F4** refined system | `~/Pictures/coursebook-direction-a/refined-system.png` | card anatomy, palette character, badge/seal language |

Concept frames are **references, not screenshots**. Nothing in them is copied literally, and the
three things they contain that the product must not contain are listed in §2.4.

Companion documents:
- `docs/GM-SUBJECT-WORLDS.md` — the four subject boards and the anti-generic swap check.
- `docs/GM-CONCEPT-PARITY-RUBRIC.md` — the scoring instrument and per-screen comparison frames.
- `docs/GM-PRINT-SPEC.md` — take-home pack page anatomy and the A4/Letter proof.
- `docs/GM-ART-PLATES.md` — approved textless plates and provenance rules.
- `docs/visual-review/` — the screenshot matrix every visual card fills in.

---

## 1. Ground truth this spec is bound to

The token table and type scale are already shipped in `desktop/plugin.js` and gated by
`contracts/cb.tokens.v2.json`, `tests/test_desktop_tokens.py` and `tests/test_desktop_type_scale.py`.
**This spec adds no token, no hue, no radius and no seventh font size.** Where a concept frame
suggests something the shipped contract forbids, §2.4 says so and names the substitute.

| Layer | Shipped authority | GM-013 ruling |
|---|---|---|
| Colour | `CB_TOKENS_JSON` — 15 tokens, light + dark | unchanged; every plate, band and chip uses a token name, never a hex |
| Type | `CB_TYPE_SCALE_JSON` — six steps: `caption` .75rem, `meta` .875rem, `body` 1rem, `lead` 1.125rem, `heading` 1.5rem, `display` clamp(2.25rem—2.5rem) | unchanged; roles are assigned to those six steps in §3 |
| Measure | `66ch` reading, `32ch` rail, `75ch` hard cap asserted by test | unchanged |
| Geometry | radius `0` fields / `2px` controls / `999px` state pills / `50%` nodes; 1px `rule`, 1px `ink` plate head, 2px active hue, 3px band; **no shadow, no gradient, no blur, no card-in-card** | unchanged; the concept's shadowed wooden shelf and pill button are replaced (§2.4) |
| Icons | `sdk.Codicon` only, 16px inline / 20px plate mark, `currentColor` | unchanged; no second icon family, no emoji |
| Illustration lane | Press Plate (deterministic, flat, textless) is the shipped cover lane | world plates are a **second, separately governed lane** — see `docs/GM-ART-PLATES.md`; Press Plate rules still bind covers |
| Mascot | one fox, textless, never a second mascot | the fox is the only Coursebook mascot; no robot, no second animal, no face on the brand mark |
| Panel fills | `accent-soft` (selected row), `lamp-soft` (hero/checkpoint field), `plum-soft` (Parent Studio panel) | unchanged; a panel fill is never a card tint and never carries body text below 4.5:1 |

### 1.1 Token inventory and job (values live only in the contract)

| Token | Job | Never |
|---|---|---|
| `paper` | route and reading surface | a card or plate flood in print |
| `paper-raised` | inputs, media frames, popovers, aside cards | a second page surface behind a card |
| `ink` | primary text, the plate head rule, the shelf ledge | a large fill block |
| `ink-soft` | captions, secondary text, labels | body prose |
| `rule` | hairlines, frames, the route spine, not-started edge | a state hue |
| `accent` | path, links, Textbook mode; the one subject accent for astronomy art | a card fill or heading colour |
| `accent-soft` | selected row | a card tint |
| `field` | evidence, Guided mode, notes; one subject accent for sourdough art | success copy without a word |
| `ochre` | review due, Field Quest, checkpoints, the Game progress fill | decoration, or a plate colour |
| `coral` | attention and errors only | a mode hue, a subject accent, a decorative mark |
| `lamp` | brand fill, primary action, seal arc, lantern light | text on `paper` (1.83:1 in light) |
| `lamp-soft` | hero field, checkpoint panel, plate ground flood | body-text background below 4.5:1 |
| `on-lamp` | text on a `lamp` fill only | any other surface |
| `plum` | Parent Studio identity | any learner surface |
| `plum-soft` | Parent Studio panel | a card tint |

Contrast is not re-derived here: `contracts/cb.tokens.v2.json` carries the gated pairs and
`tests/test_desktop_tokens.py` computes them on the shipped values. A new pair is a new contract
entry, not a local override.

---

## 2. Global Home (F1)

### 2.1 Purpose and rule

Home answers one question — *what do I want to learn now?* — and it is a **threshold, not a
dashboard**. It is also **not course-bound**: no Continue hero, no Japanese scene, no course hero.

### 2.2 Composition, measured

Wide (≥1049), top to bottom:

| Band | Height | Content | Rule |
|---|---|---|---|
| Header | 64px | brand mark (20px seal ring + wordmark) at the left; nav `Home · Courses · Workshop · Parent Studio`; settings (icon + label) at the right | one 1px `rule` under the header, full bleed; no filled control in the header |
| Invitation | 320px | display serif `What will you learn next?`, max 20ch, centred; one `lead` line `Pick a course, or chart a new one.`; gap 24px; primary `Start a new course`; `Browse the library` as a text link 12px under it | centred within the 1120px content column; no illustration inside the invitation band |
| Shelf head | 40px | `Your courses` (`heading`, sentence case) at the left; `See all` (`meta` link) at the right, aligned to the shelf's right edge | one uppercase element per region only — none here |
| Shelf | card + 48px ledge | 4–6 cards, horizontally scrolling, bottom-aligned on the ledge; fox at the right end | geometry in §2.3 |
| Footer space | — | nothing | the first viewport ends at the ledge; no stat strip, no second shelf |

Content column: `max-width: 1120px`, centred. Gutters: 32px at ≥1049, 24px at 900–1048, 16px at
≤460. The header rule and the shelf ledge bleed to the viewport; everything else stays in the
column.

Annotated diagram of these bands and measurements: `docs/gm-visual/diagrams/home-composition.svg`.

**The invitation is the one centred band in the product.** It is centred because the concept reads
as a threshold, not because the layout is a template: the shelf below it is left-anchored and the
fox closes the right edge, so the optical centre of the page is never the centre of a card grid.

### 2.3 Shelf geometry

| Property | ≥1049 | 900–1048 | ≤460 |
|---|---|---|---|
| Card width | 260px | 220px | `min(78vw, 320px)` |
| Cover | 260×173 (3:2) | 220×147 (3:2) | 78vw × 0.667 |
| Type block | 88px fixed | 88px | auto, min 88px |
| Gap between cards | 16px | 12px | 12px |
| Visible cards | 4 full + 1 clipped by the gutter | 3 full + 1 clipped | 1 full + 24px peek of the next |
| Track | horizontal scroll, `scroll-snap-type: x mandatory`, snap-start on card | same | same |
| Ledge | 2px `ink` rule across the column, 1px `rule` 8px below it | same | 1px `rule` only |
| Fox plate | 64px tall, standing on the ledge, 24px right of the last card | 56px | hidden |

Cards are **bottom-aligned to the ledge** — they stand on it. The ledge is a horizon line, not a
shelf graphic: no wood texture, no shadow, no perspective, no bracket. The two rules at 2px and
1px give the lip; that is the whole substitute for the concept's drawn shelf.

`See all` is a `meta` text link, right-aligned **above** the ledge; it is never a card and never a
button. `Start a new course` in the invitation band is the only filled control on the screen, and
therefore the only create affordance. There is no second create control on the shelf.

### 2.4 What is deliberately **not** copied from F1

| Concept element | Why not | Substitute |
|---|---|---|
| Garbled card microcopy (`Japaneee`, `Sourdnomg`, `THIFFESOOD`) | a generated still is not product truth | real course titles and real state from `library.list` |
| Five-star ratings, review counts | invented data; no rating exists in the backend | mode badge + last touched + next stop, or nothing |
| `XP` / `NEW` badges on library cards | XP is Game-only and never on global Home (§7) | none; Home has no game chrome |
| Two same-weight orange actions (`Start a new` link + button) | hierarchy defect | one `lamp` primary, one `meta` text link |
| Wooden shelf with drop shadow | shadows are forbidden; wood is a literal texture | 2px `ink` ledge + 1px `rule` lip (§2.3) |
| Pill-shaped primary button (999px) | 999px is reserved for state pills | `lamp` fill, `2px` radius, `meta` 600 label, `on-lamp` text |
| Card corner radius ~10px and card shadows | radius scale is 0/2/999/50%; shadows forbidden | `2px` radius, `1px rule` border, `paper-raised` fill |
| Serif/green nav wordmark highlighted in green | `field` is a mode/evidence hue, not a nav accent | nav is `ink`; active item is a 2px `ink` underline plus `aria-current` |

### 2.5 Home states

| State | Rendering | Forbidden |
|---|---|---|
| First open, no courses | invitation band unchanged; shelf band becomes a **blank plate**: `paper-raised`, 1px `rule`, 240×120 contour ghost at 20% ink on the right, headline `No courses yet.` and one `meta` line `Start with a goal, or browse a ready-made course.` | fake path, sample cards with invented titles, a disabled shelf |
| Loading | invitation band painted immediately; shelf band keeps its exact height and shows one `caption` line `Reading your courses…` in `ink-soft`; no shimmer, no skeleton, no spinner over the ledge | empty-state copy before the read resolves |
| Error | shelf band keeps its height, one `coral` 8px square + `meta` `Your courses could not be read.` naming the failed read (`library.list`), one `Retry` text button; invitation and primary action stay live | showing "no courses" for a failed read |
| Offline | one banner directly under the header: 1px `rule`, `ink-soft` `meta` `You are offline. Opening a course already on this device still works.`, no dismiss button | hiding the shelf, blocking the primary |
| Shelf overflows | horizontal scroll with a 24px right-edge fade drawn as a `paper`→transparent mask (mask, not gradient fill on a surface) or a 2px `rule` scrollbar | wrapping into a grid |
| One course only | card stays 260px, left-anchored; the ledge continues empty to the right with the fox on it | stretching the card |

### 2.6 Home accessibility contract

- Reading order: `h1` invitation → primary → secondary → `h2 Your courses` → cards in DOM order →
  `See all`. The fox plate is `aria-hidden` and never carries state.
- The whole card is one link (`<a>` wrapping the card body); `Open` is that link's visible label,
  not a second nested control.
- Focus ring: 2px `accent` offset 2px, visible on `:focus-visible` only.
- At 200% root text: card width grows with the text (no fixed height on the type block), the shelf
  scrolls, the primary action never clips, and the invitation band grows instead of truncating.
- Reduced motion: `scroll-behavior: auto`; no card lift, no fox idle.

---

## 3. Type roles over the shipped six steps

No seventh step. Every authored size below resolves to `CB_TYPE_SCALE_JSON`.

| Role | Step | Stack | Weight | Track | Case | Where |
|---|---|---|---|---|---|---|
| Invitation headline | `display` | serif | 600 | −0.015em | sentence | Home invitation only |
| Course title | `display` | serif | 600 | −0.015em | sentence | course home, ≤20ch, max 2 lines |
| Plate / section title | `heading` | serif | 600 | −0.01em | sentence | lesson header, studio panel title |
| Card / aside title | `lead` | serif | 600 | 0 | sentence | shelf card title, Continue card next-stop |
| Lede | `lead` | serif | 400 | 0 | sentence | course home end-capability line, invitation subline |
| Reading | `body` | serif | 400 | 0 | sentence | lesson prose, parent guide prose, 66ch |
| UI body | `body` | sans | 400 | 0 | sentence | control labels, list rows, form help |
| Meta | `meta` | sans | 400/600 | 0 | sentence | last touched, next stop, counts, captions under plates |
| Caption / label | `caption` | sans | 400/600 | 0.12em when uppercase | sentence or UPPERCASE | provenance row, source line, one label per region |
| Numeric | `meta`, tabular | sans | 600 | 0 | as written | `3 of 6`, timestamps, XP chip |

Rules: at most **one** uppercase `caption` element per region; buttons and chips are sentence case;
weights are 400 and 600 only; no `px` font-size; `1 of 4` is a count, never `25%` unless the
backend recorded a percentage.

Japanese: reading body stays in the serif stack so CJK falls back to a CJK serif; romaji uses
`body`; furigana/romaji scaffolds use `caption` in `ink-soft`, never a colour. L0 material shows
romaji; scaffolds fade but are not removed by the visual layer — the lesson document owns that
content.

---

## 4. Course home / trailhead (F2 + F3)

### 4.1 Rule

Course home is the **only** course-bound screen and the only place F2's Japanese scene belongs.
Global Home never borrows it. Every course, in either mode, has this screen.

### 4.2 Composition, measured

12-column grid inside the 1120px column, 24px gutters.

| Region | Columns | Content |
|---|---|---|
| Course header | 1–12 | breadcrumb `Courses / <course>` (`meta`, one link); course title (`display`, ≤20ch); mode badge; `Course settings` as a quiet text button at the right |
| Route spine | 1–2 | vertical `CheckpointPath`: one continuous 1.5px `rule` route, nodes 28/40/56px, current node `aria-current="step"`, state words in `caption`. 3px dot + 2px underline in the mode hue only |
| World hero | 3–9 | 16:9 plate, 2px radius, 1px `rule`, textless art only; the end-capability line sits **below** the plate in `lead`, never on top of it |
| Aside / Continue card | 10–12 | `paper-raised`, 1px `rule`, 2px radius, 24px padding: `caption` label `CONTINUE THE TRAIL`; next-stop title (`lead`); one `body` sentence naming what the learner will do; `Continue` primary (`lamp`); `Open section` as a text button; if the next step is a review the primary label is `Start the review` |
| World freshness line | 3–9 | only when `world.state = stale`: `meta` + `ink-soft`, `This world was built for the previous plan`, one `Review the world` text button |
| Take-home strip | 3–9 | `Take this with you` as a quiet text button; opens the homework generator (GM-008); never a second filled control |

F2's proportions (progress rail : hero : aside ≈ 1 : 4.5 : 2.5) become **1 : 3.4 : 1.4** at 1120px,
because the aside must hold a real primary action at `meta`/`lead` sizes and the 2-column rail is
already the minimum that can carry a node plus a state word. This is the one proportion the spec
deliberately widens; it is recorded so a reviewer scores it against the number, not the photo.

**Mode hue placement.** Exactly one mode hue is visible per page: `accent` (Textbook), `field`
(Guided), `ochre` (Field Quest). It appears as a 3px dot on the mode badge, a 2px underline under
the current nav item, and the current route node's 2px ring. Never on a card fill, never on a
button, never as a heading colour.

At 900: spine collapses to a horizontal strip above the hero (nodes in a row, same sizes at 40/32/24);
aside moves below the hero, full width of columns 1–12 with a 32px gap; header stays.
At 460: header stacks (title, then badge + settings on one row); hero becomes 3:2; Continue card is
the **first** block under the title and before the hero; spine becomes a vertical list under the
card; text measures 32ch.

### 4.3 States

| State | Rendering |
|---|---|
| No approved world (Textbook course) | hero region is a **paper plate**: `paper-raised`, 1px `rule`, one `heading` initial or section number set in type, one `caption` line `This course has no world art.` Never a grey box, never a stock image |
| World job running | hero region keeps its aspect ratio, one `caption` `Building the world for this course…`, the course remains fully usable in Textbook; no shimmer |
| World partially failed | hero shows the approved plates that exist; one `coral` 8px square + `meta` naming the missing roles (`hero`, `cover`, `section 3`); one `Retry missing plates` text button; no fabricated file |
| World stale | §4.2 freshness line; lessons stay readable |
| Plan not yet approved | Continue card is replaced by `caption` `PLAN IN REVIEW` + the end capability; one `Review the plan` primary |
| Loading | header + spine geometry painted; hero and aside hold their boxes with one `caption` `Reading the trail…` |
| Error | as Home §2.5: named failed read, `Retry`, primary stays live if the backend recorded a next step |
| Course end | Continue card becomes `caption` `COURSE COMPLETE` + recorded evidence count + one `Review a section` text button; no confetti, no score |

---

## 5. Card anatomy

One card grammar for shelf cards, section cards, collectible cards and studio concept cards.

```
┌──────────────────────────────── 2px radius, 1px rule ────────────────────────────────┐
│  COVER — 3:2, textless plate, 2px radius, no inner border, no shadow                  │
│  (world cover, Press Plate, or paper cover with a subject mark)                       │
├───────────────────────────────────────────────────────────────────────────────────────┤
│  COURSE TITLE · lead 600 serif, max 2 lines, ink                                        │
│  meta · ink-soft · last touched / next section                                         │
│  ──────────── 1px rule, 16px wide (optional divider) ────────────                      │
│  [mode badge]  Game / Textbook        `Open` meta link, ink                            │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

| Part | Rule |
|---|---|
| Cover | 3:2; world cover, Press Plate, or a **paper cover**: `lamp-soft` field + one `lamp` band + the course initial in `display` serif `ink`. Provenance is required for any image (§ `docs/GM-ART-PLATES.md`) |
| Title | `lead` 600 serif, `ink`, max 2 lines, ellipsis at the second line; never uppercase |
| Meta line | exactly one: last touched date, next section, or `Not started`; never two facts joined by `·` |
| Mode badge | `caption` UPPERCASE, `paper-raised` fill, 1px `rule`, 2px radius, 3px mode-hue dot before the word; no mode badge on a course with `presentation_mode = null` |
| Action | one `meta` `Open`; the whole card is the target; no nested `⋯` menu on a shelf card |
| State | `rule` 1px top edge for "not started"; `ochre` 2px left edge for "review due"; `field` 2px left edge for "evidence recorded"; all three always beside a word |
| Forbidden | star ratings, review counts, `NEW`/`HOT` flags, XP, progress percentages, avatars of invented learners, cards inside cards |

**Seal and stamp language (F4).** One seal per surface at most: a 48px `50%` ring, 2px `lamp`
(or `plum` in Parent Studio) arc, no letters inside. Badges earned in Game mode are `50%` discs
with a Codicon and a `caption` name, revealed only by a real action; they are never on Home.

---

## 6. Game header (Game mode only)

The play layer is a **small added layer**, never a replacement for the course path or the check.

```
[course title · display]        [Level 3] [240 XP] [Game progress ▓▓▓▓░░░░ 3 of 8]   [settings]
```

| Element | Rule |
|---|---|
| Level chip | `paper-raised`, 1px `rule`, 2px radius, `caption` `LEVEL` + `meta` 600 number. Cosmetic only |
| XP chip | `meta` 600 tabular + `caption` `XP`; awards only from a real action id; never a grade |
| Game progress | 3px track `rule`, fill `ochre`, `meta` label `3 of 8` — a count of assigned steps, never a percentage of skill |
| Placement | right end of the course header row, 32px tall, on one baseline; it may push the title's measure but never pushes `Continue`, the current objective or the check out of the first viewport |
| Hidden | entirely absent in Textbook, Guided, Parent Studio, packs and exports. `Game feedback` off hides chips and any XP motion without changing the course |
| Forbidden | `mastery %`, `proficiency`, lives/hearts, streak flames with loss framing, purchase/energy/loot |

The concept frames' `240 XP`, flames, `Official Order` seal and `2 of 5 proofs collected` are
**not data**. The shipped header shows the real numbers or nothing.

---

## 7. State grammar for every screen

Every screen in the matrix (`docs/visual-review/MATRIX.md`) declares these states. A missing state
is a review failure, not a polish item.

| State | Universal rule |
|---|---|
| Empty | keep the screen's geometry; say what is missing and give exactly one next action |
| Loading | hold the boxes; one `caption` line naming the read (`Reading the trail…`); no shimmer, no skeleton, no spinner over content |
| Error | name the failed read in learner words; keep every action the backend already supports; one `Retry` |
| Offline | one banner under the header; local reads stay; no silent empty state |
| Partial | name exactly which part is missing; never render a fabricated substitute |
| Stale | keep the last approved content visible with one line of provenance |
| Rejected | say what was rejected and by which gate, in learner words; one route back |
| Over-quota / unavailable | say the capability is unavailable and what still works (e.g. `Game mode is not available right now… The course stays in Textbook mode`) |

Colour in states: `coral` for error/attention only, `ochre` for due/checkpoint, `field` for
recorded evidence. **Every state hue sits beside its word**; no legend, no colour-only meaning.

---

## 8. Textless-art rules (binding on plates, not history)

1. **Textless.** No letters of any script, digits, logos, watermarks, UI chrome, frames, fake
   window bars, rating stars, badges with glyphs. Real text is DOM.
2. **Subject-specific.** ≥2 motifs from the course's plan/sources. The anti-generic swap check in
   `docs/GM-SUBJECT-WORLDS.md` must fail the plate for an unrelated subject.
3. **One kit.** Hero, cover and section plates share one palette path, one medium, one line weight
   and one light direction.
4. **Quiet field.** Compose for the type that will sit over or beside it: at least 35% low-contrast
   area, no essential information only inside the image.
5. **Never authority.** No plate may carry a procedure, torque, clearance, dosage, sequence,
   measurement, wiring value, hazard callout or answer. Those are text, deterministic SVG, or a
   sourced figure with permission.
6. **Provenance.** Every plate has a provenance row: provider, model, prompt hash, style hash,
   generation time, `role = orientation`, licence. A host-composed plate records the generator
   instead of a provider.
7. **Accessible.** Alt text plus a one-line text equivalent; the page works at 460px, 200% text,
   keyboard only, reduced motion, images disabled.
8. **Useful.** If the plate could be removed without changing orientation, it is rejected.

Art plates approved for use sit in `docs/GM-ART-PLATES.md`; the reference boards in
`docs/gm-visual/boards/` are host-composed, textless and CC0.

---

## 9. Where a layout may be adjusted without losing the concept

The manager may approve these without a re-review. Anything else is a concept-parity failure.

- Card width ±20px and gap ±4px, as long as 4 full cards and a clipped fifth fit at 1049px.
- Invitation band height 280–360px, as long as the shelf head still enters the first viewport.
- Route-spine column 2–3 of 12, as long as the current node is visibly larger than the next.
- Aside card width 20–26% of the content column.
- Section titles may wrap to 2 lines; they may not shrink below `heading`.
- Any spacing value move inside the 4/8/12/16/24/32/48/64 scale.
- A state may be shown in a sheet at 460px instead of inline, as long as it is the same state.

**Not adjustable:** the token table, the six type steps, one primary per screen, the absence of
shadows/gradients/card-in-card, the textless rule, the fox as the only mascot, the course-path
hierarchy under any game layer.

---

## 10. Acceptance for this document

A visual reviewer must be able to score every dimension in
`docs/GM-CONCEPT-PARITY-RUBRIC.md` using only this spec plus a screenshot: every number needed
(width, height, gap, measure, size step, hue name, radius) is above, and every screen has a named
concept frame and a state list. `tests/test_gm_visual_spec.py` checks the mechanical half:
token names/values referenced here match `contracts/cb.tokens.v2.json`, every font size named is
one of the six shipped steps, every screen in the matrix has a frame and a non-empty state list,
and every reference plate contains no `<text>` element.
