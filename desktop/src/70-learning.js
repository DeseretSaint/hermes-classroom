// ══ CB-009 — the learning workspace: course detail, lessons, notebook, quizzes ══
//
// Every read below is a real cb.rpc command named in the mounted contract. Where a surface the
// UX spec requires has no command (course outline, check stimulus, pane-side hint/answer events)
// the UI gates on `/runtime.implemented_methods`, says which command is missing, and keeps the
// working control instead of rendering a dead button. See docs/REVIEW_CB009.md.

const LEARNING_VIEWS = [
  { id: 'overview', label: 'Overview' },
  { id: 'textbook', label: 'Textbook' },
  { id: 'notebook', label: 'Notebook' },
  { id: 'quizzes', label: 'Quizzes' },
  { id: 'plan', label: 'Plan' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'sources', label: 'Sources' },
  { id: 'export', label: 'Export' }
]

const PRIMARY_SURFACE_OF_VIEW = {
  overview: 'overview',
  textbook: 'learn',
  guided: 'learn',
  field_quest: 'learn',
  learn: 'learn',
  notebook: 'notebook',
  evidence: 'evidence'
}

/** Which of the four primary course surfaces a legacy view id belongs to. */
function primarySurfaceFor(view) {
  return PRIMARY_SURFACE_OF_VIEW[view] || view
}

/** The four primary course surfaces. Learn is one surface, not three peer tabs. */
const COURSE_PRIMARY_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'learn', label: 'Learn' },
  { id: 'notebook', label: 'Notebook' },
  { id: 'evidence', label: 'Evidence' }
]

/**
 * Everything else, behind one `More` disclosure.
 *
 * Plan, Sources and Export are reference/administration; the graded-attempt record is an
 * inspector of what was already recorded, not a learning surface. Export only appears when the
 * backend advertises `course.export.read`.
 */
function courseMoreTabs(supports) {
  return [
    { id: 'quizzes', label: 'Attempts' },
    { id: 'plan', label: 'Plan' },
    { id: 'sources', label: 'Sources' },
    supports && supports('course.export.read') ? { id: 'export', label: 'Export' } : null
  ].filter(Boolean)
}

/** A section or quiz row is never colour-only: this is the text that carries the state. */
const OBJECTIVE_STATE_COPY = {
  not_started: 'Not started',
  introduced: 'Introduced',
  independent_evidence: 'Independent evidence',
  delayed_evidence: 'Delayed evidence',
  review_due: 'Review due',
  needs_review: 'Needs review',
  overridden: 'Overridden'
}

const EVIDENCE_CLASS_COPY = {
  // The backend's `cold` class means *independent*: no hint and no shown answer. The learner reads
  // what that means for them, never the evidence vocabulary (H-29, UX-05).
  cold: 'First try, no hints',
  hinted: 'Hinted',
  answer_shown: 'Answer shown',
  self_reported: 'Reported by you — not independently verified.',
  parent_reported: 'Reported by the parent — not graded by Coursebook.',
  override: 'Override — not independent evidence'
}

// Frozen copy, docs/CHECKLIST-CONFIRMATION.md §9.4. A confirmation checklist is the learner's own
// statement that they did the steps; it is never an independent observation, so neither string may
// be softened into "mastered", "verified", "passed independently" or an unqualified "complete".
const SELF_REPORTED_CONFIRM_COPY =
  'You confirmed every step. This is your own report, not an independent check.'
const SELF_REPORTED_EVIDENCE_COPY =
  'Self-reported — you told us. It cannot count as independent evidence.'

/** The notice a bare evidence-class badge cannot carry, keyed by class. */
const EVIDENCE_CLASS_NOTICE = {
  self_reported: SELF_REPORTED_EVIDENCE_COPY,
  // One line, because the phrase "First try, no hints" raises the obvious question: why does it
  // matter? It matters because it is the only thing that counts as independent evidence.
  cold: 'Independent evidence is worth more: it shows what you can do without help.'
}

/*
 * H-178 · the integrity chip.
 *
 * The chip is the product's one original mechanic made legible: the evidence class is *how the
 * answer was produced*, not how good it was. Labels stay the frozen learner vocabulary
 * (`EVIDENCE_CLASS_COPY`) except for two authored overrides: `answer_shown` prints the spec's full
 * sentence because "Answer shown" alone reads like a neutral fact rather than a downgrade, and
 * `self_reported` prints the learner's own voice ("you told us") rather than the report register of
 * "Reported by you — not independently verified." Both still say, in words, that the attempt is not
 * independent evidence — the meaning is the frozen one, only the register differs.
 *
 * The sentence under the label says what the class means for *this* answer. Nothing here is
 * computed: every value is the backend's own `evidence_class` from `attempt.submit`,
 * `lesson.assist`, or the uncommitted event `evidence.inspect` returns.
 */
const EVIDENCE_CHIP_LABEL = {
  ...EVIDENCE_CLASS_COPY,
  self_reported: 'Self-reported — you told us',
  answer_shown: 'Answer shown — this attempt is no longer independent'
}

const EVIDENCE_CHIP_SENTENCE = {
  cold: 'No hint and no shown answer went into this answer, so it can count as independent evidence for the objective.',
  hinted: 'A hint was recorded before this answer. The attempt is still recorded, but it cannot count as independent evidence.',
  answer_shown: 'The answer was shown before this attempt. It records what you did after seeing the answer, not what you can do unaided.',
  self_reported: 'It cannot count as independent evidence.',
  parent_reported: 'An adult recorded this observation. Coursebook did not grade it, so it is not independent evidence.',
  override: 'You moved on without a grade. Access advanced; the objective is not counted as independent evidence.'
}

/** Everything the chip prints for one backend evidence class, or nothing for an unknown value. */
function evidenceChipView(value) {
  if (!value) return null
  const label = EVIDENCE_CHIP_LABEL[value] || String(value).replaceAll('_', ' ')
  const sentence = EVIDENCE_CHIP_SENTENCE[value] || null
  return { value, label, sentence }
}

/**
 * The chip itself: a bordered label, never a score, plus one plain-language sentence.
 *
 * `pending` marks the class the *next* committed attempt will carry. It is rendered before the
 * learner submits (so the rule is visible at the moment of effort) and after the verdict (so the
 * record and the claim agree). The class is always passed in from a backend field; this component
 * has no default and prints nothing when it is given none.
 */
function EvidenceChip({ value, pending = false }) {
  const view = evidenceChipView(value)
  if (!view) return null
  return jsxs('div', {
    'data-cb-evidence-chip': view.value,
    'data-cb-evidence-pending': pending ? 'true' : 'false',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.2rem',
      maxWidth: CB_MEASURE,
      padding: '0.45rem 0.6rem',
      borderLeft: '2px solid var(--cb-ochre)',
      background: 'var(--cb-lamp-soft)',
      boxSizing: 'border-box'
    },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'baseline', gap: '0.4rem', flexWrap: 'wrap' },
        children: [
          jsx('span', {
            'data-cb-evidence-chip-label': view.value,
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, fontWeight: 600, lineHeight: 1.35, color: 'var(--cb-ink)' },
            children: view.label
          }),
          pending
            ? jsx('span', {
                'data-cb-evidence-chip-pending': '',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: 'if you submit now'
              })
            : null
        ]
      }),
      view.sentence
        ? jsx('p', {
            'data-cb-evidence-chip-sentence': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: view.sentence
          })
        : null
    ]
  })
}

/**
 * The learner-facing words for the rubric's evidence target.
 *
 * `discrimination` is a construct id, not a label a person should have to decode. The badge shows
 * the plain phrase; the raw id travels in the index's opened details panel so an audit can still
 * name the exact construct (UX-04, UX-05).
 */
const EVIDENCE_TARGET_LEARNER_COPY = {
  recall: 'Remember it',
  comprehension: 'Explain it',
  production: 'Say or write it',
  discrimination: 'Tell the difference',
  procedure: 'Do the steps',
  transfer: 'Use it somewhere new'
}

function learnerEvidenceTarget(value) {
  if (!value) return ''
  const known = EVIDENCE_TARGET_LEARNER_COPY[value]
  if (known) return known
  // An unknown enum is still never printed raw: snake_case becomes sentence case.
  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

/**
 * The four states the index uses. Every row carries BOTH an icon and a word, so the state is
 * legible without colour. `next` is not a stored state: it is projected from the backend's own
 * next step, and it wins over the stored state only while that section is still open.
 */
const SECTION_STATE_SEMANTIC = {
  not_started: { key: 'not_started', label: 'Not started', icon: 'circle-outline' },
  introduced: { key: 'started', label: 'Started', icon: 'circle-filled' },
  independent_evidence: { key: 'complete', label: 'Complete', icon: 'pass' },
  delayed_evidence: { key: 'complete', label: 'Complete', icon: 'pass' },
  review_due: { key: 'review', label: 'Review due', icon: 'history' },
  needs_review: { key: 'review', label: 'Review needed', icon: 'history' },
  overridden: { key: 'moved_on', label: 'Moved on without a grade', icon: 'dash' }
}

function sectionStateSemantic(state, isNext) {
  const settled = state === 'independent_evidence' || state === 'delayed_evidence'
  if (isNext && !settled) return { key: 'next', label: 'Next', icon: 'chevron-right' }
  return SECTION_STATE_SEMANTIC[state] || SECTION_STATE_SEMANTIC.not_started
}

/**
 * "3 of 4 objectives have independent evidence" — a count the backend already records.
 *
 * There is no percentage, no streak and no mastery word: `independent` is the objective's own
 * stored state, and a course with nothing recorded says so instead of showing a zero that looks
 * like a grade.
 */
function progressStatement(independent, total) {
  const done = Math.max(0, Number(independent) || 0)
  const all = Math.max(0, Number(total) || 0)
  if (all === 0) return 'No objectives recorded yet'
  const noun = all === 1 ? 'objective' : 'objectives'
  return `${done} of ${all} ${noun} ${all === 1 ? 'has' : 'have'} independent evidence`
}

/** The counts the index and overview print, read only from the outline the backend returned. */
function objectiveProgress(objectives, totalFallback) {
  const list = Array.isArray(objectives) ? objectives.filter(Boolean) : []
  const total = list.length > 0 ? list.length : Math.max(0, Number(totalFallback) || 0)
  const independent = list.filter((entry) => entry.independent).length
  const due = list.filter((entry) => entry.state === 'review_due' || entry.state === 'needs_review').length
  return { total, independent, due, statement: progressStatement(independent, total) }
}

/**
 * A self-reported attempt never renders the unqualified `Passed` label: the badge carries the
 * qualifier with it wherever attempts are listed, so a row read out of context cannot claim an
 * independent pass.
 */
function verdictLabel(verdict, evidenceClass) {
  if (evidenceClass === 'self_reported' && verdict === 'pass') return 'Self-reported pass'
  return VERDICT_COPY[verdict] || verdict || 'unknown'
}

/** Next-step copy for a self-reported verdict; the generic strings say "complete" unqualified. */
const SELF_REPORTED_NEXT_ACTION = {
  complete_objective:
    'This objective advances on your own report, not an independent check. It will come back for review.',
  review_objective:
    'Access advanced on your own report. It is not independent evidence and it will return for review.',
  continue: 'Continue when you are ready; what you confirmed here was your own report.',
  retry_attempt: 'Tick the remaining steps and submit again. This stays your own report.'
}

function nextActionCopy(result) {
  if (!result) return 'The backend recorded the next action.'
  if (result.evidence_class === 'self_reported' && SELF_REPORTED_NEXT_ACTION[result.next_action]) {
    return SELF_REPORTED_NEXT_ACTION[result.next_action]
  }
  return NEXT_ACTION_COPY[result.next_action] || 'The backend recorded the next action.'
}

/**
 * One concrete thing the learner showed, read from the graded criteria.
 *
 * This replaces the old "objective complete" line. It is deliberately not a compliment
 * generator: it repeats only what the backend marked `met` with an observation, and a pass with no
 * observation says exactly that instead of inventing a takeaway.
 */
function verdictTakeaway(result, criteria) {
  if (!result || result.verdict !== 'pass') return null
  if (result.evidence_class === 'self_reported') return null
  const shown = (criteria || [])
    .filter((item) => item && item.met && item.observed)
    .map((item) => String(item.observed).trim())
    .filter(Boolean)
  if (shown.length === 0) return 'You answered with no hints, and the backend recorded this check as a pass.'
  return `What you showed: ${shown.slice(0, 2).join('; ')}.`
}

/**
 * The checklist answer object sent to `attempt.submit`.
 *
 * Frozen by docs/CHECKLIST-CONFIRMATION.md §9.2: `kind: "selection"` over the check's own item ids.
 * The label is the question, never the answer — sending labels, or mixing in the typed text, is a
 * different answer than the one the kernel grades (`unknown_check_item` otherwise).
 */
function checklistAnswer(ids) {
  return { kind: 'selection', selection: (ids || []).slice() }
}

/** The items a check card may tick: a served `verification` stimulus with declared items. */
function checklistItems(stimulus) {
  if (!stimulus || stimulus.format !== 'verification') return []
  return Array.isArray(stimulus.items) ? stimulus.items.filter((item) => item && item.id && item.label) : []
}

/**
 * What a learner reads when the question could not be loaded.
 *
 * It names the failure when the backend did (a refusal code, a transport message) and never claims
 * the question is above. The check itself stays open, so this is a read failure and not a lost
 * attempt: the only action offered is one Retry.
 */
function stimulusUnavailableDescription(error) {
  const detail = error ? `${error.code || 'STIMULUS_UNAVAILABLE'}${error.message ? `: ${error.message}` : ''}` : null
  return detail
    ? `The check opened, but its question did not load (${detail}). Submitting here would be blind, so the answer form stays closed. Retry the read; the check itself is still open.`
    : 'The check opened, but the backend returned no question. Submitting here would be blind, so the answer form stays closed. Retry the read; the check itself is still open.'
}

// Frozen learner-facing breadth copy (`docs/ASSESSMENT-BREADTH.md` §7). One static disclosure for
// every plan and every check: this build grades written answers, choices and checklists only. The
// strings are not keyed to a topic — a keyword classifier over the learner's goal would announce a
// construct-specific limit the harness cannot actually detect.
const PLAN_BREADTH_DISCLOSURE =
  'What Coursebook can check — Written answers, choices, and checklists. This build cannot collect or grade a program, a recording, a photo, or a built object. Checks marked "practice only" never advance a section.'
const CHECK_SURFACE_DISCLOSURE =
  'Your answer is text, a choice, or a checklist. Nothing you type is executed.'
const OPEN_LANE_NOT_GRADED_COPY =
  'Saved, not graded. This build has no grading model for open answers, so no verdict was produced. Your answer is saved, no progress was changed, and Retry grading does not consume an attempt.'
// The backend writes this into `attempts.grading_provenance_json.failure` when it fails closed
// because `grading.grade_open` had no aux grader. That record is the only honest signal that a
// `needs_retry` came from the unconfigured open lane rather than a closed-lane grader fault.
const OPEN_LANE_UNCONFIGURED_PATTERN = /open-response aux grader is not configured/i

const VERDICT_COPY = {
  pass: 'Passed',
  partial: 'Partly there',
  not_yet: 'Not yet',
  // The system's state, not the learner's outcome: this says what happened to the answer, and the
  // saved/not-graded line right under it says nothing was lost (H-29, UX-05/UX-10).
  needs_retry: 'We could not grade this answer'
}

const NEXT_ACTION_COPY = {
  // A pass is evidence for one objective, never mastery of the course. The takeaway (what the
  // learner actually showed) is rendered from the graded criteria above this line.
  complete_objective:
    'Next: open the section after this one and keep going. This check is independent evidence for one objective, not mastery of the whole course.',
  continue: 'Continue the lesson when you are ready.',
  review_objective: 'Access advanced, but this was not independent evidence. It will come back for review.',
  retry_grading: 'The answer is saved. Retry grading does not consume a new attempt.'
}

const REVIEW_ACTION_COPY = {
  snooze: 'Snooze',
  stretch: 'Stretch',
  drop: 'Drop',
  resume: 'Resume'
}

const WARNING_COPY_LEARNING = {
  stale_source: 'A source behind this course changed. Old evidence is kept; the source needs review.',
  detached_chat: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.',
  plan_update: 'A newer plan draft is waiting for review.',
  provider_unavailable: 'A provider needed by this course is unavailable. Nothing is being generated.',
  pending_migration: 'This database needs a migration before every control can run.',
  pack_frozen: 'The imported pack this course came from is frozen; its content will not change.'
}

function StateText({ state }) {
  return jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: OBJECTIVE_STATE_COPY[state] || state || 'unknown' })
}

function EvidenceClassText({ value }) {
  const label = EVIDENCE_CLASS_COPY[value] || value || 'unknown'
  const notice = EVIDENCE_CLASS_NOTICE[value]
  if (!notice) {
    return jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: label })
  }
  // The frozen §9.4 sentence travels with the class wherever it is shown; a badge alone ("Self-
  // reported") could be read as a stronger claim than the learner actually made.
  return jsxs('span', {
    className: 'flex flex-wrap items-baseline gap-1',
    'data-cb-evidence-notice': value,
    children: [
      jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: label }),
      jsx('span', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: notice })
    ]
  })
}

/** True only when the backend's own attempt record says the open lane had no grader. */
function openLaneWasUnconfigured(provenance) {
  if (!provenance || typeof provenance !== 'object') return false
  const failure = provenance.failure
  return typeof failure === 'string' && OPEN_LANE_UNCONFIGURED_PATTERN.test(failure)
}

function Hairline() {
  return jsx('div', { className: 'h-px w-full bg-(--ui-stroke-tertiary)' })
}

function QuietNote({ children }) {
  return jsx('p', {
    className: 'leading-relaxed text-(--ui-text-secondary)',
    style: { maxWidth: CB_MEASURE, fontSize: CB_TYPE.caption },
    children
  })
}

/**
 * A lesson-start notice is text, or text plus one real next action.
 *
 * H-64: the old fresh-run path reported what it had done nowhere and navigated away; every
 * lesson-start outcome now renders here, and when a run is armed the action opens the chat it is
 * armed to. A notice is never a dead label with no way forward.
 */
function NoticeLine({ notice, busy }) {
  if (!notice) return null
  const text = typeof notice === 'string' ? notice : notice.text
  const action = typeof notice === 'string' ? null : notice.action
  return jsxs('div', {
    role: 'status',
    'data-cb-lesson-notice': '',
    className: 'flex flex-wrap items-center justify-between gap-2 text-xs leading-relaxed text-(--ui-text-secondary)',
    style: {
      padding: '0.6rem 0.75rem',
      borderLeft: '2px solid var(--cb-accent)',
      background: 'var(--cb-accent-soft)'
    },
    children: [
      jsx('span', { className: 'max-w-prose min-w-0', children: text }),
      action
        ? jsx(sdk.Button, {
            size: 'sm',
            variant: 'secondary',
            disabled: busy,
            onClick: action.run,
            children: action.label
          })
        : null
    ]
  })
}

function whenLabel(value) {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  const now = Date.now()
  const delta = now - parsed.getTime()
  const day = 86400000
  if (delta < 60000) return 'just now'
  if (delta < 3600000) return `${Math.max(1, Math.round(delta / 60000))} min ago`
  if (delta < day) return `${Math.round(delta / 3600000)} hr ago`
  if (delta < day * 7) return `${Math.round(delta / day)} d ago`
  return parsed.toISOString().slice(0, 10)
}

/**
 * The current check for one objective.
 *
 * `check.open` is the contract's command: it returns the open check or creates one from the
 * objective's audited spec. The revision fence travels in the envelope, so a check opened against
 * an older intent is refused as STALE_REVISION rather than silently winning.
 */
