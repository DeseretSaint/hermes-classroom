/** Small enough to draw one segment per objective without turning the row into a texture. */
const CB_COURSE_PATH_MAX = 12

/** The placeholder bar: how many unpainted parts stand in when there is no readable count. */
const CB_COURSE_PATH_PARTS = 4

/**
 * The evidence record on a cover. Segments are objectives, not quarters: `done` only where the
 * count of independent evidence actually reaches, `due` only for the objectives due for review,
 * and `quiet` everywhere else. A zero-evidence course paints nothing: the old `current` segment
 * made 0 of 4 look 25 % complete. A course too large to draw honestly carries the count only.
 */
function cbCoursePathSegments(row) {
  const summary = (row && row.evidence_summary) || {}
  const rawTotal = Number(summary.total_objectives)
  // A count this projection cannot read (a hostile or truncated summary) is not zero evidence:
  // it is no answer. Every part is `empty` so nothing is painted as reached (H-155 ENG-D1).
  if (!Number.isFinite(rawTotal)) {
    const empty = []
    for (let index = 0; index < CB_COURSE_PATH_PARTS; index += 1) empty.push({ index, state: 'empty' })
    return empty
  }
  const total = Math.max(0, Math.floor(rawTotal))
  if (total === 0 || total > CB_COURSE_PATH_MAX) return []
  const independent = Math.max(0, Math.min(total, Number(summary.independent) || 0))
  const due = Math.max(0, Math.min(total - independent, Number(summary.review_due) || 0))
  const segments = []
  for (let index = 0; index < total; index += 1) {
    let state = 'quiet'
    if (index < independent) state = 'done'
    else if (index < independent + due) state = 'due'
    segments.push({ index, state })
  }
  return segments
}

/** The exact counts under the path. Never a percentage, never a score, never a fake quarter. */
function cbCoursePathCaption(row) {
  const summary = (row && row.evidence_summary) || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  // H-155: the caption is a count or it says there is no count. "No evidence yet" replaced a real
  // "0 of 4 with evidence" with a slogan, and a learner cannot tell the two apart from it.
  if (total === 0 || !Number.isFinite(total)) return 'No sections yet'
  const independent = Math.max(0, Math.min(total, Number(summary.independent || 0)))
  const due = Math.max(0, Number(summary.review_due || 0))
  const parts = [`${independent} of ${total} with evidence`]
  if (due > 0) parts.push(`${due} due`)
  return parts.join(' · ')
}

/**
 * The one line under the title. The shelf row carries no plan goal, so this is the goal the
 * backend stored when it has one, the course's own subtitle, and otherwise the recorded next
 * step. It never invents a goal to make a card look fuller.
 */
function cbCourseGoalLine(row) {
  const goal = row && typeof row.goal === 'string' ? row.goal.trim() : ''
  if (goal) return goal
  const subtitle = row && typeof row.subtitle === 'string' ? row.subtitle.trim() : ''
  if (subtitle) return subtitle
  const label = learnerNextLabel(row && row.next_step && row.next_step.label)
  if (label) return label
  return 'No next step recorded'
}

/**
 * The backend's next-step label is plain English except for its `objective(s)` placeholder. The
 * shelf shows the sentence the learner acts on, so the placeholder is resolved here; the backend
 * keeps its contract string untouched.
 */
function learnerNextLabel(label) {
  const text = String(label || '').trim()
  if (!text) return ''
  const match = text.match(/^Review (\d+) objective\(s\)$/)
  if (match) return `Review ${plural(Number(match[1]), 'objective', 'objectives')}`
  return text.replace(/\bobjective\(s\)/g, 'objectives').replace(/\brun\(s\)/g, 'runs')
}

/**
 * H-145 — the course seal was retired from every surface it appeared on. The owner asked twice
 * what it meant; a mark that needs an explanation is not identity. `cbSealStation` stays exported
 * because the visual-identity probes address it, but nothing in the route renders an SVG seal.
 */

/** Segment kinds are internal enums; the learner sees a plain word. */
const CB_SEGMENT_WORD = {
  teaching: 'Teaching',
  practice: 'Practice',
  example: 'Worked example',
  recap: 'Recap',
  orientation: 'Getting started',
  check_prompt: 'Check',
  media: 'Media',
  audio: 'Audio',
  visual: 'Image'
}

function cbSegmentWord(kind) {
  if (!kind) return ''
  const known = CB_SEGMENT_WORD[kind]
  if (known) return known
  const text = String(kind).replaceAll('_', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** A section label in sentence case: no eyebrow, no all-caps, 0.75rem floor. */
function CbLabel({ children }) {
  return jsx('div', {
    style: {
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      letterSpacing: '0.01em',
      color: 'var(--cb-ink-soft)'
    },
    children
  })
}

/** One plate head: a display title, an optional label and one honest caption. */
function PlateHead({ id, label, title, caption, actions, level }) {
  const heading = level === 3 ? 'h3' : 'h2'
  return jsxs('div', {
    'data-cb-plate-head': '',
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: '0.5rem 1rem',
      paddingBottom: '0.5rem',
      borderBottom: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
        children: [
          label
            ? jsx('div', {
                style: {
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600,
                  letterSpacing: '0.01em',
                  color: 'var(--cb-ink-soft)'
                },
                children: label
              })
            : null,
          jsx(heading, {
            id,
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.2,
              letterSpacing: '-0.01em',
              color: 'var(--cb-ink)',
              maxWidth: '34ch'
            },
            children: title
          }),
          caption
            ? jsx('p', {
                style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.body, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
                children: caption
              })
            : null
        ]
      }),
      actions ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }, children: actions }) : null
    ]
  })
}

/** Five states, five shapes: the spine is never the only carrier of the state word. */
function cbSpineTone(state) {
  if (state === 'independent_evidence' || state === 'delayed_evidence') return 'done'
  if (state === 'review_due' || state === 'overridden') return 'due'
  if (state === 'needs_review') return 'attention'
  if (state === 'introduced') return 'active'
  return 'quiet'
}

function cbSpineNodeStyle(tone, isCurrent, phone) {
  const size = phone ? '1.5rem' : '1.75rem'
  const base = {
    flex: `0 0 ${size}`,
    width: size,
    height: size,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: CB_SANS,
    fontVariantNumeric: 'tabular-nums',
    fontSize: CB_TYPE.caption,
    fontWeight: 600,
    lineHeight: 1,
    boxSizing: 'border-box'
  }
  if (tone === 'done') return { ...base, background: 'var(--cb-field)', color: 'var(--cb-paper)', border: 'none' }
  if (tone === 'due') return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ochre)', border: '2px solid var(--cb-ochre)' }
  if (tone === 'attention') return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-coral)', border: '2px solid var(--cb-coral)' }
  if (tone === 'active') return { ...base, background: 'var(--cb-accent-soft)', color: 'var(--cb-accent)', border: '2px solid var(--cb-accent)' }
  return { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ink-soft)', border: '1.5px solid var(--cb-rule)' }
}

/** The route: a surveyed spine with numbered nodes and a state word beside every node. */
function RouteSpine({ objectives, currentId, onSelect, phone, ariaLabel }) {
  const rows = objectives || []
  const nodeSize = phone ? '1.5rem' : '1.75rem'
  const left = phone ? '0.6875rem' : '0.8125rem'
  return jsx('ol', {
    'aria-label': ariaLabel || 'Course route',
    style: {
      listStyle: 'none',
      margin: 0,
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      position: 'relative'
    },
    children: rows.map((objective) => {
      const tone = cbSpineTone(objective.state)
      const isCurrent = Boolean(currentId && objective.objective_id === currentId)
      const word = DESK_STATE_WORD[objective.state] || 'Not started'
      return jsx(
        'li',
        {
          style: { position: 'relative', display: 'flex', flexDirection: 'column' },
          children: jsx(sdk.Button, {
            variant: 'text',
            className: 'w-full justify-start',
            'aria-current': isCurrent ? 'step' : undefined,
            onClick: onSelect ? () => onSelect(objective.objective_id) : undefined,
            children: jsxs('span', {
              'data-cb-path-item': objective.objective_id,
              'data-cb-path-state': objective.state,
              'data-cb-path-current': isCurrent ? 'true' : 'false',
              style: {
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                width: '100%',
                padding: isCurrent ? '0.55rem 0.4rem 0.55rem 0.1rem' : '0.45rem 0.1rem',
                margin: isCurrent ? '0 -0.4rem 0 -0.4rem' : 0,
                boxSizing: 'border-box',
                textAlign: 'left',
                color: 'var(--cb-ink)',
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.meta,
                borderTop: '1px solid var(--cb-rule)',
                background: isCurrent ? 'var(--cb-accent-soft)' : 'transparent',
                borderLeft: isCurrent ? '2px solid var(--cb-accent)' : '2px solid transparent'
              },
              children: [
                jsx('span', {
                  'aria-hidden': 'true',
                  style: {
                    position: 'absolute',
                    left: left,
                    top: 0,
                    bottom: 0,
                    width: '1px',
                    background: 'var(--cb-rule)'
                  }
                }, 'line'),
                jsx('span', {
                  style: cbSpineNodeStyle(tone, isCurrent, phone),
                  children: String(objective.ordinal).padStart(2, '0')
                }),
                jsx('span', {
                  style: {
                    flex: '1 1 8rem',
                    minWidth: 0,
                    overflowWrap: 'anywhere',
                    whiteSpace: 'normal',
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.body,
                    fontWeight: 600,
                    lineHeight: 1.3
                  },
                  children: objective.title
                }),
                jsx('span', {
                  style: {
                    flex: '0 0 auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    fontFamily: CB_SANS,
                    fontSize: CB_TYPE.caption,
                    fontWeight: 600,
                    color: deskToneColor(tone),
                    border: `1px solid ${deskToneColor(tone)}`,
                    borderRadius: '999px',
                    padding: '0.1rem 0.5rem',
                    whiteSpace: 'nowrap'
                  },
                  children: word
                })
              ]
            })
          })
        },
        objective.objective_id
      )
    })
  })
}

/** The honest record: one tick per objective, never a bar, a ring or a percentage. */
function EvidenceTally({ objectives, caption, phone }) {
  const rows = (objectives || []).slice(0, 12)
  return jsxs('div', {
    'data-cb-tally': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
    children: [
      rows.length
        ? jsx('div', {
            'aria-hidden': 'true',
            style: { display: 'flex', flexWrap: 'wrap', gap: '4px' },
            children: rows.map((objective, index) => {
              const tone = cbSpineTone(objective.state)
              const paint =
                tone === 'done'
                  ? 'var(--cb-field)'
                  : tone === 'due'
                    ? 'var(--cb-ochre)'
                    : tone === 'attention'
                      ? 'var(--cb-coral)'
                      : tone === 'active'
                        ? 'var(--cb-accent)'
                        : 'var(--cb-rule)'
              return jsx('span', {
                style: { width: phone ? '18px' : '22px', height: '6px', borderRadius: 0, background: paint }
              }, `${objective.objective_id}-${index}`)
            })
          })
        : null,
      jsx('p', {
        'data-cb-tally-caption': '',
        style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
        children: caption
      })
    ]
  })
}

/** The lit page: one flat field of light behind the thing that matters now. */
function HeroField({ identity, children, phone }) {
  const parent = identity === 'plum'
  return jsx('section', {
    'data-cb-hero': parent ? 'plum' : 'lamp',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.65rem',
      padding: phone ? '0.9rem 0.95rem' : '1.1rem 1.2rem 1.15rem',
      background: parent ? 'var(--cb-plum-soft)' : 'var(--cb-lamp-soft)',
      borderTop: `1px solid ${parent ? 'var(--cb-plum)' : 'var(--cb-lamp)'}`,
      maxWidth: '100%',
      boxSizing: 'border-box'
    },
    children
  })
}

/** A mode hue is a 3px dot plus the mode word, never a coloured block. */
function ModeDot({ mode }) {
  const paint =
    mode === 'guided'
      ? 'var(--cb-field)'
      : mode === 'field_quest'
        ? 'var(--cb-ochre)'
        : mode === 'game'
          ? 'var(--cb-lamp)'
          : 'var(--cb-accent)'
  return jsx('span', {
    'aria-hidden': 'true',
    style: { display: 'inline-block', width: '3px', height: '3px', minWidth: '3px', borderRadius: '50%', background: paint, verticalAlign: 'middle' }
  })
}

/** Which hue a surface owns: Textbook `accent`, Guided `field`, Game `lamp`, Field Quest `ochre`. */
function cbModeFor(view) {
  if (view === 'guided') return 'guided'
  if (view === 'field_quest') return 'field_quest'
  if (view === 'player') return 'game'
  return 'textbook'
}

/**
 * Coursebook's one action primitive (H-151). `sdk.Button` supplies behaviour, focus and disabled
 * semantics; this table supplies the Coursebook control language so a route never inherits the
 * host's settings-page button (the default fill is the host accent, which is not a Coursebook
 * colour). Four variants and no fifth: `primary` is the single lamp field a screen is allowed,
 * `secondary` is a peer action beside it, `tertiary` is a text action inside prose or a meta line,
 * and `row` is a full-width list-row action that keeps its own 44px target.
 *
 * Targets: primary and secondary are 44px, row is 44px, tertiary is 24px. Type: body on the two
 * filled variants and the row, meta on the text action, so a route never gains a seventh size.
 */
const CB_ACTION_VARIANTS = Object.freeze(['primary', 'secondary', 'tertiary', 'row'])

const CB_ACTION_STYLES = {
  primary: {
    variant: 'default',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: undefined,
    style: {
      background: 'var(--cb-lamp)',
      color: 'var(--cb-on-lamp)',
      border: '1px solid var(--cb-on-lamp)',
      borderRadius: '2px',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  secondary: {
    variant: 'secondary',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: undefined,
    style: {
      background: 'var(--cb-paper)',
      color: 'var(--cb-ink)',
      border: '1px solid var(--cb-ink)',
      borderRadius: '2px',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  tertiary: {
    variant: 'text',
    minHeight: '24px',
    fontSize: CB_TYPE.meta,
    className: undefined,
    style: {
      background: 'transparent',
      color: 'var(--cb-ink)',
      border: 'none',
      borderRadius: 0,
      padding: '0.15rem 0',
      fontFamily: CB_SANS,
      fontWeight: 600
    }
  },
  row: {
    variant: 'text',
    minHeight: '44px',
    fontSize: CB_TYPE.body,
    className: 'w-full justify-start',
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'flex-start',
      textAlign: 'left',
      background: 'transparent',
      color: 'var(--cb-ink)',
      border: 'none',
      borderRadius: 0,
      padding: '0.35rem 0',
      fontFamily: CB_SANS,
      fontWeight: 500
    }
  }
}

/**
 * One wrapper around `sdk.Button`, so every migrated call site speaks the same control language.
 * The host `size` prop is accepted and dropped: the Coursebook variant owns the target and the
 * type step, so a caller cannot accidentally shrink a primary below 44px. A disabled primary
 * keeps the fill honest: it drops to paper and soft ink rather than pretending it is still live.
 *
 * `data-cb-state` is the primitive's own eight-state vocabulary, reduced to the five this control
 * can actually be in: rest, pressed, selected, disabled, pending. The press beat is one 100 ms
 * translate (docs/CRAFT-CHANNELS-RESEARCH.md §5): transform only, so it cannot move the layout or
 * the focus ring, and pointer-up/blur always return it to rest even if the pointer leaves.
 */
function CbAction({ variant, state, className, style, disabled, pending, children, ...rest }) {
  // The Coursebook variant owns the target and the type step; a caller's host `size` cannot
  // shrink a primary below 44px.
  delete rest.size
  const motion = useCbMotion()
  const [pressed, setPressed] = useState(false)
  // README §1 rule 6: a keyboard focus target paints the 2px accent ring. The SDK's own ring is
  // reset by the host, so the plugin authors it; a pointer click does not raise it.
  const [keyboardFocus, setKeyboardFocus] = useState(false)
  // A pointer press focuses the control without meaning "keyboard focus". Set here so the ring is
  // authored from intent, not from a `:focus-visible` selector the test DOM cannot resolve.
  const pointerFocus = useRef(false)
  const kind = Object.prototype.hasOwnProperty.call(CB_ACTION_STYLES, variant) ? variant : 'secondary'
  const spec = CB_ACTION_STYLES[kind]
  const isDisabled = Boolean(disabled)
  const palette = isDisabled && kind === 'primary'
    ? { background: 'var(--cb-paper)', color: 'var(--cb-ink-soft)', border: '1px solid var(--cb-rule)' }
    : null
  const cbState = state
    || (isDisabled ? 'disabled' : pending ? 'pending' : pressed ? 'pressed' : 'rest')
  const pressStyle = isDisabled || pending
    ? null
    : {
        transform: pressed ? 'translateY(1px)' : 'none',
        transition: motion.transition('transform, border-color', 'press') || 'none'
      }
  const release = () => setPressed(false)
  const call = (name, event) => {
    const handler = rest[name]
    if (typeof handler === 'function') handler(event)
  }
  return jsx(sdk.Button, {
    ...rest,
    'data-cb-action': kind,
    'data-cb-state': cbState,
    'data-cb-focus-ring': keyboardFocus ? 'visible' : 'none',
    disabled: isDisabled,
    variant: spec.variant,
    className: [spec.className, className].filter(Boolean).join(' ') || undefined,
    onPointerDown: (event) => {
      pointerFocus.current = true
      if (!isDisabled) setPressed(true)
      call('onPointerDown', event)
    },
    onPointerUp: (event) => {
      release()
      call('onPointerUp', event)
    },
    onPointerLeave: (event) => {
      release()
      call('onPointerLeave', event)
    },
    onPointerCancel: (event) => {
      release()
      call('onPointerCancel', event)
    },
    onFocus: (event) => {
      setKeyboardFocus(!pointerFocus.current || shelfRingVisible(event && event.currentTarget))
      call('onFocus', event)
    },
    onBlur: (event) => {
      pointerFocus.current = false
      setKeyboardFocus(false)
      release()
      call('onBlur', event)
    },
    style: {
      ...spec.style,
      ...(style || {}),
      ...(palette || {}),
      ...(pressStyle || {}),
      minHeight: spec.minHeight,
      fontSize: spec.fontSize,
      // Longhands rather than the `outline` shorthand: a computed-style reader (and the host's
      // own reset) sees the authored ring either way, and jsdom only exposes the longhands. At
      // rest the style is omitted, so a host UA ring is never suppressed by an inline `none`.
      ...(keyboardFocus ? {
        outlineStyle: 'solid',
        outlineWidth: '2px',
        outlineColor: 'var(--cb-accent)',
        outlineOffset: '2px'
      } : {})
    },
    children
  })
}

/**
 * The state word with its hue. The pill is always text; colour is the second channel, never the
 * only one (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §2.3, §6.3).
 */
function CbStatePill({ state, label, phone }) {
  const tone = cbSpineTone(state)
  const word = label || DESK_STATE_WORD[state] || 'Not started'
  return jsx('span', {
    'data-cb-state-pill': state || 'not_started',
    'data-cb-state-tone': tone,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      lineHeight: 1.3,
      color: deskToneColor(tone),
      border: `1px solid ${deskToneColor(tone)}`,
      borderRadius: '999px',
      padding: '0.15rem 0.55rem',
      whiteSpace: 'nowrap'
    },
    children: word
  })
}

/**
 * The recorded facts of a course, as one calm line rather than a metric block: the number and its
 * caption sit in reading order, separated by a rule. Only facts the backend read produced appear.
 */
function HeroFacts({ facts, phone }) {
  const rows = (facts || []).filter(Boolean)
  if (rows.length === 0) return null
  return jsx('div', {
    'data-cb-hero-facts': String(rows.length),
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: phone ? '0.25rem 0.6rem' : '0.25rem 0.9rem', minWidth: 0 },
    children: rows.map((fact, index) =>
      jsxs('span', {
        'data-cb-hero-fact': fact.label,
        style: { display: 'inline-flex', alignItems: 'baseline', gap: '0.3rem', minWidth: 0 },
        children: [
          index > 0
            ? jsx('span', { 'aria-hidden': 'true', style: { color: 'var(--cb-ink-soft)' }, children: '·' })
            : null,
          jsx('span', {
            style: {
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.body,
              fontWeight: 600,
              lineHeight: 1.4,
              color: 'var(--cb-ink)',
              overflowWrap: 'anywhere'
            },
            children: fact.value
          }),
          jsx('span', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
            children: fact.label
          })
        ]
      }, fact.label)
    )
  })
}

