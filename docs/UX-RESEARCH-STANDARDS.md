# UI/UX research standards for Coursebook

Status: binding design and review reference. Source: the user's Obsidian vault and OpenViking
knowledge base, reviewed 2026-11-07. This file extracts the load-bearing rules; it does not
replace the sources.

## Sources

- `~/Obsidian/dm-vault/knowledge/UI-UX-ONE-SHOT-PLAYBOOK.md` — 4,105 lines; the agent checklist is
  `## One-shot build checklist` (L2386), anti-slop is L2948, the accessibility floor is L2970,
  the existing-build audit is around L2938, and rejected patterns are L3163+.
- `~/Obsidian/personal-vault/Design & Render One-Shot Quality — Baseline, Evidence, Gates (2026-09-12).md`
  — one-shot pipeline, human-comprehension numbers and verification gates.
- `~/Obsidian/dm-vault/ops/reviews/CRAFT-LENS.md` — the four design laws and the hard-law tier.
- `~/Obsidian/dm-vault/knowledge/UI-UX-BUILD-AND-AUDIT-DIGEST.md` — the executable digest.
- `~/Obsidian/work-vault/NewCo Portal — UI-UX and Coding References.md` — reading order and hard rules.
- OpenViking: `viking://resources/dm-vault/knowledge/DESIGN-SYSTEMS-UI.md`,
  `DESIGN-RENDER-QUALITY-GATES.md`, `DESIGN-REFERENCE-PACK.md`,
  `DESIGN-VERIFICATION-GATES-DIGEST.md`.
- Product research already in this repo: `docs/FIELD-DESK-RESEARCH.md`, `docs/INK-FIELD-NOTES.md`,
  `docs/UX-AUDIT-ROUND3.md` and `docs/COURSEBOOK-VISUAL-IDENTITY-V2.md`. The visual-identity spec is
  subordinate to this file where they conflict.

## 1. The four design laws (CRAFT-LENS, verbatim)

1. "Zen first — let the work breathe; every element earns its place."
2. The message/meaning is SHOWN, never explained — no copy that names its own theme.
3. Motion must read as the intended physical act, never as a generic CSS wipe.
4. Exactly one focal hierarchy per frame — "nothing dominates the frame" is a defect,
   "balanced symmetry" is a defect.

These outrank taste. A visual change that adds a second dominant element, an explanatory
slogan, or a generic animation is a defect even if it looks polished.

## 2. First-run and onboarding

- Default to **no dedicated onboarding**. NN/g: avoid onboarding when the UI can teach
  itself; test with no onboarding first. Tutorials did not improve task success in the
  controlled sample and could make it worse. Only three cases justify onboarding: required
  identity/setup, highly tailored one-time configuration, or a genuinely novel interaction
  the UI cannot convey.
- If guidance is needed, use **pull**, not push: reveal in context, tied to the object,
  minimal text, non-modal, dismissible. No launch modal, no deck-of-cards tour, no
  what's-new modal.
- Activation-driven onboarding is the defensible exception for complex products: one
  checklist or one inline start plate that leads to the first real value; 3–4 screens
  maximum; never ask for visual customization before first use.
- Apple HIG: no splash, dive in, always skippable, never show again to returning users.
- Coursebook decision: the first-run field desk is a **single inline start plate with one
  action**, not a tour. The three-step path is explanatory structure, not three onboarding
  screens. A cold user must know what to press within five seconds.

## 3. Hierarchy, navigation and copy

- One primary action per screen. A second primary button is a hierarchy defect.
- Visible navigation by default; 4–5 primary destinations. Active state uses
  `aria-current="page"` **and** a visible non-colour cue. Hidden menus only on small
  screens and always labelled ("Menu"/"Browse").
- Breadcrumbs for deep hierarchy: hierarchy, not history; the current page is not a link.
  Back is top-left with a standard chevron.
