# Visual review evidence — how to use this directory

Every visual card (GM-002, GM-004, GM-006, GM-008, GM-010, GM-012, GM-014) and the final parity card
(GM-016) puts its evidence in `docs/visual-review/<card-id>/`. The reviewer needs no briefing beyond
this file, `docs/GM-VISUAL-SPEC.md` and `docs/GM-CONCEPT-PARITY-RUBRIC.md`.

```
docs/visual-review/
  README.md                 this file
  MATRIX.md                 the human-readable matrix (source: matrix.json)
  matrix.json               the machine source of required screens and states
  SCORECARD-TEMPLATE.md     copy per card, fill, commit
  gm-002/                   one directory per card
    MANIFEST.md
    home.global--1049--light--100--default.png
    …
    SCORECARD.md
```

## 1. Capture rules

1. **From the running app.** No mockup, no composite, no generated screenshot, no upscaled image.
   A capture that cannot be tied to a commit is not evidence.
2. **Viewport widths are CSS pixels**: 1049, 900, 460. Height 900 unless the screen scrolls, in which
   case capture the first viewport and one full-page capture marked `--full`.
3. **Text scale** is the root scale: `100` or `200`. At 200% the OS/browser zoom may be used, but the
   capture must show the same CSS viewport width.
4. **Mode** is `light` or `dark`. The host theme is switched by the app, not by devtools injection.
5. **State** comes from the screen's state list in `matrix.json`. A state that cannot be produced
   without a backend failure is produced with the documented failure switch and named in
   `MANIFEST.md`.
6. **Reduced motion** and **focus** captures are required where the screen animates or has a focus
   target. The focus capture must show the 2px `accent` ring on the primary control.
7. File name: `<screen>--<width>--<mode>--<scale>--<state>.png`. No spaces, no dates in names; the
   manifest carries the date and commit.

## 2. Required cells per screen

From `matrix.json.required_cells` — eight baseline cells, plus one capture per named state at
1049/light/100 unless the state is already one of the baseline cells:

| Cell | What it proves |
|---|---|
| `default@1049/light/100` | the composition against the concept frame |
| `default@1049/dark/100` | the token table in dark mode |
| `default@900/light/100` | the first collapse |
| `default@460/light/100` | the narrow layout |
| `default@1049/light/200` | no clipped primary at 200% text |
| `default@460/light/200` | narrow + 200% |
| `focus@1049/light/100` | visible focus ring |
| `reduced-motion@1049/light/100` | static under reduced motion |

A screen with a missing cell fails **State coverage** and **Responsiveness** in the rubric.

## 3. MANIFEST.md (copy into each card directory)

```markdown
# <CARD> evidence manifest
Branch: wt/<branch>   Commit: <sha>   Captured: <ISO date>   Captured by: <profile>
App build: <plugin pin / desktop commit>
Viewports: 1049 / 900 / 460 · Modes: light, dark · Text scale: 100, 200

| File | Screen | Viewport | Mode | Scale | State | Concept frame | Notes |
|---|---|---|---|---|---|---|---|
| home.global--1049--light--100--default.png | home.global | 1049 | light | 100 | default | home-generic-first-open.png | |
```

## 4. Reviewer checklist

- [ ] Every screen in the card's scope has a directory row in `MANIFEST.md`.
- [ ] Every required cell exists and is a real capture (open it; a blank or cropped frame is a fail).
- [ ] Each screen names its concept frame and region (`docs/GM-CONCEPT-PARITY-RUBRIC.md` §3).
- [ ] `SCORECARD.md` is filled with all nine dimensions and the five anchors per screen.
- [ ] Any score below 5 has one sentence of evidence.
- [ ] No invented rating, XP outside Game, percentage, credential, or generated screenshot.
- [ ] Verdict is `PASS` or `REQUEST CHANGES`; a maker's own scorecard is not a review.

## 5. What is not evidence

- A test log. Tests prove behaviour, not composition.
- A description of the intended screen.
- A single happy-path screenshot at one width.
- A screenshot taken from a branch other than the one submitted.
- The concept frame itself, captioned as if it were the product.
