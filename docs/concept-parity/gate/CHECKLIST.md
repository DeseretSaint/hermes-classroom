# CHECKLIST — "better than the concept", and what proves it

Card: CP-028. Source: `docs/concept-parity/SPEC-V3.md` §2 (defects the measurement exposed), §5.1–5.5
("Better than the concept" lists), §6 (honesty table). **Nothing here is invented**: every item is a
line of the spec, restated as a binary check plus the evidence that closes it. An item with no
evidence in the packet is `NOT PROVEN`, which scores as a miss for its dimension.

Evidence legend:
- **C** = a `scripts/cp-capture.mjs` capture + `.stamp.json` (matrix cell named).
- **G** = CDP geometry probe from the same commit (region boxes, computed styles).
- **T** = a named automated test.
- **D** = a data-field proof (the served value and where it comes from).

---

## 1. Global (applies to every screen)

| # | Spec line | Check | Evidence that satisfies |
|---|---|---|---|
| G1 | §1 "garbled text is never copied" (all) | OCR of every plate returns no lettering; every visible string maps to a `COPY.md` id | T + D: copy-id map; OCR output |
| G2 | §1 "stars, invented progress, `NEW`/`Life`, `240 XP` removed" | zero star/XP/progress-bar/badge elements outside Game mode | G: element query returns 0; C: `default@1049/light/100` |
| G3 | §2 "rail is icon-only" defect → labelled rail | every rail entry has Codicon + visible label; 44 px targets; `aria-current="page"` with a 3 px shape marker | G: labels/target sizes/aria; C: `focus@1049/light/100` |
| G4 | §2 "fox clipped by the route edge" → safe area | fox box inside content, ≥ 24 px (wide) / 16 px (mid, compact) from the route edge, ≥ 16 px from any target, ground contact on its ledge/plate ±1 px, `aria-hidden` | G: fox rect vs route rect vs target rects |
| G5 | §2 "two identical filled pills" → one primary | filled identity-hue control count = 1 per screen (lab: 0) | G + C: `default@1049/light/100` and `default@460/light/100` |
| G6 | §2 "painted words inside art" | art assets are textless; title/subject are DOM text | T: OCR on shipped plates; D: `pack.inspect` / `library_item.title` |
| G7 | §1 "one system replaces all of it" (D3) | 4 destinations only, same order, no fifth destination; same shell at 1049/900/460 | G at three widths; C: `default@900`, `default@460` |
| G8 | §3.1 route-relative measurement | no `vw`/`clamp(…vw…)` on the v3 route; `useCbViewportWidth()` used for gutters/stacking | T: V-12 viewport test; G: computed styles |
| G9 | §3.6 "physical objects" | card radius 12, 1 px `rule` xor `elev-1`, no card-in-card, shelf is a wood ledge with `wood-edge` lip | G: computed styles + boxes; C |
| G10 | §3.12 state contract | every matrix cell for the screen exists, keeps geometry ±4 px, one next action | C: one capture per cell; G: box diff vs default |
| G11 | §3.9 / Q8 motion | only the five named beats, ≤ 600 ms, no loops; reduced-motion removes transitions and keeps the state | T: motion test; C: `reduced-motion@1049/light/100` |
| G12 | §6 honesty table | every element on screen is a row of §6; nothing unlisted rendered | D: field map per visible string/number |

---

## 2. `home.v3` — Home (SPEC §5.1, CP-022)

| # | Item | Check | Evidence |
|---|---|---|---|
| H1 | One filled primary, one quiet outline (concept: two identical filled pills) | filled count = 1; secondary is 1 px `rule` outline, same height, `ink` label | G + C `default@1049/light/100` |
| H2 | No stars, `NEW`/`Life`, progress bar; `2 of 5 sections done` + real next-step label | card metadata is exactly title / subject / evidence, values from `evidence_summary` + `next_step` | D: `library_item.evidence_summary`, `next_step.label`; T: copy-id map |
| H3 | Cards align to the shelf's own width, one metadata pattern (concept's 4th card narrower) | card widths equal within 1 px; card tops/bottoms share baseline ±1 px | G: four card rects at 1049 |
| H4 | Fox and clock fully inside the safe box; tag only in first-use, never a second create control | fox rect ≥ 24 px from route edge; tag element absent in `default` | G; C: `default` and `first-use` |
| H5 | Shelf is a real scroll region with a named overflow state | 5 courses at wide: card width unchanged, shelf scrolls, right mask 32 px, keyboard order intact | C: `overflow@1049/light/100`; G: scrollWidth > clientWidth, card width unchanged |
| H6 | Loading/empty/error/offline keep shelf geometry | region boxes within ±4 px of default in all four states; error never renders as empty | C: `loading`, `empty`, `error`, `offline`; G: box diff |

---

## 3. `discover.v3` — Discover / Workshop (SPEC §5.2, CP-021)

