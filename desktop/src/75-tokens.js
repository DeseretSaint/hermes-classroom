/**
 * ── Atlas Lamp: the scoped Coursebook token layer ───────────────────────────────────────────
 *
 * The Desktop SDK has no per-route theme seam: `THEMES_AREA` registers an app-wide theme, and a
 * runtime plugin may import only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime`, so a
 * second stylesheet cannot be shipped as a module. The smallest honest seam is therefore a scoped
 * route shell: the token table below is applied as CSS custom properties on the Coursebook route
 * and pane roots only, and every Coursebook surface paints from `var(--cb-*)`. Hermes chrome is
 * untouched, and the host's own `--ui-*` tokens still supply anything outside this layer.
 *
 * The table is one embedded JSON literal so `tests/test_desktop_tokens.py` can read the shipped
 * module, compare it byte-for-byte with `contracts/cb.tokens.v2.json`, and compute WCAG contrast
 * on the values that actually ship. `CB_TOKENS_JSON` is the ONLY colour literal in this file: the
 * test refuses any hex outside it.
 *
 * Colour has three jobs and never four (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §2.3): identity
 * (`lamp`, `plum`), mode (`accent` Textbook, `field` Guided, `ochre` Field Quest) and state
 * (evidence/due/attention/not started). `lamp` is a fill and never text on `paper`; `coral` is
 * attention only and never a mode hue.
 */
const CB_TOKENS_JSON =
  '{"light":{"paper":"#f7f1e4","paper-raised":"#fffcf3","ink":"#1a1713","ink-soft":"#5c5347","rule":"#d7cbb4","accent":"#2c4a8c","accent-soft":"#e2e8f7","field":"#2f6047","ochre":"#7b4b0a","coral":"#9c2e1c","lamp":"#e8a93a","lamp-soft":"#fbebcb","on-lamp":"#1a1713","plum":"#6a3e74","plum-soft":"#f0e6f3"},"dark":{"paper":"#131210","paper-raised":"#1d1b16","ink":"#f5efe1","ink-soft":"#b9ae9a","rule":"#3d382d","accent":"#a8c0f2","accent-soft":"#222a3b","field":"#9fc69a","ochre":"#e0b25c","coral":"#ea9480","lamp":"#efc06b","lamp-soft":"#33290f","on-lamp":"#131210","plum":"#cda0d8","plum-soft":"#2e2434"}}'

const CB_TOKENS = JSON.parse(CB_TOKENS_JSON)
const CB_TOKEN_NAMES = Object.freeze([
  'paper',
  'paper-raised',
  'ink',
  'ink-soft',
  'rule',
  'accent',
  'accent-soft',
  'field',
  'ochre',
  'coral',
  'lamp',
  'lamp-soft',
  'on-lamp',
  'plum',
  'plum-soft'
])

/**
 * Six type steps, and only six. Every font size Coursebook authors for its own text is one of
 * these; the host's own chrome (badges, buttons, tab strips) keeps its own sizes and is outside
 * this claim. Body is `1rem`, so a 16px root paints 16px body copy; a 200% root scales the lot.
 * Display is a clamp inside the 2.25-2.5rem band, so no hero ever exceeds the step.
 */
const CB_TYPE_SCALE_JSON =
  '{"caption":"0.75rem","meta":"0.875rem","body":"1rem","lead":"1.125rem","heading":"1.5rem","display":"clamp(2.25rem, 1.9rem + 0.7vw, 2.5rem)"}'

const CB_TYPE = JSON.parse(CB_TYPE_SCALE_JSON)
const CB_TYPE_STEPS = Object.freeze(['caption', 'meta', 'body', 'lead', 'heading', 'display'])

/** One plural rule for every count the learner reads: `plural(1,'section','sections')`. */
function plural(count, one, many) {
  return `${count} ${Number(count) === 1 ? one : many}`
}

/** The host cannot ship a font file, so the voices are OS-resident stacks only. */
const CB_SERIF = 'ui-serif, Georgia, "Iowan Old Style", "Palatino Linotype", "Noto Serif", serif'
const CB_SANS = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'

/** Codicon only, two sizes: 16px beside UI text, 20px on a plate mark. Never a per-row icon. */
const CB_ICON_UI = '1rem'
const CB_ICON_PLATE = '1.25rem'