/**
 * Tier-one navigation for a course: a plain tab row with the mode dot on the reading surfaces and
 * a 2px underline on the current one. It never hides a surface behind a select.
 */
function LearningTabs({ options, value, onChange, phone, ariaLabel }) {
  const list = (options || []).filter(Boolean)
  // The row is one tab stop with a roving tabindex, so the arrow keys must work and the focused
  // tab must show a ring of its own (the host resets the UA outline). Left/Right wrap, Home/End
  // jump; the focused tab moves with the selection instead of being left behind.
  const [focusId, setFocusId] = useState(null)
  const onKeyDown = (event) => {
    const keys = ['ArrowRight', 'ArrowLeft', 'Home', 'End']
    if (!keys.includes(event.key)) return
    const index = list.findIndex((option) => option.id === value)
    const nextIndex =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? list.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length
    const next = list[nextIndex]
    if (!next) return
    event.preventDefault()
    setFocusId(next.id)
    onChange(next.id)
    const node = event.currentTarget.querySelector(`[data-cb-tab="${next.id}"]`)
    if (node && typeof node.focus === 'function') node.focus()
  }
  return jsx('nav', {
    'aria-label': ariaLabel || 'Course surfaces',
    'data-cb-learning-tabs': value,
    role: 'tablist',
    onKeyDown,
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'stretch',
      gap: phone ? '0.15rem 0.5rem' : '0.15rem 1.1rem',
      borderBottom: '1px solid var(--cb-rule)',
      minWidth: 0
    },
    children: list.map((option) => {
      const current = option.id === value
      const mode = option.mode ? cbModeFor(option.id) : null
      return jsx(
        sdk.Button,
        {
          variant: 'text',
          role: 'tab',
          'aria-selected': current ? 'true' : 'false',
          'data-cb-tab': option.id,
          'data-cb-tab-focus': focusId === option.id ? 'ring' : 'idle',
          tabIndex: current ? 0 : -1,
          className: '!h-auto !px-0 !py-0',
          onClick: () => onChange(option.id),
          onFocus: () => setFocusId(option.id),
          onBlur: () => setFocusId((id) => (id === option.id ? null : id)),
          style: {
            outline: focusId === option.id ? '2px solid var(--cb-accent)' : 'none',
            outlineOffset: '2px',
            borderRadius: '2px'
          },
          children: jsx('span', {
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: phone ? '0.7rem 0' : '0.45rem 0 0.4rem',
              borderBottom: current ? '2px solid var(--cb-accent)' : '2px solid transparent',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.meta,
              fontWeight: current ? 600 : 400,
              color: current ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
              whiteSpace: 'nowrap'
            },
            children: [mode ? jsx(ModeDot, { mode }) : null, option.label]
          })
        },
        option.id
      )
    })
  })
}

/**
 * The check / notice panel: `lamp-soft` with a 2px `lamp` top edge for a pending state, or a 1px
 * `coral` left edge for a retry. It is a field, not a card, and it never carries a red fill.
 */
function CheckPanelFrame({ kind, label, children }) {
  const retry = kind === 'retry'
  const pending = kind === 'pending'
  return jsxs('section', {
    'data-cb-check-panel': kind || 'check',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: retry ? '0.75rem 0.9rem 0.8rem 1rem' : '0.9rem 1rem 0.95rem',
      background: retry ? 'var(--cb-paper)' : pending ? 'var(--cb-lamp-soft)' : 'var(--cb-paper-raised)',
      borderTop: pending ? '1px solid var(--cb-lamp)' : 'none',
      borderLeft: retry ? '1px solid var(--cb-coral)' : 'none',
      maxWidth: CB_MEASURE,
      boxSizing: 'border-box'
    },
    children: [
      label
        ? jsx('div', {
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              lineHeight: 1.3,
              color: retry ? 'var(--cb-coral)' : 'var(--cb-ochre)'
            },
            children: label
          })
        : null,
      children
    ]
  })
}

function CbRailSection({ label, children }) {
  return jsxs('section', {
    'data-cb-rail-section': label,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      paddingTop: '0.6rem',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsx('div', {
        style: {
          fontSize: CB_TYPE.caption,
          fontWeight: 600,
          letterSpacing: '0.01em',
          color: 'var(--cb-ink-soft)'
        },
        children: label
      }),
      children
    ]
  })
}

/**
 * The Field rail: next action, the section's own facts, source cards and saved notes. It is the
 * third part of the workspace and becomes a bottom sheet (a stacked section) below 1024px.
 */
function FieldRail({ next, facts, sources, notes }) {
  const sourceRows = (sources || []).slice(0, 4)
  const noteRows = (notes || []).slice(0, 3)
  return jsxs('aside', {
    'data-cb-field-rail': '',
    'aria-label': 'Section details',
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: CB_TYPE.meta, lineHeight: 1.5 },
    children: [
      jsx(CbRailSection, {
        label: 'Next action',
        children: jsx('div', {
          'data-cb-next-action': '',
          style: { color: 'var(--cb-ink)', fontWeight: 500 },
          children: next || 'No next action was recorded for this section.'
        })
      }),
      facts && facts.length
        ? jsx(CbRailSection, {
            label: 'This section',
            children: jsx('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', color: 'var(--cb-ink-soft)' },
              children: facts.map((fact) =>
                jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }, children: [
                  jsx('span', { children: fact.label }),
                  jsx('span', { style: { color: 'var(--cb-ink)', textAlign: 'right' }, children: fact.value })
                ]}, fact.label)
              )
            })
          })
        : null,
      jsx(CbRailSection, {
        label: 'Source cards',
        children: sourceRows.length
          ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' }, children: sourceRows.map((source) =>
              jsxs('div', {
                'data-cb-source-card': source.source_id || '',
                style: { display: 'flex', flexDirection: 'column', gap: '0.05rem', borderLeft: '2px solid var(--cb-rule)', paddingLeft: '0.45rem' },
                children: [
                  jsx('span', { style: { color: 'var(--cb-ink)' }, children: source.title || 'Untitled source' }),
                  jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
                ]
              }, source.source_id || source.title)
            ) })
          : jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: 'No sources are recorded for this course yet.' })
      }),
      jsx(CbRailSection, {
        label: 'Saved notes',
        children: noteRows.length
          ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', color: 'var(--cb-ink-soft)' }, children: noteRows.map((entry) =>
              jsx('div', { 'data-cb-rail-note': entry.entry_id || '', children: entry.excerpt || entry.note || entry.kind }, entry.entry_id || entry.excerpt)
            ) })
          : jsx('div', { style: { color: 'var(--cb-ink-soft)' }, children: 'Nothing saved from this section yet.' })
      })
    ]
  })
}

/**
 * The three-part lesson workspace: header, reading column, field rail. Layout is computed from the
 * live viewport width rather than a media query, because a runtime plugin cannot ship a stylesheet;
 * the rail stacks under the reading column at 460px instead of shrinking the text.
 */
function WorkspaceShell({ eyebrow, title, subtitle, meta, actions, rail, header = true, tutorSelection = null, children }) {
  const width = useCbViewportWidth()
  const layout = cbLayoutFor(width)
  const wide = cbIsWide(layout)
  return jsxs('div', {
    'data-cb-workspace-shell': wide ? 'wide' : 'stacked',
    style: { display: 'flex', flexDirection: 'column', gap: '0.85rem', minHeight: 0 },
    children: [
      header
        ? jsxs('header', {
        'data-cb-workspace-header': '',
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: '0.5rem',
          paddingBottom: '0.5rem',
          borderBottom: '1px solid var(--cb-rule)'
        },
        children: [
          jsxs('div', {
            style: { minWidth: 0, display: 'flex', flexDirection: 'column', gap: '0.15rem' },
            children: [
              jsx('h2', {
                'data-cb-workspace-title': '',
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--cb-ink)'
                },
                children: title
              }),
              subtitle
                ? jsx('div', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' }, children: subtitle })
                : null
            ]
          }),
          actions
            ? jsx('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: '0.35rem' },
                children: actions
              })
            : null
        ]
      })
        : null,
      !header && actions
        ? jsx('div', {
            'data-cb-workspace-actions': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: '0.35rem' },
            children: actions
          })
        : null,
      header && meta && meta.length
        ? jsx('div', {
            'data-cb-route-meta': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: meta
          })
        : null,
      jsxs('div', {
        'data-cb-workspace-body': '',
        style: wide
          ? { display: 'grid', gridTemplateColumns: `minmax(0, 1fr) ${CB_RAIL_WIDTH}`, alignItems: 'start', gap: '1.25rem' }
          : { display: 'flex', flexDirection: 'column', gap: '1rem' },
        children: [
          jsx('div', {
            'data-cb-reading-column': '',
            // The host chrome sets `user-select: none` on the session surface; the lesson prose is
            // the one place a learner must be able to select a word deliberately (tutor pill).
            style: { minWidth: 0, maxWidth: wide ? CB_MEASURE : '100%', userSelect: 'text', WebkitUserSelect: 'text' },
            children: [
              tutorSelection ? jsx(TutorSelectionPill, { context: tutorSelection }) : null,
              children
            ]
          }),
          rail
            ? jsx('div', {
                'data-cb-rail-slot': wide ? 'side' : 'bottom',
                style: wide ? { minWidth: 0 } : { minWidth: 0, borderTop: '1px solid var(--cb-rule)', paddingTop: '0.75rem' },
                children: rail
              })
            : null
        ]
      })
    ]
  })
}

/**
 * A field-note frame: thin rule, the media itself, a caption, a provenance line and an explicit
 * text-equivalent disclosure. It is never decoration: a media item with no teaching role does not
 * belong in a lesson document, and a failed preview keeps the text equivalent rather than
 * substituting a fake file.
 */
function MediaFrame({ artifactId, kind, label, caption, provenance, textEquivalent, children }) {
  return jsxs('figure', {
    'data-cb-media': artifactId || 'text-only',
    'data-cb-media-kind': kind || 'visual',
    style: {
      margin: '0.75rem 0',
      padding: '0.6rem 0.75rem 0.6rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem'
    },
    children: [
      children,
      caption
        ? jsx('figcaption', {
            'data-cb-media-caption': '',
            style: { fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
            children: caption
          })
        : null,
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: [
          label
            ? jsx('span', {
                'data-cb-media-label': '',
                style: {
                  border: '1px solid var(--cb-rule)',
                  borderRadius: '0.25rem',
                  padding: '0 0.3rem',
                  color: 'var(--cb-ink-soft)'
                },
                children: label
              })
            : null,
          // Item 42: a MIME type and a byte count are provenance, not learner copy. They stay in
          // the figure but behind a named disclosure, so the line a learner reads carries the
          // caption and the role only; the file's own facts are one deliberate click away.
          provenance
            ? jsxs('details', {
                'data-cb-media-provenance-detail': '',
                style: { color: 'var(--cb-ink-soft)' },
                children: [
                  jsx('summary', {
                    style: { cursor: 'pointer', minHeight: '1.75rem', fontSize: CB_TYPE.caption },
                    children: 'Provenance'
                  }),
                  jsx('span', { 'data-cb-media-provenance': '', children: provenance })
                ]
              })
            : null
        ]
      }),
      textEquivalent
        ? jsxs('div', {
            'data-cb-media-text-equivalent': '',
            'data-cb-media-transcript': kind === 'audio' ? 'true' : null,
            style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink)' },
            children: [
              jsx('div', {
                style: { fontWeight: 600, color: 'var(--cb-ink-soft)' },
                children: 'Text equivalent'
              }),
              jsx('div', { style: { paddingTop: '0.15rem' }, children: textEquivalent })
            ]
          })
        : null
    ]
  })
}

/**
 * The drawn-label overlay (cb.rpc v27, item 28b).
 *
 * The picture is generated textless — a model that paints a label garbles it into a false fact —
 * and every word a learner reads over the figure is page text the product UI draws here. The
 * labels ride the media child as `{text, x, y, anchor}` with `x`/`y` normalised 0–1 of the figure
 * box and `anchor` naming which point of the label sits at that point.
 *
 * `mediaLabelPlacement` is the whole geometry in one pure function so it can be proved without a
 * layout engine: it takes the frame's measured pixel box and returns each label's plate position,
 * clamped so a label at the very edge of a figure still reads inside the frame instead of hanging
 * off it. The plate's width is estimated from its text (the UI does not measure glyphs here); the
 * clamp uses that estimate, which is why it is generous rather than exact.
 */
const MEDIA_LABEL_HEIGHT = 22
const MEDIA_LABEL_PAD = 6
const MEDIA_LABEL_CHAR_WIDTH = 6.6
const MEDIA_LABEL_MAX_WIDTH = 240

function mediaLabelPlateWidth(text) {
  const characters = String(text == null ? '' : text).length
  return Math.min(MEDIA_LABEL_MAX_WIDTH, Math.max(28, Math.round(characters * MEDIA_LABEL_CHAR_WIDTH + 12)))
}

function clampToFrame(value, low, high) {
  if (high < low) return low
  return Math.min(Math.max(value, low), high)
}

function mediaLabelPlacement(labels, frame) {
  const width = Number(frame && frame.width) || 0
  const height = Number(frame && frame.height) || 0
  if (!Array.isArray(labels) || !labels.length || width <= 0 || height <= 0) return []
  return labels.map((label, index) => {
    const text = String((label && label.text) || '')
    const anchor = label && (label.anchor === 'center' || label.anchor === 'end') ? label.anchor : 'start'
    const plateWidth = mediaLabelPlateWidth(text)
    const plateHeight = MEDIA_LABEL_HEIGHT
    const x = clampToFrame(Number(label && label.x) || 0, 0, 1) * width
    const y = clampToFrame(Number(label && label.y) || 0, 0, 1) * height
    const anchored = anchor === 'center' ? x - plateWidth / 2 : anchor === 'end' ? x - plateWidth : x
    return {
      index,
      text,
      anchor,
      plateWidth,
      plateHeight,
      left: Math.round(clampToFrame(anchored, MEDIA_LABEL_PAD, width - plateWidth - MEDIA_LABEL_PAD)),
      top: Math.round(clampToFrame(y - plateHeight / 2, MEDIA_LABEL_PAD, height - plateHeight - MEDIA_LABEL_PAD))
    }
  })
}

function MediaLabelOverlay({ labels, frame }) {
  const placed = mediaLabelPlacement(labels, frame)
  if (!placed.length) return null
  return jsx('div', {
    'data-cb-media-labels': String(placed.length),
    style: { position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' },
    children: placed.map((label) =>
      jsx(
        'span',
        {
          'data-cb-media-label-text': '',
          'data-cb-media-label-anchor': label.anchor,
          'data-cb-media-label-x': String(labels[label.index].x),
          'data-cb-media-label-y': String(labels[label.index].y),
          style: {
            position: 'absolute',
            left: `${label.left}px`,
            top: `${label.top}px`,
            maxWidth: `${label.plateWidth}px`,
            minHeight: `${label.plateHeight}px`,
            boxSizing: 'border-box',
            padding: '0.1rem 0.35rem',
            // A legible backing plate: the label is page text, not a printed caption, so it never
            // relies on the artwork behind it for contrast.
            background: 'color-mix(in srgb, var(--cb-paper-raised) 92%, transparent)',
            border: '1px solid var(--cb-rule)',
            borderRadius: '0.2rem',
            color: 'var(--cb-ink)',
            fontFamily: 'inherit',
            fontSize: CB_TYPE.caption,
            lineHeight: '1.25',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          },
          children: label.text
        },
        `label-${label.index}`
      )
    )
  })
}

/**
 * The review verdict, as a chip on the media item (cb.rpc item 32).
 *
 * A generated illustration is judged before its bytes are stored, and the verdict is why a figure
 * can be missing. It used to travel to the page and be drawn by nobody, so a learner met a degraded
 * item with no explanation. This chip is that explanation, and it is built only from explicit
 * fields — never by reading the prose of a reason string:
 *
 *   - the media child's own `degraded` flag plus its bounded `reason`, which is all a page is told
 *     when no bytes were delivered;
 *   - the artifact route's `review` (`{state, reasons, criteria?}`), which exists when bytes did
 *     ship — a rejected illustration repaired into a deterministic schematic still carries the
 *     verdict that caused the repair.
 *
 * An approved, delivered item draws nothing: the chip is for a verdict a reader must be told.
 */
function mediaVerdict(media, review) {
  const verdict = review && typeof review === 'object' && !Array.isArray(review) ? review : null
  const state = verdict && typeof verdict.state === 'string' ? verdict.state : null
  const reasons =
    verdict && Array.isArray(verdict.reasons)
      ? verdict.reasons.map((reason) => String(reason || '').trim()).filter(Boolean)
      : []
  const criteria =
    verdict && Array.isArray(verdict.criteria)
      ? verdict.criteria.map((criterion) => String(criterion || '').trim()).filter(Boolean)
      : []
  if (state === 'approved') return null
  if (state === 'rejected' || state === 'unreviewed') {
    return {
      state,
      tone: state === 'rejected' ? 'reject' : 'warn',
      label: state === 'rejected' ? 'Rejected by review' : 'Not reviewed',
      criteria,
      reason: reasons.length ? reasons.join('; ') : null
    }
  }
  if (media && media.degraded) {
    return {
      state: 'degraded',
      tone: 'warn',
      label: 'Media degraded',
      criteria: [],
      reason: media.reason ? String(media.reason) : null
    }
  }
  return null
}

//: The chip's two tones come from the token contract only: `coral` is the attention hue (a
//: rejection is attention), and a plain rule is a degrade notice with no verdict state at all.
const CB_VERDICT_TONE = {
  reject: { border: 'var(--cb-coral)', ink: 'var(--cb-coral)' },
  warn: { border: 'var(--cb-rule)', ink: 'var(--cb-ink-soft)' }
}

function MediaVerdictChip({ media, review }) {
  const verdict = mediaVerdict(media, review)
  if (!verdict) return null
  const tone = CB_VERDICT_TONE[verdict.tone] || CB_VERDICT_TONE.warn
  return jsxs('div', {
    'data-cb-media-verdict': verdict.state,
    'data-cb-media-verdict-tone': verdict.tone,
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.4rem', fontSize: CB_TYPE.caption },
    children: [
      jsx('span', {
        'data-cb-media-verdict-chip': verdict.state,
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.25rem',
          border: `1px solid ${tone.border}`,
          borderRadius: '0.25rem',
          padding: '0 0.3rem',
          fontWeight: 600,
          lineHeight: 1.4,
          color: tone.ink,
          whiteSpace: 'nowrap'
        },
        children: verdict.label
      }),
      verdict.criteria.length
        ? jsx('span', {
            'data-cb-media-verdict-criteria': verdict.criteria.join(','),
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: verdict.criteria.join(' · ')
          })
        : null,
      verdict.reason
        ? jsx('span', {
            'data-cb-media-verdict-reason': '',
            style: { minWidth: 0, color: 'var(--cb-ink)', overflowWrap: 'anywhere' },
            children: verdict.reason
          })
        : null
    ]
  })
}

