# CP-023 — Classroom (R-CLASS) copy and state inventory

Card body: `docs/concept-parity/cards/CP-023.md` (this card section starts line 34).
Spec: `SPEC-V3.md` §5.3 (lines 462–540), §3.10 (290), §3.8 (261–263), §6 (652–667).
Deck: `COPY.md` §4 (lines 127–184).

Deck rows used: 46 screen-specific + the 4 shared `nav.*` rows.

## Regions

| region | string | copy id | deck row | value | status |
|---|---|---|---|---|---|
| C1 | Home / Courses / Workshop / Parent Studio | `nav.*` | 52–55 | deck | ok |
| C2 | Back to {course title} | `classroom.back` | 131 | `field:library_item.title` | ok |
| C3 | {section title} (node label) | **GAP-11** | — | `field:course.outline.objectives[].title` | **gap** |
| C3 | This section (group name) | `classroom.stepper.label` | 134 | deck | ok |
| C3 | Now | `classroom.step.current` | 135 | deck | ok |
| C3 | Done | `classroom.step.done` | 136 | deck | ok |
| C3 | Next | `classroom.step.next` | 137 | deck | ok |
| C3 | Opens after the check | `classroom.step.locked` | 138 | deck | ok |
| C4 | {course title} | `classroom.title` | 132 | `field:library_item.title` | ok |
| C4 | {section title} | `classroom.section` | 133 | `field:lesson.page.section.title` | ok — resolves in `lesson.page.response.section.title` |
| C5 | {art credit} | `classroom.scene.credit` | 139 | `art:license.per_artifact[].attribution` | ok |
| C6 | 好きです。付き合ってください。 | `classroom.line.jp` | 140 | `pack:bundled/packs/japanese-affection-context-l0/content/section-01-two-ways.md` | ok — the line is at that file's line 19 under `## Dialogue B — a confession` (line 17); the deck's `#dialogue-b` is a description, not a resolvable anchor |
| C6 | 好(す)き です。付(つ)き合(あ)ってください。 | `classroom.line.furigana` | 141 | deck (ruby, omit when the pack carries no reading) | ok |
| C6 | suki desu. tsukiatte kudasai. | `classroom.line.romaji` | 142 | pack file + `pack.json` `files[].text_equivalent` | ok |
| C6 | I like you. Please go out with me. | `classroom.line.en` | 143 | pack file + `text_equivalent` | ok |
| C6 | Play the line | `classroom.line.play` | 144 | deck | ok — audio exists (`content/narration-polite-confession.mp3`, `pack.json:62`) |
| C7 | {check prompt} | `classroom.check.question` | 145 | `field:check.get.stimulus.prompt` | ok |
| C7 | {choice text} | `classroom.check.option` | 146 | `field:check.get.stimulus.choices[]` | ok |
| C7 | {item label} | `classroom.check.item` | 147 | `field:check.get.stimulus.items[].label` | ok |
| C7 | Your answer (text format meta) | **GAP-12** | — | — | **gap** |
| C7 | Selected (choice row word) | **GAP-13** | — | — | **gap** |
| C7 | Selected: {n}. {choice} / Nothing selected yet. | **GAP-14** | — | `computed` over the chosen index + `stimulus.choices[]` | **gap** |
| C7 | {helper line under the answer region} | **GAP-15** | — | — | **gap** |
| C7 | Check answer | `classroom.check.primary` | 148 | deck | ok |
| C7 | Edit answer | `classroom.check.edit` | 149 | deck | ok |
| C7 | Clear choice | `classroom.check.clear_choice` | 150 | deck | ok |
| C7 | Clear ticks | `classroom.check.clear_ticks` | 151 | deck | ok |
| C7 | That is right. {why} | `classroom.check.correct` | 152 | deck + `field:attempt.submit.criteria[].observed` | ok |
| C7 | Not quite. {why} | `classroom.check.wrong` | 153 | deck + `field:attempt.submit.criteria[].observed` | ok |
| C7 | Try again | `classroom.check.retry` | 154 | deck | ok |
| C7 | Next section | `classroom.check.next` | 155 | deck | ok |
| C8 | Evidence | `classroom.evidence.title` | 156 | deck | ok |
| C8 | {n} of {total} checks recorded | `classroom.evidence.count` | 157 | `computed:count(attempt_count > 0)` over `lesson.page.checks[]` | ok |
| C8 | No checks recorded yet. | `classroom.evidence.empty` | 158 | deck | ok |
| C8 | First try, no hints | **GAP-17** | — | `field:attempt_summary.evidence_class` == `cold` | **gap** |
| C8 | Hinted | **GAP-17** | — | `field:attempt_summary.evidence_class` == `hinted` | **gap** |
| C8 | Answer shown — no longer independent | **GAP-17** | — | `field:attempt_summary.evidence_class` == `answer_shown` | **gap** |
| C8 | Self-reported — not an independent check | **GAP-17** | — | `field:attempt_summary.evidence_class` == `self_reported` | **gap (decision)** |
| C8 | Reported by a parent — a report, not a mark | **GAP-17** | — | `field:attempt_summary.evidence_class` == `parent_reported` | **gap (decision)** |
| C8 | Opened by an override — no evidence recorded | **GAP-17** | — | `field:attempt_summary.evidence_class` == `override` | **gap (decision)** |
| C8 | Next up: {next section} | `classroom.aside.next` | 159 | `field:library_item.next_step.label` | ok |
| C8 | Ask the tutor | `classroom.aside.tutor` | 160 | deck | ok |
| C10 | — (fox `read`/`think`/`cheer`, `aria-hidden`) | — | — | — | ok, no copy |
| C11 | {n} XP | `classroom.game.xp` | 174 | `field:engagement.read.xp_total` (Game only) | ok |
| C11 | {level title} · level {n} | **GAP-16** | — | `engagement.read.level.title` + `.level` | **gap** |
| C11 | Field Challenge | `classroom.challenge.title` | 175 | deck | ok |
| C11 | Try it yourself | `classroom.challenge.primary` | 176 | deck | ok |

