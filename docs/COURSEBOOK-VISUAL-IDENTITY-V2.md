# Coursebook visual identity v2: Atlas Lamp

Status: frozen design proposal for implementation. Read-only with respect to product code.
Date: 2026-11-07.
Owner: Vellum (Desktop UI). Decision owner for departures: DeseretSaint.

This document replaces the visual direction of `docs/INK-FIELD-NOTES.md` while keeping its
scoped-token seam, its honesty rules and its component inventory. It does not change the plugin
architecture, the RPC surface, the pack format or the teaching model.

Evidence base:

- `docs/INK-FIELD-NOTES.md` (token contract v1, scope seam, contrast floor, type rhythm).
- `docs/FIELD-DESK-RESEARCH.md` (path, position, one next move, honest evidence states).
- `desktop/plugin.js` token layer at 7807, `WorkspaceShell`, `FieldRail`, `MediaFrame`,
  `ContinueCard`, `PathList`, `TextbookView`, `LessonDocumentView`, `FieldQuestView`,
  `Studio*` views and `CoursebookPage`.
- Live captures in `audit/visual/`: `m2-field-desk/01-real-light-wide.png`,
  `m2-field-quest/01-quest-light-wide.png`, `m1-guided-authoring/02-textbook-light.png` and
  `05-guided-light.png`, `m3-pronunciation/01-studio-available-light-1280.png`.
- Round-3 live captures landed in `audit/ux/round3/` while this card was in progress (dark, host
  zoom 0.896, viewports 1049/900/460 CSS; `captures.json` records the plugin sha, the text head
  and the overflow metrics). They are the primary before evidence for Field Desk, All Courses,
  Library, Parent Studio, New Course, Course Detail and the Textbook section page.
- Code anchors used to confirm behavior: `CoursesView` (3144), `LibraryView` (3588), `FirstRun`
  (1011), `CourseDetail` (12313), `OverviewView` (10533).

---

## 1. The direction

Name: **Atlas Lamp**.

Promise: Coursebook makes a course feel like a place you are travelling through: one lit page, one
marked route, and an honest record of the ground you have already covered.

Three ideas carry the identity:

1. **The lit page.** A warm paper surface with one flat field of light behind the thing that
   matters now. This is the branded moment. It is a color field, not a gradient, not a card.
2. **The marked route.** Learning is shown as a surveyed path: a thin spine, numbered nodes, a
   current position, and a legend that is just the state words. The path is the product.
3. **The honest record.** Evidence is a tally of real states, never a ring, a streak or a
   percentage. The visual language repeats what the backend recorded and nothing more.

Why this and not "modern": the current shell is readable but anonymous. Its weakness is not a
missing shadow or a missing gradient. It is that every element has the same weight, every action
looks secondary, and the course has no visual identity beyond its title. Atlas Lamp fixes that with
three cheap, durable moves: a serif reading voice, one flat lamp field per screen, and a route that
looks like a route. It stays inside a 15-token table and one ESM file.

Continuity with Ink & Field Notes:

- Same scoped seam: `cbScopeStyle(mode)` paints `--cb-*` on the route and pane roots only.
- Same refusal of gradients, shadows, glass and a second stylesheet.
- Same honesty vocabulary: `not_started`, `introduced`, `independent_evidence`,
  `delayed_evidence`, `review_due`, `needs_review`.
- Same components from the SDK. No custom button, input or icon set.

What changes: the base palette warms and deepens, four hue families and one on-color join the
table, the display and reading voices become serif, the Field Desk and Course Detail gain a lamp
field, and the path becomes a spine. The result should read as a learning product at arm's length,
before a single word is read.

### Concurrent work observed during this card

While H-81 was running, the shared working tree gained an uncommitted redesign that names itself
`field-atlas` in `contracts/cb.tokens.v1.json` (version 2 in place, 11 tokens adding `accent-ink`,
terracotta accent, an SVG curved-path cover and a custom primary button). It was not authored by
this card and is not this spec.

It does not satisfy this freeze, for four concrete reasons:

1. It mutates `cb.tokens.v1.json` in place instead of adding v2 beside it, so the historical
   contract and its test comparison lose their reference point.
2. It has no `lamp`, `lamp-soft`, `on-lamp` or `plum`, so there is no brand field, no Parent Studio
   identity and no color that is reserved for "the thing to do now".
3. It uses `accent` for identity, primary action and mode at once, which collapses three jobs into
   one hue and makes state and brand indistinguishable.
4. Its motif is a curved path illustration rather than the deterministic seal and route spine, so
   course identity is not derivable and the path is decorative rather than structural.

Do not merge both directions. The implementer either adopts Atlas Lamp as frozen here, or brings a
written counter-proposal to DeseretSaint naming which of the four points it rejects and why. The
uncommitted `field-atlas` edits must not be attributed to H-81.

---

## 2. Palette

### 2.1 Tokens

15 tokens. Ten are the v1 names, carried forward with new values where needed. Five are new:
`lamp`, `lamp-soft`, `on-lamp`, `plum`, `plum-soft`.

| Token | Job | Light | Dark |
|---|---|---|---|
| `paper` | route and reading surface | `#F7F1E4` | `#131210` |
| `paper-raised` | inputs, media frames, popovers | `#FFFCF3` | `#1D1B16` |
| `ink` | primary text | `#1A1713` | `#F5EFE1` |
| `ink-soft` | captions, secondary text, labels | `#5C5347` | `#B9AE9A` |
| `rule` | hairlines, frames, spine | `#D7CBB4` | `#3D382D` |
| `accent` | path, links, Textbook mode | `#2C4A8C` | `#A8C0F2` |
| `accent-soft` | current row, selection | `#E2E8F7` | `#222A3B` |
| `field` | evidence, Guided mode, notes | `#2F6047` | `#9FC69A` |
| `ochre` | review due, Field Quest, checkpoints | `#7B4B0A` | `#E0B25C` |
| `coral` | attention and errors only | `#9C2E1C` | `#EA9480` |
| `lamp` | brand fill, primary action, seal arc | `#E8A93A` | `#EFC06B` |
| `lamp-soft` | hero field, checkpoint panel | `#FBEBCB` | `#33290F` |
| `on-lamp` | text on a `lamp` fill only | `#1A1713` | `#131210` |
| `plum` | Parent Studio identity | `#6A3E74` | `#CDA0D8` |
| `plum-soft` | Parent Studio panel | `#F0E6F3` | `#2E2434` |

### 2.2 Contrast proof

