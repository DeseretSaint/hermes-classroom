// ══ M2 — the Field Desk home ═══════════════════════════════════════════════════════════════
//
// The home answers one question: what do I do next? It is assembled only from reads the contract
// already has:
//
//   library.list       the row: next_step, evidence_summary, updated_at and pack provenance
//   course.outline     the path: every objective with its state and last_opened_at
//   lesson.page        the current section's sources, fetched only when the drawer is opened
//   pack.inspect / parent.brief.get   the estimate the backend already recorded
//
// There is no sample course, no invented minutes and no vanity metric. A read that fails is
// rendered as a failure with its code and a retry; a value the backend never recorded is rendered
// as "not recorded" rather than guessed.

// Every learner-facing state word comes from `CB_COPY` (00-header.js), the one map. This file
// used to carry its own copy, which said "Evidence" while the learning surface said "Independent
// evidence" and the index said "Complete" for the same stored state.

/** The tone is a token name, never a colour literal: `done`/`due`/`active`/`quiet`. */
const DESK_STATE_TONE = {
  not_started: 'quiet',
  introduced: 'active',
  independent_evidence: 'done',
  delayed_evidence: 'done',
  review_due: 'due',
  needs_review: 'attention',
  overridden: 'quiet'
}

const DESK_PRIMARY_LABEL = {
  start_lesson: 'Start a fresh run',
  resume_lesson: 'Resume the lesson',
  // E2E L1: a section whose check is already closed and passed reopens as a revisit. The backend
  // says so with `review_lesson`; the desk must not offer to start it again.
  review_lesson: 'Review',
  resolve_review_due: 'Start the review',
  rebind_session: 'Reconnect the chat',
  review_plan: 'Review the plan',
  review_pack: 'Review the pack',
  // E2E L4/L5: a finished course and a page that could not be written each get their own word.
  complete: 'Course complete',
  repair_lesson: 'Repair this lesson'
}

function deskToneColor(tone) {
  if (tone === 'done') return 'var(--cb-field)'
  if (tone === 'due') return 'var(--cb-ochre)'
  if (tone === 'active') return 'var(--cb-accent)'
  return 'var(--cb-ink-soft)'
}

/**
 * The section the desk continues. A due review wins when the backend's own `next_step` says so;
 * otherwise the row's `current_objective_id` decides; otherwise the first objective without
 * independent evidence. No title matching, no recency guess.
 */
function mainlineObjective(row, objectives) {
  const list = Array.isArray(objectives) ? objectives : []
  if (list.length === 0) return null
  const kind = row && row.next_step ? row.next_step.kind : null
  if (kind === 'resolve_review_due') {
    const due = list.find((entry) => entry.state === 'review_due')
    if (due) return due
  }
  if (kind === 'repair_lesson') {
    // The backend names the objective its parked section belongs to; never guess by recency.
    const named = row.next_step.objective_id
      ? list.find((entry) => entry.objective_id === row.next_step.objective_id)
      : null
    const parked = named || list.find((entry) => entry.lesson_state === 'needs_review')
    if (parked) return parked
  }
  const currentId = row && row.evidence_summary ? row.evidence_summary.current_objective_id : null
  const byId = currentId ? list.find((entry) => entry.objective_id === currentId) : null
  if (byId) return byId
  return list.find((entry) => !entry.independent) || list[list.length - 1]
}

const HUB_SLOT_LIMIT = 4
// GM-002 — the library shelf is a first viewport, not the catalog: six authored cards at wide,
// then `See all` opens Courses. The rail limit above stays the desk's own classroom switcher.
const HUB_SHELF_LIMIT = 6

const CB_HOME_COPY = Object.freeze({
  question: 'What will you learn next?',
  subline: 'Pick a course, or chart a new one.',
  create: 'Start a new course',
  browse: 'Browse the library',
  shelf: 'Your courses',
  seeAll: 'See all',
  emptyTitle: 'No courses yet.',
  emptyBody: 'Start with a goal, or browse a ready-made course.',
  loading: 'Reading your courses…',
  errorTitle: 'Your courses could not be read',
  modeUnavailable: 'This backend does not report course mode yet.',
  modeUnreadable: 'Course mode could not be read.'
})

/**
 * The durable course mode a `world.read` answer reports.
 *
 * GM-CONTRACT §2: a stored NULL or an unrecognised value reads as Textbook, and the read never
 * writes the fallback back. The helper exists so the shelf and the course home agree on one rule;
 * the caller must still have a real answer before calling it.
 */
function readCoursePresentationMode(value) {
  return value === 'game' ? 'game' : 'textbook'
}

/**
 * GM-002 — the mode badge on a shelf card, from a real `world.read` per visible course.
 *
 * The badge is never derived from the device preference (`homePrefs.defaultMode`) and never
 * guessed when the read is absent: an unsupported or failed read leaves `state` out of `ready`,
 * and the shelf names that instead of printing a mode nobody answered.
 */
function useCourseModes(courseIds) {
  const [modes, setModes] = useState({})
  const ids = (Array.isArray(courseIds) ? courseIds : []).filter(Boolean).slice(0, HUB_SHELF_LIMIT)
  const key = ids.join('|')
  useEffect(() => {
    if (!key || !backendSupports('world.read')) {
      setModes({})
      return undefined
    }
    let cancelled = false
    setModes((previous) => {
      const next = {}
      ids.forEach((id) => {
        next[id] = previous[id] && previous[id].state === 'ready' ? previous[id] : { state: 'loading' }
      })
      return next
    })
    ids.forEach((courseId) => {
      rpc('world.read', { course_id: courseId })
        .then((response) => {
          if (cancelled) return
          if (response && response.ok && response.result) {
            setModes((previous) => ({
              ...previous,
              [courseId]: { state: 'ready', mode: readCoursePresentationMode(response.result.presentation_mode) }
            }))
          } else {
            setModes((previous) => ({ ...previous, [courseId]: { state: 'error' } }))
          }
        })
        .catch(() => {
          if (!cancelled) setModes((previous) => ({ ...previous, [courseId]: { state: 'error' } }))
        })
    })
    return () => {
      cancelled = true
    }
    // `key` is the ordered id list; the array identity is not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return modes
}

/**
 * CP-022 — the v3 Home copy, from `docs/concept-parity/COPY.md` §2. Every fixed string below is a
 * deck row with an id; nothing is authored here. Two deliberate deviations are recorded in the
 * card's review packet rather than hidden: `home.primary` ships as the card body's own label
 * ("Start a new course", also the GM-002 behavioural anchor), and the kraft tag composes the deck's
 * `home.tag.firstuse` word with the course's real title instead of inventing a sentence.
 */
const CB_HOME_V3_COPY = Object.freeze({
  title: 'Your field library',
  // CP-053: the owner's binding Home reference (R-HOME) wins on this line. The deck row keeps its
  // id; only its text follows the reference, so no unregistered copy is introduced.
  sub: 'Choose a course or start a new expedition.',
  primary: 'Start a new course',
  secondary: 'Browse library',
  shelfLabel: 'Your courses',
  seeAll: 'See all',
  tagNew: 'New course',
  firstuseTitle: 'Your field library',
  firstuseSub: 'Nothing here yet. Start a course and its first lesson will appear on this shelf.',
  firstusePrimary: 'Start your first course',
  overflowHint: 'More courses to the right',
  emptyTitle: 'No courses on this shelf',
  emptyBody: 'Courses you archive move out of this view.',
  emptyAction: 'See archived courses',
  loading: 'Reading your courses. Nothing on the shelf changes while this loads.',
  errorTitle: 'Your courses could not be read',
  errorBody: 'Nothing you saved is lost. Try again.',
  errorAction: 'Try again',
  offlineTitle: 'You are offline',
  offlineBody: 'Your shelf is here. New lessons wait until you reconnect.',
  offlineAction: 'Try again',
  cardNew: 'New',
  emptyShippedTitle: 'No courses yet.',
  emptyArchivedBody: 'Every course here is archived. Unarchive one in Courses to continue it.',
  // CP-031 — these strings still carry no `COPY.md` §2 id. They are enumerated in
  // `docs/visual-review/cp-022/MANIFEST.md` gap 3 and frozen by `test_home_v3_copy_has_an_id`;
  // the deck adopts or replaces them, this card may not invent a deck row. `failedReadWord` is
  // also pinned by the existing behavioural `tests.test_desktop_home_hub`, which this card does
  // not own.
  failedReadWord: 'This is a failed read, not an empty library.',
  parentTitle: 'Parent Studio holds your lesson plans.',
  parentBody:
    'This profile has parent-led lesson plans, not a learner course. Start a learner course here, or open Parent Studio.',
  parentAction: 'Open Parent Studio'
})

/** The shelf holds four real courses; a fifth scrolls behind `See all` (SPEC-V3 §3.3, §5.1 H5). */
const CB_HOME_V3_LIMIT = 4

/** A course is "new" for fourteen days from the newest write the row records (PLAN O5). */
const CB_HOME_TAG_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000

function homeNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

/**
 * One metadata pattern for every card in the shelf (SPEC-V3 §3.6): title / one subject line / one
 * evidence line. Every value comes from a CP-005 `library_item` field; the UI computes no count and
 * invents no percentage. A fact the read did not carry is omitted, never guessed.
 */
function homeCardFacts(row) {
  const entry = row || {}
  const summary = entry.evidence_summary && typeof entry.evidence_summary === 'object' ? entry.evidence_summary : {}
  const done = homeNumber(entry.sections_done)
  const total = homeNumber(entry.sections_total)
  const independent = homeNumber(summary.independent)
  const objectives = homeNumber(summary.total_objectives)
  let meta = null
  if (done !== null && total !== null) meta = `${done} of ${total} sections done`
  else if (independent !== null && objectives !== null) meta = `${independent} of ${objectives} sections done`
  const subject =
    typeof entry.subject_label === 'string' && entry.subject_label.trim() ? entry.subject_label.trim() : null
  const isNew = typeof entry.is_new === 'boolean' ? entry.is_new : independent === 0
  return { meta, subject, isNew, next: learnerNextLabel(entry.next_step && entry.next_step.label) }
}

/** The row's cover artifact id, from the CP-005 field, else the older `cover` object. */
function homeCoverArtifactId(row) {
  const entry = row || {}
  if (typeof entry.cover_artifact_id === 'string' && entry.cover_artifact_id) return entry.cover_artifact_id
  const cover = entry.cover && typeof entry.cover === 'object' ? entry.cover : null
  const id = cover ? cover.artifact_id || cover.artifact : null
  return typeof id === 'string' && id ? id : null
}

/**
 * The newest course a kraft tag may point at, or null. Strict PLAN O5 rule: the *most recently
 * written* course qualifies only when it has no attempt yet (`is_new`) and its recorded time is
 * under fourteen days old; otherwise no tag renders. CP-005 exposes no creation timestamp, so the
 * age is measured from `updated_at` — the gap is named in the card's review packet, not papered
 * over with a guessed date.
 */
function homeNewTagSlot(slots, nowMs) {
  const all = Array.isArray(slots) ? slots : []
  const newest = all[0]
  if (!newest) return null
  const row = newest.row || {}
  if (!homeCardFacts(row).isNew) return null
  const stamp = hubTime(row.updated_at)
  if (!stamp) return null
  const now = Number.isFinite(nowMs) ? Number(nowMs) : Date.now()
  const age = now - stamp
  if (age < 0 || age > CB_HOME_TAG_MAX_AGE_MS) return null
  return newest
}

/**
 * Route-relative shelf geometry (SPEC-V3 §3.1, §3.3, §5.1 H5). The number comes from the route
 * box `useCbViewportWidth` measures, never from a viewport unit, and it follows the shipped
 * `.cb3-gutter` rule — `clamp(1.25rem, 3.05cqi, 4rem)` above 760, `0.7rem` below — so a card row
 * can never be wider than the paper it sits on. The fox has its own lower ledge (H6) and never
 * takes a lane away from the cards.
 */
function homeGutter(width) {
  if (!(width > 0)) return 32
  if (!(width > 760)) return 0.7 * 16
  return Math.min(64, Math.max(20, width * 0.0305))
}

function homeContentWidth(width) {
  if (!(width > 0)) return 0
  return Math.max(0, width - 2 * homeGutter(width))
}

function homeShelfColumns(width) {
  if (!(width > 0)) return 4
  const content = homeContentWidth(width)
  if (content >= 880) return 4
  if (content >= 560) return 3
  return 1
}

function homeCardWidth(width) {
  if (!(width > 0)) return null
  const content = homeContentWidth(width)
  const gap = width >= 620 ? 16 : 12
  const columns = homeShelfColumns(width)
  return Math.max(140, Math.floor((content - (columns - 1) * gap) / columns))
}

/**
 * The shelf's own capacity: four cards at wide, three at mid (SPEC-V3 §5.1 overflow — five at
 * wide, four at mid), and the stacked column keeps four rows at compact. `home.gutter` above is
 * the same box the CSS draws, so the cards always fit the lane.
 */
function homeShelfLayout(width) {
  const compact = width > 0 && width < 620
  const columns = compact ? 1 : homeShelfColumns(width)
  const capacity = compact ? CB_HOME_V3_LIMIT : Math.min(CB_HOME_V3_LIMIT, columns)
  return { compact, columns, capacity }
}

/**
 * A course's own cover art is already its own picture; the crop only has to stop two cards that
 * reuse one artifact from showing the same window twice.
 */
const HOME_ART_CROPS = Object.freeze(['50% 42%', '66% 30%', '34% 58%', '60% 66%'])

/**
 * UI-K9 — the crop **and** zoom a repeated kit plate reads at. The kit ships one approved plate per
 * subject family, so two courses in one family share a plate by design; they must never share a
 * frame. Position alone is not enough: at a 160 px card the three old positions read as one room,
 * so every repeat steps the zoom as well (a plain multiple of the plate's own size, never a
 * stretch). The table covers the shelf's whole capacity (`CB_HOME_V3_LIMIT`), so no two visible
 * cards of one family resolve the same pair.
 */
const HOME_KIT_REPEAT_FRAMES = Object.freeze([
  Object.freeze({ position: '50% 50%', scale: 1 }),
  Object.freeze({ position: '72% 28%', scale: 1.18 }),
  Object.freeze({ position: '28% 64%', scale: 1.34 }),
  Object.freeze({ position: '60% 76%', scale: 1.52 })
])

/** The approved field_atlas@2 display plate a Home card reads in, or null. A cover is an asset. */
function homeKitCover(row) {
  const kit = cb3KitCoverFor(row)
  if (!kit) return null
  const src = cb3KitSource(kit.id3x2)
  if (!src) return null
  return { src, family: String(kit.id3x2).replace(/^.*field_atlas\./, '').replace(/-cover-3x2$/, '') }
}

/**
 * One cover per visible card, resolved once: the approved display plate for the course's subject
 * family first, then the course's own cover artifact, then an honest typographic plate on kit
 * paper. The kit's lesson room is **not** in this chain: its art is a painted cafe study room, so
 * a course whose pack names no family would wear a subject it may not have (UI-K9, D-011).
 *
 * Two courses that share a family plate get a different crop *and* zoom; `kind: 'own'` means
 * "this course's own artifact, else the letter plate", decided where the preview resolves.
 */
function homeCoverPlan(slots) {
  const seen = {}
  return (slots || []).map((slot, index) => {
    const row = (slot && slot.row) || {}
    const kit = homeKitCover(row)
    if (kit) {
      seen[kit.family] = (seen[kit.family] || 0) + 1
      const repeat = Math.min(seen[kit.family] - 1, HOME_KIT_REPEAT_FRAMES.length - 1)
      const frame = HOME_KIT_REPEAT_FRAMES[repeat]
      return { kind: 'kit', family: kit.family, src: kit.src, position: frame.position, scale: frame.scale }
    }
    return {
      kind: 'own',
      artifactId: homeCoverArtifactId(row),
      position: HOME_ART_CROPS[index % HOME_ART_CROPS.length]
    }
  })
}

/**
 * UI-K9 — the printed cover for a course the kit cannot dress. Kit card stock, a hairline rule and
 * the course's two-letter mark, centred like a label pasted on the card. It is **not** a second
 * copy of the title (the card's own heading carries the words — GM-002) and it is not a painted
 * room, which would claim a subject the course may not have. The mark is deterministic from the
 * title (`cbCourseMonogram`), so two undressable courses never wear the same plate.
 */
function HomeLetterCover({ title }) {
  return jsx('div', {
    'data-cb-home-cover-kind': 'letter',
    'data-cb-cover-letter': '',
    style: {
      position: 'relative',
      aspectRatio: '3 / 2',
      width: '100%',
      overflow: 'hidden',
      borderRadius: cb3Radius('square'),
      backgroundColor: cb3Role('canvas-edge'),
      border: `1px solid ${cb3Role('rule')}`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.35rem',
      padding: '0.55rem',
      boxSizing: 'border-box',
      textAlign: 'center'
    },
    children: [
      title
        ? jsx('span', {
            'aria-hidden': 'true',
            style: {
              display: 'block',
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              letterSpacing: '0.1em',
              color: cb3Role('ink-soft')
            },
            children: cbCourseMonogram(title)
          }, 'mark')
        : null,
      jsx('span', {
        'aria-hidden': 'true',
        style: { display: 'block', width: '22px', height: '1px', backgroundColor: cb3Role('rule'), flex: '0 0 auto' }
      }, 'rule')
    ]
  })
}

/**
 * A 3:2 cover: the approved kit plate, else the course's own artifact, else the printed plate above.
 * Never the lesson room.
 */
function HomeV3Cover({ cover, artifactId, title }) {
  const plan = cover || { kind: 'own', position: HOME_ART_CROPS[0] }
  const id = plan.kind === 'kit' ? null : plan.artifactId || artifactId
  const preview = useArtifactPreview(id)
  const art = preview && preview.state === 'ready' && typeof preview.data_url === 'string' ? preview.data_url : null
  const src = plan.kind === 'kit' ? plan.src : art
  if (!src) return jsx(HomeLetterCover, { title })
  return jsx(CoverPlate3, {
    src,
    title,
    'data-cb-home-cover-kind': plan.kind === 'kit' ? 'kit' : 'art',
    imageStyle: { objectPosition: plan.position, transform: plan.scale ? `scale(${plan.scale})` : undefined }
  })
}

/**
 * CP-022 — one course standing on the v3 shelf. The card is one paper object (cover, title, one
 * subject chip, one evidence line, the backend's own next-step sentence) with exactly one control:
 * an overlay `RowButton` whose name is `Open <title>`. No rating, no progress bar, no invented XP.
 */
function HomeV3Card({ slot, mode, index, width, isNew, cover, onOpen }) {
  const row = (slot && slot.row) || {}
  const title = row.title || (slot && slot.name) || 'Untitled course'
  const [keyboardFocus, setKeyboardFocus] = useState(false)
  const facts = homeCardFacts(row)
  const artifactId = homeCoverArtifactId(row)
  const modeWord =
    mode && mode.state === 'ready' ? (readCoursePresentationMode(mode.mode) === 'game' ? 'Game' : 'Textbook') : null
  const cardWidth = homeCardWidth(width)
  const open = () => {
    if (onOpen) onOpen(slot)
  }
  const chipStyle = {
    alignSelf: 'flex-start',
    paddingInline: '0.5rem',
    paddingBlock: '0.1rem',
    borderRadius: cb3Radius('soft'),
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('caption'),
    lineHeight: cb3Lead('caption'),
    color: cb3Role('ink')
  }
  const action = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
    children: [
      jsx(sdk.RowButton, {
        'aria-label': `Open ${title}`,
        'data-cb-home-card-action': row.enrollment_id || row.course_id || '',
        'data-cb-focus-ring': keyboardFocus ? 'visible' : 'none',
        className: 'absolute inset-0',
        onBlur: () => setKeyboardFocus(false),
        onFocus: (event) => setKeyboardFocus(shelfRingVisible(event && event.currentTarget)),
        style: {
          outlineStyle: keyboardFocus ? 'solid' : 'none',
          outlineWidth: keyboardFocus ? '2px' : '0',
          outlineColor: cb3Role('focus'),
          outlineOffset: '-2px',
          borderRadius: cb3Radius('soft')
        },
        onKeyDown: (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            open()
          }
        },
        onClick: open
      }, 'target'),
      modeWord || facts.next
        ? jsxs('div', {
            className: 'pointer-events-none',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.2rem 0.6rem', minWidth: 0 },
            children: [
              modeWord
                ? jsx('span', {
                    'data-cb3-chip': 'mode',
                    style: {
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      lineHeight: cb3Lead('caption'),
                      color: cb3Role('ink-soft')
                    },
                    children: modeWord
                  }, 'mode')
                : null,
              facts.next
                ? jsx('span', {
                    'data-cb-home-card-next': row.next_step && row.next_step.kind ? row.next_step.kind : 'none',
                    style: {
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      lineHeight: cb3Lead('caption'),
                      color: cb3Role('ink-soft'),
                      overflowWrap: 'anywhere'
                    },
                    children: facts.next
                  }, 'next')
                : null
            ]
          }, 'meta')
        : null
    ]
  }, 'action')
  return jsx(PaperCard, {
    'data-cb-home-card': '',
    'data-cb-home-card-index': String(index),
    'data-cb-course-id': row.course_id || '',
    'data-cb-home-card-basis': cardWidth ? `${cardWidth}px` : 'full',
    'data-cb-home-cover': cover && cover.kind === 'kit' ? 'kit' : artifactId ? 'artifact' : 'letter',
    'data-cb-home-cover-kind': cover && cover.kind === 'kit' ? 'kit' : artifactId ? 'artifact' : 'letter',
    role: 'listitem',
    style: {
      position: 'relative',
      boxSizing: 'border-box',
      width: cardWidth ? `${cardWidth}px` : '17rem',
      flex: cardWidth ? `0 0 ${cardWidth}px` : '0 0 17rem',
      gap: '0.45rem'
    },
    children: [
      jsx('div', { 'data-cb-home-cover-plate': '', children: jsx(HomeV3Cover, { cover, artifactId, title: row.title || null }) }, 'cover'),
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('heading'),
          lineHeight: cb3Lead('heading'),
          fontWeight: 600,
          color: cb3Role('ink'),
          maxWidth: '24ch',
          overflowWrap: 'anywhere'
        },
        children: title
      }, 'title'),
      facts.subject
        ? jsx('span', {
            'data-cb3-chip': 'subject',
            style: { ...chipStyle, backgroundColor: cb3Role('terracotta-quiet') },
            children: facts.subject
          }, 'subject')
        : null,
      facts.meta
        ? jsx('p', {
            'data-cb-home-card-meta': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: facts.meta
          }, 'facts')
        : null,
      isNew
        ? jsx('span', {
            'data-cb3-chip': 'new',
            style: { ...chipStyle, border: `1px solid ${cb3Role('gold')}` },
            children: CB_HOME_V3_COPY.cardNew
          }, 'new')
        : null,
      action
    ]
  })
}
// The v2 segment exported the card under this name; CP-022 keeps the export so the test surface in
// 99-tutor.js resolves while the Home it paints is the v3 object.
const HomeCourseCard = HomeV3Card

