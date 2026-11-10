/* ── GM-004: the course world and the World Studio ─────────────────────────────────────────
 * A world is a governed visual kit: textless plates plus a style specification. Everything a
 * learner reads here is authored DOM copy; the image model never supplies type, a number, a
 * rating or a procedure. The studio's states are driven by `world.read`, and every primary
 * action names the fact it needs next (a plan, a style choice, the kit, a final approval).
 */

const CB_WORLD_COPY = Object.freeze({
  label: 'Course world',
  hero: 'World',
  modeGame: 'Game',
  modeTextbook: 'Textbook',
  changeMode: 'Change mode',
  courseSettings: 'Course settings',
  notApprovedTitle: 'World not approved yet',
  notApprovedBody:
    'This course reads as Textbook until its world is approved. Your lessons and plan are unchanged.',
  openStudio: 'Open World Studio',
  readFallback: 'Use Textbook mode',
  readUnsupported: 'This backend does not report a course world yet.',
  readError: 'The course world could not be read',
  plateMissing: 'The art for this plate is not available; the text label stands in for it.'
})

/** One authored name per policy grammar. The board's own `label` is the policy word, never art. */
const CB_GRAMMAR_NAME = Object.freeze({
  field_atlas: 'Field atlas',
  workshop_manual: 'Workshop manual',
  observatory: 'Observatory',
  kitchen_table: 'Kitchen table',
  archive_desk: 'Archive desk',
  studio_bench: 'Studio bench',
  lab_bench: 'Lab bench',
  instrument_board: 'Instrument board'
})

const CB_GRAMMAR_ONE_LINE = Object.freeze({
  field_atlas: 'Maps, lanterns and a field notebook — a place to travel through the subject.',
  workshop_manual: 'A service bay, tool wall and manual pages — orientation beside the procedure.',
  observatory: 'Star charts, instruments and an observation log.',
  kitchen_table: 'A work surface, ingredient cards and a recipe board.',
  archive_desk: 'Documents, stamps, maps and index cards.',
  studio_bench: 'Materials, swatches and a sketchbook.',
  lab_bench: 'Glassware, a lab notebook and labelled stations.',
  instrument_board: 'Instruments, graph paper and a blackboard.'
})

const CB_WORLD_STATE_WORD = Object.freeze({
  not_requested: 'Not started',
  concepts_generating: 'Choosing directions',
  concepts_ready: 'Three directions',
  style_selected: 'Direction chosen',
  kit_generating: 'Building the world',
  kit_ready: 'Ready to approve',
  approved: 'Approved',
  failed: 'Could not finish',
  unavailable: 'Unavailable'
})

function cbWorldStateWord(state) {
  return CB_WORLD_STATE_WORD[state] || CB_WORLD_STATE_WORD.not_requested
}

/** The plate for one role. `section` is matched by its section id, never by index. */
function cbWorldPlate(assets, role, sectionId) {
  const list = Array.isArray(assets) ? assets : []
  if (role === 'section') {
    return list.find((item) => item && item.role === 'section' && item.section_id === sectionId) || null
  }
  return list.find((item) => item && item.role === role) || null
}

/** Sections the world actually has art for, in the plate's own order. */
function cbWorldSectionPlates(world) {
  const assets = (world && world.assets) || []
  const brief = (world && world.brief) || {}
  const byId = new Map((brief.sections || []).map((section) => [section.id, section.title || '']))
  return assets
    .filter((item) => item && item.role === 'section' && item.section_id)
    .map((item) => ({
      section_id: item.section_id,
      section_key: item.section_key || item.section_id,
      title: byId.get(item.section_id) || '',
      artifact_id: item.artifact_id
    }))
}

/** The named roles still missing from a kit: `hero`, `cover` or `section:<id>`. */
function cbWorldMissingRoles(world) {
  const error = world && world.error
  if (error && Array.isArray(error.missing_roles)) return error.missing_roles
  return []
}

/** Whether a world counts as final-approved for the Game gate. Never inferred from a style. */
function cbWorldApproved(world) {
  return Boolean(world && world.state === 'approved' && world.approved_hash)
}

/**
 * `world.read` for one course. A failed or unsupported read is its own state: the shelf and the
 * course home name the failed read instead of printing a mode nobody answered.
 */
function useWorldRead(courseId, enabled) {
  const [state, setState] = useState({ status: 'idle', data: null, error: null })
  const [ticket, setTicket] = useState(0)
  const supported = Boolean(enabled && courseId && backendSupports('world.read'))
  const reload = useCallback(() => setTicket((value) => value + 1), [])
  useEffect(() => {
    if (!supported) {
      setState({ status: courseId ? 'unsupported' : 'idle', data: null, error: null })
      return undefined
    }
    let live = true
    setState((previous) => ({
      status: previous.data ? 'ready' : 'loading',
      data: previous.data,
      error: null
    }))
    rpc('world.read', { course_id: courseId })
      .then((response) => {
        if (!live) return
        if (response && response.ok && response.result) {
          setState({ status: 'ready', data: response.result, error: null })
        } else {
          setState({ status: 'error', data: null, error: (response && response.error) || null })
        }
      })
      .catch((error) => {
        if (live) setState({ status: 'error', data: null, error })
      })
    return () => {
      live = false
    }
  }, [courseId, supported, ticket])
  return { ...state, reload }
}