Computed on the proposed values by `audit/ux/round3/concepts/contrast.py`; raw output is in
`contrast.txt` in the same directory. Every pair passes in both modes.

| Pair | Light | Dark | Floor | Why |
|---|---|---|---|---|
| `ink` on `paper` | 15.87 | 16.33 | 7.00 | reading text, AAA body |
| `ink` on `paper-raised` | 17.41 | 15.01 | 7.00 | reading text in a raised frame |
| `ink-soft` on `paper` | 6.70 | 8.54 | 4.50 | secondary text and captions |
| `ink-soft` on `paper-raised` | 7.35 | 7.85 | 4.50 | secondary text in a raised frame |
| `accent` on `paper` | 7.57 | 10.24 | 4.50 | path, links, Textbook mode |
| `field` on `paper` | 6.47 | 9.82 | 4.50 | evidence, Guided mode, notes |
| `ochre` on `paper` | 6.54 | 9.53 | 4.50 | review due, Field Quest, checkpoints |
| `coral` on `paper` | 6.61 | 8.06 | 4.50 | attention text, never decoration |
| `plum` on `paper` | 7.30 | 8.57 | 4.50 | Parent Studio identity |
| `on-lamp` on `lamp` | 8.65 | 11.07 | 4.50 | label on the primary action |
| `ink` on `accent-soft` | 14.56 | 12.53 | 4.50 | text on a selected row |
| `ink` on `lamp-soft` | 15.18 | 12.50 | 4.50 | text on the hero and checkpoint field |
| `ink` on `plum-soft` | 14.73 | 12.92 | 4.50 | text on a Parent Studio panel |
| `ink-soft` on `accent-soft` | 6.15 | 6.55 | 4.50 | caption on a selected row |
| `ink-soft` on `lamp-soft` | 6.41 | 6.54 | 4.50 | caption on the hero field |
| `ink-soft` on `plum-soft` | 6.22 | 6.76 | 4.50 | caption on a Parent Studio panel |
| `paper` on `field` | 6.47 | 9.82 | 4.50 | glyph on a done node |
| `paper` on `accent` | 7.57 | 10.24 | 4.50 | glyph on an active node |
| `rule` on `paper` | 1.43 | 1.61 | 1.25 | hairline visibility, non-text |
| `rule` on `paper-raised` | 1.56 | 1.48 | 1.25 | hairline on a raised frame, non-text |
| `lamp` on `paper` | 1.83 | 11.07 | 1.25 | primary fill edge; a 1px `on-lamp` border also defines it |

Three consequences that the implementer must respect:

- `lamp` is never text on `paper`. In light mode it is a 1.83:1 fill. It carries `on-lamp` text or
  nothing.
- Filled state marks always carry `paper` glyphs. `field` and `accent` invert correctly between
  modes, so one rule works in both.
- `coral` never becomes a mode hue. It means error or attention, full stop.

### 2.3 Color has three jobs, never four

| Job | Hues | Rule |
|---|---|---|
| Identity | `lamp`, `plum` | Brand field, seal arc, Parent Studio band. At most one identity hue on screen. |
| Mode | `accent` Textbook, `field` Guided, `ochre` Field Quest | Only the three reading modes get a hue. A 3px dot and a 2px underline, nothing more. |
| State and progress | `field` evidence, `ochre` due, `coral` attention, `rule` not started | One hue per state, always beside its word. No legend needed. |

At most two hues plus `coral` may appear in one viewport. A screen with five colored chips is a
defect, not a design.

### 2.4 No gradients, argued

The v1 rule stays. Flat fields are not a limitation here; they are the identity. A gradient would
break three things at once: the token table stops being a finite set of gated values, dark paper
bands visibly at 2x on OLED, and forced-colors mode flattens gradients into mud. The lit-page
metaphor works because the field is one color with one hard edge and one 3px rule. Depth comes from
`paper` against `lamp-soft`, a 1px `rule`, and the serif scale. No gradient, no shadow, no blur.

### 2.5 Contract proposal (not applied)

Proposal: add `contracts/cb.tokens.v2.json` next to v1 with `version: 2`,
`name: "atlas-lamp"`, the 15 token names and the 21 gates above. Update
`tests/test_desktop_tokens.py` to read v2, assert 15 names, assert the byte-for-byte table, and
compute every gate. Keep v1 on disk as history; do not mutate it. The shipped module still holds
one JSON literal (`CB_TOKENS_JSON`), so the "no hex outside the literal" test keeps its meaning.

No code in this card. The v2 file is a proposal the implementer creates in phase 0.

---

## 3. Typography

The host cannot ship a font file. The stack therefore uses only fonts the OS already has. A serif
display and reading voice is the single biggest identity change, and it costs nothing.

| Role | Stack | Size | Weight | Line height | Tracking | Case |
|---|---|---|---|---|---|---|
| Display | `ui-serif, Georgia, "Iowan Old Style", "Palatino Linotype", "Noto Serif", serif` | `clamp(1.75rem, 1.35rem + 1.6vw, 2.75rem)` | 600 | 1.04 | -0.015em | sentence |
| Section | same serif | `1.375rem` | 600 | 1.2 | -0.01em | sentence |
| Reading | same serif | `1.0625rem` | 400 | 1.65 | 0 | sentence |
| Lede | same serif | `1.1875rem` | 400 | 1.5 | 0 | sentence |
| UI body | `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif` | `0.875rem` | 400 | 1.5 | 0 | sentence |
| Caption | sans | `0.75rem` | 400 | 1.45 | 0 | sentence |
| Label | sans | `0.6875rem` | 600 | 1.2 | 0.14em | UPPERCASE |
| Numeric | sans, `font-variant-numeric: tabular-nums` | `0.8125rem`; hero counts `1.5rem` | 600 | 1.2 | 0 | as written |

Rules:

- Reading measure is `66ch` (`CB_MEASURE`), inside the 62 to 72 band. Body copy never exceeds it.
  Rail copy is `32ch`. Hero displays cap at `20ch`; section titles at `34ch`.
- One uppercase element per screen region. That is the label role. There is no second all-caps
  eyebrow, no all-caps button, no all-caps tab.
- Buttons and chips use sentence case. "Start the review", not "Start The Review".
- Weights: 400 and 600 only. No 700, no 300. The serif at 600 is the loudest thing on the page.
- Sizes are `rem` or `clamp` with a `rem` minimum. No `px` font sizes in the shell. A 200% root
  font change scales the whole surface, and the existing test that refuses `px` stays.
