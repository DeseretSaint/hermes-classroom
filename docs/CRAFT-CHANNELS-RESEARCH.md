# Craft channels: the layer the quality bar doesn't yet specify

**Status:** research note, 2026-11-07. Subordinate to `docs/UX-RESEARCH-STANDARDS.md` and
`docs/EXPERIENCE-QUALITY-BAR.md`; proposes amendments, changes no code. Counts reproducible with
`grep` on `desktop/plugin.js` at `0e37cda`.

**Question:** why does a correct, calm, honest system still read as "formatted text and buttons,"
and what would make it feel designed without slop?

**Method:** public product and design sources plus peer-reviewed learning science; vendor posts
labelled; a design survey, not a controlled study.

## 1. The gap is temporal, not decorative

The shipped module — 17,703 lines — has **one** `transition-colors` class in its own styles (two
other `transition` hits are comments), **zero** `@keyframes`, **206** `sdk.Button` references and
**three** Codicon icons. Its feedback vocabulary is a colour change, a focus outline and the native
button state. Nothing has weight, arrives or settles.

That is why it reads as text: a screen without a temporal channel is a document. The fix is not
ornament — gradients, shadows and glass are already refused — it is to allocate craft across the
channels a learning product uses, with a job and a budget for each. Visual judgement forms in about
50 ms [1], and attractive interfaces are judged more usable than plainer ones with the same function
[2]. The first frame is a claim about competence.

## 2. Three lenses

**Calm** (Linear): does anything compete for attention it hasn't earned? [3] **Alive** (Duolingo,
Things): is there one physical cause-and-effect that answers the learner? [4][5] **Honest**
(Coursebook): is every claim traceable to a recorded fact? Only calm gives formatted text — the
current state; only alive gives slop; only honest gives an audit report. `QUALITY-BAR.md` permits
"one authored functional beat" but never defines it. That is the gap.

## 3. What transfers

Duolingo contributes one route, one next node and a reaction at the point of effort [4]; Brilliant,
a manipulable visual with instant feedback about the answer [6]; Linear, chrome that recedes and
structure felt through space [3]; Things, whitespace and one signature spatial interaction [5];
Notion, a single illustrator's line voice and close crop [7]; Apple HIG, feedback matched to
significance and motion that is optional and cancellable [8][9]; Material 3, a finite duration-token
ladder (50 ms–1 s) and state layers [10][11]; game UI, causal layering where sound is the cheapest
juice and juice without context is noise [12]. Refuse their costumes: mascots, streak pressure, XP
economies, power-user density, platform materials, screenshake.

## 4. Channel rules

Numbers are proposed review thresholds, not measurements.

### Composition

- **C1 One object.** Name it in one noun; it owns the only lamp field, ≥1.75rem type and ≥35% of
  first-viewport ink. On the Field Desk that is the route, not the fact card.
- **C2 Perspective on the path.** Current 56 px + 2 px accent ring + flat `lamp-soft` halo; next 40;
  future 28; done 28 filled `field`; at 460: 44/32/24. Size and ink fall with distance — real
  position, not progress theatre.
- **C3 Depth by overlap.** Paper, raised + 1 px rule, overlay + rule. One overlap per screen — a
  raised label tucked 24 px over the plate edge. Occlusion survives forced colors.
- **C4 Squint and greyscale.** At 5% zoom: one dark mass, one accent mass. In greyscale: three
  values. Otherwise hierarchy is colour-only [13].

### Illustration

- **I1 Encode or delete.** Identity, position or state; remove it and meaning is lost. Duolingo uses
  "the fewest details" silhouetted in negative space [14]; Mayer's coherence principle says
  extraneous pictures reduce learning [15].
- **I2 Plate scale only.** Hero, empty, completion, checkpoint; one per viewport; never a row, chip,
  button or nav item; `aria-hidden`, beside text.
- **I3 One grammar.** Square, arc, meridian, dot; 1.6 px stroke; 96/64/40/28 px; four marks — seal
  (identity), route (position), gate (checkpoint), horizon (empty/complete). Notion's single line
  [7], no mascot, no generated art.

### Iconography

- **N1** Codicon only, 16 px UI and 20 px plate, matched to text weight. SF Symbols aligns
  automatically [16]; Codicon does not.
- **N2** Icons replace repeated words, never decorate unique ones; no icon per row, no coloured
  tiles (Linear cut both [3]). State is a word + 2 px underline + tint, never a second glyph.

### Motion

- **M1 Caused, not scheduled.** Every animation names its event. No entrance choreography on repeat
  visits, scroll reveal, hover lift or parallax.
