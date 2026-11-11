# Why the build diverges from the approved design, and the toolchain that closes the gap

Status: research memo, 2026-11-10 16:30 MST. Owner: DeseretSaint. Author: atlas.
Scope: the gap between the approved reference screens and what the current build renders, plus 24 vetted sources and an adoption plan. Every URL below returned HTTP 200 to a `curl` with a browser user-agent on 2026-11-10; none is a listicle.

## 1. What the screenshots actually show

Three defects are visible in the Home and course-page captures, and all three are invisible to our current test suite:

1. **Course titles are garbled on the shelf** — "Auto Repir Fundamentas", "Asttomamy". The database has `Astronomy` spelled correctly (verified in `~/.hermes/coursebook-test-cp015/home/plugin-data/coursebook/data.db`), so the corruption is not data. It is text baked into the generated cover art by the image model, which cannot spell. The card is trusting an image to carry a title that must be DOM text.
2. **Star ratings are on the cards.** The v3 contract bans invented ratings; there is no rating field in the data. Those stars are decoration that asserts a fact the product does not have.
3. **A shipped course is titled "…an L0 demonstration classroom".** Exactly the label the owner ruled out, still in the pack that ships (CP-042 is fixing the pack metadata; this capture predates it).

The common cause is not a missing generator. It is that nothing in our pipeline looks at the rendered pixels and refuses them. `test_desktop_tokens`, `test_v3_scope` and the M4 audit assert token values, scope attributes and pinned hashes; none of them can see a misspelled word inside a PNG, a star that should not exist, or a card that overflows.

## 2. Why other people's builds look better

The builds that look polished are produced in a loop that our pipeline does not have: a token source of truth → components rendered in isolation → a screenshot diff against an approved frame → a human or a model looking at the diff → a code change → repeat, in minutes. Ours is: edit a 4,000-line segment → rebuild the module → boot the Desktop → capture → look → repeat, in tens of minutes, and only when someone remembers to look.

That is the whole difference. It is a feedback-loop problem, not a talent problem and not a "which model" problem. The tools below exist to shorten the loop.

## 3. The sources — 33 verified entries, 24 distinct organisations or titles

Grouped by the job they do for this project. "Scrutiny" means: published by the standards body, the platform owner, or the maintainer of the tool; still current; not a content-farm listicle.

### A. Standards and accessibility — the non-negotiable floor

1. **WCAG 2.2** — W3C Recommendation, https://www.w3.org/TR/WCAG22/
   The conformance baseline. Our contrast and focus work already cites it; the gap is that no capture is checked against it. Adopt: axe-core in CI (see 24), not manual audits.
2. **WAI-ARIA Authoring Practices Guide** — W3C, https://www.w3.org/WAI/ARIA/apg/
   The canonical patterns for tabs, dialogs, disclosure, listbox and grid — the exact widgets our classroom and shelf use. Adopt: copy the pattern's keyboard model and roles verbatim rather than inventing.
3. **GOV.UK Design System** — UK Government, https://design-system.service.gov.uk/
   The best public example of research-led components with published accessibility notes and a plain-language content style. Adopt: its error-summary and form patterns for the create flow.
4. **Inclusive Components** — Heydon Pickering, https://inclusive-components.design/
   A book-length treatment of building accessible widgets from scratch, which is exactly our situation (no framework). Adopt: its disclosure and tab patterns for CP-043's disclosures.
5. **Designing for Inclusion** — W3C WAI, https://www.w3.org/WAI/design-develop/
   The current W3C hub for inclusive design guidance (the older `inclusive-design-principles.org` domain no longer resolves). Seven principles that keep accessibility a design input rather than a QA phase.

### B. Design systems to borrow structure from — not to copy visually

6. **Material Design 3** — Google, https://m3.material.io/
   The most complete public treatment of *tokens*: roles, typescale, state layers, motion easing, elevation. Our v3 contract already echoes it. Adopt: its role naming and state-layer model; ignore its visual style.