- Japanese: reading body stays in the serif stack so CJK falls back to a CJK serif. Romaji sits in
  the reading role. Furigana and romaji scaffolds use the caption role above the term, `ink-soft`,
  never a color. No ruby markup is invented; the existing lesson document owns that content.
- Numbers are not decorative. `1 of 4` is numeric role; never "25%" unless the backend recorded a
  percentage. It does not.

---

## 4. Component language

### 4.1 Geometry

- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64. Section rhythm is 24 or 32, not 20.
- Radius: 0 on fields and sections, `2px` on controls and chips, `999px` on state pills, `50%` on
  nodes and seals. No other radius.
- Rules: 1px `rule` for structure, 1px `ink` for a plate head, 2px hue for an active tab or node,
  3px for the hero band and a note's left edge. No 4px decorative bars.
- Shadow: none. Elevation is `paper-raised` plus a 1px `rule`, never a shadow.
- Card in card: forbidden. A region is one surface. Group with a rule and space, not a nested box.
- Motion: none by default. Any hover transition is 120ms and only when
  `data-cb-motion="full"`. No transform, no parallax, no skeleton shimmer.

### 4.2 The course seal (distinctive motif)

A deterministic geometric mark, drawn as inline SVG in the plugin. No asset file, no external
dependency, no generated art.

Spec, on a `viewBox="0 0 96 96"`:

1. Outer square: `x=4 y=4 w=88 h=88`, stroke `ink`, width 1.6, fill none.
2. Arc: a quarter circle of radius 64 from the bottom-left corner, stroke width 7, in `accent`
   for a learner course or `plum` for a parent course. Never `field`, `ochre` or `coral`; the seal
   must not look like a state.
3. Meridian: one vertical and one horizontal hairline through the square at 38% strength (a
   `rule`-colored stroke, not opacity, so contrast stays predictable).
4. Mark: a filled circle of 7 at one of four quadrant stations, plus a 13 radius ring in the same
   identity hue. The station is `stableHash(course_id) % 4`, where `stableHash` is a deterministic
   character sum. It encodes nothing; it only prevents every course looking identical.
5. Corner ticks: two 1px strokes, 14 long, at the opposite corner.

Sizes: 96 hero, 64 compact hero, 40 list row, 28 shelf row. The seal replaces the current initial
stamp. It is decorative: `aria-hidden="true"`, and the course title is always adjacent as text.

### 4.3 The route spine (second motif)

The path is an `<ol>` with a 1px `rule` line at `left: 13px`, running from the first node to the
last. Each `<li>` is a 28px circle plus content plus a state pill.

- Not started: `paper` fill, 1.5px `rule` ring, `ink-soft` number.
- Started or introduced: `accent-soft` fill, 2px `accent` ring, `accent` number.
- Evidence: `field` fill, `paper` number, no ring.
- Review due: `paper` fill, 2px `ochre` ring, `ochre` number.
- Needs review or retry: `paper` fill, 2px `coral` ring, `coral` number.
- Current: the above plus a full-bleed `accent-soft` row tint (negative 14px margin) and a second
  1px `accent` ring at 8px offset. `aria-current="step"`.
- Phone: node 24px, line at `left: 11px`, number 10px.

The state word is always present in a pill. The spine is never the only carrier of state.

### 4.4 Evidence tally

A row of ticks, not a bar and not a ring. One tick per objective, up to 12; at 13 or more, the row
wraps rather than aggregating, because aggregation would invent a number.

- Tick: 22 x 6px desktop, 18 x 6px phone, 4px gap, radius 0.
- Paint: `field` for independent evidence, `ochre` for review due, `accent` for introduced or
  started, `rule` for not started. `needs_review` uses `coral`.
- Caption below, numeric role: `1 of 4 sections with evidence · 1 due`. If the count is zero, say
  `No evidence recorded yet`, never `0%`.
- The tally is `aria-hidden`; the caption carries the meaning.

### 4.5 Course cover and hero

The hero is a flat `lamp-soft` field with a 3px `lamp` top edge, no radius and no border. It spans
the content width, not the window.

- Grid: 96px seal, flexible text, 212px action column at wide. Gap 28px.
- Eyebrow: one label, `CONTINUE`, `START HERE` or `REVIEW DUE`.
- Display title: the section or course title, serif, 2 lines max.
- Facts: three numeric facts with captions. `Section 2 of 4 / Engine fundamentals`,
  `1 of 4 / With evidence`, `20 min / Recorded estimate`. Never a fourth invented fact.
- Actions: one primary (`lamp` fill, `on-lamp` text, 1px `on-lamp` edge), one secondary (1px `ink`
  border, transparent), one tertiary text link (`Why this is next`) that opens a `Tip` or details
  block.
- Parent course hero: `plum-soft` field with a 3px `plum` edge, seal arc `plum`, primary action
  still `lamp`. The adult knows immediately which arena they are in.
- At compact widths the seal and actions stack; the primary stays first in reading order.

### 4.6 Section row

No card, no full border.

- 1px `rule` top edge; 24px vertical padding; 40px number gutter; content; state pill at the end.
- Number: numeric role, `ink-soft`; `02` not `2.`, so rows align.
- Title: section serif, 1.125rem, 600; 2 lines max.
- Subline: one honest sentence or one metadata cluster, caption. Not both.
- State pill: 11px, 600, 1px border in the state hue, text in the state hue on `paper`.
- Interactive row: hover `accent-soft`, focus 2px `accent` ring. Selected row: `accent-soft` plus
  2px `accent` left edge. No chevron-only affordance; the whole row is the target.

### 4.7 Mission node

Same as the spine node, but the content is a mission block:

- Label: `MISSION` or `CHECKPOINT`, label role, `ink-soft` or `ochre`.
- Title: section serif, 1.1875rem.
- One line of what the learner does, UI body.
- Footer: one tertiary action, for example `Read this in Textbook`, inline. Not a full-width gray
  bar under every mission.
- Checkpoint: the check component, not a mission with a textarea bolted on.

### 4.8 Source chip and source row

- Chip: 1px `rule`, 2px radius, 11px 600, sentence case. Example: `Supported`, `Partial`,
  `Not assessed`.
- Status is text first. The border may use `field` only when the word is `Supported`; it never
  uses `coral` for a weak source, because weak support is not an error.
- Source row: title at UI body 0.8125rem, provenance caption below (`Authored here · 2 November`),
  status chip right. At most 4 rows in the rail, with the rest behind `All sources`.

### 4.9 Note

