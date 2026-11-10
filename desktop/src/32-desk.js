/** The pure desk view. The container below owns the reads; this owns the geometry. */
function FieldDeskHome({
  desk,
  notes,
  onShowNotebook,
  libraryStatus,
  libraryError,
  libraryEmptyReason,
  stale,
  busy,
  notice,
  online,
  onRetry,
  onCreate,
  onSyllabus,
  onPrimary,
  onOpenSection,
  onRetryEstimate,
  onSelectCourse,
  onOpenStudio,
  world,
  engagement,
  prefs,
  onSetMode,
  onWorldChanged,
  onOpen,
  onShowAll,
  sourcesOpen,
  onToggleSources,
  sourcesStatus,
  sourcesError,
  sources,
  onRetrySources,
  outlineStatus,
  outlineError,
  onRetryOutline,
  implemented,
  onBrowseLibrary,
  onEmptyChange,
  companionEnabled,
  onSeePlan
}) {
  const width = useCbViewportWidth()
  const wide = cbLayoutFor(width) === 'wide'
  // The welcome is on screen only when the desk really has no course: a load in flight or a failed
  // read is not an empty profile. The route header reads this so its own "New course" button does
  // not duplicate the welcome's primary action (UX-01).
  const emptyFirstRun = !desk.row && libraryStatus !== 'loading' && libraryStatus !== 'error'
  useEffect(() => {
    if (onEmptyChange) onEmptyChange(emptyFirstRun)
  }, [emptyFirstRun, onEmptyChange])

  // GM-004: the mode control and the World Studio belong to this classroom, so a different
  // classroom never inherits the previous one's open studio, dialog or notice.
  const [studioOpen, setStudioOpen] = useState(false)
  const [modeDialogOpen, setModeDialogOpen] = useState(false)
  const [modePending, setModePending] = useState(false)
  const [modeNotice, setModeNotice] = useState(null)
  const studioAutoStart = useRef(false)
  const courseKey = desk.row ? desk.row.course_id : 'none'
  useEffect(() => {
    setStudioOpen(false)
    setModeDialogOpen(false)
    setModeNotice(null)
  }, [courseKey])

  const worldData = world && world.status === 'ready' ? world.data : null
  const courseMode = worldData ? readCoursePresentationMode(worldData.presentation_mode) : null
  const courseWorld = worldData ? worldData.world : null
  const sectionPlates = cbWorldSectionPlates(courseWorld)
  const worldApproved = cbWorldApproved(courseWorld)
  const worldProviderUnavailable = Boolean(
    courseWorld &&
      (courseWorld.state === 'unavailable' ||
        (courseWorld.error && courseWorld.error.reason === 'provider_unavailable'))
  )
  const applyMode = async (next) => {
    setModePending(true)
    setModeNotice(null)
    const response = onSetMode ? await onSetMode(next) : null
    setModePending(false)
    if (!response || !response.ok) {
      setModeNotice(
        `The course mode could not change: ${describeError(response && response.error)} Your lessons and evidence are unchanged.`
      )
      return
    }
    setModeDialogOpen(false)
    setModeNotice(
      next === 'game'
        ? 'This course is now in Game mode.'
        : 'World hidden. This course reads as Textbook; its art is kept and can be shown again.'
    )
  }
  const changeMode = async () => {
    if (!courseMode) return
    if (courseMode === 'game') {
      await applyMode('textbook')
      return
    }
    setModeDialogOpen(true)
  }

  if (libraryStatus === 'loading' && !desk.row) {
    // The plate keeps its geometry while the read is in flight: one restrained line, no shimmer.
    return jsx('div', {
      'data-cb-desk': 'loading',
      children: jsx(TrailheadStatePlate, {
        state: 'loading',
        children: jsxs('div', {
          className: 'flex flex-col items-center gap-3 py-8',
          children: [
            jsx(sdk.Loader, { label: 'Reading the trail' }),
            jsx('p', {
              'data-cb-trailhead-loading-line': '',
              style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
              children: 'Reading the trail… nothing already saved is lost.'
            })
          ]
        })
      })
    })
  }
  if (libraryStatus === 'idle' && !desk.row) {
    // The backend cannot serve `library.list` at all: the start plate says what it can do instead
    // of the route going blank (UX_SPEC §13 unsupported backend, H-153).
    return jsx('div', {
      'data-cb-desk': 'unavailable',
      children: jsx(FirstRun, { implemented, onCreate, onSyllabus, onBrowseLibrary, onRetry, companionEnabled })
    })
  }
  if (libraryStatus === 'error' && !desk.row) {
    return jsx('div', {
      'data-cb-desk': 'error',
      children: jsx(TrailheadStatePlate, {
        state: 'error',
        children: jsxs(sdk.ErrorState, {
          title: 'The trailhead could not read your courses',
          description: `${libraryError && libraryError.code ? libraryError.code + ': ' : ''}${describeError(libraryError)} This desk will not show an empty course in place of a failed read.`,
          children: jsx(CbAction, { variant: 'primary', onClick: onRetry, children: 'Try again' })
        })
      })
    })
  }
  if (!desk.row) {
    // H-146: a profile can have rows and still no learner classroom. Parent-authored plans are a
    // different destination, and an all-archived profile has an answer of its own; neither is
    // "first run", and neither may silently borrow the first-run plate.
    if (desk.hub.rowTotal > 0) {
      return jsx('div', {
        'data-cb-desk': 'parent-only',
        children: jsx(TrailheadStatePlate, {
          state: 'parent-only',
          children: jsxs(EmptyState, {
            title: 'Parent Studio holds your lesson plans.',
            description:
              'This profile has parent-led lesson plans, not a learner classroom. Continue belongs to a learner classroom.',
            children: jsx(CbAction, {
              variant: 'primary',
              onClick: onOpenStudio,
              children: 'Open Parent Studio'
            })
          })
        })
      })
    }
    if (libraryEmptyReason === 'all_archived') {
      return jsx('div', {
        'data-cb-desk': 'archived',
        children: jsx(TrailheadStatePlate, {
          state: 'archived',
          children: jsxs(EmptyState, {
            title: 'Every classroom here is archived.',
            description: 'Archived courses keep their evidence. Unarchive one in Courses to continue it.',
            children: jsx(CbAction, { variant: 'primary', onClick: onShowAll, children: 'Open courses' })
          })
        })
      })
    }
    return jsx('div', {
      'data-cb-desk': libraryStatus === 'idle' ? 'unavailable' : 'empty',
      children: jsx(FirstRun, {
        implemented,
        onCreate,
        onSyllabus,
        onBrowseLibrary,
        onRetry,
        companionEnabled
      })
    })
  }

  // GM-004: one mode control and, for an approved Game world, the course-home world surface.
  // A Textbook course has no world surface at all; it never renders `[data-cb-world]`.
  const modeRow = worldData
    ? jsxs('div', {
        'data-cb-mode-row': courseMode || '',
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', minWidth: 0 },
        children: [
          jsx(ModeBadge, { mode: courseMode, pending: modePending }),
          jsx(CbAction, {
            variant: 'tertiary',
            'data-cb-mode-change': '',
            pending: modePending,
            onClick: changeMode,
            children: courseMode === 'game' ? 'Hide the world' : 'Change mode'
          }),
          modeNotice
            ? jsx('span', {
                'data-cb-mode-notice': '',
                role: 'status',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', lineHeight: 1.5 },
                children: modeNotice
              })
            : null
        ]
      })
    : null
  const worldSurface =
    worldData && courseMode === 'game'
      ? jsx(CourseWorldHero, {
          world: courseWorld,
          mode: courseMode,
          sectionPlates,
          narrow: !wide,
          onOpenStudio: () => setStudioOpen(true),
          onOpenSection: (sectionId) => onOpenSection(sectionId)
        })
      : null
  const studio = studioOpen && desk.row
    ? jsx(WorldStudio, {
        courseId: desk.row.course_id,
        mode: courseMode,
        world: courseWorld,
        worldStatus: world ? world.status : 'idle',
        worldError: world ? world.error : null,
        autoStart: studioAutoStart.current,
        onReload: world ? world.reload : () => {},
        onChanged: onWorldChanged,
        onClose: () => {
          studioAutoStart.current = false
          setStudioOpen(false)
        }
      })
    : null
  const modeDialog = modeDialogOpen && desk.row
    ? jsx(ModeSwitchDialog, {
        mode: courseMode,
        world: courseWorld,
        pending: modePending,
        providerUnavailable: worldProviderUnavailable,
        onGenerate: () => {
          setModeDialogOpen(false)
          studioAutoStart.current = true
          setStudioOpen(true)
        },
        onOpenStudio: () => {
          setModeDialogOpen(false)
          studioAutoStart.current = false
          setStudioOpen(true)
        },
        onSwitch: () => applyMode('game'),
        onKeep: () => setModeDialogOpen(false),
        onCancel: () => setModeDialogOpen(false)
      })
    : null

  const shelfCard = jsx(SlotRail, {
    hub: desk.hub,
    selected: desk.selected,
    onSelect: onSelectCourse,
    onShowAll,
    onCreate
  }, 'rail')
  const continueCard = jsx(
    ContinueCard,
    { desk, busy, onPrimary, onOpenSection, onSeePlan, onRetryEstimate, companionEnabled },
    'continue'
  )
  const notesCard = jsx(FieldNotesLine, { notes, stale, onShowNotebook }, 'notes')
  const pathCard = jsx(CheckpointPath, {
    desk,
    onOpenSection,
    outlineStatus,
    outlineError,
    onRetryOutline,
    companionEnabled
  })
  const sourcesCard = jsx(SourcesDrawer, {
    open: sourcesOpen,
    onToggle: onToggleSources,
    sectionTitle: desk.current ? desk.current.title : null,
    status: sourcesStatus,
    error: sourcesError,
    sources,
    onRetry: onRetrySources
  }, 'sources')
  const trailColumn = jsxs('div', {
    'data-cb-trail': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0, width: '100%' },
    children: [continueCard, pathCard]
  }, 'trail')
  // GM-010: the play layer is pinned to a Game course and rides in its own slot under the trail,
  // so the trailhead, Continue and the check keep the first read of the page. Textbook, Guided and
  // parent-led courses mount nothing here.
  const gameCourse = cbGameCourse(desk.row, courseMode)
  const gameHeader = gameCourse
    ? jsx(
        GameHeader,
        {
          engagement: engagement ? engagement.data : null,
          status: engagement ? engagement.status : 'idle',
          error: engagement ? engagement.error : null,
          prefs,
          compact: !wide,
          onRetry: engagement ? engagement.reload : null
        },
        'game-header'
      )
    : null
  const gameJournal = gameCourse
    ? jsx(GameJournal, { objectives: desk.objectives, compact: !wide }, 'game-journal')
    : null
  // The shelf and the field notes are below the first viewport; sources stay a drawer. One
  // content column, not a rail beside a table: the trail is one object.
  const belowColumn = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0, maxWidth: CB_MEASURE },
    children: [shelfCard, notesCard, sourcesCard]
  }, 'below')

  return jsxs('div', {
    'data-cb-desk': 'ready',
    'data-cb-desk-layout': wide ? 'wide' : 'stacked',
    style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
    children: [
      stale
        ? jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) pb-2',
            children: [
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'Reconnecting. Showing the courses that were last read; the desk is paused.'
              }),
              jsx(CbAction, { variant: 'tertiary', onClick: onRetry, children: 'Retry now' })
            ]
          }, 'stale')
        : null,
      online === false
        ? jsx('div', {
            'data-cb-desk-offline': '',
            className: 'text-xs text-(--ui-text-secondary)',
            children: 'Offline. Showing the classrooms that were last read; starting a lesson is paused until the connection returns.'
          }, 'offline')
        : null,
      desk.selectionLost && desk.selected
        ? jsx('div', {
            'data-cb-desk-selection-lost': desk.selected.course_id,
            className: 'text-xs text-(--ui-text-secondary)',
            children: `That classroom is no longer on this profile. Showing ${desk.selected.name}.`
          }, 'selection')
        : null,
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }, 'notice') : null,
      modeRow,
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '1.1rem', minWidth: 0, width: '100%' },
        children: [gameHeader, worldSurface, trailColumn, gameJournal, belowColumn]
      }, 'layout'),
      studio,
      modeDialog
    ]
  })
}