/**
 * One textless plate. The artifact route is the only image source; when it refuses, the plate
 * paints its authored caption instead of an invented picture or a broken-image icon.
 */
function WorldPlate({ artifactId, caption, height, kind }) {
  const preview = useArtifactPreview(artifactId)
  const frame = {
    position: 'relative',
    width: '100%',
    height: height || '11rem',
    background: 'var(--cb3-canvas-edge)',
    border: '1px solid var(--cb3-rule)',
    borderRadius: cb3Radius('square'),
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  }
  if (preview.state === 'ready' && preview.mime && preview.mime.startsWith('image/')) {
    return jsxs('div', {
      'data-cb-world-plate': kind || 'orientation',
      'data-cb-world-plate-artifact': artifactId,
      style: frame,
      children: [
        jsx('img', {
          'data-cb-world-plate-art': '',
          alt: caption,
          src: preview.data_url,
          loading: 'lazy',
          style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' }
        }),
        jsx('span', {
          'aria-hidden': 'true',
          style: {
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: 0,
            padding: '0.25rem 0.5rem',
            fontFamily: 'var(--cb3-font-ui)',
            fontSize: cb3Type('caption'),
            color: 'var(--cb3-ink-soft)',
            background: 'var(--cb3-card-stock)',
            borderTop: '1px solid var(--cb3-rule)'
          },
          children: caption
        })
      ]
    })
  }
  return jsx('div', {
    'data-cb-world-plate': kind || 'orientation',
    'data-cb-world-plate-state': preview.state,
    style: { ...frame, padding: '0.6rem' },
    children: jsxs('div', {
      style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', textAlign: 'center' },
      children: [
        jsx('span', {
          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), color: 'var(--cb3-ink)' },
          children: caption
        }),
        jsx('span', {
          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
          children: preview.state === 'loading' ? 'Loading the plate' : CB_WORLD_COPY.plateMissing
        })
      ]
    })
  })
}

/** The durable mode badge. It is a word, never a colour-only signal, and it is not a control. */
function ModeBadge({ mode, pending }) {
  const game = mode === 'game'
  return jsx('span', {
    'data-cb-mode-badge': mode || 'textbook',
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.3rem',
      padding: '0.1rem 0.45rem',
      border: `1px solid ${game ? 'var(--cb3-gold)' : 'var(--cb3-terracotta)'}`,
      borderRadius: cb3Radius('soft'),
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('caption'),
      fontWeight: 600,
      color: game ? 'var(--cb3-gold)' : 'var(--cb3-terracotta)',
      background: 'var(--cb3-card-stock)'
    },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: {
          width: '0.4rem',
          height: '0.4rem',
          borderRadius: cb3Radius('pill'),
          background: game ? 'var(--cb3-gold)' : 'var(--cb3-terracotta)'
        }
      }),
      game ? CB_WORLD_COPY.modeGame : CB_WORLD_COPY.modeTextbook,
      pending ? ' · saving' : null
    ]
  })
}

/**
 * The course-home world: a hero plate with real DOM type over a quiet field, then the route's
 * section cards. Only an approved Game world paints here; a Textbook course has no world surface.
 */
