// CB-V3-BEGIN — CP-020a: the v3 route ground (tokens, scoped stylesheet, materials, readiness).
/**
 * ── Field Atlas v3: the route ground ──────────────────────────────────────────────────────────
 *
 * CP-020a. The contract `contracts/cb.tokens.v3.json` is the only authority for a v3 value; this
 * segment translates it into scoped `--cb3-*` custom properties on `[data-cb-v3]` — the same node
 * as `[data-cb-route]`, so `cqi` resolves against the route and never the Desktop window.
 *
 * Nothing on a product screen changes here yet: the route paints parchment, card stock and the two
 * aria-hidden material layers, and every existing surface keeps its own v2 paint. Screens land in
 * CP-021+ and may only use the roles their surface row permits.
 *
 * `CB_TOKENS_V3_JSON` is generated from the contract (six build-critical sections: modes,
 * elevation, radii, type, motion, materials — canonical bytes); `tests/test_desktop_tokens_v3.py`
 * refuses a hand edit. `CB_V3_CSS` carries no colour —
 * every value arrives through a custom property, so the two token literals stay the only hex in
 * the module. Fonts are composed from `CB_ASSETS.fonts` data URLs at render time, with
 * `font-display: swap`; a face that fails to decode leaves the system fallback in place.
 */
const CB_TOKENS_V3_JSON =
  '{"modes":{"light":{"canvas":"#f5e3c8","canvas-edge":"#e6cfae","card-stock":"#f4ecd9","ink":"#1a1713","ink-soft":"#5c5347","rule":"#cdb894","forest":"#0d281b","on-forest":"#f5e3c8","terracotta":"#b4532f","on-terracotta":"#fffaf1","terracotta-quiet":"#f0d5c1","gold":"#a1741f","sage":"#7f9a72","wood":"#a5763f","wood-edge":"#7d5529","plum":"#6a3e74","alert":"#9c2e1c","focus":"#2a813f"},"dark":{"canvas":"#14110c","canvas-edge":"#2a2419","card-stock":"#1e1a13","ink":"#f3e6cf","ink-soft":"#bfae93","rule":"#3c352a","forest":"#0e2a1c","on-forest":"#f3e6cf","terracotta":"#e0794f","on-terracotta":"#1a1713","terracotta-quiet":"#3a241a","gold":"#d8a94e","sage":"#8fae83","wood":"#8f613c","wood-edge":"#c08856","plum":"#cda0d8","alert":"#f0a08c","focus":"#f2c56a"}},"elevation":{"light":{"elev-1":"0 1px 1px rgba(58, 35, 24, 0.10), 0 6px 14px -8px rgba(58, 35, 24, 0.28)","elev-2":"0 2px 2px rgba(58, 35, 24, 0.12), 0 14px 28px -12px rgba(58, 35, 24, 0.34)","inset-1":"inset 0 1px 2px rgba(58, 35, 24, 0.18), inset 0 -1px 0 rgba(255, 250, 240, 0.50)"},"dark":{"elev-1":"0 1px 1px rgba(0, 0, 0, 0.45), 0 6px 14px -8px rgba(0, 0, 0, 0.65)","elev-2":"0 2px 3px rgba(0, 0, 0, 0.50), 0 16px 30px -12px rgba(0, 0, 0, 0.70)","inset-1":"inset 0 1px 2px rgba(0, 0, 0, 0.55), inset 0 -1px 0 rgba(255, 241, 220, 0.08)"},"rules":["Elevation is contact shadow for a physical object on paper, never a glow.","A card uses elev-1 or a 1px rule border, not both.","inset-1 is for pressed and recessed fields only (a tray, an input, a selected slot).","No elevation on text, rules, the rail or the canvas ground."]},"radii":{"square":"0px","soft":"6px","round":"12px","pill":"999px"},"type":{"families":{"display":"\\"CB Display\\", \\"Fraunces\\", ui-serif, Georgia, \\"Noto Serif JP\\", \\"Hiragino Mincho ProN\\", \\"Yu Mincho\\", serif","ui":"\\"CB UI\\", \\"Source Sans 3\\", system-ui, \\"Hiragino Kaku Gothic ProN\\", \\"Yu Gothic\\", \\"Noto Sans JP\\", sans-serif","cjk":"\\"Noto Serif JP\\", \\"Hiragino Mincho ProN\\", \\"Yu Mincho\\", \\"Noto Serif CJK JP\\", serif"},"subsets":{"CB Display":"Fraunces, OFL, subset to Latin plus punctuation","CB UI":"Source Sans 3, OFL, subset to Latin plus punctuation","cjk":"system CJK stack; a shipped Noto Serif JP subset is the first entry when CP-004 embeds it"},"loading":"font-display: swap; a face that fails to load leaves the system fallback in place and never blanks the route","container":{"name":"cb","type":"inline-size","measured_against":"the route container, never the window","note":"Every cqi in this table resolves against the [data-cb-v3] route container."},"scale":{"caption":"0.75rem","meta":"0.875rem","body":"1rem","lead":"1.25rem","heading":"clamp(1.5rem, 1.2rem + 1cqi, 2.25rem)","display":"clamp(2.5rem, 1.5rem + 3cqi, 4rem)"},"line_height":{"caption":1.35,"meta":1.4,"body":1.5,"lead":1.35,"heading":1.15,"display":1.02},"weights":{"display":600,"heading":600,"body":400,"strong":600},"measure":"50-75ch for prose; display headings at most 20ch, section headings at most 34ch","rules":["Six steps and no seventh.","Body is 1rem so a 200 percent root scales every step.","Display is measured against the route container via cqi, so a narrow route shrinks the headline instead of overflowing it.","Japanese lesson lines use the cjk family for kana and kanji and the ui family for romaji; furigana is smaller than the body step by design, never a seventh authored size."]},"motion":{"press":120,"lift":150,"route":240,"verdict":300,"complete":600,"ceiling":600,"loops":false,"easing":"cubic-bezier(0.2, 0.8, 0.2, 1)","properties":["transform","opacity"],"reduced_motion":"transitions are removed, not shortened; the state change still happens on the next frame","rules":["No duration in this table may exceed ceiling (600 ms).","No looping, pulsing, shimmering or infinite animation anywhere.","Motion is feedback for a real event: press, lift, route change, check verdict, completion.","transform and opacity only; never animate layout, colour or filter."]},"materials":{"grain":{"light":{"tile":"cb-grain-paper","file":"material/grain-paper.webp","opacity":0.1},"dark":{"tile":"cb-grain-night","file":"material/grain-night.webp","opacity":0.14}},"vignette":{"light":{"tile":"cb-vignette-parchment","file":"material/vignette-parchment.webp","opacity":0.55},"dark":{"tile":"cb-vignette-night","file":"material/vignette-night.webp","opacity":0.65}},"wood":{"light":{"tile":"cb-wood-plank","file":"material/wood-plank.webp","opacity":1.0},"dark":{"tile":"cb-wood-plank-night","file":"material/wood-plank-night.webp","opacity":1.0}},"opacity_ceiling":0.18,"rules":["Grain and vignette are aria-hidden and pointer-events none; they sit above the canvas and below all content.","Grain opacity may never exceed opacity_ceiling over a text run.","Wood is a tile on the shelf plank and the evidence tray only; it never sits behind text.","Missing texture falls back to flat canvas; never a blank route, never a broken-image mark.","Grain and wood are seamless 3x3 tiles (CP-011 proof) and at most 60 KB each."]}}'