function useOpenCheck({ enrollmentId, objectiveId, revision, enabled, implemented }) {
  // `stimulusStatus` is a state of its own, not a property inferred from `check.stimulus`: a failed
  // or empty `check.get` and a build without that command are different facts, and neither one is
  // "the question is here". `loading` holds the form back rather than offering a blind textarea.
  //   idle → unsupported (no check.get) | loading → ready | unavailable
  const [state, setState] = useState({
    status: 'idle',
    check: null,
    error: null,
    stimulusStatus: 'idle',
    stimulusError: null
  })
  const [ticket, setTicket] = useState(0)
  // `check.open` returns identity only; the learner-facing stimulus (prompt, choices, items) is a
  // separate read. A build that does not implement `check.get` keeps today's answer-only surface
  // (the question lives in the teaching chat) rather than guessing a question.
  const canReadStimulus = Boolean(implemented && implemented.has('check.get'))

  useEffect(() => {
    if (!enabled || !enrollmentId || !objectiveId) {
      setState({ status: 'idle', check: null, error: null, stimulusStatus: 'idle', stimulusError: null })
      return undefined
    }
    let cancelled = false
    setState((previous) => ({
      status: 'loading',
      check: previous.check,
      error: null,
      stimulusStatus: canReadStimulus ? 'loading' : 'unsupported',
      stimulusError: null
    }))
    const settleStimulus = (checkId, update) =>
      setState((previous) =>
        previous.check && previous.check.check_id === checkId ? { ...previous, ...update } : previous
      )
    rpc(
      'check.open',
      { enrollment_id: enrollmentId, objective_id: objectiveId },
      { expectedRevision: Number(revision) || 0 }
    )
      .then((response) => {
        if (cancelled) return
        if (!response || !response.ok) {
          setState({
            status: 'error',
            check: null,
            error: (response && response.error) || null,
            stimulusStatus: 'idle',
            stimulusError: null
          })
          return
        }
        const opened = response.result
        setState({
          status: 'ready',
          check: opened,
          error: null,
          stimulusStatus: canReadStimulus ? 'loading' : 'unsupported',
          stimulusError: null
        })
        if (!canReadStimulus || !opened || !opened.check_id) return
        // A rejection, a refused envelope and an `ok` answer with no stimulus are all "we cannot
        // show this question". Each keeps the opened check on screen and names the failure; none
        // of them may leave the answer form looking as if the prompt were above it.
        rpc('check.get', { enrollment_id: enrollmentId, check_id: opened.check_id })
          .then((detail) => {
            if (cancelled) return
            if (!detail || !detail.ok) {
              settleStimulus(opened.check_id, {
                stimulusStatus: 'unavailable',
                stimulusError: (detail && detail.error) || null
              })
              return
            }
            // `check.open` returns identity only; `check.get` is where the facts the surface needs
            // already live: the stimulus, the check's state, and `attempt_count`. Keeping the last
            // two is not bookkeeping — the pending integrity chip reads `attempt_count` to tell a
            // first try from a retry on the same check, and a dropped field made the chip print
            // "First try, no hints" while the backend committed the answer as `hinted`.
            const detailResult = (detail.result || {})
            const facts = {}
            if (detailResult.attempt_count !== undefined && detailResult.attempt_count !== null && Number.isFinite(Number(detailResult.attempt_count))) {
              facts.attempt_count = Math.max(0, Number(detailResult.attempt_count))
            }
            if (detailResult.state) facts.state = detailResult.state
            const stimulus = detailResult.stimulus || null
            setState((previous) =>
              previous.check && previous.check.check_id === opened.check_id
                ? {
                    ...previous,
                    ...(stimulus ? {} : { stimulusStatus: 'unavailable', stimulusError: null }),
                    check: { ...previous.check, ...facts, ...(stimulus ? { stimulus } : {}) }
                  }
                : previous
            )
            if (!stimulus) return
            settleStimulus(opened.check_id, { stimulusStatus: 'ready', stimulusError: null })
          })
          .catch((error) => {
            if (cancelled) return
            settleStimulus(opened.check_id, {
              stimulusStatus: 'unavailable',
              stimulusError: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
            })
          })
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'error',
            check: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(error) },
            stimulusStatus: 'idle',
            stimulusError: null
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [enrollmentId, objectiveId, revision, enabled, canReadStimulus, ticket])

  return { ...state, reload: () => setTicket((value) => value + 1) }
}

/**
 * The evidence class the learner's *next* committed attempt will carry, read from the backend.
 *
 * `attempt.submit` classifies an answer by how it was produced, and the classification is made
 * when the answer is committed — so the rule must be visible before then. Two backend facts give
 * it without guessing:
 *
 *   * `evidence.inspect` (L1) lists the assist events (`hint_request` / `answer_shown`) that have
 *     not been consumed by an attempt yet (`attempt_id = null`). The newest one names the class
 *     the next answer inherits, exactly as `lesson.assist` states in its own response and exactly
 *     as `coursebook/domain.py::_classify_evidence` reads it.
 *   * `check.get` reports `attempt_count`. A second committed answer to the same check follows
 *     feedback, so the backend classifies it at least `hinted`
 *     (`docs/CONTRACTS.md` §lesson.assist; `_classify_evidence`).
 *
 * When neither fact exists the attempt really is `cold`: no hint, no shown answer, no prior
 * attempt on this check. A build without either read prints no pending class rather than assuming.
 */
function usePendingEvidence({ enrollmentId, objectiveId, revision, enabled, implemented, refreshKey }) {
  const [pending, setPending] = useState(null)
  const canInspect = Boolean(implemented && implemented.has('evidence.inspect'))
  useEffect(() => {
    if (!enabled || !enrollmentId || !objectiveId || !canInspect) {
      setPending(null)
      return undefined
    }
    let cancelled = false
    rpc('evidence.inspect', { enrollment_id: enrollmentId, objective_id: objectiveId })
      .then((response) => {
        if (cancelled) return
        if (!response || !response.ok) {
          setPending(null)
          return
        }
        const events = (response.result && response.result.l1 && response.result.l1.events) || []
        // Newest first (h-178: `evidence.layer1` orders by created_at DESC, rowid DESC). Only an
        // unconsumed assist event changes the class of the next answer.
        const open = events.find(
          (event) =>
            event &&
            event.attempt_id === null &&
            (event.kind === 'hint_request' || event.kind === 'answer_shown')
        )
        setPending(open ? open.evidence_class || (open.kind === 'answer_shown' ? 'answer_shown' : 'hinted') : null)
      })
      .catch(() => {
        // A read-only lane probe never replaces the surface's real state.
      })
    return () => {
      cancelled = true
    }
  }, [enrollmentId, objectiveId, revision, enabled, canInspect, refreshKey])
  return pending
}

/**
 * The answer object sent to `attempt.submit`.
 *
 * `text` carries the written answer (contract max 8000). `selection` is the closed-form channel and
 * the contract caps every item at 200 characters, so a long written answer must not be copied into
 * it — a 400-character sentence was rejected as VALIDATION_FAILED before grading ever ran. Short
 * answers still travel on both channels, because a closed-form check may grade on either field.
 */
const SELECTION_MAX_CHARS = 200
function attemptAnswer(answer) {
  const payload = { kind: 'text', text: answer }
  if (answer.length <= SELECTION_MAX_CHARS) payload.selection = [answer]
  return payload
}

/**
 * The answer object for a selected choice.
 *
 * A selection check stores its accepted forms in the closed-form lane, and a matching check may
 * declare a `selection` reference. The learner picked an authored choice, so the answer is a
 * selection; the chosen text also travels on `text` so a check graded over accepted forms reads the
 * same pick. Both fields are declared by `attempt.submit`'s own answer schema.
 */
function choiceAnswer(choice) {
  const text = String(choice == null ? '' : choice).slice(0, 8000)
  return { kind: 'selection', selection: [text.slice(0, SELECTION_MAX_CHARS)], text }
}

/**
 * The graded half of a check, as a pure component so a Node test can render it without a backend.
 *
 * A `self_reported` pass never renders the generic "Passed" label: it renders the frozen §9.4
 * sentence, which is the only claim the learner actually made. A checklist result shows the
 * returned `criteria[]` against the served items (id → label, `met` → ticked/not) and a `partial`
 * keeps the check open by inviting the remaining steps.
 */
function AttemptVerdict({ result, criteria, checklist, onResumeChecklist, onNewExample, onExplain }) {
  const selfReported = Boolean(result && result.evidence_class === 'self_reported')
  const confirmed = (checklist || []).map((item) => {
    const match = (criteria || []).find((criterion) => criterion && criterion.id === item.id)
    return { id: item.id, label: item.label, met: Boolean(match && match.met) }
  })
  const confirmedCount = confirmed.filter((item) => item.met).length
  const selfReportedPass = selfReported && result.verdict === 'pass'
  const takeaway = verdictTakeaway(result, criteria)
  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-verdict': result.verdict,
    'data-cb-evidence-class': result.evidence_class || null,
    children: [
      jsx(EvidenceChip, { value: result.evidence_class || null }),
      selfReportedPass
        ? jsx('strong', {
            className: 'max-w-prose text-sm font-medium',
            'data-cb-self-reported': 'confirmation',
            children: SELF_REPORTED_CONFIRM_COPY
          })
        : jsx('div', { className: 'text-sm font-medium', children: verdictLabel(result.verdict, result.evidence_class) }),

      takeaway
        ? jsx('div', {
            className: 'max-w-prose text-sm leading-relaxed',
            'data-cb-takeaway': '',
            children: takeaway
          })
        : null,

      confirmed.length > 0
        ? jsxs('div', {
            className: 'flex flex-col gap-1',
            'data-cb-check-criteria': String(confirmed.length),
            children: [
              jsx(CbLabel, { children: 'Steps you confirmed' }),
              jsx('ul', {
                className: 'flex flex-col gap-1.5',
                children: confirmed.map((item, index) =>
                  jsxs(
                    'li',
                    {
                      className: 'flex items-start gap-2',
                      'data-cb-criterion': item.id,
                      'data-cb-criterion-met': item.met ? 'true' : 'false',
                      children: [
                        jsx(sdk.Checkbox, {
                          checked: item.met,
                          disabled: true,
                          id: `cb-result-item-${index}`,
                          'aria-label': `${item.met ? 'Confirmed' : 'Not confirmed'}: ${item.label}`
                        }),
                        jsx('label', {
                          className: 'text-sm leading-snug',
                          htmlFor: `cb-result-item-${index}`,
                          children: item.label
                        }),
                        jsx('span', {
                          className: 'ml-auto text-xs text-(--ui-text-secondary)',
                          children: item.met ? 'Confirmed' : 'Not confirmed'
                        })
                      ]
                    },
                    item.id
                  )
                )
              })
            ]
          })
        : criteria.length > 0
          ? jsx('ul', {
              className: 'flex flex-col gap-1',
              children: criteria.map((item, index) =>
                jsxs(
                  'li',
                  {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: [
                      jsx(sdk.Codicon, { name: item.met ? 'pass' : 'circle-slash', size: CB_ICON_UI }),
                      jsx('span', { className: 'ml-1', children: item.observed || item.id })
                    ]
                  },
                  `${item.id || 'criterion'}-${index}`
                )
              )
            })
          : jsx(QuietNote, { children: 'No criterion detail was returned for this verdict.' }),

      confirmed.length > 0 && !selfReportedPass
        ? jsx(QuietNote, {
            children: `You confirmed ${confirmedCount} of ${confirmed.length} steps. Tick the remaining steps and submit again; this stays your own report, not an independent check.`
          })
        : null,

      jsx(QuietNote, { children: nextActionCopy(result) }),

      selfReportedPass
        ? null
        : jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              confirmed.length > 0
                ? jsx(CbAction, {
                    variant: 'primary',
                    onClick: onResumeChecklist,
                    children: 'Tick the remaining steps'
                  })
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: onNewExample,
                    children: 'Try a new example'
                  }),
              confirmed.length > 0
                ? null
                : jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: onExplain, children: 'Explain the difference' })
            ]
          })
    ]
  })
}

/**
 * The parent-observation lane (cb.rpc v14, `observation.record`).
 *
 * `docs/CHECKLIST-CONFIRMATION.md` §6 draws the boundary: a parent-recipe objective is observed by
 * the adult, never ticked or answered by the child, so the observation is the only recording path
 * for that objective. The write is one layer-1 evidence row — no attempt, no check state, no
 * verdict, no objective transition — and the response `revision` is the enrollment revision echoed
 * unchanged, so nothing here may be rendered as a pass, a grade or a completed objective.
 *
 * The note bound is the contract's own (`maxLength: 1000`). The schema refuses 1001 rather than
 * truncating, so the control bounds the field and the call refuses before the wire, never slicing
 * a parent's words.
 */
const OBSERVATION_NOTE_MAX = 1000
const PARENT_OBSERVATION_CLASS = 'parent_reported'

/** The exact `observation.record` payload. An absent note travels as `null`, never `''`. */
function parentObservationPayload({ enrollmentId, objectiveId, note }) {
  const trimmed = String(note === undefined || note === null ? '' : note).trim()
  return {
    enrollment_id: enrollmentId,
    objective_id: objectiveId,
    evidence_class: PARENT_OBSERVATION_CLASS,
    note: trimmed ? trimmed : null
  }
}

/**
 * The envelope key for one submission.
 *
 * `idempotency_key` lives at the envelope root and is required, so a double click cannot mint two
 * evidence rows. The caller mints one key per distinct payload and reuses it on retry; a new key on
 * a retry of the same payload would record a second observation.
 */
function parentObservationKey({ enrollmentId, objectiveId, nonce }) {
  return `cb-observation-${enrollmentId}-${objectiveId}-${nonce}`
}

/** What identifies one submission: the same ids and the same note are the same write. */
function observationSignature({ enrollmentId, objectiveId, note }) {
  const trimmed = String(note === undefined || note === null ? '' : note).trim()
  return `${enrollmentId}|${objectiveId}|${trimmed}`
}

/**
 * The submission on screen, and its key.
 *
 * An unchanged payload keeps the key it already sent, so a retry of a failed or duplicated call
 * replays the stored observation instead of recording a second one. A changed note is a different
 * observation and gets its own key. Pure, with the nonce injected, so the rule is asserted directly.
 */
function nextObservationSubmission(previous, { enrollmentId, objectiveId, note, nonce }) {
  const signature = observationSignature({ enrollmentId, objectiveId, note })
  if (previous && previous.signature === signature) return previous
  return {
    signature,
    key: parentObservationKey({ enrollmentId, objectiveId, nonce: nonce || newOperationId('observation') })
  }
}

/**
 * One parent observation, over an injected transport so a test can prove the envelope.
 *
 * `call` is the rpc transport (`rpc` in the app). No `expected_revision` is sent: v14 declares no
 * fence for this method and the append moves no aggregate.
 */
async function recordParentObservation({ call, key, enrollmentId, objectiveId, note }) {
  const payload = parentObservationPayload({ enrollmentId, objectiveId, note })
  if (payload.note !== null && payload.note.length > OBSERVATION_NOTE_MAX) {
    return {
      ok: false,
      stage: 'note_too_long',
      error: {
        code: 'VALIDATION_FAILED',
        message: `A note is at most ${OBSERVATION_NOTE_MAX} characters. Nothing was recorded.`
      }
    }
  }
  return call('observation.record', payload, { idempotencyKey: key, expectedRevision: null })
}

/** The recorded state. Reuses `EvidenceClassText`, so no second badge language is invented. */
function ParentObservationRecorded({ result, nodeRef }) {
  const evidenceId = result && result.evidence_id
  return jsxs('div', {
    className: 'flex flex-col gap-1',
    role: 'status',
    tabIndex: -1,
    ref: nodeRef,
    'data-cb-parent-observation-recorded': evidenceId || 'recorded',
    children: [
      jsx(EvidenceClassText, { value: (result && result.evidence_class) || PARENT_OBSERVATION_CLASS }),
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Recorded. This is a parent report: it is not independent evidence, it is not a pass or a grade, and it does not complete this objective.'
      }),
      evidenceId
        ? jsx('p', { className: 'text-xs text-(--ui-text-secondary)', children: `Observation ${evidenceId}` })
        : null
    ]
  })
}

/**
 * Record what the parent saw. Keyboard-first: a labelled textarea, a labelled button, the error
 * inline and the control left enabled, and the recorded state announced (`role="status"`, focus
 * moved to it) instead of silently swapping the form.
 *
 * The submission ref holds the key of the payload on screen. Retrying an unchanged note re-sends
 * the SAME key (the backend replays the stored evidence); editing the note is a different payload
 * and mints a new key; a success clears it so the next observation is a new write.
 */
function ParentObservation({ enrollmentId, objectiveId, onRecorded }) {
  const [note, setNote] = useState('')
  const [phase, setPhase] = useState('editing')
  const [recorded, setRecorded] = useState(null)
  const [error, setError] = useState(null)
  const submissionRef = useRef(null)
  const statusRef = useRef(null)
  const trimmed = note.trim()
  const overLimit = trimmed.length > OBSERVATION_NOTE_MAX

  useEffect(() => {
    if (phase === 'recorded') statusRef.current?.focus({ preventScroll: true })
  }, [phase])

  const submission = useCallback(
    () =>
      nextObservationSubmission(submissionRef.current, {
        enrollmentId,
        objectiveId,
        note: trimmed
      }),
    [enrollmentId, objectiveId, trimmed]
  )

  const submit = useCallback(async () => {
    if (!enrollmentId || !objectiveId) return
    if (trimmed.length > OBSERVATION_NOTE_MAX) {
      setError({
        code: 'VALIDATION_FAILED',
        message: `A note is at most ${OBSERVATION_NOTE_MAX} characters. Nothing was recorded.`
      })
      return
    }
    const current = submission()
    submissionRef.current = current
    setPhase('saving')
    setError(null)
    const response = await recordParentObservation({
      call: rpc,
      key: current.key,
      enrollmentId,
      objectiveId,
      note: trimmed
    })
    if (!response || !response.ok) {
      // The control stays exactly as it was: the note is still in the field and Retry re-sends the
      // same key, so an offline call is recoverable rather than a lost observation.
      setError((response && response.error) || { code: 'INTERNAL_ERROR', message: 'No contract envelope was returned.' })
      setPhase('failed')
      return
    }
    setRecorded(response.result || null)
    setPhase('recorded')
    submissionRef.current = null
    if (onRecorded) onRecorded(response.result, response)
  }, [enrollmentId, objectiveId, trimmed, submission, onRecorded])

  const recordAgain = () => {
    setRecorded(null)
    setError(null)
    setNote('')
    setPhase('editing')
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-parent-observation': objectiveId || 'objective',
    children: [
      jsx(CbLabel, { children: 'Parent observation' }),
      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'Record what you saw your child do. It is stored as a parent report — not independent evidence — and it does not grade, pass or complete the objective.'
      }),
      recorded
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx(ParentObservationRecorded, { result: recorded, nodeRef: statusRef }),
              jsx('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: jsx(sdk.Button, {
                  variant: 'secondary',
                  size: 'sm',
                  onClick: recordAgain,
                  children: 'Record another observation'
                })
              })
            ]
          })
        : jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('label', {
                className: 'text-xs font-medium text-(--ui-text-secondary)',
                htmlFor: 'cb-observation-note',
                children: 'What did you observe? (optional note)'
              }),
              jsx(sdk.Textarea, {
                id: 'cb-observation-note',
                'aria-describedby': 'cb-observation-help',
                'aria-invalid': overLimit ? 'true' : undefined,
                disabled: phase === 'saving',
                maxLength: OBSERVATION_NOTE_MAX,
                onChange: (event) => setNote(event.target.value),
                placeholder: 'For example: set the table and lit the candle without being asked.',
                rows: 3,
                value: note
              }),
              jsx('p', {
                id: 'cb-observation-help',
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `Optional, up to ${OBSERVATION_NOTE_MAX} characters. ${trimmed.length}/${OBSERVATION_NOTE_MAX}`
              }),
              error ? jsx(ErrorLine, { error }) : null,
              jsx('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: jsx(CbAction, {
                  variant: 'primary',
                  disabled: phase === 'saving' || overLimit,
                  onClick: submit,
                  children: phase === 'saving' ? 'Recording…' : error ? 'Try again' : 'Record observation'
                })
              })
            ]
          })
    ]
  })
}

/**
 * A bounded conversation practice, rendered from the backend's own projection.
 *
 * `docs/CONVERSATION-PRACTICE.md` §5, §7.4 and §9 are the whole contract here:
 *
 * - the declaration comes from `check.get` → `stimulus.practice`, the projection that already
 *   withholds a target label the learner was not shown. This surface never prints a label unless
 *   `targets_visible` is true, even if one arrives in the payload;
 * - the transcript, the turn counter, the attempt id, the verdict and the criteria come from
 *   `practice.state` / `practice.end`. Nothing is graded in the pane: End practice is the only
 *   path, and a plain `attempt.submit` is refused by the backend (`practice_requires_practice_end`);
 * - the feedback is one compact line (§7.4) and the full criteria sit behind Review grading. No
 *   score, percentage or verdict is rendered unless the backend returned that value. A verdict the
 *   backend returns is printed as it is: the pane does not re-word `partial` or `not_yet`.
 * - every envelope is built by `rpc`, so the version echo is the `/runtime` one the branch
 *   declares, not a literal.
 */
const PRACTICE_UNSUPPORTED_COPY =
  'This Desktop build cannot run a conversation practice: the backend does not implement practice.state. The section and its lesson chat still work; this card stays read-only.'
const PRACTICE_START_COPY =
  'Practice runs in the lesson chat. Start it here, answer the tutor there, then end it here to grade your own turns. Nothing the tutor says is graded.'

/**
 * What a learner reads when `practice.end` or `practice.cancel` refuses.
 *
 * `docs/CONVERSATION-PRACTICE.md` §5.4 and §8 name each refusal, and each one leaves the practice
 * exactly where it was: the transcript, the session and the check are all kept. The copy says that
 * and gives the one next move, so a refusal never reads as a lost practice.
 */
function practiceRefusalCopy(error, options = {}) {
  const reason = error && error.details ? error.details.reason : null
  const details = (error && error.details) || {}
  if (reason === 'practice_not_complete') {
    const low = details.min_turns
    const held = details.learner_turns
    const need = Number.isFinite(Number(low)) ? `${low} learner turns` : 'the declared minimum of learner turns'
    const have = Number.isFinite(Number(held)) ? `${held} ${Number(held) === 1 ? 'is' : 'are'} recorded` : 'fewer are recorded'
    return `This practice needs at least ${need}; ${have}. Answer the tutor in the lesson chat, then press End practice again. Every turn is kept.`
  }
  if (reason === 'practice_empty_transcript') {
    return 'No learner turn is recorded yet. Answer the tutor in the lesson chat, then end the practice. The check is still open.'
  }
  if (reason === 'practice_not_open') {
    // On a card that already shows a graded result, "press Start practice" would be an instruction
    // the backend refuses. Say the practice is graded instead.
    if (options.graded) {
      return 'This practice is already graded, so there is no live practice to open or end here. Review grading shows the result the backend stored.'
    }
    return 'There is no live practice to end. Press Start practice; the check is still open and every stored turn is kept.'
  }
  if (reason === 'practice_already_graded') {
    return 'This practice was already graded. Review grading shows the result the backend stored.'
  }
  if (error && error.code === 'STALE_REVISION') {
    return 'The section moved on before this practice could be saved (another attempt or a refresh committed it). Reopen the section to practise against the current version; every stored turn is kept.'
  }
  return null
}

/**
 * The one compact feedback line (§7.4).
 * It repeats the verdict the backend returned and two counts it also returned: target criteria met
 * and learner turns. It never computes a percentage and never turns `partial`/`not_yet` into
 * different words. `needs_retry` is the system's failure, so the line says what happened to the
 * transcript rather than reading as a learner outcome.
 */
function practiceFeedback({ verdict, criteria, learnerTurns, targets }) {
  if (!verdict) return null
  const label = verdictLabel(verdict, null)
  const turns = Number(learnerTurns) || 0
  const turnText = `${turns} learner ${turns === 1 ? 'turn' : 'turns'}`
  if (verdict === 'needs_retry') {
    return `${label}: the transcript is saved, nothing advanced, and no verdict was recorded.`
  }
  const ids = new Set((targets || []).map((target) => String(target.id)))
  const rows = (criteria || []).filter((item) => item && ids.has(String(item.id)))
  const total = ids.size || rows.length
  if (total === 0) return `${label}: over ${turnText}.`
  const met = rows.filter((item) => item.met).length
  return `${label}: ${met} of ${total} target ${total === 1 ? 'expression' : 'expressions'} used, over ${turnText}.`
}

