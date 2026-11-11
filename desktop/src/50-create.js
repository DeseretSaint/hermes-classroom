// ── learner create → plan job → plan review ────────────────────────────────
//
// H-02: `course.create` + `enrollment.create` used to be the whole learner flow, and the screen
// told the learner that generation was not wired. It is wired: the executor pumps `plan` jobs, the
// plan pipeline writes a draft plan, and `plan.approve` fences on the kernel digest. This block is
// the one place the desktop builds those payloads.

/**
 * How much course a brief asks for. Contract enum: `single` | `short` | `full`.
 *
 * H-179 — the learner chooses a journey, not a scope label. Each row carries the shape's name, a
 * one-line consequence, and the two numbers that are actually enforced:
 *
 *   sections  `coursebook/generation.py` authors one section per blueprint objective, so the
 *             section band is `SCOPE_EXPECTATIONS[key]["blueprint_objectives"]`: (1,1), (3,6),
 *             (12,40). `tests/test_desktop_create_flow` re-reads that Python table and refuses
 *             drift, so this is a checked copy rather than a second authority.
 *   trail     how many stops the card's schematic draws. It is the band's floor, capped at six so
 *             the miniature stays a trail; `full` carries a dashed tail because its band is open.
 *
 * The research floor is not duplicated here: `SCOPE_MIN_DEPTH` below is the same table
 * `coursebook.research.effective_depth()` applies.
 */
const COURSE_SCOPES = [
  {
    id: 'single',
    label: 'One lesson',
    sections: [1, 1],
    trail: 1,
    consequence: 'One stop: a single section with one check, for a task in front of you today.'
  },
  {
    id: 'short',
    label: 'Short course',
    sections: [3, 6],
    trail: 3,
    consequence: 'A few stops that build on each other, each with its own check.'
  },
  {
    id: 'full',
    label: 'Full course',
    sections: [12, 40],
    trail: 6,
    consequence: 'A long trail split into units, planned in full before a lesson is written.'
  }
]

/** The section count as the backend states it: an exact number or the band it enforces. */
function scopeSectionBand(scope) {
  const found = COURSE_SCOPES.find((option) => option.id === scope)
  if (!found) return ''
  const [low, high] = found.sections
  return low === high ? plural(low, 'section', 'sections') : `${low}–${high} sections`
}

/** One card's facts: the sections the plan will author and the research depth it will run. */
function scopeFacts(scope) {
  const band = scopeSectionBand(scope)
  if (!band) return ''
  return `${band} · ${dialLabel('depth', SCOPE_MIN_DEPTH[scope])} research depth · several minutes`
}

/**
 * The small trail a shape card carries (H-179). Same route language as the path: one line, stops
 * left to right, the first stop marked. It is decorative and `aria-hidden`; the band beside it is
 * the number a learner can hold the backend to, and the dashed tail only appears where the band
 * is open, so the miniature never claims a fixed length the plan does not promise.
 */