const CB_TOKENS_V3 = JSON.parse(CB_TOKENS_V3_JSON)
const CB3_V3_ROLES = Object.freeze(["canvas", "canvas-edge", "card-stock", "ink", "ink-soft", "rule", "forest", "on-forest", "terracotta", "on-terracotta", "terracotta-quiet", "gold", "sage", "wood", "wood-edge", "plum", "alert", "focus"])
const CB3_V3_TYPE_STEPS = Object.freeze(['caption', 'meta', 'body', 'lead', 'heading', 'display'])
const CB3_V3_FAMILIES = Object.freeze(['CB Display', 'CB UI'])

const CB_V3_CSS = `/* Field Atlas v3 — the route ground.
 * One scoped material system: tokens arrive as --cb3-* custom properties written by CbV3Scope,
 * paint lives here, and every selector is scoped to [data-cb-v3] so nothing leaks into host chrome.
 * No raw colour, no viewport unit, no loop: the contract (contracts/cb.tokens.v3.json) owns values.
 */
/*__CB3_FONTS__*/

[data-cb-v3] {
  container-type: inline-size;
  container-name: cb;
  background-color: var(--cb3-canvas);
  color: var(--cb3-ink);
  font-family: var(--cb3-font-ui);
  --cb3-dur-press: 120ms;
  --cb3-dur-lift: 150ms;
  --cb3-dur-route: 240ms;
  --cb3-dur-verdict: 300ms;
  --cb3-dur-complete: 600ms;
  --cb3-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
}

[data-cb-v3] .cb3-material {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-position: center;
  background-repeat: repeat;
}

[data-cb-v3] .cb3-material-vignette {
  background-repeat: no-repeat;
  background-size: cover;
}

[data-cb-v3] .cb3-material-grain { opacity: 0.1; }
[data-cb-v3][data-cb-scope="dark"] .cb3-material-grain { opacity: 0.14; }
[data-cb-v3] .cb3-material-vignette { opacity: 0.55; }
[data-cb-v3][data-cb-scope="dark"] .cb3-material-vignette { opacity: 0.65; }

[data-cb-v3] .cb3-card {
  background-color: var(--cb3-card-stock);
  border: 1px solid var(--cb3-rule);
  border-radius: var(--cb3-radius-round);
  color: var(--cb3-ink);
}

[data-cb-v3] .cb3-card-elevated {
  background-color: var(--cb3-card-stock);
  border-radius: var(--cb3-radius-round);
  box-shadow: var(--cb3-elev-1);
  color: var(--cb3-ink);
}

[data-cb-v3] .cb3-plank {
  background-color: var(--cb3-wood);
  border-bottom: 1px solid var(--cb3-wood-edge);
}

[data-cb-v3] .cb3-primary {
  background-color: var(--cb3-terracotta);
  border-radius: var(--cb3-radius-pill);
  color: var(--cb3-on-terracotta);
}

[data-cb-v3] .cb3-quiet {
  background-color: var(--cb3-terracotta-quiet);
  border-radius: var(--cb3-radius-soft);
  color: var(--cb3-ink);
}

[data-cb-v3] :focus-visible {
  outline: 2px solid var(--cb3-focus);
  outline-offset: 2px;
}

[data-cb-v3] .cb3-press {
  transition: transform var(--cb3-dur-press) var(--cb3-ease), opacity var(--cb3-dur-press) var(--cb3-ease);
}

[data-cb-v3] .cb3-lift {
  transition: transform var(--cb3-dur-lift) var(--cb3-ease), box-shadow var(--cb3-dur-lift) var(--cb3-ease);
}

/* ── CP-020b primitives ──────────────────────────────────────────────────────────────────────
 * Structure only: every value below is a --cb3-* custom property written from the contract. The
 * segment 85-v3-primitives.js composes these parts and owns none of the paint.
 */

/* The page gutter is a container-query rule on an inner wrapper, never an inline vw clamp on the
 * route root: a viewport unit measures the Desktop window (SPEC-V3 3.1), and cqi on the container
 * itself resolves against its ancestor, not the route. A descendant measures the route correctly. */
[data-cb-v3] .cb3-gutter {
  padding-inline: 0.7rem;
}

@container cb (min-width: 760px) {
  [data-cb-v3] .cb3-gutter {
    padding-inline: clamp(1.25rem, 3.05cqi, 4rem);
  }
}

[data-cb-v3] .cb3-quiet-outline {
  background-color: transparent;
  border: 1px solid var(--cb3-rule);
  color: var(--cb3-ink);
}

[data-cb-v3] .cb3-pill:active {
  transform: translateY(1px);
}

[data-cb-v3] .cb3-rail-item[data-current="true"]::before {
  content: "";
  position: absolute;
  left: -0.25rem;
  top: 50%;
  width: 3px;
  height: 24px;
  transform: translateY(-50%);
  background-color: var(--cb3-terracotta);
}

[data-cb-v3] .cb3-band-item[data-current="true"]::after {
  content: "";
  position: absolute;
  left: 0.35rem;
  right: 0.35rem;
  bottom: 2px;
  height: 3px;
  background-color: var(--cb3-terracotta);
}

[data-cb-v3] .cb3-shelf {
  box-shadow: var(--cb3-elev-1);
}

/* CP-040: the elevation the v3 material contract allows on a card stock object. It lives here, in
   the stylesheet, because the token gate refuses a shadow painted from an inline style — a v3
   surface that needs elev-1 names this class instead of writing boxShadow. */
[data-cb-v3] .cb3-elev-1 {
  box-shadow: var(--cb3-elev-1);
}

[data-cb-v3] .cb3-elev-2 {
  box-shadow: var(--cb3-elev-2);
}

[data-cb-v3] .cb3-elev-inset {
  box-shadow: var(--cb3-elev-inset-1);
}

[data-cb-v3] .cb3-bubble::after {
  content: "";
  position: absolute;
  left: 24px;
  bottom: -6px;
  width: 12px;
  height: 12px;
  transform: rotate(45deg);
  background-color: var(--cb3-card-stock);
  border-right: 1px solid var(--cb3-rule);
  border-bottom: 1px solid var(--cb3-rule);
}

@media (prefers-reduced-motion: reduce) {
  [data-cb-v3] .cb3-press,
  [data-cb-v3] .cb3-lift,
  [data-cb-v3] .cb3-pill:active {
    transition: none;
    transform: none;
  }
}

@media (forced-colors: active) {
  [data-cb-v3] {
    background-color: Canvas;
    color: CanvasText;
    --cb3-elev-1: none !important;
  }
  [data-cb-v3] .cb3-material {
    display: none;
  }
  [data-cb-v3] .cb3-card,
  [data-cb-v3] .cb3-card-elevated,
  [data-cb-v3] .cb3-primary {
    background-color: Canvas;
    color: CanvasText;
    border: 1px solid CanvasText;
  }
}

/* CP-053 — the wide Home is a room: one canvas, a shelf of collectible cards, a lower ledge.
   Every position is a pixel on the binding reference frame (1344x768), so this block is authored
   geometry while the paint and type still come from the token contract. Nothing here may carry a
   raw colour, a shadow outside the elevation tokens, or a font size outside the type scale.

   E2E U9 — the scene is selected from 1200 px of route width up, so between 1200 and 1344 the
   authored frame is wider than the room it stands in. The stage therefore fits instead of clipping:
   the fit box is measured and the scene is one plate scaled by the property the component sets on
   that box. A fixed frame plus overflow hidden cut the fox's right half at 1250, so the scale is
   the composition, not a crop. */
[data-cb-v3] [data-cb-home-scene-fit] {
  position: relative;
  width: 100%;
  max-width: 1344px;
  margin: 0 auto;
  overflow: hidden;
}

[data-cb-v3] [data-cb-home-scene] {
  position: relative;
  width: 1344px;
  max-width: 1344px;
  height: 768px;
  margin: 0 auto;
  overflow: hidden;
  isolation: isolate;
  transform: scale(var(--cb-home-scene-scale, 1));
  transform-origin: top left;
  /* D-007 — the room's ground is the approved hero plate (data-cb-home-scene-backdrop), a full
     bleed painted backdrop. The token canvas stays as the ground under it so a plate that fails to
     decode leaves the canvas, never a blank route. */
  background-color: var(--cb3-canvas);
}

[data-cb-v3] [data-cb-home-scene-backdrop] {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 50% 50%;
  z-index: 0;
}

[data-cb-v3] [data-cb-home-scene-hero] {
  position: absolute;
  left: 196px;
  top: 30px;
  width: 520px;
  height: 162px;
  display: block;
  z-index: 4;
}

/* G2 — the panel is the sign the question is painted on, and it is opaque on purpose: the plate
   carries a baked mockup sentence at x 210..354, y 54..124 (E1 §5), and a translucent scrim would
   let that second heading show through the live one. Its content edge is at 218 px — the measured
   left edge of the plate's own CTA pill — so every run starts where the plate's copy starts. */
[data-cb-v3] [data-cb-home-scene-panel] {
  position: relative;
  isolation: isolate;
  width: 100%;
  height: 100%;
  padding: 22px;
  box-sizing: border-box;
  border-radius: var(--cb3-radius-round);
  text-align: left;
}

[data-cb-v3] [data-cb-home-scene-panel]::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background-color: var(--cb3-canvas);
  opacity: 1;
}

[data-cb-v3] [data-cb-home-hero-band] {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  object-position: 50% 50%;
  border-radius: var(--cb3-radius-soft);
}

[data-cb-v3] [data-cb-home-scene-question] {
  margin: 0;
  font-family: var(--cb3-font-display);
  font-size: var(--cb3-text-display);
  line-height: var(--cb3-leading-display);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--cb3-ink);
}

[data-cb-v3] [data-cb-home-scene-subline] {
  margin: 2px 0 0;
  font-family: var(--cb3-font-ui);
  font-size: var(--cb3-text-lead);
  line-height: var(--cb3-leading-lead);
  font-weight: 500;
  color: var(--cb3-ink);
}

[data-cb-v3] [data-cb-home-scene-cta] {
  margin-top: 4px;
  display: flex;
  gap: 12px;
  justify-content: flex-start;
}

/* G2 — the primary pill is 174 x 44 at (218, 126): the exact quad of the plate's baked CTA
   (E1 §5, the cta_button quad), so the live control covers the painted one instead of sitting
   beside it. The fixed width is the plate's, not the label's; the label is the deck's own
   sentence.
   LEG-01 — the label is the lead step, not body. At body (16 px) the cap is 10.56 px at 1344 and
   9.43 px at 1200 (the scene plate is transform-scaled by 1200/1344), both under the 11 px
   floor; lead (20 px) measures 13.20 / 11.79 and still fits the 174 px pill: "Start a new course"
   is 157.7 px at 20 px against the pill's 162 px content edge. */
[data-cb-v3] [data-cb-home-scene-cta] button {
  border: 0;
  border-radius: var(--cb3-radius-pill);
  height: 44px;
  padding: 0 12px;
  font-family: var(--cb3-font-ui);
  font-size: var(--cb3-text-lead);
  font-weight: 600;
  color: var(--cb3-on-terracotta);
  background-color: var(--cb3-terracotta);
  box-shadow: var(--cb3-elev-1);
  cursor: pointer;
}

[data-cb-v3] [data-cb-home-scene-cta] button[data-cb-home-scene-primary] {
  width: 174px;
  padding: 0 6px;
}

/* One filled primary per surface: the browse door is the quiet warm field that carries ink. */
[data-cb-v3] [data-cb-home-scene-cta] button[data-cb-home-scene-secondary] {
  color: var(--cb3-ink);
  background-color: var(--cb3-terracotta-quiet);
}

/* G2 — the four boards hang on the plate's wall at x 261/395/529/663, y 319, each 118 x 139.8
   (E1 §5). The card is authored to that quad, 16 px of pitch left over, so a card lands exactly on
   its board and the painted board's own mini-art is covered, not doubled. */
[data-cb-v3] [data-cb-home-scene-cards] {
  position: absolute;
  top: 319px;
  left: 261px;
  height: 140px;
  display: flex;
  gap: 16px;
  align-items: flex-end;
  z-index: 3;
  margin: 0;
  padding: 0;
  list-style: none;
}

[data-cb-v3] [data-cb-home-scene-card] {
  position: relative;
  width: 118px;
  height: 140px;
  flex: 0 0 118px;
  background-color: var(--cb3-card-stock);
  border-radius: var(--cb3-radius-soft);
  box-shadow: var(--cb3-elev-1);
  overflow: hidden;
  cursor: pointer;
  color: var(--cb3-ink);
  transform-origin: 50% 100%;
}

/* U1 — the card's one control. The overlay button covers the whole card, so the wide Home keeps
 * the same keyboard reach as the narrow shelf: Tab stops here and Enter/Space open the course.
 * It paints nothing itself (the card and its cover own the material); the ring is the identity's
 * :focus-visible rule, moved inside the card because the card clips its own overflow. */
[data-cb-v3] [data-cb-home-scene-open] {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: block;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: inherit;
  background: transparent;
  color: inherit;
  cursor: pointer;
}

[data-cb-v3] [data-cb-home-scene-open]:focus-visible {
  outline-offset: -2px;
}

/* The plate's boards are hung straight, so the cards do not rotate: a 1.6 deg tilt would push a
   corner ~4 px off the painted board it is authored onto. */

[data-cb-v3] [data-cb-home-scene-card] img,
[data-cb-v3] [data-cb-home-scene-cover] {
  display: block;
  width: 100%;
  height: 75px;
  object-fit: cover;
}

[data-cb-v3] [data-cb-home-scene-cover] {
  display: grid;
  place-items: center;
  background-color: var(--cb3-terracotta-quiet);
  font-family: var(--cb3-font-display);
  font-size: var(--cb3-text-heading);
  color: var(--cb3-forest);
}

/* UI-K9 — the printed plate for a course with no plate for its subject: kit card stock inside the
 * 118x75 window, carrying the course's own two-letter mark — never the lesson room's painted cafe,
 * which would claim a subject the course may not have, and never a second copy of the title the card
 * already sets below (GM-002). All paint lives here, so the scene carries no inline colour. */
[data-cb-v3] [data-cb-home-scene-cover="type"] {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 75px;
  overflow: hidden;
  background-color: var(--cb3-canvas-edge);
  font-family: var(--cb3-font-display);
  color: var(--cb3-ink-soft);
}

[data-cb-v3] [data-cb-home-scene-cover="type"] [data-cb-cover-letter] {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  border: 1px solid var(--cb3-rule);
}

[data-cb-v3] [data-cb-home-scene-cover="type"] [data-cb-cover-mark] {
  font-size: var(--cb3-text-heading);
  line-height: var(--cb3-leading-heading);
  font-weight: 600;
  letter-spacing: 0.1em;
}

[data-cb-v3] [data-cb-home-scene-cover="type"] [data-cb-cover-rule] {
  display: block;
  width: 22px;
  height: 1px;
  background-color: var(--cb3-rule);
}

[data-cb-v3] [data-cb-home-scene-body] {
  padding: 6px 8px 8px;
}

/* G2 — a 118 px card holds ~11 characters per line at meta size, so the title is clamped to two
   lines and the progress bar is the only thing under it. The clamp is what keeps a long course
   title inside the board it is painted on (CP-TEXT-GATE measures spill, not intent). */
[data-cb-v3] [data-cb-home-scene-title] {
  margin: 0;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-family: var(--cb3-font-ui);
  font-size: var(--cb3-text-meta);
  line-height: var(--cb3-leading-meta);
  font-weight: 600;
  color: inherit;
}

[data-cb-v3] [data-cb-home-scene-progress] {
  margin-top: 6px;
  height: 4px;
  border-radius: var(--cb3-radius-pill);
  background-color: var(--cb3-rule);
  overflow: hidden;
}

[data-cb-v3] [data-cb-home-scene-progress] > i {
  display: block;
  height: 100%;
  background-color: var(--cb3-gold);
}

/* The reference card carries a title and a progress bar, not a second line of 12 px type. The
   section pair stays in the document for a screen reader and every copy oracle; it is not painted. */
[data-cb-v3] [data-cb-home-scene-meta] {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: 0;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/* G2 — the kit's two planks are retired from this surface. The plate paints its own wall coping
   (y 309.6, E1 §4) and its own bench (seat top 488.8), so a DOM plank here would be a second shelf
   in front of a painted one. The kit keeps both objects for the surfaces that still use them. */

/* VQ-011 — the tag paints the kit's own square 256x256 kraft tag at its natural aspect: the box is
   square and contain is the one size that can never stretch the file (a box-derived two-value size
   such as 100% 100% squashed the master 1.0x by 0.34x and bent the rope hole and corners).
   No plate colour and no box shadow: the file's corners are transparent, so a box-derived fill or
   shadow would paint a square around the object. The words stay DOM type on the kraft body.
   G2 — the box is the plaster patch right of board4 (E1 §5: 790..864 x 350..486), the one painted
   surface on this wall with room for a tag; the type wraps to two lines so it stays on the kraft. */
[data-cb-v3] [data-cb-home-scene-tag] {
  position: absolute;
  left: 790px;
  top: 356px;
  width: 74px;
  height: 74px;
  box-sizing: border-box;
  padding: 0 8px;
  z-index: 4;
  display: grid;
  place-items: center;
  transform: rotate(-3deg);
  background-repeat: no-repeat;
  background-size: contain;
  font-family: var(--cb3-font-display);
  font-size: var(--cb3-text-meta);
  color: var(--cb3-ink);
  text-align: center;
  line-height: 1.1;
}

/* LEG-01 — the words lie along the tag's own face, never across its edges. The master
 * (assets/objects/tag.webp) is a *tilted* luggage tag, not the reference frame's upright paper
 * label: inside the 74 px square box its light kraft face is a ~58x29 px strip lying on a
 * -35.5 deg axis (principal axis of the master's light panel, shaded fold excluded). A horizontal
 * two-line run of the pinned copy cannot lie on a band that narrow: it needs
 * which for "New course" would push the type to ~8 px.
 * Turning the run onto the face keeps the deck's own word at meta size. The angle is the measured
 * one that keeps every glyph core on the light kraft at both widths: at -35.5 deg one glyph pixel
 * still lands on the fold's edge (min 2.10:1 at 1344); at -30 deg the worst glyph-core pixel is
 * 5.27:1 at 1344 and 5.92:1 at 1200 (67 and 41 glyph-core pixels) with no pixel under 3.0:1. The
 * box, its square aspect and the single-keyword background-size are untouched.
 * The two lines are unequal ("New" 30.4 px, "course" 44.8 px at 14 px), so turning a centred block
 * swings its ink 2.7 px right of the box centre; the translate puts the ink back on the box centre
 * (CP-TEXT-GATE's tag rule: |left-right| <= 4% of 74 px = 2.96 px). */
[data-cb-v3] [data-cb-home-scene-tag] [data-cb-home-scene-tag-word] {
  display: block;
  transform: translateX(-2.7px) rotate(-30deg);
  line-height: 1.05;
  text-align: center;
}

/* G2 — the fox stands where the plate's own fox stands (E1 §5: 868,506..967,683): its painted feet
   land on the paving row at 683 and its opaque art covers the painted silhouette it replaces. */
[data-cb-v3] [data-cb-home-scene-fox] {
  position: absolute;
  left: 791px;
  top: 480px;
  z-index: 5;
}

/* E2E U9 — the wall shows four cards; with a fifth course the room needs its own door to the rest.
   G2 — it sits on the plaster band under the board row (E1 §5: 620..862 x 462..502), the painted
   surface directly beneath the boards, rather than floating on empty sky. A bare button rather
   than a hosted or pill primitive: those carry inline type, and the scene paints only from this
   stylesheet and the token contract. */
[data-cb-v3] [data-cb-home-scene-see-all] {
  position: absolute;
  left: 700px;
  top: 462px;
  z-index: 6;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 16px;
  border: 1px solid var(--cb3-rule);
  border-radius: var(--cb3-radius-pill);
  background-color: var(--cb3-card-stock);
  font-family: var(--cb3-font-ui);
  font-size: var(--cb3-text-meta);
  font-weight: 600;
  color: var(--cb3-ink);
  cursor: pointer;
}
`