- 3px `field` left edge, 14px padding left, no fill.
- Excerpt: serif italic 0.9375rem, 1.5, 3 lines max.
- Meta: caption, `Saved from section 2 · 11 hours ago`.
- At most 3 notes in the rail; `All notes` links to Notebook.

### 4.10 Check

- Panel: `lamp-soft` field, 2px `lamp` top edge, 24px padding, no other border.
- Label: `CHECKPOINT`, label role, `ochre`.
- Question: section serif, 1.1875rem, 34ch to 48ch.
- Helper: caption, one sentence, says the check is shared across modes and is not a grade.
- Answer field: `paper-raised`, 1px `rule`, 2px radius, serif 0.875rem, min height 64px.
- Actions: primary `Submit answer`; secondary `Read the section again`; hint state as caption.
  When hints are absent, the caption reads `Hints are not available in this build`, not an
  engineering note about registration.
- Error: 1px `coral` left edge plus `coral` caption; never a red fill.

### 4.11 Empty state (blank plate)

- A 240 x 120 dashed 1px `rule` rectangle; a 40px seal ghost inside, stroke `rule`; no illustration.
- Display line: serif 1.5rem, 600, 28ch.
- Caption: one sentence, `ink-soft`.
- One primary action. If a second path exists, it is a tertiary link, not a second button.
- The plate is centered in the content column, not in the window.

### 4.12 Actions

| Kind | Fill | Text | Border | Hover |
|---|---|---|---|---|
| Primary | `lamp` | `on-lamp` | 1px `on-lamp` | `ink` fill, `paper` text |
| Secondary | transparent | `ink` | 1px `ink` | `lamp-soft` fill |
| Tertiary | transparent | `ink`, 1px underline offset 3 | none | `accent` text and underline |
| Destructive | transparent | `coral` | 1px `coral` | `coral` text stays, `lamp-soft` fill |
| Disabled | `paper` | `ink-soft` | 1px `rule` | none |

- Height 36px desktop, 44px phone. Horizontal padding 16px. Radius 2px.
- No opacity-based disabled state; opacity lowers contrast below the gate.
- Only one primary action per screen. The Field Desk hero owns it. A header repeat is removed.
- `ConfirmDialog` remains the only destructive confirmation.

### 4.13 Icons and ornament

- Icons: `sdk.Codicon` only, 16px, `currentColor`. No emoji, no second icon set, no icon font.
- Ornament: the seal and the spine are the only recurring motifs. Meridian ticks appear on the
  hero, the empty plate and the seal. Not on rows, not on chips.
- A section does not get an icon. A mode does not get an illustration. The type and the route are
  enough.

---

## 5. Screen by screen

Each entry states the current composition, then the target, then what is removed. "Current" is
grounded in the cited capture or function; where there is no capture, the code anchor is named.

### 5.1 Field Desk (`CoursesView` desk mode, `ContinueCard`, `PathList`)

Current: `Coursebook` route header with a subtitle, `New course` in the header, a three-item
segmented destination control, then a bordered Continue card: `CONTINUE`, `Section 1 of 4`, the
course and section titles, `Session length not recorded`, `Last touched 57 min ago`, a `NEXT ·`
line and two gray buttons (`Start the lesson`, `Open the section`). Three count blocks follow
(`4 SECTIONS`, `0 WITH EVIDENCE`, `0 DUE NOW`). The `YOUR PATH` list has four individually bordered
rows and a full-width `Show sources` button. The rail has an empty Field Notes block with
`Go to the current lesson`, and `ALL COURSES · 20` with three rows plus `+16 more courses on this
profile`.
Captures: `audit/ux/round3/01-field-desk-live.png` (dark, 1049) and
`audit/visual/m2-field-desk/01-real-light-wide.png` (light, wide).

Target:

- Route header shrinks to a 40px bar: wordmark at left, destination segmented control at right.
  The subtitle moves into the page and is not repeated.
- Hero: `lamp-soft` field, 3px `lamp` edge, 96px seal, `CONTINUE`, display title, three numeric
  facts, one primary action, one secondary, one `Why this is next` tertiary.
- Route: `The route` plate head with a count, the evidence tally and its caption, then the spine.
  The current row is tinted, not just left-bordered.
- Rail: Field Notes (max 3, no card), All Courses (max 3, seal plus honest next step).
- At 460 the hero stacks, facts become a 2x2 grid, actions go full width, primary first.

Removed: the second identical Continue button; the full-width `Show sources` bar; per-row borders;
the `Back to the Field Desk` text link when the desk is already the destination; the duplicate
subtitle in the header; `~20 min` as a floating metadata string (it becomes a labeled numeric fact
or `Session length not recorded`).

### 5.2 All Courses (`CoursesView` list mode, `CourseRow`)

Current: `Back to the Field Desk`, search, four filter chips, then a `REVIEW DUE` block that lists
the same course twice (`· 1 due`, `· 3 due`), each with its own `Review` button. Rows carry a
colored initial square (`OC`, `FR`, `RF`, `JA`, `KF`), a plan-profile subtitle (`A steady plan`,
`A little at a time`), a next-step line, `0 independent · 4 objectives`, badges such as
`Plan update` and `Source stale`, a full warning sentence, `From a local pack · v1.0.0`, and up to
three actions (`Open`, `Resume lesson`, overflow). A right-side callout, `No lesson chat open`,
competes with the list.
Capture: `audit/ux/round3/02-all-courses-live.png`.

Target:

- Plate head: `All courses` display plus `4 courses on this profile` numeric caption.
- One toolbar line: `SearchField` at left, one `SegmentedControl` filter at right. No second
  control, no separate due strip.
- When review is due, a single `lamp-soft` callout above the rows: `2 courses have review due`,
  with one tertiary `Review the first one` action. It does not list titles that the rows already
  show.
- The `No lesson chat open` callout leaves the list; the pane already explains binding, and the
  list must not host a second chat surface.
- Rows that share a title are distinguished by their plan profile and enrollment date, never by
  color alone. A row never shows more than one primary action.
- Row: 40px seal, serif title, one line of next step, state pill, mini tally plus
  `2 of 5 with evidence`, and a `Codicon` overflow menu for archive, delete, export.
- First run: the blank plate, not a paragraph stack.
- At 460 each row becomes two lines; the overflow menu stays a 44px target.

Removed: `pack_id`, pack version and revision strings from the row; the duplicate Resume button
(the row is the action); the repeated review-due titles; the "N of M shown" caption unless a
filter is active, in which case it becomes `Showing 12 of 30 · Clear filter`.

