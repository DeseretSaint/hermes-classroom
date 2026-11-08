# H-153 — First-run start plate and cold states

Branch `wt/h153-first-run`, base: H-145 launch shell (`8635a7f`, merged here as `c3ce957`).
Live evidence: `docs/h153-shots/` (`h153-facts.json` holds every measured value quoted below).
Capture: `scripts/h153-capture.mjs`; the rig's appearance is switched through the Desktop's own
preference store with `scripts/h153-mode.py`.

## 1. What changed on the plate

| | Before (H-28 … H-145) | After (H-153) |
|---|---|---|
| Blocks | headline, promise paragraph, primary + "next" hint, three numbered path rows, two secondary entries with hint paragraphs, progress paragraph, capability inventory note | headline, one what-happens line, primary, at most one secondary |
| Secondaries | "Use a course I already have" **and** "Use my college syllabus" | one secondary: "Use a course I already have" → the Library, which owns both doors |
| Seal | removed by H-145 (`SurveyMark` at the old line 1140) | none; the plate renders no `svg` at all |
| Inventory note | `Not in this backend build yet: pack preview, …` | removed; an unsupported entry is absent, not announced |
| Path rows | `data-cb-first-run-path` with three `data-cb-first-run-step` rows | removed |
| Progress paragraph | "Nothing is marked complete without a check you can see." | removed |
| Primary hint | "Next you choose how big the course is." | removed (the one line covers it) |

Copy that remains:

- headline: `What do you want to be able to do?`
- line: `Name one goal, review the plan, then learn. Nothing is created until you approve the plan.`
- primary: `Start with a goal` (only when `course.create` is mounted and a handler exists)
- secondary: `Use a course I already have` (only when the Library has a live door — `pack.import`
  or `syllabus.intake.create` — and the caller can route there)

32 visible words on the whole plate, one filled action, one secondary, no decorative mark.

## 2. Gating — every entry, no dead control

| Entry | Gate | Where |
|---|---|---|
| Create a course | `course.create` + an `onCreate` handler | plate primary |
| Import a pack | `pack.import` + `IMPORT_FLOW_WIRED` | Library, behind the single secondary |
| College syllabus | `syllabus.intake.create` + `onSyllabus` handler | Library, behind the single secondary |

With neither Library door mounted the secondary is **absent** and the plate's line becomes
`This version of Coursebook cannot create or add a course yet.`; with `pack.import` present but no
`course.create`, the line is `This version of Coursebook cannot create a course yet.` and the
Library door is still offered. Nothing is ever rendered disabled.

## 3. Cold states (all captured live, light and dark)

The rig's backend answered the cold read with `{"items":[],"total":0,"empty_reason":"no_courses"}`,
so the first-run frames are a real empty profile, not a fixture.

| State | What renders | One next action | Frame |
|---|---|---|---|
| First use | plate, `data-cb-first-run-state="start"`, desk `empty` | `Start with a goal` | `light/dark-firstrun-1049/900/460` |
| Loading | `data-cb-desk="loading"`, spinner **with the visible line** `Reading your courses.` | wait, or leave the section; no blank route | `light-loading`, `dark-loading` |
| Failed read | `data-cb-desk="error"`, `HOST_UNAVAILABLE: … ECONNREFUSED`, "This desk will not show an empty course in place of a failed read." | `Try again` (+ `Open Capabilities`) | `light-error`, `dark-error` |
| Offline | plate `data-cb-first-run-state="offline"`, `A new course is paused while this profile is offline. Nothing you already saved is lost.` | `Try again` | `light-offline`, `dark-offline` |
| Cleared | the same plate: a read that returns `total: 0` after deletion renders the start state (data-driven, no separate screen) | `Start with a goal` | same frames as first use |
| Unsupported backend | the plate, not a blank route: `library.list` unavailable keeps the honest "cannot create or add" line | Library door if any | structural (suite) |

Entered work is preserved on failure: the create flow holds its fields, ids and job key across a
retry (`CreateCourseFlow` state is never reset on error) — unchanged by this card; see
`tests/test_desktop_create_flow.py`.