function PracticeSurface({
  enrollmentId,
  objectiveId,
  check,
  revision,
  implemented,
  bindingState,
  onCommitted
}) {
  const practice = check && check.stimulus && check.stimulus.practice ? check.stimulus.practice : {}
  const declaration = practice || {}
  const turnRange = declaration.turns || {}
  const minTurns = Number(turnRange.min) || 0
  const maxTurns = Number(turnRange.max) || 0
  const targets = Array.isArray(declaration.targets)
    ? declaration.targets.filter((target) => target && target.id)
    : []
  const labelsVisible = declaration.targets_visible === true
  const [capabilities, setCapabilities] = useState(implemented || null)
  const known = capabilities instanceof Set ? capabilities : null
  const supports = (method) => (known ? known.has(method) : true)
  const canState = supports('practice.state')
  const detached = Boolean(bindingState && bindingState !== 'active')
  const [state, setState] = useState({ status: canState ? 'loading' : 'unsupported', session: null, error: null })
  const [phase, setPhase] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [criteriaOpen, setCriteriaOpen] = useState(false)
  const [ticket, setTicket] = useState(0)
  // The `revision` prop is the section page's revision captured when this card mounted. A graded
  // end commits the attempt and the backend answers with the *new* enrollment revision, while this
  // card deliberately stays on screen so the learner reads the verdict. Fencing the next write on
  // the mount-time prop therefore refuses the learner's own retry (`STALE_REVISION`) although
  // `docs/CONVERSATION-PRACTICE.md` §5.1 allows a `not_yet` / `partial` practice again. This local
  // fence is seeded from the prop, raised by every answer that carries `revision`, and never
  // lowered: revisions only move forward.
  const [fencedRevision, setFencedRevision] = useState(() => Number(revision) || 0)
  const adoptRevision = (value) => {
    const next = Number(value)
    if (Number.isFinite(next) && next > 0) setFencedRevision((current) => Math.max(current, next))
  }
  useEffect(() => {
    adoptRevision(revision)
  }, [revision])
  const nonceRef = useRef(null)
  const feedbackRef = useRef(null)

  useEffect(() => {
    if (!canState) {
      setState((previous) => (previous.status === 'unsupported' ? previous : { status: 'unsupported', session: null, error: null }))
      return undefined
    }
    let cancelled = false
    setState((previous) => ({ ...previous, status: previous.session ? previous.status : 'loading', error: null }))
    rpc('practice.state', { enrollment_id: enrollmentId, objective_id: objectiveId })
      .then((response) => {
        if (cancelled) return
        if (!response || !response.ok) {
          setState({ status: 'unavailable', session: null, error: (response && response.error) || null })
          return
        }
        setState({ status: 'ready', session: response.result || null, error: null })
      })
      .catch((failure) => {
        if (!cancelled) {
          setState({
            status: 'unavailable',
            session: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(failure) }
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [enrollmentId, objectiveId, canState, ticket, check && check.check_id])

  const reload = () => setTicket((value) => value + 1)

  // A practice turn is written by the chat hook, not by this surface. Coming back to the pane
  // refreshes the read; there is no timer and nothing that could steal focus from the chat.
  const liveRef = useRef(false)
  const session = state.session
  const sessionState = session && session.state ? session.state : 'none'
  liveRef.current = sessionState === 'active'
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.addEventListener !== 'function') return undefined
    const refresh = () => {
      if (liveRef.current) reload()
    }
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [])

  const verdict = result && result.verdict ? result.verdict : session ? session.verdict : null
  const criteria =
    result && Array.isArray(result.criteria)
      ? result.criteria
      : session && Array.isArray(session.criteria)
        ? session.criteria
        : []
  const learnerTurns =
    result && Number.isFinite(Number(result.learner_turns))
      ? Number(result.learner_turns)
      : session
        ? Number(session.learner_turns) || 0
        : 0
  const transcript = session && Array.isArray(session.transcript) ? session.transcript : []
  const remaining = session && Number.isFinite(Number(session.remaining)) ? Number(session.remaining) : null
  const feedback = practiceFeedback({ verdict, criteria, learnerTurns, targets })

  // A verdict is the moment the learner waited for: put focus on the line that states it rather
  // than leaving a keyboard user on a button that just disappeared.
  useEffect(() => {
    if (verdict && feedbackRef.current) feedbackRef.current.focus({ preventScroll: true })
  }, [verdict])

  const refreshCapabilities = async () => {
    const wire = await reloadBackendWire()
    setCapabilities(wire && wire.implemented ? wire.implemented : null)
    reload()
  }

  const start = async () => {
    setPhase('starting')
    setError(null)
    setNotice(null)
    const response = await rpc(
      'practice.start',
      { enrollment_id: enrollmentId, objective_id: objectiveId },
      {
        idempotencyKey: `cb-practice-start-${check.check_id}-${newOperationId('practice-start')}`,
        expectedRevision: fencedRevision
      }
    )
    setPhase('idle')
    if (!response.ok) {
      // A stale fence names the revision the backend expects next: adopt it so the learner's
      // second press on the same graded card is not refused a second time for the same reason.
      adoptRevision(staleRevision(response))
      setError(response.error)
      return
    }
    adoptRevision(response.result && response.result.revision)
    nonceRef.current = null
    // The graded line belongs to the attempt that just closed; a started session owns the card now,
    // so it is dropped only once the backend has confirmed the start.
    setResult(null)
    setNotice('Practice started. Answer the tutor in the lesson chat; opening this card again shows the turns it stored.')
    reload()
  }

  const end = async () => {
    if (!session) return
    if (!nonceRef.current) nonceRef.current = newOperationId('practice-end')
    setPhase('ending')
    setError(null)
    setNotice(null)
    const response = await rpc(
      'practice.end',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current
      },
      {
        idempotencyKey: `cb-practice-end-${check.check_id}-${nonceRef.current}`,
        expectedRevision: fencedRevision
      }
    )
    setPhase('idle')
    if (!response.ok) {
      // A refusal before the minimum is not a lost practice: the transcript, the session and the
      // check all stay where they are, so the same End practice can be pressed again.
      adoptRevision(staleRevision(response))
      setError(response.error)
      return
    }
    adoptRevision(response.result && response.result.revision)
    nonceRef.current = null
    setResult(response.result)
    // The graded line stays on screen: the check closes with the attempt, and a parent refresh
    // would unmount this card before the learner read the verdict. Everything outside refreshes
    // the next time the section is opened.
  }

  const cancel = async () => {
    setCancelOpen(false)
    setPhase('cancelling')
    setError(null)
    setNotice(null)
    const response = await rpc(
      'practice.cancel',
      { enrollment_id: enrollmentId, check_id: check.check_id },
      { expectedRevision: fencedRevision }
    )
    setPhase('idle')
    if (!response.ok) {
      adoptRevision(staleRevision(response))
      setError(response.error)
      return
    }
    adoptRevision(response.result && response.result.revision)
    nonceRef.current = null
    setNotice('Practice cancelled. Every turn is kept, nothing was graded, and the check stayed open.')
    reload()
  }

  const busy = phase !== 'idle'
  const targetBlock = labelsVisible
    ? targets.some((target) => target.label)
      ? jsxs('div', {
          className: 'flex flex-col gap-1',
          'data-cb-practice-targets-list': String(targets.length),
          children: [
            jsx(CbLabel, { children: CB3_CLASSROOM_COPY.practiceExpressions }),
            jsx('ul', {
              className: 'flex flex-col gap-1 text-sm leading-snug',
              'aria-label': CB3_CLASSROOM_COPY.practiceExpressions,
              children: targets
                .filter((target) => target.label)
                .map((target) =>
                  jsx('li', { 'data-cb-practice-target': target.id, children: target.label }, target.id)
                )
            })
          ]
        })
      : null
    : jsx(QuietNote, {
        children:
          'The target expressions are not shown for this practice. Produce them from what you know; the tutor will not list them either.'
      })

  const stateBlock =
    state.status === 'unsupported'
      ? jsxs('div', {
          className: 'flex flex-col gap-2',
          'data-cb-practice-state-block': 'unsupported',
          children: [
            jsx(QuietNote, { children: PRACTICE_UNSUPPORTED_COPY }),
            jsx(sdk.Button, {
              variant: 'secondary',
              size: 'sm',
              className: 'self-start',
              onClick: refreshCapabilities,
              children: 'Re-read the backend'
            })
          ]
        })
      : state.status === 'unavailable'
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-practice-state-block': 'unavailable',
            children: [
              jsx(sdk.ErrorState, {
                title: 'This practice could not be read',
                description: state.error
                  ? `The backend refused practice.state (${state.error.code || 'ERROR'}). The check and its chat are unchanged.`
                  : 'The backend returned no practice state. The check and its chat are unchanged.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                className: 'self-start',
                onClick: reload,
                children: 'Retry'
              })
            ]
          })
        : state.status === 'loading' && !session
          ? jsxs('div', {
              className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
              'data-cb-practice-state-block': 'loading',
              children: [jsx(sdk.Loader, { label: 'Reading the practice' }), jsx('span', { children: 'No control is offered until the stored transcript is here.' })]
            })
          : null

  const transcriptBlock =
    transcript.length > 0
      ? jsxs('div', {
          className: 'flex flex-col gap-1',
          'data-cb-practice-transcript': String(transcript.length),
          children: [
            jsx(CbLabel, { children: 'Transcript' }),
            jsx('ol', {
              className: 'flex flex-col gap-1.5',
              'aria-label': CB3_CLASSROOM_COPY.practiceTranscript,
              children: transcript.map((turn) =>
                jsxs(
                  'li',
                  {
                    className: 'flex flex-col gap-0.5',
                    'data-cb-practice-turn': turn.ordinal,
                    'data-cb-practice-speaker': turn.speaker,
                    children: [
                      jsx('span', {
                        className: 'text-xs font-medium text-(--ui-text-secondary)',
                        children: turn.speaker === 'learner' ? 'You' : 'Tutor'
                      }),
                      jsx('span', { className: 'text-sm leading-snug', children: turn.text })
                    ]
                  },
                  turn.ordinal
                )
              )
            })
          ]
        })
      : null

  const blendedState = result && result.verdict ? 'graded' : sessionState

  // The counter follows the card's own state, not the stored session: on a just-graded card the
  // stored session is still `active`, which would read "waiting for the tutor to reply" underneath
  // a verdict.
  const counterBlock =
    session && (blendedState === 'active' || blendedState === 'graded') && maxTurns > 0
      ? jsx('p', {
          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
          'data-cb-practice-counter': blendedState,
          children:
            blendedState === 'active'
              ? remaining === 0
                ? `Turn limit reached (${learnerTurns} of ${maxTurns} learner turns). End practice to grade the transcript.`
                : `${learnerTurns} of ${maxTurns} learner turns used${
                    session.awaiting_tutor ? '; waiting for the tutor to reply.' : `. ${remaining} left before the limit.`
                  }`
              : `Graded after ${learnerTurns} of at most ${maxTurns} learner turns.`
        })
      : null

  // A `pass` closes the check (`_commit_attempt`): there is nothing left to practise against on this
  // section, so the pane must not offer a button the backend will refuse with `practice_not_open`.
  // A `partial` / `not_yet` / `needs_retry` verdict leaves the check open and keeps the retry.
  const checkClosed = verdict === 'pass'
  // One computed refusal: a graded card gets graded words, an open one gets the retry words.
  const refusalCopy = error ? practiceRefusalCopy(error, { graded: Boolean(verdict) }) : null
  const controls =
    state.status !== 'ready'
      ? null
      : blendedState === 'active'
        ? jsxs('div', {
            className: 'flex flex-wrap items-center gap-2',
            children: [
              jsx(CbAction, {
                variant: 'primary',
                disabled: busy || detached,
                onClick: end,
                children: phase === 'ending' ? 'Ending practice' : 'End practice'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                disabled: busy || detached,
                onClick: () => setCancelOpen(true),
                children: 'Cancel practice'
              }),
              jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                disabled: busy,
                onClick: reload,
                children: 'Refresh transcript'
              })
            ]
          })
        : blendedState === 'none' || blendedState === 'cancelled' || blendedState === 'abandoned' || blendedState === 'graded'
          ? jsxs('div', {
              className: 'flex flex-wrap items-center gap-2',
              children: [
                checkClosed
                  ? null
                  : jsx(CbAction, {
                      variant: 'primary',
                      disabled: busy || detached,
                      onClick: start,
                      children:
                        phase === 'starting'
                          ? 'Starting practice'
                          : sessionState === 'none'
                            ? 'Start practice'
                            : 'Practice again'
                    }),
                verdict
                  ? jsx(sdk.Button, {
                      variant: 'text',
                      size: 'sm',
                      'aria-expanded': criteriaOpen ? 'true' : 'false',
                      onClick: () => setCriteriaOpen((open) => !open),
                      children: criteriaOpen ? 'Hide grading' : 'Review grading'
                    })
                  : null
              ]
            })
          : null

  const endOfSessionBlock =
    checkClosed && blendedState === 'graded'
      ? jsx(QuietNote, {
          children:
            'This section is finished: the pass closed its practice check, so there is nothing left to practise or grade here. Every stored turn stays readable, and Review grading shows what the backend recorded.'
        })
      : sessionState === 'cancelled'
        ? jsx(QuietNote, {
            children: 'Practice cancelled. Every turn is kept, nothing was graded, and the check is still open.'
          })
        : sessionState === 'abandoned'
          ? jsx(QuietNote, {
            children:
              'This practice ended when its lesson chat detached or its run paused, so it cannot be graded from here. Start a new practice on a connected lesson.'
          })
        : null

  const criteriaBlock =
    criteriaOpen && verdict
      ? jsxs('div', {
          className: 'flex flex-col gap-1',
          'data-cb-practice-criteria': String(criteria.length),
          children: [
            jsx(CbLabel, { children: CB3_CLASSROOM_COPY.checkCriteria }),
            criteria.length > 0
              ? jsx('ul', {
                  className: 'flex flex-col gap-1',
                  'aria-label': CB3_CLASSROOM_COPY.checkCriteria,
                  children: criteria.map((item, index) =>
                    jsxs(
                      'li',
                      {
                        className: 'flex items-start gap-2 text-sm leading-snug',
                        'data-cb-practice-criterion': item.id,
                        'data-cb-practice-criterion-met': item.met ? 'true' : 'false',
                        children: [
                          jsx('span', {
                            'aria-hidden': 'true',
                            className: 'text-(--ui-text-secondary)',
                            children: item.met ? '✓' : '·'
                          }),
                          jsx('span', {
                            children: item.observed ? String(item.observed) : item.met ? 'met' : 'not met'
                          })
                        ]
                      },
                      String(item.id || index)
                    )
                  )
                })
              : jsx(QuietNote, { children: 'The backend returned no criteria for this attempt.' })
          ]
        })
      : null

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    'data-cb-practice': check.check_id,
    'data-cb-practice-state': state.status === 'ready' ? blendedState : state.status,
    'data-cb-practice-targets': labelsVisible ? 'visible' : 'hidden',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `Check v${check.check_version}` }),
          jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: 'Conversation practice' })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col gap-1',
        'data-cb-practice-scenario': check.check_id,
        children: [
          jsx(CbLabel, { children: 'Scene' }),
          jsx('p', {
            className: 'max-w-prose text-sm leading-relaxed',
            children: declaration.scenario || 'No scenario was declared for this practice.'
          }),
          declaration.learner_role || declaration.tutor_role
            ? jsx('p', {
                className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
                children: `You are ${declaration.learner_role || 'the learner'}; the tutor plays ${
                  declaration.tutor_role || 'the other speaker'
                }. ${minTurns} to ${maxTurns} learner turns.`
              })
            : null
        ]
      }),

      targetBlock,

      sessionState === 'none' && declaration.opening
        ? jsx(QuietNote, { children: `The tutor opens with: “${declaration.opening}”` })
        : null,

      sessionState === 'none' ? jsx(QuietNote, { children: PRACTICE_START_COPY }) : null,

      stateBlock,
      counterBlock,
      transcriptBlock,
      controls,
      endOfSessionBlock,

      feedback
        ? jsx('p', {
            className: 'max-w-prose text-sm font-medium leading-relaxed outline-none',
            ref: feedbackRef,
            role: 'status',
            tabIndex: -1,
            'data-cb-practice-feedback': verdict,
            children: feedback
          })
        : null,

      criteriaBlock,

      notice
        ? jsx('p', { className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)', role: 'status', children: notice })
        : null,

      error && refusalCopy
        ? jsx('p', {
            className: 'max-w-prose text-sm leading-relaxed',
            role: 'status',
            'data-cb-practice-refusal': (error.details && error.details.reason) || 'refused',
            children: refusalCopy
          })
        : null,

      // A learner-facing refusal carries its own words; the raw wire code is only shown when the
      // pane has nothing better to say, so a card never reads `CHECK_STALE: ...` at a learner.
      error && !refusalCopy ? jsx(ErrorLine, { error }) : null,

      jsx(FocusReturningDialog, {
        open: cancelOpen,
        title: 'Cancel this practice?',
        description:
          'Every turn you typed is kept, nothing is graded, and the check stays open. You can start another practice on this section afterwards.',
        confirmLabel: 'Cancel practice',
        destructive: true,
        onClose: () => setCancelOpen(false),
        onConfirm: cancel,
        children: null
      })
    ]
  })
}

/**
 * H-206 · the used state of an assist control.
 *
 * A statement, never a button: once the backend has recorded that help was used for this attempt,
 * the control stops being pressable and says so. The dot is a state marker, not a pass mark — the
 * evidence chip next to it carries the verdict and the sentence.
 */
function AssistUsedFlag({ kind, children }) {
  return jsxs('span', {
    'data-cb-assist-used': kind,
    role: 'status',
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.35rem',
      padding: '0.2rem 0.5rem',
      border: '1px solid var(--cb-rule)',
      background: 'var(--cb-lamp-soft)',
      color: 'var(--cb-ink)',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      lineHeight: 1.35,
      boxSizing: 'border-box'
    },
    children: [
      jsx('span', { 'aria-hidden': 'true', style: { color: 'var(--cb-ochre)' }, children: '•' }),
      jsx('span', { children })
    ]
  })
}

/**
 * One attempt, started and finished in the pane or on the lesson page.
 *
 * Idempotency is enrollment + check + a per-view nonce: retrying a failed grade re-sends the SAME
 * nonce, so the backend returns the stored attempt instead of writing a second one. A written
 * answer carries both `text` and a one-element `selection`; a checklist answer carries only
 * `kind: "selection"` with the ticked item ids.
 */