### 5.3 Library (`LibraryView`)

Current: the route header repeats the library lead sentence, and the body repeats it again. Two
entry panels (`Have a college syllabus?` and `Import a pack`) sit above the list. Filters are
`All / Bundled / Local`. The list repeats the same pack many times (the capture shows four JA rows
and more than ten KF rows), each with a colored initial square, source (`Local pack`,
`Authored here`), version when local, `N objectives` and a `Preview` button. A `What we check /
what we do not check` disclosure carries the trust copy; a detail panel opens on Preview.
Captures: `audit/ux/round3/04-library-live.png`, `05-library-import-pack-live.png`,
`06-library-syllabus-intake-live.png`.

Target:

- Plate head: `Library` display, caption `Packs on this profile`, one sentence of lead copy.
- Two source choices become filter chips: `Bundled`, `From someone else`. Import stays one primary
  `Import pack` and one secondary `Use my college syllabus` in the toolbar.
- Row: 40px seal, serif title, source chip, numeric `5 objectives`, and one line of provenance.
  `Preview` is the row action, not a separate button.
- When several enrollments share one pack, show one row per pack with `10 enrollments` and a
  disclosure that lists each enrollment and its date. The view groups rows; it does not merge or
  delete backend records.
- Detail: a plate with title, four trust rows (`Integrity`, `Automated checks`, `Human review`,
  `Model assessment`) each with its exact label and a one-line meaning. Licence and rights in a
  definition list. One primary `Add to my courses`, one secondary `Close`.
- Empty: blank plate plus one primary `Import a pack`.

Removed: the lead repeated in the route subtitle; version and pack-id badges from the row; the
second explanatory paragraph under the empty state; any merged trust score or "verified" badge.

### 5.4 New Course (`FirstRun`, three-step create flow)

Current, entry: `Learn something specific.` heading, a promise paragraph, three buttons of similar
weight (`Start with a goal`, `Use a course someone already made`, `Use my college syllabus`), a hint
paragraph, a progress paragraph and a support note.

Current, flow: three steps, goal first (H-170). Step 1, `What do you want to be able to do?`, asks
for the goal, offers the example gallery, and names the course from the goal (the learner can edit
the suggested name). Step 2, `How much course do you want?`, offers the three scope cards
(`A single lesson`, `A short course`, `A full course`) each with a `CHOOSE` label, a disabled
`Continue` until one is picked and the helper `Choose one option above to continue`, then
`What kind of course is this?` and an optional tuning disclosure. Step 3 is the plan review.
Capture: `audit/ux/round3/08-new-course-step1-live.png`, `09-new-course-step1-selected-live.png`,
`10-new-course-step2-live.png`, `11-plan-review-live.png`.

Target:

- Entry uses the start plate: `lamp-soft`, 3px `lamp` edge, 96px seal, label `NEW COURSE`, the
  display question, one caption, primary `Start with a goal`, and two alternative rows with one
  caption each. The syllabus row keeps its own wording.
- The flow keeps one question per plate. A 3-node spine (`01 Scope`, `02 Goal`, `03 Plan`) sits
  above the question, current node in `accent-soft`; the step number is numeric, not a badge.
- Step 1: scope cards become section rows, not cards: large `01/02/03` gutter, serif title, one
  line, `Choose` as a tertiary action at the end. Selected row gets `accent-soft` plus a 2px
  `accent` left edge and an `aria-selected` state. Continue is primary and disabled with a visible
  reason until a scope is chosen.
- Step 2: fields at 66ch. The four use modes become a 2x2 choice grid of radio rows with the same
  selected treatment. The parent redirect note uses `plum-soft`, one sentence, and one tertiary
  `Open Parent Studio`.
- Step 3: plan review uses the plan plate and the check-panel language for approval. One primary
  action (`Approve the plan`), one secondary (`Back`).

Removed: three equal buttons on the entry; `CHOOSE` as an uppercase label on every card; the
standalone `Choose one option above to continue` paragraph (the disabled helper sits under the
button); the duplicate parent note; the `STEP 1 OF 3` badge in favor of the step spine.

### 5.5 Parent Studio (`Studio*`, `STUDIO_VIEWS`, `STUDIO_TABS`)

Current, landing: the route header carries the long explanation and a global `New lesson plan`
button, then `Lesson plans you prepared for your child`, a long paragraph about how two plans can
describe the same lesson, and a list of identical rows (`Kitchen fractions for a 9-year-old`,
`Lesson plan for a child`, `updated 1 d ago`, `Open plan`). The duplicate titles are not
distinguishable.
Capture: `audit/ux/round3/07-parent-studio-live.png`.

Current, editor: a five-item segmented view picker (Brief, Plan, Pages, Export, Reflection), then
tab pickers for Parent guide, Learner pages, Answers, Audio and visuals, Sources. Plum appears
nowhere. Capture: `audit/visual/m3-pronunciation/01-studio-available-light-1280.png`.

Target:

- Landing: 3px `plum` band, label `PARENT STUDIO` in `plum`, display `Plans for your child`, one
  caption on the parent contract, one primary `New lesson plan`. Plan rows carry a `plum` seal,
  serif title, the first line of the brief as the distinguishing subtitle, `Updated 1 day ago`,
  and `Open plan` as the row action.
- Editor: step route (Brief, Plan, Pages, Export, Reflection) as a numbered spine, current node in
  `plum-soft` with a 2px `plum` ring. No SegmentedControl for five steps.
- Current step panel: `plum-soft` field, 1px `plum` top edge.
- Internal tabs stay text tabs with a 2px `plum` underline; `Answers` carries a `coral`-outlined
  `Adult only` chip.
- Primary `New lesson plan` moves into the landing plate head, not the global header.
- At 900 the spine becomes a horizontal stepper with the same numbers and words; no step is hidden.

Removed: the long route-header explanation and the duplicate-plan paragraph (both move to a `Tip`),
the segmented five-way picker, the global `New lesson plan` button that competes with the page,
repeated `Lesson plan for a child · updated 1 d ago` metadata with no distinguishing line, and any
learner-facing copy inside the parent arena.

### 5.6 Course Detail (`CourseDetail`, `OverviewView`)

