# CP-024 — Course home (R-MAP) copy and state inventory

Card body: `docs/concept-parity/cards/CP-024.md` (this card section starts line 34).
Spec: `SPEC-V3.md` §5.4 (lines 542–590), §3.8 (264), §3.10 (291), §3.12 (322–331).
Deck: `COPY.md` §5 (lines 188–221).

Deck rows used: 30 screen-specific + the 4 shared `nav.*` rows.

## Regions

| region | string | copy id | deck row | value | status |
|---|---|---|---|---|---|
| M1 | Home / Courses / Workshop / Parent Studio | `nav.*` | 52–55 | deck | ok |
| M2 | Back to {parent} | `course.back` | 192 | deck (destination label) | ok |
| M3 | {course title} | `course.title` | 193 | `field:library_item.title` | ok |
| M3 | {subject label} | `course.subject` | 194 | CP-005 `library_item.subject_label` | ok (forward field, allowlisted) |
| M4 | {art credit} | `course.hero.credit` | 195 | `art:license.per_artifact[].attribution` | ok |
| M4 (no world) | No scene yet / The lesson works without art. | `course.noworld.title`, `.body` | 210, 211 | deck | ok |
| M4 (running) | Painting the scene. | `course.world.running` | 212 | deck | ok |
| M4 (rejected) | This scene was not approved / Open World Studio | `course.world.rejected.title`, `.action` | 213, 214 | deck | ok |
| M5 | Your route (group name) | `course.route.label` | 196 | deck | ok |
| M5 | {section title} (node label) | **GAP-19** | — | `field:course.outline.objectives[].title` | **gap** |
| M5 | You are here | `course.node.current` | 197 | deck | ok |
| M5 | Done | `course.node.done` | 198 | deck | ok |
| M5 | Next | `course.node.next` | 199 | deck | ok |
| M5 | Opens after the section before it | `course.node.locked` | 200 | deck | ok |
| M6 | Continue (heading) | `course.continue.title` | 201 | deck | ok |
| M6 | {next step} (filled plate) | `course.next.label` | 202 | `field:library_item.next_step.label` | ok |
| M6 (plan in review) | The plan is waiting for you / Read it, then approve it so lessons can start. / Review the plan | `course.plan.review.title`, `.body`, `.action` | 207–209 | deck | ok |
| M6 (course end) | Course complete / Every section has evidence. / Review the plan | `course.end.title`, `.body`, `.action` | 215–217 | deck | ok |
| M7 | Evidence | `course.evidence.title` | 203 | deck | ok |
| M7 | {n} of {total} sections have evidence | `course.evidence.count` | 204 | CP-005 `sections_done`/`sections_total` | ok (forward field) |
| M8 | Your other courses | `course.others.title` | 205 | deck | ok |
| M8 | {title} · {next step} | `course.others.row` | 206 | `library_item.title` + `library_item.next_step.label` | ok |
| M9 | — (fox `point`, `aria-hidden`) | — | — | — | ok, no copy |
| M9 | {displayName} · study companion | **GAP-02** | — | `pet.info` `displayName` | **gap (shell)** |
| aside | Field Notes | **GAP-20** | — | — | **gap** |

## States (SPEC §5.4 lines 572–581)

| state | copy ids | status |
|---|---|---|
| default | course.continue.title, course.next.label, course.evidence.count | ok |
| plan-in-review | course.plan.review.title/body/action | ok |
| no-world | course.noworld.title/body | ok |
| world-running | course.world.running | ok |
| world-rejected | course.world.rejected.title/action | ok |
| course-end | course.end.title/body/action | ok |
| loading | course.loading (218) | ok |
| error | course.error.title/body/action (219–221) | ok |
| **offline** | **GAP-22** | **gap** — the state is required and does not exist |

SPEC §3.12 (line 325) makes `offline` mandatory on every screen and says a failed read must never
render as an empty course. R-MAP's state table (lines 572–581) has no offline row and the deck has no
`course.offline.*` row.

## GAPS

- **GAP-19 — the route node label has no row.** CP-024 line 36 says "nodes are DOM buttons placed on
  the anchors" and SPEC line 561 lists M5's ids as the group name and the four state words. A button
  whose only text is "Next" cannot tell a learner which section it opens. The real field is
  `course.outline.objectives[].title` (`$defs.outline_objective.properties.title`). Same gap shape
  as CP-023's `GAP-11`; one row can serve both if CP-001 names it once.
- **GAP-20 — "Field Notes" is not in the deck and not in the spec's region map.** CP-024 line 38
  makes "Field Notes and course shelf as the aside". The deck has no field-notes row; SPEC's M7 is
  `course.evidence.title`/`count` and M8 is `course.others.title`/`row` — evidence and other courses,
  not notes. The shipped Field Notes strip renders its own heading and "All field notes" action
  (`desktop/src/30-home.js:2984, 2997`). Either the aside is evidence + other courses (deck and spec
  agree, body is wrong) or the deck needs `course.notes.title` and a notes row. Recommendation:
  follow the spec, and correct CP-024's body — a maker reading the body will paint a third block the
  deck cannot word.
- **GAP-22 — no offline copy for the course home.** The deck writes offline rows for Home (85–87),
  Discover (117–119) and Classroom (171–173) but none for Course home, and the spec's R-MAP state
  table omits the state. Required by §3.12.
- **GAP-21 — "One primary `Continue`" contradicts the spec's primary.** CP-024 line 38 says the one
  primary is `Continue`; SPEC line 545 and §3.10 line 291 say the one primary is the backend's
  `library_item.next_step.label` rendered as the filled plate, with `course.continue.title` only a
  heading. The deck rows are right and the body is wrong. If the plate label happens to be
  "Continue", nothing breaks; if it is "Resume section 3", a maker who followed the body would
  replace the backend's own label with the fixed word and lose the real next step.

## Notes

- `course.back` is "Back to {parent}" and the parent label comes from `DESTINATIONS`. On a course
  screen the rail's current entry is `Courses` (SPEC line 318), so the rendered back label is
  "Back to Courses" — sourced, no new row needed.
- M6's plate and M5's nodes both read `course.outline`; the deck's `course.evidence.count` reads
  CP-005's forward fields. Until CP-005 lands, that row's "when empty" wording is the section count
  from `lesson.page` — the deck does not state a fallback, so a maker must not render "0 of 0".
