// CB-V3-BEGIN — CP-020b: the Field Atlas v3 primitives and their component-lab sheet.
/**
 * ── Field Atlas v3 primitives ─────────────────────────────────────────────────────────────────
 *
 * CP-020b. Every screen card after this one (CP-021 Home, CP-022 Discover, CP-023 Classroom,
 * CP-024 course home) composes these parts instead of inventing a local box. Two rules hold for
 * everything in this segment and both are executable:
 *
 * 1. **No value, no colour.** Each primitive paints from `var(--cb3-*)` only — the roles, elevation,
 *    radii and type steps CP-020a writes onto `[data-cb-v3]` from `contracts/cb.tokens.v3.json`
 *    (SPEC-V3 §3.4–§3.6). There is not one hex, colour function, gradient, shadow recipe or
 *    viewport unit below: `tests/test_v3_primitives.py::test_primitives_use_only_v3_tokens` scans
 *    this segment for all of them, and the `--cb-` prefix (the v2 table) is a defect here, not a
 *    fallback.
 * 2. **One primary per surface.** `PillAction` is the only filled control in the system, it is
 *    always `variant: 'primary'` *or* `variant: 'quiet'` at the call site, and an unknown variant
 *    falls back to `quiet` so a typo can never mint a second primary. The lab sheet itself carries
 *    zero filled controls (SPEC-V3 §3.10: the lab's documented N/A), which is the state
 *    `test_v3_one_primary_per_surface` asserts beside the one-primary case.
 *
 * The parts, and the state each one must be able to paint:
 *   PillAction        primary / quiet, hover-free, pressed, disabled, busy
 *   ForestRail        wide rail; current item marked by a 3 px terracotta shape + word
 *   ForestBand        the same four destinations as a 56 px tab strip below 920 route px
 *   PaperCard         rule-edged paper, or elevation — never both (contract elevation.rules)
 *   CoverPlate3       a real cover artifact, or a typographic plate when there is no art
 *   CollectibleCard   cover window, title, subject chip, one real meta row, optional New chip
 *   ShelfPlank        a wood plank with its front lip; cards sit on it, bottom-aligned
 *   StampNode         done / current / upcoming / locked, always a real button element
 *   Medallion         one Codicon on one painted rim per *named* recorded event
 *   FoxPose           seven poses, aria-hidden, inside its safe area, gone below 620
 *   DialogueBubble    ruby furigana over the kana, one romaji line, optional speaker button
 *   ChallengeCard     Game-mode field challenge with a quiet action, never a second primary
 *   EvidenceTray      recorded checks, their real event names, and one refusal sentence
 *
 * `CbV3LabSheet` composes all of it for `scripts/cp-lab-shot.mjs`. It is a **component preview**
 * (surface id `component.lab`), never a live Desktop screen, and it says so in its own copy.
 */

/* ── token readers ───────────────────────────────────────────────────────────────────────────
 * One spelling per token family, so a mistyped custom property is caught by the scan rather than
 * silently painting nothing. `cb3Role` reads a colour role, `cb3Type` a type step, `cb3Lead`
 * that step's line-height and `cb3Radius` one of the contract's four radii.
 */
function cb3Role(role) {
  return `var(--cb3-${role})`
}

function cb3Type(step) {
  return `var(--cb3-text-${step})`
}

function cb3Lead(step) {
  return `var(--cb3-leading-${step})`
}

function cb3Radius(name) {
  return `var(--cb3-radius-${name})`
}

/** One frozen brand asset's data URL, or null. Never a hand-written image path. */
function cb3Asset(key) {
  const assets = CB_ASSETS && CB_ASSETS.assets ? CB_ASSETS.assets : {}
  const row = assets[key]
  return row && typeof row.src === 'string' && row.src ? row.src : null
}

/** One object-kit blank (`stamp-rim`, `medallion-rim`, `shelf-plank`, …). */
function cb3ObjectSource(name) {
  return cb3Asset(`cb.asset.object.${name}`)
}

/** The fox is one mascot in seven poses; the export sizes the contract ships are 128 and 64. */
const CB3_POSES = Object.freeze(['wave', 'point', 'clock', 'read', 'cheer', 'think', 'sleep'])

function cb3FoxSource(pose, size) {
  const key = CB3_POSES.indexOf(pose) >= 0 ? pose : 'clock'
  const want = Number(size) >= 128 ? 128 : 64
  return cb3Asset(`cb.asset.fox.${key}.${want}`) || cb3Asset(`cb.asset.fox.${key}.64`)
}

/* ── the four shipped destinations ───────────────────────────────────────────────────────────
 * SPEC-V3 §3.11 D3: one navigation system on every screen. The rail carries these in this order,
 * Codicon plus a visible label, and there is never a fifth entry. `home` is current only when the
 * route is the desk; a course screen marks `courses`.
 */
const CB3_DESTINATIONS = Object.freeze([
  Object.freeze({ id: 'home', icon: 'home', label: 'Home' }),
  Object.freeze({ id: 'courses', icon: 'library', label: 'Courses' }),
  Object.freeze({ id: 'workshop', icon: 'compass', label: 'Workshop' }),
  Object.freeze({ id: 'studio', icon: 'person', label: 'Parent Studio' })
])

/* ── the stamp stepper's four states (SPEC-V3 §5.3 C3) ─────────────────────────────────────── */
const CB3_STAMP_STATES = Object.freeze(['done', 'current', 'upcoming', 'locked'])
const CB3_STAMP_ICON = Object.freeze({
  done: 'check',
  current: 'play',
  upcoming: 'chevron-right',
  locked: 'lock'
})
const CB3_STAMP_WORD = Object.freeze({ done: 'Done', current: 'Now', upcoming: 'Next', locked: 'Locked' })

/* ── one medallion per *named* event, never per decorative shape (SPEC-V3 §6 honesty) ───────── */
const CB3_MEDALS = Object.freeze({
  first_check: Object.freeze({ icon: 'check', label: 'First check' }),
  first_review: Object.freeze({ icon: 'book', label: 'First review' }),
  first_takehome: Object.freeze({ icon: 'home', label: 'First take-home' }),
  course_complete: Object.freeze({ icon: 'verified', label: 'Course complete' })
})

/* ── contrast maths, for the lab's chips only ────────────────────────────────────────────────
 * A palette chip has to name a *computed* ratio (SPEC-V3 §5.5 S8). The numbers come from the
 * contract's two role values at render time, so the sheet can never print a ratio the shipped
 * palette does not have, and no ratio is authored here.
 */
function cb3Channel(value) {
  const channel = Number(value) / 255
  return channel <= 0.03928 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4)
}

function cb3Luminance(hex) {
  const text = String(hex || '').replace('#', '')
  if (text.length !== 6) return 0
  return (
    0.2126 * cb3Channel(parseInt(text.slice(0, 2), 16)) +
    0.7152 * cb3Channel(parseInt(text.slice(2, 4), 16)) +
    0.0722 * cb3Channel(parseInt(text.slice(4, 6), 16))
  )
}