function CbShapeTrail({ scope, height }) {
  const found = COURSE_SCOPES.find((option) => option.id === scope)
  const stops = found ? found.trail : 3
  const open = stops > 1
  const bend = scope === 'full' ? 2 : 1
  const points = []
  for (let index = 0; index < stops; index += 1) {
    const t = stops === 1 ? 0.35 : index / (stops - 1)
    points.push({
      x: 6 + t * (open ? 96 : 108),
      y: 22 - Math.sin(t * Math.PI * bend) * (scope === 'single' ? 4 : 7)
    })
  }
  const last = points[points.length - 1]
  const line = points.map((point, index) => `${index === 0 ? 'M' : 'L'}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ')
  return jsxs('svg', {
    'data-cb-scope-trail': scope || '',
    'aria-hidden': 'true',
    focusable: 'false',
    viewBox: '0 0 120 40',
    preserveAspectRatio: 'none',
    style: { display: 'block', width: '100%', height: `${Number(height) || 40}px`, overflow: 'hidden' },
    children: [
      jsx('path', {
        d: line,
        fill: 'none',
        stroke: 'var(--cb-ink-soft)',
        strokeWidth: '1.5',
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        opacity: 0.6
      }, 'line'),
      open
        ? jsx('path', {
            d: `M${last.x.toFixed(1)} ${last.y.toFixed(1)} L116 ${last.y.toFixed(1)}`,
            fill: 'none',
            stroke: 'var(--cb-rule)',
            strokeWidth: '1.5',
            strokeDasharray: '2 3',
            strokeLinecap: 'round'
          }, 'tail')
        : null,
      ...points.map((point, index) =>
        jsx('circle', {
          cx: point.x.toFixed(1),
          cy: point.y.toFixed(1),
          r: index === 0 ? 4 : 3,
          fill: index === 0 ? 'var(--cb-lamp)' : 'var(--cb-paper)',
          stroke: index === 0 ? 'var(--cb-lamp)' : 'var(--cb-ink-soft)',
          strokeWidth: '1.5'
        }, `stop-${index}`)
      )
    ]
  })
}

/**
 * H-179: the four learner uses, as one segmented choice instead of a stack of rows. Labels are
 * short enough for the track at a 460px route; the plain consequence underneath is the recipe's
 * own description from `RECIPE_COPY`, so the control adds no second copy authority and the words
 * "recipe" and "dials" never reach the screen. `parent` is not a learner choice: Parent Studio is
 * a separate entry on the rail.
 */
const CB_USE_OPTIONS = Object.freeze([
  { id: 'one_off', label: 'One task' },
  { id: 'casual', label: 'Little at a time' },
  { id: 'committed', label: 'A steady plan' },
  { id: 'companion', label: 'Alongside study' }
])

/**
 * Honest time expectation per scope. No invented minutes: a plan has no `time_estimate` until it
 * exists, and no read in this contract serves one, so this says what is true before the run starts.
 */
const SCOPE_TIME_COPY = {
  single: 'One lesson. Research and drafting may take several minutes; there is no progress percentage until the plan exists.',
  short: 'A short course of a few sessions. Research and drafting may take several minutes.',
  full: 'A full course. Research and drafting may take several minutes and run longest; the plan carries its own estimate once it exists.'
}

function planTimingCopy(scope) {
  return SCOPE_TIME_COPY[scope] || 'Research and drafting may take several minutes. A plan is written before any lesson exists.'
}

/**
 * A neutral goal gallery (H-100). The default form is a general harness, not a single-topic demo:
 * one language, one practical skill, one academic concept and one everyday skill, so a new learner
 * sees four different shapes of course in one glance.
 *
 * These are examples, never defaults. They appear as buttons and a greyed placeholder only; nothing
 * reaches the goal or title field until the learner presses one or types their own words.
 */
const GOAL_EXAMPLES = [
  { domain: 'Language', text: 'Hold a six-minute conversation in Spanish' },
  { domain: 'Skill', text: 'Wire a lamp safely' },
  { domain: 'Concept', text: 'Understand the first month of a statistics class' },
  { domain: 'Everyday', text: 'Read a nutrition label for added sugar' }
]
const GOAL_PLACEHOLDER = 'e.g. Hold a six-minute conversation in Spanish'
const TITLE_PLACEHOLDER = 'e.g. Six-minute Spanish conversation'

/**
 * The examples, labelled as examples and inert until chosen. Pressing one fills the goal field the
 * learner can still edit; it never submits the form or starts a job.
 */
function GoalGallery({ examples, onChoose }) {
  const rows = examples || GOAL_EXAMPLES
  return jsxs('div', {
    'data-cb-goal-examples': '',
    className: 'flex flex-col gap-1.5',
    children: [
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        id: 'cb-goal-examples-label',
        children: 'Examples — press one to start from it, or write your own:'
      }),
      jsx('div', {
        'aria-labelledby': 'cb-goal-examples-label',
        className: 'flex flex-wrap gap-1.5',
        role: 'group',
        children: rows.map((example) =>
          jsxs(
            sdk.Button,
            {
              'aria-label': `${example.text} — ${example.domain} example`,
              className: 'max-w-full text-left',
              onClick: () => onChoose && onChoose(example.text),
              size: 'sm',
              variant: 'outline',
              children: [
                jsx('span', { className: 'whitespace-normal text-(--ui-text-secondary)', children: `${example.domain}: ` }),
                jsx('span', { className: 'whitespace-normal', children: example.text })
              ]
            },
            example.text
          )
        )
      })
    ]
  })
}

/** The create result speaks before the receipt does (UX-03). */
const CREATE_RESULT_COPY = {
  lead: 'Your plan is being researched; this may take several minutes and you can leave this page.',
  body: 'When it arrives it opens here. Approve the plan to start the first lesson; no lesson is written before that.',
  details: 'Technical detail'
}

/** Dials are chosen as enum ids; the review panel shows the label the learner actually picked. */
function dialLabel(dial, value) {
  const options = (DIALS[dial] && DIALS[dial].options) || []
  const found = options.find((option) => option.id === value)
  return found ? found.label : value
}

/**
 * The exact `jobs.create` brief for a learner plan job (cb.rpc v10 `plan_brief`).
 *
 * Every declared input travels: ids and stage so a retry can resume, goal/recipe/dials/locale and
 * the v10 capability inputs (level, subject_domain, scope) so the policy and the planner read the
 * same decision the course row stores. Absent inputs are omitted, never sent as empty strings.
 */
function planJobBrief(input) {
  const brief = {
    stage: 'plan',
    course_id: input.courseId,
    enrollment_id: input.enrollmentId,
    goal: input.goal,
    recipe: input.recipe,
    dials: input.dials || {}
  }
  if (input.locale) brief.locale = input.locale
  if (input.level) brief.level = input.level
  if (input.subjectDomain) brief.subject_domain = input.subjectDomain
  if (input.scope) brief.scope = input.scope
  return brief
}

/** The `course.create` payload for the same decision. Only contract fields, nothing extra. */
function courseCreatePayload(input) {
  const payload = { title: input.title, recipe: input.recipe, goal: input.goal, dials: input.dials || {} }
  if (input.locale) payload.locale = input.locale
  if (input.level) payload.level = input.level
  if (input.subjectDomain) payload.subject_domain = input.subjectDomain
  if (input.scope) payload.scope = input.scope
  // GM-004: Game is the default intent; Textbook is an explicit choice. The value is creation
  // intent only — the course still needs an approved world before any Game lesson is built.
  if (input.presentationMode === 'textbook') payload.presentation_mode = 'textbook'
  else payload.presentation_mode = 'game'
  return payload
}

/**
 * One learner create: course → enrolment → one plan job, keyed so a retry replays.
 *
 * `call` is the rpc transport (`rpc` in the app), injected so a test can prove the exact sequence
 * and the idempotency keys rather than reading the source. A jobs.create failure keeps the ids it
 * already has: the course and its draft plan are real and the same key retries the same job, so the
 * draft is recoverable instead of abandoned.
 */
async function startLearnerPlan({ call, key, title, goal, recipe, dials, locale, level, subjectDomain, scope, presentationMode }) {
  const decision = { title, goal, recipe, dials, locale, level, subjectDomain, scope, presentationMode }
  const course = await call('course.create', courseCreatePayload(decision), {
    idempotencyKey: key,
    expectedRevision: null
  })
  if (!course || !course.ok) return { ok: false, stage: 'course.create', error: (course && course.error) || null }

  const courseId = course.result.course_id
  const planId = course.result.plan_id
  const enrollment = await call(
    'enrollment.create',
    { course_id: courseId, learner_label: title },
    { idempotencyKey: `${key}-enroll`, expectedRevision: null }
  )
  if (!enrollment || !enrollment.ok) {
    return {
      ok: false,
      stage: 'enrollment.create',
      error: (enrollment && enrollment.error) || null,
      courseId,
      planId
    }
  }
  const enrollmentId = enrollment.result.enrollment_id

  const job = await call(
    'jobs.create',
    { kind: 'plan', brief: planJobBrief({ courseId, enrollmentId, ...decision }) },
    { idempotencyKey: `${key}-plan` }
  )
  if (!job || !job.ok) {
    return {
      ok: false,
      stage: 'jobs.create',
      error: (job && job.error) || null,
      courseId,
      planId,
      enrollmentId
    }
  }
  return {
    ok: true,
    courseId,
    planId,
    enrollmentId,
    jobId: job.result.job_id,
    jobState: job.result.state
  }
}

/**
 * The scope a learner picks proposes how the course is used, until they choose for themselves: one
 * lesson is a task (`one_off`), a short course is casual, a full course is a steady plan. The recipe
 * stays a real contract field; this only saves the learner from decoding an enum.
 */
const SCOPE_DEFAULT_RECIPE = { single: 'one_off', short: 'casual', full: 'committed' }

/**
 * H-168 mirror: the depth a course size actually gets. `coursebook.research.effective_depth()`
 * floors the research pass by scope (single/short → working, full → deep); this is the same table
 * so the create form's default dial agrees with the pass the backend will run. It is a default
 * only — the learner can still pick a deeper pass in the tune control — and the backend remains
 * the authority that applies the floor. The payload keeps the closed four-dial object.
 */
const SCOPE_MIN_DEPTH = Object.freeze({ single: 'working', short: 'working', full: 'deep' })
const DEPTH_ORDER = Object.freeze(['survey', 'working', 'deep'])

function effectiveDepth(depth, scope) {
  const floor = SCOPE_MIN_DEPTH[scope] || 'survey'
  const declared = DEPTH_ORDER.indexOf(depth) >= 0 ? depth : 'working'
  return DEPTH_ORDER.indexOf(declared) >= DEPTH_ORDER.indexOf(floor) ? declared : floor
}

/**
 * The three steps, in the words a learner uses, each with the next thing that will happen.
 *
 * H-170: the goal is first. The first-run plate promises "name one goal, review the plan", so the
 * flow has to open on the goal field — a first-time learner should never be asked "one lesson, a
 * short course or a full course" before they have said what they want to learn. Size stays a
 * required choice on step 2 (no default is preselected) and Review still gates the single
 * mutation. H-179 renames the middle step to what it now is: the shape of the journey.
 */
const CREATE_STEP_SPINE = Object.freeze([
  { n: 1, name: 'Goal', next: 'Next: choose the shape of the course.' },
  { n: 2, name: 'Shape', next: 'Next: check the trailhead before it is created.' },
  { n: 3, name: 'Review', next: 'Create the course, then review the draft plan.' }
])

/**
 * Which step a seeded create form opens on: the first one whose answer is still missing. A rejected
 * plan's own choices are prefilled, so re-answering them is not demanded — but the form never
 * submits itself: with every answer present it opens on Review, where Create is still a press.
 */
function createStartStep(seed) {
  if (!seed) return 1
  if (!String(seed.goal || '').trim()) return 1
  if (!String(seed.scope || '').trim()) return 2
  return 3
}

/**
 * A short course name derived from the goal, so naming the course is one keystroke of work rather
 * than a second question. The learner can always edit it; the goal never changes because of it.
 * No word is invented: the name is the goal's first sentence, clamped to a list-row width.
 */
function suggestedTitle(goal) {
  const clean = String(goal || '').replace(/\s+/g, ' ').trim()
  if (!clean) return ''
  const firstClause = clean.split(/[.!?](\s|$)/)[0].trim()
  const base = firstClause || clean
  if (base.length <= 64) return base
  return `${base.slice(0, 61).trimEnd()}…`
}

/** A compact staged create flow; every step is editable before the one mutation. */
/**
 * One mode choice on the shape step. The whole card is the press target and the selected state is
 * a word, not only a fill. Game is offered first because it is the default intent.
 */
function createModeCard(mode, current, choose) {
  const selected = current === mode
  const game = mode === 'game'
  return jsx('button', {
    type: 'button',
    'aria-pressed': selected,
    'data-cb-create-mode-option': mode,
    'data-cb-create-mode-selected': selected ? 'true' : 'false',
    onClick: () => choose(mode),
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.2rem',
      minWidth: 0,
      width: '100%',
      boxSizing: 'border-box',
      padding: '0.55rem 0.7rem 0.6rem',
      textAlign: 'left',
      cursor: 'pointer',
      font: 'inherit',
      color: 'var(--cb-ink)',
      background: selected ? 'var(--cb-lamp-soft)' : 'var(--cb-paper-raised)',
      border: selected ? '2px solid var(--cb-lamp)' : '1px solid var(--cb-rule)',
      borderRadius: '2px'
    },
    children: [
      jsxs('span', {
        style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem' },
        children: [
          jsx('span', { style: { fontFamily: CB_SERIF, fontSize: CB_TYPE.lead, fontWeight: 600 }, children: game ? 'Game' : 'Textbook' }),
          jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: selected ? 'var(--cb-ink)' : 'var(--cb-ink-soft)' }, children: selected ? 'Selected' : 'Choose' })
        ]
      }),
      jsx('span', {
        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
        children: game ? 'A visual world around this course' : 'Text-first, no generated world'
      })
    ]
  }, mode)
}

function CreateCourseFlow({ onCancel, onCreated, seed }) {
  // H-103: a rejected plan can hand its goal and choices back here. The seed is a starting point,
  // never a silent submission: the learner still reviews and presses Create. H-170: it opens on the
  // first step whose answer is still missing (goal, then size, then review), so a seed that already
  // carries both answers starts at Review rather than re-asking what is known.
  const start = seed || {}
  const [step, setStep] = useState(createStartStep(seed))
  const [goal, setGoal] = useState(start.goal || '')
  const [title, setTitle] = useState(start.title || suggestedTitle(start.goal || ''))
  // H-170: the title follows the goal until the learner edits it, so naming the course costs one
  // glance instead of a second question. Once edited, it is theirs and stops following.
  const [titleEdited, setTitleEdited] = useState(Boolean(String(start.title || '').trim()))
  const [recipe, setRecipe] = useState(start.recipe || 'casual')
  // GM-004: Game is the default intent; Textbook is the explicit, plain-consequence choice. It is
  // one choice on the shape step, never a second primary action.
  const [presentationMode, setPresentationMode] = useState(
    start.presentationMode === 'textbook' ? 'textbook' : 'game'
  )
  // No scope is preselected: the size step asks a real question, so "Continue" is only enabled once
  // the learner has said whether this is one lesson, a short course or a full course (UX-09).
  const [scope, setScope] = useState(start.scope || '')
  const [recipeTouched, setRecipeTouched] = useState(Boolean(seed))
  const [level, setLevel] = useState(start.level || '')
  const [subjectDomain, setSubjectDomain] = useState(start.subjectDomain || '')
  const [locale, setLocale] = useState(start.locale || '')
  const [dials, setDials] = useState(() => {
    const base = start.dials || { pace: 'light', depth: 'working', assessment: 'self_check', autonomy: 'guided' }
    // A seeded scope raises a too-low stored depth to the floor the backend will actually run.
    return { ...base, depth: effectiveDepth(base.depth, start.scope || '') }
  })
  // H-168: the depth default follows the scope until the learner opens the tune control and picks
  // one. An explicit pick is kept, but never below the size's floor.
  const [depthTouched, setDepthTouched] = useState(Boolean(start.dials))
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  // The course/enrolment can already exist when the plan job fails. Those ids stay on screen so the
  // same key can retry the same job; the draft is never lost to a redraw.
  const [recoverable, setRecoverable] = useState(null)
  const [revision, setRevision] = useState(0)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)
  const scopeCardRefs = useRef([])
  const [focusScopeId, setFocusScopeId] = useState(null)
  // The route column, not the window: in a narrow window (a chat and the explorer open) the route
  // can be ~200px wide, where a four-option SDK track would scroll sideways. The uses fall back to
  // a 2×2 segmented block there — still one choice, still no second primary.
  const routeWidth = useCbViewportWidth()
  const narrowUses = routeWidth > 0 && routeWidth < 380

  const goalInvalid = step === 1 && goal.trim().length === 0
  // H-179: the goal alone opens the flow. The course name is suggested and optional — it lives
  // behind `Name (optional)` and can never block Continue. The shape step still needs a real
  // choice, and Review has everything, so it is never blocked by this gate.
  const canAdvance = step === 1 ? goal.trim().length > 0 : Boolean(scope)

  const changeGoal = useCallback(
    (next) => {
      const value = String(next || '')
      setGoal(value)
      if (!titleEdited) setTitle(suggestedTitle(value))
    },
    [titleEdited]
  )

  const chooseScope = useCallback(
    (id) => {
      setScope(id)
      // A one-off brief is the single-lesson shape; pairing it with a larger size is a
      // contradiction the backend refuses, so the size wins over the stale recipe.
      if (!recipeTouched || (recipe === 'one_off' && id !== 'single')) setRecipe(SCOPE_DEFAULT_RECIPE[id] || 'casual')
      // H-168: an untouched depth follows the size; an explicit one is raised to the size's floor.
      setDials((current) => {
        const next = depthTouched ? effectiveDepth(current.depth, id) : SCOPE_MIN_DEPTH[id] || current.depth
        return next === current.depth ? current : { ...current, depth: next }
      })
    },
    [depthTouched, recipeTouched]
  )
  const chooseRecipe = useCallback((id) => {
    setRecipeTouched(true)
    setRecipe(id)
  }, [])

  const submit = useCallback(async () => {
    if (submitting) return
    if (!keyRef.current) keyRef.current = `cb-course-create-${newOperationId('create')}`
    setSubmitting(true)
    setError(null)
    const outcome = await startLearnerPlan({
      call: rpc,
      key: keyRef.current,
      // The name is optional, the contract's title is not: an empty field falls back to the
      // suggestion the learner has been reading since step 1, never to an invented name.
      title: title.trim() || suggestedTitle(goal),
      goal: goal.trim(),
      // Same rule the backend applies: "One task" only survives under the single-lesson size.
      recipe: recipe === 'one_off' && scope !== 'single' ? SCOPE_DEFAULT_RECIPE[scope] || 'casual' : recipe,
      dials: { ...dials, depth: effectiveDepth(dials.depth, scope) },
      locale: locale.trim() || null,
      level: level.trim() || null,
      subjectDomain: subjectDomain.trim() || null,
      scope,
      presentationMode
    })
    setSubmitting(false)
    if (!outcome.ok) {
      if (outcome.courseId) setRecoverable(outcome)
      setError({
        code: outcome.stage,
        message:
          describeError(outcome.error) +
          (outcome.stage === 'jobs.create'
            ? ' The course and its draft plan are saved. Trying again continues the same plan; it does not create a second course.'
            : '')
      })
      return
    }
    setRecoverable(null)
    setRevision(0)
    setResult(outcome)
    onCreated(outcome)
  }, [dials, goal, level, locale, onCreated, recipe, scope, subjectDomain, submitting, title])

  const onKeyDown = useCallback(
    (event) => {
      if (event.key !== 'Escape' || event.defaultPrevented || submitting) return
      event.stopPropagation()
      if (step > 1) setStep(step - 1)
      else onCancel()
    },
    [onCancel, step, submitting]
  )

  if (result) {
    return jsxs('div', {
      className: 'mx-auto flex w-full max-w-2xl flex-col gap-3 py-4',
      children: [
        jsx('h2', { className: 'text-sm font-semibold', children: CREATE_RESULT_COPY.lead }),
        jsx('p', {
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
          children: CREATE_RESULT_COPY.body
        }),
        jsxs('details', {
          'data-cb-create-receipt': '',
          className: 'text-xs text-(--ui-text-secondary)',
          children: [
            jsx('summary', { className: 'cursor-pointer', children: CREATE_RESULT_COPY.details }),
            jsxs('div', {
              className: 'mt-1 flex flex-col',
              children: [
                jsx(StatusRow, { label: 'Course', value: result.courseId }),
                jsx(StatusRow, { label: 'Plan', value: `${result.planId} (draft)` }),
                jsx(StatusRow, { label: 'Enrolment', value: result.enrollmentId }),
                jsx(StatusRow, { label: 'Plan job', value: `${result.jobId} · ${result.jobState}` })
              ]
            })
          ]
        }),
        jsx(LearnerPlanView, {
          course: { course_id: result.courseId, enrollment_id: result.enrollmentId },
          revision,
          onRevision: setRevision,
          onOpenSection: null,
          onStartLesson: null,
          onChanged: null,
          jobHint: result.jobId,
          scopeHint: scope
        }),
        jsxs('div', {
          className: 'flex flex-wrap items-center gap-2 pt-1',
          children: [
            jsx(sdk.Button, { onClick: onCancel, variant: 'secondary', children: 'Open in Courses' }),
            jsx(sdk.Button, {
              onClick: () => {
                setResult(null)
                setRecoverable(null)
                setStep(1)
                setGoal('')
                setTitle('')
                setTitleEdited(false)
                setLevel('')
                setSubjectDomain('')
                setLocale('')
                keyRef.current = null
              },
              variant: 'text',
              children: 'Create another'
            })
          ]
        })
      ]
    })
  }

  const stepTitle =
    step === 1
      ? 'What do you want to be able to do?'
      : step === 2
        ? 'What shape should this course take?'
        : 'Your trailhead'
  // The name the learner will see: theirs if they typed one, else the suggestion from the goal.
  const displayTitle = title.trim() || suggestedTitle(goal)

  return jsxs('div', {
    className: 'mx-auto flex w-full max-w-2xl flex-col gap-4 py-2',
    onKeyDown,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'min-w-0',
            children: [
              jsx('div', {
                'data-cb-create-spine': '',
                className: 'flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-(--ui-text-secondary)',
                children: CREATE_STEP_SPINE.map((item) =>
                  jsxs(
                    'span',
                    {
                      'data-cb-create-step': String(item.n),
                      'aria-current': item.n === step ? 'step' : undefined,
                      style:
                        item.n === step
                          ? {
                              display: 'inline-flex',
                              alignItems: 'baseline',
                              gap: '0.3rem',
                              fontWeight: 600,
                              color: 'var(--ui-text-primary)',
                              borderBottom: '2px solid var(--cb-lamp)',
                              paddingBottom: '0.1rem'
                            }
                          : { display: 'inline-flex', alignItems: 'baseline', gap: '0.3rem' },
                      children: [
                        jsx('span', { style: { fontVariantNumeric: 'tabular-nums' }, children: String(item.n) }),
                        jsx('span', { children: item.name })
                      ]
                    },
                    item.n
                  )
                )
              }),
              jsx('div', { className: 'mt-1 text-xs text-(--ui-text-secondary)', children: `Step ${step} of 3` }),
              jsx('h2', { className: 'mt-1 text-lg font-semibold', children: stepTitle }),
              jsx('p', {
                'data-cb-create-next': '',
                className: 'mt-0.5 max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children: CREATE_STEP_SPINE[step - 1].next
              })
            ]
          })
        ]
      }),
      step === 1
        ? jsxs('div', {
            className: 'flex flex-col gap-4',
            children: [
              jsxs('div', {
                className: 'flex flex-col gap-1.5',
                children: [
                  jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-goal', children: 'What do you want to be able to do?' }),
                  jsx(sdk.Textarea, {
                    'aria-describedby': 'cb-goal-help',
                    'aria-invalid': goalInvalid ? true : undefined,
                    id: 'cb-goal',
                    onChange: (event) => changeGoal(event.target.value),
                    placeholder: GOAL_PLACEHOLDER,
                    rows: 4,
                    value: goal
                  }),
                  jsx('div', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    id: 'cb-goal-help',
                    children:
                      goal.trim().length === 0
                        ? 'Say it as the situation you want to handle. The examples below are starting points, not a course yet.'
                        : `${goal.trim().length} characters. Keep editing, or start from a different example.`
                  }),
                  jsx(GoalGallery, { onChoose: changeGoal })
                ]
              }),
              jsxs('details', {
                'data-cb-title-disclosure': '',
                className: 'text-xs',
                children: [
                  jsx('summary', {
                    className: 'cursor-pointer text-xs text-(--ui-text-secondary)',
                    children: [
                      jsx('span', { style: { fontWeight: 600, color: 'var(--cb-ink)' }, children: 'Name (optional)' }, 'label'),
                      jsx('span', { children: displayTitle ? ` — ${displayTitle}` : ' — suggested from your goal' }, 'value')
                    ]
                  }),
                  jsxs('div', {
                    className: 'mt-2 flex flex-col gap-1.5',
                    children: [
                      jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: 'cb-title', children: 'Course name' }),
                      jsx(sdk.Input, {
                        id: 'cb-title',
                        onChange: (event) => {
                          setTitleEdited(true)
                          setTitle(event.target.value)
                        },
                        placeholder: TITLE_PLACEHOLDER,
                        value: title
                      }),
                      jsx('div', {
                        'data-cb-title-hint': '',
                        className: 'text-xs text-(--ui-text-secondary)',
                        children: titleEdited
                          ? 'This is the name you will see in your course list.'
                          : 'Suggested from your goal — edit it if you like. This is the name you will see in your course list.'
                      })
                    ]
                  })
                ]
              })
            ]
          })
        : null,
      step === 2
        ? jsxs('div', {
            className: 'flex flex-col gap-4',
            children: [
              jsx('p', {
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children: 'Pick the shape of the journey. Nothing is created yet, and you can go back at any point.'
              }),
              jsx('div', {
                role: 'listbox',
                'aria-label': 'The shape of this course',
                'data-cb-scope-cards': '',
                onKeyDown: (event) => {
                  // A listbox is one tab stop: arrows move the choice and the focus together.
                  const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }
                  if (event.key === 'Home' || event.key === 'End') {
                    const index = event.key === 'Home' ? 0 : COURSE_SCOPES.length - 1
                    event.preventDefault()
                    chooseScope(COURSE_SCOPES[index].id)
                    const node = scopeCardRefs.current[index]
                    if (node && node.focus) node.focus()
                    return
                  }
                  const delta = keys[event.key]
                  if (!delta) return
                  event.preventDefault()
                  const ids = COURSE_SCOPES.map((entry) => entry.id)
                  const current = Math.max(0, ids.indexOf(scope))
                  const next = (current + delta + ids.length) % ids.length
                  chooseScope(ids[next])
                  const node = scopeCardRefs.current[next]
                  if (node && node.focus) node.focus()
                },
                style: {
                  display: 'grid',
                  // `min(100%, 15rem)` keeps the track inside a 200px route: at that width the
                  // card takes the column instead of overflowing it, and the text wraps.
                  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 15rem), 1fr))',
                  gap: '0.6rem',
                  minWidth: 0
                },
                children: COURSE_SCOPES.map((option, index) => {
                  const selected = scope === option.id
                  // H-64: the whole card is the hit target and carries the selected state in words
                  // as well as in `aria-selected`. H-179: the card is the shape — name, trail,
                  // consequence and the two numbers the plan will honour — not a radio row.
                  return jsx(
                    'button',
                    {
                      type: 'button',
                      role: 'option',
                      ref: (node) => {
                        scopeCardRefs.current[index] = node
                      },
                      'aria-selected': selected,
                      'data-cb-scope-option': option.id,
                      'data-cb-scope-selected': selected ? 'true' : 'false',
                      onClick: () => chooseScope(option.id),
                      onFocus: () => setFocusScopeId(option.id),
                      onBlur: () => setFocusScopeId(null),
                      style: {
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.35rem',
                        minWidth: 0,
                        width: '100%',
                        boxSizing: 'border-box',
                        padding: '0.7rem 0.8rem 0.75rem',
                        textAlign: 'left',
                        cursor: 'pointer',
                        font: 'inherit',
                        color: 'var(--cb-ink)',
                        background: selected ? 'var(--cb-lamp-soft)' : 'var(--cb-paper-raised)',
                        border: selected ? '2px solid var(--cb-lamp)' : '1px solid var(--cb-rule)',
                        borderRadius: '2px',
                        outline: focusScopeId === option.id ? '2px solid var(--cb-accent)' : 'none',
                        outlineOffset: '2px'
                      },
                      children: [
                        jsxs('span', {
                          style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem' },
                          children: [
                            jsx('span', {
                              style: {
                                fontFamily: CB_SERIF,
                                fontSize: CB_TYPE.lead,
                                fontWeight: 600,
                                letterSpacing: '-0.01em'
                              },
                              children: option.label
                            }),
                            jsx('span', {
                              style: {
                                flexShrink: 0,
                                fontFamily: CB_SANS,
                                fontSize: CB_TYPE.caption,
                                fontWeight: 600,
                                color: selected ? 'var(--cb-ink)' : 'var(--cb-ink-soft)'
                              },
                              children: selected ? 'Selected' : 'Choose'
                            })
                          ]
                        }),
                        jsx('span', {
                          'aria-hidden': 'true',
                          style: { display: 'block', height: '34px', margin: '0.05rem 0 0.1rem' },
                          children: jsx(CbShapeTrail, { scope: option.id, height: 34 })
                        }),
                        jsx('span', {
                          style: {
                            fontFamily: CB_SANS,
                            fontSize: CB_TYPE.caption,
                            lineHeight: 1.5,
                            color: 'var(--cb-ink)'
                          },
                          children: option.consequence
                        }),
                        jsx('span', {
                          'data-cb-scope-facts': option.id,
                          style: {
                            fontFamily: CB_SANS,
                            fontSize: CB_TYPE.caption,
                            lineHeight: 1.45,
                            color: 'var(--cb-ink-soft)'
                          },
                          children: scopeFacts(option.id)
                        })
                      ]
                    },
                    option.id
                  )
                })
              }),
              jsx('div', {
                'aria-live': 'polite',
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                id: 'cb-scope-time',
                children: scope
                  ? planTimingCopy(scope)
                  : 'Choose one shape above to continue. Nothing is generated until you review the trailhead on the last step.'
              }),
              jsxs('div', {
                'data-cb-create-mode': presentationMode,
                style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0 },
                children: [
                  jsx('div', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink-soft)' },
                    children: 'How this course looks'
                  }, 'label'),
                  jsx('div', {
                    role: 'group',
                    'aria-label': 'How this course looks',
                    style: { display: 'grid', gridTemplateColumns: narrowUses ? 'minmax(0, 1fr)' : 'repeat(2, minmax(0, 1fr))', gap: '0.4rem', minWidth: 0 },
                    children: [
                      createModeCard('game', presentationMode, setPresentationMode),
                      createModeCard('textbook', presentationMode, setPresentationMode)
                    ]
                  }, 'control'),
                  jsx('div', {
                    'aria-live': 'polite',
                    'data-cb-create-mode-consequence': '',
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)', maxWidth: '54ch' },
                    children:
                      presentationMode === 'game'
                        ? 'Build a visual world around this course. The plan comes first, then three art directions, then your approval. The world is orientation only; lessons and evidence are unchanged.'
                        : 'Text-first. No generated world and no image generation. You can ask for a world later from the course.'
                  }, 'consequence')
                ]
              }),
              jsxs('div', {
                'data-cb-use-choice': '',
                style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0 },
                children: [
                  jsx('div', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink-soft)' },
                    children: 'How you will use it'
                  }, 'label'),
                  // The SDK track is one unwrapping row; at 200% text it scrolls inside its own
                  // width instead of pushing the route sideways. Below a 420px route the track
                  // cannot hold four options at all, so the same choice becomes a 2×2 block of
                  // pressed buttons — one choice either way, and no horizontal scrolling.
                  jsx('div', {
                    style: { maxWidth: '100%', overflowX: narrowUses ? 'visible' : 'auto', paddingBottom: '2px' },
                    children: narrowUses
                      ? jsx('div', {
                          role: 'group',
                          'aria-label': 'How you will use it',
                          style: {
                            display: 'grid',
                            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                            gap: '0.35rem',
                            minWidth: 0
                          },
                          children: CB_USE_OPTIONS.map((option) => {
                            const chosen = recipe === option.id
                            return jsx(sdk.Button, {
                              'aria-pressed': chosen,
                              onClick: () => chooseRecipe(option.id),
                              variant: chosen ? 'secondary' : 'outline',
                              style: {
                                minHeight: '44px',
                                justifyContent: 'center',
                                whiteSpace: 'normal',
                                textAlign: 'center',
                                fontFamily: CB_SANS,
                                fontSize: CB_TYPE.meta,
                                fontWeight: 600
                              },
                              children: option.label
                            }, option.id)
                          })
                        })
                      : jsx(sdk.SegmentedControl, {
                          onChange: chooseRecipe,
                          options: CB_USE_OPTIONS,
                          sizing: 'content',
                          value: recipe
                        })
                  }, 'control'),
                  jsx('div', {
                    'aria-live': 'polite',
                    'data-cb-use-consequence': '',
                    style: {
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      lineHeight: 1.5,
                      color: 'var(--cb-ink-soft)',
                      maxWidth: '54ch'
                    },
                    children: (RECIPE_COPY[recipe] || {}).description || ''
                  }, 'consequence')
                ]
              }),
              jsxs('details', {
                'data-cb-tune': '',
                className: 'border-t border-(--ui-stroke-tertiary) pt-3 text-xs text-(--ui-text-secondary)',
                children: [
                  jsx('summary', { className: 'cursor-pointer text-xs font-medium', children: 'Help me tune it (optional)' }),
                  jsxs('div', {
                    className: 'mt-2 flex flex-col gap-3',
                    children: [
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-level', children: 'Where you are starting from' }),
                          jsx(sdk.Input, {
                            id: 'cb-level',
                            maxLength: 35,
                            onChange: (event) => setLevel(event.target.value),
                            placeholder: 'e.g. complete beginner, or rusty',
                            value: level
                          })
                        ]
                      }),
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-subject', children: 'Subject, in your own words' }),
                          jsx(sdk.Input, {
                            id: 'cb-subject',
                            maxLength: 60,
                            onChange: (event) => setSubjectDomain(event.target.value),
                            placeholder: 'e.g. Spanish, statistics, electrical safety',
                            value: subjectDomain
                          })
                        ]
                      }),
                      jsxs('div', {
                        className: 'flex flex-col gap-1.5',
                        children: [
                          jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-locale', children: 'Language or locale (language courses only)' }),
                          jsx(sdk.Input, {
                            id: 'cb-locale',
                            maxLength: 35,
                            onChange: (event) => setLocale(event.target.value),
                            placeholder: 'e.g. es-ES for Spanish, ja-JP for Japanese',
                            value: locale
                          }),
                          jsx('div', {
                            className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                            children: 'This only sets language and formatting conventions. It never describes the subject.'
                          })
                        ]
                      }),
                      ...Object.keys(DIALS).map((dial) =>
                        jsxs('div', {
                          className: 'flex flex-col gap-1.5',
                          children: [
                            jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: DIALS[dial].label }),
                            jsx(sdk.SegmentedControl, {
                              onChange: (value) => {
                                if (dial === 'depth') {
                                  // H-168: an explicit pick is honoured, but never below the size's
                                  // research floor — the control shows the depth that will be sent,
                                  // so what the learner sees is what the plan runs.
                                  setDepthTouched(true)
                                  setDials((current) => ({ ...current, depth: effectiveDepth(value, scope) }))
                                  return
                                }
                                setDials((current) => ({ ...current, [dial]: value }))
                              },
                              options: DIALS[dial].options,
                              sizing: 'content',
                              value: dials[dial]
                            }),
                            // H-168: the size's research floor is stated, not hidden — the default
                            // depth already follows it, and a lower pick is raised to it.
                            dial === 'depth' && scope
                              ? jsx('div', {
                                  'data-cb-depth-floor': scope,
                                  className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                                  children: `This size is researched at ${dialLabel('depth', SCOPE_MIN_DEPTH[scope])} depth or deeper.`
                                })
                              : null
                          ]
                        }, dial)
                      ),
                      jsx('div', {
                        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                        children: 'These shape the plan only. Nothing here becomes a grade.'
                      })
                    ]
                  })
                ]
              })
            ]
          })
        : null,
      step === 3
        ? jsxs('div', {
            className: 'flex flex-col gap-3',
            children: [
              jsxs('section', {
                'data-cb-create-preview': '',
                'data-cb-create-shape': scope || '',
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                  padding: '0.9rem 1rem 1rem',
                  background: 'var(--cb-lamp-soft)',
                  borderTop: '3px solid var(--cb-lamp)',
                  minWidth: 0,
                  boxSizing: 'border-box'
                },
                children: [
                  jsx('div', {
                    style: {
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      fontWeight: 600,
                      letterSpacing: '0.08em',
                      color: 'var(--cb-ink-soft)'
                    },
                    children: 'THE TRAILHEAD'
                  }, 'label'),
                  jsx('h3', {
                    'data-cb-create-preview-title': '',
                    style: {
                      margin: 0,
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.heading,
                      fontWeight: 600,
                      lineHeight: 1.25,
                      letterSpacing: '-0.015em',
                      color: 'var(--cb-ink)',
                      overflowWrap: 'break-word'
                    },
                    children: displayTitle || 'A course for this goal'
                  }, 'title'),
                  jsx('div', {
                    'aria-hidden': 'true',
                    style: { height: '58px', opacity: 0.8, margin: '0.1rem 0 0.15rem' },
                    children: jsx(CbShapeTrail, { scope, height: 58 })
                  }, 'trail'),
                  jsx('div', {
                    'data-cb-create-preview-shape': '',
                    style: {
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.meta,
                      color: 'var(--cb-ink)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '0.15rem 0.6rem'
                    },
                    children: [
                      jsx('span', { style: { fontWeight: 600 }, children: (COURSE_SCOPES.find((option) => option.id === scope) || {}).label || 'Shape not chosen' }, 'shape'),
                      jsx('span', { children: scopeSectionBand(scope) || 'sections not stated' }, 'sections'),
                      jsx('span', {
                        'data-cb-create-preview-mode': presentationMode,
                        children: presentationMode === 'game' ? 'Game mode' : 'Textbook mode'
                      }, 'mode'),
                      jsx('span', {
                        'data-cb-create-preview-depth': scope,
                        children: scope ? `${dialLabel('depth', SCOPE_MIN_DEPTH[scope])} research depth` : 'depth from the plan'
                      }, 'depth')
                    ]
                  }, 'facts'),
                  jsxs('p', {
                    'data-cb-create-preview-first': '',
                    style: {
                      margin: 0,
                      maxWidth: '54ch',
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.body,
                      lineHeight: 1.5,
                      color: 'var(--cb-ink)'
                    },
                    children: [
                      jsx('span', { style: { fontWeight: 600 }, children: 'First stop' }, 'label'),
                      jsx('span', { children: ' — section 1, the first section the draft plan proposes for this goal.' }, 'text')
                    ]
                  }, 'first')
                ]
              }),
              jsx('p', {
                'data-cb-create-facts': '',
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'Create course writes the course and one draft plan. The plan then opens here for you to ' +
                  'approve, and no lesson is written until you do.'
              }),
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: planTimingCopy(scope)
              }),
              // A failed plan keeps what it already wrote. One calm line, not a receipt wall: the
              // same attempt is continued, never a second course.
              recoverable
                ? jsx('div', {
                    'data-cb-create-recoverable': '',
                    className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                    children:
                      'This course and its enrolment are saved. Trying again continues the same plan; it does not create a second course.'
                  })
                : null,
              error ? jsx(ErrorLine, { error }) : null
            ]
          })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3',
        children: [
          step > 1
            ? jsx(CbAction, {
                onClick: () => setStep(step - 1),
                variant: 'secondary',
                disabled: submitting,
                children: 'Back'
              })
            : null,
          step < 3
            ? jsx(CbAction, {
                'aria-describedby':
                  !canAdvance ? (step === 1 ? 'cb-goal-help' : 'cb-scope-time') : undefined,
                disabled: !canAdvance,
                onClick: () => setStep(step + 1),
                variant: 'primary',
                children: 'Continue'
              })
            : jsx(CbAction, {
                disabled: submitting,
                onClick: submit,
                variant: 'primary',
                children: submitting ? 'Creating course' : recoverable ? 'Try again' : 'Create course'
              }),
          // One row of actions: the primary is the only filled control; Back is secondary; Cancel
          // is tertiary and sits at the far edge on every step.
          jsx(CbAction, {
            onClick: onCancel,
            variant: 'tertiary',
            disabled: submitting,
            style: { marginLeft: 'auto' },
            children: 'Cancel'
          })
        ]
      })
    ]
  })
}
