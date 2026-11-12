// ── surfaces ────────────────────────────────────────────────────────────────────────────────

/**
 * The three level answers the create flow offers, as the values the planner reads.
 *
 * `none` is one of `generation.BEGINNER_LEVEL_TOKENS`, so a course that starts from nothing is
 * sequenced with the concept before the act. `some` and `confident` are not beginner tokens. These
 * are the learner's own words, never a diagnosis or a grade.
 */
const SYLLABUS_LEVEL_OPTIONS = Object.freeze([
  { id: 'none', label: 'None' },
  { id: 'some', label: 'Some' },
  { id: 'confident', label: 'Confident' }
])

/** A value and its anchors. An unknown is a word, not an empty cell. */
function SyllabusValue({ item, label, onAnchor }) {
  const view = syllabusItemView(item)
  return jsxs('div', {
    className: 'flex min-w-0 flex-col gap-1 py-1.5',
    'data-cb-syllabus-field': label,
    'data-cb-syllabus-state': view.state,
    children: [
      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: label }),
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx('div', {
            className: view.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm',
            children: view.text
          }),
          ...view.anchorLabels.map((anchorLabel, index) =>
            jsx(
              sdk.Button,
              {
                size: 'sm',
                variant: 'text',
                'aria-label': `${label} — show the source at ${anchorLabel}`,
                onClick: () => onAnchor && onAnchor({ anchors: [view.anchors[index]], label }),
                children: anchorLabel
              },
              `${label}-anchor-${index}`
            )
          )
        ]
      })
    ]
  })
}

function SyllabusAnchorPanel({ open, anchors, blocks, label, onClose }) {
  if (!open) return null
  const index = new Map((Array.isArray(blocks) ? blocks : []).map((block) => [block.block_id, block]))
  return jsxs('div', {
    className: 'mt-2 flex flex-col gap-2 border-l-2 border-(--ui-stroke-secondary) pl-3',
    'data-cb-syllabus-anchor': label || 'source',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('div', { className: 'text-xs font-semibold', children: 'Source in your file' }),
          jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onClose, children: 'Close source' })
        ]
      }),
      ...(Array.isArray(anchors) ? anchors : []).map((anchor, position) => {
        const block = anchor && anchor.block_id ? index.get(anchor.block_id) : null
        const text = (anchor && anchor.quote) || (block && block.text) || null
        return jsxs(
          'div',
          {
            className: 'flex flex-col gap-0.5',
            children: [
              jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: syllabusAnchorLabel(anchor) }),
              jsx('div', {
                className: 'whitespace-pre-wrap break-words text-sm',
                children: text || 'That quote is no longer in this copy of your file.'
              })
            ]
          },
          `anchor-${position}`
        )
      }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        children: 'This is the text the item was read from. If it does not match, the item is wrong.'
      })
    ]
  })
}

function SyllabusWeekRow({ week, onAnchor }) {
  // A parse item (`{value,state,anchors}`) and a hand-written fixture (a plain ordinal or string)
  // are both honourd; neither is turned into a value the file did not state.
  const asItem = (value, anchors) =>
    value && typeof value === 'object' && !Array.isArray(value)
      ? value
      : value === undefined || value === null || value === ''
        ? { state: 'unknown', anchors: anchors || [] }
        : { value, state: 'extracted', anchors: anchors || [], derivation: 'explicit' }
  const ordinal = syllabusItemView(asItem(week && week.ordinal, week && week.anchors))
  const label = syllabusItemView(asItem(week && week.label, week && week.anchors))
  // `topic` is an item in the parse document and a plain string in a hand-written fixture: both
  // shapes are honoured, and neither is turned into a value the file did not state.
  const topic = syllabusItemView(asItem(week && week.topic, week && week.anchors))
  const readings = (week && Array.isArray(week.readings) ? week.readings : []).map((entry) =>
    syllabusItemView(asItem(entry, week && week.anchors))
  )
  return jsxs('div', {
    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
    'data-cb-syllabus-week': ordinal.unknown ? label.text : ordinal.text,
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx('div', { className: 'text-sm font-medium', children: ordinal.unknown ? label.text : `Week ${ordinal.text}` }),
          label.unknown ? null : jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: label.text }),
          ...topic.anchorLabels.map((anchorLabel, index) =>
            jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => onAnchor && onAnchor({ anchors: [topic.anchors[index]], label: 'the week' }), children: anchorLabel }, `w-${index}`)
          )
        ]
      }),
      jsx('div', { className: topic.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm', children: topic.text }),
      readings.length
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: `Reading: ${readings.map((entry) => entry.text).join('; ')}`
          })
        : null
    ]
  })
}

/**
 * UI-K13 — an imported syllabus can be removed.
 *
 * Intake could start, parse, align and review, and never undo: `syllabus.delete` had no caller, so
 * a file imported by mistake stayed on the profile forever. The removal is two-step on purpose
 * (this deletes the parse, its blocks and its alignments), and the answer is shown as evidence —
 * the backend's own `deleted: true` — before the surface closes. The refusal path matters more than
 * the happy one: a syllabus bound to a live companion course answers `SYLLABUS_IN_USE` with the
 * course ids, and this control shows them instead of pretending the file is gone.
 */
