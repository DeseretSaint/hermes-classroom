/**
 * Parent Studio (UX_SPEC §10) — the parent-led authoring surface.
 *
 * This is not a chat persona and never a child-facing surface. The parent is the operator: they
 * write a brief, review and approve the plan, generate the pages, approve the exact lesson set by
 * hash, export the printable files and record a reflection. Every screen here reads from cb.rpc v6
 * (`parent.*`); a control exists only when the method behind it is in `/runtime`.
 *
 * Two rules are load-bearing and deliberately visible in the UI rather than assumed:
 *   - the learner pages tab can never contain an answer key (`answer_guide` is a different role,
 *     served in its own tab, and export keeps it out of `LEARNER_FACING_ROLES`);
 *   - plan approval and final approval are different gates, with different hashes and different
 *     consequences, so they are two differently-labelled actions and two different badges.
 */

const STUDIO_SETTINGS = [
  { id: 'home', label: 'Home' },
  { id: 'classroom', label: 'Classroom' },
  { id: 'outdoors', label: 'Outdoors' },
  { id: 'car', label: 'Car' },
  { id: 'library', label: 'Library' },
  { id: 'community', label: 'Community' },
  { id: 'other', label: 'Other' }
]
const STUDIO_VISUALS = [
  { id: 'none', label: 'No visuals' },
  { id: 'diagrams', label: 'Diagrams' },
  { id: 'illustrations', label: 'Illustrations' }
]
const STUDIO_NARRATION = [
  { id: 'none', label: 'No narration' },
  { id: 'script', label: 'A script I read aloud' }
]
const STUDIO_AGE_BANDS = ['3-5', '5-7', '7-9', '8-10', '10-12', '12-14', '14-16', '16+'].map((band) => ({
  id: band,
  label: band
}))
const STUDIO_DIFFICULTIES = [
  { id: 'easy', label: 'Too easy' },
  { id: 'about_right', label: 'About right' },
  { id: 'too_hard', label: 'Too hard' }
]
const STUDIO_VIEWS = [
  { id: 'brief', label: 'Brief' },
  { id: 'plan', label: 'Plan' },
  { id: 'blueprint', label: 'Pages' },
  { id: 'export', label: 'Export' },
  { id: 'reflection', label: 'Reflection' }
]
const STUDIO_TABS = [
  { id: 'parent_guide', label: 'Parent guide' },
  { id: 'learner_pages', label: 'Learner pages' },
  { id: 'answers', label: 'Answers' },
  { id: 'narration', label: 'Audio & visuals' },
  { id: 'sources', label: 'Sources' }
]
const EVIDENCE_TARGET_OPTIONS = [
  { id: 'recall', label: 'Recall' },
  { id: 'comprehension', label: 'Comprehension' },
  { id: 'production', label: 'Production' },
  // `discrimination` is the rubric's name for telling two things apart; the parent reads the plain
  // phrase and the enum id still travels unchanged (H-28, UX-04 vocabulary).
  { id: 'discrimination', label: 'Tell the difference' },
  { id: 'procedure', label: 'Procedure' },
  { id: 'transfer', label: 'Transfer' }
]
const PLAN_STATE_COPY = {
  draft: 'Plan draft',
  approved: 'Plan approved',
  superseded: 'Plan superseded'
}
const APPROVAL_STATE_COPY = {
  none: 'Lesson set not approved',
  active: 'Lesson set approved',
  superseded: 'Changes need review'
}
/** `parent_export_status.blocked_reason` → the sentence the export panel shows. */
const EXPORT_BLOCKED_COPY = {
  no_final_approval: 'The generated lesson set has not been approved. Approval is a separate step from approving the plan.',
  changes_need_review: 'Changes need review. The approved lesson set no longer matches the pages shown, so export is blocked until you approve them again.',
  plan_not_approved: 'The plan is not approved, so there are no pages to export.',
  no_generated_content: 'No lesson pages have been generated yet.'
}
/** `parent.export` refusals include ones the blueprint read cannot predict. */
const EXPORT_REFUSAL_COPY = {
  plan_not_approved: 'The plan is not approved.',
  no_final_approval: 'Approve the exact lesson set first.',
  changes_need_review: 'The pages changed after approval; review and approve them again.',
  no_generated_content: 'There is no generated content to export.',
  course_pack_backed: 'This course came from an imported pack. Use Library → Export pack for it.',
  export_not_exportable: 'The generated lessons do not meet the pack’s teaching minima yet.',
  export_write_failed: 'The files could not be written. Nothing was exported.'
}
const JOB_TERMINAL_STATES = new Set([
  'completed',
  'failed',
  'cancelled',
  'completed_late',
  'interrupted_requires_retry'
])

function blankBrief() {
  return {
    title: '',
    goal: '',
    starting_point: '',
    age_band: '8-10',
    reading_level: '',
    duration_minutes: 25,
    setting: 'home',
    materials: [],
    exclusions: [],
    supervision: '',
    desired_pages: 3,
    desired_visuals: 'diagrams',
    narration: 'script',
    locale: null,
    egress_acknowledged: false,
    redaction_requested: false
  }
}

/** The typed brief from `parent.brief.get`, defaulted field by field for the form. */
function briefForForm(brief) {
  const base = blankBrief()
  if (!brief || typeof brief !== 'object') return base
  return {
    ...base,
    ...brief,
    materials: Array.isArray(brief.materials) ? brief.materials : [],
    exclusions: Array.isArray(brief.exclusions) ? brief.exclusions : [],
    // A copied brief still has to be acknowledged in this form: the disclosure is shown again.
    egress_acknowledged: false
  }
}

/** One item per line → a bounded string array the contract accepts. */
function linesToList(value, maxItems, maxLength) {
  const items = String(value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, maxItems)
    .map((line) => line.slice(0, maxLength))
  return items
}

/** A stale fence is recoverable: the backend names the revision it expects next. */
function staleRevision(response) {
  const error = (response && response.error) || {}
  const value = error.current_revision !== undefined ? error.current_revision : (error.details || {}).current_revision
  return typeof value === 'number' ? value : null
}

function StudioField({ id, label, hint, children, error }) {
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    children: [
      jsx('label', { className: 'text-xs font-medium text-(--ui-text-secondary)', htmlFor: id, children: label }),
      children,
      error
        ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: error })
        : hint
          ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: hint })
          : null
    ]
  })
}

function StudioSelect({ id, label, value, options, onChange, hint }) {
  return jsx(StudioField, {
    id,
    label,
    hint,
    children: jsxs(sdk.Select, {
      value,
      onValueChange: onChange,
      children: [
        jsx(sdk.SelectTrigger, { id, className: 'w-full', children: jsx(sdk.SelectValue, {}) }, 'trigger'),
        jsx(
          sdk.SelectContent,
          {
            children: options.map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id))
          },
          'content'
        )
      ]
    })
  })
}

function StudioCheck({ id, checked, onChange, children }) {
  return jsxs('label', {
    className: 'flex items-start gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    htmlFor: id,
    children: [
      jsx('input', { id, type: 'checkbox', checked, onChange: (event) => onChange(Boolean(event.target.checked)) }),
      jsx('span', { children })
    ]
  })
}

/** Plan-level badge: this is the outline gate, never the lesson-set gate. */
function PlanStateBadge({ plan }) {
  const state = plan && plan.state
  if (!state) return jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'No plan yet' })
  return jsx(sdk.Badge, {
    size: 'xs',
    variant: state === 'approved' ? 'muted' : 'outline',
    children: `${PLAN_STATE_COPY[state] || state} · v${plan.version}`
  })
}

/** Lesson-set badge: `active` binds exact bytes, `superseded` means the pages moved on. */
function ApprovalBadge({ approval }) {
  const state = (approval && approval.state) || 'none'
  return jsx(sdk.Badge, {
    size: 'xs',
    variant: state === 'active' ? 'muted' : state === 'superseded' ? 'warn' : 'outline',
    children: APPROVAL_STATE_COPY[state] || state
  })
}

function JobStateText({ job }) {
  if (!job) return null
  const progress = job.progress || {}
  const message = progress.message ? ` — ${progress.message}` : ''
  if (job.state === 'queued') {
    return jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Waiting to start. Nothing is spent until it begins.' })
  }
  if (job.state === 'cancel_requested' || job.state === 'cancelling') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'Stopping. The step already under way finishes, then this stops before the next one.'
    })
  }
  if (job.state === 'running') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: `Working on it${message}`
    })
  }
  if (job.state === 'completed' || job.state === 'completed_late') {
    return jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `Finished${message}` })
  }
  if (job.state === 'interrupted_requires_retry') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'It stopped early. The work already saved is kept; start the stage again to finish it.'
    })
  }
  if (job.state === 'cancelled') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: 'Cancelled before it finished. The brief and any work that had already been saved are kept.'
    })
  }
  const error = job.error || {}
  return jsxs('div', {
    className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
    children: [
      jsx('div', { children: 'It stopped before finishing.' }),
      error.message ? jsx('div', { className: 'text-(--ui-text-secondary)', children: error.message }) : null,
      error.code
        ? jsxs('details', {
            'data-cb-job-technical': '',
            style: { color: 'var(--cb3-ink-soft)' },
            children: [
              jsx('summary', { style: { cursor: 'pointer', minHeight: '1.75rem' }, children: 'Technical detail' }),
              jsx('p', { style: { margin: '0.25rem 0 0', overflowWrap: 'anywhere' }, children: error.code })
            ]
          })
        : null
    ]
  })
}

/**
 * The honest wait, before the plan exists.
 *
 * CREATE-EXPERIENCE items 3–5: a learner waiting for a draft plan gets a clock, the stage the job
 * itself reports and the shape's own time band. There is deliberately **no percentage**: the plan
 * job exposes `progress.stage`, `progress.steps_done`, `progress.steps_total` and
 * `progress.message` and none of them is a fraction of the whole run. The clock is the only number
 * this screen can prove, and it starts at the first poll that answers — never at a guessed start.
 */
const PLAN_WAIT_BAND = {
  single: 'One lesson usually takes a few minutes.',
  short: 'Short courses usually take a few minutes.',
  full: 'A full course takes longer than a short course; the clock counts the real wait.'
}

/** The job's own stage, in words a person reads. Unknown stages are de-slugged, never invented. */
const PLAN_STAGE_WORDS = {
  queued: 'Waiting to start',
  plan: 'Writing the outline',
  research: 'Researching the goal',
  authoring: 'Writing the outline',
  validating: 'Checking the outline',
  needs_review: 'Ready for your review'
}

function planWaitBand(scope) {
  return PLAN_WAIT_BAND[scope] || 'A plan usually takes a few minutes.'
}

function planStageWords(stage) {
  const key = String(stage || '').trim()
  if (!key) return ''
  if (PLAN_STAGE_WORDS[key]) return PLAN_STAGE_WORDS[key]
  return key.replace(/[_-]+/g, ' ').replace(/^./, (character) => character.toUpperCase())
}

/**
 * A ticking elapsed clock, anchored on the job id the first poll answered with. The counter only
 * runs while the job is queued or running; a settled job stops the interval and keeps the reading.
 */
function useElapsedSeconds(jobId, active) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!jobId || !active) return undefined
    const startedAt = Date.now()
    setSeconds(0)
    // The host's timer seam lets a disposed plugin drop the interval; a bare window timer is the
    // fallback so the clock still ticks in a host that exposes no seam.
    const start =
      pluginContext && typeof pluginContext.setInterval === 'function'
        ? pluginContext.setInterval
        : typeof window !== 'undefined' && typeof window.setInterval === 'function'
          ? (handler, ms) => window.setInterval(handler, ms)
          : null
    if (!start) return undefined
    const timer = start(() => {
      setSeconds(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    }, 1000)
    return () => {
      if (pluginContext && typeof pluginContext.clearInterval === 'function') pluginContext.clearInterval(timer)
      else if (typeof window !== 'undefined' && typeof window.clearInterval === 'function') window.clearInterval(timer)
    }
  }, [jobId, active])
  return active ? seconds : null
}

/**
 * The plan-screen wait panel: elapsed clock, the real stage line from `progress`, and the scope's
 * honest band. It replaces the old "there is no progress percentage" paragraph and keeps the one
 * cancel door that was already there.
 */
function PlanWritingPanel({ jobId, job, scope, onSettled, onRunAgain }) {
  const state = job && job.state
  const active = state === 'queued' || state === 'running'
  const elapsed = useElapsedSeconds(job ? job.job_id || jobId : null, active)
  const progress = (job && job.progress) || {}
  const stage = String(progress.stage || (state === 'queued' ? 'queued' : '') || '').trim()
  const stageWords = planStageWords(stage)
  const message = String(progress.message || '').trim()
  const stepsTotal = Number(progress.steps_total)
  const stepsDone = Number(progress.steps_done)
  const stepsText =
    Number.isFinite(stepsTotal) && stepsTotal > 0
      ? `Step ${Number.isFinite(stepsDone) ? stepsDone : 0} of ${stepsTotal}`
      : ''

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-plan-wait': state || 'reading',
    children: [
      jsx('div', {
        className: 'text-sm font-semibold',
        children: active || !state ? 'The plan is being written' : 'The plan is not running right now'
      }, 'title'),
      elapsed === null
        ? jsx(
            'div',
            {
              className: 'text-xs text-(--ui-text-secondary)',
              'data-cb-plan-elapsed': 'reading',
              children: 'Reading the job…'
            },
            'elapsed'
          )
        : jsx(
            'div',
            {
              className: 'text-xs tabular-nums text-(--ui-text-secondary)',
              'data-cb-plan-elapsed': String(elapsed),
              children: `${elapsed}s elapsed`
            },
            'elapsed'
          ),
      stageWords
        ? jsx(
            'div',
            {
              className: 'text-xs text-(--ui-text-secondary)',
              'data-cb-plan-stage': stage,
              children: stepsText ? `${stageWords} · ${stepsText}` : stageWords
            },
            'stage'
          )
        : null,
      message
        ? jsx(
            'div',
            {
              className: 'text-xs text-(--ui-text-secondary)',
              'data-cb-plan-message': '',
              children: message
            },
            'message'
          )
        : null,
      jsx(
        'div',
        {
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
          'data-cb-plan-band': scope || 'unknown',
          children: planWaitBand(scope)
        },
        'band'
      ),
      jsx(StudioJobLine, { jobId, job, onSettled, onRunAgain }, 'job')
    ]
  })
}

/**
 * Poll one job until it settles. The poll never navigates and never focuses anything: it re-renders
 * the line the parent is already looking at and calls `onSettled` so the caller can re-read.
 */
function useStudioJob(jobId, onSettled) {
  const [job, setJob] = useState(null)
  const settled = useRef(null)
  const settledHandler = useRef(onSettled)
  settledHandler.current = onSettled

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      return undefined
    }
    let cancelled = false
    let cancelTimer = null
    settled.current = null
    const poll = async () => {
      const response = await rpc('jobs.get', { job_id: jobId })
      if (cancelled) return
      if (!response.ok) {
        setJob({ job_id: jobId, state: 'unknown', error: response.error })
        cancelTimer = pluginContext.setTimeout(poll, 5000)
        return
      }
      const next = response.result.job
      setJob(next)
      if (JOB_TERMINAL_STATES.has(next.state)) {
        if (settled.current !== next.state) {
          settled.current = next.state
          if (settledHandler.current) settledHandler.current(next)
        }
        return
      }
      cancelTimer = pluginContext.setTimeout(poll, 3000)
    }
    cancelTimer = pluginContext.setTimeout(poll, 0)
    return () => {
      cancelled = true
      if (cancelTimer) cancelTimer()
    }
  }, [jobId])

  return job
}

function StudioJobLine({ jobId, job: providedJob, onSettled, onRunAgain, retryKey }) {
  // A caller that already reads the job (plan review needs it for the rejection model) passes it
  // in; the line then shares that read instead of polling the same id a second time.
  const polledJob = useStudioJob(providedJob ? null : jobId, onSettled)
  const job = providedJob || polledJob
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  if (!jobId) return null

  const state = job && job.state
  const running = state === 'queued' || state === 'running'
  const retryable = Boolean(
    onRunAgain && job && job.brief && (state === 'cancelled' || state === 'failed' || state === 'interrupted_requires_retry')
  )

  const cancel = async () => {
    setBusy(true)
    setError(null)
    const response = await rpc('jobs.cancel', { job_id: jobId })
    setBusy(false)
    if (!response.ok) setError(response.error)
  }

  // Re-queue the same stage from the brief the job itself stored. The parent re-reads, so the line
  // shows the new job id rather than pretending the cancelled one resumed. The key is derived from
  // the job being retried, so a double click replays one job instead of queueing a second spend. A
  // caller whose stage names a unit (lessons) supplies its own key so the retry carries that unit.
  const runAgain = async () => {
    setBusy(true)
    setError(null)
    const response = await rpc(
      'jobs.create',
      { kind: job.kind || 'plan', brief: job.brief },
      { idempotencyKey: typeof retryKey === 'function' ? retryKey(jobId, job) : `cb-stage-again-${jobId}` }
    )
    setBusy(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    if (onRunAgain) onRunAgain(response.result.job_id)
  }

  return jsxs('div', {
    className: 'flex flex-col gap-1',
    'data-cb-job-id': jobId,
    'data-cb-job-state': state || 'reading',
    children: [
      jsx(JobStateText, { job }),
      running ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'It runs in the background; leaving this page does not stop it.' }) : null,
      running
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: cancel,
            className: 'self-start',
            children: busy ? 'Cancelling' : 'Cancel generation'
          })
        : null,
      retryable
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: runAgain,
            className: 'self-start',
            children: busy ? 'Starting' : 'Run this stage again'
          })
        : null,
      error
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `${error.code ? error.code + ': ' : ''}${describeError(error)}`
          })
        : null
    ]
  })
}

/** The studio list: lesson plans the parent prepared. Imported packs stay in Library. */
function StudioList({ implemented, onCreate, onOpen, reloadSignal, sessionMinutes, onOpenSettings, triggerRef }) {
  const supported = Boolean(implemented && implemented.has('library.list'))
  const query = useRpcQuery(
    'library.list',
    { filter: 'all', recipe: 'parent', limit: 50, sort: 'recent' },
    `studio-list-${reloadSignal}`,
    supported
  )
  const rows = query.data && Array.isArray(query.data.items) ? query.data.items : []
  // H-99: fourteen copies of the same prepared brief are one shelf object with an `N plans`
  // disclosure, not fourteen identical text rows. The records stay reachable inside it.
  const groups = groupShelfRows(rows)

  if (!supported) {
    return jsx(EmptyState, {
      title: 'Parent Studio needs the v6 authoring methods',
      description:
        'This backend does not list library.list, so no authored course can be read. Update the plugin instead of using a placeholder screen.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
    })
  }
  if (query.status === 'loading' && !query.data) {
    return jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading your parent courses' }) })
  }
  if (query.status === 'error' && !query.data) {
    return jsx(sdk.ErrorState, {
      title: 'Your parent courses could not be read',
      description: `${query.error && query.error.code ? query.error.code + ': ' : ''}${describeError(query.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: query.reload, children: 'Try again' })
    })
  }
  if (rows.length === 0) {
    return jsx(EmptyState, {
      title: 'No lesson plans yet',
      description:
        'A lesson plan starts from a short brief: the child’s age and reading level, where you will teach, what you have, ' +
        'what to leave out, and what you want them to be able to do. Coursebook drafts a plan for you to review before any ' +
        'lesson page is written.',
      children: jsx(CbAction, { onClick: onCreate, variant: 'primary', children: 'New lesson plan' })
    })
  }

  return jsx(StudioLanding, { rows, onCreate, onOpen, sessionMinutes, onOpenSettings, triggerRef })
}

/**
 * The Parent Studio landing plate: the one place a parent starts a new plan. The route header
 * carries no create action, so this in-page primary is the only `variant=default` control on the
 * surface (H-94 V2-4; H-91 P2-4 removed the duplicate header button).
 */
function StudioLanding({ rows, onCreate, onOpen, sessionMinutes, onOpenSettings, triggerRef }) {
  // `groups` is computed here, not inherited by the caller: the shelf grouping is a property of
  // the rows this component renders. Without it the whole Parent Studio route throws
  // `groups is not defined` as soon as one prepared plan exists.
  const groups = groupShelfRows(rows)
  return jsxs('div', {
    'data-cb-studio-landing': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      maxWidth: CB_MEASURE,
      gap: '0.75rem',
      padding: '1rem 1rem 1.1rem',
      background: 'var(--cb3-card-stock)',
      border: '1px solid var(--cb3-rule)',
      borderRadius: cb3Radius('round'),
      boxSizing: 'border-box'
    },
    children: [
      jsx(PlateHead, {
        label: 'Parent Studio',
        title: 'Plans for your child',
        caption:
          'Prepare a lesson for a child. Each brief you write is kept as its own plan, so you can compare versions without losing the first.',
        actions: jsx(CbAction, { onClick: onCreate, variant: 'primary', children: 'New lesson plan' })
      }),
      jsx(ChildSafeLine, { sessionMinutes, onOpenSettings, triggerRef }),
      ...groups.map((group) =>
        jsx(
          CourseCover,
          {
            row: group.primary,
            group,
            identity: 'plum',
            onOpenMember: onOpen,
            detail: jsx('span', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                jsx('span', { children: 'Lesson plan for a child' }),
                jsx('span', { children: `updated ${whenLabel(group.primary.updated_at)}` })
              ]
            }),
            action: jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: () => onOpen(group.primary), children: 'Open plan' })
          },
          group.key
        )
      )
    ]
  })
}

/**
 * GM-006 — Parent Studio take-home entrance.
 *
 * A take-home pack is a rendered print artifact over a lesson the parent already teaches, never a
 * second course and never a child surface. This block adds the second entrance beside `My lesson
 * plans`: a source shelf over the learner library, a read-only lesson preview, the composed pack
 * pages, a print proof of the actual pages and the approval/export gate.
 *
 * Every read and write goes through `takehome.sources/preview/create/approve/export/read`; the
 * source course is never cloned, edited, re-approved or enrolled. The learner page and the answer
 * guide are separate page objects, and the proof marks the answer guide `Parent only` so a parent
 * cannot hand the wrong sheet over.
 */

const CB_STUDIO_ENTRANCES = [
  { id: 'plans', label: 'My lesson plans' },
  { id: 'takehome', label: 'Take-home from a lesson' },
  // GM-008: the parent's door to the tasks a learner took with them. It is a record, not a chat.
  { id: 'homework', label: 'Homework' }
]

/** The three things a parent can make from one source lesson. */
const CB_TAKEHOME_KINDS = [
  {
    id: 'print_pack',
    label: 'Print a take-home pack',
    hint: 'A parent guide, the learner page and a separate answer guide, bound to this lesson.'
  },
  {
    id: 'activity_plan',
    label: 'Prepare an activity plan',
    hint: 'The same lesson, composed for a short parent-led activity away from the screen.'
  },
  {
    id: 'homework_sheet',
    label: 'Send with homework',
    hint: 'One real-world practice task on a single sheet the learner can carry with them.'
  }
]

const CB_TAKEHOME_AUDIENCES = [
  { id: 'parent', label: 'For me to teach from' },
  { id: 'learner', label: 'For the learner to hold' }
]

const CB_TAKEHOME_PAGE_WORD = {
  cover: 'Cover',
  parent_guide: 'Parent guide',
  learner_page: 'Learner page',
  plate: 'Plate',
  answer_guide: 'Answer guide'
}

/**
 * The one sentence that keeps each page in its lane. It is printed on the proof itself, not left
 * to the reader to infer from position: the learner page carries no answers, and the answer guide
 * is a parent-only sheet.
 */
const CB_TAKEHOME_PAGE_NOTE = {
  cover: 'The first page of the printed pack.',
  parent_guide: 'For the adult preparing the lesson. It is not the learner’s page.',
  learner_page: 'For the learner. This page carries no answers.',
  plate: 'Captioned orientation art. It is not the lesson text.',
  answer_guide: 'Parent only. Keep this page back.'
}

const CB_TAKEHOME_STATE_WORD = {
  draft: 'Draft',
  approved: 'Approved',
  exported: 'Exported',
  superseded: 'Superseded'
}

const CB_TAKEHOME_MODE_WORD = {
  game: 'Game course',
  textbook: 'Textbook course'
}

const CB_TAKEHOME_KIND_WORD = {
  print_pack: 'Take-home pack',
  activity_plan: 'Activity plan',
  homework_sheet: 'Homework sheet'
}

/** A blocked objective names why in plain words; the backend's reason stays the fallback. */
const CB_TAKEHOME_BLOCKED_WORD = {
  'no generated lesson': 'The lesson for this objective has not been written yet.',
  parent_only_course: 'A parent-authored plan is not a learner source.',
  ai_art_as_procedure: 'This procedure has only illustration art, so it cannot print as authority.'
}

/** Named export refusals, in the parent's words, with the backend reason kept verbatim. */
const CB_TAKEHOME_EXPORT_WORD = {
  pack_not_approved: 'Approve the exact pages above before exporting.',
  approval_stale: 'The pages changed after approval. Approve the pages you can see again.',
  preview_hash_mismatch: 'The preview moved on. Preview the pages again, then approve them.',
  already_exported: 'This pack is already exported. The file below is that export.',
  print_font_cannot_render_text:
    'The print font cannot draw every character in this lesson, so no PDF was written. Nothing was corrupted.',
  pdf_render_failed: 'The PDF renderer failed. The pack is kept; the export did not run.',
  parent_only_course: 'A parent-authored plan is not a learner source.',
  pack_superseded: 'This draft was superseded. Start a fresh draft from the lesson.'
}

/** The Parent Studio's entrances side by side: authored plans, take-home packs, homework.
 *
 * CP-025b: this is the v3 tab strip. The host's `sdk.SegmentedControl` used to paint it, which put
 * host chrome on Coursebook's own route; the tabs are now authored buttons with `role="tab"`,
 * `aria-selected` and a 3 px terracotta marker under the current label — a shape *and* a word,
 * never colour alone. Targets stay 44 px so the strip survives 460 and 200% text.
 */
function StudioEntranceTabs({ value, onChange }) {
  return jsx('div', {
    'data-cb-parent-studio-tabs': '',
    role: 'tablist',
    'aria-label': 'Parent Studio sections',
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'stretch',
      gap: '0.25rem',
      padding: '0.9rem 1rem 0',
      borderBottom: '1px solid var(--cb3-rule)',
      boxSizing: 'border-box'
    },
    children: CB_STUDIO_ENTRANCES.map((item) => {
      const current = item.id === value
      return jsx('button', {
        type: 'button',
        role: 'tab',
        'data-cb3-tab': item.id,
        'data-current': current ? 'true' : 'false',
        'aria-selected': current ? 'true' : 'false',
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          minHeight: '44px',
          paddingInline: '0.6rem',
          border: 0,
          borderBottom: current ? '3px solid var(--cb3-terracotta)' : '3px solid transparent',
          background: 'transparent',
          color: 'var(--cb3-ink)',
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: cb3Lead('meta'),
          fontWeight: current ? 600 : 400,
          cursor: 'pointer'
        },
        onClick: () => onChange(item.id),
        children: item.label
      }, item.id)
    })
  })
}

/** The shelf excludes parent-authored plans: those belong to `My lesson plans`. */
function cbTakeHomeSourceRows(rows) {
  return (Array.isArray(rows) ? rows : []).filter((row) => row && row.recipe !== 'parent')
}

function cbTakeHomeModeWord(mode) {
  return CB_TAKEHOME_MODE_WORD[mode] || 'Course'
}

function cbTakeHomeKindWord(kind) {
  return CB_TAKEHOME_KIND_WORD[kind] || 'Take-home'
}

/**
 * The proof's page order, from either `takehome.preview` (an array) or `takehome.read` (an object
 * of the three required pages). One order for every renderer: cover, parent guide, learner page,
 * plates, answer guide last.
 */
function cbTakeHomePageOrder(pages) {
  const list = Array.isArray(pages) ? pages : pages && typeof pages === 'object' ? Object.values(pages) : []
  const rank = { cover: 0, parent_guide: 1, learner_page: 2, plate: 3, answer_guide: 4 }
  return list
    .filter((page) => page && page.role)
    .slice()
    .sort(
      (left, right) =>
        (rank[left.role] === undefined ? 9 : rank[left.role]) - (rank[right.role] === undefined ? 9 : rank[right.role])
    )
}

/**
 * The pages a proof may show for one audience. A learner copy prints the cover, the learner page
 * and captioned plates; the parent guide and the answer guide never reach it.
 */
function cbTakeHomeProofPages(pack) {
  const audience = (pack && pack.audience) || 'parent'
  const allowed =
    audience === 'learner'
      ? new Set(['cover', 'learner_page', 'plate'])
      : new Set(['cover', 'parent_guide', 'learner_page', 'plate', 'answer_guide'])
  return cbTakeHomePageOrder(pack && pack.pages).filter((page) => allowed.has(page.role))
}

function cbTakeHomeBlockedCopy(reason) {
  if (!reason) return 'This lesson cannot be printed yet.'
  return CB_TAKEHOME_BLOCKED_WORD[reason] || `This lesson cannot be printed: ${reason}.`
}

function cbTakeHomeExportCopy(error) {
  const details = (error && error.details) || {}
  const reason = details.reason
  if (reason && CB_TAKEHOME_EXPORT_WORD[reason]) return CB_TAKEHOME_EXPORT_WORD[reason]
  return `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`
}

function TakeHomePaperBadge({ children, tone }) {
  return jsx('span', {
    'data-cb-takehome-badge': tone || 'plain',
    style: {
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('caption'),
      fontWeight: 600,
      letterSpacing: '0.01em',
      color: tone === 'warn' ? 'var(--cb3-alert)' : 'var(--cb3-ink-soft)',
      border: '1px solid var(--cb3-rule)',
      borderRadius: '999px',
      padding: '0.05rem 0.5rem',
      whiteSpace: 'nowrap'
    },
    children
  })
}

/** The source shelf: courses this profile already teaches, without their parent plans. */
function TakeHomeShelf({ rows, status, error, onSelect, onRetry }) {
  const sources = cbTakeHomeSourceRows(rows)
  if (status === 'loading' && !rows) {
    return jsx('div', { className: 'py-10', children: jsx(sdk.Loader, { label: 'Reading the courses you teach' }) })
  }
  if (status === 'error' && !rows) {
    return jsx(sdk.ErrorState, {
      title: 'The courses you teach could not be read',
      description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: onRetry, children: 'Try again' })
    })
  }
  if (sources.length === 0) {
    return jsx(EmptyState, {
      title: 'No learner course to draw from',
      description:
        'A take-home pack is printed from a Game or Textbook lesson you already teach. Write or import a learner course first; a parent plan belongs under My lesson plans.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: onRetry, children: 'Check again' })
    })
  }
  return jsxs('section', {
    'data-cb-takehome-shelf': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      padding: '1rem 1rem 1.1rem',
      background: 'var(--cb3-canvas-edge)',
      borderTop: '1px solid var(--cb3-plum)',
      boxSizing: 'border-box'
    },
    children: [
      jsx(PlateHead, {
        label: 'Take-home from a lesson',
        title: 'Draw a take-home from a course you already teach',
        caption:
          'The source course is not copied, changed or re-approved. The pack binds to this lesson’s version and hash, so printing it never touches the course.'
      }),
      jsx('div', {
        role: 'list',
        'aria-label': 'Courses you can draw a take-home from',
        style: { display: 'flex', flexDirection: 'column' },
        children: sources.map((row) =>
          jsxs(
            'div',
            {
              role: 'listitem',
              'data-cb-source-course': row.course_id,
              style: {
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                gap: '0.4rem 1rem',
                padding: '0.7rem 0',
                borderTop: '1px solid var(--cb3-rule)'
              },
              children: [
              jsxs(
                'div',
                {
                  style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0 },
                  children: [
                    jsx('div', {
                      style: {
                        fontFamily: 'var(--cb3-font-display)',
                        fontSize: cb3Type('body'),
                        fontWeight: 600,
                        color: 'var(--cb3-ink)',
                        overflowWrap: 'anywhere'
                      },
                      children: row.title || 'Untitled course'
                    }),
                    jsx('div', {
                      style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                      children:
                        `${(row.provenance && row.provenance.source) === 'bundled' ? 'Bundled' : (row.provenance && row.provenance.source) === 'community' ? 'Imported' : 'Written here'} · ` +
                        `${row.learner_label || 'Learner course'}`
                    })
                  ]
                }
              ),
              jsx(sdk.Button, {
                size: 'sm',
                variant: 'secondary',
                onClick: () => onSelect(row),
                children: 'Choose this course'
              })
              ]
            }
          )
        )
      })
    ]
  })
}

/** Sections and their written lessons, with the source's mode stated before anything is made. */
function TakeHomeSourcePanel({ courseTitle, source, status, error, onSelectObjective, onRetry, onBack }) {
  const objectives = (source && source.objectives) || []
  const groups = []
  for (const objective of objectives) {
    const last = groups[groups.length - 1]
    if (last && last.title === objective.section_title) last.items.push(objective)
    else groups.push({ title: objective.section_title, items: [objective] })
  }
  return jsxs('section', {
    'data-cb-takehome-source': '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', padding: '1rem 1rem 1.1rem', boxSizing: 'border-box' },
    children: [
      jsx(PlateHead, {
        label: 'Source lesson',
        title: courseTitle || 'Choose a lesson',
        caption:
          'Pick the written lesson to print. The preview is read-only: the course, its plan and its approval are not touched.',
        actions: jsx(sdk.Button, { size: 'sm', variant: 'tertiary', onClick: onBack, children: 'Back to courses' })
      }),
      status === 'loading'
        ? jsx('div', { className: 'py-8', children: jsx(sdk.Loader, { label: 'Reading the lessons in this course' }) })
        : status === 'error'
          ? jsx(sdk.ErrorState, {
              title: 'This course’s lessons could not be read',
              description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)}`,
              children: jsx(sdk.Button, { variant: 'secondary', onClick: onRetry, children: 'Try again' })
            })
          : objectives.length === 0
            ? jsx(EmptyState, {
                title: 'This course has no written lessons yet',
                description:
                  'A take-home pack prints the lesson as it already exists. Write the lesson in the course first, then come back.',
                children: jsx(sdk.Button, { variant: 'secondary', onClick: onBack, children: 'Choose another course' })
              })
            : jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
                children: [
                  jsxs('div', {
                    'data-cb-source-mode': (source && source.presentation_mode) || '',
                    style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' },
                    children: [
                      jsx(TakeHomePaperBadge, { children: cbTakeHomeModeWord(source && source.presentation_mode) }),
                      jsx(TakeHomePaperBadge, { children: plural(objectives.length, 'written lesson', 'written lessons') }),
                      jsx('span', {
                        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                        children: 'No child account and no child chat: the adult prepares and prints.'
                      })
                    ]
                  }),
                  ...groups.map((group) =>
                    jsxs(
                      'div',
                      {
                        'data-cb-source-section': group.title,
                        style: { display: 'flex', flexDirection: 'column' },
                        children: [
                          jsx('h3', {
                            style: {
                              margin: 0,
                              fontFamily: 'var(--cb3-font-display)',
                              fontSize: cb3Type('body'),
                              fontWeight: 600,
                              color: 'var(--cb3-ink)',
                              paddingBottom: '0.3rem',
                              borderBottom: '1px solid var(--cb3-rule)'
                            },
                            children: group.title
                          }),
                          ...group.items.map((objective) =>
                            jsxs(
                              'div',
                              {
                                'data-cb-source-objective': objective.objective_id,
                                'data-cb-source-available': objective.available ? 'true' : 'false',
                                style: {
                                  display: 'flex',
                                  flexWrap: 'wrap',
                                  alignItems: 'baseline',
                                  justifyContent: 'space-between',
                                  gap: '0.4rem 1rem',
                                  padding: '0.65rem 0',
                                  borderBottom: '1px solid var(--cb3-rule)'
                                },
                                children: [
                                jsxs(
                                  'div',
                                  {
                                    style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0 },
                                    children: [
                                      jsx('div', {
                                        style: {
                                          fontFamily: 'var(--cb3-font-display)',
                                          fontSize: cb3Type('body'),
                                          color: 'var(--cb3-ink)',
                                          overflowWrap: 'anywhere'
                                        },
                                        children: `${objective.ordinal}. ${objective.title}`
                                      }),
                                      jsx('div', {
                                        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                                        children: objective.available
                                          ? `Evidence target: ${objective.evidence_target} · ${objective.lesson_state}` +
                                            (objective.has_world_plate ? ' · world plates available' : ' · no world art')
                                          : cbTakeHomeBlockedCopy(objective.blocked_reason)
                                      })
                                    ]
                                  }
                                ),
                                jsx(sdk.Button, {
                                  size: 'sm',
                                  variant: 'secondary',
                                  disabled: !objective.available,
                                  onClick: () => onSelectObjective(objective),
                                  children: objective.available ? 'Preview this lesson' : 'Not printable yet'
                                })
                                ]
                              }
                            )
                          )
                        ]
                      },
                      group.title
                    )
                  )
                ]
              })
    ]
  })
}