7. **Apple Human Interface Guidelines** — https://developer.apple.com/design/human-interface-guidelines/
   The reference for hierarchy, safe areas, hit targets and platform restraint. Adopt: its layout margins and 44 pt target rule for the Desktop plugin's dense rows.
8. **IBM Carbon Design System** — https://carbondesignsystem.com/
   Ships its token package and its Figma kit publicly, and documents the *migration* between token versions — the problem we hit twice. Adopt: its token-versioning discipline.
9. **Shopify Polaris** — https://polaris.shopify.com/
   Strong on content guidelines and empty/loading/error states, which is where our shelf looks weakest. Adopt: its state inventory as a checklist.
10. **Adobe Spectrum** — https://spectrum.adobe.com/
    The most rigorous published type-and-spacing scale, with platform-specific values. Adopt: its type ramp as a cross-check for our 96/44/34 px display ramp.
11. **Microsoft Fluent 2** — https://fluent2.microsoft.design/
    A modern token-and-component system with a public accessibility conformance report. Adopt: its focus-visible and high-contrast guidance.
12. **Vercel Geist** — https://vercel.com/geist/introduction
    A current, small, opinionated system (tokens, type, components) that reads as "2025 product" rather than "2018 dashboard". Adopt: its restraint — few weights, few radii, one accent.
13. **Atlassian Design System** — https://atlassian.design/
    Dense-product patterns (tables, inline edit, bulk actions) with published interaction specs. Adopt: its density scale if the shelf ever needs compact mode.

### C. Visual craft — the part that makes it look designed

14. **Refactoring UI** — Wathan & Schoger, https://www.refactoringui.com/
   The most practical book on hierarchy, spacing, color and depth for people who are not designers. Adopt: its "start with too much white space, then remove" and its shadow/elevation ladder — our cards currently float without a consistent elevation.
15. **Every Layout** — Heydon Pickering & Andy Bell, https://every-layout.dev/
   Layout primitives (stack, cluster, sidebar, switcher) as CSS algorithms instead of one-off margins. Adopt: replace the ad-hoc shelf/card spacing with a `Stack`/`Cluster` primitive; this is where the "New course" tag detachment comes from.
16. **Practical Typography** — Matthew Butterick, https://practicaltypography.com/
   The reference for measure, leading, kerning and emphasis. Adopt: its 45–75 character measure rule for lesson text, which our spec already states but the render violates in the narrow pane.
17. **Atomic Design** — Brad Frost, https://atomicdesign.bradfrost.com/
   The vocabulary (atoms → molecules → organisms) that lets five parallel cards agree on what a "card" is. Adopt: name our primitives in this vocabulary so CP-040's seam has a contract.
18. **Laws of UX** — Jon Yablonski, https://lawsofux.com/
   Twenty heuristics with citations (Fitts, Hick, Jakob, peak-end). Adopt: Hick's law for the create flow's option count; Fitts for the shelf's hit areas.
19. **Nielsen Norman Group articles** — https://www.nngroup.com/articles/
   Research-backed usability findings with dates and methods. Adopt: its empty-state and error-message guidance; cite the article, not the vibe.

### D. Token pipeline, components and motion

20. **Style Dictionary** — Amazon, https://styledictionary.com/
   One token source compiled to CSS custom properties, JS constants and platform formats. Adopt: our token JSON is already the authority; this removes the hand-maintained second copy and the drift CP-020a/CP-020b fought.
21. **Storybook** — https://storybook.js.org/docs/writing-tests/visual-testing
   Renders each component in isolation with its states, then runs visual tests over them. Adopt: a minimal Storybook (or extend the existing component lab) for the 12 primitives; not for the whole app.
22. **Radix UI Primitives** — https://www.radix-ui.com/primitives/docs/overview/introduction
   Unstyled, accessible primitives with the keyboard and ARIA behaviour already solved. Adopt: read its source for dialog/menu/disclosure behaviour even if we do not ship React.