## States (SPEC §5.3 lines 518–527)

| state | copy ids | status |
|---|---|---|
| default | check.primary, line.jp, line.furigana, line.romaji, line.en | ok |
| correct | check.correct (152), check.next (155) | ok |
| wrong | check.wrong (153), check.retry (154) | ok |
| no-chat | nochat.title (161), .body (162), .action (163) | ok |
| complete | complete.title (164), .body (165), .action (166) | ok |
| loading | classroom.loading (167) | ok |
| error | error.title (168), .body (169), .action (170) | ok |
| offline | offline.title (171), .body (172), .action (173) | ok |

The three answer formats (`text`, `selection`, `verification`) share the C7 card, the question row
and the primary. Only the answer region differs — and that region is the one with unwritten copy.

## GAPS

- **GAP-11 — the stepper node label has no row.** SPEC line 480 lists C3's ids as the group name and
  the four state words only, but CP-023 line 35 says "every node is a button opening its section",
  and SPEC line 540 says the stepper count is the plan's section count. A button needs the section's
  own name. The real field is `course.outline.objectives[].title`
  (`$defs.outline_objective.properties.title`, max 300). Without a row the maker invents node names
  or renders bare numbers.
- **GAP-12 — `Your answer`.** SPEC line 500 requires the meta label "Your answer" above the text
  area. No deck row.
- **GAP-13 — `Selected`.** SPEC line 501 requires the word "Selected" on the chosen radio row.
  No deck row.
- **GAP-14 — the live selection summary.** SPEC line 501 requires `Selected: {n}. {choice}` or
  `Nothing selected yet.` as a live line. No deck row, no stated empty variant.
- **GAP-15 — the helper line.** SPEC lines 500 and 502 require "one helper line under" the text
  area and the checklist, and the text format also needs "one helper line". No deck row and no
  stated content, so every maker writes a different sentence — exactly the invented-copy failure
  this card exists to prevent.
- **GAP-16 — the level line.** CP-023 line 43 says the Challenge card carries "XP and level from
  `engagement.read`". The deck has `classroom.game.xp` (174) and nothing for the level. The contract
  supplies `engagement.read.level.{level,title,xp_into_level,xp_for_next_level,is_cosmetic}`, and the
  shipped v2 band renders `Level 1 · Curious · cosmetic` (`desktop/src/30-home.js:3846-3848`). A v3
  maker must not re-invent that phrasing.
- **GAP-17 — the evidence-class words.** CP-023 lines 45–46 require "first-try, hinted and
  answer-shown states stay visible", and `docs/EXPERIENCE-QUALITY-BAR.md` requires a visible
  integrity state ("First try, no hints" / "Hinted" / "Answer shown — no longer independent").
  The deck's evidence rows are counts only (157, 158). The field is
  `$defs.attempt_summary.properties.evidence_class`, and `lesson.page.attempts[]` carries
  `attempt_summary`. Its enum is `contracts/vocabulary.v1.json:20`:
  `cold | hinted | answer_shown | self_reported | parent_reported | override`. Only `cold` counts as
  independent evidence and `override` grants access, never mastery, so **all six values need a row**:
  the first three are the integrity claim the product is built on, and the last three are proposed
  but marked **decision** because a maker must not word them. A row keyed to a value that is not in
  the enum (such as `independent`) never matches and silently deletes the honesty state.
- **GAP-18 — the body contradicts the one-primary rule.** CP-023 line 40 says "choosing an option is
  the one primary action"; SPEC §3.10 line 290 and §5.3 line 465 say **`Check answer` is the one
  primary**. If choosing an option submitted the check, `Check answer` would have no job. The deck
  (148) and the spec win; the body line should be corrected to "one primary: Check answer".

## Notes

- `classroom.evidence.count` (157) counts `lesson.page.checks[]` where `attempt_count > 0`, and its
  total is that array's length. That is a per-section count, and the spec's worked value
  ("2 of 5 checks recorded", line 536) is 5 checks in a section. If the served page has one check per
  section the string reads "2 of 1", so the maker must render the section's own check total, not the
  page's. The deck's `computed:` rule is written as if a section has many checks; it does not say
  where the denominator comes from when `lesson.page.checks[]` has one item. Flagged for CP-001.
- The Japanese example rows (140–143) are a fixture: the deck says the screen renders the lesson's
  own authored line, so the component must read pack content, never these literals.
