function EmptyState({ title, description, children }) {
  return jsxs('div', {
    className: 'flex flex-col items-center gap-3',
    children: [jsx(sdk.EmptyState, { title, description }), children || null]
  })
}

function openCapabilities() {
  if (!pluginContext) return
  const outcome = pluginContext.runAction('nav.capabilities')
  if (!outcome || !outcome.ok) {
    sdk.host.notify({ kind: 'warning', message: 'Open Capabilities → Plugins and enable Coursebook.' })
  }
}

function StatusRow({ label, value, detail }) {
  return jsxs('div', {
    className: 'flex items-baseline justify-between gap-4 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
    children: [
      jsxs('div', {
        className: 'min-w-0',
        children: [
          jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: label }),
          detail
            ? jsx('div', { className: 'mt-0.5 text-xs text-(--ui-text-secondary)', children: detail })
            : null
        ]
      }),
      jsx('div', { className: 'shrink-0 text-right text-xs text-(--ui-text-secondary)', children: value })
    ]
  })
}

/** A warning is text, never color alone. */
const WARNING_COPY = {
  detached_chat: {
    label: 'Detached chat',
    detail: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.'
  },
  pack_frozen: {
    label: 'Pack frozen',
    detail: 'The imported pack this course came from is frozen; its content will not change.'
  },
  stale_source: {
    label: 'Source stale',
    detail: 'A source behind this course changed. Existing evidence is kept; the source needs review.'
  },
  plan_update: {
    label: 'Plan update',
    detail: 'A newer plan draft is waiting for review.'
  }
}

function WarningBadge({ warning }) {
  const copy = WARNING_COPY[warning]
  if (!copy) return null
  return jsx(sdk.Badge, { variant: 'warn', children: copy.label })
}

function EvidenceLine({ summary }) {
  if (!summary) return null
  const independent = Number(summary.independent || 0)
  const reviewDue = Number(summary.review_due || 0)
  const total = Number(summary.total_objectives || 0)
  const parts = [
    `${independent} independent`,
    reviewDue > 0 ? `${reviewDue} due` : null,
    total > 0 ? `${total} objective${total === 1 ? '' : 's'}` : null
  ].filter(Boolean)
  return jsx('div', {
    className: 'mt-1.5 text-xs text-(--ui-text-secondary)',
    children: parts.join(' · ')
  })
}

function ErrorLine({ error }) {
  if (!error) return null
  const code = error.code ? String(error.code) : ''
  // H-183: the learner reads the sentence. The typed code is inspection evidence, so it sits behind
  // the same `Technical detail` disclosure the rest of the surface uses.
  return jsxs('div', {
    className: 'mt-2 text-xs text-(--ui-text-secondary)',
    children: [
      jsx('div', { children: describeError(error) }),
      code
        ? jsxs('details', {
            'data-cb-error-technical': '',
            style: { color: 'var(--cb-ink-soft)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer', minHeight: '1.75rem' }, children: 'Technical detail' }),
              jsx('p', { style: { margin: '0.25rem 0 0', overflowWrap: 'anywhere' }, children: code })
            ]
          })
        : null
    ]
  })
}

/** Shared page chrome: the route's one `main` landmark, named for the surface it holds. */
function PageBody({ children, label }) {
  return jsx('main', {
    id: 'cb-main-content',
    'data-cb-main': '',
    tabIndex: -1,
    'aria-label': label || 'Coursebook content',
    className: 'min-h-0 flex-1 overflow-auto pb-6',
    children
  })
}

/**
 * The skip path. It is the first focus stop on the route and is clipped until it is focused, so a
 * keyboard or screen-reader user can jump the route header and the destination nav. It lands on the
 * reading column when the surface has one (a section or textbook page), and on the `main` region
 * otherwise — never on the header.
 */
function SkipToContent({ label }) {
  const [revealed, setRevealed] = useState(false)
  const hidden = {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0 0 0 0)',
    whiteSpace: 'nowrap',
    border: '1px solid transparent',
    fontFamily: CB_SANS,
    fontSize: CB_TYPE.meta,
    lineHeight: 1.4
  }
  const shown = {
    ...hidden,
    width: 'auto',
    height: 'auto',
    margin: 0,
    padding: '0.35rem 0.7rem',
    overflow: 'visible',
    clip: 'auto',
    zIndex: 40,
    color: 'var(--cb-on-lamp)',
    background: 'var(--cb-lamp)',
    border: '1px solid var(--cb-ink)',
    borderRadius: '2px',
    textDecoration: 'none'
  }
  return jsx('a', {
    href: '#cb-main-content',
    'data-cb-skip': '',
    onFocus: () => setRevealed(true),
    onBlur: () => setRevealed(false),
    onClick: (event) => {
      const root = document.querySelector('[data-cb-route]')
      const reading = root ? root.querySelector('[data-cb-reading-column]') : null
      const main = document.getElementById('cb-main-content')
      const target = reading || main
      if (!target) return
      event.preventDefault()
      target.setAttribute('tabindex', '-1')
      if (typeof target.focus === 'function') target.focus({ preventScroll: true })
      if (typeof target.scrollIntoView === 'function') target.scrollIntoView({ block: 'start' })
    },
    style: revealed ? shown : hidden,
    children: label || 'Skip to course content'
  })
}