function SyllabusRemoveControl({ syllabusId, onRemoved }) {
  const [stage, setStage] = useState('idle')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [deleted, setDeleted] = useState(false)

  if (!syllabusId) return null

  const remove = async () => {
    setBusy(true)
    setError(null)
    // No idempotency key: `syllabus.delete` is not replay-safe (the row is gone on the second
    // call), and this control disables itself while the call is in flight.
    const response = await rpc('syllabus.delete', { syllabus_id: syllabusId })
    setBusy(false)
    if (!response || response.ok !== true) {
      setStage('idle')
      setError(
        (response && response.error) || {
          code: 'INTERNAL_ERROR',
          message: 'The backend did not answer the removal, so the syllabus is still here.'
        }
      )
      return
    }
    setDeleted(true)
  }

  const courseIds =
    error && error.details && Array.isArray(error.details.course_ids) ? error.details.course_ids : []

  return jsxs('div', {
    'data-cb-syllabus-remove': deleted ? 'deleted' : stage,
    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', minWidth: 0 },
    children: [
      deleted
        ? jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.3rem' },
            children: [
              jsx('div', {
                'data-cb-syllabus-remove-evidence': 'deleted',
                style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink)' },
                children: `Removed. The backend answered deleted: true for ${syllabusId}; its parse, blocks and alignments are gone.`
              }),
              // The evidence stays on screen until the reader dismisses it; leaving immediately
              // would turn a recorded deletion into a toast.
              onRemoved
                ? jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    'data-cb-syllabus-remove-done': syllabusId,
                    onClick: () => onRemoved({ deleted: true, syllabus_id: syllabusId }),
                    children: 'Back to the syllabus door'
                  })
                : null
            ]
          })
        : stage === 'confirm'
          ? jsxs('div', {
              style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
              children: [
                jsx('span', {
                  style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink)' },
                  children: 'Remove this imported syllabus? Its parsed blocks and any alignment are deleted and cannot be restored.'
                }),
                jsx(sdk.Button, {
                  variant: 'secondary',
                  size: 'sm',
                  disabled: busy,
                  'data-cb-syllabus-remove-confirm': syllabusId,
                  onClick: remove,
                  children: busy ? 'Removing…' : 'Yes, remove it'
                }),
                jsx(sdk.Button, {
                  variant: 'text',
                  size: 'sm',
                  disabled: busy,
                  onClick: () => {
                    setStage('idle')
                    setError(null)
                  },
                  children: 'Keep it'
                })
              ]
            })
          : jsx(sdk.Button, {
              variant: 'text',
              size: 'sm',
              'data-cb-syllabus-remove-start': syllabusId,
              onClick: () => {
                setStage('confirm')
                setError(null)
              },
              children: 'Remove this syllabus'
            }),
      error
        ? jsxs('div', {
            'data-cb-syllabus-remove-refusal': error.code || 'ERROR',
            style: { display: 'flex', flexDirection: 'column', gap: '0.1rem' },
            children: [
              jsx(ErrorLine, { error }),
              courseIds.length
                ? jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
                    children: `Still used by: ${courseIds.join(', ')}. Archive or delete that course first; nothing was removed here.`
                  })
                : jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: 'Nothing was removed.'
                  })
            ]
          })
        : null
    ]
  })
}

/**
 * The parse review: course facts, outcomes, weeks, assessments, then what the file does not
 * state. The coverage line is measured by the backend; the sentence is the design's own.
 */
