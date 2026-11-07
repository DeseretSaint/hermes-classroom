# M2-V1 evidence: Ink & Field Notes token layer and route shell

Method: `scripts/m2v-frames.py` renders the shipped `desktop/plugin.js` (the real React
components, the real SDK stub used by the render tests) into self-contained HTML documents inside
the same `[data-cb-scope]` root the Coursebook route paints. `scripts/m2v-shot.mjs` then loads
them in headless Chromium (CDP), emulates `prefers-reduced-motion`, captures a PNG at 2x and reads
the painted DOM into `evidence.json`.

Honest scope: this is a **renderer audit of the shipped module**, not a live-app capture. No
backend, chat, RPC or gateway is involved, and the media frame below is a presentational render of
`MediaFrame`, not bytes served by the artifact route. The route-shell layout, the painted token
values, the 200% root-font measurement, the 460px reflow and the reduced-motion posture are real
measurements of the shipped code.

Reproduce:

```
python3 scripts/m2v-frames.py
node scripts/m2v-shot.mjs audit/visual/m2-ink-field-notes
```

## Frames

| Frame | Width | Root font | Layout | Rail |
|---|---|---|---|---|
| `01-light-wide.png` | 1280 | 16px | wide | side |
| `02-dark-wide.png` | 1280 | 16px | wide | side |
| `03-light-460.png` | 460 | 16px | stacked | bottom |
| `04-dark-460.png` | 460 | 16px | stacked | bottom |
| `05-dark-200pct.png` | 1280 | 32px | wide | side |
| `06-dark-460-200pct.png` | 460 | 32px | stacked | bottom |
| `07-light-reduced-motion.png` | 1280 | 16px | wide | side (motion preference recorded) |

Every frame reports `horizontal_overflow: false`, the ten painted `--cb-*` values for its mode,
`media_caption / media_provenance / media_text_equivalent` true, and the title's computed font size
(32px at a 16px root: the shell title is `clamp()` in `rem`, so 200% text scales).

## What the DOM shows

- Light paints `paper #f7f3ea` / `ink #191713`; dark paints `paper #141312` / `ink #f2ece0` from the
  same token table, on the same root, with no host patch.
- At 460px the rail is a stacked bottom section (`data-cb-rail-slot="bottom"`) and the reading
  column is `max-width: 100%`; the grid is not used.
- At a 32px root font the reading column and rail both scale (all shell type is `rem`/`clamp`);
  nothing clips and there is no horizontal scroll.
- The reduced-motion frame records `data-cb-motion="reduced"`. The shell contains no transitions
  at all, so reduced motion is satisfied by construction rather than by a media query a plugin
  cannot ship.

## Not claimed

- Not a live backend lesson. No `lesson.page` RPC was called; no artifact bytes were served.
- Not a keyboard-interaction run and not a screen-reader pass. Tab order and semantics are the
  host primitives' own (`sdk.Button`, `sdk.SegmentedControl`) and are covered by the render tests.