- Headings are literal and carry their own weight. **Do not add a decorative kicker or
  eyebrow above a heading.** If a label is semantically required, use a `<p>`/`<span>`,
  never a heading element. (The playbook's anti-slop table is explicit.)
- No same-size card-row grid as the page structure. Use one featured element, prose and
  asymmetry; cards are for heterogeneous browsing, not for making every collection look
  the same. Never nest cards.
- No hero-metric template (big number + label + stats) as the main statement. Lead with the
  outcome in words; numbers only when they change a decision.
- Section numbers `01/02/03` only when the sequence itself carries information. Do not
  number decorative sections.
- Copy:
  - 6th–8th-grade reading level; experts are not exempt.
  - Concise + scannable + objective is the measured combination; about 28% of words are
    read on an average page and 57% of viewing time is above the fold.
  - Sentence case for UI labels; reserve all-caps for short chips/legal micro-labels.
  - Ban "Learn more", "click here", directional references, invented branded terms, and
    clever headings. Spell out acronyms except universal ones (PDF/URL/FAQ).
  - Error copy = what happened + why + how to fix, in the user's words; no blame, no
    "Oops", raw codes in a secondary line. Empty states say WHY + next action + icon.
  - Placeholders are format examples only; a visible label is always present.

## 4. Type, spacing, color and shape

- One font family; 4–6 sizes on a body-first ramp (steps roughly 1.14–1.25). Body line-height
  ~1.5; display ~1.12. Prose measure 50–75ch, hard cap 80ch.
- No gradients, glass/blur, gradient text, thick decorative left borders (>1px), hard offset
  shadows, or emoji as icons. Emphasis comes from weight, size, space and one accent.
- Spacing ladder: 4px inside components, 8pt between components/sections; 8px in-list,
  24px between items, 64px between sections. Pin one value per layout role; no magic numbers.
- Grayscale-first: 2–3 colors maximum before semantic status colors. Color is never the only
  signal. WCAG 2.2 AA: text ≥4.5:1 (large ≥3:1), non-text UI/graphics ≥3:1. Dark mode is its
  own palette, not inverted light mode.
- One radius family; radii from tokens; elevation agrees with z-layer; static content is flat,
  resting cards subtle, overlays above.
- Focus: `:focus-visible`, outline 2px, offset 2–4px, ≥3:1 against the real component
  background; never `outline:none` or box-shadow-only. Focus must remain visible.
- Touch targets: 24×24px WCAG floor; 44×44px for field use. Adjacent targets need spacing.

## 5. Forms and the New Course flow

- Wizard only for novice/infrequent, step-dependent flows. Course creation qualifies; repeated
  expert editing does not.
- One thing per step; enforce linear order; Back never loses data; persist and resume with a
  summary. Progress indicator is conditional: use a step list with current highlight for a
  complex/branching flow; a short linear flow can omit it. Never fake a total step count.
- Label above the input; required/optional marker; placeholder only as an example. Validate on
  blur, then re-validate on input once errored. Error below the input, with border + text, and
  `aria-describedby` carrying help first, then error. Submit errors appear in a summary at the
  top of a long form.
- Advanced/optional settings go behind a disclosure, revealed inline, not hidden then surprising.
- Keep all real consequences and approval boundaries. Do not simplify away a limitation.

## 6. Empty, loading and error states

- Empty states route by cause: first use → explain + one primary CTA (+ sample if real);
  cleared → acknowledge + next; filtered → name the filter + "Clear filters" (not a create
  CTA); search-no-results → echo the query + suggestions; expired auth → "Session expired"
  + sign in.
- Every empty state: WHY + next action + icon; cold user must know what to click in five
  seconds.
- Never show a "No records" state that will fill after a delay; that is a loading state.
  Skeletons match final layout, delay ~200ms, escalate at 5s.
- Errors name what failed, what the user can do, and how to recover; preserve the user's
  work; two actions where possible. No "Something went wrong."

## 7. Motion and interaction

- Feedback 100–200ms; enter/exit 200–300ms. Animate transform/opacity only; never width,
  height, top, left or margin. Easing is purpose-tied.
- Two distinct animation effects per screen maximum; functional motion only. No animation
  above the fold on a dashboard/tool or on frequent low-novelty updates.
- Respect `prefers-reduced-motion`: strip translate/scale/rotate, keep opacity/colour
  crossfades. Focus indicators are never animated away.
- Button press feedback: scale ≈0.95 or translateY(2px), 100–150ms, paired with a visible
  state; never the only feedback channel.
- Do not use a custom gesture as the only path to an action; every gesture has a visible
  single-pointer alternative.

## 8. Verification gates

- WCAG 2.2 AA, not just 2.5.8. Name all six new 2.2 criteria when claiming 2.2 AA:
  2.4.11 Focus Not Obscured, 2.5.7 Dragging, 2.5.8 Target Size, 3.2.6 Consistent Help,
  3.3.7 Redundant Entry, 3.3.8 Accessible Authentication.
- axe with the `wcag22aa` tag plus keyboard/focus/reading-order and a manual screen-reader
  spot check. Automation catches only ~30–40% of WCAG criteria; zero axe violations is not
  certification.
- Test 460/900/1049px; light and dark; 200% text; reduced motion; forced colors where the
  host supports it. No horizontal overflow, clipped text, or unnamed controls.
- Human checks: visual appeal is judged in ~50ms, credibility forms by ~3.4s, and the value
  proposition must land within 10s. Design look is the top stated trust cue.

## 9. Coursebook-specific directives

1. **First screen:** one primary action that starts a real course; two secondary entry points
   (existing course, syllabus) with clear labels. No onboarding modal, no sample-course lie.
2. **Persistent wayfinding:** Courses / Library / Parent Studio visible; active state not
   colour-only; All courses and back links consistent.
3. **New Course:** three-step novice wizard; step 1 cards with selected state in words; step 2
   goal + usage; step 3 review + explicit next action. No internal enums or jargon.
4. **Lesson start:** one primary action. If no chat, one sentence and "Start a fresh run"; no
   disabled resume beside a live start. After start, say the chat is open and the first message
   binds the run — in plain words ("binds" is acceptable only if explained, otherwise say
   "connects").
5. **Lesson views:** Textbook is editorial reading; Guided is one step at a time; Field Quest is
   a path of mission cards. All three use the same document, check and evidence; no invented
   mastery, XP, streaks, percentages or locks.
6. **Empty / error:** every state has a next action; a failed read never renders as an empty
   course.
7. **Colour:** course covers and mode identity may use semantic tones; do not turn every status
   into a different colour. Thick border-left bars, gradients and glass are not part of the
   language.
8. **No decorative kicker row** above headings; the brand seal and plate head carry identity.

## 10. Review checklist

A screen is not finished when it looks plausible. It is finished when:

- [ ] one primary action is unmistakable;
- [ ] the user knows where they are and how to go back without a tooltip;
- [ ] all copy is plain, literal, short, and free of internal enums;
- [ ] empty/loading/error states each have one next action;
- [ ] colour is redundant with text/shape and meets contrast;
- [ ] keyboard focus, 200% text, reduced motion and 460px work;
- [ ] no dead, duplicate or disabled-without-reason control;
- [ ] no decorative kicker, gradient, thick border-left, nested card or card-grid scaffold;
- [ ] every claim about progress/evidence is backed by a recorded fact, not a visual metric.

If a rule conflicts with a visual idea, the rule wins unless the owner explicitly overrides it.