/**
 * GM-VISUAL-SPEC §2.5 — the shelf's edge affordance. A shelf that overflows fades the last 24px
 * at each edge that still has cards behind it, drawn as a `paper`→transparent mask on the scroll
 * container (a mask, not a gradient fill painted on a surface). Without it a clipped card is a
 * hard cut and nothing tells the learner the shelf scrolls.
 *
 * `state` is the measured edge (`data-cb-shelf-mask`) the live capture asserts on; `style` is the
 * mask itself.
 */
function cbShelfEdgeMask(scrollLeft, clientWidth, scrollWidth) {
  const left = Number(scrollLeft) || 0
  const client = Number(clientWidth) || 0
  const total = Number(scrollWidth) || 0
  if (total - client <= 1) return { state: 'none', style: {} }
  const fadeStart = left > 1
  const fadeEnd = left < total - client - 1
  if (!fadeStart && !fadeEnd) return { state: 'none', style: {} }
  const stops = fadeStart ? ['transparent 0', 'black 24px'] : ['black 0']
  if (fadeEnd) stops.push('black calc(100% - 24px)', 'transparent 100%')
  else stops.push('black 100%')
  const maskImage = `linear-gradient(to right, ${stops.join(', ')})`
  return {
    state: fadeStart && fadeEnd ? 'both' : fadeEnd ? 'right' : 'left',
    style: {
      maskImage,
      WebkitMaskImage: maskImage,
      maskRepeat: 'no-repeat',
      WebkitMaskRepeat: 'no-repeat',
      maskSize: '100% 100%',
      WebkitMaskSize: '100% 100%'
    }
  }
}

/**
 * CP-022 — the v3 global Home (R-HOME): a field library and a threshold.
 *
 * It answers "which course do I open next, and how do I start a new one?" with one threshold band
 * (type only), one filled primary plus one quiet outline pill, and one wooden shelf holding up to
 * four real courses, the fox at its right end and a kraft tag for a genuinely new course. It is not
 * a course page: no Continue, no trailhead, no course-bound hero. SPEC-V3 §5.1 is the region map and
 * `docs/concept-parity/COPY.md` §2 is the copy deck; every card fact is a CP-005 `library_item`
 * field, so no number is computed by the UI.
 */

/* ── Home scene (wide) ────────────────────────────────────────────────────────────────────────
 * The owner's approved Home is a room, not a dashboard: a centred invitation, one wooden shelf of
 * collectible cards, and a lower ledge with the mascot, the clock and the new-course tag. This
 * layer is used only on a route at least 1200 px wide; every narrower layout (and jsdom, which
 * reports width 0) keeps the existing compact Home, so the scene never degrades into a list.
 * Geometry is authored at 1344x768 — the reference canvas — and the block is centred on wider
 * routes. Art comes from the shipped object kit and each card's real cover artifact; no rating is
 * invented, the row under a title is the course's own section progress.
 */
/* CP-053 — the scene's authored geometry, measured off the binding reference frame
 * (`docs/concept-parity/refs/home.png`, R-HOME in `docs/concept-parity/refs/REFS.md`, 1344x768).
 * Every number below is a pixel position on that canvas. `design/home-scene.html` is generated
 * from this module by `scripts/gen-home-proof.py` and `tests/test_desktop_home_scene_parity.py`
 * fails if the committed page differs from a fresh render, so the proof cannot drift from the
 * shipped scene. The room's own material tones (wall, plank, card stock, tag) are scene-local
 * because the reference is a lit room, not the desk's flat paper.
 */
const CB_HOME_SCENE = Object.freeze({
  canvas: Object.freeze({ width: 1344, height: 768 }),
  hero: Object.freeze({ top: 128, title: 72, titleTracking: -1.2, subline: 32, sublineGap: 24, ctaGap: 26, ctaHeight: 48, ctaPadding: 22, ctaGapX: 24 }),
  cards: Object.freeze({ top: 384, left: 273, width: 176, height: 175, gap: 24, cover: 106, radius: 7 }),
  shelf: Object.freeze({ left: 219, width: 915, top: 559, height: 18, lip: 10 }),
  ledge: Object.freeze({ left: 130, width: 1150, top: 684, height: 30, face: 24 }),
  // VQ-011: the plate is the kit's square 256x256 tag object painted at its own aspect (148x148,
  // rope loop included). The old 164x88 box with background-size: 100% 100% squashed the master
  // 1.0x horizontally and 0.34x vertically, which bent the rope hole and the corners. The box top
  // is the shelf's top edge (the rope hangs from behind it) and its bottom lands on the ledge.
  tag: Object.freeze({ left: 888, top: 559, width: 148, height: 148, font: 23 }),
  // D-007 seating: the animated group stands ON plank two, whose top edge is y=684. The clock's
  // painted base sits 2.3 px above its 118 px box bottom and the fox's painted feet 4.9 px above its
  // 208 px box bottom, so the boxes start at 568 and 481 to land base/feet on 683.7 / 684.1. The fox
  // also clears the clock's opaque right edge by 11.4 px (1099.5 -> 1153.9): no overlap.
  clock: Object.freeze({ left: 1042, top: 568, size: 118 }),
  fox: Object.freeze({ left: 1110, top: 481, size: 208 })
})

function HomeSceneCard({ slot, index, cover, onOpen }) {
  const row = (slot && slot.row) || {}
  const media = cbCoverMedia(row)
  const plan = cover || { kind: 'own', position: HOME_ART_CROPS[0] }
  const preview = useArtifactPreview(plan.kind === 'kit' ? null : plan.artifactId || (media ? media.artifact_id : null))
  const artifactSrc =
    plan.kind !== 'kit' && preview && preview.state === 'ready' && preview.mime && preview.mime.startsWith('image/') && preview.data_url
      ? preview.data_url
      : null
  // UI-K9: with no plate for its subject and no art of its own, the card wears the printed title
  // on the scene's own kit-paper cover rule — never the painted lesson room, which reads as a
  // different course's subject. `[data-cb-home-scene-cover]` in 76-v3-scope.js styles the element.
  const src = plan.kind === 'kit' ? plan.src : artifactSrc
  const kind = plan.kind === 'kit' ? 'kit' : artifactSrc ? 'art' : 'type'
  const title = (slot && (slot.title || slot.name)) || 'Untitled course'
  // A course with no title of its own gets the plate's rule but no mark: a monogram debossed from
  // the "Untitled course" / learner-label placeholder would read as an invented identity.
  const mark = row && typeof row.title === 'string' && row.title.trim() ? cbCourseMonogram(row.title) : null
  const total = Number(row.sections_total) || 0
  const done = Number(row.sections_done) || 0
  const ratio = total > 0 ? Math.max(0, Math.min(1, done / total)) : 0
  return jsxs('article', {
    'data-cb-home-scene-card': '',
    role: 'listitem',
    children: [
      src
        ? jsx('img', {
            'data-cb-home-scene-cover': kind,
            src,
            alt: kind === 'art' && media ? media.caption || '' : '',
            style: {
              objectPosition: plan.position,
              transform: plan.scale ? `scale(${plan.scale})` : undefined
            }
          }, 'cover')
        : jsx('div', {
            'data-cb-home-scene-cover': kind,
            'data-cb-cover-letter': '',
            children: [
              mark ? jsx('span', { 'data-cb-cover-mark': '', children: mark }, 'mark') : null,
              jsx('span', { 'data-cb-cover-rule': '' }, 'rule')
            ]
          }, 'cover'),
      jsxs('div', {
        'data-cb-home-scene-body': '',
        children: [
          jsx('h3', { 'data-cb-home-scene-title': '', children: title }, 'title'),
          jsx('div', {
            'data-cb-home-scene-progress': '',
            'aria-hidden': 'true',
            children: jsx('i', { style: { width: `${Math.round(ratio * 100)}%` } }, 'fill')
          }, 'progress'),
          jsx('p', {
            'data-cb-home-scene-meta': '',
            children: total > 0 ? `${done} of ${total} sections done` : CB_COPY.state.not_started
          }, 'meta')
        ]
      }, 'body'),
      // U1: the card is a real button, not a click handler on an article. The overlay covers the
      // whole card, so pointer and keyboard reach the same control; `Tab` stops on it between the
      // hero's two buttons and the scene's shelf, and Enter/Space open the course natively. Paint
      // lives in 76-v3-scope.js so the scene still carries no inline paint. It sits last in the
      // card so the card's own cover/title markup is unchanged for the parity proof.
      jsx('button', {
        type: 'button',
        'data-cb-home-scene-open': (slot && (slot.course_id || slot.enrollment_id)) || '',
        'aria-label': `Open ${title}`,
        onClick: () => onOpen && onOpen(slot)
      }, 'open')
    ]
  })
}

/**
 * E2E U9 — the measured box the wide Home scene is scaled into.
 *
 * The route width includes the route's own gutters, so the box the scene actually stands in can be
 * narrower than `useCbViewportWidth()` reports. Measure the fit box itself; a render with no layout
 * (jsdom, a static proof) leaves this at 0 and the caller falls back to the route width so the
 * scale is still deterministic.
 */
function useHomeSceneFit() {
  const ref = useRef(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const node = ref.current
    if (!node) return undefined
    const read = () => {
      if (!node.isConnected) return
      const rect = node.getBoundingClientRect()
      if (rect.width > 0) setWidth(Math.round(rect.width))
    }
    read()
    if (typeof ResizeObserver !== 'function') return undefined
    const observer = new ResizeObserver(read)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

function HomeScene({ slots, canCreate, onStartCreate, onBrowseLibrary, onOpenCourse, onShowAll, overflow }) {
  const wood = cb3ObjectSource('shelf-plank')
  const clock = cb3ObjectSource('clock')
  const tagObject = cb3ObjectSource('tag')
  const heroPlate = cb3KitSource('home-hero')
  const woodImage = wood ? { backgroundImage: `url(${wood})` } : undefined
  const coverPlan = homeCoverPlan(slots)
  // E2E U9: the authored frame is 1344x768 and the scene is chosen from 1200 px up, so a narrower
  // room scales the whole plate instead of cropping the fox and the ledge off its right edge.
  const routeWidth = useCbViewportWidth()
  const [fitRef, fitWidth] = useHomeSceneFit()
  const stageWidth = fitWidth > 0 ? fitWidth : routeWidth
  const scale = stageWidth > 0 ? Math.min(1, stageWidth / CB_HOME_SCENE.canvas.width) : 1
  return jsx('div', {
    'data-cb-home-scene-fit': '',
    'data-cb-home-scene-scale': String(Math.round(scale * 10000) / 10000),
    ref: fitRef,
    style: { height: `${Math.round(CB_HOME_SCENE.canvas.height * scale)}px` },
    children: jsxs('div', {
      'data-cb-home': 'scene',
      'data-cb-home-scene': '',
      style: { '--cb-home-scene-scale': String(scale) },
      children: [
        heroPlate
          ? jsx('img', { 'data-cb-home-scene-backdrop': '', src: heroPlate, alt: '', 'aria-hidden': 'true' }, 'backdrop')
          : null,
        jsx('div', {
          'data-cb-home-scene-hero': '',
          children: jsxs('div', {
            'data-cb-home-scene-panel': '',
            children: [
              jsx('h1', {
                'data-cb-home-question': '',
                'data-cb-home-scene-question': '',
                children: CB_HOME_V3_COPY.title
              }, 'question'),
              jsx('p', { 'data-cb-home-scene-subline': '', children: CB_HOME_V3_COPY.sub }, 'subline'),
              jsxs('div', {
                'data-cb-home-scene-cta': '',
                children: [
                  canCreate
                    ? jsx('button', {
                        type: 'button',
                        'data-cb-home-scene-primary': '',
                        onClick: onStartCreate,
                        children: CB_HOME_V3_COPY.primary
                      }, 'create')
                    : null,
                  jsx('button', {
                    type: 'button',
                    'data-cb-home-scene-secondary': '',
                    onClick: onBrowseLibrary,
                    children: CB_HOME_V3_COPY.secondary
                  }, 'browse')
                ]
              }, 'cta')
            ]
          }, 'panel')
        }, 'hero'),
        jsx('div', {
          'data-cb-home-scene-cards': '',
          role: 'list',
          'aria-label': CB_HOME_COPY.shelf,
          children: slots.slice(0, 4).map((slot, index) =>
            jsx(HomeSceneCard, { slot, index, cover: coverPlan[index], onOpen: onOpenCourse }, (slot && slot.course_id) || `scene-${index}`)
          )
        }, 'cards'),
        jsx('div', {
          'data-cb-home-scene-plank-one': '',
          'aria-hidden': 'true',
          style: woodImage,
          children: jsx('i', {})
        }, 'plank-one'),
        jsx('div', {
          'data-cb-home-scene-tag': '',
          style: tagObject ? { backgroundImage: `url(${tagObject})` } : undefined,
          children: CB_HOME_V3_COPY.tagNew
        }, 'tag'),
        clock
          ? jsx('img', { 'data-cb-home-scene-clock': '', src: clock, alt: '', 'aria-hidden': 'true' }, 'clock')
          : null,
        jsx('div', { 'data-cb-home-scene-fox': '', children: jsx(FoxPose, { pose: 'clock', size: CB_HOME_SCENE.fox.size }, 'fox') }, 'fox-wrap'),
        jsx('div', {
          'data-cb-home-scene-plank-two': '',
          'aria-hidden': 'true',
          style: woodImage,
          children: jsx('i', {})
        }, 'plank-two'),
        // The shelf shows four cards; a fifth course is reached through this door, on the shelf's
        // own right edge rather than through a cropped fifth card nobody can click.
        overflow && onShowAll
          ? jsx('button', {
              type: 'button',
              'data-cb-home-scene-see-all': '',
              onClick: onShowAll,
              children: CB_HOME_V3_COPY.seeAll
            }, 'seeAll')
          : null
      ]
    })
  })
}

function CoursebookHome({
  library,
  modes,
  modesSupported,
  online,
  canCreate,
  onStartCreate,
  onBrowseLibrary,
  onOpenCourse,
  onShowAll,
  onOpenStudio,
  onRetry
}) {
  const width = useCbViewportWidth()
  const compact = width > 0 && width < 620
  const status = library ? library.status : 'loading'
  const data = library ? library.data : null
  const rows = data && Array.isArray(data.items) ? data.items : []
  const parentPlans = rows.filter((entry) => entry && entry.recipe === 'parent').length
  const hub = hubSlots(rows)
  const slots = hub.all.slice(0, CB_HOME_V3_LIMIT)
  const coverPlan = homeCoverPlan(slots)
  const modeMap = modes && typeof modes === 'object' ? modes : {}
  const parentOnly = status === 'ready' && hub.total === 0 && parentPlans > 0
  const firstUse = status === 'ready' && hub.total === 0 && parentPlans === 0
  const archived = Boolean(data && data.empty_reason === 'all_archived')
  const overflow = hub.total > CB_HOME_V3_LIMIT
  const tagSlot = status === 'ready' ? homeNewTagSlot(hub.all, Date.now()) : null
  // The one filled pill keeps one label on every Home state: the card's own `Start a new course`.
  // SPEC §5.1's `home.firstuse.primary` ("Start your first course") is not rendered, because the
  // first-run plate already carries the deck's first-use sentence and one surface has one action.
  const primaryLabel = CB_HOME_V3_COPY.primary
  const [primaryFocus, setPrimaryFocus] = useState(false)
  const caption = {
    margin: 0,
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('caption'),
    lineHeight: cb3Lead('caption'),
    color: cb3Role('ink-soft')
  }
  const body = {
    margin: 0,
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('body'),
    lineHeight: cb3Lead('body'),
    color: cb3Role('ink'),
    maxWidth: '60ch'
  }
  const stateTitle = {
    margin: 0,
    fontFamily: 'var(--cb3-font-display)',
    fontSize: cb3Type('heading'),
    lineHeight: cb3Lead('heading'),
    fontWeight: 600,
    color: cb3Role('ink'),
    maxWidth: '34ch',
    overflowWrap: 'anywhere'
  }

  // The shelf fades the edge that still has cards behind it. Measured from the live row; jsdom and
  // a static render report zeroes and honestly stay `none`. The route width is a dependency: the
  // card basis changes with it, so a stale measure would leave a clipped shelf with no fade.
  const shelfRowRef = useRef(null)
  const [shelfMask, setShelfMask] = useState({ state: 'none', style: {} })
  const shelfSlotCount = slots.length
  useEffect(() => {
    const row = shelfRowRef.current
    if (!row) return undefined
    const measure = () => setShelfMask(cbShelfEdgeMask(row.scrollLeft, row.clientWidth, row.scrollWidth))
    measure()
    row.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    let observer = null
    if (typeof ResizeObserver === 'function') {
      observer = new ResizeObserver(measure)
      observer.observe(row)
    }
    return () => {
      row.removeEventListener('scroll', measure)
      window.removeEventListener('resize', measure)
      if (observer) observer.disconnect()
    }
  }, [status, compact, width, shelfSlotCount])

  const invitation = jsxs('section', {
    'data-cb-home-invitation': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-start',
      gap: '0.7rem',
      minWidth: 0,
      maxWidth: '42rem',
      paddingBlock: compact ? '0.5rem 1rem' : '1rem 1.5rem'
    },
    children: [
      jsx('h2', {
        'data-cb-home-question': '',
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('heading'),
          lineHeight: cb3Lead('heading'),
          fontWeight: 600,
          color: cb3Role('ink'),
          maxWidth: '24ch',
          overflowWrap: 'anywhere'
        },
        children: CB_HOME_V3_COPY.title
      }, 'title'),
      jsx('p', {
        'data-cb-home-subline': '',
        style: { ...body, color: cb3Role('ink-soft') },
        children: CB_HOME_V3_COPY.sub
      }, 'sub'),
      jsxs('div', {
        style: {
          display: 'flex',
          flexDirection: compact ? 'column' : 'row',
          flexWrap: 'wrap',
          alignItems: compact ? 'stretch' : 'center',
          gap: compact ? '0.75rem' : '1rem',
          paddingTop: '0.2rem'
        },
        children: [
          canCreate
            ? jsx(PillAction, {
                variant: 'primary',
                label: primaryLabel,
                'data-cb-action': 'primary',
                'data-cb-home-primary': '',
                'data-cb-focus-ring': primaryFocus ? 'visible' : 'none',
                onFocus: () => setPrimaryFocus(true),
                onBlur: () => setPrimaryFocus(false),
                style: {
                  width: compact ? '100%' : undefined,
                  outlineStyle: primaryFocus ? 'solid' : 'none',
                  outlineWidth: primaryFocus ? '2px' : '0',
                  outlineColor: cb3Role('focus'),
                  outlineOffset: '2px'
                },
                onClick: onStartCreate
              }, 'create')
            : null,
          jsx(PillAction, {
            variant: 'quiet',
            label: CB_HOME_V3_COPY.secondary,
            'data-cb-home-secondary': '',
            style: { width: compact ? '100%' : undefined },
            onClick: onBrowseLibrary
          }, 'browse')
        ]
      }, 'actions')
    ]
  }, 'invitation')

  const shelfHead = jsxs('div', {
    'data-cb-home-shelf-head': '',
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.25rem 0.75rem', minWidth: 0 },
    children: [
      jsx('h2', {
        'data-cb-home-shelf-label': '',
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('heading'),
          lineHeight: cb3Lead('heading'),
          fontWeight: 600,
          color: cb3Role('ink')
        },
        children: CB_HOME_V3_COPY.shelfLabel
      }, 'label'),
      overflow && onShowAll
        ? jsx(PillAction, {
            variant: 'quiet',
            label: CB_HOME_V3_COPY.seeAll,
            'data-cb-home-see-all': '',
            onClick: onShowAll
          }, 'seeAll')
        : null
    ]
  }, 'head')

  const tagTitle = tagSlot ? (tagSlot.row && tagSlot.row.title) || tagSlot.name : null
  const tag = tagSlot
    ? jsxs('button', {
        type: 'button',
        'data-cb-home-tag': '',
        className: 'cb3-press',
        'aria-label': `${CB_HOME_V3_COPY.tagNew}: ${tagTitle}`,
        onClick: () => {
          if (onOpenCourse) onOpenCourse(tagSlot.row)
        },
        style: {
          alignSelf: 'flex-end',
          display: 'inline-flex',
          flexDirection: 'column',
          gap: '0.1rem',
          minHeight: '44px',
          maxWidth: '14ch',
          padding: '0.35rem 0.6rem',
          backgroundColor: cb3Role('terracotta-quiet'),
          border: `1px solid ${cb3Role('rule')}`,
          borderRadius: cb3Radius('soft'),
          color: cb3Role('ink'),
          textAlign: 'left',
          cursor: 'pointer',
          transform: 'rotate(-1.5deg)'
        },
        children: [
          jsx('span', {
            style: {
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              color: cb3Role('ink-soft')
            },
            children: CB_HOME_V3_COPY.tagNew
          }, 'label'),
          jsx('span', {
            style: {
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              overflowWrap: 'anywhere'
            },
            children: tagTitle
          }, 'title')
        ]
      }, 'tag')
    : null

  let shelf
  if (status === 'loading' || status === 'idle') {
    shelf = jsxs('section', {
      'data-cb-home-shelf': 'loading',
      'data-cb-home-shelf-state': status,
      style: { display: 'flex', flexDirection: 'column', gap: '0.55rem', minWidth: 0 },
      children: [
        shelfHead,
        jsx(ShelfPlank, {
          style: { overflow: 'visible' },
          children: [0, 1, 2, 3].slice(0, compact ? 4 : Math.min(4, homeShelfColumns(width))).map((index) =>
            jsx('div', {
              'data-cb-home-skeleton': String(index),
              'aria-hidden': 'true',
              style: {
                boxSizing: 'border-box',
                width: homeCardWidth(width) ? `${homeCardWidth(width)}px` : '17rem',
                height: '9.5rem',
                flex: homeCardWidth(width) ? `0 0 ${homeCardWidth(width)}px` : '0 0 17rem',
                backgroundColor: cb3Role('card-stock'),
                opacity: 0.4,
                borderRadius: cb3Radius('round')
              }
            }, `skeleton-${index}`)
          )
        }, 'plank'),
        jsx('p', { 'data-cb-home-loading': '', style: body, children: CB_HOME_V3_COPY.loading }, 'loading')
      ]
    }, 'shelf')
  } else if (status === 'error' && rows.length === 0) {
    const cause = library && library.error ? describeError(library.error) : ''
    const code = library && library.error && library.error.code ? `${library.error.code}: ` : ''
    shelf = jsxs('section', {
      'data-cb-home-shelf': 'error',
      'data-cb-home-shelf-state': 'error',
      style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0 },
      children: [
        jsx('h3', {
          'data-cb-home-error-title': '',
          style: stateTitle,
          children: online === false ? CB_HOME_V3_COPY.offlineTitle : CB_HOME_V3_COPY.errorTitle
        }, 'title'),
        jsx('p', {
          'data-cb-home-error-body': '',
          style: body,
          children: `${code}${cause ? `${cause.replace(/\.$/, '')}. ` : ''}${CB_HOME_V3_COPY.failedReadWord} ${
            online === false ? CB_HOME_V3_COPY.offlineBody : CB_HOME_V3_COPY.errorBody
          }`
        }, 'body'),
        jsx(PillAction, {
          variant: 'quiet',
          label: online === false ? CB_HOME_V3_COPY.offlineAction : CB_HOME_V3_COPY.errorAction,
          'data-cb-home-retry': '',
          onClick: onRetry
        }, 'retry')
      ]
    }, 'shelf')
  } else if (parentOnly) {
    shelf = jsxs('section', {
      'data-cb-home-shelf': 'parent-only',
      'data-cb-home-shelf-state': 'empty',
      'data-cb-home-empty-reason': 'parent_only',
      style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0, maxWidth: '42rem' },
      children: [
        jsx('h3', { style: stateTitle, children: CB_HOME_V3_COPY.parentTitle }, 'title'),
        jsx('p', { style: body, children: CB_HOME_V3_COPY.parentBody }, 'body'),
        jsx(PillAction, {
          variant: 'quiet',
          label: CB_HOME_V3_COPY.parentAction,
          'data-cb-home-studio': '',
          onClick: onOpenStudio
        }, 'studio')
      ]
    }, 'shelf')
  } else if (firstUse) {
    const plateTitle = archived ? CB_HOME_V3_COPY.emptyTitle : CB_HOME_V3_COPY.emptyShippedTitle
    const plateBody = archived ? CB_HOME_V3_COPY.emptyArchivedBody : CB_HOME_V3_COPY.firstuseSub
    shelf = jsxs('section', {
      'data-cb-home-shelf': 'empty',
      'data-cb-home-shelf-state': 'empty',
      'data-cb-home-empty-reason': archived ? 'all_archived' : 'no_courses',
      style: { display: 'flex', flexDirection: 'column', gap: '0.55rem', minWidth: 0 },
      children: [
        shelfHead,
        jsxs('div', {
          'data-cb-home-shelf-frame': '',
          style: { display: 'flex', flexDirection: 'column', minWidth: 0 },
          children: [
            jsx(ShelfPlank, {
              style: { overflow: 'visible' },
              children: jsxs('div', {
                'data-cb-home-start-plate': '',
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: '0.6rem',
                  maxWidth: '42ch',
                  padding: '1.1rem 1.25rem',
                  backgroundColor: cb3Role('card-stock'),
                  border: `1px solid ${cb3Role('rule')}`,
                  borderRadius: cb3Radius('round')
                },
                children: [
                  jsx('h3', { 'data-cb-home-plate-title': '', style: stateTitle, children: plateTitle }, 'title'),
                  jsx('p', { style: body, children: plateBody }, 'body'),
                  archived && onShowAll
                    ? jsx(PillAction, {
                        variant: 'quiet',
                        label: CB_HOME_V3_COPY.emptyAction,
                        'data-cb-home-archived': '',
                        onClick: onShowAll
                      }, 'archived')
                    : null
                ]
              }, 'plate')
            }, 'plank'),
            compact
              ? null
              : jsx('div', {
                  'data-cb-home-ledge': '',
                  style: {
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    minWidth: 0,
                    minHeight: '16px',
                    borderTop: `1px solid ${cb3Role('rule')}`,
                    paddingTop: '0.35rem'
                  },
                  children: jsx(FoxPose, {
                    pose: 'wave',
                    size: width >= 900 || width === 0 ? 128 : 112,
                    style: { alignSelf: 'flex-end' }
                  }, 'fox')
                }, 'ledge')
          ]
        }, 'shelf-frame')
      ]
    }, 'shelf')
  } else {
    const shelfLayout = homeShelfLayout(width)
    // SPEC-V3 §5.1 overflow: a fifth course at wide or a fourth at mid. The row scrolls inside its
    // frame with the edge mask; the cards never shrink and the fox never takes their lane.
    const shelfOverflow = hub.total > shelfLayout.capacity
    shelf = jsxs('section', {
      'data-cb-home-shelf': 'ready',
      'data-cb-home-shelf-state': 'ready',
      'data-cb-home-shelf-overflow': shelfOverflow ? 'true' : 'false',
      style: { display: 'flex', flexDirection: 'column', gap: '0.55rem', minWidth: 0 },
      children: [
        shelfHead,
        jsxs('div', {
          'data-cb-home-shelf-frame': '',
          style: { display: 'flex', flexDirection: 'column', minWidth: 0 },
          children: [
            jsx(ShelfPlank, {
              style: { overflow: 'visible' },
              children: jsx('div', {
                'data-cb-home-shelf-row': '',
                'data-cb-shelf-mask': shelfMask.state,
                ref: shelfRowRef,
                role: 'list',
                'aria-label': CB_HOME_V3_COPY.shelfLabel,
                style: {
                  display: 'flex',
                  flexDirection: compact ? 'column' : 'row',
                  alignItems: compact ? 'stretch' : 'flex-end',
                  gap: compact ? '0.75rem' : '1rem',
                  overflowX: compact ? 'visible' : 'auto',
                  minWidth: 0,
                  flex: '1 1 auto',
                  ...shelfMask.style
                },
                children: slots.map((slot, index) =>
                  jsx(HomeV3Card, {
                    slot,
                    mode: slot && slot.course_id ? modeMap[slot.course_id] : null,
                    index,
                    width,
                    isNew: homeCardFacts(slot && slot.row).isNew,
                    cover: coverPlan[index],
                    onOpen: (opened) => onOpenCourse && onOpenCourse(opened ? opened.row : null)
                  }, (slot && slot.course_id) || `slot-${index}`)
                )
              }, 'frame')
            }, 'plank'),
            // H6 — the lower ledge. The fox box and the kraft tag stand here, on their own paper,
            // so the shelf's full width belongs to the cards at every route width.
            compact
              ? null
              : jsxs('div', {
                  'data-cb-home-ledge': '',
                  style: {
                    display: 'flex',
                    alignItems: 'flex-end',
                    justifyContent: 'flex-end',
                    gap: '0.9rem',
                    minWidth: 0,
                    minHeight: '16px',
                    borderTop: `1px solid ${cb3Role('rule')}`,
                    paddingTop: '0.35rem'
                  },
                  children: [
                    tag,
                    jsx(FoxPose, {
                      pose: 'clock',
                      size: width >= 900 || width === 0 ? 128 : 112,
                      style: { alignSelf: 'flex-end' }
                    }, 'fox')
                  ]
                }, 'ledge')
          ]
        }, 'shelf-frame'),
        shelfOverflow && !compact
          ? jsx('p', { 'data-cb-home-overflow-hint': '', style: caption, children: CB_HOME_V3_COPY.overflowHint }, 'overflow')
          : null
      ]
    }, 'shelf')
  }

  // CP-053 — the wide Home is the room scene: a centred invitation, one shelf of collectible cards
  // and a lower ledge. It owns the route width >= 1200 band only. Every narrower layout, and every
  // loading / error / empty state, keeps the v3 hub below exactly as the seam wrote it.
  if (width >= 1200 && status === 'ready' && hub.total > 0) {
    return jsx(HomeScene, {
      slots,
      canCreate,
      onStartCreate,
      onBrowseLibrary,
      onOpenCourse,
      onShowAll,
      overflow
    }, 'scene')
  }

  // D-007 — below the scene breakpoint the same approved hero plate reads as a 16:9 band over the
  // shelf, so the narrow and docked Home carry the kit as well; the compact states below are kept.
  const heroBandSource = cb3KitSource('home-hero')
  const heroBand =
    heroBandSource && status === 'ready' && hub.total > 0 && width > 0 && width < 1200
      ? jsx('img', { 'data-cb-home-hero-band': '', src: heroBandSource, alt: '', 'aria-hidden': 'true' }, 'heroBand')
      : null

  return jsxs('div', {
    'data-cb-home': status === 'ready' && hub.total === 0 ? 'empty' : status,
    'data-cb-home-layout': compact ? 'stacked' : 'wide',
    style: { display: 'flex', flexDirection: 'column', gap: '0.8rem', minWidth: 0 },
    children: [
      online === false && status !== 'error'
        ? jsxs('div', {
            'data-cb-home-offline': '',
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.4rem 0.75rem',
              padding: '0.5rem 0.75rem',
              backgroundColor: cb3Role('card-stock'),
              border: `1px solid ${cb3Role('rule')}`,
              borderRadius: cb3Radius('soft')
            },
            children: [
              jsxs('p', {
                style: { ...caption, color: cb3Role('ink') },
                children: [
                  jsx('span', {
                    'data-cb-home-offline-word': '',
                    style: { fontWeight: 600, marginInlineEnd: '0.4rem' },
                    children: CB_HOME_V3_COPY.offlineTitle
                  }, 'word'),
                  jsx('span', { children: CB_HOME_V3_COPY.offlineBody }, 'text')
                ]
              }, 'text'),
              jsx(PillAction, {
                variant: 'quiet',
                label: CB_HOME_V3_COPY.offlineAction,
                'data-cb-home-offline-retry': '',
                onClick: onRetry
              }, 'retry')
            ]
          }, 'offline')
        : null,
      library && library.stale
        ? jsxs('div', {
            'data-cb-home-stale': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem 0.75rem' },
            children: [
              jsx('p', { style: caption, children: CB_HOME_V3_COPY.errorBody }, 'text'),
              jsx(PillAction, { variant: 'quiet', label: CB_HOME_V3_COPY.errorAction, 'data-cb-home-stale-retry': '', onClick: onRetry }, 'retry')
            ]
          }, 'stale')
        : null,
      invitation,
      heroBand,
      shelf
    ]
  })
}

