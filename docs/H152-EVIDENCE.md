# H-152 — Motion and feedback contract (evidence)

Branch `wt/h152-motion`, base `wt/h149-lesson-player` (bd1ccf8 = H-148 a27231d + H-149) merged with
`wt/h151-action-type` (the CbAction primitive and the research docs). Sources:
`docs/CRAFT-CHANNELS-RESEARCH.md` §4 M1–M3 + §5, `docs/EXPERIENCE-QUALITY-BAR.md` §2.3.

## What changed

One motion table, one hook, four functional beats, no library, no keyframes.

| Beat | Event | Moves | Token | Reduced motion |
|---|---|---|---|---|
| press | pointer down on a `CbAction` | `translateY(1px)`, border colour | `--cb-dur-press: 100ms` | colour only, `transition: none` |
| route settle | path mount | node `opacity .96→1` + `translateY(2px)→0`, 40 ms stagger, **max 8 nodes** | `--cb-dur-route: 180ms` | all at once |
| verdict | graded result arrives | `opacity .9→1` + `translateY(2px)→0` | `--cb-dur-verdict: 160ms` | static |
| completion | close plate | `opacity .88→1` + `scale(.995)→1`, once | `--cb-dur-complete: 600ms` | static |

- `useCbMotion()` is the single source of truth. It returns `{ preference, reduced, duration(beat),
  transition(props, beat), crossfade(props) }`; every duration is a `var(--cb-dur-*)` token painted
  by `cbScopeStyle()`, so no call site can author a fifth duration. `--cb-dur-fade: 120ms` is the
  reduced-motion ceiling, not a beat.
- `useCbSettled()` / `cbSettleFrame()` gate every beat: a beat runs only in a browser frame, only
  while the reader allows motion, and once. A server render or a reduced-motion reader paints the
  resting frame immediately — a static capture is never mid-animation.
- `CbAction` (the H-151 action/row primitive) now carries `data-cb-state`
  (`rest | pressed | selected | disabled | pending`) and the press beat. Pointer-up, pointer-leave,
  pointer-cancel and blur all return it to rest, so a press can never stick. The path's eight-plus
  checkpoint rows, the player footer primary, the close primary and the retry-grading action are all
  `CbAction`s, so the primitive is the only thing a Coursebook button can be.
- Out, and asserted absent by the suite: seal draw, beacon loop, hover lift, parallax, entrance
  choreography, confetti, particles, shake, count-ups, `@keyframes`, `animation:`.

## Live measurement (isolated Desktop, `scripts/h152-motion-capture.mjs`)

Rig `~/.hermes/coursebook-test-h152`, CDP 9367, backend `127.0.0.1:44219`. Full JSON in
`docs/h152-shots/measurements.json`; frames at `route-1049.png`, `route-460.png`,
`route-reduced-460.png`, `press-1049.png`.

| Width | innerWidth | page overflow | route overflow | plugin transitions | host transitions |
|---|---|---|---|---|---|
| 1049 | 1049 | 0 | 0 | 12 | 3 |
| 460 | 459 | 0 | 0 | 12 | 3 |

**Press** (real `Input.dispatchMouseEvent` on the route's primary, 1049):

```
during: data-cb-state=pressed  transform=matrix(1,0,0,1,0,1)   (translateY(1px))
        transition=transform 0.1s cubic-bezier(0.2, 0, 0, 1), border-color 0.1s …
events: 6 × transitionrun(transform) at t=0; 6 × transitionend(transform) elapsed 100 ms
after:  data-cb-state=rest     transform=none
```

**Route settle** (fresh mount, 1049 and 460): 40 `transitionrun` events across the path; every node
carries `opacity/transform 0.18s`; delays measured `0s, 0.04s, 0.08s, 0.12s` for the four objectives
this course has (the cap of 8 is enforced in code and unit-tested with a 10-node path). Nodes past
the cap carry `data-cb-path-node-motion="static"` and no transition at all.

**Measured durations across all plugin transitions: `[100, 100, 180, …]`, max 180 ms.**

**No decorative motion**: `plugin_animations: 0`, `seal_draw: 0`, `plugin_shadows: 0`,
`plugin_gradients: 0`, `max_iteration: "1"`. The page does carry 32 host keyframe rules
(`codicon-spin`, `scroll-fade-top/bottom`, `arc-border`, `starmap-twinkle`, …) — the Hermes host
stylesheet, not Coursebook's. No element inside the route carries an inline `animation`.

**Reduced motion** (`Emulation.setEmulatedMedia prefers-reduced-motion: reduce`): route attribute
flips to `reduced`, `path_in_beat: 0`, every node `transition-delay: 0s`, the primary computes
`transition: none`, `plugin_animated_elements: 0`. The 11 remaining animated elements are host SDK
controls on their own stylesheet. The state changes are still visible (state words, `data-cb-state`,
the verdict copy) — only the travel is gone.

**Layout**: `layout_shift: 0`, page overflow 0, route overflow 0 at both widths; the press beat is a
transform, so it cannot move a box.

## Keyboard and focus

- Focus never animates: no transition lists `outline`, `box-shadow` or `margin`, and no beat writes
  an `outline` style (asserted in `test_focus_is_never_part_of_a_beat`).
- The press beat is pointer-only and always released on `pointerleave`/`blur`, so a keyboard user's
  focused action never sits in a pressed pose.
- Enter still runs the player's footer action (H-149 behaviour untouched; the button is now
  `CbAction primary`, which keeps the host's Enter/Space semantics).

## Test coverage (`tests/test_desktop_h152_motion.py`, 22 tests)

Computed-style surface (React + jsdom, the shipped module):
`CbAction` rest/pressed/released/disabled, the row variant, a 10-node `CheckpointPath`, both
verdicts, and the close plate — asserted for transition properties (⊆ transform, opacity,
border-color), durations (every one a `var(--cb-dur-*)` token; ladder 100/180/160/600 ≤ 600 ms),
delays (0/40/80/120/160/200/240/280 then static), no `box-shadow`, no gradient, `animation-name:
none`, iteration 1, `data-cb-state` on action and row, plus the whole reduced-motion snapshot
(no transition, opacity 1, transform none, no stagger).

Source contract: one `CB_MOTION` table, one `useCbMotion()`, `transition:` literals only `'none'`,
no `@keyframes`/`animation:`/`boxShadow`/gradient, the only Tailwind transition utility is
`transition-colors` (colour-only, in the create flow), and none of the banned decorative beats.

Live evidence gate: the committed capture must show full + reduced preference, zero plugin
animations/shadows/gradients/seal, press + route event samples, and zero overflow.

## Not verified (honest gaps)

- **The verdict and completion beats are render/computed-style proven, not live-proven.** A typed
  answer + `Check` was attempted in the isolated window through the native value setter; the window
  exited before a verdict rendered (the same `Gateway inaccessible (runtime_exited)` fragility H-149
  recorded). Their 160 ms and 600 ms frames therefore come from the jsdom computed-style suite, not
  from a photograph of a graded result. A human cold walkthrough of check → verdict → close is still
  owed, exactly as H-149 left it.
- **60 fps / compositor proof is not claimed.** Durations and properties are measured; a profiler
  trace of the beats is not.
- **Host SDK controls still animate** (11 elements under reduced motion, 3 transitions at 1049).
  They are the host's own stylesheet and outside this card's scope; Coursebook authors none of them.
- The press screenshot (`press-1049.png`) was taken while the action was held; the run's own
  `during` sample is the authoritative reading.