function CourseWorldHero({ world, mode, sectionPlates, narrow, onOpenStudio, onOpenSection }) {
  const approved = cbWorldApproved(world)
  const hero = cbWorldPlate(world && world.assets, 'hero')
  const title = ((world && world.brief && world.brief.title) || '').trim()
  const grammar = world && world.selected_concept_id
    ? String(world.selected_concept_id).split('--').pop()
    : null
  const grammarName = (grammar && CB_GRAMMAR_NAME[grammar]) || null
  if (!approved) {
    return jsxs('section', {
      'data-cb-world': 'unapproved',
      'data-cb-world-state': (world && world.state) || 'not_requested',
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        padding: '0.9rem 1rem 1rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round'),
        minWidth: 0
      },
      children: [
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
          children: [jsx(ModeBadge, { mode }), jsx('span', {
            style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-ink)' },
            children: CB_WORLD_COPY.notApprovedTitle
          })]
        }),
        jsx('p', {
          style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)', maxWidth: '58ch' },
          children: CB_WORLD_COPY.notApprovedBody
        }),
        jsx(PillAction, {
          variant: 'quiet',
          'data-cb-world-open-studio': '',
          onClick: onOpenStudio,
          style: { alignSelf: 'flex-start' },
          children: CB_WORLD_COPY.openStudio
        })
      ]
    })
  }
  return jsxs('section', {
    'data-cb-world': 'game',
    'data-cb-world-approved': world.approved_hash,
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: 0 },
    children: [
      jsxs('div', {
        'data-cb-world-hero': '',
        style: {
          display: 'grid',
          gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) 13.25rem',
          gap: '0.9rem',
          padding: '0.9rem 1rem 1rem',
          background: 'var(--cb3-terracotta-quiet)',
          borderRadius: cb3Radius('round'),
          minWidth: 0
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0, justifyContent: 'center' },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem' },
                children: [
                  jsx(ModeBadge, { mode })
                ]
              }),
              jsx('h2', {
                'data-cb-world-title': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-display)',
                  fontSize: cb3Type('heading'),
                  lineHeight: cb3Lead('heading'),
                  fontWeight: 600,
                  color: 'var(--cb3-ink)',
                  minWidth: 0,
                  overflowWrap: 'anywhere'
                },
                children: title || 'This course'
              }),
              jsx('div', {
                'data-cb-world-grammar': '',
                style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)' },
                children: grammarName ? `${CB_WORLD_COPY.label} · ${grammarName}` : CB_WORLD_COPY.label
              }),
              jsx(PillAction, {
                variant: 'quiet',
                'data-cb-world-change': '',
                onClick: onOpenStudio,
                style: { alignSelf: 'flex-start' },
                children: 'Review the world'
              })
            ]
          }, 'type'),
          jsx(WorldPlate, {
            artifactId: hero ? hero.artifact_id : null,
            caption: CB_WORLD_COPY.hero,
            height: '8.5rem',
            kind: 'hero'
          }, 'hero')
        ]
      }, 'hero'),
      sectionPlates.length
        ? jsx('div', {
            'data-cb-world-route': '',
            role: 'list',
            style: {
              display: 'grid',
              gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(min(100%, 12rem), 1fr))',
              gap: '0.6rem',
              minWidth: 0
            },
            children: sectionPlates.map((plate) => {
              const card = jsxs('span', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0, width: '100%', textAlign: 'left', font: 'inherit' },
                children: [
                  jsx(WorldPlate, { artifactId: plate.artifact_id, caption: plate.title || plate.section_key, height: '6.5rem', kind: 'section' }),
                  jsx('span', {
                    'data-cb-world-section-title': plate.section_id,
                    style: { fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('body'), fontWeight: 600, color: 'var(--cb3-ink)', lineHeight: cb3Lead('body') },
                    children: plate.title || 'Section'
                  })
                ]
              })
              if (!onOpenSection) {
                return jsx('div', { role: 'listitem', 'data-cb-world-section': plate.section_id, style: { minWidth: 0 } }, plate.section_id)
              }
              return jsx('button', {
                type: 'button',
                role: 'listitem',
                'data-cb-world-section': plate.section_id,
                onClick: () => onOpenSection(plate.section_id),
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.3rem',
                  minWidth: 0,
                  padding: 0,
                  border: 'none',
                  background: 'transparent',
                  color: 'inherit',
                  cursor: 'pointer',
                  textAlign: 'left',
                  font: 'inherit'
                },
                children: card
              }, plate.section_id)
            })
          })
        : null
    ]
  })
}

/**
 * The World Studio. It is a step in a course's setup, never a top-level destination, and every
 * state has exactly one primary action. It never renders generated text: the concept `label` is
 * the policy's authored grammar word, the palette chips are swatches only, and a plate is art.
 */
