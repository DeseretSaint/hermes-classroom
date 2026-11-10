function CoursesView({ implemented, onStartCreate, onStartSyllabus, onBrowseLibrary, createOpen, onOpen, onShowDesk, onEmptyChange }) {
  const [filter, setFilter] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!pluginContext) return undefined
    const timer = pluginContext.setTimeout(() => setQuery(searchInput.trim()), 250)
    return timer
  }, [searchInput])

  const payload = { filter, limit: 50, sort: 'recent' }
  if (query) payload.query = query
  const key = JSON.stringify(payload)
  const { status, data, error, stale, reload } = useRpcQuery(
    'library.list',
    payload,
    key,
    !createOpen && backendSupports('library.list')
  )

  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleteScope, setDeleteScope] = useState(null)
  const [actionError, setActionError] = useState(null)

  const onResume = useCallback(async (row) => {
    const response = await loadBinding({ enrollmentId: row.enrollment_id })
    if (!response || !response.ok) {
      host.notify({
        kind: 'warning',
        message: response && response.error ? `${response.error.code}: ${describeError(response.error)}` : 'Could not read which chat belongs to this course.'
      })
      return
    }
    const outcome = await resumeBoundSession(response.result.binding)
    if (!outcome.ok) host.notify({ kind: 'warning', message: outcome.message })
  }, [])

  const onArchive = useCallback(
    async (row, action) => {
      const response = await rpc(
        'enrollment.update',
        { enrollment_id: row.enrollment_id, action },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setActionError(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      setActionError(null)
      reload()
    },
    [reload]
  )

  const onDelete = useCallback(async (row) => {
    // A preview is still a contract call: cb.rpc requires idempotency_key at the root. Without it
    // this dry run was refused (VALIDATION_FAILED: 'idempotency_key' is a required property) and
    // the confirm never opened — the destructive path was unreachable from the UI. The key is
    // derived from the row, so re-opening the same preview is the same operation.
    const response = await rpc(
      'enrollment.delete',
      { enrollment_id: row.enrollment_id, dry_run: true },
      {
        idempotencyKey: `cb-enrollment-delete-preview-${row.enrollment_id}`,
        expectedRevision: row.revision
      }
    )
    if (!response.ok) {
      host.notify({
        kind: 'warning',
        message: `${response.error.code}: ${describeError(response.error)}`
      })
      return
    }
    setPendingDelete(row)
    setDeleteScope(response.result.data_scope)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete || !deleteScope) return
    const response = await rpc(
      'enrollment.delete',
      {
        enrollment_id: pendingDelete.enrollment_id,
        dry_run: false,
        data_scope_hash: deleteScope.scope_hash
      },
      {
        idempotencyKey: `cb-delete-${pendingDelete.enrollment_id}-${deleteScope.scope_id}`,
        expectedRevision: pendingDelete.revision
      }
    )
    if (!response.ok) {
      throw new Error(`${response.error.code}: ${describeError(response.error)}`)
    }
    setPendingDelete(null)
    setDeleteScope(null)
    reload()
  }, [pendingDelete, deleteScope, reload])

  const allRows = data && Array.isArray(data.items) ? data.items : []
  // H-99: one shelf object per distinct course. The review block and the row list both read the
  // grouped view, so a course cannot appear twice in either place.
  const groups = groupShelfRows(allRows)
  const rows = groups.map((group) => group.primary)
  const groupReviewDue = (group) =>
    group.members.reduce((sum, member) => sum + Number((member.evidence_summary || {}).review_due || 0), 0)
  const noCourses = data && Number(data.total || 0) === 0
  // A search is a filter too: with rows present on the profile, an empty result set caused by the
  // search box must never be presented as first-run. `applied_filter` alone missed that case.
  const filteredEmpty =
    noCourses && (Boolean(query) || Boolean(data.applied_filter && data.applied_filter !== 'all'))

  // The filter chips and search box are chrome for a list that exists; the welcome replaces them
  // on first run. This is also what the route header reads to drop its duplicate New course button.
  const emptyFirstRun = Boolean(data) && noCourses && !filteredEmpty
  useEffect(() => {
    if (onEmptyChange) onEmptyChange(emptyFirstRun)
  }, [emptyFirstRun, onEmptyChange])
  const showTools = courseToolsVisible(data)

  let body
  if (status === 'idle') {
    // The backend cannot serve `library.list` at all: the same start plate, with its honest
    // "cannot create or add" line, instead of a blank route (H-153, UX_SPEC §13 unsupported backend).
    body = jsx(FirstRun, {
      implemented,
      onCreate: onStartCreate,
      onSyllabus: onStartSyllabus,
      onBrowseLibrary,
      onRetry: reload
    })
  } else if (status === 'loading' && !data) {
    body = jsxs('div', {
      className: 'flex flex-col items-center gap-3 py-10',
      children: [
        jsx(sdk.Loader, { label: 'Reading your courses' }),
        jsx('p', {
          style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
          children: 'Reading your courses.'
        })
      ]
    })
  } else if (status === 'error' && !data) {
    body = jsx('div', {
      className: 'mx-auto w-full max-w-xl py-6',
      children: jsxs(sdk.ErrorState, {
        title: 'Your courses could not be read',
        description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} This page will not show an empty list in place of a failed read.`,
        children: jsxs('div', {
          className: 'flex flex-wrap items-center justify-center gap-2',
          children: [
            jsx(CbAction, { variant: 'primary', onClick: reload, children: 'Try again' }),
            jsx(CbAction, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
          ]
        })
      })
    })
  } else if (noCourses) {
    body = filteredEmpty
      ? jsx('div', {
          className: 'py-6',
          children: jsxs('div', {
            className: 'mx-auto flex w-full max-w-xl flex-col items-center gap-3',
            children: [
              jsx(EmptyState, {
                title: query ? 'No courses match your search' : 'No courses match this filter',
                description: query
                  ? 'Your courses are still here; the search just excludes them right now.'
                  : 'Your courses are still here; this filter just excludes them right now.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => {
                  setFilter('all')
                  setSearchInput('')
                },
                children: query ? 'Clear search' : 'Clear filter'
              })
            ]
          })
        })
      : jsx(FirstRun, {
          implemented,
          onCreate: onStartCreate,
          onSyllabus: onStartSyllabus,
          onBrowseLibrary,
          onRetry: reload
        })
  } else {
    body = jsxs('div', {
      className: 'flex flex-col',
      children: [
        stale
          ? jsxs('div', {
              className: 'mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) pb-2',
              children: [
                jsx('div', {
                  className: 'text-xs text-(--ui-text-secondary)',
                  children: 'Reconnecting. Showing the last courses that were read; changes are paused.'
                }),
                jsx(CbAction, { variant: 'tertiary', onClick: reload, children: 'Retry now' })
              ]
            })
          : null,
        actionError ? jsx(ErrorLine, { error: { message: actionError } }) : null,
        groups.some((group) => groupReviewDue(group) > 0)
          ? jsxs('div', {
              className: 'mb-2 flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) pb-2',
              children: [
                jsx(CbLabel, { children: 'Review due' }),
                groups
                  .filter((group) => groupReviewDue(group) > 0)
                  .map((group) =>
                    jsxs(
                      'div',
                      {
                        className: 'flex flex-wrap items-center justify-between gap-2 text-xs',
                        children: [
                          jsx('span', {
                            className: 'min-w-0 break-words text-(--ui-text-secondary)',
                            children: `${group.primary.title} · ${groupReviewDue(group)} due`
                          }),
                          jsx(CbAction, {
                            variant: 'tertiary',
                            onClick: () => onOpen(group.primary),
                            children: 'Review'
                          })
                        ]
                      },
                      `review-${group.key}`
                    )
                  )
              ]
            })
          : null,
        groups.map((group) =>
          jsx(
            CourseRow,
            {
              row: group.primary,
              group,
              implemented,
              onResume,
              onArchive,
              onDelete,
              onOpen,
              // H-201: the disclosure under this cover lists the other enrollments of a shared
              // pack. Hand it the shelf's own open path so a member row is reachable, and the
              // Library destination as the working next action if a row cannot be opened here.
              onOpenMember: onOpen,
              onOpenLibrary: onBrowseLibrary
            },
            group.key
          )
        ),
        data.next_cursor
          ? jsx('div', {
              className: 'pt-3 text-xs text-(--ui-text-secondary)',
              children: `${groups.length} courses shown. Narrow the filter to see the rest.`
            })
          : null
      ]
    })
  }

  const toolsDisabled = createOpen
  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      onShowDesk
        ? jsx(CbAction, {
            className: 'mb-2 self-start',
            variant: 'tertiary',
            onClick: onShowDesk,
            children: 'Back to the Field Desk'
          })
        : null,
      jsx(PlateHead, {
        title: 'All courses',
        caption: data
          ? `${Number(data.total || 0)} ${Number(data.total || 0) === 1 ? 'course' : 'courses'} on this profile`
          : 'Reading the courses on this profile'
      }),
      jsxs('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: [
          showTools
            ? jsx(sdk.SearchField, {
                'aria-label': 'Search courses',
                containerClassName: 'max-w-sm min-w-0 flex-1',
                onChange: setSearchInput,
                placeholder: 'Search courses',
                value: searchInput
              })
            : null,
          showTools
            ? jsx(sdk.SegmentedControl, {
                onChange: setFilter,
                options: FILTERS,
                sizing: 'content',
                value: filter,
                disabled: toolsDisabled
              })
            : null
        ]
      }),
      body,
      jsx(FocusReturningDialog, {
        confirmLabel: 'Delete enrollment',
        description: pendingDelete
          ? `This deletes the learning data for “${pendingDelete.title}” on this profile. The course content and the pack it came from are kept.`
          : '',
        destructive: true,
        onClose: () => {
          setPendingDelete(null)
          setDeleteScope(null)
        },
        onConfirm: confirmDelete,
        open: Boolean(pendingDelete),
        title: 'Delete this enrollment?',
        children: deleteScope
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Attempts', value: String((deleteScope.counts || {}).attempts || 0) }),
                jsx(StatusRow, { label: 'Notebook entries', value: String((deleteScope.counts || {}).notebook_entries || 0) }),
                jsx(StatusRow, { label: 'Lesson runs', value: String((deleteScope.counts || {}).lesson_runs || 0) }),
                jsx(StatusRow, { label: 'Background tasks', value: String((deleteScope.counts || {}).jobs || 0) }),
                jsx(StatusRow, { label: 'Course and plan kept', value: (deleteScope.preserved || {}).course ? 'yes' : 'no' }),
                jsx(StatusRow, { label: 'Hermes transcripts kept', value: (deleteScope.preserved || {}).hermes_transcripts ? 'yes' : 'no' })
              ]
            })
          : null
      })
    ]
  })
}

function sourceLabel(source) {
  if (source === 'bundled') return 'Bundled'
  if (source === 'community') return 'Community'
  if (source === 'local') return 'Local pack'
  if (source === 'authored') return 'Authored here'
  return source || 'Unknown source'
}

/** `enrollment_status` is a contract enum; a learner reads a sentence, not the raw value (H-28). */
const ENROLLMENT_STATUS_COPY = {
  active: 'Active',
  archived: 'Archived',
  completed: 'Completed'
}

function enrollmentStatusLabel(value) {
  return ENROLLMENT_STATUS_COPY[value] || value || 'Unknown'
}

/**
 * Maintenance actions for one pack. They sit under overflow so the preview keeps one primary
 * (Open/Resume) and one secondary; nothing destructive competes with the learner's next step.
 */
function PackMenu({ row, supports, onExportPack, onDelete, onDeletePack }) {
  const items = []
  const packBacked = Boolean(row.provenance && row.provenance.pack_id)
  if (packBacked && supports('pack.export')) {
    items.push(
      jsx(sdk.DropdownMenuItem, { onSelect: () => onExportPack(row), children: 'Export pack…' }, 'export')
    )
  }
  if (supports('enrollment.delete')) {
    items.push(
      jsx(
        sdk.DropdownMenuItem,
        { onSelect: () => onDelete(row), variant: 'destructive', children: 'Delete enrollment…' },
        'delete-enrollment'
      )
    )
  }
  if (packBacked && supports('pack.delete') && row.warning !== 'pack_frozen') {
    items.push(
      jsx(
        sdk.DropdownMenuItem,
        { onSelect: () => onDeletePack(row), variant: 'destructive', children: 'Remove pack…' },
        'delete-pack'
      )
    )
  }
  if (items.length === 0) return null
  return jsxs(sdk.DropdownMenu, {
    children: [
      jsx(sdk.DropdownMenuTrigger, {
        asChild: true,
        children: jsx(sdk.Button, {
          'aria-label': `More actions for ${row.title || 'this pack'}`,
          size: 'icon-sm',
          variant: 'ghost',
          children: jsx(sdk.Codicon, { name: 'kebab-vertical', size: CB_ICON_UI })
        })
      }),
      jsx(sdk.DropdownMenuContent, { align: 'end', children: items })
    ]
  })
}

/**
 * H-150 — a pack preview, not an inspector. It answers what this pack is and what to do next:
 * one primary, one secondary, maintenance under overflow. Pack identifiers and record revisions
 * are real but they are not learner facts, so they live under a closed Technical details
 * disclosure instead of in the header and the status lines.
 */
function PackFacts({ row, implemented, onOpen, onResume, onArchive, onDelete, onExportPack, onDeletePack, onBack, showBack }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const warning = WARNING_COPY[row.warning]
  const summary = row.evidence_summary || {}
  const total = Math.max(0, Number(summary.total_objectives || 0))
  const independent = Math.max(0, Number(summary.independent || 0))
  const due = Math.max(0, Number(summary.review_due || 0))
  const canResume = next.kind === 'resume_lesson' && supports('binding.get')
  const provenance = row.provenance || {}
  const technical = [
    provenance.pack_id ? { label: 'Pack ID', value: provenance.pack_id } : null,
    provenance.pack_version ? { label: 'Pack version', value: `v${provenance.pack_version}` } : null,
    { label: 'Record version', value: String(row.revision == null ? 0 : row.revision) }
  ].filter(Boolean)
  return jsxs('div', {
    className: 'flex min-w-0 flex-1 flex-col gap-3',
    'data-cb-pack-preview': '',
    children: [
      showBack
        ? jsx(sdk.Button, {
            'data-cb-pack-back': '',
            className: 'self-start',
            onClick: onBack,
            size: 'sm',
            variant: 'text',
            children: 'All packs'
          })
        : null,
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('h2', { className: 'text-sm font-semibold', children: row.title || 'Untitled pack' }),
          jsxs('div', {
            className: 'mt-1 flex flex-wrap items-center gap-2',
            children: [
              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: sourceLabel(provenance.source) }),
              warning ? jsx(WarningBadge, { warning: row.warning }) : null
            ]
          })
        ]
      }),
      jsx(CbLabel, { children: 'What this pack shows' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(StatusRow, { label: 'Next step', value: learnerNextLabel(next.label) || '—' }),
          jsx(StatusRow, { label: 'Enrolment', value: enrollmentStatusLabel(row.enrollment_status) }),
          jsx(StatusRow, {
            label: 'Evidence',
            value: total === 0 ? 'None recorded' : `${independent} of ${plural(total, 'section', 'sections')}`,
            detail: total === 0 ? 'This pack has no lesson sections.' : `${plural(due, 'review', 'reviews')} due`
          }),
          jsx(StatusRow, { label: 'Last change', value: formatWhen(row.updated_at) })
        ]
      }),
      warning
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: warning.detail })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 pt-1',
        children: [
          canResume && onResume
            ? jsx(CbAction, { onClick: () => onResume(row), variant: 'primary', children: 'Resume lesson' })
            : onOpen
              ? jsx(CbAction, { onClick: () => onOpen(row), variant: 'primary', children: 'Open course' })
              : null,
          supports('enrollment.update')
            ? jsx(CbAction, {
                onClick: () => onArchive(row, row.enrollment_status === 'archived' ? 'unarchive' : 'archive'),
                variant: 'secondary',
                children: row.enrollment_status === 'archived' ? 'Unarchive' : 'Archive'
              })
            : null,
          jsx(PackMenu, { row, supports, onExportPack, onDelete, onDeletePack })
        ]
      }),
      row.recipe === 'parent'
        ? jsx('div', {
            className: 'border-l border-(--ui-stroke-secondary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
            children:
              'Parent Studio blueprint: the adult prepares and teaches from this plan. Checks are observations, ' +
              'not graded child answers, and this course is never offered as an adult graded course.'
          })
        : null,
      jsxs('details', {
        'data-cb-pack-technical': '',
        className: 'mt-1',
        children: [
          jsx('summary', {
            className: 'flex cursor-pointer items-center gap-1 text-xs font-medium',
            style: { listStyle: 'none', minHeight: '1.75rem', color: 'var(--ui-text-secondary)' },
            children: [
              jsx(sdk.Codicon, { name: 'chevron-right', size: CB_ICON_UI }),
              jsx('span', { children: 'Technical details' })
            ]
          }),
          jsxs('div', {
            className: 'flex flex-col',
            children: technical.map((item) => jsx(StatusRow, { label: item.label, value: item.value }, item.label))
          })
        ]
      })
    ]
  })
}

function formatWhen(value) {
  if (!value) return 'not recorded'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString()
}

/**
 * How a pack is explained before anything is added (UX-06).
 *
 * The absence of a marketplace and of a verified badge is true but it is not a welcome. It lives in
 * an opened disclosure, under what is checked and what is not, so the trust labels keep their
 * meaning and nobody reads a pack as endorsed.
 */
const LIBRARY_COPY = {
  lead: 'Every pack installed on this profile: the ones that ship with Coursebook and the ones added here from someone else. Preview a pack to see who made it, where it came from and what has been checked.',
  whatWeCheck:
    'What we check — that every file matches the hashes in the pack’s manifest, that its structure and teaching minima pass the automated checks, and whether a named reviewer and a model assessment are recorded. Those are separate labels on every pack and they are never merged into a score.',
  whatWeDoNotCheck:
    'What we do not check — whether the teaching is good for you, whether the author is trustworthy, and how this pack compares with any other. There is no marketplace ranking and no verified badge.',
  emptyTitle: 'No packs on this profile yet',
  emptyBody:
    'A pack is a zip file someone else made: lessons, sources and a manifest that lists every file. Bundled packs ship with Coursebook; a pack from someone else is added from the Import flow, where you review it first.'
}

/**
 * H-150c — the route column below which the shelf shows one pane at a time.
 *
 * Measured route columns on the isolated rig: 958 px in a 1600 px window, 407 px in a 1049 px one,
 * 257 px at 900 and 215 px at 460. A pack row needs roughly 18rem to show its title, its next step
 * and its one Preview affordance, so below ~25rem the preview and the list cannot both be read;
 * once a pack is opened there, the preview replaces the list. This is a route width, not a window
 * width: the host keeps the chat workspace beside the route, so a window breakpoint picks the
 * wrong pane (a 900 px window leaves Coursebook 257 px).
 */
const CB_SHELF_COMPACT_WIDTH = 400

/**
 * H-150c — the shelf's two panes, and who holds focus after a pack is opened.
 *
 * The panes are stacked, not beside each other. The deck emits `.min-[47.5rem]:flex-row`,
 * `:w-52` and `:gap-5` — but not the `.min-[47.5rem]:flex` or `:w-72` the shelf asked for, so the
 * list's `hidden min-[47.5rem]:flex` never un-hid and its 18rem width never applied: the intended
 * two-column split was never drawn, and at 460 px the `hidden` class took the list — and the
 * focused row button with it — out of layout, which is why `document.activeElement` fell to `body`.
 *
 * `compact` is the one rule that both hides the list when a pack is open and picks the focus
 * target, so the pane the user can still see is the pane that keeps focus. `focus` is the caller's
 * request object, not a scalar: opening the same pack twice must move focus twice, and equal
 * scalars would leave the effect asleep on the second press.
 */
function PackShelfSplit({ compact, detailOpen, focus, list, detail }) {
  const rootRef = useRef(null)
  useEffect(() => {
    if (!focus || !rootRef.current) return
    const root = rootRef.current
    const node =
      focus.target === 'detail'
        ? root.querySelector('[data-cb-pack-preview] button')
        : Array.from(root.querySelectorAll('[data-cb-pack-row-action]')).find(
            (candidate) => candidate.getAttribute('data-cb-pack-row-action') === String(focus.key || '')
          )
    if (!node || typeof node.focus !== 'function') return
    const moved = typeof document !== 'undefined' && document.activeElement !== node
    node.focus()
    // This Electron build moves `activeElement` for a script focus without firing `focusin`
    // (measured in H-146b), so React's `onFocus` never runs and a retained row would keep its
    // ring off. Announce the focus we just made, once, and only when we actually moved it.
    if (moved && typeof FocusEvent === 'function') node.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
  }, [focus])
  return jsxs('div', {
    ref: rootRef,
    'data-cb-pack-split': compact ? 'one-pane' : 'stacked',
    'data-cb-pack-detail-open': detailOpen ? 'true' : 'false',
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
    children: [
      jsx('div', {
        'data-cb-pack-list-pane': '',
        style: {
          display: detailOpen && compact ? 'none' : 'flex',
          flexDirection: 'column',
          minWidth: 0
        },
        children: list
      }),
      detail
    ]
  })
}

/**
 * H-150c — where focus belongs once a pack is opened.
 *
 * In the stacked shelf the row the user pressed is still on screen, so focus stays on it. In the
 * compact shelf the list is gone, so focus goes to the preview's own `All packs` back control —
 * the visible way out. One function keeps the two keys, the layout and the focus target aligned.
 */
function shelfFocusTarget(compact, detailOpen) {
  return detailOpen && compact ? 'detail' : 'list'
}

function LibraryView({ implemented, createOpen, onOpen, onStartSyllabus, onStartImport }) {
  const [view, setView] = useState('all')
  const [selected, setSelected] = useState(null)
  const [packPanel, setPackPanel] = useState(null)
  const [packPanelRow, setPackPanelRow] = useState(null)
  // H-150c: where focus goes after a pack is opened, decided from the route column the shelf is
  // actually drawn in — not from the window width.
  const [focusIntent, setFocusIntent] = useState(null)
  const routeWidth = useCbViewportWidth()
  // An unmeasured route (first paint, SSR) is treated as the stacked shelf: the list is visible,
  // so the row is the honest focus target.
  const compactShelf = Number.isFinite(routeWidth) && routeWidth > 0 && routeWidth < CB_SHELF_COMPACT_WIDTH

  const openPack = useCallback(
    (row) => {
      setSelected(row.enrollment_id)
      setFocusIntent({ target: shelfFocusTarget(compactShelf, true), key: row.enrollment_id })
    },
    [compactShelf]
  )

  const closePack = useCallback(
    (row) => {
      setSelected(null)
      if (row) setFocusIntent({ target: 'list', key: row.enrollment_id })
    },
    []
  )

  const payload = { filter: 'all', limit: 50, sort: 'title' }
  const key = JSON.stringify(payload)
  const { status, data, error, stale, reload } = useRpcQuery(
    'library.list',
    payload,
    key,
    !createOpen && backendSupports('library.list')
  )

  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleteScope, setDeleteScope] = useState(null)

  const onResume = useCallback(async (row) => {
    const response = await loadBinding({ enrollmentId: row.enrollment_id })
    if (!response || !response.ok) {
      host.notify({ kind: 'warning', message: 'Could not read which chat belongs to this lesson.' })
      return
    }
    const outcome = await resumeBoundSession(response.result.binding)
    if (!outcome.ok) host.notify({ kind: 'warning', message: outcome.message })
  }, [])

  const onArchive = useCallback(
    async (row, action) => {
      const response = await rpc(
        'enrollment.update',
        { enrollment_id: row.enrollment_id, action },
        { expectedRevision: row.revision }
      )
      if (!response.ok) host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
      reload()
    },
    [reload]
  )

  const onDelete = useCallback(async (row) => {
    // A preview is still a contract call: cb.rpc requires idempotency_key at the root. Without it
    // this dry run was refused (VALIDATION_FAILED: 'idempotency_key' is a required property) and
    // the confirm never opened — the destructive path was unreachable from the UI. The key is
    // derived from the row, so re-opening the same preview is the same operation.
    const response = await rpc(
      'enrollment.delete',
      { enrollment_id: row.enrollment_id, dry_run: true },
      {
        idempotencyKey: `cb-enrollment-delete-preview-${row.enrollment_id}`,
        expectedRevision: row.revision
      }
    )
    if (!response.ok) {
      host.notify({ kind: 'warning', message: `${response.error.code}: ${describeError(response.error)}` })
      return
    }
    setPendingDelete(row)
    setDeleteScope(response.result.data_scope)
  }, [])

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete || !deleteScope) return
    const response = await rpc(
      'enrollment.delete',
      {
        enrollment_id: pendingDelete.enrollment_id,
        dry_run: false,
        data_scope_hash: deleteScope.scope_hash
      },
      {
        idempotencyKey: `cb-delete-${pendingDelete.enrollment_id}-${deleteScope.scope_id}`,
        expectedRevision: pendingDelete.revision
      }
    )
    if (!response.ok) throw new Error(`${response.error.code}: ${describeError(response.error)}`)
    setPendingDelete(null)
    setDeleteScope(null)
    setSelected(null)
    reload()
  }, [pendingDelete, deleteScope, reload])

  const allRows = data && Array.isArray(data.items) ? data.items : []
  // H-150: the labels must describe the rows they return. Bundled means the packs that ship with
  // Coursebook; "From someone else" is every imported pack (community or added from a file), and
  // never an authored course. There is no "Local" bucket that quietly includes community packs.
  const filteredRows = allRows.filter((row) => {
    const source = (row.provenance && row.provenance.source) || 'authored'
    if (view === 'bundled') return source === 'bundled'
    if (view === 'other') return source === 'community' || source === 'local'
    return true
  })
  // H-99: one shelf object per course/pack. Fourteen enrollments of the same pack are one row
  // with an `N enrollments` disclosure, not fourteen identical text cards.
  const groups = groupShelfRows(filteredRows)
  const rows = filteredRows

  const detailRow = selected ? allRows.find((row) => row.enrollment_id === selected) || null : null

  let listBody
  if (status === 'loading' && !data) {
    listBody = jsx('div', { className: 'py-8', children: jsx(sdk.Loader, { label: 'Reading installed packs' }) })
  } else if (status === 'error' && !data) {
    listBody = jsxs('div', {
      className: 'flex flex-col gap-3 py-4',
      children: [
        jsx(EmptyState, {
          title: 'Installed packs could not be read',
          description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`
        }),
        jsx(CbAction, { className: 'self-start', onClick: reload, variant: 'tertiary', children: 'Try again' })
      ]
    })
  } else if (rows.length === 0) {
    listBody = jsx('div', {
      className: 'flex flex-col gap-3',
      children: jsx(EmptyState, {
        title:
          view === 'bundled'
            ? 'No bundled pack on this profile'
            : view === 'other'
              ? 'No pack from someone else on this profile'
              : LIBRARY_COPY.emptyTitle,
        description: LIBRARY_COPY.emptyBody
      })
    })
  } else {
    listBody = jsxs('div', {
      className: 'flex flex-col',
      children: [
        stale
          ? jsx('div', {
              className: 'mb-2 text-xs text-(--ui-text-secondary)',
              children: 'Reconnecting. Showing the last packs that were read.'
            })
          : null,
        groups.map((group) => {
          const row = group.primary
          return jsx(
            PackShelfRow,
            {
              row,
              group,
              selected: row.enrollment_id === selected,
              onOpenMember: (member) => openPack(member),
              onPreview: (member) => openPack(member)
            },
            group.key
          )
        })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex flex-col',
    style: { maxWidth: CB_MEASURE },
    children: [
      // H-150: the route shell already prints the page h1 "Library". This plate names the shelf
      // region once and carries the single lead; it must not repeat the destination name.
      jsx(PlateHead, {
        title: 'Packs on this profile',
        caption: jsx('span', { children: LIBRARY_COPY.lead })
      }),
      stale
        ? jsx('div', {
            className: 'mb-2 text-xs text-(--ui-text-secondary)',
            children: 'Reconnecting. Showing the last packs that were read.'
          })
        : null,
      // H-99: the two import paths live in the route header — one primary `Import pack` and one
      // secondary `Use my college syllabus`. They are no longer repeated here under a second set
      // of labels; one surface, one primary per object (see the H-94 rule).
      jsx('div', {
        className: 'mb-2 flex flex-wrap items-center justify-between gap-2',
        children: jsx(sdk.SegmentedControl, {
          onChange: (next) => {
            setView(next)
            setSelected(null)
          },
          options: [
            { id: 'all', label: 'All packs' },
            { id: 'bundled', label: 'Bundled' },
            { id: 'other', label: 'From someone else' }
          ],
          sizing: 'content',
          value: view
        })
      }),
      jsx(PackShelfSplit, {
        detailOpen: Boolean(detailRow),
        detail: detailRow
          ? jsx(PackFacts, {
              implemented,
              onArchive,
              onBack: () => closePack(detailRow),
              onDelete,
              onOpen,
              onDeletePack: (row) => {
                setPackPanelRow(row)
                setPackPanel('delete')
              },
              onExportPack: (row) => {
                setPackPanelRow(row)
                setPackPanel('export')
              },
              onResume,
              row: detailRow,
              showBack: true
            })
          : jsx('div', {
              'data-cb-pack-placeholder': '',
              style: { display: compactShelf ? 'none' : 'flex', minWidth: 0, flex: 1, alignItems: 'flex-start' },
              children: jsx(EmptyState, {
                className: 'w-full',
                title: 'Choose a pack to see what we know about it',
                description: 'Preview shows who made the pack, where it came from, the progress you have and what has been checked — nothing inferred.'
              })
            }),
        compact: compactShelf,
        focus: focusIntent,
        list: listBody
      }),
      // H-150: trust is read after the shelf, not before it. The learner browses packs first;
      // what is and is not checked sits below the list as one closed disclosure.
      jsxs('details', {
        'data-cb-pack-trust': '',
        className: 'mt-4 max-w-prose leading-relaxed text-(--ui-text-secondary)',
        style: { maxWidth: CB_MEASURE, fontSize: CB_TYPE.body },
        children: [
          jsx('summary', {
            'data-cb-affordance': 'disclosure',
            className: 'flex cursor-pointer items-center gap-1 text-xs font-medium',
            style: { listStyle: 'none', minHeight: '1.75rem' },
            children: [
              jsx(sdk.Codicon, { name: 'chevron-right', size: CB_ICON_UI }),
              jsx('span', { children: 'What we check / what we do not check' })
            ]
          }),
          jsx('p', { className: 'mt-1', style: { fontSize: CB_TYPE.body, lineHeight: 1.55 }, children: LIBRARY_COPY.whatWeCheck }),
          jsx('p', { className: 'mt-1', style: { fontSize: CB_TYPE.body, lineHeight: 1.55 }, children: LIBRARY_COPY.whatWeDoNotCheck })
        ]
      }),
      packPanel && packPanelRow
        ? jsxs('div', {
            className: 'mt-4 flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-3',
            children: [
              packPanel === 'export'
                ? jsx(PackExportPanel, { onClose: () => setPackPanel(null), row: packPanelRow })
                : jsx(PackDeletePanel, {
                    onClose: () => setPackPanel(null),
                    onDeleted: () => {
                      setPackPanel(null)
                      setSelected(null)
                      reload()
                    },
                    row: packPanelRow
                  })
            ]
          })
        : null,
      jsx(FocusReturningDialog, {
        confirmLabel: 'Delete enrollment',
        description: pendingDelete
          ? `This deletes the learning data for “${pendingDelete.title}” on this profile. The pack content itself is kept.`
          : '',
        destructive: true,
        onClose: () => {
          setPendingDelete(null)
          setDeleteScope(null)
        },
        onConfirm: confirmDelete,
        open: Boolean(pendingDelete),
        title: 'Delete this enrollment?',
        children: deleteScope
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Attempts', value: String((deleteScope.counts || {}).attempts || 0) }),
                jsx(StatusRow, { label: 'Notebook entries', value: String((deleteScope.counts || {}).notebook_entries || 0) }),
                jsx(StatusRow, { label: 'Lesson runs', value: String((deleteScope.counts || {}).lesson_runs || 0) }),
                jsx(StatusRow, { label: 'Pack provenance kept', value: (deleteScope.preserved || {}).pack_provenance ? 'yes' : 'no' })
              ]
            })
          : null
      })
    ]
  })
}

