# GM concept-parity rubric

Card: GM-013. The scoring instrument for every visual card (GM-002, GM-004, GM-006, GM-008, GM-010,
GM-012, GM-014) and for GM-016. Reviewer: a profile that did not build the screen.

**Pass rule.** Score each of the nine dimensions 1–5. The card passes only if **every** dimension is
≥4 **and** the composition anchor check (§4) passes for every submitted screen. A single 3 is a
`request-changes`, not a rounding decision. Three loops maximum; a fourth failure escalates to the
manager, who splits the screen rather than lowering the threshold.

The reviewer must be able to score from `docs/GM-VISUAL-SPEC.md` plus the screenshots, **without
asking the maker a question**. If a dimension cannot be scored, the spec is defective and that is
itself a finding.

---

## 1. The nine dimensions

Each row gives the 1, 3 and 5 anchors. 2 and 4 are interpolations, and the reviewer writes one
sentence of evidence for any score below 5.

| # | Dimension | 1 — fail | 3 — below bar | 5 — pass |
|---|---|---|---|---|
| 1 | **Focal hierarchy** | several equal-weight blocks; the eye lands on chrome or a stat strip | one primary exists but a second filled control or a bright card competes | exactly one obvious primary; the eye lands on the course/action; every other control is visually quieter by fill, weight or size |
| 2 | **Composition** | header + equal boxes in a grid; centred dashboard | an authored layout with one generic region (usually the shelf or the aside) | authored asymmetry: a threshold band, an anchored shelf, a reading column, a route spine; regions differ in weight on purpose; nothing is a repeated box |
| 3 | **Type** | mixed families, tiny unexplained labels, >6 authored sizes | one system, but a heading or a caption is off-step or a card title is uppercase | one serif/sans system on the six shipped steps; body ≤66ch; headings ≤20ch (display) / 34ch (section); one uppercase element per region |
| 4 | **Palette and texture** | raw hex, gradient, coloured card fills | tokens used, but a mode or state hue is used decoratively, or two identity hues on one screen | 15-token palette only; at most two hues + `coral`; every state hue beside its word; flat fields with hard edges; no shadow, no gradient |
| 5 | **Illustration** | stock-like or generic fantasy; text in the art; wrong subject | right subject but only one motif, or inconsistent light/line weight across plates | ≥2 subject motifs from the course's plan; one kit across hero/cover/section; textless; quiet field for type; could not pass the swap check |
| 6 | **Card / game system** | fake ratings, XP on Home, invented progress | cards tactile but a badge or chip means nothing, or XP sits outside Game | cards read as physical objects (3:2 plate, 2px radius, 1px rule, no shadow); every badge names a real event; XP/level/progress appear **only** in Game mode |
| 7 | **State coverage** | only the happy path | empty and error exist but loading shows a shimmer or an empty state replaces a failed read | every state in `docs/visual-review/MATRIX.md` for that screen exists, keeps the geometry, names the read and offers one action |
| 8 | **Responsiveness** | clipped primary at 460 or 200%; no focus ring | 900 and 460 work but a measure exceeds 75ch or a card grid appears at 460 | 1049/900/460 all preserve the composition; 200% text without clipping; 2px `accent` focus ring visible; reduced motion static; keyboard reaches every control in reading order |
| 9 | **Truth** | any invented label, rating, XP, percentage or generated screenshot | real data but one decorative mark implies progress or a credential | every visible label is DOM text from real state; no AI text; no invented progress; provenance visible on any plate; a missing fact shows as an honest empty state |

**Scored once per card, not per screenshot**: if one viewport fails a dimension, the card fails that
dimension.

---

## 2. Evidence rules (what the reviewer is scoring)

1. Screenshots are captured from the **running app**, at the named viewport, with the app's own
   fonts. No compositing, no mockup, no upscaled image, no generated screenshot.
2. Each capture is listed in `docs/visual-review/<card>/MANIFEST.md` with viewport, mode
   (light/dark), text scale, state, and the commit it was taken from.
3. The comparison is **side by side at equal width** with the named concept frame (§3), not from
   memory.
4. A screen with no named concept frame cannot be scored and therefore cannot pass.
5. The reviewer writes the remaining differences, even on a pass. "Close enough" is not a verdict.

---

## 3. Comparison frame per screen

Every screen a GM card ships has exactly one named frame and a named region of that frame. The
implementer must state the frame in the card's review packet; the reviewer compares that region.

