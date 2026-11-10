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
 * `CB_TOKENS_V3_JSON` is generated from the contract (five build-critical sections, canonical
 * bytes); `tests/test_desktop_tokens_v3.py` refuses a hand edit. `CB_V3_CSS` carries no colour —
 * every value arrives through a custom property, so the two token literals stay the only hex in
 * the module. Fonts are composed from `CB_ASSETS.fonts` data URLs at render time, with
 * `font-display: swap`; a face that fails to decode leaves the system fallback in place.
 */
const CB_TOKENS_V3_JSON =
  '{"modes":{"light":{"canvas":"#f5e3c8","canvas-edge":"#e6cfae","card-stock":"#f4ecd9","ink":"#1a1713","ink-soft":"#5c5347","rule":"#cdb894","forest":"#0d281b","on-forest":"#f5e3c8","terracotta":"#b4532f","on-terracotta":"#fffaf1","terracotta-quiet":"#f0d5c1","gold":"#a1741f","sage":"#7f9a72","wood":"#a5763f","wood-edge":"#7d5529","plum":"#6a3e74","alert":"#9c2e1c","focus":"#2a813f"},"dark":{"canvas":"#14110c","canvas-edge":"#2a2419","card-stock":"#1e1a13","ink":"#f3e6cf","ink-soft":"#bfae93","rule":"#3c352a","forest":"#0e2a1c","on-forest":"#f3e6cf","terracotta":"#e0794f","on-terracotta":"#1a1713","terracotta-quiet":"#3a241a","gold":"#d8a94e","sage":"#8fae83","wood":"#8f613c","wood-edge":"#c08856","plum":"#cda0d8","alert":"#f0a08c","focus":"#f2c56a"}},"elevation":{"light":{"elev-1":"0 1px 1px rgba(58, 35, 24, 0.10), 0 6px 14px -8px rgba(58, 35, 24, 0.28)","elev-2":"0 2px 2px rgba(58, 35, 24, 0.12), 0 14px 28px -12px rgba(58, 35, 24, 0.34)","inset-1":"inset 0 1px 2px rgba(58, 35, 24, 0.18), inset 0 -1px 0 rgba(255, 250, 240, 0.50)"},"dark":{"elev-1":"0 1px 1px rgba(0, 0, 0, 0.45), 0 6px 14px -8px rgba(0, 0, 0, 0.65)","elev-2":"0 2px 3px rgba(0, 0, 0, 0.50), 0 16px 30px -12px rgba(0, 0, 0, 0.70)","inset-1":"inset 0 1px 2px rgba(0, 0, 0, 0.55), inset 0 -1px 0 rgba(255, 241, 220, 0.08)"},"rules":["Elevation is contact shadow for a physical object on paper, never a glow.","A card uses elev-1 or a 1px rule border, not both.","inset-1 is for pressed and recessed fields only (a tray, an input, a selected slot).","No elevation on text, rules, the rail or the canvas ground."]},"radii":{"square":"0px","soft":"6px","round":"12px","pill":"999px"},"type":{"families":{"display":"\\"CB Display\\", \\"Fraunces\\", ui-serif, Georgia, \\"Noto Serif JP\\", \\"Hiragino Mincho ProN\\", \\"Yu Mincho\\", serif","ui":"\\"CB UI\\", \\"Source Sans 3\\", system-ui, \\"Hiragino Kaku Gothic ProN\\", \\"Yu Gothic\\", \\"Noto Sans JP\\", sans-serif","cjk":"\\"Noto Serif JP\\", \\"Hiragino Mincho ProN\\", \\"Yu Mincho\\", \\"Noto Serif CJK JP\\", serif"},"subsets":{"CB Display":"Fraunces, OFL, subset to Latin plus punctuation","CB UI":"Source Sans 3, OFL, subset to Latin plus punctuation","cjk":"system CJK stack; a shipped Noto Serif JP subset is the first entry when CP-004 embeds it"},"loading":"font-display: swap; a face that fails to load leaves the system fallback in place and never blanks the route","container":{"name":"cb","type":"inline-size","measured_against":"the route container, never the window","note":"Every cqi in this table resolves against the [data-cb-v3] route container."},"scale":{"caption":"0.75rem","meta":"0.875rem","body":"1rem","lead":"1.25rem","heading":"clamp(1.5rem, 1.2rem + 1cqi, 2.25rem)","display":"clamp(2.5rem, 1.5rem + 3cqi, 4rem)"},"line_height":{"caption":1.35,"meta":1.4,"body":1.5,"lead":1.35,"heading":1.15,"display":1.02},"weights":{"display":600,"heading":600,"body":400,"strong":600},"measure":"50-75ch for prose; display headings at most 20ch, section headings at most 34ch","rules":["Six steps and no seventh.","Body is 1rem so a 200 percent root scales every step.","Display is measured against the route container via cqi, so a narrow route shrinks the headline instead of overflowing it.","Japanese lesson lines use the cjk family for kana and kanji and the ui family for romaji; furigana is smaller than the body step by design, never a seventh authored size."]},"motion":{"press":120,"lift":150,"route":240,"verdict":300,"complete":600,"ceiling":600,"loops":false,"easing":"cubic-bezier(0.2, 0.8, 0.2, 1)","properties":["transform","opacity"],"reduced_motion":"transitions are removed, not shortened; the state change still happens on the next frame","rules":["No duration in this table may exceed ceiling (600 ms).","No looping, pulsing, shimmering or infinite animation anywhere.","Motion is feedback for a real event: press, lift, route change, check verdict, completion.","transform and opacity only; never animate layout, colour or filter."]},"materials":{"grain":{"light":{"tile":"cb-grain-paper","file":"material/grain-paper.webp","opacity":0.1},"dark":{"tile":"cb-grain-night","file":"material/grain-night.webp","opacity":0.14}},"vignette":{"light":{"tile":"cb-vignette-parchment","file":"material/vignette-parchment.webp","opacity":0.55},"dark":{"tile":"cb-vignette-night","file":"material/vignette-night.webp","opacity":0.65}},"wood":{"light":{"tile":"cb-wood-plank","file":"material/wood-plank.webp","opacity":1.0},"dark":{"tile":"cb-wood-plank-night","file":"material/wood-plank-night.webp","opacity":1.0}},"opacity_ceiling":0.18,"rules":["Grain and vignette are aria-hidden and pointer-events none; they sit above the canvas and below all content.","Grain opacity may never exceed opacity_ceiling over a text run.","Wood is a tile on the shelf plank and the evidence tray only; it never sits behind text.","Missing texture falls back to flat canvas; never a blank route, never a broken-image mark.","All tiles are seamless 3x3 (CP-011 proof) and at most 60 KB each."]}}'

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