/**
 * The route's Home surface: one `library.list` read feeds the shelf, and the mode map is a real
 * `world.read` per visible card. It never mounts the desk's transcript, the trailhead or Continue.
 */
function HomeLibraryPanel({ canCreate, online, onStartCreate, onBrowseLibrary, onOpenCourse, onShowAll, onOpenStudio }) {
  const payload = { filter: 'all', limit: 50, sort: 'recent' }
  const library = useRpcQuery('library.list', payload, JSON.stringify(payload), backendSupports('library.list'))
  const rows = library.data && Array.isArray(library.data.items) ? library.data.items : []
  const hub = hubSlots(rows)
  const modes = useCourseModes(hub.all.slice(0, CB_HOME_V3_LIMIT).map((slot) => slot.course_id))
  return jsx(CoursebookHome, {
    library,
    modes,
    modesSupported: backendSupports('world.read'),
    online,
    canCreate,
    onStartCreate,
    onBrowseLibrary,
    onOpenCourse,
    onShowAll,
    onOpenStudio,
    onRetry: library.reload
  })
}

/** Numeric clock for `updated_at`; an unparseable stamp sorts last, never first. */
function hubTime(value) {
  const time = Date.parse(String(value || ''))
  return Number.isFinite(time) ? time : 0
}

/**
 * The name of a classroom, from the row and nothing else: the enrollment's own `learner_label`
 * when it has one, otherwise the course title. "Learner 1" is never generated; a pack import has
 * no label, and a course switcher is the honest thing to show until rename exists.
 */
function hubSlotName(row) {
  const label = row && typeof row.learner_label === 'string' ? row.learner_label.trim() : ''
  if (label) return label
  const title = row && typeof row.title === 'string' ? row.title.trim() : ''
  return title || 'Untitled course'
}

function hubSlotFrom(entry) {
  const row = entry.row
  return {
    course_id: row.course_id,
    enrollment_id: row.enrollment_id,
    name: hubSlotName(row),
    learner_label: row.learner_label || null,
    title: row.title || null,
    updated_at: row.updated_at || null,
    // How many non-archived progress records this course carries in the rows the hub read.
    // Objective state is course-scoped, so this is a disclosure, not a second classroom.
    recordCount: entry.records,
    row
  }
}

/**
 * H-146 — the hub's read model. A classroom is the pair Coursebook already stores: a course plus
 * its newest enrollment (`library.list` rows are exactly that pair). Parent-authored rows are a
 * different destination and never become learner classrooms. Two enrollments on one course are
 * one classroom with two progress records, because objective state in the kernel is course-scoped:
 * splitting them would show two identical progress readings dressed as two learners.
 *
 * Pure and exported: it takes the contract's own rows and returns the rail, its visible cap and
 * the counts. It never reads the DOM, the clock or a host atom.
 */
function hubSlots(rows) {
  const list = Array.isArray(rows) ? rows : []
  const byCourse = new Map()
  list.forEach((row) => {
    if (!row || !row.course_id) return
    if (row.recipe === 'parent') return
    const held = byCourse.get(row.course_id)
    if (!held) {
      byCourse.set(row.course_id, { row, records: 1 })
      return
    }
    held.records += 1
    if (hubTime(row.updated_at) > hubTime(held.row.updated_at)) held.row = row
  })
  const classrooms = [...byCourse.values()]
    .map(hubSlotFrom)
    .sort((a, b) => {
      const delta = hubTime(b.updated_at) - hubTime(a.updated_at)
      if (delta !== 0) return delta
      return a.name.localeCompare(b.name)
    })
  const slots = classrooms.slice(0, HUB_SLOT_LIMIT)
  return {
    slots,
    // The full list is what the select above four needs; the cap is what the rail may show.
    all: classrooms,
    hidden: Math.max(0, classrooms.length - slots.length),
    total: classrooms.length,
    rowTotal: list.length
  }
}

/** The selected classroom, or the newest one when nothing is selected (or it just vanished). */
function selectedHubSlot(hub, selectedCourseId) {
  const all = hub && Array.isArray(hub.all) ? hub.all : []
  const wanted = selectedCourseId ? all.find((slot) => slot.course_id === selectedCourseId) : null
  return wanted || (hub && hub.slots && hub.slots[0]) || null
}

/**
 * When `course.outline` could not be read, the row still carries the section the enrollment is on.
 * This is only a pointer, never a fabricated objective: it has an id and no title or ordinal, so
 * the plate says the backend's own next-step label until the outline answers.
 */
function rowFallbackCurrent(row) {
  const summary = row && row.evidence_summary ? row.evidence_summary : {}
  if (!summary.current_objective_id) return null
  return {
    objective_id: summary.current_objective_id,
    title: null,
    ordinal: null,
    state: null,
    independent: false,
    last_opened_at: null
  }
}

/**
 * The estimate state, normalized for rendering. `error` means the read itself failed: the desk
 * has no answer, so it must not say the author recorded none. `none` means the backend answered
 * successfully and the answer carries no estimate. The two are never collapsed.
 */
function deskEstimateState(estimate) {
  const status = estimate && estimate.status ? estimate.status : 'none'
  if (status === 'loading' || status === 'idle') return 'loading'
  if (status === 'error') return 'error'
  if (status === 'ready' && Number(estimate.minutes) > 0) return 'ready'
  return 'none'
}

/** "Estimated minutes" is either recorded, absent from a real answer, or unreadable. Never derived. */
function deskEstimateLabel(estimate) {
  const state = deskEstimateState(estimate)
  if (state === 'loading') return 'Reading the estimate'
  if (state === 'error') return 'Session length could not be read'
  if (state === 'ready') return `≈ ${Number(estimate.minutes)} min`
  return 'Session length not recorded'
}

/**
 * Pure projection of the three reads into what the desk renders. Tested without a DOM.
 *
 * H-146: `selectedCourseId` picks the classroom; every read above it is keyed to that slot's
 * enrollment. `outlineState` tells the model whether `course.outline` answered, failed, or is
 * still in flight, so a failed route read falls back to the row's own current objective instead
 * of inventing one or disabling Continue.
 */
function buildDeskModel({ library, outline, estimate, selectedCourseId = null, outlineState = null }) {
  const rows = library && Array.isArray(library.items) ? library.items : []
  const hub = hubSlots(rows)
  const selected = selectedHubSlot(hub, selectedCourseId)
  // A selected course that is no longer in the rows is not silently replaced as if it still
  // existed; the fallback is named in `selectionLost` so the surface can say what happened.
  const selectionLost = Boolean(selectedCourseId) && Boolean(selected) && selected.course_id !== selectedCourseId
  const row = selected ? selected.row : null
  if (!row) {
    return {
      rows: [],
      row: null,
      hub,
      selected: null,
      selectionLost: false,
      current: null,
      objectives: [],
      total: 0,
      settled: 0,
      dueCount: 0,
      sectionLabel: null,
      nextLabel: null,
      primaryLabel: null,
      primaryKind: null,
      estimateLabel: deskEstimateLabel(estimate),
      estimateState: deskEstimateState(estimate),
      estimateError: estimate && estimate.error ? estimate.error : null,
      lastTouched: null,
      touchedSource: null
    }
  }
  const readState = outlineState || (outline ? 'ready' : 'idle')
  const objectives = outline && Array.isArray(outline.objectives) ? outline.objectives : []
  // Only an unanswered outline (failed or in flight) uses the row's current-objective pointer.
  // A ready outline with zero objectives is a real answer: this course has no path yet.
  const current = mainlineObjective(row, objectives) || (readState !== 'ready' ? rowFallbackCurrent(row) : null)
  const total = outline && Number(outline.total) ? Number(outline.total) : objectives.length
  const settled = objectives.filter((entry) => entry.independent).length
  const dueCount = objectives.filter((entry) => entry.state === 'review_due').length
  const next = row.next_step || {}
  return {
    rows,
    row,
    hub,
    selected,
    selectionLost,
    current,
    objectives,
    total,
    settled,
    dueCount,
    sectionLabel: current && current.ordinal ? CB_COPY.sectionLabel(current.ordinal, total) : null,
    nextLabel: next.label || 'No next step was recorded for this course.',
    primaryLabel: DESK_PRIMARY_LABEL[next.kind] || 'Open the lesson',
    primaryKind: next.kind || 'start_lesson',
    estimateLabel: deskEstimateLabel(estimate),
    estimateState: deskEstimateState(estimate),
    estimateError: estimate && estimate.error ? estimate.error : null,
    // `last_opened_at` is this section's newest lesson run; `updated_at` is the enrollment's own
    // write. The section wins when it exists, and the label says which clock was read.
    lastTouched: (current && current.last_opened_at) || row.updated_at || null,
    touchedSource: current && current.last_opened_at ? 'section' : 'course'
  }
}

function DeskLabel({ children, as }) {
  const tag = as || 'div'
  return jsx(tag, {
    style: {
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      letterSpacing: '0.01em',
      color: 'var(--cb-ink-soft)',
      margin: 0
    },
    children
  })
}

/** Deterministic initial stamp: kept as plain text for hosts that render no SVG. */
function courseStampText(title) {
  return cbCourseMonogram(title)
}

/** The course cover: deterministic monogram as type, with the title adjacent. */
function CourseStamp({ title, large, courseId, identity }) {
  return jsx('div', {
    'data-cb-course-stamp': '',
    title: title || 'Course',
    'aria-hidden': 'true',
    style: { flex: '0 0 auto', display: 'flex', alignItems: 'center' },
    children: jsx('span', {
      style: {
        fontFamily: CB_SERIF,
        fontSize: large ? CB_TYPE.heading : CB_TYPE.meta,
        fontWeight: 600,
        letterSpacing: '0.04em',
        color: 'var(--cb-ink-soft)'
      },
      children: courseStampText(title || 'Course')
    })
  })
}

/* ── The shelf object: cover, goal and a four-segment path (H-99) ────────────────────────── */

const CB_PATH_TONE = {
  done: 'var(--cb-field)',
  due: 'var(--cb-ochre)',
  current: 'var(--cb-accent)',
  quiet: 'var(--cb-rule)',
  empty: 'var(--cb-rule)'
}

/**
 * The evidence record under a cover. One segment per objective for courses small enough to draw
 * honestly; a larger course shows the count only rather than inventing a bucket. Colour never
 * carries the state alone: the caption does.
 */
function CoursePath({ row }) {
  const segments = cbCoursePathSegments(row)
  return jsxs('div', {
    'data-cb-course-path': String(segments.length),
    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', marginTop: '0.1rem' },
    children: [
      segments.length
        ? jsx('div', {
            'aria-hidden': 'true',
            style: { display: 'flex', gap: '0.2rem', height: '0.3rem', alignItems: 'stretch' },
            children: segments.map((segment) =>
              jsx(
                'span',
                {
                  style: {
                    flex: '1 1 0',
                    minWidth: 0,
                    background: CB_PATH_TONE[segment.state] || CB_PATH_TONE.quiet,
                    opacity: segment.state === 'quiet' || segment.state === 'empty' ? 0.45 : 1
                  }
                },
                segment.index
              )
            )
          })
        : null,
      jsx('div', {
        'data-cb-course-path-caption': '',
        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.4, color: 'var(--cb-ink-soft)' },
        children: cbCoursePathCaption(row)
      })
    ]
  })
}

/**
 * One openable record inside a shelf disclosure.
 *
 * H-201: this control must say what it opens. A bare "Open" beside two course names gave the
 * learner no way to tell which enrollment a click would land on, so the visible label carries the
 * member's own title. The ring is the identity ring (H-146a/H-150c): a Tab stop paints it, a
 * pointer press does not, and it is drawn inside the row so a scroll container cannot clip it.
 */
function ShelfMemberOpen({ member, onOpen }) {
  const [keyboardFocus, setKeyboardFocus] = useState(false)
  const title = member.title || 'Untitled course'
  return jsx(CbAction, {
    variant: 'tertiary',
    'data-cb-shelf-member-open': member.enrollment_id,
    'data-cb-focus-ring': keyboardFocus ? 'visible' : 'none',
    'aria-label': `Open ${title}, updated ${whenLabel(member.updated_at)}`,
    onFocus: (event) => setKeyboardFocus(focusRingVisible(event && event.currentTarget)),
    onBlur: () => setKeyboardFocus(false),
    onClick: () => onOpen(member),
    style: {
      outline: keyboardFocus ? CB_FOCUS_RING : 'none',
      outlineOffset: '2px',
      borderRadius: '2px'
    },
    children: `Open “${title}”`
  })
}

/**
 * The disclosure under a grouped cover. It is the only place the other records for a shared
 * course are named, so grouping never hides a plan or an enrollment: each line is openable.
 *
 * H-201: the member rows used to be built as `jsxs('li', props, children, key)`. React's
 * jsx-runtime takes children inside `props` and its third argument is the key, so the children
 * array became a key and every row painted an empty `<li>` — zero controls, measured in the live
 * window. Children now travel in `props` like every other node in this file. A shelf that has no
 * open handler says so in plain language and offers the Library instead of rendering nothing.
 */
