# GM-002 scorecard — maker's draft (not a review)

The maker may not certify this card. This draft exists so `quill` has a filled starting point; the
reviewer changes the numbers and the verdict.

Screen: `home.global` (concept F1 `home-generic-first-open.png`) and `home.course` (F3
`refined-classroom.png`). All nine dimensions, 1–5; pass requires every dimension ≥ 4.

| Dimension | home.global | home.course | Evidence / note (required below 5) |
|---|---|---|---|
| Focal hierarchy | 4 | 4 | one filled create action on Home; Continue is the only primary on the course home |
| Composition | 4 | 4 | invitation band + one shelf row with authored card widths (17/13/15 rem), not an equal grid; course home keeps the existing trail composition |
| Type | 5 | 5 | six-step scale only; invitation at `heading`, card titles at `lead`, no authored sizes |
| Palette and texture | 5 | 5 | parchment/ink/ochre/coral tokens only; no raw hex in the render; dark frame from the same table |
| Illustration | 4 | 4 | text-derived paper covers with the subject monogram and subject only; the card heading is the single title (and a real artifact when a row carries one); course world hero is GM-004 |
| Card/game system | 4 | 4 | tactile cards with real next step and a real `world.read` mode badge; no stars, ratings or XP |
| State coverage | 5 | 5 | empty, loading, error, offline, overflow for Home; loading, error, no-outline for course home; overflow paints the spec's 24 px edge mask, proven by an on/off pixel diff at the same scroll (1018 changed px in the right band) |
| Responsiveness | 5 | 5 | 1049/900/460, 200 % text (root 32 px), no horizontal document overflow in any frame; global Home carries `--full` cells at 460/100, 1049/200 and 460/200 showing the whole shelf and `See all` |
| Truth | 5 | 5 | every label DOM text; mode badge only from a real read; no invented progress |

Known gaps carried into review:

- Keyboard ring: the live focus capture shows the authored 2 px `--cb-accent` ring on the primary
  (`data-cb-focus-ring="visible"`, outline recorded in `live-evidence.json`); the computed width is
  reported at ≈1.12 px because this Electron build renders the page at ≈0.896 zoom.
- Cards use paper covers because no course world exists yet (GM-004 owns the hero/cover art).
- `home.course` world states (running/partial/stale) and `course-end` are GM-004 scope; this packet
  captures default, no-world, plan-in-review, loading, error and the responsive/focus cells.

Round-4 resubmission (plugin `bca1bcbe…`): the two defects from review round 3 are fixed and
recaptured live — the `overflow` cell now shows GM-VISUAL-SPEC §2.5's 24 px `paper`→transparent
mask as a real `mask-image` on `[data-cb-home-shelf-row]` (measured `data-cb-shelf-mask="both"`
while parked mid-scroll, computed `maskImage` recorded in `live-evidence.json`, and an on/off pixel
diff at identical scroll changes 1018 px in the right 24 px band and 559 px at the left); global
Home now carries `home.global--460--light--100--full.png`, the 460/100 screen that scrolls. Round-3
items are retained: each card paints its title once, and the 200 % `--full` cells include the shelf
and `See all`.

Verdict: **REQUEST REVIEW** — reviewer decides.