/** Four named ranges, measured from the route, never from a media query. */
const CB_WIDE_BREAKPOINT = 1050
const CB_MID_BREAKPOINT = 900
const CB_NARROW_BREAKPOINT = 460
/** A comfortable reading measure (62-72 characters) for the lesson column. */
const CB_MEASURE = '66ch'
const CB_RAIL_WIDTH = '20rem'
/** The route settle is capped at eight nodes, 40 ms apart (docs/CRAFT-CHANNELS-RESEARCH.md §5). */
const CB_PATH_SETTLE_NODES = 8
const CB_PATH_SETTLE_STAGGER_MS = 40

/** Painted light/dark, from the SDK's own theme context. Never inferred from a colour value. */
function cbModeFromTheme(theme) {
  const mode = theme && (theme.renderedMode || theme.resolvedMode)
  return mode === 'light' || mode === 'dark' ? mode : null
}

/**
 * `useTheme()` is a hook, so it may only be called when the running host exports it. The
 * fallback reads the `.dark` class the host's theme context toggles on `:root`; older hosts
 * therefore still land on the right palette, they just do not repaint mid-session.
 */
function useCbMode() {
  const theme = typeof sdk.useTheme === 'function' ? sdk.useTheme() : null
  const painted = cbModeFromTheme(theme)
  if (painted) return painted
  try {
    if (typeof document !== 'undefined' && document.documentElement) {
      return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
    }
  } catch (error) {
    // A host without a document (SSR) falls through to the light default.
  }
  return 'light'
}

/**
 * The motion ladder, from docs/CRAFT-CHANNELS-RESEARCH.md §4 (M2) and §5 (the aliveness kit) and
 * docs/EXPERIENCE-QUALITY-BAR.md §2.3. Four functional beats and no more: press 90–120 ms, route
 * settle 180 ms, check verdict 120–180 ms, completion ≤600 ms. The values are tokens so a test can
 * read them, and so no surface can author a fifth duration inline.
 */
const CB_MOTION = Object.freeze({
  press: '100ms',
  /**
   * H-189: the route/edge beat is the trailhead's one arrival. 280 ms sits inside the card's
   * authored 240-320 ms window and inside the 600 ms ceiling; the path settles its eight nodes
   * 40 ms apart on the same rung, so a route paints once and then rests.
   */
  route: '280ms',
  verdict: '160ms',
  complete: '600ms',
  /** The reduced-motion crossfade ceiling (M3): the state still changes, it does not travel. */
  fade: '120ms',
  ease: 'cubic-bezier(0.2, 0, 0, 1)'
})
/** The only beats the product may paint. `fade` is the reduced-motion substitute, not a beat. */
const CB_MOTION_BEATS = Object.freeze(['press', 'route', 'verdict', 'complete'])
/** Nothing Coursebook animates may outlast this, except a progress indicator. */
const CB_MOTION_CEILING_MS = 600

/** The scoped custom properties. Inline, so the layer travels with the route and nothing leaks. */
function cbScopeStyle(mode) {
  const palette = CB_TOKENS[mode === 'dark' ? 'dark' : 'light']
  const style = {}
  for (const name of CB_TOKEN_NAMES) style[`--cb-${name}`] = palette[name]
  for (const step of CB_TYPE_STEPS) style[`--cb-text-${step}`] = CB_TYPE[step]
  for (const beat of CB_MOTION_BEATS) style[`--cb-dur-${beat}`] = CB_MOTION[beat]
  style['--cb-dur-fade'] = CB_MOTION.fade
  style['--cb-ease'] = CB_MOTION.ease
  style.colorScheme = mode === 'dark' ? 'dark' : 'light'
  style.backgroundColor = 'var(--cb-paper)'
  style.color = 'var(--cb-ink)'
  return style
}

/** Motion is functional only; a reduced-motion reader gets none of the transitions. */
function cbMotionPreference(media) {
  return media && media.matches === true ? 'reduced' : 'full'
}

/**
 * The one motion object every Coursebook surface asks for. `preference` is the reader's setting;
 * `transition(props, beat)` is the only way a surface may name a duration, so no call site can
 * invent a fifth beat or a longer one. Reduced motion keeps the state change and drops the travel:
 * an instant repaint, or at most a §4 M3 crossfade inside the 120 ms ceiling.
 */