/** One mode answer for the palette and the material tiles. */
function cbV3Mode(mode) {
  return mode === 'dark' ? 'dark' : 'light'
}

/** Every value the stylesheet reads, written as custom properties on the route container. */
function cbV3ScopeStyle(mode) {
  const theme = cbV3Mode(mode)
  const palette = CB_TOKENS_V3.modes[theme]
  const elevation = CB_TOKENS_V3.elevation[theme] || {}
  const radii = CB_TOKENS_V3.radii || {}
  const type = CB_TOKENS_V3.type || {}
  const style = {}
  for (const role of CB3_V3_ROLES) style[`--cb3-${role}`] = palette[role]
  for (const key of Object.keys(elevation)) style[`--cb3-${key}`] = elevation[key]
  // `inset-1` is a pressed-field look, not an object sitting on paper, but the v3 gate scopes every
  // shadow to an `--cb3-elev-*` token so a raw recipe can never hide in a class. The alias keeps
  // that one rule true for the recessed level too.
  if (elevation['inset-1']) style['--cb3-elev-inset-1'] = elevation['inset-1']
  for (const key of Object.keys(radii)) style[`--cb3-radius-${key}`] = radii[key]
  for (const step of CB3_V3_TYPE_STEPS) {
    if (type.scale && type.scale[step]) style[`--cb3-text-${step}`] = type.scale[step]
    if (type.line_height && type.line_height[step] !== undefined) {
      style[`--cb3-leading-${step}`] = String(type.line_height[step])
    }
  }
  const families = type.families || {}
  if (families.display) style['--cb3-font-display'] = families.display
  if (families.ui) style['--cb3-font-ui'] = families.ui
  if (families.cjk) style['--cb3-font-cjk'] = families.cjk
  style.colorScheme = theme === 'dark' ? 'dark' : 'light'
  style.backgroundColor = 'var(--cb3-canvas)'
  style.color = 'var(--cb3-ink)'
  return style
}

