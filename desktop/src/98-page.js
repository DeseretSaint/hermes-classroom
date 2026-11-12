function CoursebookPage() {
  const { state: health, reload: reloadHealth } = useHealth()
  const implemented = useRuntime(health.status)
  // H-147: appearance and motion are the learner's own settings, so they are read here and every
  // surface below (route and pane) paints from the same document. `system` defers to the host.
  const [homePrefs, updateHomePrefs, resetHomePrefs] = useCbHomePrefs()
  // The scoped Ink & Field Notes layer: every Coursebook surface paints from `--cb-*`, and the
  // layer stops at this root, so Hermes chrome keeps its own theme untouched.
  const hostMode = useCbMode()
  const cbMode = cbAppliedMode(hostMode, homePrefs.appearance)
  const systemReduced = useCbReducedMedia()
  const cbMotion = homePrefs.reducedMotion === 'reduce' || systemReduced ? cbMotionFor('reduced') : cbMotionFor('full')
  // H-179: the setting is published to the surfaces below, so `Reduce motion` actually reaches
  // every CbAction whether the learner picked it or the OS asked for it.
  useEffect(() => {
    publishCbMotion(cbMotion)
  }, [cbMotion.reduced])
  const online = useOnline()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const settingsTriggerRef = useRef(null)
  // The classroom the Home rail has selected, named so the classroom section of the sheet can say
  // which classroom its override belongs to rather than "this one".
  const [homeClassroom, setHomeClassroom] = useState(null)
  const [destination, setDestination] = useState(rememberedDestination)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [syllabusFlow, setSyllabusFlow] = useState(false)
  const [syllabusSupersedes, setSyllabusSupersedes] = useState(null)
  const [companionTarget, setCompanionTarget] = useState(null)
  const [courseReloadTick, setCourseReloadTick] = useState(0)
  // Set by the mounted course surface when the welcome (first run) is what is on screen. The header
  // then drops its duplicate "New course" button: one screen, one primary action (UX-01).
  const [coursesEmpty, setCoursesEmpty] = useState(false)
  const [openCourse, setOpenCourse] = useState(null)
  // H-146: the selected classroom is shell state, not a backend field and not localStorage. It
  // survives Course Detail because it lives here, beside `openCourse`, and it is never written to
  // progress. A slot switch changes this value only.
  const [selectedCourseId, setSelectedCourseId] = useState(null)
  // GM-002: global Home is the library. Opening a card asks for that course's own home; this id is
  // the only thing that turns Home into a course home, so a fresh mount never silently does it.
  // Leaving Home (or pressing Home again) clears it.
  const [homeCourseId, setHomeCourseId] = useState(null)
  // H-103: "Change the goal" carries the rejected plan's own choices into the create form instead
  // of asking the learner to retype them. It is a seed, not an automatic submit.
  const [createSeed, setCreateSeed] = useState(null)
  // Every door into the create form clears the previous seed; only the plan-rejection action seeds.
  const beginCreate = useCallback((seed = null) => {
    setCreateSeed(seed)
    setCreating(true)
  }, [])
  const [studioCourse, setStudioCourse] = useState(null)
  const [studioSeed, setStudioSeed] = useState(null)
  const [studioRevision, setStudioRevision] = useState(0)
  const [studioReload, setStudioReload] = useState(0)
  // GM-006: the Parent Studio has two entrances. The tab is route state beside the open plan, so
  // leaving and returning keeps the parent where they were, and opening a plan is still a plan.
  const [studioTab, setStudioTab] = useState('plans')

  const changeDestination = useCallback((next) => {
    rememberedDestination = next
    setCreating(false)
    setImporting(false)
    setSyllabusFlow(false)
    setOpenCourse(null)
    setStudioCourse(null)
    setStudioSeed(null)
    // A destination is not a course: leaving Home (or any move) drops the opened course home.
    setHomeCourseId(null)
    setDestination(next)
  }, [])

  // GM-002: selecting a shelf card is the one act that opens a course home. It is a local
  // selection beside the route, never a URL guess, and it does not open Course Detail.
  const openCourseHome = useCallback((row) => {
    if (!row) return
    if (row.recipe !== 'parent' && row.course_id) {
      setSelectedCourseId(row.course_id)
      setHomeCourseId(row.course_id)
    }
  }, [])

  const closeCourseHome = useCallback(() => {
    setHomeCourseId(null)
  }, [])

  // H-147: the sheet closes back onto the control that opened it — Escape, Close and a backdrop
  // click all land here, so keyboard focus never drops to <body>.
  const openSettings = useCallback(() => setSettingsOpen(true), [])
  const closeSettings = useCallback(() => {
    setSettingsOpen(false)
    const wrap = settingsTriggerRef.current
    const button = wrap && typeof wrap.querySelector === 'function' ? wrap.querySelector('button') : null
    if (button && typeof button.focus === 'function') button.focus({ preventScroll: true })
  }, [])

  // A created companion course is opened from the library read, never from the create response:
  // the row carries the enrolment revision the plan tab fences on, and the plan itself is still a
  // background job. This waits for the row to appear instead of inventing one.
  useEffect(() => {
    if (!companionTarget) return undefined
    let cancelled = false
    let attempts = 0
    const find = async () => {
      attempts += 1
      const response = await rpc('library.list', { filter: 'all', limit: 100, sort: 'recent' })
      if (cancelled) return
      const rows = response && response.ok && response.result && Array.isArray(response.result.items) ? response.result.items : []
      const row = rows.find((candidate) => candidate.course_id === companionTarget.courseId)
      if (row) {
        rememberedDestination = 'courses'
        setDestination('courses')
        setSelectedCourseId(row.course_id)
        setOpenCourse({ row, objectiveId: null, view: 'plan' })
        setCompanionTarget(null)
        return
      }
      if (attempts >= 20) setCompanionTarget(null)
    }
    find()
    const handle = setInterval(find, 1500)
    return () => {
      cancelled = true
      clearInterval(handle)
    }
  }, [companionTarget])

  const openNewSyllabusRevision = useCallback((target) => {
    setSyllabusSupersedes(target || {})
    setSyllabusFlow(true)
  }, [])

  useRouteIntent(
    useCallback((intent) => {
      if (!intent) return
      if (intent.kind === 'create') {
        rememberedDestination = 'courses'
        setDestination('courses')
        setCreateSeed(null)
        setCreating(true)
        setSyllabusFlow(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'import') {
        rememberedDestination = 'workshop'
        setDestination('workshop')
        setCreating(false)
        setSyllabusFlow(false)
        setImporting(true)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'syllabus') {
        rememberedDestination = 'workshop'
        setDestination('workshop')
        setCreating(false)
        setImporting(false)
        setSyllabusFlow(true)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'library') {
        rememberedDestination = 'workshop'
        setDestination('workshop')
        setCreating(false)
        setSyllabusFlow(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioSeed(null)
      } else if (intent.kind === 'studio') {
        rememberedDestination = 'studio'
        setDestination('studio')
        setCreating(false)
        setImporting(false)
        setOpenCourse(null)
        setStudioCourse(null)
        setStudioSeed(null)
        // "Open Parent Studio" means the authored plans, the entrance the route opens on.
        setStudioTab('plans')
      } else if (intent.kind === 'studio-takehome') {
        // GM-006: the take-home entrance is its own palette destination, not a second route.
        // It lands on the same Parent Studio and never opens a plan behind the tab.
        rememberedDestination = 'studio'
        setDestination('studio')
        setCreating(false)
        setImporting(false)
        setSyllabusFlow(false)
        setOpenCourse(null)
        setStudioCourse(null)
        setStudioSeed(null)
        setStudioTab('takehome')
      } else if (intent.kind === 'studio-new') {
        rememberedDestination = 'studio'
        setDestination('studio')
        setCreating(false)
        setImporting(false)
        setStudioCourse(null)
        setStudioTab('plans')
        setStudioSeed({ initial: null, note: null })
      } else if (intent.kind === 'lesson-block' && intent.row) {
        // GM-012: a citation is a real link back to the block it names. The course detail opens
        // the same section and focuses the exact block; a source-only citation opens the section
        // where the source list lives. The learner pressed the citation, so this is not a
        // background navigation.
        if (intent.row.course_id) setSelectedCourseId(intent.row.course_id)
        setCreating(false)
        setImporting(false)
        setSyllabusFlow(false)
        setStudioCourse(null)
        setOpenCourse({
          row: intent.row,
          objectiveId: intent.objectiveId || null,
          blockId: intent.blockId || null,
          view: null
        })
      }
    }, [])
  )

  const canCreate = Boolean(implemented && implemented.has('course.create'))
  const canImport = Boolean(IMPORT_FLOW_WIRED && implemented && implemented.has('pack.import'))
  const canSyllabus = Boolean(implemented && implemented.has('syllabus.intake.create'))
  const canAuthor = Boolean(implemented && implemented.has('parent.brief.create'))
  // R1 (CP-020b): the page gutter is a container-query rule on the route's inner wrapper, not an
  // inline clamp on the route root. A viewport unit measured the Desktop window rather than the
  // route, and a container unit on the container element resolves against its *ancestor*, so
  // neither can live here. The `cb3-gutter` class in CB_V3_CSS owns the two branches (0.7rem below
  // a 760 px route, clamp(1.25rem, 3.05cqi, 4rem) above it) and `test_v3_scope` refuses a viewport
  // unit that reaches the rendered element's own style.

  // CP-040 — the classroom route. SPEC-V3 §5.3 makes the section the classroom, and the learner's
  // presentation mode decides which reading surface that classroom uses: Game and Guided open the
  // v3 classroom (stepper, section plate, one check), Textbook keeps the reader workspace that owns
  // the document blocks, pronunciation, the tutor rail and take-home. `openCourse.view` is an
  // explicit request for one of those views (Plan, Note, a citation handoff) and is never
  // overridden; a section opened with no view follows the mode.
  const classroomMode =
    openCourse && openCourse.row && !openCourse.view && !openCourse.blockId
      ? cbEffectiveMode(homePrefs, openCourse.row.course_id)
      : null
  // The run behind the classroom's no-chat action. It arms the exact run first and only then opens
  // the chat, so the chat pane's pending binder — not a bare new chat — is what the learner lands
  // in. A failed `lesson.begin` reports the backend's own code and never falls through to a chat.
  const startClassroomRun = useCallback(async (course) => {
    const row = course && course.row
    const objectiveId = course && course.objectiveId
    if (!row || !objectiveId) return
    const profile = currentScope().profile
    const response = await rpc(
      'lesson.begin',
      { enrollment_id: row.enrollment_id, objective_id: objectiveId, mode: 'fresh' },
      { idempotencyKey: `cb3-classroom-run-${objectiveId}-${newOperationId('run')}` }
    )
    if (!response.ok) {
      host.notify({
        kind: 'warning',
        message: `${response.error.code}: ${describeError(response.error)}`
      })
      return
    }
    armPendingBind({
      enrollmentId: row.enrollment_id,
      objectiveId,
      objectiveTitle: null,
      lessonRunId: response.result.lesson_run_id,
      profile
    })
    if (!startLessonChat(profile)) {
      host.notify({
        kind: 'warning',
        message: 'This Desktop build cannot open a new chat; start one from the sidebar.'
      })
    }
  }, [])

  let body
  if (health.status === 'loading' && !health.result) {
    body = jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading the Coursebook backend' }) })
  } else if (health.status === 'unavailable') {
    body = jsx(BackendUnavailable, { error: health.error, reload: reloadHealth })
  } else if (health.status === 'degraded') {
    body = jsx(DegradedBody, { reload: reloadHealth, result: health.result })
  } else if (creating) {
    body = jsx(CreateCourseFlow, {
      seed: createSeed,
      onCancel: () => {
        setCreating(false)
        setCreateSeed(null)
      },
      onCreated: () => {
        setCreateSeed(null)
        reloadHealth()
      }
    })
  } else if (importing) {
    body = jsx(PackImportFlow, {
      implemented,
      onCancel: () => setImporting(false),
      onImported: () => {
        setImporting(false)
        reloadHealth()
      }
    })
  } else if (syllabusFlow) {
    body = jsx(SyllabusIntakeFlow, {
      revisionOnly: Boolean(syllabusSupersedes),
      supersedes: syllabusSupersedes,
      onCancel: () => {
        setSyllabusFlow(false)
        setSyllabusSupersedes(null)
      },
      // The course and its plan job are real ids the backend returned; the desk reloads so the
      // new companion course appears from `library.list`, not from this screen's memory.
      onCreated: (created) => {
        const revising = Boolean(syllabusSupersedes)
        setSyllabusFlow(false)
        setSyllabusSupersedes(null)
        if (revising) setCourseReloadTick((value) => value + 1)
        else if (created && created.courseId) setCompanionTarget({ courseId: created.courseId })
        reloadHealth()
      }
    })
  } else if (destination === 'studio') {
    if (studioSeed) {
      body = jsx(StudioBriefForm, {
        initial: studioSeed.initial,
        note: studioSeed.note,
        supported: canAuthor,
        onCancel: () => setStudioSeed(null),
        onCreated: (created) => {
          setStudioSeed(null)
          setStudioCourse({
            course_id: created.course_id,
            enrollment_id: created.enrollment_id,
            title: created.title,
            revision: Number(created.revision || 0)
          })
          setStudioRevision(Number(created.revision || 0))
          setStudioReload((value) => value + 1)
        }
      })
    } else if (studioCourse) {
      body = jsx(StudioDetail, {
        course: studioCourse,
        implemented,
        revision: studioRevision,
        onRevision: setStudioRevision,
        onBack: () => setStudioCourse(null),
        onChanged: () => setStudioReload((value) => value + 1),
        onDuplicate: (brief, note) => setStudioSeed({ initial: brief, note })
      })
    } else {
      body = jsxs('div', {
        'data-cb-parent-studio': studioTab,
        style: { display: 'flex', flexDirection: 'column', minWidth: 0 },
        children: [
          jsx(StudioEntranceTabs, { value: studioTab, onChange: setStudioTab }),
          studioTab === 'takehome'
            ? jsx(TakeHomeStudio, {
                implemented,
                sessionMinutes: homePrefs.sessionMinutes,
                onOpenSettings: openSettings,
                triggerRef: settingsTriggerRef
              })
            : studioTab === 'homework'
              ? jsx(HomeworkStudio, { implemented })
              : jsx(StudioList, {
                implemented,
                reloadSignal: studioReload,
                sessionMinutes: homePrefs.sessionMinutes,
                onOpenSettings: openSettings,
                triggerRef: settingsTriggerRef,
                onCreate: () => setStudioSeed({ initial: null, note: null }),
                onOpen: (row) => {
                  setStudioCourse(row)
                  setStudioRevision(Number(row.revision || 0))
                }
              })
        ]
      })
    }
  } else if (destination === 'workshop') {
    body = jsx(WorkshopView, {
      createOpen: creating,
      implemented,
      canSyllabus,
      canImport,
      onStartSyllabus: canSyllabus ? () => setSyllabusFlow(true) : null,
      onStartImport: canImport ? onImportPlaceholder : null,
      onOpenCourse: (row) => {
        if (row && row.recipe !== 'parent') setSelectedCourseId(row.course_id)
        rememberedDestination = 'workshop'
        setDestination('workshop')
        setOpenCourse({ row, objectiveId: null })
      }
    })
  } else if (classroomMode && openCourse.objectiveId) {
    // CP-040: the classroom's own surface. It is a wired container (its own outline, page, world
    // and Game engagement reads), so the route hands it identity and navigation only. Back returns
    // to the course home; the post-pass primary carries the next section's objective id (item 36),
    // and the last section passes null, which is the course path.
    body = jsx(ClassroomV3Surface, {
      row: openCourse.row,
      enrollmentId: openCourse.row ? openCourse.row.enrollment_id : null,
      objectiveId: openCourse.objectiveId,
      mode: classroomMode,
      onBack: () => setOpenCourse({ ...openCourse, objectiveId: null, blockId: null }),
      onOpenSection: (objectiveId) => setOpenCourse({ ...openCourse, objectiveId, blockId: null }),
      onNextSection: (nextObjectiveId) =>
        setOpenCourse({ ...openCourse, objectiveId: nextObjectiveId || null, blockId: null }),
      onStartChat: () => startClassroomRun(openCourse),
      onChanged: () => reloadHealth()
    })
  } else if (openCourse) {
    body = jsx(CourseDetail, {
      row: openCourse.row,
      // GM-010: the play layer obeys the learner's own Game feedback switch on this device.
      prefs: homePrefs,
      focusObjectiveId: openCourse.objectiveId,
      focusBlockId: openCourse.blockId || null,
      focusView: openCourse.view || null,
      // H-147: the view the lesson opens in is the classroom's own override, else the Home default.
      defaultLessonView:
        CB_PRESENTATION_VIEW[cbEffectiveMode(homePrefs, openCourse.row ? openCourse.row.course_id : null)] ||
        'textbook',
      implemented,
      profile: currentScope().profile,
      onBack: () => setOpenCourse(null),
      onChanged: () => reloadHealth(),
      onOpenLibrary: () => {
        setOpenCourse(null)
        rememberedDestination = 'workshop'
        setDestination('workshop')
      },
      reloadSignal: courseReloadTick,
      onChangeGoal: (seed) => {
        setOpenCourse(null)
        rememberedDestination = 'courses'
        setDestination('courses')
        beginCreate(seed || null)
      },
      onNewSyllabus: openNewSyllabusRevision
    })
  } else if (destination === 'courses') {
    body = jsx(CoursesView, {
      createOpen: creating,
      implemented,
      onEmptyChange: setCoursesEmpty,
      onStartCreate: () => beginCreate(),
      onStartSyllabus: canSyllabus ? () => setSyllabusFlow(true) : null,
      onBrowseLibrary: () => changeDestination('workshop'),
      onOpen: (row) => {
        if (row && row.recipe !== 'parent') setSelectedCourseId(row.course_id)
        setOpenCourse({ row, objectiveId: null })
      },
      onShowDesk: () => changeDestination('home')
    })
  } else if (destination === 'home' && homeCourseId) {
    // GM-002: the selected course's home. It keeps the trailhead, the current objective, Continue
    // and the path, and it is reachable only by opening that course on the library Home. It is a
    // distinct surface (`data-cb-course-home`), not the global Home wearing a course.
    body = jsx('div', {
      'data-cb-course-home': homeCourseId,
      style: { display: 'flex', flexDirection: 'column', minWidth: 0 },
      children: jsx(FieldDesk, {
      implemented,
      profile: currentScope().profile,
      online,
      prefs: homePrefs,
      selectedCourseId: homeCourseId,
      onSelectCourse: (courseId) => {
        setSelectedCourseId(courseId)
        setHomeCourseId(courseId)
      },
      onSelectedClassroom: setHomeClassroom,
      onOpenStudio: () => changeDestination('studio'),
      onEmptyChange: setCoursesEmpty,
      onOpen: (row, objectiveId, blockId, view) => {
        if (row && row.recipe !== 'parent') setSelectedCourseId(row.course_id)
        setOpenCourse({ row, objectiveId: objectiveId || null, blockId: blockId || null, view: view || null })
      },
      onShowAll: () => changeDestination('courses'),
      // A course home is not a create surface: the one create action lives on global Home.
      onStartCreate: null,
      onStartSyllabus: null,
        onBrowseLibrary: () => changeDestination('workshop')
      })
    })
  } else {
    // GM-002: global Home is the field library. It launches courses; it is not the selected
    // course's page and never carries Continue, the trailhead or a Japanese lesson scene.
    body = jsx(HomeLibraryPanel, {
      online,
      canCreate,
      onStartCreate: () => beginCreate(),
      onBrowseLibrary: () => changeDestination('workshop'),
      onOpenCourse: openCourseHome,
      onShowAll: () => changeDestination('courses'),
      onOpenStudio: () => changeDestination('studio')
    })
  }

  const statusCopy = backendCopy(health.status)
  const showDestinationNav = health.status === 'ready' && !creating && !importing && !syllabusFlow
  // One stable page title per surface. It is the route's only `h1` in every health and flow
  // state, so the first heading is the page title and never a card's objective; every surface
  // below it is an `h2` region. An open course is its own page ("Course"), not a second "Home"
  // or a second course title (CourseDetail already prints the course name at h2). GM-002: the
  // opened course home under Home is "Course" too — it is not the library.
  const pageTitle = openCourse || (destination === 'home' && homeCourseId)
    ? 'Course'
    : ((DESTINATIONS.find((item) => item.id === destination) || {}).label) || ROUTE_TITLE

  return jsx(CbV3Scope, {
    mode: cbMode,
    className: 'relative flex h-full min-h-0 flex-col',
    contentClassName: 'cb3-gutter',
    attributes: {
      'data-cb-destination': destination,
      'data-cb-route': ROUTE_PATH,
      'data-cb-scope': cbMode,
      'data-cb-motion': cbMotion.preference
    },
    style: { ...cbScopeStyle(cbMode), ...cbHostVars(homePrefs.appearance) },
    children: [
      // Every top-level child carries a key: `children` is an array, and React warns on an
      // unkeyed element in any list — including a props array — on the console only.
      jsx(SkipToContent, {}, 'skip'),
      jsxs('header', {
        className: 'flex shrink-0 flex-col gap-2 pt-3',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-start justify-between gap-3',
            children: [
              jsxs('div', {
                className: 'flex min-w-0 flex-col gap-1',
                children: [
                  jsx(CoursebookWordmark, {}),
                  jsx('h1', {
                    'data-cb-page-title': '',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.display,
                      fontWeight: 600,
                      lineHeight: 1.05,
                      letterSpacing: '-0.02em',
                      color: 'var(--cb-ink)',
                      // H-160: the page title is a single word at the display step. At 460 px with
                      // 200% text the route column is 154 px and "Course" at 72 px is ~220 px, so
                      // the unbreakable token pushed the route to routeOverflowX: 53. `anywhere`
                      // (not `break-word`) also lowers the min-content width, which is what the
                      // wrapping header row sizes itself from.
                      minWidth: 0,
                      maxWidth: '100%',
                      overflowWrap: 'anywhere'
                    },
                    children: pageTitle
                  }),
                  destination === 'home' && !openCourse
                    ? jsx(HomeDefaultsLine, {
                        prefs: homePrefs,
                        classroom: homeClassroom,
                        onOpenSettings: openSettings,
                        triggerRef: settingsTriggerRef
                      })
                    : null
                ]
              }),
              jsxs('div', {
                // The actions must give way before the route does: at a 460 px window the route pane
                // is ~214 px, and two nowrap buttons refused to shrink (V2-2: 19 px at 900, 45 px at
                // 460). Shrinkable + wrapping lets them stack onto their own rows instead of clipping.
                className: 'flex min-w-0 flex-wrap items-center justify-end gap-2',
                children: [
                  online ? null : jsx(sdk.Badge, { variant: 'warn', children: 'Offline' }),
                  statusCopy ? jsx(sdk.Badge, { variant: health.status === 'unavailable' ? 'warn' : 'muted', children: statusCopy }) : null,
                  // GM-002: the course home is one step in from the library Home. This is the way
                  // back; it never relies on the nav's current-item click being re-armed.
                  destination === 'home' && homeCourseId && !openCourse
                    ? jsx(CbAction, {
                        variant: 'tertiary',
                        'data-cb-home-back': '',
                        onClick: closeCourseHome,
                        children: 'Back to Home'
                      }, 'home-back')
                    : null,
                  // H-176 — Settings is a small labelled control in the top-right of the
                  // trailhead, outside the action row. It is not a second primary.
                  destination === 'home' && !openCourse
                    ? jsx('span', {
                        ref: settingsTriggerRef,
                        style: { display: 'inline-flex', alignItems: 'center' },
                        children: jsx(sdk.Button, {
                          size: 'sm',
                          variant: 'ghost',
                          'data-cb-settings-open': '',
                          'aria-label': 'Open Coursebook settings',
                          'aria-haspopup': 'dialog',
                          style: { minHeight: '44px' },
                          onClick: openSettings,
                          children: 'Settings'
                        })
                      }, 'settings')
                    : null,
                  // H-160: UX_SPEC §4 names Courses' page-header primary as **New course**; H-151
                  // measured zero primaries here because this call site was still `secondary`.
                  // Only one eligibility check owns it (non-empty catalog, so FirstRun's own
                  // primary cannot co-exist), so the catalog never carries two.
                  health.status === 'ready' && online && !creating && !importing && destination === 'courses' && canCreate && !coursesEmpty && !openCourse
                    ? jsx(CbAction, { onClick: () => beginCreate(), variant: 'primary', children: 'New course' })
                    : null,
                  // H-196: the Workshop's Library tab owns Import pack and the syllabus door, so
                  // Discover keeps one primary per object (Add to library / Continue) and the route
                  // header carries none of them. The banner stays hidden on this surface.
                  // H-91 P2-4: the Parent Studio landing plate already carries the one
                  // "New lesson plan" primary, so the route header must not repeat it (the gate
                  // counted two primaries with the same label on that surface).
                ]
              })
            ]
          }),
          online
            ? null
            : jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children:
                  'Offline. Lessons, notes and review keep working from what this profile already saved. ' +
                  'Creating a course, writing a brief and grading open answers are paused until the connection returns.'
              }),
          showDestinationNav
            ? jsx(CbDestinationNav, { value: destination, onChange: changeDestination, onHome: closeCourseHome }, 'destination-nav')
            : null
        ]
      }, 'page-header'),
      jsx(PageBody, { label: `${pageTitle} content`, children: body }, 'page-body'),
      // H-147: the sheet lives over the route, not at a route of its own. It is only mounted while
      // open, so Home is the only place a reader meets it.
      jsx(HomeSettingsSheet, {
        open: settingsOpen,
        prefs: homePrefs,
        classroom: homeClassroom,
        onUpdate: updateHomePrefs,
        onReset: resetHomePrefs,
        onClose: closeSettings
      }, 'settings-sheet')
    ]
  })
}