function MediaSegment({ segment }) {
  const preview = useArtifactPreview(segment.artifact_id)
  // The figure's measured box, in CSS pixels. The overlay's geometry is expressed against it, so
  // a label at `x=1` is clamped inside the frame at any width the lesson is read at. Measuring is
  // observation, not a claim: before the first measurement the overlay renders nothing rather
  // than guessing a frame size and painting a label in the wrong place.
  const frameRef = useRef(null)
  const [frame, setFrame] = useState(null)
  useEffect(() => {
    const node = frameRef.current
    if (!node) return undefined
    const measure = () => {
      const width = Number(node.clientWidth) || 0
      const height = Number(node.clientHeight) || 0
      setFrame((previous) =>
        previous && previous.width === width && previous.height === height ? previous : { width, height }
      )
    }
    measure()
    if (typeof ResizeObserver === 'function') {
      const observer = new ResizeObserver(measure)
      observer.observe(node)
      return () => observer.disconnect()
    }
    return undefined
  }, [preview.state, segment.artifact_id])

  // The authored kind is the description of the item; a served MIME is the observation. The
  // observation wins once the preview is ready, but a route that refuses or is unreachable must
  // not silently turn authored narration into a visual.
  const authoredKind = segment.kind === 'audio' || segment.kind === 'visual' ? segment.kind : null
  const previewKind =
    preview.state === 'ready' && preview.mime
      ? preview.mime.startsWith('audio/')
        ? 'audio'
        : preview.mime.startsWith('image/')
          ? 'visual'
          : null
      : null
  const kind = previewKind || authoredKind || 'visual'
  const caption = segment.text || preview.text_equivalent || ''
  const label =
    preview.label ||
    segment.label ||
    (kind === 'audio' ? 'Narration' : 'Illustration')
  const provenance =
    preview.state === 'ready'
      ? [
          preview.mime,
          typeof preview.bytes === 'number' ? `${preview.bytes} bytes` : null,
          segment.purpose || 'served by this host’s artifact route'
        ].filter(Boolean).join(' · ')
      : null
  const textEquivalent =
    preview.text_equivalent || segment.text_equivalent || segment.purpose || null
  // The verdict is drawn from explicit fields only: the route's own review for bytes that exist,
  // the child's degraded flag and reason when nothing was delivered (item 32).
  const verdictChip = jsx(MediaVerdictChip, {
    media: { degraded: segment.degraded, reason: segment.reason },
    review: preview.state === 'ready' ? preview.review : null
  })
  const element =
    preview.state === 'ready' && preview.mime === 'image/svg+xml'
      ? jsx('img', {
          alt: caption,
          style: { maxHeight: '380px', width: '100%', objectFit: 'contain' },
          loading: 'lazy',
          src: preview.data_url
        })
      : preview.state === 'ready' && preview.mime && preview.mime.startsWith('image/')
        ? jsx('img', {
            alt: caption,
            style: { maxHeight: '380px', width: '100%', objectFit: 'contain', borderRadius: '0.125rem' },
            loading: 'lazy',
            src: preview.data_url
          })
        : preview.state === 'ready' && preview.mime && preview.mime.startsWith('audio/')
          ? jsx('audio', {
              'aria-label': caption || 'Coursebook narration',
              style: { width: '100%' },
              controls: true,
              preload: 'metadata',
              src: preview.data_url
            })
          : preview.state === 'loading'
            ? jsx('div', { style: { padding: '0.35rem 0', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: 'Loading media' })
            : jsx('div', {
                style: { padding: '0.25rem 0', fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: preview.message
              })
  return jsx(MediaFrame, {
    artifactId: segment.artifact_id,
    kind,
    label,
    caption,
    provenance,
    textEquivalent: textEquivalent && textEquivalent !== caption ? textEquivalent : null,
    children: jsxs('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
      children: [
        kind === 'visual'
          ? jsxs('div', {
              // The figure and its drawn labels share one positioned box, so the overlay is
              // measured against the picture the learner actually sees — 380px tall in a narrow
              // column, 70vh or more in a wide one — and never against an assumed size.
              ref: frameRef,
              'data-cb-media-frame': '',
              style: { position: 'relative', display: 'block', lineHeight: 0, maxWidth: '100%' },
              children: [
                element,
                jsx(MediaLabelOverlay, { labels: segment.labels, frame })
              ]
            })
          : element,
        verdictChip,
        segment.artifact_id && supportsArtifactGet()
          ? jsx(sdk.Button, {
              variant: 'text',
              size: 'sm',
              onClick: async () => {
                const response = await rpc('artifact.get', { artifact_id: segment.artifact_id })
                if (!response.ok) {
                  host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
                  return
                }
                host.notify({ kind: 'info', message: `Artifact ready: ${response.result.mime}, ${response.result.bytes} bytes.` })
              },
              children: 'Artifact details'
            })
          : null
      ]
    })
  })
}

function supportsArtifactGet() {
  return backendSupports('artifact.get')
}

/**
 * One artifact preview through the plugin's own media route.
 *
 * The route is the only door this module has to media bytes, and it answers with a data URL for
 * renderable types only. `MediaSegment` and the pronunciation reference share this loader, so the
 * practice loop cannot grow a second audio source beside the lesson's own narration.
 */
function useArtifactPreview(artifactId) {
  const [preview, setPreview] = useState({ state: 'loading' })
  useEffect(() => {
    let live = true
    if (!artifactId) {
      setPreview({ state: 'text', message: 'No generated artifact is attached; the text equivalent is shown.' })
      return () => {
        live = false
      }
    }
    setPreview({ state: 'loading' })
    rest(`/media/${encodeURIComponent(artifactId)}`)
      .then((response) => {
        if (!live) return
        if (!response || response.ok !== true || typeof response.data_url !== 'string') {
          setPreview({
            state: 'text',
            message: (response && response.message) || 'This media could not be previewed; the text equivalent remains.'
          })
          return
        }
        setPreview({ state: 'ready', ...response })
      })
      .catch((error) => {
        if (live) {
          setPreview({
            state: 'text',
            message: `This media could not be previewed (${describeError(error)}); the text equivalent remains.`
          })
        }
      })
    return () => {
      live = false
    }
  }, [artifactId])
  return preview
}

/* ── Pronunciation Studio ────────────────────────────────────────────────────────────────────
 * docs/VISUAL_MEDIA_PLAN.md §7. The model phrase is the lesson's own narration artifact and its
 * authored transcript; the learner plays it, records one explicit take, and the backend compares
 * the transcript with its own recogniser.
 *
 * The honesty rules this component is built around, and why each exists:
 *   - the reference is loaded through the one media route and never autoplays — a lesson's audio
 *     is never a surprise, and there is no second audio source in this module;
 *   - capture starts only on an explicit Record press and stops on Stop/unmount; nothing listens
 *     in the background and no take is captured while the reader is doing something else;
 *   - the number on screen is the recogniser's own `confidence` and the deterministic word
 *     comparison the backend already returned. This component computes no score, so a fabricated
 *     percentage is not expressible here;
 *   - the result is labelled `model_assessed` and described as a practice measurement, never as
 *     "verified pronunciation", mastery or a graded pass;
 *   - without a recogniser the surface says "Practice only, not graded" and does not offer a
 *     Record control that would imply a grade;
 *   - the take is deleted from memory after comparison. Coursebook retains no audio at all.
 */
const PRONUNCIATION_VERDICT_COPY = {
  meets_target: 'Meets the target phrase',
  close: 'Close — another pass would help',
  needs_practice: 'Needs practice',
  unavailable: 'Not assessed'
}

const PRONUNCIATION_REASON_COPY = {
  empty_transcript: 'The recogniser did not catch any speech. Try again a little closer to the microphone.',
  transcription_failed: 'The recogniser could not transcribe this take. Nothing was recorded as evidence.',
  stt_dependency_missing: 'the local recogniser is not installed',
  ffmpeg_missing: 'the audio decoder is not installed',
  model_unavailable: 'the local model is not available',
  stt_cache_unavailable: 'the local model cache is unavailable',
  numpy_missing: 'the numeric runtime is not installed',
  decode_failed: 'the take could not be decoded',
  decode_empty: 'the take decoded to silence',
  audio_too_long: 'the take is longer than the 30 second limit'
}

/** An honest percentage: only a real 0..1 number becomes a percent, otherwise nothing prints. */
function pronPercent(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) return null
  return `${Math.round(value * 100)}%`
}

function pronUnitLabel(unit) {
  return unit === 'character' ? 'characters' : 'words'
}

/** The backend's own per-unit comparison, printed as it was returned. */
function PronunciationWords({ words, unit }) {
  const list = Array.isArray(words) ? words : []
  if (list.length === 0) return null
  return jsx('ol', {
    'data-cb-pronunciation-words': String(list.length),
    'aria-label': `Comparison by ${pronUnitLabel(unit)}`,
    style: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem', listStyle: 'none', margin: 0, padding: 0 },
    children: list.map((word, index) =>
      jsxs(
        'li',
        {
          'data-cb-pronunciation-word': word.match ? 'match' : 'miss',
          style: {
            display: 'inline-flex',
            alignItems: 'baseline',
            gap: '0.3rem',
            border: `1px solid ${word.match ? 'var(--cb-rule)' : 'var(--cb-ink-soft)'}`,
            borderRadius: '0.25rem',
            padding: '0.05rem 0.35rem',
            fontSize: CB_TYPE.meta
          },
          children: [
            jsx('span', { children: word.expected || '—' }),
            word.match
              ? null
              : jsx('span', {
                  style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: word.heard ? `heard “${word.heard}”` : 'not heard'
                }),
            word.match && pronPercent(word.confidence)
              ? jsx('span', {
                  'data-cb-word-confidence': pronPercent(word.confidence),
                  style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: pronPercent(word.confidence)
                })
              : null
          ]
        },
        `${word.expected || 'unit'}-${index}`
      )
    )
  })
}

/** One honest status line: what would assess a take right now, and where it runs. */
function pronunciationAvailabilityCopy(status) {
  if (!status || status.state === 'loading') return { tone: 'loading', text: 'Checking for a recogniser on this machine.' }
  if (status.state === 'error') {
    return {
      tone: 'unavailable',
      text: `Practice only, not graded. The recogniser status could not be read (${status.message}).`
    }
  }
  const provider = status.provider || 'unknown provider'
  if (status.available === true) {
    return {
      tone: 'available',
      text:
        `Assessed on this machine by Coursebook’s own recogniser (provider ${provider}` +
        `${status.model ? `, model ${status.model}` : ''}). Nothing is uploaded, and the take is ` +
        'deleted after comparison.'
    }
  }
  const reason = PRONUNCIATION_REASON_COPY[status.reason] || status.reason || 'no recogniser is configured'
  return { tone: 'unavailable', text: `Practice only, not graded. Recording stays off because ${reason}.` }
}