/**
 * The estimate the backend already recorded: a pack manifest's per-objective `estimated_minutes`,
 * or the parent brief's `duration_minutes`. It never computes one from a count of sections.
 *
 * A failed read is its own state (`error`), not `none`: the desk has no answer and must not tell
 * the author they recorded none. `retryToken` re-runs the read for the desk's Retry control.
 */
function useSessionEstimate({ row, current, enabled, retryToken = 0 }) {
  const [state, setState] = useState({ status: 'none', minutes: null, source: null, error: null })
  const courseId = row ? row.course_id : null
  const packId = row && row.provenance ? row.provenance.pack_id : null
  const packVersion = row && row.provenance ? row.provenance.pack_version : null
  const ordinal = current ? current.ordinal : null
  const key = [courseId, packId, packVersion, ordinal].join('|')

  useEffect(() => {
    if (!enabled || !courseId || !ordinal) {
      setState({ status: 'none', minutes: null, source: null, error: null })
      return undefined
    }
    let cancelled = false
    setState({ status: 'loading', minutes: null, source: null, error: null })
    // A refusal is not an empty answer: only `parent.brief.get`'s NOT_FOUND is a real answer
    // ("this course has no parent brief"), so it alone collapses to `none`.
    const refusalIsAnAnswer = (method, response) =>
      method === 'parent.brief.get' && Boolean(response.error) && response.error.code === 'NOT_FOUND'
    let read
    if (packId && packVersion && backendSupports('pack.inspect')) {
      read = rpc('pack.inspect', { pack_id: packId, pack_version: packVersion }).then((response) => {
        if (!response.ok) return { failed: true, error: response.error || null }
        const manifest = response.result && response.result.manifest
        const entries = manifest && Array.isArray(manifest.objectives) ? manifest.objectives : []
        const match = entries.find((entry) => Number(entry.ordinal) === Number(ordinal))
        const minutes = match && Number(match.estimated_minutes) > 0 ? Number(match.estimated_minutes) : null
        return minutes ? { minutes, source: 'pack_manifest' } : null
      })
    } else if (backendSupports('parent.brief.get')) {
      read = rpc('parent.brief.get', { course_id: courseId }).then((response) => {
        if (!response.ok) {
          return refusalIsAnAnswer('parent.brief.get', response)
            ? null
            : { failed: true, error: response.error || null }
        }
        const brief = response.result && response.result.brief
        const minutes = brief && Number(brief.duration_minutes) > 0 ? Number(brief.duration_minutes) : null
        return minutes ? { minutes, source: 'parent_brief' } : null
      })
    } else {
      read = Promise.resolve(null)
    }
    read
      .then((found) => {
        if (cancelled) return
        if (found && found.failed) {
          setState({ status: 'error', minutes: null, source: null, error: found.error || null })
          return
        }
        setState(
          found
            ? { status: 'ready', minutes: found.minutes, source: found.source, error: null }
            : { status: 'none', minutes: null, source: null, error: null }
        )
      })
      .catch((error) => {
        if (cancelled) return
        setState({
          status: 'error',
          minutes: null,
          source: null,
          error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
        })
      })
    return () => {
      cancelled = true
    }
  }, [enabled, courseId, packId, packVersion, ordinal, key, retryToken])

  return state
}