function cbMotionFor(preference) {
  const reduced = preference === 'reduced'
  return Object.freeze({
    preference: reduced ? 'reduced' : 'full',
    reduced,
    beats: CB_MOTION_BEATS,
    duration(beat) {
      return Object.prototype.hasOwnProperty.call(CB_MOTION, beat) ? CB_MOTION[beat] : null
    },
    /** A transition string for one beat, or `null` when reduced motion keeps the change static. */
    transition(props, beat) {
      if (reduced) return null
      if (!Object.prototype.hasOwnProperty.call(CB_MOTION, beat)) return null
      return props
        .split(',')
        .map((prop) => `${prop.trim()} var(--cb-dur-${beat}) var(--cb-ease)`)
        .join(', ')
    },
    /** The reduced-motion crossfade: opacity only, never longer than the 120 ms ceiling. */
    crossfade(props) {
      if (!reduced) return null
      return props
        .split(',')
        .map((prop) => `${prop.trim()} var(--cb-dur-fade) linear`)
        .join(', ')
    }
  })
}

/** A media query that is stable for the life of the window, read once per mount. */
function cbReducedMotionMedia() {
  try {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
      return window.matchMedia('(prefers-reduced-motion: reduce)')
    }
  } catch (error) {
    // No matchMedia: assume the default, motion-on posture.
  }
  return null
}

/**
 * The learner's own motion setting and the OS preference are one answer. A nested surface cannot
 * see the route's props, so the route publishes its effective choice here: `useCbMotion()` below it
 * reads the same answer the settings sheet shows instead of shipping a switch with no reader.
 * `null` means "follow the OS", which is what `system` means.
 */
const cbMotionListeners = new Set()
let cbMotionPublished = null
function publishCbMotion(motion) {
  const next = motion && motion.reduced === true ? 'reduced' : null
  if (next === cbMotionPublished) return
  cbMotionPublished = next
  for (const listener of cbMotionListeners) listener()
}

/**
 * The OS answer alone. The route must publish its effective choice without reading its own
 * publication, or a learner who once chose `reduce` could never get motion back.
 */
function useCbReducedMedia() {
  const [reduced, setReduced] = useState(() => cbMotionPreference(cbReducedMotionMedia()) === 'reduced')
  useEffect(() => {
    const media = cbReducedMotionMedia()
    if (!media) return undefined
    const sync = () => setReduced(cbMotionPreference(media) === 'reduced')
    sync()
    if (typeof media.addEventListener === 'function') media.addEventListener('change', sync)
    else if (typeof media.addListener === 'function') media.addListener(sync)
    return () => {
      if (typeof media.removeEventListener === 'function') media.removeEventListener('change', sync)
      else if (typeof media.removeListener === 'function') media.removeListener(sync)
    }
  }, [])
  return reduced
}

function useCbMotion() {
  const [preference, setPreference] = useState(
    () => cbMotionPublished || cbMotionPreference(cbReducedMotionMedia())
  )
  useEffect(() => {
    const media = cbReducedMotionMedia()
    const sync = () => setPreference(cbMotionPublished || cbMotionPreference(media))
    cbMotionListeners.add(sync)
    sync()
    if (typeof media?.addEventListener === 'function') media.addEventListener('change', sync)
    else if (typeof media?.addListener === 'function') media.addListener(sync)
    return () => {
      cbMotionListeners.delete(sync)
      if (typeof media?.removeEventListener === 'function') media.removeEventListener('change', sync)
      else if (typeof media?.removeListener === 'function') media.removeListener(sync)
    }
  }, [])
  return cbMotionFor(preference)
}

/**
 * The one mount gate every beat shares: a beat runs only in a browser frame, only while the reader
 * allows motion, and only once. A server render or a reduced-motion reader is `settled` at once, so
 * a static frame is the resting frame and nothing arrives late.
 */