Current: `All courses`, a colored course stamp with the plan profile (`A STEADY PLAN`), the title,
the next objective, `Export course…` and `Start lesson`, then a `View` label with a single select
showing `Overview`. Seven other surfaces (Textbook, Notebook, Quizzes, Plan, Evidence, Sources,
Export) are hidden in that dropdown. The body repeats `FIELD NOTES`, `Next ·` and `Next`, then
`CURRENT OBJECTIVE`, `REVIEW`, `RECENT EVENT` and `Course details`.
Captures: `audit/ux/round3/12-course-detail-live.png` and `11-plan-review-live.png`.

Target:

- Compact hero, 64px seal: title, `Section 2 of 4 · Textbook`, three numeric facts, primary
  `Resume the lesson` or `Start the lesson`, secondary `Open the textbook`.
- Two-tier navigation. Tier one: `Overview`, `Textbook`, `Notebook`, `Quizzes`, `Evidence`.
  Tier two, a text row or overflow: `Plan`, `Sources`, `Export`. The three reading modes keep
  their hue dot and 2px underline. Everything remains reachable in one click.
- Overview body: one `Next` block using the section row language, then the route spine of sections,
  then `Recent evidence` as a short list. No second hero.
- Pending-attempt and `needs_retry` notices use the check-panel language: `lamp-soft` for a pending
  attempt, `coral` 1px left edge for a retry, with the exact reason and one action. No toast-only
  message for a state the learner must resolve.

Removed: the single `View` select and the seven surfaces hidden behind it; the duplicate `FIELD
NOTES` and `Next` labels; `Export course…` as a header action (it moves to the secondary tier);
the route subtitle that repeats the hero; any optimistic "Continue" that implies progress the
backend has not recorded.

### 5.7 Textbook (`TextbookView`, `LessonDocumentView` textbook)

Current: a Field Notes identity paragraph, an honest count, a section index of rows with metadata,
then an open section rendered through the lesson document. The round-3 section page shows
`COURSEBOOK` as an eyebrow, the objective title, `Needs review · Last opened 21 hr ago`, three
isolated chips (`Lesson view`, `Textbook only`, `No chat`), an empty teaching block, five repeated
attempt rows with the same explanatory sentence, and a rail that prints raw values: `needs_review`,
`Evidence: Tell the difference`, `Attempts: 23`, four source cards with raw statuses such as
`model_assessed`, and an empty saved-notes block.
Captures: `audit/ux/round3/` Textbook section page, `audit/visual/m1-guided-authoring/02-textbook-light.png`
and `07-textbook-dark-460px.png`.

Target:

- Index: `Reading` plate head, tally plus exact caption, then section rows with `01` gutters,
  serif titles, one-line objective, state pill, mini tally. The old identity paragraph becomes a
  single caption: `66 characters per line. Evidence is named, never estimated.`
- Open section: 66ch serif reading column, 0.9375 to 1.0625rem, first paragraph lede in serif with
  a 2px `accent` left edge, block titles in section role, media framed with 1px `rule` and
  `paper-raised` only.
- Rail: This section (spine), Sources (max 4), Field Notes (max 3).
- Objective kicker above the lesson title: `Objective 2 · Trace the cause` in label role, `accent`.

Removed: repeated per-row metadata (`5 objectives`, revision, source counts); the identity
paragraph as a block; the per-block card borders; the duplicated evidence label beside the state
pill; raw enum values in the rail (`needs_review`, `model_assessed`) replaced by the state words
already defined; repeated identical attempt rows collapsed into one summary plus a disclosure.

### 5.8 Guided (`LessonDocumentView` guided)

Current: the same document with guided step blocks, checkpoint block, and a note that the mode is
guided. Captures: `05-guided-light.png`, `11-guided-light-460px.png`.

Target:

- Same reading column and typography as Textbook. Guided is a posture, not a skin.
- Left step margin at wide: a 28px node column with the current step number and a 1px `rule`
  connector, `field` hue because Guided owns green. At narrow it collapses into the section row
  number gutter.
- Each step: one paragraph of instruction, then the action. No separate card, no colored step
  backgrounds except the checkpoint.
- Footer of the open section: one `Next step` row with the current action, one tertiary
  `Back to the section index`.

Removed: the mode explainer paragraph; step borders; the duplicated checkpoint explanation; any
progress claim not in the document.

### 5.9 Field Quest (`FieldQuestView`)

Current: `FIELD QUEST` label plus a technical sentence about scoring and missions, right-aligned
`2 independent · 1 due · 4 missions, 1 checkpoint`, then four sections as a flat list with
`Read in Textbook` full-width bars, an active section marked by a thin blue left border, and a
checkpoint with developer copy about hints and answer registration.
Capture: `audit/visual/m2-field-quest/01-quest-light-wide.png`.

Target:

- Header: label `FIELD QUEST` in `ochre`, display `Four missions, one checkpoint` (derived from
  the outline, not invented), caption `Missions are the reading path. The checkpoint is shared
  with the other lesson views.`
- Three numeric facts: missions, checkpoints, due.
- Quest body: the route spine with mission nodes. Mission label, serif title, one line of action,
  a tertiary `Read this in Textbook` link at the foot. Checkpoint renders the check panel in
  `lamp-soft`.
- The due state uses `ochre`; a retry uses `coral` and names the reason.
- `Counts describe evidence the backend already recorded` moves into a `?` Tip beside the numeric
  facts. It is true and it stays available; it is not body copy.

Removed: full-width gray `Read in Textbook` bars under every mission; the lone left border as the
only current marker; the developer sentence `Hint and Show answer are not registered by this build
yet` (replaced by `Hints are not available in this build` when that is true); the scoring lecture
in the header.

### 5.10 Empty, error, offline and stale states

Current: `EmptyState` plus explanatory paragraphs and, in places, a support note with engineering
vocabulary. Captures: `audit/visual/m2-field-desk/08-empty-light.png`,
`09-loading-dark.png`, `10-error-light.png`, `11-backend-off-light.png`.

Target:

- Empty: blank plate (4.11), one display line, one caption, one primary. The first-run case uses
  the start plate (5.4) instead, because an empty profile is a welcome, not a failure.
- Loading: keep the SDK `Loader` with a specific label (`Reading your courses`), centered in the
  content column. No skeleton invented from fake shapes.
- Error: 1px `coral` left edge, section title in sentence case, caption with the human description,
  raw code in a `details` line, primary `Try again`, secondary `Open Capabilities`. Never an empty
  list in place of a failed read.
- Offline: a `lamp-soft` banner with a 3px `lamp` edge, one sentence on what still works and what
  pauses, no action unless a retry is meaningful.
- Stale: a 1px `rule` banner with a caption and a tertiary `Retry now`. It never looks like an
  error.
