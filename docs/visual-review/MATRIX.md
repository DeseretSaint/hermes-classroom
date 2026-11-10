# Required screenshot matrix

Source of truth: `docs/visual-review/matrix.json` (validated by `tests/test_gm_visual_spec.py`).
This page is the human rendering; if the two disagree, the JSON wins and this file is a defect.

Eight baseline cells per screen — `1049/light/100`, `1049/dark/100`, `900/light/100`,
`460/light/100`, `1049/light/200`, `460/light/200`, `focus`, `reduced-motion` — plus one capture per
named state at 1049/light/100. File naming and capture rules are in `README.md`.

## Screens and states

| Screen | Card | Concept frame | Named states (each needs a capture) |
|---|---|---|---|
| `home.global` | GM-002 | F1 `home-generic-first-open.png` | default · empty · loading · error · offline · overflow |
| `home.course` | GM-002 | F3 `refined-classroom.png` | default · no-world · world-running · world-partial · world-stale · plan-in-review · loading · error · course-end |
| `world.studio.concept` | GM-004 | F4 `refined-system.png` | default · generating · partial · provider-unavailable · rejected |
| `world.studio.world` | GM-004 | F3 | default · missing-roles · approving · approved |
| `course.world` | GM-004 | F2 `japanese-classroom-reference.png` | default · stale · no-art |
| `parent.source-picker` | GM-006 | F3 | default · empty · loading · error · no-eligible-lesson |
| `parent.takehome.preview` | GM-006 | F3 | default · editing · stale-source · error |
| `parent.export.approval` | GM-006 | F4 | default · not-approved · exporting · error |
| `homework.sheet` | GM-008 | F3 | default · one-page · self-reported · parent-reported · skipped · expired |
| `lesson.take-with-you` | GM-008 | F3 | default · generating · unavailable |
| `game.header` | GM-010 | F3 | default · feedback-off · no-xp-yet · textbook-hidden |
| `game.lesson` | GM-010 | F3 | default · award · wrong-answer · feedback-off |
| `game.completion` | GM-010 | F3 | default · recorded · not-recorded |
| `tutor.rail` | GM-012 | F3 | collapsed · open · selection · answer-pending · error · citation-missing |
| `tutor.practice` | GM-012 | F3 | default · recording · unavailable · complete |
| `print.pack` | GM-014 | print spec | parent-guide · learner-page · answer-guide · sources · caption-sheet · low-ink · a4 · letter |

`print.pack` is captured as a PDF page render (`pdftoppm -r 110`), not a browser screenshot: the
print stylesheet is what is under review, and `docs/GM-PRINT-SPEC.md` §6 is its proof path.

## v3 screens (CP-001)

The v3 entries are additive. Every v3 screen also carries a **forced-colors** cell, which the v2
baseline does not require: `forced-colors@1049/light/100`. `concept_frame` for a v3 screen is a
repo-relative path into `docs/concept-parity/refs/`, pinned by sha256 in `refs/REFS.md`.

| Screen | Card | Concept frame | Named states |
|---|---|---|---|
| `home.v3` | CP-022 | `refs/home.png` | default · first-use · overflow · empty · loading · error · offline |
| `discover.v3` | CP-021 | `refs/discover.png` | default · empty · loading · error · offline · rejected |
| `classroom.v3` | CP-023 | `refs/classroom.png` | default · correct · wrong · no-chat · complete · loading · error · offline |
| `course-home.v3` | CP-024 | `refs/map.png` | default · plan-in-review · no-world · world-running · world-rejected · course-end · loading · error |
| `lab.v3` | CP-020b | `refs/system.png` | default · reduced-motion · forced-colors · text-200 · loading · error |

`docs/concept-parity/SPEC-V3.md` §5 is the region map, the one primary action and the state's one
next action for each of these. A v3 capture is taken with `scripts/cp-capture.mjs` and is invalid
without its stamp JSON.

## Per-card minimum

| Card | Screens | Minimum captures |
|---|---|---|
| GM-002 | `home.global` 13 + `home.course` 16 | 29 |
| GM-004 | `world.studio.concept` 12 + `world.studio.world` 11 + `course.world` 10 | 33 |
| GM-006 | `parent.source-picker` 12 + `parent.takehome.preview` 11 + `parent.export.approval` 11 | 34 |
| GM-008 | `homework.sheet` 13 + `lesson.take-with-you` 10 | 23 |
| GM-010 | `game.header` 11 + `game.lesson` 11 + `game.completion` 10 | 32 |
| GM-012 | `tutor.rail` 14 + `tutor.practice` 11 | 25 |
| GM-014 | 8 page states × A4 and Letter (no viewport cells for print) | 16 |

Arithmetic, so the reviewer can check it: 8 baseline cells + (named states − 1, because `default` is
already a baseline cell). `tutor.rail` has no state called `default`, so all 6 of its states are
extra.

The counts are the cost of a real visual pass. A card that submits fewer has not covered its states.