function cb3Contrast(first, second) {
  const a = cb3Luminance(first)
  const b = cb3Luminance(second)
  const light = Math.max(a, b)
  const dark = Math.min(a, b)
  return (light + 0.05) / (dark + 0.05)
}

/* ── the 1049 rendering of a fluid step, for the type rows ───────────────────────────────────
 * SPEC-V3 §3.4 is a *rendering* of the contract, so the lab computes it instead of quoting it:
 * `clamp(min, base + slope·cqi, max)` is evaluated with one cqi = containerWidth / 100.
 */
function cb3StepRendering(step, containerPx) {
  const scale = (CB_TOKENS_V3.type && CB_TOKENS_V3.type.scale) || {}
  const leading = (CB_TOKENS_V3.type && CB_TOKENS_V3.type.line_height) || {}
  const value = String(scale[step] || '')
  const ratio = Number(leading[step] || 0)
  let px = 0
  const clamp = /^clamp\(\s*([\d.]+)rem\s*,\s*([\d.]+)rem\s*\+\s*([\d.]+)cqi\s*,\s*([\d.]+)rem\s*\)$/.exec(value)
  if (clamp) {
    const cqi = Math.max(0, Number(containerPx) || 0) / 100
    px = Math.min(Number(clamp[4]), Math.max(Number(clamp[1]), Number(clamp[2]) + Number(clamp[3]) * cqi)) * 16
  } else if (value.endsWith('rem')) {
    px = Number(value.slice(0, -3)) * 16
  }
  const line = ratio > 0 ? px * ratio : 0
  return { px: Math.round(px * 100) / 100, line: Math.round(line * 100) / 100 }
}

/* ── PillAction ──────────────────────────────────────────────────────────────────────────────
 * The one action in the system, in two weights: `primary` is the single filled control on a
 * surface (terracotta fill, on-terracotta label, pill radius); `quiet` is a 1 px rule outline
 * with an ink label at the same 48 px height, so the pair reads as one action and one door
 * without a second fill. It is always a real button element; `disabled` and `aria-busy` are states of
 * that same button, never a dead div. Touch target: 48 px tall, never shrunk at 460 or 200%.
 * Tokens: terracotta, on-terracotta, rule, ink, radius.pill, type.meta.
 */
function PillAction({ variant, label, icon, onClick, disabled, busy, type, className, style, children, ...rest }) {
  const weight = variant === 'primary' ? 'primary' : 'quiet'
  return jsxs('button', {
    ...rest,
    type: type || 'button',
    'data-cb3-pill': weight,
    className: ['cb3-pill', weight === 'primary' ? 'cb3-primary cb3-press' : 'cb3-quiet-outline cb3-press', className || '']
      .filter(Boolean)
      .join(' '),
    disabled: disabled === true,
    'aria-busy': busy === true ? 'true' : undefined,
    onClick,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.5rem',
      minHeight: '48px',
      paddingInline: '1.25rem',
      borderRadius: cb3Radius('pill'),
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('meta'),
      lineHeight: cb3Lead('meta'),
      fontWeight: 600,
      textDecoration: 'none',
      cursor: disabled === true ? 'not-allowed' : 'pointer',
      opacity: disabled === true ? 0.55 : 1,
      ...(style || {})
    },
    children: [
      icon ? jsx(sdk.Codicon, { name: icon, size: CB_ICON_UI }, 'icon') : null,
      jsx('span', { children: label || children }, 'label')
    ]
  })
}

/* ── ForestRail ──────────────────────────────────────────────────────────────────────────────
 * The wide shell: an 80 px forest rail inside the route (never the host sidebar), one labelled
 * Codicon row per destination, at least 56 px targets. The current destination is a 3 px terracotta
 * marker on the rail's inner edge *plus* `aria-current="page"` and the full-contrast label —
 * a shape and a word, never colour alone (SPEC-V3 §3.11).
 * Tokens: forest, on-forest, terracotta, radius.soft, type.meta.
 */
function ForestRail({ value, onChange, className, ...rest }) {
  return jsx('nav', {
    ...rest,
    'data-cb3-rail': '',
    'aria-label': 'Coursebook sections',
    className: ['cb3-rail', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
      width: 'clamp(72px, 7.63cqi, 80px)',
      minHeight: '100%',
      paddingBlock: '0.75rem',
      paddingInline: '0.25rem',
      backgroundColor: cb3Role('forest'),
      color: cb3Role('on-forest')
    },
    children: CB3_DESTINATIONS.map((item) => {
      const current = item.id === value
      return jsxs('button', {
        type: 'button',
        'data-cb3-rail-item': item.id,
        'data-current': current ? 'true' : 'false',
        'aria-current': current ? 'page' : undefined,
        className: 'cb3-rail-item',
        onClick: () => {
          if (typeof onChange === 'function') onChange(item.id)
        },
        style: {
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.25rem',
          minHeight: '56px',
          padding: '0.35rem 0.2rem',
          border: 0,
          borderRadius: cb3Radius('soft'),
          background: 'transparent',
          color: cb3Role('on-forest'),
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('caption'),
          lineHeight: cb3Lead('caption'),
          fontWeight: current ? 600 : 400,
          cursor: 'pointer'
        },
        children: [
          jsx(sdk.Codicon, { name: item.icon, size: CB_ICON_UI }, 'glyph'),
          jsx('span', { children: item.label }, 'label')
        ]
      }, item.id)
    })
  })
}

/* ── ForestBand ──────────────────────────────────────────────────────────────────────────────
 * The same four destinations below a 920 px route: a 56 px top strip that scrolls sideways
 * instead of shrinking its labels. Same markers, same accessible contract as the rail, so a
 * reader who resizes never meets a second navigation vocabulary.
 * Tokens: forest, on-forest, terracotta, radius.soft, type.meta.
 */
function ForestBand({ value, onChange, className, ...rest }) {
  return jsxs('nav', {
    ...rest,
    'data-cb3-band': '',
    'aria-label': 'Coursebook sections',
    className: ['cb3-band', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      alignItems: 'stretch',
      gap: '0.25rem',
      minHeight: '56px',
      paddingInline: '0.25rem',
      overflowX: 'auto',
      backgroundColor: cb3Role('forest'),
      color: cb3Role('on-forest')
    },
    children: CB3_DESTINATIONS.map((item) => {
      const current = item.id === value
      return jsxs('button', {
        type: 'button',
        'data-cb3-band-item': item.id,
        'data-current': current ? 'true' : 'false',
        'aria-current': current ? 'page' : undefined,
        className: 'cb3-band-item',
        onClick: () => {
          if (typeof onChange === 'function') onChange(item.id)
        },
        style: {
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          flex: '0 0 auto',
          minHeight: '44px',
          paddingInline: '0.55rem',
          border: 0,
          borderRadius: cb3Radius('soft'),
          background: 'transparent',
          color: cb3Role('on-forest'),
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: cb3Lead('meta'),
          fontWeight: current ? 600 : 400,
          whiteSpace: 'nowrap',
          cursor: 'pointer'
        },
        children: [
          jsx(sdk.Codicon, { name: item.icon, size: CB_ICON_UI }, 'glyph'),
          jsx('span', { children: item.label }, 'label')
        ]
      }, item.id)
    })
  })
}