/** The data URL for one material tile id (`cb-grain-paper` -> `cb.asset.material.grain-paper`). */
function cbV3MaterialSource(tile) {
  const assets = CB_ASSETS && CB_ASSETS.assets ? CB_ASSETS.assets : {}
  const row = assets[`cb.asset.material.${String(tile || '').replace(/^cb-/, '')}`]
  return row && typeof row.src === 'string' && row.src ? row.src : null
}

/** `@font-face` rules are composed from the frozen asset segment, never hand-written here. */
function cbV3FontCss() {
  const fonts = CB_ASSETS && CB_ASSETS.fonts ? CB_ASSETS.fonts : {}
  const faces = []
  for (const family of CB3_V3_FAMILIES) {
    const src = fonts[family]
    if (!src) continue
    faces.push(
      '@font-face { font-family: "' + family + '"; src: url(' + src + ") format('woff2');" +
        ' font-weight: 100 900; font-style: normal; font-display: swap; }'
    )
  }
  return faces.join('\n')
}

/** The one stylesheet text the route mounts: the gate's CSS plus the two generated faces. */
function cbV3StyleText() {
  return CB_V3_CSS.replace('/*__CB3_FONTS__*/', cbV3FontCss())
}

/** The two ground layers for this mode: grain under vignette, each a real asset data URL. */
function cbV3MaterialLayers(mode) {
  const theme = cbV3Mode(mode)
  const materials = CB_TOKENS_V3.materials || {}
  const layers = []
  for (const key of ['grain', 'vignette']) {
    const spec = materials[key] && materials[key][theme]
    if (!spec) continue
    const src = cbV3MaterialSource(spec.tile)
    if (!src) continue
    layers.push({ key, src })
  }
  return layers
}