function useCbSettled(motion, enabled) {
  const active = enabled !== false
    && !motion.reduced
    && typeof window !== 'undefined'
    && typeof window.requestAnimationFrame === 'function'
  const [settled, setSettled] = useState(!active)
  useEffect(() => {
    if (!active) {
      setSettled(true)
      return undefined
    }
    const frame = window.requestAnimationFrame(() => setSettled(true))
    return () => {
      if (typeof window.cancelAnimationFrame === 'function') window.cancelAnimationFrame(frame)
    }
  }, [active])
  return { active, settled }
}

/** The style for one settle frame; shared by the mount hook and the staggered path list. */
function cbSettleFrame(motion, settled, options) {
  const spec = options || {}
  if (motion.reduced) return null
  const beat = spec.beat || 'route'
  const delay = Math.max(0, Number(spec.delay) || 0)
  const frame = {
    opacity: settled ? 1 : Number(spec.fromOpacity) || 0.96,
    transform: settled ? 'none' : spec.from || 'translateY(2px)'
  }
  if (!settled) return { ...frame, transition: 'none' }
  const transition = motion.transition(spec.props || 'opacity, transform', beat)
  if (!transition) return null
  return { ...frame, transition, ...(delay ? { transitionDelay: `${delay}ms` } : {}) }
}

/**
 * One mount beat: the node paints at its start position for a single frame, then transitions to
 * rest. `index`/`staggerMs` space a list; the caller decides how many nodes may be in the beat
 * (the route caps at eight), and the ones past the cap settle with no motion at all.
 */
function useCbSettle(motion, options) {
  const spec = options || {}
  const { active, settled } = useCbSettled(motion, spec.enabled)
  if (!active) return {}
  return cbSettleFrame(motion, settled, {
    beat: spec.beat,
    props: spec.props,
    from: spec.from,
    fromOpacity: spec.fromOpacity,
    delay: Math.max(0, Number(spec.index) || 0) * (Number(spec.staggerMs) || 0)
  }) || {}
}

/**
 * H-189 — one settle per selection change.
 *
 * `useCbSettled` settles a node once for the life of the mount. A course switch needs the new
 * card to land again, so this re-arms whenever `token` changes: the card paints at its start
 * position for one frame, then transitions to rest once and stays there. Reduced motion returns
 * `true` immediately — the state change survives, the travel does not.
 */
function useCbSelectionSettle(motion, token) {
  const live =
    !motion.reduced && typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function'
  const [landed, setLanded] = useState(!live)
  useEffect(() => {
    if (!live) {
      setLanded(true)
      return undefined
    }
    setLanded(false)
    const frame = window.requestAnimationFrame(() => setLanded(true))
    return () => {
      if (typeof window.cancelAnimationFrame === 'function') window.cancelAnimationFrame(frame)
    }
  }, [token, live])
  return live ? landed : true
}

/**
 * H-189 — the current stop's one gentle cycle.
 *
 * The card asks for a ring that lifts from 0.55 to 0.9, runs **two** cycles and stops. This is a
 * finite state machine, not a stylesheet loop: each leg is one `route`-beat opacity transition, and
 * after four legs the last timer is gone, so nothing repeats. Reduced motion (or no timers) returns
 * `pulse: false` and the ring keeps its static resting opacity.
 *
 * Returns `{ scale, running }`; the caller reads `scale` as the ring's opacity.
 */