function PronunciationStudio({ enrollmentId, objectiveId, revision, locale, block, media, implemented, onSaved }) {
  const target = String((media && media.text_equivalent) || '').trim()
  const preview = useArtifactPreview(media && media.artifact_id)
  const motion = useCbMotion()
  const [status, setStatus] = useState({ state: 'loading' })
  const [phase, setPhase] = useState('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const audioRef = useRef(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const tickRef = useRef(null)
  const nonceRef = useRef(null)

  useEffect(() => {
    let live = true
    rest('/pronunciation/status')
      .then((response) => {
        if (live) setStatus({ state: 'ready', ...(response || {}) })
      })
      .catch((failure) => {
        if (live) setStatus({ state: 'error', message: describeError(failure) })
      })
    return () => {
      live = false
    }
  }, [])

  const releaseCapture = useCallback(() => {
    const stream = streamRef.current
    streamRef.current = null
    if (stream && typeof stream.getTracks === 'function') {
      stream.getTracks().forEach((track) => {
        try {
          track.stop()
        } catch (failure) {
          // A track that is already closed needs no second stop.
        }
      })
    }
    if (tickRef.current) {
      clearInterval(tickRef.current)
      tickRef.current = null
    }
  }, [])

  // A take never outlives the surface: leaving the section closes the microphone.
  useEffect(() => releaseCapture, [releaseCapture])

  const assess = useCallback(
    async (blob) => {
      setPhase('comparing')
      setError(null)
      setResult(null)
      setSaved(false)
      let dataUrl
      try {
        dataUrl = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(String(reader.result || ''))
          reader.onerror = () => reject(reader.error || new Error('the take could not be read'))
          reader.readAsDataURL(blob)
        })
      } catch (readFailure) {
        setPhase('error')
        setError({ code: 'TAKE_UNREADABLE', message: describeError(readFailure) })
        return
      }
      let response
      try {
        response = await rest('/pronunciation/attempt', {
          method: 'POST',
          timeoutMs: 180000,
          body: {
            enrollment_id: enrollmentId,
            objective_id: objectiveId,
            attempt_nonce: nonceRef.current || newOperationId('take'),
            target,
            locale,
            audio_data_url: dataUrl,
            expected_revision: Number(revision) || 0,
            idempotency_key: `cb-pronunciation-${nonceRef.current || newOperationId('take')}`
          }
        })
      } catch (transportFailure) {
        setPhase('error')
        setError({ code: 'HOST_UNAVAILABLE', message: describeError(transportFailure) })
        return
      }
      if (!response || response.ok !== true) {
        setPhase('error')
        setError(
          (response && response.error) || {
            code: 'INTERNAL_ERROR',
            message: 'Coursebook answered with data it could not read.'
          }
        )
        return
      }
      setResult(response.result || null)
      setPhase('done')
    },
    [enrollmentId, objectiveId, revision, target, locale]
  )

  const start = useCallback(async () => {
    setError(null)
    setResult(null)
    setSaved(false)
    nonceRef.current = newOperationId('take')
    const devices = typeof navigator !== 'undefined' ? navigator.mediaDevices : null
    if (!devices || typeof devices.getUserMedia !== 'function' || typeof MediaRecorder === 'undefined') {
      setPhase('error')
      setError({ code: 'MIC_UNAVAILABLE', message: 'This window has no microphone capture, so no take can be recorded.' })
      return
    }
    let stream
    try {
      stream = await devices.getUserMedia({ audio: true })
    } catch (permissionFailure) {
      setPhase('error')
      setError({ code: 'MIC_BLOCKED', message: `The microphone was not opened: ${describeError(permissionFailure)}` })
      return
    }
    streamRef.current = stream
    chunksRef.current = []
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg'].find(
      (candidate) => typeof MediaRecorder.isTypeSupported === 'function' && MediaRecorder.isTypeSupported(candidate)
    )
    let recorder
    try {
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined)
    } catch (recorderFailure) {
      releaseCapture()
      setPhase('error')
      setError({ code: 'MIC_UNAVAILABLE', message: `The recorder could not start: ${describeError(recorderFailure)}` })
      return
    }
    recorderRef.current = recorder
    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) chunksRef.current.push(event.data)
    }
    recorder.onstop = () => {
      const chunks = chunksRef.current
      chunksRef.current = []
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
      releaseCapture()
      if (blob.size === 0) {
        setPhase('error')
        setError({ code: 'EMPTY_TAKE', message: 'The recorder produced no audio. Try again.' })
        return
      }
      assess(blob)
    }
    recorder.start()
    setSeconds(0)
    setPhase('recording')
    const startedAt = Date.now()
    tickRef.current = setInterval(() => {
      const elapsed = Math.round((Date.now() - startedAt) / 1000)
      setSeconds(elapsed)
      // The backend refuses a take longer than 30 s; the bound is enforced here too so the
      // learner is never asked to upload something the contract will reject.
      if (elapsed >= 30 && recorder.state === 'recording') {
        try {
          recorder.stop()
        } catch (stopFailure) {
          // onstop already ran or will run; nothing else to do.
        }
      }
    }, 250)
  }, [assess, releaseCapture])

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (recorder && recorder.state === 'recording') {
      try {
        recorder.stop()
      } catch (stopFailure) {
        // A recorder that already stopped is not an error the learner needs to see.
      }
    }
    releaseCapture()
  }, [releaseCapture])

  /** Discard the take and the result. No audio was ever stored, so this only clears this surface. */
  const forget = useCallback(() => {
    nonceRef.current = null
    setResult(null)
    setError(null)
    setSaved(false)
    setSeconds(0)
    setPhase('idle')
  }, [])

  const saveResult = useCallback(async () => {
    if (!result || !result.assessment) return
    const assessment = result.assessment
    const matched = (assessment.words || []).filter((word) => word.match).length
    const total = (assessment.words || []).length
    setSaving(true)
    const response = await rpc('notebook.save', {
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: null,
      kind: 'personal_note',
      excerpt: `${assessment.target} — heard ${assessment.transcript || 'nothing'}`,
      note:
        `Pronunciation practice (${assessment.provider}). ${matched} of ${total} ` +
        `${pronUnitLabel(assessment.unit)} matched; ${PRONUNCIATION_VERDICT_COPY[assessment.verdict] || assessment.verdict}. ` +
        'Assessed by a model — a practice measurement, not a graded score.',
      tags: ['pronunciation_practice'],
      source_ref: notebookSourceRef({
        block_id: block && block.id,
        artifact_id: media && media.artifact_id,
        source_ids: (block && block.source_ids) || []
      })
    })
    setSaving(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setSaved(true)
    if (onSaved) onSaved()
  }, [result, enrollmentId, objectiveId, block, media, onSaved])

  const availability = pronunciationAvailabilityCopy(status)
  const canRecord = status.state === 'ready' && status.available === true && phase !== 'comparing'
  const assessment = result && result.assessment ? result.assessment : null
  const matchedCount = assessment ? (assessment.words || []).filter((word) => word.match).length : 0
  const totalCount = assessment ? (assessment.words || []).length : 0

  const listen = () => {
    const audio = audioRef.current
    if (!audio || typeof audio.play !== 'function') return
    try {
      const started = audio.play()
      if (started && typeof started.catch === 'function') started.catch(() => {})
    } catch (playFailure) {
      // The native controls remain the fallback; a refused play() is not a lost lesson.
    }
  }

  return jsxs('section', {
    'data-cb-pronunciation': (block && block.id) || 'block',
    'data-cb-pronunciation-phase': phase,
    'data-cb-pronunciation-availability': availability.tone,
    'data-cb-pronunciation-motion': motion.preference,
    'aria-label': `Pronunciation practice: ${target}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      margin: '0.5rem 0 0.25rem',
      padding: '0.6rem 0.75rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.4rem' },
        children: [
          jsx('h4', {
            style: { margin: 0, fontSize: CB_TYPE.meta, fontWeight: 600 },
            children: 'Pronunciation practice'
          }),
          jsx('span', {
            'data-cb-pronunciation-target': target,
            lang: locale,
            style: { fontSize: CB_TYPE.body },
            children: target
          })
        ]
      }),

      // The reference: the lesson's own narration artifact, through the same media route. Native
      // controls mean Play is the explicit action; nothing here autoplays.
      preview.state === 'ready' && preview.mime && String(preview.mime).startsWith('audio/')
        ? jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
            children: [
              jsx('audio', {
                ref: audioRef,
                'aria-label': `Reference recording of ${target}`,
                'data-cb-pronunciation-reference': preview.mime,
                controls: true,
                preload: 'metadata',
                src: preview.data_url,
                style: { width: '100%', maxWidth: '22rem' }
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                onClick: listen,
                children: 'Listen'
              })
            ]
          })
        : jsx('p', {
            'data-cb-pronunciation-reference': preview.state === 'loading' ? 'loading' : 'none',
            style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children:
              preview.state === 'loading'
                ? 'Loading the reference recording.'
                : 'No reference recording is attached to this block; the transcript above is the model.'
          }),

      jsx('p', {
        'data-cb-pronunciation-disclosure': availability.tone,
        'aria-live': 'polite',
        style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: availability.text
      }),

      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
        children: [
          phase === 'recording'
            ? jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: stop, children: 'Stop' })
            : jsx(CbAction, {
                variant: 'primary',
                disabled: !canRecord,
                onClick: start,
                'aria-describedby': 'cb-pronunciation-availability',
                children: phase === 'done' || phase === 'error' ? 'Record again' : 'Record'
              }),
          phase === 'recording'
            ? jsx('span', {
                'data-cb-pronunciation-timer': String(seconds),
                role: 'status',
                'aria-live': 'polite',
                style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: `Recording — ${seconds} s of 30 s. Stop when you are done.`
              })
            : null,
          phase === 'comparing'
            ? jsx('span', {
                role: 'status',
                style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: 'Comparing your take with the target…'
              })
            : null,
          phase === 'recording' || phase === 'comparing' || phase === 'done' || phase === 'error'
            ? jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                disabled: phase === 'comparing',
                onClick: forget,
                children: phase === 'comparing' ? 'Delete take' : 'Delete take and result'
              })
            : null
        ]
      }),

      error
        ? jsxs('div', {
            'data-cb-pronunciation-error': error.code || 'ERROR',
            role: 'status',
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
            children: [
              jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600 }, children: `${error.code}: ${describeError(error)}` }),
              jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: 'No evidence was recorded.' })
            ]
          })
        : null,

      result && result.status === 'assessed' && assessment
        ? jsxs('div', {
            'data-cb-pronunciation-result': 'assessed',
            style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
                children: [
                  jsx(sdk.Badge, {
                    size: 'xs',
                    variant: 'outline',
                    children: 'Practice measurement'
                  }),
                  jsx('span', {
                    'data-cb-pronunciation-verdict': assessment.verdict,
                    style: { fontSize: CB_TYPE.meta, fontWeight: 600 },
                    children: PRONUNCIATION_VERDICT_COPY[assessment.verdict] || assessment.verdict
                  }),
                  pronPercent(assessment.confidence)
                    ? jsx('span', {
                        'data-cb-pronunciation-confidence': pronPercent(assessment.confidence),
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: `Recogniser confidence ${pronPercent(assessment.confidence)}`
                      })
                    : null,
                  totalCount > 0
                    ? jsx('span', {
                        'data-cb-pronunciation-matched': `${matchedCount}/${totalCount}`,
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: `${matchedCount} of ${totalCount} ${pronUnitLabel(assessment.unit)} matched`
                      })
                    : null
                ]
              }),
              jsx('p', {
                style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.5 },
                children: `Heard: ${assessment.transcript || 'nothing'}`
              }),
              jsx(PronunciationWords, { words: assessment.words, unit: assessment.unit }),
              jsx('p', {
                'data-cb-pronunciation-provenance': assessment.provider,
                style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children:
                  `Practice measurement by ${assessment.provider}` +
                  `${assessment.model ? ` (${assessment.model})` : ''} — not verified pronunciation and not a graded score.` +
                  `${result.attempt_id ? ` Attempt ${result.attempt_id}.` : ''}`
              }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
                children: [
                  implemented && implemented.has('notebook.save')
                    ? jsx(sdk.Button, {
                        variant: 'secondary',
                        size: 'sm',
                        disabled: saving || saved,
                        onClick: saveResult,
                        children: saved ? 'Saved to notebook' : saving ? 'Saving' : 'Save result to notebook'
                      })
                    : null,
                  saved
                    ? jsx('span', {
                        role: 'status',
                        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: 'The result is in the notebook; the audio was never stored.'
                      })
                    : null
                ]
              })
            ]
          })
        : null,

      result && result.status !== 'assessed'
        ? jsxs('div', {
            'data-cb-pronunciation-result': result.status || 'unavailable',
            role: 'status',
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
            children: [
              jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600 }, children: 'Practice only, not graded' }),
              jsx('span', {
                style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children:
                  PRONUNCIATION_REASON_COPY[result.reason] ||
                  result.reason ||
                  'This take was not assessed. Nothing was recorded as evidence.'
              })
            ]
          })
        : null
    ]
  })
}

/**
 * The studio's seat in a block.
 *
 * Only a block that carries a narration audio child has an authored model phrase: its transcript is
 * the authoritative target and its artifact is the reference. A block with no narration gets no
 * studio — this never invents a phrase to pronounce.
 */
function PronunciationSeat({ block, pronunciation }) {
  if (!pronunciation) return null
  const media = (block.media || []).find(
    (item) => item && item.kind === 'audio' && String(item.text_equivalent || '').trim()
  )
  if (!media) return null
  return jsx(PronunciationStudio, {
    enrollmentId: pronunciation.enrollmentId,
    objectiveId: pronunciation.objectiveId,
    revision: pronunciation.revision,
    locale: pronunciation.locale,
    block,
    media,
    implemented: pronunciation.implemented,
    onSaved: pronunciation.onSaved
  })
}

/**
 * The presentation views this build implements (docs/VISUAL_MEDIA_PLAN.md §3.3, §5).
 *
 * `player` is the default learning surface (docs/EXPERIENCE-QUALITY-BAR.md §7.4, H-149): one
 * concept, one check, one close, rendered from the same lesson document, check and evidence as
 * the reference views. Textbook stays the optional reference view, and the order here is the order
 * the Home default offers: Game, Guided, Textbook.
 */
const LESSON_VIEWS = [
  { id: 'player', label: 'Game' },
  { id: 'guided', label: 'Guided' },
  { id: 'textbook', label: 'Textbook' },
  { id: 'field_quest', label: 'Field Quest' }
]

/**
 * Why a view cannot render for this document, in the learner's words.
 *
 * An older stored page has no `views` object at all; that is the same fact as `guided: false`,
 * not a reason to hide the choice. The switcher names all three views and explains the missing
 * ones instead of silently dropping them (H-96 / H-80 F3).
 */
const LESSON_VIEW_UNAVAILABLE_REASON = {
  guided: 'This lesson has no guided version.',
  field_quest: 'This lesson has no Field Quest version.'
}

/**
 * The views *this document* can render.
 *
 * Textbook and the player are the floor: both are read from the document's own blocks and its one
 * check, so neither can be missing for a document that has blocks. Guided needs authored `short`
 * prose on every block. Field Quest needs the same and exactly one attachable check, because its
 * checkpoints are the document's existing checks and nothing else. This returns only the enabled
 * options (the legacy marker value); `lessonViewChoices` returns all four with an availability
 * flag and a reason.
 */
function lessonViewOptions(document) {
  const views = (document && document.views) || {}
  return LESSON_VIEWS.filter((view) =>
    view.id === 'textbook' || view.id === 'player' ? true : Boolean(views[view.id])
  )
}

/** All four named views, each marked available or carrying the plain-words reason it is not. */
function lessonViewChoices(document) {
  const views = (document && document.views) || {}
  return LESSON_VIEWS.map((view) => {
    const available = view.id === 'textbook' || view.id === 'player' ? true : Boolean(views[view.id])
    return {
      ...view,
      available,
      reason: available ? null : LESSON_VIEW_UNAVAILABLE_REASON[view.id] || `This lesson has no ${view.label} version.`
    }
  })
}

/** A role is where the block sits in the teaching sequence, never a skin or a difficulty claim. */
const BLOCK_ROLE_COPY = {
  orient: 'Orient',
  explain: 'Explain',
  example: 'Example',
  practice: 'Practice',
  recap: 'Recap'
}

/**
 * Source chips for one block.
 *
 * A chip prints the course's own source title. An id the course did not return is printed as the
 * id: the Desktop never turns an unknown id into a citation it cannot show.
 */
function BlockSourceChips({ ids, index }) {
  if (!ids || ids.length === 0) return null
  return jsx('div', {
    'data-cb-block-sources': String(ids.length),
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.3rem' },
    children: ids.map((id) =>
      jsx(
        'span',
        {
          'data-cb-source-chip': id,
          style: {
            display: 'inline-flex',
            maxWidth: '100%',
            minWidth: 0,
            alignItems: 'center',
            border: '1px solid var(--cb-rule)',
            borderRadius: '2px',
            padding: '0.1rem 0.45rem',
            fontFamily: CB_SANS,
            fontSize: CB_TYPE.caption,
            fontWeight: 600,
            lineHeight: 1.3,
            color: 'var(--cb-ink-soft)',
            whiteSpace: 'normal',
            overflowWrap: 'anywhere'
          },
          children: (index && index[id] && index[id].title) || `Source ${id}`
        },
        id
      )
    )
  })
}

/**
 * Media as a child of a block.
 *
 * One artifact, one text equivalent, one label. The preview, the audio player and the honest
 * text fallback are `MediaSegment`'s own implementation: a block view re-frames the same node, it
 * does not grow a second media renderer.
 */
function BlockMedia({ media, blockId, ordinal }) {
  const segment = {
    artifact_id: media.artifact_id,
    // The authored kind travels with the media child: a failed preview still knows whether the
    // author wrote narration or an illustration, so it cannot relabel audio as visual.
    kind: media.kind,
    text: media.text_equivalent || media.purpose,
    label: media.label,
    // The drawn labels ride the media child: they are the words the UI paints over a textless
    // figure, and they are page text, so the block frame draws them rather than the raster.
    labels: media.labels,
    // The verdict travels with the item: a degraded illustration is the gate's own decision, and
    // `MediaSegment` draws it as the chip rather than a paragraph of prose (item 32).
    degraded: media.degraded,
    reason: media.reason
  }
  return jsx(
    'div',
    {
      className: 'flex flex-col gap-1',
      'data-cb-block-media': media.artifact_id || 'text-only',
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.35rem',
        maxWidth: '48rem',
        padding: '0.55rem 0.7rem',
        border: '1px solid var(--cb-rule)',
        background: 'var(--cb-paper-raised)',
        borderRadius: 0,
        boxSizing: 'border-box'
      },
      children: [jsx(MediaSegment, { segment })]
    },
    `${blockId}-media-${ordinal}`
  )
}

/**
 * Checklist labels are check data, not prose.
 *
 * A section's `deep`/`short` prose can still carry the lines an author also wrote into the check
 * (older sections did exactly that: the teaching segment, the `check_prompt` practice block and
 * the check surface each printed the same list). The check surface prints every structured item
 * once, so the document renderer drops a prose line whose only content is that item's label. The
 * comparison ignores case, spacing and punctuation, the same rule the backend validates with.
 */
function normalizeCheckLabel(value) {
  return String(value == null ? '' : value)
    .toLowerCase()
    .replace(/[\p{P}\p{S}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function withoutCheckLabels(text, checkLabels) {
  if (!text || !checkLabels || checkLabels.length === 0) return text
  const hidden = new Set(checkLabels.map(normalizeCheckLabel).filter(Boolean))
  if (hidden.size === 0) return text
  const kept = []
  for (const line of String(text).split('\n')) {
    if (hidden.has(normalizeCheckLabel(line))) continue
    if (line.trim() === '' && kept.length > 0 && kept[kept.length - 1].trim() === '') continue
    kept.push(line)
  }
  return kept.join('\n').trim()
}

/**
 * One save affordance per teaching block and per media child.
 *
 * The excerpt is the backend-owned structured segment: the block's own `deep` prose (or its
 * `text_equivalent` for a media child). There is no transcript selection API behind this, and the
 * Desktop does not ask the chat for text — it saves the document it was served.
 */
function BlockSaveActions({ block, checkLabels, onSaveBlock, className }) {
  if (!onSaveBlock) return null
  const buttons = [
    jsx(sdk.Button, {
      variant: 'text',
      size: 'sm',
      'aria-label': `Save ${block.headline || 'this block'} to the notebook`,
      onClick: () => onSaveBlock(block, null),
      children: 'Save to notebook'
    })
  ]
  ;(block.media || []).forEach((media, index) => {
    buttons.push(
      jsx(sdk.Button, {
        variant: 'text',
        size: 'sm',
        'aria-label': `Save ${media.label || 'this media'} from ${block.headline || 'this block'} to the notebook`,
        onClick: () => onSaveBlock(block, media),
        children: media.kind === 'audio' ? 'Save audio' : 'Save visual'
      })
    )
  })
  return jsx('div', {
    className: className || 'flex flex-wrap items-center gap-1',
    'data-cb-block-save': block.id || 'block',
    children: buttons
  })
}

/**
 * Authored lesson prose is content underneath the page's one `h1`. A markdown document may carry
 * its own `#` title, so an `h1` inside a reading body is given ARIA heading level 2: the page keeps
 * exactly one `h1`, the prose keeps its own heading, and no level is skipped. The text, its order
 * and the host's markdown renderer are untouched — only the announced level changes.
 */
function useProseHeadingTier() {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return undefined
    const apply = () => {
      for (const heading of root.querySelectorAll('h1')) {
        if (heading.getAttribute('role') === 'heading' && heading.getAttribute('aria-level') === '2') continue
        heading.setAttribute('role', 'heading')
        heading.setAttribute('aria-level', '2')
      }
    }
    apply()
    if (typeof MutationObserver !== 'function') return undefined
    const observer = new MutationObserver(apply)
    observer.observe(root, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  return ref
}

/** The host's markdown renderer inside a reading body, with the one-`h1` prose tier applied. */
function ProseText({ text, ...wrapper }) {
  const ref = useProseHeadingTier()
  return jsx('div', { ...wrapper, ref, children: jsx(sdk.MessageTextContent, { text }) })
}

/** The excerpt a save will carry: the block's own prose, never a re-summarised one. */
function blockSaveExcerpt(block, checkLabels, media) {
  if (media) return media.text_equivalent || media.purpose || block.headline || ''
  return withoutCheckLabels(block.deep, checkLabels) || block.short || block.headline || ''
}

/**
 * The reading voice of one block: serif, 66ch, 1.65. The first block of a section is its lede and
 * carries a 2px `accent` reading edge; every later block is the same column without the edge, so
 * long prose stays scannable without a second font or a card per paragraph.
 */
function BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede }) {
  const body = withoutCheckLabels(block.deep, checkLabels)
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      body
        ? jsx(ProseText, {
            'data-cb-reading-body': lede ? 'lede' : 'body',
            style: {
              maxWidth: CB_MEASURE,
              fontFamily: CB_SERIF,
              fontSize: lede ? CB_TYPE.lead : CB_TYPE.body,
              lineHeight: lede ? 1.5 : 1.65,
              color: 'var(--cb-ink)',
              borderLeft: lede ? '1px solid var(--cb-accent)' : 'none',
              paddingLeft: lede ? '0.9rem' : 0
            },
            text: body
          })
        : null,
      (block.media || []).map((media, index) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal: index }, `${block.id}-media-${index}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Checkpoint',
            children: jsx('div', {
              className: 'flex flex-col gap-2',
              'data-cb-block-check': block.id,
              children: [
                checkSlot,
                jsx('p', {
                  style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                  children: 'This is the section’s one check. It is the same in Game, Textbook, Guided and Field Quest, and it is not a grade.'
                })
              ]
            })
          })
        : null
    ]
  })
}

/** Textbook: every block in authored order, the full `deep` prose, inline figures. */
function TextbookBlock({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede }) {
  return jsxs('article', {
    className: 'flex flex-col gap-2',
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    'data-cb-block-lede': lede ? 'true' : 'false',
    tabIndex: -1,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      maxWidth: CB_MEASURE,
      padding: lede ? '0 0 1.35rem' : '1.35rem 0',
      borderTop: lede ? 'none' : '1px solid var(--cb-rule)',
      userSelect: 'text',
      WebkitUserSelect: 'text'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem 0.6rem' },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.25,
              letterSpacing: '-0.01em',
              color: 'var(--cb-ink)',
              maxWidth: '34ch',
              overflowWrap: 'anywhere'
            },
            children: block.headline
          }),
          jsx('span', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, lineHeight: 1.3, color: 'var(--cb-ink-soft)' },
            children: BLOCK_ROLE_COPY[block.role] || block.role
          })
        ]
      }),
      BlockBody({ block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation, lede })
    ]
  })
}

/** Guided: one step at a time, the authored `short` prose, the step's place, and the action. */
function GuidedBlock({ block, index, total, sources, checkSlot, checkLabels, onBack, onNext, onSaveBlock, pronunciation }) {
  const last = index >= total - 1
  const body = withoutCheckLabels(block.short || block.deep, checkLabels)
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  return jsxs('section', {
    className: 'flex flex-col gap-3',
    'aria-labelledby': `cb-guided-headline-${block.id}`,
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    'data-cb-step-count': `${index + 1}/${total}`,
    tabIndex: -1,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      maxWidth: CB_MEASURE,
      paddingLeft: phone ? 0 : '2.75rem',
      position: 'relative',
      userSelect: 'text',
      WebkitUserSelect: 'text'
    },
    children: [
      // The step margin: a 28px node and a 1px connector in the Guided hue. At narrow widths the
      // step number moves into the heading line instead of shrinking the reading column.
      phone
        ? null
        : jsxs('span', {
            'aria-hidden': 'true',
            style: { position: 'absolute', left: 0, top: '0.15rem', display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%' },
            children: [
              jsx('span', {
                'data-cb-guided-node': String(index + 1),
                style: {
                  width: '1.75rem',
                  height: '1.75rem',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'var(--cb-accent-soft)',
                  border: '2px solid var(--cb-field)',
                  color: 'var(--cb-field)',
                  fontFamily: CB_SANS,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600
                },
                children: String(index + 1).padStart(2, '0')
              }),
              jsx('span', { style: { flex: '1 1 auto', width: '1px', background: 'var(--cb-rule)', marginTop: '0.25rem' } })
            ]
          }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.3rem 0.75rem' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem 0.6rem', minWidth: 0 },
            children: [
              jsx('h3', {
                id: `cb-guided-headline-${block.id}`,
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.2,
                  letterSpacing: '-0.01em',
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: block.headline
              }),
              jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, lineHeight: 1.3, color: 'var(--cb-field)' },
                children: BLOCK_ROLE_COPY[block.role] || block.role
              })
            ]
          }),
          jsx('span', {
            style: {
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.caption,
              color: 'var(--cb-ink-soft)'
            },
            'aria-live': 'polite',
            'data-cb-step': `${index + 1}/${total}`,
            children: `Step ${index + 1} of ${total}`
          })
        ]
      }),
      body
        ? jsx(ProseText, {
            style: {
              maxWidth: CB_MEASURE,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.lead,
              lineHeight: 1.6,
              color: 'var(--cb-ink)'
            },
            text: body
          })
        : null,
      (block.media || []).map((media, ordinal) =>
        jsx(BlockMedia, { media, blockId: block.id, ordinal }, `${block.id}-media-${ordinal}`)
      ),
      jsx(PronunciationSeat, { block, pronunciation }),
      jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
      jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
      checkSlot
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Checkpoint',
            children: jsx('div', { className: 'flex flex-col gap-2', 'data-cb-block-check': block.id, children: checkSlot })
          })
        : null,
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.5rem',
          paddingTop: '0.65rem',
          borderTop: '1px solid var(--cb-rule)'
        },
        children: [
          jsx(sdk.Button, {
            variant: 'secondary',
            size: 'sm',
            disabled: index === 0,
            onClick: onBack,
            children: 'Back'
          }),
          jsx(CbAction, {
            variant: 'primary',
            disabled: last,
            onClick: onNext,
            children: 'Continue'
          }),
          last
            ? jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                children: 'End of the guided pass. The Textbook view keeps the full text.'
              })
            : null
        ]
      })
    ]
  })
}

/**
 * A mission is one block of the same document, in authored order.
 *
 * There is no second lesson here: `block` is the document's own block, `checkpoint` is a label on
 * the block that already carries the document's single check, and nothing is generated.
 */
function questMissions(document) {
  const blocks = (document && document.blocks) || []
  const checkId = document ? document.check_id : null
  return blocks.map((block, index) => ({
    index,
    total: blocks.length,
    block,
    checkpoint: Boolean(checkId && block.check_id === checkId)
  }))
}

/**
 * Progress is descriptive, never a score.
 *
 * "2 independent · 1 due" counts objectives the backend has already recorded as independent and
 * objectives it has already flagged as due. It is not a streak, an XP total or a mastery claim; a
 * course with nothing recorded says so instead of showing a zero that looks like a grade.
 */
function questProgressLabel(summary) {
  if (!summary || typeof summary !== 'object') return 'Progress not recorded'
  const total = Number(summary.total_objectives) || 0
  if (total === 0) return 'No objectives recorded yet'
  const independent = Number(summary.independent) || 0
  const due = Number(summary.review_due) || 0
  return `${independent} independent · ${due} due`
}

/**
 * The one line a mission shows.
 *
 * Field Quest is a path, not a second reader: the brief is the block's authored `short` prose cut
 * to its first sentence, and the full prose, media and pronunciation studio stay in Textbook. The
 * line is also painted as a single row (`nowrap` + ellipsis), so a narrow window never turns the
 * pointer back into a prose block.
 */
function missionBriefLine(block, checkLabels) {
  const text = withoutCheckLabels(block.short || block.deep, checkLabels) || ''
  const flat = String(text).replace(/\s+/g, ' ').trim()
  if (!flat) return ''
  const stop = flat.search(/[.!?](\s|$)/)
  const first = stop >= 0 ? flat.slice(0, stop + 1) : flat
  return first.length > 140 ? `${first.slice(0, 137).trimEnd()}…` : first
}

/**
 * One mission on the quest spine: a numbered node, the role word, a serif title, one line of what
 * the learner does, and one way into the same block in Textbook. A checkpoint keeps the same node
 * but gains the `lamp-soft` check field. Nothing is locked, nothing is scored, and the row holds
 * exactly one action — the whole row is not a second, invisible control.
 */
function QuestMission({ mission, sources, checkSlot, checkLabels, onReadInTextbook, onSaveBlock, pronunciation }) {
  const block = mission.block
  const brief = missionBriefLine(block, checkLabels)
  const checkpoint = mission.checkpoint
  const stateWord = checkpoint ? 'Checkpoint' : 'Mission'
  const tone = checkpoint ? 'var(--cb-ochre)' : 'var(--cb-ink-soft)'
  return jsxs('li', {
    'data-cb-mission': block.id,
    'data-cb-mission-index': String(mission.index + 1),
    'data-cb-mission-role': block.role,
    'data-cb-mission-checkpoint': checkpoint ? 'true' : 'false',
    'data-cb-mission-check': checkpoint && block.check_id ? block.check_id : '',
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      listStyle: 'none',
      padding: checkpoint ? '0.85rem 0.95rem 0.95rem 2.9rem' : '0.75rem 0.5rem 0.8rem 2.9rem',
      background: checkpoint ? 'var(--cb-lamp-soft)' : 'transparent',
      borderTop: checkpoint ? '1px solid var(--cb-lamp)' : 'none',
      maxWidth: '46rem',
      boxSizing: 'border-box'
    },
    children: [
      // The spine: a node per mission and a hairline that runs through the whole list.
      jsxs('span', {
        'aria-hidden': 'true',
        style: { position: 'absolute', left: '0.75rem', top: 0, bottom: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' },
        children: [
          jsx('span', {
            'data-cb-mission-node': String(mission.index + 1),
            style: {
              width: '1.75rem',
              height: '1.75rem',
              flex: '0 0 1.75rem',
              marginTop: checkpoint ? '0.05rem' : '0.1rem',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: checkpoint ? 'var(--cb-ochre)' : 'var(--cb-paper)',
              color: checkpoint ? 'var(--cb-paper)' : 'var(--cb-ink-soft)',
              border: checkpoint ? 'none' : '1.5px solid var(--cb-rule)',
              fontFamily: CB_SANS,
              fontVariantNumeric: 'tabular-nums',
              fontSize: CB_TYPE.caption,
              fontWeight: 600
            },
            children: String(mission.index + 1).padStart(2, '0')
          }),
          jsx('span', { style: { flex: '1 1 auto', width: '1px', background: 'var(--cb-rule)', marginTop: '0.2rem' } })
        ]
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.2rem 0.75rem' },
            children: [
              jsx('h3', {
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.25,
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: block.headline
              }),
              jsxs('span', {
                'data-cb-mission-state': checkpoint ? 'checkpoint' : 'mission',
                style: {
                  flex: '0 0 auto',
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  color: tone
                },
                children: [stateWord, ' · ', BLOCK_ROLE_COPY[block.role] || block.role]
              })
            ]
          }),
          brief
            ? jsx('p', {
                'data-cb-mission-brief': block.id,
                style: {
                  margin: 0,
                  maxWidth: '46rem',
                  fontFamily: CB_SANS,
                  fontSize: CB_TYPE.meta,
                  lineHeight: 1.5,
                  color: 'var(--cb-ink-soft)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                },
                children: brief
              })
            : null,
          jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
          // Notebook save and the pronunciation studio are the same controls every lesson view
          // offers at this block; only the prose moves to Textbook.
          jsx(BlockSaveActions, { block, checkLabels, onSaveBlock, className: 'flex flex-wrap items-center gap-1 self-start' }),
          jsx(PronunciationSeat, { block, pronunciation }),
          checkpoint
            ? jsxs('div', {
                'data-cb-mission-gate': block.check_id || 'unattached',
                style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: '0.35rem' },
                children: [
                  jsx('p', {
                    style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                    children: 'The section’s one check. Nothing on this page is locked.'
                  }),
                  checkSlot
                    ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' }, children: checkSlot })
                    : jsx('div', {
                        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                        children: 'No check could be attached to this checkpoint, so the mission stays readable and ungated.'
                      })
                ]
              })
            : null,
          // Exactly one action per mission. Everything else about this block is in Textbook.
          jsx('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.1rem' },
            children: jsx(sdk.Button, {
              variant: 'text',
              size: 'sm',
              className: 'self-start',
              'data-cb-mission-read': block.id,
              'aria-label': `Read mission ${mission.index + 1}, ${block.headline}, in Textbook`,
              onClick: () => onReadInTextbook(block.id),
              children: 'Read in Textbook'
            })
          })
        ]
      })
    ]
  })
}

/**
 * Field Quest: the same block sequence drawn as a path of small missions.
 *
 * What changes is the frame — numbering, the `Mission`/`Checkpoint` word and the course's
 * descriptive evidence counts. What does not change is the teaching truth (§2, §5): every mission
 * prints the authored `short` prose, every checkpoint holds the document's own single check node,
 * every block, check and source id is the document's, and nothing is locked. There is no XP, no
 * streak, no badge that stands in for evidence and no second grading path.
 */
function FieldQuestView({ document, sources, checkSlot, checkLabels, progress, unattached, onOpenBlock, onSaveBlock, pronunciation }) {
  const missions = questMissions(document)
  const motion = useCbMotion()
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  const progressLabel = questProgressLabel(progress)
  const checkpoints = missions.filter((mission) => mission.checkpoint).length
  const display = `${plural(missions.length, 'mission', 'missions')}, ${plural(checkpoints, 'checkpoint', 'checkpoints')}`
  const hasRecord = progress && typeof progress === 'object' && Number(progress.total_objectives) > 0
  const evidenceLine = hasRecord
    ? `${Number(progress.independent) || 0} of ${Number(progress.total_objectives)} with independent evidence${
        Number(progress.review_due) > 0 ? ` · ${Number(progress.review_due)} due for review` : ''
      }`
    : questProgressLabel(progress)
  return jsxs('div', {
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'field_quest',
    'data-cb-document': document.document_id,
    'data-cb-motion': motion.preference,
    'data-cb-quest-progress': progressLabel,
    'data-cb-quest-missions': String(missions.length),
    'data-cb-quest-checkpoints': String(checkpoints),
    style: { display: 'flex', flexDirection: 'column', gap: '0.9rem' },
    children: [
      // The section is the heading; the counts are a caption under it, never the hero. One real
      // evidence line follows, and it is the only number on the page that is not a length.
      jsxs('header', {
        'data-cb-quest-head': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', maxWidth: '46rem' },
        children: [
          jsx('h2', {
            'data-cb-quest-title': '',
            style: {
              margin: 0,
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.heading,
              fontWeight: 600,
              lineHeight: 1.1,
              letterSpacing: '-0.015em',
              color: 'var(--cb-ink)',
              maxWidth: '24ch',
              overflowWrap: 'anywhere'
            },
            children: document.section_title || 'This section'
          }),
          jsx('p', {
            'data-cb-quest-caption': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: display
          }),
          jsx('p', {
            'data-cb-quest-evidence': hasRecord ? 'recorded' : 'none',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: evidenceLine
          })
        ]
      }),
      jsx('ol', {
        'data-cb-quest-path': '',
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 0 },
        children: missions.map((mission) =>
          jsx(
            QuestMission,
            {
              mission,
              sources,
              checkLabels,
              checkSlot: mission.checkpoint ? checkSlot : null,
              onSaveBlock,
              pronunciation,
              onReadInTextbook: (blockId) => onOpenBlock && onOpenBlock(blockId)
            },
            mission.block.id
          )
        )
      }),
      unattached
    ]
  })
}

/**
 * The lesson document, rendered as one of its views.
 *
 * The document is server-owned; this component decides placement, never content. A view switch
 * re-renders the same blocks, the same ids and the same single check.
 *
 * A procedure document takes the procedure lens in Textbook: the typed header, the numbered step
 * references, the deterministic schematic and the source card. Guided and Field Quest keep their
 * existing single-block lenses over the same document.
 */
/* ── Procedure layout ───────────────────────────────────────────────────────────────────────
 * docs/VISUAL_MEDIA_PLAN.md §8. A procedure is a lens over the section's existing blocks: the
 * header is typed facts, each numbered step references one block the document already carries,
 * and the section's one check is printed once as a verification checklist. Nothing here reads
 * prose to recover a torque value, and nothing here mints a second check or a second schematic.
 *
 * The honesty rules this layout exists to keep:
 *   - a generated illustration is labelled context, never a specification, measurement, sequence
 *     or safety authority;
 *   - the only torque/clearance values on screen are the typed schematic rows and the source card
 *     they cite; the deterministic schematic is drawn from those rows, not from an image;
 *   - the stop condition is a distinct "do not proceed" callout, not decoration and never inside
 *     an illustration;
 *   - a procedure always shows its source and that source's permission status.
 */
const PROCEDURE_PERMISSION_COPY = {
  public_domain: 'Public domain',
  licensed: 'Licensed for this course',
  linked: 'Linked source — not reproduced'
}

const PROCEDURE_MEDIA_NOTE = {
  illustration: 'Context illustration — not a specification, measurement, sequence or safety authority.',
  schematic: 'Drawing made from the steps below.',
  sourced_technical: 'Sourced reference — check the cited source and its permission status.',
  narration: 'Narration — the transcript is the authoritative text.'
}

function procedureSourceMeta(sourceId, sources) {
  return (sources && sources[sourceId]) || null
}

/** Tools and parts: typed header lists, printed as written, never inferred from the prose. */
function ProcedureHeader({ procedure, sectionTitle }) {
  const tools = Array.isArray(procedure.tools) ? procedure.tools : []
  const parts = Array.isArray(procedure.parts) ? procedure.parts : []
  const columns = []
  if (tools.length > 0) {
    columns.push(
      jsxs('div', {
        'data-cb-procedure-tools': String(tools.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Tools' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: tools.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-tool-${index}`))
          })
        ]
      }, 'tools')
    )
  }
  if (parts.length > 0) {
    columns.push(
      jsxs('div', {
        'data-cb-procedure-parts': String(parts.length),
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: '12rem', flex: '1 1 12rem' },
        children: [
          jsx(DeskLabel, { children: 'Parts' }),
          jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: parts.map((item, index) => jsx('li', { children: item }, `${sectionTitle}-part-${index}`))
          })
        ]
      }, 'parts')
    )
  }
  return jsxs('section', {
    'data-cb-procedure-header': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.6rem',
      padding: '0.85rem 1rem 0.95rem',
      background: 'var(--cb-paper-raised)',
      border: '1px solid var(--cb-rule)',
      maxWidth: '48rem'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
        children: [
          jsx(DeskLabel, { children: 'Procedure' }),
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: 'Ordered steps' })
        ]
      }),
      columns.length > 0
        ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '1rem' }, children: columns })
        : jsx('p', {
            style: { margin: 0, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
            children: 'The author listed no tools or parts for this procedure.'
          })
    ]
  })
}