/* ── PaperCard ───────────────────────────────────────────────────────────────────────────────
 * A card is a paper object on the desk. `emphasis: 'rule'` (default) is card stock with a 1 px
 * rule edge; `emphasis: 'elev-1'` is card stock with a contact shadow and *no* border — the
 * contract's elevation rule forbids both on one object, so the pair is one prop, not two
 * independent booleans a caller could set at once.
 * Tokens: card-stock, rule, ink, ink-soft, radius.round, elev-1, type.body.
 */
function PaperCard({ emphasis, title, meta, children, footer, className, style, ...rest }) {
  const elevated = emphasis === 'elev-1'
  return jsxs('div', {
    ...rest,
    'data-cb3-card': 'paper',
    'data-cb3-emphasis': elevated ? 'elev-1' : 'rule',
    className: ['cb3-paper', elevated ? 'cb3-card-elevated' : 'cb3-card', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      minWidth: 0,
      padding: '1rem',
      color: cb3Role('ink'),
      ...(style || {})
    },
    children: [
      title
        ? jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              maxWidth: '34ch',
              overflowWrap: 'anywhere'
            },
            children: title
          }, 'title')
        : null,
      meta
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: meta
          }, 'meta')
        : null,
      children || null,
      footer || null
    ]
  })
}

/* ── CoverPlate3 ─────────────────────────────────────────────────────────────────────────────
 * A 3:2 plate, mechanically cropped. With a real artifact URL it is media (an `img`, alt empty,
 * `aria-hidden` — the card's own title carries the words). With no artifact it is a
 * **typographic** plate: the title itself at the heading step on the canvas-edge plate, which is
 * DOM text and the only place that title appears, so no cover is ever invented and no monogram
 * pretends to be a logo.
 * Tokens: canvas-edge, ink, rule, radius.square, type.heading.
 */
function CoverPlate3({ src, title, className, style, ...rest }) {
  const hasArt = typeof src === 'string' && src.length > 0
  return jsxs('div', {
    ...rest,
    'data-cb3-cover': hasArt ? 'art' : 'type',
    className: ['cb3-cover', className || ''].filter(Boolean).join(' '),
    style: {
      position: 'relative',
      aspectRatio: '3 / 2',
      width: '100%',
      overflow: 'hidden',
      borderRadius: cb3Radius('square'),
      backgroundColor: cb3Role('canvas-edge'),
      border: hasArt ? 0 : `1px solid ${cb3Role('rule')}`,
      ...(style || {})
    },
    children: [
      hasArt
        ? jsx('img', {
            src,
            alt: '',
            'aria-hidden': 'true',
            style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover' }
          }, 'art')
        : jsx('span', {
            style: {
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'flex-end',
              padding: '0.75rem',
              boxSizing: 'border-box',
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              color: cb3Role('ink'),
              overflowWrap: 'anywhere'
            },
            children: title || ''
          }, 'type')
    ]
  })
}

/* ── CollectibleCard ─────────────────────────────────────────────────────────────────────────
 * The shelf object: a cover window, the title, one subject chip, and one real meta row
 * (`2 of 5 sections done · Continue section 3`, never a rating). `New` is a chip only when the
 * caller has a backing fact for it (no attempts yet). There is no star row, no review count, no
 * progress bar and no invented XP anywhere in this component — the meta row is the whole story.
 * Tokens: card-stock, rule, ink, ink-soft, terracotta-quiet, radius.round, radius.soft,
 * type.heading, type.meta, type.caption.
 */
function CollectibleCard({ title, subject, meta, src, isNew, newLabel, action, onOpen, className, style, ...rest }) {
  const hasArt = typeof src === 'string' && src.length > 0
  const subjectChip = subject
    ? jsx('span', {
        'data-cb3-chip': 'subject',
        style: {
          display: 'inline-block',
          alignSelf: 'flex-start',
          paddingInline: '0.5rem',
          paddingBlock: '0.15rem',
          borderRadius: cb3Radius('soft'),
          backgroundColor: cb3Role('terracotta-quiet'),
          color: cb3Role('ink'),
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('caption'),
          lineHeight: cb3Lead('caption')
        },
        children: subject
      }, 'subject')
    : null
  return jsxs('article', {
    ...rest,
    'data-cb3-card': 'collectible',
    'data-cb3-cover-mode': hasArt ? 'art' : 'type',
    className: ['cb3-collectible', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      minWidth: 0,
      padding: '0.65rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      ...(style || {})
    },
    children: [
      jsx(CoverPlate3, { src: hasArt ? src : null, title }, 'cover'),
      hasArt
        ? jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              maxWidth: '34ch',
              overflowWrap: 'anywhere'
            },
            children: title
          }, 'title')
        : null,
      subjectChip,
      meta
        ? jsx('p', {
            'data-cb3-card-meta': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: meta
          }, 'meta')
        : null,
      isNew && newLabel
        ? jsx('span', {
            'data-cb3-chip': 'new',
            style: {
              alignSelf: 'flex-start',
              paddingInline: '0.5rem',
              paddingBlock: '0.1rem',
              borderRadius: cb3Radius('soft'),
              border: `1px solid ${cb3Role('gold')}`,
              color: cb3Role('ink'),
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption')
            },
            children: newLabel
          }, 'new')
        : null,
      action || null
    ]
  })
}

/* ── ShelfPlank ──────────────────────────────────────────────────────────────────────────────
 * A shelf is a wooden ledge inside its own scroll frame, not a bordered box: the wood face is
 * the top of the plank, `wood-edge` is its front lip (the 1 px of thickness beneath), and
 * `elev-1` is the contact shadow of the object on the paper. Cards are bottom-aligned on it and
 * never float above it; the row scrolls rather than shrinking a card (SPEC-V3 §3.3).
 * Tokens: wood, wood-edge, elev-1, radius.square.
 */
function ShelfPlank({ children, className, style, ...rest }) {
  return jsxs('div', {
    ...rest,
    'data-cb3-shelf': '',
    className: ['cb3-shelf', className || ''].filter(Boolean).join(' '),
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'flex-end',
      gap: '1rem',
      minWidth: 0,
      paddingBottom: '12px',
      overflowX: 'auto',
      ...(style || {})
    },
    children: [
      jsx('div', {
        'aria-hidden': 'true',
        className: 'cb3-plank cb3-plank-face',
        style: {
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: '12px',
          backgroundImage: cb3ObjectSource('shelf-plank') ? `url(${cb3ObjectSource('shelf-plank')})` : undefined,
          backgroundRepeat: 'repeat-x',
          backgroundSize: 'auto 100%',
          borderBottom: `1px solid ${cb3Role('wood-edge')}`
        }
      }, 'plank'),
      jsxs('div', {
        style: {
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          alignItems: 'flex-end',
          gap: '1rem',
          minWidth: 0
        },
        children
      }, 'row')
    ]
  })
}