function ShelfDisclosure({ group, onOpen, onOpenLibrary, label }) {
  if (!group || !group.label) return null
  return jsxs('details', {
    'data-cb-shelf-versions': group.key,
    style: { marginTop: '0.1rem' },
    children: [
      jsx('summary', {
        className: 'cursor-pointer',
        'aria-label': `${label || 'Records'} for ${group.primary.title}`,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '0.3rem',
          minHeight: '1.75rem',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.caption,
          fontWeight: 600,
          color: 'var(--cb-ink-soft)'
        },
        children: [
          jsx(sdk.Codicon, { name: 'chevron-right', size: CB_ICON_UI }, 'chevron'),
          jsx('span', { children: group.label }, 'label')
        ]
      }, 'summary'),
      jsx('ul', {
        style: {
          margin: '0.2rem 0 0',
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.25rem'
        },
        children: group.members.map((member) =>
          jsxs(
            'li',
            {
              style: {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.25rem 0.5rem',
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.caption,
                lineHeight: 1.45,
                color: 'var(--cb-ink-soft)'
              },
              children: [
                jsxs('span', { style: { minWidth: 0, overflowWrap: 'anywhere' }, children: [
                  jsx('span', { children: member.title || 'Untitled' }, 'title'),
                  jsx('span', { children: ` · ${whenLabel(member.updated_at)}` }, 'when')
                ] }, 'record'),
                onOpen
                  ? jsx(ShelfMemberOpen, { member, onOpen }, 'open')
                  : jsxs('span', {
                      style: {
                        display: 'inline-flex',
                        flexWrap: 'wrap',
                        alignItems: 'center',
                        gap: '0.25rem 0.5rem'
                      },
                      children: [
                        jsx('span', { children: `Can’t open “${member.title || 'this record'}” from here.` }, 'note'),
                        onOpenLibrary
                          ? jsx(CbAction, {
                              variant: 'tertiary',
                              onClick: onOpenLibrary,
                              children: 'Open the Library shelf'
                            }, 'action')
                          : jsx('span', { children: 'Open it from the Library shelf.' }, 'action')
                      ]
                    }, 'open')
              ]
            },
            member.enrollment_id
          )
        )
      }, 'rows')
    ]
  })
}

/**
 * One course on a shelf: a 16:9 cover field on `paper-raised` carrying the seal and the
 * two-letter monogram, then the title, the goal line and the four-segment path. The cover is
 * deterministic (`cbSealStation(course_id)` and the monogram from the title), so reloading the
 * route paints the same object, and `data-cb-course-cover` carries the content fingerprint.
 */
function CourseCover({ row, identity, detail, action, group, onOpenMember, onOpenLibrary, testId }) {
  // The Courses card reads the same approved display cover the workshop does (D-007).
  // UI-K9: a course whose pack names no family gets the printed cover — its own title set on kit
  // paper behind a measured rule, with the course's initial as a stamp — and never the kit's
  // lesson room, whose art is a cafe study room and would claim a subject this course may not
  // have. The kit plate still wins whenever one exists for the subject.
  const provenance = row && row.provenance && typeof row.provenance === 'object' ? row.provenance : {}
  const kit = cb3KitCoverFor({ pack_id: provenance.pack_id || (row && row.pack_id), title: row && row.title })
  const coverSrc = kit ? cb3KitSource(kit.id3x2) : null
  return jsxs('article', {
    'data-cb-course-cover': cbShelfFingerprint(row),
    'data-cb-course-id': row.course_id || '',
    'data-cb-all-courses-row': testId || undefined,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      minWidth: 0,
      paddingTop: '0.55rem',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs('div', {
        'data-cb-cover-field': '',
        'data-cb-cover-kind': coverSrc ? 'kit' : 'letter',
        style: {
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: '0.5rem',
          aspectRatio: '16 / 9',
          minHeight: '3rem',
          maxHeight: '7.5rem',
          padding: 0,
          boxSizing: 'border-box',
          background: 'var(--cb-paper-raised)',
          overflow: 'hidden'
        },
        children: coverSrc
          ? jsx('img', {
              src: coverSrc,
              alt: '',
              'aria-hidden': 'true',
              'data-cb-cover-image': '',
              'data-cb-cover-plate': kit.id3x2.split('.').pop(),
              style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center' }
            })
          : jsxs('div', {
              'data-cb-cover-letter': '',
              style: {
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                width: '100%',
                height: '100%',
                padding: '0.45rem 0.55rem',
                boxSizing: 'border-box',
                border: '1px solid var(--cb-rule)',
                overflow: 'hidden'
              },
              children: [
                jsx('div', {
                  'aria-hidden': 'true',
                  style: {
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.meta,
                    fontWeight: 600,
                    letterSpacing: '0.08em',
                    lineHeight: 1,
                    color: 'var(--cb-ink-soft)'
                  },
                  children: cbCourseMonogram(row.title)
                }, 'stamp'),
                jsx('div', {
                  style: {
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.meta,
                    fontWeight: 600,
                    lineHeight: 1.25,
                    color: 'var(--cb-ink)',
                    overflowWrap: 'anywhere'
                  },
                  children: row.title || 'Untitled course'
                }, 'words')
              ]
            })
      }),
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: CB_TYPE.lead,
          fontWeight: 600,
          lineHeight: 1.3,
          color: 'var(--cb-ink)',
          overflowWrap: 'anywhere'
        },
        children: row.title || 'Untitled course'
      }),
      jsx('p', {
        'data-cb-course-goal': '',
        style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: cbCourseGoalLine(row)
      }),
      jsx(CoursePath, { row }),
      detail ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem' }, children: detail }) : null,
      group && group.label ? jsx(ShelfDisclosure, { group, onOpen: onOpenMember, onOpenLibrary }) : null,
      action ? jsx('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' }, children: action }) : null
    ]
  })
}

/**
 * H-150c — is this focus worth a ring?
 *
 * `:focus-visible` is the identity's rule (H-146a): a keyboard stop paints, a pointer press on the
 * row leaves nothing behind. An engine that cannot answer the query keeps the ring, because losing
 * it for a keyboard user is the failure this card is about.
 */
function shelfRingVisible(node) {
  if (!node || typeof node.matches !== 'function') return true
  try {
    return node.matches(':focus-visible')
  } catch (error) {
    return true
  }
}

/**
 * One pack on the Library shelf: a compact row, not a course cover.
 *
 * A pack is not a course. Reusing `CourseCover` here put a 16:9 decorative field, a 40 px
 * Atlas Lamp seal and a title-derived monogram above every pack. Two test packs whose titles
 * began with the same two words therefore showed the same "HL" mark and the same empty cover,
 * which read as a product logo and made the rows impossible to tell apart. The pack's own title,
 * source and state are the identity; no seal or monogram is invented for it.
 *
 * An empty pack keeps the row honest: it names the missing sections and still offers Preview
 * (the manifest is inspectable) without a four-segment path that would imply content.
 */
function PackShelfRow({ row, group, onOpenMember, onPreview, selected }) {
  const [keyboardFocus, setKeyboardFocus] = useState(false)
  const summary = (row && row.evidence_summary) || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  const empty = total === 0
  const title = row.title || 'Untitled pack'
  const source = sourceLabel(row.provenance && row.provenance.source)
  const openPreview = () => { if (onPreview) onPreview(row) }
  return jsxs('article', {
    'data-cb-pack-row': cbShelfFingerprint(row),
    'data-cb-pack-empty': empty ? 'true' : 'false',
    'data-cb-pack-selected': selected ? 'true' : undefined,
    style: {
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.35rem',
      minWidth: 0,
      padding: '0.55rem 0.6rem',
      borderTop: '1px solid var(--cb-rule)',
      background: selected ? 'var(--cb-accent-soft)' : 'transparent'
    },
    children: [
      // H-150: the whole row is the target. One real button paints over the row's empty space
      // and takes the keyboard (Enter/Space); the row content is inert, and the single Preview
      // affordance below sits above the overlay. This mirrors the host's own RowButton pattern.
      //
      // H-150c: the ring is drawn *inside* the row. The old `outlineOffset: '2px'` put the left
      // and right strokes outside a row that sits flush with `MAIN.overflow-auto`, so only the top
      // and bottom strokes ever painted. A negative offset keeps the same 2px accent ring (the
      // H-146a identity ring) entirely within the row's own box, where the scroll container cannot
      // clip it. `data-cb-pack-row-action` is the stable handle the shelf uses to put focus back on
      // this row after the preview is dismissed.
      onPreview
        ? jsx(sdk.RowButton, {
            'aria-label': `Preview ${title}`,
            'aria-pressed': selected ? 'true' : 'false',
            'data-cb-pack-row-action': row.enrollment_id,
            'data-cb-focus-ring': keyboardFocus ? 'visible' : 'none',
            className: 'absolute inset-0 rounded-[2px]',
            onBlur: () => setKeyboardFocus(false),
            onFocus: (event) => setKeyboardFocus(shelfRingVisible(event && event.currentTarget)),
            style: {
              outline: keyboardFocus ? '2px solid var(--cb-accent)' : 'none',
              outlineOffset: '-2px',
              borderRadius: '2px'
            },
            onKeyDown: (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                openPreview()
              }
            },
            onClick: openPreview
          })
        : null,
      jsxs('div', {
        className: 'pointer-events-none flex flex-wrap items-start justify-between gap-2',
        children: [
          jsxs('div', {
            style: { display: 'flex', minWidth: 0, flexDirection: 'column', gap: '0.2rem' },
            children: [
              jsx('h3', {
                style: {
                  margin: 0,
                  fontFamily: CB_SERIF,
                  fontSize: CB_TYPE.lead,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  color: 'var(--cb-ink)',
                  overflowWrap: 'anywhere'
                },
                children: title
              }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                children: [
                  jsx(sdk.Badge, { variant: 'muted', size: 'xs', children: source }),
                  jsx('span', {
                    children: empty ? 'No sections yet' : plural(total, 'section', 'sections')
                  }),
                  selected
                    ? jsxs('span', {
                        'data-cb-pack-selected-cue': '',
                        className: 'inline-flex items-center gap-1 font-semibold',
                        style: { color: 'var(--cb-accent)' },
                        children: [
                          jsx(sdk.Codicon, { name: 'check', size: CB_ICON_UI }),
                          jsx('span', { children: 'Selected' })
                        ]
                      })
                    : null
                ]
              })
            ]
          })
        ]
      }),
      empty
        ? jsx('p', {
            'data-cb-pack-empty-note': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: 'Nothing to open yet. Preview it to see the manifest.'
          })
        : jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
            children: [
              jsx('p', {
                'data-cb-pack-goal': '',
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: cbCourseGoalLine(row)
              }),
              jsx(CoursePath, { row })
            ]
          }),
      group && group.label ? jsx(ShelfDisclosure, { group, onOpen: onOpenMember }) : null,
      onPreview
        ? jsx(sdk.Button, {
            className: 'relative self-start',
            'aria-label': `Preview ${title}`,
            onClick: openPreview,
            size: 'sm',
            variant: selected ? 'secondary' : 'text',
            children: 'Preview'
          })
        : null
    ]
  })
}

/** A real-state progress strip: one segment per objective, painted from its own state. */
function DeskProgress({ objectives }) {
  const list = Array.isArray(objectives) ? objectives.slice(0, 12) : []
  if (list.length === 0) return null
  return jsx('div', {
    'data-cb-desk-progress': '',
    'aria-hidden': 'true',
    style: { display: 'flex', gap: '0.18rem', height: '0.3rem', alignItems: 'stretch' },
    children: list.map((objective) => {
      const tone = DESK_STATE_TONE[objective.state] || 'quiet'
      const started = objective.state !== 'not_started'
      return jsx(
        'span',
        {
          style: {
            flex: '1 1 0',
            minWidth: 0,
            background: deskToneColor(tone),
            opacity: started ? 1 : 0.32
          }
        },
        objective.objective_id
      )
    })
  })
}

/**
 * The desk's facts, in the same voice as course detail's hero line: one line, the value then its
 * caption, separated by a rule. It replaces the three equal stat cards (H-94 V2-5): there is no
 * percentage, no streak and no invented goal, only counts the backend actually recorded.
 */
function DeskFacts({ desk }) {
  const current = desk.current
  const facts = [
    current ? { value: CB_COPY.stateWord(current.state), label: 'This section' } : null,
    { value: `${desk.settled} of ${desk.total}`, label: 'With evidence' },
    desk.dueCount > 0 ? { value: String(desk.dueCount), label: 'Due now' } : null
  ].filter(Boolean)
  return jsx('div', {
    'data-cb-desk-facts': String(facts.length),
    style: { borderTop: '1px solid var(--cb-rule)', paddingTop: '0.55rem' },
    children: jsx(HeroFacts, { facts })
  })
}

/**
 * H-146 — the focus ring for one classroom tab.
 *
 * The host stylesheet owns `:focus` and its reset clears the user agent's ring on a bare `button`,
 * and this plugin has no stylesheet of its own to declare `:focus-visible` in — an inline `outline`
 * is the only hook left. So the ring is state on the control: it is painted while the tab matches
 * `:focus-visible` and it is `none` otherwise, matching
 * `docs/COURSEBOOK-VISUAL-IDENTITY-V2.md` (2px `accent`, 2px offset, a 2px radius on the ring).
 * It is never removed for keyboard users: a Tab stop always paints it, a pointer click does not.
 */
const CB_FOCUS_RING = '2px solid var(--cb-accent)'

/**
 * Does this focus deserve a ring? `:focus-visible` is the identity's rule, so a pointer click on a
 * plain text tab leaves nothing behind while a Tab stop always paints. The query is asked on the
 * focused node itself; an engine that cannot answer keeps the ring on focus rather than losing it
 * for a keyboard user.
 */
function focusRingVisible(node) {
  if (!node || typeof node.matches !== 'function') return true
  try {
    return node.matches(':focus-visible')
  } catch (error) {
    return true
  }
}

/**
 * H-189 — the classroom cover.
 *
 * The owner's verdict on the drawn contour was that it read as code, not as a place: an
 * `aria-hidden` ridge drawing above each name, with no course fact inside it. So a classroom now
 * carries one of exactly two covers, and neither is invented here:
 *
 *   * an authored artifact, only when a `library.list` row actually declares one
 *     (`row.cover = { artifact_id, caption, … }`), served through the one media route and always
 *     with a non-empty `alt` plus the authored text equivalent visible underneath;
 *   * otherwise a quiet typographic paper cover: the classroom's own name, the subject it records
 *     (level/locale when the backend recorded one), and its monogram. No illustration, no ridge
 *     line, no equalizer.
 *
 * The two classrooms on a shelf are told apart by their names and subjects, never by decoration.
 * A row with no cover and no caption therefore cannot produce an empty `alt`: it produces type.
 */
function cbCoverMedia(row) {
  const cover = row && row.cover
  if (!cover || typeof cover !== 'object') return null
  const artifactId = cover.artifact_id || cover.artifact
  if (!artifactId) return null
  const caption = typeof cover.caption === 'string' ? cover.caption.trim() : ''
  // No caption means no `alt`, and an image with an empty `alt` is a decorative lie about a
  // teaching artifact. Type is the honest fallback, not an empty alt.
  if (!caption) return null
  return {
    artifact_id: String(artifactId),
    caption,
    text_equivalent:
      typeof cover.text_equivalent === 'string' && cover.text_equivalent.trim()
        ? cover.text_equivalent.trim()
        : caption,
    provenance: typeof cover.provenance === 'string' ? cover.provenance : null
  }
}

/** The subject a classroom records, in the backend's own words, or nothing. */
function cbCoverSubject(row) {
  const level = row && typeof row.level_label === 'string' ? row.level_label.trim() : ''
  if (level) return level
  const locale = row && typeof row.locale === 'string' ? row.locale.trim() : ''
  if (locale) return locale
  return null
}

function ClassroomCover({ slot, compact, hideTitle }) {
  const row = slot.row || {}
  const media = cbCoverMedia(row)
  // One hook, called every render: an absent artifact is a synchronous text state, not a request.
  const preview = useArtifactPreview(media ? media.artifact_id : null)
  const subject = cbCoverSubject(row)
  const height = compact ? 44 : 56
  const frame = {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    gap: '0.1rem',
    minHeight: `${height}px`,
    minWidth: 0,
    padding: '0.3rem 0.45rem',
    boxSizing: 'border-box',
    background: 'var(--cb-paper)',
    borderTop: '2px solid var(--cb-rule)'
  }
  if (media && preview.state === 'ready' && preview.mime && preview.mime.startsWith('image/') && preview.data_url) {
    return jsxs('figure', {
      'data-cb-slot-cover': 'artifact',
      style: { ...frame, margin: 0, padding: 0, gap: 0, borderTop: '2px solid var(--cb-lamp)' },
      children: [
        jsx('img', {
          alt: media.caption,
          src: preview.data_url,
          loading: 'lazy',
          style: { display: 'block', width: '100%', height: `${height}px`, objectFit: 'cover' }
        }, 'image'),
        // The authored text equivalent stays readable, so the cover is never only a picture.
        jsx('figcaption', {
          'data-cb-slot-cover-caption': '',
          style: {
            padding: '0.15rem 0.45rem 0.25rem',
            fontFamily: CB_SANS,
            fontSize: CB_TYPE.caption,
            lineHeight: 1.35,
            color: 'var(--cb-ink-soft)',
            overflowWrap: 'anywhere'
          },
          children: media.text_equivalent
        }, 'caption')
      ]
    })
  }
  return jsxs('div', {
    'data-cb-slot-cover': 'typographic',
    style: frame,
    children: [
      jsxs('span', {
        style: { display: 'flex', alignItems: 'baseline', gap: '0.35rem', minWidth: 0 },
        children: [
          jsx('span', {
            'aria-hidden': 'true',
            style: {
              flex: '0 0 auto',
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              letterSpacing: '0.06em',
              color: 'var(--cb-ink-soft)'
            },
            children: courseStampText(slot.name || (row && row.title) || 'Coursebook')
          }, 'monogram'),
          // When the card owns the heading (`hideTitle`), the cover carries the monogram and the
          // subject only. Painting the title here too made every shelf card read title → title.
          hideTitle
            ? null
            : jsx('span', {
                'data-cb-slot-cover-title': '',
                style: {
                  minWidth: 0,
                  fontFamily: CB_SERIF,
                  fontSize: compact ? CB_TYPE.meta : CB_TYPE.body,
                  fontWeight: 600,
                  lineHeight: 1.25,
                  color: 'var(--cb-ink)',
                  whiteSpace: 'normal',
                  overflowWrap: 'anywhere'
                },
                children: slot.name || (row && row.title) || 'Classroom'
              }, 'title')
        ]
      }),
      subject
        ? jsx('span', {
            'data-cb-slot-cover-subject': '',
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              lineHeight: 1.3,
              color: 'var(--cb-ink-soft)',
              whiteSpace: 'normal',
              overflowWrap: 'anywhere'
            },
            children: subject
          }, 'subject')
        : null
    ]
  })
}

/** One classroom tile on the shelf: its own cover, name, next stop and last touch. */
function SlotTab({ slot, isCurrent, onSelect, compact }) {
  const [focused, setFocused] = useState(false)
  const motion = useCbMotion()
  // H-189: switching classrooms has one visible consequence — the newly selected card settles.
  // It is one beat on the card that changed, re-armed by the course id, never a looping entrance.
  const landed = useCbSelectionSettle(motion, `${slot.course_id}|${isCurrent ? 'current' : 'available'}`)
  const row = slot.row || {}
  const next = row.next_step && row.next_step.label ? row.next_step.label : null
  return jsxs('button', {
    type: 'button',
    'data-cb-slot-tab': slot.course_id,
    'data-cb-slot-state': isCurrent ? 'current' : 'available',
    'data-cb-slot-motion': motion.reduced ? 'static' : landed ? 'settled' : 'settling',
    'data-cb-focus-ring': focused ? 'visible' : 'none',
    'aria-current': isCurrent ? 'true' : undefined,
    onFocus: (event) => setFocused(focusRingVisible(event.currentTarget)),
    onBlur: () => setFocused(false),
    onClick: () => {
      if (!isCurrent) onSelect(slot.course_id)
    },
    style: {
      minHeight: '44px',
      maxWidth: '100%',
      flex: '1 1 10rem',
      padding: '0.5rem 0.6rem 0.55rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      alignItems: 'stretch',
      textAlign: 'left',
      background: isCurrent ? 'var(--cb-paper-raised)' : 'transparent',
      border: 'none',
      borderTop: `2px solid ${isCurrent ? 'var(--cb-lamp)' : 'var(--cb-rule)'}`,
      borderRadius: '2px',
      outline: focused ? CB_FOCUS_RING : 'none',
      outlineOffset: '2px',
      cursor: isCurrent ? 'default' : 'pointer',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.meta,
      color: isCurrent ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
      overflowWrap: 'anywhere',
      ...cbSettleFrame(motion, landed, { beat: 'route', props: 'opacity, transform', from: 'translateY(3px)', fromOpacity: 0.9 })
    },
    children: [
      jsx(ClassroomCover, { slot, compact }, 'cover'),
      jsx('span', {
        style: { fontWeight: isCurrent ? 600 : 400, lineHeight: 1.35 },
        children: slot.name
      }, 'name'),

      jsx('span', {
        'data-cb-slot-next': next ? 'recorded' : 'none',
        style: { fontSize: CB_TYPE.caption, lineHeight: 1.35, color: 'var(--cb-ink-soft)' },
        children: next || 'Next step not recorded'
      }, 'next'),
      jsx('span', {
        style: { fontSize: CB_TYPE.caption, lineHeight: 1.35, color: 'var(--cb-ink-soft)' },
        children: slot.updated_at ? `Last touched ${whenLabel(slot.updated_at)}` : 'Nothing touched yet'
      }, 'touched')
    ]
  })
}


/**
 * H-146 — the classroom rail, kept as the classroom shelf: up to four tiles, one `aria-current`,
 * and the active classroom named in words underneath. Above four, the shelf becomes one labelled
 * select rather than a wrapping card grid. A switch changes only shell state:
 * `onSelect(course_id)` is a local selection, never `?profile=`, a host route read, or a backend
 * write. Each tile carries only its own deterministic contour, name, recorded next stop and last
 * touch.
 */