- Detached pane binding: a `lamp-soft` panel at the top of the pane with the exact reason
  (`This chat is not bound to a lesson`) and one action. It never shows another chat's lesson.

Removed: paragraph stacks under an empty state; engineering asides in body copy; red fills;
spinners without a label; any banner that steals focus or navigates on its own.

---

## 6. Responsive and accessibility

### 6.1 Breakpoints

The plugin cannot ship a media query, so layout is computed from the route's own measured width
(`useCbViewportWidth`) by a pure function. Replace `CB_WIDE_BREAKPOINT = 1024` with four named
ranges. The widths are CSS pixels, so a 200% zoom moves the surface into a narrower range as it
should.

| Range | Name | Layout |
|---|---|---|
| 1050 and above | `wide` | Route padding `clamp(24px, 4vw, 64px)`. Desk grid `minmax(0,1.3fr) / 20rem`, gap 56. Hero 96px seal + text + 212px actions. Rail beside main. |
| 900 to 1049 | `mid` | Rail stacks after main; hero becomes 64px seal + text, actions move below the facts in one row. Mode tabs wrap to two rows. Content max 100%. |
| 460 to 899 | `narrow` | One column everywhere. Hero 64px seal, facts 2x2, actions stacked full width, primary first. Section rows keep the 40px gutter; nodes 24px. Tables become definition lists. |
| below 460 | `phone` | 16px padding. Display floor `1.75rem`. Reading `1rem/1.6`. All controls 44px high and full width. Mode tabs wrap, never scroll horizontally behind an invisible affordance. Seal 40px. No fixed-height media. |

Order rules: the next action and the route always come before the rail in reading order. At narrow
widths the rail follows the main column; it is never hidden behind a control. A secondary tab must
never be the only way to reach a required surface at any width.

### 6.2 Focus

- `:focus-visible`: 2px solid `accent`, 2px offset, 2px radius on the ring. On a `lamp` fill the
  ring is 2px `on-lamp` plus a 2px `paper` gap, because `accent` on `lamp` is not 3:1.
- Focus is never removed on mouse click without a visible replacement.
- Tab order follows reading order: header, hero actions, route, rail. The route is one tab stop per
  row, not one per number and one per title.
- Dialogs use `ConfirmDialog` and trap focus; on close, focus returns to the invoking control.
- Background jobs never move focus and never navigate. A completed generation surfaces as a row
  state and, at most, a non-modal notice.

### 6.3 Contrast and color

- The 21 gates in 2.2 are the floor, not the goal. Body text is AAA in both modes.
- Color is never the only channel. Every hue has a word beside it; the tally has a caption; the
  seal is decorative.
- Forced-colors: structure survives because it is built from 1px borders, `<ol>`, headings and
  text. No background-only affordance.
- Disabled controls use real tokens, not opacity, so their labels remain readable.

### 6.4 Motion

- Default: no transitions, matching the current shell.
- If a 120ms background transition is added, it is gated on `data-cb-motion="full"`. Reduced motion
  gets the end state immediately. No transform, no scale, no shimmer, no autoplay.
- Loading uses the SDK `Loader` with a text label; there is no decorative animation.

### 6.5 Semantics and copy

- One `h1` per route, `h2` per plate, `h3` per section. No skipped levels.
- Mode navigation uses `role="tab"` with `aria-selected`, or a plain nav with `aria-current="page"`
  if tabs would imply panels that do not exist. The implementer chooses one and tests it.
- State pills are text; the spine uses `aria-current="step"` on exactly one item.
- Copy is sentence case, no exclamation, no "Oops", no "mastery" and no "score" where the backend
  records evidence. Backend enums are never shown raw.

---

## 7. Concept plates

Two static plates, not product code, under `audit/ux/round3/concepts/`:

| Plate | File | What it proves |
|---|---|---|
| Field Desk, light, 1440 | `01-field-desk-light.html` / `.png` | Lamp hero, seal, three facts, one primary, route spine, tally, notes and shelf. |
| Textbook plus check, dark, 1440 | `02-textbook-dark.html` / `.png` | Serif reading column, 66ch measure, mode coding, checkpoint panel, sources, mission rail. |

Rendered with headless Chromium at 2x device scale:

```
chromium --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1440,1400 \
  --screenshot=01-field-desk-light.png \
  "file://$PWD/01-field-desk-light.html"
```

Both plates were checked for horizontal overflow (`scrollWidth == clientWidth`). They contain no
host chrome, no external assets and no gradients. They are illustrations of the language, not a
pixel contract for the implementation; the token table and the component metrics above are the
contract.

The contrast proof is reproducible:

```
python3 audit/ux/round3/concepts/contrast.py
```

Expected: 21 rows, `Failing pairs: 0`, `Tokens: light=15 dark=15`.

---

## 8. Implementation checklist

Bounded to one writer, one file for product code (`desktop/plugin.js`), one contract file, one
test file. No new RPC method, route, dependency, font file or asset directory. Estimated diff:
about +900 / -450 lines. Land in the order below; each phase is independently shippable and
independently revertible.

### Phase 0: contract proposal (no product change)

1. Add `contracts/cb.tokens.v2.json`: version 2, name `atlas-lamp`, 15 token names, 21 gates from
   2.2, note that `lamp` is a fill and `coral` is attention only.
2. Update `tests/test_desktop_tokens.py` to load v2 and assert: 15 names, exact table equality,
   every gate, no hex outside `CB_TOKENS_JSON`, no `gradient(`, no `box-shadow`.
3. Run the test against the unchanged module. Expected: table mismatch, which is the RED state for
   phase 1. Do not touch strings yet.

Acceptance: the new test fails only on the v1 table and passes every structural rule.

### Phase 1: token layer and primitives

4. Replace `CB_TOKENS_JSON` and `CB_TOKEN_NAMES` at 7807 with the v2 literal (one literal, 15
   names). `cbScopeStyle` keeps its signature.
5. Replace `CB_WIDE_BREAKPOINT` with `cbLayoutFor(width)` returning `wide`, `mid`, `narrow`,
   `phone` at 1050, 900, 460. Keep `CB_MEASURE = '66ch'`.
6. Add exported-in-module primitives near the token layer: `SurveyMark`, `PlateHead`,
   `RouteSpine`, `EvidenceTally`, `ModeDot`, `CheckPanel`, `BlankPlate`, `HeroField`. Every one
   reads `var(--cb-*)` only. No raw hex, no gradient, no shadow.