function useCbStopPulse(motion, enabled) {
  const running =
    enabled !== false && !motion.reduced && typeof window !== 'undefined' && typeof window.setTimeout === 'function'
  const [leg, setLeg] = useState(0)
  useEffect(() => {
    if (!running) {
      setLeg(0)
      return undefined
    }
    const timers = []
    const duration = 280
    // 0 -> 1 -> 0 -> 1 -> 0 is two full cycles; the final 0 is the rest frame, then it stops.
    for (let step = 1; step <= 4; step += 1) {
      timers.push(window.setTimeout(() => setLeg(step % 2 === 0 ? 0 : 1), step * duration))
    }
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [running])
  return { running, scale: running ? (leg === 1 ? 0.9 : 0.55) : 0.55 }
}

/** True while the document is visible; a hidden page stops painting frames. */
function useCbPageVisible() {
  const read = () =>
    typeof document === 'undefined' || !document || document.visibilityState === undefined
      ? true
      : document.visibilityState !== 'hidden'
  const [visible, setVisible] = useState(read)
  useEffect(() => {
    if (typeof document === 'undefined' || !document || typeof document.addEventListener !== 'function') {
      return undefined
    }
    const onChange = () => setVisible(read())
    onChange()
    document.addEventListener('visibilitychange', onChange)
    return () => document.removeEventListener('visibilitychange', onChange)
  }, [])
  return visible
}


/** Live width from `host.state.viewport`, with a static read for hosts that predate the atom. */
function useCbViewportWidth() {
  // The host atom reports the whole application window. Coursebook can sit in a much narrower
  // route pane (for example beside the chat rail), and choosing the wide shell from the window
  // width squeezes the Continue card into a word-per-line column. Measure the route itself when a
  // DOM exists; keep the host read as the SSR/older-host fallback.
  const [containerWidth, setContainerWidth] = useState(0)
  useEffect(() => {
    if (typeof document === 'undefined' || typeof window === 'undefined') return undefined
    let node = null
    let observer = null
    const read = () => {
      if (!node || !node.isConnected) return
      const rect = node.getBoundingClientRect()
      if (rect.width > 0) setContainerWidth(Math.round(rect.width))
    }
    const attach = () => {
      node = document.querySelector('[data-cb-route]')
      if (!node) return false
      read()
      if (typeof ResizeObserver === 'function') {
        observer = new ResizeObserver(read)
        observer.observe(node)
      }
      window.addEventListener('resize', read)
      return true
    }
    if (!attach()) {
      const retry = window.setTimeout(attach, 0)
      return () => window.clearTimeout(retry)
    }
    return () => {
      if (observer) observer.disconnect()
      window.removeEventListener('resize', read)
    }
  }, [])

  const atom = sdk.host && sdk.host.state ? sdk.host.state.viewport : null
  const read = () => {
    try {
      const rect = atom && typeof atom.get === 'function' ? atom.get() : null
      if (rect && typeof rect.width === 'number') return rect.width
    } catch (error) {
      // A host without the atom reports 0, which stacks the rail rather than overflowing.
    }
    return 0
  }
  if (atom && typeof sdk.useValue === 'function') {
    const rect = sdk.useValue(atom)
    if (rect && typeof rect.width === 'number') return containerWidth || rect.width
  }
  return containerWidth || read()
}

/** Pure so the layout decision is testable without a window: the route decides, not the app. */
function cbLayoutFor(width) {
  if (typeof width !== 'number' || !Number.isFinite(width) || width <= 0) return 'phone'
  if (width >= CB_WIDE_BREAKPOINT) return 'wide'
  if (width >= CB_MID_BREAKPOINT) return 'mid'
  if (width >= CB_NARROW_BREAKPOINT) return 'narrow'
  return 'phone'
}

/** The rail sits beside the reading column only at `wide`; every other range stacks it after. */
function cbIsWide(layout) {
  return layout === 'wide'
}

/* ── Atlas Lamp primitives ─────────────────────────────────────────────────────────────────
 * The recurring motifs of the identity, built from tokens only: the course seal, the plate head,
 * the route spine, the evidence tally and the hero field. No primitive names a colour directly,
 * so the scoped layer is still the only place a palette value exists.
 */

/** Deterministic character sum, so one course keeps one seal station across sessions. */
function cbSealStation(courseId) {
  const text = String(courseId || '')
  let sum = 0
  for (let index = 0; index < text.length; index += 1) sum += text.charCodeAt(index)
  return sum % 4
}

/* ── The shelf: one object per course, deterministic cover ─────────────────────────────────
 * H-99. Library, All Courses and Parent Studio all read the same `library.list` rows, and the
 * store can legitimately hold many enrollments (or many plans) that describe the same course.
 * Everything below is pure: no sdk, no jsx, no DOM. `tests/test_desktop_course_shelf.py`
 * imports these functions through Node and executes them, so grouping and cover determinism
 * are proven by running the shipped code rather than by matching source strings.
 */

/** FNV-1a over UTF-16 code units: stable across reloads, engines and row order. */
function cbStableHash(text) {
  const value = String(text == null ? '' : text)
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash >>> 0
}

/** The two-letter mark on a cover. Deterministic from the title; never random, never a colour. */
function cbCourseMonogram(title) {
  const words = String(title || 'Coursebook')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (words.length === 0) return 'CB'
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return `${words[0][0]}${words[1][0]}`.toUpperCase()
}

/**
 * The content the shelf can actually see on one `library.list` row. The per-plan hash lives in
 * `course.outline`, which the shelf does not call for every row; this projection is the honest
 * substitute and its fingerprint is shown to the reader, so two rows that share a cover can be
 * told apart without opening either.
 */
function cbShelfContent(row) {
  const provenance = (row && row.provenance) || {}
  const summary = (row && row.evidence_summary) || {}
  return {
    title: String((row && row.title) || '').trim().replace(/\s+/g, ' ').toLowerCase(),
    recipe: String((row && row.recipe) || ''),
    locale: String((row && row.locale) || ''),
    objectives: Math.max(0, Number(summary.total_objectives || 0)),
    packId: String(provenance.pack_id || ''),
    packVersion: String(provenance.pack_version || ''),
    source: String(provenance.source || '')
  }
}

/** The full content fingerprint: the closest thing to a plan hash a shelf row carries. */
function cbShelfFingerprint(row) {
  const content = cbShelfContent(row)
  const text = [
    content.title,
    content.recipe,
    content.locale,
    content.objectives,
    content.packId,
    content.packVersion,
    content.source
  ].join('|')
  return cbStableHash(text).toString(16).padStart(8, '0')
}

/**
 * The grouping key. A pack-backed course is one object per pack (docs/COURSEBOOK-VISUAL-
 * IDENTITY-V2 §5.3: "when several enrollments share one pack, show one row per pack"). An
 * authored course groups by its normalised title and recipe, so fourteen copies of the same
 * named plan become one row plus a disclosure — the records are listed there, never deleted.
 */
function cbShelfGroupKey(row) {
  const content = cbShelfContent(row)
  if (content.packId) return `pack:${content.packId}`
  const text = [content.title, content.recipe, content.locale].join('|')
  return `plan:${cbStableHash(text).toString(16)}`
}

/** Active first, then most recently touched, then highest revision, then the id — no ties. */
function cbShelfMemberOrder(left, right) {
  const activeLeft = left && left.enrollment_status === 'active' ? 0 : 1
  const activeRight = right && right.enrollment_status === 'active' ? 0 : 1
  if (activeLeft !== activeRight) return activeLeft - activeRight
  const touchedLeft = String((left && left.updated_at) || '')
  const touchedRight = String((right && right.updated_at) || '')
  if (touchedLeft !== touchedRight) return touchedLeft < touchedRight ? 1 : -1
  const revisionLeft = Number((left && left.revision) || 0)
  const revisionRight = Number((right && right.revision) || 0)
  if (revisionLeft !== revisionRight) return revisionRight - revisionLeft
  return String((left && left.enrollment_id) || '').localeCompare(String((right && right.enrollment_id) || ''))
}

/**
 * Group rows into shelf objects. The reader gets the primary enrollment of each object plus a
 * count; `members` keeps every record so the disclosure can list them and nothing is hidden.
 */
function groupShelfRows(rows) {
  const list = Array.isArray(rows) ? rows : []
  const buckets = new Map()
  for (const row of list) {
    if (!row || !row.enrollment_id) continue
    const key = cbShelfGroupKey(row)
    if (!buckets.has(key)) buckets.set(key, { key, members: [] })
    buckets.get(key).members.push(row)
  }
  const groups = []
  for (const bucket of buckets.values()) {
    const members = bucket.members.slice().sort(cbShelfMemberOrder)
    const versions = new Set(members.map(cbShelfFingerprint))
    const courses = new Set(members.map((member) => member.course_id || member.enrollment_id))
    let label = ''
    if (members.length > 1) {
      const packBacked = Boolean(cbShelfContent(members[0]).packId)
      if (packBacked) label = `${members.length} enrollments`
      else if (versions.size > 1) label = `${members.length} plans · ${versions.size} versions`
      else label = `${members.length} copies of this plan`
    }
    groups.push({
      key: bucket.key,
      primary: members[0],
      members,
      count: members.length,
      versions: versions.size,
      courses: courses.size,
      label
    })
  }
  groups.sort((left, right) => cbShelfMemberOrder(left.primary, right.primary) || String(left.key).localeCompare(String(right.key)))
  return groups
}