/* ── StampNode ───────────────────────────────────────────────────────────────────────────────
 * A real button element in every state — done, current, upcoming, locked. The painted `stamp-rim`
 * blank is the object, the Codicon is the icon, the label is DOM text under it, and the current
 * step adds the word `Now` beside a 3 px ring, so the state never depends on colour alone. A
 * locked node is a disabled button (the plan gates it), not a decorative padlock.
 * Tokens: ink, ink-soft, terracotta, type.caption, radius.square.
 */
function StampNode({ state, label, stateWord, index, onClick, className, style, ...rest }) {
  const tone = CB3_STAMP_STATES.indexOf(state) >= 0 ? state : 'upcoming'
  const current = tone === 'current'
  const locked = tone === 'locked'
  const word = tone === 'done' || tone === 'upcoming' ? null : stateWord || CB3_STAMP_WORD[tone]
  return jsxs('button', {
    ...rest,
    type: 'button',
    'data-cb3-stamp': tone,
    'data-cb3-stamp-index': index === undefined ? undefined : String(index),
    'aria-current': current ? 'step' : undefined,
    disabled: locked,
    'aria-disabled': locked ? 'true' : undefined,
    className: ['cb3-stamp', 'cb3-press', className || ''].filter(Boolean).join(' '),
    onClick,
    style: {
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.35rem',
      minWidth: '56px',
      padding: 0,
      border: 0,
      background: 'transparent',
      color: cb3StampInk(tone),
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('caption'),
      lineHeight: cb3Lead('caption'),
      cursor: locked ? 'not-allowed' : 'pointer',
      ...(style || {})
    },
    children: [
      jsxs('span', {
        'aria-hidden': 'true',
        className: 'cb3-stamp-blank',
        style: {
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '48px',
          height: '48px',
          backgroundImage: cb3ObjectSource('stamp-rim') ? `url(${cb3ObjectSource('stamp-rim')})` : undefined,
          backgroundSize: 'contain',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center',
          // The current-step ring is a 3 px shape, not a glow and not a shadow (contract
          // elevation.rules: no elevation on a mark). Outline keeps it outside the glyph.
          outline: current ? `3px solid ${cb3Role('terracotta')}` : 'none',
          outlineOffset: '0px',
          borderRadius: cb3Radius('square'),
          opacity: locked ? 0.5 : 1
        },
        children: jsx(sdk.Codicon, { name: CB3_STAMP_ICON[tone], size: CB_ICON_PLATE }, 'glyph')
      }, 'blank'),
      jsx('span', { style: { maxWidth: '12ch', overflowWrap: 'anywhere' }, children: label }, 'label'),
      word ? jsx('span', { style: { fontWeight: 600 }, children: word }, 'word') : null
    ]
  })
}

/** A stamp's ink: done and current are reading text, the rest are soft metadata. */
function cb3StampInk(tone) {
  if (tone === 'done' || tone === 'current') return cb3Role('ink')
  return cb3Role('ink-soft')
}

/* ── Medallion ───────────────────────────────────────────────────────────────────────────────
 * One painted rim, one Codicon glyph, one *named* recorded event, one DOM label. The same blank
 * is used for every event (five different painted medallions would be decoration a learner
 * cannot name); an event this system does not know renders nothing rather than an empty seal.
 * The rim is the object-kit `medallion-rim` blank (art), so gold is not a paint token here.
 * Tokens: ink, type.caption.
 */
function Medallion({ event, label, size, className, style, ...rest }) {
  const spec = CB3_MEDALS[event]
  if (!spec) return null
  const box = Number(size) > 0 ? Number(size) : 64
  return jsxs('div', {
    ...rest,
    'data-cb3-medal': event,
    className: ['cb3-medal', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'inline-flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.35rem',
      width: `${box + 16}px`,
      textAlign: 'center',
      ...(style || {})
    },
    children: [
      jsxs('span', {
        'aria-hidden': 'true',
        style: {
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: `${box}px`,
          height: `${box}px`,
          backgroundImage: cb3ObjectSource('medallion-rim') ? `url(${cb3ObjectSource('medallion-rim')})` : undefined,
          backgroundSize: 'contain',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'center',
          color: cb3Role('ink')
        },
        children: jsx(sdk.Codicon, { name: spec.icon, size: CB_ICON_PLATE }, 'glyph')
      }, 'blank'),
      jsx('span', {
        style: {
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('caption'),
          lineHeight: cb3Lead('caption'),
          color: cb3Role('ink-soft')
        },
        children: label || spec.label
      }, 'label')
    ]
  })
}

/* ── FoxPose ─────────────────────────────────────────────────────────────────────────────────
 * The one mascot, in one of seven poses, inside one box. `aria-hidden` throughout: the adjacent
 * visible text carries whatever meaning it has, never the picture. Sizes are the shipped
 * exports (128 and 64) and the box includes the pose's widest frame. Below a 620 px route the
 * fox is absent, not squashed (SPEC-V3 §3.8), and it never overlaps type or a control: the
 * safe-area clearance is 24 px at a wide route and 16 px below it.
 * Tokens: none (the plate is art); geometry from the spec's safe area.
 */
function FoxPose({ pose, size, className, style, ...rest }) {
  const width = useCbViewportWidth()
  if (width > 0 && width < 620) return null
  const box = Number(size) > 0 ? Number(size) : 128
  const clearance = width >= 920 ? '24px' : '16px'
  return jsx('div', {
    ...rest,
    'data-cb3-fox': CB3_POSES.indexOf(pose) >= 0 ? pose : 'clock',
    'data-cb3-fox-safe': clearance,
    'aria-hidden': 'true',
    className: ['cb3-fox', className || ''].filter(Boolean).join(' '),
    style: {
      width: `${box}px`,
      height: `${box}px`,
      marginInlineEnd: clearance,
      pointerEvents: 'none',
      flex: '0 0 auto',
      ...(style || {})
    },
    children: jsx('img', {
      src: cb3FoxSource(pose, box),
      alt: '',
      'aria-hidden': 'true',
      style: { display: 'block', width: '100%', height: '100%', objectFit: 'contain' }
    }, 'img')
  }, 'fox')
}

/* ── DialogueBubble ──────────────────────────────────────────────────────────────────────────
 * The lesson line: the pack's kana with the deck's ruby over each kanji, one romaji line under
 * it, the English meaning, and an optional speaker button on the bubble only (never as an
 * answer option). The ruby is `<rt>` so a screen reader reads the reading with its base; the
 * romaji is a separate `lang="ja-Latn"` line, a scaffold and never the only form offered. The
 * speaker is a **quiet text action**: `playLabel` (the deck's `classroom.line.play`) is its
 * visible label *and* its accessible name, and a bubble with no label renders no control —
 * never an unlabelled icon button.
 * Tokens: card-stock, rule, ink, ink-soft, radius.round, radius.soft, type.lead, type.body,
 * type.meta.
 */
