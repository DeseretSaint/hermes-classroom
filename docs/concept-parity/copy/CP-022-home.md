# CP-022 — Home (R-HOME) copy and state inventory

Card body: `docs/concept-parity/cards/CP-022.md` (this card section starts line 34).
Spec: `SPEC-V3.md` §5.1 (lines 356–406), §3.8 (239–269), §3.10 (288), §3.11 (297–320),
§3.12 (322–331).
Deck: `COPY.md` §2 (lines 59–87), §1 (48–55).

Deck rows used: 25 screen-specific + the 4 shared `nav.*` rows.

## Regions

| region | string | copy id | deck row | value | status |
|---|---|---|---|---|---|
| H1 | Home / Courses / Workshop / Parent Studio | `nav.*` | 52–55 | deck | ok |
| H2 | Your field library | `home.title` | 63 | deck | ok |
| H2 | Pick a course, or start a new one. | `home.sub` | 64 | deck | **conflict — GAP-06** |
| H3 | Start a course | `home.primary` | 65 | deck | **conflict — GAP-06** |
| H3 | Browse library | `home.secondary` | 66 | deck | ok |
| H4 | Your courses | `home.shelf.label` | 68 | deck | ok |
| H5 | {course title} (card title) | **GAP-03** | — | `field:library_item.title` | **gap** |
| H5 | {subject label} (line 2) | `home.card.subject` | 69 | CP-005 `library_item.subject_label` + `world_brief.subject_domain` + `library_item.recipe` | ok |
| H5 | {done} of {total} sections done (line 3) | `home.card.meta` | 70 | CP-005 `sections_done`/`sections_total`, else `evidence_summary.independent`/`total_objectives` | ok |
| H5 | New (chip) | `home.card.new` | 71 | CP-005 `library_item.is_new`, else `evidence_summary.independent` | ok |
| H5 | {next step} (quiet action) | `home.card.next` | 72 | `field:library_item.next_step.label` | ok |
| H5 (overflow) | More courses to the right | `home.overflow.hint` | 77 | deck | ok |
| H5 (overflow) | See all | **GAP-04** | — | — | **gap** |
| H6 | New course (paper tag, first use) | `home.tag.firstuse` | 73 | deck | **conflict — GAP-05** |
| H6 | {displayName} · study companion | **GAP-02** | — | `sdk.host.request('pet.info')` `displayName` | **gap (shell)** |
| H7 | Settings | `home.settings` | 67 | deck | ok |
| H7 (sheet) | Appearance / Default view / Sound / Reduced motion / Show my study companion / On this device | **GAP-01** | — | `ctx.storage`, `pet.info` | **gap (shell)** |

## States (SPEC §5.1 lines 384–392)

| state | copy ids | status |
|---|---|---|
| default | home.title, home.sub, home.primary, home.secondary, home.shelf.label, card.* | ok (+GAP-03, GAP-06) |
| first-use | `home.firstuse.title` (74), `.sub` (75), `.primary` (76), `home.tag.firstuse` (73) | ok |
| overflow | `home.overflow.hint` (77) + scroll or `home.secondary` (66) | ok (+GAP-04 if "See all" stays) |
| empty | `home.empty.title` (78), `.body` (79), `.action` (80) | ok |
| loading | `home.loading` (81) | ok — "Reading your courses. Nothing on the shelf changes while this loads." |
| error | `home.error.title` (82), `.body` (83), `.action` (84) | ok |
| offline | `home.offline.title` (85), `.body` (86), `.action` (87) | ok |

Note: `home.title` (63) and `home.firstuse.title` (74) carry the identical string. A surface renders
exactly one of them; do not render both H2s. Not a defect, but a maker copying both rows into one
component duplicates the heading.

## GAPS

- **GAP-03 — the shelf card title has no row.** SPEC line 375 lists H5's copy ids as meta/new/next
  only, and the deck has no `home.card.title`. The card's title is `library_item.title`
  (`$defs.library_item.properties.title`, max 200). A maker has no id to cite for the largest string
  on the shelf. Proposal in `GAPS.md`.
- **GAP-04 — "See all" has no row and no agreed action.** CP-022 line 39 says `See all` appears
  "when more than four". The deck's overflow row is `home.overflow.hint` (77) — a *hint*, not a
  control — and SPEC line 388 gives overflow's one next action as "scroll or `Browse library`".
  Adding a fifth control is a duplicate-CTA risk (`EXPERIENCE-QUALITY-BAR` §Q2). Recommendation:
  drop "See all" and keep `Browse library` + the hint; if the owner wants it, it needs a row and a
  spec amendment.
- **GAP-05 — the tag conflicts with both the deck and the spec.** CP-022 lines 40–42 define the tag
  as "New: <title of the most recently created course>", opening that course, when the course is
  under 14 days old and has no attempts. The deck row is `home.tag.firstuse` = "New course", first
  use only (line 73), and SPEC line 401 says the tag "exists only in first-use and is not a second
  create control", while PLAN O5 (line 940) recommends the CP-022 rule. These are three different
  rules. The maker cannot satisfy all three. This is an owner/manager decision, not a copy fix.
- **GAP-06 — two body strings disagree with the deck.** Line 35 says "Choose a course or start a
  new expedition." (`home.sub` is "Pick a course, or start a new one.", line 64); line 36 says
  "Start a new course" (`home.primary` is "Start a course", line 65, cap 24 — the body string is 18
  characters and would fit, but the deck is the only source). Deck wins; correct the body.
- **GAP-01 — the settings sheet has no copy section.** SPEC line 320 makes the sheet part of Home
  ("one sheet opened by `settings-gear`"), and the shipped sheet renders Appearance, Default view,
  Sound, Reduced motion, the companion switch and the "On this device" scope line
  (`desktop/src/30-home.js:3319, 3343, 3484, 3547, 3508, 3515` and the header comment at
  `00-header.js:143`). The deck has only the `home.settings` entry label. Any maker restyling Home
  invents the sheet.
- **GAP-02 — the companion's visible name has no row.** SPEC §3.8 and the pet rule require an
  adjacent visible name (`<displayName> · study companion`). The shipped fallback is
  "Your study companion" (`desktop/src/30-home.js:1970-1971`). The deck has no row.