/** A tile that never decodes is not a blank route: it settles as a failure and flat canvas stays. */
function cbV3DecodeTexture(src, timeoutMs) {
  return new Promise((resolve) => {
    if (!src || typeof window === 'undefined' || typeof window.Image !== 'function') {
      resolve(false)
      return
    }
    let settled = false
    const finish = (ok) => {
      if (settled) return
      settled = true
      resolve(ok)
    }
    try {
      const image = new window.Image()
      image.onload = () => finish(true)
      image.onerror = () => finish(false)
      image.src = src
    } catch (error) {
      finish(false)
    }
    // jsdom and a resource-blocked host never fire load/error; a timer keeps the route honest
    // instead of leaving data-cb-v3-ready pending forever.
    if (typeof window.setTimeout === 'function') {
      window.setTimeout(() => finish(false), Math.max(200, Number(timeoutMs) || 900))
    }
  })
}

/**
 * `pending` until `document.fonts.ready` and every tile have settled, then `ready` (all tiles
 * decoded) or `fallback` (at least one did not — the flat canvas remains). A host without
 * `document.fonts` counts as settled, so an older Desktop still marks the ground ready.
 */
function useCbV3Ready(mode, sources) {
  const [state, setState] = useState('pending')
  useEffect(() => {
    let cancelled = false
    const fontsSettled =
      typeof document !== 'undefined' && document.fonts && document.fonts.ready
        ? Promise.resolve(document.fonts.ready).then(() => true, () => false)
        : Promise.resolve(true)
    const textures = sources.map((src) => cbV3DecodeTexture(src, 900))
    Promise.all([fontsSettled, ...textures]).then((results) => {
      if (cancelled) return
      setState(results.slice(1).every(Boolean) ? 'ready' : 'fallback')
    })
    return () => {
      cancelled = true
    }
  }, [mode])
  return state
}