function SlotRail({ hub, selected, onSelect, onShowAll, onCreate }) {
  const all = hub && Array.isArray(hub.all) ? hub.all : []
  if (all.length === 0) return null
  const width = useCbViewportWidth()
  const compact = width > 0 && width < 620
  const active = selected || all[0]
  const useSelect = all.length > HUB_SLOT_LIMIT
  const nameCount = {}
  all.forEach((slot) => {
    nameCount[slot.name] = (nameCount[slot.name] || 0) + 1
  })
  // Two classrooms can share a learner label; the course title disambiguates in the select only,
  // where there is room for it. Tabs keep the short identity.
  const optionLabel = (slot) =>
    nameCount[slot.name] > 1 && slot.title && slot.title !== slot.name ? `${slot.name} · ${slot.title}` : slot.name
  const quiet = { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }
  const heading = (key) => jsxs('div', {
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.25rem 0.75rem' },
    children: [
      jsx(DeskLabel, { children: 'Your other classrooms' }, 'label'),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.25rem 0.75rem' },
        children: [
          onCreate
            ? jsx('span', {
                'data-cb-shelf-new-course': '',
                style: { display: 'inline-flex', alignItems: 'center' },
                children: jsx(sdk.Button, {
                  variant: 'secondary',
                  size: 'sm',
                  style: { minHeight: '44px' },
                  onClick: onCreate,
                  children: 'New course'
                })
              }, 'new')
            : null,
          onShowAll
            ? jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onShowAll, children: 'All courses' }, 'all')
            : null
        ]
      }, 'doors')
    ]
  }, key)
  const current = (key) => jsx('p', {
    'data-cb-slot-current': active.course_id,
    'id': 'cb-hub-slot-current',
    style: { ...quiet, color: 'var(--cb-ink)' },
    children: `Showing ${active.name}`
  }, key)
  const disclosure = (key) =>
    active.recordCount > 1
      ? jsx('p', {
          'data-cb-slot-disclosure': String(active.recordCount),
          style: quiet,
          children: `This course has ${active.recordCount} progress records; showing the most recent.`
        }, key)
      : null

  let control
  if (all.length === 1) {
    // One classroom is named, not turned into a control that can only select itself. It still
    // carries its own cover, because one classroom is still a place.
    control = jsxs('div', {
      'data-cb-slot-rail': 'single',
      'data-cb-slot-single': active.course_id,
      style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
      children: [
        heading('heading'),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.6rem', minWidth: 0 },
          children: [
            jsx('div', {
              style: { width: '11rem', maxWidth: '100%', flex: '0 0 auto', minWidth: 0 },
              children: jsx(ClassroomCover, { slot: active, compact }, 'cover')
            }, 'cover'),
            jsx('span', {
              style: {
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.body,
                fontWeight: 600,
                color: 'var(--cb-ink)',
                overflowWrap: 'break-word'
              },
              children: active.name
            }, 'name')
          ]
        }, 'identity'),
        current('current'),
        disclosure('disclosure')
      ]
    })
  } else if (useSelect) {
    control = jsxs('div', {
      'data-cb-slot-rail': 'select',
      style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
      children: [
        heading('heading'),
        jsxs('div', {
          style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
          children: [
            jsx('label', {
              htmlFor: 'cb-hub-classroom',
              style: { ...quiet, fontWeight: 600 },
              children: 'Choose a classroom'
            }, 'label'),
            jsx('select', {
              id: 'cb-hub-classroom',
              'data-cb-classroom-select': '',
              'aria-describedby': 'cb-hub-slot-current',
              value: active.course_id,
              onChange: (event) => onSelect(event.target.value),
              style: {
                width: '100%',
                maxWidth: '22rem',
                minHeight: '44px',
                padding: '0.35rem 0.5rem',
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.meta,
                color: 'var(--cb-ink)',
                background: 'var(--cb-paper-raised)',
                border: '1px solid var(--cb-ink)',
                borderRadius: '2px',
                boxSizing: 'border-box'
              },
              children: all.map((slot) =>
                jsx('option', { value: slot.course_id, children: optionLabel(slot) }, slot.course_id)
              )
            }, 'select')
          ]
        }, 'field'),
        current('current'),
        disclosure('disclosure')
      ]
    })
  } else {
    control = jsxs('div', {
      'data-cb-slot-rail': 'tabs',
      style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', minWidth: 0 },
      children: [
        heading('heading'),
        jsx('nav', {
          'data-cb-classroom-tabs': '',
          'aria-label': 'Classrooms',
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'stretch', gap: '0.4rem', minWidth: 0 },
          children: all.map((slot) => {
            const isCurrent = slot.course_id === active.course_id
            return jsx(SlotTab, { slot, isCurrent, onSelect, compact }, slot.course_id)
          })
        }, 'tabs'),
        current('current'),
        disclosure('disclosure')
      ]
    })
  }

  return jsx('section', {
    'data-cb-slot-rail-section': '',
    'data-cb-classroom-shelf': '',
    'aria-label': 'Classroom shelf',
    style: { maxWidth: CB_MEASURE, minWidth: 0 },
    children: control
  })
}

/* ── H-176 — the trailhead: course identity, companion and the trail ───────────────────────
 * The plate is one object, not a card grid: a deterministic contour derived from the course id
 * and title (so two classrooms never share a beige rectangle), the learner's own Hermes pet at
 * the edge, one sentence naming the next stop, then one primary Continue. The contour is inline
 * SVG and `aria-hidden`; the pet is drawn from the host's own `pet.info` seam and is absent when
 * the host has no pet. Nothing here invents a fact, an avatar or a count.
 */

/** Deterministic ridge geometry: same course id/title paints the same three ridgelines. */
function cbCourseContour(courseId, title) {
  const seed = cbStableHash(`${courseId || ''}|${title || ''}`)
  const ridges = []
  for (let line = 0; line < 3; line += 1) {
    const points = []
    for (let step = 0; step <= 6; step += 1) {
      const bit = (seed >>> ((line * 7 + step * 3) % 29)) & 7
      const x = (200 / 6) * step
      const y = 30 + line * 22 + (bit - 3) * 3 + (step % 2 ? 3 : -2)
      points.push(`${x.toFixed(1)},${y.toFixed(1)}`)
    }
    ridges.push(`M${points.join(' L')}`)
  }
  return ridges
}

/** One course's contour. Decorative: the title beside it is the identity, not the drawing. */
function CourseContour({ row, title, height, opacity }) {
  const ridges = cbCourseContour(row && row.course_id, title || (row && row.title) || '')
  const h = Number(height) || 120
  return jsxs('svg', {
    'data-cb-course-contour': row && row.course_id ? String(row.course_id) : '',
    'aria-hidden': 'true',
    focusable: 'false',
    viewBox: '0 0 200 120',
    preserveAspectRatio: 'none',
    style: { display: 'block', width: '100%', height: `${h}px`, overflow: 'hidden' },
    children: [
      jsx('line', {
        x1: 0,
        y1: 102,
        x2: 200,
        y2: 102,
        stroke: 'var(--cb-rule)',
        strokeWidth: '1'
      }, 'horizon'),
      jsx('circle', {
        cx: 170,
        cy: 24,
        r: 8,
        fill: 'none',
        stroke: 'var(--cb-lamp)',
        strokeWidth: '1.5'
      }, 'mark'),
      ...ridges.map((d, index) =>
        jsx('path', {
          d,
          fill: 'none',
          stroke: index === 0 ? 'var(--cb-field)' : 'var(--cb-ink-soft)',
          strokeWidth: index === 0 ? '1.5' : '1',
          strokeLinecap: 'round',
          strokeLinejoin: 'round',
          opacity: opacity === undefined ? 0.55 - index * 0.13 : opacity
        }, `ridge-${index}`)
      )
    ]
  })
}

/** Profile-scoped cache: one `pet.info` read and one decoded sheet per app session. */
const CB_COMPANION_INFO = new Map()
const CB_COMPANION_SHEETS = new Map()

function cbCompanionProfile() {
  // The live host profile wins; the plugin scope is only the fallback for an older host.
  try {
    const atom = sdk.host && sdk.host.state ? sdk.host.state.profile : null
    const live = atom && typeof atom.get === 'function' ? atom.get() : null
    if (live) return String(live)
  } catch (error) {
    // Fall through to the plugin scope.
  }
  try {
    return currentScope().profile || 'default'
  } catch (error) {
    return 'default'
  }
}

/** -32601 is "no such method": the host predates `pet.info.meta`, so ask the full method. */
function cbHostMethodMissing(error) {
  if (!error) return false
  const code = error.code !== undefined ? error.code : error.error && error.error.code
  if (code === -32601 || code === '-32601') return true
  return /method not found|-32601/i.test(String(error.message || ''))
}

/**
 * The learner's own Hermes pet, through the one supported host seam.
 *
 * Meta first (`pet.info.meta`), then the sheet (`pet.info`). A host without `host.request`, a
 * disabled or absent pet, an unsupported older gateway and a failed read all resolve to `null`,
 * and the plate simply carries no companion. The response is cached per live profile so a route
 * change does not re-fetch a spritesheet.
 */
function useStudyCompanion(enabled) {
  const profile = cbCompanionProfile()
  const [pet, setPet] = useState(null)
  useEffect(() => {
    if (enabled === false) {
      setPet(null)
      return undefined
    }
    const request = sdk.host && typeof sdk.host.request === 'function' ? sdk.host.request : null
    if (!request) {
      setPet(null)
      return undefined
    }
    if (CB_COMPANION_INFO.has(profile)) {
      setPet(CB_COMPANION_INFO.get(profile))
      return undefined
    }
    let cancelled = false
    // Meta first: the lightweight answer says whether a pet is enabled without moving a sheet.
    // A gateway that does not know `pet.info.meta` (-32601) falls through to the full read.
    const read = (async () => {
      let meta = null
      try {
        meta = await request('pet.info.meta', { profile })
      } catch (error) {
        if (!cbHostMethodMissing(error)) return null
      }
      if (meta && meta.enabled === false) return null
      try {
        return await request('pet.info', { profile })
      } catch (error) {
        return null
      }
    })()
    read
      .then((info) => {
        const usable =
          info &&
          info.enabled === true &&
          Boolean(info.spritesheetBase64) &&
          Number(info.frameW) > 0 &&
          Number(info.frameH) > 0
            ? info
            : null
        CB_COMPANION_INFO.set(profile, usable)
        if (!cancelled) setPet(usable)
      })
      .catch(() => {
        CB_COMPANION_INFO.set(profile, null)
      })
    return () => {
      cancelled = true
    }
  }, [enabled, profile])
  return pet
}

/**
 * The learner's own pet, one frame at a time.
 *
 * H-189: the sheet already carries an `idle` row, so the companion uses it at a deliberately low
 * cadence (about 2.4 frames a second) instead of freezing on frame 0. Three rules keep it from
 * becoming decoration:
 *
 *   * reduced motion (or a sheet with one frame) paints frame 0 and never starts a timer;
 *   * a hidden document stops the timer, so a background tab does no drawing;
 *   * the frames come only from the host's own `pet.info` sheet — there is no second avatar, no
 *     dialogue and no invented pose.
 *
 * The canvas stays `aria-hidden`; the adjacent name is the visible copy.
 */
function StudyCompanion({ info, size, label }) {
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const motion = useCbMotion()
  const visible = useCbPageVisible()
  const [loaded, setLoaded] = useState(0)
  const [frame, setFrame] = useState(0)
  const px = Number(size) || 64
  const frameW = info ? Number(info.frameW) || 0 : 0
  const frameH = info ? Number(info.frameH) || 0 : 0
  const rows = info && Array.isArray(info.stateRows) ? info.stateRows : []
  const idle = rows.findIndex((name) => String(name).toLowerCase() === 'idle')
  const row = idle >= 0 ? idle : 0

  // Frames in the idle row: the host's own per-state count when it names one, else the sheet width
  // divided by one frame. A sheet with no readable width is one frame, which is a valid answer.
  const framesInRow = () => {
    const image = imageRef.current
    if (!image || !frameW) return 1
    const named = info && info.framesByState && typeof info.framesByState === 'object' ? info.framesByState : null
    if (named) {
      const key = rows[row] !== undefined ? rows[row] : String(row)
      const count = Number(named[key])
      if (Number.isFinite(count) && count > 0) return Math.floor(count)
    }
    const width = Number(image.naturalWidth || image.width) || 0
    return Math.max(1, Math.floor(width / frameW))
  }
  const total = loaded ? framesInRow() : 1
  const animating = !motion.reduced && visible && loaded && total > 1

  // Load (or reuse) the one decoded sheet. The base64 payload is dropped once decoded so a
  // spritesheet is never held twice for the life of the route.
  useEffect(() => {
    if (!info || !frameW || !frameH) return undefined
    const key = `${info.slug || ''}|${info.spritesheetRevision || ''}|${frameW}x${frameH}`
    let image = CB_COMPANION_SHEETS.get(key)
    if (!image) {
      if (!info.spritesheetBase64 || typeof Image === 'undefined') return undefined
      image = new Image()
      image.onload = () => {
        imageRef.current = image
        setLoaded((count) => count + 1)
        try {
          delete info.spritesheetBase64
        } catch (error) {
          // A frozen response stays as-is; the image cache still owns the decode.
        }
      }
      image.src = `data:${info.mime || 'image/webp'};base64,${info.spritesheetBase64}`
      CB_COMPANION_SHEETS.set(key, image)
      return undefined
    }
    imageRef.current = image
    if (image.complete && image.naturalWidth > 0) {
      setLoaded((count) => count + 1)
      return undefined
    }
    if (typeof image.addEventListener === 'function') {
      const onLoad = () => {
        imageRef.current = image
        setLoaded((count) => count + 1)
      }
      image.addEventListener('load', onLoad)
      return () => image.removeEventListener('load', onLoad)
    }
    return undefined
  }, [info, frameW, frameH])

  // Paint the current idle frame. Reduced motion always paints frame 0.
  useEffect(() => {
    const canvas = canvasRef.current
    const image = imageRef.current
    if (!canvas || !image || !frameW || !frameH) return
    try {
      const ratio = typeof window !== 'undefined' && window.devicePixelRatio ? window.devicePixelRatio : 1
      canvas.width = Math.max(1, Math.round(px * ratio))
      canvas.height = Math.max(1, Math.round(px * ratio))
      const ctx = typeof canvas.getContext === 'function' ? canvas.getContext('2d') : null
      if (!ctx) return
      const index = motion.reduced ? 0 : Math.min(frame, Math.max(0, total - 1))
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.imageSmoothingEnabled = true
      ctx.imageSmoothingQuality = 'high'
      ctx.drawImage(image, index * frameW, row * frameH, frameW, frameH, 0, 0, canvas.width, canvas.height)
    } catch (error) {
      // A canvas that cannot paint is not a reason to lose the Continue action.
    }
  }, [loaded, frame, px, motion.reduced, frameW, frameH, row, total])

  // The idle cadence: one timer, low tempo, and only while the page is visible and motion is on.
  useEffect(() => {
    if (!animating || typeof window === 'undefined' || typeof window.setInterval !== 'function') {
      setFrame(0)
      return undefined
    }
    const timer = window.setInterval(() => setFrame((index) => (index + 1) % total), 420)
    return () => window.clearInterval(timer)
  }, [animating, total])

  return jsxs('div', {
    'data-cb-companion': 'ready',
    'data-cb-companion-motion': animating ? 'idle' : 'static',
    style: { display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 },
    children: [
      jsx('canvas', {
        ref: canvasRef,
        'aria-hidden': 'true',
        width: px,
        height: px,
        style: { width: `${px}px`, height: `${px}px`, flex: '0 0 auto' }
      }, 'canvas'),
      jsx('span', {
        'data-cb-companion-name': '',
        style: {
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.caption,
          lineHeight: 1.35,
          color: 'var(--cb-ink-soft)',
          maxWidth: '12ch'
        },
        children: label === 'name'
          ? (info.displayName || 'Your study companion')
          : info.displayName ? `${info.displayName} · study companion` : 'Your study companion'
      }, 'name')
    ]
  })
}

/** What the learner will actually do at the recorded stop, in the backend's own term. */
function cbNextStopSentence(kind) {
  if (kind === 'resolve_review_due') return ' is due for another check. Answer it once to bring the evidence up to date.'
  if (kind === 'resume_lesson') return '. Pick up where you stopped and finish this section.'
  if (kind === 'start_lesson') return '. Work through this section, then finish its check.'
  if (kind === 'review_plan') return '. Read the recorded plan before the first lesson starts.'
  if (kind === 'review_pack') return '. Check the imported pack before it becomes a course.'
  if (kind === 'repair_lesson') return '. The page could not be written; repair it from the reasons it names.'
  if (kind === 'complete') return '. Every section has evidence and nothing is due.'
  return '. Open it to see what this course records next.'
}

/** The one empty/error state plate: same field, same top edge, exactly one next action. */
function TrailheadStatePlate({ state, children }) {
  return jsxs('section', {
    'data-cb-trailhead-state': state,
    style: {
      width: '100%',
      maxWidth: '46rem',
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.8rem',
      padding: '1rem 1.1rem 1.1rem',
      background: 'var(--cb-lamp-soft)',
      borderTop: '3px solid var(--cb-lamp)',
      boxSizing: 'border-box'
    },
    children: [
      jsx('div', {
        'aria-hidden': 'true',
        style: { height: '56px', opacity: 0.45, pointerEvents: 'none' },
        children: jsx(CourseContour, { height: 56 })
      }, 'ghost'),
      children
    ]
  })
}

function ContinueCard({ desk, busy, onPrimary, onOpenSection, onSeePlan, onRetryEstimate, companionEnabled }) {
  const current = desk.current
  const title = current ? current.title : desk.nextLabel
  const courseTitle = desk.row && desk.row.title ? desk.row.title : null
  const viewportWidth = useCbViewportWidth()
  const compact = viewportWidth > 0 && viewportWidth < 620
  // H-189: the trailhead arrives once, on the route beat, and re-arms when the learner switches
  // classroom. Reduced motion paints the resting frame at once.
  const motion = useCbMotion()
  const arrival = useCbSelectionSettle(motion, desk.row && desk.row.course_id ? desk.row.course_id : 'none')
  const edgeFrame = cbSettleFrame(motion, arrival, { beat: 'route', props: 'opacity, transform', from: 'translateY(6px)', fromOpacity: 0.35 })
  const bandFrame = cbSettleFrame(motion, arrival, { beat: 'route', props: 'opacity, transform', from: 'translateY(-4px)', fromOpacity: 0.45 })

  // A lesson start needs a section id. Plan/review/pack next steps open Course Detail and do not,
  // so a failed outline read never disables the one primary action.
  const needsSection =
    desk.primaryKind === 'start_lesson' ||
    desk.primaryKind === 'resume_lesson' ||
    desk.primaryKind === 'repair_lesson'
  const canPrimary = Boolean(desk.row) && (Boolean(current) || !needsSection)
  // A parent-authored classroom is still a classroom: the plate takes the plum seal and the
  // same composition. The companion is the adult's own pet, never an invented child avatar.
  const isParent = Boolean(desk.row && desk.row.recipe === 'parent')
  const pet = useStudyCompanion(companionEnabled !== false)
  const companion = pet ? jsx(StudyCompanion, { info: pet, size: compact ? 44 : 64 }, 'companion') : null
  const label =
    desk.primaryKind === 'resolve_review_due'
      ? 'THE REVIEW IS DUE'
      : desk.primaryKind === 'complete'
        ? 'COURSE COMPLETE'
        : desk.primaryKind === 'repair_lesson'
          ? 'THE PAGE COULD NOT BE WRITTEN'
          : 'CONTINUE THE TRAIL'
  const sentence = cbNextStopSentence(desk.primaryKind)
  const plateField = isParent ? 'var(--cb-plum-soft)' : 'var(--cb-lamp-soft)'
  const plateEdge = isParent ? 'var(--cb-plum)' : 'var(--cb-lamp)'
  const copy = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: 0 },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.75rem', minWidth: 0 },
        children: [
          jsx('span', {
            'data-cb-trailhead-label': '',
            style: {
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              fontWeight: 600,
              letterSpacing: '0.08em',
              color: isParent ? 'var(--cb-plum)' : 'var(--cb-ink-soft)'
            },
            children: label
          }, 'label'),
          compact ? companion : null
        ]
      }),
      // The course title is the identity; the next stop is the sentence underneath. Two lines is
      // the ceiling at every width (FINAL-POLISH-SPEC §3) so a long authored name cannot push the
      // one action off the plate; at narrow the title takes the copy width before it clamps.
      jsx('h2', {
        'data-cb-desk-course': '',
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: compact ? CB_TYPE.lead : CB_TYPE.heading,
          fontWeight: 600,
          letterSpacing: '-0.015em',
          color: 'var(--cb-ink)',
          maxWidth: compact ? '100%' : '26ch',
          overflowWrap: 'break-word',
          lineHeight: 1.3,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden'
        },
        children: courseTitle || title
      }, 'title'),
      jsxs('p', {
        'data-cb-trailhead-next': '',
        style: {
          margin: 0,
          maxWidth: '54ch',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.body,
          lineHeight: 1.55,
          color: 'var(--cb-ink)',
          overflowWrap: 'break-word'
        },
        children: [
          desk.sectionLabel
            ? jsx('span', { 'data-cb-continue-position': '', children: desk.sectionLabel }, 'position')
            : null,
          desk.sectionLabel ? jsx('span', { children: ' · ' }, 'dot') : null,
          jsx('span', { 'data-cb-continue-section': '', style: { fontWeight: 600 }, children: title }, 'stop'),
          jsx('span', { children: sentence }, 'rest')
        ]
      }, 'next'),
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: '0.2rem 0.85rem',
          fontSize: CB_TYPE.caption,
          color: 'var(--cb-ink-soft)'
        },
        children: [
          jsx('span', {
            'data-cb-continue-minutes': '',
            'data-cb-continue-minutes-state': desk.estimateState || 'none',
            title:
              desk.estimateState === 'error' && desk.estimateError && desk.estimateError.code
                ? `${desk.estimateError.code}: ${desk.estimateError.message || ''}`.trim()
                : undefined,
            style: desk.estimateState === 'error' ? { color: 'var(--cb-ochre)' } : undefined,
            children: desk.estimateLabel
          }, 'estimate'),
          desk.estimateState === 'error'
            ? jsx(CbAction, {
                variant: 'tertiary',
                onClick: onRetryEstimate,
                'aria-label': 'Retry reading the session length',
                children: 'Retry'
              }, 'retry')
            : null,
          jsx('span', {
            'data-cb-continue-touched': desk.touchedSource || 'none',
            children: desk.lastTouched ? `Last touched ${whenLabel(desk.lastTouched)}` : 'Nothing touched yet'
          }, 'touched')
        ]
      }, 'meta'),
      jsxs('div', {
        'data-cb-trailhead-actions': '',
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.15rem' },
        children: [
          jsx(CbAction, {
            variant: 'primary',
            disabled: Boolean(busy) || !canPrimary,
            onClick: onPrimary,
            children: busy ? 'Opening' : desk.primaryLabel
          }, 'primary'),
          jsx(CbAction, {
            variant: 'secondary',
            disabled: !current,
            onClick: () => onOpenSection(current ? current.objective_id : null),
            children: 'Open section'
          }, 'section'),
          onSeePlan
            ? jsx(CbAction, {
                variant: 'tertiary',
                'data-cb-trailhead-see-plan': '',
                onClick: onSeePlan,
                children: 'See the plan'
              }, 'plan')
            : null
        ]
      }, 'actions'),
      // H-189 hierarchy: the old facts line repeated the path's own evidence count and the current
      // stop's state word inside the plate, so the plate said the route twice before the route.
      // The one count now lives in the route header; the plate keeps only what it alone knows —
      // position, estimate and last touch.
      null
    ]
  }, 'copy')
  return jsxs('section', {
    'data-cb-continue': '',
    'data-cb-trailhead': '',
    'data-cb-continue-compact': compact ? 'true' : 'false',
    'data-cb-trailhead-motion': motion.reduced ? 'static' : arrival ? 'settled' : 'arriving',
    'data-cb-trail-palette': isParent ? 'parent' : 'learner',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.7rem',
      padding: compact ? '0.9rem 0.95rem' : '1.1rem 1.2rem 1.15rem',
      background: plateField,
      border: 'none',
      borderTop: `3px solid ${plateEdge}`,
      maxWidth: '100%',
      minWidth: 0,
      boxSizing: 'border-box'
    },
    children: [
      compact
        ? jsx('div', {
            'aria-hidden': 'true',
            style: { height: '26px', opacity: 0.5, ...(bandFrame || {}) },
            children: jsx(CourseContour, { row: desk.row, title: courseTitle, height: 26 })
          }, 'band')
        : null,
      jsxs('div', {
        style: compact
          ? { display: 'flex', flexDirection: 'column', gap: '0.7rem', minWidth: 0 }
          : {
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1fr) minmax(9rem, 14rem)',
              gap: '1rem',
              alignItems: 'start',
              minWidth: 0
            },
        children: [
          copy,
          compact
            ? null
            : jsxs('div', {
                'data-cb-trailhead-edge': '',
                style: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.35rem', minWidth: 0, ...(edgeFrame || {}) },
                children: [
                  jsx('div', {
                    'aria-hidden': 'true',
                    style: { width: '100%', height: '88px', opacity: 0.6 },
                    children: jsx(CourseContour, { row: desk.row, title: courseTitle, height: 88 })
                  }, 'contour'),
                  companion
                ]
              }, 'edge')
        ]
      }, 'body')
    ]
  })
}

