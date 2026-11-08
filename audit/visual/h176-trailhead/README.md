# H-176 — The Trailhead (Home identity, companion, one Continue)

Evidence for the Home composition named in `docs/FINAL-POLISH-SPEC.md` §3. This is product-line
evidence for one final-polish card, not release evidence. Plugin under test:
`desktop/plugin.js` sha256 `a45b3547aeb015fb5d9d1bcd21203e3eb5e3f9dd39c508687fc67ded33509413`.

## What changed

Home is one object, not a dashboard:

- **Trailhead plate** (`[data-cb-continue]`): `lamp-soft` field with a 3 px `lamp` top edge (plum for
  a parent-authored classroom), a deterministic contour derived from `course_id` + title on the
  right (a narrow band at compact), the course title clamped to two lines, the recorded position,
  the next-stop sentence, the estimate state and last touched.
- **One primary**: the backend's recorded next step, labelled `Continue` / `Start the review` /
  `Start here`. Secondary `Open section`; tertiary `See the plan`. Settings is a small labelled
  control in the route header, outside the action row. There is exactly one action row.
- **Trail**: `CheckpointPath` sits directly below the plate (0.35 rem join), current stop larger,
  next smaller, future quiet; the evidence caption is a count the backend recorded.
- **Shelf**: the existing `SlotRail` data, now drawn as distinct places with each course's contour
  and next stop. `New course` is secondary to Continue.
- **Companion**: the learner's own Hermes pet through `host.request`, meta-first
  (`pet.info.meta`, falling through to `pet.info` on `-32601`), row resolved by the `idle` name in
  `stateRows` (never a hard-coded row 3), cached per live profile, base64 dropped after decode,
  one static frame on an `aria-hidden` canvas. Absent, disabled, unsupported or failed reads render
  nothing; the plate never invents a face. `Study companion` on/off lives in `HomeSettingsSheet`,
  persisted through the existing Home prefs.
- **States**: `ready`, `empty`/first-use, `unavailable`, `loading`, `error`, `parent-only`,
  `archived`, plus stale/offline banners. First-use keeps the plate geometry with a contour ghost
  and one primary; no path is drawn.

## Before / after

The `before/` frames are a clean checkout of `473471b` rendered through the same pipeline at the
same widths. The `01`–`13` frames are this branch.

| Before (`before/01-real-light-1049.png`) | After (`01-real-light-1049.png`) |
|---|---|
| Classroom rail at the top | Trailhead plate with course title + next stop |
| Large section title (“Diagnose a no-start”) | Course title, clamped to two lines |
| Two equal grey actions | One primary, one secondary, one tertiary |
| Flat path list | Path joined under the plate |
| No course identity, no contour, no companion | Deterministic contour; companion only when the host has one |

`before/` contains 1049 light/dark, 900 light/dark, 460 light/dark, 200 % text at 460, and the
backend-off state, so each after frame has a same-geometry counterpart. `13-first-use-light.png`
has no before counterpart: the old tree had no distinct first-use plate.

## The 5-second question (hand-written walkthrough)

**Wide, 1049 px, light (`01`).** First look lands on “THE REVIEW IS DUE”, then the course name, then
one sentence naming the stop (“Section 2 of 4 · Diagnose a no-start is due for another check…”).
The eye finds `Start the review` — outlined in this static render because the SDK stub paints the
primary; the live frame paints it filled — and the other two actions read as lesser. The contour on
the right is quiet enough not to compete. Below, the path starts at the current stop without a card
border around it. Answer: “I am on section 2 of this course, and I should do the review.”

**900 px (`03`).** Same order; the plate narrows, the contour keeps its edge column, the title stays
one line, the action row stays one row. Nothing wraps into a second filled action.

**460 px (`05`, `06`).** The contour becomes a 26 px top band; the companion (when present) sits
beside the label rather than over the title; the action row wraps. The label, title, sentence,
position, estimate and last touch are all still legible before the first scroll. Answer is unchanged.

**200 % text at 460 (`07`).** Root font 32 px: the title is two lines, not more; the action row
wraps but does not clip; `horizontal_overflow` is false; no horizontal scroll. The primary remains
reachable without zooming out.

**Reduced motion (live).** With `prefers-reduced-motion: reduce` emulated, `document.getAnimations()`
is 0 and the companion carries `data-cb-companion-motion="static"`; the plate has no transition, so
the same static composition is the reduced-motion composition.