function DialogueBubble({ segments, romaji, en, onPlay, playLabel, className, style, ...rest }) {
  const parts = Array.isArray(segments) ? segments : []
  return jsxs('div', {
    ...rest,
    'data-cb3-bubble': '',
    className: ['cb3-bubble cb3-card', className || ''].filter(Boolean).join(' '),
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      maxWidth: '44ch',
      padding: '1rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      ...(style || {})
    },
    children: [
      jsx('p', {
        lang: 'ja',
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-cjk)',
          fontSize: cb3Type('lead'),
          lineHeight: cb3Lead('lead')
        },
        children: parts.map((part, index) =>
          part && part.ruby
            ? jsxs('ruby', {
                children: [
                  jsx('span', { children: part.text }, 'base'),
                  jsx('rt', {
                    style: {
                      fontSize: '0.5em',
                      fontFamily: 'var(--cb3-font-cjk)',
                      color: cb3Role('ink-soft')
                    },
                    children: part.ruby
                  }, 'ruby')
                ]
              }, `seg-${index}`)
            : jsx('span', { children: part ? part.text : '' }, `seg-${index}`)
        )
      }, 'jp'),
      romaji
        ? jsx('p', {
            lang: 'ja-Latn',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: romaji
          }, 'romaji')
        : null,
      en
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('body'),
              lineHeight: cb3Lead('body')
            },
            children: en
          }, 'en')
        : null,
      typeof onPlay === 'function' && playLabel
        ? jsx('button', {
            type: 'button',
            'data-cb3-speak': '',
            'aria-label': playLabel,
            onClick: onPlay,
            style: {
              alignSelf: 'flex-start',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              minHeight: '44px',
              paddingInline: '0.5rem',
              border: `1px solid ${cb3Role('rule')}`,
              borderRadius: cb3Radius('soft'),
              background: 'transparent',
              color: cb3Role('ink'),
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              cursor: 'pointer'
            },
            children: [
              jsx(sdk.Codicon, { name: 'unmute', size: CB_ICON_UI }, 'glyph'),
              jsx('span', { children: playLabel }, 'label')
            ]
          }, 'speak')
        : null
    ]
  })
}

/* ── ChallengeCard ───────────────────────────────────────────────────────────────────────────
 * Game mode's field challenge, in the aside, behind a real served check. Its action is a
 * **quiet** pill on purpose: the lesson's one filled control is `Check answer`, and a second
 * fill in the aside would be two primaries on one screen. The card names the check it opens and
 * carries no reward the backend did not record.
 * Tokens: card-stock, rule, ink, ink-soft, type.heading, type.body, type.meta.
 */
function ChallengeCard({ title, prompt, recordNote, actionLabel, onStart, className, style, ...rest }) {
  return jsxs('div', {
    ...rest,
    'data-cb3-challenge': '',
    className: ['cb3-card cb3-challenge', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: '1rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      ...(style || {})
    },
    children: [
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('heading'),
          lineHeight: cb3Lead('heading'),
          fontWeight: 600,
          maxWidth: '34ch'
        },
        children: title
      }, 'title'),
      prompt
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('body'),
              lineHeight: cb3Lead('body')
            },
            children: prompt
          }, 'prompt')
        : null,
      recordNote
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: recordNote
          }, 'note')
        : null,
      actionLabel
        ? jsx(PillAction, { variant: 'quiet', label: actionLabel, onClick: onStart, style: { alignSelf: 'flex-start' } }, 'action')
        : null
    ]
  })
}

/* ── EvidenceTray ────────────────────────────────────────────────────────────────────────────
 * The evidence surface: a wooden tray object with its lip, the recorded-check tally in `sage`
 * (a fill, never a text background — every word sits on card stock beside it), the real event
 * names, and one refusal/observation sentence in `alert`. A zero state says `No checks recorded
 * yet` instead of painting an empty bar. The tray is interactive: its record toggle is a quiet
 * pill, and the focus ring belongs to that button (`.cb3-press`), never to the tray's own
 * non-focusable `div`.
 * Tokens: card-stock, wood, wood-edge, sage, ink, ink-soft, alert, rule, radius.round.
 */
function EvidenceTray({ countLabel, recorded, emptyLabel, events, note, toggleLabel, onToggle, className, style, ...rest }) {
  const marks = Math.max(0, Math.min(24, Number(recorded) || 0))
  const rows = Array.isArray(events) ? events.filter(Boolean) : []
  const empty = marks === 0 && !countLabel
  return jsxs('div', {
    ...rest,
    'data-cb3-surface': 'evidence',
    'data-cb3-tray-recorded': String(marks),
    className: ['cb3-card cb3-tray', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: '0.75rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      ...(style || {})
    },
    children: [
      jsxs('div', {
        'aria-hidden': 'true',
        style: {
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: '0.2rem',
          minHeight: '12px',
          paddingInline: '0.4rem',
          backgroundImage: cb3ObjectSource('passport-tray') ? `url(${cb3ObjectSource('passport-tray')})` : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundColor: cb3Role('wood'),
          borderBottom: `1px solid ${cb3Role('wood-edge')}`,
          borderRadius: cb3Radius('square')
        },
        children: Array.from({ length: marks }).map((_, index) =>
          jsx('span', {
            style: {
              display: 'block',
              width: '8px',
              height: '8px',
              borderRadius: cb3Radius('square'),
              backgroundColor: cb3Role('sage')
            }
          }, `mark-${index}`)
        )
      }, 'tray'),
      jsx('p', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: cb3Lead('meta'),
          color: cb3Role('ink')
        },
        children: empty ? emptyLabel || '' : countLabel
      }, 'count'),
      rows.length
        ? jsx('ul', {
            style: {
              margin: 0,
              paddingInlineStart: '1rem',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: rows.map((row, index) => jsx('li', { children: row }, `event-${index}`))
          }, 'events')
        : null,
      note
        ? jsx('p', {
            role: 'status',
            'data-cb3-alert': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('alert')
            },
            children: note
          }, 'note')
        : null,
      toggleLabel
        ? jsx(PillAction, { variant: 'quiet', label: toggleLabel, onClick: onToggle, style: { alignSelf: 'flex-start' } }, 'toggle')
        : null
    ]
  })
}

/* ── the component lab ───────────────────────────────────────────────────────────────────────
 * Surface `component.lab` from the contract: ground canvas, every role permitted, interactive,
 * and *never shipped as a screen*. It renders each primitive in each state at the real values,
 * and its own copy says what it is. It carries no filled control (SPEC-V3 §5.5 / §3.10): the
 * anatomy's `Next step` callout is a quiet pill because the specimen is disassembly, not a
 * screen.
 */