/**
 * The check row's learner word. `check_state` is the backend's highest-version check for the
 * objective; `none` means no check was ever authored, which is a fact, not a lock. The words live
 * in `CB_COPY.checkState` (00-header.js), so a check reads the same on every surface.
 */
function cbCheckStateWord(value) {
  return CB_COPY.checkWord(value)
}

/** The objective the route stands on: the desk's current section, else the first without evidence. */
function cbPathCurrentId(objectives, current) {
  if (current && current.objective_id) return current.objective_id
  const list = Array.isArray(objectives) ? objectives : []
  const fallback = list.find((entry) => !entry.independent)
  return fallback ? fallback.objective_id : list.length ? list[0].objective_id : null
}

/** The next node is the next section that still needs evidence; a settled one is not "next". */
function cbPathNextId(objectives, currentId) {
  const list = Array.isArray(objectives) ? objectives : []
  const index = list.findIndex((entry) => entry.objective_id === currentId)
  if (index < 0) return null
  for (let cursor = index + 1; cursor < list.length; cursor += 1) {
    if (!list[cursor].independent) return list[cursor].objective_id
  }
  return null
}

/**
 * Position on the route is geometry, not evidence: current / next / done / future. A done node is
 * only a node the backend marks independent; no node is ever locked.
 */
function cbPathNodeKind(objective, currentId, nextId) {
  if (!objective) return 'future'
  if (currentId && objective.objective_id === currentId) return 'current'
  if (nextId && objective.objective_id === nextId) return 'next'
  if (objective.independent) return 'done'
  return 'future'
}

/** 56/44 current, 40/32 next, 28/24 for done and future: measured against the route, not the window. */
function cbPathNodeSize(kind, compact) {
  if (kind === 'current') return compact ? 44 : 56
  if (kind === 'next') return compact ? 32 : 40
  return compact ? 24 : 28
}

/** The one evidence caption on the path. Zero evidence says so; it never paints a reached segment. */
function cbPathEvidenceCaption(settled, total, due) {
  const all = Math.max(0, Number(total) || 0)
  if (all === 0) return 'No sections yet'
  const done = Math.max(0, Math.min(all, Number(settled) || 0))
  const waiting = Math.max(0, Number(due) || 0)
  // H-155: the caption is a count or it says there is no count. "No evidence yet" hid a real
  // "0 of 4 with evidence" behind a slogan; the number is the honest statement.
  const noun = all === 1 ? 'section' : 'sections'
  return `${done} of ${all} ${noun} with evidence${waiting > 0 ? ` · ${waiting} due` : ''}`
}

/** Node paint: fill and ring come from the stored state tone; only current adds the ring. */
function cbPathMarkerStyle(tone, kind, size) {
  const base = {
    width: `${size}px`,
    height: `${size}px`,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxSizing: 'border-box',
    fontFamily: CB_SANS,
    fontVariantNumeric: 'tabular-nums',
    fontWeight: 600,
    fontSize: kind === 'current' ? CB_TYPE.meta : CB_TYPE.caption,
    lineHeight: 1,
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    zIndex: 2,
    pointerEvents: 'none'
  }
  let painted
  if (tone === 'done') painted = { ...base, background: 'var(--cb-field)', color: 'var(--cb-paper)', border: 'none' }
  else if (tone === 'due') painted = { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ochre)', border: '2px solid var(--cb-ochre)' }
  else if (tone === 'attention') painted = { ...base, background: 'var(--cb-paper)', color: 'var(--cb-coral)', border: '2px solid var(--cb-coral)' }
  else if (tone === 'active') painted = { ...base, background: 'var(--cb-accent-soft)', color: 'var(--cb-accent)', border: '2px solid var(--cb-accent)' }
  else painted = { ...base, background: 'var(--cb-paper)', color: 'var(--cb-ink-soft)', border: '1.5px solid var(--cb-rule)' }
  if (kind !== 'current') return painted
  // One 2 px accent ring. The soft halo is a separate flat disc (cbPathHaloStyle), never a shadow.
  return { ...painted, border: '2px solid var(--cb-accent)', color: tone === 'done' ? 'var(--cb-paper)' : 'var(--cb-accent)' }
}

function cbPathTone(state) {
  if (state === 'needs_review') return 'attention'
  return DESK_STATE_TONE[state] || 'quiet'
}

function cbPathToneColor(tone) {
  if (tone === 'done') return 'var(--cb-field)'
  if (tone === 'due') return 'var(--cb-ochre)'
  if (tone === 'attention') return 'var(--cb-coral)'
  if (tone === 'active') return 'var(--cb-accent)'
  return 'var(--cb-ink-soft)'
}

/**
 * Trail geometry. At wide the route bows around a centre line by at most CB_PATH_SWING px and the
 * stops alternate sides; at 620 px and below it is one straight spine. Coordinates are confined to
 * the route gutter, so a stop's text column never moves with the drawing.
 */
const CB_PATH_SWING = 32

function cbPathGutter(compact) {
  return compact ? 44 : 128
}

function cbPathCenter(compact) {
  return cbPathGutter(compact) / 2
}

function cbPathStopX(index, compact) {
  const center = cbPathCenter(compact)
  if (compact) return center
  return index % 2 === 0 ? center - CB_PATH_SWING : center + CB_PATH_SWING
}

/**
 * One half of the decorative route: the curve in from the previous stop and the straight run out
 * to the row's edge. Two halves per row meet exactly, so the line reads as one continuous route.
 * The SVG is `aria-hidden`; the `<ol>` below stays the structure and the reading order.
 */
function PathRouteSegment({ from, to, gutter, half }) {
  const d = half === 'enter' ? `M ${from} 0 C ${from} 42, ${to} 58, ${to} 100` : `M ${to} 0 L ${to} 100`
  return jsx('svg', {
    'aria-hidden': 'true',
    focusable: 'false',
    viewBox: `0 0 ${gutter} 100`,
    preserveAspectRatio: 'none',
    style: {
      position: 'absolute',
      left: 0,
      top: half === 'enter' ? 0 : '50%',
      width: `${gutter}px`,
      height: '50%',
      pointerEvents: 'none'
    },
    children: jsx('path', {
      d,
      fill: 'none',
      stroke: 'var(--cb-rule)',
      strokeWidth: 1.5,
      strokeLinecap: 'round',
      vectorEffect: 'non-scaling-stroke'
    })
  })
}

/** `Start` and `Course end` are place labels, not stops and not completion claims. */
function PathPlace({ kind, label, x }) {
  return jsxs('div', {
    'data-cb-path-place': kind,
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      minHeight: '1.5rem',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      color: 'var(--cb-ink-soft)'
    },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: { display: 'block', width: `${Math.max(0, x)}px`, height: '1.5px', background: 'var(--cb-rule)', flex: '0 0 auto' }
      }, 'horizon'),
      jsx('span', {
        style: { fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' },
        children: label
      }, 'label')
    ]
  })
}

/** The current stop's one soft halo: a flat accent-soft disc behind the ringed marker. */
function cbPathHaloStyle(x, size) {
  const diameter = size + 20
  return {
    position: 'absolute',
    left: `${x - diameter / 2}px`,
    top: '50%',
    transform: 'translateY(-50%)',
    width: `${diameter}px`,
    height: `${diameter}px`,
    borderRadius: '50%',
    background: 'var(--cb-accent-soft)',
    zIndex: 1,
    pointerEvents: 'none'
  }
}

/** A real checkpoint gets one diamond on the route; the check word beside the stop says which. */
function cbPathGateStyle(x, size, tone) {
  return {
    position: 'absolute',
    left: `${x - 5}px`,
    top: `calc(50% + ${Math.round(size / 2 + 10)}px)`,
    width: '10px',
    height: '10px',
    border: `1.5px solid ${cbPathToneColor(tone)}`,
    background: 'var(--cb-paper)',
    transform: 'rotate(45deg)',
    zIndex: 1,
    pointerEvents: 'none'
  }
}

/** The one honest detail line the current and next stops may carry. Never a score. */
function cbPathDetailText(objective, attempts) {
  const parts = []
  if (objective.evidence_target) parts.push(`Evidence: ${learnerEvidenceTarget(objective.evidence_target)}`)
  parts.push(attempts === 0 ? 'No committed attempts yet' : `${attempts} committed attempt${attempts === 1 ? '' : 's'}`)
  parts.push(objective.last_opened_at ? `Last opened ${whenLabel(objective.last_opened_at)}` : 'Not opened yet')
  return parts.join(' · ')
}

/** The run header: recorded action, recorded position, recorded estimate, next stop in order. */
function cbPathRunParts(desk, nextObjective) {
  const parts = []
  if (desk.primaryKind === 'resolve_review_due') parts.push('Review')
  else if (desk.primaryKind === 'resume_lesson') parts.push('Resume')
  else if (desk.primaryKind === 'start_lesson') parts.push('Start')
  if (desk.sectionLabel) parts.push(desk.sectionLabel)
  if (desk.estimateState === 'ready' && desk.estimateLabel) parts.push(desk.estimateLabel)
  if (nextObjective) parts.push(`Next: ${CB_COPY.sectionLabel(nextObjective.ordinal)} · ${nextObjective.title}`)
  return parts
}

/**
 * The path is a trail, not a table. Every objective is a real node: one continuous route curves
 * between the stops at wide widths and runs straight at 620 px and below; the current stop is the
 * largest and carries `aria-current="step"`, the next one is smaller, evidence already held is a
 * filled field, and the rest are quiet. No node is locked and no node is a fake checkpoint: a
 * diamond marks the backend's own `check_state`, and the words beside the stop say what it is.
 */
/** One stop on the trail. It owns its focus ring so a keyboard reader can see where they are. */
function PathStop({
  objective,
  nodeIndex,
  compact,
  gutter,
  center,
  currentId,
  nextId,
  showCompanion,
  pet,
  motion,
  routeSettle,
  pulse,
  onOpenSection
}) {
  const [focused, setFocused] = useState(false)
  const tone = cbPathTone(objective.state)
  const kind = cbPathNodeKind(objective, currentId, nextId)
  const size = cbPathNodeSize(kind, compact)
  const isCurrent = kind === 'current'
  const x = cbPathStopX(nodeIndex, compact)
  const fromX = nodeIndex === 0 ? center : cbPathStopX(nodeIndex - 1, compact)
  const stateWord = CB_COPY.stateWord(objective.state)
  const checkWord = cbCheckStateWord(objective.check_state)
  const checkState = objective.check_state || 'none'
  const attempts = Math.max(0, Number(objective.attempt_count) || 0)
  const detailOpen = kind === 'current' || kind === 'next'
  // The route settle is one beat for the whole list: at most eight nodes, 40 ms apart.
  const inBeat = routeSettle.active && nodeIndex < CB_PATH_SETTLE_NODES
  const settleStyle = inBeat
    ? cbSettleFrame(motion, routeSettle.settled, {
        beat: 'route',
        props: 'opacity, transform',
        from: 'scale(0.96)',
        fromOpacity: 0.96,
        delay: nodeIndex * CB_PATH_SETTLE_STAGGER_MS
      }) || {}
    : {}
  const companionPad = showCompanion && isCurrent ? '3.25rem' : '0.5rem'
  const rowStyle = {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    position: 'relative',
    minHeight: isCurrent ? (compact ? 76 : 88) : kind === 'next' ? 64 : 56,
    ...settleStyle
  }
  // Focus is a static ring, never a beat: the host resets the UA outline on its buttons.
  if (focused) {
    rowStyle.outline = '2px solid var(--cb-accent)'
    rowStyle.outlineOffset = '2px'
  }
  return jsx(
    'li',
    {
      'data-cb-path-node': objective.objective_id,
      'data-cb-path-node-motion': inBeat ? 'settle' : 'static',
      'data-cb-path-focused': focused ? 'true' : 'false',
      style: rowStyle,
      children: [
        jsx(PathRouteSegment, { from: fromX, to: x, gutter, half: 'enter' }, 'enter'),
        jsx(PathRouteSegment, { from: x, to: x, gutter, half: 'exit' }, 'exit'),
        isCurrent
          ? jsx('span', { 'data-cb-path-halo': '', 'aria-hidden': 'true', style: cbPathHaloStyle(x, size) }, 'halo')
          : null,
        checkState !== 'none'
          ? jsx('span', { 'data-cb-path-gate': checkState, 'aria-hidden': 'true', style: cbPathGateStyle(x, size, tone) }, 'gate')
          : null,
        jsx('span', {
          'data-cb-path-marker': objective.objective_id,
          'data-cb-path-marker-check': checkState,
          'aria-hidden': 'true',
          style: { ...cbPathMarkerStyle(tone, kind, size), left: `${x - size / 2}px` },
          children: [
            // H-189: the current stop's one gentle cycle, two legs up and down, then it rests.
            // Carried inside the marker so the H-177 route (gate, place labels, one halo) and the
            // H-189 pulse are the same stop, not two competing renderings of it.
            isCurrent && pulse
              ? jsx('span', {
                  'data-cb-path-pulse': pulse.running ? 'cycle' : 'rest',
                  style: {
                    position: 'absolute',
                    inset: '-5px',
                    borderRadius: '50%',
                    borderWidth: '2px',
                    borderStyle: 'solid',
                    borderColor: 'var(--cb-accent)',
                    opacity: pulse.scale,
                    pointerEvents: 'none',
                    ...(motion.transition('opacity', 'route')
                      ? { transition: motion.transition('opacity', 'route') }
                      : {})
                  }
                }, 'pulse')
              : null,
            jsx('span', { children: String(objective.ordinal).padStart(2, '0') }, 'ordinal')
          ]
        }, 'marker'),
        showCompanion && isCurrent && pet
          ? jsx('span', {
              'data-cb-path-companion': '',
              style: { position: 'absolute', right: '0.35rem', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', zIndex: 3, maxWidth: '6rem' },
              children: jsx(StudyCompanion, { info: pet, size: 32, label: 'name' })
            }, 'companion')
          : null,
        jsx(CbAction, {
          variant: 'row',
          className: 'w-full justify-start',
          'aria-current': isCurrent ? 'step' : undefined,
          'aria-label': `${CB_COPY.sectionLabel(objective.ordinal)}: ${objective.title}, ${stateWord}, ${checkWord}`,
          state: isCurrent ? 'selected' : 'rest',
          style: { padding: 0, display: 'block', minHeight: '44px', borderRadius: 0 },
          onFocus: () => setFocused(true),
          onBlur: () => setFocused(false),
          onClick: () => onOpenSection(objective.objective_id),
          children: jsxs('span', {
            'data-cb-path-open': objective.objective_id,
            'data-cb-path-item': objective.objective_id,
            'data-cb-path-state': objective.state,
            'data-cb-path-check': checkState,
            'data-cb-path-kind': kind,
            'data-cb-path-current': isCurrent ? 'true' : 'false',
            'data-cb-path-node-size': String(size),
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              width: '100%',
              padding: `0.45rem ${companionPad} 0.45rem ${gutter}px`,
              position: 'relative',
              boxSizing: 'border-box',
              textAlign: 'left',
              color: 'var(--cb-ink)',
              fontSize: CB_TYPE.meta,
              background: 'transparent'
            },
            children: [
              jsxs('span', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.2rem 0.55rem', minWidth: 0 },
                children: [
                  jsx('span', {
                    style: {
                      flex: '1 1 8rem',
                      minWidth: 0,
                      overflowWrap: 'anywhere',
                      whiteSpace: 'normal',
                      fontFamily: CB_SERIF,
                      fontSize: isCurrent ? CB_TYPE.body : kind === 'next' ? CB_TYPE.body : CB_TYPE.meta,
                      fontWeight: 600,
                      lineHeight: 1.35,
                      color: kind === 'done' || kind === 'future' ? 'var(--cb-ink-soft)' : 'var(--cb-ink)'
                    },
                    children: objective.title
                  }, 'title'),
                  jsx('span', {
                    'data-cb-path-word': '',
                    style: {
                      flex: '0 0 auto',
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      fontWeight: 600,
                      color: cbPathToneColor(tone),
                      border: `1px solid ${cbPathToneColor(tone)}`,
                      borderRadius: '999px',
                      padding: '0.05rem 0.45rem',
                      whiteSpace: 'nowrap'
                    },
                    children: stateWord
                  }, 'state'),
                  jsx('span', {
                    'data-cb-path-check-word': '',
                    style: { flex: '0 0 auto', fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: checkWord
                  }, 'check')
                ]
              }, 'titleline'),
              detailOpen
                ? jsx('span', {
                    'data-cb-path-detail': objective.objective_id,
                    'data-cb-path-detail-body': '',
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
                    children: cbPathDetailText(objective, attempts)
                  }, 'detail')
                : null
            ]
          }, 'body')
        }, 'open')
      ]
    },
    objective.objective_id
  )
}

/** One honest detail line: label, value. Never a score, a percentage or a gate. */
function CheckpointDetailRow({ label, value }) {
  return jsxs('div', {
    style: { display: 'flex', flexWrap: 'wrap', gap: '0.15rem 0.5rem', fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45 }
  , children: [
    jsx('span', { style: { color: 'var(--cb-ink-soft)', minWidth: '8.5rem' }, children: label }, 'label'),
    jsx('span', { style: { color: 'var(--cb-ink)' }, children: value }, 'value')
  ] })
}

function CheckpointPath({ desk, onOpenSection, outlineStatus, outlineError, onRetryOutline, companionEnabled }) {
  const width = useCbViewportWidth()
  const motion = useCbMotion()
  const routeSettle = useCbSettled(motion, true)
  const pet = useStudyCompanion(companionEnabled !== false)
  // H-189: the route arrives once. The whole route column settles on the route beat, re-armed when
  // the selected classroom changes, so a switch has one visible consequence.
  const arrival = useCbSelectionSettle(motion, desk.row ? desk.row.course_id : 'none')
  const compact = width > 0 && width < 620
  const objectives = Array.isArray(desk.objectives) ? desk.objectives : []
  // H-189: one gentle cycle on the current stop, then it rests. Running only when a route exists.
  // Declared before any early return so the hook order is identical in every state.
  const pulse = useCbStopPulse(motion, objectives.length > 0)
  // A failed route read is its own state (H-146). Continue still works from the row's next step;
  // the path says what it could not read and offers the retry, rather than claiming the course is
  // empty. H-148 owns the checkpoint geometry; this branch is the read state it did not carry.
  if (outlineStatus === 'error' && objectives.length === 0) {
    return jsxs('section', {
      'data-cb-path': 'error',
      style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', maxWidth: '100%' },
      children: [
        jsx(PlateHead, {
          label: 'The route',
          title: desk.row && desk.row.title ? desk.row.title : 'Your path'
        }, 'head'),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
          children: [
            jsx('p', {
              style: { margin: 0, lineHeight: 1.55 },
              children: `${outlineError && outlineError.code ? outlineError.code + ': ' : ''}${describeError(outlineError)} The route was not read. Continue still uses the next step this course recorded.`
            }, 'copy'),
            jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: onRetryOutline, children: 'Try again' }, 'retry')
          ]
        }, 'body')
      ]
    })
  }
  const currentId = cbPathCurrentId(objectives, desk.current)
  const nextId = cbPathNextId(objectives, currentId)
  const currentIndex = objectives.findIndex((objective) => objective.objective_id === currentId)
  const nextObjective = currentIndex >= 0 && currentIndex + 1 < objectives.length ? objectives[currentIndex + 1] : null
  const gutter = cbPathGutter(compact)
  const center = cbPathCenter(compact)
  const showCompanion = Boolean(pet) && !compact && !motion.reduced
  const caption = cbPathEvidenceCaption(desk.settled, desk.total, desk.dueCount)
  const runParts = cbPathRunParts(desk, nextObjective)
  return jsxs('section', {
    'data-cb-path': '',
    'data-cb-path-layout': compact ? 'compact' : 'full',
    'data-cb-path-motion': motion.reduced ? 'static' : arrival ? 'settled' : 'arriving',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      maxWidth: '100%',
      ...(cbSettleFrame(motion, arrival, { beat: 'route', props: 'opacity, transform', from: 'translateY(4px)', fromOpacity: 0.92 }) || {})
    },
    children: [
      jsx(PlateHead, {
        label: 'The route',
        title: desk.row && desk.row.title ? desk.row.title : 'Your path'
      }),
      runParts.length
        ? jsx('p', {
            'data-cb-path-run': '',
            style: { margin: 0, maxWidth: CB_MEASURE, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
            children: runParts.join(' · ')
          })
        : null,
      // H-189 hierarchy: the route is the one object. The old twelve-bar tally painted the same
      // evidence a second time above the nodes; the count now lives as one caption line, and the
      // nodes themselves carry the state.
      objectives.length
        ? jsx('p', {
            'data-cb-tally-caption': '',
            'data-cb-path-caption': '',
            style: {
              margin: 0,
              maxWidth: CB_MEASURE,
              fontFamily: CB_SANS,
              fontSize: CB_TYPE.caption,
              lineHeight: 1.45,
              color: 'var(--cb-ink-soft)'
            },
            children: caption
          })
        : jsx('p', {
            'data-cb-path-empty': '',
            style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'This course has no objectives yet, so there is no path to show. Approve its plan to start one.'
          }),
      objectives.length
        ? jsx('ol', {
            'aria-label': 'Course route',
            style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', position: 'relative' },
            children: [
              jsx(PathPlace, { kind: 'start', label: 'Start', x: cbPathStopX(0, compact) }, 'start'),
              ...objectives.map((objective, nodeIndex) =>
                jsx(PathStop, {
                  objective,
                  nodeIndex,
                  compact,
                  gutter,
                  center,
                  currentId,
                  nextId,
                  showCompanion,
                  pet,
                  motion,
                  routeSettle,
                  pulse,
                  onOpenSection
                }, objective.objective_id)
              ),
              jsx(PathPlace, { kind: 'end', label: 'Course end', x: cbPathStopX(objectives.length - 1, compact) }, 'end')
            ]
          })
        : null
    ]
  })
}

