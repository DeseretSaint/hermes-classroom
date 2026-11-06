# README and demo screenshot set

These are the final, committed images for the README and demo materials. Each file is a real
capture from the Coursebook Desktop route, not a mock. The provenance column records which merged
evidence set the frame came from so a reader can replay it.

| Image | README/demo use | Provenance |
|---|---|---|
| `docs/assets/readme-overview-dark.png` | Landing / course overview, dark | `docs/cb049-shots/030-overview-dark.png` — CB-049 final polish |
| `docs/assets/readme-overview-light.png` | Landing / course overview, light | `docs/cb049-shots/040-overview-light.png` — CB-049 final polish |
| `docs/assets/readme-library-dark.png` | Library and imported pack | `docs/cb049-shots/036-library-dark.png` — CB-049 final polish |
| `docs/assets/readme-textbook-dark.png` | Textbook surface | `docs/cb049-shots/031-textbook-dark.png` — CB-049 final polish |
| `docs/assets/readme-notebook-dark.png` | Notebook surface | `docs/cb049-shots/033-notebook-dark.png` — CB-049 final polish |
| `docs/assets/readme-lesson-pane-dark.png` | Lesson pane beside a bound chat | `docs/cb009-shots/pane-02-bound-chat-pane.png` — CB-009 live pane evidence |
| `docs/assets/readme-quiz-in-progress.png` | Quiz in progress, answer typed | `docs/cb-loops-shots/21-quiz-answer-typed.png` — CB-015 loop proof |
| `docs/assets/readme-quiz-results.png` | Quiz results and attempt history | `docs/cb-loops-shots/23-quiz-graded.png` — CB-015 loop proof |
| `docs/assets/readme-parent-studio-dark.png` | Parent Studio | `docs/cb049-shots/037-studio-dark.png` — CB-049 final polish |

## Why the lesson and quiz frames reuse earlier evidence

The README rig's seeded section arrives with its chat binding detached. In that rig, `Reattach`
returns to the course list and the next visit is detached again; `Start a fresh run` leaves the
Coursebook route. That makes a clean in-progress lesson/quiz frame impossible to produce from the
seed without deciding whether the reattach path is a product defect.

The selected lesson and quiz frames are the already-merged CB-009 and CB-015 live captures of a
bound chat and a completed quiz loop. The images are captioned with that provenance rather than
presented as a new readme-rig capture. This is a rig limitation; no product defect is claimed.

## Reproduction

The capture rig and its exact status are in `docs/README-SHOTS-STATUS.md` and the scripts committed
at `b098753`. The CB-049 and CB-015 evidence sets are on `master`.