function AttemptControls({
  enrollmentId,
  objectiveId,
  check,
  revision,
  implemented,
  bindingState,
  onCommitted,
  parentLed = false,
  stimulusStatus = null,
  stimulusError = null,
  onRetryStimulus = null,
  playerMode = false,
  playerController = null,
  onPlayerState = null
}) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'
  const [text, setText] = useState('')
  const [ticked, setTicked] = useState([])
  // H-178: a selection check is answered by picking an authored choice, not by typing its text.
  // The index is the only local answer state; the value that travels to `attempt.submit` is the
  // served choice string, never a label the pane invented.
  const [selected, setSelected] = useState(-1)
  const [assistClass, setAssistClass] = useState(null)
  // H-206: the pressed control shows what it is recording, then leaves. `assistPending` is the one
  // kind in flight; `assistBusy` stays the guard every other branch already reads.
  const [assistPending, setAssistPending] = useState(null)
  // H-206/W2-4: the two hint controls write the same event but mean different things, so the
  // in-flight label names the one that was pressed ("Asking…" vs "Recording…").
  const [assistIntent, setAssistIntent] = useState(null)
  const assistBusy = assistPending !== null
  // U2: "I saw the answer" is one-way. It changes what this attempt can ever count for, so the
  // first press only opens a consequence sentence and a confirm; no `lesson.assist` leaves this
  // card until the learner confirms. Cancel throws nothing away because nothing was written.
  const [answerConfirmOpen, setAnswerConfirmOpen] = useState(false)
  const answerConfirmRef = useRef(null)
  const answerConfirmTouched = useRef(false)
  // H-178: `lesson.assist` bumps the enrollment revision (`docs/CONTRACTS.md` §lesson.assist), and
  // its response states the new revision. Adopting it locally means pressing "I used a hint" and
  // then "Check" inside the refresh window still carries the current fence instead of losing the
  // submit to STALE_REVISION. Revisions only increase, so the larger of the page's and the assist's
  // is always the newest fact this card holds.
  const [assistRevision, setAssistRevision] = useState(0)
  const [phase, setPhase] = useState('awaiting_input')
  const [result, setResult] = useState(null)
  const [resultCheck, setResultCheck] = useState(null)
  const [error, setError] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [openLaneUnconfigured, setOpenLaneUnconfigured] = useState(false)
  const nonceRef = useRef(null)
  const answerRef = useRef(null)
  const resultRef = useRef(null)
  // H-206: the assist group that replaces a pressed control, and whether the learner just pressed it.
  const assistGroupRef = useRef(null)
  const assistRecordedNow = useRef(false)
  const detached = Boolean(bindingState && bindingState !== 'active')

  // What this card is asking for. A `verification` stimulus with declared items is a checklist and
  // is answered with the item ids; a practice stimulus is a bounded conversation and is never
  // answered with `attempt.submit` (the backend refuses that with `practice_requires_practice_end`),
  // so it takes the one practice surface instead of the written-answer form.
  const stimulus = check ? check.stimulus || null : null
  const practice = stimulus && stimulus.practice ? stimulus.practice : null
  // The form is only offered for a question the learner can actually see. `stimulusStatus` comes
  // from `useOpenCheck`; a direct render that does not pass it keeps the pre-existing behaviour
  // (a served stimulus is ready; otherwise the build speaks about the teaching chat).
  const stimulusState = stimulusStatus || (stimulus ? 'ready' : 'unsupported')
  const promptPresent = Boolean(stimulus && stimulus.prompt)
  const stimulusLoading = stimulusState === 'loading'
  const stimulusUnavailable = stimulusState === 'unavailable'
  const stimulusReady = stimulusState === 'ready'
  const mayAnswer = stimulusReady || stimulusState === 'unsupported'
  const servedItems = stimulus && Array.isArray(stimulus.items) ? stimulus.items : []
  // A parent-led lesson is observed by an adult through the observation control (H-21), never ticked here.
  const checklist = parentLed ? [] : checklistItems(stimulus)
  const readOnlyItems = parentLed ? [] : checklist.length > 0 ? [] : servedItems
  // H-178: the authored check decides the answer surface. A `selection` stimulus with declared
  // choices is a choice check; every other authored format keeps the written answer. The pane never
  // upgrades a text check into a choice (the backend would have nothing to grade the pick against).
  const choices = !parentLed && stimulus && Array.isArray(stimulus.choices) ? stimulus.choices.filter((choice) => String(choice || '').trim()) : []
  const choiceMode = checklist.length === 0 && stimulus && stimulus.format === 'selection' && choices.length > 0
  const selectedChoice = choiceMode && selected >= 0 && selected < choices.length ? choices[selected] : null
  // The pending class: an unconsumed assist event for this objective, else a prior committed
  // attempt on this check (a second answer follows feedback), else the answer is a first try.
  const uncommittedClass = usePendingEvidence({
    enrollmentId,
    objectiveId,
    revision,
    enabled: Boolean(check) && !parentLed,
    implemented,
    refreshKey: phase
  })
  const attemptCount = check && Number(check.attempt_count) > 0 ? Number(check.attempt_count) : 0
  const nextEvidenceClass = assistClass || uncommittedClass || (attemptCount > 0 ? 'hinted' : 'cold')
  // H-206: has this attempt already recorded help? Both values come from the backend (the assist
  // response, or an unconsumed `evidence.inspect` event), never from the click alone.
  const assistRecorded = assistClass || uncommittedClass
  const hintUsed = assistRecorded === 'hinted' || assistRecorded === 'answer_shown'
  const answerUsed = assistRecorded === 'answer_shown'
  // H-206: pressing an assist control replaces it with a statement. Keep focus on the group that
  // replaced it so a keyboard learner is not dropped back on <body>; only a real press sets the
  // flag, so a page that mounts with a hint already recorded never steals focus.
  useEffect(() => {
    if (!assistRecordedNow.current) return
    assistRecordedNow.current = false
    const node = assistGroupRef.current
    if (node && typeof node.focus === 'function') node.focus({ preventScroll: true })
  }, [hintUsed, answerUsed])
  // U2: opening the confirm moves focus into it; closing it returns focus to the assist group that
  // holds the trigger again. Only a real open or cancel sets the flag, so a card that mounts with
  // the confirm closed never steals focus from the page.
  useEffect(() => {
    if (!answerConfirmTouched.current) return
    const node = answerConfirmOpen ? answerConfirmRef.current : assistGroupRef.current
    if (node && typeof node.focus === 'function') node.focus({ preventScroll: true })
  }, [answerConfirmOpen])
  // The fence this card submits against. See `assistRevision`.
  const fenceRevision = Math.max(Number(revision) || 0, Number(assistRevision) || 0)

  // The answer form unmounts when a verdict arrives; put focus on the verdict itself so a keyboard
  // user is not dropped back on <body> with no idea whether the submission went through.
  useEffect(() => {
    if (phase === 'graded' || phase === 'needs_retry' || phase === 'overridden') {
      resultRef.current?.focus({ preventScroll: true })
    }
  }, [phase])

  // A verdict stays on screen until the learner acts on it. Committing an attempt refreshes the
  // section and opens the next check version; that refresh must not wipe the feedback the person
  // just earned (the panel used to snap straight to an empty v3 form).
  useEffect(() => {
    if (result) return
    setText('')
    setTicked([])
    setSelected(-1)
    setAssistClass(null)
    setAnswerConfirmOpen(false)
    setPhase('awaiting_input')
    setResult(null)
    setResultCheck(null)
    setError(null)
    setOpenLaneUnconfigured(false)
    nonceRef.current = null
  }, [check && check.check_id, result])
  const displayCheck = resultCheck || check

  // §7.3 copy is keyed to the lane, not to the topic. `attempt.submit` returns the verdict but not
  // the reference kind, so read the attempt's own grading provenance once: only when the backend
  // recorded that the open-response grader was unconfigured does the "Saved, not graded" copy
  // replace the generic retry copy. If that read is unavailable or silent, nothing changes.
  const resolveNeedsRetryLane = useCallback(
    async (attemptId) => {
      if (!attemptId || !(implemented && implemented.has('quiz.history'))) return
      try {
        const response = await rpc('quiz.history', { enrollment_id: enrollmentId, objective_id: objectiveId })
        if (!response.ok) return
        const rows = (response.result && response.result.attempts) || []
        const row = rows.find((item) => item.attempt_id === attemptId)
        if (row && openLaneWasUnconfigured(row.grading_provenance)) setOpenLaneUnconfigured(true)
      } catch (err) {
        // A read-only lane probe must never replace the verdict the learner just received.
      }
    },
    [enrollmentId, objectiveId, implemented]
  )

  const submit = useCallback(async () => {
    if (!check) return
    // A checklist submits the ticked item ids, never the labels and never the typed text (§9.2).
    // A selection check submits the chosen served choice; a written check submits what was typed.
    const answer =
      checklist.length > 0
        ? checklistAnswer(ticked)
        : choiceMode
          ? selectedChoice !== null
            ? choiceAnswer(selectedChoice)
            : null
          : attemptAnswer(text.trim())
    if (checklist.length > 0 && ticked.length === 0) {
      setError({ code: 'VALIDATION_FAILED', message: 'Tick at least one step before submitting.' })
      return
    }
    if (choiceMode && selectedChoice === null) {
      setError({ code: 'VALIDATION_FAILED', message: 'Pick one of the choices before submitting.' })
      return
    }
    if (!choiceMode && checklist.length === 0 && !text.trim()) {
      setError({ code: 'VALIDATION_FAILED', message: 'Write an answer before submitting.' })
      return
    }
    answerRef.current = answer
    if (!nonceRef.current) nonceRef.current = newOperationId('attempt')
    // U2: submitting an answer closes an open disclosure. The learner chose to answer, so the
    // confirm that never wrote anything must not survive past the attempt it was about.
    setAnswerConfirmOpen(false)
    setPhase('submitting')
    setError(null)
    const response = await rpc(
      'attempt.submit',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current,
        answer
      },
      {
        idempotencyKey: `cb-attempt-${check.check_id}-${nonceRef.current}`,
        expectedRevision: fenceRevision
      }
    )
    if (!response.ok) {
      const code = response.error && response.error.code
      setError(response.error)
      setPhase(code === 'STALE_REVISION' || code === 'CHECK_STALE' ? 'stale' : 'awaiting_input')
      return
    }
    const graded = response.result
    setResult(graded)
    setResultCheck(check)
    setOpenLaneUnconfigured(false)
    setPhase(graded.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    cbPlayCheckCue(graded.verdict)
    if (graded.verdict === 'needs_retry') void resolveNeedsRetryLane(graded.attempt_id)
    if (onCommitted) onCommitted(graded)
  }, [check, text, ticked, checklist, choiceMode, selectedChoice, enrollmentId, fenceRevision, onCommitted, resolveNeedsRetryLane])

  const retryGrading = useCallback(async () => {
    if (!check || !nonceRef.current) return
    setPhase('submitting')
    setError(null)
    const response = await rpc(
      'attempt.submit',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current,
        answer: answerRef.current || (checklist.length > 0 ? checklistAnswer(ticked) : choiceMode && selectedChoice !== null ? choiceAnswer(selectedChoice) : attemptAnswer(text.trim()))
      },
      {
        idempotencyKey: `cb-attempt-${check.check_id}-${nonceRef.current}`,
        expectedRevision: fenceRevision
      }
    )
    if (!response.ok) {
      setError(response.error)
      setPhase('needs_retry')
      return
    }
    setResult(response.result)
    setResultCheck(check)
    setOpenLaneUnconfigured(false)
    setPhase(response.result.verdict === 'needs_retry' ? 'needs_retry' : 'graded')
    cbPlayCheckCue(response.result.verdict)
    if (response.result.verdict === 'needs_retry') void resolveNeedsRetryLane(response.result.attempt_id)
    if (onCommitted) onCommitted(response.result)
  }, [check, text, ticked, checklist, choiceMode, selectedChoice, enrollmentId, fenceRevision, onCommitted, resolveNeedsRetryLane])

  const moveOn = useCallback(async () => {
    if (!check) return
    const response = await rpc(
      'attempt.override',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        reason: 'Moved on after a grading failure (recorded from the Coursebook pane).'
      },
      { expectedRevision: Number(revision) || 0 }
    )
    setOverrideOpen(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setResult({ verdict: 'overridden', evidence_class: 'override', criteria: [], next_action: 'complete_objective' })
    setResultCheck(check)
    setPhase('overridden')
    if (onCommitted) onCommitted(response.result)
  }, [check, enrollmentId, revision, onCommitted])

  /**
   * Start a different re-attempt on the same open check.
   *
   * `Check` never changes the check the backend served, so retrying is free and unshamed: the
   * nonce is dropped (a new attempt, never a replay), the answer is cleared and any feedback is
   * dismissed. Nothing is scored and nothing is counted against the learner.
   */
  const newExample = useCallback(() => {
    setText('')
    setTicked([])
    setSelected(-1)
    setAnswerConfirmOpen(false)
    setResult(null)
    setResultCheck(null)
    setError(null)
    setPhase('awaiting_input')
    nonceRef.current = null
  }, [])

  /**
   * Record that the learner used help, before — never after — the answer that inherits it.
   *
   * This is the pane's own `lesson.assist`: the same layer-1 event the chat hook writes, with the
   * same `hint_request` / `answer_shown` kinds. The response states the class the next committed
   * attempt will carry, and the enrollment revision moves so an in-flight submit loses its fence
   * instead of being committed as cold (`docs/CONTRACTS.md` §lesson.assist). Nothing is revealed and
   * nothing is graded: the control records the learner's own statement.
   */
  const recordAssist = useCallback(
    async (kind) => {
      if (!check || assistBusy) return false
      // H-206: a hint is one recorded statement per attempt. The control is already in its used
      // state after the first one, so a repeat may not add a second event that changes nothing.
      if (kind === 'hint_request' && hintUsed) return false
      if (kind === 'answer_shown' && answerUsed) return false
      setAssistPending(kind)
      setError(null)
      const response = await rpc(
        'lesson.assist',
        { enrollment_id: enrollmentId, objective_id: objectiveId, kind },
        {
          idempotencyKey: newOperationId('assist'),
          expectedRevision: fenceRevision
        }
      )
      setAssistPending(null)
      if (!response.ok) {
        setError(response.error)
        return false
      }
      const recorded = response.result && response.result.evidence_class
      assistRecordedNow.current = true
      setAssistClass(recorded || (kind === 'answer_shown' ? 'answer_shown' : 'hinted'))
      // The assist moved the enrollment revision; adopt it before the async page refresh lands so
      // a hint followed immediately by a submit cannot be refused as STALE_REVISION.
      const bumped = response.result ? Number(response.result.revision) : NaN
      if (Number.isFinite(bumped) && bumped > 0) setAssistRevision(bumped)
      if (onCommitted) onCommitted(response.result)
      return true
    },
    [check, assistBusy, hintUsed, answerUsed, enrollmentId, objectiveId, fenceRevision, onCommitted]
  )

  /**
   * Ask for a hint, then answer it.
   *
   * Two writes, in order: this pane records the learner's own `hint_request` (the same event the
   * disclosure below writes), and only after it is stored does the rail receive the one hint
   * question. The disclosure stays a record of what already happened; this control is the one
   * that actually asks, so a learner who presses it is told something before the check is marked.
   */
  const askHintBesideCheck = useCallback(async () => {
    setAssistIntent('ask')
    const recorded = await recordAssist('hint_request')
    setAssistIntent(null)
    if (recorded) requestTutorHint()
  }, [recordAssist])

  /** The post-hoc disclosure: it records the learner's own statement and answers nothing. */
  const recordHintDisclosure = useCallback(async () => {
    setAssistIntent('record')
    await recordAssist('hint_request')
    setAssistIntent(null)
  }, [recordAssist])

  /**
   * U2: the answer disclosure asks first.
   *
   * "I saw the answer" is the only control here that takes something away from the learner — the
   * next committed attempt can never be `independent` again — so the first press writes nothing at
   * all. It opens one sentence saying what the click costs and a confirm; only the confirm reaches
   * `lesson.assist(kind:'answer_shown')`. A failed write keeps the confirm open with the refusal
   * beside its buttons, so the learner sees it and can decide again; cancelling writes nothing and
   * leaves the attempt exactly as it was.
   */
  const openAnswerConfirm = useCallback(() => {
    answerConfirmTouched.current = true
    setError(null)
    setAnswerConfirmOpen(true)
  }, [])

  const cancelAnswerConfirm = useCallback(() => {
    answerConfirmTouched.current = true
    setError(null)
    setAnswerConfirmOpen(false)
  }, [])

  const confirmAnswerShown = useCallback(async () => {
    const recorded = await recordAssist('answer_shown')
    // Only a stored event closes the confirm. A refusal leaves it open with `error` beside the
    // buttons, so the learner is not told a write happened when it did not.
    if (recorded) setAnswerConfirmOpen(false)
    return recorded
  }, [recordAssist])

  /** Radio-group keys: 1–8 pick by number, arrows move and select, Home/End jump. */
  const choiceKeyDown = (event) => {
    if (locked || detached || event.altKey || event.ctrlKey || event.metaKey) return
    const count = choices.length
    if (count === 0) return
    const key = event.key
    let next = null
    if (key === 'ArrowDown' || key === 'ArrowRight') next = (Math.max(selected, -1) + 1) % count
    else if (key === 'ArrowUp' || key === 'ArrowLeft') next = selected <= 0 ? count - 1 : selected - 1
    else if (key === 'Home') next = 0
    else if (key === 'End') next = count - 1
    else if (/^[1-9]$/.test(key)) {
      const index = Number(key) - 1
      if (index < count) next = index
    }
    if (next === null) return
    event.preventDefault()
    setSelected(next)
    const root = event.currentTarget
    if (root && typeof root.querySelector === 'function') {
      const option = root.querySelector(`[data-cb-choice="${next + 1}"]`)
      if (option && typeof option.focus === 'function') option.focus()
    }
  }

  /**
   * The player bridge.
   *
   * The player owns the single footer primary, so the answer card must not paint a second one and
   * must tell its host when `Check` is legal. The snapshot is deliberately small and primitive so
   * the parent only re-renders when the answer state actually changes; every action below already
   * exists for the reference views and this bridge only exposes it.
   */
  const playerSnapshot = {
    phase,
    canCheck: !check
      ? false
      : Boolean(
          stimulusState === 'unsupported' ||
            (stimulusState === 'ready' &&
              (checklist.length > 0
                ? ticked.length > 0
                : choiceMode
                  ? selectedChoice !== null
                  : text.trim().length > 0))
        ) && phase === 'awaiting_input' && !detached,
    verdict: result ? result.verdict : null,
    evidenceClass: result ? result.evidence_class || null : null,
    nextEvidenceClass,
    answerKind: checklist.length > 0 || choiceMode ? 'selection' : 'text'
  }
  const playerSnapshotKey = `${playerSnapshot.phase}|${playerSnapshot.canCheck}|${playerSnapshot.verdict}|${playerSnapshot.answerKind}|${playerSnapshot.nextEvidenceClass}`
  useEffect(() => {
    if (!playerMode || !onPlayerState) return
    onPlayerState(playerSnapshot)
    // The key is what changes; the object itself is rebuilt every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerMode, onPlayerState, playerSnapshotKey])
  useEffect(() => {
    if (!playerMode || !playerController) return
    playerController.current = {
      submit,
      retryGrading,
      newExample,
      moveOn: () => setOverrideOpen(true)
    }
  })

  if (!check) {
    return jsx(QuietNote, {
      children: 'There is no open check for this objective yet. Opening the section asks the backend for one.'
    })
  }

  const locked = phase === 'submitting'
  const showForm = phase === 'awaiting_input' || phase === 'stale'
  const criteria = (result && result.criteria) || []
  // The learner-facing question, projected by `check.get`. `check.open` carries identity only, so a
  // build without that read simply has no stimulus here and shows the answer form alone.
  const toggleItem = (id, next) => {
    setTicked((previous) => {
      const already = previous.includes(id)
      if (next && !already) return [...previous, id]
      if (!next && already) return previous.filter((item) => item !== id)
      return previous
    })
  }
  const checklistEmpty = checklist.length > 0 && ticked.length === 0
  // A partial keeps the check open: tick the rest and submit again. That is a new attempt, so the
  // per-view nonce is dropped rather than replaying the stored partial.
  const resumeChecklist = () => {
    nonceRef.current = null
    setError(null)
    setPhase('awaiting_input')
  }

  // A practice is answered by its own surface, after every hook above has run: the check can be
  // replaced (v1 → v2) without changing which hooks this component called.
  if (practice) {
    return jsx(PracticeSurface, {
      enrollmentId,
      objectiveId,
      check,
      revision,
      implemented,
      bindingState,
      onCommitted
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: `Check v${displayCheck.check_version}` }),
          jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: displayCheck.evidence_target || 'evidence' }),
          result && result.evidence_class ? jsx(EvidenceClassText, { value: result.evidence_class }) : null
        ]
      }),

      stimulus && stimulus.prompt
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-check-stimulus': check.check_id,
            children: [
              jsx(ProseText, { className: 'max-w-prose', text: stimulus.prompt }),
              // The instructions are printed only when they say something the question does not.
              // The same sentence in both fields is the same question twice on one screen.
              classroomExtraInstruction(stimulus.prompt, stimulus.learner_instructions)
                ? jsx('p', {
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children: classroomExtraInstruction(stimulus.prompt, stimulus.learner_instructions)
                  })
                : null,
              choices.length > 0 && !choiceMode
                ? jsx('ul', {
                    className: 'flex flex-col gap-1 text-sm leading-snug',
                    'aria-label': CB3_CLASSROOM_COPY.checkChoices,
                    children: choices.map((choice, index) =>
                      jsx('li', { children: choice }, `choice-${index}`)
                    )
                  })
                : null,
              checklist.length > 0
                ? jsxs('div', {
                    className: 'flex flex-col gap-1',
                    'data-cb-check-items': String(checklist.length),
                    'data-cb-check-items-mode': 'selection',
                    children: [
                      jsx(CbLabel, { children: CB3_CLASSROOM_COPY.checkChecklist }),
                      // One row per declared item: the served id is the submitted value, the label
                      // is the question. Ticking is the answer; nothing is typed here.
                      jsx('ul', {
                        className: 'flex flex-col gap-1.5',
                        'aria-label': CB3_CLASSROOM_COPY.checkChecklist,
                        children: checklist.map((item, index) =>
                          jsxs(
                            'li',
                            {
                              className: 'flex items-start gap-2',
                              'data-cb-check-item': item.id,
                              children: [
                                jsx(sdk.Checkbox, {
                                  'aria-describedby': 'cb-attempt-help',
                                  checked: ticked.includes(item.id),
                                  'data-cb-check-tick': item.id,
                                  disabled: locked || detached,
                                  id: `cb-check-item-${index}`,
                                  onCheckedChange: (next) => toggleItem(item.id, next === true)
                                }),
                                jsx('label', {
                                  className: 'text-sm leading-snug',
                                  htmlFor: `cb-check-item-${index}`,
                                  children: item.label
                                })
                              ]
                            },
                            item.id
                          )
                        )
                      })
                    ]
                  })
                : readOnlyItems.length > 0
                  ? jsxs('div', {
                      className: 'flex flex-col gap-1',
                      'data-cb-check-items': String(readOnlyItems.length),
                      'data-cb-check-items-mode': 'read_only',
                      children: [
                        jsx(CbLabel, { children: CB3_CLASSROOM_COPY.checkChecklist }),
                        // One label per item, printed here and nowhere else in the lesson.
                        jsx('ul', {
                          className: 'flex flex-col gap-1',
                          'aria-label': CB3_CLASSROOM_COPY.checkChecklist,
                          children: readOnlyItems.map((item) =>
                            jsx('li', {
                              className: 'text-sm leading-snug',
                              'data-cb-check-item': item.id,
                              children: item.label
                            }, item.id)
                          )
                        })
                      ]
                    })
                  : null
            ]
          })
        : null,

      showForm && stimulusLoading
        ? jsxs('div', {
            className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
            'data-cb-check-stimulus-state': 'loading',
            children: [
              jsx(sdk.Loader, { label: 'Loading the question' }),
              jsx('span', { children: 'The answer form stays closed until the question is here.' })
            ]
          })
        : null,

      showForm && stimulusUnavailable
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-check-stimulus-state': 'unavailable',
            children: [
              jsx(sdk.ErrorState, {
                title: 'The question could not be loaded',
                description: stimulusUnavailableDescription(stimulusError)
              }),
              onRetryStimulus
                ? jsx(sdk.Button, {
                    className: 'self-start',
                    size: 'sm',
                    variant: 'secondary',
                    disabled: locked,
                    onClick: onRetryStimulus,
                    children: 'Retry'
                  })
                : null
            ]
          })
        : null,

      showForm && mayAnswer && !parentLed
        ? jsx(EvidenceChip, { value: nextEvidenceClass, pending: true })
        : null,

      showForm && mayAnswer
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            'data-cb-answer-kind': checklist.length > 0 || choiceMode ? 'selection' : 'text',
            children: [
              checklist.length > 0
                ? jsx('p', {
                    id: 'cb-attempt-help',
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    children:
                      'Tick every step you actually completed. Your ticks are recorded as your own report, not as an independent check.'
                  })
                : choiceMode
                  ? jsx('p', {
                      id: 'cb-attempt-help',
                      className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                      children: 'Pick one answer. Press 1–' + String(Math.min(choices.length, 8)) + ' or use the arrow keys, then submit.'
                    })
                  : jsx('label', {
                      className: 'text-xs font-medium text-(--ui-text-secondary)',
                      htmlFor: 'cb-attempt-answer',
                      children: 'Your answer'
                    }),
              checklist.length > 0
                ? null
                : choiceMode
                  ? jsxs('div', {
                      role: 'radiogroup',
                      'aria-label': CB3_CLASSROOM_COPY.checkAnswers,
                      'aria-describedby': 'cb-attempt-help',
                      'data-cb-choice-group': String(choices.length),
                      'data-cb-choice-selected': selected >= 0 ? String(selected + 1) : '',
                      onKeyDown: choiceKeyDown,
                      style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', maxWidth: CB_MEASURE },
                      children: [
                        choices.map((choice, index) => {
                          const active = index === selected
                          return jsxs(
                            'div',
                            {
                              role: 'radio',
                              'aria-checked': active ? 'true' : 'false',
                              tabIndex: active || (selected < 0 && index === 0) ? 0 : -1,
                              'data-cb-choice': String(index + 1),
                              'data-cb-choice-state': active ? 'selected' : 'available',
                              'aria-disabled': locked || detached ? 'true' : undefined,
                              onClick: () => {
                                if (locked || detached) return
                                setSelected(index)
                              },
                              style: {
                                display: 'flex',
                                alignItems: 'baseline',
                                gap: '0.55rem',
                                minHeight: '2.75rem',
                                padding: '0.6rem 0.7rem',
                                cursor: locked || detached ? 'default' : 'pointer',
                                border: `1px solid ${active ? 'var(--cb-accent)' : 'var(--cb-rule)'}`,
                                background: active ? 'var(--cb-lamp-soft)' : 'var(--cb-paper)',
                                boxSizing: 'border-box',
                                outlineOffset: '2px'
                              },
                              children: [
                                jsx('span', {
                                  'aria-hidden': 'true',
                                  style: {
                                    fontFamily: CB_SANS,
                                    fontSize: CB_TYPE.caption,
                                    fontWeight: 600,
                                    fontVariantNumeric: 'tabular-nums',
                                    color: active ? 'var(--cb-accent)' : 'var(--cb-ink-soft)',
                                    minWidth: '1.1rem'
                                  },
                                  children: String(index + 1)
                                }),
                                jsx('span', {
                                  style: {
                                    flex: '1 1 auto',
                                    minWidth: 0,
                                    fontFamily: CB_SERIF,
                                    fontSize: phone ? CB_TYPE.body : CB_TYPE.lead,
                                    lineHeight: 1.4,
                                    color: 'var(--cb-ink)',
                                    overflowWrap: 'anywhere'
                                  },
                                  children: choice
                                }),
                                jsx('span', {
                                  'data-cb-choice-word': active ? 'selected' : 'available',
                                  style: {
                                    fontFamily: CB_SANS,
                                    fontSize: CB_TYPE.caption,
                                    lineHeight: 1.3,
                                    color: active ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
                                    whiteSpace: 'nowrap'
                                  },
                                  children: active ? 'Selected' : ''
                                })
                              ]
                            },
                            `choice-${index}`
                          )
                        }),
                        jsx('p', {
                          'data-cb-choice-answer': '',
                          'aria-live': 'polite',
                          style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                          children:
                            selectedChoice !== null
                              ? `Selected: ${selected + 1}. ${selectedChoice}`
                              : 'Nothing selected yet.'
                        })
                      ]
                    })
                  : jsx(sdk.Textarea, {
                      id: 'cb-attempt-answer',
                      'aria-describedby': 'cb-attempt-help',
                      disabled: locked || detached,
                      onChange: (event) => setText(event.target.value),
                      placeholder: 'Type the answer you would give in the lesson.',
                      rows: playerMode ? 5 : 3,
                      value: text
                    }),
              checklist.length > 0 || choiceMode
                ? null
                : jsx('p', {
                    id: 'cb-attempt-help',
                    className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                    style: { maxWidth: CB_MEASURE },
                    children: stimulusReady && promptPresent
                      ? 'The question and any choices are shown above; this field records what you answered.'
                      : 'The question and any choices are in the teaching chat. This field records your answer and the backend grades it once.'
                  }),
              detached
                ? jsx(QuietNote, {
                    children: 'This lesson is no longer connected to its chat, so Submit is off. Open a new lesson run to connect a new chat.'
                  })
                : null,
              supports('lesson.assist') && !detached
                ? jsxs('div', {
                    'data-cb-assist': 'available',
                    'data-cb-assist-state': answerUsed ? 'answer_shown' : hintUsed ? 'hinted' : 'available',
                    ref: assistGroupRef,
                    tabIndex: -1,
                    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem', outlineOffset: '2px' },
                    children: [
                      hintUsed
                        ? jsx(AssistUsedFlag, { kind: 'hint_request', children: 'Hint recorded' })
                        : jsxs('span', {
                            style: { display: 'inline-flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem' },
                            children: [
                              jsx(sdk.Button, {
                                variant: 'text',
                                size: 'sm',
                                'data-cb-ask-hint': '',
                                disabled: locked || assistBusy,
                                onClick: askHintBesideCheck,
                                children: assistIntent === 'ask' && assistPending === 'hint_request' ? 'Asking…' : 'Ask for a hint'
                              }, 'ask'),
                              jsx(sdk.Button, {
                                variant: 'text',
                                size: 'sm',
                                'data-cb-assist-disclosure': 'hint_request',
                                disabled: locked || assistBusy,
                                'data-cb-assist-pending': assistPending === 'hint_request' && assistIntent === 'record' ? '' : undefined,
                                onClick: recordHintDisclosure,
                                children: assistIntent === 'record' && assistPending === 'hint_request' ? 'Recording…' : 'I already used a hint'
                              }, 'disclosure')
                            ]
                          }),
                      answerUsed
                        ? jsx(AssistUsedFlag, { kind: 'answer_shown', children: 'Answer shown' })
                        : answerConfirmOpen
                          ? jsxs('div', {
                              'data-cb-assist-confirm': 'answer_shown',
                              id: 'cb-answer-confirm',
                              role: 'group',
                              'aria-label': 'Confirm that you saw the answer',
                              ref: answerConfirmRef,
                              tabIndex: -1,
                              onKeyDown: (event) => {
                                if (event.key !== 'Escape') return
                                event.stopPropagation()
                                cancelAnswerConfirm()
                              },
                              style: {
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.35rem',
                                flexBasis: '100%',
                                minWidth: 0,
                                padding: '0.5rem 0.6rem',
                                border: '1px solid var(--cb-ochre)',
                                background: 'var(--cb-lamp-soft)',
                                boxSizing: 'border-box',
                                outlineOffset: '2px'
                              },
                              children: [
                                jsx('p', {
                                  id: 'cb-answer-confirm-note',
                                  style: {
                                    margin: 0,
                                    fontFamily: CB_SANS,
                                    fontSize: CB_TYPE.caption,
                                    lineHeight: 1.45,
                                    color: 'var(--cb-ink)'
                                  },
                                  children:
                                    'This marks the attempt "answer shown". The answer you send next cannot count as independent evidence, and this cannot be undone.'
                                }, 'note'),
                                jsxs('div', {
                                  style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem 0.6rem' },
                                  children: [
                                    jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      'data-cb-answer-confirm-yes': '',
                                      'aria-describedby': 'cb-answer-confirm-note',
                                      disabled: locked || assistBusy,
                                      onClick: confirmAnswerShown,
                                      children: assistPending === 'answer_shown' ? 'Recording…' : 'Yes, record that I saw the answer'
                                    }, 'yes'),
                                    jsx(sdk.Button, {
                                      variant: 'text',
                                      size: 'sm',
                                      'data-cb-answer-confirm-cancel': '',
                                      disabled: assistBusy,
                                      onClick: cancelAnswerConfirm,
                                      children: 'Cancel'
                                    }, 'cancel')
                                  ]
                                }, 'actions'),
                                // A refused write keeps this confirm exactly where it is and prints
                                // the refusal beside the buttons that caused it.
                                error
                                  ? jsx('div', {
                                      role: 'alert',
                                      'data-cb-answer-confirm-error': '',
                                      children: jsx(ErrorLine, { error })
                                    })
                                  : null
                              ]
                            })
                          : jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              disabled: locked || assistBusy,
                              'data-cb-assist-answer': '',
                              'data-cb-assist-pending': assistPending === 'answer_shown' ? '' : undefined,
                              onClick: openAnswerConfirm,
                              children: assistPending === 'answer_shown' ? 'Recording…' : 'I saw the answer'
                            }),
                      jsx('span', {
                        'data-cb-assist-note': '',
                        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                        children: hintUsed
                          ? 'Recorded for this attempt. This answer cannot count as independent evidence.'
                          : 'Said honestly, this changes what the next answer can count for.'
                      })
                    ]
                  })
                : null,
              // The player carries the one footer primary (`Check`), so the answer card paints no
              // button of its own there. The reference views keep their inline actions unchanged.
              playerMode
                ? null
                : jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx(CbAction, {
                    variant: 'primary',
                    disabled: locked || detached || (checklist.length > 0 ? checklistEmpty : choiceMode ? selectedChoice === null : !text.trim()),
                    onClick: submit,
                    children: locked ? 'Submitting' : checklist.length > 0 ? 'Submit confirmation' : choiceMode ? 'Submit choice' : 'Submit answer'
                  }),
                  checklist.length > 0
                    ? jsx(sdk.Button, {
                        variant: 'text',
                        size: 'sm',
                        disabled: locked || ticked.length === 0,
                        onClick: () => {
                          setTicked([])
                          setError(null)
                        },
                        children: 'Clear ticks'
                      })
                    : choiceMode
                      ? jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          disabled: locked || selected < 0,
                          onClick: () => {
                            setSelected(-1)
                            setError(null)
                          },
                          children: 'Clear choice'
                        })
                      : jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          disabled: locked || !text,
                          onClick: () => {
                            setText('')
                            setError(null)
                          },
                          children: 'Edit answer'
                        })
                ]
              })
            ]
          })
        : null,

      phase === 'submitting'
        ? jsxs('div', {
            className: 'flex items-center gap-2 text-xs text-(--ui-text-secondary)',
            children: [
              jsx(sdk.Loader, { label: 'Grading this answer' }),
              jsx('span', { children: 'Answer locked. No second attempt is created while this runs.' })
            ]
          })
        : null,

      phase === 'graded' && result
        ? jsxs('div', {
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
            children: [
              playerMode
                ? jsx(PlayerVerdict, {
                    result,
                    criteria,
                    checklist,
                    answer:
                      checklist.length > 0
                        ? checklist.filter((item) => ticked.includes(item.id)).map((item) => item.label)
                        : choiceMode
                          ? selectedChoice || ''
                          : text.trim()
                  })
                : jsx(AttemptVerdict, {
                    result,
                    criteria,
                    checklist,
                    onResumeChecklist: resumeChecklist,
                    onNewExample: newExample,
                    onExplain: () => setPhase('awaiting_input')
                  })
            ]
          })
        : null,

      phase === 'needs_retry'
        ? jsxs('div', {
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
            children: [
              openLaneUnconfigured
                ? jsx('p', {
                    className: 'max-w-prose text-sm leading-relaxed',
                    'data-cb-breadth': 'open-lane',
                    children: OPEN_LANE_NOT_GRADED_COPY
                  })
                : jsx('div', {
                    className: 'text-sm font-medium',
                    children: 'We could not grade this answer'
                  }),
              openLaneUnconfigured
                ? null
                : jsx(QuietNote, {
                    children:
                      'Your answer is saved, not graded. No progress was changed, and Retry grading does not create a second attempt.'
                  }),
              error ? jsx(ErrorLine, { error }) : null,
              playerMode
                ? null
                : jsxs('div', {
                    className: 'flex flex-wrap items-center gap-2',
                    children: [
                      jsx(CbAction, { variant: 'primary', onClick: retryGrading, children: 'Retry grading' }),
                  jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => setPhase('awaiting_input'),
                    children: 'Edit answer'
                  }),
                  jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => setOverrideOpen(true), children: 'Move on…' })
                ]
              })
            ]
          })
        : null,

      phase === 'overridden'
        ? jsxs('div', {
            className: 'flex flex-col gap-2 outline-none',
            ref: resultRef,
            tabIndex: -1,
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'Access granted — not independent evidence' }),
              jsx(QuietNote, {
                children: 'The override is recorded against this objective. It advances access and is never counted as a pass.'
              }),
              playerMode
                ? null
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                  setResult(null)
                  setResultCheck(null)
                  setPhase('awaiting_input')
                  nonceRef.current = null
                },
                children: 'Back to the check'
              })
            ]
          })
        : null,

      phase === 'stale'
        ? jsxs('div', {
            className: 'flex flex-col gap-2',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'This check moved on while you were answering.' }),
              jsx(QuietNote, {
                children: 'No attempt was created and nothing was overwritten. Re-read the section to get the current check.'
              }),
              error ? jsx(ErrorLine, { error }) : null
            ]
          })
        : null,

      // U2: while the answer confirm is open it prints its own refusal beside its buttons, so the
      // same sentence must not also appear at the foot of the card.
      error && !answerConfirmOpen && phase !== 'needs_retry' && phase !== 'stale' ? jsx(ErrorLine, { error }) : null,

      playerMode
        ? null
        : jsx(QuietNote, {
            children: supports('lesson.assist')
              ? 'Hints and shown answers are recorded against the next attempt.'
              : 'No hint and no shown answer are offered on this check. Work it out from the section text.'
          }),

      jsx('p', {
        className: 'max-w-prose text-xs leading-relaxed text-(--ui-text-secondary)',
        style: { maxWidth: CB_MEASURE },
        'data-cb-breadth': 'check',
        children: CHECK_SURFACE_DISCLOSURE
      }),

      jsx(FocusReturningDialog, {
        open: overrideOpen,
        title: 'Move on without a grade?',
        description:
          'This records an override: access advances, but the objective is marked overridden and this attempt is never counted as independent evidence. The saved answer is kept.',
        confirmLabel: 'Record override',
        onClose: () => setOverrideOpen(false),
        onConfirm: moveOn,
        children: null
      })
    ]
  })
}