/**
 * Sources are collapsed by default and read only when opened. The read is `lesson.page` for the
 * section the desk continues, so the drawer names exactly whose sources these are.
 */
function SourcesDrawer({ open, onToggle, sectionTitle, status, error, sources, onRetry }) {
  const items = Array.isArray(sources) ? sources : []
  return jsxs('section', {
    'data-cb-sources-drawer': open ? 'open' : 'closed',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', maxWidth: '100%' },
    children: [
      jsx(CbAction, {
        variant: 'tertiary',
        className: 'self-start',
        'aria-expanded': open ? 'true' : 'false',
        'aria-controls': 'cb-desk-sources',
        onClick: onToggle,
        children: open ? 'Hide sources' : 'Show sources'
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: sectionTitle ? `Sources for “${sectionTitle}”` : 'Sources'
      }),
      open
        ? jsx('div', {
            id: 'cb-desk-sources',
            role: 'region',
            'aria-label': 'Sources for the current section',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', borderTop: '1px solid var(--cb-rule)', paddingTop: '0.45rem' },
            children:
              status === 'loading'
                ? jsx(sdk.Loader, { label: 'Reading this section’s sources' })
                : status === 'error'
                  ? jsxs('div', {
                      style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                      children: [
                        jsx('span', {
                          children: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} The sources were not read.`
                        }),
                        jsx(CbAction, { variant: 'tertiary', onClick: onRetry, children: 'Try again' })
                      ]
                    })
                  : items.length === 0
                    ? jsx('p', { style: { margin: 0, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' }, children: 'No sources are recorded for this section yet.' })
                    : jsx('ul', {
                        style: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem' },
                        children: items.map((source) =>
                          jsxs(
                            'li',
                            {
                              'data-cb-desk-source': source.source_id || '',
                              style: { borderLeft: '2px solid var(--cb-rule)', paddingLeft: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.05rem' },
                              children: [
                                jsx('span', { style: { fontSize: CB_TYPE.meta, color: 'var(--cb-ink)' }, children: source.title || 'Untitled source' }),
                                jsx('span', { style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: source.support_status || 'status unrecorded' })
                              ]
                            },
                            source.source_id || source.title
                          )
                        )
                      })
          })
        : null
    ]
  })
}

/**
 * The strip is a glance surface, not the notebook: the saved excerpt is summarised to plain text
 * and clipped here only. Plain text means the authored markdown syntax is removed for this one
 * line, not re-rendered — the strip does not grow a second markdown surface. The saved row keeps
 * its whole excerpt and the Notebook renders it unfiltered.
 */
const STRIP_EXCERPT_CHARS = 240
function stripExcerpt(entry) {
  const raw = String(entry.excerpt || entry.note || entry.kind || '')
  const plain = raw
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^\s*\|/gm, '')
    .replace(/\|\s*$/gm, '')
    .replace(/\|/g, ' · ')
    .replace(/[*_`~]{1,3}/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return plain.length > STRIP_EXCERPT_CHARS ? `${plain.slice(0, STRIP_EXCERPT_CHARS - 1).trimEnd()}…` : plain
}

/**
 * The Field Notes strip on the Field Desk.
 *
 * A saved moment is a first-class learning surface, not a settings side list: the desk shows the
 * last few things this course saved, each one able to return to its exact block. It reads only
 * `notebook.list`; it never writes, never invents an empty row and never hides a failed read.
 */
/**
 * H-189 — Field Notes on Home is one tertiary line, not a feed.
 *
 * The owner's note was that the strip filled Home with an audit list. Home is the trailhead; the
 * Notebook is the notes surface. So this renders exactly one quiet line — the backends's own saved
 * count — and the whole line is the door to the Notebook. Loading, failure and an empty notebook
 * are said in the same single line; none of them expands into a list.
 */
function FieldNotesLine({ notes, stale, onShowNotebook }) {
  if (!notes) return null
  const status = notes.status ? notes.status : 'idle'
  const entries = notes.data && Array.isArray(notes.data.entries) ? notes.data.entries : []
  const count = entries.length
  let text
  if (status === 'loading' && !notes.data) text = 'Field notes · reading'
  else if (status === 'error' && !notes.data) text = 'Field notes · could not be read'
  else if (count === 0) text = 'Field notes · nothing saved yet'
  else text = `Field notes · ${count} saved`
  return jsx('div', {
    'data-cb-field-notes-line': status === 'ready' && count > 0 ? 'ready' : status,
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.25rem', minWidth: 0 },
    children: jsx(CbAction, {
      variant: 'tertiary',
      onClick: onShowNotebook,
      'aria-describedby': 'cb-field-notes-count',
      style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 500, minHeight: '44px' },
      children: jsxs('span', {
        id: 'cb-field-notes-count',
        style: { color: 'var(--cb-ink-soft)' },
        children: [
          jsx('span', { 'data-cb-field-notes-count': String(count), children: text }, 'count'),
          stale ? jsx('span', { children: ' · paused until the desk reconnects' }, 'stale') : null
        ]
      })
    })
  })
}

function FieldNotesStrip({ notes, courseTitle, current, sections, stale, onOpenSection, onShowNotebook, onRetry }) {
  const status = notes && notes.status ? notes.status : 'idle'
  const entries = notes && notes.data && Array.isArray(notes.data.entries) ? notes.data.entries : []
  const recent = entries.slice(0, 4)
  const error = notes ? notes.error : null
  const reload = notes && notes.reload ? notes.reload : onRetry
  const sectionTitles = {}
  ;(sections || []).forEach((entry) => {
    if (entry && entry.objective_id && entry.title) sectionTitles[entry.objective_id] = entry.title
  })

  if (!notes) return null

  const action = current
    ? jsx(sdk.Button, {
        variant: 'secondary',
        size: 'sm',
        onClick: () => onOpenSection(current.objective_id),
        children: 'Go to the current lesson'
      })
    : null

  const quietText = { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.55, color: 'var(--cb-ink-soft)' }

  return jsxs('section', {
    'data-cb-field-notes': status === 'ready' && recent.length > 0 ? 'ready' : status,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.45rem',
      maxWidth: '100%',
      border: '1px solid var(--cb-rule)',
      background: 'var(--cb-paper-raised)',
      padding: '0.8rem 0.9rem'
    },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.25rem 0.75rem'
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.5rem' },
            children: [
              jsx(DeskLabel, { as: 'h2', children: 'Field Notes' }),
              entries.length > 0
                ? jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: `${entries.length} saved${entries.length > recent.length ? ` · showing the last ${recent.length}` : ''}`
                  })
                : null
            ]
          }),
          jsx(sdk.Button, {
            variant: 'text',
            size: 'sm',
            onClick: onShowNotebook,
            children: 'All field notes'
          })
        ]
      }),
      stale
        ? jsx('p', {
            style: { ...quietText, fontSize: CB_TYPE.caption },
            children: 'These are the notes last read. A save or an edit is paused until the desk reconnects.'
          })
        : null,
      status === 'error' && !notes.data
        ? jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
            children: [
              jsx('span', {
                style: quietText,
                children: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} Saved moments are still stored; this strip just could not read them.`
              }),
              jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: reload, children: 'Try again' })
            ]
          })
        : status === 'loading' && !notes.data
          ? jsx('div', { style: { padding: '0.35rem 0' }, children: jsx(sdk.Loader, { label: 'Reading your field notes' }) })
          : recent.length === 0
            ? jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' },
                children: [
                  jsx('p', {
                    style: { ...quietText, maxWidth: CB_MEASURE },
                    children: 'Save an explanation, visual or quiz moment and it will appear here.'
                  }),
                  action
                ]
              })
            : jsx('div', {
                style: { display: 'flex', flexDirection: 'column' },
                children: recent.map((entry) => {
                  const ref = readNotebookRef(entry.source_ref)
                  return jsxs(
                    'div',
                    {
                      'data-cb-field-note': entry.entry_id,
                      style: {
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.2rem',
                        borderTop: '1px solid var(--cb-rule)',
                        padding: '0.5rem 0 0.55rem'
                      },
                      children: [
                        jsx('p', {
                          style: {
                            margin: 0,
                            fontSize: CB_TYPE.meta,
                            lineHeight: 1.55,
                            color: 'var(--cb-ink)',
                            whiteSpace: 'pre-wrap',
                            overflowWrap: 'anywhere'
                          },
                          children: stripExcerpt(entry)
                        }),
                        entry.note && entry.excerpt
                          ? jsx('p', {
                              style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                              children: entry.note
                            })
                          : null,
                        jsxs('div', {
                          style: {
                            display: 'flex',
                            flexWrap: 'wrap',
                            alignItems: 'baseline',
                            gap: '0.25rem 0.8rem',
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink-soft)'
                          },
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: entry.kind }),
                            (entry.tags || []).map((item) =>
                              jsx(
                                'span',
                                {
                                  style: {
                                    border: '1px solid var(--cb-rule)',
                                    padding: '0 0.3rem',
                                    fontSize: CB_TYPE.caption,
                                    color: 'var(--cb-ink-soft)'
                                  },
                                  children: item
                                },
                                item
                              )
                            ),
                            sectionTitles[entry.objective_id]
                              ? jsx('span', { children: `Section · ${sectionTitles[entry.objective_id]}` })
                              : null,
                            courseTitle ? jsx('span', { children: courseTitle }) : null,
                            jsx('span', { children: `saved ${whenLabel(entry.created_at)}` }),
                            jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              'aria-label': `Open the saved moment “${(entry.excerpt || entry.kind).slice(0, 60)}” in Textbook`,
                              onClick: () => onOpenSection(entry.objective_id, ref.block_id),
                              children: 'Open in textbook'
                            })
                          ]
                        })
                      ]
                    },
                    entry.entry_id
                  )
                })
              })
    ]
  })
}

/**
 * One settings section: heading, one sentence, the control, and its own Reset.
 *
 * The reset is disabled at the default, so "already at the default" is visible instead of
 * offering a control that would do nothing. Every control fires on change; there is no Save.
 */
function CbSettingsSection({ id, title, description, resetLabel, atDefault, onReset, children, readOnly = false }) {
  return jsxs('section', {
    'data-cb-settings-section': id,
    'aria-labelledby': `cb-settings-${id}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.5rem',
      padding: '0.9rem 0',
      borderTop: '1px solid var(--cb-rule)'
    },
    children: [
      jsxs(
        'div',
        {
          style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', minHeight: '2.75rem' },
          children: [
            jsx('h3', {
              id: `cb-settings-${id}`,
              style: {
                margin: 0,
                fontFamily: CB_SANS,
                fontSize: CB_TYPE.meta,
                fontWeight: 600,
                letterSpacing: '0.02em',
                color: 'var(--cb-ink)'
              },
              children: title
            }),
            readOnly
              ? null
              : jsx(sdk.Button, {
                  size: 'sm',
                  variant: 'ghost',
                  disabled: Boolean(atDefault),
                  'data-cb-settings-reset': id,
                  'aria-label': resetLabel,
                  style: { minHeight: '44px' },
                  onClick: onReset,
                  children: 'Reset'
                })
          ]
        },
        'head'
      ),
      jsx('p', {
        style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
        children: description
      }),
      children
    ]
  })
}

/**
 * UI-K13 — what generation has actually used, on Home settings.
 *
 * `usage.summary` had no surface at all: a learner could spend provider calls and never see a
 * number. It stays quiet (a few caption lines, no card, no chart) and every value is the backend's
 * own field. A token count the backend did not record reads "not recorded" — never a zero, and
 * never a total this screen adds up itself. A failed read shows the code and states that no number
 * is being shown, because a stale or invented usage figure is worse than none.
 */
function CbGenerationUsage() {
  const supported = typeof backendSupports === 'function' ? backendSupports('usage.summary') : true
  const query = useRpcQuery('usage.summary', {}, 'cb-home-usage', supported)
  const usage = query.status === 'ready' ? query.data || {} : null

  const count = (value) =>
    typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString() : 'not recorded'
  const tokenRows = usage && usage.tokens ? usage.tokens : {}

  return jsxs('div', {
    'data-cb-usage': query.status,
    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
    children: [
      !supported
        ? jsx('p', {
            'data-cb-usage-unavailable': 'unsupported',
            style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: 'This build does not report generation usage.'
          })
        : query.status === 'loading'
          ? jsx('p', {
              style: { margin: 0, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
              children: 'Reading the usage record…'
            })
          : query.status === 'error'
            ? jsxs('div', {
                'data-cb-usage-error': (query.error && query.error.code) || 'ERROR',
                style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
                children: [
                  jsx(ErrorLine, { error: query.error }),
                  jsx('p', {
                    style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                    children: 'No usage total is shown while this read fails.'
                  }),
                  jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: query.reload, children: 'Read it again' })
                ]
              })
            : jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: CB_TYPE.caption, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
                children: [
                  jsx('div', {
                    'data-cb-usage-calls': String(usage && typeof usage.calls === 'number' ? usage.calls : ''),
                    children: `Generation calls: ${count(usage ? usage.calls : null)}`
                  }),
                  jsx('div', {
                    'data-cb-usage-tokens': 'input',
                    children: `Tokens in: ${count(tokenRows.input)} · out: ${count(tokenRows.output)}`
                  }),
                  jsx('div', {
                    'data-cb-usage-tokens': 'cache',
                    children: `Cache read: ${count(tokenRows.cache_read)} · cache write: ${count(tokenRows.cache_write)}`
                  }),
                  jsx('div', {
                    'data-cb-usage-artifacts': String(usage && typeof usage.artifacts === 'number' ? usage.artifacts : ''),
                    children: `Artifacts generated: ${count(usage ? usage.artifacts : null)}`
                  }),
                  usage && Array.isArray(usage.unknown_fields) && usage.unknown_fields.length
                    ? jsx('div', {
                        'data-cb-usage-unknown': String(usage.unknown_fields.length),
                        // `unknown_fields` names a field with at least one usage row that
                        // recorded no value for it (domain.usage_summary adds it per row), so
                        // this line must not call those fields "recorded". "not recorded" above
                        // stays the only claim about a missing count.
                        children: `Not recorded on every usage row: ${usage.unknown_fields.join(', ')}.`
                      })
                    : null,
                  jsx('div', {
                    children:
                      'A value the backend did not record reads “not recorded”. Nothing on this line is estimated, and no total is added up here.'
                  })
                ]
              })
    ]
  })
}

/**
 * H-147 — the one compact settings sheet, opened from Home.
 *
 * It is a sheet, not a route and not a second profile: the route stays `/coursebook`, and no
 * settings tab is added anywhere. It applies on change, names the current value on every control,
 * says "On this device" because the host has no account preference API, and keeps focus inside
 * itself until Escape or Close returns the reader to the control that opened it.
 */
function HomeSettingsSheet({ open, prefs, classroom, onUpdate, onReset, onClose }) {
  const panelRef = useRef(null)
  // GM-010: the SDK switch paints its own on/off colour but the host reset clears the UA focus
  // ring, so a keyboard reader cannot see which switch they are on. React's focus events bubble
  // from the SDK button, so the plugin-owned wrapper paints the identity ring while the inner
  // control matches `:focus-visible` — the same rule every other keyboard stop in this plugin uses.
  const [gameFeedbackFocused, setGameFeedbackFocused] = useState(false)
  const courseId = classroom && classroom.courseId ? classroom.courseId : null
  const override = courseId ? (prefs.classrooms && prefs.classrooms[courseId]) || null : null

  useEffect(() => {
    if (!open) return undefined
    const focusables = () => {
      const panel = panelRef.current
      if (!panel || typeof panel.querySelectorAll !== 'function') return []
      return Array.from(
        panel.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
      ).filter((node) => !node.disabled && node.getAttribute('aria-hidden') !== 'true')
    }
    const nodes = focusables()
    if (nodes.length > 0 && typeof nodes[0].focus === 'function') nodes[0].focus({ preventScroll: true })
    const onKeyDown = (event) => {
      if (!event || !event.key) return
      if (event.key === 'Escape' || event.key === 'Esc') {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        if (typeof event.stopPropagation === 'function') event.stopPropagation()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      const active = typeof document !== 'undefined' ? document.activeElement : null
      if (event.shiftKey && (active === first || !items.includes(active))) {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        last.focus({ preventScroll: true })
      } else if (!event.shiftKey && (active === last || !items.includes(active))) {
        if (typeof event.preventDefault === 'function') event.preventDefault()
        first.focus({ preventScroll: true })
      }
    }
    if (typeof document !== 'undefined' && document.addEventListener) {
      document.addEventListener('keydown', onKeyDown, true)
    }
    return () => {
      if (typeof document !== 'undefined' && document.removeEventListener) {
        document.removeEventListener('keydown', onKeyDown, true)
      }
    }
  }, [open, onClose])

  if (!open) return null

  return jsx('div', {
    'data-cb-settings-backdrop': '',
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 60,
      display: 'flex',
      justifyContent: 'flex-end',
      // A token-derived scrim: no hard-coded colour enters the palette.
      background: 'color-mix(in srgb, var(--cb-ink) 26%, transparent)'
    },
    onMouseDown: (event) => {
      if (event && event.target === event.currentTarget) onClose()
    },
    children: jsxs(
      'div',
      {
        ref: panelRef,
        role: 'dialog',
        'aria-modal': 'true',
        'aria-labelledby': CB_SETTINGS_TITLE_ID,
        'data-cb-settings-sheet': 'open',
        style: {
          width: '28.75rem',
          maxWidth: '100%',
          height: '100%',
          overflowY: 'auto',
          background: 'var(--cb-paper-raised)',
          color: 'var(--cb-ink)',
          borderLeft: '1px solid var(--cb-rule)',
          display: 'flex',
          flexDirection: 'column',
          padding: '0.75rem 1rem 1.25rem'
        },
        children: [
          jsxs(
            'div',
            {
              style: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' },
              children: [
                jsxs('div', {
                  style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
                  children: [
                    jsx('h2', {
                      id: CB_SETTINGS_TITLE_ID,
                      style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.heading, fontWeight: 600, lineHeight: 1.1 },
                      children: 'Settings'
                    }),
                    jsx('div', {
                      'data-cb-settings-scope': 'device',
                      style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                      children: 'On this device'
                    })
                  ]
                }),
                jsx(sdk.Button, {
                  size: 'sm',
                  variant: 'ghost',
                  'data-cb-settings-close': '',
                  'aria-label': 'Close settings',
                  style: { minHeight: '44px' },
                  onClick: onClose,
                  children: 'Close'
                })
              ]
            },
            'head'
          ),
          jsx('p', {
            style: {
              margin: '0.4rem 0 0',
              fontSize: CB_TYPE.caption,
              lineHeight: 1.5,
              color: 'var(--cb-ink-soft)'
            },
            children:
              'Stored for this Hermes profile on this device. Coursebook does not sync these settings to another device.'
          }),
          jsx(
            CbSettingsSection,
            {
              id: 'appearance',
              title: 'Appearance',
              description:
                'The palette Coursebook paints inside its own surfaces. Hermes chrome keeps the app theme.',
              resetLabel: 'Reset appearance to System',
              atDefault: prefs.appearance === CB_HOME_PREF_DEFAULTS.appearance,
              onReset: () => onReset('appearance'),
              children: jsx('div', {
                'data-cb-settings-control': 'appearance',
                'data-cb-settings-value': prefs.appearance,
                style: { minWidth: 0 },
                children: jsx(sdk.SegmentedControl, {
                  options: CB_APPEARANCE_OPTIONS,
                  value: prefs.appearance,
                  onChange: (id) => onUpdate({ appearance: id }),
                  className: 'min-h-11 items-stretch'
                })
              })
            },
            'appearance'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'default-view',
              title: 'Default view',
              description: 'The view a lesson opens in. A single classroom can override it.',
              resetLabel: 'Reset the default view to Game',
              atDefault: prefs.defaultMode === CB_HOME_PREF_DEFAULTS.defaultMode,
              onReset: () => onReset('defaultMode'),
              children: jsx('div', {
                'data-cb-settings-control': 'default-view',
                'data-cb-settings-value': prefs.defaultMode,
                style: { minWidth: 0 },
                children: jsx(sdk.SegmentedControl, {
                  options: CB_PRESENTATION_OPTIONS,
                  value: prefs.defaultMode,
                  onChange: (id) => onUpdate({ defaultMode: id }),
                  className: 'min-h-11 items-stretch'
                })
              })
            },
            'default-view'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'classroom',
              title: courseId && classroom.title ? `This classroom · ${classroom.title}` : 'This classroom',
              description: courseId
                ? 'This classroom keeps its own view. Choosing the home default clears the override.'
                : 'Select a classroom on Home to give it its own view.',
              resetLabel: 'Clear this classroom’s view override',
              atDefault: !override,
              onReset: () => onReset('classroom'),
              children: jsx('div', {
                'data-cb-settings-control': 'classroom',
                'data-cb-settings-value': override || 'default',
                style: { minWidth: 0, opacity: courseId ? 1 : 0.6 },
                children: jsx(sdk.SegmentedControl, {
                  options: [{ id: 'default', label: 'Home default' }].concat(CB_PRESENTATION_OPTIONS),
                  value: override || 'default',
                  disabled: !courseId,
                  onChange: (id) => {
                    if (!courseId) return
                    const classrooms = { ...(prefs.classrooms || {}) }
                    if (id === 'default') delete classrooms[courseId]
                    else classrooms[courseId] = id
                    onUpdate({ classrooms })
                  },
                  className: 'min-h-11 items-stretch'
                })
              })
            },
            'classroom'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'child-safe',
              title: 'Child-safe defaults',
              description:
                'For any lesson a child uses. No reminder scheduler, no public ranking, no random rewards and no streaks. XP and levels are cosmetic Game feedback only, and the Game feedback switch below hides them here.',
              resetLabel: 'Reset the session length to 15 minutes',
              atDefault: prefs.sessionMinutes === CB_HOME_PREF_DEFAULTS.sessionMinutes,
              onReset: () => onReset('sessionMinutes'),
              children: jsxs('div', {
                'data-cb-child-safe': 'on',
                style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0 },
                children: [
                  jsx('ul', {
                    'data-cb-child-safe-rules': '',
                    style: {
                      listStyle: 'none',
                      margin: 0,
                      padding: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.3rem'
                    },
                    children: CB_CHILD_SAFE_RULES.map((rule) => {
                      // UX-2: the same sheet says XP does not exist and then offers the switch
                      // that shows it. The rule names what is true: XP and levels are Game-mode
                      // feedback only, and this device's switch reports whether it is hidden here.
                      const state =
                        rule.id === 'xp' && prefs.gameFeedback === false ? 'Hidden here' : rule.state
                      return jsxs(
                        'li',
                        {
                          'data-cb-child-safe-rule': rule.id,
                          'data-cb-child-safe-state': state.toLowerCase().replace(/\s+/g, '-'),
                          style: {
                            display: 'flex',
                            alignItems: 'baseline',
                            justifyContent: 'space-between',
                            gap: '0.75rem',
                            fontSize: CB_TYPE.meta,
                            lineHeight: 1.45,
                            color: 'var(--cb-ink-soft)'
                          },
                          children: [
                            jsx('span', { children: rule.label }),
                            jsx('strong', {
                              style: { color: 'var(--cb-ink)', fontWeight: 600, whiteSpace: 'nowrap' },
                              children: state
                            })
                          ]
                        },
                        rule.id
                      )
                    })
                  }),
                  jsxs('div', {
                    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
                    children: [
                      jsx('span', {
                        id: 'cb-settings-session-length-label',
                        style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' },
                        children: 'Session length'
                      }),
                      jsx('div', {
                        'data-cb-settings-control': 'session-length',
                        'data-cb-settings-value': String(prefs.sessionMinutes),
                        'aria-labelledby': 'cb-settings-session-length-label',
                        style: { minWidth: 0 },
                        children: jsx(sdk.SegmentedControl, {
                          options: CB_SESSION_OPTIONS,
                          value: String(prefs.sessionMinutes),
                          onChange: (id) => {
                            const minutes = Number(id)
                            if (CB_SESSION_CHOICES.indexOf(minutes) >= 0) onUpdate({ sessionMinutes: minutes })
                          },
                          className: 'min-h-11 items-stretch'
                        })
                      }),
                      jsx('p', {
                        style: { margin: 0, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                        children:
                          'A plan the parent writes, not a countdown. No reminder is sent when a session is missed.'
                      })
                    ]
                  })
                ]
              })
            },
            'child-safe'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'sound',
              title: 'Sound',
              description: 'A short tone when a check is scored. Off by default.',
              resetLabel: 'Reset sound to off',
              atDefault: prefs.sound === CB_HOME_PREF_DEFAULTS.sound,
              onReset: () => onReset('sound'),
              children: jsx('div', {
                'data-cb-settings-toggle': 'sound',
                children: jsx(sdk.ToggleRow, {
                  checked: prefs.sound === true,
                  label: 'Check cue sound',
                  description: 'One quiet tone at a verdict, never narration.',
                  onChange: (on) => onUpdate({ sound: on === true })
                })
              })
            },
            'sound'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'companion',
              title: 'Study companion',
              description:
                'The Hermes pet already installed in this profile can stand at the trailhead. Coursebook never draws a different avatar, and the companion is never a progress marker.',
              resetLabel: 'Reset the study companion to shown',
              atDefault: prefs.companion === CB_HOME_PREF_DEFAULTS.companion,
              onReset: () => onReset('companion'),
              children: jsx('div', {
                'data-cb-settings-toggle': 'companion',
                children: jsx(sdk.ToggleRow, {
                  checked: prefs.companion === true,
                  label: 'Show my study companion',
                  description: 'Your own Hermes pet beside the trailhead. Off leaves the plate without a companion.',
                  onChange: (on) => onUpdate({ companion: on === true })
                })
              })
            },
            'companion'
          ),
          // H-183: a desktop has no haptic engine, so this is an availability note, never a switch.
          // A disabled toggle would still promise a setting the host cannot honour.
          jsx(
            CbSettingsSection,
            {
              id: 'haptics',
              title: 'Haptics',
              description: 'Not available on desktop.',
              resetLabel: 'Haptics are always off on desktop',
              atDefault: true,
              onReset: () => {},
              children: jsx('p', {
                'data-cb-settings-unavailable': 'haptics',
                style: { margin: 0, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children:
                  'A desktop has no haptic engine, so Coursebook never offers a vibration response. There is nothing here to switch on or off.'
              })
            },
            'haptics'
          ),
          jsx(
            CbSettingsSection,
            {
              id: 'reduced-motion',
              title: 'Reduced motion',
              description:
                'Follow the system setting, or hold Coursebook to no transitions even when the system allows them.',
              resetLabel: 'Reset motion to follow the system',
              atDefault: prefs.reducedMotion === CB_HOME_PREF_DEFAULTS.reducedMotion,
              onReset: () => onReset('reducedMotion'),
              children: jsx('div', {
                'data-cb-settings-control': 'reduced-motion',
                'data-cb-settings-value': prefs.reducedMotion,
                style: { minWidth: 0 },
                children: jsx(sdk.SegmentedControl, {
                  options: CB_REDUCED_MOTION_OPTIONS,
                  value: prefs.reducedMotion,
                  onChange: (id) => onUpdate({ reducedMotion: id }),
                  className: 'min-h-11 items-stretch'
                })
              })
            },
            'reduced-motion'
          ),
          // GM-010: the play layer's own switch. It sits beside Sound and Reduced motion because
          // it changes feedback, not the course; turning it off keeps every ledger row.
          jsx(
            CbSettingsSection,
            {
              id: 'game-feedback',
              title: 'Game feedback',
              description:
                'XP, the cosmetic level and the Game progress bar in Game mode, earned by finished checks — never by opening the app or checking in. Play progress only: hiding it never deletes your play history, and no check, source or lesson depends on it.',
              resetLabel: 'Reset Game feedback to shown',
              atDefault: prefs.gameFeedback === CB_HOME_PREF_DEFAULTS.gameFeedback,
              onReset: () => onReset('gameFeedback'),
              children: jsx('div', {
                'data-cb-settings-toggle': 'game-feedback',
                'data-cb-settings-focus': gameFeedbackFocused ? 'ring' : null,
                onFocus: (event) => setGameFeedbackFocused(focusRingVisible(event.target)),
                onBlur: () => setGameFeedbackFocused(false),
                style: {
                  borderRadius: '0.5rem',
                  outline: gameFeedbackFocused ? CB_FOCUS_RING : 'none',
                  outlineOffset: '2px'
                },
                children: jsx(sdk.ToggleRow, {
                  checked: prefs.gameFeedback !== false,
                  label: 'Show Game feedback',
                  description:
                    'The XP chip, level and progress bar in Game mode. Textbook, Guided and Parent Studio never show them either way.',
                  onChange: (on) => onUpdate({ gameFeedback: on === true })
                })
              })
            },
            'game-feedback'
          ),
          // UI-K13: the one quiet usage block. It is a read, not a setting, so it carries no
          // reset control; it sits last because nothing here changes how a lesson behaves.
          jsx(
            CbSettingsSection,
            {
              id: 'usage',
              title: 'Generation usage',
              description:
                'What Coursebook’s own generation has used on this profile. A number the backend did not record is shown as not recorded, never as zero.',
              readOnly: true,
              children: jsx(CbGenerationUsage, {})
            },
            'usage'
          )
        ]
      },
      'sheet'
    )
  })
}