## 4. Measured (light and dark, from `h153-facts.json`)

| Frame | h1 | desk | seals / svg | plate words | primary | secondary | overflow | gutter |
|---|---|---|---|---|---|---|---|---|
| light 1049 | 1 ("Home") | empty | 0 / 0 | 32 | 360×44 | 1 | 0 px | 11.2 px |
| light 900 | 1 | empty | 0 / 0 | 32 | 218×44 | 1 | 0 px | 11.2 px |
| light 460 | 1 | empty | 0 / 0 | 32 | 176×44 | 1 | 0 px | 11.2 px |
| dark 1049 / 900 / 460 | 1 | empty | 0 / 0 | 32 | 360 / 218 / 176 ×44 | 1 | 0 px | 11.2 px |
| 200% light/dark 1049 | 1 | empty | 0 / 0 | 32 | 299×68 | 1 | 0 px | 22.4 px |
| 200% light/dark 460 | 1 | empty | 0 / 0 | 32 | 123×193 (label wraps) | 1 | 0 px | 22.4 px |

Keyboard (real Tab presses, `:focus-visible`): skip link → Home → Courses → Library → Parent
Studio → **Start with a goal**; the host Button paints its 3 px ring
(`oklab(0.527864 -0.0327826 -0.257344 / 0.5) 0 0 0 3px`, border `rgb(26, 23, 19)` light /
`rgb(19, 18, 16)` dark). Reduced motion was emulated for the 200% frames; the plate has no motion
of its own.

Five-second cold task: from the route request to a pressable plate measured **95 ms (light) /
102 ms (dark)**. The script a first-time reader can answer in five seconds — "what do I press, and
what happens next?" — is answered by the plate's only filled control plus its one line:
press *Start with a goal* → name a goal → review the plan → learn; nothing is created until the
plan is approved.

## 5. Findings fixed in this card

1. **The secondary's label was clipped at 460 px.** The host `Button` sets `whitespace-nowrap`;
   at the 460 px window the route column is ~215 px, so `Use a course I already have` was cut
   inside its own box (the page had no overflow, which is why a page-level check missed it). The
   plate now lets the label wrap and keeps `minHeight: 44px`; both labels are complete at 460.
2. **200% text character-wrapped the headline.** The plate's rem padding doubled with the root
   font while the column did not, leaving ~96 px of measure. At a column under 300 px the plate now
   steps the headline to `CB_TYPE.lead` and trims its own inset; words wrap, not letters.
3. **The loading state was a bare spinner.** `sdk.Loader`'s `label` is an `aria-label` only, so the
   cold read showed an unlabelled spinner. Home and Courses now print `Reading your courses.`
   under it.
4. **An unsupported backend rendered a blank route.** `CoursesView` returned `body = null` when
   `library.list` was not mounted; it and the Home desk now render the plate's honest
   "cannot create or add" state.

## 6. Card checks

- Q1 first-screen grasp — 32-word plate, one filled action, 95–102 ms to pressable; script above.
- Q2 one primary — exactly one `variant="default"` control on the plate in every state; the
  secondary is `variant="secondary"`; the error state's retry is its only primary.
- Q5 authored visual — no seal, monogram or decorative mark on the learner surface (0 `svg`);
  one focal hierarchy (headline → line → action).
- Q7 state completeness — first use, loading, failed read, offline and cleared each render with one
  next action; a failed read never renders as an empty profile.
- Q11 copy and truth — no governance vocabulary, no capability inventory, no test/debug content;
  every label maps to a mounted command.

## 7. Out of scope / known limits

- The route column is the shell's: at a 460 px window it is ~215 px, so at 200% text the plate is
  123 px wide and the primary's label wraps to a tall button. Nothing overflows; the column, not
  the plate, is the limit.
- H-109 owns the demo seed. The rig used here is a disposable copy with an empty course table; the
  older rig's `H103 live reject check` row is untouched.
- The M4 visual-audit digest pin must be re-run on this `plugin.js` (same open item H-145 carried).
- Q12 human proof is a reviewer's task; this record is the automated and operator-side evidence.