function WorldStudio({ courseId, mode, world, worldStatus, worldError, onReload, onClose, onChanged, autoStart }) {
  const [busy, setBusy] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [direction, setDirection] = useState({ tone: '', audience: '', include: '', avoid: '' })
  const [editing, setEditing] = useState(false)
  const [reasonOpen, setReasonOpen] = useState(false)
  const width = useCbViewportWidth()
  const narrow = width > 0 && width < 720
  const state = (world && world.state) || 'not_requested'
  const revision = world ? world.revision : 0
  const missing = cbWorldMissingRoles(world)
  const providerUnavailable = Boolean(
    world && (state === 'unavailable' || (world.error && world.error.reason === 'provider_unavailable'))
  )

  // A generation is a real media job. Poll its own state; on a terminal answer re-read the world
  // instead of guessing what was produced.
  useEffect(() => {
    if (!jobId) return undefined
    let live = true
    let tries = 0
    const poll = async () => {
      tries += 1
      const response = await rpc('jobs.get', { job_id: jobId })
      if (!live) return
      const row = response && response.ok && response.result ? response.result.job : null
      if (!row) return
      setJob(row)
      const finished = ['succeeded', 'done', 'failed', 'cancelled', 'interrupted_requires_retry'].includes(row.state)
      if (!finished && tries < 120) return
      setJobId(null)
      setBusy(null)
      if (row.state === 'failed' || row.state === 'cancelled') {
        setError({
          code: 'WORLD_JOB_' + String(row.state).toUpperCase(),
          message: (row.error && (row.error.message || row.error.reason)) || 'The world job did not finish.'
        })
      }
      onReload()
    }
    const handle = setInterval(poll, 1200)
    poll()
    return () => {
      live = false
      clearInterval(handle)
    }
  }, [jobId])

  const patch = useCallback(() => {
    const value = {}
    if (direction.tone.trim()) value.tone = direction.tone.trim()
    if (direction.audience.trim()) value.audience = direction.audience.trim()
    const motifs = direction.include.split(',').map((item) => item.trim()).filter(Boolean).slice(0, 6)
    const forbidden = direction.avoid.split(',').map((item) => item.trim()).filter(Boolean).slice(0, 6)
    if (motifs.length) value.motifs = motifs
    if (forbidden.length) value.forbidden = forbidden
    return Object.keys(value).length ? value : null
  }, [direction])

  const generate = useCallback(async (stage, extra) => {
    if (busy) return
    setError(null)
    setBusy(stage)
    const payload = { course_id: courseId, stage, ...extra }
    const response = await rpc('world.generate', payload, {
      idempotencyKey: `cb-world-${stage}-${newOperationId('world')}`,
      expectedRevision: revision
    })
    if (!response || !response.ok) {
      setBusy(null)
      setError({
        code: (response && response.error && response.error.code) || 'HOST_UNAVAILABLE',
        message: describeError(response && response.error)
      })
      onReload()
      return
    }
    setJobId(response.result.job_id)
    setJob({ state: response.result.state, progress: { message: 'Queued' } })
    onReload()
  }, [busy, courseId, onReload, revision])

  const approveStyle = useCallback(async (concept) => {
    if (busy) return
    setError(null)
    setBusy('style')
    const response = await rpc('world.approve', {
      course_id: courseId,
      world_id: world.world_id,
      stage: 'style',
      approved_hash: concept.style_hash
    }, {
      idempotencyKey: `cb-world-style-${newOperationId('world')}`,
      expectedRevision: revision
    })
    setBusy(null)
    if (!response || !response.ok) {
      setError({ code: (response && response.error && response.error.code) || 'HOST_UNAVAILABLE', message: describeError(response && response.error) })
    }
    onReload()
  }, [busy, courseId, onReload, revision, world])

  const approveFinal = useCallback(async () => {
    if (busy) return
    setError(null)
    setBusy('final')
    const approved = await rpc('world.approve', {
      course_id: courseId,
      world_id: world.world_id,
      stage: 'final',
      approved_hash: world.kit_hash
    }, {
      idempotencyKey: `cb-world-final-${newOperationId('world')}`,
      expectedRevision: revision
    })
    if (!approved || !approved.ok) {
      setBusy(null)
      setError({ code: (approved && approved.error && approved.error.code) || 'HOST_UNAVAILABLE', message: describeError(approved && approved.error) })
      onReload()
      return
    }
    // Final visual approval is the gate: the same press is what lets the course enter Game mode.
    if (mode !== 'game') {
      const nextRevision = (approved.result.world && approved.result.world.revision) || revision + 1
      const switched = await rpc('course.mode.set', { course_id: courseId, mode: 'game' }, {
        idempotencyKey: `cb-mode-game-${newOperationId('world')}`,
        expectedRevision: nextRevision
      })
      if (!switched || !switched.ok) {
        setBusy(null)
        setError({
          code: (switched && switched.error && switched.error.code) || 'HOST_UNAVAILABLE',
          message:
            'The world is approved, but the course could not switch to Game mode: ' +
            describeError(switched && switched.error)
        })
        onReload()
        if (onChanged) onChanged()
        return
      }
    }
    setBusy(null)
    if (onChanged) onChanged()
    onReload()
  }, [busy, courseId, mode, onChanged, onReload, revision, world])

  const concepts = (world && Array.isArray(world.concepts)) ? world.concepts : []
  const sectionPlates = cbWorldSectionPlates(world)
  const hero = cbWorldPlate(world && world.assets, 'hero')
  const cover = cbWorldPlate(world && world.assets, 'cover')

  // The Textbook → Game prompt promises generation, so arriving from that dialog starts the
  // concept job once. It is not a background job: the learner is on the screen that shows it.
  useEffect(() => {
    if (!autoStart) return
    if (worldStatus !== 'ready') return
    if (state !== 'not_requested' || busy || jobId) return
    generate('concepts', { brief_patch: patch() })
    // Only the first mount of an untouched world starts a job.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, worldStatus, state])

  if (worldStatus === 'unsupported') {
    return jsx(WorldStudioFrame, {
      onClose,
      state: 'unsupported',
      children: jsx(PaperCard, {
        title: 'This backend does not carry the world wire yet',
        meta: CB_WORLD_COPY.readUnsupported + ' Your course stays in Textbook mode and no art is generated.',
        footer: jsx(PillAction, { variant: 'primary', label: 'Keep Textbook', onClick: onClose })
      })
    })
  }
  if (worldStatus === 'error') {
    return jsx(WorldStudioFrame, {
      onClose,
      state: 'error',
      children: jsx(PaperCard, {
        title: 'The course world could not be read',
        meta: describeError(worldError),
        footer: jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', gap: '0.5rem' },
          children: [
            jsx(PillAction, { variant: 'primary', label: 'Try again', onClick: onReload }, 'retry'),
            jsx(PillAction, { variant: 'quiet', label: 'Back to the course', onClick: onClose }, 'back')
          ]
        })
      })
    })
  }
  if (worldStatus === 'loading' && !world) {
    return jsx(WorldStudioFrame, {
      onClose,
      state: 'loading',
      children: jsxs('div', {
        'data-cb-world-loading': '',
        role: 'status',
        'aria-live': 'polite',
        style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', padding: '1.5rem 0' },
        children: [
          jsx('p', { style: { margin: 0, fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('lead'), lineHeight: cb3Lead('lead'), color: 'var(--cb3-ink)' }, children: 'Reading the course world' }),
          jsx('p', { style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)' }, children: 'Nothing already saved is lost.' })
        ]
      })
    })
  }

  const generating = Boolean(jobId) || state === 'concepts_generating' || state === 'kit_generating'
  const stageMessage = (job && job.progress && job.progress.message) || cbWorldStateWord(state)

  const body = []
  body.push(jsxs('div', {
    'data-cb-world-studio-head': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: [
      jsx('h2', {
        id: 'cb-world-studio-title',
        style: { margin: 0, fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('heading'), lineHeight: cb3Lead('heading'), fontWeight: 600, color: 'var(--cb3-ink)' },
        children: 'Choose the world for this course'
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
        children: [
          jsx(ModeBadge, { mode }),
          jsx('span', {
            style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)' },
            children: CB_WORLD_COPY.label
          })
        ]
      }),
      jsx('p', {
        style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)', maxWidth: '58ch' },
        children: (world && world.brief && world.brief.end_capability) || 'The world is orientation art. Your lessons, checks and evidence are unchanged by it.'
      })
    ]
  }, 'head'))

  if (error) {
    body.push(jsxs('div', {
      'data-cb-world-error': error.code || 'ERROR',
      role: 'alert',
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.35rem',
        padding: '0.75rem 0.85rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round'),
        minWidth: 0
      },
      children: [
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-alert)' }, children: 'That did not finish' }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink)' }, children: error.message })
      ]
    }, 'error'))
  }

  if (providerUnavailable) {
    body.push(jsxs('div', {
      'data-cb-world-provider': 'unavailable',
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        padding: '0.75rem 0.85rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round'),
        minWidth: 0
      },
      children: [
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: 'Game mode is unavailable because image generation is not configured.' }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)' }, children: 'The course stays in Textbook mode and your lessons are unchanged. No fake world is created.' })
      ]
    }, 'provider'))
  }

  if (state === 'failed' && missing.length) {
    body.push(jsxs('div', {
      'data-cb-world-partial': missing.join(','),
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        padding: '0.75rem 0.85rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round'),
        minWidth: 0
      },
      children: [
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: 'Some plates are missing' }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink-soft)' }, children: `Missing: ${missing.join(', ')}. Nothing is approved until every role exists, and no placeholder art is saved.` })
      ]
    }, 'partial'))
  }

  // Three directions, or the chosen one. Boards are art plus an authored name and a palette strip.
  if ((state === 'concepts_ready' || state === 'style_selected') && concepts.length) {
    body.push(jsx('div', {
      'data-cb-world-concepts': String(concepts.length),
      role: 'list',
      style: {
        display: 'grid',
        gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(min(100%, 15rem), 1fr))',
        gap: '0.7rem',
        minWidth: 0
      },
      children: concepts.map((concept) => {
        const selected = world.selected_concept_id === concept.style_id
        const grammar = String(concept.style_id).split('--').pop()
        const name = CB_GRAMMAR_NAME[concept.label] || CB_GRAMMAR_NAME[grammar] || 'Direction'
        const one = CB_GRAMMAR_ONE_LINE[concept.label] || CB_GRAMMAR_ONE_LINE[grammar] || ''
        return jsxs('div', {
          role: 'listitem',
          'data-cb-world-concept': concept.style_id,
          'data-cb-world-concept-selected': selected ? 'true' : 'false',
          'data-cb3-card': 'paper',
          style: {
            display: 'flex',
            flexDirection: 'column',
            gap: '0.4rem',
            padding: '0.65rem',
            minWidth: 0,
            background: 'var(--cb3-card-stock)',
            border: selected ? '2px solid var(--cb3-terracotta)' : '1px solid var(--cb3-rule)',
            borderRadius: cb3Radius('round')
          },
          children: [
            jsx(WorldPlate, { artifactId: concept.artifact_id, caption: name, height: '8rem', kind: 'concept' }),
            jsx('span', { style: { fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('lead'), lineHeight: cb3Lead('lead'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: name }),
            one ? jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: one }) : null,
            jsxs('span', {
              'data-cb-world-palette': concept.style_id,
              'aria-hidden': 'true',
              style: { display: 'flex', gap: '0.2rem' },
              children: (concept.palette || []).slice(0, 5).map((swatch, index) => jsx('span', {
                style: { width: '1rem', height: '0.75rem', background: swatch, border: '1px solid var(--cb3-rule)', borderRadius: cb3Radius('square') }
              }, String(index)))
            }),
            selected
              ? jsx('span', { 'data-cb-world-chosen': '', style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: 'Chosen direction' })
              : jsx('div', {
                  'data-cb-world-use-direction': concept.style_id,
                  'data-cb-world-primary': concept.style_id === (concepts[0] && concepts[0].style_id) ? 'direction' : undefined,
                  style: { display: 'inline-flex' },
                  children: jsx(PillAction, {
                    variant: concept.style_id === (concepts[0] && concepts[0].style_id) ? 'primary' : 'quiet',
                    label: 'Use this direction',
                    disabled: Boolean(busy),
                    onClick: () => approveStyle(concept)
                  })
                })
          ]
        }, concept.style_id)
      })
    }, 'concepts'))
  }

  if (state === 'kit_ready' && world.kit_hash) {
    body.push(jsxs('div', {
      'data-cb-world-kit': world.kit_hash,
      style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0 },
      children: [
        jsxs('div', {
          style: {
            display: 'grid',
            gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'minmax(0, 1fr) 11rem',
            gap: '0.7rem',
            padding: '0.85rem 0.95rem',
            background: 'var(--cb3-card-stock)',
            border: '1px solid var(--cb3-rule)',
            borderRadius: cb3Radius('round'),
            minWidth: 0
          },
          children: [
            jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', justifyContent: 'center', minWidth: 0 },
              children: [
                jsx('span', { style: { fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('heading'), lineHeight: cb3Lead('heading'), fontWeight: 600, color: 'var(--cb3-ink)', overflowWrap: 'anywhere' }, children: (world.brief && world.brief.title) || 'This course' }),
                jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: 'The world you would get' }),
                jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: `1 hero · 1 cover · ${sectionPlates.length} section ${sectionPlates.length === 1 ? 'card' : 'cards'}` })
              ]
            }),
            jsx(WorldPlate, { artifactId: cover ? cover.artifact_id : null, caption: 'Library cover', height: '7rem', kind: 'cover' })
          ]
        }),
        jsx('div', {
          style: { display: 'grid', gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'repeat(auto-fit, minmax(min(100%, 9rem), 1fr))', gap: '0.5rem', minWidth: 0 },
          children: sectionPlates.map((plate) => jsx(WorldPlate, {
            artifactId: plate.artifact_id,
            caption: plate.title || 'Section card',
            height: '5.5rem',
            kind: 'section'
          }, plate.section_id))
        }),
        jsx('p', {
          style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)', maxWidth: '58ch' },
          children: mode === 'game'
            ? 'Use this world and the course opens on it. This is the final visual approval; you can review it again from Course settings.'
            : 'Use this world to approve the kit and switch this course to Game mode. Your lessons, checks and evidence do not change.'
        })
      ]
    }, 'kit'))
  }

  if (state === 'approved') {
    body.push(jsxs('div', {
      'data-cb-world-approved-panel': world.approved_hash,
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        padding: '0.8rem 0.9rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round'),
        minWidth: 0
      },
      children: [
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: 'This world is approved.' }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: 'Changing it starts a new direction and leaves this approved kit on the course until you approve another.' })
      ]
    }, 'approved'))
  }

  // Edit direction: presentation-only fields, exactly the closed patch the backend accepts.
  body.push(jsxs('div', {
    'data-cb-world-direction': editing ? 'open' : 'closed',
    style: { display: 'flex', flexDirection: 'column', gap: '0.45rem', borderTop: '1px solid var(--cb3-rule)', paddingTop: '0.6rem', minWidth: 0 },
    children: [
      jsx('button', {
        type: 'button',
        'data-cb-world-direction-toggle': '',
        onClick: () => setEditing((value) => !value),
        style: { alignSelf: 'flex-start', background: 'none', border: 'none', padding: 0, font: 'inherit', fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-terracotta)', cursor: 'pointer', textDecoration: 'underline' },
        children: editing ? 'Close the direction' : 'Edit direction'
      }),
      editing
        ? jsxs('div', {
            style: { display: 'grid', gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'repeat(2, minmax(0, 1fr))', gap: '0.5rem', minWidth: 0 },
            children: [
              worldField('Mood', 'cb-world-tone', direction.tone, (value) => setDirection((current) => ({ ...current, tone: value })), 'e.g. calm, practical'),
              worldField('Who it is for', 'cb-world-audience', direction.audience, (value) => setDirection((current) => ({ ...current, audience: value })), 'e.g. adult learner'),
              worldField('Motifs to include', 'cb-world-include', direction.include, (value) => setDirection((current) => ({ ...current, include: value })), 'comma separated'),
              worldField('Motifs to avoid', 'cb-world-avoid', direction.avoid, (value) => setDirection((current) => ({ ...current, avoid: value })), 'comma separated')
            ]
          }, 'fields')
        : null,
      editing
        ? jsx('p', {
            style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' },
            children: 'These words steer the next generation only. They never edit a lesson, a check or a source.'
          })
        : null
    ]
  }, 'direction'))

  if (reasonOpen) {
    body.push(jsxs('div', {
      'data-cb-world-reason': '',
      style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', padding: '0.6rem 0.75rem', background: 'var(--cb3-card-stock)', border: '1px solid var(--cb3-rule)', minWidth: 0 },
      children: [
        jsx('label', {
          htmlFor: 'cb-world-reason-input',
          style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), fontWeight: 600, color: 'var(--cb3-ink)' },
          children: 'What should change?'
        }),
        jsx(sdk.Input, {
          id: 'cb-world-reason-input',
          value: direction.motifsNote || '',
          onChange: (event) => setDirection((current) => ({ ...current, motifsNote: event.target.value })),
          placeholder: 'e.g. warmer light, fewer props'
        }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: 'The reason is used as mood text for the next set. It is not shown to the image model as a scene description.' })
      ]
    }, 'reason'))
  }

  // One primary action per state. The footer says what it needs next.
  const primary = buildWorldPrimary({ state, busy, generating, providerUnavailable, hasStyles: concepts.length > 0, approved: cbWorldApproved(world), mode })
  body.push(jsxs('div', {
    'data-cb-world-actions': state,
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', paddingTop: '0.2rem', minWidth: 0 },
    children: [
      primary
        ? jsx('div', {
            'data-cb-world-primary': primary.id,
            style: { display: 'inline-flex' },
            children: jsx(PillAction, {
              variant: 'primary',
              disabled: Boolean(busy) || primary.disabled,
              busy: Boolean(busy) && primary.id === busy,
              onClick: () => {
                if (primary.id === 'concepts') generate('concepts', { brief_patch: patch() })
                else if (primary.id === 'retry-concepts') generate('concepts', { brief_patch: patch() })
                else if (primary.id === 'kit') generate('kit', { style_id: world.selected_concept_id })
                else if (primary.id === 'retry-kit') generate('kit', { style_id: world.selected_concept_id })
                else if (primary.id === 'approve') approveFinal()
                else if (primary.id === 'change') { onReload(); if (onChanged) onChanged() }
              },
              children: primary.label
            })
          }, 'primary')
        : null,
      (state === 'concepts_ready')
        ? jsx('div', {
            'data-cb-world-another': '',
            style: { display: 'inline-flex' },
            children: jsx(PillAction, { variant: 'quiet', disabled: Boolean(busy), onClick: () => generate('concepts', { brief_patch: patch() }), children: 'Try another set' })
          }, 'another')
        : null,
      jsx(PillAction, { variant: 'quiet', 'data-cb-world-textbook': '', onClick: onClose, children: 'Use Textbook mode' }),
      jsx(PillAction, { variant: 'quiet', 'data-cb-world-cancel': '', onClick: onClose, children: 'Cancel' })
    ]
  }, 'actions'))

  if (generating) {
    body.push(jsxs('div', {
      'data-cb-world-progress': (job && job.state) || state,
      role: 'status',
      'aria-live': 'polite',
      style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
      children: [
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: cbWorldStateWord(state) }),
        jsx('span', { style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), lineHeight: cb3Lead('caption'), color: 'var(--cb3-ink-soft)' }, children: `${stageMessage} — you can leave this open or cancel. No lesson is built until the world is approved.` })
      ]
    }, 'progress'))
  }

  return jsx(WorldStudioFrame, { onClose, state, children: body })
}