/**
 * The notebook's provenance ref.
 *
 * `notebook.save` has a course/objective column pair and one opaque `source_ref` string (≤500
 * chars). A saved moment can point at a block, its artifact, several source ids and the check it
 * came from, so those refs travel as one compact JSON object in that column. A caller that only
 * has a bare id keeps passing the bare id; `readNotebookRef` reads both, so older rows still
 * resolve and the backend schema is untouched.
 */
function notebookSourceRef(seed) {
  if (!seed) return null
  const ref = {}
  if (seed.block_id) ref.block = String(seed.block_id).slice(0, 120)
  if (seed.artifact_id) ref.artifact = String(seed.artifact_id).slice(0, 120)
  if (Array.isArray(seed.source_ids) && seed.source_ids.length > 0) {
    ref.sources = seed.source_ids.filter(Boolean).slice(0, 8).map((id) => String(id).slice(0, 80))
  }
  if (seed.check_id) ref.check = String(seed.check_id).slice(0, 120)
  if (Object.keys(ref).length === 0) return seed.source_ref ? String(seed.source_ref).slice(0, 500) : null
  return JSON.stringify(ref).slice(0, 500)
}

/** Read a `source_ref` written by `notebookSourceRef`, or an older bare id. Never guesses one. */
function readNotebookRef(value) {
  const ref = { block_id: null, artifact_id: null, source_ids: [], check_id: null, legacy: null }
  if (!value) return ref
  const text = String(value)
  if (text.charAt(0) === '{') {
    try {
      const parsed = JSON.parse(text)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        ref.block_id = typeof parsed.block === 'string' ? parsed.block : null
        ref.artifact_id = typeof parsed.artifact === 'string' ? parsed.artifact : null
        ref.source_ids = Array.isArray(parsed.sources) ? parsed.sources.filter((id) => typeof id === 'string') : []
        ref.check_id = typeof parsed.check === 'string' ? parsed.check : null
        return ref
      }
    } catch (error) {
      // A hand-written or truncated value is still a reference, just not a structured one.
    }
  }
  ref.legacy = text
  return ref
}

/** Save one moment into the notebook: excerpt preview, note, tags, provenance. */
function NotebookSaveDialog({ open, onClose, enrollmentId, objectiveId, lessonRunId, seed, implemented, onSaved }) {
  const [note, setNote] = useState('')
  const [tags, setTags] = useState('')
  const [excerpt, setExcerpt] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const supports = (method) => Boolean(implemented && implemented.has(method))

  useEffect(() => {
    if (!open) return
    setNote('')
    setTags('')
    setExcerpt((seed && seed.excerpt) || '')
    setError(null)
    setBusy(false)
  }, [open, seed])

  const provenance = []
  if (seed && seed.course_title) provenance.push({ label: 'Course', value: seed.course_title })
  if (seed && seed.objective_title) provenance.push({ label: 'Objective', value: seed.objective_title })
  if (seed && seed.block_headline) provenance.push({ label: 'Saved from', value: seed.block_headline })
  const sourceNames = (seed && (seed.source_titles || seed.source_ids)) || []
  if (sourceNames.length > 0) {
    provenance.push({ label: sourceNames.length === 1 ? 'Source' : 'Sources', value: sourceNames.join(', ') })
  }
  if (seed && seed.artifact_id) provenance.push({ label: 'Media', value: seed.artifact_id })

  const save = useCallback(async () => {
    setBusy(true)
    setError(null)
    const tagList = tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
      .slice(0, 20)
    const response = await rpc('notebook.save', {
      enrollment_id: enrollmentId,
      objective_id: objectiveId,
      lesson_run_id: lessonRunId || null,
      kind: (seed && seed.kind) || 'lesson_segment',
      excerpt: excerpt.trim() || null,
      note: note.trim() || null,
      tags: tagList,
      source_ref: notebookSourceRef(seed)
    })
    setBusy(false)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setBusy(false)
    onSaved()
    onClose()
  }, [enrollmentId, objectiveId, lessonRunId, seed, excerpt, note, tags, onSaved, onClose])

  return jsx(FocusReturningDialog, {
    open,
    title: 'Save to notebook',
    description: 'Saved excerpts and personal notes stay on this profile. They never enter a shared pack.',
    confirmLabel: busy ? 'Saving' : 'Save to notebook',
    onClose,
    onConfirm: save,
    children: jsxs('div', {
      className: 'flex flex-col gap-3',
      children: [
        provenance.length > 0
          ? jsxs('div', {
              className: 'flex flex-col gap-0.5',
              'data-cb-save-provenance': 'ready',
              children: provenance.map((item) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-wrap items-baseline gap-1 text-xs',
                    children: [
                      jsx('span', { className: 'text-(--ui-text-secondary)', children: `${item.label} ·` }),
                      jsx('span', { className: 'min-w-0 break-words', children: item.value })
                    ]
                  },
                  item.label
                )
              )
            })
          : jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              'data-cb-save-provenance': 'none',
              children: 'This moment has no block or source attached; it is saved under the section you are reading.'
            }),
        jsx('label', {
          htmlFor: 'cb-note-excerpt',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Excerpt'
        }),
        jsx(sdk.Textarea, {
          id: 'cb-note-excerpt',
          rows: 3,
          value: excerpt,
          onChange: (event) => setExcerpt(event.target.value)
        }),
        jsx('label', {
          htmlFor: 'cb-note-note',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Your note (optional)'
        }),
        jsx(sdk.Textarea, {
          id: 'cb-note-note',
          rows: 2,
          value: note,
          onChange: (event) => setNote(event.target.value),
          placeholder: 'Why this matters to you.'
        }),
        jsx('label', {
          htmlFor: 'cb-note-tags',
          className: 'text-xs font-medium text-(--ui-text-secondary)',
          children: 'Tags (comma separated)'
        }),
        jsx(sdk.Input, {
          id: 'cb-note-tags',
          value: tags,
          onChange: (event) => setTags(event.target.value),
          placeholder: 'register, politeness'
        }),
        supports('notebook.save') ? null : jsx(QuietNote, { children: 'Saving to the notebook is not available in this build.' }),
        error ? jsx(ErrorLine, { error }) : null
      ]
    })
  })
}

/** The section index. Uses `course.outline` when the backend has it; otherwise names what it can. */
function sectionRows({ row, review, notebooks, outline, page }) {
  const seen = new Map()
  const add = (entry) => {
    if (!entry || !entry.objective_id) return
    const existing = seen.get(entry.objective_id) || {}
    // A later source (a notebook save, a review row) can carry the id without the label. Merge
    // field-by-field so a missing title never erases one an earlier source already named.
    const merged = { ...existing }
    Object.keys(entry).forEach((field) => {
      const value = entry[field]
      if (value !== null && value !== undefined) merged[field] = value
    })
    seen.set(entry.objective_id, merged)
  }
  if (outline && Array.isArray(outline.objectives)) {
    outline.objectives.forEach((objective) =>
      add({
        objective_id: objective.objective_id,
        title: objective.title,
        ordinal: objective.ordinal,
        state: objective.state,
        evidence_target: objective.evidence_target,
        attempt_count: objective.attempt_count,
        independent: objective.independent,
        unit: objective.unit,
        last_opened_at: objective.last_opened_at
      })
    )
  }
  if (review && Array.isArray(review.items)) {
    review.items.forEach((item) =>
      add({
        objective_id: item.objective_id,
        title: item.title,
        ordinal: item.ordinal,
        state: item.state,
        evidence_target: item.evidence_target,
        due_at: item.due_at,
        overdue: item.overdue
      })
    )
  }
  const current = row && row.evidence_summary && row.evidence_summary.current_objective_id
  if (current) {
    const pageSection = page && page.section && page.section.objective_id === current ? page.section : null
    // The current objective only *names* a row the outline already carries; it must not overwrite
    // that row's title with a placeholder or drop the unit it belongs to.
    if (!seen.has(current)) {
      add({
        objective_id: current,
        title: (pageSection && pageSection.title) || 'Current section',
        ordinal: pageSection ? pageSection.ordinal : 0,
        state: pageSection ? pageSection.state : undefined,
        evidence_target: pageSection ? pageSection.evidence_target : undefined
      })
    } else if (pageSection) {
      add({
        objective_id: current,
        title: pageSection.title,
        ordinal: pageSection.ordinal,
        state: pageSection.state,
        evidence_target: pageSection.evidence_target
      })
    }
  }
  if (notebooks && Array.isArray(notebooks.entries)) {
    notebooks.entries.forEach((entry) => {
      if (entry.objective_id) add({ objective_id: entry.objective_id, title: null })
    })
  }
  return Array.from(seen.values())
    .map((entry) => ({ ...entry, title: entry.title || 'Saved section' }))
    .sort((left, right) => (left.ordinal || 0) - (right.ordinal || 0))
}

// CB-V3-BEGIN — CP-023: the v3 classroom (R-CLASS, docs/concept-parity/SPEC-V3.md §5.3)
/**
 * ── Classroom v3 ──────────────────────────────────────────────────────────────────────────────
 *
 * The peer problem, executed: the lesson screen has to be *one* reading column facing a framed
 * scene and one check, not a stack of equal boxes. This segment owns the composition and the
 * check's v3 answer surfaces; it paints from the v3 primitives (`StampNode`, `DialogueBubble`,
 * `EvidenceTray`, `ChallengeCard`, `FoxPose`, `PillAction`) and from `var(--cb3-*)` only.
 *
 * Everything visible is deck copy (`docs/concept-parity/COPY.md` §4) or a backend field:
 *
 *   stepper      `course.outline.objectives[]` — one `StampNode` per real section; `Now` on the
 *                section the lesson page names, `Done` on an objective with independent or delayed
 *                evidence, `Next` otherwise. A section is `locked` **only** when the plan records
 *                the gate (`objective.locked === true`); nothing is inferred, because the outline
 *                carries no prerequisite field today and inventing a padlock would be a lie.
 *   scene        the course world's section plate (`world.read` → artifact id → `artifact.get`),
 *                else a typographic plate that states the course title. Never an invented cover.
 *   dialogue     the pack's own line, read out of the authored teaching segment (kana, romaji and
 *                the English meaning are all in that line); the ruby is deck-authored over known
 *                kanji and is omitted for any line this deck has no reading for.
 *   check        the served stimulus in its own format (`text`, `selection`, `verification`) with
 *                exactly one filled control; `Check answer` → `Try again` / `Next section`.
 *   aside        evidence (counted from `lesson.page.checks[]`), the real next section, and the
 *                tutor door. Game mode adds the XP chip and the Field Challenge; Textbook and
 *                Guided never render XP.
 *
 * A volatile copy of this warning lives on the screen it protects: nothing here may print an
 * evidence vocabulary word, a percentage, a streak or a second filled control.
 */

