# Toolchain 50, and an adversarial answer on Three.js

Status: research memo and board wiring, 2026-11-10 18:05 MST. Owner: DeseretSaint. Author: atlas.
Method: every candidate was fetched with a browser-user-agent `curl` on 2026-11-10; the 50 below returned HTTP 200. "Fit" is a judgement about Coursebook specifically — a vanilla-JS Hermes Desktop plugin with no framework, a 4 MB module budget, a paper-textured 2D visual language, and a deadline of 2026-11-11 15:00 MST. NOW means it can land this cycle without colliding with the v3 merge; POST means it is worth doing after submission; REJECT means it does not fit and should not be adopted.

## 1. Three.js: the claim, attacked

**The claim.** "Three.js is popular among agents, so it might be useful to us."

**What it actually is.** A WebGL renderer for 3D scenes: https://threejs.org/. It draws into a `<canvas>`; nothing inside that canvas is DOM.

**What it costs us.**
- **Text fidelity.** Our entire product is text — course titles, lesson prose, checks, evidence counts. Canvas text is painted pixels: it cannot be selected, searched, translated, reflowed, or read by a screen reader without a parallel DOM. MDN states the problem directly and prescribes a fallback DOM for canvas content: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/canvas. The approved design is a book; Three.js would make it a poster.
- **The capture contract.** Every frame we ship is a DOM screenshot with a stamped route and plugin sha. A WebGL canvas adds GPU-dependent output — the same commit renders differently on a different driver — which breaks reproducibility, the one thing the evidence rules depend on.
- **Weight and runtime.** Three.js is hundreds of kilobytes before any scene, and it needs a live WebGL context. The plugin is a single generated module with a strict budget and a no-dependency posture; adding a 3D engine for decoration is the largest imaginable dependency for the smallest imaginable gain. WebGL support itself is not the issue (https://caniuse.com/webgl); the issue is that we have no 3D content.
- **Accessibility and motion.** Canvas content needs an equivalent DOM tree, keyboard handling and reduced-motion handling, all of which we get free in DOM/CSS today.

**Where it would be legitimate.** A single decorative hero (a 3D book opening), a particle transition, or a 3D mascot. None of those is in the approved visual language: the approved Home is paper, wood, ink and a flat fox illustration. Adding a 3D scene would be a new design, not a better implementation of the approved one — exactly the drift the owner has been rejecting.

**Verdict: REJECT for the product UI.** If the fox needs to move, use Rive (state machine, vector, tiny runtime) or CSS; if a hero needs depth, use a static painted plate with parallax. Three.js is the right tool for a different product.

## 2. The 50

### Design sources and visual craft

1. **Penpot** — https://penpot.app/ — open-source design and prototyping, self-hostable; a design source we could version beside the code. POST.
2. **Figma** — https://www.figma.com/ — the industry design source; free tier is enough for one designer. POST.
3. **Spline** — https://spline.design/ — browser 3D/illustration with export to web; the honest alternative to Three.js if we ever need one 3D object. POST.
4. **Rive** — https://rive.app/ — state-machine vector animation with a small runtime; the right way to animate the fox against lesson state. POST.
5. **LottieFiles** — https://lottiefiles.com/ — JSON vector animation, tiny and accessible-friendly if used as decoration. POST.
6. **Haikei** — https://haikei.app/ — generated SVG textures, blobs and grain; consistent paper grain without a bitmap. POST.
7. **Lucide** — https://lucide.dev/ — consistent 24px stroke icon set, MIT. POST (we use Codicon today; one set only).
8. **Phosphor Icons** — https://phosphoricons.com/ — six weights of one icon family; useful if we need weight-matched icons. POST.
9. **Fontshare** — https://www.fontshare.com/ — free commercial-use typefaces with licences stated per family. POST.
10. **v-fonts** — https://v-fonts.com/ — variable-font specimen index; source for a display face with a real weight axis. POST.
11. **Modern Font Stacks** — https://modernfontstacks.com/ — OS-resident stacks ranked by quality, for the fallback path. NOW (fallbacks already exist; use this to justify them).
12. **Utopia** — https://utopia.fyi/ — fluid type and space scales generated from two viewports, exported as CSS custom properties. POST.
13. **Typescale** — https://typescale.com/ — modular scale calculator with line-height pairing. POST.
14. **Leonardo** — https://leonardocolor.io/ — contrast-based color scale generation from a source color. POST.
15. **Stark** — https://www.getstark.co/ — contrast and accessibility checks inside design tools. POST.
16. **Tokens Studio** — https://tokens.studio/ — design-token management in Figma, exports JSON. POST.
17. **Style Dictionary** — https://styledictionary.com/ — one token source compiled to CSS/JS/platforms; ends the two-copy drift. POST (the v3 contract is already the source; this is the build step).
18. **Open Props** — https://open-props.style/ — a well-designed set of CSS custom properties; reference for naming and scales, not a dependency. POST.
19. **Modern CSS Reset** — https://piccalil.li/blog/a-modern-css-reset/ — Andy Bell's reset; removes default-margin and box-model surprises in one small block. POST.
20. **Every Layout** — https://every-layout.dev/ — Stack/Cluster/Sidebar/Switcher as CSS algorithms; replaces ad-hoc margins. POST.

### Build and asset pipeline

21. **Vite** — https://vitejs.dev/ — fast dev server and build; relevant only if we split the plugin into modules with a real build. POST.
22. **esbuild** — https://esbuild.github.io/ — sub-second bundling/minification; could replace the segment concatenator if module size becomes a problem. POST.
23. **Lightning CSS** — https://lightningcss.dev/ — Rust CSS parser/minifier with vendor handling; safe for the v3 stylesheet. POST.
24. **PostCSS** — https://postcss.org/ — plugin pipeline for CSS transforms; only if we adopt a token compiler. POST.
25. **SVGO** — https://svgo.dev/ — strips metadata and redundant paths from SVG; every icon and plate should pass through it. NOW.
26. **Sharp** — https://sharp.pixelplumbing.com/ — libvips-backed image resize/convert; the right way to produce 2x/3x covers and thumbnails deterministically. NOW.
27. **Squoosh** — https://squoosh.app/ — visual image compression with per-codec settings; useful for one-off hero assets. POST.
28. **pngquant** — https://pngquant.org/ — lossy PNG quantization with alpha; cuts plate weight without visible banding at our grain levels. NOW.
29. **libvips** — https://www.libvips.org/ — the fast image engine under Sharp; batch pipelines without loading full images. NOW (via Sharp).
30. **Tesseract** — https://tesseract-ocr.github.io/ — OCR; the objective test that a cover carries no glyphs. NOW (the cover rule needs a machine check).
31. **FontTools** — https://fonttools.readthedocs.io/ — subsetting and inspection; trim the kanji font to the pack's glyphs instead of shipping a full CJK face. POST.
32. **Subfont** — https://github.com/Munter/subfont — automatic webfont subsetting per page; same goal, different tool. POST.
33. **ImageMagick** — https://imagemagick.org/ — the universal image CLI; contact sheets, montages, format conversion for review packets. NOW.

### Component workshops and primitives

34. **Storybook** — https://storybook.js.org/ — isolated component stories with visual test hooks. POST (heavy; the component lab already exists).
35. **Ladle** — https://ladle.dev/ — a Vite-native, much lighter Storybook alternative; the right fit if we want a lab without the weight. POST.
36. **Histoire** — https://histoire.dev/ — Vite-native component explorer with a focus on props/state. POST.
37. **Radix Primitives** — https://www.radix-ui.com/primitives — unstyled accessible primitives; read its keyboard/ARIA model even though we are not React. POST (patterns now, code later).
38. **Headless UI** — https://headlessui.com/ — accessible unstyled components for React/Vue; same value as Radix. POST.
39. **Ark UI** — https://ark-ui.com/ — state-machine-driven headless components across frameworks. POST.
40. **Zag.js** — https://zagjs.com/ — framework-agnostic component state machines; the most portable way to get correct keyboard behaviour in vanilla JS. POST (this is the one I would actually use).
41. **Floating UI** — https://floating-ui.com/ — collision-aware positioning for tooltips, popovers and the "New course" tag. POST.
42. **TanStack Virtual** — https://tanstack.com/virtual/latest — virtualised lists; only if the shelf or lesson list grows past a few hundred rows. POST.
43. **cmdk** — https://cmdk.paco.me/ — command-palette primitive; a good pattern for the create flow's course picker. POST.

### Testing, performance and operations

44. **Vitest browser mode** — https://vitest.dev/guide/browser/ — run unit tests in a real browser with the DOM; useful if the segment code grows testable units. POST.
45. **Testing Library** — https://testing-library.com/ — query by role and text, which is exactly how our DOM should be asserted. POST.
46. **MSW** — https://mswjs.io/ — mock the RPC layer at the network boundary; lets visual tests run without a live backend. POST.
47. **Lost Pixel** — https://lost-pixel.com/ — open-source visual regression with a hosted review UI; the fallback if our Playwright diff outgrows itself. POST.
48. **Argos** — https://argos-ci.com/ — visual review on every PR with a free tier; same role, hosted. POST.
49. **Pa11y** — https://pa11y.org/ — a second accessibility engine beside axe; catches different rules. NOW (cheap, CLI, no service).
50. **Lighthouse CI** — https://github.com/GoogleChrome/lighthouse-ci — budgets and assertions in CI; relevant to the docs site and any web surface, not the Desktop plugin. POST.

**Reserve, verified but not counted in the 50:** Happo (https://happo.io/), Applitools (https://applitools.com/), Sitespeed.io (https://www.sitespeed.io/), BrowserStack (https://www.browserstack.com/), Polypane (https://polypane.app/), Responsively (https://responsively.app/), Sentry (https://sentry.io/), OpenReplay (https://www.openreplay.com/), Checkly (https://www.checklyhq.com/), k6 (https://k6.io/), Renovate (https://docs.renovatebot.com/), Knip (https://knip.dev/), size-limit (https://github.com/ai/size-limit), Biome (https://biomejs.dev/), Snyk (https://snyk.io/), REUSE (https://reuse.software/).

## 3. What we adopt this cycle

Only four are both safe and useful before the deadline:

1. **SVGO + Sharp + pngquant** — a real asset pipeline for covers, icons and plates: deterministic sizes, stripped metadata, no 4 MB PNGs.
2. **Tesseract** — the machine check that a cover carries no text. This is the test CP-042 needs so "no glyphs in art" is enforced, not hoped for.
3. **ImageMagick** — contact sheets for review packets, so a reviewer sees all states in one image.
4. **Pa11y** — a second accessibility engine beside axe in the visual audit.

Everything else is POST, and the ones that touch layout or components (20, 37-43) would collide with the v3 merge, so they wait for CP-040 to land.

## 4. How the board uses them

- `visual/audit.mjs` already runs Playwright + pixelmatch + axe; it is the gate every screen card must pass.
- CP-042 owns the cover rule and now also the Tesseract check (OCR must find no text), with SVGO/Sharp/pngquant for the plates.
- CP-040 runs the visual audit on the merged tree before it pins the M4 evidence; a frame that fails fonts, axe or the pixel diff cannot be pinned.
- The post-submission cards (tokens, layout primitives, component lab) name Style Dictionary, Utopia, Every Layout and Zag.js as their tools, so the next cycle starts from this list rather than reinventing it.

The one thing this list cannot buy is the thing that mattered most today: somebody looking at the rendered frame. The tools shorten the loop; they do not replace the looking.