- **M2 Ladder.** Press 90–120 ms; state 160–200 ms; panel 240–300 ms; celebration 450–600 ms, once
  [10]. Our cap: nothing over 600 ms except progress. Transform/opacity only; one moving element per
  interaction; focus in one frame.
- **M3 Reduced motion is designed.** Every effect keeps meaning as a static or ≤120 ms crossfade
  [17]; Apple's standard is purposeful, brief, cancellable [8]. No sustained oscillation.

### Sound and haptics

- **S1 Off by default, persisted.** Three state one-shots — recorded, needs you, complete — at
  ≤120 ms, −18 LUFS, synthesised (`OscillatorNode` + gain envelope; no assets). Unlock on first
  pointerdown; never hover, navigation or typing; no loop; state signals, not reward jingles.
  Autoplay beyond 3 s would trigger WCAG 1.4.2 [18].
- **S2 Complement, never sole channel** [9]. The error tone is neutral, not a buzzer: a wrong answer
  is information, and about a third of feedback effects turn negative when feedback evaluates the
  person [19]. Haptics are a no-op here: gate on `(pointer: coarse)`, three patterns only, always
  paired [20]; never claim them in desktop copy.

### State feedback

- **F1 Eight states.** Rest, hover, focus-visible, pressed, selected/current, disabled, pending,
  error. Each changes at least two of fill, border, weight, position (≤1 px) or copy.
- **F2** Acknowledge under 100 ms; pending at 150 ms ("Saving…"); progress at 1 s; a way out at 10 s
  [21]. Errors already have a binding standard [22]; the addition is that focus never animates and
  success never outruns the backend [9][23].

## 5. The aliveness kit

The "one authored functional beat" made executable. Play is a well-timed response, not a costume.
Durations are proposed tokens, not research findings.

| Beat | Event | What moves | Duration | Reduced |
|---|---|---|---|---|
| Seal draw | First course visit, once/session | Arc draw; meridian fade | 400 ms | Static |
| Route settle | Mount | Nodes `.96→1` + fade, 40 ms stagger, max 8 | 180 ms, ≤500 | All at once |
| Beacon | Current node | Ring `.55→.9`, two cycles, stop | 2.4 s ×2 | Static |
| Tick commit | Evidence recorded | `scaleX 0→1`, 30 ms stagger, cap 12 | 120 ms | Opacity |
| Press | Any action | `translateY(1px)`, border darkens | 90/120 ms | Colour |
| Verdict | Check submitted | 3 px edge grows; verdict fades; hue shifts | 180/120 ms | Instant |
| Complete | Evidence event | Seal completes; one tick; title crossfade | 600 ms | Static |

The kit is a vocabulary, not a playlist: one beat per interaction and at most two per screen. No
confetti, particles, shake, count-up numbers or looping celebration; milestones only, once,
skippable.

## 6. Slop ledger

| Pattern | Why it fails | Replace with |
|---|---|---|
| Gradient or glow hero | Breaks the token table; mud in forced colors | Flat `lamp-soft` plate, 3 px edge |
| Glass, blur, shadow | Fakes depth without hierarchy | Overlap plus 1 px rule |
| Coloured icon tiles | Decoration competing with state | Plain 16 px `currentColor` |
| Mascot commenting on progress | Infantilises adults; no teaching job | Seal plus route |
| Confetti per answer | Celebrates compliance, not evidence | One tally tick |
| Hover lift or tilt | Fake physics; breaks keyboard parity | 80 ms tint plus 2 px edge |
| Sound on hover or keys | Noise with no information | Three event one-shots |
| Illustration restating the heading | Redundancy increases load [15] | Delete it |
| Badge wall or streak flame | Small competence gain [24] | Visible evidence state |

## 7. React/Desktop contract

- **Tokens.** `--cb-dur-press/state/enter/celebrate` and `--cb-ease-out/inout` in `cbScopeStyle`;
  colours stay the 15.
- **One source.** `useCbMotion()` is the only truth; CSS for states, WAAPI for seal and stagger; no
  library.
- **Press.** `<CbPressable>` wraps `sdk.Button`, adds `data-cb-state` and the 1 px press; migrate 203
  `jsx` call sites by wrapper; native semantics, Enter/Space.
- **Marks.** Four inline SVGs, `currentColor`, `non-scaling-stroke`, `aria-hidden`.
- **Audio.** Lazy `AudioContext`, three synthesised buffers, one gain, mute persisted; no assets.
- **Geometry.** `--cb-node`; spine `calc(var(--cb-node)/2 - 0.5px)`; 44 px rows; `rem` text, `px`
  hairlines; scoped `--cb-*` only, no global selectors, `100vh` or body styles; layout from measured
  width.
