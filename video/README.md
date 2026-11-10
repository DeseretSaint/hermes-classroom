# Launch film — motion system (CP-035 scaffold)

The Remotion project for the Coursebook launch film. Binding spec:
[`docs/launch/VIDEO-PLAN.md`](../docs/launch/VIDEO-PLAN.md). This directory owns
**one thing**: the motion system — tokens, components, the eleven beats and their
timings — so that CP-033c only has to drop real captures in and render.

Right now every capture slot renders a labelled placeholder. The end card (B11)
is final, because it is graphic, not a capture.

## Run it

```bash
cd video
npm install                       # once
npm run render:75                 # → out/scaffold-75s.mp4, 2250 frames @ 30 fps
npm run render:30                 # → out/scaffold-30s.mp4, 900 frames
npm run check:fonts               # proves the bundled faces are really used
npm run check:copy -- out/scaffold-75s.mp4   # OCRs the render against the §4 deck
npm run typecheck
```

Chromium is taken from `/usr/bin/chromium` (`--browser-executable`). The bundled
Chrome headless shell works too if it is already cached.

## What was measured on this scaffold

| Check | Result |
|---|---|
| `ffprobe` Hero75 | h264 High, 1920×1080, yuv420p, `30/1`, **2250 frames**, 75.000 s, 3.08 MB |
| `ffprobe` Hero30 | 1920×1080, `30/1`, **900 frames**, 30.000 s, 1.27 MB |
| `scripts/check-copy.sh` | 27/27 §4 strings found in `out/scaffold-75s.mp4` at the frames §3 puts them |
| `scripts/check-fonts.sh` | 5/5 — SS3 400/600 and Fraunces roman/italic are all distinct from the serif fallback |
| `tsc --noEmit` | clean |
| scene cuts (`select=gt(scene,0.15)`) | 3.5, 7.5, 11.0, 14.0, 70.0 s — placeholder→placeholder cuts at 24/38/47/56/64 s are below the threshold because both sides are the same card stock; the copy audit proves those beats changed |
| `blackdetect` | one run, 74.833–74.967 s (4 fully black frames at the tail fade) — inside the §9 allowance |

`out/` is gitignored: the mp4 is a build product, the sources are the deliverable.

## Dropping a capture in is one line

Every beat picture comes from `src/captures.ts`. A slot with `file: null` renders
`PLACEHOLDER <beat-id>`; a slot with a file renders the real capture, cropped:

```diff
  'beat-05 create-topic': {
    state: 'create-topic-light',
-   file: null,
+   file: 'captures/beat-05-create-topic-1920-light.png',
    routeWidth: 1920,
    crop: {x: 0, y: 0, w: 1920, h: 1080},
  },
```

Put the PNG in `public/captures/` and that is the whole change. Geometry does not
need touching: `routeWidth` is the *logical* width of the captured route (1920 px
per plan §6), so a 2× capture of 3840 px produces identical framing and only buys
sharpness under the push. Change `crop` only when you want a tighter region than
full bleed — the maths in `src/components/Crop.tsx` derives the scale factor from
`crop` and the frame, never from the image's pixel size.

Slots, in beat order (`state` is the plan §6 name the still must carry):

| slot | state | used by |
|---|---|---|
| `beat-04 home` | `home-1049-light` | B04 |
| `beat-05 create-topic` | `create-topic-light` | B05 (0–60 %) |
| `beat-05 plan-sections` | `plan-sections-light` | B05 (60–100 %) |
| `beat-06 classroom-line` | `classroom-line-light` | B06 (0–42 %) |
| `beat-06 classroom-check` | `classroom-check-light` | B06 (42–72 %) |
| `beat-06 classroom-feedback` | `classroom-feedback-light` | B06 (72–100 %) |
| `beat-07 tutor-cited` | `tutor-cited-light` | B07 |
| `beat-08 game-challenge` | `game-challenge-light` | B08 (0–67 %) |
| `beat-08 game-complete` | `game-complete-light` | B08 (67–100 %) |
| `beat-09 parent-observation` | `parent-observation-light` | B09 |
| `beat-10 discover-grid` | `discover-grid-light` | B10 |

