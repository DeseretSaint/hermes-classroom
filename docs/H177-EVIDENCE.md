# H-177 — Path: the trail, not a table: evidence

Branch: `wt/h177-trail`, base `80eecce` (integrated master: H-176 Trailhead, H-184 lessons unit facts).
Module: `desktop/plugin.js` sha256 `6aeca2214aed058aec08688fdd12eeb73003c18fa0bc8f9b122564ec1fbf6d4f`.

## What changed

`CheckpointPath` still owns the same honest data — one `<ol>`, every objective a real node,
`aria-current="step"` on exactly the current one, no locked node, backend `state` and `check_state`
words, one evidence count and no invented XP or percentage. What changed is the reading of it:

- **Geometry.** One continuous 1.5 px `--cb-rule` route, drawn as two decorative `aria-hidden` SVG
  halves per row. At wide it bows between stops at x = 64 ± 32 px around the route centre line
  (a 64 px lateral swing, inside the spec's 48 px-per-side cap); at 620 px and below the same code
  paints a straight spine. Every stop's text column is fixed at the route gutter (128 px wide,
  44 px compact), so the drawing never moves the reading column. A failed line-to-marker
  measurement is a hard evidence error, not a rounding note: the live probe compares the enter
  path's endpoint with the marker's centre and reports `alignmentErrors`.