function worldField(label, id, value, onChange, placeholder) {
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
    children: [
      jsx('label', { htmlFor: id, style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), fontWeight: 600, color: 'var(--cb3-ink)' }, children: label }),
      jsx(sdk.Input, { id, value, onChange: (event) => onChange(event.target.value), placeholder })
    ]
  }, id)
}

function buildWorldPrimary({ state, busy, generating, providerUnavailable, hasStyles, approved }) {
  if (generating) return { id: 'wait', label: 'Working…', disabled: true }
  if (providerUnavailable) return { id: 'retry-concepts', label: 'Try again' }
  if (state === 'not_requested') return { id: 'concepts', label: 'Show me three directions' }
  if (state === 'concepts_ready') return null
  if (state === 'style_selected') return { id: 'kit', label: 'Build this world' }
  if (state === 'kit_ready') return { id: 'approve', label: 'Use this world' }
  if (state === 'approved') return { id: 'change', label: 'Change world' }
  if (state === 'failed') return hasStyles ? { id: 'retry-kit', label: 'Retry the missing plates' } : { id: 'retry-concepts', label: 'Try the directions again' }
  if (state === 'unavailable') return { id: 'retry-concepts', label: 'Try again' }
  return { id: 'concepts', label: 'Show me three directions' }
}