## Measured (this branch)

Static renderer frames (`evidence.json`, 13 frames):

- `01` ready: label, course title (1 line), next stop, `Section 2 of 4`, `≈ 20 min`,
  `Last touched 2 d ago`; one action row with `Start the review`, `Open section`, `See the plan`;
  plate → path → shelf tops 20 → 265 → 884; 3 contours (plate edge + two shelf covers);
  2 shelf courses; no table; no horizontal overflow.
- `05`/`06` 460 light/dark and `07` 200 %: title ≤ 2 lines, one action row, no overflow.
- `13` first-use: `first_run_contour` true, 2 buttons (`Start with a goal`, `Use a course I already
  have`), zero path items.
- `08` unavailable, `09` loading, `10` error (one retry), `11` backend-off, `12` keyboard focus on
  the current path row.

Live Desktop (`live-check.json`; rig `~/.hermes/coursebook-test-h176a`, CDP 9376; the plugin file in
that rig hashes to the sha above):

- Home at a 1049 px window (route column 567 px): `data-cb-desk="ready"`, label, course title,
  sentence, position, estimate, last touched; one action row; 4 path items; 2 shelf courses;
  plate 196 < path 541 < shelf 1296; no horizontal overflow.
- **Primary opens the real destination**: clicking the first action lands on
  `[data-cb-course-detail="overview"]` — the recorded review opens Course Detail, not a mock route.
- `Open section` lands on `[data-cb-course-detail="textbook"]` for the same course.
- Settings: `Show my study companion` is present on the sheet, `aria-checked="true"`, and Escape
  closes the sheet without moving the route.
- Reduced motion at a 459 px window (route column 214 px): 0 animations, no overflow, same three
  actions.
- Companion in this rig: absent. The rig's host profile has no pet installed, so the plate draws
  nothing — the honest fallback, not a placeholder face. A pet installed mid-run did not appear
  because the host gateway caches the pet profile and the card forbids restarting it; the DOM
  harness proves the visible case with the real payload shape below.

## Companion seam tests

`tests/test_desktop_field_desk.py::test_the_companion_appears_only_when_a_real_pet_answers` renders
the shipped component with a scripted host that refuses `pet.info.meta` with `-32601` and answers
`pet.info` with `{enabled, slug, displayName, mime, spritesheetBase64, spritesheetRevision, frameW,
frameH, stateRows}`:

- without `host.request`: no `[data-cb-companion]`, Continue still enabled;
- with it: one `[data-cb-companion]` with a canvas, `data-cb-companion-motion="static"`, and the
  pet's `displayName` in adjacent visible copy. The meta refusal proves the fall-through path.

## Gates

- `node --check desktop/plugin.js` — clean.
- `python3 -m unittest tests.test_desktop_home_hub tests.test_desktop_field_desk
  tests.test_desktop_h147_home_settings tests.test_desktop_h174_empty_textbook
  tests.test_desktop_tokens tests.test_desktop_type_scale` — 128 tests OK.
- The same set plus `tests.test_desktop_h28_copy tests.test_desktop_contracts
  tests.test_desktop_control_paths tests.test_desktop_h151_action_type` — 219 tests OK.
- **M4 re-run** (`python3 scripts/m4v-audit.py`, scratch out, plugin sha above): 15 PASS, 0 not PASS.
  The pinned `audit/visual/m4-visual/` record is intentionally not replaced by this card.
- H-146 capture facts and the two architecture docs were amended in the same commit so M4 and the
  rail doc do not read the contour or the canvas companion as the retired H-145 seal/avatar.

## Honest limits

- The `01`–`13` frames are a static render of the shipped module in Chromium: no backend, no chat,
  no RPC. The live paragraphs above are the behaviour proof.
- The before set was rendered from `473471b` with the same scripts, but through that tree's own
  `scripts/h176-frames.py` copy; it is a static render, not a screenshot of the old app.
- The live rig is an isolated home; the operator profile and gateway were not touched, restarted or
  published. No live companion frame exists because no pet is configured for that rig's host
  profile and the gateway may not be restarted. The plate without a companion and the plate with
  one are both proven; only the second is not photographed against the live host.
- The keyboard frame proves focus reaches the current path row with a visible ring; it is not a
  full tab-order audit (the M4 keyboard claim covers that).