const CB3_LAB_COPY = Object.freeze({
  title: 'Design system',
  sub: 'The parts every screen uses, with the values they read.',
  readonly: 'Read-only sheet. Values come from the token contract.',
  back: 'Back',
  sections: Object.freeze({
    fox: 'Fox poses',
    card: 'Card anatomy',
    medals: 'Medallions',
    palette: 'Palette',
    type: 'Type',
    materials: 'Materials'
  }),
  poses: Object.freeze({
    wave: 'Waving',
    point: 'Pointing',
    clock: 'Clock',
    read: 'Reading',
    cheer: 'Cheering',
    think: 'Thinking',
    sleep: 'Sleeping'
  }),
  anatomy: Object.freeze({
    plate: '01 Art plate',
    title: '02 Title',
    subject: '03 Subject',
    evidence: '04 Evidence line',
    next: '05 Next step',
    cover: '06 Cover mark'
  }),
  type: Object.freeze(['caption', 'meta', 'body', 'lead', 'heading', 'display']),
  typeName: Object.freeze({
    caption: 'Caption',
    meta: 'Meta',
    body: 'Body',
    lead: 'Lead',
    heading: 'Heading',
    display: 'Display'
  }),
  typeSample: Object.freeze({
    caption: '4 of 5 checks recorded',
    meta: 'Check answer',
    body: 'A sentence of real lesson text.',
    lead: 'A sentence that opens the lesson.',
    heading: 'Japanese Lantern District',
    display: 'Your field library'
  }),
  materials: Object.freeze({
    grain: 'Paper grain',
    wood: 'Wood ledge',
    elevation: 'Elevation',
    radius: 'Radius'
  }),
  // Specimen content the lab borrows verbatim from the deck (COPY.md). Nothing on the sheet is
  // authored prose: a row's text lives here only so the guard can prove it is the deck's string.
  deck: Object.freeze({
    primary: 'Start a course',                    // home.primary
    continue: 'Continue',                         // course.continue.title
    secondary: 'Browse library',                  // home.secondary
    clearTicks: 'Clear ticks',                    // classroom.check.clear_ticks
    checkPrimary: 'Check answer',                 // classroom.check.primary
    play: 'Play the line',                        // classroom.line.play
    jp: '好きです。付き合ってください。',            // classroom.line.jp
    romaji: 'suki desu. tsukiatte kudasai.',      // classroom.line.romaji
    en: 'I like you. Please go out with me.',     // classroom.line.en
    stepper: 'This section',                      // classroom.stepper.label
    challengeTitle: 'Field Challenge',            // classroom.challenge.title
    challengeStart: 'Try it yourself',            // classroom.challenge.primary
    question: '{check prompt}',                   // classroom.check.question (field template)
    evidenceCount: '2 of 5 checks recorded',      // classroom.evidence.count (2 of 5 recorded)
    evidenceEmpty: 'No checks recorded yet.',     // classroom.evidence.empty
    evidenceFirst: 'First check',                 // lab.medal.first_check
    errorBody: 'Your attempt is unchanged. Try again.', // classroom.error.body
    tryAgain: 'Try again'                         // classroom.error.action
  })
})

/** One section heading on the sheet: an h2 at the heading step, never an eyebrow above it. */
function CbV3LabSection({ id, title, children }) {
  return jsxs('section', {
    'data-cb3-lab-section': id,
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', margin: 0 },
    children: [
      jsx('h2', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('heading'),
          lineHeight: cb3Lead('heading'),
          fontWeight: 600,
          maxWidth: '34ch',
          color: cb3Role('ink')
        },
        children: title
      }, 'heading'),
      children
    ]
  })
}

/** A palette chip: the role's own colour, its contract key, and the computed ratio on paper. */
function CbV3PaletteChip({ role, value, ratio }) {
  return jsxs('div', {
    'data-cb3-chip-role': role,
    style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', width: '80px' },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: {
          width: '64px',
          height: '64px',
          borderRadius: cb3Radius('soft'),
          border: `1px solid ${cb3Role('rule')}`,
          backgroundColor: `var(--cb3-${role})`
        }
      }, 'swatch'),
      jsx('span', {
        style: {
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('caption'),
          lineHeight: cb3Lead('caption'),
          color: cb3Role('ink'),
          overflowWrap: 'anywhere'
        },
        children: role
      }, 'name'),
      jsx('span', {
        'data-cb3-ratio': '',
        style: {
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('caption'),
          lineHeight: cb3Lead('caption'),
          color: cb3Role('ink-soft')
        },
        children: `${ratio}:1`
      }, 'ratio')
    ]
  })
}