const CB3_CLASSROOM_COPY = Object.freeze({
  // COPY.md §4 — the classroom rows, verbatim. A template keeps the `{slot}` fill visible.
  back: 'Back to {course}',
  stepper: 'This section',
  stepCurrent: 'Now',
  stepDone: 'Done',
  stepNext: 'Next',
  stepLocked: 'Opens after the check',
  play: 'Play the line',
  checkPrimary: 'Check answer',
  checkEdit: 'Edit answer',
  clearChoice: 'Clear choice',
  clearTicks: 'Clear ticks',
  // Group names (COPY.md §4, SPEC-V3 §5.3 C7): the visible words and the aria-labels of the
  // answer surfaces are these rows, so a group can never be named twice.
  checkChoices: 'Choices',
  checkChecklist: 'Checklist',
  checkAnswers: 'Answers',
  checkCriteria: 'Grading criteria',
  // W2-4 item 35: the check's own door to the tutor. The first press records the assist and asks
  // the one hint question; the status line says where the answer went, never its content.
  checkHint: 'Ask for a hint',
  checkHintPending: 'Asking the tutor for a hint.',
  checkHintRecorded: 'Hint recorded. The tutor has answered in the tutor panel.',
  checkHintFailed: 'The hint could not be recorded. Try again.',
  correct: 'That is right.',
  wrong: 'Not quite.',
  // A grader that could not finish is not a wrong answer: the attempt is saved and the retry is
  // free, so the card says that instead of claiming the learner missed.
  retryGrading: 'This answer could not be graded yet. It is saved, and checking again does not use a new attempt.',
  retry: 'Try again',
  next: 'Next section',
  evidenceTitle: 'Evidence',
  evidenceCount: '{n} of {total} checks recorded',
  evidenceEmpty: 'No checks recorded yet.',
  asideNext: 'Next up: {next}',
  asideTutor: 'Ask the tutor',
  // Practice group names (COPY.md §4, SPEC-V3 §5.3 C8).
  practiceExpressions: 'Expressions to practise',
  practiceTranscript: 'Practice transcript',
  nochatTitle: 'This section has no chat yet',
  nochatBody: 'Start a fresh run to open a chat for this section.',
  nochatAction: 'Start a fresh run',
  completeTitle: 'Section finished',
  completeBody: 'Your check is recorded.',
  // CREATE-EXPERIENCE item 38: an ending is not a receipt. When the commit carried no evidence
  // row (a lane that names a self-reported class, or an answer the backend did not record), the
  // panel still closes the section but never says a result was recorded.
  completeBodyUnrecorded: 'Your check passed, but nothing was recorded for it, so it does not count toward your evidence yet.',
  completeAction: 'Back to the path',
  loading: 'Opening this section.',
  errorTitle: 'This section could not be read',
  errorBody: 'Your attempt is unchanged. Try again.',
  errorAction: 'Try again',
  offlineTitle: 'You are offline',
  offlineBody: 'The page you opened last is still here. Checking an answer waits.',
  gameXp: '{n} XP',
  challengeTitle: 'Field Challenge',
  challengeStart: 'Try it yourself',
  // The aside's action is the door to the check already on this page: it focuses the visible check
  // card and never starts a second question or advances the section. A section with no check
  // renders no action at all, so these rows have no "opening"/"unavailable" states to name.
  // COPY.md §4 has no row for these strings (like `answerLabel` above); the deck gap is reported
  // in the review summary rather than invented elsewhere.
  // SPEC-V3 §5.3 C7 does not name this label and the deck has no row for it (ruling 2026-11-10):
  // the visible words stay identical and the missing row is reported in the review summary,
  // never invented here as a second copy source.
  answerLabel: 'Your answer',
  selected: 'Selected',
  nothingSelected: 'Nothing selected yet.',
  selectedSummary: 'Selected: {n}. {choice}',
  playUnavailable: 'No audio for this line yet.'
})

/** Fill one deck row's `{slot}` without ever printing an empty box. */
function classroomCopy(template, values) {
  let out = String(template || '')
  Object.keys(values || {}).forEach((key) => {
    out = out.split(`{${key}}`).join(String(values[key]))
  })
  return out
}

/**
 * The deck-authored ruby over the bundled L0 pack's line.
 *
 * A reading is never derived from kana (SPEC-V3 §4): only these kanji runs have an authored
 * reading, and a line with any other kanji renders plain. `好き`/`付き合って` are the two words
 * the pack's own worked example uses; nothing else is guessed.
 */
const CB3_CLASSROOM_RUBY = Object.freeze({
  好き: 'すき',
  付き合って: 'つきあって'
})

/** Split one Japanese line into plain runs and ruby runs, in reading order. */
function classroomRubySegments(text) {
  const value = String(text || '')
  if (!value) return []
  const keys = Object.keys(CB3_CLASSROOM_RUBY).sort((left, right) => right.length - left.length)
  const parts = []
  let index = 0
  while (index < value.length) {
    const hit = keys.find((key) => value.startsWith(key, index))
    if (hit) {
      parts.push({ text: hit, ruby: CB3_CLASSROOM_RUBY[hit] })
      index += hit.length
      continue
    }
    let end = index + 1
    while (end < value.length && !keys.some((key) => value.startsWith(key, end))) end += 1
    parts.push({ text: value.slice(index, end) })
    index = end
  }
  return parts
}

const CB3_JAPANESE = /[\u3040-\u30ff\u3400-\u9fff]/
const CB3_KANJI = /[\u3400-\u9fff]/
//: `Speaker: 好きです。 (suki desu.) — "I like you."` — the pack's own authored dialogue shape.
const CB3_DIALOGUE_LINE = /^\s*([^:\n]{1,24}):\s*([^()\n]+?)\s*\(([^()\n]+)\)\s*[—-]\s*["“”']?(.+?)["“”']?\s*$/

/**
 * The lesson's real line, read from the page's authored teaching text.
 *
 * `lesson.page.segments[].text` is the pack's own section content, not model prose and not a
 * transcript. A line qualifies only when it carries all three scaffolds on the same authored
 * line (kana/kanji, romaji in parentheses, the English meaning after a dash). Among qualifying
 * lines the last one containing kanji is preferred: that is the section's target line, and it is
 * the only kind the deck's ruby can sit on. With no qualifying line the bubble is not rendered
 * at all — a decorative quote would be invented content.
 */
function classroomLineFromPage(page) {
  const texts = []
  if (page && Array.isArray(page.segments)) {
    page.segments.forEach((segment) => {
      if (segment && typeof segment.text === 'string') texts.push(segment.text)
    })
  }
  const document = page && page.document
  if (document && Array.isArray(document.blocks)) {
    document.blocks.forEach((block) => {
      if (!block) return
      if (typeof block.deep === 'string') texts.push(block.deep)
      if (typeof block.short === 'string') texts.push(block.short)
    })
  }
  const lines = []
  texts.forEach((text) => {
    String(text)
      .split(/\r?\n/)
      .forEach((line) => {
        const match = CB3_DIALOGUE_LINE.exec(line)
        if (!match) return
        const kana = match[2].trim()
        const romaji = match[3].trim()
        const english = match[4].trim()
        if (!CB3_JAPANESE.test(kana) || !romaji || !english) return
        lines.push({ kana, romaji, english })
      })
  })
  if (lines.length === 0) return null
  const withKanji = lines.filter((line) => CB3_KANJI.test(line.kana))
  const picked = withKanji.length > 0 ? withKanji[withKanji.length - 1] : lines[0]
  return {
    kana: picked.kana,
    romaji: picked.romaji,
    english: picked.english,
    segments: classroomRubySegments(picked.kana)
  }
}

/**
 * The authored prose the classroom shows for one block (CREATE-EXPERIENCE item 33).
 *
 * `short` when the author wrote one, else the first paragraph of `deep` — the same rule the v2
 * player applies (`playerConcept`), so a section does not read differently in the two surfaces.
 * Nothing is summarised, re-flowed or invented here.
 */
function classroomBlockProse(block) {
  if (!block) return ''
  const short = typeof block.short === 'string' ? block.short.trim() : ''
  if (short) return short
  const deep = typeof block.deep === 'string' ? block.deep : ''
  return String(deep).split(/\n\s*\n/)[0].trim()
}

/** The blocks of the served document that carry prose, in the authored order. */
function classroomProseBlocks(page) {
  const document = page && page.document
  const blocks = document && Array.isArray(document.blocks) ? document.blocks : []
  return blocks.filter((block) => Boolean(classroomBlockProse(block)))
}

/**
 * The stepper's nodes, in the plan's own order (SPEC-V3 §5.3 C3, "better than the concept" 3/7).
 *
 * `Done` means the objective reached independent or delayed evidence — the same fact the course
 * home reads. `Now` is the section the lesson page is showing. `locked` is only a plan-recorded
 * gate, never a guess from ordinal alone.
 */
function classroomStepNodes(outline, page) {
  const objectives = outline && Array.isArray(outline.objectives) ? outline.objectives : []
  const currentId = page && page.section ? page.section.objective_id : null
  return objectives
    .filter((objective) => objective && objective.objective_id)
    .map((objective, index) => {
      const done =
        objective.independent === true ||
        objective.state === 'independent_evidence' ||
        objective.state === 'delayed_evidence' ||
        objective.state === 'overridden'
      const locked = objective.locked === true
      const current = objective.objective_id === currentId
      const state = locked ? 'locked' : current ? 'current' : done ? 'done' : 'upcoming'
      return {
        key: objective.objective_id,
        index,
        label: objective.title || '',
        state,
        stateWord:
          state === 'current'
            ? CB3_CLASSROOM_COPY.stepCurrent
            : state === 'locked'
              ? CB3_CLASSROOM_COPY.stepLocked
              : undefined
      }
    })
}

/**
 * `2 of 5 checks recorded`, counted from the served page (COPY.md §4 `classroom.evidence.count`).
 *
 * The denominator is the page's own `checks[]` length and the numerator counts a check with a
 * committed attempt. The event rows keep the integrity states visible: a recorded check prints
 * the class its newest attempt was committed with (`First try, no hints` / `Hinted` /
 * `Answer shown`), never a score.
 */
function classroomEvidence(page) {
  const checks = page && Array.isArray(page.checks) ? page.checks : []
  const attempts = page && Array.isArray(page.attempts) ? page.attempts : []
  const byCheck = {}
  attempts.forEach((attempt) => {
    if (!attempt || !attempt.check_id) return
    const current = byCheck[attempt.check_id]
    if (!current) byCheck[attempt.check_id] = attempt
  })
  const recordedChecks = checks.filter((check) => check && Number(check.attempt_count) > 0)
  const events = []
  recordedChecks.forEach((check) => {
    const attempt = byCheck[check.check_id]
    const label = attempt && attempt.evidence_class ? EVIDENCE_CLASS_COPY[attempt.evidence_class] : null
    if (label) events.push(label)
  })
  return {
    recorded: recordedChecks.length,
    total: checks.length,
    countLabel: classroomCopy(CB3_CLASSROOM_COPY.evidenceCount, {
      n: recordedChecks.length,
      total: checks.length
    }),
    events: Array.from(new Set(events))
  }
}

/**
 * CREATE-EXPERIENCE item 38 — which commit may end the section.
 *
 * The panel existed but nothing ever set `complete`: finishing the last check left the learner on
 * a graded card with no ending, so a finished section read as unfinished work.
 *
 * The rule is the backend's own answer, not a click count. A committed `pass` names the check it
 * closed; the section ends when the served page carries no *other* open check. A newer open check
 * (for example one `progression.challenge_out` just superseded the first with) keeps the section
 * open — the learner has not answered the question on screen yet. A page whose `checks[]` no
 * longer names the passed check (a stale read racing the commit) is not an ending either.
 */
function classroomCompletion(page, passed) {
  const checks = page && Array.isArray(page.checks) ? page.checks : []
  const attempts = page && Array.isArray(page.attempts) ? page.attempts : []
  if (passed && passed.verdict === 'pass') {
    const checkId = passed.checkId || null
    if (checkId && checks.length > 0 && !checks.some((row) => row && row.check_id === checkId)) {
      return null
    }
    const anotherOpen = checks.some(
      (row) => row && row.state === 'open' && (!checkId || row.check_id !== checkId)
    )
    if (anotherOpen) return null
    return { evidence: passed.evidence === true }
  }
  // A revisit has no commit in this session, so the same ending is read back from the recorded
  // rows: every served check has been answered, none is open, and the newest committed attempt is a
  // pass. An override (`overridden`, self-reported) is not a pass and never ends a section here.
  if (!page || checks.length === 0) return null
  if (checks.some((row) => row && row.state === 'open')) return null
  if (!checks.every((row) => row && Number(row.attempt_count) > 0)) return null
  const newestPass = attempts.find((attempt) => attempt && attempt.verdict === 'pass')
  if (!newestPass) return null
  return { evidence: classroomEvidenceRecorded(newestPass) }
}

/**
 * Item 38 — is this section the course's last one?
 *
 * The ending belongs to the course, not to every section: a section with more teaching after it
 * hands the learner on with `Next section` (item 36), so the ending may only stand where the path
 * has nothing after it. A truncated outline is not a finished path, so it never ends a course.
 */
function classroomLastSection(outline, page) {
  if (!outline || outline.truncated === true) return false
  const steps = classroomStepNodes(outline, page)
  if (steps.length === 0) return false
  const currentId = page && page.section ? page.section.objective_id : null
  const at = steps.findIndex((step) => step.key === currentId)
  return at >= 0 && at === steps.length - 1
}

/**
 * Item 38: did this commit write an evidence row?
 *
 * `attempt.submit` answers a committed pass with the attempt it stored; the backend writes the
 * layer-1 evidence row in the same transaction, so an attempt id is the record. A lane that names
 * a non-independent class (`self_reported`, `override`) stores no evidence row, and an answer with
 * no attempt id never committed — both are `false`, and the ending must not claim otherwise.
 */
function classroomEvidenceRecorded(graded) {
  if (!graded || graded.verdict !== 'pass') return false
  if (graded.evidence_id) return true
  if (!graded.attempt_id) return false
  const evidenceClass = String(graded.evidence_class || '')
  if (evidenceClass === 'self_reported' || evidenceClass === 'override') return false
  return true
}

/**
 * The scene's plate: the course world's own section plate, else a typographic field.
 *
 * `world.read` returns the governed kit; a plate is used only when it names this section, so the
 * classroom never borrows another section's art (the swap check, SPEC-V3 §5.3). No world plate
 * means a typographic plate that prints the course title — never an invented cover, and never the
 * host's placeholder image.
 */
function classroomSceneFromWorld(read, sectionId, courseTitle) {
  const world = read && read.world ? read.world : null
  const kit = world && (world.kit || world)
  // world.read serves `assets` (role, section_id, section_key, artifact_id); older drafts used
  // `plates`. Reading only `plates` meant generated world art never reached a lesson and every
  // game lesson fell back to the kit's generic room. Both shapes are accepted here.
  const plates = Array.isArray(kit && kit.assets)
    ? kit.assets
    : Array.isArray(kit && kit.plates)
      ? kit.plates
      : []
  const usable = plates.filter((plate) => plate && (plate.artifact_id || plate.artifactId))
  const match = sectionId
    ? usable.find((plate) => plate.section_id === sectionId || plate.sectionId === sectionId)
    : null
  if (match) {
    return {
      artifactId: match.artifact_id || match.artifactId,
      title: courseTitle || '',
      credit: match.credit || match.attribution || null,
      kind: match.kind || null
    }
  }
  // No plate for this section: the world's own hero is still this course's art, and it is a
  // better answer than a generic room from another subject. Never another section's plate.
  const hero = usable.find((plate) => plate.role === 'hero' || plate.role === 'cover')
  if (hero) {
    return {
      artifactId: hero.artifact_id || hero.artifactId,
      title: courseTitle || '',
      credit: hero.credit || hero.attribution || null,
      kind: hero.kind || null
    }
  }
  return { artifactId: null, title: courseTitle || '', credit: null, kind: null }
}

/** One quiet line of teaching state: never a goal, never a compliment. */
function ClassroomQuietLine({ children, role, ...rest }) {
  return jsx('p', {
    ...rest,
    role: role || undefined,
    style: {
      margin: 0,
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('meta'),
      lineHeight: cb3Lead('meta'),
      color: cb3Role('ink-soft')
    },
    children
  })
}

/**
 * D-007 (UI-K3): which plate the lesson stands in — a real per-section artifact, then the
 * approved kit's lesson room, and only then the typographic field of an older asset segment.
 *
 * Pure, so the chain is testable without an effect: `preview` is the media loader's state and
 * `kitRow` is the resolved `cb3KitSource('field-atlas-lesson-room')` data URL (null when this
 * build's asset segment carries no kit plate).
 */
function classroomSceneSource(scene, preview, kitRow) {
  const artifactId = scene && scene.artifactId ? scene.artifactId : null
  const ready = Boolean(artifactId && preview && preview.state === 'ready' && preview.data_url)
  if (ready) return { kind: 'art', artifactId, src: preview.data_url }
  if (kitRow) return { kind: 'kit', artifactId: 'field-atlas-lesson-room', src: kitRow }
  return { kind: 'type', artifactId: artifactId || 'none', src: null }
}

/**
 * The framed scene (SPEC-V3 §5.3 C5): a mounted plate, 8 px canvas-edge mat, 1 px ink rule and the
 * elevation token from the stylesheet — never a shadow recipe here.
 */
function ClassroomScene({ scene, title, height }) {
  const artifactId = scene && scene.artifactId ? scene.artifactId : null
  // `useArtifactPreview` is declared in the components segment; the call is unconditional so the
  // hook order is stable whether or not this section has a plate (a conditional hook throws).
  const preview = useArtifactPreview(artifactId)
  // D-007 (UI-K3): a section with no plate of its own — or a plate that never became ready —
  // stands in the approved kit's lesson room. A real artifact always wins; the typographic field
  // survives only for a build whose asset segment carries no kit row.
  const source = classroomSceneSource(scene, preview, cb3KitSource('field-atlas-lesson-room'))
  return jsxs('div', {
    'data-cb3-scene': source.kind,
    'data-cb3-scene-artifact': source.artifactId,
    className: 'cb3-card-elevated',
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '100%',
      height: height || '10.25rem',
      padding: '8px',
      backgroundColor: cb3Role('canvas-edge'),
      border: `1px solid ${cb3Role('ink')}`,
      borderRadius: cb3Radius('round'),
      overflow: 'hidden',
      minWidth: 0
    },
    children: [
      source.kind === 'art'
        ? jsx('img', {
            'data-cb3-scene-art': '',
            alt: '',
            'aria-hidden': 'true',
            src: source.src,
            style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover' }
          }, 'art')
        : source.kind === 'kit'
          ? jsx('img', {
              'data-cb3-scene-kit': source.artifactId,
              alt: '',
              'aria-hidden': 'true',
              src: source.src,
              style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover' }
            }, 'kit')
          : jsxs('div', {
              'data-cb3-scene-plate': 'type',
              style: {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '100%',
                paddingInline: '1rem',
                backgroundColor: cb3Role('card-stock'),
                border: `1px solid ${cb3Role('rule')}`,
                borderRadius: cb3Radius('square')
              },
              children: [
                jsx('span', {
                  style: {
                    fontFamily: 'var(--cb3-font-display)',
                    fontSize: cb3Type('heading'),
                    lineHeight: cb3Lead('heading'),
                    fontWeight: 600,
                    maxWidth: '20ch',
                    textAlign: 'center',
                    color: cb3Role('ink')
                  },
                  children: title || ''
                }, 'title')
              ]
            }, 'plate'),
      scene && scene.credit
        ? jsx('span', {
            'data-cb3-scene-credit': '',
            style: {
              position: 'absolute',
              right: '0.75rem',
              bottom: '0.75rem',
              paddingInline: '0.35rem',
              backgroundColor: cb3Role('card-stock'),
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              color: cb3Role('ink-soft')
            },
            children: scene.credit
          }, 'credit')
        : null
    ]
  })
}

/**
 * The deterministic grader's own sentences (`coursebook/validators.py`). They are audit text, not
 * feedback: "does not match an accepted answer" is written for a log, and printing it at a learner
 * is the defect this map closes. The set is deliberately closed — a value that matches is dropped
 * before it can reach the DOM, and a value that does not match is treated as the open lane's
 * authored prose and printed as the reason.
 */
const CB3_GRADER_MACHINE_TEXT = Object.freeze([
  'matches an accepted answer',
  'does not match an accepted answer',
  'no accepted answer is configured for this check',
  'selection matches',
  'selection matches (order-insensitive)',
  'selection does not match an accepted combination',
  'the answer is not a selection',
  'the check has no readable reference value',
  'the answer is not a number this check can read',
  'a unit was given but this check expects a plain number'
])
const CB3_GRADER_MACHINE_PATTERNS = Object.freeze([
  /^within tolerance \(/,
  /^outside tolerance by /,
  /^the answer has no unit; expected /,
  /^the unit .+ is not accepted for this check$/,
  /^cannot convert .+ to .+$/
])

/** Whether one observed value is a deterministic grader's sentence rather than authored prose. */
function classroomGraderMachineText(value) {
  const text = String(value == null ? '' : value).trim()
  if (!text) return false
  return (
    CB3_GRADER_MACHINE_TEXT.indexOf(text) >= 0 ||
    CB3_GRADER_MACHINE_PATTERNS.some((pattern) => pattern.test(text))
  )
}

/** A, B, C … for the served choice at `index`. */
function classroomChoiceLetter(index) {
  return String.fromCharCode(65 + Number(index))
}

/**
 * The accepted choice a grade result names, resolved against the served choices, or `null`.
 *
 * `attempt.submit`'s contracted response carries criteria observations and no reference, so a
 * deterministic selection grader does not say which option it would have accepted. When a grader
 * does name it (an `expected`/`accepted` on the result or on an unmet criterion, as an index, a
 * letter or the choice text), this resolves that name to a served row. When nothing names it the
 * caller says only what the learner chose — the answer is never guessed.
 */
function classroomAcceptedChoice(result, choices) {
  if (!Array.isArray(choices) || choices.length === 0) return null
  const pick = (index) => ({ index, letter: classroomChoiceLetter(index), text: choices[index] })
  const rows = result && Array.isArray(result.criteria) ? result.criteria : []
  // An index is only trusted when the field says it is one; a bare `expected: 1` could be a
  // number, a label, or an answer, so it is never read as a position.
  const indexFields = result ? [result.expected_index, result.accepted_index] : []
  rows.forEach((row) => {
    if (!row || row.met === true) return
    indexFields.push(row.expected_index, row.accepted_index, row.answer_index, row.correct_index)
  })
  for (const index of indexFields) {
    if (Number.isInteger(index) && index >= 0 && index < choices.length) return pick(index)
  }
  const candidates = []
  const push = (value) => {
    if (value !== undefined && value !== null && value !== '') candidates.push(value)
  }
  if (result) {
    push(result.accepted)
    push(result.expected)
  }
  rows.forEach((row) => {
    if (!row || row.met === true) return
    push(row.expected)
    push(row.accepted)
  })
  for (const candidate of candidates) {
    const text = String(candidate).trim()
    if (!text) continue
    if (/^[A-Ha-h]$/.test(text)) {
      const index = text.toUpperCase().charCodeAt(0) - 65
      if (index >= 0 && index < choices.length) return pick(index)
    }
    const exact = choices.findIndex((choice) => String(choice).trim() === text)
    if (exact >= 0) return pick(exact)
    // A choice authored as "A: …" also matches when the grader names just its text.
    const bare = choices.findIndex(
      (choice) => String(choice).replace(/^\s*[A-Ha-h]\s*[:.)-]\s*/, '').trim() === text
    )
    if (bare >= 0) return pick(bare)
  }
  return null
}