/**
 * The stop condition, as a callout that cannot be mistaken for a step or a generated image.
 *
 * `role="note"` and the coral rule are the signal; the hazards are the author's own strings. The
 * callout is not an illustration and carries no image.
 */
function ProcedureHazardCallout({ hazards, stopCondition }) {
  const list = Array.isArray(hazards) ? hazards : []
  return jsxs('section', {
    role: 'note',
    'aria-label': 'Do not proceed',
    'data-cb-procedure-hazard': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      margin: '0 0 0.25rem',
      padding: '0.7rem 0.85rem 0.75rem 0.9rem',
      borderLeft: '1px solid var(--cb-coral)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsx('div', {
        style: {
          fontSize: CB_TYPE.caption,
          fontWeight: 700,
          letterSpacing: '0.01em',
          color: 'var(--cb-coral)'
        },
        children: 'Do not continue'
      }),
      list.length > 0
        ? jsx('ul', {
            style: { margin: 0, paddingLeft: '1.1rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' },
            children: list.map((item, index) => jsx('li', { children: item }, `hazard-${index}`))
          })
        : null,
      jsxs('p', {
        'data-cb-procedure-stop': '',
        style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.6, color: 'var(--cb-ink)' },
        children: [jsx('strong', { children: 'Stop if: ' }), stopCondition]
      })
    ]
  })
}

/**
 * A torque or sequence schematic, deterministic from typed rows.
 *
 * The rows are the authority and are always printed, sorted by the backend's own `row` then
 * label rule. An attached SVG artifact is this same drawing and is shown through the one
 * `MediaSegment` preview; when that artifact cannot be reached the rows remain, so the value is
 * never lost behind an image.
 */