function WorldStudioFrame({ state, onClose, children }) {
  return jsx('div', {
    'data-cb-world-studio-backdrop': '',
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 60,
      display: 'flex',
      justifyContent: 'flex-end',
      background: 'color-mix(in srgb, var(--cb3-forest) 42%, transparent)'
    },
    onMouseDown: (event) => {
      if (event && event.target === event.currentTarget) onClose()
    },
    children: jsxs('div', {
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'cb-world-studio-title',
      'data-cb-world-studio': state,
      style: {
        width: '46rem',
        maxWidth: '100%',
        height: '100%',
        overflowY: 'auto',
        background: 'var(--cb3-canvas)',
        color: 'var(--cb3-ink)',
        borderLeft: '1px solid var(--cb3-rule)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        padding: '0.85rem 1rem 1.25rem'
      },
      children: [
        jsx('div', {
          style: { display: 'flex', justifyContent: 'flex-end' },
          children: jsx(PillAction, {
            variant: 'quiet',
            label: 'Close',
            'data-cb-world-studio-close': '',
            'aria-label': 'Close the World Studio',
            onClick: onClose
          })
        }),
        ...(Array.isArray(children) ? children : [children])
      ]
    })
  })
}

/**
 * The Textbook → Game prompt. One decision, three plain answers, and the provider-unavailable
 * case says exactly what is preserved instead of offering a world it cannot make.
 */