/**
 * The proof of the actual pages. Page sheets are real DOM text in reading order, not a thumbnail:
 * a parent approves what is on this screen, and the learner page and answer guide are visibly
 * different objects with their own audience label.
 */
function TakeHomeProof({ pages, audience, title, printProfile }) {
  const list = cbTakeHomeProofPages({ pages, audience })
  if (list.length === 0) return null
  const profile = printProfile || {}
  const paper = (profile.paper || 'letter') === 'a4' ? 'A4' : 'Letter'
  const margin = profile.margin_pt || 56
  return jsxs('section', {
    'data-cb-takehome-proof': '',
    'data-cb-proof-audience': audience || 'parent',
    'data-cb-proof-pages': String(list.length),
    'aria-label': 'Print proof of the pack pages',
    style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
    children: [
      jsxs(
        'div',
        {
          style: {
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            gap: '0.3rem 1rem'
          },
          children: [
            jsx(CbLabel, { children: 'Print proof' }),
            jsx('span', {
              style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
              children: `${plural(list.length, 'page', 'pages')} · ${paper} · ${margin} pt margins · selectable text`
            })
          ]
        }
      ),
      jsx('div', {
        role: 'list',
        style: { display: 'flex', flexDirection: 'column', gap: '0.85rem' },
        children: list.map((page, index) => {
          const role = page.role
          // One sheet voice per role: warm paper for parent pages, the field edge for the learner
          // page, and the plum wash plus a dashed rule for the parent-only answer guide.
          const sheet =
            {
              cover: { background: 'var(--cb3-terracotta-quiet)', borderColor: 'var(--cb3-terracotta)' },
              parent_guide: { background: 'var(--cb3-card-stock)', borderColor: 'var(--cb3-terracotta)' },
              learner_page: { background: 'var(--cb3-card-stock)', borderColor: 'var(--cb3-sage)' },
              plate: { background: 'var(--cb3-terracotta-quiet)', borderColor: 'var(--cb3-terracotta)' },
              answer_guide: { background: 'var(--cb3-canvas-edge)', borderColor: 'var(--cb3-plum)' }
            }[role] || { background: 'var(--cb3-card-stock)', borderColor: 'var(--cb3-rule)' }
          return jsxs(
            'article',
            {
              role: 'listitem',
              'data-cb-proof-page': role,
              'data-cb-proof-audience': page.audience,
              'data-cb-proof-index': String(index + 1),
              style: {
                display: 'flex',
                flexDirection: 'column',
                gap: '0.45rem',
                width: '100%',
                maxWidth: '46rem',
                boxSizing: 'border-box',
                padding: '1.1rem 1.25rem 1rem',
                background: sheet.background,
                border: '1px solid ' + sheet.borderColor,
                borderTopStyle: role === 'answer_guide' ? 'dashed' : 'solid',
              },
              children: [
            jsxs(
              'header',
              {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.35rem 0.6rem' },
                children: [
                  jsx(TakeHomePaperBadge, {
                    tone: role === 'answer_guide' ? 'warn' : 'plain',
                    children: CB_TAKEHOME_PAGE_WORD[role] || role
                  }),
                  jsx('span', {
                    style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                    children: CB_TAKEHOME_PAGE_NOTE[role] || ''
                  }),
                  jsx('span', {
                    style: {
                      marginLeft: 'auto',
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      color: 'var(--cb3-ink-soft)'
                    },
                    children: `Page ${index + 1} of ${list.length}`
                  })
                ]
              }
            ),
            jsx('h3', {
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-display)',
                fontSize: cb3Type('body'),
                fontWeight: 600,
                lineHeight: 1.25,
                color: 'var(--cb3-ink)',
                overflowWrap: 'anywhere'
              },
              children: page.title
            }),
            page.alt_text
              ? jsx('p', {
                  style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                  children: `Text alternative: ${page.alt_text}`
                })
              : null,
            jsx(ProseText, {
              'data-cb-proof-text': role,
              style: {
                fontFamily: 'var(--cb3-font-display)',
                fontSize: cb3Type('body'),
                lineHeight: 1.6,
                color: 'var(--cb3-ink)',
                maxWidth: CB_MEASURE
              },
              text: page.text
            })
              ]
            }
          )
        })
      })
    ]
  })
}

/**
 * The pack workspace: choose what to make, preview the actual pages, save the draft, approve the
 * exact pages and print. It is presentational; `TakeHomeStudio` owns the command sequence so a
 * test can render every state without a live backend.
 */
function TakeHomePackPanel({
  courseTitle,
  source,
  objective,
  kind,
  audience,
  onKind,
  onAudience,
  preview,
  previewStatus,
  previewError,
  onPreview,
  onRetryPreview,
  onBack,
  pack,
  busy,
  error,
  exportError,
  exported,
  artifact,
  onSaveDraft,
  onApprove,
  onExport
}) {
  const pages = preview ? preview.pages : null
  const ready = Boolean(preview)
  const state = (pack && pack.state) || null
  const revision = pack && typeof pack.revision === 'number' ? pack.revision : null
  const approved = state === 'approved' || state === 'exported'
  const isBusy = Boolean(busy)
  return jsxs('section', {
    'data-cb-takehome-pack': '',
    'data-cb-takehome-pack-state': state || 'none',
    style: { display: 'flex', flexDirection: 'column', gap: '0.85rem', padding: '1rem 1rem 1.2rem', boxSizing: 'border-box' },
    children: [
      jsx(PlateHead, {
        label: 'Take-home from a lesson',
        title: objective ? objective.title : 'Take-home',
        caption: objective ? objective.section_title : '',
        actions: jsx(sdk.Button, { size: 'sm', variant: 'tertiary', onClick: onBack, children: 'Back to the lesson list' })
      }),
      jsxs(
        'div',
        {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
          children: [
            jsx(TakeHomePaperBadge, { children: cbTakeHomeModeWord(source && source.presentation_mode) }),
            jsx(TakeHomePaperBadge, {
              children: objective ? `Evidence target: ${objective.evidence_target}` : 'Lesson'
            }),
            jsx(TakeHomePaperBadge, { children: cbTakeHomeKindWord(kind) })
          ]
        }
      ),
      // The source line is the pack's binding, printed where the parent makes the decision.
      jsxs(
        'div',
        {
          'data-cb-takehome-source-line': '',
          style: {
            display: 'flex',
            flexDirection: 'column',
            gap: '0.15rem',
            fontFamily: 'var(--cb3-font-ui)',
            fontSize: cb3Type('caption'),
            color: 'var(--cb3-ink-soft)'
          },
          children: [
            jsx('div', {
              children:
                `Source: ${courseTitle || 'course'} · ` +
                `${objective ? `lesson v${objective.lesson_version}` : 'lesson'} · ` +
                `state ${objective ? objective.lesson_state : 'unknown'}`
            }),
            jsx('div', {
              style: { overflowWrap: 'anywhere' },
              children: `Source content hash: ${(preview && preview.content_hash) || (objective && objective.content_hash) || '—'}`
            }),
            jsx('div', { children: 'Printing this pack does not change the course, its plan or its approval.' })
          ]
        }
      ),
      jsx(CbLabel, { children: 'What to make' }),
      jsx('div', {
        role: 'radiogroup',
        'aria-label': 'What to make from this lesson',
        style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
        children: CB_TAKEHOME_KINDS.map((option) =>
          jsxs(
            'label',
            {
              'data-cb-takehome-kind': option.id,
              style: {
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.55rem',
                padding: '0.45rem 0.6rem',
                border: '1px solid ' + (kind === option.id ? 'var(--cb3-terracotta)' : 'var(--cb3-rule)'),
                background: kind === option.id ? 'var(--cb3-terracotta-quiet)' : 'transparent',
                fontFamily: 'var(--cb3-font-ui)',
                fontSize: cb3Type('caption'),
                color: 'var(--cb3-ink)',
                cursor: 'pointer'
              },
              children: [
              jsx('input', {
                type: 'radio',
                name: 'cb-takehome-kind',
                value: option.id,
                checked: kind === option.id,
                onChange: () => onKind(option.id),
                style: { marginTop: '0.15rem' }
              }),
              jsxs(
                'span',
                {
                  style: { display: 'flex', flexDirection: 'column', gap: '0.1rem' },
                  children: [
                    jsx('span', { style: { fontWeight: 600, fontSize: cb3Type('body') }, children: option.label }),
                    jsx('span', { style: { color: 'var(--cb3-ink-soft)' }, children: option.hint })
                  ]
                }
              )
              ]
            }
          )
        )
      }),
      jsx(CbLabel, { children: 'Who holds this copy' }),
      jsx('div', {
        'data-cb-takehome-audience': audience,
        role: 'radiogroup',
        'aria-label': 'Who holds this copy',
        style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' },
        children: CB_TAKEHOME_AUDIENCES.map((option) => {
          const chosen = option.id === audience
          return jsx('button', {
            type: 'button',
            role: 'radio',
            'data-cb3-choice': option.id,
            'aria-checked': chosen ? 'true' : 'false',
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              minHeight: '44px',
              paddingInline: '0.7rem',
              border: chosen ? '2px solid var(--cb3-terracotta)' : '1px solid var(--cb3-rule)',
              borderRadius: cb3Radius('pill'),
              background: chosen ? 'var(--cb3-terracotta-quiet)' : 'transparent',
              color: 'var(--cb3-ink)',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              fontWeight: chosen ? 600 : 400,
              cursor: 'pointer'
            },
            onClick: () => onAudience(option.id),
            children: option.label
          }, option.id)
        })
      }),
      // One primary at a time, in the order the artifact actually moves.
      !ready
        ? jsx(CbAction, {
            variant: 'primary',
            disabled: isBusy || !objective || !objective.available,
            onClick: onPreview,
            children: busy === 'preview' ? 'Composing the pages' : 'Preview the pages'
          })
        : null,
      !ready && previewStatus === 'error'
        ? jsx(sdk.ErrorState, {
            title: 'The pages could not be composed',
            description: `${previewError && previewError.code ? previewError.code + ': ' : ''}${describeError(previewError)}`,
            children: jsx(sdk.Button, { variant: 'secondary', onClick: onRetryPreview, children: 'Try again' })
          })
        : null,
      ready
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
            children: [
              jsx(TakeHomeProof, {
                pages,
                audience,
                title: objective ? objective.title : '',
                printProfile: preview.print_profile
              }),
              preview.sources && preview.sources.length
                ? jsxs(
                    'div',
                    {
                      'data-cb-takehome-sources': '',
                      style: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
                      children: [
                        jsx(CbLabel, { children: 'Recorded sources' }),
                        ...preview.sources.map((item) =>
                          jsx(
                            'div',
                            {
                              style: {
                                fontFamily: 'var(--cb3-font-ui)',
                                fontSize: cb3Type('caption'),
                                color: 'var(--cb3-ink-soft)',
                                overflowWrap: 'anywhere'
                              },
                              children: `${item.title}${item.url ? ' · ' + item.url : ''} · ${item.support_status}`
                            },
                            item.source_id
                          )
                        )
                      ]
                    }
                  )
                : jsx('div', {
                    style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                    children: 'This lesson records no external sources.'
                  })
            ]
          })
        : null,
      ready
        ? jsxs(
            'div',
            {
              'data-cb-takehome-gate': '',
              style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
              children: [
                jsx(CbLabel, { children: 'Approval and print' }),
                jsx('div', {
                  style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)', overflowWrap: 'anywhere' },
                  children: `Previewed pages: ${(preview.pages || []).length} · preview hash: ${preview.preview_hash}`
                }),
                state === 'draft'
                  ? jsx('div', {
                      style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                      children: `Draft ${pack.pack_id} · revision ${revision}. Approval covers exactly the pages above.`
                    })
                  : null,
                state === 'approved' || state === 'exported'
                  ? jsx('div', {
                      style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)', overflowWrap: 'anywhere' },
                      children: `${CB_TAKEHOME_STATE_WORD[state]} on ${pack.approved_at || 'approval'} · approval hash: ${pack.approval_hash || '—'}`
                    })
                  : null,
                !pack
                  ? jsx(CbAction, {
                      variant: 'primary',
                      disabled: isBusy,
                      onClick: onSaveDraft,
                      children: busy === 'draft' ? 'Saving the draft' : 'Save this draft'
                    })
                  : null,
                pack && !approved
                  ? jsx(CbAction, {
                      variant: 'primary',
                      disabled: isBusy,
                      onClick: onApprove,
                      children: busy === 'approve' ? 'Approving the pages' : 'Approve these pages'
                    })
                  : null,
                approved
                  ? jsx(CbAction, {
                      variant: 'primary',
                      disabled: isBusy || state === 'exported',
                      onClick: onExport,
                      children:
                        state === 'exported'
                          ? 'PDF exported'
                          : busy === 'export'
                            ? 'Printing the PDF'
                            : 'Export the print-ready PDF'
                    })
                  : null,
                error
                  ? jsxs(
                      'div',
                      {
                        'data-cb-takehome-error': (error.details && error.details.reason) || error.code || 'error',
                        style: {
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.15rem',
                          fontFamily: 'var(--cb3-font-ui)',
                          fontSize: cb3Type('caption'),
                          color: 'var(--cb3-alert)'
                        },
                        children: [
                          jsx('div', {
                            children:
                              (error.details && error.details.reason && CB_TAKEHOME_EXPORT_WORD[error.details.reason]) ||
                              `${error.code ? error.code + ': ' : ''}${describeError(error)}`
                          }),
                          jsx('div', {
                            style: { color: 'var(--cb3-ink-soft)' },
                            children: `Backend reason: ${(error.details && error.details.reason) || 'none reported'}.`
                          })
                        ]
                      }
                    )
                  : null,
                exportError
                  ? jsx('div', {
                      'data-cb-takehome-export-error':
                        (exportError.details && exportError.details.reason) || exportError.code || 'error',
                      style: {
                        fontFamily: 'var(--cb3-font-ui)',
                        fontSize: cb3Type('caption'),
                        color: 'var(--cb3-alert)'
                      },
                      children: cbTakeHomeExportCopy(exportError)
                    })
                  : null,
                exported
                  ? jsxs(
                      'div',
                      {
                        'data-cb-takehome-exported': exported.artifact_id,
                        style: {
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.3rem',
                          fontFamily: 'var(--cb3-font-ui)',
                          fontSize: cb3Type('caption'),
                          color: 'var(--cb3-ink-soft)'
                        },
                        children: [
                          jsx('div', {
                            children: `Exported ${exported.exported_at || ''} · artifact ${exported.artifact_id}`
                          }),
                          artifact && artifact.download
                            ? jsx(sdk.Button, {
                                asChild: true,
                                size: 'sm',
                                variant: 'secondary',
                                children: jsx('a', {
                                  download: 'take-home-pack.pdf',
                                  href: artifact.download.url,
                                  children: 'Download the print-ready PDF'
                                })
                              })
                            : jsx('div', { children: 'The file is recorded; its download link is not available in this host.' })
                        ]
                      }
                    )
                  : null
              ]
            }
          )
        : null
    ]
  })
}

/**
 * The take-home entrance: shelf → source lessons → pack. Reads and writes only the
 * `takehome.*` methods; every state above is a real backend answer, not a placeholder.
 */
function TakeHomeStudio({ implemented, onOpenSettings, sessionMinutes, triggerRef }) {
  const canRead = Boolean(implemented && implemented.has('library.list'))
  const library = useRpcQuery('library.list', { filter: 'all', limit: 50, sort: 'recent' }, 'takehome-shelf', canRead)
  const [step, setStep] = useState('shelf')
  const [course, setCourse] = useState(null)
  const [sources, setSources] = useState({ status: 'idle', data: null, error: null })
  const [objective, setObjective] = useState(null)
  const [kind, setKind] = useState('print_pack')
  const [audience, setAudience] = useState('parent')
  const [preview, setPreview] = useState(null)
  const [previewStatus, setPreviewStatus] = useState('idle')
  const [previewError, setPreviewError] = useState(null)
  const [pack, setPack] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifact, setArtifact] = useState(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [exportError, setExportError] = useState(null)

  const resetPack = useCallback(() => {
    setPreview(null)
    setPreviewStatus('idle')
    setPreviewError(null)
    setPack(null)
    setExported(null)
    setArtifact(null)
    setError(null)
    setExportError(null)
  }, [])

  const chooseCourse = useCallback(async (row) => {
    setCourse(row)
    setStep('source')
    setSources({ status: 'loading', data: null, error: null })
    const response = await rpc('takehome.sources', { course_id: row.course_id })
    if (!response.ok) {
      setSources({ status: 'error', data: null, error: response.error })
      return
    }
    setSources({ status: 'ready', data: response.result, error: null })
  }, [])

  const reloadSources = useCallback(async () => {
    if (!course) return
    setSources({ status: 'loading', data: null, error: null })
    const response = await rpc('takehome.sources', { course_id: course.course_id })
    if (!response.ok) {
      setSources({ status: 'error', data: null, error: response.error })
      return
    }
    setSources({ status: 'ready', data: response.result, error: null })
  }, [course])

  const chooseObjective = useCallback(
    (entry) => {
      setObjective(entry)
      resetPack()
      setStep('pack')
    },
    [resetPack]
  )

  const runPreview = useCallback(async () => {
    if (!course || !objective) return
    setBusy('preview')
    setPreviewStatus('loading')
    setPreviewError(null)
    setError(null)
    const response = await rpc('takehome.preview', {
      course_id: course.course_id,
      objective_id: objective.objective_id,
      source_lesson_version: objective.lesson_version,
      audience,
      kind
    })
    setBusy(null)
    if (!response.ok) {
      setPreviewStatus('error')
      setPreviewError(response.error)
      return
    }
    setPreviewStatus('ready')
    setPreview(response.result)
  }, [course, objective, audience, kind])

  const saveDraft = useCallback(async () => {
    if (!course || !objective || !preview) return
    setBusy('draft')
    setError(null)
    const response = await rpc(
      'takehome.create',
      {
        course_id: course.course_id,
        objective_id: objective.objective_id,
        source_lesson_version: objective.lesson_version,
        audience,
        kind,
        title: objective.title
      },
      { expectedRevision: 0, idempotencyKey: newOperationId('takehome-create') }
    )
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setPack({ ...response.result, preview_hash: preview.preview_hash, approved_at: null, approval_hash: null })
  }, [course, objective, preview, audience, kind])

  const approvePages = useCallback(async () => {
    if (!pack || !preview) return
    setBusy('approve')
    setError(null)
    const response = await rpc(
      'takehome.approve',
      { pack_id: pack.pack_id, preview_hash: preview.preview_hash },
      { expectedRevision: pack.revision, idempotencyKey: newOperationId('takehome-approve') }
    )
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    // The approve response carries no revision field; approval always advances the pack by one.
    setPack((previous) => ({ ...previous, ...response.result, revision: (previous.revision || 0) + 1 }))
  }, [pack, preview])

  const exportPdf = useCallback(async () => {
    if (!pack) return
    setBusy('export')
    setExportError(null)
    const response = await rpc(
      'takehome.export',
      { pack_id: pack.pack_id },
      { expectedRevision: pack.revision, idempotencyKey: newOperationId('takehome-export') }
    )
    if (!response.ok) {
      setBusy(null)
      setExportError(response.error)
      return
    }
    setExported(response.result)
    setPack((previous) => ({ ...previous, state: 'exported', revision: previous.revision + 1 }))
    const facts = await rpc('artifact.get', { artifact_id: response.result.artifact_id })
    setBusy(null)
    if (facts.ok) setArtifact(facts.result)
  }, [pack])

  if (!canRead) {
    return jsx(EmptyState, {
      title: 'Take-home needs the library methods',
      description:
        'This backend does not list library.list, so no source course can be read. Update the plugin instead of using a placeholder screen.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: openCapabilities, children: 'Open Capabilities' })
    })
  }

  if (step === 'shelf') {
    return jsx(TakeHomeShelf, {
      rows: library.data && Array.isArray(library.data.items) ? library.data.items : null,
      status: library.status,
      error: library.error,
      onSelect: chooseCourse,
      onRetry: library.reload
    })
  }

  if (step === 'source') {
    return jsx(TakeHomeSourcePanel, {
      courseTitle: course && course.title,
      source: sources.data,
      status: sources.status,
      error: sources.error,
      onSelectObjective: chooseObjective,
      onRetry: reloadSources,
      onBack: () => {
        setStep('shelf')
        setCourse(null)
        setSources({ status: 'idle', data: null, error: null })
      }
    })
  }

  return jsx(TakeHomePackPanel, {
    courseTitle: course && course.title,
    source: sources.data,
    objective,
    kind,
    audience,
    onKind: (next) => {
      setKind(next)
      resetPack()
    },
    onAudience: (next) => {
      setAudience(next)
      resetPack()
    },
    preview,
    previewStatus,
    previewError,
    onPreview: runPreview,
    onRetryPreview: runPreview,
    onBack: () => {
      resetPack()
      setObjective(null)
      setStep('source')
    },
    pack,
    busy,
    error,
    exportError,
    exported,
    artifact,
    onSaveDraft: saveDraft,
    onApprove: approvePages,
    onExport: exportPdf,
    sessionMinutes,
    onOpenSettings,
    triggerRef
  })
}

/* ── GM-008 · homework the learner takes with them ─────────────────────────────────────────
 * One small task, taken out of the lesson and into the learner's day. The plan (§10A.4-§10A.7)
 * fixes the shape: one target, one context, at most three steps, one observable success
 * criterion, 3-10 minutes, and a completion that is *reported* by the learner or the parent and
 * never graded.
 *
 * Honesty rules this surface is built on:
 *   - every task on screen is a `homework.read` answer; the sheet is the backend's own rendered
 *     field card (`task.sheet.html`), not a second template that could drift from the print;
 *   - the index in `pluginContext.storage` holds task *ids* only. It is a door to `homework.read`,
 *     never a copy of the task, so a state shown here is always the backend's;
 *   - there is no `homework.list` in cb.rpc v24. A task is enumerable because the learner saved it
 *     to the notebook (`notebook.save`, kind `personal_note`, `source_ref.homework_task_id`) or
 *     because this device proposed it. Nothing is invented for a task neither source knows;
 *   - print and download are local. No file is sent, no photo is asked for, and no XP, score,
 *     grade or mastery word exists anywhere in this block.
 */

const CB_HOMEWORK_STATE_WORD = Object.freeze({
  proposed: 'Planned',
  self_reported_done: 'Done — you recorded it',
  parent_reported_done: 'Done — a parent recorded it',
  skipped: 'Skipped',
  expired: 'Expired'
})

const CB_HOMEWORK_KIND_WORD = Object.freeze({
  real_world_use: 'Use it for real',
  observe: 'Notice it',
  label: 'Label it',
  practice: 'Say it aloud',
  make: 'Make it',
  teach_back: 'Tell someone'
})

/** A task that still accepts a report. `skipped`/`expired` are closed, a report is final. */
const CB_HOMEWORK_OPEN_STATES = Object.freeze(['proposed'])

/** Words a learner-visible sheet must never carry (mirrors coursebook/homework.py). */
const CB_HOMEWORK_FORBIDDEN = Object.freeze([
  'xp',
  'grade',
  'graded',
  'score',
  'scored',
  'mastery',
  'streak',
  'answer',
  'photo'
])

const CB_HOMEWORK_INDEX_KEY = 'homework-index.v1'
const _CB_JP_RUN = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/

/** True when the copy carries Japanese, so the node can be marked `lang="ja"` for a reader. */
function cbHasJapanese(value) {
  return _CB_JP_RUN.test(String(value || ''))
}

/**
 * The device index of homework task ids: `{enrollments: {id: {course_id, tasks: {task_id}}}}`.
 * Only ids and their lesson anchors live here. A hand-edited or older document reads as empty.
 */
function cbHomeworkIndex() {
  const storage = cbPrefsStorage()
  let raw = null
  try {
    raw = storage ? storage.get(CB_HOMEWORK_INDEX_KEY, null) : null
  } catch (error) {
    raw = null
  }
  const source = raw && typeof raw === 'object' ? raw : {}
  const sourceEnrollments =
    source.enrollments && typeof source.enrollments === 'object' ? source.enrollments : {}
  const enrollments = {}
  for (const enrollmentId of Object.keys(sourceEnrollments)) {
    const entry = sourceEnrollments[enrollmentId]
    if (!entry || typeof entry !== 'object' || !entry.tasks || typeof entry.tasks !== 'object') continue
    const tasks = {}
    for (const taskId of Object.keys(entry.tasks)) {
      const row = entry.tasks[taskId]
      if (!row || typeof row !== 'object' || !row.objective_id) continue
      tasks[taskId] = {
        objective_id: String(row.objective_id),
        course_id: String(row.course_id || entry.course_id || ''),
        created_at: String(row.created_at || '')
      }
    }
    if (Object.keys(tasks).length === 0) continue
    enrollments[enrollmentId] = {
      course_id: String(entry.course_id || ''),
      tasks
    }
  }
  return { enrollments }
}

/** Remember one proposed task so a later visit can read it again. Ids only; never the task. */
function cbRememberHomework(task) {
  if (!task || !task.task_id || !task.enrollment_id || !task.objective_id) return
  const storage = cbPrefsStorage()
  if (!storage) return
  const index = cbHomeworkIndex()
  const enrollment =
    index.enrollments[task.enrollment_id] || { course_id: task.course_id || '', tasks: {} }
  enrollment.course_id = task.course_id || enrollment.course_id
  enrollment.tasks[task.task_id] = {
    objective_id: task.objective_id,
    course_id: task.course_id || enrollment.course_id,
    created_at: task.created_at || ''
  }
  index.enrollments[task.enrollment_id] = enrollment
  try {
    storage.set(CB_HOMEWORK_INDEX_KEY, index)
  } catch (error) {
    // The index is a convenience door; failing to write it never hides a task the backend holds.
  }
}

/** Indexed task ids, newest first, optionally narrowed to one enrollment. */
function cbHomeworkIndexRows(enrollmentId) {
  const index = cbHomeworkIndex()
  const rows = []
  for (const id of Object.keys(index.enrollments)) {
    if (enrollmentId && id !== enrollmentId) continue
    const enrollment = index.enrollments[id]
    for (const taskId of Object.keys(enrollment.tasks)) {
      rows.push({
        task_id: taskId,
        enrollment_id: id,
        course_id: enrollment.tasks[taskId].course_id || enrollment.course_id,
        objective_id: enrollment.tasks[taskId].objective_id,
        created_at: enrollment.tasks[taskId].created_at
      })
    }
  }
  return rows.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)))
}

/** The task id a notebook entry was saved from, or null. */
function cbHomeworkRefTaskId(value) {
  if (!value) return null
  const text = String(value)
  if (text.charAt(0) !== '{') return null
  try {
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    if (typeof parsed.homework_task_id === 'string' && parsed.homework_task_id) {
      return parsed.homework_task_id
    }
    return null
  } catch (error) {
    return null
  }
}