/** The whole sheet. `scale` is 1 or 2 so the lab can be captured at 200% text. */
function CbV3LabSheet({ scale, mode, onBack, className, ...rest }) {
  const textScale = Number(scale) === 2 ? 2 : 1
  const theme = mode === 'dark' ? 'dark' : 'light'
  const width = useCbViewportWidth() || 1049
  const palette = (CB_TOKENS_V3.modes && CB_TOKENS_V3.modes[theme]) || {}
  const roles = CB3_V3_ROLES.slice()
  const steps = CB3_LAB_COPY.type
  const rendering = steps.map((step) => ({ step, ...cb3StepRendering(step, width) }))
  return jsxs('div', {
    ...rest,
    'data-cb3-lab': '',
    'data-cb3-surface': 'component.lab',
    'data-cb3-text-scale': String(textScale),
    className: ['cb3-lab', className || ''].filter(Boolean).join(' '),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '2rem',
      padding: '2rem',
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('body'),
      color: cb3Role('ink')
    },
    children: [
      jsxs('header', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
        children: [
          jsx(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.back, icon: 'arrow-left', onClick: onBack }, 'back'),
          jsx('h1', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('display'),
              lineHeight: cb3Lead('display'),
              fontWeight: 600,
              maxWidth: '20ch'
            },
            children: CB3_LAB_COPY.title
          }, 'title'),
          jsx('p', {
            style: {
              margin: 0,
              maxWidth: '60ch',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('body'),
              lineHeight: cb3Lead('body')
            },
            children: CB3_LAB_COPY.sub
          }, 'sub'),
          jsx('p', {
            style: {
              margin: 0,
              maxWidth: '60ch',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: CB3_LAB_COPY.readonly
          }, 'readonly')
        ]
      }, 'head'),
      jsxs('div', {
        // SPEC-V3 §5.5 text-200: at 200% text the sheet collapses to one column and every chip
        // wraps. It is a state of the same sheet (the same DOM), not a second layout: the columns
        // stack and keep their order (left column first).
        style: {
          display: 'flex',
          flexDirection: textScale === 2 ? 'column' : 'row',
          flexWrap: textScale === 2 ? 'nowrap' : 'wrap',
          gap: '2rem',
          alignItems: 'flex-start'
        },
        children: [
          jsxs('div', {
            'data-cb3-lab-column': 'left',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '2rem',
              flex: textScale === 2 ? '1 1 auto' : '1 1 480px',
              width: textScale === 2 ? '100%' : undefined,
              minWidth: 0
            },
            children: [
              jsx(CbV3LabSection, {
                id: 'fox',
                title: CB3_LAB_COPY.sections.fox,
                children: jsx('div', {
                  style: { display: 'flex', flexWrap: 'wrap', gap: '1rem' },
                  children: CB3_POSES.map((pose) =>
                    jsxs('figure', {
                      'data-cb3-specimen': `fox-${pose}`,
                      style: { margin: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' },
                      children: [
                        jsx(FoxPose, { pose, size: 128, style: { marginInlineEnd: 0 } }, 'pose'),
                        jsx('figcaption', {
                          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
                          children: CB3_LAB_COPY.poses[pose]
                        }, 'caption')
                      ]
                    }, pose)
                  )
                })
              }, 'fox'),
              jsx(CbV3LabSection, {
                id: 'card',
                title: CB3_LAB_COPY.sections.card,
                children: jsxs('div', {
                  'data-cb3-specimen': 'card-anatomy',
                  style: { display: 'flex', flexWrap: 'wrap', gap: '1.25rem', alignItems: 'flex-start' },
                  children: [
                    jsx(ShelfPlank, {
                      style: { overflowX: 'visible' },
                      children: jsxs(CollectibleCard, {
                        title: CB3_LAB_COPY.typeSample.heading,
                        subject: 'Language',
                        meta: '2 of 5 sections done',
                        isNew: true,
                        newLabel: 'New',
                        action: jsx(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.deck.continue, onClick: () => {} }, 'next'),
                        style: { width: '214px' }
                      }, 'card')
                    }, 'shelf'),
                    // The second card state: the same object with a real installed artifact in its
                    // cover window. The typographic fallback is the card above (no `src`).
                    jsx(CollectibleCard, {
                      'data-cb3-specimen': 'cover-media',
                      title: CB3_LAB_COPY.typeSample.heading,
                      subject: 'Language',
                      meta: '2 of 5 sections done',
                      src: cb3ObjectSource('passport-tray'),
                      style: { width: '214px' }
                    }, 'cover-media'),
                    jsx('ol', {
                      style: {
                        margin: 0,
                        paddingInlineStart: '1.1rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.25rem',
                        fontFamily: 'var(--cb3-font-ui)',
                        fontSize: cb3Type('caption'),
                        lineHeight: cb3Lead('caption'),
                        color: cb3Role('ink-soft')
                      },
                      children: [
                        CB3_LAB_COPY.anatomy.plate,
                        CB3_LAB_COPY.anatomy.title,
                        CB3_LAB_COPY.anatomy.subject,
                        CB3_LAB_COPY.anatomy.evidence,
                        CB3_LAB_COPY.anatomy.next,
                        CB3_LAB_COPY.anatomy.cover
                      ].map((row, index) => jsx('li', { children: row }, `callout-${index}`))
                    }, 'callouts'),
                    // PaperCard's two states, one per contract rule: `rule` is a 1 px edge and
                    // `elev-1` is a contact shadow, never both. Each card borrows a callout's own
                    // deck name, so no third caption is authored for the sheet.
                    jsx(PaperCard, {
                      emphasis: 'rule',
                      title: CB3_LAB_COPY.anatomy.evidence,
                      meta: CB3_LAB_COPY.anatomy.subject,
                      style: { minWidth: '200px' }
                    }, 'paper-rule'),
                    jsx(PaperCard, {
                      emphasis: 'elev-1',
                      title: CB3_LAB_COPY.anatomy.next,
                      style: { minWidth: '240px' },
                      footer: jsxs('div', {
                        style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' },
                        children: [
                          jsx(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.deck.secondary, onClick: () => {} }, 'quiet'),
                          jsx(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.deck.clearTicks, disabled: true, onClick: () => {} }, 'disabled'),
                          jsx(PillAction, { variant: 'quiet', label: CB3_LAB_COPY.deck.checkPrimary, busy: true, onClick: () => {} }, 'busy')
                        ]
                      })
                    }, 'paper-elev')
                  ]
                })
              }, 'card'),
              jsx(CbV3LabSection, {
                id: 'medals',
                title: CB3_LAB_COPY.sections.medals,
                children: jsx('div', {
                  'data-cb3-specimen': 'medals',
                  style: { display: 'flex', flexWrap: 'wrap', gap: '1rem' },
                  children: Object.keys(CB3_MEDALS).map((event) => jsx(Medallion, { event }, event))
                })
              }, 'medals')
            ]
          }, 'left'),
          jsxs('div', {
            'data-cb3-lab-column': 'right',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '2rem',
              flex: textScale === 2 ? '1 1 auto' : '1 1 280px',
              width: textScale === 2 ? '100%' : undefined,
              minWidth: 0
            },
            children: [
              jsx(CbV3LabSection, {
                id: 'palette',
                title: CB3_LAB_COPY.sections.palette,
                children: jsxs('div', {
                  style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
                  children: [
                    jsx('div', {
                      'data-cb3-specimen': 'palette',
                      style: { display: 'flex', flexWrap: 'wrap', gap: '0.75rem' },
                      children: roles.map((role) =>
                        jsx(CbV3PaletteChip, {
                          role,
                          value: palette[role],
                          ratio: cb3Contrast(palette[role] || palette.canvas, palette.canvas).toFixed(2)
                        }, role)
                      )
                    }, 'chips'),
                    // The primary's fill/label pair as a *swatch*, not a control: the lab carries no
                    // live filled action (SPEC-V3 §3.10 — the lab's documented N/A), and a disabled
                    // pill would look like a broken button rather than a specimen.
                    jsxs('div', {
                      'data-cb3-specimen': 'primary-fill',
                      'aria-hidden': 'true',
                      style: {
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minHeight: '48px',
                        paddingInline: '1.25rem',
                        alignSelf: 'flex-start',
                        borderRadius: cb3Radius('pill'),
                        backgroundColor: cb3Role('terracotta'),
                        color: cb3Role('on-terracotta'),
                        fontFamily: 'var(--cb3-font-ui)',
                        fontSize: cb3Type('meta'),
                        lineHeight: cb3Lead('meta'),
                        fontWeight: 600
                      },
                      children: jsx('span', { children: CB3_LAB_COPY.deck.primary }, 'label')
                    }, 'primary')
                  ]
                })
              }, 'palette'),
              jsx(CbV3LabSection, {
                id: 'type',
                title: CB3_LAB_COPY.sections.type,
                children: jsxs('ol', {
                  'data-cb3-specimen': 'type',
                  style: { margin: 0, paddingInlineStart: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' },
                  children: rendering.map((row) =>
                    jsxs('li', {
                      'data-cb3-type-row': row.step,
                      style: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
                      children: [
                        jsx('span', {
                          style: {
                            fontFamily: 'var(--cb3-font-ui)',
                            fontSize: cb3Type('caption'),
                            lineHeight: cb3Lead('caption'),
                            color: cb3Role('ink-soft')
                          },
                          children: `${CB3_LAB_COPY.typeName[row.step]} · ${row.px}/${row.line}`
                        }, 'label'),
                        jsx('span', {
                          'data-cb3-type-sample': row.step,
                          style: {
                            fontFamily: row.step === 'heading' || row.step === 'display' ? 'var(--cb3-font-display)' : 'var(--cb3-font-ui)',
                            fontSize: cb3Type(row.step),
                            lineHeight: cb3Lead(row.step),
                            fontWeight: row.step === 'body' ? 400 : 600,
                            color: cb3Role('ink'),
                            overflowWrap: 'anywhere'
                          },
                          children: CB3_LAB_COPY.typeSample[row.step]
                        }, 'sample')
                      ]
                    }, row.step)
                  )
                })
              }, 'type'),
              jsx(CbV3LabSection, {
                id: 'materials',
                title: CB3_LAB_COPY.sections.materials,
                children: jsxs('div', {
                  'data-cb3-specimen': 'materials',
                  style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
                  children: [
                    jsx('figure', {
                      style: { margin: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' },
                      children: [
                        jsx('div', {
                          style: {
                            height: '48px',
                            borderRadius: cb3Radius('soft'),
                            border: `1px solid ${cb3Role('rule')}`,
                            backgroundColor: cb3Role('canvas-edge'),
                            backgroundImage: cb3Asset('cb.asset.material.grain-paper') ? `url(${cb3Asset('cb.asset.material.grain-paper')})` : undefined,
                            backgroundRepeat: 'repeat'
                          },
                          'aria-hidden': 'true'
                        }, 'tile'),
                        jsx('figcaption', {
                          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
                          children: CB3_LAB_COPY.materials.grain
                        }, 'caption')
                      ]
                    }, 'grain'),
                    jsx('figure', {
                      style: { margin: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' },
                      children: [
                        jsx('div', {
                          style: {
                            height: '24px',
                            width: '100%',
                            backgroundColor: cb3Role('wood'),
                            backgroundImage: cb3ObjectSource('shelf-plank') ? `url(${cb3ObjectSource('shelf-plank')})` : undefined,
                            backgroundRepeat: 'repeat-x',
                            backgroundSize: 'auto 100%',
                            borderBottom: `1px solid ${cb3Role('wood-edge')}`
                          },
                          'aria-hidden': 'true'
                        }, 'tile'),
                        jsx('figcaption', {
                          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
                          children: CB3_LAB_COPY.materials.wood
                        }, 'caption')
                      ]
                    }, 'wood'),
                    jsx('div', {
                      style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
                      children: [
                        jsx('div', {
                          style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' },
                          children: ['elev-1', 'elev-2', 'inset-1'].map((level) =>
                            jsx('span', {
                              'data-cb3-elevation': level,
                              className: level === 'elev-1' ? 'cb3-card-elevated' : level === 'elev-2' ? 'cb3-elev-2' : 'cb3-elev-inset',
                              style: {
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '80px',
                                height: '40px',
                                borderRadius: cb3Radius('soft'),
                                backgroundColor: cb3Role('card-stock'),
                                fontFamily: 'var(--cb3-font-ui)',
                                fontSize: cb3Type('caption'),
                                color: cb3Role('ink-soft')
                              },
                              children: level
                            }, level)
                          )
                        }, 'levels'),
                        jsx('span', {
                          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
                          children: CB3_LAB_COPY.materials.elevation
                        }, 'caption')
                      ]
                    }, 'elevations'),
                    jsx('div', {
                      style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
                      children: [
                        jsx('div', {
                          style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' },
                          children: ['square', 'soft', 'round', 'pill'].map((radius) =>
                            jsx('span', {
                              'data-cb3-radius': radius,
                              style: {
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '64px',
                                height: '40px',
                                borderRadius: cb3Radius(radius),
                                border: `1px solid ${cb3Role('rule')}`,
                                fontFamily: 'var(--cb3-font-ui)',
                                fontSize: cb3Type('caption'),
                                color: cb3Role('ink-soft')
                              },
                              children: radius
                            }, radius)
                          )
                        }, 'radii'),
                        jsx('span', {
                          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
                          children: CB3_LAB_COPY.materials.radius
                        }, 'caption')
                      ]
                    }, 'radius-row')
                  ]
                })
              }, 'materials')
            ]
          }, 'right')
        ]
      }, 'columns'),
      // The parts the R-SYS sheet does not name: a stepper, the dialogue, the challenge and the
      // evidence tray. SPEC-V3 §5.5 defines six sections and the deck has no id for a seventh
      // group, so the band carries **no authored heading** — its group name is the sheet's own
      // `lab.sub` line and each part is identified by the deck text it renders.
      jsxs('div', {
        'data-cb3-specimen': 'parts',
        role: 'group',
        'aria-label': CB3_LAB_COPY.sub,
        style: { display: 'flex', flexWrap: 'wrap', gap: '1.25rem', alignItems: 'flex-start' },
        children: [
          jsx('div', {
            'data-cb3-specimen': 'stamps',
            style: { display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-start' },
            children: CB3_STAMP_STATES.map((state, index) =>
              jsx(StampNode, {
                state,
                index: index + 1,
                label: CB3_LAB_COPY.deck.stepper,
                onClick: () => {}
              }, state)
            )
          }, 'stamps'),
          jsx(DialogueBubble, {
            segments: [
              { text: '好', ruby: 'す' },
              { text: 'きです。' },
              { text: '付', ruby: 'つ' },
              { text: 'き', ruby: 'あ' },
              { text: 'ってください。' }
            ],
            romaji: CB3_LAB_COPY.deck.romaji,
            en: CB3_LAB_COPY.deck.en,
            playLabel: CB3_LAB_COPY.deck.play,
            onPlay: () => {}
          }, 'bubble'),
          jsx(ChallengeCard, {
            title: CB3_LAB_COPY.deck.challengeTitle,
            prompt: CB3_LAB_COPY.deck.question,
            actionLabel: CB3_LAB_COPY.deck.challengeStart,
            onStart: () => {}
          }, 'challenge'),
          jsx(EvidenceTray, {
            countLabel: CB3_LAB_COPY.deck.evidenceCount,
            recorded: 2,
            events: [CB3_LAB_COPY.deck.evidenceFirst],
            toggleLabel: CB3_LAB_COPY.deck.tryAgain
          }, 'tray'),
          jsx(EvidenceTray, {
            recorded: 0,
            emptyLabel: CB3_LAB_COPY.deck.evidenceEmpty,
            events: [],
            note: CB3_LAB_COPY.deck.errorBody,
            toggleLabel: CB3_LAB_COPY.deck.tryAgain
          }, 'tray-empty')
        ]
      }, 'parts'),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
        children: [
          jsx(ForestBand, { value: 'home', onChange: () => {} }, 'band'),
          jsx('div', {
            style: { display: 'flex', gap: '0', alignItems: 'stretch', minHeight: '220px', border: `1px solid ${cb3Role('rule')}` },
            children: [
              jsx(ForestRail, { value: 'home', onChange: () => {} }, 'rail'),
              jsx('div', {
                style: {
                  flex: '1 1 auto',
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: 'flex-end',
                  padding: '1rem',
                  backgroundColor: cb3Role('canvas')
                },
                children: jsx(FoxPose, { pose: 'clock', size: 128 }, 'rail-fox')
              }, 'rail-body')
            ]
          }, 'rail-frame')
        ]
      }, 'navigation')
    ]
  })
}

// CB-V3-END