7. Add CSS custom-property utilities through Tailwind arbitrary values where an SDK component needs
   a token (`bg-(--cb-lamp-soft)`), never a hex.

Acceptance: `tests/test_desktop_tokens.py` green; the primitives render in the existing SSR test
harness; the file still has exactly one hex-bearing literal.

### Phase 2: Field Desk

8. `ContinueCard` and `DeskView` (around 2130 to 2320): hero field, seal, one primary, one
   secondary, three facts, `Why this is next` disclosure.
9. `PathList` (around 2350 to 2465): plate head, tally plus caption, spine, current row tint,
   state pills. One `aria-current="step"`.
10. `AllCoursesShelf` and `FieldNotes` rail: max 3 each, seal 28, no card border.
11. Delete the `Back to the Field Desk` duplicate when already on the desk; delete `Show sources`
    as a full-width bar.

Acceptance: the desk tests for grid, stat counts, stamp and path wrap still pass after their selectors
are updated; screenshots at 1280, 1049, 900, 460, 200%, light and dark.

### Phase 3: lists and start

12. `CoursesView` (3144) and `CourseRow`: plate head, single toolbar, due callout, row anatomy,
    overflow actions.
13. `LibraryView` (3588): lead once, filter chips, row anatomy, detail plate with four trust rows.
14. `FirstRun` (1011) and `CreateCourseFlow` (4489): start plate, step spine, scope rows, 2x2 use
    choice grid, plan review plate, support caption.

Acceptance: no duplicated header subtitle; each screen has one primary; empty and filtered-empty
states both use the correct plate.

### Phase 4: Course Detail

15. `CourseDetail` (12313): compact hero, two-tier navigation, one `Next` block.
16. Pending-attempt and `needs_retry` notices use `CheckPanel` / `coral` left rule with the exact
    reason and a single action.

Acceptance: all eight surfaces remain reachable in one click; the tab order is hero, tabs, body,
rail; a background job never changes the route.

### Phase 5: reading views

17. `TextbookView` (11028): index plate, row anatomy, caption.
18. `LessonDocumentView` (9948): serif roles, 66ch, lede, block rhythm, media frame.
19. `FieldQuestView` (9416): quest plate, mission nodes, checkpoint panel, tertiary textbook link,
    developer copy moved to a Tip.
20. Guided step margin.

Acceptance: reading measure never exceeds 66ch at 1280 and 200%; no horizontal overflow at 460;
checkpoint and source components are shared, not forked.

### Phase 6: Parent Studio

21. `Studio*` surfaces (12898 to 15260): `plum` band, eyebrow, step spine, `plum-soft` panel,
    text tabs with `plum` underline, `Adult only` chip on Answers.
22. Remove the global `New lesson plan` duplicate; keep one primary inside the step route.

Acceptance: no learner-facing copy inside the studio; all five steps reachable at 900 and 460
without a hidden control; the parent course hero uses `plum-soft`.

### Phase 7: states, responsive, accessibility

23. Empty, error, offline, stale and detached-binding states per 5.10.
24. `cbLayoutFor` applied to every grid; verify 1049, 900, 460 and 200% text.
25. Focus rings, tab order, reduced motion, forced-colors, one `h1` per route.
26. Run the full desktop suite (`python3 -m unittest discover -s tests` or the project's runner),
    plus the existing keyboard, layout and fault probes under `audit/ux/`.

Acceptance for the whole card:

- `tests/test_desktop_tokens.py` green with 15 tokens and 21 gates.
- All existing desktop tests green after selector updates; no test deleted to make a screenshot pass.
- Screenshots at 1280, 1049, 900, 460 and 200% text, light and dark, for Field Desk, All Courses,
  Library, New Course, Parent Studio, Course Detail, Textbook, Guided, Field Quest, empty and error.
- Zero horizontal overflow at 460 and 200%.
- No raw hex outside the literal; no `gradient(`; no `box-shadow`; no new dependency.

### Surface map

| Surface | Function / anchor | Phase |
|---|---|---|
| Token table | `CB_TOKENS_JSON` 7807, `CB_TOKEN_NAMES` 7811 | 1 |
| Layout | `CB_WIDE_BREAKPOINT` 7825, `useCbViewportWidth` 7906 | 1 |
| Shell | `WorkspaceShell`, `FieldRail`, `MediaFrame` 2000 to 2130 | 1, 5 |
| Field Desk | `ContinueCard` 2230, `PathList` 2350, desk 2860 | 2 |
| All Courses | `CoursesView` 3144, `CourseRow` | 3 |
| Library | `LibraryView` 3588, `PackFacts` 3420 | 3 |
| New Course | `FirstRun` 1011, `CreateCourseFlow` 4489 | 3 |
| Course Detail | `CourseDetail` 12313, `OverviewView` 10533 | 4 |
| Textbook | `TextbookView` 11028 | 5 |
| Guided / document | `LessonDocumentView` 9948 | 5 |
| Field Quest | `FieldQuestView` 9416 | 5 |
| Parent Studio | `StudioBriefView` 13710, `StudioPlanView` 13800, `StudioBlueprintView` 14598, `StudioReflectionView` 14981 | 6 |
| States | `EmptyState` wrappers, `ErrorLine`, banners, pane 15617 | 7 |

---

## 9. What this spec refuses

- No XP, streak, league, level, mastery percentage, progress ring or invented goal. Ever.
- No gradient, shadow, glass, blur, glow or pseudo-3D. The lit page is a flat field.
- No external asset, illustration pipeline, icon font or second icon set.
- No new route, RPC method, pack field, grade rule or chat surface.
- No host `styles.css`, desktop asar or app chrome edit.
- No raw hex outside the token literal.
- No card inside a card.
- No uppercase cascade: one label per region, everything else sentence case.
- No color-only state, no color-only mode, no color-only validation.
- No auto-navigation, no focus steal, no modal spawned by a background job.
- No fabricated data in a concept plate or a screenshot. The plates use plausible example content
  and say so in the footer; they are not evidence of a live backend.

## 10. Open decisions for DeseretSaint

1. The display question on New Course: keep `Learn something specific.` or switch to `What do you
   want to be able to do?`. The second is stronger but changes product voice; this spec recommends
   the question.
2. Whether `plum` is allowed to become the Parent Studio identity everywhere, including the
   sidebar nav item in a later host seam. The current spec confines it to the scoped route.
3. Whether serif reading is acceptable for every subject, including procedural and
   non-language courses. The spec says yes because it is a reading surface; a subject-specific sans
   would fragment the identity.