function ModeSwitchDialog({ mode, world, pending, providerUnavailable, onGenerate, onOpenStudio, onSwitch, onKeep, onCancel }) {
  const state = (world && world.state) || 'not_requested'
  const approved = cbWorldApproved(world)
  const unapproved = state !== 'not_requested' && !approved
  let title = ''
  let body = ''
  let primaryLabel = ''
  let primaryId = ''
  if (providerUnavailable) {
    title = 'Game mode is not available right now'
    body = 'Game mode is not available right now because the image provider is not configured. The course stays in Textbook mode and your lessons are unchanged.'
    primaryLabel = 'Keep Textbook'
    primaryId = 'keep'
  } else if (approved) {
    title = 'This course already has a world.'
    body = 'Switch to Game mode? The approved world is reused; no art is generated.'
    primaryLabel = 'Switch to Game mode'
    primaryId = 'switch'
  } else if (unapproved) {
    title = 'A world is not approved yet.'
    body = 'This course has a world in progress. It stays in Textbook mode until you approve the final kit.'
    primaryLabel = 'Open World Studio'
    primaryId = 'studio'
  } else {
    // Card copy is literal: `Game mode is not available yet. Generate a game world?` with
    // Studio/Cancel. Studio opens the World Studio and starts the three directions there.
    title = 'Game mode is not available yet. Generate a game world?'
    body = 'This course was built in Textbook mode. The World Studio shows three art directions, then builds the kit, then asks for your final approval. Your plan, lessons, checks and evidence stay exactly as they are.'
    primaryLabel = 'Studio'
    primaryId = 'generate'
  }
  return jsx('div', {
    'data-cb-mode-dialog': primaryId,
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 70,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      background: 'color-mix(in srgb, var(--cb3-forest) 46%, transparent)'
    },
    onMouseDown: (event) => {
      if (event && event.target === event.currentTarget) onCancel()
    },
    children: jsxs('div', {
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'cb-mode-dialog-title',
      style: {
        width: '30rem',
        maxWidth: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem',
        padding: '1rem 1.1rem 1.1rem',
        background: 'var(--cb3-card-stock)',
        border: '1px solid var(--cb3-rule)',
        borderRadius: cb3Radius('round')
      },
      children: [
        jsx('h2', {
          id: 'cb-mode-dialog-title',
          style: { margin: 0, fontFamily: 'var(--cb3-font-display)', fontSize: cb3Type('heading'), lineHeight: cb3Lead('heading'), fontWeight: 600, color: 'var(--cb3-ink)' },
          children: title
        }),
        jsx('p', {
          'data-cb-mode-dialog-body': '',
          style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: cb3Lead('meta'), color: 'var(--cb3-ink)', maxWidth: '54ch' },
          children: body
        }),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem', paddingTop: '0.2rem' },
          children: [
            jsx('div', {
              'data-cb-mode-primary': primaryId,
              style: { display: 'inline-flex' },
              children: jsx(PillAction, {
                variant: 'primary',
                busy: Boolean(pending),
                onClick: () => {
                  if (primaryId === 'switch') onSwitch()
                  else if (primaryId === 'studio') onOpenStudio()
                  else if (primaryId === 'keep') onKeep()
                  else onGenerate()
                },
                children: primaryLabel
              })
            }),
            primaryId === 'keep' || primaryId === 'generate'
              ? null
              : jsx(PillAction, { variant: 'quiet', 'data-cb-mode-keep': '', onClick: onKeep, children: 'Keep Textbook' }),
            jsx(PillAction, { variant: 'quiet', 'data-cb-mode-cancel': '', onClick: onCancel, children: 'Cancel' })
          ]
        })
      ]
    })
  })
}