function backendCopy(status) {
  if (status === 'degraded') return 'Database not migrated'
  if (status === 'unavailable') return 'Backend off'
  return null
}

function BackendUnavailable({ error, reload }) {
  return jsx('div', {
    className: 'mx-auto flex w-full max-w-xl flex-col gap-4 py-8',
    children: [
      jsx(sdk.ErrorState, {
        title: 'Coursebook needs its agent plugin',
        description:
          'Coursebook is turned on in Desktop, but its backend is not answering for this profile. ' +
          'Enable Coursebook under Capabilities → Plugins, then restart the gateway. ' +
          'Desktop and backend halves are enabled separately.',
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(CbAction, { variant: 'primary', onClick: openCapabilities, children: 'Open Capabilities' }),
            jsx(CbAction, { variant: 'secondary', onClick: reload, children: 'Check again' })
          ]
        })
      }),
      jsx('div', {
        className: 'text-center text-xs text-(--ui-text-secondary)',
        children: error && error.code
          ? `${error.code}: ${describeError(error)}`
          : describeError(error)
      })
    ]
  })
}

/** The backend answered, but its database has no schema: nothing can be stored or listed yet. */
function DegradedBody({ result, reload }) {
  const db = result && result.db ? result.db : {}
  return jsx('div', {
    className: 'mx-auto flex w-full max-w-xl flex-col gap-4 py-8',
    children: [
      jsx(sdk.ErrorState, {
        title: 'The course database is not migrated yet',
        description:
          'The backend is connected and its contract is loaded, but this profile has no course ' +
          'tables, so there is nowhere to store a course and nothing honest to list. This page ' +
          'will not show an empty library as if you had no courses.',
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(CbAction, { variant: 'primary', onClick: reload, children: 'Check again' }),
            jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, {
            label: 'Backend contract',
            value: `cb.rpc v${result && result.contract_version ? result.contract_version : backendWire.contractVersion}`,
            detail: `plugin ${result && result.plugin_version ? result.plugin_version : 'unknown'}`
          }),
          jsx(StatusRow, {
            label: 'Database',
            value: db.ready ? `schema v${db.schema_version}` : 'not migrated',
            detail: db.ready ? 'Profile-scoped SQLite is ready.' : 'No course tables exist for this profile yet.'
          })
        ]
      })
    ]
  })
}

/**
 * H-153 — the start plate: one headline, one short "what happens" line, one primary action and at
 * most one secondary door.
 *
 * What this replaces, and why: the plate used to carry a three-step explainer, a progress
 * paragraph and a capability inventory ("Not in this backend build yet: pack preview, ..."). Read
 * cold, that was a policy page: four blocks of explanation before a learner could press anything.
 * The question, one sentence about what pressing does, and one button are enough. The seal is gone
 * (H-145), and so is the support note: an absent command is *absent*, never announced as inventory.
 *
 * Every entry is still gated on the command that serves it, never rendered disabled:
 *   create    `course.create` — the plate's primary.
 *   import    `pack.import` — one of the Library's two doors, behind the one secondary.
 *   syllabus  `syllabus.intake.create` — the Library's other door, behind the same secondary.
 * The secondary opens the Library only when at least one of its doors is actually mounted; with
 * neither, the secondary is absent rather than dead. If this build cannot create a course, the
 * same line says so instead of listing missing methods.
 *
 * Offline is a state, not an empty profile: the plate keeps its headline, says what is paused and
 * offers one retry. A failed or in-flight read never reaches this component at all — the surfaces
 * above it show the error or the loader — so nothing here can claim a profile is empty.
 */
const FIRST_RUN_COPY = {
  title: 'What do you want to be able to do?',
  promise: 'Name one goal, review the plan, then learn. Nothing is created until you approve the plan.',
  primary: 'Start with a goal',
  secondary: 'Use a course I already have',
  unavailable: 'This version of Coursebook cannot create a course yet.',
  noEntries: 'This version of Coursebook cannot create or add a course yet.',
  offline: 'A new course is paused while this profile is offline. Nothing you already saved is lost.',
  retry: 'Try again'
}