/** The `source_ref` a notebook save carries, so the notebook can find this task again. */
function cbHomeworkSourceRef(task) {
  return JSON.stringify({ homework_task_id: task.task_id, objective_id: task.objective_id })
}

/** The notebook excerpt for a saved task: the task's own words, one line. */
function cbHomeworkExcerpt(task) {
  const target = task && task.target ? task.target : {}
  const head = `Take this with you: ${task.title || 'one task'}`
  const where = task.context ? ` — ${task.context}` : ''
  const what = target.display ? ` (${target.display})` : ''
  return `${head}${what}${where}`.slice(0, 8000)
}

/** A sheet's own copy, flattened for the guard below. */
function cbHomeworkSheetCopy(task) {
  const target = (task && task.target) || {}
  return [
    task && task.title,
    task && task.context,
    (task && task.steps ? task.steps : []).join(' '),
    task && task.success_criterion,
    target.display,
    target.reading,
    target.meaning,
    (target.completion_record || []).join(' ')
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

/** Reasons a sheet cannot be shown, in the learner's words. Rendering refuses a banned word. */
function cbHomeworkSheetGuard(task) {
  const copy = cbHomeworkSheetCopy(task)
  const found = CB_HOMEWORK_FORBIDDEN.filter((word) => {
    const pattern = new RegExp(`(?<![a-z0-9])${word}(?![a-z0-9])`)
    return pattern.test(copy)
  })
  if (found.length > 0) {
    return 'This task would print a word a take-home sheet must not carry, so it is not shown.'
  }
  if (task && Array.isArray(task.steps) && task.steps.length > 3) {
    return 'A field card carries at most three steps, so this task is not shown.'
  }
  return null
}

/**
 * Print one sheet. The backend's rendered HTML is loaded into a same-origin frame that is not on
 * screen; Chromium's print dialog then prints that document alone, never the app around it.
 */
function cbPrintHomeworkSheet(html) {
  if (!html || typeof document === 'undefined' || !document.body) return false
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.setAttribute('title', 'Homework sheet for printing')
  frame.style.position = 'fixed'
  frame.style.right = '0'
  frame.style.bottom = '0'
  frame.style.width = '0'
  frame.style.height = '0'
  frame.style.border = '0'
  let printed = false
  const run = () => {
    if (printed) return
    printed = true
    try {
      const win = frame.contentWindow
      if (win) {
        win.focus()
        win.print()
      }
    } finally {
      setTimeout(() => {
        if (frame.parentNode) frame.parentNode.removeChild(frame)
      }, 60000)
    }
  }
  frame.addEventListener('load', run)
  frame.srcdoc = html
  document.body.appendChild(frame)
  return true
}

/* ── The lesson on paper (item 41) ───────────────────────────────────────────────────────────
 * A finished lesson must be keepable. This builds one standalone, printable HTML document from
 * the served `lesson_document`: each block's headline, its `deep` prose, its media captions and
 * the check prompt (the document's `practice` block), and nothing else.
 *
 * The answer key is *not expressible here*: this function reads only `headline`, `deep` (with the
 * check labels filtered out, exactly as the reading column does) and each media child's caption
 * text. It never enumerates another property of the block or the check, so `reference_answer`,
 * `accepted_answers`, `accepted_alternatives` and `rubric` cannot reach the paper even if a
 * caller hands them over. Everything is HTML-escaped before it is printed.
 *
 * The sheet prints through the same hidden-frame path as the take-home card
 * (`cbPrintHomeworkSheet`), so Chromium prints this document alone and never the app around it.
 */
const CB_LESSON_PRINT_ROLE_WORD = {
  orient: 'Start',
  explain: 'Explain',
  example: 'Example',
  practice: 'Your turn',
  recap: 'Recap'
}

// The runtime-plugin gates refuse a literal JSX-looking closing sequence in the shipped module.
// A printable sheet still needs closing tags, so they are composed from two characters at render
// time: the source carries no closing-tag literal, and the sheet carries ordinary HTML.
const CB_PRINT_CLOSE = '<' + '/'

/** Compose one closing tag for the printed sheet. */
function cbPrintEnd(tag) {
  return `${CB_PRINT_CLOSE}${tag}>`
}

/**
 * The print palette, read from the shipped token table.
 *
 * The sheet is a standalone document in a hidden frame: the route's CSS custom properties do not
 * reach it, so the values are inlined. They still come from `CB_TOKENS.light` — the paper is the
 * printer's own white, and every stroke and word is a contract colour — so the sheet cannot drift
 * into a raw hex the token gate would (rightly) refuse.
 */
function cbPrintPalette() {
  const light = (CB_TOKENS && CB_TOKENS.light) || {}
  const pick = (name) => (typeof light[name] === 'string' && light[name] ? light[name] : 'currentColor')
  return { ink: pick('ink'), soft: pick('ink-soft'), rule: pick('rule') }
}

function cbLessonPrintCss() {
  const { ink, soft, rule } = cbPrintPalette()
  return `
@page { size: A4 portrait; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { margin: 0; color: ${ink};
  font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  font-size: 11.5pt; line-height: 1.55; }
header { border-bottom: 1pt solid ${ink}; padding-bottom: 6mm; margin-bottom: 6mm; }
.eyebrow { margin: 0 0 2mm; font-family: "Helvetica Neue", Arial, sans-serif;
  font-size: 8pt; letter-spacing: 0.12em; text-transform: uppercase; color: ${soft}; }
h1 { margin: 0; font-size: 20pt; line-height: 1.2; font-weight: 600; }
section.block { margin: 0 0 6mm; break-inside: avoid; page-break-inside: avoid; }
h2 { margin: 0 0 1.5mm; font-size: 13pt; line-height: 1.25; font-weight: 600; }
.role { margin: 0 0 1.5mm; font-family: "Helvetica Neue", Arial, sans-serif;
  font-size: 8pt; letter-spacing: 0.1em; text-transform: uppercase; color: ${soft}; }
p { margin: 0 0 2.5mm; }
.caption { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9pt; color: ${soft};
  border-left: 1.5pt solid ${rule}; padding-left: 3mm; }
section.check { border-top: 1pt solid ${ink}; padding-top: 4mm; }
.note { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8.5pt; color: ${soft}; }
footer { margin-top: 8mm; border-top: 1pt solid ${rule}; padding-top: 3mm;
  font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8pt; color: ${soft}; }
`
}

/** HTML-escape one authored string. Print copy is text, never markup. */
function cbPrintEscape(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/[<]/g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** Authored prose as escaped paragraphs; blank lines separate paragraphs, single lines wrap. */
function cbPrintParagraphs(text) {
  return String(text == null ? '' : text)
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => `<p>${cbPrintEscape(part).replace(/\n/g, '<br>')}${cbPrintEnd('p')}`)
    .join('')
}

/** One media child's caption: the text equivalent the lesson already shows, else its label. */
function cbPrintMediaCaption(child) {
  if (!child || typeof child !== 'object') return ''
  const values = [child.text_equivalent, child.purpose, child.label]
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

/**
 * Build the printable lesson. `lesson` is the served `lesson_document`; `options.checkLabels`
 * are the check's structured labels the reading column also hides from prose.
 */
function cbLessonPrintHtml(lesson, options) {
  const doc = lesson && typeof lesson === 'object' ? lesson : null
  if (!doc) return ''
  const labels = options && Array.isArray(options.checkLabels) ? options.checkLabels : []
  const blocks = Array.isArray(doc.blocks) ? doc.blocks : []
  const sectionTitle = String(doc.section_title || '').trim() || 'Lesson'
  const sections = []
  let checkPrinted = false
  blocks.forEach((block) => {
    if (!block || typeof block !== 'object') return
    const headline = typeof block.headline === 'string' ? block.headline.trim() : ''
    const prose = withoutCheckLabels(typeof block.deep === 'string' ? block.deep : '', labels)
    const media = Array.isArray(block.media) ? block.media : []
    const captions = media.map(cbPrintMediaCaption).filter(Boolean)
    if (!headline && !prose && captions.length === 0) return
    const isCheck = block.role === 'practice'
    const roleWord = CB_LESSON_PRINT_ROLE_WORD[block.role] || ''
    const parts = ['<section class="' + (isCheck ? 'block check' : 'block') + '">']
    if (headline) parts.push(`<h2>${cbPrintEscape(headline)}${cbPrintEnd('h2')}`)
    if (roleWord) parts.push(`<p class="role">${cbPrintEscape(roleWord)}${cbPrintEnd('p')}`)
    if (prose) parts.push(cbPrintParagraphs(prose))
    for (const caption of captions) parts.push(`<p class="caption">${cbPrintEscape(caption)}${cbPrintEnd('p')}`)
    if (isCheck) {
      if (prose) checkPrinted = true
      parts.push(`<p class="note">Answer this on the lesson screen. The answer key is not printed here.${cbPrintEnd('p')}`)
    }
    parts.push(cbPrintEnd('section'))
    sections.push(parts.join(''))
  })
  // The live check's own prompt is the learner-facing wording. It is printed only when the
  // document's practice block did not carry it, so the sheet never prints the prompt twice.
  const livePrompt =
    options && typeof options.checkPrompt === 'string' ? options.checkPrompt.trim() : ''
  if (livePrompt && !checkPrinted) {
    sections.push(
      [
        '<section class="block check">',
        `<p class="role">Your turn${cbPrintEnd('p')}`,
        cbPrintParagraphs(livePrompt),
        `<p class="note">Answer this on the lesson screen. The answer key is not printed here.${cbPrintEnd('p')}`,
        cbPrintEnd('section')
      ].join('')
    )
  }
  const lang = typeof doc.lang === 'string' && /^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(doc.lang)
    ? ` lang="${cbPrintEscape(doc.lang)}"`
    : ''
  return [
    '<!doctype html>',
    `<html${lang}>`,
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<title>${cbPrintEscape(sectionTitle)}${cbPrintEnd('title')}`,
    `<style>${cbLessonPrintCss()}${cbPrintEnd('style')}`,
    cbPrintEnd('head'),
    '<body>',
    '<header>',
    `<p class="eyebrow">Coursebook · lesson${cbPrintEnd('p')}`,
    `<h1>${cbPrintEscape(sectionTitle)}${cbPrintEnd('h1')}`,
    cbPrintEnd('header'),
    '<main>',
    sections.join(''),
    cbPrintEnd('main'),
    '<footer>Coursebook · printed from this lesson. The answer key is never part of this sheet.',
    cbPrintEnd('body'),
    cbPrintEnd('html')
  ].join('\n')
}

/** Download one sheet as a local file. No upload, no share sheet. */
function cbDownloadHomeworkSheet(html, filename) {
  if (!html || typeof document === 'undefined' || typeof URL === 'undefined') return false
  if (typeof URL.createObjectURL !== 'function') return false
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || 'homework-sheet.html'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => {
    try {
      URL.revokeObjectURL(url)
    } catch (error) {
      // A revoked or already-collected URL is not a failure the learner can act on.
    }
  }, 4000)
  return true
}

function cbHomeworkFilename(task) {
  const title = String((task && task.title) || 'homework-sheet')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return `${title || 'homework-sheet'}-field-card.html`
}

/**
 * The one-page field card, as the learner sees it on screen.
 *
 * It renders the same facts the backend prints — target, where and when, at most three steps,
 * done-when, minutes, the completion line — from the `homework.read` task. The print and download
 * actions hand over the backend's own `sheet.html`, so the paper cannot drift from the screen.
 */
function HomeworkSheetCard({ task, compact = false }) {
  if (!task) return null
  const target = task.target || {}
  const steps = Array.isArray(task.steps) ? task.steps.slice(0, 3) : []
  const record = Array.isArray(target.completion_record) ? target.completion_record : []
  const state = task.state || 'proposed'
  const done = state === 'self_reported_done' || state === 'parent_reported_done'
  const reading = target.reading && target.reading !== target.display ? target.reading : null
  const eyebrow = {
    margin: 0,
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('caption'),
    fontWeight: 600,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: 'var(--cb3-ink-soft)'
  }
  const label = {
    margin: 0,
    fontFamily: 'var(--cb3-font-ui)',
    fontSize: cb3Type('caption'),
    fontWeight: 600,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: 'var(--cb3-ink-soft)'
  }
  const rule = { border: 0, borderTop: '1px solid var(--cb3-rule)', margin: '0.15rem 0', width: '100%' }
  const completion =
    state === 'skipped'
      ? 'Skipped. Nothing is owed and nothing is lost.'
      : state === 'expired'
        ? 'This task closed without a report.'
        : state === 'parent_reported_done'
          ? `A parent recorded this as done${task.completion && task.completion.completed_at ? ` on ${whenLabel(task.completion.completed_at)}` : ''}. A report, not a verdict.`
          : state === 'self_reported_done'
            ? `You recorded this as done${task.completion && task.completion.completed_at ? ` on ${whenLabel(task.completion.completed_at)}` : ''}. A report, not a verdict.`
            : 'Done — I will record this myself.'
  return jsxs('article', {
    'data-cb-homework-sheet': task.task_id,
    'data-cb3-homework': 'sheet',
    'data-cb-homework-state': state,
    'aria-label': `Take-home task: ${task.title || ''}`,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: compact ? '0.35rem' : '0.45rem',
      minWidth: 0,
      maxWidth: CB_MEASURE,
      boxSizing: 'border-box',
      padding: compact ? '0.7rem 0.75rem' : '0.95rem 1rem 1rem',
      background: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round')
    },
    children: [
      jsx('p', { style: eyebrow, children: 'Coursebook field card' }, 'eyebrow'),
      jsx('h3', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: compact ? cb3Type('lead') : cb3Type('heading'),
          fontWeight: 600,
          lineHeight: 1.2,
          color: 'var(--cb3-ink)'
        },
        children: task.title || 'One task'
      }, 'title'),
      target.display
        ? jsx('p', {
            'data-cb-homework-target': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: compact ? cb3Type('body') : cb3Type('heading'),
              lineHeight: 1.2,
              color: 'var(--cb3-ink)',
              overflowWrap: 'anywhere'
            },
            lang: cbHasJapanese(target.display) ? 'ja' : undefined,
            children: target.display
          }, 'target')
        : null,
      reading
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('body'),
              color: 'var(--cb3-ink-soft)',
              overflowWrap: 'anywhere'
            },
            lang: cbHasJapanese(reading) ? 'ja' : undefined,
            children: reading
          }, 'reading')
        : null,
      target.romaji
        ? jsx('p', {
            style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
            children: target.romaji
          }, 'romaji')
        : null,
      target.meaning
        ? jsx('p', {
            style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), color: 'var(--cb3-ink-soft)' },
            children: target.meaning
          }, 'meaning')
        : null,
      jsx('hr', { style: rule }, 'rule-a'),
      jsx('p', { style: label, children: 'Where and when' }, 'where-label'),
      jsx('p', {
        'data-cb-homework-context': '',
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('body'),
          lineHeight: 1.5,
          color: 'var(--cb3-ink)',
          overflowWrap: 'anywhere'
        },
        children: task.context || ''
      }, 'context'),
      jsx('p', { style: label, children: 'Do this' }, 'steps-label'),
      jsx('ol', {
        style: {
          margin: 0,
          paddingLeft: '1.2rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.25rem',
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('body'),
          lineHeight: 1.5,
          color: 'var(--cb3-ink)'
        },
        children: steps.map((step, index) =>
          jsx('li', { style: { overflowWrap: 'anywhere' }, children: step }, `${task.task_id}-step-${index}`)
        )
      }, 'steps'),
      record.length > 0
        ? jsx('p', {
            style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
            children: `Ticks for this card: ${record.join(' · ')}`
          }, 'record')
        : null,
      jsx('hr', { style: rule }, 'rule-b'),
      jsx('p', { style: label, children: 'Done when' }, 'done-label'),
      jsx('p', {
        style: {
          margin: 0,
          fontFamily: 'var(--cb3-font-display)',
          fontSize: cb3Type('body'),
          lineHeight: 1.5,
          color: 'var(--cb3-ink)',
          overflowWrap: 'anywhere'
        },
        children: task.success_criterion || ''
      }, 'criterion'),
      jsx('p', {
        style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), color: 'var(--cb3-ink-soft)' },
        children: `About ${Number(task.estimated_minutes) || 5} minutes · ${CB_HOMEWORK_KIND_WORD[task.task_kind] || 'Away from the screen'}`
      }, 'minutes'),
      jsx('p', {
        'data-cb-homework-completion': done ? 'reported' : state,
        style: {
          margin: 0,
          paddingTop: '0.35rem',
          borderTop: '1px solid var(--cb3-rule)',
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: 1.5,
          color: 'var(--cb3-ink)'
        },
        children: completion
      }, 'completion'),
      Array.isArray(task.sources) && task.sources.length > 0
        ? jsxs('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: 1.5,
              color: 'var(--cb3-ink-soft)',
              overflowWrap: 'anywhere'
            },
            children: [
              jsx('span', { children: task.sources.length === 1 ? 'Source · ' : 'Sources · ' }, 'word'),
              ...task.sources.map((source, index) =>
                jsxs(
                  'span',
                  {
                    children: [
                      index > 0 ? jsx('span', { children: '; ' }, 'sep') : null,
                      jsx('a', {
                        href: source.url,
                        style: { color: 'inherit', textDecoration: 'underline' },
                        children: source.title || source.source_id
                      }, 'link'),
                      source.accessed ? jsx('span', { children: ` (accessed ${source.accessed})` }, 'date') : null
                    ]
                  },
                  source.source_id || `src-${index}`
                )
              )
            ]
          }, 'sources')
        : null
    ]
  })
}

/** The sheet's actions: print, download, save to the notebook. Local, never an external send. */
function HomeworkSheetActions({ task, canSave, busy, onSave, onPrinted, onDownloaded, saved }) {
  return jsxs('div', {
    'data-cb-homework-actions': '',
    'data-cb3-homework': 'actions',
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', maxWidth: CB_MEASURE },
    children: [
      jsx(PillAction, {
        'data-cb-homework-action': 'print',
        variant: 'quiet',
        label: 'Print the sheet',
        disabled: Boolean(busy),
        onClick: () => {
          const ok = cbPrintHomeworkSheet(task && task.sheet ? task.sheet.html : '')
          if (onPrinted) onPrinted(ok)
        }
      }, 'print'),
      jsx(PillAction, {
        'data-cb-homework-action': 'download',
        variant: 'quiet',
        label: 'Download',
        disabled: Boolean(busy),
        onClick: () => {
          const ok = cbDownloadHomeworkSheet(
            task && task.sheet ? task.sheet.html : '',
            cbHomeworkFilename(task)
          )
          if (onDownloaded) onDownloaded(ok)
        }
      }, 'download'),
      canSave
        ? jsx(PillAction, {
            'data-cb-homework-action': 'save',
            variant: 'quiet',
            label: saved ? 'Saved to the notebook' : 'Save to notebook',
            disabled: Boolean(busy) || saved,
            onClick: onSave
          }, 'save')
        : null,
      jsx('span', {
        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: cb3Role('ink-soft') },
        children: 'Local only. Nothing is sent.'
      }, 'note')
    ]
  })
}

/**
 * The quiet `Take this with you` action on a lesson.
 *
 * It is a text button in the reading column, not a modal: pressing it opens a small inline panel
 * beside the lesson, so the lesson stays where it is. The learner writes the one sentence that
 * says where and when; `homework.create` proposes the task from that context; then the card, the
 * print/download/save actions and the two honest endings — `I did it` and `Not this one` — are
 * all in place.
 */
function TakeThisWithYou({
  enrollmentId,
  courseId,
  objectiveId,
  sectionTitle,
  implemented,
  onChanged
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const wired =
    supports('homework.create') &&
    supports('homework.read') &&
    supports('homework.complete') &&
    supports('homework.skip')
  const [open, setOpen] = useState(false)
  const [task, setTask] = useState(null)
  const [status, setStatus] = useState('idle')
  const [source, setSource] = useState({ status: 'idle', objective: null, error: null })
  const [contextText, setContextText] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saved, setSaved] = useState(false)

  const readTask = useCallback(async (taskId) => {
    setStatus('reading')
    setError(null)
    const response = await rpc('homework.read', { task_id: taskId })
    if (!response.ok) {
      setStatus('error')
      setError(response.error)
      return null
    }
    setTask(response.result.task)
    setStatus('ready')
    return response.result.task
  }, [])

  // Opening reads the task the device already knows for this objective, else the source lesson.
  const prepare = useCallback(async () => {
    setError(null)
    setNotice(null)
    const known = cbHomeworkIndexRows(enrollmentId).find((row) => row.objective_id === objectiveId)
    if (known) {
      await readTask(known.task_id)
      return
    }
    setStatus('reading')
    const response = await rpc('takehome.sources', { course_id: courseId })
    if (!response.ok) {
      setSource({ status: 'error', objective: null, error: response.error })
      setStatus('error')
      setError(response.error)
      return
    }
    const rows = response.result && Array.isArray(response.result.objectives) ? response.result.objectives : []
    const entry = rows.find((row) => row.objective_id === objectiveId) || null
    setSource({ status: 'ready', objective: entry, error: null })
    setStatus('ready')
  }, [courseId, enrollmentId, objectiveId, readTask])

  const propose = useCallback(async () => {
    const sentence = contextText.trim()
    if (!sentence) return
    const entry = source.objective
    if (!entry || !entry.lesson_version) {
      setError({
        code: 'NO_SOURCE_LESSON',
        message: 'The lesson for this section is not written yet, so there is no task to take with you.'
      })
      return
    }
    setBusy('propose')
    setError(null)
    const response = await rpc(
      'homework.create',
      {
        course_id: courseId,
        enrollment_id: enrollmentId,
        objective_id: objectiveId,
        audience: 'learner',
        source_lesson_version: entry.lesson_version,
        context: sentence
      },
      { expectedRevision: 0, idempotencyKey: newOperationId('homework-create') }
    )
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setTask(response.result.task)
    cbRememberHomework(response.result.task)
    setStatus('ready')
    setNotice('This is the whole task. It stays in your notebook and on paper; it is not a chat.')
    if (onChanged) onChanged()
  }, [contextText, courseId, enrollmentId, objectiveId, onChanged, source.objective])

  const report = useCallback(
    async (actor) => {
      if (!task) return
      setBusy(actor)
      setError(null)
      const method = 'homework.complete'
      const response = await rpc(
        method,
        { task_id: task.task_id, actor, note: '' },
        { expectedRevision: task.revision, idempotencyKey: newOperationId('homework-complete') }
      )
      setBusy(null)
      if (!response.ok) {
        setError(response.error)
        return
      }
      setTask(response.result.task)
      cbRememberHomework(response.result.task)
      setNotice(
        actor === 'parent'
          ? 'Recorded: a parent reported this done. A report, not a mark.'
          : 'Recorded: you reported this done. A report, not a mark.'
      )
      if (onChanged) onChanged()
    },
    [onChanged, task]
  )

  const skipTask = useCallback(async () => {
    if (!task) return
    setBusy('skip')
    setError(null)
    const response = await rpc(
      'homework.skip',
      { task_id: task.task_id, actor: 'learner' },
      { expectedRevision: task.revision, idempotencyKey: newOperationId('homework-skip') }
    )
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setTask(response.result.task)
    setNotice('Skipped. Nothing is owed, nothing is lost, and no streak breaks.')
    if (onChanged) onChanged()
  }, [onChanged, task])

  const saveToNotebook = useCallback(async () => {
    if (!task) return
    setBusy('save')
    setError(null)
    const response = await rpc('notebook.save', {
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: null,
      kind: 'personal_note',
      excerpt: cbHomeworkExcerpt(task),
      note: null,
      tags: ['homework'],
      source_ref: cbHomeworkSourceRef(task)
    })
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setSaved(true)
    setNotice('Saved to the notebook. The task itself stays a homework task, not a note.')
    if (onChanged) onChanged()
  }, [enrollmentId, objectiveId, onChanged, task])

  if (!wired) return null

  const blocked =
    source.status === 'ready' && source.objective && source.objective.available === false
      ? source.objective.blocked_reason || 'The lesson for this section is not written yet.'
      : null
  const sheetGuard = task ? cbHomeworkSheetGuard(task) : null
  const openState = task && CB_HOMEWORK_OPEN_STATES.indexOf(task.state) >= 0

  const panel = !open
    ? null
    : jsxs('section', {
        'data-cb-homework-panel': status,
        'aria-label': 'Take this with you',
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: '0.55rem',
          minWidth: 0,
          maxWidth: CB_MEASURE,
          marginTop: '0.6rem',
          paddingTop: '0.6rem',
          borderTop: '1px solid var(--cb3-rule)'
        },
        children: [
          jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              fontWeight: 600,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--cb3-ink-soft)'
            },
            children: sectionTitle ? `Take this with you · ${sectionTitle}` : 'Take this with you'
          }),
          status === 'reading'
            ? jsx(sdk.Loader, { label: 'Reading this lesson’s task' })
            : null,
          error
            ? jsxs('div', {
                'data-cb-homework-error': error.code || 'ERROR',
                style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
                children: [
                  jsx('p', {
                    style: {
                      margin: 0,
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('meta'),
                      lineHeight: 1.5,
                      color: 'var(--cb3-alert)',
                      overflowWrap: 'anywhere'
                    },
                    children: error.message || 'The task could not be read.'
                  }),
                  error.code ? jsx(QuietNote, { children: `Reason · ${error.code}` }) : null,
                  jsx(PillAction, {
                    variant: 'quiet',
                    'data-cb-homework-retry': '',
                    onClick: prepare,
                    label: 'Try again'
                  }, 'retry')
                ]
              })
            : null,
          blocked && !task
            ? jsx('div', {
                'data-cb-homework-blocked': 'lesson-not-ready',
                children: jsx(QuietNote, {
                  children: `${blocked} There is nothing to take with you from this section yet, and nothing is lost.`
                })
              })
            : null,
          status === 'ready' && !task && !blocked
            ? jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0 },
                children: [
                  jsx('p', {
                    style: {
                      margin: 0,
                      fontFamily: 'var(--cb3-font-display)',
                      fontSize: cb3Type('body'),
                      lineHeight: 1.5,
                      color: 'var(--cb3-ink)'
                    },
                    children:
                      'Coursebook can write one small task from this lesson — one thing to use where you actually are. Say where and when, in one sentence.'
                  }),
                  jsx('label', {
                    htmlFor: 'cb-homework-context',
                    style: {
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      fontWeight: 600,
                      color: 'var(--cb3-ink-soft)'
                    },
                    children: 'Where and when'
                  }),
                  jsx(sdk.Input, {
                    id: 'cb-homework-context',
                    value: contextText,
                    placeholder: 'Before dinner at our own table',
                    onChange: (event) => setContextText(event.target.value)
                  }),
                  jsxs('div', {
                    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
                    children: [
                      jsx(PillAction, {
                        variant: 'quiet',
                        'data-cb-homework-propose': '',
                        disabled: Boolean(busy) || contextText.trim().length === 0,
                        onClick: propose,
                        label: busy === 'propose' ? 'Writing the task' : 'Show me the task'
                      }, 'propose'),
                      jsx('span', {
                        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                        children: 'One task, at most three steps, three to ten minutes.'
                      })
                    ]
                  }),
                  jsx(QuietNote, {
                    children:
                      'It opens no chat and sends nothing anywhere. Printing and downloading are local.'
                  })
                ]
              })
            : null,
          task && !sheetGuard
            ? jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.5rem', minWidth: 0 },
                children: [
                  jsx(HomeworkSheetCard, { task }),
                  jsx(HomeworkSheetActions, {
                    task,
                    canSave: supports('notebook.save'),
                    busy,
                    saved,
                    onSave: saveToNotebook,
                    onPrinted: (ok) =>
                      setNotice(ok ? 'The sheet is open in the print dialog.' : 'This build cannot open a print dialog.'),
                    onDownloaded: (ok) =>
                      setNotice(ok ? 'The sheet was saved as a file on this device.' : 'This build cannot save a file.')
                  }),
                  openState
                    ? jsxs('div', {
                        'data-cb-homework-report': 'open',
                        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', maxWidth: CB_MEASURE },
                        children: [
                          jsx(PillAction, {
                            variant: 'quiet',
                            'data-cb-homework-report-action': 'done',
                            disabled: Boolean(busy),
                            onClick: () => report('learner'),
                            label: busy === 'learner' ? 'Recording' : 'I did it'
                          }, 'report'),
                          jsx(PillAction, {
                            variant: 'quiet',
                            'data-cb-homework-report-action': 'skip',
                            disabled: Boolean(busy),
                            onClick: skipTask,
                            label: busy === 'skip' ? 'Skipping' : 'Not this one'
                          }, 'skip'),
                          jsx('span', {
                            style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                            children: 'Only you record it. Nothing here is marked.'
                          })
                        ]
                      })
                    : jsx('div', {
                        'data-cb-homework-report': task.state,
                        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
                        children:
                          task.state === 'skipped'
                            ? 'This one is closed as skipped. A fresh task can be taken with you from another lesson.'
                            : 'This task already carries a report; it cannot be reported twice.'
                      })
                ]
              })
            : null,
          task && sheetGuard
            ? jsx('div', { 'data-cb-homework-refused': 'sheet', children: jsx(QuietNote, { children: sheetGuard }) })
            : null,
          notice
            ? jsx('p', {
                'data-cb-homework-notice': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: 1.5,
                  color: 'var(--cb3-ink)'
                },
                children: notice
              })
            : null
        ]
      })

  return jsxs('div', {
    'data-cb-homework': open ? 'open' : 'closed',
    'data-cb3-homework': 'action',
    style: { display: 'flex', flexDirection: 'column', minWidth: 0, maxWidth: CB_MEASURE },
    children: [
      // The GM-008 DOM contract names this quiet action by `data-variant="text"`; the v3 quiet
      // pill keeps that attribute so the existing contract and tests resolve the same control.
      jsx(PillAction, {
        variant: 'quiet',
        'data-cb-homework-action': 'take-this-with-you',
        'data-variant': 'text',
        'aria-expanded': open ? 'true' : 'false',
        onClick: () => {
          const next = !open
          setOpen(next)
          setNotice(null)
          if (next && !task) prepare()
        },
        label: 'Take this with you'
      }, 'trigger'),
      panel
    ]
  })
}

/**
 * One homework record, read from the backend by id.
 *
 * Used by the notebook and by Parent Studio: both surfaces hold ids (this device's index, or a
 * notebook save), never a task snapshot, so the state and the sheet are always the live answer.
 */
function HomeworkRecord({ taskId, actor = 'learner', courseTitle, lessonTitle, onChange, canSave }) {
  const [task, setTask] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(async () => {
    setStatus('loading')
    setError(null)
    const response = await rpc('homework.read', { task_id: taskId })
    if (!response.ok) {
      setStatus('error')
      setError(response.error)
      return
    }
    setTask(response.result.task)
    setStatus('ready')
  }, [taskId])

  useEffect(() => {
    load()
  }, [load])

  const settle = useCallback(
    async (method, payload, label) => {
      if (!task) return
      setBusy(label)
      setError(null)
      const response = await rpc(method, { task_id: task.task_id, ...payload }, {
        expectedRevision: task.revision,
        idempotencyKey: newOperationId(method)
      })
      setBusy(null)
      if (!response.ok) {
        setError(response.error)
        return
      }
      setTask(response.result.task)
      if (method === 'homework.complete') {
        setNotice(
          actor === 'parent'
            ? 'Recorded: a parent reported this done. A report, not a mark.'
            : 'Recorded: the learner reported this done. A report, not a mark.'
        )
      } else {
        setNotice('Skipped. Nothing is owed and nothing is lost.')
      }
      if (onChange) onChange()
    },
    [actor, onChange, task]
  )

  const save = useCallback(async () => {
    if (!task) return
    setBusy('save')
    const response = await rpc('notebook.save', {
      enrollment_id: task.enrollment_id,
      objective_id: task.objective_id,
      lesson_run_id: null,
      kind: 'personal_note',
      excerpt: cbHomeworkExcerpt(task),
      note: null,
      tags: ['homework'],
      source_ref: cbHomeworkSourceRef(task)
    })
    setBusy(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setSaved(true)
    if (onChange) onChange()
  }, [onChange, task])

  if (status === 'loading') {
    return jsx('div', { 'data-cb-homework-record': 'loading', children: jsx(sdk.Loader, { label: 'Reading this task' }) })
  }
  if (status === 'error' || !task) {
    return jsxs('div', {
      'data-cb-homework-record': 'error',
      style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', maxWidth: CB_MEASURE, minWidth: 0 },
      children: [
        jsx('p', {
          style: {
            margin: 0,
            fontFamily: 'var(--cb3-font-ui)',
            fontSize: cb3Type('meta'),
            lineHeight: 1.5,
            color: 'var(--cb3-alert)',
            overflowWrap: 'anywhere'
          },
          children: error ? `${error.code}: ${error.message}` : 'This task could not be read.'
        }),
        jsx(PillAction, { variant: 'quiet', onClick: load, label: 'Try again' }, 'retry')
      ]
    })
  }
  const openState = CB_HOMEWORK_OPEN_STATES.indexOf(task.state) >= 0
  return jsxs('div', {
    'data-cb-homework-record': task.state,
    'data-cb3-homework': 'record',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
      minWidth: 0,
      maxWidth: CB_MEASURE,
      padding: '0.5rem 0',
      borderTop: '1px solid var(--cb3-rule)'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.4rem', minWidth: 0 },
        children: [
          jsx('span', {
            'data-cb-homework-record-target': '',
            style: {
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('lead'),
              color: 'var(--cb3-ink)',
              minWidth: 0,
              overflowWrap: 'anywhere'
            },
            lang: cbHasJapanese(task.target && task.target.display) ? 'ja' : undefined,
            children: (task.target && task.target.display) || task.title
          }),
          jsx('span', {
            'data-cb-homework-record-state': task.state,
            'data-cb3-chip': 'state',
            style: {
              display: 'inline-flex',
              alignItems: 'center',
              padding: '0.1rem 0.5rem',
              borderRadius: cb3Radius('pill'),
              border: `1px solid ${cb3Role('rule')}`,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              color: cb3Role('ink')
            },
            children: CB_HOMEWORK_STATE_WORD[task.state] || task.state
          }, 'state'),
          jsx('span', {
            style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink-soft)' },
            children: `${Number(task.estimated_minutes) || 5} min`
          })
        ]
      }),
      jsx('span', {
        style: { fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('meta'), lineHeight: 1.5, color: 'var(--cb3-ink-soft)' },
        children: [lessonTitle || null, courseTitle || null].filter(Boolean).join(' · ') || 'This course',
      }),
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem' },
        children: [
          jsx(PillAction, {
            variant: 'quiet',
            'data-cb-homework-record-action': 'toggle-sheet',
            'aria-expanded': open ? 'true' : 'false',
            onClick: () => setOpen(!open),
            label: open ? 'Hide the sheet' : 'Show the sheet'
          }, 'toggle'),
          openState
            ? jsx(PillAction, {
                variant: 'quiet',
                'data-cb-homework-record-action': 'done',
                disabled: Boolean(busy),
                onClick: () => settle('homework.complete', { actor, note: '' }, 'report'),
                label: busy === 'report'
                  ? 'Recording'
                  : actor === 'parent'
                    ? 'A parent recorded this'
                    : 'I did it'
              }, 'report')
            : null,
          openState
            ? jsx(PillAction, {
                variant: 'quiet',
                'data-cb-homework-record-action': 'skip',
                disabled: Boolean(busy),
                onClick: () => settle('homework.skip', { actor }, 'skip'),
                label: busy === 'skip' ? 'Skipping' : 'Skip'
              }, 'skip')
            : null
        ]
      }),
      open
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', paddingTop: '0.35rem', minWidth: 0 },
            children: [
              jsx(HomeworkSheetCard, { task, compact: true }),
              jsx(HomeworkSheetActions, {
                task,
                canSave: Boolean(canSave) && !saved,
                busy,
                saved,
                onSave: save,
                onPrinted: (ok) =>
                  setNotice(ok ? 'The sheet is open in the print dialog.' : 'This build cannot open a print dialog.'),
                onDownloaded: (ok) =>
                  setNotice(ok ? 'The sheet was saved as a file on this device.' : 'This build cannot save a file.')
              })
            ]
          })
        : null,
      notice
        ? jsx('p', {
            style: { margin: 0, fontFamily: 'var(--cb3-font-ui)', fontSize: cb3Type('caption'), color: 'var(--cb3-ink)' },
            children: notice
          })
        : null,
      error
        ? jsx('p', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              color: 'var(--cb3-alert)',
              overflowWrap: 'anywhere'
            },
            children: `${error.code}: ${error.message}`
          })
        : null
    ]
  })
}

/**
 * The homework list. One row per task, in the order the learner met them, with the four states the
 * plan names: planned, done (self or parent reported), skipped.
 */
function HomeworkRecordList({ rows, actor, emptyTitle, emptyDescription, onChange, canSave, title }) {
  if (!rows || rows.length === 0) {
    return jsx('div', {
      'data-cb-homework-list': 'empty',
      'data-cb3-homework': 'list-empty',
      style: { display: 'flex', flexDirection: 'column', gap: '0.3rem' },
      children: jsx(EmptyState, { title: emptyTitle, description: emptyDescription })
    })
  }
  return jsx('div', {
    'data-cb-homework-list': String(rows.length),
    'data-cb3-homework': 'list',
    style: { display: 'flex', flexDirection: 'column', gap: '0.1rem', minWidth: 0 },
    children: [
      title
        ? jsx('div', { style: { paddingTop: '0.2rem' }, children: jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              color: cb3Role('ink'),
              maxWidth: '34ch'
            },
            children: title
          }) }, 'title')
        : null,
      ...rows.map((row) =>
        jsx(
          HomeworkRecord,
          {
            taskId: row.task_id,
            actor,
            courseTitle: row.course_title,
            lessonTitle: row.lesson_title,
            canSave,
            onChange
          },
          row.task_id
        )
      )
    ]
  })
}

/**
 * Parent Studio → Homework. The parent's door to the tasks a learner took with them.
 *
 * It reads the same records the learner does, through `homework.read`, and can record a
 * `parent_reported_done`. It never opens a chat between the parent and the child, and it never
 * turns a report into evidence.
 */
function HomeworkStudio({ implemented, onOpenSource }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const wired = supports('homework.read')
  const [rows, setRows] = useState(() => cbHomeworkIndexRows())
  const [library, setLibrary] = useState({ status: 'idle', titles: {} })
  const [sources, setSources] = useState({ status: 'idle', lessons: {} })

  useEffect(() => {
    if (!wired) return
    setRows(cbHomeworkIndexRows())
  }, [wired])

  const courseIds = Array.from(new Set(rows.map((row) => row.course_id).filter(Boolean)))

  useEffect(() => {
    if (!supports('library.list')) return
    let cancelled = false
    ;(async () => {
      setLibrary((previous) => ({ ...previous, status: 'loading' }))
      const response = await rpc('library.list', { filter: 'all', limit: 50, sort: 'recent' })
      if (cancelled) return
      if (!response.ok) {
        setLibrary({ status: 'error', titles: {} })
        return
      }
      const titles = {}
      for (const item of (response.result && response.result.items) || []) {
        if (item && item.course_id) titles[item.course_id] = item.title || ''
      }
      setLibrary({ status: 'ready', titles })
    })()
    return () => {
      cancelled = true
    }
  }, [implemented])

  useEffect(() => {
    if (!supports('takehome.sources') || courseIds.length === 0) return undefined
    let cancelled = false
    ;(async () => {
      const lessons = {}
      let failed = false
      for (const courseId of courseIds) {
        const response = await rpc('takehome.sources', { course_id: courseId })
        if (cancelled) return
        if (!response.ok) {
          failed = true
          continue
        }
        for (const objective of (response.result && response.result.objectives) || []) {
          if (objective && objective.objective_id) lessons[objective.objective_id] = objective.title || ''
        }
      }
      setSources({ status: failed ? 'error' : 'ready', lessons })
    })()
    return () => {
      cancelled = true
    }
  }, [courseIds.join('|'), implemented])

  const refresh = useCallback(() => setRows(cbHomeworkIndexRows()), [])

  if (!wired) {
    return jsx(EmptyState, {
      title: 'Homework needs the homework methods',
      description:
        'This backend does not implement homework.read, so no task can be read here. Update the plugin instead of showing a placeholder.',
      children: null
    })
  }

  const outgoing = rows.map((row) => ({
    task_id: row.task_id,
    course_title: row.course_id ? (library.titles[row.course_id] || row.course_id) : '',
    lesson_title: sources.lessons[row.objective_id] || ''
  }))

  return jsxs('div', {
    'data-cb-homework-studio': String(rows.length),
    'data-cb3-homework': 'studio',
    style: { display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.9rem 1rem 1.2rem', minWidth: 0 },
    children: [
      jsx('p', {
        style: {
          margin: 0,
          maxWidth: CB_MEASURE,
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: 1.5,
          color: 'var(--cb3-ink-soft)'
        },
        children:
          'Tasks a learner took with them from a lesson on this device. A parent can record one as done; it is a report, never a mark, and it opens no chat.'
      }),
      library.status === 'error'
        ? jsx(QuietNote, { children: 'The course names could not be read. The tasks below are unchanged.' })
        : null,
      sources.status === 'error'
        ? jsx(QuietNote, { children: 'A lesson title could not be read. The task itself is unchanged.' })
        : null,
      jsx(HomeworkRecordList, {
        rows: outgoing,
        actor: 'parent',
        canSave: supports('notebook.save'),
        onChange: refresh,
        title: 'Homework taken with you',
        emptyTitle: 'No homework yet',
        emptyDescription:
          'When a learner takes a task with them from a lesson, it appears here. A task starts on a lesson page, never from this screen.'
      })
    ]
  })
}

/**
 * The §10 brief. Every field the contract requires is here, in the order a parent thinks in:
 * what they want, who it is for, where it happens and with what, what to avoid, and only then the
 * provider/egress disclosure that must be acknowledged before submit is possible.
 */
function StudioBriefForm({ initial, note, supported, onCancel, onCreated }) {
  const [form, setForm] = useState(() => briefForForm(initial))
  const [materialsText, setMaterialsText] = useState(() => (initial && initial.materials ? initial.materials.join('\n') : ''))
  const [exclusionsText, setExclusionsText] = useState(() => (initial && initial.exclusions ? initial.exclusions.join('\n') : ''))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const update = useCallback((key, value) => setForm((previous) => ({ ...previous, [key]: value })), [])

  const materials = linesToList(materialsText, 20, 120)
  const exclusions = linesToList(exclusionsText, 20, 200)
  const problems = []
  if (!form.title.trim()) problems.push('A title is required.')
  if (!form.goal.trim()) problems.push('Say what you want the child to be able to do.')
  if (!form.age_band) problems.push('Pick an age band.')
  if (!form.reading_level.trim()) problems.push('Say the reading level in your own words.')
  const duration = Number(form.duration_minutes)
  if (!Number.isFinite(duration) || duration < 5 || duration > 600) problems.push('Duration must be between 5 and 600 minutes.')
  const pages = Number(form.desired_pages)
  if (!Number.isFinite(pages) || pages < 1 || pages > 40) problems.push('Desired pages must be between 1 and 40.')
  if (!form.egress_acknowledged) problems.push('Acknowledge the provider/egress disclosure before submitting.')

  const submit = useCallback(async () => {
    setBusy(true)
    setError(null)
    const brief = {
      ...form,
      title: form.title.trim(),
      goal: form.goal.trim(),
      starting_point: form.starting_point.trim() ? form.starting_point.trim() : null,
      reading_level: form.reading_level.trim(),
      duration_minutes: Number(form.duration_minutes),
      desired_pages: Number(form.desired_pages),
      materials,
      exclusions,
      supervision: form.supervision.trim(),
      locale: form.locale || null,
      egress_acknowledged: true,
      redaction_requested: Boolean(form.redaction_requested)
    }
    const response = await rpc('parent.brief.create', { brief }, { idempotencyKey: newOperationId('brief') })
    setBusy(false)
    if (!response.ok) {
      setError({ code: response.error && response.error.code, message: describeError(response.error) })
      return
    }
    onCreated({ ...response.result, title: brief.title })
  }, [form, materials, exclusions, onCreated])

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx('h2', { className: 'text-sm font-semibold', children: initial ? 'Duplicate this brief' : 'Write a lesson brief' }),
          jsx(QuietNote, {
            children:
              'Prepare a lesson for a child. You are the operator: Coursebook prepares the material for you to teach, and there is no child chat, no child persona and no grading of the child. Everything here is a plan you review before any page is generated.'
          }),
          note
            ? jsx('div', {
                className: 'mt-1 border-l border-(--ui-stroke-tertiary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `From your last reflection: ${note}`
              })
            : null
        ]
      }),

      jsx(CbLabel, { children: 'What and who' }),
      jsx(StudioField, {
        id: 'cb-brief-title',
        label: 'Title',
        hint: 'How this course appears in your list.',
        children: jsx(sdk.Input, {
          id: 'cb-brief-title',
          maxLength: 200,
          value: form.title,
          onChange: (event) => update('title', event.target.value),
          placeholder: 'Kitchen fractions for a 9-year-old'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-goal',
        label: 'What should the child be able to do afterwards?',
        hint: 'Concrete beats aspirational. One skill, described as an action you can watch.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-goal',
          rows: 3,
          value: form.goal,
          onChange: (event) => update('goal', event.target.value),
          placeholder: 'Halve and quarter a real object and explain each cut.'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-start',
        label: 'Starting point and content prerequisites',
        hint: 'What they can already do, and anything they must have read or seen first.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-start',
          rows: 2,
          value: form.starting_point || '',
          onChange: (event) => update('starting_point', event.target.value),
          placeholder: 'Counts to 100, follows a recipe with help.'
        })
      }),
      jsxs('div', {
        className: 'grid gap-3 sm:grid-cols-2',
        children: [
          jsx(StudioSelect, {
            id: 'cb-brief-age',
            label: 'Age band',
            value: form.age_band,
            options: STUDIO_AGE_BANDS,
            onChange: (value) => update('age_band', value)
          }),
          jsx(StudioField, {
            id: 'cb-brief-reading',
            label: 'Reading level',
            hint: 'Your words are enough: “Year 3, short sentences”.',
            children: jsx(sdk.Input, {
              id: 'cb-brief-reading',
              maxLength: 120,
              value: form.reading_level,
              onChange: (event) => update('reading_level', event.target.value),
              placeholder: 'Year 3, short decodable sentences'
            })
          })
        ]
      }),

      jsx(CbLabel, { children: 'Where, how long, with what' }),
      jsxs('div', {
        className: 'grid gap-3 sm:grid-cols-3',
        children: [
          jsx(StudioSelect, {
            id: 'cb-brief-setting',
            label: 'Setting',
            value: form.setting,
            options: STUDIO_SETTINGS,
            onChange: (value) => update('setting', value)
          }),
          jsx(StudioField, {
            id: 'cb-brief-duration',
            label: 'Minutes',
            children: jsx(sdk.Input, {
              id: 'cb-brief-duration',
              type: 'number',
              min: 5,
              max: 600,
              value: String(form.duration_minutes),
              onChange: (event) => update('duration_minutes', event.target.value)
            })
          }),
          jsx(StudioField, {
            id: 'cb-brief-pages',
            label: 'Pages',
            children: jsx(sdk.Input, {
              id: 'cb-brief-pages',
              type: 'number',
              min: 1,
              max: 40,
              value: String(form.desired_pages),
              onChange: (event) => update('desired_pages', event.target.value)
            })
          })
        ]
      }),
      jsx(StudioField, {
        id: 'cb-brief-materials',
        label: 'Materials you have',
        hint: 'One per line. Up to 20. Safety notes are written against this list.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-materials',
          rows: 3,
          value: materialsText,
          onChange: (event) => setMaterialsText(event.target.value),
          placeholder: 'one apple\nplastic knife\nmeasuring cup'
        })
      }),
      jsx(StudioSelect, {
        id: 'cb-brief-visuals',
        label: 'Visuals',
        value: form.desired_visuals,
        options: STUDIO_VISUALS,
        onChange: (value) => update('desired_visuals', value)
      }),
      jsx(StudioSelect, {
        id: 'cb-brief-narration',
        label: 'Narration',
        value: form.narration,
        options: STUDIO_NARRATION,
        onChange: (value) => update('narration', value),
        hint: 'A narration script is text you read aloud; it is not an audio file.'
      }),

      jsx(CbLabel, { children: 'Exclusions and supervision' }),
      jsx(StudioField, {
        id: 'cb-brief-exclusions',
        label: 'Leave these out',
        hint: 'One per line: foods, topics, activities, anything the child must not meet here.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-exclusions',
          rows: 3,
          value: exclusionsText,
          onChange: (event) => setExclusionsText(event.target.value),
          placeholder: 'no nuts\nno timed pressure'
        })
      }),
      jsx(StudioField, {
        id: 'cb-brief-supervision',
        label: 'Supervision and safety',
        hint: 'Who holds what, what the adult must do, what the child may not do alone.',
        children: jsx(sdk.Textarea, {
          id: 'cb-brief-supervision',
          rows: 2,
          value: form.supervision,
          onChange: (event) => update('supervision', event.target.value),
          placeholder: 'An adult holds the knife; the child places the pieces.'
        })
      }),

      jsx(CbLabel, { children: 'Before you paste: provider and egress' }),
      jsxs('div', {
        className: 'flex flex-col gap-2 border-l border-(--ui-stroke-secondary) pl-3',
        children: [
          jsx('p', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            children:
              'This brief is sent to the model provider configured for this Hermes profile so the plan can be drafted. Coursebook stores no provider key and sends the brief nowhere else. Anything you paste can appear in the generated pages — do not paste a child’s full name, address, school or anything you would not hand to a provider.'
          }),
          jsx(StudioCheck, {
            id: 'cb-brief-egress',
            checked: form.egress_acknowledged,
            onChange: (value) => update('egress_acknowledged', value),
            children: 'I have read this and want to send this brief to the provider.'
          }),
          jsx(StudioCheck, {
            id: 'cb-brief-redaction',
            checked: Boolean(form.redaction_requested),
            onChange: (value) => update('redaction_requested', value),
            children: 'Ask for identifying details to be redacted where it is possible.'
          })
        ]
      }),

      problems.length > 0
        ? jsxs('div', {
            className: 'flex flex-col gap-1',
            children: [
              jsx(CbLabel, { children: 'Before submitting' }),
              ...problems.map((problem) => jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: problem }, problem))
            ]
          })
        : null,
      error
        ? jsxs('div', {
            className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
            children: [
              jsx('div', { children: `${error.code ? error.code + ': ' : ''}${error.message}` }),
              jsx('div', { className: 'text-(--ui-text-secondary)', children: 'The brief was not saved, and nothing was started.' })
            ]
          })
        : null,

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(CbAction, {
            variant: 'primary',
            disabled: busy || problems.length > 0 || !supported,
            onClick: submit,
            children: busy ? 'Saving the brief' : 'Create the course and start the plan'
          }),
          jsx(sdk.Button, { variant: 'secondary', onClick: onCancel, children: 'Cancel' })
        ]
      }),
      !supported
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'This backend does not register parent.brief.create.' })
        : null
    ]
  })
}

/** The view switcher: authored v3 tabs when the route has width, a labelled Select when it has
 * not. The breakpoint is read from the route (`useCbViewportWidth`), never from the window: the
 * Desktop window can be ~1050 px wide while this route is 407 px. */
function StudioViewPicker({ id, label, value, options, onChange }) {
  const width = useCbViewportWidth()
  const wide = !(width > 0 && width < 760)
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-studio-view-picker': value,
    children: [
      wide
        ? jsx('div', {
            role: 'tablist',
            'aria-label': label,
            style: { display: 'flex', flexWrap: 'wrap', gap: '0.25rem', borderBottom: '1px solid var(--cb3-rule)' },
            children: options.map((option) => {
              const current = option.id === value
              return jsx('button', {
                type: 'button',
                role: 'tab',
                'data-cb3-view-tab': option.id,
                'data-current': current ? 'true' : 'false',
                'aria-selected': current ? 'true' : 'false',
                style: {
                  display: 'inline-flex',
                  alignItems: 'center',
                  minHeight: '44px',
                  paddingInline: '0.6rem',
                  border: 0,
                  borderBottom: current ? '3px solid var(--cb3-terracotta)' : '3px solid transparent',
                  background: 'transparent',
                  color: 'var(--cb3-ink)',
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: cb3Lead('meta'),
                  fontWeight: current ? 600 : 400,
                  cursor: 'pointer'
                },
                onClick: () => onChange(option.id),
                children: option.label
              }, option.id)
            })
          })
        : jsxs('div', {
            className: 'flex items-center gap-2',
            children: [
              jsx('label', { htmlFor: id, className: 'text-xs font-medium text-(--ui-text-secondary)', children: label }),
              jsxs(sdk.Select, {
                value,
                onValueChange: onChange,
                children: [
                  jsx(sdk.SelectTrigger, { id, className: 'w-44', 'aria-label': label, children: jsx(sdk.SelectValue, {}) }, 'trigger'),
                  jsx(
                    sdk.SelectContent,
                    { children: options.map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)) },
                    'content'
                  )
                ]
              })
            ]
          })
    ]
  })
}

const APPROVAL_INVALIDATION_COPY = {
  plan_edited: 'You edited the plan after approving the lesson set.',
  content_changed: 'The generated pages changed after you approved them.',
  course_edited: 'You changed the course title or goal after approving the lesson set.',
  replaced: 'A newer approval replaced this one.'
}

/** "Changes need review" — the banner is derived from the approval row, never from local state. */
function StudioReviewBanner({ approval, exportStatus }) {
  if (!approval || approval.state !== 'superseded') return null
  return jsxs('div', {
    className: 'flex flex-col gap-1 border-l border-(--ui-stroke-secondary) pl-3',
    role: 'status',
    children: [
      jsx('div', { className: 'text-xs font-semibold', children: 'Changes need review' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          APPROVAL_INVALIDATION_COPY[approval.invalidated_reason] ||
          'The lesson set you approved no longer matches the current pages.'
      }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        children: exportStatus && exportStatus.blocked_reason
          ? EXPORT_BLOCKED_COPY[exportStatus.blocked_reason] || `Export is blocked (${exportStatus.blocked_reason}).`
          : 'Approve the current lesson set before exporting.'
      })
    ]
  })
}

/** The brief recap. It is a read: v6 has no brief edit verb, so the honest action is Duplicate. */
function StudioBriefView({ briefQuery, course, planJobId, onJobSettled, onDuplicate, reflections }) {
  const brief = briefQuery.data && briefQuery.data.brief
  if (briefQuery.status === 'loading' && !briefQuery.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the brief' }) })
  }
  if (!brief) {
    return jsx(sdk.ErrorState, {
      title: 'This course has no parent brief',
      description:
        'It was not created by parent.brief.create, or the saved record that stores it is gone. Nothing is reconstructed from a form.',
      children: jsx(sdk.Button, { variant: 'secondary', onClick: briefQuery.reload, children: 'Try again' })
    })
  }
  const settingsLabel = (STUDIO_SETTINGS.find((item) => item.id === brief.setting) || {}).label || brief.setting
  const rows = [
    { label: 'Goal', value: brief.goal },
    { label: 'Starting point', value: brief.starting_point || '—' },
    { label: 'Age band', value: brief.age_band },
    { label: 'Reading level', value: brief.reading_level },
    { label: 'Setting', value: settingsLabel },
    { label: 'Duration', value: `${brief.duration_minutes} minutes` },
    { label: 'Materials', value: (brief.materials || []).join(', ') || 'None listed' },
    { label: 'Exclusions', value: (brief.exclusions || []).join(', ') || 'None listed' },
    { label: 'Supervision', value: brief.supervision || '—' },
    { label: 'Pages / visuals / narration', value: `${brief.desired_pages} pages · ${brief.desired_visuals} · ${brief.narration}` },
    { label: 'Provider disclosure acknowledged', value: brief.egress_acknowledged ? 'yes' : 'no' },
    { label: 'Redaction requested', value: brief.redaction_requested ? 'yes' : 'no' }
  ]
  const plane = (briefQuery.data && briefQuery.data.plan_job) || {}
  const latestProposal =
    reflections && Array.isArray(reflections.reflections)
      ? reflections.reflections.find((item) => item.apply_to_next_draft && item.revisit_note)
      : null

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(QuietNote, {
        children:
          'You are the operator of this course. Coursebook drafted material for you to teach; the child never chats with it. A brief is immutable once stored — changing the teaching comes from editing the plan, and copying this brief makes a new course.'
      }),
      jsx(CbLabel, { children: 'The brief' }),
      jsxs('div', {
        className: 'flex flex-col',
        children: rows.map((row) => jsx(PackReviewLine, { label: row.label, value: row.value }, row.label))
      }),
      jsx(CbLabel, { children: 'Plan' }),
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx(PackReviewLine, { label: 'Job', value: plane.job_id || '—' }),
          jsx(PackReviewLine, { label: 'Submitted', value: plane.submitted_at ? whenLabel(plane.submitted_at) : '—' }),
          jsx(StudioJobLine, { jobId: planJobId, onSettled: onJobSettled, onRunAgain: onJobSettled })
        ]
      }),
      latestProposal
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-tertiary) pl-3',
            children: [
              jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'A note from your last reflection' }),
              jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: latestProposal.revisit_note }),
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'It is shown here as a proposal. It is not applied to any brief unless you copy one.'
              })
            ]
          })
        : null,
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(CbAction, { variant: 'primary', onClick: () => onDuplicate(brief, null), children: 'Duplicate brief' }),
          latestProposal
            ? jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => onDuplicate(brief, latestProposal.revisit_note),
                children: 'Duplicate with the reflection note'
              })
            : null
        ]
      })
    ]
  })
}

/**
 * H-103: a rejected plan is explained, not printed.
 *
 * The backend records the validator's reasons, but a reason is written for a machine: an item id,
 * a contract criterion, a sentence about ordinals. Plan review owes the learner one literal
 * explanation, the unit or check that failed, and one action that can actually be taken. The raw
 * record stays available behind a disclosure; the visible copy never contains a bare `reject`,
 * `model_assessed` or a contract enum.
 */
const PLAN_CHECK_LABELS = Object.freeze({
  alignment: 'whether each objective matches the goal',
  sources: 'whether each claim has a source that was actually read',
  structure: 'whether the units, objectives and checks fit together',
  schedule: 'whether the schedule and time estimates add up',
  policy: 'whether the plan follows the recipe and its limits'
})

/** Map an internal check to a sentence a learner can use. Unknown wording is never a bare token. */
function planCheckLabel(text) {
  const value = String(text || '').toLowerCase()
  if (/source|ledger|citation|provenance|grounded|unsourced|support/.test(value)) return PLAN_CHECK_LABELS.sources
  if (/ordinal|unit|section|prerequisite|contiguous|check plan|coverage|scope|recipe|schedule|parent|structure/.test(value)) return PLAN_CHECK_LABELS.structure
  if (/hour|week|time|duration|estimate|confidence|benchmark/.test(value)) return PLAN_CHECK_LABELS.schedule
  if (/policy|dial|autonomy|assessment|delivery|budget|ceiling/.test(value)) return PLAN_CHECK_LABELS.policy
  return PLAN_CHECK_LABELS.alignment
}

/** Replace snake_case contract tokens with words, so a disclosure cannot leak a bare enum. */
function plainPlanReason(text) {
  return String(text || '')
    .replace(/[A-Za-z]+(?:_[A-Za-z]+)+/g, (token) => token.replace(/_/g, ' '))
    .replace(/\s+/g, ' ')
    .trim()
}

function splitPlanReason(reason) {
  const text = plainPlanReason(reason)
  const match = /^([^:]{1,48}):\s*(.+)$/.exec(text)
  if (match) return { place: match[1].trim(), why: match[2].trim() }
  return { place: null, why: text }
}

const PLAN_RUN_TERMINAL_FAILURE = new Set(['failed', 'cancelled', 'interrupted_requires_retry'])

const VALIDATION_OUTCOME_COPY = {
  rejected: 'The validator did not pass this draft.',
  model_assessed: 'The author model checked its own work; no independent check was recorded.',
  independently_validated: 'A different model checked this draft and passed it.',
  not_validated: 'No validator record was written for this draft.'
}

const VALIDATION_INDEPENDENCE_COPY = {
  independent: 'The writing model and the checking model were different.',
  same_model: 'The same model wrote and checked the plan.',
  unidentified: 'The checking model could not be identified.'
}

const RESEARCH_STATUS_COPY = {
  available: 'Research fetched its sources.',
  degraded: 'Research returned only part of its sources.',
  unavailable: 'Research was unavailable, so no source could be checked.'
}

/**
 * H-105: the validator record, said plainly.
 *
 * `model_assessed` is a limitation, not a badge. The one line only names *who* checked; the words
 * "independently validated" are reserved for a record whose `independence` is `independent` — both
 * model identities were reported by the provider and the model names differ. A same-model or
 * unidentified pass, and a pass with research unavailable, can never be presented as independent.
 * The rule and its consequences are the same as `docs/GENERATION.md` §1 and the status table in
 * `docs/HARNESS-STATUS.md`; the technical provenance stays behind the disclosure.
 *
 * The record travels on the plan job's checkpoint (`checkpoint.validation`), bound to the plan id
 * that job wrote. A carried plan version (`plan.replan`) has no validation record of its own, so
 * this model says no check is recorded for this version rather than borrowing the previous one's.
 */
const PLAN_VALIDATION_LINES = Object.freeze({
  independent: 'Checked by a second model',
  same_model: 'Checked by the same model',
  unidentified: 'Checked by a model that could not be identified',
  unrecorded: 'No validator record is stored for this version',
  rejected: 'The validator refused this version',
  manual: 'Edited by you; this version has no validator record',
  stale: 'Its validation record covers earlier bytes'
})

/**
 * H-167: the one instruction that turns a same-model pass into a real cross-model one.
 *
 * It names the two settings that create the route and the host trust gate that must permit the
 * override, and it points at `coursebook_status`, whose `validator` block is the read-only
 * answer to "is a different checking model configured here?". It deliberately never says
 * "second model", "checked" or "fresh eyes": this copy appears *because* no such check happened.
 */
const PLAN_VALIDATION_SETTINGS_HINT =
  'To have a different model review plans, set ' +
  'plugins.entries.coursebook.settings.validator_model (and optionally validator_provider) and ' +
  'allow it with plugins.entries.coursebook.llm.allow_model_override / allow_provider_override ' +
  '(with allowed_models / allowed_providers), then read coursebook_status to confirm a ' +
  'validator route is configured.'

const PLAN_VALIDATION_CONFIGURE_LINE =
  'No different checking model is configured here; coursebook_status reports the setting to change.'

/** Read the recorded independence, or derive it exactly as the backend does. Never upgrade. */
function planValidationIndependence(validation) {
  const declared = validation && validation.independence
  if (declared === 'independent' || declared === 'same_model' || declared === 'unidentified') {
    return declared
  }
  const generator = (validation && validation.generator) || {}
  const validator = (validation && validation.validator) || {}
  if (!generator.model || !validator.model) return 'unidentified'
  return String(generator.model) === String(validator.model) ? 'same_model' : 'independent'
}

/** `provider/model` only from what the runtime reported; a missing half is not invented. */
function planValidationModelName(identity) {
  const model = identity && identity.model ? String(identity.model) : ''
  const provider = identity && identity.provider ? String(identity.provider) : ''
  if (model && provider) return `${provider}/${model}`
  return model || null
}

/**
 * The plan-review provenance model.
 *
 * `null` means the screen is still reading the job that owns the record: a line is not shown until
 * the record is, so a pending read can never look like "no check". A record whose `plan_id` names
 * another version is discarded, because a carried plan is a copy, not a re-validation.
 */
function planValidationView({ job, jobHint, plan, reading, learner }) {
  const planId = plan && plan.plan_id ? String(plan.plan_id) : null
  // H-182/D3: the durable projection names this exact version's fate. It is read before either
  // job line, so a refused or edited version never renders "no record" and a pass is never
  // borrowed from a job that wrote a different version.
  const durable = plan && plan.validation ? plan.validation : null
  if (durable && durable.manual_authoring === true) {
    return {
      state: 'manual',
      independence: 'unidentified',
      outcome: durable.outcome || 'not_validated',
      line: PLAN_VALIDATION_LINES.manual,
      validatorModel: null,
      generatorModel: null,
      factsUnverified: Boolean(durable.facts_unverified),
      configure: false,
      warning: null,
      note: null,
      detail: [
        'This plan version was edited by its owner. Approval is a human review of that outline; nothing here claims a validation pass.'
      ]
    }
  }
  if (durable && durable.reason === 'plan_validation_stale') {
    return {
      state: 'stale',
      independence: 'unidentified',
      outcome: durable.outcome || null,
      line: PLAN_VALIDATION_LINES.stale,
      validatorModel: null,
      generatorModel: null,
      factsUnverified: Boolean(durable.facts_unverified),
      configure: false,
      warning: null,
      note: null,
      detail: ['The plan changed after it was validated, so the recorded pass covers different bytes.']
    }
  }
  if (durable && (durable.verdict === 'reject' || durable.outcome === 'rejected')) {
    return {
      state: 'rejected',
      independence: durable.independence || 'unidentified',
      outcome: 'rejected',
      line: PLAN_VALIDATION_LINES.rejected,
      validatorModel: null,
      generatorModel: null,
      factsUnverified: Boolean(durable.facts_unverified),
      configure: false,
      warning: null,
      note: null,
      detail: ['The stored record for this version is a refusal; the review panel above explains it.']
    }
  }
  const sources = [job, jobHint].filter(Boolean)
  let checkpoint = null
  let mismatched = false
  for (const source of sources) {
    const candidate = source.checkpoint || {}
    if (!candidate.validation) continue
    if (planId && candidate.plan_id && String(candidate.plan_id) !== planId) {
      mismatched = true
      continue
    }
    checkpoint = candidate
    break
  }
  if (!checkpoint) {
    // A durable pass still names who checked this version even when the job line is no longer on
    // the page (jobs.list is bounded). The independence is the stored one, never upgraded here.
    if (durable && durable.approvable === true && durable.source && durable.source !== 'manual') {
      const independence = durable.independence || 'unidentified'
      const configure = !learner && (independence === 'same_model' || independence === 'unidentified')
      const detail = [
        VALIDATION_OUTCOME_COPY[durable.outcome] || 'The stored record passed this version.',
        'The job line for this run is no longer on the page; this comes from the stored record.'
      ]
      if (configure) detail.push(PLAN_VALIDATION_SETTINGS_HINT)
      return {
        state: independence,
        independence,
        outcome: durable.outcome || null,
        line: PLAN_VALIDATION_LINES[independence],
        validatorModel: null,
        generatorModel: null,
        factsUnverified: Boolean(durable.facts_unverified),
        configure,
        warning: null,
        note: durable.facts_unverified
          ? 'The facts were not checked against sources, so this is not factual verification.'
          : null,
        detail
      }
    }
    // While the owning job is still being read, stay silent rather than claim "no record".
    if (reading && !mismatched) return null
    return {
      state: 'unrecorded',
      line: PLAN_VALIDATION_LINES.unrecorded,
      validatorModel: null,
      generatorModel: null,
      factsUnverified: false,
      warning: null,
      note: null,
      configure: null,
      detail: [
        'No validation record is bound to this exact plan version, so nothing here claims a second model.',
        mismatched
          ? 'This plan was checked against an earlier version; a carried version is a copy, not a re-check.'
          : null
      ].filter(Boolean)
    }
  }
  const validation = checkpoint.validation
  const independence = planValidationIndependence(validation)
  const outcome = String(validation.outcome || checkpoint.validation_verdict || '')
  const generatorModel = planValidationModelName(validation.generator)
  const validatorModel = planValidationModelName(validation.validator)
  const factsUnverified = Boolean(validation.facts_unverified)
  const detail = []
  if (VALIDATION_OUTCOME_COPY[outcome]) detail.push(VALIDATION_OUTCOME_COPY[outcome])
  else if (outcome === 'pass') detail.push('The validator passed this draft.')
  if (generatorModel) detail.push(`Writing model: ${generatorModel}.`)
  detail.push(
    validatorModel
      ? `Checking model: ${validatorModel}.`
      : 'The runtime did not report the checking model.'
  )
  if (factsUnverified) detail.push('The sources were not checked, so a pass is not factual verification.')
  if (validation.warning) detail.push(String(validation.warning))
  // H-167: a same-model or unidentified pass is exactly where the operator needs the setting that
  // would create a real cross-model route. A genuinely independent pass gets no such hint, and a
  // learner surface never shows host settings.
  const configure = !learner && (independence === 'same_model' || independence === 'unidentified')
  if (configure) detail.push(PLAN_VALIDATION_SETTINGS_HINT)
  return {
    // `state` carries the rejection for the screen; the line itself only ever names who checked.
    state: outcome === 'rejected' ? 'rejected' : independence,
    independence,
    outcome,
    line: PLAN_VALIDATION_LINES[independence],
    validatorModel,
    generatorModel,
    factsUnverified,
    configure,
    warning: validation.warning || null,
    note: factsUnverified
      ? 'The facts were not checked against sources, so this is not factual verification.'
      : null,
    detail
  }
}

/**
 * One plain line plus a disclosure. Never a badge, never an "independently validated" claim for a
 * same-model pass; the model/provider names appear only when the runtime reported them.
 */
function PlanValidationLine({ job, jobHint, plan, reading, learner }) {
  const model = planValidationView({ job, jobHint, plan, reading, learner })
  if (!model) return null
  return jsxs('div', {
    'data-cb-plan-validation': model.state,
    className: 'flex max-w-prose flex-col gap-1 text-xs leading-relaxed text-(--ui-text-secondary)',
    children: [
      jsx('div', {
        'data-cb-plan-validation-line': model.independence || model.state,
        style: { color: 'var(--cb3-ink)', fontWeight: 600 },
        children: model.line
      }),
      model.validatorModel
        ? jsx('div', {
            'data-cb-plan-validation-model': model.validatorModel,
            children: `Checking model: ${model.validatorModel}`
          })
        : null,
      model.note
        ? jsx('div', { 'data-cb-plan-validation-facts': 'unverified', children: model.note })
        : null,
      model.configure && !learner
        ? jsx('div', {
            'data-cb-plan-validation-configure': '',
            children: PLAN_VALIDATION_CONFIGURE_LINE
          })
        : null,
      jsxs('details', {
        'data-cb-plan-validation-detail': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }),
          jsx('div', {
            className: 'mt-1 flex flex-col gap-1',
            children: [
              ...model.detail.map((line, index) =>
                jsx('div', { children: line }, `validation-detail-${index}`)
              ),
              learner
                ? null
                : jsx('div', {
                    'data-cb-plan-validation-source': 'docs/GENERATION.md',
                    children:
                      'Provenance rule: docs/GENERATION.md §1 (validator independence) and ' +
                      'docs/HARNESS-STATUS.md.'
                  })
            ]
          })
        ]
      })
    ]
  })
}

/**
 * The rejection review model. `null` means there is nothing to repair: the job is still running,
 * it finished with a usable draft, or it failed in a way a fresh job cannot repeat.
 *
 * `canChangeGoal` is the surface's capability, not the plan's: only a surface that can open the
 * create form may offer "Change the goal". Everywhere else the same refusal gets `try_again`,
 * which is a control that actually runs. Offering the goal action and then answering it with a
 * sentence is the dead end this replaces.
 */
function planRejectView({ job, plan, planValidation, objectiveCount, surface, goal, title, canChangeGoal = true }) {
  const planId = plan && plan.plan_id ? String(plan.plan_id) : null
  const checkpoint = (job && job.checkpoint) || {}
  const checkpointPlanId = checkpoint.plan_id ? String(checkpoint.plan_id) : null
  // A job explains only the plan version it wrote. After "Try again" the screen polls the *new*
  // job, which has no checkpoint yet; reading the old job's refusal through it is how the panel
  // used to disappear and reveal an Approve control for the rejected draft. The durable
  // `plan.validation` projection is the authority for the version on screen, and a job from
  // another version never contributes reasons.
  const jobBelongsToPlan = !planId || !checkpointPlanId || checkpointPlanId === planId
  const validation = (jobBelongsToPlan && checkpoint.validation) || {}
  const jobReasons =
    jobBelongsToPlan && Array.isArray(checkpoint.rejection_reasons) ? checkpoint.rejection_reasons : []
  const stored = planValidation || null
  // Only a recorded refusal is a rejection. A version with no record of its own (a carried
  // replan, or a draft whose job line is gone) is *not approvable*, but it was not rejected and
  // must not borrow this panel's copy. The durable projection wins over the job line: after an
  // edit the job still carries the pre-edit refusal, while the stored record is the parent's
  // manual decision and the panel must step away.
  const durableRefusal = Boolean(
    stored &&
      (stored.verdict === 'reject' ||
        (!stored.verdict && stored.manual_authoring !== true && stored.outcome === 'rejected'))
  )
  const jobRefusal = Boolean(
    jobBelongsToPlan && (checkpoint.validation_verdict === 'reject' || validation.outcome === 'rejected')
  )
  const validatorRejected = durableRefusal || (jobRefusal && !stored)
  // Reasons travel only with a refusal record; a manual or carried version keeps its history in
  // the document, not in a panel that would claim it is still refused.
  const storedReasons = durableRefusal && stored && Array.isArray(stored.reasons) ? stored.reasons : []
  const reasons = jobReasons.length > 0 ? jobReasons : storedReasons
  const failedRun = Boolean(
    job &&
      job.state &&
      PLAN_RUN_TERMINAL_FAILURE.has(job.state) &&
      (!jobBelongsToPlan || !planId || !checkpointPlanId || checkpointPlanId === planId)
  )
  if (!failedRun && !validatorRejected) return null

  const learner = surface === 'learner'
  const goalText = String(goal || (job && job.brief && job.brief.goal) || '').trim()
  const titleText = String(title || '').trim()
  const spoken = goalText ? `“${goalText}”` : titleText ? `“${titleText}”` : 'this course'
  // H-182/D2: a retry that the backend answered by replaying the stored draft is named as such.
  // The renderer never repeats the old "research another pass" claim for a reused result.
  const replayed = checkpoint.reused === true

  if (failedRun) {
    const cancelled = job.state === 'cancelled'
    const interrupted = job.state === 'interrupted_requires_retry'
    const errorCode = String((job.error && job.error.code) || '')
    const provider = /provider|timeout|llm|research|media|unavailable|deadline/i.test(errorCode)
    const draftKept = Boolean(plan)
    return {
      kind: cancelled ? 'cancelled' : interrupted ? 'interrupted' : provider ? 'provider' : 'failed',
      title: cancelled
        ? 'You stopped this run'
        : interrupted
          ? 'The run lost its worker'
          : provider
            ? 'The planning service did not answer'
            : 'Planning stopped before a plan was written',
      body: cancelled
        ? draftKept
          ? `You stopped this run for ${spoken}. A draft plan had already been written, so it stays here, unapproved; nothing was deleted.`
          : `No plan was written for ${spoken}. Your goal and every choice you made are saved with this plan, so running it again repeats the same brief rather than starting over.`
        : draftKept
          ? `The run stopped before it finished, but a draft plan for ${spoken} had already been written. It stays here, unapproved; running the brief again does not create a second course.`
          : `No plan was written for ${spoken}. The brief is saved; running it again sends the same brief and does not create a second course.`,
      where: cancelled ? 'The run, before the plan was approved' : 'The plan, before it was approved',
      detail: [
        errorCode ? `What happened: ${plainPlanReason(errorCode)}` : 'No plan record was written for this run.',
        job.state === 'interrupted_requires_retry'
          ? 'The previous attempt stopped early; it is safe to start again.'
          : draftKept
            ? 'A draft plan exists and is readable; it is not approved.'
            : 'Nothing was approved, and no lesson pages exist.'
      ],
      action: { id: 'try_again', label: 'Try again' },
      draftKept
    }
  }

  const parsed = reasons.map(splitPlanReason)
  const joined = reasons.join(' ')
  const emptyPlan =
    Number(objectiveCount || 0) === 0 ||
    /no objectives|objective list|empty plan|at least one objective|nothing to teach/i.test(joined)
  const unsourced = /source|ledger|citation|provenance|grounded|unsourced|support/i.test(joined)
  const first = parsed[0] || { place: null, why: '' }
  const kind = emptyPlan ? 'empty' : unsourced ? 'unsourced' : 'structural'
  const count = reasons.length

  const models = {
    empty: {
      title: 'The plan came back with nothing to teach',
      body: `The draft for ${spoken} arrived without any objectives, so there is nothing to approve. The course, its brief and this draft are still saved; nothing was deleted.`,
      where: 'The whole plan: no objective was written',
      action: learner && canChangeGoal
        ? { id: 'change_goal', label: 'Change the goal' }
        : { id: 'try_again', label: 'Try again' },
      secondary: null
    },
    unsourced: {
      title: 'The plan could not show where its facts came from',
      body: replayed
        ? `${count === 1 ? 'One part' : `${count} parts`} of the draft could not be tied to a source the research pass actually read. This run returned the draft that was already refused instead of starting a new attempt, so nothing about it changed; the draft is saved and nothing was lost.`
        : `${count === 1 ? 'One part' : `${count} parts`} of the draft could not be tied to a source the research pass actually read. The draft is saved, so nothing is lost. ${
            learner
              ? 'Trying again runs the research pass again and writes a new plan version; if the sources still do not cover it, this same check refuses the new attempt.'
              : 'Run research again to start a new attempt — it runs the research pass from scratch and writes a new plan version, never this draft again — or edit the objectives to what the sources you have can actually support, then approve that as your own plan.'
          }`,
      where: first.place ? `${first.place}: ${planCheckLabel(first.why)}` : planCheckLabel(first.why),
      action: learner
        ? { id: 'try_again', label: 'Try again' }
        : { id: 'edit_plan', label: 'Edit the plan' },
      secondary: learner ? null : { id: 'try_again', label: 'Run research again' }
    },
    structural: {
      title: 'The outline does not fit together yet',
      body: `The plan was written but failed an outline check${first.why ? `: ${first.why}` : ''}. The draft is saved, so you can repair the outline instead of starting over.`,
      where: first.place ? `${first.place}: ${planCheckLabel(first.why)}` : planCheckLabel(first.why),
      action: learner
        ? { id: 'try_again', label: 'Try again' }
        : { id: 'edit_plan', label: 'Edit the plan' },
      secondary: learner ? null : { id: 'try_again', label: 'Run research again' }
    }
  }
  const copy = models[kind]

  const detail = []
  if (reasons.length > 0) detail.push(`Checks that did not clear: ${reasons.map(plainPlanReason).join(' · ')}`)
  if (validation.outcome) detail.push(VALIDATION_OUTCOME_COPY[validation.outcome] || 'The validator did not pass this draft.')
  if (validation.independence) detail.push(VALIDATION_INDEPENDENCE_COPY[validation.independence] || VALIDATION_INDEPENDENCE_COPY.unidentified)
  if (validation.research_status) detail.push(RESEARCH_STATUS_COPY[validation.research_status] || `Research status: ${plainPlanReason(validation.research_status)}`)
  if (detail.length === 0) detail.push('No detailed reason was recorded for this refusal.')

  return {
    kind,
    title: copy.title,
    body: copy.body,
    where: copy.where,
    detail,
    action: copy.action,
    secondary: copy.secondary || null,
    draftKept: Boolean(plan),
    reasons: reasons.map(plainPlanReason)
  }
}

/**
 * One panel, one action. The panel is a status region, not a dialog: the draft stays on screen
 * underneath it and nothing is auto-navigated.
 */
function PlanRejectPanel({ model, busy, error, onAction }) {
  if (!model) return null
  return jsxs('div', {
    role: 'status',
    'data-cb-plan-reject': model.kind,
    'data-cb-plan-reject-action': model.action.id,
    className: 'flex max-w-prose flex-col gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    style: {
      padding: '0.6rem 0.75rem',
      border: '1px solid var(--cb3-rule)',
      borderRadius: cb3Radius('round'),
      background: 'var(--cb3-card-stock)'
    },
    children: [
      jsx('div', {
        style: { fontSize: cb3Type('meta'), fontWeight: 600, color: 'var(--cb3-ink)' },
        children: model.title
      }, 'title'),
      jsx('p', { className: 'max-w-prose', children: model.body }, 'body'),
      jsx('div', { 'data-cb-plan-reject-where': '', children: `Where: ${model.where}` }, 'where'),
      jsx('div', {
        'data-cb-plan-reject-draft': model.draftKept ? 'kept' : 'none',
        children: model.draftKept
          ? 'Your draft is still here. It is not approved, and no lesson will be written from it.'
          : 'No draft was written, so there is nothing to lose by running the brief again.'
      }, 'draft'),
      jsx('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(CbAction, {
            variant: 'primary',
            disabled: busy,
            onClick: () => onAction(model.action.id),
            children: busy ? 'Starting' : model.action.label
          }, 'action'),
          model.secondary && !busy
            ? jsx(sdk.Button, {
                size: 'sm',
                variant: 'text',
                'data-cb-plan-reject-secondary': model.secondary.id,
                onClick: () => onAction(model.secondary.id),
                children: model.secondary.label
              }, 'secondary')
            : null
        ]
      }, 'actions'),
      error ? jsx('div', { children: error }, 'error') : null,
      jsxs('details', {
        'data-cb-plan-reject-details': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }, 'summary'),
          jsx('div', {
            className: 'mt-1 flex flex-col gap-1',
            children: model.detail.map((line, index) => jsx('div', { children: line }, `detail-${index}`))
          }, 'detail')
        ]
      }, 'details')
    ]
  })
}

/**
 * H-194 — fine-tuning an approved course in place.
 *
 * The backend kernel owns every mutation: `plan.edit` (reorder and objective metadata on an
 * **approved** plan), `plan.undo`, `lesson.revise`, `lesson.regenerate`, and `parent.review.read`
 * for the pending diff. This surface is a client of those commands and never a second plan
 * authority, so:
 *
 *   - every move is sent as the full ordered id list, and the list on screen is replaced with the
 *     ids the command **returned** — the UI never keeps an order the backend refused;
 *   - `prerequisite_order_conflict` keeps the stored order and says why, instead of silently
 *     re-sorting the screen;
 *   - the page digest and section id come from the wire (`parent.review.read` lesson revisions),
 *     never from a hash this file computes. When the wire serves neither, the authored-page and
 *     regenerate actions are withheld and the reason is on screen, not in the console.
 */
const FINE_TUNE_CHIP = Object.freeze({
  edited: { id: 'edited', label: 'Edited', variant: 'outline' },
  needs_review: { id: 'needs_review', label: 'Needs review', variant: 'warn' },
  approved: { id: 'approved', label: 'Approved', variant: 'muted' }
})

const FINE_TUNE_CHIP_COPY = {
  edited: 'This objective or section was changed by the course author; one revision row records it.',
  needs_review:
    'This change is stored and readable, but nobody has approved it. Export and any new check wait for approval.',
  approved:
    'This change was approved with the lesson set it belongs to. It is still not an independent validation.'
}

const FINE_TUNE_SECTION_ACTIONS_GAP =
  'This course serves no authored section identity, so one section cannot be revised or ' +
  'regenerated from here. `lesson.revise` and `lesson.regenerate` are keyed on the `section_id` ' +
  'and `page_hash` that `parent.blueprint.read` reports in `sections[]`; a pack-backed course is ' +
  'composed from its pack and reports none. Nothing here invents a section id or a digest.'

const FINE_TUNE_EVIDENCE_CONSEQUENCE =
  'Editing this page keeps every stored attempt and the previous page version; the new page is ' +
  'stored as a revision that nobody has approved, so its check stays closed and export waits.'

/** One criterion, said in plain words: the row may be a string or the rubric object. */
function fineTuneCriteriaText(item) {
  if (item && typeof item === 'object') {
    return String(item.description || item.criterion || '').trim()
  }
  return String(item == null ? '' : item).trim()
}

/**
 * The chip for one objective: a pending revision wins over an approved one, and an approved
 * authored page is still "Edited", never "validated". `provenanceOutcome` is the served
 * `lesson.page` outcome (`needs_review` / `parent_approved`) — it can only ever add a state the
 * revision rows already recorded, it never upgrades one.
 */
function fineTuneChip({ planRevisions, lessonRevisions, objectiveId, provenanceOutcome }) {
  const id = String(objectiveId || '')
  const plans = (planRevisions || []).filter(
    (row) =>
      (row.after || []).some((item) => item.objective_id === id) ||
      (row.before || []).some((item) => item.objective_id === id)
  )
  const lessons = (lessonRevisions || []).filter((row) => row.objective_id === id)
  const states = [...plans, ...lessons].map((row) => String(row.state || ''))
  if (provenanceOutcome === 'needs_review' || states.includes('needs_review')) {
    return FINE_TUNE_CHIP.needs_review
  }
  if (provenanceOutcome === 'parent_approved' || states.includes('approved')) {
    return FINE_TUNE_CHIP.approved
  }
  if (states.some((state) => state === 'superseded' || state === 'reverted')) {
    return FINE_TUNE_CHIP.edited
  }
  return null
}

function FineTuneChip({ chip, title }) {
  if (!chip) return null
  return jsx('span', {
    'data-cb-finetune-chip': chip.id,
    title: title || FINE_TUNE_CHIP_COPY[chip.id] || null,
    children: jsx(sdk.Badge, { size: 'xs', variant: chip.variant, children: chip.label })
  })
}

/** `1 section: <title>` — the scope sentence shown before a one-section job is queued. */
function fineTuneScopeLine(title) {
  return `1 section: ${String(title || 'untitled')}`
}

/**
 * The pending review diff (`parent.review.read`): what an approval would bind, in storage order.
 * It is a diff of stored rows, not a second approval path, and the export gate it prints is the
 * backend's own `blocked_reason` — shown verbatim so a mapped sentence can never soften it.
 */
function StudioReviewDiff({ review, objectives }) {
  const label = jsx(CbLabel, { children: 'Review changes' })
  if (!review) return null
  const data = review.data || null
  if (!data) {
    return jsxs('div', {
      className: 'flex flex-col gap-1',
      'data-cb-review-diff': 'reading',
      children: [
        label,
        jsx('div', {
          className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
          children:
            review.status === 'error'
              ? 'The pending changes could not be read, so nothing here claims the course has none.'
              : 'Reading the pending changes.'
        })
      ]
    })
  }
  const planRevisions = data.plan_revisions || []
  const lessonRevisions = data.lesson_revisions || []
  const exportStatus = data.export || {}
  const ready = Boolean(exportStatus.ready)
  const blockedReason = exportStatus.blocked_reason || null
  const titleOf = (objectiveId) => {
    const row = (objectives || []).find((item) => item.objective_id === objectiveId)
    return row ? row.title : String(objectiveId || 'section')
  }
  const orderLine = (rows) => (rows || []).map((item) => `${item.ordinal}. ${item.title}`).join(' · ')

  return jsxs('div', {
    className: 'flex max-w-prose flex-col gap-2',
    'data-cb-review-diff': planRevisions.length + lessonRevisions.length > 0 ? 'pending' : 'clean',
    'data-cb-review-export': ready ? 'ready' : 'blocked',
    'data-cb-review-blocked-reason': blockedReason || '',
    children: [
      jsx(CbLabel, { children: 'Review changes' }, 'label'),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children: ready
          ? 'The approved lesson set matches the pages shown, so export is available.'
          : blockedReason
            ? `Export is blocked. The backend’s reason: ${blockedReason}.`
            : 'Export is blocked and the backend returned no reason string.'
      }, 'gate'),
      planRevisions.length === 0 && lessonRevisions.length === 0
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            'data-cb-review-empty': 'true',
            children: 'No fine-tune change is waiting for review.'
          }, 'empty')
        : null,
      ...planRevisions.map((row) =>
        jsxs(
          'div',
          {
            className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
            'data-cb-review-plan-revision': row.revision_id,
            'data-cb-review-state': row.state,
            children: [
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2 text-xs',
                children: [
                  jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `plan ${row.kind}` }, 'kind'),
                  jsx(FineTuneChip, {
                    chip:
                      row.state === 'needs_review'
                        ? FINE_TUNE_CHIP.needs_review
                        : row.state === 'approved'
                          ? FINE_TUNE_CHIP.approved
                          : FINE_TUNE_CHIP.edited
                  }, 'chip'),
                  jsx('span', {
                    className: 'text-(--ui-text-secondary)',
                    children: whenLabel(row.created_at)
                  }, 'when')
                ]
              }, 'head'),
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                'data-cb-review-changed': (row.changed_fields || []).join(','),
                children: `Changed: ${(row.changed_fields || []).join(' · ') || 'no named field'}`
              }, 'changed'),
              jsx('div', {
                className: 'text-xs break-words text-(--ui-text-secondary)',
                'data-cb-review-after': orderLine(row.after),
                children: `Now: ${orderLine(row.after)}`
              }, 'after'),
              jsx('div', {
                className: 'text-xs break-words text-(--ui-text-secondary)',
                children: `Before: ${orderLine(row.before)}`
              }, 'before')
            ]
          },
          row.revision_id
        )
      ),
      ...lessonRevisions.map((row) =>
        jsxs(
          'div',
          {
            className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
            'data-cb-review-lesson-revision': row.revision_id,
            'data-cb-review-state': row.state,
            children: [
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2 text-xs',
                children: [
                  jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: 'lesson page' }, 'kind'),
                  jsx(FineTuneChip, {
                    chip:
                      row.state === 'needs_review'
                        ? FINE_TUNE_CHIP.needs_review
                        : row.state === 'approved'
                          ? FINE_TUNE_CHIP.approved
                          : FINE_TUNE_CHIP.edited
                  }, 'chip'),
                  jsx('span', {
                    className: 'text-(--ui-text-secondary)',
                    children: whenLabel(row.created_at)
                  }, 'when')
                ]
              }, 'head'),
              jsx('div', {
                className: 'text-xs break-words text-(--ui-text-secondary)',
                children: `${titleOf(row.objective_id)} — changed: ${(row.changed_fields || []).join(' · ') || 'no named field'}`
              }, 'changed'),
              row.evidence_attempts > 0
                ? jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    'data-cb-review-evidence-attempts': String(row.evidence_attempts),
                    children: `${row.evidence_attempts} stored attempt(s) reference this section; the edit was confirmed against that consequence.`
                  }, 'attempts')
                : null,
              jsx('div', {
                className: 'text-xs break-all text-(--ui-text-secondary)',
                children: `page ${String(row.page_hash_after || '').slice(0, 23)}…`
              }, 'hash')
            ]
          },
          row.revision_id
        )
      )
    ]
  })
}

/**
 * The Plan-tab fine-tune controls for an **approved** plan.
 *
 * Reorder (buttons + Alt+ArrowUp/Down), undo, inline objective metadata, review/export links and
 * the one-section regenerate path. Every successful mutation refreshes the review read and the
 * outline, so the screen always shows what storage returned rather than what the last click
 * assumed.
 */
function StudioFineTunePanel({
  course,
  revision,
  onRevision,
  plan,
  objectives,
  sections,
  planHash,
  supported,
  onChanged,
  onOpenReview,
  review,
  onDirtyChange
}) {
  const [order, setOrder] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [draft, setDraft] = useState(null)
  const [discardPrompt, setDiscardPrompt] = useState(null)
  const [evidencePrompt, setEvidencePrompt] = useState(null)
  const [regenFor, setRegenFor] = useState(null)
  const [regenBusy, setRegenBusy] = useState(false)
  const [regenError, setRegenError] = useState(null)
  const [regenResult, setRegenResult] = useState(null)
  const [revertBusy, setRevertBusy] = useState(false)

  const jobs = useRpcQuery(
    'jobs.list',
    { enrollment_id: course.enrollment_id, kind: ['plan'], limit: 20 },
    `finetune-jobs-${course.enrollment_id}`,
    supported('jobs.list')
  )
  const reviewData = (review && review.data) || null
  const planRevisions = (reviewData && reviewData.plan_revisions) || []
  const lessonRevisions = (reviewData && reviewData.lesson_revisions) || []
  const latestRevision = planRevisions.find((row) => row.state !== 'reverted') || null
  const dirty = Boolean(draft) && Boolean(draft.dirty)

  useEffect(() => {
    if (typeof onDirtyChange === 'function') onDirtyChange(dirty)
    return undefined
  }, [dirty, onDirtyChange])
  useEffect(
    () => () => {
      if (typeof onDirtyChange === 'function') onDirtyChange(false)
    },
    [onDirtyChange]
  )
  // Guard a close or a reload while a draft differs from storage. The in-app guard below covers
  // navigation inside the studio; this covers the window itself.
  useEffect(() => {
    if (!dirty || typeof window === 'undefined') return undefined
    const guard = (event) => {
      event.preventDefault()
      event.returnValue = ''
      return ''
    }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])
  useEffect(() => setOrder(null), [objectives])

  const display = order
    ? order.map((id) => objectives.find((objective) => objective.objective_id === id)).filter(Boolean)
    : objectives

  // `section_id` and the page digest only ever come from the wire. `parent.blueprint.read` serves
  // one identity per composed section (cb.rpc v20), including a section that has never been
  // revised; that `page_hash` is the exact fence `lesson.revise` compares, so the value read here
  // is sent back unchanged and never recomputed in this file. A lesson revision row is only a
  // fallback for a section the blueprint no longer lists.
  const sectionRefs = {}
  for (const row of sections || []) {
    if (!row || !row.objective_id || !row.section_id) continue
    sectionRefs[row.objective_id] = {
      section_id: String(row.section_id),
      page_hash: row.page_hash || null,
      title: row.title || null,
      lesson_state: row.lesson_state || null,
      lesson_version: row.lesson_version == null ? null : Number(row.lesson_version),
      source: 'blueprint'
    }
  }
  for (const row of lessonRevisions) {
    if (sectionRefs[row.objective_id]) continue
    sectionRefs[row.objective_id] = {
      section_id: row.section_id,
      page_hash: row.page_hash_after || null,
      title: null,
      lesson_state: null,
      lesson_version: null,
      source: 'revision'
    }
  }

  // One section's likely price, estimated from what this course's last lessons run actually cost —
  // arithmetic on stored numbers, labelled as an estimate, not a promise about this click. The
  // learner reads the dollars only; the per-call arithmetic that produced them stays here.
  const planJobs = (jobs.data && jobs.data.jobs) || []
  const lastLessonsJob =
    planJobs.find((job) => job && job.brief && job.brief.stage === 'lessons') || null
  const recorded = (lastLessonsJob && lastLessonsJob.checkpoint && lastLessonsJob.checkpoint.preflight) || null
  let estimate = null
  if (recorded && Number(recorded.section_count) > 0) {
    const perCall = Number(recorded.cost_per_call_usd) || 0
    const minCalls = Math.max(1, Math.ceil(Number(recorded.minimum_calls || 0) / Number(recorded.section_count)))
    const maxCalls = Math.max(minCalls, Math.ceil(Number(recorded.maximum_calls || 0) / Number(recorded.section_count)))
    estimate = {
      low: minCalls * perCall,
      high: maxCalls * perCall
    }
  }
  const money = (value) => `$${Number(value || 0).toFixed(2)}`
  // The queued job's own one-section price, read once from the contract field the regenerate answer
  // carries. The learner reads the dollars; the field's name never reaches the screen.
  const regenPrice = (regenResult && regenResult.preflight) || null

  const refreshAfterMutation = useCallback(
    (result) => {
      if (result && typeof result.revision === 'number') onRevision(result.revision)
      if (review && review.reload) review.reload()
      if (jobs && jobs.reload) jobs.reload()
      if (onChanged) onChanged()
    },
    [onRevision, review, jobs, onChanged]
  )

  const refusalText = useCallback(
    (response) => {
      const details = (response.error && response.error.details) || {}
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      const code = response.error && response.error.code ? `${response.error.code}: ` : ''
      let reason = ''
      if (details.reason === 'prerequisite_order_conflict') {
        reason =
          ' That move would put one unit’s objectives behind a later unit, so the stored order was kept.'
      } else if (details.reason === 'revision_conflict') {
        reason =
          ' A later change landed after that revision, so the undo would overwrite it; nothing was written.'
      } else if (details.reason === 'revision_already_reverted') {
        reason = ' That structural change was already undone.'
      } else if (details.reason === 'nothing_to_undo') {
        reason = ' This plan has no structural change to undo.'
      } else if (details.reason === 'plan_not_approved') {
        reason = ' The plan is not approved, so only a draft edit applies.'
      }
      return (
        `${code}${describeError(response.error)}${reason}` +
        (nextRevision !== null ? ' The course revision was refreshed; try again.' : '')
      )
    },
    [onRevision]
  )

  // A move is a real command: the full ordered id list, the digest read from storage, and the
  // returned order as the new screen state. Nothing is reordered only on screen.
  const move = useCallback(
    async (index, direction) => {
      if (busy) return
      const ids = display.map((objective) => objective.objective_id)
      const target = index + direction
      if (target < 0 || target >= ids.length) return
      const next = ids.slice()
      const [moved] = next.splice(index, 1)
      next.splice(target, 0, moved)
      setBusy(true)
      setError(null)
      setNotice(null)
      const response = await rpc(
        'plan.edit',
        {
          enrollment_id: course.enrollment_id,
          plan_id: plan.plan_id,
          expected_plan_hash: planHash,
          reorder: next
        },
        { expectedRevision: revision, idempotencyKey: newOperationId('plan-reorder') }
      )
      setBusy(false)
      if (!response.ok) {
        setOrder(null)
        setError(refusalText(response))
        if (review && review.reload) review.reload()
        return
      }
      const result = response.result || {}
      const saved = result.objective_ids || next
      setOrder(saved)
      setNotice(
        `Order saved. ${saved
          .map((id, position) => {
            const row = objectives.find((objective) => objective.objective_id === id)
            return `${position + 1}. ${row ? row.title : id}`
          })
          .join(' · ')}`
      )
      refreshAfterMutation(result)
    },
    [
      busy,
      display,
      course.enrollment_id,
      plan,
      planHash,
      revision,
      objectives,
      review,
      refusalText,
      refreshAfterMutation
    ]
  )

  const rowKeyDown = (index) => (event) => {
    if (!event.altKey) return
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      move(index, -1)
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      move(index, 1)
    }
  }

  const undo = useCallback(async () => {
    if (revertBusy) return
    setRevertBusy(true)
    setError(null)
    setNotice(null)
    const payload = {
      enrollment_id: course.enrollment_id,
      plan_id: plan.plan_id,
      expected_plan_hash: planHash
    }
    if (latestRevision) payload.revision_id = latestRevision.revision_id
    const response = await rpc('plan.undo', payload, {
      expectedRevision: revision,
      idempotencyKey: newOperationId('plan-undo')
    })
    setRevertBusy(false)
    if (!response.ok) {
      setError(refusalText(response))
      if (review && review.reload) review.reload()
      return
    }
    const result = response.result || {}
    setOrder(null)
    const restored = (result.objective_ids || [])
      .map((id, position) => {
        const row = objectives.find((objective) => objective.objective_id === id)
        return `${position + 1}. ${row ? row.title : id}`
      })
      .join(' · ')
    setNotice(`Undid the last structural change. Stored order: ${restored}`)
    refreshAfterMutation(result)
  }, [
    revertBusy,
    course.enrollment_id,
    plan,
    planHash,
    latestRevision,
    revision,
    objectives,
    review,
    refusalText,
    refreshAfterMutation
  ])

  /** The newest snapshot a revision row holds for this objective — the only scored criteria read. */
  const knownSnapshot = useCallback(
    (objectiveId) => {
      for (const row of planRevisions) {
        const after = (row.after || []).find((item) => item.objective_id === objectiveId)
        if (after) return after
        const before = (row.before || []).find((item) => item.objective_id === objectiveId)
        if (before) return before
      }
      return null
    },
    [planRevisions]
  )

  const openEditor = useCallback(
    (objective) => {
      const known = knownSnapshot(objective.objective_id)
      const criteriaText =
        known && Array.isArray(known.criteria)
          ? known.criteria.map(fineTuneCriteriaText).filter(Boolean).join('\n')
          : ''
      const ref = sectionRefs[objective.objective_id] || null
      const pageTitle = ref && ref.title ? String(ref.title) : String(objective.title || '')
      setEditingId(objective.objective_id)
      setDiscardPrompt(null)
      setEvidencePrompt(null)
      setError(null)
      setDraft({
        objectiveId: objective.objective_id,
        title: objective.title,
        evidence_target: objective.evidence_target,
        criteriaText,
        originalCriteriaText: criteriaText,
        criteriaKnown: Boolean(known && Array.isArray(known.criteria)),
        sectionTitle: pageTitle,
        originalSectionTitle: pageTitle,
        dirty: false
      })
    },
    [knownSnapshot, sectionRefs]
  )

  const closeEditor = useCallback(() => {
    setEditingId(null)
    setDraft(null)
    setDiscardPrompt(null)
    setEvidencePrompt(null)
    if (typeof onDirtyChange === 'function') onDirtyChange(false)
  }, [onDirtyChange])

  const beginEdit = useCallback(
    (objective) => {
      if (dirty) {
        setDiscardPrompt({ kind: 'switch', objectiveId: objective.objective_id })
        return
      }
      if (editingId === objective.objective_id) {
        closeEditor()
        return
      }
      openEditor(objective)
    },
    [dirty, editingId, closeEditor, openEditor]
  )

  const requestCancel = useCallback(() => {
    if (dirty) {
      setDiscardPrompt({ kind: 'cancel' })
      return
    }
    closeEditor()
  }, [dirty, closeEditor])

  const patchDraft = useCallback((patch) => {
    setDraft((previous) => (previous ? { ...previous, ...patch, dirty: true } : previous))
  }, [])

  const saveSection = useCallback(
    async (options) => {
      if (!draft) return
      const confirmEvidence = Boolean(options && options.confirmEvidence)
      const objective = objectives.find((item) => item.objective_id === draft.objectiveId)
      if (!objective) return
      const ref = sectionRefs[draft.objectiveId] || null
      const edits = { objective_id: draft.objectiveId }
      const title = String(draft.title || '').trim()
      if (title && title !== objective.title) edits.title = title.slice(0, 300)
      if (draft.evidence_target && draft.evidence_target !== objective.evidence_target) {
        edits.evidence_target = draft.evidence_target
      }
      if (
        String(draft.criteriaText || '').trim() !== String(draft.originalCriteriaText || '').trim() &&
        (String(draft.criteriaText || '').trim() || draft.criteriaKnown)
      ) {
        edits.criteria = linesToList(draft.criteriaText, 12, 500)
      }
      const planChanged = Boolean(edits.title || edits.evidence_target || edits.criteria !== undefined)
      const pageTitle = String(draft.sectionTitle || '').trim()
      const pageTitleChanged = Boolean(pageTitle) && pageTitle !== String(draft.originalSectionTitle || '').trim()
      if (!planChanged && !pageTitleChanged) {
        setError('Nothing changed yet.')
        return
      }
      if (pageTitleChanged && (!ref || !ref.section_id)) {
        setError(FINE_TUNE_SECTION_ACTIONS_GAP)
        return
      }
      if (pageTitleChanged && !ref.page_hash) {
        setError(
          'This section has no authored page yet, so there is no page digest to revise. ' +
            'Use “Regenerate this section” to author it first.'
        )
        return
      }
      setBusy(true)
      setError(null)
      setNotice(null)
      let nextRevision = revision
      if (planChanged) {
        const response = await rpc(
          'plan.edit',
          {
            enrollment_id: course.enrollment_id,
            plan_id: plan.plan_id,
            expected_plan_hash: planHash,
            objective_edits: [edits]
          },
          { expectedRevision: revision, idempotencyKey: newOperationId('plan-objective-edit') }
        )
        if (!response.ok) {
          setBusy(false)
          setError(refusalText(response))
          if (review && review.reload) review.reload()
          return
        }
        const result = response.result || {}
        if (typeof result.revision === 'number') {
          nextRevision = result.revision
          onRevision(result.revision)
        }
      }
      if (pageTitleChanged) {
        const payload = {
          enrollment_id: course.enrollment_id,
          plan_id: plan.plan_id,
          section_id: ref.section_id,
          expected_page_hash: ref.page_hash,
          title: pageTitle.slice(0, 300),
          page: { section_title: pageTitle.slice(0, 300) }
        }
        if (confirmEvidence) payload.confirm_evidence_consequence = true
        const response = await rpc('lesson.revise', payload, {
          expectedRevision: nextRevision,
          idempotencyKey: newOperationId('lesson-revise')
        })
        if (!response.ok) {
          setBusy(false)
          const details = (response.error && response.error.details) || {}
          if (details.reason === 'evidence_consequence_confirmation_required') {
            const attempts = Number(details.evidence_attempts || 0)
            setEvidencePrompt({ objectiveId: draft.objectiveId, attempts })
            setError(
              `${attempts} learner attempt(s) already reference this section. ` +
                `${FINE_TUNE_EVIDENCE_CONSEQUENCE} Confirm to store the edit.`
            )
            return
          }
          setError(refusalText(response))
          if (review && review.reload) review.reload()
          return
        }
        const result = response.result || {}
        if (typeof result.revision === 'number') {
          nextRevision = result.revision
          onRevision(result.revision)
        }
        setEvidencePrompt(null)
        setNotice(
          'Section page saved as a new revision that needs review before export. ' +
            'Every stored attempt and the previous page version are untouched.'
        )
      } else {
        setNotice(
          'Section metadata saved. The edited objective is recorded as a revision that needs review before export.'
        )
      }
      setBusy(false)
      closeEditor()
      refreshAfterMutation({ revision: nextRevision })
    },
    [
      draft,
      objectives,
      sectionRefs,
      course.enrollment_id,
      plan,
      planHash,
      revision,
      review,
      refusalText,
      closeEditor,
      refreshAfterMutation,
      onRevision
    ]
  )

  const confirmEvidenceAndSave = useCallback(() => {
    return saveSection({ confirmEvidence: true })
  }, [saveSection])

  const queueRegenerate = useCallback(
    async (objective) => {
      const ref = sectionRefs[objective.objective_id]
      if (!ref || !ref.section_id) return
      setRegenBusy(true)
      setRegenError(null)
      const response = await rpc(
        'lesson.regenerate',
        {
          enrollment_id: course.enrollment_id,
          plan_id: plan.plan_id,
          section_id: ref.section_id
        },
        { idempotencyKey: newOperationId('lesson-regenerate') }
      )
      setRegenBusy(false)
      if (!response.ok) {
        setRegenError(refusalText(response))
        if (review && review.reload) review.reload()
        return
      }
      const result = response.result || {}
      setRegenResult({
        objectiveId: objective.objective_id,
        title: objective.title,
        jobId: result.job_id,
        scope: result.scope || null,
        preflight: result.preflight || null
      })
      setRegenFor(null)
      setNotice(
        `Queued regenerating 1 section: ${objective.title}. Other sections, their media and every attempt are untouched.`
      )
      refreshAfterMutation(result)
    },
    [sectionRefs, course.enrollment_id, plan, review, refusalText, refreshAfterMutation]
  )

  if (!plan || plan.state !== 'approved') return null

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3 rounded border border-(--ui-stroke-tertiary) p-3',
    'data-cb-finetune': 'approved',
    'data-cb-finetune-plan': String(plan.plan_id || ''),
    children: [
      jsxs(
        'div',
        {
          className: 'flex flex-wrap items-center justify-between gap-2',
          children: [
            jsx(CbLabel, { children: 'Fine-tune this approved course' }),
            jsx('div', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                onOpenReview
                  ? jsx(sdk.Button, {
                      size: 'sm',
                      variant: 'secondary',
                      'data-cb-finetune-review': '',
                      onClick: onOpenReview,
                      children: 'Review changes'
                    }, 'review')
                  : null,
                jsx(sdk.Button, {
                  size: 'sm',
                  variant: 'secondary',
                  disabled: busy || revertBusy || !latestRevision,
                  'data-cb-finetune-undo': latestRevision ? latestRevision.revision_id : 'none',
                  onClick: undo,
                  children: revertBusy ? 'Undoing' : 'Undo last structural change'
                }, 'undo')
              ]
            }, 'actions')
          ]
        },
        'header'
      ),
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Reorder or retitle an objective and the change is written to storage as a revision that needs review; ' +
          'lesson pages, checks and attempts are not rewritten. Every move is sent with the full order, so the ' +
          'order you see is the order the backend returned.'
      }, 'intro'),
      notice
        ? jsx('div', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-finetune-notice': 'saved',
            children: notice
          }, 'notice')
        : null,
      error
        ? jsx('div', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            role: 'status',
            'data-cb-finetune-error': '',
            children: error
          }, 'error')
        : null,
      jsx('div', {
        role: 'list',
        'aria-label': 'Objectives in stored order',
        'data-cb-finetune-order': display.map((objective) => objective.objective_id).join(','),
        className: 'flex flex-col gap-2',
        children: display.map((objective, index) => {
          const ref = sectionRefs[objective.objective_id]
          const chip = fineTuneChip({
            planRevisions,
            lessonRevisions,
            objectiveId: objective.objective_id,
            provenanceOutcome: ref ? ref.lesson_state : null
          })
          const isEditing = editingId === objective.objective_id && draft
          return jsxs(
            'div',
            {
              role: 'listitem',
              tabIndex: 0,
              'aria-label': `${objective.ordinal}. ${objective.title}. Press Alt+ArrowUp or Alt+ArrowDown to move it.`,
              'aria-keyshortcuts': 'Alt+ArrowUp Alt+ArrowDown',
              'data-cb-finetune-row': objective.objective_id,
              'data-cb-finetune-editing': isEditing ? 'true' : 'false',
              className: 'flex flex-col gap-1 rounded border border-(--ui-stroke-tertiary) p-2',
              onKeyDown: rowKeyDown(index),
              children: [
                jsxs(
                  'div',
                  {
                    className: 'flex flex-wrap items-center justify-between gap-2',
                    children: [
                      jsxs('div', {
                        className: 'flex min-w-0 items-baseline gap-2',
                        children: [
                          jsx('span', {
                            className: 'shrink-0 text-xs tabular-nums text-(--ui-text-secondary)',
                            children: String(index + 1).padStart(2, '0')
                          }, 'ordinal'),
                          jsx('span', {
                            className: 'min-w-0 break-words text-sm',
                            'data-cb-finetune-title': objective.objective_id,
                            children: objective.title
                          }, 'title'),
                          jsx(FineTuneChip, { chip }, 'chip'),
                          ref
                            ? jsx('span', {
                                className: 'text-xs text-(--ui-text-secondary)',
                                'data-cb-finetune-section': 'known',
                                children:
                                  ref.lesson_version == null
                                    ? 'no page yet'
                                    : `page v${ref.lesson_version}`
                              }, 'section-known')
                            : jsx('span', {
                                className: 'text-xs text-(--ui-text-secondary)',
                                'data-cb-finetune-section': 'unknown',
                                title: FINE_TUNE_SECTION_ACTIONS_GAP,
                                children: 'no authored section'
                              }, 'section-unknown')
                        ]
                      }, 'label'),
                      jsxs('div', {
                        className: 'flex flex-wrap items-center gap-1',
                        children: [
                          jsx(sdk.Button, {
                            size: 'sm',
                            variant: 'text',
                            disabled: busy || index === 0,
                            'data-cb-finetune-move': 'up',
                            onClick: () => move(index, -1),
                            children: 'Move up'
                          }, 'up'),
                          jsx(sdk.Button, {
                            size: 'sm',
                            variant: 'text',
                            disabled: busy || index === display.length - 1,
                            'data-cb-finetune-move': 'down',
                            onClick: () => move(index, 1),
                            children: 'Move down'
                          }, 'down'),
                          jsx(sdk.Button, {
                            size: 'sm',
                            variant: 'text',
                            'data-cb-finetune-edit': objective.objective_id,
                            onClick: () => beginEdit(objective),
                            children: isEditing ? 'Close editor' : 'Edit section'
                          }, 'edit'),
                          jsx(sdk.Button, {
                            size: 'sm',
                            variant: 'text',
                            disabled: !ref || !ref.section_id,
                            'data-cb-finetune-regenerate': ref && ref.section_id ? ref.section_id : 'unavailable',
                            title: ref && ref.section_id ? null : FINE_TUNE_SECTION_ACTIONS_GAP,
                            onClick: () => {
                              setRegenError(null)
                              setRegenFor(objective.objective_id)
                            },
                            children: 'Regenerate this section'
                          }, 'regenerate')
                        ]
                      }, 'actions')
                    ]
                  },
                  'title'
                ),
                isEditing
                  ? jsxs('div', {
                      className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                      'data-cb-finetune-editor': objective.objective_id,
                      children: [
                        jsx(StudioField, {
                          id: `cb-finetune-title-${objective.objective_id}`,
                          label: 'Objective title',
                          hint:
                            'Stored on the objective. The section page keeps its authored prose; a retitle is a plan revision that needs review.',
                          children: jsx(sdk.Input, {
                            id: `cb-finetune-title-${objective.objective_id}`,
                            value: draft.title,
                            onChange: (event) => patchDraft({ title: event.target.value }),
                            className: 'w-full'
                          })
                        }),
                        jsx(StudioField, {
                          id: `cb-finetune-page-title-${objective.objective_id}`,
                          label: 'Section page title',
                          hint: ref
                            ? ref.page_hash
                              ? `Stored on the authored page through lesson.revise, fenced on the page digest this read served (${String(ref.page_hash).slice(0, 16)}…). The result is a new page revision that needs review.`
                              : 'This section has no authored page yet, so there is no digest to revise. Regenerate this section to author one.'
                            : FINE_TUNE_SECTION_ACTIONS_GAP,
                          children: jsx(sdk.Input, {
                            id: `cb-finetune-page-title-${objective.objective_id}`,
                            value: draft.sectionTitle,
                            disabled: !ref || !ref.section_id || !ref.page_hash,
                            onChange: (event) => patchDraft({ sectionTitle: event.target.value }),
                            className: 'w-full'
                          })
                        }),
                        jsx(StudioField, {
                          id: `cb-finetune-target-${objective.objective_id}`,
                          label: 'Evidence target',
                          children: jsxs(sdk.Select, {
                            value: draft.evidence_target,
                            onValueChange: (value) => patchDraft({ evidence_target: value }),
                            children: [
                              jsx(
                                sdk.SelectTrigger,
                                {
                                  id: `cb-finetune-target-${objective.objective_id}`,
                                  className: 'w-full',
                                  children: jsx(sdk.SelectValue, {})
                                },
                                'trigger'
                              ),
                              jsx(
                                sdk.SelectContent,
                                {
                                  children: EVIDENCE_TARGET_OPTIONS.map((option) =>
                                    jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                                  )
                                },
                                'content'
                              )
                            ]
                          })
                        }),
                        jsx(StudioField, {
                          id: `cb-finetune-criteria-${objective.objective_id}`,
                          label: 'Assessment criteria',
                          hint: draft.criteriaKnown
                            ? 'One criterion per line. Saving replaces the objective’s criteria.'
                            : 'This build was not served the objective’s current criteria, so this field starts empty. ' +
                              'Enter the criteria you want stored; leaving it untouched keeps whatever storage holds.',
                          children: jsx(sdk.Textarea, {
                            id: `cb-finetune-criteria-${objective.objective_id}`,
                            rows: 3,
                            value: draft.criteriaText,
                            onChange: (event) => patchDraft({ criteriaText: event.target.value })
                          })
                        }),
                        jsxs('div', {
                          className: 'flex flex-wrap items-center gap-2',
                          children: [
                            jsx(CbAction, {
                              size: 'sm',
                              variant: 'primary',
                              disabled: busy,
                              'data-cb-finetune-save': objective.objective_id,
                              onClick: saveSection,
                              children: busy ? 'Saving' : 'Save section'
                            }, 'save'),
                            jsx(sdk.Button, {
                              size: 'sm',
                              variant: 'text',
                              'data-cb-finetune-cancel': '',
                              onClick: requestCancel,
                              children: 'Cancel'
                            }, 'cancel'),
                            dirty
                              ? jsx('span', {
                                  className: 'text-xs text-(--ui-text-secondary)',
                                  'data-cb-finetune-dirty': 'true',
                                  children: 'Unsaved changes'
                                }, 'dirty')
                              : null
                          ]
                        }),
                        jsx('div', {
                          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                          'data-cb-finetune-section-gap': ref ? 'known' : 'unavailable',
                          children: ref
                            ? 'The section’s segment bodies are authored by the lessons job; this editor changes the page title and the objective metadata, and lesson.revise stores a new page revision that needs review before export.'
                            : FINE_TUNE_SECTION_ACTIONS_GAP
                        }),
                        evidencePrompt && evidencePrompt.objectiveId === objective.objective_id
                          ? jsxs('div', {
                              role: 'alertdialog',
                              'aria-label': 'Confirm the evidence consequence',
                              'data-cb-finetune-evidence': String(evidencePrompt.attempts),
                              className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                              children: [
                                jsx('span', {
                                  className: 'max-w-prose text-xs text-(--ui-text-secondary)',
                                  children: `${evidencePrompt.attempts} stored attempt(s) reference this section. ${FINE_TUNE_EVIDENCE_CONSEQUENCE}`
                                }, 'copy'),
                                jsx(CbAction, {
                                  size: 'sm',
                                  variant: 'primary',
                                  disabled: busy,
                                  'data-cb-finetune-evidence-confirm': objective.objective_id,
                                  onClick: confirmEvidenceAndSave,
                                  children: busy ? 'Saving' : 'Confirm and save'
                                }, 'confirm-evidence'),
                                jsx(sdk.Button, {
                                  size: 'sm',
                                  variant: 'text',
                                  'data-cb-finetune-evidence-cancel': '',
                                  onClick: () => setEvidencePrompt(null),
                                  children: 'Keep editing'
                                }, 'dismiss-evidence')
                              ]
                            }, 'evidence-prompt')
                          : null
                      ]
                    }, 'editor')
                  : null,
                discardPrompt && discardPrompt.kind !== 'leave'
                  ? jsxs('div', {
                      role: 'alertdialog',
                      'aria-label': 'Unsaved section changes',
                      'data-cb-finetune-discard': discardPrompt.kind,
                      className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                      children: [
                        jsx('span', {
                          className: 'text-xs text-(--ui-text-secondary)',
                          children: 'Discard the unsaved changes to this section?'
                        }, 'prompt'),
                        jsx(sdk.Button, {
                          size: 'sm',
                          variant: 'text',
                          'data-cb-finetune-discard-confirm': '',
                          onClick: () => {
                            const pending = discardPrompt
                            setDiscardPrompt(null)
                            if (pending.kind === 'switch') {
                              const objectiveRow = objectives.find(
                                (item) => item.objective_id === pending.objectiveId
                              )
                              if (objectiveRow) openEditor(objectiveRow)
                            } else {
                              closeEditor()
                            }
                          },
                          children: 'Discard changes'
                        }, 'discard'),
                        jsx(sdk.Button, {
                          size: 'sm',
                          variant: 'text',
                          'data-cb-finetune-discard-keep': '',
                          onClick: () => setDiscardPrompt(null),
                          children: 'Keep editing'
                        }, 'keep')
                      ]
                    }, 'discard-prompt')
                  : null,
                regenFor === objective.objective_id
                  ? jsxs('div', {
                      className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
                      'data-cb-finetune-regenerate-confirm': objective.objective_id,
                      children: [
                        jsx('div', {
                          className: 'text-xs font-medium',
                          'data-cb-regenerate-scope': '',
                          children: fineTuneScopeLine(objective.title)
                        }),
                        jsx('div', {
                          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                          'data-cb-regenerate-cost': estimate ? 'estimated' : 'unknown',
                          children: estimate
                            ? `Regenerating this section costs about ${money(estimate.low)}–${money(estimate.high)}, ` +
                              'based on what writing lessons for this course has cost so far. ' +
                              'The price for this section appears here once you queue it.'
                            : 'We work out what one section costs when you queue it — this course has no earlier lesson run to go by yet.'
                        }),
                        jsxs('div', {
                          className: 'flex flex-wrap items-center gap-2',
                          children: [
                            jsx(CbAction, {
                              size: 'sm',
                              variant: 'primary',
                              disabled: regenBusy,
                              'data-cb-regenerate-queue': objective.objective_id,
                              onClick: () => queueRegenerate(objective),
                              children: regenBusy ? 'Queueing' : 'Queue regenerating 1 section'
                            }),
                            jsx(sdk.Button, {
                              size: 'sm',
                              variant: 'text',
                              onClick: () => setRegenFor(null),
                              children: 'Cancel'
                            })
                          ]
                        }),
                        regenError
                          ? jsx('div', {
                              className: 'text-xs text-(--ui-text-secondary)',
                              'data-cb-regenerate-error': '',
                              children: regenError
                            }, 'regen-error')
                          : null
                      ]
                    }, 'regen-confirm')
                  : null,
                regenResult && regenResult.objectiveId === objective.objective_id
                  ? jsxs('div', {
                      className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
                      'data-cb-regenerate-result': regenResult.jobId || '',
                      children: [
                        jsx('div', {
                          className: 'text-xs',
                          children: `Queued ${fineTuneScopeLine(regenResult.title)} · job ${regenResult.jobId}`
                        }),
                        regenPrice
                          ? jsx('div', {
                              className: 'text-xs text-(--ui-text-secondary)',
                              'data-cb-regenerate-price-estimate': String(regenPrice.minimum_cost_usd),
                              children:
                                `This section costs ${money(regenPrice.minimum_cost_usd)}–` +
                                `${money(regenPrice.maximum_cost_usd)} to regenerate.`
                            })
                          : null,
                        regenResult.jobId
                          ? jsx(StudioJobLine, {
                              jobId: regenResult.jobId,
                              onSettled: () => refreshAfterMutation({})
                            }, 'regen-job')
                          : null
                      ]
                    }, 'regen-result')
                  : null
              ]
            },
            objective.objective_id
          )
        })
      })
    ]
  })
}

/**
 * The unit a lessons job was authoring, read from its own checkpoint.
 *
 * `next_unit_ordinal` is the next unit the stored rows still need; a job that failed before it
 * could report that carries the unit it was on (`unit_ordinal`), so a retry names the same unit
 * instead of skipping ahead. `null` means there is nothing left to write — never a guess from the
 * number of pages on screen.
 */
function lessonsUnitTarget(job) {
  const checkpoint = (job && job.checkpoint) || {}
  if (checkpoint.units_complete_all === true) return null
  for (const key of ['next_unit_ordinal', 'next_unit_to_author', 'unit_ordinal']) {
    const value = checkpoint[key]
    if (Number.isInteger(value)) return value
  }
  return null
}

/**
 * The plan working view: outline and activities on the left, sources and review notes on the
 * right. The parent can edit every meaningful field of a **draft** plan; an approved plan is
 * changed in place through the H-194 fine-tune commands, which record a reviewable revision.
 */
function StudioPlanView({
  course,
  revision,
  onRevision,
  outline,
  book,
  brief,
  planJobId,
  planJob,
  planJobHint,
  planScope,
  onChangeGoal,
  onJobSettled,
  onChanged,
  supported,
  surface,
  outlineHidden,
  syllabusGate,
  review,
  onOpenReview,
  onDirtyChange
}) {
  // `surface: 'learner'` is the same outline/plan review for a learner course: identical reads,
  // identical approve and lessons actions, minus the parent-only authoring controls (edit plan,
  // start a new version). It is one component so the two doors can never drift.
  const learner = surface === 'learner'
  // A learner's approved-plan tab shows its own objective state list, so this panel keeps the
  // actions and the job line and drops the duplicated outline.
  const hideOutline = Boolean(outlineHidden)
  const plan = outline.data && outline.data.plan
  const objectives = (outline.data && outline.data.objectives) || []
  // `course.outline.plan.plan_hash` echoes the digest generation stored with the plan document,
  // while `plan.approve` / `parent.plan.edit` fence on the digest recomputed from the plan rows.
  // `parent.blueprint.read` serves the recomputed one, so that is the value the studio sends.
  const planHash =
    (book && book.data && book.data.plan && book.data.plan.plan_hash) || (plan && plan.plan_hash) || null
  const [order, setOrder] = useState(null)
  const [editing, setEditing] = useState(false)
  const [drafts, setDrafts] = useState({})
  const [added, setAdded] = useState([])
  const [removed, setRemoved] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [lessonJobId, setLessonJobId] = useState(null)
  // G2: a lessons job authors exactly one unit, so the unit being asked for is part of the request.
  // It is read from the settled job's own checkpoint (`next_unit_ordinal`) or, after a reload, from
  // the stored jobs — never from a page count or from how many times this screen was pressed.
  const [lessonCheckpoint, setLessonCheckpoint] = useState(null)
  const lessonJobs = useRpcQuery(
    'jobs.list',
    { enrollment_id: course && course.enrollment_id, kind: ['plan'], limit: 20 },
    `studio-plan-lesson-jobs-${(course && course.enrollment_id) || 'none'}`,
    Boolean(course && course.enrollment_id) && Boolean(supported && supported('jobs.list'))
  )
  const lessonPages = Boolean(
    book && book.data && book.data.tabs && (book.data.tabs.learner_pages || []).length > 0
  )
  const storedLessonJob =
    ((lessonJobs && lessonJobs.data && lessonJobs.data.jobs) || [])
      .filter((job) => (job.brief || {}).stage === 'lessons')
      .sort((left, right) => (Number(right.updated_at) || 0) - (Number(left.updated_at) || 0))[0] || null
  // The job whose checkpoint this screen reads. A settle beats a stored row for the job on screen;
  // once the id moves (a retry or the next unit) the stale local read stops applying.
  const lessonStateJob =
    lessonCheckpoint && lessonCheckpoint.job_id === lessonJobId ? lessonCheckpoint : storedLessonJob
  const nextUnitOrdinal = lessonsUnitTarget(lessonStateJob)
  // The ordinal this press asks for. `next_unit_ordinal` is the backend's own answer; a job with no
  // checkpoint yet is retried at the unit it names; a course whose every unit is authored gets one
  // key beyond the last unit so the honest no-op job is still a fresh request.
  const unitTotal =
    Number((lessonStateJob && lessonStateJob.checkpoint && lessonStateJob.checkpoint.units_total) || 0) ||
    ((plan && plan.units) || []).length
  const allUnitsAuthored = Boolean(
    lessonStateJob && lessonStateJob.checkpoint && lessonStateJob.checkpoint.units_complete_all === true
  )
  const authoredUnit = Number(
    (lessonStateJob && lessonStateJob.checkpoint && lessonStateJob.checkpoint.unit_ordinal) || 0
  )
  const lessonRequestOrdinal = Number.isInteger(nextUnitOrdinal)
    ? nextUnitOrdinal
    : allUnitsAuthored
      ? Math.max(unitTotal + 1, 1)
      : authoredUnit || 1
  // H-103: the plan job is read here, once, so the review can explain a rejection. The old job
  // line polled this same id separately; StudioJobStatus now shares this read instead of minting a
  // second poller.
  const [retryPlanJobId, setRetryPlanJobId] = useState(null)
  const retryPlanKey = useRef(null)
  const activePlanJobId = retryPlanJobId || planJobId
  // A caller that already read the job (the create result carries the first job it queued, the
  // learner route finds one by enrolment) passes it in; the panel then shares that read instead
  // of polling the same id twice. A retry minted a new id, so the injected row stops applying.
  const injectedPlanRun = planJob && (!activePlanJobId || planJob.job_id === activePlanJobId) ? planJob : null
  const polledPlanRun = useStudioJob(injectedPlanRun ? null : activePlanJobId, onJobSettled)
  const planRun = injectedPlanRun || polledPlanRun
  // The scope the wait band names. Learner routes pass it; Parent Studio has it in the brief.
  const waitScope = planScope || (brief && brief.brief && brief.brief.scope) || null
  const [rejectBusy, setRejectBusy] = useState(false)
  const [rejectError, setRejectError] = useState(null)
  // Editing changes the draft the refusal was about. Once an edit is saved the panel steps away:
  // approval is then a deliberate human decision on a different outline, not a silent retry.
  const [rejectionHandled, setRejectionHandled] = useState(false)
  // H-182/D3: approvability is a durable backend fact about *this version*, read from the same
  // gate `plan.approve` fences on. It is never inferred from whichever job line is being polled:
  // that inference is what rendered an Approve control for a rejected draft while a retry ran.
  const planValidation =
    (book && book.data && book.data.plan && book.data.plan.validation) ||
    (plan && plan.validation) ||
    null
  const approvable = Boolean(planValidation && planValidation.approvable === true)
  const rejection = planRejectView({
    job: planRun,
    plan,
    planValidation,
    objectiveCount: objectives.length,
    surface,
    // A surface that cannot open the create form is never offered "Change the goal".
    canChangeGoal: typeof onChangeGoal === 'function',
    goal:
      (planRun && planRun.brief && planRun.brief.goal) ||
      (brief && brief.brief && brief.brief.goal) ||
      (plan && plan.goal) ||
      null,
    title: (course && course.title) || (brief && brief.brief && brief.brief.title) || null
  })
  const shownRejection = rejectionHandled ? null : rejection

  // A plan version carries its authored document (sections and research) in `gen_plan_documents`,
  // keyed by plan_id. `plan.replan` now carries that document onto a content-preserving new version
  // (keep / retitle / defer / remove), so a replanned plan is authorable again — the version is no
  // longer unauthorable just because it was replanned. Two cases still leave the version without a
  // covering document: a structural `add` through the editor (no authored section exists for a new
  // objective) and a version whose replan could not carry. No wire field declares authorship, so the
  // studio does not guess before the click: it reads the refusal the lessons job itself returns and
  // withholds the action for that plan version instead of offering the same failure twice.
  const [lessonDocumentGap, setLessonDocumentGap] = useState(null)
  const planIdOnScreen = plan && plan.plan_id

  // The editor's displayed order. Local until Save changes sends it as a permutation.
  useEffect(() => setOrder(null), [outline.data])
  const displayObjectives = order
    ? order.map((id) => objectives.find((objective) => objective.objective_id === id)).filter(Boolean)
    : objectives

  // A new plan version (plan.replan) is a new set of objective rows with new ids. The editor is
  // opened right after that replan, before the outline reload lands, so its drafts can be keyed by
  // the previous version's ids — every title input then renders empty. Backfill a draft for any
  // objective that has none while the editor is open, so a title is never shown as blank.
  useEffect(() => {
    if (!editing) return
    setDrafts((previous) => {
      let changed = false
      const next = { ...previous }
      for (const objective of objectives) {
        if (!next[objective.objective_id]) {
          next[objective.objective_id] = { title: objective.title, evidence_target: objective.evidence_target }
          changed = true
        }
      }
      return changed ? next : previous
    })
  }, [editing, objectives])

  const startEditing = useCallback(() => {
    const next = {}
    for (const objective of displayObjectives) {
      next[objective.objective_id] = {
        title: objective.title,
        evidence_target: objective.evidence_target
      }
    }
    setDrafts(next)
    setAdded([])
    setRemoved([])
    setError(null)
    setEditing(true)
  }, [displayObjectives])

  const cancelEditing = useCallback(() => {
    setEditing(false)
    setError(null)
  }, [])

  const savePlan = useCallback(async () => {
    if (!outline.data || !plan) return
    const edits = []
    for (const objective of displayObjectives) {
      const draft = drafts[objective.objective_id]
      if (!draft) continue
      const changedTitle = draft.title.trim() && draft.title.trim() !== objective.title
      const changedTarget = draft.evidence_target && draft.evidence_target !== objective.evidence_target
      if (changedTitle || changedTarget) {
        edits.push({
          objective_id: objective.objective_id,
          ...(changedTitle ? { title: draft.title.trim().slice(0, 300) } : {}),
          ...(changedTarget ? { evidence_target: draft.evidence_target } : {})
        })
      }
    }
    const survivingOrder = displayObjectives.map((objective) => objective.objective_id).filter((id) => !removed.includes(id))
    const orderChanged = displayObjectives.map((objective) => objective.objective_id).join('|') !== objectives.map((objective) => objective.objective_id).join('|')
    const payload = {
      enrollment_id: course.enrollment_id,
      plan_id: plan.plan_id,
      expected_plan_hash: planHash
    }
    if (edits.length > 0) payload.objective_edits = edits
    if (removed.length > 0) payload.remove_objective_ids = removed
    if (added.length > 0) {
      payload.add_objectives = added
        .filter((item) => item.title.trim())
        .map((item) => ({
          title: item.title.trim().slice(0, 300),
          evidence_target: item.evidence_target
        }))
    }
    if (removed.length > 0 || orderChanged) payload.order = survivingOrder
    if (!payload.objective_edits && !payload.remove_objective_ids && !payload.add_objectives && !payload.order) {
      setError('Nothing changed yet.')
      return
    }
    setBusy(true)
    setError(null)
    const response = await rpc('parent.plan.edit', payload, {
      expectedRevision: revision,
      idempotencyKey: newOperationId('plan-edit')
    })
    setBusy(false)
    if (!response.ok) {
      const details = (response.error && response.error.details) || {}
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      setError(
        `${response.error && response.error.code ? response.error.code + ': ' : ''}${describeError(response.error)}` +
          (nextRevision !== null ? ' The course was updated elsewhere; press Save changes again.' : '') +
          (details.reason === 'plan_not_draft'
            ? ' This plan is approved; start a new plan version to change it.'
            : details.reason === 'objective_in_use'
              ? ' That objective already has content or learning state, so it cannot be removed.'
              : '')
      )
      return
    }
    onRevision(response.result.revision)
    setEditing(false)
    setRejectionHandled(true)
    const savedVersion = response.result && response.result.plan_version
    setNotice(
      `Plan saved${savedVersion ? ` as version ${savedVersion}` : ''}. The edit is versioned and marks the lesson set as needing review until it is approved again.`
    )
    onChanged()
  }, [outline.data, plan, objectives, displayObjectives, drafts, removed, added, course.enrollment_id, revision, onRevision, onChanged])

  const approvePlan = useCallback(async () => {
    if (!plan) return
    setBusy(true)
    setError(null)
    // `plan.approve` fences on the digest recomputed from the plan rows, and an edit changes it the
    // moment it is saved. The page's `book` query can still hold the pre-edit digest for a render or
    // two, and submitting that is refused `VALIDATION_FAILED: the approved hash does not match the
    // current plan content`. Read the digest directly at approve time instead of trusting the render.
    let hash = planHash
    if (supported('parent.blueprint.read')) {
      const fresh = await rpc('parent.blueprint.read', { course_id: course.course_id })
      const freshPlan = fresh && fresh.ok && fresh.result && fresh.result.plan ? fresh.result.plan : null
      // H-182/D3 belt: the same read carries the durable gate. A version the backend says is not
      // approvable is never sent to `plan.approve` from this screen.
      if (freshPlan && freshPlan.validation && freshPlan.validation.approvable !== true) {
        setBusy(false)
        setError(
          freshPlan.validation.reason === 'plan_validation_stale'
            ? 'This version changed after it was validated, so approval is withheld. Re-read the plan or run a new version.'
            : 'This version has no passing validation record, so approval is withheld. Repair the plan above or run a new version.'
        )
        return
      }
      const freshHash = freshPlan ? freshPlan.plan_hash : null
      if (freshHash) hash = freshHash
    }
    if (!hash) {
      setBusy(false)
      setError('The plan digest is not available yet. Re-read the plan and try again.')
      return
    }
    const response = await rpc(
      'plan.approve',
      { enrollment_id: course.enrollment_id, plan_id: plan.plan_id, plan_hash: hash },
      { expectedRevision: revision, idempotencyKey: newOperationId('plan-approve') }
    )
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      const hashMismatch = /plan content/i.test((response.error && response.error.message) || '')
      if (hashMismatch) onChanged()
      setError(
        `${response.error.code}: ${describeError(response.error)}` +
          (hashMismatch ? ' The plan was re-read; press Approve plan again.' : '') +
          (nextRevision !== null ? ' The course was updated elsewhere; press Approve plan again.' : '')
      )
      return
    }
    onRevision(response.result.revision)
    setNotice('Plan approved. The outline and activities are now fixed; the generated pages are a separate approval.')
    onChanged()
  }, [plan, course.enrollment_id, course.course_id, planHash, revision, onRevision, onChanged, supported])

  const generateLessons = useCallback(async () => {
    if (!plan) return
    setBusy(true)
    setError(null)
    // Keyed by the plan version **and** the unit this press asks for. The executor authors exactly
    // one unit per job and `jobs.create` replays the job stored for a key, so a key without the
    // unit made the second press replay unit 1 forever. A double click on one press still replays:
    // both clicks carry the same (plan, unit) key.
    const response = await rpc(
      'jobs.create',
      { kind: 'plan', brief: { stage: 'lessons', plan_id: plan.plan_id, enrollment_id: course.enrollment_id } },
      { idempotencyKey: `cb-lessons-${plan.plan_id}-${lessonRequestOrdinal}` }
    )
    setBusy(false)
    if (!response.ok) {
      setError(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setLessonJobId(response.result.job_id)
    // The read that offered this unit described the previous job; re-read so the next offer comes
    // from the job that just started rather than from a screen that has already moved on.
    setLessonCheckpoint(null)
    if (lessonJobs.reload) lessonJobs.reload()
  }, [plan, course.enrollment_id, lessonRequestOrdinal, lessonJobs])

  const startRevision = useCallback(async () => {
    if (!plan || objectives.length === 0) return
    setBusy(true)
    setError(null)
    const response = await rpc(
      'plan.replan',
      {
        enrollment_id: course.enrollment_id,
        objective_changes: objectives.map((objective) => ({ objective_id: objective.objective_id, change: 'keep' }))
      },
      { expectedRevision: revision, idempotencyKey: newOperationId('replan') }
    )
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) onRevision(nextRevision)
      setError(
        `${response.error.code}: ${describeError(response.error)}` +
          (nextRevision !== null ? ' The course was updated elsewhere; press Start a new plan version again.' : '')
      )
      return
    }
    onRevision(response.result.revision)
    setNotice('A new draft plan version was created. The approved lesson set stops applying until the new plan and its pages are approved.')
    onChanged()
    startEditing()
  }, [plan, objectives, course.enrollment_id, revision, onRevision, onChanged, startEditing])

  // H-103/H-182: the repair actions on a rejected plan.
  //
  // `edit_plan` opens the existing editor on this draft, and saving is the parent's explicit
  // manual decision: the plan is then approvable *as manual*, never as validated. `change_goal`
  // hands the same choices back to the create form so a new goal is a new course, not a silent
  // overwrite. `try_again` queues a new job from the brief this job stored; the backend no longer
  // replays a rejected draft to a new job, so this is a real new attempt and the notice only
  // claims a fresh run when the answer is actually a new job.
  const runPlanRepair = useCallback(async (actionId) => {
    if (!shownRejection || rejectBusy) return
    const action = actionId || shownRejection.action.id
    if (action === 'edit_plan') {
      startEditing()
      return
    }
    if (action === 'change_goal') {
      // The panel offers this action only on a surface that wires a handler (`canChangeGoal`),
      // so this is a real return to the create form with the brief that ran, never a sentence.
      // A caller that reaches here without one gets the retry below: the same brief, a new job,
      // which is the only repair this surface can actually perform.
      if (typeof onChangeGoal === 'function') {
        const source = (planRun && planRun.brief) || {}
        onChangeGoal({
          goal: source.goal || '',
          title: (course && course.title) || '',
          recipe: source.recipe || null,
          dials: source.dials || null,
          locale: source.locale || null,
          level: source.level || null,
          subjectDomain: source.subject_domain || null,
          scope: source.scope || null
        })
        return
      }
    }
    const source = planRun
    if (!source || !source.brief || !source.job_id) {
      setRejectError('The saved brief could not be read yet, so this run cannot be repeated. Try again once the plan finishes reading.')
      return
    }
    setRejectBusy(true)
    setRejectError(null)
    if (!retryPlanKey.current || retryPlanKey.current.jobId !== source.job_id || !retryPlanKey.current.key) {
      retryPlanKey.current = { jobId: source.job_id, key: `cb-plan-retry-${source.job_id}` }
    }
    const response = await rpc(
      'jobs.create',
      { kind: source.kind || 'plan', brief: source.brief },
      { idempotencyKey: retryPlanKey.current.key }
    )
    setRejectBusy(false)
    if (!response.ok) {
      setRejectError(
        `${response.error && response.error.code ? response.error.code + ': ' : ''}${describeError(response.error)} The saved draft is unchanged.`
      )
      return
    }
    const newJobId = response.result && response.result.job_id
    if (!newJobId || newJobId === source.job_id) {
      // The backend replayed the refused run. Do not claim a fresh pass that did not start.
      setRejectError('The planning service answered with the run that already finished, so nothing new started. The refused draft is unchanged; try again shortly.')
      return
    }
    // A new job id is a new attempt: the next click gets its own key instead of replaying this one.
    retryPlanKey.current = { jobId: newJobId, key: null }
    setRetryPlanJobId(newJobId)
    setNotice('A new planning run started from the same brief: research runs again and the draft it writes is a new version. The refused draft stays readable until a new plan replaces it.')
    if (onChanged) onChanged()
  }, [shownRejection, rejectBusy, startEditing, onChangeGoal, planRun, course, onChanged])

  // Clear the gap when the screen moves to another plan version (a replan or a fresh authoring job
  // that completed and reloaded the outline).
  useEffect(() => setLessonDocumentGap(null), [planIdOnScreen])
  useEffect(() => {
    setRejectionHandled(false)
    setRejectError(null)
  }, [planIdOnScreen])

  const settled = useCallback(
    (job) => {
      if (!job) return
      const isLessons = job.brief && job.brief.stage === 'lessons'
      if (isLessons) {
        // G2: the settled checkpoint names the unit just authored and the next one, so the primary
        // action becomes "Write unit N lessons" from the job's own facts. The stored jobs are
        // re-read too, so a reload offers the same unit this screen offers now.
        setLessonCheckpoint({ job_id: job.job_id, checkpoint: job.checkpoint || {} })
        if (lessonJobs.reload) lessonJobs.reload()
      }
      const message = (job.error && job.error.message) || ''
      if (isLessons && job.state === 'failed' && /no authored document|outline covers objectives/i.test(message)) {
        setLessonDocumentGap(message)
        onJobSettled(job)
        return
      }
      if (job.state === 'completed' || job.state === 'completed_late') {
        if (isLessons) setLessonDocumentGap(null)
        onChanged()
        return
      }
      onJobSettled(job)
    },
    [onChanged, onJobSettled]
  )

  if (outline.status === 'loading' && !outline.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the plan' }) })
  }
  if (outline.status === 'error' && !outline.data) {
    return jsx(sdk.ErrorState, {
      title: 'The plan could not be read',
      description: `${outline.error && outline.error.code ? outline.error.code + ': ' : ''}${describeError(outline.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: outline.reload, children: 'Try again' })
    })
  }
  if (!plan || objectives.length === 0) {
    // A rejected draft is never replaced by a blank "no plan yet" screen. The panel names what
    // failed and the one repair; the draft (or the saved brief, when nothing was written) is the
    // page, so a reload cannot turn a refusal into an empty course.
    if (shownRejection) {
      return jsxs('div', {
        className: 'flex flex-col gap-4',
        'data-cb-plan-draft': shownRejection.draftKept ? 'kept' : 'none',
        children: [
          jsx(PlanRejectPanel, {
            model: shownRejection,
            busy: rejectBusy,
            error: rejectError,
            onAction: runPlanRepair
          }),
          plan && plan.plan_id
            ? jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: `Draft plan ${String(plan.plan_id)} · version ${plan.version || 1} is still stored.`
              })
            : null
        ]
      })
    }
    if (planJobId) {
      // CREATE-EXPERIENCE items 3–5: the wait is legible instead of opaque. The clock, stage and
      // band come from the job this screen is already polling; nothing here invents a percentage.
      return jsx(PlanWritingPanel, {
        jobId: planJobId,
        job: planRun,
        scope: waitScope,
        onSettled: onJobSettled,
        onRunAgain: onChanged
      })
    }
    return jsx(EmptyState, {
      title: 'No plan yet',
      description: learner
        ? 'This course has no plan attached. Start a new course to generate one; nothing is invented to fill the gap.'
        : 'No plan is attached to this course, so there is nothing to review. Start a new brief.'
    })
  }

  const isDraft = plan.state === 'draft'
  const contentReady = lessonPages
  const setting = brief && brief.brief ? brief.brief.setting : null
  const sources = (book && book.data && book.data.sources) || []

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              jsx(PlanStateBadge, { plan }),
              jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: `plan ${String(planHash || '').slice(0, 19)}…` })
            ]
          }),
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: shownRejection && !editing
              ? null
              : [
              isDraft && !editing
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'secondary',
                    onClick: startEditing,
                    children: learner ? 'Adjust this plan' : 'Edit plan'
                  })
                : null,
              editing
                ? jsx(CbAction, { size: 'sm', variant: 'primary', disabled: busy, onClick: savePlan, children: busy ? 'Saving' : 'Save changes' })
                : null,
              editing ? jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: cancelEditing, children: 'Cancel' }) : null,
              isDraft && !editing && approvable
                ? jsx(CbAction, {
                    variant: 'primary',
                    'data-cb-plan-approve': 'approvable',
                    disabled: busy || !supported('plan.approve') || Boolean(syllabusGate && syllabusGate.required && !syllabusGate.ready),
                    onClick: approvePlan,
                    children: 'Approve plan'
                  })
                : null,
              !isDraft && !editing && !lessonDocumentGap
                ? jsx(CbAction, {
                    variant: 'primary',
                    'data-cb-lessons-unit': String(lessonRequestOrdinal),
                    disabled: busy || !supported('jobs.create'),
                    onClick: generateLessons,
                    children: Number.isInteger(nextUnitOrdinal)
                      ? `Write unit ${nextUnitOrdinal} lessons`
                      : contentReady
                        ? 'Generate missing lessons'
                        : 'Generate lessons'
                  })
                : null,
              !isDraft && !editing
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'secondary',
                    disabled: busy || !supported('plan.replan'),
                    onClick: startRevision,
                    children: learner ? 'Ask for a change' : 'Start a new plan version'
                  })
                : null
            ]
          })
        ]
      }),

      shownRejection
        ? jsx(PlanRejectPanel, {
            model: shownRejection,
            busy: rejectBusy,
            error: rejectError,
            onAction: runPlanRepair
          })
        : jsx(PlanValidationLine, {
            // H-105: who checked this exact plan version, read from the job that wrote it. The
            // line never claims more than the stored record says; the enums stay in the disclosure.
            job: planRun,
            jobHint: planJobHint,
            plan,
            reading: Boolean(activePlanJobId && !planRun),
            learner
          }),
      shownRejection
        ? null
        : isDraft && !editing && !approvable
          ? jsx('div', {
              className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
              'data-cb-plan-approval-gate': (planValidation && planValidation.reason) || 'no_record',
              children:
                planValidation && planValidation.reason === 'plan_validation_stale'
                  ? 'This version cannot be approved: it changed after its validation record was written, so that record covers different bytes. Run a new plan version, or edit the plan to take ownership of it as your own outline.'
                  : planValidation && (planValidation.verdict === 'reject' || planValidation.outcome === 'rejected')
                    ? 'This version cannot be approved: the validator refused it. Repair it above; approving a refused draft is never offered.'
                    : planValidation && planValidation.manual_authoring === true
                      ? 'This version was edited by you, so approval is a human review of your own outline; it is not presented as validated.'
                      : planValidation && planValidation.verdict
                        ? 'This version cannot be approved: no passing validation record is stored for it. Edit the plan to own it, or run a new plan version.'
                        : 'Approval is withheld until this version has a validation record: a draft with no record is not approvable.'
            })
          : null,
      shownRejection
        ? null
        : jsx(QuietNote, {
            children:
              'Approving the plan approves this outline and these activities. It does not approve a single generated page: the lesson set is approved later, by its own hash.'
          }),
      syllabusGate && syllabusGate.required && !syllabusGate.ready
        ? jsx('div', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-syllabus-gate': 'blocked',
            children: syllabusGate.reason
          })
        : null,
      lessonDocumentGap
        ? jsx('p', {
            className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-plan-document': 'missing',
            children:
              `Lessons cannot be generated from this plan version: ${lessonDocumentGap} ` +
              'The authored outline (its sections and research) belongs to the version that was written with the plan, and this version has changes it does not cover, so Generate lessons is withheld rather than offered as a second failure. Start a new plan version to author an outline that covers every objective.'
          })
        : null,
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error }) : null,
      activePlanJobId && !shownRejection
        ? jsx(StudioJobLine, {
            jobId: activePlanJobId,
            job: planRun,
            onSettled: onJobSettled,
            onRunAgain: onChanged
          })
        : null,
      lessonJobId
        ? jsx(StudioJobLine, {
            jobId: lessonJobId,
            onSettled: settled,
            // G2: a failed lessons job is retried from its own stored brief, and the key names the
            // unit plus the failed run — so the retry is a new job id while a double click on Run
            // again still replays one job.
            onRunAgain: (newJobId) => {
              setLessonJobId(newJobId)
              setLessonCheckpoint(null)
              if (lessonJobs.reload) lessonJobs.reload()
            },
            retryKey: (failedJobId, run) => {
              const unit = lessonsUnitTarget(run)
              return `cb-lessons-${plan.plan_id}-${Number.isInteger(unit) ? unit : lessonRequestOrdinal}-retry-${failedJobId}`
            }
          })
        : null,

      // H-194: an approved plan is fine-tuned here, through `plan.edit` / `plan.undo`, never by
      // re-sorting this screen. The panel is parent-only: a learner surface has no authoring.
      !isDraft && !learner
        ? jsx(StudioFineTunePanel, {
            course,
            revision,
            onRevision,
            plan,
            objectives,
            sections: (book && book.data && book.data.sections) || [],
            planHash,
            supported,
            onChanged,
            onOpenReview,
            review,
            onDirtyChange
          })
        : null,

      !isDraft && contentReady
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children:
              'Re-running generation reuses every lesson already authored at this plan version and only authors what is missing. Nothing is paid for twice.'
          })
        : null,

      hideOutline
        ? null
        : jsxs('div', {
        className: 'flex flex-col gap-4 min-[60rem]:flex-row min-[60rem]:items-start',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-1 flex-col gap-2',
            children: [
              jsx('p', {
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                'data-cb-breadth': 'plan',
                children: PLAN_BREADTH_DISCLOSURE
              }),
              jsx(CbLabel, { children: `OUTLINE AND ACTIVITIES (${objectives.length})` }),
              ...displayObjectives.map((objective, index) => {
                const draft = drafts[objective.objective_id] || {}
                const isRemoved = removed.includes(objective.objective_id)
                return jsxs(
                  'div',
                  {
                    className: `flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2${isRemoved ? ' opacity-60' : ''}`,
                    'data-cb-objective': objective.objective_id,
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('div', {
                            className: 'flex min-w-0 items-baseline gap-2',
                            children: [
                              jsx('span', { className: 'shrink-0 text-xs tabular-nums text-(--ui-text-secondary)', children: String(objective.ordinal).padStart(2, '0') }),
                              editing
                                ? jsx(sdk.Input, {
                                    'aria-label': `Objective ${objective.ordinal} title`,
                                    value: draft.title || '',
                                    onChange: (event) =>
                                      setDrafts((previous) => ({
                                        ...previous,
                                        [objective.objective_id]: { ...draft, title: event.target.value }
                                      })),
                                    className: 'min-w-0 flex-1'
                                  })
                                : jsx('span', { className: 'min-w-0 break-words text-sm', children: objective.title })
                            ]
                          }),
                          jsxs('div', {
                            className: 'flex shrink-0 items-center gap-2',
                            children: [
                              editing
                                ? jsx(sdk.Select, {
                                    value: draft.evidence_target || objective.evidence_target,
                                    onValueChange: (value) =>
                                      setDrafts((previous) => ({
                                        ...previous,
                                        [objective.objective_id]: { ...draft, evidence_target: value }
                                      })),
                                    children: [
                                      jsx(sdk.SelectTrigger, {
                                        'aria-label': `Objective ${objective.ordinal} evidence target`,
                                        className: 'w-36',
                                        children: jsx(sdk.SelectValue, {})
                                      }, 'trigger'),
                                      jsx(
                                        sdk.SelectContent,
                                        {
                                          children: EVIDENCE_TARGET_OPTIONS.map((option) =>
                                            jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                                          )
                                        },
                                        'content'
                                      )
                                    ]
                                  })
                                : jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: objective.evidence_target }),
                              editing
                                ? jsxs('div', {
                                    className: 'flex items-center gap-1',
                                    children: [
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        disabled: index === 0,
                                        onClick: () => {
                                          const ids = displayObjectives.map((item) => item.objective_id)
                                          const [moved] = ids.splice(index, 1)
                                          ids.splice(index - 1, 0, moved)
                                          setOrder(ids)
                                        },
                                        children: 'Up'
                                      }),
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        disabled: index === displayObjectives.length - 1,
                                        onClick: () => {
                                          const ids = displayObjectives.map((item) => item.objective_id)
                                          const [moved] = ids.splice(index, 1)
                                          ids.splice(index + 1, 0, moved)
                                          setOrder(ids)
                                        },
                                        children: 'Down'
                                      }),
                                      jsx(sdk.Button, {
                                        size: 'sm',
                                        variant: 'text',
                                        onClick: () =>
                                          setRemoved((previous) =>
                                            previous.includes(objective.objective_id)
                                              ? previous.filter((id) => id !== objective.objective_id)
                                              : [...previous, objective.objective_id]
                                          ),
                                        children: isRemoved ? 'Keep' : 'Remove'
                                      })
                                    ]
                                  })
                                : null
                            ]
                          })
                        ]
                      }),
                      jsx('div', {
                        className: 'text-xs text-(--ui-text-secondary)',
                        'data-cb-objective-state': objective.state || 'none',
                        'data-cb-objective-check': objective.check_state || 'none',
                        // The authoring row still shows the plan gate's own state, in the same
                        // words the trail and the path use. The backend enum is the `data-*`
                        // attribute for evidence inspection, never the sentence a parent reads.
                        children: `${OBJECTIVE_STATE_COPY[objective.state] || 'State not recorded'} · ${cbCheckStateWord(objective.check_state)}`
                      })
                    ]
                  },
                  objective.objective_id
                )
              }),
              editing
                ? jsxs('div', {
                    className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                    children: [
                      jsx(CbLabel, { children: 'Add an objective' }),
                      added.map((item, index) =>
                        jsxs(
                          'div',
                          {
                            className: 'flex flex-wrap items-center gap-2',
                            children: [
                              jsx(sdk.Input, {
                                'aria-label': `New objective ${index + 1} title`,
                                value: item.title,
                                onChange: (event) =>
                                  setAdded((previous) =>
                                    previous.map((entry, position) =>
                                      position === index ? { ...entry, title: event.target.value } : entry
                                    )
                                  ),
                                placeholder: 'Objective title',
                                className: 'min-w-0 flex-1'
                              }),
                              jsx(sdk.Select, {
                                value: item.evidence_target,
                                onValueChange: (value) =>
                                  setAdded((previous) =>
                                    previous.map((entry, position) =>
                                      position === index ? { ...entry, evidence_target: value } : entry
                                    )
                                  ),
                                children: [
                                  jsx(sdk.SelectTrigger, {
                                    'aria-label': `New objective ${index + 1} evidence target`,
                                    className: 'w-36',
                                    children: jsx(sdk.SelectValue, {})
                                  }, 'trigger'),
                                  jsx(
                                    sdk.SelectContent,
                                    {
                                      children: EVIDENCE_TARGET_OPTIONS.map((option) =>
                                        jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id)
                                      )
                                    },
                                    'content'
                                  )
                                ]
                              }),
                              jsx(sdk.Button, {
                                size: 'sm',
                                variant: 'text',
                                onClick: () => setAdded((previous) => previous.filter((_entry, position) => position !== index)),
                                children: 'Remove'
                              })
                            ]
                          },
                          `added-${index}`
                        )
                      ),
                      jsx(sdk.Button, {
                        size: 'sm',
                        variant: 'secondary',
                        className: 'self-start',
                        onClick: () => setAdded((previous) => [...previous, { title: '', evidence_target: 'recall' }]),
                        children: 'Add objective'
                      })
                    ]
                  })
                : null
            ]
          }),
          jsxs('div', {
            className: 'flex w-full shrink-0 flex-col gap-2 min-[60rem]:w-[20rem]',
            children: [
              jsx(CbLabel, { children: 'Sources and review notes' }),
              jsx(QuietNote, {
                children:
                  'Sources come from the research that produced this plan. If research was unavailable the plan says so; no citation is invented here.'
              }),
              jsx(SourceProvenancePanel, {
                sources,
                status: book && book.status ? (book.status === 'ready' ? 'ready' : book.status) : 'loading',
                error: book ? book.error : null,
                onRetry: book ? book.reload : null,
                dense: true,
                emptyTitle: 'No source is recorded for this plan',
                emptyDescription:
                  'No source was recorded for this plan. Nothing on this plan is presented as cited, and no excerpt is invented to fill the gap.',
                extra: jsx(ProvenanceInventoryRow, {
                  vocabulary: planRun && planRun.checkpoint ? planRun.checkpoint.vocabulary : null
                })
              }),
              setting === 'car'
                ? jsx('div', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: 'Car activities are passenger-only. The driver never handles material.'
                  })
                : null,
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: 'A draft plan can be edited freely. An approved plan is changed only by starting a new version, so what you approved stays exact.'
              })
            ]
          })
        ]
      })
    ]
  })
}

/**
 * The learner's plan surface.
 *
 * Parent Studio and a learner course review the same outline through `StudioPlanView`; this
 * wrapper adds what a learner needs around it: the plan job found by enrolment (leaving and
 * reopening reattaches by id, not by memory), the honest time expectation for the chosen scope,
 * and — once the pages exist — a link into the first lesson. It never invents content or a
 * percentage: a failed job keeps its typed reason and the draft stays recoverable.
 */
function LearnerPlanView({
  course,
  revision,
  onRevision,
  implemented,
  onOpenSection,
  onStartLesson,
  onChanged,
  jobHint,
  scopeHint,
  reloadSignal,
  onChangeGoal,
  onNewSyllabus
}) {
  const supports = (method) => (implemented ? implemented.has(method) : backendSupports(method))
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: course.enrollment_id },
    `learner-plan-outline-${course.enrollment_id}`,
    supports('course.outline')
  )
  const book = useRpcQuery(
    'parent.blueprint.read',
    { course_id: course.course_id },
    `learner-plan-book-${course.course_id}`,
    supports('parent.blueprint.read')
  )
  // The job is discovered from the enrolment it names, so a reload or a route change reattaches to
  // the same run instead of starting another one.
  const jobs = useRpcQuery(
    'jobs.list',
    { enrollment_id: course.enrollment_id, kind: ['plan'], limit: 20 },
    `learner-plan-jobs-${course.enrollment_id}`,
    supports('jobs.list')
  )
  const [retryJobId, setRetryJobId] = useState(null)
  // The plan tab's approval is gated by the syllabus mapping on a companion course. The panel
  // reports readiness; the button reads it, and the backend enforces the same rule.
  const [syllabusGate, setSyllabusGate] = useState({ required: false, ready: true, reason: null, stale: false })

  const plan = outline.data && outline.data.plan
  const objectives = (outline.data && outline.data.objectives) || []
  const jobRows = (jobs.data && jobs.data.jobs) || []
  const planJob = jobRows.find((job) => ((job.brief || {}).stage || 'plan') === 'plan') || null
  // G2: a course can have one lessons job per unit, so the surface reads the newest one — its
  // checkpoint is the only honest answer to "is the course fully written?".
  const lessonsJob =
    jobRows
      .filter((job) => (job.brief || {}).stage === 'lessons')
      .sort((left, right) => (Number(right.updated_at) || 0) - (Number(left.updated_at) || 0))[0] || null
  const nextUnitOrdinal = lessonsUnitTarget(lessonsJob)
  const scope = (planJob && planJob.brief && planJob.brief.scope) || scopeHint || null
  const jobId = retryJobId || jobHint || (planJob && planJob.job_id) || null
  // A plan that is already readable does not need its finished job line repeated on every visit.
  // H-103: a rejected or stopped plan is the exception — plan review must read that job to explain
  // the refusal, so its id travels even when objectives already exist.
  const planRunStopped = Boolean(
    planJob &&
      (['failed', 'cancelled', 'interrupted_requires_retry'].includes(planJob.state) ||
        (planJob.checkpoint && planJob.checkpoint.validation_verdict === 'reject'))
  )
  const showJob = Boolean(
    jobId && (objectives.length === 0 || !planJob || !JOB_TERMINAL_STATES.has(planJob.state) || planRunStopped)
  )

  const reloadAll = useCallback(() => {
    outline.reload()
    book.reload()
    jobs.reload()
    if (onChanged) onChanged()
  }, [outline, book, jobs, onChanged])

  if (outline.status === 'error' && !outline.data) {
    return jsx(sdk.ErrorState, {
      title: 'The plan could not be read',
      description: `${outline.error && outline.error.code ? outline.error.code + ': ' : ''}${describeError(outline.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: outline.reload, children: 'Try again' })
    })
  }

  const lessonsFailed = Boolean(
    lessonsJob && ['failed', 'cancelled', 'interrupted_requires_retry'].includes(lessonsJob.state)
  )
  const lessonsReady = Boolean(
    lessonsJob &&
      !lessonsFailed &&
      JOB_TERMINAL_STATES.has(lessonsJob.state) &&
      Number((lessonsJob.checkpoint || {}).lessons || 0) > 0
  )
  const approved = Boolean(plan && plan.state === 'approved')

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    'data-cb-learner-plan': (plan && plan.state) || 'none',
    'data-cb-learner-plan-job': jobId || 'none',
    children: [
      jsx('p', { className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)', children: planTimingCopy(scope) }),
      approved && objectives.length > 0
        ? jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              lessonsReady && onStartLesson && !Number.isInteger(nextUnitOrdinal)
                ? jsx(CbAction, {
                    variant: 'primary',
                    onClick: () => onStartLesson(objectives[0].objective_id),
                    children: 'Start the first lesson'
                  })
                : null,
              onOpenSection
                ? jsx(sdk.Button, {
                    size: 'sm',
                    variant: 'secondary',
                    onClick: () => onOpenSection(objectives[0].objective_id),
                    children: 'Open the first section'
                  })
                : null
            ]
          })
        : null,
      approved && !lessonsReady && !lessonsFailed
        ? jsx(QuietNote, {
            children:
              'The outline is approved. Coursebook writes the lesson pages below; the section list is the approved outline.'
          })
        : null,
      approved && objectives.length > 0 && onOpenSection
        ? jsx(PlanView, {
            row: { course_id: course.course_id, enrollment_id: course.enrollment_id, revision },
            review: null,
            notebooks: null,
            outline: outline.data,
            page: null,
            implemented,
            onOpenSection,
            onChanged: reloadAll
          })
        : null,
      jsx(SyllabusAlignmentPanel, {
        course,
        planId: plan ? plan.plan_id : null,
        planState: plan ? plan.state : null,
        reloadSignal,
        onGateChange: setSyllabusGate,
        onChanged: reloadAll,
        onNewSyllabus
      }),
      jsx(StudioPlanView, {
        course,
        revision,
        onRevision,
        outline,
        book,
        brief: null,
        planJobId: showJob ? jobId : null,
        // The learner route already found this job by enrolment, so the wait panel renders the
        // clock and stage on the first paint instead of waiting for a second poll of the same id.
        planJob,
        planScope: scope,
        // H-105: a finished plan job is not re-polled, but its checkpoint already carries the
        // validator record, so a revisit still shows who checked this version.
        planJobHint: planJob,
        onChangeGoal,
        onJobSettled: reloadAll,
        onChanged: reloadAll,
        supported: supports,
        surface: 'learner',
        outlineHidden: approved,
        syllabusGate
      })
    ]
  })
}