- **Tests.** No shadow or gradient; transition props ⊆ transform/opacity/colour; ≤600 ms; iteration 1
  except the loader; 460/900/1049 × light/dark × 200%; reduced snapshot; axe `wcag22aa`.

## 8. Amendments to V2

Four, not a rewrite. §4.1's "motion: none by default" becomes functional motion by default, zero
decorative motion; §4.3's 28 px node becomes the 56/40/28 perspective (44/32/24 on phone); §4.13's
16 px icon cap becomes 16 px UI and 20 px plate; and "a mode does not get an illustration" becomes
"no per-mode illustration; plate marks for identity, position, state." The first wording produced
one transition class in 17.7k lines; the rest let the route and the marks carry identity without
reopening row decoration.

## 9. Review scorecard

1. Name the screen's one object and its share of first-viewport ink.
2. Squint at 5% and in greyscale: one dark mass, one accent, three values.
3. Point at every illustration and icon: what does each encode?
4. Name every animation's event; none exceeds 600 ms.
5. Press, wait, fail, retry: acknowledged, pending, specific, recoverable?
6. Unplug sound, enable reduced motion, zoom to 200%, tab through: still complete?

The bar is not "add delight." It is: **spend the channels you have on information, and only on
information.**

## References

1. Lindgaard et al. (2006), via Nature News — https://www.nature.com/news/2006/060109/full/news060109-13.html
2. Tractinsky, Katz & Ikar (2000), "What is beautiful is usable" — https://doi.org/10.1016/S0953-5438(00)00031-X
3. Linear, "A calmer interface for a product in motion" — https://linear.app/now/behind-the-latest-design-refresh
4. Duolingo, "Introducing the new Duolingo learning path" — https://blog.duolingo.com/new-duolingo-home-screen-design/
5. MacStories, "Things 3: Beauty and Delight in a Task Manager" — https://www.macstories.net/reviews/things-3-beauty-and-delight-in-a-task-manager/
6. Brilliant, "About us" (vendor statement) — https://brilliant.org/about/
7. Notion, "The thinking behind our latest brand campaign" — https://www.notion.com/blog/the-thinking-behind-our-latest-brand-campaign
8. Apple HIG, Motion — https://developer.apple.com/design/human-interface-guidelines/motion
9. Apple HIG, Feedback — https://developer.apple.com/design/human-interface-guidelines/feedback
10. Material 3 motion tokens — https://m3.material.io/styles/motion/easing-and-duration/tokens-specs ; values verified in https://github.com/material-components/material-web/blob/main/tokens/versions/v0_192/_md-sys-motion.scss
11. Material 3 state layers — https://github.com/material-components/material-web/blob/main/tokens/versions/v0_192/_md-sys-state.scss
12. Jonasson & Purho, "Juice It or Lose It" — https://gamedesign.gg/watch/juice-it-or-lose-it/ ; layer detail and counter-talk at https://gdad.wiki/wiki/sources/source-juice-it-or-lose-it
13. NN/g, "Visual Hierarchy" — https://www.nngroup.com/articles/visual-hierarchy-ux-definition/
14. Duolingo, "Shape language" — https://blog.duolingo.com/shape-language-duolingos-art-style/
15. Mayer, "The 12 Principles of Multimedia Learning" — https://www.utwente.nl/en/learning-teaching/themes/educational-design/mayers-ed.-design-principles-1.pdf
16. Apple HIG, SF Symbols — https://developer.apple.com/design/human-interface-guidelines/sf-symbols
17. W3C, WCAG 2.2 SC 2.3.3 — https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
18. W3C, WCAG 2.2 SC 1.4.2 — https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html
19. Kluger & DeNisi (1996) — https://doi.apa.org/doi/10.1037/0033-2909.119.2.254 ; synthesis in https://pmc.ncbi.nlm.nih.gov/articles/PMC6987456/
20. Apple HIG, Playing haptics — https://developer.apple.com/design/human-interface-guidelines/playing-haptics
21. NN/g, "Response Times: The 3 Important Limits" — https://www.nngroup.com/articles/response-times-3-important-limits/
22. NN/g, "Error-Message Guidelines" — https://www.nngroup.com/articles/error-message-guidelines/
23. W3C, WCAG 2.2 SC 2.4.11 — https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
24. Li, Hew & Du (2024), gamification meta-analysis — https://link.springer.com/article/10.1007/s11423-023-10337-7