function FirstRun({ implemented, onCreate, onSyllabus, onBrowseLibrary, onRetry, companionEnabled }) {
  const online = useOnline()
  const connected = online !== false
  const canCreate = Boolean(connected && implemented && implemented.has('course.create')) && typeof onCreate === 'function'
  // The Library owns import and college-syllabus intake; its row is offered only when one of those
  // doors is mounted, so the secondary always opens a shelf that can actually do something.
  const libraryHasEntry = Boolean(
    implemented &&
      (implemented.has('syllabus.intake.create') || (IMPORT_FLOW_WIRED && implemented.has('pack.import')))
  )
  const canBrowse = Boolean(connected && libraryHasEntry) && typeof onBrowseLibrary === 'function'
  const canRetry = !connected && typeof onRetry === 'function'
  const line = !connected
    ? FIRST_RUN_COPY.offline
    : canCreate
      ? FIRST_RUN_COPY.promise
      : canBrowse
        ? FIRST_RUN_COPY.unavailable
        : FIRST_RUN_COPY.noEntries
  const actionLabel = connected ? FIRST_RUN_COPY.primary : FIRST_RUN_COPY.retry
  const action = connected ? onCreate : onRetry
  const showAction = connected ? canCreate : canRetry
  const width = useCbViewportWidth()
  const compact = width > 0 && width < 520
  // FINAL-POLISH-SPEC §3 first-run: the same plate with no course, a contour ghost, and the
  // learner's own companion at the threshold. The ghost is decorative (`aria-hidden`); the pet is
  // only drawn when the host answers with a real sheet, and never on a surface that is not Home.
  const pet = useStudyCompanion(companionEnabled === true)
  const ghostHeight = width > 0 && width < 380 ? 48 : 96
  // At 460 px the route column is ~215 px; at 200% text that is the width a phone browser gives a
  // 320 px layout, so the headline steps down and the plate's own inset stops eating the measure.
  // (The column width is the host shell's; the plate must not make it worse.)
  const veryNarrow = width > 0 && width < 300
  const headingSize = veryNarrow ? CB_TYPE.lead : compact ? CB_TYPE.heading : CB_TYPE.display
  // A host Button keeps its label on one line (`whitespace-nowrap`). At a 460 px window the route
  // column is ~215 px, so "Use a course I already have" was clipped inside its own box. Let the
  // label wrap and keep the 44 px target: narrow is a width, not a reason to truncate an action.
  const buttonStyle = {
    flex: '1 1 auto',
    borderRadius: '2px',
    minHeight: '44px',
    height: 'auto',
    whiteSpace: 'normal',
    textAlign: 'center',
    lineHeight: 1.3,
    fontSize: CB_TYPE.body
  }
  // One secondary at most: a real destination, never a disabled control. It is the same door
  // whether or not the plate has a primary, because "use a course I already have" does not depend
  // on this build being able to create one.
  const secondary = canBrowse
    ? jsx(sdk.Button, {
        'data-cb-first-run-secondary': '',
        variant: 'secondary',
        onClick: onBrowseLibrary,
        style: buttonStyle,
        children: FIRST_RUN_COPY.secondary
      })
    : null
  return jsxs('div', {
    'data-cb-first-run': '',
    'data-cb-first-run-state': !connected ? 'offline' : canCreate ? 'start' : 'unavailable',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: compact ? '0.8rem' : '1rem',
      width: '100%',
      maxWidth: '42rem',
      margin: '0 auto',
      padding: veryNarrow ? '0.7rem 0.45rem 0.8rem' : compact ? '0.9rem 0.7rem 1rem' : '1.4rem 1.5rem 1.5rem',
      background: 'var(--cb-lamp-soft)',
      border: '1px solid var(--cb-rule)',
      borderTop: '1px solid var(--cb-lamp)',
      boxSizing: 'border-box'
    },
    children: [
      jsx('div', {
        'data-cb-first-run-contour': '',
        'aria-hidden': 'true',
        style: {
          width: '100%',
          maxWidth: ghostHeight > 48 ? '240px' : '100%',
          height: `${ghostHeight}px`,
          alignSelf: ghostHeight > 48 ? 'flex-end' : 'stretch',
          opacity: 0.3,
          overflow: 'hidden'
        },
        children: jsx(CourseContour, { height: ghostHeight })
      }, 'ghost'),
      jsx('h2', {
        'data-cb-first-run-title': '',
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: headingSize,
          fontWeight: 600,
          lineHeight: 1.08,
          letterSpacing: '-0.015em',
          color: 'var(--cb-ink)',
          maxWidth: '22ch',
          overflowWrap: 'break-word'
        },
        children: FIRST_RUN_COPY.title
      }),
      jsx('p', {
        'data-cb-first-run-line': '',
        style: {
          margin: 0,
          maxWidth: '54ch',
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.body,
          lineHeight: 1.55,
          color: 'var(--cb-ink)'
        },
        children: line
      }),
      pet ? jsx(StudyCompanion, { info: pet, size: compact ? 36 : 44 }) : null,
      showAction || secondary
        ? jsxs('div', {
            'data-cb-first-run-actions': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'stretch', gap: '0.6rem' },
            children: [
              showAction
                ? jsx(CbAction, {
                    'data-cb-first-run-primary': '',
                    variant: 'primary',
                    onClick: action,
                    style: { whiteSpace: 'normal', textAlign: 'center', lineHeight: 1.3 },
                    children: actionLabel
                  })
                : null,
              secondary
            ]
          })
        : null
    ]
  })
}

function onImportPlaceholder() {
  requestIntent({ kind: 'import' })
}