/**
 * The Field Desk container. One `library.list` read feeds the hub projection; the selected
 * classroom's enrollment keys `course.outline`, `lesson.page`, `notebook.list` and Continue.
 * `selectedCourseId` is shell state owned by the page, so opening Course Detail and coming back
 * restores the same classroom. Every failed read is shown, never papered over.
 */
function FieldDesk({
  implemented,
  onOpen,
  onShowAll,
  onStartCreate,
  onStartSyllabus,
  profile,
  onEmptyChange,
  selectedCourseId,
  onSelectCourse,
  onOpenStudio,
  onBrowseLibrary,
  onSelectedClassroom,
  online,
  prefs
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const payload = { filter: 'all', limit: 50, sort: 'recent' }
  const key = JSON.stringify(payload)
  const library = useRpcQuery('library.list', payload, key, backendSupports('library.list'))

  const provisional = buildDeskModel({
    library: library.data,
    outline: null,
    estimate: null,
    selectedCourseId: selectedCourseId || null
  })
  const row = provisional.row
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: row ? row.enrollment_id : null },
    `desk-outline-${row ? row.enrollment_id : 'none'}`,
    Boolean(row) && supports('course.outline')
  )
  const withOutline = buildDeskModel({
    library: library.data,
    outline: outline.data,
    estimate: null,
    selectedCourseId: selectedCourseId || null,
    outlineState: outline.status
  })
  const current = withOutline.current
  const [estimateTicket, setEstimateTicket] = useState(0)
  const estimate = useSessionEstimate({
    row,
    current,
    enabled: Boolean(row) && Boolean(current),
    retryToken: estimateTicket
  })
  const onRetryEstimate = useCallback(() => setEstimateTicket((value) => value + 1), [])
  const desk = buildDeskModel({
    library: library.data,
    outline: outline.data,
    estimate,
    selectedCourseId: selectedCourseId || null,
    outlineState: outline.status
  })

  // A selected classroom that disappeared between reads is replaced by the newest slot and named
  // in the surface. The shell value is synced to the row that is actually shown, but no route or
  // focus changes: a background archive must not navigate the learner.
  const selectedCourseKey = desk.selected ? desk.selected.course_id : null
  useEffect(() => {
    if (desk.selectionLost && selectedCourseKey && onSelectCourse) onSelectCourse(selectedCourseKey)
  }, [desk.selectionLost, selectedCourseKey, onSelectCourse])

  // H-147: the settings sheet names the classroom its override belongs to, so the shell learns the
  // selected slot's id and title from the same model the rail paints.
  const selectedCourseTitle = desk.selected ? desk.selected.title || null : null
  useEffect(() => {
    if (onSelectedClassroom) {
      onSelectedClassroom(selectedCourseKey ? { courseId: selectedCourseKey, title: selectedCourseTitle } : null)
    }
  }, [selectedCourseKey, selectedCourseTitle, onSelectedClassroom])

  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  // A different classroom must not inherit the previous one's open drawer.
  useEffect(() => {
    setSourcesOpen(false)
  }, [row ? row.enrollment_id : 'none'])

  const page = useRpcQuery(
    'lesson.page',
    {
      enrollment_id: row ? row.enrollment_id : null,
      objective_id: current ? current.objective_id : null
    },
    `desk-page-${row ? row.enrollment_id : 'none'}-${current ? current.objective_id : 'none'}`,
    sourcesOpen && Boolean(row) && Boolean(current) && supports('lesson.page')
  )

  const notes = useRpcQuery(
    'notebook.list',
    { enrollment_id: row ? row.enrollment_id : null },
    `desk-notes-${row ? row.enrollment_id : 'none'}`,
    Boolean(row) && supports('notebook.list')
  )

  // GM-004: the durable course mode and its latest world. A failed or unsupported read is a state
  // the surface names; neither the badge nor the world hero is guessed from the device preference.
  const world = useWorldRead(row ? row.course_id : null, Boolean(row))
  // GM-010: the play layer is read from `engagement.read` and nowhere else. It is enabled only for
  // a Game course, and the mode comes from `world.read` — a `library.list` row carries no mode, so
  // no device preference and no stale row can turn the layer on.
  const deskMode = world.data ? readCoursePresentationMode(world.data.presentation_mode) : null
  const engagement = useRpcQuery(
    'engagement.read',
    { course_id: row ? row.course_id : null, enrollment_id: row ? row.enrollment_id : null },
    `desk-game-${row ? row.enrollment_id : 'none'}`,
    Boolean(row) && cbGameCourse(row, deskMode) && supports('engagement.read')
  )
  const onSetMode = useCallback(
    async (mode) => {
      if (!desk.row) return null
      const response = await rpc(
        'course.mode.set',
        { course_id: desk.row.course_id, mode },
        {
          idempotencyKey: `cb-mode-${newOperationId('mode')}`,
          expectedRevision: world.data ? world.data.revision : 0
        }
      )
      if (response && response.ok) {
        world.reload()
        library.reload()
      }
      return response
    },
    [desk.row, library, world]
  )
  const onWorldChanged = useCallback(() => {
    world.reload()
    library.reload()
  }, [library, world])

  const onPrimary = useCallback(async () => {
    if (!desk.row) return
    const kind = desk.primaryKind
    if (kind === 'start_lesson' || kind === 'resume_lesson') {
      if (!desk.current) return
      setBusy(true)
      setNotice(null)
      const outcome = await beginLessonFor({
        row: desk.row,
        objectiveId: desk.current.objective_id,
        objectiveTitle: desk.current.title || (desk.current.section ? desk.current.section.title : null),
        mode: kind === 'resume_lesson' ? 'resume' : 'fresh',
        profile: profile || currentScope().profile
      })
      setBusy(false)
      setNotice(outcome.message)
      if (outcome.ok) library.reload()
      if (outcome.ok && outcome.armed) {
        // The desk is a start surface too: arm the exact run, then open the new chat that carries
        // the pending binder. A host without newChat keeps the section/drawer open instead.
        const opened = openArmedLessonChat(profile || currentScope().profile)
        if (!opened) onOpen(desk.row, desk.current.objective_id)
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') onOpen(desk.row, desk.current.objective_id)
      return
    }
    // Review, plan and pack states are course-detail actions, not a second lesson path.
    onOpen(desk.row)
  }, [desk, profile, onOpen, library])

  return jsx(FieldDeskHome, {
    desk,
    libraryStatus: library.status,
    libraryError: library.error,
    libraryEmptyReason: library.data ? library.data.empty_reason : null,
    stale: Boolean(library.stale),
    busy,
    notice,
    online,
    onRetry: library.reload,
    onCreate: onStartCreate,
    onSyllabus: onStartSyllabus,
    onPrimary,
    onOpenSection: (objectiveId, blockId) => onOpen(desk.row, objectiveId, blockId),
    onSeePlan: () => onOpen(desk.row),
    companionEnabled: !prefs || prefs.companion !== false,
    onRetryEstimate,
    onSelectCourse,
    onOpenStudio,
    world,
    engagement,
    prefs,
    onSetMode,
    onWorldChanged,
    notes,
    onShowNotebook: () => onOpen(desk.row, null, null, 'notebook'),
    onOpen,
    onShowAll,
    sourcesOpen,
    onToggleSources: () => setSourcesOpen((value) => !value),
    sourcesStatus: page.status,
    sourcesError: page.error,
    sources: page.data && page.data.sources,
    onRetrySources: page.reload,
    outlineStatus: outline.status,
    outlineError: outline.error,
    onRetryOutline: outline.reload,
    implemented,
    onBrowseLibrary,
    onEmptyChange
  })
}

/**
 * Search and filter only exist when there is something to search (UX-01). With zero courses on the
 * profile, a search box and four pills would be chrome that cannot do anything, so they are absent
 * on first run and appear with the first course.
 */
function courseToolsVisible(data) {
  if (!data) return true
  return Number(data.total || 0) > 0
}