function ProcedureSchematic({ schematic, sources, blockId }) {
  if (!schematic) return null
  const rows = (Array.isArray(schematic.rows) ? schematic.rows : [])
    .slice()
    .sort((left, right) => (Number(left.row) || 0) - (Number(right.row) || 0) || String(left.label).localeCompare(String(right.label)))
  const source = procedureSourceMeta(schematic.source_id, sources)
  return jsxs('section', {
    'data-cb-procedure-schematic': '',
    'aria-labelledby': `cb-procedure-schematic-${blockId || 'document'}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.4rem',
      padding: '0.7rem 0.85rem',
      border: '1px solid var(--cb-rule)',
      background: 'var(--cb-paper)',
      maxWidth: '48rem'
    },
    children: [
      jsx('h3', {
        id: `cb-procedure-schematic-${blockId || 'document'}`,
        style: { margin: 0, fontSize: CB_TYPE.body, fontWeight: 600, color: 'var(--cb-ink)' },
        children: schematic.title
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, letterSpacing: '0.01em', color: 'var(--cb-ink-soft)' },
        children: 'Drawing from the steps below'
      }),
      jsx('table', {
        'data-cb-procedure-rows': String(rows.length),
        style: { borderCollapse: 'collapse', width: '100%', fontSize: CB_TYPE.meta, color: 'var(--cb-ink)' },
        children: jsxs('tbody', {
          children: rows.map((row, index) =>
            jsxs(
              'tr',
              {
                style: { borderTop: index === 0 ? 'none' : '1px solid var(--cb-rule)' },
                children: [
                  jsx('th', {
                    scope: 'row',
                    style: { textAlign: 'left', padding: '0.25rem 0.5rem 0.25rem 0', fontWeight: 500 },
                    children: row.label
                  }),
                  jsx('td', {
                    style: { textAlign: 'right', padding: '0.25rem 0', fontVariantNumeric: 'tabular-nums' },
                    children: row.value
                  })
                ]
              },
              `${blockId || 'schematic'}-row-${index}`
            )
          )
        })
      }),
      jsx('p', {
        style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
        children: schematic.text_equivalent
      }),
      schematic.source_id
        ? jsx('p', {
            'data-cb-procedure-schematic-source': schematic.source_id,
            style: { margin: 0, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `Facts from ${(source && source.title) || schematic.source_id}`
          })
        : null,
      schematic.artifact_id
        ? jsx(BlockMedia, {
            media: {
              artifact_id: schematic.artifact_id,
              role: 'schematic',
              label: 'Drawing made from these steps.',
              text_equivalent: schematic.text_equivalent,
              purpose: schematic.title
            },
            blockId: blockId || 'procedure',
            ordinal: 'schematic'
          })
        : null
    ]
  })
}

/** The cited manual with its permission status; never an unlabelled link. */
function ProcedureSourceCard({ source, sources }) {
  const meta = procedureSourceMeta(source.source_id, sources)
  const permission = PROCEDURE_PERMISSION_COPY[source.permission] || source.permission
  return jsxs('section', {
    'data-cb-procedure-source': source.source_id,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
      padding: '0.65rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      maxWidth: '48rem'
    },
    children: [
      jsx(DeskLabel, { children: 'Source' }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
        children: [
          jsx('span', { style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' }, children: (meta && meta.title) || source.source_id }),
          jsx(sdk.Badge, { size: 'xs', variant: source.permission === 'licensed' ? 'muted' : 'outline', children: permission })
        ]
      }),
      meta && meta.url
        ? jsx('a', {
            href: meta.url,
            rel: 'noreferrer noopener',
            target: '_blank',
            style: { fontSize: CB_TYPE.meta, color: 'var(--cb-accent)', overflowWrap: 'anywhere' },
            children: meta.url
          })
        : null,
      jsx('p', {
        style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: 'Torque values and sequence come from this reference and the structured schematic; the illustration is context only.'
      })
    ]
  })
}

/** One numbered step. The action is the referenced block's own prose; the check is the author's step cue. */
function ProcedureStepCard({ step, index, block, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  const body = withoutCheckLabels(block.deep, checkLabels)
  const media = (block.media || []).map((item, ordinal) => {
    const note = PROCEDURE_MEDIA_NOTE[item.role]
    return jsxs(
      'div',
      {
        'data-cb-procedure-media': item.role || 'media',
        style: { display: 'flex', flexDirection: 'column', gap: '0.25rem' },
        children: [
          note
            ? jsx('p', {
                'data-cb-procedure-media-note': item.role || '',
                style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: item.role === 'illustration' ? 'var(--cb-ochre)' : 'var(--cb-ink-soft)' },
                children: note
              })
            : null,
          jsx(BlockMedia, { media: item, blockId: block.id, ordinal })
        ]
      },
      `${block.id}-procedure-media-${ordinal}`
    )
  })
  return jsxs('li', {
    'data-cb-procedure-step': String(index + 1),
    'data-cb-block': block.id,
    'data-cb-role': block.role,
    tabIndex: -1,
    style: {
      display: 'flex',
      gap: '0.7rem',
      padding: '0.7rem 0 0.7rem 0.85rem',
      borderLeft: '2px solid var(--cb-rule)',
      listStyle: 'none',
      userSelect: 'text',
      WebkitUserSelect: 'text'
    },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: {
          fontSize: CB_TYPE.meta,
          fontWeight: 700,
          fontVariantNumeric: 'tabular-nums',
          color: 'var(--cb-accent)',
          minWidth: '1.4rem'
        },
        children: String(index + 1).padStart(2, '0')
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0, flex: '1 1 auto' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.4rem' },
            children: [
              jsx('span', { className: 'sr-only', children: `Step ${index + 1}` }),
              jsx('h3', {
                style: { margin: 0, fontSize: CB_TYPE.body, fontWeight: 600, lineHeight: 1.35, color: 'var(--cb-ink)' },
                children: block.headline
              })
            ]
          }),
          body
            ? jsx(ProseText, { style: { maxWidth: '44rem' }, text: body })
            : null,
          step.check
            ? jsxs('p', {
                'data-cb-procedure-step-check': block.id,
                style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
                children: [jsx('strong', { children: 'Check: ' }), step.check]
              })
            : null,
          media.length > 0 ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' }, children: media }) : null,
          jsx(PronunciationSeat, { block, pronunciation }),
          jsx(BlockSourceChips, { ids: block.source_ids, index: sources }),
          jsx(BlockSaveActions, { block, checkLabels, onSaveBlock }),
          checkSlot
            ? jsx('div', { style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: '0.15rem' }, 'data-cb-block-check': block.id, children: checkSlot })
            : null
        ]
      })
    ]
  })
}

/**
 * The procedure lens: header, hazard callout, numbered steps, one verification checklist, source.
 *
 * Blocks the author did not place in `steps` are still taught: they render after the numbered
 * list in the ordinary textbook frame, so a procedure can never silently hide authored material.
 */
function ProcedureDocument({ document, sources, checkSlot, checkLabels, onSaveBlock, pronunciation }) {
  const procedure = document.procedure
  const blocks = document.blocks || []
  const byId = {}
  blocks.forEach((block) => {
    byId[block.id] = block
  })
  const steps = (procedure.steps || [])
    .map((step, index) => ({ step, index, block: byId[step.block_id] }))
    .filter((entry) => Boolean(entry.block))
  const placed = new Set(steps.map((entry) => entry.block.id))
  const leftover = blocks.filter((block) => !placed.has(block.id))
  const checkId = document.check_id
  const attachedIndex = checkId ? steps.findIndex((entry) => entry.block.check_id === checkId) : -1
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'procedure',
    'data-cb-document': document.document_id,
    'data-cb-procedure': '',
    children: [
      jsx(ProcedureHeader, { procedure, sectionTitle: document.section_title }),
      jsx(ProcedureHazardCallout, { hazards: procedure.hazards, stopCondition: procedure.stop_condition }),
      jsx(ProcedureSchematic, { schematic: procedure.schematic, sources, blockId: document.document_id }),
      jsx('ol', {
        'data-cb-procedure-steps': String(steps.length),
        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.2rem', maxWidth: '48rem' },
        children: steps.map((entry) =>
          jsx(
            ProcedureStepCard,
            {
              step: entry.step,
              index: entry.index,
              block: entry.block,
              sources,
              checkLabels,
              onSaveBlock,
              pronunciation,
              checkSlot: attachedIndex === entry.index ? checkSlot : null
            },
            entry.block.id
          )
        )
      }),
      checkId && checkSlot && attachedIndex < 0
        ? jsxs('section', {
            'data-cb-procedure-verification': '',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '48rem' },
            children: [jsx(DeskLabel, { children: 'Verification checklist' }), checkSlot]
          })
        : attachedIndex >= 0
          ? jsxs('section', {
              'data-cb-procedure-verification': 'attached',
              style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '48rem' },
              children: [
                jsx(DeskLabel, { children: 'Verification checklist' }),
                jsx('p', {
                  style: { margin: 0, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                  children: 'The checklist is on the step above. It is the section’s one check, not an extra quiz.'
                })
              ]
            })
          : null,
      leftover.length > 0
        ? jsxs('div', {
            'data-cb-procedure-unplaced': String(leftover.length),
            style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', maxWidth: '48rem' },
            children: [
              jsx(DeskLabel, { children: 'Also in this lesson' }),
              ...leftover.map((block) =>
                jsx(TextbookBlock, { block, sources, checkSlot: null, checkLabels, onSaveBlock, pronunciation }, block.id)
              )
            ]
          })
        : null,
      jsx(ProcedureSourceCard, { source: procedure.source, sources })
    ]
  })
}

function lessonTextAttrs(document) {
  // H-18: lang and direction are properties of the text. Every view renders the same document,
  // so every view root carries the same two attributes; absence means the page never recorded a
  // locale and no direction is invented.
  const attrs = {}
  if (document && (document.direction === 'rtl' || document.direction === 'ltr')) {
    attrs.dir = document.direction
  }
  if (document && typeof document.lang === 'string' && document.lang) {
    attrs.lang = document.lang
  }
  return attrs
}

/* ---------------------------------------------------------------------------------------------
 * H-149 · the lesson player.
 *
 * The learner surface is a bounded session over the section's own document: one concept per step,
 * one response (the document's one check), immediate corrective feedback, and a close that returns
 * to the path with the recorded result. Nothing here authors content: the steps are the document's
 * blocks in authored order, the response is the same `check.get` the reference views mount, and
 * every number on the close plate is read from the enrollment row.
 * ------------------------------------------------------------------------------------------- */

/** The player's steps: the document's blocks, with the section's one check on the block that carries it. */
function playerSteps(document) {
  const blocks = (document && document.blocks) || []
  const checkId = document ? document.check_id : null
  const carried = blocks.some((block) => Boolean(checkId && block.check_id === checkId))
  return blocks.map((block, index) => ({
    index,
    total: blocks.length,
    block,
    // A document whose one check is not attached to a block still gets its response: the last
    // step hosts it rather than dropping the check from the session.
    check: Boolean(checkId && (block.check_id === checkId || (!carried && index === blocks.length - 1)))
  }))
}

/** How many distinct checks this section's document declares. One is the normal case. */
function playerCheckCount(document) {
  const blocks = (document && document.blocks) || []
  const ids = new Set()
  for (const block of blocks) if (block && block.check_id) ids.add(block.check_id)
  if (ids.size === 0 && document && document.check_id) ids.add(document.check_id)
  return ids.size
}

/**
 * The one concept on a step: the authored `short` when the document has one, otherwise the first
 * paragraph of the authored `deep` prose. The clip is declared to the learner and Textbook keeps
 * the full text, so the player never silently drops authored material.
 */
function playerConcept(block, checkLabels) {
  const short = withoutCheckLabels(block.short, checkLabels)
  if (short) return { text: short, clipped: false }
  const deep = withoutCheckLabels(block.deep, checkLabels) || ''
  const first = String(deep).split(/\n\s*\n/)[0].trim()
  return { text: first, clipped: Boolean(first) && first.length < String(deep).trim().length }
}

/**
 * The player's verdict card.
 *
 * Two verdicts only — `Correct` and `Not quite` — always as words, with the learner's own answer in
 * context and the backend's own criterion text as the reason. The correct answer is not invented:
 * the contract returns criteria and a next action, not a reference answer, so the card prints what
 * the backend recorded and says plainly that a retry is free.
 */
function PlayerVerdict({ result, criteria, checklist, answer }) {
  const motion = useCbMotion()
  // The verdict beat is caused by a real graded result: it cannot start before the backend answers,
  // because the surface only mounts once `result` exists. 160 ms, opacity + 2 px, once.
  const verdictBeat = useCbSettle(motion, { beat: 'verdict', props: 'opacity, transform', from: 'translateY(2px)', fromOpacity: 0.9 })
  const passed = Boolean(result) && (result.verdict === 'pass' || result.verdict === 'overridden')
  const rows = (criteria || []).filter(Boolean)
  const unmet = rows.filter((row) => !row.met)
  const met = rows.filter((row) => row.met && row.observed)
  const override = Boolean(result) && result.verdict === 'overridden'
  const selfReported = Boolean(result) && result.evidence_class === 'self_reported'
  const why = passed ? verdictTakeaway(result, criteria) : nextActionCopy(result)
  const rule = unmet.length > 0 ? String(unmet[0].observed || unmet[0].id || '').trim() : null
  const answerText = Array.isArray(answer) ? answer.join('; ') : String(answer || '').trim()
  return jsxs('div', {
    'data-cb-player-feedback': passed ? 'correct' : 'not_quite',
    'data-cb-state': passed ? 'correct' : 'not_quite',
    'data-cb-player-beat': motion.reduced ? 'static' : 'verdict',
    style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', maxWidth: CB_MEASURE, ...verdictBeat },
    children: [
      jsx(EvidenceChip, { value: result && result.evidence_class ? result.evidence_class : null }),
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: '0.4rem' },
        children: [
          jsx(sdk.Codicon, { name: passed ? 'pass-filled' : 'circle-slash', size: CB_ICON_UI }),
          jsx('strong', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.body, fontWeight: 700, color: 'var(--cb-ink)' },
            children: override ? 'Recorded — not a pass' : passed ? 'Correct' : 'Not quite'
          })
        ]
      }),
      answerText
        ? jsxs('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
            'data-cb-player-answer': '',
            children: ['You answered: ', jsx('span', { style: { color: 'var(--cb-ink)' }, children: answerText })]
          })
        : null,
      selfReported
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
            children: SELF_REPORTED_CONFIRM_COPY
          })
        : null,
      why
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
            'data-cb-player-why': '',
            children: why
          })
        : null,
      !passed && rule
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
            'data-cb-player-rule': '',
            children: `The part that did not hold: ${rule}`
          })
        : null,
      !passed && met.length > 0
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: `What you did show: ${met.slice(0, 2).map((row) => String(row.observed).trim()).join('; ')}.`
          })
        : null,
      !passed && checklist && checklist.length > 0
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: 'Tick the remaining steps and check again. Nothing here is counted against you.'
          })
        : !passed
          ? jsx('p', {
              style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
              children: 'Try again with a different answer. The retry is free and nothing is counted against you.'
            })
          : null
    ]
  })
}

/**
 * The close: the section is finished, and every number is the enrollment row's own count.
 *
 * `recorded` is the session's own evidence fact, passed from the player: a verdict exists only
 * after an attempt was committed. When no verdict exists — a stop whose document carries no check
 * is finished without an attempt — the close must not claim a result. Item 39.
 */
function PlayerClose({ section, progress, onBack, onReadSection, evidenceClass, recorded = false, companionEnabled = true }) {
  const motion = useCbMotion()
  // Completion is one beat, once: the result mark settles in 600 ms or not at all. Nothing is
  // celebrated, counted up or replayed, and the title is readable on the first frame.
  const completeBeat = useCbSettle(motion, { beat: 'complete', props: 'opacity, transform', from: 'scale(0.995)', fromOpacity: 0.88 })
  // The learner's own pet, through the supported seam only. Absent, disabled, still loading and
  // unreachable all resolve to no companion; no placeholder face is invented (H-176/H-177).
  const companion = useStudyCompanion(companionEnabled && !(motion && motion.reduced))
  const ordinal = section && section.ordinal ? String(section.ordinal) : null
  const summary = progress || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  const independent = Math.max(0, Math.min(total, Number(summary.independent || 0)))
  const due = Math.max(0, Number(summary.review_due || 0))
  const facts = []
  if (total > 0) facts.push(`${independent} of ${total} with independent evidence`)
  if (total > 0) facts.push(due > 0 ? `${due} to review` : 'Nothing due for review')
  return jsxs('section', {
    'data-cb-player-close': '',
    'data-cb-state': 'complete',
    'data-cb-player-beat': motion.reduced ? 'static' : 'complete',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      maxWidth: CB_MEASURE,
      padding: '1.25rem 0',
      ...completeBeat
    },
    children: [
      companion
        ? jsx('div', {
            'data-cb-player-gate': 'companion',
            style: { display: 'flex', alignItems: 'center', gap: '0.5rem' },
            children: jsx(StudyCompanion, { info: companion, size: 40, label: 'companion' })
          })
        : null,
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: CB_TYPE.display,
          fontWeight: 600,
          lineHeight: 1.1,
          letterSpacing: '-0.015em',
          color: 'var(--cb-ink)',
          overflowWrap: 'anywhere'
        },
        children: ordinal ? `You finished Section ${ordinal}` : 'You finished this section'
      }),
      jsx(EvidenceChip, { value: evidenceClass || null }),
      facts.length > 0
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.lead, lineHeight: 1.5, color: 'var(--cb-ink)' },
            'data-cb-player-close-facts': '',
            children: facts.join(' · ')
          })
        : jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.lead, lineHeight: 1.5, color: 'var(--cb-ink)' },
            'data-cb-player-close-facts': '',
            'data-cb-player-close-recorded': recorded ? 'true' : 'false',
            children: recorded
              ? 'The result is recorded on this profile.'
              : 'Nothing was recorded for this stop.'
          }),
      jsx('p', {
        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        'data-cb-player-close-trail': recorded ? 'recorded' : 'open',
        children: recorded
          ? 'The trail shows this stop as recorded, and which stop is next. Nothing is lost when you leave.'
          : 'The trail still shows this stop as open. Nothing is lost, and you can come back to it.'
      }),
      jsxs('div', {
        'data-cb-player-close-actions': '',
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
        children: [
          jsx(CbAction, {
            'data-cb-player-close-primary': '',
            variant: 'primary',
            onClick: onBack,
            children: 'Return to the trail'
          }),
          onReadSection
            ? jsx(sdk.Button, {
                'data-cb-player-close-textbook': '',
                variant: 'secondary',
                size: 'sm',
                onClick: onReadSection,
                children: 'Read the section'
              })
            : null
        ]
      })
    ]
  })
}

/**
 * The player surface.
 *
 * One footer, one primary: `Check` becomes `Continue`, then `Finish` on the last step, then the
 * close. Enter runs the same action as the footer; a textarea keeps Enter for its own newlines.
 */
function LessonPlayer({
  document,
  sources,
  checkSlot,
  checkLabels,
  section,
  progress,
  playerState,
  playerController,
  onExit,
  onReload,
  onReadSection,
  onSaveBlock,
  pronunciation,
  takeHome
}) {
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  const steps = playerSteps(document)
  const [index, setIndex] = useState(0)
  const [closed, setClosed] = useState(false)
  const state = playerState || { phase: 'awaiting_input', canCheck: false, verdict: null }
  if (steps.length === 0) return null
  const current = steps[Math.min(index, steps.length - 1)]
  const last = current.index >= steps.length - 1
  const concept = playerConcept(current.block, checkLabels)
  const call = (name) => {
    const api = playerController && playerController.current
    if (api && typeof api[name] === 'function') api[name]()
  }
  const advance = () => {
    if (last) setClosed(true)
    else setIndex(current.index + 1)
  }
  if (closed) {
    return jsx(PlayerClose, {
      section,
      progress,
      onBack: onExit,
      onReadSection,
      // Only a *recorded* class belongs on the close. A stop whose document carries no check is
      // finished without an attempt, so `nextEvidenceClass` (a prediction) must not become the
      // claim that something was earned. With nothing recorded the close renders without a chip.
      evidenceClass: state.evidenceClass || null,
      // A verdict exists only after an attempt committed, so it is the session's own evidence
      // fact: with no verdict the close says plainly that nothing was recorded (item 39).
      recorded: Boolean(state.verdict)
    })
  }

  const passed = state.verdict === 'pass' || state.verdict === 'overridden'
  let action
  if (!current.check) {
    action = { label: last ? 'Finish' : 'Continue', run: advance, disabled: false }
  } else if (state.phase === 'submitting') {
    action = { label: 'Checking', run: null, disabled: true }
  } else if (state.phase === 'graded' || state.phase === 'overridden') {
    action = passed
      ? { label: last ? 'Finish' : 'Continue', run: advance, disabled: false }
      : { label: 'Try again', run: () => call('newExample'), disabled: false }
  } else if (state.phase === 'needs_retry') {
    action = { label: 'Retry grading', run: () => call('retryGrading'), disabled: false }
  } else if (state.phase === 'stale') {
    action = { label: 'Read the current check', run: onReload || advance, disabled: false }
  } else {
    action = { label: 'Check', run: () => call('submit'), disabled: !state.canCheck }
  }
  const onKeyDown = (event) => {
    if (event.key !== 'Enter' || event.shiftKey) return
    const target = event.target
    // Item 40: Enter keeps the meaning of whatever has focus. A link, a disclosure summary and a
    // role="button" element all handle Enter themselves; advancing the step as well would run two
    // actions from one press.
    if (
      target &&
      typeof target.closest === 'function' &&
      target.closest('button, a[href], summary, [role="button"], textarea, input, select, [contenteditable="true"]')
    ) return
    if (action.disabled || !action.run) return
    event.preventDefault()
    action.run()
  }
  const ordinal = section && section.ordinal ? String(section.ordinal) : null
  // Item 42: one denominator for the whole lesson surface. The session's own step count is the
  // only total a learner can act on here ("how much of this stop is left"), and it is the number
  // the step readout advances. The course's objective total is a trail fact and is printed once,
  // as "Section n of m" — printing it here too gave one session two disagreeing totals.
  const stopTotal = steps.length > 0 ? String(steps.length) : null
  const stopLabel = ordinal && stopTotal ? `STOP ${ordinal} OF ${stopTotal}` : ordinal ? `STOP ${ordinal}` : 'STOP'
  // One objective sentence, composed only from recorded fields: the section's own evidence target,
  // in learner words. A section that records no target gets the title alone rather than a slogan.
  const objective =
    section && section.evidence_target
      ? `By the end of this stop you can show: ${String(learnerEvidenceTarget(section.evidence_target) || '').toLowerCase()}.`
      : null
  return jsxs('div', {
    'data-cb-lesson-view': 'player',
    'data-cb-player': '',
    'data-cb-document': document.document_id,
    'data-cb-play-heading-tier': 'prose',
    onKeyDown,
    style: { display: 'flex', flexDirection: 'column', gap: '0.85rem', minWidth: 0 },
    ...lessonTextAttrs(document),
    children: [
      jsxs('header', {
        'data-cb-player-bar': '',
        'data-cb-player-stop': `${ordinal || ''}/${stopTotal || ''}`,
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: '0.3rem',
          paddingBottom: '0.6rem',
          borderBottom: '1px solid var(--cb-rule)',
          minWidth: 0
        },
        children: [
          jsxs('div', {
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.35rem 0.9rem',
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              color: 'var(--cb-ink-soft)'
            },
            children: [
              jsx('span', {
                'data-cb-player-section': ordinal || 'section',
                style: { fontWeight: 600, letterSpacing: '0.06em', color: 'var(--cb-ink)' },
                children: stopLabel
              }),
              jsxs('span', {
                'data-cb-player-mode': 'game',
                style: { display: 'inline-flex', alignItems: 'center', gap: '0.35rem' },
                children: [jsx(ModeDot, { mode: 'game' }), 'Game']
              }),
              jsx('span', {
                'data-cb-player-step': `${current.index + 1}/${steps.length}`,
                'aria-live': 'polite',
                style: { fontVariantNumeric: 'tabular-nums', marginLeft: 'auto' },
                children: `Step ${current.index + 1} of ${steps.length}`
              }),
              jsx(sdk.Button, {
                'data-cb-player-exit': '',
                variant: 'text',
                size: 'sm',
                onClick: onExit,
                children: 'Exit'
              })
            ]
          }),
          section && section.title
            ? jsx('h2', {
                'data-cb-player-title': '',
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.15,
                  letterSpacing: '-0.015em',
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: section.title
              })
            : null,
          objective
            ? jsx('p', {
                'data-cb-player-objective': '',
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: objective
              })
            : null
        ]
      }),
      jsxs('section', {
        'data-cb-player-step-block': current.block.id,
        'data-cb-player-role': current.block.role,
        'aria-labelledby': `cb-play-headline-${current.block.id}`,
        style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0 },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem 0.6rem', minWidth: 0 },
            children: [
              jsx('h3', {
                id: `cb-play-headline-${current.block.id}`,
                style: {
                  margin: 0,
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.heading,
                  fontWeight: 600,
                  lineHeight: 1.2,
                  letterSpacing: '-0.01em',
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: current.block.headline
              }),
              jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, lineHeight: 1.3, color: 'var(--cb-ink-soft)' },
                children: BLOCK_ROLE_COPY[current.block.role] || current.block.role
              })
            ]
          }),
          concept.text
            ? jsx(ProseText, {
                'data-cb-play-concept': current.block.id,
                style: {
                  maxWidth: CB_MEASURE,
                  fontFamily: CB_SERIF,
                  fontSize: phone ? CB_TYPE.body : CB_TYPE.lead,
                  lineHeight: 1.6,
                  color: 'var(--cb-ink)'
                },
                text: concept.text
              })
            : null,
          concept.clipped
            ? jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                children: 'First paragraph of this step. The full text is in Textbook.'
              })
            : null,
          (current.block.media || []).map((media, ordinalIndex) =>
            jsx(BlockMedia, { media, blockId: current.block.id, ordinal: ordinalIndex }, `${current.block.id}-media-${ordinalIndex}`)
          ),
          jsx(PronunciationSeat, { block: current.block, pronunciation }),
          jsx(BlockSourceChips, { ids: current.block.source_ids, index: sources }),
          onSaveBlock ? jsx(BlockSaveActions, { block: current.block, checkLabels, onSaveBlock }) : null,
          current.check && checkSlot
            ? jsx(CheckPanelFrame, {
                kind: 'check',
                label: 'Your turn',
                children: jsx('div', {
                  className: 'flex flex-col gap-2',
                  'data-cb-block-check': current.block.id,
                  children: checkSlot
                })
              })
            : null
        ]
      }),
      jsxs('footer', {
        'data-cb-player-footer': '',
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.5rem 0.75rem',
          paddingTop: '0.65rem',
          borderTop: '1px solid var(--cb-rule)'
        },
        children: [
          jsx(CbAction, {
            'data-cb-player-primary': action.label,
            variant: 'primary',
            disabled: action.disabled,
            pending: state.phase === 'submitting',
            onClick: action.run || undefined,
            children: action.label
          }),
          jsx('span', {
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.4, color: 'var(--cb-ink-soft)' },
            children: action.disabled && state.phase === 'awaiting_input' ? 'Answer above, then press Enter.' : 'Enter does the same.'
          }),
          // H-149: the take-with-you action lives in the player's own footer row, so every lesson
          // mode offers it while the player keeps exactly one footer.
          takeHome
            ? jsx(TakeThisWithYou, { ...takeHome })
            : null
        ]
      })
    ]
  })
}

function LessonDocumentView({ document, view, sources, checkSlot, checkLabels, progress, focusBlockId, onOpenBlock, onSaveBlock, pronunciation, player }) {
  const blocks = (document && document.blocks) || []
  const labels = Array.isArray(checkLabels) ? checkLabels : []
  const [step, setStep] = useState(0)
  const rootRef = useRef(null)
  const focusIndex = focusBlockId ? blocks.findIndex((block) => block.id === focusBlockId) : -1
  // A mission can hand the reader to the same block in another view. The ids are the document's,
  // so the handoff sets Guided's step by id and moves focus to that block rather than guessing an
  // offset; nothing about the block, its check or its sources is re-created by the switch.
  useEffect(() => {
    if (focusIndex < 0) return
    if (view === 'guided' && focusIndex !== step) {
      setStep(focusIndex)
      return
    }
    const root = rootRef.current
    if (!root || typeof root.querySelector !== 'function') return
    const target = root.querySelector(`[data-cb-block="${focusBlockId}"]`)
    if (target && typeof target.focus === 'function') target.focus()
  }, [focusBlockId, focusIndex, view, step])
  if (blocks.length === 0) {
    // H-174/H-183: an approved lesson page with no blocks is incomplete, not a chat prompt. The
    // page is written by Coursebook from the approved plan; a teaching turn adds runtime segments,
    // it does not write the page.
    return jsx(EmptyState, {
      title: 'This lesson page has no blocks yet',
      description:
        (document && document.view_note) ||
        'The page exists, but it carries no teaching blocks yet. Writing it again from Plan replaces this placeholder.'
    })
  }
  const checkId = document.check_id
  const attached = checkId ? blocks.findIndex((block) => block.check_id === checkId) : -1
  const unattached = attached < 0 && checkSlot
    ? jsxs('div', {
        className: 'flex flex-col gap-2',
        children: [jsx(CbLabel, { children: 'Check' }), checkSlot]
      })
    : null

  if (document.procedure && view === 'textbook') {
    return jsx(ProcedureDocument, {
      document,
      sources,
      checkSlot,
      checkLabels: labels,
      onSaveBlock,
      pronunciation
    })
  }

  if (view === 'field_quest' && document.views && document.views.field_quest) {
    return jsx(FieldQuestView, {
      document,
      sources,
      checkSlot,
      checkLabels: labels,
      progress,
      unattached,
      onOpenBlock,
      onSaveBlock,
      pronunciation
    })
  }

  if (view === 'player' && player) {
    return jsx(
      LessonPlayer,
      {
        document,
        sources,
        checkSlot: player.slot || checkSlot,
        checkLabels: labels,
        section: player.section,
        progress,
        playerState: player.state,
        playerController: player.controller,
        onExit: player.onExit,
        onReload: player.onReload,
        onReadSection: player.onReadSection,
        takeHome: player.takeHome,
        onSaveBlock,
        pronunciation
      },
      document.document_id
    )
  }

  if (view === 'guided' && document.views && document.views.guided) {
    const current = Math.min(step, blocks.length - 1)
    const block = blocks[current]
    return jsxs('div', {
      ref: rootRef,
      className: 'flex flex-col gap-3',
      ...lessonTextAttrs(document),
      'data-cb-lesson-view': 'guided',
      'data-cb-document': document.document_id,
      children: [
        jsx(GuidedBlock, {
          block,
          index: current,
          total: blocks.length,
          sources,
          checkLabels: labels,
          checkSlot: block.check_id && block.check_id === checkId ? checkSlot : null,
          onBack: () => setStep(Math.max(0, current - 1)),
          onNext: () => setStep(Math.min(blocks.length - 1, current + 1)),
          onSaveBlock,
          pronunciation
        }),
        unattached
      ]
    })
  }

  return jsxs('div', {
    ref: rootRef,
    className: 'flex flex-col gap-3',
    ...lessonTextAttrs(document),
    'data-cb-lesson-view': 'textbook',
    'data-cb-document': document.document_id,
    children: [
      jsx('div', {
        className: 'flex flex-col',
        children: blocks.map((block, index) =>
          jsx(
            TextbookBlock,
            {
              block,
              lede: index === 0,
              sources,
              checkLabels: labels,
              checkSlot: attached >= 0 && block.check_id === checkId ? checkSlot : null,
              onSaveBlock,
              pronunciation
            },
            block.id
          )
        )
      }),
      unattached
    ]
  })
}

/**
 * H-174: what actually backs a section page.
 *
 * A section is not "empty because the learner has not said anything". Lesson pages are authored by
 * the harness's lessons job (`run_lesson_job` -> `_enforce_lesson_document`) and served by
 * `lesson.page`; a bound chat may add runtime segments, but it is not the authoring path. This
 * model answers one question — is there a readable approved page for this section, and if not, who
 * owns it — so the hero, the section body and the empty state cannot give three different reasons.
 *
 * States, in resolution order:
 *   readable    -- the served document has teaching blocks; the player is the surface
 *   reading     -- the outline or the page read has not settled yet
 *   unreadable  -- the page or plan read failed; nothing was lost, the read just did not finish
 *   no_page     -- a caller that cannot see the plan: the page is missing and the plan is unknown
 *   unapproved  -- the plan is missing or still a draft; the lessons job cannot run yet
 *   failed      -- the lessons job stopped; its typed error and a retry are the next step
 *   running     -- the lessons job is queued or writing; the page is not there yet
 *   incomplete  -- a document that carries no blocks (an approved plan, or a caller with no plan)
 *   not_started -- the plan is approved and the lessons job has not run
 */
const LESSON_JOB_LIVE_STATES = new Set(['queued', 'running', 'leased', 'pending', 'retrying'])

function lessonsJobFrom(jobs) {
  const rows = jobs && Array.isArray(jobs.jobs) ? jobs.jobs : []
  return rows.find((job) => job && ((job.brief || {}).stage || 'plan') === 'lessons') || null
}

function lessonJobError(job) {
  if (!job || !job.error) return null
  const code = job.error.code ? `${job.error.code}: ` : ''
  return `${code}${job.error.message || 'No reason was recorded.'}`
}

function lessonReadiness({ outline, page, jobs, pageStatus, planStatus } = {}) {
  // Callers that cannot see the plan (a standalone section render) pass no `outline` at all;
  // production passes `outline.data` and `outline.status`, so "loading" and "no plan" stay distinct.
  const planProvided = outline !== undefined
  const planLoading = planStatus === 'loading'
  const plan = (outline && outline.plan) || null
  const planApproved = Boolean(plan && plan.state === 'approved')
  const document = (page && page.document) || null
  const blocks = document && Array.isArray(document.blocks) ? document.blocks : []
  // A backend that predates the v8 document projection answers with runtime segments only. Those
  // segments are real teaching content, so they count as a readable page rather than as an empty one.
  const segments = page && Array.isArray(page.segments) ? page.segments : []
  const job = lessonsJobFrom(jobs)
  const jobState = (job && job.state) || null
  const jobLive = Boolean(job && LESSON_JOB_LIVE_STATES.has(jobState))
  const jobFailed = Boolean(
    job && ['failed', 'cancelled', 'interrupted_requires_retry'].includes(jobState)
  )
  const error = lessonJobError(job)
  const base = {
    plan,
    planApproved,
    job,
    jobState,
    document,
    blockCount: blocks.length,
    segmentCount: segments.length,
    error,
    // H-183: the typed reason is evidence, not learner copy. The readiness panel puts this behind
    // its own `Technical detail` disclosure; no default sentence carries the code.
    technical: error,
    // A job that settles as completed but wrote no lessons for this plan version is not running
    // and did not fail: it is the `not_started`/`incomplete` fact the plan surface already reports.
    lessonsReported: Number((job && job.checkpoint && job.checkpoint.lessons) || 0)
  }

  if (blocks.length > 0 || (!document && segments.length > 0)) {
    return { ...base, state: 'readable', headline: null, detail: null, action: null, secondary: null }
  }
  if (pageStatus === 'error') {
    return {
      ...base,
      state: 'unreadable',
      headline: 'The lesson page could not be read',
      detail: 'Nothing was lost. The saved page is still on this profile; the read just did not finish.',
      action: { kind: 'check', label: 'Try again' },
      secondary: null
    }
  }
  if (pageStatus === 'loading' || planLoading) {
    return {
      ...base,
      state: 'reading',
      headline: 'Reading this lesson page',
      detail: 'The saved page for this section is still being read.',
      action: null,
      secondary: null
    }
  }
  if (planStatus === 'error') {
    return {
      ...base,
      state: 'unreadable',
      headline: 'The plan could not be read',
      detail: 'Nothing was lost. The approved plan is still stored; the read just did not finish.',
      action: { kind: 'check', label: 'Try again' },
      secondary: null
    }
  }
  if (jobFailed) {
    return {
      ...base,
      state: 'failed',
      headline: 'This lesson page could not be written',
      detail:
        'The approved plan is unchanged and every page already written is kept. ' +
        'Write this page again; nothing is rebuilt from a template. The reason is under Technical detail.',
      action: { kind: 'retry', label: 'Write this page again' },
      secondary: { kind: 'plan', label: 'View the plan' }
    }
  }
  if (jobLive) {
    return {
      ...base,
      state: 'running',
      headline: 'This lesson page is being written',
      detail:
        'Coursebook writes one page for each approved section. This page appears here as soon as it is ready; nothing on screen is invented while you wait.',
      action: { kind: 'check', label: 'Check again' },
      secondary: { kind: 'plan', label: 'View the plan' }
    }
  }
  if (document && (planApproved || !planProvided)) {
    // A saved page with no blocks is incomplete whatever the plan says; naming the plan here would
    // hide the fact that a page exists. A draft plan's document is handled by `unapproved` below,
    // because the page cannot be written until the plan is approved.
    return {
      ...base,
      state: 'incomplete',
      headline: 'This lesson page is incomplete',
      detail:
        'The page exists but has no teaching blocks yet. Writing it again from Plan replaces this placeholder.',
      action: { kind: 'plan', label: 'Open the plan' },
      secondary: null
    }
  }
  if (!planProvided) {
    // A caller that cannot see the plan must not claim the plan's state. The page is still missing,
    // so the owner is named without inventing which step it is on.
    return {
      ...base,
      state: 'no_page',
      headline: 'This section has no lesson page yet',
      detail:
        'Lesson pages are written from an approved plan. Open Plan to see where this one stands; nothing is invented to fill the gap.',
      action: { kind: 'plan', label: 'View the plan' },
      secondary: null
    }
  }
  if (!planApproved) {
    // An unapproved plan outranks an empty document: no page can be written for a plan that is not
    // approved, so "write it again" would be the wrong instruction here.
    return {
      ...base,
      state: 'unapproved',
      headline: plan ? 'The plan is not approved yet' : 'The plan has not been written yet',
      detail: plan
        ? 'Lesson pages are written after the plan is approved. Approve the plan in Plan, then Coursebook writes one page per section.'
        : 'Lesson pages are written from an approved plan. Open Plan to write one; nothing is invented to fill the gap.',
      action: { kind: 'plan', label: 'Open the plan' },
      secondary: null
    }
  }
  return {
    ...base,
    state: 'not_started',
    headline: 'This lesson page is not written yet',
    detail:
      'The plan is approved. Coursebook writes one page for each section, and this one has not been written yet.',
    action: { kind: 'plan', label: 'View the plan' },
    secondary: null
  }
}

/**
 * The one explanation a section with no approved page gets, with at most one action.
 *
 * The panel never renders a primary: nothing on this screen advances learning until the lessons
 * job has written the page, so there is nothing to point at as "the next lesson". `compact` is the
 * course-detail hero (a meta-size line under the title); the section body uses the heading size.
 */
function LessonReadinessPanel({
  readiness,
  onOpenPlan,
  onCheckAgain,
  onRetryLessonsJob,
  busy = false,
  compact = false
}) {
  if (!readiness) return null
  const handlers = {
    plan: onOpenPlan,
    check: onCheckAgain,
    retry: onRetryLessonsJob
  }
  const actionFor = (descriptor) => {
    if (!descriptor) return null
    const run = handlers[descriptor.kind]
    if (typeof run !== 'function') return null
    return jsx(sdk.Button, {
      size: 'sm',
      variant: compact ? 'text' : 'secondary',
      disabled: busy,
      'data-cb-readiness-action': descriptor.kind,
      onClick: run,
      children: descriptor.label
    })
  }
  const tertiaryFor = (descriptor) => {
    if (!descriptor) return null
    const run = handlers[descriptor.kind]
    if (typeof run !== 'function') return null
    return jsx(sdk.Button, {
      size: 'sm',
      variant: 'text',
      disabled: busy,
      'data-cb-readiness-action': descriptor.kind,
      onClick: run,
      children: descriptor.label
    })
  }
  const failed = readiness.state === 'failed' || readiness.state === 'unreadable'
  const heading = readiness.headline || 'This lesson page is not ready'
  const body = readiness.detail || ''
  const primaryAction = actionFor(readiness.action)
  const secondaryAction = tertiaryFor(readiness.secondary)
  return jsxs('div', {
    role: 'status',
    'data-cb-lesson-readiness': readiness.state,
    'data-cb-lesson-job': (readiness.job && readiness.job.job_id) || 'none',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: compact ? '0.3rem' : '0.45rem',
      maxWidth: CB_MEASURE,
      padding: compact ? '0.55rem 0 0.2rem' : '0.8rem 0.9rem 0.85rem 1rem',
      borderLeft: `1px solid ${failed ? 'var(--cb-coral)' : 'var(--cb-rule)'}`
    },
    children: [
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: compact ? CB_SANS : CB_SERIF,
          fontSize: compact ? CB_TYPE.meta : CB_TYPE.heading,
          fontWeight: 600,
          lineHeight: compact ? 1.4 : 1.2,
          color: 'var(--cb-ink)'
        },
        children: heading
      }),
      body
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: CB_SANS,
              fontSize: compact ? CB_TYPE.caption : CB_TYPE.meta,
              lineHeight: 1.5,
              color: compact ? 'var(--cb-ink-soft)' : 'var(--cb-ink)'
            },
            children: body
          })
        : null,
      // H-183: a typed failure reason is inspection evidence, never the sentence a learner reads.
      readiness.technical
        ? jsxs('details', {
            'data-cb-readiness-technical': '',
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer', minHeight: '1.75rem' }, children: 'Technical detail' }),
              jsx('p', { style: { margin: '0.25rem 0 0', overflowWrap: 'anywhere' }, children: readiness.technical })
            ]
          })
        : null,
      primaryAction || secondaryAction
        ? jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.15rem' },
            children: [primaryAction, secondaryAction]
          })
        : null
    ]
  })
}

function SectionPage({
  row,
  objectiveId,
  page,
  pageStatus,
  pageError,
  onRetryPage,
  implemented,
  onBack,
  onChanged,
  review,
  targetBlockId,
  outline,
  planStatus,
  jobs,
  onOpenPlan,
  onRetryLessonsJob,
  // A page served by Course Detail's hero; the hero owns the explanation of why a section has no
  // approved page, so the embedded body never repeats it (H-174).
  embedded = false,
  // The Home settings sheet (H-147) owns the learner's default presentation mode (Game / Guided /
  // Textbook, docs/EXPERIENCE-QUALITY-BAR.md §7.2) and passes it here. H-149 makes the player the
  // default surface; a preference naming a view this document cannot render falls back to it.
  defaultLessonView = 'player'
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const section = page && page.section
  const runtime = page && page.runtime
  const bindingActive = Boolean(runtime && runtime.binding_status === 'active')
  // H-174: the section's own read, plus the plan and the lessons job that own the page. A chat
  // binding never substitutes for an approved page, so `bindingActive` no longer decides whether
  // this screen offers a run to start.
  const readiness = lessonReadiness({ outline, page, jobs, pageStatus, planStatus })
  const pageReadable = readiness.state === 'readable'
  const [saveSeed, setSaveSeed] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const preferredView = LESSON_VIEWS.some((view) => view.id === defaultLessonView) ? defaultLessonView : 'player'
  const [lessonView, setLessonView] = useState(preferredView)
  // A mission or a saved moment hands the reader to the same block in Textbook. The target is a
  // block id, so the handoff survives the view switch and lands on the document's own block, not
  // an offset. A target from outside the section (Notebook, Field Desk) arrives the same way.
  const [focusBlockId, setFocusBlockId] = useState(targetBlockId || null)
  // The document is a v8 read projection. A backend that predates it answers with segments only,
  // so the segment list below stays as the fallback rather than becoming dead code.
  const document = page && page.document ? page.document : null
  const sourceIndex = {}
  for (const source of (page && page.sources) || []) {
    if (source && source.source_id) sourceIndex[source.source_id] = source
  }
  // One view is on screen at a time, so a single check node serves the Textbook block, the Guided
  // step and the legacy segment list. It is never rendered twice in one view.
  useEffect(() => {
    setLessonView(preferredView)
    setFocusBlockId(targetBlockId || null)
  }, [objectiveId, targetBlockId, preferredView])
  const check = useOpenCheck({
    enrollmentId: row.enrollment_id,
    objectiveId,
    revision: page ? page.revision : 0,
    enabled: Boolean(page) && supports('check.open') && Boolean(section),
    implemented
  })
  // The check surface prints one label per structured item; the document prose must not print the
  // same line again on the teaching block or the practice block.
  const checkStimulus = check.check && check.check.stimulus ? check.check.stimulus : null
  const checkLabels =
    checkStimulus && Array.isArray(checkStimulus.items)
      ? checkStimulus.items.map((item) => item && item.label).filter(Boolean)
      : []
  // A parent-recipe objective is observed by the adult: its check is a parent observation
  // (`coursebook/generation.py` rejects anything else for that recipe) and the confirmation lane is
  // disabled for it (`coursebook/grading.py`, docs/CHECKLIST-CONFIRMATION.md §6), so the observation
  // is the only recording path for this surface. A learner surface never gets this node.
  const parentLed = Boolean(row && row.recipe === 'parent')
  const observationNode = parentLed
    ? supports('observation.record')
      ? jsx(ParentObservation, {
          enrollmentId: row.enrollment_id,
          objectiveId,
          onRecorded: () => {
            if (onChanged) onChanged()
          }
        })
      : jsxs('div', {
          className: 'flex flex-col gap-2',
          children: [
            jsx(CbLabel, { children: 'Parent observation' }),
            jsx(QuietNote, {
              children:
                'This Desktop build cannot record a parent observation: the backend does not implement observation.record (cb.rpc v14). The section stays readable; nothing can be recorded here yet.'
            })
          ]
        })
    : null

  // When a live check is mounted it is the learner's action on this surface; the chat-run action
  // steps back to secondary so the screen still has exactly one primary (H-151).
  const checkOwnsPrimary = Boolean(!parentLed && check && check.check)
  const checkNode =
    check.status === 'error'
      ? jsx(QuietNote, {
          children: check.error
            ? `${check.error.code}: ${describeError(check.error)}`
            : 'The current check could not be opened.'
        })
      : check.status === 'loading' && !check.check
        ? jsx(sdk.Loader, { label: 'Opening the current check' })
        : jsx(AttemptControls, {
          enrollmentId: row.enrollment_id,
          objectiveId,
          check: check.check,
          revision: page ? page.revision : 0,
          implemented,
          bindingState: runtime ? runtime.binding_status : 'detached',
          parentLed,
          stimulusStatus: check.stimulusStatus,
          stimulusError: check.stimulusError,
          onRetryStimulus: check.reload,
          onCommitted: () => {
            if (onChanged) onChanged()
          }
        })
  // The player's own check node. It is the same `AttemptControls` over the same open check; the
  // only difference is that it reports its answer phase to the player footer and paints no button
  // of its own, so the session has exactly one primary.
  const [playerCheckState, setPlayerCheckState] = useState({ phase: 'awaiting_input', canCheck: false, verdict: null })
  const playerController = useRef(null)
  const playerCheckNode =
    check.status === 'error' || (check.status === 'loading' && !check.check)
      ? checkNode
      : jsx(AttemptControls, {
          enrollmentId: row.enrollment_id,
          objectiveId,
          check: check.check,
          revision: page ? page.revision : 0,
          implemented,
          bindingState: runtime ? runtime.binding_status : 'detached',
          parentLed,
          stimulusStatus: check.stimulusStatus,
          stimulusError: check.stimulusError,
          onRetryStimulus: check.reload,
          playerMode: true,
          playerController,
          onPlayerState: setPlayerCheckState,
          onCommitted: () => {
            if (onChanged) onChanged()
          }
        })

  const begin = useCallback(
    async (mode) => {
      setBusy(true)
      setNotice(null)
      // One shared path with the course detail: a fresh run arms the exact run, then this surface
      // opens the new chat that carries that binder. It never leaves the learner on a blank chat
      // with no indication of which run it belongs to.
      const outcome = await beginLessonFor({
        row,
        objectiveId,
        objectiveTitle: section ? section.title : null,
        mode,
        profile: row.profile || currentScope().profile
      })
      setBusy(false)
      if (outcome.ok && outcome.armed) {
        // A fresh run is only useful once the learner can type into it. The run is armed first;
        // opening the new chat then lets CoursebookPane name that exact run (never a recency
        // guess). If the host cannot open a chat, the explicit action remains on this page.
        const opened = openArmedLessonChat(row.profile || currentScope().profile)
        setNotice(
          opened
            ? { text: 'A new lesson chat is open. Send the first message to connect it to this lesson.' }
            : {
                text: outcome.message,
                action: {
                  label: 'Open the lesson chat',
                  run: () => startLessonChat(row.profile || currentScope().profile)
                }
              }
        )
        if (onChanged) onChanged()
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') {
        // Resume is impossible without a saved chat. Do not leave the learner with a sentence and
        // no way forward: the same arm path the fresh button uses is the honest next action.
        setNotice({
          text: outcome.message,
          action: { label: 'Start a fresh run', run: () => begin('fresh') }
        })
        return
      }
      setNotice(outcome.message)
      if (outcome.ok && onChanged) onChanged()
    },
    [row, objectiveId, section, onChanged]
  )

  const saveSegment = useCallback((segment) => {
    setSaveSeed({
      course_title: row.title || null,
      objective_title: section ? section.title : null,
      excerpt: segment.text,
      kind: segment.artifact_id ? 'artifact' : 'lesson_segment',
      artifact_id: segment.artifact_id || null,
      source_ids: segment.source_id ? [segment.source_id] : [],
      source_titles: segment.source_id ? [(sourceIndex[segment.source_id] && sourceIndex[segment.source_id].title) || segment.source_id] : []
    })
  }, [row, section, sourceIndex])

  /**
   * Seed the notebook editor from the document's own block.
   *
   * `block` and `media` are exactly what the backend served: no excerpt is fetched from the chat,
   * no selection API is invented. The block id, its source ids and the artifact id travel with the
   * save so `Open in textbook` can return to this block and `Play/view media` to this artifact.
   */
  const saveBlock = useCallback((block, media) => {
    const sourceIds = (block.source_ids || []).slice(0, 8)
    setSaveSeed({
      course_title: row.title || null,
      objective_title: section ? section.title : null,
      block_id: block.id,
      block_headline: block.headline,
      artifact_id: media ? media.artifact_id || null : null,
      source_ids: sourceIds,
      source_titles: sourceIds.map((id) => (sourceIndex[id] && sourceIndex[id].title) || id),
      excerpt: blockSaveExcerpt(block, checkLabels, media),
      kind: media ? 'artifact' : 'lesson_segment',
      check_id: block.check_id || null
    })
  }, [row, section, checkLabels, sourceIndex])

  /**
   * Hand a mission to another view by block id.
   *
   * The check node is not re-created by this: it is the same `check.get` read and the same
   * `AttemptControls` node, mounted once in whichever view is on screen.
   */
  const openBlock = useCallback((blockId, targetView) => {
    setFocusBlockId(blockId || null)
    setLessonView(targetView || 'textbook')
  }, [])

  /**
   * The practice loop travels as one bundle.
   *
   * It exists only when the backend registers `pronunciation.attempt` and the enrollment row carries
   * a locale: without either, the studio would have to invent a language hint or a score. The
   * studio itself is seated per block, and only a block with an authored narration transcript gets
   * one (see `PronunciationSeat`).
   */
  const pronunciation =
    document && row.locale && supports('pronunciation.attempt')
      ? {
          enrollmentId: row.enrollment_id,
          objectiveId,
          revision: page ? page.revision : 0,
          locale: row.locale,
          implemented,
          onSaved: () => {
            if (onChanged) onChanged()
          }
        }
      : null

  // The player owns the screen's one primary (`Check`), so the chat action beside it is secondary
  // while the player is on screen. It keeps its handler: nothing becomes a dead control.
  const playerSurface = Boolean(document) && lessonView === 'player'
  // The footer accounting follows the surface that actually mounts, not the selected name. A
  // parent-led course (`parentLed`, no player document) and a blockless page keep the section
  // footer, so the take-with-you action is never lost to a view name that renders no footer of
  // its own. `playerSteps` maps blocks one-to-one, so `blocks.length` is exactly "a player will
  // render".
  const playerOnScreen =
    playerSurface && !parentLed && Boolean(document && document.blocks && document.blocks.length > 0)
  // The Field Stop header lives inside the player (STOP n OF m, title, objective, step, exit). The
  // shell's own title block and metadata strip step aside there so the surface has one header; the
  // view switcher stays in `shellActions` because the learner must be able to leave for Textbook.
  const shellHeader = !playerSurface

  let body
  if (!page) {
    body =
      pageStatus === 'error'
        ? jsx('section', {
            'data-cb-section-error': '',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              maxWidth: CB_MEASURE,
              padding: '0.8rem 0.9rem 0.85rem 1rem',
              borderLeft: '1px solid var(--cb-coral)'
            },
            children: [
              jsx('h3', {
                style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.heading, fontWeight: 600, lineHeight: 1.2, color: 'var(--cb-ink)' },
                children: 'This section could not be read'
              }),
              jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                children: 'Nothing was lost. The page is still saved on this profile; the read just did not finish.'
              }),
              pageError && pageError.code
                ? jsxs('details', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: [
                      jsx('summary', { style: { cursor: 'pointer' }, children: 'Technical detail' }),
                      jsx('p', { style: { margin: '0.25rem 0 0' }, children: `${pageError.code}: ${describeError(pageError)}` })
                    ]
                  })
                : null,
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem', paddingTop: '0.2rem' },
                children: [
                  jsx(CbAction, { variant: 'primary', onClick: onRetryPage, children: 'Try again' }),
                  jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
                ]
              })
            ]
          })
        : pageStatus === 'loading'
          ? jsx('div', {
              style: { padding: '2rem 0', display: 'flex', justifyContent: 'center' },
              children: jsx(sdk.Loader, { label: 'Reading this section' })
            })
          // H-174: `lesson.page` answered without a section projection. This is not a loader that
          // never ends — the page the lessons job owns simply does not exist yet, and the readiness
          // panel says so. The course hero carries the same answer when this page is embedded.
          : embedded
            ? null
            : jsx(LessonReadinessPanel, {
                readiness,
                onOpenPlan,
                onCheckAgain: onRetryPage,
                onRetryLessonsJob,
                busy
              })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col gap-4',
      children: [
        // H-174: the readiness panel owns the explanation of a page that is not readable. The
        // backend's own view_note still describes a readable page's lens, so it stays there and
        // never competes with the panel above it.
        document && pageReadable && !(document.views && document.views.guided) && document.view_note
          ? jsx(QuietNote, { children: document.view_note })
          : null,

        !bindingActive && pageReadable
          ? jsx('div', {
              // A section may have no runtime read at all (the no-chat case): page.runtime is null,
              // and only `bindingActive` is guaranteed. Never dereference `runtime` unguarded here.
              'data-cb-detached': (runtime && runtime.binding_status) || 'detached',
              style: {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
                padding: '0.7rem 0.9rem',
                background: 'var(--cb-lamp-soft)',
                borderTop: '1px solid var(--cb-lamp)'
              },
              children: [
                jsx('span', {
                  style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                  children: 'This section has no lesson chat yet. Start one and send the first message to begin.'
                })
              ]
            })
          : null,

        // One live action per screen, and only once there is an approved page to teach from. H-174:
        // a section with no lessons-job page offers no run to start — the readiness panel below
        // (or the course hero, when embedded) names the job that owns it and the one next action.
        pageReadable
          ? jsxs('div', {
              'data-cb-section-actions': bindingActive ? 'resume' : 'start',
              style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.6rem' },
              children: [
                jsx(CbAction, {
                  'data-cb-section-primary': playerSurface ? 'secondary' : '',
                  variant: playerSurface ? 'secondary' : 'primary',
                  disabled: busy,
                  pending: busy,
                  onClick: () => begin(bindingActive ? 'resume' : 'fresh'),
                  children: busy ? 'Opening the lesson' : bindingActive ? 'Continue in the lesson chat' : 'Start a fresh run'
                })
              ]
            })
          : null,
        !pageReadable && !embedded
          ? jsx(LessonReadinessPanel, {
              readiness,
              onOpenPlan,
              onCheckAgain: onRetryPage,
              onRetryLessonsJob,
              busy
            })
          : null,
        jsx(NoticeLine, { notice, busy }),

        document && pageReadable
          ? jsx(
              LessonDocumentView,
              {
                document,
                view: lessonView,
                sources: sourceIndex,
                checkSlot: parentLed ? null : checkNode,
                checkLabels,
                progress: row.evidence_summary || null,
                focusBlockId,
                onOpenBlock: openBlock,
                onSaveBlock: supports('notebook.save') ? saveBlock : null,
                pronunciation,
                player: parentLed
                  ? null
                  : {
                      slot: playerCheckNode,
                      state: playerCheckState,
                      controller: playerController,
                      section,
                      takeHome: {
                        enrollmentId: row.enrollment_id,
                        courseId: row.course_id,
                        objectiveId,
                        sectionTitle: section ? section.title : null,
                        implemented,
                        onChanged
                      },
                      onExit: onBack,
                      onReload: onRetryPage,
                      // `Read the section` opens the same document in Textbook without leaving the
                      // page: it is the reference view of this stop, not a second surface.
                      onReadSection: () => {
                        setFocusBlockId(null)
                        setLessonView('textbook')
                      }
                    }
              },
              objectiveId
            )
          : null,
        document ? null : page.segments && page.segments.length > 0
          ? jsx('div', {
              className: 'flex flex-col',
              children: page.segments.map((segment) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                    children: [
                      jsxs('div', {
                        className: 'flex items-center justify-between gap-2',
                        children: [
                          jsx('span', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: cbSegmentWord(segment.kind) }),
                          jsxs('div', {
                            className: 'flex items-center gap-1',
                            children: [
                              segment.artifact_id && supports('artifact.get')
                                ? jsx(sdk.Button, {
                                    variant: 'text',
                                    size: 'sm',
                                    onClick: async () => {
                                      const response = await rpc('artifact.get', { artifact_id: segment.artifact_id })
                                      if (!response.ok) {
                                        host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
                                        return
                                      }
                                      host.notify({ kind: 'info', message: `Artifact ready: ${response.result.mime}, ${response.result.bytes} bytes.` })
                                    },
                                    children: 'View media'
                                  })
                                : null,
                              supports('notebook.save')
                                ? jsx(sdk.Button, {
                                    variant: 'text',
                                    size: 'sm',
                                    onClick: () => saveSegment(segment),
                                    children: 'Save to notebook'
                                  })
                                : null
                            ]
                          })
                        ]
                      }),
                      segment.kind === 'media'
                        ? jsx(MediaSegment, { segment })
                        : jsx(ProseText, { className: 'max-w-3xl', text: segment.text }),
                      segment.source_id
                        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `Source ${segment.source_id}` })
                        : null
                    ]
                  },
                  segment.segment_id
                )
              )
            })
          : null,

        // A parent-recipe page records an observation; it never mounts the graded check node.
        parentLed ? observationNode : null,

        document || parentLed ? null : jsx(CbLabel, { children: 'Current check' }),
        document || parentLed ? null : checkNode,

        // Repeated identical attempt rows are collapsed into one summary plus a disclosure: the
        // count is recorded, the detail is available, and the reading column stays quiet.
        page.attempts && page.attempts.length > 0
          ? jsxs('details', {
              'data-cb-attempts': String(page.attempts.length),
              style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: CB_MEASURE },
              children: [
                jsx('summary', {
                  style: { cursor: 'pointer', fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                  children: `${page.attempts.length} ${page.attempts.length === 1 ? 'attempt' : 'attempts'} recorded on this section · last ${whenLabel(page.attempts[0].committed_at || page.attempts[0].created_at)}`
                }),
                jsx('div', {
                  style: { display: 'flex', flexDirection: 'column', paddingTop: '0.3rem' },
                  children: page.attempts.map((attempt) =>
                    jsxs(
                      'div',
                      {
                        className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                        style: { borderTop: '1px solid var(--cb-rule)', padding: '0.4rem 0' },
                        children: [
                          jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: whenLabel(attempt.committed_at || attempt.created_at) }),
                          jsxs('span', {
                            className: 'flex items-center gap-2',
                            children: [
                              jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
                              jsx(EvidenceClassText, { value: attempt.evidence_class })
                            ]
                          })
                        ]
                      },
                      attempt.attempt_id
                    )
                  )
                })
              ]
            })
          : null,

        page.notebook_entries && page.notebook_entries.length > 0
          ? jsxs('div', {
              className: 'flex flex-col gap-1',
              children: [
                jsx(CbLabel, { children: 'Saved from this section' }),
                page.notebook_entries.map((entry) =>
                  jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: entry.excerpt || entry.note || entry.kind }, entry.entry_id)
                )
              ]
            })
          : null
      ]
    })
  }

  // The header, the view switcher and the field rail are the route shell; `body` is the reading
  // column only. The rail replaces the old in-page sources/notebook blocks, so nothing is printed
  // twice: the source cards and saved notes live in the third part of the workspace.
  const railFacts = section
    ? [
        { label: 'State', value: DESK_STATE_WORD[section.state] || 'Not started' },
        { label: 'Evidence', value: learnerEvidenceTarget(section.evidence_target) || 'Not recorded' },
        { label: 'Attempts', value: String((page && page.attempts ? page.attempts.length : 0)) }
      ]
    : []
  const viewOptions = document ? lessonViewOptions(document) : []
  const viewChoices = document ? lessonViewChoices(document) : []
  const unavailableViews = viewChoices.filter((choice) => !choice.available)
  const activeView = viewOptions.some((option) => option.id === lessonView) ? lessonView : (viewOptions[0] && viewOptions[0].id) || 'player'
  const activeViewLabel = (LESSON_VIEWS.find((view) => view.id === activeView) || {}).label || 'Game'
  const activeMode = cbModeFor(activeView)
  // One switcher, always in the header, at every pane width. The three names never disappear: a
  // view this document cannot render stays as a disabled choice with its reason in plain words,
  // and no breakpoint swaps the row for a hidden rail or a below-fold combobox (H-96 / H-80 F3).
  const switcher = document
    ? jsxs('div', {
        role: 'group',
        'aria-label': 'Lesson view',
        className: 'flex flex-wrap items-center gap-2',
        style: { minWidth: 0 },
        'data-cb-view-switcher': viewOptions.length > 1 ? 'available' : 'textbook-only',
        'data-cb-view-options': viewOptions.map((option) => option.id).join(' '),
        'data-cb-view-unavailable': unavailableViews.map((choice) => choice.id).join(' '),
        children: [
          jsxs('span', {
            style: { display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [jsx(ModeDot, { mode: activeMode }), 'Lesson view']
          }, 'label'),
          jsx('div', {
            'data-cb-view-choice-row': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.25rem', minWidth: 0 },
            children: viewChoices.map((choice) =>
              jsx(
                sdk.Button,
                {
                  size: 'xs',
                  variant: choice.id === activeView ? 'secondary' : 'ghost',
                  disabled: !choice.available,
                  title: choice.reason || undefined,
                  'aria-pressed': choice.available ? choice.id === activeView : undefined,
                  'aria-describedby': choice.available ? undefined : `cb-view-reason-${choice.id}`,
                  'data-cb-view-choice': choice.id,
                  'data-cb-view-choice-state': choice.available ? 'available' : 'unavailable',
                  onClick: () => {
                    if (!choice.available) return
                    setFocusBlockId(null)
                    setLessonView(choice.id)
                  },
                  children: choice.label
                },
                choice.id
              )
            )
          }, 'choices'),
          unavailableViews.length > 0
            ? jsx('span', {
                'data-cb-view-reasons': '',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.35, color: 'var(--cb-ink-soft)', minWidth: 0, overflowWrap: 'anywhere' },
                children: unavailableViews.map((choice, index) =>
                  jsx(
                    'span',
                    {
                      id: `cb-view-reason-${choice.id}`,
                      'data-cb-view-reason': choice.id,
                      children: `${index === 0 ? '' : ' '}${choice.reason}`
                    },
                    choice.id
                  )
                )
              }, 'reasons')
            : null
        ]
      })
    : null
  // The breadcrumb is the course the section belongs to. H-160: the course title is a long token at
  // 460 px / 200% text and the host text button is `shrink-0 whitespace-nowrap`, so it measured
  // 790 px inside a 154 px reading column — the reading column scrolled sideways at 460 px even at
  // a 16 px root. A breadcrumb is prose: it may shrink to the column and wrap like the rest.
  const crumbAction = jsx(CbAction, {
    variant: 'tertiary',
    'data-cb-breadcrumb': 'sections',
    className: 'self-start',
    onClick: onBack,
    style: {
      display: 'inline-flex',
      alignItems: 'flex-start',
      gap: '0.25rem',
      flexShrink: 1,
      minWidth: 0,
      maxWidth: '100%',
      height: 'auto',
      whiteSpace: 'normal',
      overflowWrap: 'anywhere',
      textAlign: 'left'
    },
    children: [jsx(sdk.Codicon, { name: 'chevron-left', size: CB_ICON_UI }), row.title || 'All sections']
  }, 'back')
  // On the Field Stop the shell header stands down, so the breadcrumb and the view switcher travel
  // together in one slim row above the reading column. Navigation is not metadata; it stays.
  const shellActions = page ? (playerSurface ? [crumbAction, switcher] : [switcher]) : []

  // The section's place in the course, printed only where the shell header is shown.
  const ordinal = section && section.ordinal ? String(section.ordinal) : null
  const total = row.evidence_summary && row.evidence_summary.total_objectives ? String(row.evidence_summary.total_objectives) : null
  const place = ordinal && total ? `Section ${ordinal} of ${total}` : ordinal ? `Section ${ordinal}` : null
  const metaLine = section
    ? [
        crumbAction,
        jsx('span', {
          style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
          children: [place, activeViewLabel].filter(Boolean).join(' · ')
        }, 'place'),
        jsx(CbStatePill, { state: section.state }, 'state'),
        section.evidence_target
          ? jsx('span', {
              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
              children: learnerEvidenceTarget(section.evidence_target) || 'Evidence target not recorded'
            }, 'evidence')
          : null,
        section.last_opened_at
          ? jsx('span', {
              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
              children: `Last opened ${whenLabel(section.last_opened_at)}`
            }, 'opened')
          : null
      ]
    : [jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onBack, children: 'All sections' }, 'back')]

  return jsx(WorkspaceShell, {
    eyebrow: null,
    title: section && section.title ? section.title : 'Section',
    subtitle: null,
    header: shellHeader,
    meta: metaLine,
    actions: shellActions,
    rail: page
      ? jsx(FieldRail, {
          next: row.next_step && (row.next_step.label || row.next_step.kind) ? (row.next_step.label || row.next_step.kind) : null,
          facts: railFacts,
          sources: page.sources || [],
          notes: page.notebook_entries || [],
        })
      : null,
    // GM-012: the lesson's own reading column is the only surface that can arm a tutor quote.
    // The pill appears after a completed selection and never sends; the rail lives in the pane.
    tutorSelection: page ? { courseId: row.course_id || null, objectiveId } : null,
    children: [
      body,
      // H-149: the section footer belongs to the section index. While the player is on screen
      // it owns the screen's single footer, and the take-with-you action travels into that row
      // instead — no surface may render data-cb-section-footer beside data-cb-player-footer.
      page && pageReadable && !playerOnScreen
        ? jsx('div', {
            'data-cb-section-footer': '',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              paddingTop: '0.9rem',
              borderTop: '1px solid var(--cb-rule)',
              maxWidth: CB_MEASURE
            },
            children: [
              jsx('div', {
                style: { display: 'flex', flexDirection: 'column', minWidth: 0 },
                children: jsx(TakeThisWithYou, {
                  enrollmentId: row.enrollment_id,
                  courseId: row.course_id,
                  objectiveId,
                  sectionTitle: section ? section.title : null,
                  implemented,
                  onChanged
                })
              }, 'homework'),
              jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                onClick: onBack,
                children: 'Back to the section index'
              }, 'back')
            ]
          })
        : null,
      jsx(NotebookSaveDialog, {
        open: Boolean(saveSeed),
        seed: saveSeed,
        onClose: () => setSaveSeed(null),
        enrollmentId: row.enrollment_id,
        objectiveId,
        lessonRunId: runtime ? runtime.lesson_run_id : null,
        implemented,
        onSaved: () => {
          if (onChanged) onChanged()
        }
      })
    ]
  })
}