/**
 * The Home defaults line and its one-interaction Settings trigger. It names the current default
 * without opening anything, and it names a classroom override when the selected classroom has one.
 */
function HomeDefaultsLine({ prefs, classroom, onOpenSettings, triggerRef }) {
  const courseId = classroom && classroom.courseId ? classroom.courseId : null
  const override = courseId ? (prefs.classrooms && prefs.classrooms[courseId]) || null : null
  const effective = cbEffectiveMode(prefs, courseId)
  return jsxs('div', {
    'data-cb-home-defaults': prefs.defaultMode,
    'data-cb-home-effective': effective,
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem', minHeight: '2.75rem' },
    children: [
      jsxs('span', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: [
          'Default view · ',
          jsx('strong', { style: { color: 'var(--cb-ink)', fontWeight: 600 }, children: CB_PRESENTATION_LABEL[prefs.defaultMode] || 'Game' })
        ]
      }),
      override
        ? jsxs('span', {
            'data-cb-home-override': override,
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [
              '· This classroom · ',
              jsx('strong', { style: { color: 'var(--cb-ink)', fontWeight: 600 }, children: CB_PRESENTATION_LABEL[override] || override })
            ]
          })
        : null,
      // H-156 — the child-safe floor and the parent-set session length are visible on Home before
      // the sheet is opened, so nobody has to find Settings to learn what the defaults are.
      jsx('span', {
        'data-cb-child-safe': 'on',
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: '· Child-safe defaults'
      }),
      jsx('span', {
        'data-cb-session-minutes': String(prefs.sessionMinutes),
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: `· Session · ${prefs.sessionMinutes} min`
      })
      // H-176: Settings is the route header's small labelled control now, not a third item on
      // this line. The line still names the effective defaults without opening anything.
    ]
  })
}

/**
 * H-156 — the same child-safe line in Parent Studio, where a parent prepares the lesson.
 *
 * It names the session length and the fixed floor, and it opens the one settings sheet. Two
 * destinations never mount at once, so the route's single trigger ref belongs to whichever line
 * is on screen; Escape returns focus to that line's own Settings button.
 */
function ChildSafeLine({ sessionMinutes, onOpenSettings, triggerRef }) {
  return jsxs('div', {
    'data-cb-child-safe': 'on',
    'data-cb-session-minutes': String(sessionMinutes),
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem', minHeight: '2.75rem' },
    children: [
      jsx('span', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: 'Child-safe defaults · no loss-framed reminders, no ranking, no random rewards, no streaks · XP is cosmetic Game feedback'
      }),
      jsx('span', {
        style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: `· Session · ${sessionMinutes} min`
      }),
      jsx('span', {
        ref: triggerRef,
        style: { display: 'inline-flex', alignItems: 'center' },
        children: jsx(sdk.Button, {
          size: 'sm',
          variant: 'ghost',
          'data-cb-settings-open': '',
          'aria-label': 'Open Coursebook settings',
          'aria-haspopup': 'dialog',
          style: { minHeight: '44px' },
          onClick: onOpenSettings,
          children: 'Settings'
        })
      })
    ]
  })
}

/**
 * GM-010 — the Game-only play layer: XP chip, cosmetic level and `Game progress`.
 *
 * `engagement.read` is the only source of every number painted here. The renderer never adds a
 * point, never derives a level, never turns a count into a percentage of skill and never stores
 * anything: the ledger belongs to the backend (GM-009), and this block reads it.
 *
 * The layer is mounted only where the *course's own durable mode* is `game`, so Textbook, Guided,
 * Parent Studio, packs and exports cannot show it by accident — those surfaces never mount this
 * block at all. A parent-led course (`recipe === 'parent'`) is excluded as well: §10B.4 says a
 * child using a parent-led lesson does not get a child-facing XP surface.
 */
const CB_GAME_ACTION_WORD = Object.freeze({
  lesson_step: 'Lesson step',
  check_submitted: 'Check',
  review: 'Review',
  homework_completed: 'Homework done',
  returned: 'Came back'
})

/**
 * The one honesty line every game surface carries. The plan allows the play layer and forbids
 * calling it learning: so the bar is labelled `Game progress` (the backend's own const) and this
 * note sits beside it. No screen may say mastery, proficiency or verified skill here.
 */
const CB_GAME_PROGRESS_NOTE = 'Play progress, not evidence.'

/** Whether the play layer may paint. The device switch and the backend setting both hide it. */
function cbGameFeedbackVisible(prefs, engagement) {
  if (prefs && prefs.gameFeedback === false) return false
  const progress = engagement && engagement.progress ? engagement.progress : null
  return !(progress && progress.feedback_visible === false)
}

/**
 * A Game course is the durable mode read from `world.read`, never the device preference and never
 * the recipe alone. A `library.list` row carries no mode, so a caller that has not read the mode
 * passes `null` and gets no play layer — the honest answer for "unknown".
 */
function cbGameCourse(row, mode) {
  if (!row || !row.course_id || row.recipe === 'parent') return false
  return readCoursePresentationMode(mode) === 'game'
}

/**
 * The Game header: one band of honest play-state chips over one bar.
 *
 * It is deliberately short. The primary action, the current objective and the check live in their
 * own surfaces below and keep their hierarchy; this band names play progress and nothing else. A
 * zero-step course paints no bar rather than an empty frame.
 *
 * v3 (CP-025a): the band paints from `--cb3-*` roles and the v3 type steps only. Gold is a mark in
 * the contract, never a text background, so the XP chip carries a gold edge and ink text; the bar's
 * fill is the same mark tone. The flame glyph is the only Game-only icon (SPEC-V3 §3.7).
 * Tokens: rule, ink, ink-soft, gold, card-stock, radius.pill, type.meta, type.caption.
 */
function GameHeader({ engagement, status, error, prefs, compact, onRetry }) {
  const motion = useCbMotion()
  if (!cbGameFeedbackVisible(prefs, engagement)) return null

  const bandStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: compact ? '0.4rem 0.5rem' : '0.5rem 0.75rem',
    minWidth: 0,
    padding: '0.5rem 0',
    borderTop: `1px solid ${cb3Role('rule')}`,
    borderBottom: `1px solid ${cb3Role('rule')}`
  }
  const chipStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.3rem',
    minHeight: '32px',
    padding: '0.2rem 0.6rem',
    borderRadius: cb3Radius('pill'),
    border: `1px solid ${cb3Role('rule')}`,
    backgroundColor: 'transparent',
    color: cb3Role('ink'),
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('meta'),
    lineHeight: cb3Lead('meta'),
    whiteSpace: 'nowrap'
  }
  const quietLine = {
    margin: 0,
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('caption'),
    lineHeight: cb3Lead('caption'),
    color: cb3Role('ink-soft')
  }

  if (status === 'error') {
    return jsxs('div', {
      'data-cb-game': 'error',
      'data-cb3-game': 'error',
      role: 'status',
      style: bandStyle,
      children: [
        jsx('span', {
          style: quietLine,
          children: `The field journal could not be read: ${describeError(error)} Your course is unaffected.`
        }, 'message'),
        onRetry
          ? jsx(PillAction, { 'data-cb3-game-retry': '', variant: 'quiet', onClick: onRetry, children: 'Try again' }, 'retry')
          : null
      ]
    })
  }

  if (!engagement) {
    // A read in flight is a state, not a zero: no chip and no bar until the backend answers.
    return jsx('div', {
      'data-cb-game': 'loading',
      'data-cb3-game': 'loading',
      role: 'status',
      style: bandStyle,
      children: jsx('span', { style: quietLine, children: 'Reading the field journal…' })
    })
  }

  const level = engagement.level || {}
  const progress = engagement.progress || {}
  const xp = Math.max(0, Number(engagement.xp_total) || 0)
  const assigned = Math.max(0, Number(progress.assigned_steps) || 0)
  const completed = Math.max(0, Number(progress.completed_steps) || 0)
  // `completed_steps` can exceed the plan's assigned count after a re-plan; the bar shows reached
  // of assigned and never a ratio that implies a skill score.
  const done = assigned ? Math.min(completed, assigned) : 0
  const ratio = assigned ? done / assigned : 0
  const levelNumber = Math.max(1, Number(level.level) || 1)

  return jsxs('section', {
    'data-cb-game': 'ready',
    'data-cb3-game': 'header',
    'aria-label': 'Game',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: [
      jsxs('div', {
        style: bandStyle,
        children: [
          jsxs('span', {
            'data-cb-game-xp': String(xp),
            'data-cb3-chip': 'xp',
            style: { ...chipStyle, borderColor: cb3Role('gold'), fontWeight: 600 },
            children: [
              jsx('span', {
                'aria-hidden': 'true',
                style: { display: 'inline-flex', color: cb3Role('gold') },
                children: jsx(sdk.Codicon, { name: 'flame', size: CB_ICON_UI })
              }, 'flame'),
              jsx('span', { children: `${xp} XP` }, 'value')
            ]
          }, 'xp'),
          jsxs('span', {
            'data-cb-game-level': String(levelNumber),
            'data-cb3-chip': 'level',
            style: { ...chipStyle, padding: '0.2rem 0.65rem' },
            children: [
              jsx('span', { style: { fontWeight: 600 }, children: `Level ${levelNumber}` }, 'level'),
              jsx('span', { style: { color: cb3Role('ink-soft') }, children: level.title || 'Explorer' }, 'title'),
              jsx('span', { style: { color: cb3Role('ink-soft') }, children: '· cosmetic' }, 'cosmetic')
            ]
          }, 'level'),
          jsxs('div', {
            'data-cb-game-progress': String(done),
            'data-cb3-game-progress': String(done),
            style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', flex: '1 1 12rem', minWidth: 0 },
            children: [
              jsxs('div', {
                style: {
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'baseline',
                  justifyContent: 'space-between',
                  gap: '0.15rem 0.5rem',
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('caption'),
                  lineHeight: cb3Lead('caption'),
                  color: cb3Role('ink-soft')
                },
                children: [
                  jsx('span', { style: { fontWeight: 600, color: cb3Role('ink') }, children: progress.label || 'Game progress' }, 'label'),
                  jsx('span', {
                    children: assigned
                      ? `${done} of ${assigned} ${assigned === 1 ? 'step' : 'steps'}`
                      : 'No steps assigned yet'
                  }, 'count')
                ]
              }),
              assigned
                ? jsx('div', {
                    role: 'progressbar',
                    'aria-label': progress.label || 'Game progress',
                    'aria-valuemin': 0,
                    'aria-valuemax': assigned,
                    'aria-valuenow': done,
                    style: {
                      position: 'relative',
                      height: '0.4rem',
                      width: '100%',
                      backgroundColor: cb3Role('rule'),
                      borderRadius: cb3Radius('pill'),
                      overflow: 'hidden'
                    },
                    children: jsx('div', {
                      style: {
                        position: 'absolute',
                        inset: '0',
                        width: `${Math.round(ratio * 100)}%`,
                        backgroundColor: cb3Role('gold'),
                        // One authored beat: the fill arrives once; a reduced-motion reader gets
                        // the same state with no travel at all.
                        transition: motion.reduced
                          ? 'none'
                          : `width var(--cb3-dur-complete) var(--cb3-ease)`
                      }
                    })
                  })
                : null
            ]
          }, 'progress'),
          jsx('span', {
            style: { ...quietLine, flex: '0 1 auto' },
            children: CB_GAME_PROGRESS_NOTE
          }, 'note')
        ]
      })
    ]
  })
}

/**
 * Collectible section cards, earned only by real evidence.
 *
 * A card is stamped when the outline says that section carries independent evidence
 * (`objective.independent`), which is the same fact the evidence surfaces print. No star, no
 * rating, no invented count: a card that has not been earned says what it actually is.
 */
function cbGameSectionCards(objectives) {
  const rows = Array.isArray(objectives) ? objectives.filter(Boolean) : []
  return rows.slice(0, 12).map((entry) => ({
    id: entry.objective_id,
    title: entry.title || 'Untitled section',
    ordinal: entry.ordinal ? Number(entry.ordinal) : null,
    state: entry.state || 'not_started',
    earned: entry.independent === true
  }))
}

/**
 * The field journal: one paper panel, one row per real section, stamped only by recorded evidence.
 *
 * A card is stamped when the outline says that section carries independent evidence
 * (`objective.independent`), which is the same fact the evidence surfaces print. No star, no
 * rating, no invented count: a card that has not been earned says what it actually is. The rows are
 * a list inside one paper object rather than twelve floating cards, so a small course still reads
 * as one shelf and never as card-in-card.
 * Tokens: card-stock, rule, ink, ink-soft, gold, radius.round, radius.pill, type.*.
 */
function GameJournal({ objectives, compact }) {
  const cards = cbGameSectionCards(objectives)
  if (cards.length === 0) return null
  const earned = cards.filter((card) => card.earned).length
  return jsx(PaperCard, {
    'data-cb-game-journal': String(earned),
    'data-cb3-game': 'journal',
    'aria-label': 'Field journal',
    emphasis: 'elev-1',
    style: { gap: '0.5rem', maxWidth: CB_MEASURE },
    children: jsxs('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0 },
      children: [
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.15rem 0.75rem' },
          children: [
            jsx('h3', {
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-display)',
                fontSize: cb3Type('heading'),
                lineHeight: cb3Lead('heading'),
                fontWeight: 600,
                color: cb3Role('ink'),
                maxWidth: '34ch'
              },
              children: 'Field journal'
            }, 'heading'),
            jsx('span', {
              style: {
                fontFamily: 'var(--cb3-font-ui)',
                fontSize: cb3Type('caption'),
                lineHeight: cb3Lead('caption'),
                color: cb3Role('ink-soft')
              },
              children: earned
                ? `${earned} of ${cards.length} sections stamped by recorded evidence.`
                : 'No section is stamped yet. A stamp appears when evidence is recorded, never for opening a page.'
            }, 'count')
          ]
        }),
        jsx('ul', {
          style: {
            display: 'flex',
            flexDirection: 'column',
            margin: 0,
            padding: 0,
            listStyle: 'none',
            minWidth: 0
          },
          children: cards.map((card, index) =>
            jsxs(
              'li',
              {
                'data-cb-game-card': card.earned ? 'earned' : card.state,
                style: {
                  display: 'grid',
                  gridTemplateColumns: compact ? 'minmax(0, 1fr)' : '5.5rem minmax(0, 1fr) auto',
                  alignItems: 'baseline',
                  gap: compact ? '0.15rem' : '0.75rem',
                  padding: '0.5rem 0',
                  borderTop: index === 0 ? 0 : `1px solid ${cb3Role('rule')}`,
                  minWidth: 0
                },
                children: [
                  jsx('span', {
                    style: {
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      lineHeight: cb3Lead('caption'),
                      color: cb3Role('ink-soft'),
                      letterSpacing: '0.04em'
                    },
                    children: CB_COPY.sectionLabel(card.ordinal, null)
                  }, 'ordinal'),
                  jsx('span', {
                    style: {
                      fontFamily: 'var(--cb3-font-display)',
                      fontSize: cb3Type('meta'),
                      lineHeight: cb3Lead('meta'),
                      fontWeight: 600,
                      color: cb3Role('ink'),
                      overflowWrap: 'anywhere'
                    },
                    children: card.title
                  }, 'title'),
                  card.earned
                    ? jsx('span', {
                        'data-cb3-chip': 'stamped',
                        style: {
                          justifySelf: compact ? 'start' : 'end',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          padding: '0.1rem 0.5rem',
                          borderRadius: cb3Radius('pill'),
                          border: `1px solid ${cb3Role('gold')}`,
                          fontFamily: 'var(--cb3-font-ui)',
                          fontSize: cb3Type('caption'),
                          lineHeight: cb3Lead('caption'),
                          fontWeight: 600,
                          color: cb3Role('ink')
                        },
                        children: [
                          jsx('span', {
                            'aria-hidden': 'true',
                            style: { display: 'inline-flex', color: cb3Role('gold') },
                            children: jsx(sdk.Codicon, { name: 'check', size: CB_ICON_UI })
                          }, 'glyph'),
                          jsx('span', { children: 'Stamped' }, 'word')
                        ]
                      }, 'state')
                    : jsx('span', {
                        style: {
                          justifySelf: compact ? 'start' : 'end',
                          fontFamily: 'var(--cb3-font-ui)',
                          fontSize: cb3Type('caption'),
                          lineHeight: cb3Lead('caption'),
                          fontWeight: 500,
                          color: cb3Role('ink-soft')
                        },
                        children: CB_COPY.stateWord(card.state)
                      }, 'state')
                ]
              },
              card.id
            )
          )
        })
      ]
    })
  })
}