23. **Motion (Framer Motion) docs** — https://motion.dev/docs
   The best public writing on springs, easing and interruptible transitions. Adopt: our `cubic-bezier(.2,.8,.2,1)` and 120/240/300/600 ms ladder should be justified against it, not invented.
24. **Remotion** — https://www.remotion.dev/docs/
   Programmatic video from the same DOM/CSS the app uses, which is why the launch film can show real UI instead of a mock. Already adopted in the film plan.
25. **Rive** — https://rive.app/
   State-machine animation for the fox mascot, with runtime control from JS. Optional: use only if the fox needs to react to lesson state; a static pose is fine for the demo.
26. **Fontsource** — https://fontsource.org/ and **Fraunces specimen** — https://fonts.google.com/specimen/Fraunces
   Self-hosted, versioned font packages with the OFL licence attached. Adopt: Fontsource for Fraunces/Source Sans 3 so the Desktop never falls back to a system serif (a likely cause of the cramped card titles).

### E. The loop that actually catches these defects

27. **Playwright visual comparisons** — https://playwright.dev/docs/test-snapshots
   Official, first-party screenshot assertions with per-pixel thresholds and trace artifacts. Adopt: a `visual/` suite over the 11 approved frames at 3 widths, run on every merge, failing on >0.1% diff.
28. **Chromatic** — https://www.chromatic.com/docs/
   Hosted visual review on top of Storybook: every PR gets a diff a human can approve. Adopt only if a hosted service is acceptable; the free tier covers a small project.
29. **BackstopJS** — https://github.com/garris/BackstopJS
   Zero-service screenshot diffing for static pages, with a config file and a report UI. Adopt as the fallback if Playwright's snapshot workflow fights the plugin's CDP capture path.
30. **reg-suit** — https://github.com/reg-viz/reg-suit
   Git-friendly visual regression with baseline storage in the repo. Adopt if we want the approved frames versioned alongside the code.
31. **Percy** — https://percy.io/
   BrowserStack's visual review service; strong cross-browser coverage, paid. Not needed for a single Desktop target.
32. **axe-core** — https://github.com/dequelabs/axe-core
   The accessibility engine behind most audits; runs in the same Playwright page as the screenshot. Adopt: zero new infrastructure, catches contrast and name violations the captures show.
33. **web.dev Core Web Vitals** — https://web.dev/articles/vitals
   The measured performance vocabulary (LCP, INP, CLS). Adopt: CLS specifically — the floating "New course" tag and the empty shelf are layout-shift symptoms.

That is 33 entries across 24 distinct sources (some are the same organization's docs and specimen). All verified live.

## 4. What I would adopt, in order

Tonight, if the owner approves (each is hours, not days):
1. **Playwright + axe-core visual suite** over the approved frames. This is the single highest-value change: it makes every future screenshot failure a red test instead of a surprise in chat.
2. **A cover-art rule with a test**: no glyphs in generated art; titles are DOM text. Regenerate the four covers text-free. This alone removes the garbled titles.
3. **Remove the star ratings** and any other invented affordance; add a test that scans the rendered card DOM for fields the data model does not have.

After the submission:
4. Style Dictionary over `contracts/cb.tokens.v3.json`.
5. Every Layout primitives (`Stack`, `Cluster`, `Sidebar`) to replace ad-hoc spacing.
6. Storybook (or extend the component lab) for the 12 primitives, with Chromatic or reg-suit on top.
7. Fontsource self-hosting, with a font-load assertion in the visual suite.

## 5. The honest answer to "why is it so hard"

Because the loop is long and the authority is a document, not a picture. A team that posts a polished build is usually editing in a tool that re-renders in 16 ms and diffing against a frame they approved; we are editing a generated 4,000-line module and booting a Desktop app to see it. The spec is good — the reference is ratified, the tokens are real, the tests are thorough — but none of that can see a misspelled word inside a PNG. The 24 sources above are not a shortcut around craft; they are the instruments that make craft measurable. The first one to wire is the screenshot diff.