| # | Item | Check | Evidence |
|---|---|---|---|
| D1 | Grid aligned to the banner edges, one track | `abs(banner.left − grid.left) ≤ 1` and same on the right at 1049, 900, 460 | G at three widths |
| D2 | No dead zone right of the grid | grid right edge reaches the content measure (≤ 1 px from banner right); no > 8 px dead band | G |
| D3 | Labelled rail, 44 px targets (concept: unlabelled glyphs) | labels visible, targets ≥ 44, `aria-current` present | G; C `focus@1049/light/100` |
| D4 | Fox inside the safe area, clear of the last card | fox offset ≥ 24 px from grid corner and ≥ 16 px from the last card's box | G |
| D5 | One metadata pattern per card | title / one subject line / one trust label / one count; identical order and sizes across all cards | G + D: `trust_labels()` values |
| D6 | No invented trust; `model_assessed_support` never rendered as approval | every trust label maps to a `trust_labels()` value; the model label carries its own wording | D: trust label values per card |
| D7 | No duplicate course in the same shelf | `library.list` ids unique per shelf; duplicate id = fail | D: id list |
| — | Rejected-pack state still ships | `discover.rejected.banner` row present, pack stays listed | C: `rejected@1049/light/100` |

---

## 4. `classroom.v3` — Classroom (SPEC §5.3, CP-023)

| # | Item | Check | Evidence |
|---|---|---|---|
| C1 | One filled primary (`Check answer`); `Play the line` is quiet text, never an answer option | filled count = 1 in C7; play control has no fill and is not inside the answer surface | G + C |
| C2 | Aside carries evidence + next section, not XP/names/leaderboard | aside contains only `classroom.evidence.*` and `classroom.aside.next`; no user names, no flame outside Game | D + C: `default@1049/light/100` |
| C3 | Current step marked by 3 px ring **and** the word `Now` | ring width = 3 px and label text present | G + C: stepper crop |
| C4 | Evidence reads `2 of 5 checks recorded`, not an invented count | number equals recorded checks from `evidence.inspect` | D |
| C5 | Fox inside the gutter (concept: clipped) | fox rect ≥ 16 px inside the gutter, not over type or the check card | G |
| C6 | Japanese line shows kana + furigana + romaji + meaning together; it is the lesson's real line | all four present where the pack/deck supplies them; string matches the pack section content | D: pack section + deck ruby; T: copy map |
| C7 | Stepper count = section count from the plan, not a fixed four | number of stamps equals `sections_total` | D |
| — | Three answer surfaces (or a written deferral) | `text`, `selection`, `verification` render their served format; a deferred format renders nothing | T: format routing test; C: one capture per format built |

---

## 5. `course-home.v3` — Course home (SPEC §5.4, CP-024)

| # | Item | Check | Evidence |
|---|---|---|---|
| M1 | Route nodes are buttons with words and `aria-current` (concept: unlabelled ornaments) | each node is focusable, has a visible label, current node `aria-current="step"` | G + C `focus@1049/light/100` |
| M2 | No search box, no truncated second create action; one primary, one back | 0 search inputs; exactly one filled plate = `next_step.label`; one back control top-left, first focusable | G |
| M3 | Shelf below is small and honest (other courses only), not six duplicates | ≤ 3 rows at wide, ids unique, no row repeats the current course | D: id list; C `default@1049` |
| M4 | Fox does not overlap the route or the type field | fox rect ∩ route nodes = ∅; ∩ type boxes = ∅ | G |
| M5 | Plate's text sits in a reserved quiet field, not on a scrim | text boxes sit over the plate's flat region; no scrim/gradient element | G + art asset check |

---

## 6. `lab.v3` — Design-system lab (SPEC §5.5, CP-020b)

| # | Item | Check | Evidence |
|---|---|---|---|
| S1 | Every callout label is real text at 12 px with a real meaning | caption step = 12 px; no script/decoration-only label; 6 anatomy callouts traceable | G + C |
| S2 | Palette chips carry role name and computed ratio (concept: unlabelled paint) | every chip shows `role` + ratio, and the ratio recomputes from `contracts/cb.tokens.v3.json` within 0.01 | T: ratio recompute; C |
| S3 | Medallions are one Codicon on one blank mapped to one recorded event, no invented ribbon text | 4 medallions, each bound to a named event id; no extra text | D + C |
| S4 | Sheet states it is read-only and where values come from | `lab.readonly` present; values read from the contract at render time | C + D |
| S5 | Six type rows in contract order; no `section` step painted | row order `caption→display`; no 7th row | G |

---

## 7. The spec's own defect list, closed (SPEC §2)

| Defect | Closed when | Evidence |
|---|---|---|
| Grid narrower than its banner by 80 px each side | banner and grid share one track | D1 |
| 241 px dead margin right of the grid | content centred on one measure | D2 |
| Two `Public Speaking` cards / duplicated artwork | one card per real course, ids unique | D7, M3 |
| Fox clipped by the route edge | safe area holds on every screen with a fox | G4, D4, C5, M4 |
| Rail icon-only, hover guess needed | visible labels + 44 px targets | G3, D3 |
| Two identical filled pills on Home | one filled + one outline | H1 |
| Stars/XP/progress/`NEW` on card rows | removed; real fields only | G2, H2 |
| User names + leaderboard in the lesson aside | aside is evidence + next section | C2 |
| Painted words in art | textless plates | G6 |
| Progress bars on Home cards | evidence tally, not a bar | H2 |

---

## 8. Checklist verdict rules

- Each row is `PROVEN` / `NOT PROVEN` / `N/A (justified in the card body)`.
- One `NOT PROVEN` item on a screen = `request-changes` for that screen, with the row id, the
  measured value and the capture that should close it. It is not a discussion.
- The checklist is scored **per screen**, and a screen can only be `PASS` when every one of its rows
  is `PROVEN`. GM-016 passes only when all five screens pass and G1–G12 pass globally.
- The reviewer writes the evidence path in the row. "Seen in the board" is not evidence; the board is
  a comparison, not a measurement.