- **Perspective.** Current 56 / 44 px, next 40 / 32, done and future 28 / 24 (unchanged from
  H-148's measured decision). The current stop gets one 2 px accent ring and one flat
  `--cb-accent-soft` halo disc — no shadow, no pulse, no loop. Done/future titles drop to
  `--cb-ink-soft`; current and next keep full ink.
- **Gates.** A diamond is drawn on the route only when the backend's `check_state` is not `none`,
  and it disappears when it is. The check word beside the stop is the backend's own
  (`Check closed` / `Check open` / `Check replaced` / `No check yet`). No diamond exists for a
  course with no recorded checks.
- **Place labels and header.** `Start` before the first stop and `Course end` after the last
  (a position label, never a completion claim). The run header is assembled only from recorded
  facts: `Review · Section 1 of 4 · ≈ 8 min · Next: Checkpoint 2 · <title>`. With no recorded
  estimate the minutes segment is absent (tested); `Next` is the next node in reading order, not
  a guessed checkpoint.
- **Details.** The `<details>` disclosure under every row is gone. Only the current and next stops
  carry one honest detail line (evidence target in learner words · committed attempts · last
  opened). Done and future stops stay collapsed.
- **Companion.** One 32 px `StudyCompanion` at the current stop's trailing edge at wide, with its
  own name as the visible adjacent copy. It renders only when the host's `pet.info` seam returns a
  usable sheet, is hidden below 620 px and under `prefers-reduced-motion`, and is never the only
  position marker: `aria-current="step"` and the state word stay on the row.
- **Motion.** The existing route-settle beat still runs nodes `scale(0.96) → 1` with a 40 ms
  stagger capped at eight; reduced motion is static (no transition, no staggered delay).
- **Keyboard.** `PathStop` owns a focus state: a focused row paints a static 2 px
  `--cb-accent` outline (offset 2 px). Focus is not a beat; it is not part of any transition.

## State matrix (rendered, `audit/visual/h177-trail/after/shots/09-matrix-light-1049.png`)

| # | backend `state` | `check_state` | gate diamond | state word | check word | detail line |
|---|---|---|---|---|---|---|
| 1 | `not_started` | `none` | no | Not started | No check yet | no |
| 2 | `introduced` | `none` | no | Started | No check yet | no |
| 3 | `independent_evidence` | `closed` | yes | Evidence | Check closed | no |
| 4 (current) | `review_due` | `open` | yes | Review due | Check open | yes |
| 5 (next) | `needs_review` | `open` | yes | Needs review | Check open | yes |
| 6 | `overridden` | `superseded` | yes | Overridden | Check replaced | no |
| 7 | `not_started` | `open` | yes | Not started | Check open | no |

Overridden is its own word and is not counted as evidence (`desk.settled` is 1, from stop 3 only).

## Static frames (`audit/visual/h177-trail/{before,after}`, same measurement code)

Rendered from the shipped module inside the route wrapper by `scripts/h177-path-frames.py`, then
measured in Chromium by `scripts/h177-path-shot.mjs`. The before set is the same pipeline pointed
at `git show HEAD:desktop/plugin.js`.

| fact | before (base `80eecce`) | after |
|---|---|---|
| route SVGs | 0 | 8 (2 per stop), all `aria-hidden="true"` |
| marker centres at 1049 | `[28, 28, 28, 28]` | `[32, 96, 32, 96]` |
| marker centres at 460 | `[22, 22, 22, 22]` | `[22, 22, 22, 22]` (straight spine) |
| line-to-marker alignment errors | — | 0 at every frame and width |
| `<details>` disclosures | 4 | 0 |
| detail lines | 0 (4 disclosures instead) | 2 (current + next only) |
| halos | 0 | 1, current only |
| gate diamonds | 0 | 3 in the 4-stop course; 5 in the state matrix |
| Start / Course end | absent | present at every width |
| run header | absent | honest position + recorded estimate + next stop |
| overflow (page / route / path) | 0 / 0 / 0 | 0 / 0 / 0 at 1049, 900, 460 and 200% text |

Frames: 1049/900/460 in light and dark, 200% text at 460 and dark 1049, the state matrix at 1049
and dark 460, no-estimate, keyboard frame, reduced-motion frame. `evidence.json` carries the raw
numbers, including `focusRow`, marker boxes, segment boxes and stroke widths.

## Live facts (isolated rig `~/.hermes/coursebook-test-h177`, CDP 9381)

`scripts/h177-live-check.mjs` — real Desktop, real backend, the new module loaded at window start.

| window | route width | layout | centres | sizes | overflow | animations |
|---|---|---|---|---|---|---|
| 1049 | 813 | full | `[32, 96, 32, 96]` | `[56, 40, 28, 28]` | 0 | 0 |
| 900 | 663 | full | `[32, 96, 32, 96]` | `[56, 40, 28, 28]` | 0 | 0 |
| 460 | 460 | compact | `[22, 22, 22, 22]` | `[44, 32, 24, 24]` | 0 | 0 |

Every live node reported `lineX === markerX` and `lineY === markerY` (no alignment errors). The
path carried 1 halo, 2 detail lines, 0 `<details>` elements, 4 gate diamonds (this live course has
`Check open` on all four objectives), one `aria-current="step"` and 4 list items in one `<ol>`.

Keyboard, from real `Tab` presses: the header controls, then `Checkpoint 1`, then
`Checkpoint 2`. The focused row carried the host's 3 px ring **and** the plugin's
`2px solid var(--cb-accent)` row outline (`data-cb-path-focused="true"`). Pressing `Enter` on the
focused stop opened the real destination: Course Detail / textbook,
`Section 2 of 4 — Choose the polite expression for a first confession` — the same stop that was
focused.

Reduced motion (`Emulation.setEmulatedMedia` reduce): 0 animations, every node static, no
companion, no overflow.

Screenshots: `audit/visual/h177-trail/live/live-{1049,900,460}.png`,
`live-keyboard-focus-1049.png`, `live-keyboard-destination.png`,
`live-reduced-motion-1049.png`; facts in `live-check.json`.

## Companion

The live rig profile has no usable pet sheet (its `pets/` directory is empty), so the live capture
honestly renders no companion. The placement and its three gates are proven by mounting the
shipped component with the SDK's `CB_TEST_PET` seam:
`tests/test_desktop_h177_trail.py` asserts one 32 px companion with the pet's name at the current
stop at 1049, none at 460, none under reduced motion, and `aria-current`/state word present in all
three cases. This is the same limitation H-176 recorded; no invented avatar was added.

## Tests

- `python3 -m unittest tests.test_desktop_h148_path_truth tests.test_desktop_h157_detail_quest tests.test_desktop_h152_motion tests.test_desktop_home_hub` — 67 OK.
- `python3 -m unittest tests.test_desktop_h177_trail` — 7 OK (companion, narrow, reduced motion, list/decorative SVG, gates, detail lines, focus ring).
- `python3 -m unittest discover -s tests -p 'test_desktop_*.py'` — 739 OK.
- `node --check desktop/plugin.js` — OK.
- `python3 scripts/m4v-audit.py` — re-pinned `audit/visual/m4-visual` to
  `6aeca221…`; 15 PASS, 0 not PASS.

Deliberate test updates (geometry/content changed by this card, not regressions):

- `tests/test_desktop_h148_path_truth.py`: current/next detail assertions now describe the one
  detail line (4 disclosures removed), plus new place-label, halo, gate and run-header tests.
- `tests/test_desktop_field_desk.py`: the title-wrap source contract now reads `PathStop`, where
  the row moved; the contract itself is unchanged.
- `scripts/h148-capture.mjs`: reads the marker size from the row, since the marker is no longer
  inside the button's content span.

## Known limits

- No live companion frame: the rig profile has no pet sheet; the jsdom suite proves the
  component's three postures.
- The 460 px window has a 460 px route once the host sidebars are collapsed; at wider windows the
  route pane is 813 / 663 px, which is the product's real reading width. Both the frame set and
  the live set measure the route, not the app window.
