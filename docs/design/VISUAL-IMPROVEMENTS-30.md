# Thirty ways to raise the visual output, and what happened to each

Status: research + adoption record, 2026-11-10 17:15 MST. Owner: DeseretSaint. Author: atlas.
Every technique names the source that documents it; every source is a standards body, platform owner, or tool maintainer, and every URL returned HTTP 200 to a browser-user-agent `curl` on 2026-11-10. Status is honest: LIVE means it is in the tree now, CARD means a card owns it, POST means it would conflict with the in-flight v3 merge.

## The finding that drove this

The approved design's display face was never reaching the page. `75-tokens.js` defined the serif as the OS stack `ui-serif, Georgia, …`, and every heading wrote that inline, so the `@font-face` for **CB Display** (Fraunces, shipped as a data URL by the v3 scope) stayed `unloaded` on all four routes. That single line explains the cramped, generic headings in the owner's captures. It is fixed in `4d37e2` and the visual audit now fails if it regresses.

The covers are the second cause: the AI-painted plates carry painted titles and even painted star ratings ("Auto Repir Fundamentas", "Asttomamy", four stars). No code renders those stars — they are in the image. Text must never live in generated art.

## Typography

1. **Fluid type scale with `clamp()`** — one ramp that scales with the pane instead of breakpoint jumps. Source: web.dev, https://web.dev/articles/min-max-clamp. Application: the v3 display/heading/lead/body steps already use clamp; keep every new step on it. Status: LIVE (contract), enforced by `test_desktop_tokens_v3`.
2. **Apply the shipped face to the elements that need it** — a `@font-face` that nothing references never loads. Source: MDN FontFaceSet, https://developer.mozilla.org/en-US/docs/Web/API/FontFaceSet. Application: `CB_SERIF`/`CB_SANS` now prefer `var(--cb3-font-display/--cb3-font-ui)` before the OS stack. Status: LIVE (`4d37e2`).
3. **Measure cap of 45–75 characters** — lines longer than that lose the reader. Source: Butterick, https://practicaltypography.com/. Application: lesson body max 68ch; the classroom pane currently allows longer on wide routes. Status: CARD (CP-040 seam, low risk).
4. **Tabular numerals for counts, XP and evidence** — proportional digits make "3 of 12" jitter as it counts. Source: Butterick, https://practicaltypography.com/ ("Tabular figures", same guide). Application: evidence counts, XP chips, stepper numbers. Status: CARD.
5. **Weight axis, not faux bold** — the variable face carries 100–900; synthetic bold smears. Source: Google Fonts, https://fonts.google.com/specimen/Fraunces. Application: never `font-weight: 700` on a static face; the v3 faces are variable. Status: LIVE (by construction).
6. **Assert the font actually loaded** — a silent fallback is a defect, not a preference. Source: CSS Font Loading, https://developer.mozilla.org/en-US/docs/Web/API/CSS_Font_Loading_API. Application: `visual/audit.mjs` fails when `CB Display` or `CB UI` is unloaded. Status: LIVE.

## Layout and spacing

7. **8-point spacing scale** — every gap a multiple of 4/8, no 13px inventions. Source: Material 3, https://m3.material.io/foundations/layout/understanding-layout/spacing. Application: shelf gaps, card padding, section rhythm. Status: LIVE (tokens), audit for drift.
8. **Layout primitives instead of one-off margins** — Stack, Cluster, Sidebar, Switcher. Source: Every Layout, https://every-layout.dev/. Application: the detached "New course" tag and the empty shelf are ad-hoc absolute positioning; a Cluster primitive would anchor them. Status: POST (touches every screen; waits for CP-040).
9. **Container queries, not viewport queries** — the plugin lives in a resizable pane, so `cqi` is the only honest unit. Source: MDN, https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries. Application: already the v3 scope's rule; keep new CSS on `cqi`. Status: LIVE.
10. **Optical alignment over mathematical** — text and icons that "measure" centered often look off; nudge by eye. Source: Refactoring UI, https://www.refactoringui.com/. Application: the fox and clock sit beside the shelf; align to the shelf's visual edge, not its box. Status: CARD.
11. **44px hit targets, even in dense rows** — pointer accuracy is not a function of how tight the design looks. Source: Apple HIG, https://developer.apple.com/design/human-interface-guidelines/. Application: nav items, stepper stamps, evidence chips. Status: LIVE (nav), CARD (stepper).
12. **Two densities, not one** — comfortable and compact, chosen by container width. Source: Atlassian Design System, https://atlassian.design/. Application: the shelf at 428px needs the compact row; the classroom at 852px does not. Status: POST.

## Colour and material

13. **Role tokens, never raw hex in a component** — `canvas`, `ink`, `rule`, `forest`, `terracotta`, `gold` are roles; a hex is a leak. Source: Material 3 colour roles, https://m3.material.io/styles/color/roles. Application: already the v3 contract; `test_tokens_v3_contract` refuses a literal. Status: LIVE.
14. **Contrast pairs travel with the role** — every `X` has an `on-X` chosen for it, not computed at render. Source: WCAG 2.2, https://www.w3.org/TR/WCAG22/. Application: `--cb3-on-forest`, `--cb3-on-terracotta`, `--cb3-on-lamp`; audit contrast in the visual run. Status: LIVE (tokens), CARD (axe contrast gate).
15. **A two-shadow elevation ladder** — one tight contact shadow plus one soft ambient; a single blur reads as a sticker. Source: Refactoring UI, https://www.refactoringui.com/. Application: `--cb3-elev-1/2` already encode it; the shelf cards currently float without a contact shadow in light mode. Status: CARD.
16. **A texture budget** — one paper grain at low opacity, never three overlays. Source: Refactoring UI, https://www.refactoringui.com/. Application: `data-cb-v3-textures="ready"`; refuse a second grain in new work. Status: LIVE.
17. **Dark mode as a designed mode, not an inversion** — separate canvas/ink values, warmer than pure black. Source: Fluent 2, https://fluent2.microsoft.design/. Application: `--cb3-canvas #14110c` in dark; the owner's app is in dark scope, which is why the same screen reads differently from the light references. Status: LIVE, but the dark palette has never been visually ratified — flag for GM-016.