| Screen (card) | Concept frame | Region compared | What must survive |
|---|---|---|---|
| `home.global` (GM-002) | F1 `home-generic-first-open.png` | invitation band + shelf | threshold headline, one primary, a shelf that stands on a ledge, fox closing the right edge |
| `home.course` (GM-002) | F3 `refined-classroom.png` | three-column body | route spine, dominant hero, aside Continue card, type over/next to art |
| `world.studio` / concept check (GM-004) | F4 `refined-system.png` | card anatomy + palette sheet | three cards at one size with real alternatives, palette chips as tokens, one seal at most |
| `world.studio` / world check (GM-004) | F3 | hero + card composition | the assembled course home is shown with real type, not a bare image |
| `course.world` (GM-004) | F2 `japanese-classroom-reference.png` for Japanese; F3 for any other world | course-bound hero + route | the hero belongs to the course's world and only to that course |
| `parent.source-picker` (GM-006) | F3 | aside + list column | one list, one preview, one primary (`Print a take-home pack`) |
| `parent.takehome.preview` (GM-006) | F3 | reading column | the page reads as a printed sheet at screen scale; page roles distinct |
| `parent.export.approval` (GM-006) | F4 | seal/stamp language | one seal, real approval state, no fake credential |
| `homework.sheet` (GM-008) | print spec `docs/GM-PRINT-SPEC.md` | one-page sheet | one task, one target, one success criterion, no answer key |
| `lesson.take-with-you` (GM-008) | F3 | aside affordance | quiet text action, never a second filled control |
| `game.header` (GM-010) | F3 | header row | play chips at the right, `Continue` and the check unmoved |
| `game.lesson` (GM-010) | F3 | lesson column | one concept, one artifact, one check; game layer does not displace the reading hierarchy |
| `game.completion` (GM-010) | F3 | aside close | one authored beat, recorded evidence count, no confetti or score |
| `tutor.rail` (GM-012) | F3 | aside rail | the rail is a quiet second column; no second chat look; citation rows visible |
| `tutor.practice` (GM-012) | F3 | aside rail | practice is a mode of the same rail, not a new screen |
| `print.pack` (GM-014) | `docs/GM-PRINT-SPEC.md` §3 | five page roles | parent/learner/answer/sources/caption separation at A4 and Letter |
| `visual.reference` (GM-013) | F4 | palette sheet | textless plates, token chips, no invented ratings |

---

## 4. Composition anchor check ("near-concept overall composition")

Score is per screen, binary per anchor. **All five anchors must be present.** This is the gate that
stops a card that scores 4 on every dimension but still looks like a well-typeset admin grid.

| Anchor | Question | Applies to |
|---|---|---|
| A1 Threshold | Is there one place the eye enters, with one action, before any list or grid? | every screen |
| A2 Anchored asymmetry | Does at least one region break the equal-column rhythm on purpose (shelf on a ledge, route spine, offset aside, plate bleeding one edge)? | every screen |
| A3 Material surface | Does the page read as a lit sheet — flat fields, hard edges, hairlines — rather than floating cards with shadows? | every screen |
| A4 Subject mark | Is there at least one mark that could only belong to this course's subject (a motif, a seal, a spine, a plate)? | course-bound screens |
| A5 Quiet field | Is ≥35% of the first viewport quiet, low-contrast space that carries the type rather than competing with it? | Home, course home, studio |

**Anchors that are auto-fail regardless of score:** a card grid as the primary composition on Home;
shadows or a gradient; a second mascot; a second filled primary; XP/level/streak on a non-Game
screen; text inside a plate; a fabricated rating, percentage or credential.

---

## 5. Scorecard (copy per card)

```
Card: GM-___            Branch/commit: ____________________
Reviewer: _____________ Date: __________  Loop: 1 / 2 / 3
Screens submitted: ____________________________________________
Concept frames used: __________________________________________

Dimension                         Score (1-5)   Evidence (one sentence)
1 Focal hierarchy                 ____          ______________________
2 Composition                     ____          ______________________
3 Type                            ____          ______________________
4 Palette and texture             ____          ______________________
5 Illustration                    ____          ______________________
6 Card / game system              ____          ______________________
7 State coverage                  ____          ______________________
8 Responsiveness                  ____          ______________________
9 Truth                           ____          ______________________

Composition anchors (screen: A1..A5)   _____________________________
All dimensions >= 4?                   YES / NO
All anchors present?                   YES / NO
Verdict: PASS / REQUEST CHANGES
Smallest fix if not passing: ___________________________________
Remaining differences even on pass: __________________________
```

A filled example exists at `docs/visual-review/gm-013/SCORECARD.md`, scoring this spec's own
reference boards and print proof. It is a **self-consistency check of the instrument**, not a
product review: GM-013 ships no screen, so its scorecard scores the reference material only.

---

## 6. What this rubric refuses

- A pass without screenshots at 1049/900/460, light/dark and 200% text.
- A pass by the maker of the screen, or by a profile that shares the maker's chat.
- A generated image used as a screenshot of the UI.
- A 4 given for "close enough" when an anchor is missing.
- Raising a score after a verbal explanation: the score is of the artifact, not the explanation.
- Waiving a dimension because "the backend limits it". A backend limit is a spec defect to fix, not
  a review outcome.