Beat 7's 2 px terracotta underline is also manifest-driven: set
`highlight: {x, y, w, h}` (logical px, within the crop) and the line draws there
over 9 frames. Left unset, no underline is drawn — it is never guessed.

## Structure

```
src/
  index.ts          registerRoot
  Root.tsx          compositions Hero75 (2250) and Hero30 (900)
  schedule.ts       the beat table, frame numbers copied from plan §3
  tokens.ts         palette + type scale from plan §5, motion bounds from §7
  captures.ts       the capture manifest (above)
  fonts.ts          bundled woff2, loaded locally, failure-loud
  Cut.tsx           renders a schedule, plus the 6-frame tail fade
  beats/B01Hook.tsx … B11End.tsx
  components/
    Push.tsx        scale-only push (3–6 %), optional lateral pan
    Crop.tsx        2×-capture placement maths
    Caption.tsx     lower third, 44 px Source Sans 3 600, 120 px margins
    TypeCard.tsx    Fraunces 600 display, 96–132 px, −1.5 % tracking
    Placeholder.tsx labelled capture slot
    CaptureScene.tsx capture-or-placeholder switch
  FontProbe.tsx     A/B rows used by scripts/check-fonts.sh
public/
  fonts/            Fraunces 600 (rom + italic), Source Sans 3 400/600 + OFL texts
  captures/         drop the real stills here
```

## Rules the code enforces

- **Palette and type come from `tokens.ts`.** No hex or size is declared anywhere
  else; `tokens.ts` holds exactly the §5 values.
- **Push is scale-only and clamped to 3–6 %**, with `cubic-bezier(.2,.8,.2,1)`.
  Beat 9 passes `delta={0}` because §3 gives it a 40 px lateral pan and a hold.
- **Safe area**: 120 px margins; the caption's bottom edge sits at y ≈ 952, above
  the y = 972 limit for X's player chrome.
- **Copy is the plan §4 deck, verbatim**, one message at a time. Display lines are
  broken by hand to stay inside the 18-character cap.
- **Nothing draws product UI.** Placeholders are dashed and labelled; the XP chip
  in B08 and the cursor/typing in B05 belong to the capture (see the comments in
  `B08Game.tsx` / `B05CreateTopic.tsx`).

## Fonts: no network at render

The four woff2 files are committed under `public/fonts/` (Fraunces 600 roman and
italic, Source Sans 3 400 and 600) with their OFL licence texts. `src/fonts.ts`
registers them with `@font-face`, waits on `document.fonts.load`, then **checks**
each descriptor and cancels the render if a face is missing.

This is not belt-and-braces. `font-family: Source Sans 3` written unquoted is an
*invalid* declaration (`3` is not a CSS identifier), React does not add quotes, and
Chrome then silently substitutes Times. The first scaffold render shipped exactly
that: type that looked plausible and was the wrong face. `npm run check:fonts`
renders an A/B probe and fails if a bundled face is pixel-identical to the serif
fallback.

## Two recorded decisions and one plan discrepancy

1. **`Hero30` split.** The plan fixes the cutdown's beat list (1, 3, 4, 5, 6, 11)
   and its 900 frames, not the per-beat split. `schedule.ts` keeps the hero's
   proportions for the proof beats (B05 and B06 at 9 s each) inside 900 frames.
2. **"Built with Hermes"** is set in Fraunces 600 italic (the signature line under
   the wordmark) rather than adding a fifth face for Source Sans 3 italic.
3. **Discrepancy — the tail fade.** Plan §3 rule 1 says "the 6-frame fade at
   74.4–75.0 s", which is 0.6 s = 18 frames. The quantity ("6-frame") is what the
   QC rule in §9 item 4 allows, so this project implements a **6-frame** fade
   (frames 2244–2250) and flags the time range as inconsistent in the plan.

## Not in this card

Audio, music, SFX and the final encode/loudness pass belong to CP-036 and
CP-033d. Real captures belong to CP-033b. This scaffold renders picture only.