/** A served choice's text without its authored letter prefix: the message supplies the letter. */
function classroomChoiceText(choice) {
  return String(choice == null ? '' : choice)
    .replace(/^\s*[A-Ha-h]\s*[:.)-]\s*/, '')
    .trim()
}

/** One sentence ending at the choice's own punctuation, never a doubled full stop. */
function classroomChoiceSentence(choice) {
  const text = classroomChoiceText(choice)
  if (!text) return ''
  return /[.!?。！？]$/.test(text) ? text : `${text}.`
}

/**
 * The miss sentence for a selection check: the learner's own choice, then the accepted choice only
 * when the grade result names one. Never a grader string, never an invented answer.
 */
function classroomSelectionMiss(result, choices, chosenIndex) {
  const chosen =
    Number.isInteger(chosenIndex) && chosenIndex >= 0 && chosenIndex < choices.length
      ? chosenIndex
      : -1
  const accepted = classroomAcceptedChoice(result, choices)
  const chose = chosen >= 0 ? `You chose ${classroomChoiceLetter(chosen)}.` : ''
  if (accepted) {
    return `${chose ? `${chose} ` : ''}The answer is ${accepted.letter}: ${classroomChoiceSentence(accepted.text)}`
  }
  if (chosen >= 0) {
    return `You chose ${classroomChoiceLetter(chosen)}: ${classroomChoiceSentence(choices[chosen])} That is not the answer this check accepts.`
  }
  return 'That choice is not the answer this check accepts.'
}

/**
 * The extra instruction a stimulus carries, or `null` when it only repeats the question.
 *
 * `stimulus.learner_instructions` is an optional field beside the question. When it is the prompt
 * again — or the prompt with a trailing clause — printing both reads as the same question twice.
 * Case, spacing and terminal punctuation do not make a new sentence, so compare on normalized
 * text: drop a leading sentence that is the prompt, and return `null` when nothing is left.
 */
function classroomExtraInstruction(prompt, instructions) {
  const question = String(prompt == null ? '' : prompt).trim()
  const raw = String(instructions == null ? '' : instructions).trim()
  if (!raw) return null
  const norm = (value) =>
    String(value)
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .replace(/[\s.!?。！？:;,\u2014\u2013-]+$/g, '')
  const questionNorm = norm(question)
  if (!questionNorm) return raw
  const instructionNorm = norm(raw)
  if (!instructionNorm || instructionNorm === questionNorm) return null
  // The instructions are the question again with a clause on the end: keep only the new clause.
  if (instructionNorm.startsWith(questionNorm)) {
    const kept = raw
      .split(/(?<=[.!?\u3002\uff01\uff1f])\s+/)
      .map((sentence) => sentence.trim())
      .filter((sentence) => sentence && norm(sentence) !== questionNorm)
    return kept.length > 0 ? kept.join(' ') : null
  }
  // The instructions say nothing the question does not already say.
  if (questionNorm.includes(instructionNorm)) return null
  return raw
}

/** One observed clause as a whole sentence: capitalised once, terminated once. */
function classroomObservedSentence(value) {
  const text = String(value == null ? '' : value).trim()
  if (!text) return ''
  const cased = /^[a-z]/.test(text) ? `${text.charAt(0).toUpperCase()}${text.slice(1)}` : text
  return /[.!?\u3002\uff01\uff1f]$/.test(cased) ? cased : `${cased}.`
}

/**
 * One verdict line: the deck's sentence plus only the observation a learner can act on.
 *
 * CREATE-EXPERIENCE item 34: a selection check branches on the served format. Its message is
 * composed from the chosen row and (when the result names it) the accepted row; the deterministic
 * grader's sentence never reaches the DOM. A free-text check keeps the authored observation the
 * open lane wrote — that is prose, and it is the reason the learner needs.
 */
function classroomVerdictSentence(result, stimulus, chosenIndex) {
  if (!result) return null
  const choices =
    stimulus && Array.isArray(stimulus.choices)
      ? stimulus.choices.filter((choice) => String(choice || '').trim())
      : []
  const selection =
    Boolean(stimulus) && String(stimulus.format || '') === 'selection' && choices.length > 0
  const criteria = Array.isArray(result.criteria) ? result.criteria : []
  const observed = criteria
    .filter((item) => item && item.observed)
    .map((item) => String(item.observed).trim())
    .filter((value) => Boolean(value) && !classroomGraderMachineText(value))
  const why = observed.length > 0 ? observed[0] : null
  if (result.verdict === 'pass') {
    if (selection) return CB3_CLASSROOM_COPY.correct
    return why ? `${CB3_CLASSROOM_COPY.correct} ${classroomObservedSentence(why)}` : CB3_CLASSROOM_COPY.correct
  }
  if (result.verdict === 'needs_retry') return CB3_CLASSROOM_COPY.retryGrading
  if (result.verdict === 'partial' || result.verdict === 'not_yet') {
    if (selection) return classroomSelectionMiss(result, choices, chosenIndex)
    return why ? `${CB3_CLASSROOM_COPY.wrong} ${classroomObservedSentence(why)}` : CB3_CLASSROOM_COPY.wrong
  }
  return null
}

/**
 * The check card (SPEC-V3 §5.3 C7): one paper card, the served question, the answer surface the
 * stimulus names, and the screen's **only** filled control.
 *
 * It deliberately shares no state machine with `AttemptControls`: that component is the v2 answer
 * pane pinned by H-149/H-178 and is still mounted in two v2 surfaces. This is the v3 composition,
 * with the same backend commands and the same fences (`expectedRevision`, one `attempt_nonce` per
 * answer, a fresh nonce only on `Try again`), so the kernel sees identical input.
 */
function ClassroomCheckCard({
  check,
  stimulusStatus = 'ready',
  stimulusError = null,
  enrollmentId,
  objectiveId,
  revision,
  onRevision,
  onRetryStimulus,
  onCommitted,
  onVerdict,
  onNextSection,
  busyLabel
}) {
  const [text, setText] = useState('')
  const [ticked, setTicked] = useState([])
  const [selected, setSelected] = useState(-1)
  const [phase, setPhase] = useState('awaiting_input')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const nonceRef = useRef(null)
  const verdictRef = useRef(null)

  const stimulus = check ? check.stimulus || null : null
  // The served stimulus can carry `learner_instructions` beside its `prompt`. When the instructions
  // are the question again (or the question plus a clause), printing both reads as the same
  // question twice; the card prints the question once and an instruction only when it adds
  // something the question does not already say.
  const extraInstruction = classroomExtraInstruction(
    stimulus && stimulus.prompt,
    stimulus && stimulus.learner_instructions
  )
  const items = checklistItems(stimulus)
  const choices =
    stimulus && stimulus.format === 'selection' && Array.isArray(stimulus.choices)
      ? stimulus.choices.filter((choice) => String(choice || '').trim())
      : []
  const kind = items.length > 0 ? 'verification' : choices.length > 0 ? 'selection' : 'text'
  const ready = stimulusStatus === 'ready' && Boolean(stimulus)
  const selectedChoice = kind === 'selection' && selected >= 0 && selected < choices.length ? choices[selected] : null
  const locked = phase === 'submitting'
  const canCheck =
    ready &&
    !locked &&
    (kind === 'verification' ? ticked.length > 0 : kind === 'selection' ? selectedChoice !== null : text.trim().length > 0)

  useEffect(() => {
    if (phase === 'graded' || phase === 'wrong') {
      verdictRef.current?.focus?.({ preventScroll: true })
    }
  }, [phase])

  const submit = useCallback(async () => {
    if (!check || !canCheck) return
    const answer =
      kind === 'verification' ? checklistAnswer(ticked) : kind === 'selection' ? choiceAnswer(selectedChoice) : attemptAnswer(text.trim())
    if (!nonceRef.current) nonceRef.current = newOperationId('attempt')
    setPhase('submitting')
    setError(null)
    const response = await rpc(
      'attempt.submit',
      {
        enrollment_id: enrollmentId,
        check_id: check.check_id,
        check_version: check.check_version,
        attempt_nonce: nonceRef.current,
        answer
      },
      {
        idempotencyKey: `cb-attempt-${check.check_id}-${nonceRef.current}`,
        expectedRevision: Number(revision) || 0
      }
    )
    if (!response.ok) {
      setError(response.error)
      setPhase('awaiting_input')
      return
    }
    const graded = response.result
    setResult(graded)
    setPhase(graded.verdict === 'pass' ? 'graded' : 'wrong')
    if (onVerdict) onVerdict(graded.verdict)
    if (onCommitted) onCommitted(graded)
  }, [check, canCheck, kind, ticked, selectedChoice, text, enrollmentId, revision, onCommitted, onVerdict])

  const tryAgain = useCallback(() => {
    nonceRef.current = null
    setResult(null)
    setError(null)
    setPhase('awaiting_input')
  }, [])

  const moveOn = useCallback(() => {
    if (onNextSection) onNextSection()
  }, [onNextSection])

  /**
   * Item 35: a hint is a hint.
   *
   * A press writes the learner's own `hint_request` through `lesson.assist` (the check's revision
   * fence is current here), adopts the bumped revision, and only then hands the one hint question
   * to the tutor rail. The answer is the tutor's, rendered in the rail this press reveals; the card
   * states that the hint was recorded and where it went. The check still owns the verdict.
   */
  const [hintState, setHintState] = useState(null)
  const hintCheckId = check && check.check_id ? check.check_id : null
  const hintCheckRef = useRef(null)
  useEffect(() => {
    // A section's check is the boundary; a transient null while `check.open` re-reads after the
    // assist's revision bump is not a new check and must not wipe the recorded line.
    if (!hintCheckId) return
    if (hintCheckRef.current && hintCheckRef.current !== hintCheckId) setHintState(null)
    hintCheckRef.current = hintCheckId
  }, [hintCheckId])
  const hintAvailable =
    Boolean(check) &&
    !locked &&
    hintState !== 'asking' &&
    hintState !== 'recorded' &&
    backendSupports('lesson.assist') &&
    backendSupports('tutor.ask')
  const askHint = useCallback(async () => {
    if (!check || hintState === 'asking' || hintState === 'recorded') return
    setHintState('asking')
    setError(null)
    const response = await rpc(
      'lesson.assist',
      { enrollment_id: enrollmentId, objective_id: objectiveId, kind: 'hint_request' },
      { idempotencyKey: newOperationId('assist'), expectedRevision: Number(revision) || 0 }
    )
    if (!response.ok) {
      setHintState('failed')
      return
    }
    const bumped = response.result ? Number(response.result.revision) : NaN
    if (Number.isFinite(bumped) && bumped > 0 && onRevision) onRevision(bumped)
    setHintState('recorded')
    requestTutorHint()
  }, [check, hintState, enrollmentId, objectiveId, revision, onRevision])

  const primary =
    phase === 'graded'
      ? { label: CB3_CLASSROOM_COPY.next, onClick: moveOn }
      : phase === 'wrong'
        ? { label: CB3_CLASSROOM_COPY.retry, onClick: tryAgain }
        : { label: CB3_CLASSROOM_COPY.checkPrimary, onClick: submit }

  const toggleTick = (id) => {
    if (locked) return
    setTicked((previous) => (previous.includes(id) ? previous.filter((item) => item !== id) : previous.concat(id)))
  }

  const card = jsxs('div', {
    'data-cb3-surface': 'check',
    'data-cb3-check': kind,
    'data-cb3-check-phase': phase,
    className: 'cb3-card',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      padding: '1.25rem',
      backgroundColor: cb3Role('card-stock'),
      border: `1px solid ${cb3Role('rule')}`,
      borderRadius: cb3Radius('round'),
      color: cb3Role('ink'),
      minWidth: 0
    },
    children: [
      stimulus && stimulus.prompt
        ? jsx('p', {
            'data-cb3-question': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('lead'),
              lineHeight: cb3Lead('lead'),
              maxWidth: '60ch'
            },
            children: stimulus.prompt
          }, 'question')
        : null,

      extraInstruction
        ? jsx('p', {
            'data-cb3-instructions': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft'),
              maxWidth: '60ch'
            },
            children: extraInstruction
          }, 'instructions')
        : null,

      !ready
        ? jsxs('div', {
            'data-cb3-check-read': stimulusStatus,
            style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
            children: [
              jsx(ClassroomQuietLine, {
                role: 'status',
                children:
                  stimulusStatus === 'loading'
                    ? busyLabel || CB3_CLASSROOM_COPY.loading
                    : stimulusUnavailableDescription(stimulusError)
              }),
              typeof onRetryStimulus === 'function' && stimulusStatus === 'unavailable'
                ? jsx(PillAction, { variant: 'quiet', label: CB3_CLASSROOM_COPY.errorAction, onClick: onRetryStimulus }, 'retry')
                : null
            ]
          }, 'read')
        : null,

      ready && kind === 'verification'
        ? jsx('div', {
            role: 'group',
            'data-cb3-answer': 'verification',
            style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
            children: items.map((item, index) =>
              jsxs('label', {
                'data-cb3-item': item.id,
                style: {
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  minHeight: '44px',
                  paddingInline: '0.5rem',
                  border: `1px solid ${cb3Role('rule')}`,
                  borderRadius: cb3Radius('soft'),
                  cursor: locked ? 'not-allowed' : 'pointer',
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('body'),
                  lineHeight: cb3Lead('body')
                },
                children: [
                  jsx('input', {
                    type: 'checkbox',
                    checked: ticked.includes(item.id),
                    disabled: locked,
                    onChange: () => toggleTick(item.id),
                    style: { width: '24px', height: '24px', accentColor: cb3Role('terracotta') }
                  }, 'box'),
                  jsx('span', { children: item.label }, 'label')
                ]
              }, `item-${index}`)
            )
          }, 'verification')
        : null,

      ready && kind === 'selection'
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
            children: [
              jsx('div', {
                role: 'radiogroup',
                'aria-label': CB3_CLASSROOM_COPY.checkChoices,
                'data-cb3-answer': 'selection',
                style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
                children: choices.map((choice, index) =>
                  jsxs('label', {
                    'data-cb3-choice': index + 1,
                    'data-cb3-choice-selected': selected === index ? 'true' : 'false',
                    style: {
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.6rem',
                      minHeight: '44px',
                      paddingInline: '0.5rem',
                      border: `1px solid ${cb3Role(selected === index ? 'terracotta' : 'rule')}`,
                      borderRadius: cb3Radius('soft'),
                      cursor: locked ? 'not-allowed' : 'pointer',
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('body'),
                      lineHeight: cb3Lead('body')
                    },
                    children: [
                      jsx('input', {
                        type: 'radio',
                        name: 'cb3-classroom-choice',
                        checked: selected === index,
                        disabled: locked,
                        onChange: () => setSelected(index),
                        style: { width: '20px', height: '20px', accentColor: cb3Role('terracotta') }
                      }, 'radio'),
                      jsx('span', { 'aria-hidden': 'true', children: String(index + 1) }, 'number'),
                      jsx('span', { children: choice }, 'text'),
                      selected === index
                        ? jsx('span', {
                            style: {
                              marginInlineStart: 'auto',
                              fontFamily: 'var(--cb3-font-ui)',
                              fontSize: cb3Type('meta'),
                              lineHeight: cb3Lead('meta'),
                              fontWeight: 600
                            },
                            children: CB3_CLASSROOM_COPY.selected
                          }, 'word')
                        : null
                    ]
                  }, `choice-${index}`)
                )
              }, 'choices'),
              jsx(ClassroomQuietLine, {
                role: 'status',
                children: selectedChoice
                  ? classroomCopy(CB3_CLASSROOM_COPY.selectedSummary, { n: selected + 1, choice: selectedChoice })
                  : CB3_CLASSROOM_COPY.nothingSelected
              }, 'summary')
            ]
          }, 'selection')
        : null,

      ready && kind === 'text'
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem' },
            children: [
              jsx('label', {
                htmlFor: 'cb3-classroom-answer',
                style: {
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: cb3Lead('meta'),
                  color: cb3Role('ink-soft')
                },
                children: CB3_CLASSROOM_COPY.answerLabel
              }, 'label'),
              jsx('textarea', {
                id: 'cb3-classroom-answer',
                'data-cb3-answer': 'text',
                value: text,
                rows: 3,
                disabled: locked || !ready,
                onChange: (event) => setText(event.target.value),
                style: {
                  width: '100%',
                  minHeight: '44px',
                  padding: '0.6rem',
                  backgroundColor: cb3Role('card-stock'),
                  border: `1px solid ${cb3Role('rule')}`,
                  borderRadius: cb3Radius('soft'),
                  color: cb3Role('ink'),
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('body'),
                  lineHeight: cb3Lead('body'),
                  resize: 'vertical'
                }
              }, 'field')
            ]
          }, 'text')
        : null,

      error
        ? jsx(ClassroomQuietLine, {
            role: 'alert',
            children: `${error.code || 'ERROR'}: ${describeError(error)}`
          }, 'error')
        : null,

      result
        ? jsx('p', {
            ref: verdictRef,
            tabIndex: -1,
            role: 'status',
            'data-cb3-verdict': result.verdict,
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('body'),
              lineHeight: cb3Lead('body'),
              color: result.verdict === 'pass' ? cb3Role('ink') : cb3Role('alert'),
              maxWidth: '60ch'
            },
            children: classroomVerdictSentence(result, stimulus, selected)
          }, 'verdict')
        : null,

      jsxs('div', {
        'data-cb3-hint-row': hintState || 'available',
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem 0.75rem' },
        children: [
          hintState === 'recorded'
            ? jsx(ClassroomQuietLine, {
                role: 'status',
                'data-cb3-hint': 'recorded',
                children: CB3_CLASSROOM_COPY.checkHintRecorded
              }, 'recorded')
            : jsx(PillAction, {
                'data-cb3-hint': hintState === 'asking' ? 'asking' : hintState === 'failed' ? 'failed' : 'available',
                variant: 'quiet',
                label: hintState === 'asking' ? CB3_CLASSROOM_COPY.checkHintPending : CB3_CLASSROOM_COPY.checkHint,
                disabled: !hintAvailable,
                onClick: askHint
              }, 'ask'),
          hintState === 'failed'
            ? jsx(ClassroomQuietLine, {
                role: 'alert',
                'data-cb3-hint': 'failed-note',
                children: CB3_CLASSROOM_COPY.checkHintFailed
              }, 'failed')
            : null
        ]
      }, 'hint'),

      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' },
        children: [
          jsx(PillAction, {
            'data-cb3-primary': '',
            variant: 'primary',
            label: primary.label,
            disabled: phase === 'submitting' || (phase === 'awaiting_input' && !canCheck),
            busy: phase === 'submitting',
            onClick: primary.onClick
          }, 'primary'),
          phase === 'awaiting_input' && ready && kind !== 'text'
            ? jsx(PillAction, {
                variant: 'quiet',
                label: kind === 'selection' ? CB3_CLASSROOM_COPY.clearChoice : CB3_CLASSROOM_COPY.clearTicks,
                onClick: () => (kind === 'selection' ? setSelected(-1) : setTicked([]))
              }, 'clear')
            : null
        ]
      }, 'actions')
    ]
  })

  return card
}

/**
 * The classroom surface (SPEC-V3 §5.3). Pure: every fact arrives as a prop, so the render test can
 * mount each matrix state without a backend and the container below is the only place that reads.
 */