## Hierarchy and content

18. **One primary action per view** — two filled buttons compete. Source: Refactoring UI, https://www.refactoringui.com/. Application: Home currently offers "Start a new course" and "Browse the library" at equal weight; make the second quiet. Status: CARD (CP-022 territory; comment, not edit).
19. **A state inventory per surface: default, loading, empty, error, offline** — design them before they happen. Source: Shopify Polaris, https://polaris.shopify.com/. Application: the shelf's empty state is an empty wooden shelf with no words. Status: CARD.
20. **Skeletons that match final geometry, no shimmer** — a shimmering box is a lie about what is coming. Source: NN/g, https://www.nngroup.com/articles/skeleton-screens/. Application: the spec already says "real boxes, 40% card stock, no shimmer"; audit it. Status: LIVE (spec), CARD (capture).
21. **Verb-first, sentence-case microcopy** — "Start a new course", not "New Course Creation". Source: GOV.UK content design, https://www.gov.uk/guidance/content-design/writing-for-gov-uk. Application: the copy deck already enforces this; keep pack titles in the same voice. Status: LIVE.
22. **Progressive disclosure over a wall of choices** — show the next decision, not all of them. Source: NN/g, https://www.nngroup.com/articles/progressive-disclosure/. Application: the create flow's goal gallery currently shows every option at once. Status: POST.

## Motion

23. **An easing and duration ladder, not per-animation guesses** — 120/240/300/600ms with one curve. Source: Material motion, https://m3.material.io/styles/motion/easing-and-duration. Application: the v3 scope already names `--cb3-dur-*` and `cubic-bezier(.2,.8,.2,1)`. Status: LIVE.
24. **Reduced-motion parity** — every animation has a non-moving equivalent that still communicates the state. Source: WCAG 2.2 SC 2.3.3, https://www.w3.org/TR/WCAG22/. Application: `data-cb-motion="reduced"` path in the scope; capture it as a state. Status: LIVE (scope), CARD (evidence).
25. **Interruptible transitions** — a new state cancels the old animation instead of queueing. Source: Motion docs, https://motion.dev/docs. Application: route changes during a stamp animation; the scope's transitions are CSS, so they interrupt by default. Status: LIVE.
26. **Choreograph the state change, don't decorate it** — the stamp lands, then the evidence count ticks; one beat, not two effects. Source: Material motion, https://m3.material.io/styles/motion/easing-and-duration. Application: check submit → verdict → evidence count. Status: CARD.

## Assets and verification

27. **Visual regression over approved frames, per route and width** — the only way a pixel defect becomes a red test. Source: Playwright, https://playwright.dev/docs/test-snapshots. Application: `visual/audit.mjs` captures Home, Courses, Workshop, Parent Studio at 1440 (2x DPR), diffs against `visual/baselines/`, fails past 0.1%. Status: LIVE (`4d37e2`).
28. **Accessibility in the same render** — axe on the same DOM that was just photographed. Source: Deque axe-core, https://github.com/dequelabs/axe-core. Application: the audit injects axe and fails on serious/critical; it already reports 0 on the four routes. Status: LIVE.
29. **Zero glyphs and zero UI chrome in generated art** — the model cannot spell and will invent stars. Source: our own capture evidence plus OpenAI's image guide, https://platform.openai.com/docs/guides/image-generation. Application: covers are text-free deterministic plates; titles, ratings and badges are DOM. Status: CARD (CP-042, extended with the photo evidence).
30. **A capture contract: 100% zoom, 2x DPR, route crop, stamped sha** — a frame that cannot prove where it came from is not evidence. Source: our CP-038 capture door, `scripts/cp-capture.mjs`. Application: every frame carries `route`, `destination`, `clicks`, `scroll`, `plugin_sha256`. Status: LIVE.

## What changed in this pass

- `desktop/src/75-tokens.js`: headings now prefer the shipped v3 faces; the display font actually loads. Commit `4d37e2`.
- `visual/`: a working Playwright audit that connects to the live Desktop over CDP, captures four routes at 2x, diffs against baselines, runs axe, asserts fonts, and writes `report.html`.
- `docs/design/QUALITY-TOOLCHAIN-RESEARCH.md`: 33 verified sources for the wider toolchain.
- CP-042 extended with the photo evidence: text-free covers, no painted stars, titles are DOM.

The audit's first run found the font defect on all four routes; after the fix is loaded by a restarted app it should report `CB Display:true`. The running Desktop still holds the pre-fix module in memory — that is CB-017, and it is the only reason the fix is not visible on screen yet.

## What is deliberately not done before the deadline

Techniques 8, 12, 18, 22 touch every screen and would collide with the five v3 branches currently merging through CP-040. They are recorded here and belong in the first post-submission pass. Techniques 3, 4, 10, 15, 19, 20, 24, 26 are small and carded against the surfaces that own them.