function SyllabusParseReview({ parsed, blocks, onContinue, onBack, onReparse, busy, continueLabel, onRemoved }) {
  const [anchor, setAnchor] = useState(null)
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const fields = syllabusCourseFields(document)
  const outcomes = (Array.isArray(document.learning_outcomes) ? document.learning_outcomes : []).map(syllabusItemView)
  const weeks = Array.isArray(document.weeks) ? document.weeks : []
  const assessments = syllabusAssessmentRows(document.assessments)
  const policies = (Array.isArray(document.policies) ? document.policies : []).map(syllabusItemView)
  const unknowns = Array.isArray(document.unknowns) ? document.unknowns : []
  const coverage = document.coverage || {}
  const needsReview = (parsed && parsed.parse_state) === 'needs_review'
  const warnings = Array.isArray(parsed && parsed.warnings) ? parsed.warnings : []

  return jsxs('div', {
    className: 'flex flex-col gap-4',
    'data-cb-syllabus': 'parse-review',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'What Coursebook read from your syllabus' }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseSentence }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.notOfficial })
      ] }),
      needsReview
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-syllabus': 'parse-warning',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'Check these items before you continue' }),
              jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseNeedsReview })
            ]
          })
        : null,
      ...warnings.slice(0, 6).map((warning, index) =>
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: String(warning) }, `warning-${index}`)
      ),
      jsxs('div', {
        className: 'grid grid-cols-1 gap-x-8 gap-y-1 min-[47.5rem]:grid-cols-2',
        children: [
          jsx(SyllabusValue, { item: document.course && document.course.code, label: 'Course code', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.course && document.course.title, label: 'Course title', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.institution, label: 'Institution', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.instructor, label: 'Instructor', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.meeting_pattern, label: 'When it meets', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.term && document.term.start_date, label: 'Term starts', onAnchor: setAnchor }),
          jsx(SyllabusValue, { item: document.term && document.term.end_date, label: 'Term ends', onAnchor: setAnchor })
        ]
      }),
      anchor ? jsx(SyllabusAnchorPanel, { open: true, anchors: anchor.anchors, blocks, label: anchor.label, onClose: () => setAnchor(null) }) : null,
      jsx(CbLabel, { children: 'Learning outcomes in your file' }),
      outcomes.length
        ? jsxs('div', { className: 'flex flex-col', children: outcomes.map((outcome, index) =>
            jsxs('div', { className: 'flex flex-col gap-0.5 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0', children: [
              jsx('div', { className: outcome.unknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm', children: outcome.text }),
              jsxs('div', { className: 'flex flex-wrap gap-2', children: outcome.anchorLabels.map((label, position) =>
                jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => setAnchor({ anchors: [outcome.anchors[position]], label: 'an outcome' }), children: label }, `o-${index}-${position}`)) })
            ] }, `outcome-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list learning outcomes.' }),
      jsx(CbLabel, { children: 'Weeks' }),
      weeks.length
        ? jsx('div', { className: 'flex flex-col', children: weeks.map((week, index) => jsx(SyllabusWeekRow, { week, onAnchor: setAnchor }, `week-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list weeks.' }),
      jsx(CbLabel, { children: 'Assessments and weights' }),
      assessments.length
        ? jsx('div', {
            className: 'flex flex-col',
            children: assessments.map((row, index) =>
              jsxs('div', {
                className: 'flex flex-col gap-0.5 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                'data-cb-syllabus-assessment': row.title,
                children: [
                  jsxs('div', { className: 'flex flex-wrap items-baseline gap-2', children: [
                    jsx('div', { className: row.titleUnknown ? 'text-sm italic text-(--ui-text-secondary)' : 'text-sm font-medium', children: row.title }),
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: row.due }),
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: row.weight })
                  ] }),
                  jsxs('div', { className: 'flex flex-wrap gap-2', children: row.anchorLabels.map((label, position) =>
                    jsx(sdk.Button, { size: 'sm', variant: 'text', onClick: () => setAnchor({ anchors: [row.anchors[position]], label: 'an assessment' }), children: label }, `a-${index}-${position}`)) })
                ]
              }, `assessment-${index}`)
            )
          })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not list assessments.' }),
      jsx(CbLabel, { children: 'Policies your file states' }),
      policies.length
        ? jsx('div', { className: 'flex flex-col', children: policies.map((policy, index) =>
            jsx('div', { className: 'max-w-prose border-b border-(--ui-stroke-tertiary) py-1.5 text-sm last:border-b-0', children: policy.text }, `policy-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Your file does not state study policies Coursebook can quote.' }),
      jsx(CbLabel, { children: 'What your file does not state' }),
      unknowns.length
        ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: unknowns.join(' · ') })
        : jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'Nothing was left out by this parse.' }),
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        'data-cb-syllabus-coverage': `${coverage.pages || 0}/${coverage.items_total || 0}/${coverage.items_extracted || 0}`,
        children: coverage.pages
          ? `Read from ${coverage.pages} page${coverage.pages === 1 ? '' : 's'}: ${coverage.items_extracted || 0} of ${coverage.items_total || 0} items had a quote in your file.`
          : 'The backend did not report coverage for this parse.'
      }),
      jsxs('div', { className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: onBack, children: 'Back' }),
        onReparse ? jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onReparse, disabled: Boolean(busy), children: 'Read it again' }) : null,
        // UI-K13: undo an import. It sits with the secondary actions, never beside the primary.
        onRemoved
          ? jsx(SyllabusRemoveControl, {
              syllabusId: (parsed && parsed.syllabus_id) || null,
              onRemoved
            })
          : null,
        jsx(CbAction, {
          variant: 'primary',
          disabled: Boolean(busy) || needsReview,
          onClick: onContinue,
          children: continueLabel || 'Confirm these details'
        })
      ] })
    ]
  })
}

/** The authority sentence, the counts, then one row per item with its reason and source. */
function SyllabusAlignmentReview({ alignment, onDecision, onApprove, onRealign, busy }) {
  const [anchor, setAnchor] = useState(null)
  const view = syllabusAlignmentView(alignment)
  const countsLine = ['aligned', 'partial', 'unmatched', 'conflict', 'unknown', 'stale']
    .filter((state) => Number(view.counts[state] || 0) > 0)
    .map((state) => `${view.counts[state]} ${(ALIGNMENT_STATE_COPY[state] || ALIGNMENT_STATE_COPY.unknown).label.toLowerCase()}`)
    .join(' · ')
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    'data-cb-syllabus': 'alignment',
    'data-cb-syllabus-approve': view.approveReady ? 'ready' : 'blocked',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'How the course maps to your syllabus' }),
        jsx('div', { className: 'max-w-prose text-sm', 'data-cb-syllabus': 'authority', children: SYLLABUS_COPY.authority }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.alignmentGate })
      ] }),
      view.stale
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-syllabus': 'stale',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'This mapping is out of date' }),
              jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.staleAction }),
              onRealign ? jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onRealign, disabled: Boolean(busy), children: 'Check the new version' }) : null
            ]
          })
        : null,
      jsx('div', { className: 'text-xs text-(--ui-text-secondary)', 'data-cb-syllabus-counts': countsLine, children: countsLine || 'The backend reported no items to align.' }),
      view.rows.length
        ? jsx('div', { className: 'flex flex-col', children: view.rows.map((row, index) =>
            jsxs('div', {
              className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
              'data-cb-align-row': row.state,
              'data-cb-align-item': row.itemId || `row-${index}`,
              children: [
                jsxs('div', { className: 'flex flex-wrap items-baseline gap-2', children: [
                  jsx('div', { className: 'text-sm font-medium', children: row.title }),
                  jsx(sdk.Badge, { variant: row.tone === 'bad' ? 'warn' : row.tone === 'ok' ? 'muted' : 'outline', size: 'xs', children: row.stateLabel }),
                  row.targetLabel ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `→ ${row.targetLabel}` }) : null
                ] }),
                jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: row.reason }),
                jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
                  row.anchorLabels.map((label, position) =>
                    jsx(sdk.Button, {
                      size: 'sm',
                      variant: 'text',
                      onClick: () => setAnchor({ anchors: [row.anchors[position]], label: row.title }),
                      children: label
                    }, `anchor-${position}`)),
                  row.actions.map((entry) =>
                    jsx(sdk.Button, {
                      size: 'sm',
                      variant: 'secondary',
                      disabled: Boolean(busy),
                      onClick: () => onDecision && onDecision({ item_id: row.itemId, action: entry.action }),
                      children: entry.label
                    }, entry.action))
                ] })
              ]
            }, row.itemId || `row-${index}`)) })
        : jsx(sdk.PanelEmpty, { children: 'Nothing has been mapped yet. Run the alignment against a draft plan first.' }),
      anchor ? jsx(SyllabusAnchorPanel, { open: true, anchors: anchor.anchors, blocks: alignment && alignment.blocks, label: anchor.label, onClose: () => setAnchor(null) }) : null,
      jsxs('div', { className: 'flex flex-wrap items-center gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(CbAction, {
          variant: 'primary',
          disabled: Boolean(busy) || !view.approveReady,
          onClick: onApprove,
          children: 'Approve this mapping'
        }),
        view.approveBlockedReason
          ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', 'data-cb-syllabus': 'approve-reason', children: view.approveBlockedReason })
          : jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Approved. The plan can be approved on the Plan tab.' })
      ] })
    ]
  })
}

/**
 * The plan-tab gate, as one value both the panel and a test can read.
 *
 * `plan.approve` on a companion course is refused by the backend until the bound syllabus revision
 * has been reviewed and no mapping row is stale. The UI predicts exactly that so the button is
 * disabled with a reason instead of failing after a click; the backend remains the authority.
 */
function syllabusPlanGate({ binding, planState, rowsReady }) {
  if (!binding) return { required: false, ready: true, reason: null, stale: false }
  const stale = Boolean(binding.stale)
  const reviewed =
    binding.reviewed_revision !== null &&
    binding.reviewed_revision !== undefined &&
    Number(binding.reviewed_revision) === Number(binding.revision)
  const ready = Boolean(reviewed) && !stale
  const reason = stale
    ? 'Your syllabus changed. This course stays as it was until the new version is mapped and reviewed; approval is blocked.'
    : !rowsReady
      ? 'Map the draft plan to your syllabus before approving it.'
      : !reviewed
        ? 'Review the mapping on this tab before approving the plan.'
        : null
  return { required: true, ready, reason, stale }
}

/**
 * The alignment gate on a companion course's plan tab.
 *
 * It reads the binding from `course.get`, the parsed document from `syllabus.get` and the mapping
 * from `syllabus.alignment.get`. Mapping is an explicit click once a draft plan exists (the plan is
 * the thing being mapped), the learner's decisions go through `syllabus.alignment.review`, and the
 * component reports to its parent whether `plan.approve` may be pressed. It never regenerates a
 * plan, never re-aligns after a revision change on its own, and never hides a stale mapping.
 */
function SyllabusAlignmentPanel({ course, planId, planState, reloadSignal, onGateChange, onChanged, onNewSyllabus }) {
  const supports = (method) => (typeof backendSupports === 'function' ? backendSupports(method) : false)
  const signal = Number(reloadSignal || 0)
  const bindingQuery = useRpcQuery(
    'course.get',
    { course_id: course.course_id },
    `cb-syl-binding-${course.course_id}-${signal}`,
    supports('course.get') && supports('syllabus.alignment.get')
  )
  const binding =
    bindingQuery.data && bindingQuery.data.course && bindingQuery.data.course.syllabus
      ? bindingQuery.data.course.syllabus
      : null
  const syllabusId = binding ? binding.syllabus_id : null
  const syllabusRevision = binding ? binding.revision : null
  const documentQuery = useRpcQuery(
    'syllabus.get',
    { syllabus_id: syllabusId, revision: syllabusRevision, include_blocks: true },
    `cb-syl-doc-${syllabusId}-${syllabusRevision}-${signal}`,
    Boolean(syllabusId) && supports('syllabus.get')
  )
  const alignmentQuery = useRpcQuery(
    'syllabus.alignment.get',
    { syllabus_id: syllabusId, revision: syllabusRevision, course_id: course.course_id },
    `cb-syl-align-${syllabusId}-${syllabusRevision}-${course.course_id}-${signal}`,
    Boolean(syllabusId) && supports('syllabus.alignment.get')
  )
  const [decisions, setDecisions] = useState({})
  const [busy, setBusy] = useState(false)
  const [aligning, setAligning] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const alignment = alignmentQuery.data || null
  const view = alignment ? syllabusAlignmentView(alignment) : null
  const blocks = (documentQuery.data && documentQuery.data.blocks) || (alignment && alignment.blocks) || []
  const needsDecision = view
    ? view.rows.filter(
        (row) =>
          row.reviewState === 'pending' &&
          ['partial', 'unmatched', 'conflict'].includes(row.state) &&
          row.valueState !== 'unknown'
      )
    : []
  const stale = Boolean((binding && binding.stale) || (view && view.stale))
  const rowsReady = Boolean(view && view.rows.length > 0)
  const gate = syllabusPlanGate({ binding, planState, rowsReady })
  const gateReady = gate.ready
  const gateReason = gate.reason

  useEffect(() => {
    if (onGateChange) {
      onGateChange({ required: Boolean(binding), ready: gateReady, reason: gateReason, stale })
    }
  }, [binding, gateReady, gateReason, stale, onGateChange])

  // Mapping runs as the existing import job; the screen polls the alignment read instead of
  // inventing a percentage for a job that reports state only.
  useEffect(() => {
    if (!aligning) return undefined
    let attempts = 0
    const handle = setInterval(() => {
      attempts += 1
      alignmentQuery.reload()
      if (attempts >= 40) setAligning(false)
    }, 1500)
    return () => clearInterval(handle)
  }, [aligning, alignmentQuery.reload])

  useEffect(() => {
    if (view && view.rows.length > 0 && aligning) setAligning(false)
  }, [view, aligning])

  const mapPlan = useCallback(async () => {
    if (!planId || !syllabusId) return
    setBusy(true)
    setError(null)
    setNotice(null)
    const outcome = await queueSyllabusAlignment({
      call: rpc,
      syllabusId,
      revision: syllabusRevision,
      courseId: course.course_id,
      planId
    })
    setBusy(false)
    if (!outcome.ok) {
      setError(outcome.error || { code: 'INTERNAL_ERROR', message: 'The mapping could not be started.' })
      return
    }
    setAligning(true)
    setNotice('Mapping the plan to your syllabus. This runs on this device; the rows appear when it finishes.')
    alignmentQuery.reload()
  }, [planId, syllabusId, syllabusRevision, course.course_id, alignmentQuery.reload])

  const review = useCallback(async () => {
    if (!view || !syllabusId) return
    const payload = syllabusReviewPayload({
      syllabusId,
      revision: syllabusRevision,
      courseId: course.course_id,
      alignmentRevision: view.alignmentRevision,
      decisions: needsDecision.map((row) => ({ item_id: row.itemId, action: decisions[row.itemId] })).filter((row) => row.action)
    })
    // An empty decision set is a checked claim, not a shortcut: the backend accepts it only
    // when no row needs a decision, and refuses it otherwise with the rows that do. Refusing
    // to send it here made a fully aligned mapping impossible to approve.
    setBusy(true)
    setError(null)
    const response = await rpc('syllabus.alignment.review', payload, { idempotencyKey: newOperationId('syllabus-review') })
    setBusy(false)
    if (!response.ok) {
      const nextRevision = staleRevision(response)
      if (nextRevision !== null) alignmentQuery.reload()
      setError(response.error || { code: 'INTERNAL_ERROR', message: 'The review was not recorded.' })
      return
    }
    const result = response.result || {}
    if (result.plan_replan_required) {
      setNotice('The plan needs to change to match your syllabus. Start a new plan version, then map it again. Your current plan is unchanged.')
    } else if (result.reviewed_revision !== null && result.reviewed_revision !== undefined) {
      setNotice('Mapping approved. The plan can now be approved on this tab.')
    } else {
      setNotice('Some items still need a decision before the mapping is approved.')
    }
    bindingQuery.reload()
    alignmentQuery.reload()
    if (onChanged) onChanged()
  }, [view, syllabusId, syllabusRevision, course.course_id, needsDecision, decisions, alignmentQuery, bindingQuery, onChanged])

  const decide = useCallback((itemId, action) => {
    setDecisions((previous) => ({ ...previous, [itemId]: action }))
  }, [])

  if (bindingQuery.status === 'error' && !bindingQuery.data) {
    return jsx(sdk.ErrorState, {
      title: 'The syllabus binding could not be read',
      description: `${bindingQuery.error && bindingQuery.error.code ? bindingQuery.error.code + ': ' : ''}${describeError(bindingQuery.error)}`,
      children: jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: bindingQuery.reload, children: 'Try again' })
    })
  }
  if (!binding) return null
  if (!planId) {
    return jsx('div', {
      className: 'max-w-prose text-xs text-(--ui-text-secondary)',
      'data-cb-align-panel': 'waiting',
      children: 'Your syllabus is attached to this course. The matching appears once the draft plan is written; nothing is matched against a template.'
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3 border-t border-(--ui-stroke-tertiary) pt-3',
    'data-cb-align-panel': gateReady ? 'ready' : 'blocked',
    children: [
      stale
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
            'data-cb-align-stale': 'true',
            children: [
              jsx('div', { className: 'text-sm font-medium', children: 'You added a new version of your syllabus' }),
              jsx('div', {
                className: 'max-w-prose text-xs text-(--ui-text-secondary)',
                children:
                  syllabusStaleNotice({ revision: syllabusRevision, counts: (alignment && alignment.counts) || {}, planRevision: syllabusRevision }).lines.join(' ')
              }),
              onNewSyllabus
                ? jsx(sdk.Button, {
                    className: 'self-start',
                    size: 'sm',
                    variant: 'secondary',
                    onClick: () => onNewSyllabus({ syllabusId, revision: syllabusRevision, courseId: course.course_id, enrollmentId: course.enrollment_id }),
                    children: 'Upload the new syllabus'
                  })
                : null
            ]
          })
        : null,
      !rowsReady && !aligning
        ? jsxs('div', { className: 'flex flex-col gap-2', children: [
            jsx('div', { className: 'text-sm font-semibold', children: 'Map this plan to your syllabus' }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.alignmentGate }),
            jsx(CbAction, {
              className: 'self-start',
              variant: 'primary',
              disabled: busy || stale,
              onClick: mapPlan,
              children: 'Map the plan to my syllabus'
            })
          ] })
        : null,
      aligning && !rowsReady
        ? jsxs('div', { className: 'flex flex-col gap-2', children: [
            jsx(sdk.Loader, { label: 'Mapping the plan to your syllabus' }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'The mapping runs on this device and is built from validated items only. There is no percentage to show.' })
          ] })
        : null,
      rowsReady
        ? jsx(SyllabusAlignmentReview, {
            alignment: { ...alignment, blocks },
            busy,
            onDecision: (decision) => decide(decision.item_id, decision.action),
            onApprove: review,
            onRealign: stale ? null : mapPlan
          })
        : null,
      needsDecision.length
        ? jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-secondary)',
            children: `${needsDecision.filter((row) => decisions[row.itemId]).length} of ${needsDecision.length} ${needsDecision.length === 1 ? 'item has' : 'items have'} a decision. Every partly covered, uncovered or conflicting item needs one before the mapping is approved.`
          })
        : null,
      notice ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error
        ? jsx(sdk.ErrorState, {
            title: error.code || 'The mapping could not be recorded',
            description: error.message || describeError(error)
          })
        : null
    ]
  })
}

/**
 * Intake. The file door is feature-detected: a build without a byte-reading door gets the honest
 * sentence and the paste box, never a picker that cannot deliver. Every refusal is the backend's
 * typed code with a readable sentence, and cancellation stops before the next call.
 */
function SyllabusIntakeFlow({ onCancel, onCreated, onParsed, supersedes, revisionOnly }) {
  const supersedesId = supersedes && supersedes.syllabusId ? supersedes.syllabusId : null
  const [step, setStep] = useState('choose')
  const [pasted, setPasted] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [syllabus, setSyllabus] = useState(null)
  const [parseJob, setParseJob] = useState(null)
  const [parsed, setParsed] = useState(null)
  const [cancelled, setCancelled] = useState(false)
  const [ack, setAck] = useState(false)
  const [door, setDoor] = useState('unknown')
  const cancelledRef = useRef(false)

  useEffect(() => {
    const files = pluginContext && pluginContext.files
    const canRead =
      files &&
      typeof files.readText === 'function' &&
      typeof files.readDataUrl === 'function' &&
      typeof files.requestFolder === 'function'
    setDoor(canRead ? 'available' : 'absent')
  }, [])

  const refuse = useCallback((failure) => {
    const code = failure && failure.code ? failure.code : 'HOST_UNAVAILABLE'
    const message = failure && failure.message ? failure.message : describeError(failure)
    setError({ code, message })
  }, [])

  const submitPasted = useCallback(async () => {
    if (busy || cancelledRef.current) return
    const built = syllabusIntakePayload({ pastedText: pasted, supersedesSyllabusId: supersedesId })
    if (!built.ok) {
      refuse(built.error)
      return
    }
    setBusy(true)
    setError(null)
    setStep('reading')
    try {
      const created = await rpc('syllabus.intake.create', built.payload, {
        idempotencyKey: `cb-syllabus-intake-${newOperationId('intake')}`,
        expectedRevision: null
      })
      if (cancelledRef.current) return
      if (!created.ok) {
        refuse(created.error)
        setStep('choose')
        return
      }
      setSyllabus(created.result)
      const job = await rpc('syllabus.parse', {
        syllabus_id: created.result.syllabus_id,
        revision: created.result.revision,
        egress_acknowledged: true
      }, { idempotencyKey: `cb-syllabus-parse-${created.result.syllabus_id}-${created.result.revision}-${created.result.content_sha256}` })
      if (cancelledRef.current) return
      if (!job.ok) {
        refuse(job.error)
        setStep('choose')
        return
      }
      setParseJob(job.result)
      onParsed && onParsed(created.result)
      setStep('parsing')
    } catch (failure) {
      refuse({ code: 'HOST_UNAVAILABLE', message: describeError(failure) })
      setStep('choose')
    } finally {
      setBusy(false)
    }
  }, [busy, pasted, refuse, onParsed, supersedesId])

  const openFile = useCallback(async () => {
    const files = pluginContext && pluginContext.files
    if (!files || typeof files.requestFolder !== 'function') {
      setDoor('absent')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const picked = await files.requestFolder()
      if (cancelledRef.current) return
      if (!picked || !picked.ok || !picked.folder) {
        if (picked && picked.message) refuse({ code: 'HOST_UNAVAILABLE', message: picked.message })
        return
      }
      const listing = await files.list(picked.folder.id)
      if (!listing || !listing.ok) {
        refuse({ code: 'HOST_UNAVAILABLE', message: (listing && listing.message) || 'That folder could not be read.' })
        return
      }
      const entry = (listing.entries || []).find((candidate) => !candidate.isDirectory && syllabusAcceptEntry(candidate.name))
      if (!entry) {
        refuse({ code: 'SYLLABUS_REJECTED', message: 'No Markdown, text, PDF or Word file was in that folder.' })
        return
      }
      const acceptable = syllabusAcceptEntry(entry.name)
      const read = acceptable.text
        ? await files.readText(picked.folder.id, entry.path)
        : await files.readDataUrl(picked.folder.id, entry.path)
      if (cancelledRef.current) return
      if (!read || !read.ok) {
        refuse({ code: (read && read.code) || 'HOST_UNAVAILABLE', message: (read && read.message) || 'The host could not read that file.' })
        return
      }
      const built = syllabusIntakePayload(
        acceptable.text
          ? { fileName: entry.name, text: read.text, supersedesSyllabusId: supersedesId }
          : { fileName: entry.name, dataUrl: read.dataUrl, supersedesSyllabusId: supersedesId }
      )
      if (!built.ok) {
        refuse(built.error)
        return
      }
      await sendIntake(built.payload)
    } catch (failure) {
      refuse({ code: 'HOST_UNAVAILABLE', message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [supersedesId])

  const sendIntake = useCallback(async (payload) => {
    const created = await rpc('syllabus.intake.create', payload, {
      idempotencyKey: `cb-syllabus-intake-${newOperationId('intake')}`,
      expectedRevision: null
    })
    if (!created.ok) {
      refuse(created.error)
      return
    }
    setSyllabus(created.result)
    const job = await rpc('syllabus.parse', {
      syllabus_id: created.result.syllabus_id,
      revision: created.result.revision,
      egress_acknowledged: true
    }, { idempotencyKey: `cb-syllabus-parse-${created.result.syllabus_id}-${created.result.revision}-${created.result.content_sha256}` })
    if (!job.ok) {
      refuse(job.error)
      return
    }
    setParseJob(job.result)
    onParsed && onParsed(created.result)
    setStep('parsing')
  }, [refuse, onParsed])

  // Cancelling before the backend has minted a parse job is honest only if it says why: nothing
  // further is sent from this screen, and there is no job id here to stop. Once a job exists the
  // parse stage owns the cancel so its answer is rendered instead of assumed.
  const cancelBeforeJob = useCallback(() => {
    cancelledRef.current = true
    setCancelled(true)
  }, [])

  if (step === 'parsing' || step === 'parsed') {
    return jsx(SyllabusParseStage, {
      syllabus,
      jobId: parseJob && parseJob.job_id,
      parsed,
      revisionOnly,
      onParsed: setParsed,
      onStep: setStep,
      onCancel: onCancel,
      onCreated,
      door: door,
      busy,
      error,
      refuse
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-3',
    'data-cb-syllabus': 'intake',
    children: [
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-sm font-semibold', children: SYLLABUS_COPY.action }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.entryBody }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.acceptTypes })
      ] }),
      door === 'absent'
        ? jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', 'data-cb-syllabus': 'no-file-door', children: SYLLABUS_COPY.noFileDoor })
        : null,
      jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
        door === 'available'
          ? jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: openFile, disabled: busy, children: 'Choose a syllabus file' })
          : null,
        jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: cancelBeforeJob, children: 'Cancel' })
      ] }),
      jsxs('div', { className: 'flex flex-col gap-1', children: [
        jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: 'Or paste the syllabus text' }),
        jsx(sdk.Textarea, {
          'aria-label': 'Paste your syllabus text',
          value: pasted,
          rows: 8,
          onChange: (event) => setPasted(event && event.target ? event.target.value : '')
        }),
        jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `${pasted.length.toLocaleString()} of ${SYLLABUS_LIMITS.text_chars.toLocaleString()} characters` })
      ] }),
      jsxs('div', { className: 'flex items-start gap-2', children: [
        jsx(sdk.Checkbox, {
          id: 'cb-syllabus-egress',
          'aria-label': 'Acknowledge that the extracted text goes to my configured model provider',
          checked: ack,
          onCheckedChange: setAck
        }),
        jsx('div', {
          className: 'max-w-prose text-xs text-(--ui-text-secondary)',
          'data-cb-syllabus': 'egress',
          children: SYLLABUS_COPY.storage
        })
      ] }),
      jsx(CbAction, {
        className: 'self-start',
        variant: 'primary',
        disabled: busy || !ack || pasted.trim().length === 0,
        onClick: submitPasted,
        children: busy ? 'Reading your syllabus' : 'Use this text'
      }),
      error
        ? jsx(sdk.ErrorState, { title: error.code, description: error.message })
        : null,
      cancelled
        ? jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancelled-before-job', children: [
          jsx('div', {
            className: 'max-w-prose text-xs text-(--ui-text-secondary)',
            children: 'Cancelled. Nothing further was sent — nothing had been started here yet, so there was nothing to stop.'
          }),
          jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Close' })
        ] })
        : null
    ]
  })
}

/** Parse stage: poll the stored document, then hand the review screen its real items. */
function SyllabusParseStage({ syllabus, jobId, parsed, revisionOnly, onParsed, onStep, onCancel, onCreated, busy, error, refuse }) {
  const [document, setDocument] = useState(null)
  const [state, setState] = useState(parsed && parsed.parse_state ? 'parsed' : 'parsing')
  const [step, setStep] = useState('review')
  const [scope, setScope] = useState('short')
  // WIRE-3/WIRE-4: one sheet, not a wizard. The same answers the create flow asks for travel with
  // the companion course: the learner's level, the lesson mode, and an optional typed goal.
  const [goal, setGoal] = useState('')
  const [level, setLevel] = useState('')
  const [presentationMode, setPresentationMode] = useState('game')
  const [subjectDomain, setSubjectDomain] = useState('')
  const [locale, setLocale] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [failure, setFailure] = useState(null)
  // The backend's answer to a cancel, rendered instead of assumed. `asking` is the unanswered
  // moment; nothing claims the job stopped until this holds the backend's own state.
  const [cancelOutcome, setCancelOutcome] = useState(null)
  const cancelRef = useRef(false)
  const keyRef = useRef(null)

  useEffect(() => {
    if (!syllabus || document || cancelOutcome) return undefined
    let stopped = false
    let attempts = 0
    let dispose = null
    const stop = () => {
      stopped = true
      if (dispose) {
        dispose()
        dispose = null
      }
    }
    const tick = async () => {
      if (stopped || cancelRef.current) return
      attempts += 1
      const response = await rpc('syllabus.get', {
        syllabus_id: syllabus.syllabus_id,
        revision: syllabus.revision,
        include_blocks: true
      })
      if (stopped) return
      if (!response.ok) {
        setFailure(response.error)
        stop()
        return
      }
      const result = response.result || {}
      // `syllabus.get` carries no top-level state: the parse run is the state, and the stored
      // document is only readable once that run exists.
      const view = syllabusParseView(result)
      if (view.parse_state) {
        setDocument(view)
        setState('parsed')
        onParsed && onParsed(view)
        stop()
        return
      }
      if (result.syllabus && result.syllabus.state === 'failed') {
        setFailure({ code: 'SYLLABUS_REJECTED', message: 'Your file could not be read. Check it is the syllabus itself and try again.' })
        setState('failed')
        stop()
        return
      }
      if (jobId) {
        const job = await rpc('jobs.get', { job_id: jobId })
        if (stopped) return
        const jobView = job && job.ok ? job.result.job : null
        if (jobView && ['failed', 'cancelled', 'interrupted_requires_retry'].includes(jobView.state)) {
          const message = (jobView.error && jobView.error.message) || 'The parse did not finish. Check the file is the syllabus itself and try again.'
          setFailure({ code: (jobView.error && jobView.error.code) || 'SYLLABUS_REJECTED', message })
          setState('failed')
          stop()
          return
        }
      }
      if (attempts >= 150) {
        setState('slow')
        stop()
      }
    }
    // `ctx.setInterval` returns a disposer and is cleared when the plugin unloads, so a poller
    // cannot outlive the surface that started it.
    if (pluginContext && typeof pluginContext.setInterval === 'function') {
      dispose = pluginContext.setInterval(tick, 2000)
    } else {
      const handle = setInterval(tick, 2000)
      dispose = () => clearInterval(handle)
    }
    return stop
  }, [syllabus, jobId, document, onParsed, cancelOutcome])

  // Stopping the watch is not stopping the job. `cancelRef` halts the poll immediately, then the
  // `jobs.cancel` answer decides which of the three outcomes is shown: accepted (`queued` became
  // `cancelled`), requested but still finishing (`running` became `cancel_requested`), or refused.
  const requestCancel = useCallback(async () => {
    cancelRef.current = true
    setCancelOutcome({ status: 'asking' })
    if (!jobId) {
      setCancelOutcome({ status: 'no-job' })
      return
    }
    const response = await rpc('jobs.cancel', { job_id: jobId }, { idempotencyKey: `cb-syllabus-parse-cancel-${jobId}` })
    if (!response || response.ok !== true) {
      const refusal = (response && response.error) || {
        code: 'INTERNAL_ERROR',
        message: 'The backend did not answer the cancel, so this screen cannot say the parse stopped.'
      }
      setCancelOutcome({ status: 'failed', error: refusal })
      return
    }
    const target = response.result && response.result.state
    if (target === 'cancelled') setCancelOutcome({ status: 'accepted' })
    else setCancelOutcome({ status: 'requested', state: target || null })
  }, [jobId])

  if (cancelOutcome) {
    const close = jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back to Library' })
    if (cancelOutcome.status === 'asking') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-asking', children: [
        jsx(sdk.Loader, { label: 'Asking the backend to stop the parse' })
      ] })
    }
    if (cancelOutcome.status === 'accepted') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-accepted', children: [
        jsx('div', { className: 'max-w-prose text-sm', children: 'Cancelled. Nothing further was sent.' }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: 'The backend accepted the stop, so no course will be created from this parse.' }),
        close
      ] })
    }
    if (cancelOutcome.status === 'requested') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-requested', children: [
        jsx('div', {
          className: 'max-w-prose text-sm',
          children: 'Asked the backend to stop; it will not start new work. The course will not be created until you review it.'
        }),
        close
      ] })
    }
    if (cancelOutcome.status === 'no-job') {
      return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancelled-before-job', children: [
        jsx('div', {
          className: 'max-w-prose text-sm',
            children: 'Cancelled. Nothing further was sent — nothing had been started here yet, so there was nothing to stop.'
        }),
        close
      ] })
    }
    const refusal = cancelOutcome.error || {}
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'cancel-failed', children: [
      jsx(sdk.ErrorState, {
        title: refusal.code || 'CANCEL_REFUSED',
        description: `${refusal.message || 'The backend refused the cancel.'} The parse may still be running, and a course could be created from it. Retry the cancel, or review the course when it appears.`
      }),
      jsxs('div', { className: 'flex flex-wrap gap-2', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: requestCancel, children: 'Retry cancel' }),
        close
      ] })
    ] })
  }

  const target = document || (parsed && parsed.document ? parsed : null)

  if (state === 'parsing') {
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'parsing', children: [
      jsx(sdk.Loader, { label: 'Reading your syllabus' }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.parseRunning }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'ghost', onClick: requestCancel, children: 'Stop watching this parse' })
    ] })
  }
  if (state === 'failed' || failure) {
    return jsxs('div', { className: 'flex flex-col gap-2', children: [
      jsx(sdk.ErrorState, { title: failure ? failure.code : 'SYLLABUS_REJECTED', description: failure ? failure.message : 'The parse did not finish.' }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back' })
    ] })
  }
  if (state === 'slow') {
    return jsxs('div', { className: 'flex flex-col gap-2', children: [
      jsx('div', { className: 'max-w-prose text-sm', children: 'The parse is taking longer than usual. It keeps running on this device; you can come back to it from Library.' }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back to Library' })
    ] })
  }
  if (!target) {
    return jsxs('div', { className: 'flex flex-col gap-2', 'data-cb-syllabus': 'parse-unreadable', children: [
      jsx(sdk.ErrorState, {
        title: 'The parsed details could not be read',
        description: 'The parse finished but its stored items did not load. Nothing is shown from a template; try reading the file again.'
      }),
      jsx(sdk.Button, { className: 'self-start', size: 'sm', variant: 'secondary', onClick: onCancel, children: 'Back' })
    ] })
  }

  if (step === 'scope') {
    const proposal = syllabusScopeProposal(target)
    const choices = [
      { id: 'single', label: 'One lesson' },
      { id: 'short', label: 'A short course' },
      { id: 'full', label: 'The whole term' }
    ]
    const defaultGoal = syllabusDefaultGoal(target)
    const tune = (id, label, value, onChange, placeholder, maxLength) => jsxs('div', {
      className: 'flex flex-col gap-1.5',
      children: [
        jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: id, children: label }),
        jsx(sdk.Input, { id, maxLength, onChange: (event) => onChange(event.target.value), placeholder, value })
      ]
    })
    return jsxs('div', { className: 'flex flex-col gap-4', 'data-cb-syllabus': 'scope', children: [
      jsx('div', { className: 'text-sm font-semibold', children: SYLLABUS_COPY.sheetTitle }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.sheetLead }),
      // Goal: the create flow opens here, so the syllabus sheet asks it first too. A blank field is
      // not an empty goal — the syllabus title becomes the goal sentence, and the hint says which.
      jsxs('div', { className: 'flex flex-col gap-1.5', 'data-cb-syllabus-goal': '', children: [
        jsx('label', { className: 'text-xs text-(--ui-text-secondary)', htmlFor: 'cb-syllabus-goal', children: SYLLABUS_COPY.goalQuestion }),
        jsx(sdk.Input, {
          id: 'cb-syllabus-goal',
          maxLength: 4000,
          onChange: (event) => setGoal(event.target.value),
          placeholder: defaultGoal,
          value: goal
        }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.goalHint(defaultGoal) })
      ] }),
      jsxs('div', { className: 'flex flex-col gap-1.5', children: [
        jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: 'How much of the class should this course support?' }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: proposal.proposal ? proposal.reason : proposal.reason }),
        jsx(sdk.SegmentedControl, { onChange: setScope, options: choices, sizing: 'content', value: scope })
      ] }),
      // Level: the same three answers the create flow offers. `none` is the token the planner's
      // beginner rule recognises, so the course builds the concept before it asks for the act.
      jsxs('div', { className: 'flex flex-col gap-1.5', 'data-cb-syllabus-level': level || 'unset', children: [
        jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: SYLLABUS_COPY.levelQuestion }),
        jsx(sdk.SegmentedControl, { onChange: setLevel, options: SYLLABUS_LEVEL_OPTIONS, sizing: 'content', value: level }),
        jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.levelHint })
      ] }),
      // Mode: the same two cards the create flow uses, Game first because it is the default intent.
      jsxs('div', { className: 'flex flex-col gap-1.5', 'data-cb-syllabus-mode': presentationMode, children: [
        jsx('div', { className: 'text-xs font-medium text-(--ui-text-secondary)', children: SYLLABUS_COPY.modeQuestion }),
        jsx('div', {
          style: { display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '0.4rem', minWidth: 0 },
          children: ['game', 'textbook'].map((mode) => createModeCard(mode, presentationMode, setPresentationMode))
        })
      ] }),
      jsxs('details', {
        'data-cb-syllabus-tune': '',
        className: 'border-t border-(--ui-stroke-tertiary) pt-3 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('summary', { className: 'cursor-pointer text-xs font-medium', children: SYLLABUS_COPY.tuneLabel }),
          jsxs('div', { className: 'mt-2 flex flex-col gap-3', children: [
            tune('cb-syllabus-subject', SYLLABUS_COPY.subjectLabel, subjectDomain, setSubjectDomain, 'e.g. computer science, Spanish, electrical safety', 60),
            tune('cb-syllabus-locale', SYLLABUS_COPY.localeLabel, locale, setLocale, 'e.g. es-ES for Spanish, ja-JP for Japanese', 35)
          ] })
        ]
      }),
      jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.researchMinutes }),
      failure ? jsx(sdk.ErrorState, { title: failure.code, description: failure.message }) : null,
      jsxs('div', { className: 'flex flex-wrap gap-2 border-t border-(--ui-stroke-tertiary) pt-3', children: [
        jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: () => setStep('review'), disabled: submitting, children: 'Back to the details' }),
        jsx(CbAction, {
          variant: 'primary',
          disabled: submitting,
          onClick: async () => {
            if (!keyRef.current) keyRef.current = `cb-companion-${newOperationId('companion')}`
            setSubmitting(true)
            const outcome = await startCompanionCourse({
              call: rpc,
              key: keyRef.current,
              parsed: target,
              scope,
              goal: goal.trim(),
              level: level || null,
              subjectDomain: subjectDomain.trim() || null,
              locale: locale.trim() || null,
              presentationMode,
              learnerLabel: (syllabusCourseFields(target).title || 'Companion course')
            })
            setSubmitting(false)
            if (!outcome.ok) {
              setFailure(outcome.error || { code: 'INTERNAL_ERROR', message: 'The course could not be created.' })
              return
            }
            onCreated && onCreated(outcome)
          },
          children: submitting ? 'Creating the course' : SYLLABUS_COPY.startsCompanion
        })
      ] })
    ] })
  }

  return jsx(SyllabusParseReview, {
    parsed: target,
    blocks: (target && target.blocks) || [],
    busy: Boolean(busy),
    continueLabel: revisionOnly ? 'Check the new version' : null,
    onBack: onCancel,
    // UI-K13: a syllabus imported by mistake can be removed from the surface that read it. The
    // removal deletes the parse; this flow then returns to the entry point instead of leaving the
    // sheet on a document that no longer exists.
    onRemoved: () => {
      onCancel && onCancel()
    },
    onContinue: () => {
      if (revisionOnly) {
        // A new revision is not a new course: the parse is recorded, the mapping is now stale, and
        // the screen returns to the course so the learner can see that before anything else.
        onCreated && onCreated({ revision: target.revision, syllabusId: target.syllabus_id })
        return
      }
      const proposal = syllabusScopeProposal(target)
      setScope(proposal.proposal || 'short')
      setStep('scope')
    }
  })
}

/** The entry point, shared by Library and the first-run card. Two import paths, said plainly. */
function SyllabusEntry({ onStartSyllabus, onStartImport, compact }) {
  return jsxs('div', {
    className: compact ? 'mb-2 flex flex-wrap items-center gap-2' : 'mb-4 flex flex-col gap-2 border-b border-(--ui-stroke-tertiary) pb-3',
    'data-cb-syllabus': 'entry',
    children: [
      compact
        ? null
        : jsxs('div', { className: 'flex flex-col gap-1', children: [
            jsx('div', { className: 'text-sm font-medium', children: SYLLABUS_COPY.entryTitle }),
            jsx('div', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: SYLLABUS_COPY.entryBody })
          ] }),
      onStartSyllabus
        ? jsx(sdk.Button, { size: 'sm', variant: compact ? 'secondary' : 'default', onClick: onStartSyllabus, children: SYLLABUS_COPY.action })
        : null,
      onStartImport
        ? jsx(sdk.Button, { size: 'sm', variant: 'ghost', onClick: onStartImport, children: 'Import a pack' })
        : null
    ]
  })
}