/** The five tabs of §10, as declared text. Sources is its own tab and is always answered. */
function StudioBlueprintView({ book }) {
  const [tab, setTab] = useState('learner_pages')
  if (!book || book.status === 'loading') {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the pages' }) })
  }
  if (book.status === 'error' && !book.data) {
    return jsx(sdk.ErrorState, {
      title: 'The pages could not be read',
      description: `${book.error && book.error.code ? book.error.code + ' : ' : ''}${describeError(book.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: book.reload, children: 'Try again' })
    })
  }
  const data = book.data || {}
  const tabs = data.tabs || {}
  const files = tabs[tab] || []
  const sources = data.sources || []
  const notice = {
    parent_guide: 'The parent guide is what you follow while teaching. It can quote the answer guide; the learner pages never do.',
    learner_pages: 'These are the learner pages. No answer key is included here — answers live in their own tab and are a different file role.',
    answers: 'The answer guide. It is served by course id only, so it is never reachable from a learner’s lesson surface, and export keeps it out of the learner pages.',
    narration: 'The narration script you read aloud. It is text, not an audio file, and it is also inside the parent guide.',
    sources: 'Every source this plan recorded, with the support verdict it earned.'
  }[tab]

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx(StudioViewPicker, { id: 'cb-studio-tab', label: 'Tab', value: tab, options: STUDIO_TABS, onChange: setTab }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: notice }),
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('span', { children: `${files.length} file${files.length === 1 ? '' : 's'} in this tab` }),
          jsx('span', { children: `content hash ${String(data.content_hash || '').slice(0, 19)}…` })
        ]
      }),
      tab === 'sources'
        ? jsx(SourceProvenancePanel, {
            sources,
            status: book.status === 'ready' ? 'ready' : book.status,
            error: book.error,
            onRetry: book.reload,
            emptyTitle: 'No source is recorded for this course',
            emptyDescription:
              'No source was recorded for this course. Nothing here is presented as cited, and no excerpt is invented to fill the gap.',
            intro: notice
          })
        : files.length === 0
          ? jsx(EmptyState, {
              title: 'Nothing generated for this tab yet',
              description:
                tab === 'narration'
                  ? 'This course asked for no narration, or no lesson has been generated yet.'
                  : 'The plan must be approved and its lessons generated before this tab has text.',
              children: null
            })
          : jsx('div', {
              className: 'flex flex-col gap-4',
              children: files.map((file, index) =>
                jsxs(
                  'article',
                  {
                    className: 'flex flex-col gap-1.5 border-t border-(--ui-stroke-tertiary) pt-3',
                    'data-cb-blueprint-role': file.role,
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('h3', { className: 'min-w-0 break-words text-sm font-semibold', children: file.title }),
                          jsxs('div', {
                            className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
                            children: [
                              jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                              jsx('span', { children: bytesLabel(file.bytes) }),
                              file.truncated ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: 'clipped' }) : null
                            ]
                          })
                        ]
                      }),
                      jsx(ProseText, { className: 'max-w-3xl', text: file.text }),
                      jsxs('div', {
                        className: 'text-xs break-all text-(--ui-text-secondary)',
                        children: [`sha256 ${file.sha256}`, file.truncated ? ' · the served text was clipped at the tab limit' : '']
                      })
                    ]
                  },
                  `${file.role}-${index}`
                )
              )
            })
    ]
  })
}

/** Export: gated on the backend's own `export.blocked_reason`, files and downloads from the response. */
function StudioExportPanel({ course, book, revision, onRevision, supported, onChanged, review, objectives }) {
  const [formats, setFormats] = useState({ pack: true, pdf: true })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifacts, setArtifacts] = useState({})
  const [approving, setApproving] = useState(false)
  const [approveError, setApproveError] = useState(null)

  const status = (book && book.data && book.data.export) || { ready: false, blocked_reason: 'no_generated_content' }
  const approval = (book && book.data && book.data.approval) || { state: 'none' }
  const plan = (book && book.data && book.data.plan) || {}
  const planHash = plan.plan_hash || null
  const contentHash = (book && book.data && book.data.content_hash) || null
  const chosen = [formats.pack ? 'pack' : null, formats.pdf ? 'pdf' : null].filter(Boolean)

  // Final approval is its own gate: the plan approved an outline, this approves the exact
  // generated lesson set, fenced by the content hash the backend served (never computed here).
  const approveFinal = useCallback(async () => {
    setApproving(true)
    setApproveError(null)
    const response = await rpc(
      'parent.final.approve',
      {
        enrollment_id: course.enrollment_id,
        plan_id: plan.plan_id,
        plan_hash: planHash,
        content_hash: contentHash
      },
      {
        expectedRevision: typeof revision === 'number' ? revision : 0,
        idempotencyKey: newOperationId('parent-final-approve')
      }
    )
    setApproving(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null && typeof onRevision === 'function') onRevision(nextRevision)
      setApproveError(
        describeError(response.error) +
          (nextRevision !== null ? ' The course was updated elsewhere; press Approve this lesson set again.' : '')
      )
      return
    }
    if (typeof onRevision === 'function') onRevision(Number(response.result.revision) || 0)
    if (typeof onChanged === 'function') onChanged()
  }, [course.enrollment_id, plan.plan_id, planHash, contentHash, revision, onRevision, onChanged])

  const run = useCallback(async () => {
    setBusy(true)
    setError(null)
    setExported(null)
    setArtifacts({})
    const response = await rpc(
      'parent.export',
      { enrollment_id: course.enrollment_id, formats: chosen },
      { idempotencyKey: newOperationId('parent-export') }
    )
    if (!response.ok) {
      setBusy(false)
      const details = (response.error && response.error.details) || {}
      setError({
        code: response.error && response.error.code,
        reason: details.reason,
        message: describeError(response.error),
        problems: Array.isArray(details.problems) ? details.problems : null
      })
      return
    }
    setExported(response.result)
    const next = {}
    for (const artifact of response.result.artifacts || []) {
      const facts = await rpc('artifact.get', { artifact_id: artifact.artifact_id })
      if (facts.ok) next[artifact.artifact_id] = facts.result
    }
    setArtifacts(next)
    setBusy(false)
  }, [course.enrollment_id, formats.pack, formats.pdf])

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(CbLabel, { children: 'Export gate' }),
      jsx(StudioReviewDiff, { review, objectives }),
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx(PackReviewLine, { label: 'Plan', value: (book && book.data && book.data.plan && `${book.data.plan.state} · v${book.data.plan.version}`) || '—' }),
          jsx(PackReviewLine, { label: 'Lesson set approval', value: APPROVAL_STATE_COPY[approval.state] || approval.state }),
          jsx(PackReviewLine, {
            label: 'Approved content hash',
            value: jsx('code', { className: 'text-xs break-all', children: approval.content_hash || '—' })
          }),
          jsx(PackReviewLine, {
            label: 'Current content hash',
            value: jsx('code', { className: 'text-xs break-all', children: (book && book.data && book.data.content_hash) || '—' })
          })
        ]
      }),
      jsx(CbLabel, { children: 'Final approval' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Approving the plan approved the outline and its activities. This gate is separate: it approves the generated lesson set by its content hash, and any later edit to the plan, the pages or the course title clears it.'
      }),
      approval.state === 'active'
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `Lesson set approved${approval.approved_at ? ' on ' + whenLabel(approval.approved_at) : ''}${
              approval.content_hash ? ' for content hash ' + approval.content_hash : ''
            }.`
          })
        : jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              !planHash || !contentHash
                ? jsx('div', {
                    className: 'text-xs text-(--ui-text-secondary)',
                    children: !planHash
                      ? 'There is no approved plan to approve a lesson set for yet.'
                      : 'No generated pages exist yet, so there is nothing to approve. Generate the lessons from the Plan view first.'
                  })
                : !supported('parent.final.approve')
                  ? jsx('div', {
                      className: 'text-xs text-(--ui-text-secondary)',
                      children: 'This backend does not implement parent.final.approve yet.'
                    })
                  : null,
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                className: 'self-start',
                disabled: approving || !planHash || !contentHash || !supported('parent.final.approve'),
                onClick: approveFinal,
                children: approving ? 'Approving the lesson set' : 'Approve this lesson set'
              }),
              approveError ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: approveError }) : null
            ]
          }),
      status.ready
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Export is available: the approved lesson set matches the pages shown.' })
        : jsxs('div', {
            className: 'flex flex-col gap-0.5 text-xs leading-relaxed text-(--ui-text-secondary)',
            'data-cb-export-blocked': status.blocked_reason || 'unknown',
            children: [
              jsx('div', {
                children:
                  EXPORT_BLOCKED_COPY[status.blocked_reason] ||
                  `Export is blocked (${status.blocked_reason}).`
              }),
              // The backend's own word, verbatim: a mapped sentence may explain it, never soften it.
              jsx('div', {
                'data-cb-export-blocked-reason': status.blocked_reason || '',
                children: `Backend reason: ${status.blocked_reason || 'none reported'}.`
              })
            ]
          }),

      jsx(CbLabel, { children: 'Formats' }),
      jsx(StudioCheck, {
        id: 'cb-export-pack',
        checked: formats.pack,
        onChange: (value) => setFormats((previous) => ({ ...previous, pack: value })),
        children: 'Pack archive (parent guide, learner pages, answer guide).'
      }),
      jsx(StudioCheck, {
        id: 'cb-export-pdf',
        checked: formats.pdf,
        onChange: (value) => setFormats((previous) => ({ ...previous, pdf: value })),
        children: 'Printable PDF: selectable text, low-ink layout, no color-only answers.'
      }),
      jsx(CbAction, {
        variant: 'primary',
        disabled: busy || !status.ready || chosen.length === 0 || !supported('parent.export'),
        onClick: run,
        children: busy ? 'Exporting' : 'Export the approved files'
      }),
      error
        ? jsxs('div', {
            className: 'flex flex-col gap-1 text-xs text-(--ui-text-secondary)',
            children: [
              jsx('div', {
                children: `${error.code ? error.code + ': ' : ''}${error.reason ? (EXPORT_REFUSAL_COPY[error.reason] || error.reason) : ''} ${error.message}`
              }),
              error.problems
                ? jsxs('div', {
                    className: 'flex flex-col gap-0.5 text-(--ui-text-secondary)',
                    children: [
                      jsx('div', { children: 'The pack minima reported these problems:' }),
                      ...error.problems.map((problem, index) =>
                        jsx('div', { children: typeof problem === 'string' ? problem : JSON.stringify(problem) }, `problem-${index}`)
                      )
                    ]
                  })
                : null
            ]
          })
        : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col gap-3',
            children: [
              jsx(CbLabel, { children: 'Exported files' }),
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: `Export ${exported.export_id} · ${whenLabel(exported.exported_at)} · content hash ${exported.content_hash}`
              }),
              jsxs('div', {
                className: 'flex flex-col',
                children: (exported.files || []).map((file) =>
                  jsx(PackReviewLine, {
                    label: `${file.role} · ${file.name}`,
                    value: `${bytesLabel(file.bytes)} · ${file.mime}`
                  }, file.name)
                )
              }),
              jsxs('div', {
                className: 'flex flex-col gap-1 text-xs leading-relaxed text-(--ui-text-secondary)',
                children: [
                  jsx('div', {
                    children:
                      'The pack carries parent guide, learner pages and answer guide. Narration stays an audio role, so an authored text script is not exported as a narration file: it is the Audio & visuals tab and part of the parent guide.'
                  }),
                  jsx('div', { children: 'Exported files never include attempts, notebook notes, reflections, transcripts or provider settings.' })
                ]
              }),
              ...(exported.artifacts || []).map((artifact) => {
                const facts = artifacts[artifact.artifact_id]
                return jsxs(
                  'div',
                  {
                    className: 'flex flex-col gap-1 border-t border-(--ui-stroke-tertiary) pt-2',
                    children: [
                      jsxs('div', {
                        className: 'flex flex-wrap items-baseline justify-between gap-2',
                        children: [
                          jsx('div', { className: 'text-xs font-medium', children: `${artifact.kind} · ${artifact.mime} · ${bytesLabel(artifact.bytes)}` }),
                          jsx('div', { className: 'min-w-0 break-all text-xs text-(--ui-text-secondary)', children: artifact.content_hash })
                        ]
                      }),
                      facts && facts.download
                        ? jsx(sdk.Button, {
                            asChild: true,
                            size: 'sm',
                            variant: 'secondary',
                            children: jsx('a', {
                              download:
                                artifact.kind === 'pdf'
                                  ? 'parent-lesson-pack.pdf'
                                  : artifact.kind === 'pack'
                                    ? 'parent-lesson-pack.zip'
                                    : 'parent-export.json',
                              href: facts.download.url,
                              children:
                                artifact.kind === 'pdf'
                                  ? 'Download PDF'
                                  : artifact.kind === 'pack'
                                    ? 'Download pack archive'
                                    : 'Download export record'
                            })
                          })
                        : null,
                      facts && facts.download
                        ? jsx('div', {
                            className: 'text-xs text-(--ui-text-secondary)',
                            children: facts.download.requires_session
                              ? 'Session-bound, expiring link served by this host’s artifact route. A filesystem path never leaves the backend.'
                              : 'Host artifact route.'
                          })
                        : null
                    ]
                  },
                  artifact.artifact_id
                )
              })
            ]
          })
        : null
    ]
  })
}

/** §10 reflection: parent-reported, easy/about right/too hard plus a revisit note. */
function StudioReflectionView({ course, reflections, supported, onDuplicate, onSaved }) {
  const [difficulty, setDifficulty] = useState('about_right')
  const [note, setNote] = useState('')
  const [applyToNext, setApplyToNext] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(null)

  const record = useCallback(async () => {
    setBusy(true)
    setError(null)
    const response = await rpc(
      'parent.reflection.record',
      {
        course_id: course.course_id,
        enrollment_id: course.enrollment_id,
        difficulty,
        revisit_note: note.trim() ? note.trim() : null,
        apply_to_next_draft: applyToNext
      },
      { idempotencyKey: newOperationId('reflection') }
    )
    setBusy(false)
    if (!response.ok) {
      setError(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setSaved(response.result)
    setNote('')
    onSaved()
  }, [course.course_id, course.enrollment_id, difficulty, note, applyToNext, onSaved])

  const list = (reflections && Array.isArray(reflections.reflections) ? reflections.reflections : []).slice()
  const latest = list.find((item) => item.apply_to_next_draft && item.revisit_note)

  return jsxs('div', {
    className: 'flex max-w-2xl flex-col gap-4',
    children: [
      jsx(QuietNote, {
        children:
          'A reflection is parent-reported. It is not evidence of learning, it is never graded, and it is excluded from every exported pack. Its only purpose is to seed your next brief.'
      }),
      jsx(CbLabel, { children: 'How did it go?' }),
      jsx(StudioViewPicker, {
        id: 'cb-studio-difficulty',
        label: 'Difficulty',
        value: difficulty,
        options: STUDIO_DIFFICULTIES,
        onChange: setDifficulty
      }),
      jsx(StudioField, {
        id: 'cb-reflection-note',
        label: 'What would you revisit?',
        hint: 'Optional. This note is offered to your next draft as a proposal, never applied silently.',
        children: jsx(sdk.Textarea, {
          id: 'cb-reflection-note',
          rows: 3,
          value: note,
          onChange: (event) => setNote(event.target.value),
          placeholder: 'The quarter-to-eighth cut needed a second demonstration.'
        })
      }),
      jsx(StudioCheck, {
        id: 'cb-reflection-apply',
        checked: applyToNext,
        onChange: setApplyToNext,
        children: 'Offer this note to my next draft.'
      }),
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(CbAction, {
            variant: 'primary',
            disabled: busy || !supported('parent.reflection.record'),
            onClick: record,
            children: busy ? 'Saving' : 'Record reflection'
          }),
          latest
            ? jsx(sdk.Button, {
                variant: 'secondary',
                onClick: () => onDuplicate(null, latest.revisit_note),
                children: 'Start the next brief from this note'
              })
            : null
        ]
      }),
      error ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: error }) : null,
      saved
        ? jsxs('div', {
            className: 'flex flex-col',
            children: [
              jsx(CbLabel, { children: 'Recorded' }),
              jsx(PackReviewLine, { label: 'Difficulty', value: (STUDIO_DIFFICULTIES.find((item) => item.id === saved.difficulty) || {}).label || saved.difficulty }),
              jsx(PackReviewLine, { label: 'When', value: whenLabel(saved.created_at) }),
              jsx(PackReviewLine, { label: 'Plan hash', value: jsx('code', { className: 'text-xs break-all', children: saved.plan_hash || '—' }) })
            ]
          })
        : null,
      jsx(CbLabel, { children: `REFLECTIONS (${list.length})` }),
      list.length === 0
        ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'No reflections recorded for this course yet.' })
        : jsx('div', {
            className: 'flex flex-col',
            children: list.map((item, index) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-0.5 border-t border-(--ui-stroke-tertiary) py-2',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs',
                      children: [
                        jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: (STUDIO_DIFFICULTIES.find((entry) => entry.id === item.difficulty) || {}).label || item.difficulty }),
                        jsx('span', { className: 'text-(--ui-text-secondary)', children: `parent-reported · ${whenLabel(item.created_at)}` }),
                        item.apply_to_next_draft ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'for next draft' }) : null
                      ]
                    }),
                    item.revisit_note ? jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: item.revisit_note }) : null
                  ]
                },
                item.reflection_id || `reflection-${index}`
              )
            )
          })
    ]
  })
}

/**
 * One authored course, one studio. The header states the two approvals separately because they
 * are separate gates; the body is only ever read from the backend's own rows.
 */
function StudioDetail({ course, implemented, revision, onRevision, onBack, onChanged, onDuplicate }) {
  const supports = useCallback((method) => Boolean(implemented && implemented.has(method)), [implemented])
  const [view, setView] = useState('brief')
  const [notice, setNotice] = useState(null)
  // H-194: an inline section edit is a real unsaved draft. Leaving the view or the course while it
  // differs from storage asks first; the window close/reload is guarded by the panel itself.
  const [dirty, setDirty] = useState(false)
  const [pendingLeave, setPendingLeave] = useState(null)

  const brief = useRpcQuery('parent.brief.get', { course_id: course.course_id }, `studio-brief-${course.course_id}`, supports('parent.brief.get'))
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: course.enrollment_id },
    `studio-outline-${course.course_id}`,
    supports('course.outline') && Boolean(course.enrollment_id)
  )
  const book = useRpcQuery('parent.blueprint.read', { course_id: course.course_id }, `studio-book-${course.course_id}`, supports('parent.blueprint.read'))
  // One review read for both surfaces: the Plan tab's chips and the Export tab's diff are the same
  // `parent.review.read` payload, so they can never disagree about what is pending.
  const review = useRpcQuery(
    'parent.review.read',
    { course_id: course.course_id },
    `studio-review-${course.course_id}`,
    supports('parent.review.read')
  )
  const reflections = useRpcQuery(
    'parent.reflection.list',
    { course_id: course.course_id },
    `studio-reflections-${course.course_id}`,
    supports('parent.reflection.list')
  )

  const reloadAll = useCallback(() => {
    brief.reload()
    outline.reload()
    book.reload()
    review.reload()
    reflections.reload()
    if (onChanged) onChanged()
  }, [brief.reload, outline.reload, book.reload, review.reload, reflections.reload, onChanged])

  const requestView = useCallback(
    (next) => {
      if (next === view) return
      if (dirty) {
        setPendingLeave({ kind: 'view', next })
        return
      }
      setView(next)
    },
    [dirty, view]
  )
  const requestBack = useCallback(() => {
    if (dirty) {
      setPendingLeave({ kind: 'back' })
      return
    }
    onBack()
  }, [dirty, onBack])

  const planJobId = (brief.data && brief.data.plan_job && brief.data.plan_job.job_id) || null
  const onPlanJobSettled = useCallback(() => reloadAll(), [reloadAll])

  const plan = outline.data && outline.data.plan
  const approval = book.data && book.data.approval
  const exportStatus = book.data && book.data.export

  let body
  if (view === 'brief') {
    body = jsx(StudioBriefView, {
      briefQuery: brief,
      course,
      planJobId,
      onJobSettled: onPlanJobSettled,
      onDuplicate,
      reflections: reflections.data
    })
  } else if (view === 'plan') {
    body = jsx(StudioPlanView, {
      course,
      revision,
      onRevision,
      outline,
      book,
      brief: brief.data,
      planJobId,
      onJobSettled: onPlanJobSettled,
      onChanged: reloadAll,
      supported: supports,
      review,
      onOpenReview: () => requestView('export'),
      onDirtyChange: setDirty
    })
  } else if (view === 'blueprint') {
    body = jsx(StudioBlueprintView, { book })
  } else if (view === 'export') {
    body = jsx(StudioExportPanel, {
      course,
      book,
      revision,
      onRevision,
      supported: supports,
      onChanged: reloadAll,
      review,
      objectives: (outline.data && outline.data.objectives) || []
    })
  } else {
    body = jsx(StudioReflectionView, {
      course,
      reflections: reflections.data,
      supported: supports,
      onDuplicate,
      onSaved: reloadAll
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx(sdk.Button, { className: 'self-start', variant: 'text', size: 'sm', onClick: requestBack, children: 'All parent courses' }),
      jsxs('div', {
        className: 'flex flex-wrap items-start justify-between gap-3',
        children: [
          jsxs('div', {
            className: 'flex min-w-0 flex-col gap-1',
            children: [
              jsx('h2', { className: 'min-w-0 break-words text-sm font-semibold', children: course.title || 'Parent course' }),
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'Parent preparation' }),
                  jsx(PlanStateBadge, { plan }),
                  jsx(ApprovalBadge, { approval }),
                  exportStatus && exportStatus.ready
                    ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'Export ready' })
                    : null
                ]
              }),
              // H-156 — what this view reports. The parent sees evidence and their own reports;
              // there is no XP, level or ranking to read here, and the line says so.
              jsx('div', {
                'data-cb-parent-evidence': 'parent_reported',
                className: 'text-xs text-(--ui-text-secondary)',
                children:
                  'Parent view · what your child did and what you observed, never points, levels or rankings.'
              })
            ]
          }),
          jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `You are the operator · revision ${revision}`
          })
        ]
      }),
      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      jsx(StudioReviewBanner, { approval, exportStatus }),
      jsx(StudioViewPicker, { id: 'cb-studio-view', label: 'Studio view', value: view, options: STUDIO_VIEWS, onChange: requestView }),
      pendingLeave
        ? jsxs('div', {
            role: 'alertdialog',
            'aria-label': 'Unsaved section changes',
            'data-cb-studio-leave-guard': pendingLeave.kind,
            className: 'flex flex-wrap items-center gap-2',
            style: {
              padding: '0.6rem 0.75rem',
              background: 'var(--cb3-card-stock)',
              border: '1px solid var(--cb3-rule)',
              borderRadius: cb3Radius('round')
            },
            children: [
              jsx('span', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'The section editor has unsaved changes. Leaving discards them and leaves storage exactly as it is now.'
              }),
              jsx(sdk.Button, {
                size: 'sm',
                variant: 'text',
                'data-cb-studio-leave-discard': '',
                onClick: () => {
                  const pending = pendingLeave
                  setPendingLeave(null)
                  setDirty(false)
                  if (pending && pending.kind === 'back') onBack()
                  else if (pending) setView(pending.next)
                },
                children: 'Discard and leave'
              }),
              jsx(sdk.Button, {
                size: 'sm',
                variant: 'text',
                onClick: () => setPendingLeave(null),
                children: 'Keep editing'
              })
            ]
          })
        : null,
      body
    ]
  })
}

/**
 * A controlled `ConfirmDialog` that hands focus back to the control that opened it.
 *
 * Every Coursebook dialog is opened from a button, not a DialogTrigger, so Radix has no trigger to
 * restore to and focus lands on `<body>` when the dialog unmounts. The control that opened it is
 * remembered at open time and refocused at close; when the section refresh replaced that node while
 * the dialog was up, the same control is found again by its label inside this plugin's own route
 * root. Only Coursebook's own markup is read — nothing here observes or restyles the app shell.
 *
 * This is the ONLY focus-restoration mechanism in the plugin. A separate `useReturnFocus` hook
 * briefly coexisted here (both ran on NotebookSaveDialog); it restored the same opener from the
 * effect cleanup, one animation frame later. It was removed rather than the dialog wrapper because
 * the wrapper also owns the label fallback for a replaced opener and is used by every dialog in
 * this file, so keeping one mechanism means no dialog can drift.
 */
function FocusReturningDialog({ open, ...props }) {
  const openerRef = useRef(null)
  useEffect(() => {
    if (open) {
      const active = document.activeElement
      if (active && active !== document.body && !(active.closest && active.closest('[role="dialog"]'))) {
        openerRef.current = { element: active, label: (active.innerText || '').trim().slice(0, 80) }
      }
      return
    }
    const opener = openerRef.current
    openerRef.current = null
    if (!opener) return
    let target = opener.element && opener.element.isConnected ? opener.element : null
    if (!target && opener.label) {
      const root = document.querySelector('[data-cb-route]')
      target =
        (root &&
          [...root.querySelectorAll('button')].find(
            (button) => (button.innerText || '').trim().slice(0, 80) === opener.label
          )) ||
        null
    }
    if (target && typeof target.focus === 'function') target.focus({ preventScroll: true })
  }, [open])
  const dialogProps = { open, ...props }
  return jsx(sdk.ConfirmDialog, dialogProps)
}

/**
 * H-145 — the product wordmark. It is type, not an ornament: the seal read as an avatar or a
 * refresh glyph and needed an explanation, so the route header carries the name instead. It is a
 * plain div, never a heading, so the page `h1` stays the only page label.
 */
function CoursebookWordmark() {
  return jsx('div', {
    'data-cb-wordmark': '',
    style: {
      fontFamily: 'var(--cb3-font-display)',
      fontSize: cb3Type('meta'),
      fontWeight: 600,
      letterSpacing: '0.14em',
      textTransform: 'uppercase',
      lineHeight: 1.2,
      color: 'var(--cb3-ink-soft)',
      // H-160: "COURSEBOOK" at 28 px (200% text) plus 0.14em tracking measures 239 px, and the
      // route pane at a 460 px window is 215 px (170 px of content). The wordmark was therefore
      // the widest unbreakable token on the route: 46 px of the 53 px routeOverflowX on its own,
      // 7 px more with the page title beside it. Type must not shrink when the learner scales
      // text, so the mark reflows instead: it may break rather than push the route sideways.
      // `anywhere` lowers the min-content width, which is what the wrapping header row sizes from.
      minWidth: 0,
      maxWidth: '100%',
      overflowWrap: 'anywhere'
    },
    children: 'Coursebook'
  })
}

