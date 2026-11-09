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
| Illustration | 4 | 4 | text-derived paper covers with subject monogram (and real artifact when a row carries one); course world hero is GM-004 |
| Card/game system | 4 | 4 | tactile cards with real next step and a real `world.read` mode badge; no stars, ratings or XP |
| State coverage | 5 | 5 | empty, loading, error, offline, overflow for Home; loading, error, no-outline for course home |
| Responsiveness | 5 | 5 | 1049/900/460, 200 % text (root 32 px), no horizontal document overflow in any frame |
| Truth | 5 | 5 | every label DOM text; mode badge only from a real read; no invented progress |

Known gaps carried into review:

- Keyboard ring: the live focus capture shows the authored 2 px `--cb-accent` ring on the primary
  (`data-cb-focus-ring="visible"`, outline recorded in `live-evidence.json`); the computed width is
  reported at ≈1.12 px because this Electron build renders the page at ≈0.896 zoom.
- Cards use paper covers because no course world exists yet (GM-004 owns the hero/cover art).
- `home.course` world states (running/partial/stale) and `course-end` are GM-004 scope; this packet
  captures default, no-world, plan-in-review, loading, error and the responsive/focus cells.

Verdict: **REQUEST REVIEW** — reviewer decides.