@media (prefers-reduced-motion: reduce) {
  [data-cb-v3] .cb3-press,
  [data-cb-v3] .cb3-lift {
    transition: none;
  }
}

@container cb (max-width: 619px) {
  [data-cb-v3] .cb3-material-grain { opacity: 0.06; }
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
 */
function CbV3Scope({ mode, className, attributes, style, children }) {
  const layers = cbV3MaterialLayers(mode)
  const ready = useCbV3Ready(mode, layers.map((layer) => layer.src))
  const scopeStyle = { ...(style || {}), ...cbV3ScopeStyle(mode) }
  scopeStyle.containerType = 'inline-size'
  scopeStyle.containerName = 'cb'
  const attrs = { ...(attributes || {}) }
  attrs['data-cb-v3'] = ''
  if (ready !== 'pending') attrs['data-cb-v3-ready'] = ''
  attrs['data-cb-v3-textures'] = ready === 'pending' ? 'decoding' : ready
  return jsxs('div', {
    ...attrs,
    className,
    style: scopeStyle,
    children: [
      jsx('style', { children: cbV3StyleText() }),
      ...layers.map((layer) =>
        jsx('div', {
          className: `cb3-material cb3-material-${layer.key}`,
          'aria-hidden': 'true',
          style: { backgroundImage: `url(${layer.src})`, pointerEvents: 'none' }
        }, `cb3-${layer.key}`)
      ),
      jsx('div', {
        className: 'relative flex h-full min-h-0 flex-col',
        style: { zIndex: 1 },
        children
      })
    ]
  })
}

// CB-V3-END