function ClassroomV3({
  row,
  outline,
  page,
  check,
  stimulusStatus = 'ready',
  stimulusError = null,
  mode = 'guided',
  engagement = null,
  award = null,
  scene = null,
  state = 'default',
  evidenceRecorded = null,
  chatAvailable = true,
  gameRows = [],
  enrollmentId,
  objectiveId,
  revision,
  onRevision,
  onBack,
  onOpenSection,
  onNextSection,
  onStartChat,
  onAskTutor,
  onPlayLine,
  onRetry,
  onRetryStimulus,
  onCommitted
}) {
  const width = useCbViewportWidth()
  const wide = width >= 1000
  const compact = width > 0 && width < 620
  const courseTitle = (row && row.title) || (page && page.course && page.course.title) || ''
  const section = page && page.section ? page.section : null
  const steps = classroomStepNodes(outline, page)
  const evidence = classroomEvidence(page)
  const line = classroomLineFromPage(page)
  const game = mode === 'game'
  const [verdict, setVerdict] = useState(null)
  // CREATE-EXPERIENCE item 33: the default modes read the lesson's authored document, one block at
  // a time. `document.blocks` was never read here, so the reading column was a scene, a line and a
  // quiz. The index is local to the section and resets when the section changes; a page with no
  // blocks renders exactly what it rendered before.
  const proseBlocks = classroomProseBlocks(page)
  const [blockIndex, setBlockIndex] = useState(0)
  useEffect(() => {
    setBlockIndex(0)
  }, [objectiveId])
  const proseAt = proseBlocks.length > 0 ? Math.min(blockIndex, proseBlocks.length - 1) : -1
  const proseBlock = proseAt >= 0 ? proseBlocks[proseAt] : null
  const proseText = classroomBlockProse(proseBlock)
  const proseLast = proseAt === proseBlocks.length - 1
  const checkRef = useRef(null)
  const continueProse = useCallback(() => {
    if (!proseLast) {
      setBlockIndex(proseAt + 1)
      return
    }
    // The last block's Continue is the door to the check: scroll to it and put focus on it, so a
    // keyboard user lands where the reading was pointing instead of at the top of the column.
    const node = checkRef.current
    if (node && typeof node.scrollIntoView === 'function') node.scrollIntoView({ block: 'start' })
    if (node && typeof node.focus === 'function') node.focus({ preventScroll: true })
  }, [proseAt, proseLast])
  // The next section in the plan's own order (CREATE-EXPERIENCE item 36). The post-pass primary
  // carries that objective id up to the route; on the last section the id is null and the route
  // falls back to the course path.
  const currentSectionId = section && section.objective_id ? section.objective_id : objectiveId
  const currentStepAt = steps.findIndex((step) => step.key === currentSectionId)
  const nextSectionId =
    currentStepAt >= 0 && currentStepAt + 1 < steps.length ? steps[currentStepAt + 1].key : null
  const advanceSection = useCallback(() => {
    if (typeof onNextSection === 'function') onNextSection(nextSectionId)
  }, [nextSectionId, onNextSection])
  const foxPose = verdict === 'pass' ? 'cheer' : verdict && verdict !== 'pass' ? 'think' : 'read'
  const nextStep = row && row.next_step && row.next_step.label ? row.next_step.label : null
  // The aside's `Try it yourself` is a door to the check already on this page, not a second
  // question and not the next section. It scrolls to the check card and puts focus on the card
  // itself (the slot is `tabIndex={-1}`), so a keyboard user lands where the action pointed.
  // Nothing here starts a challenge or advances a section; a section with no check renders no
  // control at all (see `aside` below).
  const focusCheck = useCallback(() => {
    const node = checkRef.current
    if (!node) return
    if (typeof node.scrollIntoView === 'function') node.scrollIntoView({ block: 'start' })
    if (typeof node.focus === 'function') node.focus({ preventScroll: true })
  }, [])
  // WIRE-9: the award sentence is the backend's own points plus, when the backend supplies one,
  // its own `basis` sentence. Nothing here computes a number. With no basis the line is the
  // number and `XP` only — never a manufactured explanation — and a refused award is `null`,
  // which renders nothing at all.
  const awardPoints = award && Number(award.points) > 0 ? Number(award.points) : 0
  const awardLine = awardPoints
    ? award.basis
      ? `${classroomCopy(CB3_CLASSROOM_COPY.gameXp, { n: awardPoints })}: ${award.basis}`
      : classroomCopy(CB3_CLASSROOM_COPY.gameXp, { n: awardPoints })
    : null

  const handleVerdict = useCallback(
    (value) => {
      // `ClassroomCheckCard` reports the whole graded result through `onCommitted`; the fox reads
      // the verdict word, not the object, so a pass cheers and a miss thinks.
      setVerdict(value && value.verdict ? value.verdict : value)
      if (onCommitted) onCommitted(value)
    },
    [onCommitted]
  )

  const stepper = jsxs('nav', {
    'aria-label': CB3_CLASSROOM_COPY.stepper,
    'data-cb3-stepper': wide ? 'column' : 'strip',
    style: {
      display: 'flex',
      flexDirection: wide ? 'column' : 'row',
      alignItems: wide ? 'center' : 'flex-start',
      gap: wide ? '0.85rem' : '0.5rem',
      overflowX: wide ? 'visible' : 'auto',
      paddingBlock: wide ? 0 : '0.25rem',
      minWidth: 0
    },
    children: steps.map((step) =>
      jsx(StampNode, {
        state: step.state,
        label: step.label,
        stateWord: step.stateWord,
        index: step.index,
        onClick: () => onOpenSection && onOpenSection(step.key)
      }, step.key)
    )
  })

  const head = jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: [
      jsxs('div', {
        style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.75rem' },
        children: [
          jsx('h2', {
            'data-cb3-classroom-title': '',
            // CP-040 residual: the route shell prints the page title as the surface's only `h1`
            // (`Course` for an open course); every region under it is an `h2`. The classroom's own
            // title was an `h1`, so the section shipped two page titles and its heading order was
            // 1, 1, 3. The type role is unchanged; only the level is corrected.
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              maxWidth: '34ch',
              overflowWrap: 'anywhere'
            },
            children: courseTitle
          }, 'title'),
          game && engagement
            ? jsxs('span', {
                'data-cb3-xp': String(Number(engagement.xp_total) || 0),
                style: {
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: cb3Lead('meta'),
                  fontWeight: 600,
                  color: cb3Role('ink')
                },
                children: [
                  jsx(sdk.Codicon, { name: 'flame', size: CB_ICON_UI }, 'icon'),
                  jsx('span', {
                    children: classroomCopy(CB3_CLASSROOM_COPY.gameXp, { n: Number(engagement.xp_total) || 0 })
                  }, 'label')
                ]
              }, 'xp')
            : null
        ]
      }),
      game && awardLine
        ? jsx('p', {
            'data-cb3-award': String(awardPoints),
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft'),
              maxWidth: '70ch'
            },
            children: awardLine
          }, 'award')
        : null,
      section
        ? jsx('p', {
            'data-cb3-classroom-section': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('body'),
              lineHeight: cb3Lead('body'),
              color: cb3Role('ink-soft'),
              maxWidth: '70ch'
            },
            children: section.title
          }, 'section')
        : null,
      state === 'loading' ? jsx(ClassroomQuietLine, { role: 'status', children: CB3_CLASSROOM_COPY.loading }) : null
    ]
  })

  const statePanel =
    state === 'error' || state === 'offline'
      ? jsxs('div', {
          'data-cb3-classroom-state': state,
          className: 'cb3-card',
          style: {
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            padding: '1rem',
            border: `1px solid ${cb3Role('rule')}`,
            borderRadius: cb3Radius('round'),
            backgroundColor: cb3Role('card-stock')
          },
          children: [
            jsx('p', {
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-ui)',
                fontSize: cb3Type('body'),
                lineHeight: cb3Lead('body'),
                fontWeight: 600
              },
              children: state === 'offline' ? CB3_CLASSROOM_COPY.offlineTitle : CB3_CLASSROOM_COPY.errorTitle
            }, 'title'),
            jsx(ClassroomQuietLine, {
              children: state === 'offline' ? CB3_CLASSROOM_COPY.offlineBody : CB3_CLASSROOM_COPY.errorBody
            }, 'body'),
            jsx(PillAction, { variant: 'quiet', label: CB3_CLASSROOM_COPY.errorAction, onClick: onRetry }, 'retry')
          ]
        }, 'state')
      : null

  const nochat =
    chatAvailable === false && state === 'default'
      ? jsxs('div', {
          'data-cb3-classroom-state': 'no-chat',
          style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
          children: [
            jsx('p', {
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-ui)',
                fontSize: cb3Type('body'),
                lineHeight: cb3Lead('body'),
                fontWeight: 600
              },
              children: CB3_CLASSROOM_COPY.nochatTitle
            }, 'title'),
            jsx(ClassroomQuietLine, { children: CB3_CLASSROOM_COPY.nochatBody }, 'body'),
            jsx(PillAction, { variant: 'quiet', label: CB3_CLASSROOM_COPY.nochatAction, onClick: onStartChat }, 'action')
          ]
        }, 'nochat')
      : null

  const complete =
    state === 'complete'
      ? jsxs('div', {
          'data-cb3-classroom-state': 'complete',
          className: 'cb3-card',
          style: {
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
            padding: '1.25rem',
            border: `1px solid ${cb3Role('rule')}`,
            borderRadius: cb3Radius('round'),
            backgroundColor: cb3Role('card-stock')
          },
          children: [
            jsx('p', {
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-display)',
                fontSize: cb3Type('heading'),
                lineHeight: cb3Lead('heading'),
                fontWeight: 600
              },
              children: CB3_CLASSROOM_COPY.completeTitle
            }, 'title'),
            jsx(ClassroomQuietLine, {
              'data-cb3-complete-evidence': evidenceRecorded === true ? 'recorded' : 'unrecorded',
              // Item 38: the copy is the record, not a receipt printed on hope. A pass whose
              // commit stored no evidence row says exactly that instead of "recorded".
              children:
                evidenceRecorded === true
                  ? CB3_CLASSROOM_COPY.completeBody
                  : CB3_CLASSROOM_COPY.completeBodyUnrecorded
            }, 'body'),
            jsx(PillAction, {
              variant: 'primary',
              label: CB3_CLASSROOM_COPY.completeAction,
              // "Back to the path" is always the path: a finished section never auto-opens another.
              onClick: () => {
                if (typeof onNextSection === 'function') onNextSection(null)
              }
            }, 'action')
          ]
        }, 'complete')
      : null

  const checkCard =
    state === 'default' && !complete
      ? jsx('div', {
          ref: checkRef,
          tabIndex: -1,
          'data-cb3-check-slot': '',
          style: { minWidth: 0 },
          children: jsx(ClassroomCheckCard, {
            check,
            stimulusStatus,
            stimulusError,
            enrollmentId,
            objectiveId,
            revision,
            onRevision,
            onRetryStimulus,
            onCommitted: handleVerdict,
            onNextSection: advanceSection,
            busyLabel: CB3_CLASSROOM_COPY.loading
          }, check && check.check_id ? `check-${check.check_id}` : 'check')
        }, check && check.check_id ? `check-slot-${check.check_id}` : 'check-slot')
      : null

  const aside = jsxs('aside', {
    'data-cb3-aside': '',
    // A complementary landmark must carry a name (the v2 Field rail is "Section details"). The
    // classroom's aside is the same region under the new composition: evidence, the next real stop
    // and the tutor door.
    'aria-label': 'Section details',
    style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: 0 },
    children: [
      game && check && checkCard
        ? jsx(ChallengeCard, {
            title: CB3_CLASSROOM_COPY.challengeTitle,
            // A section with no check renders no control: there is nothing on this page for the
            // action to open, and inventing a question here would be a second check.
            recordNote: engagement ? classroomCopy(CB3_CLASSROOM_COPY.gameXp, { n: Number(engagement.xp_total) || 0 }) : null,
            actionLabel: CB3_CLASSROOM_COPY.challengeStart,
            onStart: focusCheck
          }, 'challenge')
        : null,
      game && Array.isArray(gameRows) && gameRows.length > 0
        ? jsx('ul', {
            'data-cb3-game-rows': '',
            style: {
              margin: 0,
              paddingInlineStart: '1rem',
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink-soft')
            },
            children: gameRows.map((entry, index) =>
              jsx('li', { children: entry && entry.label ? entry.label : '' }, `game-row-${index}`)
            )
          }, 'game-rows')
        : null,
      jsx(EvidenceTray, {
        countLabel: evidence.recorded > 0 || evidence.total > 0 ? evidence.countLabel : null,
        recorded: evidence.recorded,
        emptyLabel: CB3_CLASSROOM_COPY.evidenceEmpty,
        events: evidence.events
      }, 'evidence'),
      nextStep
        ? jsx(ClassroomQuietLine, {
            children: classroomCopy(CB3_CLASSROOM_COPY.asideNext, { next: nextStep })
          }, 'next')
        : null,
      typeof onAskTutor === 'function'
        ? jsx(PillAction, { variant: 'quiet', label: CB3_CLASSROOM_COPY.asideTutor, onClick: onAskTutor, 'data-cb-aside-tutor': '' }, 'tutor')
        : null,
      jsx(FoxPose, { pose: foxPose, size: wide ? 96 : 88 }, 'fox')
    ]
  })

  return jsxs('div', {
    'data-cb-classroom': '',
    'data-cb3-surface': 'classroom',
    'data-cb3-classroom-mode': game ? 'game' : mode,
    'data-cb3-classroom-state': state,
    className: 'cb3-gutter',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
      paddingBlock: '1rem',
      minWidth: 0,
      fontFamily: 'var(--cb3-font-ui)',
      color: cb3Role('ink')
    },
    children: [
      jsx(PillAction, {
        variant: 'quiet',
        icon: 'arrow-left',
        label: classroomCopy(CB3_CLASSROOM_COPY.back, { course: courseTitle }),
        onClick: onBack,
        style: { alignSelf: 'flex-start' }
      }, 'back'),
      head,
      jsxs('div', {
        style: wide
          ? {
              display: 'grid',
              gridTemplateColumns: '96px minmax(0, 1fr) 268px',
              columnGap: '24px',
              alignItems: 'start',
              minWidth: 0
            }
          : {
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              minWidth: 0
            },
        children: [
          jsx('div', { 'data-cb3-stepper-column': wide ? 'wide' : 'flow', style: { minWidth: 0 }, children: stepper }, 'stepper'),
          jsxs('div', {
            'data-cb3-reading': '',
            // CP-040 residual: the shell's skip path lands on the reading column when the surface
            // has one. This is that column under the v3 composition, so it carries the shared
            // marker the skip link already looks for; without it the skip link fell back to `main`
            // and a keyboard user had to tab past the stepper and the header to reach the lesson.
            'data-cb-reading-column': '',
            style: { display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 },
            children: [
              jsx(ClassroomScene, {
                scene,
                title: courseTitle,
                height: wide ? '16rem' : compact ? '8.95rem' : '17.75rem'
              }, 'scene'),
              line && !compact
                ? jsx(DialogueBubble, {
                    segments: line.segments,
                    romaji: line.romaji,
                    en: line.english,
                    onPlay: typeof onPlayLine === 'function' ? onPlayLine : undefined,
                    playLabel: typeof onPlayLine === 'function' ? CB3_CLASSROOM_COPY.play : undefined
                  }, 'line')
                : line && compact
                  ? jsx(DialogueBubble, {
                      segments: line.segments,
                      romaji: line.romaji,
                      en: line.english
                    }, 'line-compact')
                  : null,
              // CREATE-EXPERIENCE item 33: the authored prose of the current block, at the
              // reader's own measure, between the scene/line and the check. With no document
              // blocks this renders nothing and the column is exactly what it was.
              proseText
                ? jsxs('section', {
                    'data-cb3-prose': (proseBlock && proseBlock.id) || '',
                    'aria-label': 'Lesson text',
                    style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', minWidth: 0 },
                    children: [
                      jsx('div', {
                        'data-cb3-prose-step': String(proseAt + 1),
                        style: {
                          fontFamily: 'var(--cb3-font-ui)',
                          fontSize: cb3Type('meta'),
                          lineHeight: cb3Lead('meta'),
                          fontWeight: 600,
                          color: cb3Role('ink-soft')
                        },
                        children: `Step ${proseAt + 1} of ${proseBlocks.length}`
                      }, 'step'),
                      jsx(ProseText, {
                        'data-cb3-prose-body': '',
                        style: {
                          maxWidth: CB_MEASURE,
                          fontFamily: 'var(--cb3-font-display)',
                          fontSize: cb3Type('body'),
                          lineHeight: cb3Lead('body'),
                          color: cb3Role('ink')
                        },
                        text: proseText
                      }, 'body'),
                      jsx(PillAction, {
                        'data-cb3-prose-continue': proseLast ? 'check' : 'next',
                        'aria-label': proseLast ? 'Continue to the check' : 'Continue to the next part',
                        variant: 'quiet',
                        label: 'Continue',
                        onClick: continueProse,
                        style: { alignSelf: 'flex-start' }
                      }, 'continue')
                    ]
                  }, 'prose')
                : null,
              nochat,
              statePanel,
              complete,
              checkCard
            ]
          }, 'reading'),
          aside
        ]
      })
    ]
  })
}

/**
 * The wired classroom: one place that reads, one place that composes.
 *
 * Reads are the same ones the v2 lesson pane makes, keyed so a section switch refetches:
 * `course.outline` (the stepper), `lesson.page` (scene text, checks, attempts), `check.open` +
 * `check.get` through `useOpenCheck` (the answer surface), `world.read` (the section plate) and,
 * only in Game mode, `engagement.read` (XP and the challenge). Nothing here invents a row: a read
 * that fails paints the error state, never an empty lesson.
 */
function ClassroomV3Surface({
  row,
  enrollmentId,
  objectiveId,
  mode = 'guided',
  onBack,
  onOpenSection,
  onNextSection,
  onStartChat,
  onAskTutor,
  onPlayLine
}) {
  const courseId = row && row.course_id ? row.course_id : null
  // GM-010/UX-2: the device switch the settings sheet names must be the one the classroom obeys.
  // Reading the same preference here keeps the copy honest: with Game feedback off the XP chip,
  // the level and the award line disappear (the ledger row is still written by the backend), and
  // the Field Challenge — gameplay, not feedback — stays.
  const [homePrefs] = useCbHomePrefs()
  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: enrollmentId },
    `cb3-classroom-outline-${enrollmentId}`,
    Boolean(enrollmentId) && backendSupports('course.outline')
  )
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: enrollmentId, objective_id: objectiveId },
    `cb3-classroom-page-${enrollmentId}-${objectiveId}`,
    Boolean(enrollmentId) && Boolean(objectiveId) && backendSupports('lesson.page')
  )
  const world = useRpcQuery(
    'world.read',
    { course_id: courseId },
    `cb3-classroom-world-${courseId}`,
    Boolean(courseId) && backendSupports('world.read')
  )
  const engagement = useRpcQuery(
    'engagement.read',
    { course_id: courseId, enrollment_id: enrollmentId },
    `cb3-classroom-engagement-${courseId}-${enrollmentId}`,
    mode === 'game' && Boolean(courseId) && Boolean(enrollmentId) && backendSupports('engagement.read')
  )
  const feedbackVisible =
    typeof cbGameFeedbackVisible === 'function' ? cbGameFeedbackVisible(homePrefs, engagement.data) : true
  const [revisionFloor, setRevisionFloor] = useState(0)
  const [award, setAward] = useState(null)
  // CREATE-EXPERIENCE item 38: the last check's pass is the door to the ending, and the learner
  // opens it with the card's own primary — the verdict and its observation are the teaching beat,
  // so the ending may not erase them. `pass` is what the commit said; `ended` is the learner having
  // read it and closed the section.
  const [pass, setPass] = useState(null)
  const [ended, setEnded] = useState(false)
  // A new section starts with no award line from the previous section.
  useEffect(() => {
    setAward(null)
  }, [objectiveId])
  useEffect(() => {
    setPass(null)
    setEnded(false)
  }, [objectiveId])
  // WIRE-8: `progression.challenge_out` bumps the enrollment revision and supersedes the open
  // check. The page read that follows can still carry the older revision for one render, so this
  // surface keeps the newest revision it was told about and fences the next check/attempt with it.
  const revision = Math.max(
    page.data ? Number(page.data.revision) || 0 : 0,
    modelRevision(row),
    revisionFloor
  )
  const check = useOpenCheck({
    enrollmentId,
    objectiveId,
    revision,
    enabled: Boolean(objectiveId) && Boolean(page.data) && backendSupports('check.open'),
    implemented: backendWire.implemented
  })
  const reloadEngagement = engagement.reload
  // WIRE-9: one XP event per committed passing attempt. `check_submitted` is the contract's own
  // action kind and `attempt_id` is the real committed row the backend prices — never a click, a
  // page view or a check-in. Idempotency is doubled: this envelope key and the backend's own
  // `(enrollment_id, action_kind, action_id)` row, so a re-render cannot pay twice. The award
  // response's own `points` and (when present) `basis` are what the surface paints; nothing here
  // computes XP, and the chip re-reads `engagement.read` so the total is the backend's too.
  const awardCheck = useCallback(
    (graded) => {
      if (!graded || graded.verdict !== 'pass' || !graded.attempt_id) return
      if (mode !== 'game' || !courseId || !enrollmentId) return
      if (!backendSupports('engagement.award')) return
      rpc(
        'engagement.award',
        {
          course_id: courseId,
          enrollment_id: enrollmentId,
          action_kind: 'check_submitted',
          action_id: String(graded.attempt_id)
        },
        { idempotencyKey: `cb-award-${enrollmentId}-${graded.attempt_id}` }
      )
        .then((response) => {
          // Rule from the owner: a typed refusal (no real action) or an already-awarded replay
          // is silence — no sentence and no animation. Only a real award paints the backend's own
          // points, plus its own basis sentence when it supplies one.
          if (!response || !response.ok) return
          const result = response.result || {}
          if (result.awarded !== true) return
          const points = Number(result.points)
          if (!Number.isFinite(points) || points <= 0) return
          setAward({
            points,
            basis:
              typeof result.basis === 'string' && result.basis.trim() ? result.basis.trim() : null
          })
          if (reloadEngagement) reloadEngagement()
        })
        .catch(() => {})
    },
    [mode, courseId, enrollmentId, reloadEngagement]
  )
  const sectionId = page.data && page.data.section ? page.data.section.objective_id : objectiveId
  const scene = classroomSceneFromWorld(world.data, sectionId, (row && row.title) || '')
  const lastSection = classroomLastSection(outline.data, page.data)
  const canEnd = Boolean(lastSection && pass && classroomCompletion(page.data, pass))
  // A pass in this session waits for the learner's own press: the page re-read after the commit
  // already shows the check closed, and that must not snatch the verdict away. A revisit (no pass
  // in this session) reads the ending straight back from the recorded rows.
  const finished = lastSection
    ? pass
      ? ended
        ? classroomCompletion(page.data, pass)
        : null
      : classroomCompletion(page.data, null)
    : null
  // The card's post-pass primary is the ending's door on the last check. Everywhere else it is
  // exactly what it always was: the next section, or the course path. Once the ending is open, the
  // same handler is the panel's "Back to the path", so it may not re-open the ending.
  const advanceFromCheck = useCallback(
    (nextId) => {
      if (!ended && canEnd) {
        setEnded(true)
        return
      }
      if (typeof onNextSection === 'function') onNextSection(nextId)
    },
    [ended, canEnd, onNextSection]
  )
  const state =
    page.status === 'error' && !page.data
      ? 'error'
      : page.status === 'loading' && !page.data
        ? 'loading'
        : finished
          ? 'complete'
          : 'default'
  return jsx(ClassroomV3, {
    row,
    outline: outline.data,
    page: page.data,
    check: check.check,
    stimulusStatus: check.stimulusStatus,
    stimulusError: check.stimulusError,
    mode,
    engagement: mode === 'game' && feedbackVisible ? engagement.data : null,
    award: mode === 'game' && feedbackVisible ? award : null,
    scene,
    state,
    evidenceRecorded: finished ? finished.evidence : null,
    chatAvailable: Boolean(page.data && page.data.runtime && page.data.runtime.binding_status === 'active'),
    enrollmentId,
    objectiveId,
    revision,
    // W2-4: an assist moves the enrollment revision before the page refresh lands, so the check
    // card's next submit fences on the bumped value instead of losing to STALE_REVISION.
    onRevision: (value) => {
      const next = Number(value)
      if (Number.isFinite(next) && next > 0) setRevisionFloor(next)
    },
    onBack,
    onOpenSection,
    onNextSection: advanceFromCheck,
    onStartChat,
    onAskTutor,
    onPlayLine,
    onRetry: () => {
      page.reload()
      outline.reload()
      check.reload()
    },
    onRetryStimulus: check.reload,
    onCommitted: (graded) => {
      // Item 38: remember the committed pass before the re-read, so the ending is the backend's
      // verdict and not a guess about which card is on screen.
      if (graded && graded.verdict === 'pass') {
        setPass({
          checkId: check.check && check.check.check_id ? check.check.check_id : null,
          verdict: graded.verdict,
          evidence: classroomEvidenceRecorded(graded)
        })
      }
      page.reload()
      outline.reload()
      awardCheck(graded)
    }
  })
}

/** The enrollment revision a row carries, for the check fence before the page lands. */
function modelRevision(row) {
  return row && Number.isFinite(Number(row.revision)) ? Number(row.revision) : 0
}
// CB-V3-END — CP-023