/**
 * The v3 route scope. It *is* the route root (`data-cb-route` travels in `attributes`), so the
 * container query units and the paint scope agree on one box. Children paint above the ground.
 *
 * Every child carries a stable key: the array mixes generated material layers with two siblings,
 * and an unkeyed sibling makes React warn on every render (a warning, not an error — visible only
 * in the console, which is exactly where a capture stamp has to look).
 *
 * `data-cb-v3-ready` means *the ground painted*: it is written only once the fonts settled **and**
 * every tile decoded. The failure path keeps `data-cb-v3-textures="fallback"`, so a capture can
 * tell a materialised ground from flat paper instead of treating both as "ready".
 */
function CbV3Scope({ mode, className, attributes, style, children, contentClassName }) {
  const layers = cbV3MaterialLayers(mode)
  const status = useCbV3Ready(mode, layers.map((layer) => layer.src))
  const scopeStyle = { ...(style || {}), ...cbV3ScopeStyle(mode) }
  scopeStyle.containerType = 'inline-size'
  scopeStyle.containerName = 'cb'
  const attrs = { ...(attributes || {}) }
  attrs['data-cb-v3'] = ''
  if (status === 'ready') attrs['data-cb-v3-ready'] = 'true'
  attrs['data-cb-v3-textures'] = status === 'pending' ? 'decoding' : status
  return jsxs('div', {
    ...attrs,
    className,
    style: scopeStyle,
    children: [
      jsx('style', { children: cbV3StyleText() }, 'cb3-style'),
      ...layers.map((layer) =>
        jsx('div', {
          className: `cb3-material cb3-material-${layer.key}`,
          'aria-hidden': 'true',
          style: { backgroundImage: `url(${layer.src})`, pointerEvents: 'none' }
        }, `cb3-${layer.key}`)
      ),
      jsx('div', {
        className: ['relative flex h-full min-h-0 flex-col', contentClassName || ''].filter(Boolean).join(' '),
        style: { zIndex: 1 },
        children
      }, 'cb3-content')
    ]
  })
}

// CB-V3-END
