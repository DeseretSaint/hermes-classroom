/** Overview: the course summary, one next move, the route, then recent evidence and reference. */
function OverviewView({ row, page, review, quizzes, outline, implemented, onOpenSection, onResume }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const next = row.next_step || {}
  const section = page && page.section
  const due = review && Array.isArray(review.items) ? review.items.filter((item) => item.overdue) : []
  const recent = quizzes && Array.isArray(quizzes.attempts) ? quizzes.attempts.slice(0, 3) : []
  const warning = row.warning ? WARNING_COPY_LEARNING[row.warning] : null
  const objectives = outline && Array.isArray(outline.objectives) ? outline.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const progress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const nextEntry = mainlineObjective(row, objectives)
  const nextTitle = section ? section.title : nextEntry ? nextEntry.title : next.label || null
  const nextSemantic = nextEntry ? sectionStateSemantic(nextEntry.state, true) : null
  const currentId = section ? section.objective_id : nextEntry ? nextEntry.objective_id : null
  const phone = cbLayoutFor(useCbViewportWidth()) === 'phone'

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-5',
    children: [
      warning ? jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: warning }) : null,

      jsx(CourseIdentity, {
        title: row.title || 'This course',
        progress: progress.statement || progressStatement(progress.independent, progress.total),
        nextTitle,
        nextSemantic,
        compact: true
      }),

      // One next move, in the same row language as the course index: the row itself is the action
      // and the primary button is the only filled control on the screen.
      jsxs('section', {
        'data-cb-overview-next': currentId || 'none',
        style: { display: 'flex', flexDirection: 'column', gap: '0.6rem', maxWidth: '46rem' },
        children: [
          jsxs('div', {
            style: {
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.9rem',
              padding: '0.9rem 0.9rem 0.9rem 1rem',
              background: 'var(--cb-lamp-soft)',
              borderTop: '1px solid var(--cb-lamp)',
              boxSizing: 'border-box'
            },
            children: [
              jsx('span', {
                'aria-hidden': 'true',
                style: {
                  flex: '0 0 2.5rem',
                  fontFamily: CB_SANS,
                  fontVariantNumeric: 'tabular-nums',
                  fontSize: CB_TYPE.meta,
                  fontWeight: 600,
                  lineHeight: 1.6,
                  color: 'var(--cb-ink-soft)'
                },
                children: section && section.ordinal ? String(section.ordinal).padStart(2, '0') : '—'
              }),
              jsxs('div', {
                style: { display: 'flex', flexDirection: 'column', gap: '0.25rem', minWidth: 0, flex: '1 1 auto' },
                children: [
                  jsx('div', {
                    style: {
                      fontFamily: CB_SERIF,
                      fontSize: CB_TYPE.heading,
                      fontWeight: 600,
                      lineHeight: 1.25,
                      color: 'var(--cb-ink)',
                      overflowWrap: 'anywhere'
                    },
                    children: nextTitle || 'No objective recorded yet'
                  }),
                  section
                    ? jsxs('div', { style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' } , children: [
                        jsx(CbStatePill, { state: section.state }),
                        section.evidence_target
                          ? jsx('span', {
                              style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                              children: learnerEvidenceTarget(section.evidence_target)
                            })
                          : null
                      ] })
                    : null,
                  jsx('div', {
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                    children: next.label ? `Next: ${next.label}` : 'The backend did not return a next step for this course.'
                  })
                ]
              })
            ]
          }),
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.6rem' },
            children: [
              jsx(CbAction, {
                variant: 'primary',
                disabled: !section,
                onClick: () => onResume(section ? section.objective_id : null),
                children: next.kind === 'resume_lesson' ? 'Resume the lesson' : 'Start a fresh run'
              }),
              jsx(CbAction, {
                variant: 'tertiary',
                disabled: !section,
                onClick: () => onOpenSection(section ? section.objective_id : null),
                children: 'Read this section'
              })
            ]
          })
        ]
      }),

      objectives.length > 0
        ? jsxs('section', {
            'data-cb-overview-route': '',
            style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
            children: [
              jsx(PlateHead, {
                title: `${objectives.length} ${objectives.length === 1 ? 'section' : 'sections'}`
              }),
              jsx(RouteSpine, {
                objectives,
                currentId,
                phone,
                onSelect: (objectiveId) => onOpenSection(objectiveId),
                ariaLabel: 'Course sections'
              })
            ]
          })
        : null,

      jsxs('section', {
        'data-cb-overview-evidence': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
        children: [
          jsx(PlateHead, {
            title: 'Recent evidence',
            caption: due.length > 0 ? `${due.length} ${due.length === 1 ? 'section is' : 'sections are'} due for review.` : null
          }),
          recent.length > 0
            ? jsx('div', {
                style: { display: 'flex', flexDirection: 'column' },
                children: recent.map((attempt, index) =>
                  jsxs('div', {
                    'data-cb-evidence-row': attempt.attempt_id || String(index),
                    style: {
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'baseline',
                      justifyContent: 'space-between',
                      gap: '0.2rem 0.75rem',
                      padding: '0.45rem 0',
                      borderTop: index === 0 ? '1px solid var(--cb-rule)' : '1px solid var(--cb-rule)',
                      fontFamily: CB_SANS,
                      fontSize: CB_TYPE.caption,
                      lineHeight: 1.45
                    },
                    children: [
                      jsx('span', {
                        style: { color: 'var(--cb-ink-soft)' },
                        children: `${verdictLabel(attempt.verdict, attempt.evidence_class)} · ${whenLabel(attempt.committed_at || attempt.created_at)}`
                      }),
                      jsx(EvidenceClassText, { value: attempt.evidence_class })
                    ]
                  }, attempt.attempt_id || index)
                )
              })
            : jsx('p', {
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                children: 'No attempt has been recorded on this course yet.'
              }),
          due.length > 0
            ? jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                className: 'self-start',
                onClick: () => onOpenSection(due[0].objective_id),
                children: `Start with the oldest: ${due[0].title || 'the first section due'}`
              })
            : null
        ]
      }),

      // Reference material, not the headline: it opens on purpose, after the learner has already
      // read where they are and what is next.
      jsxs('details', {
        'data-cb-overview-details': '',
        className: 'flex flex-col',
        children: [
          jsx('summary', {
            className: 'cursor-pointer text-xs font-medium text-(--ui-text-secondary)',
            children: 'Course details'
          }),
          jsxs('div', {
            className: 'flex flex-col pt-1',
            children: [
              jsx(StatusRow, {
                label: 'How you will use it',
                value: (RECIPE_COPY[row.recipe] || {}).title || 'Not recorded'
              }),
              jsx(StatusRow, {
                label: 'Enrolment',
                value: enrollmentStatusLabel(row.enrollment_status)
              }),
              jsx(StatusRow, {
                label: 'Evidence',
                value: `${Number(summary.independent || 0)} independent`,
                detail: `${plural(Number(summary.total_objectives || 0), 'objective', 'objectives')} · ${plural(Number(summary.review_due || 0), 'due', 'due')}`
              }),
              jsx(StatusRow, {
                label: 'Where it came from',
                value: sourceLabel(row.provenance && row.provenance.source),
                detail: row.provenance && row.provenance.pack_id ? `${row.provenance.pack_id}${row.provenance.pack_version ? ` v${row.provenance.pack_version}` : ''}` : 'authored on this profile'
              }),
              supports('pack.export') && row.provenance && row.provenance.pack_id
                ? jsx(QuietNote, { children: 'Exporting the pack is a Library action; it never includes your answers or notes.' })
                : null
            ]
          })
        ]
      })
    ]
  })
}

/**
 * A deterministic field-note mark, seeded from the course title.
 *
 * This is composition, not a second theme: every stroke is a `--cb-*` token, there is no gradient,
 * no image asset and no randomness, so the same course paints the same mark on every render. It is
 * decorative (`aria-hidden`), and the course title beside it carries the identity in text.
 */
function fieldNoteSeed(text) {
  let hash = 2166136261
  const value = String(text || '')
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619) >>> 0
  }
  return hash
}

function FieldNoteMark({ title, compact }) {
  const seed = fieldNoteSeed(title)
  // Ruled-note strokes, not a bar chart: every line is horizontal and the variation is indentation
  // and length, so the mark cannot be misread as a progress meter.
  const lines = Array.from({ length: 5 }, (_, index) => {
    const width = 34 + (((seed >>> (index * 5)) & 0xff) % 58)
    const indent = ((seed >>> (index * 5 + 3)) & 0x1) * 8
    return { width, indent, y: 5 + index * 6, accent: index === 2 }
  })
  return jsx('svg', {
    'aria-hidden': 'true',
    focusable: 'false',
    width: compact ? '76' : '108',
    height: compact ? '24' : '32',
    viewBox: '0 0 108 32',
    'data-cb-field-note': '',
    style: { flex: '0 0 auto' },
    children: lines.map((line, index) =>
      jsx(
        'line',
        {
          x1: line.indent,
          y1: line.y,
          x2: line.indent + line.width,
          y2: line.y,
          stroke: line.accent ? 'var(--cb-accent)' : 'var(--cb-rule)',
          strokeWidth: line.accent ? 1.8 : 1,
          strokeLinecap: 'round'
        },
        index
      )
    )
  })
}

/** The token that tints a state's icon; the word beside it is what actually names the state. */
function sectionToneColor(key) {
  if (key === 'complete') return 'var(--cb-field)'
  if (key === 'review') return 'var(--cb-ochre)'
  if (key === 'next') return 'var(--cb-accent)'
  return 'var(--cb-ink-soft)'
}

/**
 * The course line: the title, the recorded progress sentence and the next move, in that order.
 * It is a summary strip, not a hero — the course hero belongs to Course Detail — so it carries no
 * lamp field, no seal and no action. Every value is one the backend recorded; there is no percent,
 * ring or streak (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §3, §4.4).
 */
function CourseIdentity({ title, subtitle, progress, nextTitle, nextSemantic, compact }) {
  return jsxs('section', {
    'data-cb-identity': compact ? 'summary' : 'course',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.3rem',
      padding: compact ? '0.15rem 0 0.55rem' : '0.2rem 0 0.7rem',
      borderBottom: '1px solid var(--cb-rule)',
      maxWidth: '46rem'
    },
    children: [
      jsx('h2', {
        style: {
          margin: 0,
          fontFamily: CB_SERIF,
          fontSize: compact ? CB_TYPE.heading : CB_TYPE.heading,
          fontWeight: 600,
          lineHeight: 1.15,
          letterSpacing: '-0.01em',
          color: 'var(--cb-ink)',
          maxWidth: '34ch',
          overflowWrap: 'anywhere'
        },
        children: title
      }),
      jsx('div', {
        'data-cb-progress-statement': '',
        style: {
          fontFamily: CB_SANS,
          fontVariantNumeric: 'tabular-nums',
          fontSize: CB_TYPE.meta,
          lineHeight: 1.5,
          color: 'var(--cb-ink-soft)'
        },
        children: progress
      }),
      nextTitle
        ? jsxs('div', {
            'data-cb-next-statement': '',
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.35rem', fontFamily: CB_SANS, fontSize: CB_TYPE.meta },
            children: [
              jsx('span', { style: { fontWeight: 600, color: 'var(--cb-accent)' }, children: 'Next ·' }),
              jsx('span', { style: { color: 'var(--cb-ink)', overflowWrap: 'anywhere' }, children: nextTitle }),
              nextSemantic
                ? jsx('span', { style: { color: sectionToneColor(nextSemantic.key) }, children: ` ${nextSemantic.label}` })
                : null
            ]
          })
        : null,
      subtitle
        ? jsx('div', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }, children: subtitle })
        : null
    ]
  })
}

/**
 * One section row in the course index: a 40px number gutter, a serif title, one honest subline
 * and the state word at the end. The row itself is the action — no chevron-only affordance, no
 * repeated "Open section" label, no card border. State is a word plus its hue, never colour alone
 * (docs/COURSEBOOK-VISUAL-IDENTITY-V2.md §4.6).
 */
function SectionRow({ entry, semantic, isNext, onOpen }) {
  const [hover, setHover] = useState(false)
  const target = learnerEvidenceTarget(entry.evidence_target)
  const subline = target || (isNext && entry.last_opened_at ? `Last opened ${whenLabel(entry.last_opened_at)}` : null)
  return jsx(sdk.Button, {
    variant: 'text',
    className: 'w-full justify-start',
    'aria-current': isNext ? 'step' : undefined,
    'data-cb-section-row': entry.objective_id,
    'data-cb-section-state': semantic.key,
    onClick: () => onOpen(entry.objective_id),
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    onFocus: () => setHover(true),
    onBlur: () => setHover(false),
    children: jsxs('span', {
      style: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.9rem',
        width: '100%',
        padding: '0.8rem 0.35rem 0.8rem 0.6rem',
        boxSizing: 'border-box',
        textAlign: 'left',
        borderTop: '1px solid var(--cb-rule)',
        borderLeft: isNext ? '2px solid var(--cb-accent)' : '2px solid transparent',
        background: isNext ? 'var(--cb-accent-soft)' : hover ? 'var(--cb-accent-soft)' : 'transparent'
      },
      children: [
        jsx('span', {
          'aria-hidden': 'true',
          style: {
            flex: '0 0 2.5rem',
            fontFamily: CB_SANS,
            fontVariantNumeric: 'tabular-nums',
            fontSize: CB_TYPE.meta,
            fontWeight: 600,
            lineHeight: 1.6,
            color: isNext ? 'var(--cb-accent)' : 'var(--cb-ink-soft)'
          },
          children: String(entry.ordinal || 0).padStart(2, '0')
        }),
        jsxs('span', {
          style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', minWidth: 0, flex: '1 1 auto' },
          children: [
            jsx('span', {
              style: {
                overflowWrap: 'anywhere',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                fontFamily: CB_SERIF,
                fontSize: CB_TYPE.lead,
                fontWeight: 600,
                lineHeight: 1.3,
                color: 'var(--cb-ink)'
              },
              children: entry.title
            }),
            subline
              ? jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }, children: subline })
              : null
          ]
        }),
        jsx('span', {
          'data-cb-section-pill': semantic.key,
          style: { flex: '0 0 auto', alignSelf: 'center' },
          children: jsx(CbStatePill, { state: entry.state })
        })
      ]
    })
  })
}

/** A unit heading with its own progress line, shown only when the plan really has more than one. */
function UnitHeading({ unit, entries }) {
  const progress = objectiveProgress(entries)
  const blocked =
    unit.prerequisite_state === 'unmet' && Array.isArray(unit.prereq_unit_ordinals) && unit.prereq_unit_ordinals.length > 0
  return jsxs('div', {
    'data-cb-unit': String(unit.ordinal),
    style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', paddingTop: '0.55rem' },
    children: [
      jsxs('div', {
        style: {
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '0.2rem 0.75rem',
          borderBottom: '1px solid var(--cb-rule)',
          paddingBottom: '0.3rem'
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.45rem', minWidth: 0 },
            children: [
              jsx('span', {
                style: {
                  fontSize: CB_TYPE.caption,
                  fontWeight: 600,
                  letterSpacing: '0.01em',
                  color: 'var(--cb-ink-soft)'
                },
                children: `Unit ${unit.ordinal}`
              }),
              jsx('span', {
                style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)', overflowWrap: 'anywhere' },
                children: unit.title
              })
            ]
          }),
          jsx('span', {
            'data-cb-unit-progress': '',
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: progress.statement
          })
        ]
      }),
      blocked
        ? jsx('div', {
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `This unit starts after Unit ${unit.prereq_unit_ordinals.join(', ')}. You can still open it.`
          })
        : null
    ]
  })
}

/**
 * The index's one details affordance: the legend and the rubric's own construct names.
 *
 * A learner never has to decode "discrimination" in the list — the row says "Tell the difference".
 * The raw id is still auditable here, inside a panel the learner opens on purpose.
 */
function TextbookIndexDetails({ rows }) {
  const targets = Array.from(new Set(rows.map((entry) => entry.evidence_target).filter(Boolean)))
  const legend = [
    { semantic: { key: 'complete', label: 'Complete', icon: 'pass' }, meaning: 'this objective has independent evidence.' },
    { semantic: { key: 'next', label: 'Next', icon: 'chevron-right' }, meaning: 'the section the course points to now.' },
    { semantic: { key: 'review', label: 'Review due', icon: 'history' }, meaning: 'evidence is scheduled to come back.' },
    { semantic: { key: 'not_started', label: 'Not started', icon: 'circle-outline' }, meaning: 'no attempt recorded yet.' }
  ]
  return jsxs('details', {
    'data-cb-index-details': '',
    style: { maxWidth: '46rem', paddingTop: '0.2rem' },
    children: [
      jsx('summary', {
        style: { cursor: 'pointer', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
        children: 'What the states and check types mean'
      }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingTop: '0.4rem' },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.2rem' },
            children: legend.map((entry) =>
              jsxs(
                'div',
                {
                  style: { display: 'flex', alignItems: 'baseline', gap: '0.4rem', fontSize: CB_TYPE.caption },
                  children: [
                    jsx('span', { style: { color: sectionToneColor(entry.semantic.key) }, children: entry.semantic.label }),
                    jsx('span', { style: { color: 'var(--cb-ink-soft)' }, children: `— ${entry.meaning}` })
                  ]
                },
                entry.semantic.key
              )
            )
          }),
          targets.length > 0
            ? jsxs('div', {
                'data-cb-check-types': '',
                style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: CB_TYPE.caption },
                children: [
                  jsx('div', {
                    style: { fontWeight: 600, color: 'var(--cb-ink-soft)' },
                    children: 'Check types in this course'
                  }),
                  ...targets.map((target) =>
                    jsx(
                      'div',
                      {
                        style: { color: 'var(--cb-ink-soft)' },
                        children: `${learnerEvidenceTarget(target)} — the backend calls this “${target}”.`
                      },
                      target
                    )
                  )
                ]
              })
            : null
        ]
      })
    ]
  })
}

/** Textbook — a scannable section list, not one endless thread. */
function TextbookView({ row, page, pageState, review, notebooks, outline, planStatus, jobs, implemented, defaultLessonView, openSectionId, onOpenSection, onCloseSection, onChanged, onOpenPlan, onRetryLessonsJob, targetBlockId }) {
  const rows = sectionRows({ row, review, notebooks, outline, page })
  const hasOutline = Boolean(outline && Array.isArray(outline.objectives))
  const objectives = hasOutline ? outline.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const progress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const nextEntry = mainlineObjective(row, objectives) || rows.find((entry) => !entry.independent) || null
  const nextSemantic = nextEntry ? sectionStateSemantic(nextEntry.state, true) : null
  const nextTitle = nextEntry ? nextEntry.title : null

  // A plan with more than one unit groups its sections. One implicit unit (a legacy or pack plan)
  // stays a flat list: the backend's single unit is not a heading the learner should have to read.
  const units =
    outline && outline.plan && Array.isArray(outline.plan.units)
      ? outline.plan.units.filter((unit) => unit && Array.isArray(unit.objectives))
      : []
  const rowIndex = new Map(rows.map((entry) => [entry.objective_id, entry]))
  const grouped = units.length > 1
  const groups = grouped
    ? units.map((unit) => ({
        unit,
        entries: unit.objectives
          .map((objective) => rowIndex.get(objective && objective.objective_id) || objective)
          .filter((entry) => entry && entry.objective_id)
      }))
    : []
  const groupedIds = new Set(groups.flatMap((group) => group.entries.map((entry) => entry.objective_id)))
  const extras = grouped ? rows.filter((entry) => !groupedIds.has(entry.objective_id)) : []

  // Opening a section is owned by CourseDetail, so a route in from Overview, Notebook or Quizzes
  // ("Continue from here") lands on the same durable page as a click in this list, and the
  // `lesson.page` request that backs it is always aimed at the section being shown.
  if (openSectionId) {
    return jsx(SectionPage, {
      row,
      objectiveId: openSectionId,
      defaultLessonView,
      page: page && page.section && page.section.objective_id === openSectionId ? page : null,
      pageStatus: pageState.status,
      pageError: pageState.error,
      onRetryPage: pageState.reload,
      implemented,
      review,
      outline,
      planStatus,
      jobs,
      onOpenPlan,
      onRetryLessonsJob,
      onBack: onCloseSection,
      onChanged,
      targetBlockId: targetBlockId || null,
      // Inside Course Detail the page hero owns the primary; the embedded section does not repeat it.
      embedded: true
    })
  }

  const rowFor = (entry) => {
    const isNext = Boolean(nextEntry && nextEntry.objective_id === entry.objective_id)
    return jsx(
      SectionRow,
      {
        entry,
        semantic: sectionStateSemantic(entry.state, isNext),
        isNext,
        onOpen: onOpenSection
      },
      entry.objective_id
    )
  }

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-4',
    children: [
      jsx(CourseIdentity, {
        title: row.title || 'This course',
        progress: progress.statement || progressStatement(progress.independent, progress.total),
        nextTitle,
        nextSemantic,
        compact: true
      }),
      // The reading plate: what is here, how much of it carries evidence, and the one line that
      // explains the measure. The old identity paragraph becomes this caption.
      jsxs('section', {
        'data-cb-reading-plate': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.55rem' },
        children: [
          jsx(PlateHead, {
            title: `${rows.length} ${rows.length === 1 ? 'section' : 'sections'}`,
            caption: progress.due > 0
              ? `${progress.due} ${progress.due === 1 ? 'section is' : 'sections are'} due for review.`
              : null
          }),
          objectives.length > 0
            ? jsx(EvidenceTally, {
                objectives,
                caption: progress.statement || progressStatement(progress.independent, progress.total)
              })
            : null,
          jsx('p', {
            'data-cb-reading-caption': '',
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
            children: '66 characters per line. Evidence is named, never estimated.'
          })
        ]
      }),
      hasOutline
        ? null
        : jsx(QuietNote, {
            children:
              'This build can name the current section and every section with scheduled evidence. The complete ' +
              'section list needs course.outline; rows light up here automatically once that command is registered.'
          }),
      rows.length === 0
        ? jsx(EmptyState, {
            title: 'No sections yet',
            description: 'A section appears once the course has an approved plan with objectives. Approve the plan first.'
          })
        : grouped
          ? jsxs('div', {
              className: 'flex flex-col',
              children: [
                ...groups.map((group) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-col',
                      children: [
                        jsx(UnitHeading, { unit: group.unit, entries: group.entries }, `unit-${group.unit.ordinal}`),
                        ...group.entries.map(rowFor)
                      ]
                    },
                    `group-${group.unit.ordinal}`
                  )
                ),
                extras.length > 0
                  ? jsxs('div', {
                      className: 'flex flex-col',
                      children: [
                        jsx('div', {
                          style: {
                            fontSize: CB_TYPE.caption,
                            color: 'var(--cb-ink-soft)',
                            paddingTop: '0.55rem',
                            borderBottom: '1px solid var(--cb-rule)',
                            paddingBottom: '0.3rem'
                          },
                          children: 'Also recorded on this course'
                        }),
                        ...extras.map(rowFor)
                      ]
                    })
                  : null
              ]
            })
          : jsx('div', { className: 'flex flex-col', children: rows.map(rowFor) }),
      jsx(TextbookIndexDetails, { rows }),
      !hasOutline
        ? jsx(QuietNote, {
            children:
              'Jumping backward never erases later evidence: each section keeps its own lesson runs, attempts and notebook saves.'
          })
        : null
    ]
  })
}

/** Notebook — saved moments, searchable, editable, with a route back to the exact section. */
function NotebookView({ row, notebooks, implemented, onOpenSection, onChanged, sections }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState('all')
  const [order, setOrder] = useState('recent')
  const [editing, setEditing] = useState(null)
  const [editNote, setEditNote] = useState('')
  const [editTags, setEditTags] = useState('')
  const [pendingRemove, setPendingRemove] = useState(null)
  const [undo, setUndo] = useState(null)
  const [error, setError] = useState(null)
  const editTriggerRef = useRef(null)

  useEffect(() => {
    if (!pluginContext) return undefined
    const timer = pluginContext.setTimeout(() => setQuery(searchInput.trim()), 250)
    return timer
  }, [searchInput])

  const entries = notebooks && Array.isArray(notebooks.entries) ? notebooks.entries : []
  const sectionTitles = {}
  ;(sections || []).forEach((entry) => {
    if (entry && entry.objective_id && entry.title) sectionTitles[entry.objective_id] = entry.title
  })
  const [mediaOpen, setMediaOpen] = useState(null)
  const tags = Array.from(new Set(entries.flatMap((entry) => entry.tags || []))).sort()
  const filtered = entries
    .filter((entry) => {
      if (tag !== 'all' && !(entry.tags || []).includes(tag)) return false
      if (!query) return true
      const needle = query.toLowerCase()
      return [entry.excerpt, entry.note, entry.kind, (entry.tags || []).join(' ')]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    })
    .slice()
    .sort((left, right) =>
      order === 'recent'
        ? String(right.created_at || '').localeCompare(String(left.created_at || ''))
        : String(left.created_at || '').localeCompare(String(right.created_at || ''))
    )

  // GM-008 — homework taken with you. A homework task is not a notebook entry: the notebook is
  // where the learner finds it again. The ids come from a save whose `source_ref` names the task
  // and from this device's index; every row is then read through `homework.read`, so a state
  // shown here is the backend's, never a cached copy.
  const homeworkIds = []
  const addHomework = (taskId, objectiveId, createdAt) => {
    if (!taskId || homeworkIds.some((row) => row.task_id === taskId)) return
    homeworkIds.push({ task_id: taskId, objective_id: objectiveId || null, created_at: createdAt || '' })
  }
  entries.forEach((entry) => {
    const taskId = cbHomeworkRefTaskId(entry.source_ref)
    if (taskId) addHomework(taskId, entry.objective_id, entry.created_at)
  })
  cbHomeworkIndexRows(row.enrollment_id).forEach((item) =>
    addHomework(item.task_id, item.objective_id, item.created_at)
  )
  homeworkIds.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)))
  const homeworkRows = homeworkIds.map((item) => ({
    task_id: item.task_id,
    lesson_title: sectionTitles[item.objective_id] || '',
    course_title: row.title || ''
  }))

  const saveEdit = useCallback(async () => {
    if (!editing) return
    const payload = { entry_id: editing.entry_id }
    payload.note = editNote.trim() || null
    payload.tags = editTags
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 20)
    const response = await rpc('notebook.update', payload, {
      // The entry carries its own revision fence (0 for a fresh save), so the edit is fenced on the
      // row the user is editing rather than on the enrollment.
      expectedRevision: typeof editing.revision === 'number' ? editing.revision : 0,
      idempotencyKey: newOperationId('notebook-update')
    })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setEditing(null)
    onChanged()
    // The editor's fields unmount here; hand focus back to the control that opened them.
    editTriggerRef.current?.focus({ preventScroll: true })
  }, [editing, editNote, editTags, onChanged])

  const removeEntry = useCallback(async () => {
    if (!pendingRemove) return
    const entry = pendingRemove
    const response = await rpc('notebook.delete', { entry_id: entry.entry_id })
    setPendingRemove(null)
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setUndo(entry)
    onChanged()
  }, [pendingRemove, onChanged])

  const undoRemove = useCallback(async () => {
    if (!undo) return
    const response = await rpc('notebook.save', {
      enrollment_id: undo.enrollment_id,
      objective_id: undo.objective_id,
      lesson_run_id: undo.lesson_run_id || null,
      kind: undo.kind,
      excerpt: undo.excerpt,
      note: undo.note,
      tags: undo.tags || [],
      source_ref: undo.source_ref || null
    })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setUndo(null)
    onChanged()
  }, [undo, onChanged])

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.SearchField, {
            'aria-label': 'Search the notebook',
            containerClassName: 'max-w-sm min-w-0 flex-1',
            onChange: setSearchInput,
            placeholder: 'Search notes and excerpts',
            value: searchInput
          }),
          jsxs(sdk.Select, {
            value: tag,
            onValueChange: setTag,
            children: [
              jsx(
                sdk.SelectTrigger,
                {
                  'aria-label': 'Filter by tag',
                  className: 'w-40',
                  children: jsx(sdk.SelectValue, { placeholder: 'All tags' })
                },
                'trigger'
              ),
              jsx(
                sdk.SelectContent,
                {
                  children: [{ id: 'all', label: 'All tags' }]
                    .concat(tags.map((item) => ({ id: item, label: item })))
                    .map((option) => jsx(sdk.SelectItem, { value: option.id, children: option.label }, option.id))
                },
                'content'
              )
            ]
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setOrder,
            options: [
              { id: 'recent', label: 'Recently saved' },
              { id: 'oldest', label: 'Oldest first' }
            ],
            sizing: 'content',
            value: order
          })
        ]
      }),
      error ? jsx(ErrorLine, { error }) : null,
      undo
        ? jsxs('div', {
            className: 'flex flex-wrap items-center justify-between gap-2 border-l border-(--ui-stroke-secondary) pl-3',
            children: [
              jsx('div', {
                className: 'text-xs text-(--ui-text-secondary)',
                children: 'Removed from the notebook. The lesson and any media it referenced are untouched.'
              }),
              jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: undoRemove, children: 'Undo (restores as a new entry)' })
            ]
          })
        : null,

      homeworkRows.length > 0
        ? jsxs('div', {
            'data-cb-notebook-homework': String(homeworkRows.length),
            className: 'flex flex-col gap-2',
            children: [
              jsx(CbLabel, { children: 'Taken with you' }),
              jsx(HomeworkRecordList, {
                rows: homeworkRows,
                actor: 'learner',
                canSave: false,
                onChange: onChanged,
                emptyTitle: 'No homework yet',
                emptyDescription: 'A task you take with you from a lesson is listed here.'
              })
            ]
          })
        : null,

      filtered.length === 0
        ? jsx(EmptyState, {
            title: entries.length === 0 ? 'Nothing saved yet' : 'No saved moment matches',
            description:
              entries.length === 0
                ? 'Save an explanation, visual or quiz moment and it will appear here.'
                : 'Your saved moments are still here; this search or tag just excludes them.',
            children:
              entries.length === 0
                ? jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => onOpenSection(row.evidence_summary && row.evidence_summary.current_objective_id),
                    children: 'Go to the current lesson'
                  })
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                      setSearchInput('')
                      setQuery('')
                      setTag('all')
                    },
                    children: 'Clear search and tag'
                  })
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: filtered.map((entry) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsx('div', {
                      className: 'max-w-3xl',
                      children: jsx(ProseText, { text: entry.excerpt || entry.note || entry.kind })
                    }),
                    entry.note && entry.excerpt
                      ? jsx('p', { className: 'max-w-prose text-xs text-(--ui-text-secondary)', children: entry.note })
                      : null,
                    mediaOpen === entry.entry_id
                      ? jsx(MediaSegment, {
                          segment: {
                            artifact_id: readNotebookRef(entry.source_ref).artifact_id,
                            text: entry.excerpt
                          }
                        })
                      : null,
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
                      children: [
                        jsx('span', {
                          'data-cb-note-lesson': sectionTitles[entry.objective_id] || 'This lesson',
                          children: sectionTitles[entry.objective_id] || 'This lesson'
                        }),
                        row.title ? jsx('span', { children: `Course · ${row.title}` }) : null
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-1',
                      children: [
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => onOpenSection(entry.objective_id, readNotebookRef(entry.source_ref).block_id),
                          children: 'Open in textbook'
                        }),
                        readNotebookRef(entry.source_ref).artifact_id
                          ? jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              'aria-expanded': mediaOpen === entry.entry_id ? 'true' : 'false',
                              onClick: () => setMediaOpen(mediaOpen === entry.entry_id ? null : entry.entry_id),
                              children: 'Play/view media'
                            })
                          : null,
                        supports('notebook.update')
                          ? jsx(sdk.Button, {
                              variant: 'text',
                              size: 'sm',
                              onClick: (event) => {
                                editTriggerRef.current = event.currentTarget
                                setEditing(entry)
                                setEditNote(entry.note || '')
                                setEditTags((entry.tags || []).join(', '))
                              },
                              children: 'Edit note and tags'
                            })
                          : null,
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => setPendingRemove(entry),
                          children: 'Remove from notebook'
                        })
                      ]
                    }),
                    // H-189: the saved row's machine-facing anchors (kind enum, tag enums, the
                    // objective id, source ids, the saved-from metadata) live here, behind the
                    // existing Technical detail disclosure. The learner-facing row above is the
                    // note, the lesson and one way back.
                    jsxs('details', {
                      'data-cb-note-technical': entry.entry_id,
                      className: 'text-xs text-(--ui-text-secondary)',
                      children: [
                        jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }),
                        jsxs('div', {
                          className: 'flex flex-col gap-1 pt-1',
                          children: [
                            jsx('span', {
                              'data-cb-note-section': entry.objective_id,
                              children: `Section id · ${entry.objective_id || 'not recorded'}`
                            }),
                            jsx('span', { children: `Saved from · ${entry.kind || 'not recorded'}` }),
                            readNotebookRef(entry.source_ref).source_ids.length > 0
                              ? jsx('span', {
                                  children: `Source · ${readNotebookRef(entry.source_ref).source_ids.join(', ')}`
                                })
                              : null,
                            (entry.tags || []).length > 0
                              ? jsx('span', { children: `Tags · ${(entry.tags || []).join(', ')}` })
                              : null,
                            jsx('span', { children: `Saved ${whenLabel(entry.created_at)}` })
                          ]
                        })
                      ]
                    }),
                    editing && editing.entry_id === entry.entry_id
                      ? jsxs('div', {
                          className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                          children: [
                            jsx('label', {
                              htmlFor: 'cb-edit-note',
                              className: 'text-xs font-medium text-(--ui-text-secondary)',
                              children: 'Your note'
                            }),
                            jsx(sdk.Textarea, {
                              id: 'cb-edit-note',
                              rows: 2,
                              value: editNote,
                              onChange: (event) => setEditNote(event.target.value)
                            }),
                            jsx('label', {
                              htmlFor: 'cb-edit-tags',
                              className: 'text-xs font-medium text-(--ui-text-secondary)',
                              children: 'Tags (comma separated)'
                            }),
                            jsx(sdk.Input, {
                              id: 'cb-edit-tags',
                              value: editTags,
                              onChange: (event) => setEditTags(event.target.value)
                            }),
                            jsxs('div', {
                              className: 'flex items-center gap-2',
                              children: [
                                jsx(CbAction, { variant: 'primary', size: 'sm', onClick: saveEdit, children: 'Save changes' }),
                                jsx(sdk.Button, {
                                  variant: 'text',
                                  size: 'sm',
                                  onClick: () => {
                                    setEditing(null)
                                    editTriggerRef.current?.focus({ preventScroll: true })
                                  },
                                  children: 'Cancel'
                                })
                              ]
                            })
                          ]
                        })
                      : null
                  ]
                },
                entry.entry_id
              )
            )
          }),

      jsx(FocusReturningDialog, {
        open: Boolean(pendingRemove),
        title: 'Remove this moment from the notebook?',
        description:
          'Only the notebook entry is removed. The lesson, its attempts and any media it referenced are kept.',
        confirmLabel: 'Remove entry',
        onClose: () => setPendingRemove(null),
        onConfirm: removeEntry,
        children: null
      })
    ]
  })
}

/** Quizzes — past attempts with their original feedback, read-only until an explicit new version. */
function QuizzesView({ row, quizzes, implemented, onOpenSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const [verdict, setVerdict] = useState('all')
  const [klass, setKlass] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [disputeNote, setDisputeNote] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [saveSeed, setSaveSeed] = useState(null)

  const attempts = quizzes && Array.isArray(quizzes.attempts) ? quizzes.attempts : []
  const filtered = attempts.filter((attempt) => {
    if (verdict !== 'all' && attempt.verdict !== verdict) return false
    if (klass !== 'all' && attempt.evidence_class !== klass) return false
    return true
  })
  const selected = filtered.find((attempt) => attempt.attempt_id === selectedId) || null

  const newVersion = useCallback(
    async (attempt) => {
      setError(null)
      setNotice(null)
      const response = await rpc(
        'progression.challenge_out',
        { enrollment_id: row.enrollment_id, objective_id: attempt.objective_id },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setError(response.error)
        return
      }
      setNotice('A new audited version of this check is open. The original attempt stays inspectable.')
      onChanged()
    },
    [row, onChanged]
  )

  const dispute = useCallback(async () => {
    if (!selected) return
    if (disputeNote.trim().length < 3) {
      setError({ code: 'VALIDATION_FAILED', message: 'Write at least a sentence explaining the dispute.' })
      return
    }
    const response = await rpc('attempt.dispute', { attempt_id: selected.attempt_id, note: disputeNote.trim() })
    if (!response.ok) {
      setError(response.error)
      return
    }
    setError(null)
    setDisputeNote('')
    setNotice('Dispute recorded. The original verdict is unchanged and the history is append-only.')
    onChanged()
  }, [selected, disputeNote, onChanged])

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2',
        children: [
          jsx(sdk.SegmentedControl, {
            onChange: setVerdict,
            options: [
              { id: 'all', label: 'All results' },
              { id: 'pass', label: 'Passed' },
              { id: 'partial', label: 'Partly there' },
              { id: 'not_yet', label: 'Not yet' },
              { id: 'needs_retry', label: 'Could not be graded' }
            ],
            sizing: 'content',
            value: verdict
          }),
          jsx(sdk.SegmentedControl, {
            onChange: setKlass,
            options: [
              { id: 'all', label: 'All assistance' },
              { id: 'cold', label: 'First try' },
              { id: 'hinted', label: 'Hinted' },
              { id: 'answer_shown', label: 'Answer shown' },
              { id: 'override', label: 'Override' }
            ],
            sizing: 'content',
            value: klass
          })
        ]
      }),

      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,
      error ? jsx(ErrorLine, { error }) : null,

      filtered.length === 0
        ? jsx(EmptyState, {
            title: attempts.length === 0 ? 'No quiz attempts yet' : 'No attempt matches',
            description:
              attempts.length === 0
                ? 'Answers you give in a lesson are recorded here with their original feedback.'
                : 'Your attempts are still here; these filters just exclude them.',
            children:
              attempts.length === 0
                ? null
                : jsx(sdk.Button, {
                    variant: 'secondary',
                    size: 'sm',
                    onClick: () => {
                      setVerdict('all')
                      setKlass('all')
                    },
                    children: 'Clear filters'
                  })
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: filtered.map((attempt) =>
              jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center justify-between gap-2',
                      children: [
                        jsxs('div', {
                          className: 'flex flex-wrap items-center gap-2',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
                            jsx(EvidenceClassText, { value: attempt.evidence_class }),
                            jsx('span', { className: 'text-xs text-(--ui-text-secondary)', children: whenLabel(attempt.committed_at || attempt.created_at) })
                          ]
                        }),
                        jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => setSelectedId(attempt.attempt_id === selectedId ? null : attempt.attempt_id),
                          children: attempt.attempt_id === selectedId ? 'Close' : 'Open attempt'
                        })
                      ]
                    }),
                    attempt.answer && attempt.answer.text
                      ? jsx('p', { className: 'max-w-prose whitespace-pre-wrap break-words text-xs text-(--ui-text-secondary)', children: attempt.answer.text })
                      : null,
                    selectedId === attempt.attempt_id && selected
                      ? jsxs('div', {
                          className: 'flex flex-col gap-2 border-t border-(--ui-stroke-tertiary) pt-2',
                          children: [
                            jsx(QuietNote, { children: 'Reviewing is read-only. Nothing here consumes a retry or changes the old grade.' }),
                            (attempt.criteria || []).length > 0
                              ? jsx('ul', {
                                  className: 'flex flex-col gap-1',
                                  children: attempt.criteria.map((item, index) =>
                                    jsx(
                                      'li',
                                      {
                                        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                                        children: `${item.met ? 'Met' : 'Not met'}: ${item.observed || item.id}`
                                      },
                                      `${item.id || 'criterion'}-${index}`
                                    )
                                  )
                                })
                              : jsx(QuietNote, { children: 'No criterion detail was stored for this attempt.' }),
                            jsxs('div', {
                              className: 'flex flex-col',
                              children: [
                                jsx(StatusRow, {
                                  label: 'Grader',
                                  value: (attempt.grading_provenance && attempt.grading_provenance.grader) || 'not recorded'
                                }),
                                jsx(StatusRow, { label: 'Check version', value: `v${attempt.check_version}` }),
                                jsx(StatusRow, {
                                  label: 'Disputes',
                                  value: String((attempt.disputes || []).length)
                                })
                              ]
                            }),
                            (attempt.disputes || []).length > 0
                              ? jsxs('div', {
                                  className: 'flex flex-col gap-1',
                                  children: [
                                    jsx(CbLabel, { children: 'Dispute history' }),
                                    attempt.disputes.map((item) =>
                                      jsx(
                                        'div',
                                        { className: 'text-xs text-(--ui-text-secondary)', children: `${item.state} · ${whenLabel(item.created_at)} · ${item.note}` },
                                        item.id
                                      )
                                    )
                                  ]
                                })
                              : null,
                            jsxs('div', {
                              className: 'flex flex-wrap items-center gap-2',
                              children: [
                                jsx(sdk.Button, {
                                  variant: 'secondary',
                                  size: 'sm',
                                  onClick: () => onOpenSection(attempt.objective_id),
                                  children: 'Review lesson'
                                }),
                                supports('progression.challenge_out')
                                  ? jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      onClick: () => newVersion(attempt),
                                      children: 'Try a new version'
                                    })
                                  : null,
                                supports('notebook.save')
                                  ? jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      onClick: () =>
                                        setSaveSeed({
                                          excerpt: attempt.answer && attempt.answer.text ? attempt.answer.text : 'Quiz moment',
                                          kind: 'quiz_moment',
                                          course_title: row.title || null,
                                          objective_title: attempt.title || null,
                                          check_id: attempt.check_id
                                        }),
                                      children: 'Save to notebook'
                                    })
                                  : null
                              ]
                            }),
                            supports('attempt.dispute')
                              ? jsxs('div', {
                                  className: 'flex flex-col gap-2',
                                  children: [
                                    jsx('label', {
                                      htmlFor: 'cb-dispute',
                                      className: 'text-xs font-medium text-(--ui-text-secondary)',
                                      children: 'Dispute this grade'
                                    }),
                                    jsx(sdk.Textarea, {
                                      id: 'cb-dispute',
                                      rows: 2,
                                      value: disputeNote,
                                      onChange: (event) => setDisputeNote(event.target.value),
                                      placeholder: 'What did the grader get wrong?'
                                    }),
                                    jsx(sdk.Button, {
                                      variant: 'secondary',
                                      size: 'sm',
                                      disabled: !disputeNote.trim(),
                                      onClick: dispute,
                                      children: 'Record dispute'
                                    }),
                                    jsx(QuietNote, {
                                      children: 'A dispute never overwrites the original verdict; a re-grade would be a new operation.'
                                    })
                                  ]
                                })
                              : null
                          ]
                        })
                      : null
                  ]
                },
                attempt.attempt_id
              )
            )
          }),

      jsx(NotebookSaveDialog, {
        open: Boolean(saveSeed),
        seed: saveSeed,
        onClose: () => setSaveSeed(null),
        enrollmentId: row.enrollment_id,
        objectiveId: selected ? selected.objective_id : row.evidence_summary.current_objective_id,
        lessonRunId: null,
        implemented,
        onSaved: onChanged
      })
    ]
  })
}

/** Plan — the same objective state vocabulary, one flat list, no progress ring. */
function PlanView({ row, review, notebooks, outline, page, implemented, onOpenSection, onChanged }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const rows = sectionRows({ row, review, notebooks, outline, page })
  const reviewById = new Map(((review && review.items) || []).map((item) => [item.objective_id, item]))
  const [challengeError, setChallengeError] = useState(null)

  const challenge = useCallback(
    async (objectiveId) => {
      const response = await rpc(
        'progression.challenge_out',
        { enrollment_id: row.enrollment_id, objective_id: objectiveId },
        { expectedRevision: row.revision }
      )
      if (!response.ok) {
        setChallengeError(`${response.error.code}: ${describeError(response.error)}`)
        return
      }
      setChallengeError(null)
      onChanged()
    },
    [row, onChanged]
  )

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsx(QuietNote, {
        children:
          'Estimated sessions are planning aids, not promises. Only a cold independent result moves an objective to independent evidence.'
      }),
      challengeError ? jsx(ErrorLine, { error: { message: challengeError } }) : null,
      rows.length === 0
        ? jsx(EmptyState, {
            title: 'No objectives to show',
            description: 'The plan is not approved, or this build cannot read the objective list.'
          })
        : jsx('div', {
            className: 'flex flex-col',
            children: rows.map((entry) => {
              const item = reviewById.get(entry.objective_id)
              return jsxs(
                'div',
                {
                  className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-2 last:border-b-0',
                  children: [
                    jsxs('div', {
                      className: 'flex flex-wrap items-center justify-between gap-2',
                      children: [
                        jsx('div', { className: 'min-w-0 break-words text-sm font-medium', children: entry.title }),
                        jsx(StateText, { state: entry.state || (item && item.state) || 'not_started' })
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
                      children: [
                        entry.evidence_target ? jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: learnerEvidenceTarget(entry.evidence_target) }) : null,
                        item ? jsx('span', { children: `next review ${whenLabel(item.due_at)}` }) : null,
                        item ? jsx('span', { children: `interval ${item.interval_days}d · step ${item.step}` }) : null
                      ]
                    }),
                    jsxs('div', {
                      className: 'flex flex-wrap items-center gap-1',
                      children: [
                        jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => onOpenSection(entry.objective_id), children: 'Open section' }),
                        supports('progression.challenge_out')
                          ? jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => challenge(entry.objective_id), children: 'Challenge out' })
                          : null
                      ]
                    })
                  ]
                },
                entry.objective_id
              )
            })
          }),
      jsx(QuietNote, {
        children:
          'This build cannot edit evidence criteria, attempt counts or settings yet. Nothing is filled in to hide that.'
      })
    ]
  })
}

/** Evidence — three linked layers, actual verdicts and provenance, no personality claims. */
function EvidenceView({ evidence, implemented, onOpenSection }) {
  if (!evidence) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading the evidence layers' }) })
  }
  const l1 = evidence.l1 || { attempts: [], events: [] }
  const l2 = evidence.l2 || { objectives: [] }
  const l3 = evidence.l3 || { recommendations: [], as_of: null, is_persona: false }
  const disputes = (evidence.disputes && evidence.disputes.disputes) || []
  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-4',
    children: [
      jsxs('div', {
        className: 'flex flex-col',
        'data-cb-evidence-block': 'l3',
        children: [
          jsx(CbLabel, { children: 'What to do next' }),
          (l3.recommendations || []).length === 0
            ? jsx(QuietNote, { children: 'Nothing is suggested yet, because no evidence has been recorded.' })
            : (l3.recommendations || []).map((item, index) =>
                jsx(
                  'div',
                  {
                    className: 'flex flex-col gap-0.5 py-1',
                    children: jsx('div', { className: 'text-sm text-(--ui-text-secondary)', children: item.text })
                  },
                  `${item.kind}-${index}`
                )
              ),
          jsx(QuietNote, {
            children: `It changes when new evidence is recorded, and it describes that evidence rather than judging you. Updated ${whenLabel(l3.as_of)}.`
          }),
          (l3.recommendations || []).length > 0
            ? jsxs('details', {
                'data-cb-evidence-technical': 'l3',
                className: 'flex flex-col',
                children: [
                  jsx('summary', {
                    className: 'cursor-pointer text-xs text-(--ui-text-secondary)',
                    children: 'Technical detail'
                  }),
                  jsxs('div', {
                    className: 'flex flex-col gap-0.5 pt-1',
                    children: (l3.recommendations || []).map((item, index) =>
                      jsx(
                        'code',
                        { className: 'break-words text-xs text-(--ui-text-secondary)', children: `basis: ${item.basis}` },
                        `basis-${item.kind}-${index}`
                      )
                    )
                  })
                ]
              })
            : null
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        'data-cb-evidence-block': 'l2',
        children: [
          jsx(CbLabel, { children: 'What the evidence shows' }),
          (l2.objectives || []).length === 0
            ? jsx(QuietNote, { children: 'No objective in your plan has evidence yet.' })
            : jsx('div', {
                className: 'flex flex-col',
                children: (l2.objectives || []).map((objective) =>
                  jsxs(
                    'div',
                    {
                      className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
                      children: [
                        jsx('span', { className: 'min-w-0 break-words text-xs text-(--ui-text-secondary)', children: objective.title }),
                        jsxs('span', {
                          className: 'flex items-center gap-2',
                          children: [
                            jsx(sdk.Badge, { size: 'xs', variant: objective.independent ? 'outline' : 'muted', children: objective.independent ? 'independent' : 'no cold result' }),
                            jsx('button', {
                              type: 'button',
                              className: 'text-xs text-(--ui-text-secondary) underline-offset-2 hover:underline',
                              onClick: () => onOpenSection(objective.objective_id),
                              children: 'Open'
                            })
                          ]
                        })
                      ]
                    },
                    objective.objective_id
                  )
                )
              })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-col',
        'data-cb-evidence-block': 'l1',
        children: [
          jsx(CbLabel, { children: 'Your attempts' }),
          jsxs('div', {
            className: 'flex flex-col',
            children: [
              (l1.attempts || []).slice(0, 12).map((attempt) =>
                jsxs(
                  'div',
                  {
                    className: 'flex flex-wrap items-center justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 text-xs last:border-b-0',
                    children: [
                      jsx('span', { className: 'text-(--ui-text-secondary)', children: whenLabel(attempt.committed_at || attempt.created_at) }),
                      jsxs('span', {
                        className: 'flex items-center gap-2',
                        children: [
                          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: verdictLabel(attempt.verdict, attempt.evidence_class) }),
                          jsx(EvidenceClassText, { value: attempt.evidence_class })
                        ]
                      })
                    ]
                  },
                  attempt.attempt_id
                )
              ),
              (l1.events || []).filter((event) => event.is_action).slice(0, 8).map((event) =>
                jsx(
                  'div',
                  {
                    className: 'flex flex-wrap items-center justify-between gap-2 py-1 text-xs text-(--ui-text-secondary)',
                    children: jsxs('span', {
                      className: 'flex items-center gap-2',
                      children: [jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: event.kind }), jsx('span', { children: whenLabel(event.created_at) })]
                    })
                  },
                  event.evidence_id
                )
              )
            ]
          }),
          disputes.length > 0
            ? jsxs('div', {
                className: 'flex flex-col',
                children: [
                  jsx(CbLabel, { children: 'Disputes' }),
                  disputes.slice(0, 8).map((item) =>
                    jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `${item.state} · ${whenLabel(item.created_at)} · ${item.note}` }, item.id)
                  )
                ]
              })
            : null
        ]
      })
    ]
  })
}

/**
 * H-106 — source provenance, in words a parent can read.
 *
 * The frozen `support_status` is a *class* (`model_assessed`, `conflicting`, `unassessed`,
 * `stale`, `unreachable`); the model's own verdict (`supported`/`partial`/`unverified`/
 * `contradictory`) travels beside it as `support_assessment`. Neither is a document proof, so the
 * card always says which one it is showing. The exact fetched words live in a disclosure; a source
 * with no stored excerpt says so instead of borrowing a citation it cannot back. The raw enums,
 * ids and hashes stay in the technical disclosure, never in the main line.
 */
const SOURCE_SUPPORT_CLASS = Object.freeze({
  model_assessed: {
    label: 'Model-assessed',
    basis: 'A model read this source and rated how it bears on the claim. That is an assessment, not a document proof.'
  },
  conflicting: {
    label: 'Conflicting',
    basis: 'The model found this source at odds with a claim. A person has to settle the disagreement.'
  },
  unassessed: {
    label: 'Not assessed',
    basis: 'Nothing has checked this source against a claim, so it is listed as provenance only.'
  },
  stale: {
    label: 'Source changed',
    basis: 'The stored words changed after this course used them. Dependent checks wait for review rather than grading against old text.'
  },
  unreachable: {
    label: 'Source unreachable',
    basis: 'The last re-fetch failed. The stored evidence is kept, and reuse triggers review.'
  },
  authoritative_documentation: {
    label: 'Publisher’s own document',
    basis: 'This is the publisher’s own documentation, which is provenance for the text — not a check that any claim is true.'
  }
})

const SOURCE_ASSESSMENT_WORDS = Object.freeze({
  supported: 'the model judged that this source supports the claim',
  partial: 'the model judged that this source only partly supports the claim',
  unverified: 'the model could not verify the claim from this source',
  contradictory: 'the model judged that this source contradicts the claim'
})

const SOURCE_TYPE_WORDS = Object.freeze({
  government: 'Government',
  academic: 'Academic',
  reference: 'Reference',
  documentation: 'Documentation',
  organization: 'Organization',
  web_page: 'Web page'
})

function sourceSupportModel(source) {
  const status = source && typeof source.support_status === 'string' ? source.support_status : 'unassessed'
  const known = SOURCE_SUPPORT_CLASS[status] || {
    label: 'Status unrecorded',
    basis: 'The backend did not record how this source bears on the claim.'
  }
  const assessment = source && SOURCE_ASSESSMENT_WORDS[source.support_assessment]
    ? source.support_assessment
    : null
  return {
    status,
    label: known.label,
    basis: known.basis,
    assessment,
    assessmentWords: assessment ? SOURCE_ASSESSMENT_WORDS[assessment] : null
  }
}

function sourceTypeLabel(value) {
  if (!value) return 'Source type not recorded'
  return SOURCE_TYPE_WORDS[value] || String(value).replace(/_/g, ' ')
}

function sourceExcerptState(source) {
  const state = source && source.excerpt_state
  if (state === 'recorded' || state === 'missing' || state === 'unreadable') return state
  // A pre-H-106 payload has no typed state: an excerpt is the only evidence of itself.
  return source && source.excerpt ? 'recorded' : 'missing'
}

/** The stored words, or the typed reason there are none. A disclosure, never a silent omission. */
function SourceExcerpt({ source }) {
  const state = sourceExcerptState(source)
  const text = source && typeof source.excerpt === 'string' ? source.excerpt : ''
  if (state !== 'recorded' || !text) {
    return jsx('div', {
      'data-cb-source-excerpt': state,
      style: { fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', maxWidth: CB_MEASURE },
      children:
        state === 'unreadable'
          ? 'The recorded research snapshot could not be read, so this source’s excerpt is unknown — not absent. Nothing here is presented as a quote.'
          : 'No excerpt is stored for this source. It is listed as provenance only, so no claim on this course is presented as supported by it.'
    })
  }
  return jsxs('details', {
    'data-cb-source-excerpt': 'recorded',
    style: { maxWidth: CB_MEASURE },
    children: [
      jsx('summary', {
        className: 'cursor-pointer',
        style: { fontSize: CB_TYPE.meta, color: 'var(--cb-ink)' },
        children: `Exact excerpt (${text.length.toLocaleString()} characters)`
      }),
      jsxs('div', {
        style: { marginTop: '0.35rem' },
        children: [
          jsx('blockquote', {
            style: {
              margin: 0,
              paddingLeft: '0.6rem',
              borderLeft: '2px solid var(--cb-rule)',
              fontSize: CB_TYPE.meta,
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
              overflowWrap: 'anywhere',
              maxHeight: '14rem',
              overflowY: 'auto',
              color: 'var(--cb-ink)'
            },
            children: text
          }),
          jsx('div', {
            style: { marginTop: '0.3rem', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children:
              'These are the words the research step stored when it fetched the page. They are shown as stored; reading them is not a re-fetch and proves nothing beyond what they say.'
          })
        ]
      })
    ]
  })
}

/** One source: title, publisher/URL, support basis, excerpt, and the technical record behind it. */
function SourceProvenanceCard({ source, dense = false }) {
  const model = sourceSupportModel(source)
  const excerptState = sourceExcerptState(source)
  const publisher = source && source.publisher ? source.publisher : null
  const modality = source && source.modality ? source.modality : null
  const licence = source && source.licence ? source.licence : null
  const facts = []
  facts.push(publisher ? `Published by ${publisher}` : 'Publisher not recorded')
  facts.push(sourceTypeLabel(source && source.source_type))
  if (source && source.published_at) facts.push(`Published ${whenLabel(source.published_at)}`)
  if (source && source.fetched_at) facts.push(`Fetched ${whenLabel(source.fetched_at)}`)
  if (source && Number(source.claim_count) > 0) {
    const count = Number(source.claim_count)
    facts.push(`${count} claim${count === 1 ? '' : 's'} cite it`)
  }
  const detail = [
    `Source id: ${(source && source.source_id) || 'not recorded'}.`,
    `Support class: ${model.status}.`,
    model.assessment ? `Model assessment: ${model.assessment}.` : 'Model assessment: none recorded.',
    `Excerpt state: ${excerptState}.`,
    `Content hash: ${(source && source.content_hash) || 'not recorded'}.`,
    `Modality: ${modality || 'not recorded'}. Licence: ${licence || 'not recorded'}.`
  ]
  return jsxs('div', {
    'data-cb-source-card': (source && source.source_id) || '',
    'data-cb-source-support': model.status,
    'data-cb-source-excerpt-state': excerptState,
    className: 'flex flex-col gap-1 border-b border-(--ui-stroke-tertiary) py-3 last:border-b-0',
    style: { maxWidth: CB_MEASURE },
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx('span', {
            style: { minWidth: 0, fontSize: dense ? CB_TYPE.meta : CB_TYPE.body, fontWeight: 600, overflowWrap: 'anywhere', color: 'var(--cb-ink)' },
            children: (source && source.title) || 'Untitled source'
          }),
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: model.label }),
          !dense && model.assessment
            ? jsx(sdk.Badge, {
                size: 'xs',
                variant: 'muted',
                'data-cb-source-assessment': model.assessment,
                children: 'the model’s verdict'
              })
            : null
        ]
      }),
      jsx('div', {
        style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
        children: facts.join(' · ')
      }),
      jsx('div', {
        'data-cb-source-basis': '',
        style: { fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
        children: model.assessmentWords
          ? `Support basis: ${model.assessmentWords}, because a model read it. ${model.basis}`
          : `Support basis: ${model.basis}`
      }),
      source && source.url
        ? jsxs('div', {
            className: 'flex flex-wrap items-baseline gap-2',
            style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: [
              jsx('span', {
                style: { minWidth: 0, overflowWrap: 'anywhere' },
                children: source.url
              }),
              jsx('a', {
                href: source.url,
                target: '_blank',
                rel: 'noreferrer noopener',
                'data-cb-source-open': '',
                style: { color: 'var(--cb-ink)', textDecoration: 'underline' },
                children: 'Open source'
              })
            ]
          })
        : null,
      jsx(SourceExcerpt, { source }),
      !dense || licence || modality
        ? jsxs('div', {
            style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
            children: [
              `Rights: ${licence || 'not recorded'}`,
              modality ? ` · Modality: ${modality}` : ' · Modality: not recorded',
              '. A title and a URL are not a licence.'
            ]
          })
        : null,
      jsxs('details', {
        'data-cb-source-detail': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: 'Technical detail' }),
          jsxs('div', {
            style: { marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0, overflowWrap: 'anywhere', fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: detail.map((line, index) => jsx('div', { children: line }, `source-detail-${index}`))
          })
        ]
      })
    ]
  })
}

/**
 * The sources panel. `status` is the read state of the call that produced `sources`, so a failed
 * read is an error with a retry — never an empty list. An empty list is its own typed state and
 * says plainly that nothing is presented as cited.
 */
function SourceProvenancePanel({
  sources,
  status,
  error,
  onRetry,
  intro,
  emptyTitle,
  emptyDescription,
  dense = false,
  extra = null
}) {
  const items = Array.isArray(sources) ? sources : []
  const frame = (children, state) =>
    jsxs('div', {
      'data-cb-provenance-panel': '',
      'data-cb-provenance-state': state,
      className: 'flex flex-col gap-2',
      children: [extra, children].filter(Boolean)
    })
  if (status === 'loading') return frame(jsx(sdk.Loader, { label: 'Reading this course’s sources' }), 'loading')
  if (status === 'error') {
    return frame(
      jsx(sdk.ErrorState, {
        title: 'The sources could not be read',
        description: `${error && error.code ? error.code + ': ' : ''}${describeError(error)} Nothing is shown from a cached list.`,
        children: onRetry ? jsx(sdk.Button, { variant: 'secondary', onClick: onRetry, children: 'Try again' }) : null
      }),
      'error'
    )
  }
  if (status === 'idle' || (!items.length && !status)) {
    return frame(
      jsx(EmptyState, {
        title: 'No source has been read yet',
        description:
          'A source list is read with this course’s lesson page. Until that read runs, nothing is presented as cited.'
      }),
      'unread'
    )
  }
  if (!items.length) {
    return frame(
      jsx(EmptyState, {
        title: emptyTitle || 'No source is recorded',
        description:
          emptyDescription ||
          'No source is recorded for this course. Nothing on it is presented as cited, and no excerpt is invented to fill the gap.'
      }),
      'empty'
    )
  }
  return frame(
    jsxs('div', {
      className: 'flex flex-col',
      children: [
        intro
          ? jsx('p', {
              style: { margin: '0 0 0.25rem', fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)', maxWidth: CB_MEASURE },
              children: intro
            })
          : null,
        ...items.map((source) =>
          jsx(SourceProvenanceCard, { source, dense }, (source && source.source_id) || (source && source.url) || source.title)
        )
      ]
    }),
    'ready'
  )
}

/**
 * H-101's vocabulary provenance, read from the plan job's own checkpoint (`checkpoint.vocabulary`).
 * An inventory prints its source id, licence, modality, band and rows hash; anything else prints the
 * typed absence and never a word list or a coverage percentage.
 */
function ProvenanceInventoryRow({ vocabulary }) {
  const record = vocabulary && typeof vocabulary === 'object' ? vocabulary : null
  const status = (record && record.status) || 'unverified'
  if (status !== 'inventory') {
    const notApplicable = status === 'not_applicable'
    return jsxs('div', {
      'data-cb-vocabulary-source': notApplicable ? 'not_applicable' : 'unverified',
      style: { fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)', maxWidth: CB_MEASURE },
      children: [
        jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: notApplicable ? 'Not applicable' : 'Unverified' }),
        jsx('span', {
          children: notApplicable
            ? ' No vocabulary inventory applies: this course does not declare a language domain.'
            : ` No word list is verified for this plan${record && record.detail ? ` — ${record.detail}` : ''}. No word list or coverage claim is shown.`
        })
      ]
    })
  }
  const band = record.band || {}
  const items = Array.isArray(record.items) ? record.items.length : 0
  const hash = typeof record.content_hash === 'string' && record.content_hash.length > 0
    ? `${record.content_hash.slice(0, 19)}…`
    : 'not recorded'
  return jsxs('div', {
    'data-cb-vocabulary-source': 'inventory',
    style: { fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)', maxWidth: CB_MEASURE },
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-baseline gap-2',
        children: [
          jsx(sdk.Badge, { size: 'xs', variant: 'outline', children: 'Word list recorded' }),
          jsx('span', {
            children: `Vocabulary source ${record.source_id} · ${record.licence} · ${record.modality} · band ${band.id} (ranks ${band.from_rank}–${band.to_rank}) · ${hash}`
          })
        ]
      }),
      jsx('span', {
        children:
          ` ${items} vocabulary item${items === 1 ? '' : 's'} named from this band. The plan may only use words this declared list contains.`
      }),
      jsxs('details', {
        'data-cb-vocabulary-detail': '',
        children: [
          jsx('summary', { className: 'cursor-pointer', children: 'Technical detail' }),
          jsx('div', {
            style: { marginTop: '0.25rem', minWidth: 0, overflowWrap: 'anywhere' },
            children: [
              `Inventory id: ${record.inventory_id || 'not recorded'}. Rows hash: ${record.content_hash || 'not recorded'}. ` +
              `Licence URL: ${record.licence_url || 'not recorded'}.`
            ]
          })
        ]
      })
    ]
  })
}

/** Sources — support status in words; unverified is never a green "verified". */
function SourcesView({ pageState, inventory }) {
  const page = pageState && pageState.data
  const status = pageState ? pageState.status : 'idle'
  const sources = (page && page.sources) || []
  return jsx(SourceProvenancePanel, {
    sources,
    status: status === 'ready' ? 'ready' : status,
    error: pageState ? pageState.error : null,
    onRetry: pageState ? pageState.reload : null,
    extra: inventory ? jsx(ProvenanceInventoryRow, { vocabulary: inventory }) : null,
    intro:
      'Each row is one recorded source. The support class is what the backend stored; the excerpt is the text it fetched. A support verdict came from a model unless it says otherwise, and a listed source is not itself a citation.'
  })
}
/**
 * Export — the learner's course packages itself (cb.rpc v11).
 *
 * `course.export.read` is the review, `course.export` is the write, and the two agree about the
 * content hash: the surface echoes the hash it displayed, so the exported archive is the exact
 * page set a person read. The file list, licence, rights statement and no-upload statement all come
 * from the backend; nothing here invents a file, a size or a promise.
 *
 * A pack-backed course has no business here — its bytes belong to `pack.export` — so the backend
 * answers `course_pack_backed` and this view says so instead of offering a second, competing export.
 */
const COURSE_EXPORT_BLOCKED_COPY = {
  plan_not_approved:
    'The plan is not approved yet. Approve the plan before packaging this course: an unapproved plan is not a published design.',
  lessons_not_validated:
    'At least one lesson page has not passed validation, so it cannot be packaged. Regenerate or fix the page first; a page no validator cleared is not content to hand to someone else.',
  no_generated_content:
    'This course has no lesson pages yet. Generate the lessons before packaging it.',
  changes_need_review:
    'The lesson text changed after it was approved. Review the pages again before packaging them.',
  export_not_exportable:
    'The generated lessons do not meet the pack’s teaching minima yet, so the archive would not import. Fix the lesson content first.',
  export_write_failed:
    'The archive could not be written. Nothing was exported and nothing was sent anywhere.',
  course_pack_backed:
    'This course came from a pack. Its file list and licence belong to that pack, so re-export it from the pack surface — this course cannot export its own copy.'
}

/**
 * What a course archive holds and what it never holds.
 *
 * The right-hand list is the backend's own contract: `course_export` builds its manifest from the
 * authored lesson rows and has no read path to these tables. There is deliberately no control to
 * opt any of them in — this build offers no way to put learner history in a course archive, so the
 * surface states that instead of showing a toggle that would do nothing.
 */
const COURSE_EXPORT_PRIVATE_ROWS = [
  { label: 'Attempts, answers and grades', value: 'learner evidence, never read' },
  { label: 'Notebook notes and saved excerpts', value: 'personal prose, never read' },
  { label: 'Parent observations and chat transcripts', value: 'teaching history, never read' },
  { label: 'Provider settings, bindings and enrollment id', value: 'local state, never read' }
]

/**
 * The one repair each refusal offers (H-121). A refusal writes nothing, so the useful next step is
 * the surface that can clear the gate: the plan (approve, generate, re-approve the lesson set), or
 * the Library for a pack-backed course whose bytes belong to `pack.export`. `export_write_failed`
 * has no repair beyond trying again, so it keeps only the re-check action.
 */
const COURSE_EXPORT_REPAIR = {
  plan_not_approved: { target: 'plan', label: 'Review and approve the plan' },
  no_generated_content: { target: 'plan', label: 'Generate the lessons' },
  lessons_not_validated: { target: 'plan', label: 'Open the plan to fix the pages' },
  changes_need_review: { target: 'plan', label: 'Review and re-approve the lesson set' },
  export_not_exportable: { target: 'plan', label: 'Open the plan to fix the lessons' },
  course_pack_backed: { target: 'library', label: 'Export the pack from Library' }
}

function courseExportRepair(reason) {
  return COURSE_EXPORT_REPAIR[reason] || null
}

/** The exact write call, including the reviewed-content fence. Pure so a test can assert it. */
function courseExportRequest(row, reviewedContentHash) {
  return {
    method: 'course.export',
    payload: {
      enrollment_id: row.enrollment_id,
      expected_content_hash: reviewedContentHash
    },
    options: { idempotencyKey: newOperationId('course-export') }
  }
}

function CourseExportView({ row, implemented, onRepair, onOpenLibrary }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  const key = `course-export-${row.enrollment_id}`
  const query = useRpcQuery(
    'course.export.read',
    { enrollment_id: row.enrollment_id },
    key,
    supports('course.export.read')
  )
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [exported, setExported] = useState(null)
  const [artifact, setArtifact] = useState(null)

  const run = useCallback(async () => {
    if (!query.data || !query.data.content_hash) return
    setBusy(true)
    setError(null)
    try {
      const request = courseExportRequest(row, query.data.content_hash)
      const response = await rpc(request.method, request.payload, request.options)
      if (!response.ok) {
        if (response.error && response.error.code === 'DELETE_SCOPE_STALE') {
          setError({
            message:
              'The lesson text changed since this page was read, so nothing was exported. The review was refreshed; export again only if the new file list is the one you want.'
          })
          query.reload()
          return
        }
        throw new Error(`${response.error ? response.error.code + ': ' : ''}${describeError(response.error)}`)
      }
      if (response.result.content_hash !== query.data.content_hash) {
        throw new Error(
          'The backend exported a different content hash than the one reviewed. Nothing here should be handed on.'
        )
      }
      setExported(response.result)
      const facts = await rpc('artifact.get', {
        artifact_id: response.result.artifacts[0].artifact_id
      })
      if (facts.ok) setArtifact(facts.result)
      query.reload()
    } catch (failure) {
      setError({ message: describeError(failure) })
    } finally {
      setBusy(false)
    }
  }, [query, row])

  if (!supports('course.export.read')) {
    return jsx(QuietNote, {
      children:
        'This backend build does not publish the course export commands, so there is no export action here. Nothing is offered that would produce a file the backend did not write.'
    })
  }
  if (query.status === 'loading' && !query.data) {
    return jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading what an export would contain' }) })
  }
  if (query.status === 'error' && !query.data) {
    return jsx(sdk.ErrorState, {
      title: 'The export review could not be read',
      description: `${query.error && query.error.code ? query.error.code + ': ' : ''}${describeError(query.error)}`,
      children: jsx(sdk.Button, { variant: 'secondary', onClick: query.reload, children: 'Try again' })
    })
  }
  const read = query.data || {}
  const files = read.files || []

  if (!read.ready) {
    const repair = courseExportRepair(read.blocked_reason)
    const repairAction = repair ? (repair.target === 'library' ? onOpenLibrary : onRepair) : null
    return jsxs('div', {
      className: 'flex max-w-3xl flex-col gap-3',
      'data-cb-export-blocked': read.blocked_reason || 'unstated',
      children: [
        jsx('div', { className: 'text-sm font-semibold', children: 'This course cannot be packaged yet' }),
        jsx('div', {
          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
          children:
            (read.blocked_reason && COURSE_EXPORT_BLOCKED_COPY[read.blocked_reason]) ||
            read.blocked_message ||
            'The backend gave no reason, so no export is offered.'
        }),
        (read.problems || []).length > 0
          ? jsx('div', {
              className: 'flex flex-col gap-1',
              children: read.problems.map((problem) =>
                jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: `• ${problem}` }, problem)
              )
            })
          : null,
        read.sections
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: `${Number(read.sections.validated)} of ${plural(Number(read.sections.total), 'lesson page', 'lesson pages')} validated.`
            })
          : null,
        // One repair, not a menu: the refusal names the surface that can clear it. The re-check
        // stays secondary so a learner who fixed the gate can come straight back here.
        repair && repairAction
          ? jsx('div', {
              className: 'flex flex-wrap items-center gap-2',
              'data-cb-export-repair': repair.target,
              children: [
                jsx(CbAction, {
                  variant: 'primary',
                  onClick: repair.target === 'library' ? onOpenLibrary : onRepair,
                  children: repair.label
                }),
                jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: query.reload, children: 'Check again' })
              ]
            })
          : jsx(sdk.Button, { size: 'sm', variant: 'secondary', onClick: query.reload, children: 'Check again' }),
        jsx('div', {
          className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
          children: 'Nothing was exported: a refused review writes no archive and sends nothing anywhere.'
        })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex max-w-3xl flex-col gap-3',
    children: [
      jsx(PlateHead, {
        title: 'Export this course',
        caption: 'Review what goes with the course, what stays behind, and the exact text hash before anything is packaged.'
      }),
      jsx(CbLabel, { children: 'GOES IN THE ARCHIVE' }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        'data-cb-export-stays': '',
        children: `${plural(files.length, 'file', 'files')}: this course’s own lesson text and its guides, and nothing else.`
      }),
      jsxs('div', {
        className: 'flex flex-col',
        children: files.map((file) =>
          jsxs(
            'div',
            {
              className:
                'flex flex-wrap items-baseline justify-between gap-2 border-b border-(--ui-stroke-tertiary) py-1.5 last:border-b-0',
              children: [
                jsx('div', { className: 'min-w-0 break-all text-xs', children: file.name }),
                jsxs('div', {
                  className: 'flex shrink-0 items-center gap-2 text-xs text-(--ui-text-secondary)',
                  children: [
                    jsx(sdk.Badge, { size: 'xs', variant: 'muted', children: file.role }),
                    jsx('span', { children: bytesLabel(file.bytes) })
                  ]
                })
              ]
            },
            file.name
          )
        )
      }),
      jsx(CbLabel, { children: 'STAYS ON THIS PROFILE' }),
      jsx('div', {
        className: 'flex flex-col',
        'data-cb-export-leaves': '',
        children: COURSE_EXPORT_PRIVATE_ROWS.map((item) =>
          jsx(PackReviewLine, { label: item.label, value: item.value }, item.label)
        )
      }),
      jsx('div', {
        className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
        children:
          'There is no option here to add learner history to a course archive. The backend builds the archive from ' +
          'the lesson rows only, so notes and answers are absent by construction, not by a setting this page forgot.'
      }),
      jsxs('div', {
        className: 'flex flex-col',
        'data-cb-export-hash': read.content_hash || '',
        children: [
          jsx(PackReviewLine, { label: 'Files', value: String(files.length) }),
          jsx(PackReviewLine, {
            label: 'Content hash',
            value: jsx('code', { className: 'text-xs', children: read.content_hash })
          }),
          jsx(PackReviewLine, {
            label: 'Licence',
            value: `${(read.license && read.license.id) || 'unknown'} · ${(read.license && read.license.redistribution) || 'unknown'}`
          }),
          jsx(PackReviewLine, {
            label: 'Plan',
            value: read.plan ? `version ${read.plan.version} · ${read.plan.state}` : 'not recorded'
          })
        ]
      }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: read.rights }),
      jsx('div', { className: 'text-xs leading-relaxed text-(--ui-text-secondary)', children: read.no_upload }),
      jsxs('label', {
        className: 'flex items-start gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('input', {
            checked: confirmed,
            onChange: (event) => setConfirmed(Boolean(event.target.checked)),
            type: 'checkbox'
          }),
          jsx('span', {
            children: 'I reviewed these files, the licence and the rights statement; package exactly this text.'
          })
        ]
      }),
      jsx(CbAction, {
        disabled: busy || !confirmed,
        onClick: run,
        variant: 'primary',
        children: busy ? 'Packaging' : 'Export these files'
      }),
      error ? jsx('div', { className: 'text-xs', children: error.message }) : null,
      exported
        ? jsxs('div', {
            className: 'flex flex-col',
            'data-cb-export-done': exported.content_hash,
            children: [
              jsx(CbLabel, { children: 'Exported' }),
              jsx(PackReviewLine, {
                label: 'Content hash',
                value: jsx('code', { className: 'text-xs', children: exported.content_hash })
              }),
              jsx(PackReviewLine, { label: 'Matches the reviewed hash', value: 'yes' }),
              jsx(PackReviewLine, {
                label: 'Pack',
                value: `${exported.pack.pack_id} v${exported.pack.pack_version}`
              }),
              jsx(PackReviewLine, {
                label: 'Pack manifest hash',
                value: jsx('code', { className: 'text-xs', children: exported.pack.manifest_hash })
              }),
              jsx(PackReviewLine, { label: 'Files', value: String((exported.files || []).length) }),
              jsx(PackReviewLine, {
                label: 'Archive bytes',
                value: bytesLabel(exported.artifacts && exported.artifacts[0] ? exported.artifacts[0].bytes : 0)
              }),
              artifact
                ? jsx(PackReviewLine, {
                    label: 'Archive file hash',
                    value: jsx('code', { className: 'text-xs', children: artifact.content_hash })
                  })
                : null,
              artifact
                ? jsx(sdk.Button, {
                    asChild: true,
                    size: 'sm',
                    variant: 'secondary',
                    children: jsx('a', {
                      download: `${exported.pack.pack_id}-${exported.pack.pack_version}.zip`,
                      href: artifact.download.url,
                      children: 'Download archive'
                    })
                  })
                : null,
              jsx('div', {
                className: 'mt-1 text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'The download link is the host route the backend named; the session is checked there and the ' +
                  'handle expires. The file is byte-identical to the hash above.'
              }),
              jsx('div', {
                className: 'mt-1 text-xs leading-relaxed text-(--ui-text-secondary)',
                'data-cb-export-portable': '',
                children:
                  'The archive travels: open Library → Import pack on another profile, review the same hash, then ' +
                  'resume an existing classroom for this pack or start a fresh enrollment. The pack identity (id and ' +
                  'hash above) is the shared course; the enrollment identity is created by the profile that imports it.'
              })
            ]
          })
        : null
    ]
  })
}

/**
 * H-174: the hero's action set as data, so "at most one primary" is a property of the model rather
 * than a promise about three hand-written conditionals. A learner can only get a primary action
 * when the approved lesson page is readable; every other state is explained by the readiness panel
 * and has no primary at all.
 */
function lessonHeroPlan(readiness, { overview = false, sectionOpen = false } = {}) {
  const readable = Boolean(readiness && readiness.state === 'readable')
  if (overview || !readable) return []
  if (sectionOpen) {
    return [
      { id: 'sections', variant: 'secondary', label: 'Back to sections' },
      { id: 'why', variant: 'text', label: 'Why this is next' }
    ]
  }
  return [
    { id: 'start', variant: 'primary', label: 'Start the lesson' },
    { id: 'textbook', variant: 'secondary', label: 'Open the textbook' },
    { id: 'why', variant: 'text', label: 'Why this is next' }
  ]
}

/* ══ CP-024 — the v3 course home (R-MAP) ══════════════════════════════════════════════════════
 * The course page's own composition (SPEC-V3 §5.4): a back path, the course head, a mounted hero
 * plate with the route's nodes on it, and an aside carrying Continue, the evidence count and the
 * other courses.
 *
 * Provenance, in the order the deck and the contract set it:
 *  - every visible string is a `course.*` row from `docs/concept-parity/COPY.md`, or a backend
 *    field the deck names for that row. Nothing here authors a label;
 *  - every number is a stored fact (`library_item.sections_done`/`sections_total`, the outline's
 *    objective states, the review queue). No streak, XP, percentage or invented total;
 *  - every colour, radius, type size and elevation is the v3 contract through the `cb3*` readers,
 *    so this segment carries no hex, no viewport unit and no shadow recipe of its own.
 *
 * The route nodes (M5) are DOM buttons placed on **normalised coordinates the plate's manifest
 * declares** (`route_anchors: [{section_id | objective_id, x, y}]`, each 0–1 of the plate box).
 * A plate that declares no usable anchors — today's `world.read` asset rows carry none, which is
 * reported as a gap rather than filled in — or a route narrower than 900 px renders the vertical
 * `StampNode` route instead. A node is a real button with its section's own title; the current one
 * carries `aria-current="step"` and the word `You are here`, never a colour alone.
 */

/** The deck's `course.*` strings. Every literal below is a `COPY.md` row, verbatim. */
const CB3_COURSE_COPY = Object.freeze({
  backPrefix: 'Back to ',
  routeLabel: 'Your route',
  nodeCurrent: 'You are here',
  nodeDone: 'Done',
  nodeNext: 'Next',
  nodeLocked: 'Opens after the section before it',
  continueTitle: 'Continue',
  evidenceTitle: 'Evidence',
  othersTitle: 'Your other courses',
  noWorldTitle: 'No scene yet',
  noWorldBody: 'The lesson works without art.',
  worldRunning: 'Painting the scene.',
  worldRejectedTitle: 'This scene was not approved',
  worldRejectedAction: 'Open World Studio',
  planReviewTitle: 'The plan is waiting for you',
  planReviewBody: 'Read it, then approve it so lessons can start.',
  endTitle: 'Course complete',
  endBody: 'Every section has evidence.',
  loading: 'Opening this course.',
  errorTitle: 'This course could not be read',
  errorBody: 'The route shows what was saved last. Try again.',
  errorAction: 'Try again'
})

/** `course.evidence.count`, filled from stored section counts. A zero total prints no claim. */
function cb3CourseEvidenceLine(done, total) {
  const have = Math.max(0, Number(done) || 0)
  const all = Math.max(0, Number(total) || 0)
  if (all <= 0) return null
  return `${have} of ${all} sections have evidence`
}

/**
 * Normalised anchor points, from either shape: `{key, x, y}` (already normalised) or the plate's
 * own `{section_id | objective_id | section_key, x, y}`. Malformed entries (no key, a non-finite
 * or out-of-range coordinate) are dropped rather than clamped: a coordinate the renderer invents
 * is not the plate's composition.
 */
function cb3CourseAnchorPoints(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return []
  const points = []
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue
    const key = entry.key || entry.section_id || entry.objective_id || entry.section_key || null
    const x = Number(entry.x)
    const y = Number(entry.y)
    if (!key) continue
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    if (x < 0 || x > 1 || y < 0 || y > 1) continue
    points.push({ key: String(key), x, y })
  }
  return points
}

/**
 * Normalised anchors declared by a plate. One shape, several legal carriers: the manifest's
 * `route_anchors`, the asset row's own `route_anchors`, the world brief's `plate.route_anchors`
 * or `route_anchors`, and the world row itself. The brief is the only plate document today's
 * `world.read` returns, so it is a legal home; the asset row's own manifest is preferred when a
 * backend exposes it, and this order keeps that preference.
 */
function cb3CoursePlateAnchors(plate, world) {
  const brief = world && world.brief && typeof world.brief === 'object' ? world.brief : null
  const sources = [
    plate && plate.manifest,
    plate,
    brief && brief.plate,
    brief,
    world
  ]
  for (const source of sources) {
    if (!source || typeof source !== 'object') continue
    const points = cb3CourseAnchorPoints(source.route_anchors)
    if (points.length) return points
  }
  return []
}

/**
 * The one hero plate a course home resolves, in this order and nothing else:
 *
 *   1. an approved `world.read` artifact (the course's own plate) — it wins and is previewed;
 *   2. the approved kit's `course-map` plate;
 *   3. the approved kit's `home-hero` plate;
 *   4. nothing, which is the typographic field (the deck's `No scene yet` row).
 *
 * `kit` is injectable so the fallback order is executable without the shipped asset segment; in
 * the product it is `cb3KitSource`. A plate the caller already resolved (`src` set, as the
 * `world.read` branch carries) is treated as the approved artifact it is, never re-resolved.
 */
function cb3CourseHeroResolution({ plate, kit } = {}) {
  const source =
    typeof kit === 'function' ? kit : typeof cb3KitSource === 'function' ? cb3KitSource : () => null
  const row = plate && typeof plate === 'object' ? plate : {}
  const direct = typeof row.src === 'string' && row.src ? row.src : null
  const artifactId = row.artifactId ? String(row.artifactId) : null
  const anchors = Array.isArray(row.anchors) ? row.anchors : []
  // An already-resolved plate keeps the scene it names. Without this, the kit plate that
  // `cb3CourseHeroPlate` just resolved arrives with `src` set and would be relabelled as a
  // caller-supplied artifact on the second pass.
  if (row.scene === 'kit' && direct) {
    return {
      scene: 'kit',
      artifactId: null,
      sceneArtifact: row.sceneArtifact || null,
      src: direct,
      credit: null,
      anchors
    }
  }
  if (artifactId || direct) {
    return {
      scene: 'artifact',
      artifactId,
      sceneArtifact: artifactId,
      src: direct,
      credit: row.credit || null,
      anchors
    }
  }
  for (const id of ['course-map', 'home-hero']) {
    const src = source(id)
    if (typeof src === 'string' && src) {
      return { scene: 'kit', artifactId: null, sceneArtifact: id, src, credit: null, anchors }
    }
  }
  return { scene: 'none', artifactId: null, sceneArtifact: null, src: null, credit: null, anchors }
}

/** The one hero plate a course has: its approved world plate, else the approved kit field. */
function cb3CourseHeroPlate(world) {
  const assets = world && Array.isArray(world.assets) ? world.assets : []
  const hero = cbWorldPlate(assets, 'hero')
  const anchors = cb3CoursePlateAnchors(hero, world)
  const base =
    hero && hero.artifact_id
      ? { artifactId: hero.artifact_id, src: null, anchors, credit: hero.attribution || null }
      : { artifactId: null, src: null, anchors, credit: null }
  // D-007: the approved kit is the product lane, so the course home always has a field behind its
  // trail. A per-course approved artifact still wins over the kit plate.
  return cb3CourseHeroResolution({ plate: base })
}

/**
 * The route's sections as nodes. State precedence is honest: a gated section is `locked`, the
 * section the backend names current is `current`, a section with independent evidence is `done`,
 * everything else is `upcoming`. `label` is the section's own title; when the outline carries no
 * title the node falls back to its state word rather than to a fabricated name.
 */
function cb3CourseNodes({ objectives, row, page, complete = false }) {
  const list = Array.isArray(objectives) ? objectives.filter(Boolean) : []
  const summary = (row && row.evidence_summary) || {}
  const section = page && page.section
  const mainline = mainlineObjective(row, list) || {}
  const currentId =
    (section && section.objective_id) || summary.current_objective_id || mainline.objective_id || null
  return list.map((entry, index) => {
    const locked = entry.locked === true || entry.state === 'locked'
    const independent = entry.independent === true || entry.state === 'completed'
    let state = 'upcoming'
    if (locked) state = 'locked'
    // At the course's close every node is done, including whichever section was opened last:
    // SPEC-V3 §5.4's `course-end` says "every node marked done", and leaving the last section as
    // the current step would mark one node not-done on a screen whose own beat is completion.
    else if (complete && independent) state = 'done'
    else if (entry.objective_id === currentId) state = 'current'
    else if (independent) state = 'done'
    const word =
      state === 'current'
        ? CB3_COURSE_COPY.nodeCurrent
        : state === 'done'
          ? CB3_COURSE_COPY.nodeDone
          : state === 'locked'
            ? CB3_COURSE_COPY.nodeLocked
            : CB3_COURSE_COPY.nodeNext
    return {
      id: entry.objective_id || `node-${index + 1}`,
      sectionKey: entry.section_key || entry.section_id || entry.objective_id || null,
      label: entry.title || null,
      state,
      word,
      ordinal: Number(entry.ordinal) || index + 1
    }
  })
}

/**
 * Map or list. The map needs a wide route **and** a placement for every node: a plate that misses
 * one section would hide it, so a partial anchor set falls back to the complete vertical route
 * rather than drawing an incomplete path.
 */
function cb3CourseRoutePlan({ nodes, anchors, width }) {
  const list = Array.isArray(nodes) ? nodes : []
  const wide = Number(width) >= 900
  const points_ = cb3CourseAnchorPoints(anchors)
  if (wide && list.length && points_.length) {
    const byKey = new Map(list.map((node) => [String(node.sectionKey), node]))
    const points = []
    for (const anchor of points_) {
      const node = byKey.get(String(anchor.key))
      if (!node) continue
      if (points.some((point) => point.node.id === node.id)) continue
      points.push({ node, x: anchor.x, y: anchor.y })
    }
    if (points.length === list.length) return { mode: 'map', points }
  }
  return { mode: 'list', points: [] }
}

/**
 * One route node placed on the plate. A button, not an ornament: it has a 48/56 px dot, its
 * section's title on a paper chip (never a scrim over art), `aria-current="step"` and the word for
 * its state, and the anchor is the only thing that decides where it sits.
 */
function CourseRouteMapNode({ node, x, y, big, onOpen }) {
  const size = big ? '56px' : '48px'
  const locked = node.state === 'locked'
  const current = node.state === 'current'
  return jsxs('button', {
    type: 'button',
    'data-cb-course-node': node.id,
    'data-cb-course-node-state': node.state,
    'data-cb-course-anchor': `${x.toFixed(4)},${y.toFixed(4)}`,
    'aria-current': current ? 'step' : undefined,
    disabled: locked,
    'aria-disabled': locked ? 'true' : undefined,
    className: 'cb3-press',
    onClick: () => {
      if (locked || typeof onOpen !== 'function') return
      onOpen(node.id)
    },
    style: {
      position: 'absolute',
      left: `${(x * 100).toFixed(3)}%`,
      top: `${(y * 100).toFixed(3)}%`,
      transform: 'translate(-50%, -50%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '0.25rem',
      minWidth: size,
      padding: 0,
      border: 0,
      background: 'transparent',
      color: cb3Role('ink'),
      fontFamily: 'var(--cb3-font-ui)',
      fontSize: cb3Type('caption'),
      lineHeight: cb3Lead('caption'),
      cursor: locked ? 'not-allowed' : 'pointer',
      textAlign: 'center'
    },
    children: [
      jsx('span', {
        'aria-hidden': 'true',
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: size,
          height: size,
          boxSizing: 'border-box',
          borderRadius: cb3Radius('pill'),
          backgroundColor: cb3Role('card-stock'),
          border: `1px solid ${cb3Role('rule')}`,
          // The current step is marked by a 3 px ring *and* by the word below it, never by colour
          // alone (SPEC-V3 §5.4, better than the concept #1).
          outline: current ? `3px solid ${cb3Role('terracotta')}` : 'none',
          outlineOffset: '0px',
          opacity: locked ? 0.5 : 1
        },
        children: jsx(sdk.Codicon, {
          name: locked ? 'lock' : current ? 'play' : node.state === 'done' ? 'check' : 'chevron-right',
          size: CB_ICON_UI
        })
      }, 'dot'),
      jsx('span', {
        'data-cb-course-node-label': '',
        // Type over the plate sits on an opaque token chip, never raw art: `card-stock` carries
        // `ink` at 15:1 in both modes. No text is baked into the plate itself.
        'data-cb-course-scrim': 'card-stock',
        style: {
          maxWidth: '14ch',
          paddingInline: '0.35rem',
          paddingBlock: '0.1rem',
          borderRadius: cb3Radius('soft'),
          backgroundColor: cb3Role('card-stock'),
          border: `1px solid ${cb3Role('rule')}`,
          overflowWrap: 'anywhere'
        },
        children: node.label || node.word
      }, 'label'),
      node.label ? jsx('span', {
        'data-cb-course-node-word': '',
        'data-cb-course-scrim': 'card-stock',
        style: {
          paddingInline: '0.3rem',
          borderRadius: cb3Radius('soft'),
          backgroundColor: cb3Role('card-stock'),
          color: current ? cb3Role('ink') : cb3Role('ink-soft'),
          fontWeight: current ? 600 : 400
        },
        children: node.word
      }, 'word') : null
    ]
  })
}

/** The vertical route: the same nodes as `StampNode` buttons, in section order. */
function CourseRouteList({ nodes, onOpen }) {
  return jsx('ol', {
    'data-cb-course-route': 'list',
    'aria-label': CB3_COURSE_COPY.routeLabel,
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
      margin: 0,
      padding: 0,
      listStyle: 'none',
      minWidth: 0
    },
    children: nodes.map((node, index) =>
      jsx(
        'li',
        {
          'data-cb-course-route-item': node.id,
          style: { display: 'flex', minWidth: 0 },
          children: jsx(StampNode, {
            state: node.state,
            label: node.label || node.word,
            stateWord: node.word,
            index: index + 1,
            onClick: () => {
              if (node.state === 'locked' || typeof onOpen !== 'function') return
              onOpen(node.id)
            }
          })
        },
        node.id
      )
    )
  })
}

/**
 * The world's plate posture, from the state the backend recorded — never inferred from art
 * presence. `unavailable`, `not_requested` and an absent world are `none`; a generating kit keeps
 * the last approved plate underneath and says it is painting (`running`); a failed generation is
 * `rejected`, and its typographic field says the scene was not approved.
 */
function cb3CourseWorldPosture(state) {
  const value = String(state || '')
  if (value === 'approved' || value === 'kit_ready') return 'ready'
  if (value === 'failed') return 'rejected'
  if (
    value === 'concepts_generating' ||
    value === 'concepts_ready' ||
    value === 'style_selected' ||
    value === 'kit_generating' ||
    value === 'stale'
  ) {
    return 'running'
  }
  return 'none'
}

/**
 * The mounted hero plate (M4): an 8 px `canvas-edge` mat, a 1 px `ink` rule, `elev-1`, and art
 * that is textless. With no plate it is a typographic field carrying the course title, and the
 * deck's own state row says what the learner loses — the lesson still works. A world in flight
 * keeps its last approved plate underneath; a rejected world says so and offers the one quiet
 * way into the studio, never a dead control.
 */
function CourseHeroPlate({ plate, title, big, worldState, onOpenStudio, children }) {
  const preview = useArtifactPreview(plate && plate.artifactId ? plate.artifactId : null)
  const direct = plate && typeof plate.src === 'string' && plate.src ? plate.src : null
  const posture = cb3CourseWorldPosture(worldState)
  const painted =
    (!plate || !plate.artifactId) && direct
      ? direct
      : preview.state === 'ready' && preview.mime && String(preview.mime).startsWith('image/')
        ? preview.data_url
        : null
  // A rejected world never paints its refused art: the field carries the course title instead.
  const ready = posture === 'rejected' ? null : painted
  const note =
    posture === 'running'
      ? jsx('p', {
          'data-cb-course-plate-note': '',
          'data-cb-course-plate-running': '',
          style: {
            margin: 0,
            fontFamily: 'var(--cb3-font-ui)',
            fontSize: cb3Type('caption'),
            lineHeight: cb3Lead('caption'),
            color: cb3Role('ink-soft')
          },
          children: CB3_COURSE_COPY.worldRunning
        }, 'note')
      : posture === 'rejected'
        ? jsxs('div', {
            'data-cb-course-plate-note': '',
            'data-cb-course-plate-rejected': '',
            style: {
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'baseline',
              gap: '0.5rem',
              minWidth: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              color: cb3Role('ink-soft')
            },
            children: [
              jsx('strong', { style: { fontWeight: 600 }, children: CB3_COURSE_COPY.worldRejectedTitle }, 'title'),
              typeof onOpenStudio === 'function'
                ? jsx('button', {
                    type: 'button',
                    'data-cb-course-world-studio': '',
                    className: 'cb3-press',
                    onClick: () => onOpenStudio(),
                    style: {
                      border: 0,
                      background: 'transparent',
                      padding: 0,
                      color: cb3Role('ink'),
                      fontFamily: 'var(--cb3-font-ui)',
                      fontSize: cb3Type('caption'),
                      lineHeight: cb3Lead('caption'),
                      textDecoration: 'underline',
                      cursor: 'pointer'
                    },
                    children: CB3_COURSE_COPY.worldRejectedAction
                  }, 'action')
                : null
            ]
          }, 'note')
        : ready
          ? plate && plate.credit
            ? jsx('p', {
                'data-cb-course-credit': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('caption'),
                  lineHeight: cb3Lead('caption'),
                  color: cb3Role('ink-soft')
                },
                children: plate.credit
              }, 'note')
            : null
          : jsxs('p', {
              'data-cb-course-plate-note': '',
              style: {
                margin: 0,
                fontFamily: 'var(--cb3-font-ui)',
                fontSize: cb3Type('caption'),
                lineHeight: cb3Lead('caption'),
                color: cb3Role('ink-soft')
              },
              children: [
                jsx('strong', { style: { fontWeight: 600 }, children: CB3_COURSE_COPY.noWorldTitle }, 'title'),
                ' ',
                jsx('span', { children: CB3_COURSE_COPY.noWorldBody }, 'body')
              ]
            }, 'note')
  return jsxs('div', {
    'data-cb-course-plate': ready ? 'art' : 'type',
    'data-cb-course-plate-state': plate && plate.artifactId ? preview.state : ready ? 'ready' : 'none',
    'data-cb-course-world-state': posture,
    // The painted plate's provenance, so a capture can name the scene it is looking at instead of
    // inferring it from a blob. `artifact` is the course's own approved plate; `kit` is the
    // approved field_atlas plate standing behind the trail (D-007). A plate that is not painted
    // (a rejected world, or an install with no kit segment) carries no scene marker.
    'data-cb3-scene': ready && plate && plate.scene && plate.scene !== 'none' ? plate.scene : undefined,
    'data-cb3-scene-artifact':
      ready && plate ? plate.artifactId || plate.sceneArtifact || undefined : undefined,
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: [
      jsxs('div', {
        className: 'cb3-shelf',
        style: {
          position: 'relative',
          width: '100%',
          // An art plate is the fixed M4 ratio (3:1 wide, 2:1 compact). The typographic field is
          // the same ratio as a **minimum** and grows with its title: at 200 % text a heading-step
          // title needed more than the fixed 204/214 px box and its first lines were cut off.
          aspectRatio: ready ? (big ? '3 / 1' : '2 / 1') : undefined,
          minHeight: ready ? undefined : big ? '204px' : '214px',
          padding: '8px',
          boxSizing: 'border-box',
          backgroundColor: cb3Role('canvas-edge'),
          border: `1px solid ${cb3Role('ink')}`,
          borderRadius: cb3Radius('round'),
          overflow: 'hidden',
          minWidth: 0
        },
        children: [
          jsxs('div', {
            style: {
              position: 'relative',
              width: '100%',
              height: ready ? '100%' : 'auto',
              minHeight: ready ? undefined : big ? '188px' : '198px',
              overflow: 'hidden',
              borderRadius: cb3Radius('soft'),
              backgroundColor: cb3Role('card-stock')
            },
            children: [
              ready
                ? jsx('img', {
                    'data-cb-course-plate-art': '',
                    src: ready,
                    alt: '',
                    'aria-hidden': 'true',
                    style: { display: 'block', width: '100%', height: '100%', objectFit: 'cover' }
                  }, 'art')
                : jsx('span', {
                    'data-cb-course-plate-title': '',
                    style: {
                      // Positioned over the art; in the typographic field it is in flow so the
                      // field can grow with the title instead of clipping it.
                      position: ready ? 'absolute' : 'static',
                      inset: ready ? 0 : undefined,
                      width: ready ? undefined : '100%',
                      minHeight: ready ? undefined : big ? '188px' : '198px',
                      display: 'flex',
                      alignItems: 'flex-end',
                      padding: '0.75rem',
                      boxSizing: 'border-box',
                      fontFamily: 'var(--cb3-font-display)',
                      // The plate is a fixed-height field (SPEC-V3 §5.4 M4: 3:1 wide, 2:1 compact),
                      // so its decorative title takes the body step at compact widths: the course
                      // `h2` already carries the heading, and a heading step inside a 214 px field
                      // clipped the title's first lines at 200 % text.
                      fontSize: cb3Type(big ? 'heading' : 'body'),
                      lineHeight: cb3Lead(big ? 'heading' : 'body'),
                      fontWeight: 600,
                      color: cb3Role('ink'),
                      // Normal word wrapping: a title may wrap between words, never inside one.
                      // `anywhere` split "demonstration" mid-word at 460 px / 200 % text; `break-word`
                      // still reflows a word that genuinely cannot fit, without hyphenating it.
                      overflowWrap: 'break-word',
                      wordBreak: 'normal',
                      hyphens: 'none'
                    },
                    children: title || ''
                  }, 'type'),
              children
            ]
          })
        ]
      }),
      note
    ]
  })
}

/**
 * The aside (M6–M9): Continue, the evidence count, the other courses, the fox. Continue is the
 * screen's only filled control, and its label is the backend's own `next_step.label` — including
 * the review and completion steps, which are the backend's words, not a second action.
 */
function CourseHomeAside({
  row,
  nodes,
  evidenceLine,
  others,
  step,
  big,
  busy,
  onContinue,
  onOpenPlan,
  onOpenOther
}) {
  const nextStep = (row && row.next_step) || {}
  const motion = useCbMotion()
  const nextLabel = nextStep.label || step.label
  const complete = step.done === true
  const planReview = !complete && step.kind === 'review_plan'
  const heading = complete
    ? CB3_COURSE_COPY.endTitle
    : planReview
      ? CB3_COURSE_COPY.planReviewTitle
      : CB3_COURSE_COPY.continueTitle
  const body = complete
    ? CB3_COURSE_COPY.endBody
    : planReview
      ? CB3_COURSE_COPY.planReviewBody
      : null
  const run = () => {
    if (planReview || complete) {
      if (typeof onOpenPlan === 'function') onOpenPlan()
      return
    }
    if (typeof onContinue === 'function') onContinue(nextStep.kind || 'start_lesson')
  }
  const others_ = Array.isArray(others) ? others.slice(0, 3) : []
  return jsxs('aside', {
    'data-cb-course-aside': '',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.85rem',
      minWidth: 0,
      alignItems: 'flex-start'
    },
    children: [
      jsxs('section', {
        'data-cb-continue': step.kind || 'none',
        className: 'cb3-card',
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          width: '100%',
          padding: '1rem',
          boxSizing: 'border-box',
          minWidth: 0
        },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              fontWeight: 700,
              color: cb3Role('ink-soft')
            },
            children: heading
          }, 'heading'),
          body
            ? jsx('p', {
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('body'),
                  lineHeight: cb3Lead('body'),
                  color: cb3Role('ink')
                },
                children: body
              }, 'body')
            : null,
          jsx(PillAction, {
            variant: 'primary',
            'data-cb-continue-action': '',
            label: nextLabel,
            busy: Boolean(busy),
            disabled: Boolean(busy),
            onClick: run,
            style: { width: '100%' }
          }, 'primary')
        ]
      }, 'continue'),
      jsxs('section', {
        'data-cb-course-evidence': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', width: '100%', minWidth: 0 },
        children: [
          jsx('h3', {
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('caption'),
              lineHeight: cb3Lead('caption'),
              fontWeight: 700,
              color: cb3Role('ink-soft')
            },
            children: CB3_COURSE_COPY.evidenceTitle
          }, 'heading'),
          jsx('p', {
            'data-cb-course-evidence-count': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-ui)',
              fontSize: cb3Type('meta'),
              lineHeight: cb3Lead('meta'),
              color: cb3Role('ink')
            },
            children: evidenceLine
          }, 'count')
        ]
      }, 'evidence'),
      others_.length
        ? jsxs('section', {
            'data-cb-course-others': '',
            style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', width: '100%', minWidth: 0 },
            children: [
              jsx('h3', {
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('caption'),
                  lineHeight: cb3Lead('caption'),
                  fontWeight: 700,
                  color: cb3Role('ink-soft')
                },
                children: CB3_COURSE_COPY.othersTitle
              }, 'heading'),
              jsx('ul', {
                style: {
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem',
                  margin: 0,
                  padding: 0,
                  listStyle: 'none',
                  minWidth: 0
                },
                children: others_.map((item) => {
                  const rowStyle = {
                    display: 'flex',
                    alignItems: 'center',
                    width: '100%',
                    minHeight: '40px',
                    padding: '0.35rem 0.5rem',
                    boxSizing: 'border-box',
                    textAlign: 'left',
                    border: `1px solid ${cb3Role('rule')}`,
                    borderRadius: cb3Radius('soft'),
                    backgroundColor: cb3Role('card-stock'),
                    color: cb3Role('ink'),
                    fontFamily: 'var(--cb3-font-ui)',
                    fontSize: cb3Type('meta'),
                    lineHeight: cb3Lead('meta'),
                    overflowWrap: 'anywhere'
                  }
                  const text = `${item.title} · ${(item.next_step && item.next_step.label) || CB3_COURSE_COPY.continueTitle}`
                  // A row is a signpost. It is a control only when this surface can actually open
                  // the course; a button that goes nowhere is a dead end, so with no handler the
                  // row stays plain text.
                  const interactive = typeof onOpenOther === 'function'
                  return jsx(
                    'li',
                    {
                      'data-cb-course-other-row': item.course_id || '',
                      style: { minWidth: 0 },
                      children: interactive
                        ? jsx('button', {
                            type: 'button',
                            'data-cb-course-other': item.course_id || '',
                            className: 'cb3-press',
                            onClick: () => onOpenOther(item),
                            style: { ...rowStyle, cursor: 'pointer' },
                            children: text
                          })
                        : jsx('span', { style: rowStyle, children: text })
                    },
                    item.course_id || item.title
                  )
                })
              }, 'rows')
            ]
          }, 'others')
        : null,
      // M9: the course-home pose is the approved `point` asset, beside the Continue plate and
      // outside the hero's quiet field. The box never exceeds its export (208 gets the 256 master,
      // 128 gets the 128) so the character is never upscaled. `FoxPose` hides itself below a
      // 620 px route; a reader who asked for reduced motion gets no companion figure at all.
      motion.reduced ? null : jsx(FoxPose, { pose: 'point', size: big ? 208 : 128 }, 'fox')
    ]
  })
}

/**
 * The v3 course home. One composition, two route modes, every value read from a caller that read
 * the backend: no fetch happens here, so the surface can be rendered in a test and in the route
 * from the same data.
 */
function CourseHomeV3({
  row,
  objectives,
  page,
  plate,
  anchors,
  others,
  sectionsDone,
  sectionsTotal,
  parentLabel,
  width,
  busy,
  worldState,
  readState,
  onBack,
  onContinue,
  onOpenPlan,
  onOpenSection,
  onOpenOther,
  onRetry,
  onOpenStudio
}) {
  const measured = useCbViewportWidth()
  const routeWidth = Number(width) > 0 ? Number(width) : Number(measured) || 0
  // Two breakpoints, kept apart on purpose (SPEC-V3 §5.4): the map route holds from 900 px, where
  // M5's nodes shrink to 48 and the plate stays 3:1; the aside only becomes a right column at
  // 1000 px, where the nodes are 56 and the fox is 96. Tying the column to the map breakpoint put
  // a 268 px aside beside an 852 px plate on a 900 route, which §5.4 puts below the route.
  const mapWide = routeWidth >= 900
  const wide = routeWidth >= 1000
  const summary = (row && row.evidence_summary) || {}
  const declaredDone = Number(sectionsDone)
  const done = Number.isFinite(declaredDone)
    ? Math.max(0, declaredDone)
    : Math.max(0, Number(summary.independent) || 0)
  const total = Math.max(0, Number(sectionsTotal) || Number(summary.total_objectives) || 0)
  const courseComplete = total > 0 && done >= total
  // `complete` is passed before the anchors: at the course's close every node reads done, so the
  // last opened section cannot keep a "You are here" word on a completed route.
  const nodes = cb3CourseNodes({ objectives, row, page, complete: courseComplete })
  // Anchor precedence: an explicit set from the caller, then the plate's own declaration, then the
  // plate row's inline field. The plan normalises whichever arrives, and falls back to the vertical
  // route when a section would be left unplaced.
  const explicitAnchors = Array.isArray(anchors) && anchors.length ? anchors : null
  const manifestAnchors = cb3CoursePlateAnchors(plate, null)
  const plan = cb3CourseRoutePlan({
    nodes,
    anchors:
      explicitAnchors ||
      (manifestAnchors.length
        ? manifestAnchors
        : plate && Array.isArray(plate.anchors)
          ? plate.anchors
          : []),
    width: routeWidth
  })
  const evidenceLine = cb3CourseEvidenceLine(done, total)
  // The hero resolves in the card's order and nothing else: the course's approved world artifact,
  // then the kit's `course-map`, then the kit's `home-hero`. Resolution happens here so a plate the
  // caller could not resolve still lands on the product lane (D-007), and the chosen source is
  // carried in the markup as `data-cb3-scene` / `data-cb3-scene-artifact`.
  const heroPlate = cb3CourseHeroResolution({ plate })
  const nextKind = (row && row.next_step && row.next_step.kind) || 'start_lesson'
  const step = {
    kind: nextKind,
    label: (row && row.next_step && row.next_step.label) || CB3_COURSE_COPY.continueTitle,
    done: courseComplete
  }
  const backLabel = CB3_COURSE_COPY.backPrefix + (parentLabel || 'Home')
  return jsxs('div', {
    'data-cb-course-home-v3': plan.mode,
    'data-cb-course-home-width': routeWidth ? String(routeWidth) : 'unknown',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.85rem',
      minWidth: 0,
      color: cb3Role('ink')
    },
    children: [
      // M2: the back path is the first focusable element on a deep screen (SPEC-V3 §3.11).
      jsxs('button', {
        type: 'button',
        'data-cb-course-back': '',
        className: 'cb3-press',
        onClick: () => {
          if (typeof onBack === 'function') onBack()
        },
        style: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
          alignSelf: 'flex-start',
          minHeight: '40px',
          paddingInline: '0.25rem',
          border: 0,
          background: 'transparent',
          color: cb3Role('ink'),
          fontFamily: 'var(--cb3-font-ui)',
          fontSize: cb3Type('meta'),
          lineHeight: cb3Lead('meta'),
          cursor: 'pointer'
        },
        children: [
          jsx(sdk.Codicon, { name: 'arrow-left', size: CB_ICON_UI }, 'icon'),
          jsx('span', { children: backLabel }, 'label')
        ]
      }, 'back'),
      // M3: the course head. The title is the screen's heading; the subject line is the deck's
      // one stored subject label.
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', minWidth: 0 },
        children: [
          jsx('h2', {
            'data-cb-course-title': '',
            style: {
              margin: 0,
              fontFamily: 'var(--cb3-font-display)',
              fontSize: cb3Type('heading'),
              lineHeight: cb3Lead('heading'),
              fontWeight: 600,
              letterSpacing: '-0.01em',
              color: cb3Role('ink'),
              maxWidth: '34ch',
              // Same rule as the plate's type field: wrap between words, never inside one.
              overflowWrap: 'break-word',
              wordBreak: 'normal',
              hyphens: 'none'
            },
            children: (row && row.title) || ''
          }, 'title'),
          row && row.subject_label
            ? jsx('p', {
                'data-cb-course-subject': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('body'),
                  lineHeight: cb3Lead('body'),
                  color: cb3Role('ink-soft')
                },
                children: row.subject_label
              }, 'subject')
            : null,
          // The course's own read state. A loading head says it is opening; a failed read says so
          // in place and offers one quiet way to try again, while the route keeps what was saved.
          readState === 'loading'
            ? jsx('p', {
                'data-cb-course-loading': '',
                style: {
                  margin: 0,
                  fontFamily: 'var(--cb3-font-ui)',
                  fontSize: cb3Type('meta'),
                  lineHeight: cb3Lead('meta'),
                  color: cb3Role('ink-soft')
                },
                children: CB3_COURSE_COPY.loading
              }, 'loading')
            : readState === 'error'
              ? jsxs('div', {
                  'data-cb-course-error': '',
                  role: 'status',
                  style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.5rem', minWidth: 0 },
                  children: [
                    jsx('strong', {
                      style: {
                        fontFamily: 'var(--cb3-font-ui)',
                        fontSize: cb3Type('meta'),
                        lineHeight: cb3Lead('meta'),
                        fontWeight: 600,
                        color: cb3Role('ink')
                      },
                      children: CB3_COURSE_COPY.errorTitle
                    }, 'title'),
                    jsx('span', {
                      style: {
                        fontFamily: 'var(--cb3-font-ui)',
                        fontSize: cb3Type('meta'),
                        lineHeight: cb3Lead('meta'),
                        color: cb3Role('ink-soft')
                      },
                      children: CB3_COURSE_COPY.errorBody
                    }, 'body'),
                    typeof onRetry === 'function'
                      ? jsx('button', {
                          type: 'button',
                          'data-cb-course-retry': '',
                          className: 'cb3-press',
                          onClick: () => onRetry(),
                          style: {
                            border: 0,
                            background: 'transparent',
                            padding: 0,
                            color: cb3Role('ink'),
                            fontFamily: 'var(--cb3-font-ui)',
                            fontSize: cb3Type('meta'),
                            lineHeight: cb3Lead('meta'),
                            textDecoration: 'underline',
                            cursor: 'pointer'
                          },
                          children: CB3_COURSE_COPY.errorAction
                        }, 'action')
                      : null
                  ]
                }, 'error')
              : null
        ]
      }, 'head'),
      // M4/M5 and M6–M9: the hero plate with the route, and the aside. Two columns only at a wide
      // route (≥ 1000 px, SPEC-V3 §5.4); below it the aside follows the plate and keeps its order.
      jsxs('div', {
        'data-cb-course-body': wide ? 'split' : 'stacked',
        style: {
          display: 'grid',
          gridTemplateColumns: wide ? 'minmax(0, 1fr) 268px' : 'minmax(0, 1fr)',
          gap: wide ? '1rem' : '0.85rem',
          alignItems: 'start',
          minWidth: 0
        },
        children: [
          jsxs('div', {
            style: { display: 'flex', flexDirection: 'column', gap: '0.75rem', minWidth: 0 },
            children: [
              jsx(CourseHeroPlate, {
                plate: heroPlate,
                title: (row && row.title) || '',
                big: mapWide,
                worldState,
                onOpenStudio,
                children:
                  plan.mode === 'map'
                    ? jsx('div', {
                        'data-cb-course-nodes': '',
                        role: 'group',
                        'aria-label': CB3_COURSE_COPY.routeLabel,
                        style: { position: 'absolute', inset: 0 },
                        children: plan.points.map((point) =>
                          jsx(
                            CourseRouteMapNode,
                            { node: point.node, x: point.x, y: point.y, big: wide, onOpen: onOpenSection },
                            point.node.id
                          )
                        )
                      })
                    : null
              }),
              // SPEC-V3 §5.4: M6 sits **below** M5, and the aside moves under the route. In list
              // mode the route therefore lives in the main column directly under the plate, so the
              // DOM order is plate → route → aside at every width (the map carries its route
              // inside the plate instead).
              plan.mode === 'list' && nodes.length
                ? jsx(CourseRouteList, { nodes, onOpen: onOpenSection }, 'route-list')
                : null
            ]
          }, 'hero'),
          jsx(CourseHomeAside, {
            row,
            nodes,
            evidenceLine,
            others,
            step,
            big: wide,
            busy,
            onContinue,
            onOpenPlan,
            onOpenOther
          }, 'aside')
        ]
      }, 'body')
    ]
  })
}

/**
 * UI-K13 — the review queue, with the four scheduling actions `review.action` records.
 *
 * A dropped item is **not** a queue row, and cannot be made into one: `coursebook.review._item`
 * returns `None` once the latest scheduling event is `review_drop`, so `review.queue` omits it
 * while its stored state still reads `independent_evidence`. Resume is therefore rendered from
 * `evidence.inspect`, whose layer-1 events carry the scheduler's own `review_drop` /
 * `review_resume` kinds newest-first — the only read that can say "this objective was taken out of
 * the queue". That read is bounded by its `limit`, so the paused list is bounded too; it never
 * claims to be the whole history.
 *
 * An objective is *not* dropped because its state is `independent_evidence`: that is also the state
 * of an overdue objective whose `refresh_due` has not run yet. Only a `review_drop` event with no
 * later `review_resume` makes a row a dropped one, so snooze / stretch / drop stay on every due row.
 */
const REVIEW_SCHEDULE_COPY = Object.freeze({
  snooze: { label: 'Snooze', hint: 'Start the interval again from today.' },
  stretch: { label: 'Stretch', hint: 'Wait one interval longer before this returns.' },
  drop: { label: 'Drop', hint: 'Take it out of the review queue. The evidence stays.' },
  resume: { label: 'Resume', hint: 'Put this section back in the review queue.' }
})

const REVIEW_QUEUE_ACTIONS = Object.freeze(['snooze', 'stretch', 'drop'])
const REVIEW_RESUME_ACTIONS = Object.freeze(['resume'])

/** The two layer-1 event kinds that change whether an objective is in the queue at all. */
const REVIEW_SCHEDULING_EVENTS = Object.freeze(['review_drop', 'review_resume'])

function reviewDueLabel(value) {
  if (!value) return 'no due date recorded'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toISOString().slice(0, 10)
}

/**
 * The objectives a learner has taken out of the review queue, derived from `evidence.inspect`.
 *
 * One row per objective whose newest scheduling event is `review_drop`. A later `review_resume`
 * cancels it, so a resumed objective never appears here. Titles come from the same read's layer 2;
 * an objective whose title is not in the bounded read keeps its id instead of inventing a name.
 */
function reviewPausedItems(evidence) {
  const l1 = (evidence && evidence.l1) || {}
  const events = Array.isArray(l1.events) ? l1.events : []
  const l2 = (evidence && evidence.l2) || {}
  const objectives = new Map()
  for (const objective of Array.isArray(l2.objectives) ? l2.objectives : []) {
    if (objective && objective.objective_id) objectives.set(objective.objective_id, objective)
  }
  // Newest first. The backend already orders the read that way; sorting defensively means a caller
  // that reorders the list cannot flip a resumed objective back to "dropped".
  const scheduling = events
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event && event.objective_id && REVIEW_SCHEDULING_EVENTS.includes(event.kind))
    .sort((a, b) => {
      const left = Date.parse(a.event.created_at)
      const right = Date.parse(b.event.created_at)
      if (Number.isFinite(left) && Number.isFinite(right) && left !== right) return right - left
      return a.index - b.index
    })
  const newest = new Map()
  for (const { event } of scheduling) {
    if (!newest.has(event.objective_id)) newest.set(event.objective_id, event)
  }
  const rows = []
  for (const [objectiveId, event] of newest) {
    if (event.kind !== 'review_drop') continue
    const objective = objectives.get(objectiveId) || null
    const ordinal = objective && typeof objective.ordinal === 'number' ? objective.ordinal : null
    rows.push({
      objective_id: objectiveId,
      title: (objective && objective.title) || objectiveId,
      state: (objective && objective.state) || null,
      ordinal,
      dropped_at: event.created_at || null,
      due_at: null,
      overdue: false
    })
  }
  rows.sort((a, b) => (Number(a.ordinal) || 0) - (Number(b.ordinal) || 0))
  return rows
}

/**
 * The queue panel: the rows `review.queue` says are due, then the rows `evidence.inspect` says were
 * taken out of the queue. Both lists call the same method and both show its answer as evidence.
 */
function ReviewDuePanel({ enrollmentId, revision, review, evidence, onRecorded, onOpenSection }) {
  const dueRows = (review && Array.isArray(review.items) ? review.items : []).filter(
    (item) => item && (item.overdue || item.state === 'review_due')
  )
  const pausedRows = reviewPausedItems(evidence)
  const rows = [
    ...dueRows.map((item) => ({ item, paused: false })),
    ...pausedRows.map((item) => ({ item, paused: true }))
  ]
  const [pending, setPending] = useState(null)
  const [outcomes, setOutcomes] = useState({})
  const [error, setError] = useState(null)

  const act = useCallback(
    async (item, action) => {
      const objectiveId = item && item.objective_id
      if (!objectiveId) return
      setPending(`${objectiveId}:${action}`)
      setError(null)
      // One logical action at one revision is one operation: a double click replays the stored
      // result instead of writing a second scheduling event.
      const response = await rpc(
        'review.action',
        { enrollment_id: enrollmentId, objective_id: objectiveId, action },
        {
          expectedRevision: Number(revision) || 0,
          idempotencyKey: `cb-review-${objectiveId}-${action}-${Number(revision) || 0}`
        }
      )
      setPending(null)
      if (!response || response.ok !== true) {
        setError(
          (response && response.error) || {
            code: 'INTERNAL_ERROR',
            message: 'The backend did not answer the review action, so nothing here changed.'
          }
        )
        const current = response && response.error ? staleRevision(response) : null
        if (current !== null) onRecorded && onRecorded(current)
        return
      }
      const result = response.result || {}
      setOutcomes((previous) => ({
        ...previous,
        [objectiveId]: {
          action: result.action || action,
          state: result.state || null,
          due_at: result.due_at !== undefined ? result.due_at : null,
          recorded_at: result.recorded_at || null
        }
      }))
      if (onRecorded && typeof response.revision === 'number') onRecorded(response.revision)
    },
    [enrollmentId, revision, onRecorded]
  )

  if (rows.length === 0) return null

  return jsxs('div', {
    'data-cb-review-queue': String(rows.length),
    'data-cb-review-paused-count': String(pausedRows.length),
    style: { display: 'flex', flexDirection: 'column', gap: '0.4rem', minWidth: 0 },
    children: [
      // Every row this read produced gets its controls. There is no display cap: a cap made the
      // queue actions and the Resume door unreachable past the Nth row while the banner above
      // still counted the whole read, which is the defect this panel exists to close. The reads
      // are already bounded (`review.queue` cap 25, `evidence.inspect` limit 200).
      rows.map(({ item, paused }) => {
        const objectiveId = item.objective_id
        const actions = paused ? REVIEW_RESUME_ACTIONS : REVIEW_QUEUE_ACTIONS
        const outcome = outcomes[objectiveId] || null
        const busyRow = pending !== null && String(pending).startsWith(`${objectiveId}:`)
        // Repeated controls must not share one accessible name: three rows of "Snooze" give a
        // screen-reader user no way to tell which section each acts on. The repo's own
        // convention names the target (cf. `20-packs.js` "Actions for ${row.title}").
        const title = item.title || 'Untitled section'
        const rowLabel = item.ordinal ? `section ${item.ordinal}: ${title}` : title
        const stateLine = paused
          ? `${OBJECTIVE_STATE_COPY[item.state] || item.state || 'State not recorded'} · dropped ${reviewDueLabel(item.dropped_at)}`
          : `${OBJECTIVE_STATE_COPY[item.state] || item.state || 'State not recorded'} · due ${reviewDueLabel(item.due_at)}`
        return jsxs(
          'div',
          {
            'data-cb-review-item': objectiveId,
            'data-cb-review-state': item.state || 'unknown',
            'data-cb-review-paused': paused ? 'true' : 'false',
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.25rem',
              padding: '0.4rem 0',
              borderTop: '1px solid var(--cb-rule)',
              minWidth: 0
            },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.3rem 0.6rem', minWidth: 0 },
                children: [
                  jsx('span', {
                    style: { fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)', overflowWrap: 'anywhere' },
                    children: title
                  }),
                  jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: stateLine
                  }),
                  onOpenSection && objectiveId
                    ? jsx(sdk.Button, {
                        variant: 'text',
                        size: 'sm',
                        'aria-label': `Open ${rowLabel}`,
                        title: `Open ${rowLabel}`,
                        onClick: () => onOpenSection(objectiveId),
                        children: 'Open section'
                      })
                    : null
                ]
              }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.35rem' },
                children: [
                  jsx('span', {
                    style: { fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                    children: paused
                      ? 'You took this out of the queue. Resume puts it back.'
                      : 'Decide when this comes back.'
                  }),
                  actions.map((action) =>
                    jsx(
                      sdk.Button,
                      {
                        variant: 'text',
                        size: 'sm',
                        'data-cb-review-action': action,
                        'data-cb-review-target': objectiveId,
                        disabled: busyRow,
                        'aria-label': `${REVIEW_SCHEDULE_COPY[action].label} review of ${rowLabel}`,
                        title: `${REVIEW_SCHEDULE_COPY[action].hint} (${rowLabel})`,
                        onClick: () => act(item, action),
                        children:
                          pending === `${objectiveId}:${action}`
                            ? `${REVIEW_SCHEDULE_COPY[action].label}…`
                            : REVIEW_SCHEDULE_COPY[action].label
                      },
                      action
                    )
                  )
                ]
              }),
              outcome
                ? jsxs('div', {
                    'data-cb-review-outcome': `${outcome.action}:${outcome.state || 'unknown'}`,
                    style: { fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink)' },
                    children: [
                      `${REVIEW_SCHEDULE_COPY[outcome.action] ? REVIEW_SCHEDULE_COPY[outcome.action].label : outcome.action} recorded. `,
                      `State now ${OBJECTIVE_STATE_COPY[outcome.state] || outcome.state || 'not recorded'}; `,
                      `next due ${reviewDueLabel(outcome.due_at)}; `,
                      `recorded ${whenLabel(outcome.recorded_at)}.`
                    ]
                  })
                : null
            ]
          },
          objectiveId
        )
      }),
      error
        ? jsxs('div', {
            'data-cb-review-refusal': error.code || 'ERROR',
            style: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
            children: [
              jsx(ErrorLine, {
                error: {
                  ...error,
                  message: `${error.message || describeError(error)} The queue is unchanged; read it again before retrying.`
                }
              }),
              jsx(sdk.Button, {
                variant: 'text',
                size: 'sm',
                onClick: () => onRecorded && onRecorded(Number(revision) || 0),
                children: 'Read the queue again'
              })
            ]
          })
        : null
    ]
  })
}

/**
 * Course detail — the durable page for one enrollment.
 *
 * Local tabs, not more sidebar destinations. At wide widths the view switcher is a segmented
 * control; below ~47.5rem it collapses into one labelled picker so the strip can never clip.
 */
function CourseDetail({ row, implemented, profile, prefs, onBack, onChanged, focusObjectiveId, focusBlockId, focusView, defaultLessonView, reloadSignal, onChangeGoal, onNewSyllabus, onOpenLibrary }) {
  const supports = (method) => Boolean(implemented && implemented.has(method))
  // A route in from the Field Desk names the section to open; otherwise the course opens on its
  // overview with the backend's own current objective already selected.
  const [view, setView] = useState(focusView || (focusObjectiveId ? 'textbook' : 'overview'))
  const [objectiveId, setObjectiveId] = useState(
    focusObjectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id) || null
  )
  const [openSectionId, setOpenSectionId] = useState(focusObjectiveId || null)
  // A saved moment carries the block it came from; the section opens on that block, not its top.
  const [targetBlockId, setTargetBlockId] = useState(focusBlockId || null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  // CP-024: a rejected world's one quiet next action opens the studio that owns the world. It is
  // the shipped surface from 97-world.js, rendered as a sheet over this page — the course home
  // never grows a second world editor of its own, and a failed read never opens it silently.
  const [studioOpen, setStudioOpen] = useState(false)
  // `plan.approve` fences on the enrolment revision, so the page tracks the revision the last
  // mutation returned instead of trusting the row it was opened with.
  const [revision, setRevision] = useState(Number(row.revision || 0))

  const outline = useRpcQuery(
    'course.outline',
    { enrollment_id: row.enrollment_id },
    `outline-${row.enrollment_id}`,
    supports('course.outline')
  )
  const review = useRpcQuery(
    'review.queue',
    { enrollment_id: row.enrollment_id, cap: 25, include_upcoming: true },
    `review-${row.enrollment_id}`,
    supports('review.queue')
  )
  const notebooks = useRpcQuery(
    'notebook.list',
    { enrollment_id: row.enrollment_id },
    `notebook-${row.enrollment_id}`,
    supports('notebook.list')
  )
  const quizzes = useRpcQuery(
    'quiz.history',
    { enrollment_id: row.enrollment_id },
    `quiz-${row.enrollment_id}`,
    supports('quiz.history')
  )
  const evidence = useRpcQuery(
    'evidence.inspect',
    // The contract's own maximum: the review panel derives its paused rows from this read's
    // layer-1 events, so a short window would hide a drop the learner can still undo.
    { enrollment_id: row.enrollment_id, limit: 200 },
    `evidence-${row.enrollment_id}`,
    supports('evidence.inspect')
  )
  // UI-K13: `review.queue` cannot return a dropped objective, so the resume door reads the
  // scheduler's own drop/resume events out of the evidence bundle this page already holds.
  const pausedReview = reviewPausedItems(evidence.data)
  // H-174: the section whose page this screen is about. The backend's current objective wins; a
  // course whose plan exists but whose evidence is empty opens on the plan's mainline section, so
  // the hero can answer "is there a readable page here?" instead of guessing from an absent id.
  const outlineObjectives =
    outline.data && Array.isArray(outline.data.objectives) ? outline.data.objectives.filter(Boolean) : []
  const pageObjectiveId =
    objectiveId ||
    ((mainlineObjective(row, outlineObjectives) || {}).objective_id || null)
  // The plan and the lessons job are what author this page. The page read alone cannot say why a
  // section is empty; this row of jobs names the job that owns it (H-174).
  const jobs = useRpcQuery(
    'jobs.list',
    { enrollment_id: row.enrollment_id, limit: 20 },
    `course-jobs-${row.enrollment_id}`,
    supports('jobs.list')
  )
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: row.enrollment_id, objective_id: pageObjectiveId },
    `page-${row.enrollment_id}-${pageObjectiveId}`,
    supports('lesson.page') && Boolean(pageObjectiveId)
  )
  // CP-024 M8: the aside's `Your other courses` rows read the same library the Home shelf reads.
  // It is a real read with no counters, and the course whose page this is is filtered out.
  const library = useRpcQuery(
    'library.list',
    { filter: 'all', limit: 20, sort: 'recent' },
    `course-others-${row.enrollment_id}`,
    supports('library.list')
  )

  // GM-010: the play layer belongs to the course's Game overview and nowhere else. The durable mode
  // comes from `world.read` (a library row carries none); the read is enabled only on that surface,
  // so opening the reading path (Textbook, Guided or Field Quest) issues no engagement call and
  // cannot paint a chip, and no other surface mounts this block.
  const world = useWorldRead(row.course_id, true)
  const courseMode = world.data ? readCoursePresentationMode(world.data.presentation_mode) : null
  const courseGame = cbGameCourse(row, courseMode)
  const engagement = useRpcQuery(
    'engagement.read',
    { course_id: row.course_id, enrollment_id: row.enrollment_id },
    `game-${row.enrollment_id}`,
    courseGame && supports('engagement.read') && view === 'overview'
  )

  const refresh = useCallback(() => {
    review.reload()
    notebooks.reload()
    quizzes.reload()
    evidence.reload()
    page.reload()
    jobs.reload()
    if (outline) outline.reload()
    if (library) library.reload()
    if (onChanged) onChanged()
  }, [review, notebooks, quizzes, evidence, page, jobs, outline, library, onChanged])

  const openSection = useCallback((nextObjectiveId, blockId) => {
    if (nextObjectiveId) setObjectiveId(nextObjectiveId)
    setOpenSectionId(nextObjectiveId || null)
    // Only a call that names a block aims at one; a plain "Open section" lands at the top.
    setTargetBlockId(blockId || null)
    setView('textbook')
  }, [])

  const closeSection = useCallback(() => {
    setOpenSectionId(null)
    setTargetBlockId(null)
  }, [])

  const selectView = useCallback((nextView) => {
    // `learn` is the primary surface; the reading path itself is the textbook index, and the
    // section page offers Textbook / Guided / Field Quest over the same document.
    const target = nextView === 'learn' ? 'textbook' : nextView
    setView(target)
    if (target === 'textbook') setOpenSectionId(null)
  }, [])

  const viewLabel = (LEARNING_VIEWS.find((option) => option.id === view) || { label: view }).label

  const startLesson = useCallback(
    async (mode, explicitObjectiveId) => {
      const target = explicitObjectiveId || objectiveId || pageObjectiveId || (row.evidence_summary && row.evidence_summary.current_objective_id)
      if (!target) {
        setNotice('This course has no current objective yet; approve the plan first.')
        return
      }
      setBusy(true)
      setNotice(null)
      const outcome = await beginLessonFor({
        row,
        objectiveId: target,
        objectiveTitle: page.data && page.data.section ? page.data.section.title : null,
        mode,
        profile: profile || currentScope().profile
      })
      setBusy(false)
      if (outcome.ok && outcome.armed) {
        refresh()
        // Arm first, then open the chat that the pending binder names. The old ordering opened a
        // session before a durable id existed and left the learner on a blank chat.
        const opened = openArmedLessonChat(profile || currentScope().profile)
        openSection(target)
        setNotice(
          opened
            ? { text: 'A new lesson chat is open. Send the first message to connect it to this lesson.' }
            : {
                text: outcome.message,
                action: {
                  label: 'Open the lesson chat',
                  run: () => startLessonChat(profile || currentScope().profile)
                }
              }
        )
        return
      }
      if (!outcome.ok && outcome.reason === 'no-binding') {
        setNotice({
          text: outcome.message,
          action: {
            label: 'Start a fresh run',
            run: () => startLesson('fresh', target)
          }
        })
        openSection(target)
        return
      }
      setNotice(outcome.message)
      if (outcome.ok) refresh()
      else if (outcome.reason === 'no-binding') openSection(target)
    },
    [objectiveId, pageObjectiveId, row, page.data, profile, refresh, openSection]
  )

  // H-174/H-183: write the failed page again from the brief it stored, keyed by that run so a
  // double click replays one attempt. The page never invents content and never fakes a page.
  const [readinessBusy, setReadinessBusy] = useState(false)
  const retryLessonsKey = useRef(null)
  const retryLessonsJob = useCallback(async () => {
    const job = lessonsJobFrom(jobs.data)
    if (!job || !job.brief || !job.job_id) {
      setNotice('The saved plan could not be read yet, so this page cannot be written from here. Open Plan to start it.')
      selectView('plan')
      return
    }
    setReadinessBusy(true)
    setNotice(null)
    if (!retryLessonsKey.current || retryLessonsKey.current.jobId !== job.job_id) {
      retryLessonsKey.current = { jobId: job.job_id, key: `cb-lessons-retry-${job.job_id}` }
    }
    const response = await rpc(
      'jobs.create',
      { kind: job.kind || 'plan', brief: job.brief },
      { idempotencyKey: retryLessonsKey.current.key }
    )
    setReadinessBusy(false)
    if (!response.ok) {
      setNotice(
        'This page could not be written again. The plan and every page already written are unchanged.'
      )
      return
    }
    retryLessonsKey.current = { jobId: response.result.job_id, key: null }
    setNotice('Writing this page again. Pages already written for this plan are kept.')
    refresh()
  }, [jobs.data, refresh])

  const rows = sectionRows({ row, review: review.data, notebooks: notebooks.data, outline: outline.data, page: page.data })
  const currentTitle =
    page.data && page.data.section && page.data.section.title
      ? page.data.section.title
      : (row.next_step && row.next_step.label) || 'No objective recorded yet'

  let body
  if (view === 'overview') {
    // CP-024: the course's own overview IS the v3 R-MAP composition below (`courseHome`). The
    // legacy OverviewView was still mounted under it, so the shipped screen carried two filled
    // primaries (its "Start a fresh run" plus the v3 Continue plate), two route containers and the
    // title twice — falsifying SPEC-V3 §5.4 and the quality bar's one-primary rule. It is retired
    // from this route; its Evidence tab remains the record, and M7 carries the recorded count.
    body = null
  } else if (view === 'textbook') {
    body = jsx(TextbookView, {
      row,
      page: page.data,
      pageState: page,
      review: review.data,
      notebooks: notebooks.data,
      outline: outline.data,
      planStatus: outline.status,
      jobs: jobs.data,
      implemented,
      // H-147: the Home default (or this classroom's override) is the view the section opens in.
      defaultLessonView,
      openSectionId,
      onOpenSection: openSection,
      onCloseSection: closeSection,
      onChanged: refresh,
      onOpenPlan: () => selectView('plan'),
      onRetryLessonsJob: retryLessonsJob,
      targetBlockId
    })
  } else if (view === 'notebook') {
    body = notebooks.status === 'error' && !notebooks.data
      ? jsx(sdk.ErrorState, {
          title: 'The notebook could not be read',
          description: `${notebooks.error && notebooks.error.code ? notebooks.error.code + ': ' : ''}${describeError(notebooks.error)}`,
          children: jsx(sdk.Button, { variant: 'secondary', onClick: notebooks.reload, children: 'Try again' })
        })
      : jsx(NotebookView, {
          row,
          notebooks: notebooks.data,
          implemented,
          onOpenSection: openSection,
          onChanged: refresh,
          sections: rows
        })
  } else if (view === 'quizzes') {
    body = jsx(QuizzesView, {
      row,
      quizzes: quizzes.data,
      implemented,
      onOpenSection: openSection,
      onChanged: refresh
    })
  } else if (view === 'plan') {
    body = jsx(LearnerPlanView, {
      course: { course_id: row.course_id, enrollment_id: row.enrollment_id, title: row.title },
      revision,
      onRevision: setRevision,
      implemented,
      onOpenSection: openSection,
      onStartLesson: (objectiveId) => startLesson('fresh', objectiveId),
      onChanged: refresh,
      reloadSignal,
      onChangeGoal,
      onNewSyllabus
    })
  } else if (view === 'evidence') {
    body = jsx(EvidenceView, { evidence: evidence.data, implemented, onOpenSection: openSection })
  } else if (view === 'export') {
    // A refusal names the surface that clears it; the plan is a local tab, the Library is a
    // destination. Neither navigates on its own — the learner presses the one repair button.
    body = jsx(CourseExportView, {
      row,
      implemented,
      onRepair: () => selectView('plan'),
      onOpenLibrary
    })
  } else {
    body = jsx(SourcesView, { pageState: page })
  }

  const nextKind = (row.next_step && row.next_step.kind) || 'start_lesson'
  const topCanResume = Boolean(
    page.data && page.data.runtime && page.data.runtime.binding_status === 'active'
  )
  // H-174: the hero's action set reads the page, not just the objective id. No approved page means
  // no run to start and no textbook to open; the panel below the hero names the plan or the
  // lessons job that owns the page and offers its one next action.
  const heroReadiness = lessonReadiness({
    outline: outline.data,
    page: page.data,
    jobs: jobs.data,
    pageStatus: page.status,
    planStatus: outline.status
  })
  const heroReadable = heroReadiness.state === 'readable'
  const heroPlan = lessonHeroPlan(heroReadiness, {
    overview: view === 'overview',
    sectionOpen: Boolean(openSectionId)
  })
  const objectives = outline.data && Array.isArray(outline.data.objectives) ? outline.data.objectives.filter(Boolean) : []
  const summary = row.evidence_summary || {}
  const courseProgress = objectives.length
    ? objectiveProgress(objectives)
    : {
        total: Number(summary.total_objectives) || 0,
        independent: Number(summary.independent) || 0,
        due: Number(summary.review_due) || 0
      }
  const section = page.data && page.data.section ? page.data.section : null
  const sectionTotal = objectives.length || Number(courseProgress.total) || 0
  const sectionOrdinal = section && section.ordinal ? Number(section.ordinal) : null
  const dueCount = review.data && typeof review.data.total_overdue === 'number' ? Number(review.data.total_overdue) : null
  const heroFacts = [
    sectionTotal
      ? {
          value: sectionOrdinal ? `Section ${sectionOrdinal} of ${sectionTotal}` : `${sectionTotal} ${sectionTotal === 1 ? 'section' : 'sections'}`,
          label: (section && section.title) || 'In this course'
        }
      : null,
    courseProgress.total
      ? { value: `${courseProgress.independent} of ${courseProgress.total}`, label: 'With independent evidence' }
      : null,
    dueCount !== null && dueCount > 0 ? { value: String(dueCount), label: 'Due for review' } : null
  ].filter(Boolean)
  const parentIdentity = row.recipe === 'parent' ? 'plum' : 'lamp'
  // Four primary surfaces. Learn hosts the reading path in its three lesson views (Textbook,
  // Guided, Field Quest, chosen on the section page), so the learner sees one way in, not a
  // control panel. Everything that is reference or administration sits behind one `More`
  // disclosure: Plan, Sources, Export and the record of graded attempts.
  const primaryTabs = COURSE_PRIMARY_TABS
  const moreTabs = courseMoreTabs(supports)
  const primaryActive = primarySurfaceFor(view)
  const moreActive = moreTabs.some((option) => option.id === view)
  const layout = cbLayoutFor(useCbViewportWidth())
  const phone = layout === 'phone'
  const compactHero = layout !== 'wide'
  const [moreOpen, setMoreOpen] = useState(moreActive)
  useEffect(() => {
    if (moreActive) setMoreOpen(true)
  }, [moreActive])

  // GM-010: a Game course paints its play band above the surfaces and its field journal under the
  // overview body. Both are absent from every reading view, so Textbook and Guided stay calm.
  const gameHeader =
    courseGame && view === 'overview'
      ? jsx(
          GameHeader,
          {
            engagement: engagement.data,
            status: engagement.status,
            error: engagement.error,
            prefs,
            compact: phone,
            onRetry: engagement.reload
          },
          'game-header'
        )
      : null
  const gameJournal =
    courseGame && view === 'overview'
      ? jsx(GameJournal, { objectives, compact: phone }, 'game-journal')
      : null

  // CP-024: on the course's own overview the page is the v3 R-MAP composition — the hero plate
  // with the route's nodes, one Continue plate, the evidence count and the other courses. The
  // compact hero stays for the reading surfaces, where the course head is context, not the page.
  const courseHomePlate = cb3CourseHeroPlate(world.data)
  const courseWorldState =
    world.data && world.data.world && world.data.world.state ? world.data.world.state : null
  const courseReadState =
    outline.status === 'error' || world.status === 'error'
      ? 'error'
      : outline.status === 'loading' && !outline.data
        ? 'loading'
        : 'ready'
  const otherCourses = (library.data && Array.isArray(library.data.items) ? library.data.items : []).filter(
    (item) => item && item.course_id !== row.course_id && item.recipe !== 'parent'
  )
  const courseHome =
    view === 'overview'
      ? jsx(CourseHomeV3, {
          row,
          objectives,
          page: page.data,
          plate: courseHomePlate,
          others: otherCourses,
          sectionsDone: row.sections_done,
          sectionsTotal: row.sections_total,
          parentLabel: 'Home',
          busy,
          worldState: courseWorldState,
          readState: courseReadState,
          onBack,
          onContinue: (kind) =>
            startLesson(kind === 'resume_lesson' && topCanResume ? 'resume' : 'fresh'),
          onOpenPlan: () => selectView('plan'),
          onOpenSection: openSection,
          onOpenStudio: () => setStudioOpen(true),
          onRetry: () => {
            if (outline) outline.reload()
            if (world) world.reload()
            if (page) page.reload()
          }
        })
      : null

  return jsxs('div', {
    'data-cb-course-detail': view,
    className: 'flex flex-col gap-4',
    children: [
      // CP-024: the course home carries its own back path and its one Continue plate.
      courseHome,

      // The rejected world's quiet action opens the studio that owns the world; it is a sheet over
      // this page, never a second copy of the studio and never opened on its own.
      studioOpen && view === 'overview'
        ? jsx(WorldStudio, {
            courseId: row.course_id,
            mode: courseMode || 'textbook',
            world: world.data && world.data.world ? world.data.world : null,
            worldStatus: world.status,
            worldError: world.error,
            autoStart: false,
            onReload: () => {
              if (world) world.reload()
            },
            onChanged: () => {
              refresh()
              if (onChanged) onChanged()
            },
            onClose: () => setStudioOpen(false)
          }, 'world-studio')
        : null,

      courseHome
        ? null
        : jsx(sdk.Button, {
            className: 'self-start',
            variant: 'text',
            size: 'sm',
            'data-cb-course-back': '',
            onClick: onBack,
            children: 'All courses'
          }),

      // The compact hero: one lamp field, one seal, three recorded facts, one primary action.
      courseHome ? null : jsx(HeroField, {
        identity: parentIdentity,
        phone,
        children: jsxs('div', {
          style: {
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'flex-start',
            gap: phone ? '0.75rem' : '1.75rem'
          },
          children: [
            jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: 0, flex: compactHero ? '1 1 100%' : '1 1 16rem' },
              children: [
                jsx('h2', {
                  'data-cb-course-title': '',
                  style: {
                    margin: 0,
                    fontFamily: CB_SERIF,
                    fontSize: CB_TYPE.heading,
                    fontWeight: 600,
                    lineHeight: 1.12,
                    letterSpacing: '-0.015em',
                    color: 'var(--cb-ink)',
                    maxWidth: '20ch',
                    overflowWrap: 'anywhere'
                  },
                  children: row.title || 'This course'
                }),
                jsxs('div', {
                  style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.45rem' },
                  children: [
                    jsx(CbStatePill, { state: section ? section.state : row.enrollment_status === 'active' ? 'introduced' : 'not_started' }),
                    row.recipe
                      ? jsx('span', {
                          style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
                          children: (RECIPE_COPY[row.recipe] || {}).title || row.recipe
                        })
                      : null,
                    row.warning ? jsx(WarningBadge, { warning: row.warning }) : null
                  ]
                }),
                jsx(HeroFacts, { facts: heroFacts, phone })
              ]
            }),
            jsxs('div', {
              'data-cb-hero-actions': '',
              style: {
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'stretch',
                gap: '0.45rem',
                flex: compactHero ? '1 1 100%' : '0 0 13rem',
                minWidth: 0
              },
              children: heroPlan.map((item) =>
                item.id === 'why'
                  ? jsxs(
                      'details',
                      {
                        'data-cb-why-next': '',
                        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                        children: [
                          jsx('summary', { style: { cursor: 'pointer' }, children: 'Why this is next' }),
                          jsx('p', { style: { margin: '0.35rem 0 0', lineHeight: 1.5 }, children: currentTitle })
                        ]
                      },
                      item.id
                    )
                  : jsx(
                      CbAction,
                      item.id === 'start'
                        ? {
                            variant: 'primary',
                            disabled: busy,
                            onClick: () => startLesson(nextKind === 'resume_lesson' && topCanResume ? 'resume' : 'fresh'),
                            children: busy ? 'Opening' : topCanResume ? 'Resume the lesson' : 'Start a fresh run'
                          }
                        : {
                            variant: item.variant,
                            'data-cb-textbook-entry': item.id === 'sections' ? 'back' : 'open',
                            onClick: () => {
                              setView('textbook')
                              setOpenSectionId(null)
                            },
                            children: item.label
                          },
                      item.id
                    )
              )
            })
          ]
        })
      }),

      // GM-010: a live Game band, one hairline strip, under the hero and above the surfaces.
      gameHeader,

      // H-174: when there is no approved page, the hero says who owns it and what the one next
      // action is. It sits between the hero and the surfaces so the reading column never opens on a
      // contradictory pair of buttons.
      heroReadable
        ? null
        : jsx(LessonReadinessPanel, {
            readiness: heroReadiness,
            compact: true,
            busy: readinessBusy,
            onOpenPlan: () => selectView('plan'),
            onCheckAgain: () => {
              page.reload()
              jobs.reload()
              outline.reload()
            },
            onRetryLessonsJob: retryLessonsJob
          }),

      jsx(NoticeLine, { notice, busy }),

      // Four primary surfaces, then one `More` disclosure for reference and administration. Every
      // surface stays one click away and every legacy view id still resolves, so a direct link
      // lands on the surface it names.
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: '0.15rem' },
        children: [
          jsx(LearningTabs, {
            options: primaryTabs,
            value: primaryActive,
            onChange: selectView,
            phone,
            ariaLabel: 'Course surfaces'
          }),
          jsxs('details', {
            'data-cb-more': moreActive ? 'active' : 'idle',
            open: moreOpen,
            onToggle: (event) => setMoreOpen(Boolean(event.currentTarget.open)),
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, color: 'var(--cb-ink-soft)' },
            children: [
              jsx('summary', {
                'data-cb-more-summary': '',
                style: { cursor: 'pointer', padding: '0.3rem 0', width: 'fit-content' },
                children: moreActive
                  ? `More · ${(moreTabs.find((option) => option.id === view) || { label: '' }).label}`
                  : 'More'
              }),
              jsx('div', {
                'data-cb-tier-two': view,
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.15rem 0.9rem', padding: '0.1rem 0 0.35rem' },
                children: moreTabs.map((option) =>
                  jsx(
                    sdk.Button,
                    {
                      variant: 'text',
                      size: 'sm',
                      'data-cb-tab': option.id,
                      'aria-current': option.id === view ? 'page' : undefined,
                      onClick: () => selectView(option.id),
                      children: option.label
                    },
                    option.id
                  )
                )
              })
            ]
          })
        ]
      }),

      moreActive
        ? jsx('div', {
            'data-cb-outside-route': view,
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: `You are reading ${((moreTabs.find((option) => option.id === view) || {}).label || viewLabel).toLowerCase()} from More. Overview, Learn, Notebook and Evidence stay one click away above.`
          })
        : null,
      // UI-K13: the queue itself, with the four scheduling actions `review.action` records. Due
      // rows are the `review.queue` read this banner counted; paused rows are derived from the
      // `evidence.inspect` read this page already holds, because a dropped objective is absent
      // from `review.queue` by construction. Rendered on Overview too, so the row controls are on
      // the page a learner lands on.
      ((review.data && review.data.total_overdue > 0) || pausedReview.length > 0) &&
      (view !== 'overview' || supports('review.action'))
        ? jsx(CheckPanelFrame, {
            kind: 'check',
            label: 'Review due',
            children: jsxs('div', {
              style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
              children: [
                jsxs('div', {
                  style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' },
                  children: [
                    jsx('span', {
                      style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' },
                      children: [
                        review.data && review.data.total_overdue > 0
                          ? `${review.data.total_overdue} ${review.data.total_overdue === 1 ? 'section is' : 'sections are'} due for review.`
                          : 'Nothing is due for review right now.',
                        pausedReview.length > 0
                          ? ` ${pausedReview.length} ${pausedReview.length === 1 ? 'section is' : 'sections are'} out of the queue.`
                          : ''
                      ].join('')
                    }),
                    review.data && review.data.total_overdue > 0 && view !== 'overview'
                      ? jsx(sdk.Button, {
                          variant: 'text',
                          size: 'sm',
                          onClick: () => selectView('overview'),
                          children: 'See what is due'
                        })
                      : null
                  ]
                }),
                supports('review.action')
                  ? jsx(ReviewDuePanel, {
                      enrollmentId: row.enrollment_id,
                      revision,
                      review: review.data,
                      evidence: evidence.data,
                      onRecorded: (nextRevision) => {
                        if (typeof nextRevision === 'number') setRevision(nextRevision)
                        review.reload()
                        evidence.reload()
                      },
                      onOpenSection: (objectiveId) => {
                        setView('textbook')
                        setOpenSectionId(objectiveId)
                      }
                    })
                  : null
              ]
            })
          })
        : null,
      body,
      // GM-010: the collectible section cards close the Game overview. They are earned from the
      // outline's own evidence, so they sit after the sections they describe, never before the
      // course's first action.
      gameJournal
    ]
  })
}

/**
 * A teaching turn that reached the chat but not the lesson page.
 *
 * `binding.get` answers `snapshot_failures = {recorded, last_at}` for the bound lesson run: the
 * count of teaching turns whose durable `lesson_segments` row could not be written after one
 * retry. This is an integrity notice, not a blocking error — the chat still holds the turn, so
 * there is no dialog, no disabled control and no retry (a retry writes a *new* turn, not the lost
 * one). The three states are kept distinct: a positive count names the loss, an explicit zero is
 * silent, and `null` is "unknown", never a zero.
 */
function SnapshotLossNotice({ failures }) {
  const recorded = failures && typeof failures === 'object' ? failures.recorded : undefined
  if (recorded === 0) return null
  const count = Number(recorded)
  if (Number.isFinite(count) && count > 0) {
    const lastAt = failures && failures.last_at
    return jsxs('div', {
      className: 'flex flex-col gap-1 border-l-2 border-(--ui-stroke-secondary) pl-3',
      role: 'status',
      'data-cb-snapshot-loss': 'recorded',
      'data-cb-snapshot-count': String(count),
      children: [
        jsx('div', {
          className: 'text-xs leading-relaxed',
          children: `${count} teaching ${count === 1 ? 'turn' : 'turns'} could not be saved to this lesson. The chat has them; this page does not.`
        }),
        lastAt
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: `Last recorded ${whenLabel(lastAt)}.`
            })
          : null
      ]
    })
  }
  return jsx('div', {
    className: 'border-l-2 border-(--ui-stroke-secondary) pl-3 text-xs leading-relaxed text-(--ui-text-secondary)',
    role: 'status',
    'data-cb-snapshot-loss': 'unknown',
    children: 'Coursebook could not check whether any teaching turn was lost.'
  })
}

/**
 * The bound lesson pane.
 *
 * Scope is the focused chat's stored session id → binding → enrollment. Nothing here falls back to
 * "the most recent lesson", and an unrelated chat gets an explicit entry action, never a stale
 * objective from another enrollment.
 */
function LessonPaneBody({ binding, storedId }) {
  const profile = binding.profile || currentScope().profile
  const library = useRpcQuery(
    'library.list',
    { filter: 'all', limit: 100 },
    `pane-library-${binding.enrollment_id}`,
    backendSupports('library.list')
  )
  const row =
    library.data && Array.isArray(library.data.items)
      ? library.data.items.find((item) => item.enrollment_id === binding.enrollment_id)
      : null
  // The chat is bound to ONE objective. Showing the enrollment's current objective instead would
  // make a chat bound to section 3 display section 1 (and section 1's detached run) as its lesson.
  const objectiveId =
    binding.objective_id || (row && row.evidence_summary ? row.evidence_summary.current_objective_id : null)
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: binding.enrollment_id, objective_id: objectiveId },
    `pane-page-${binding.enrollment_id}-${objectiveId}`,
    backendSupports('lesson.page') && Boolean(objectiveId)
  )
  const review = useRpcQuery(
    'review.queue',
    { enrollment_id: binding.enrollment_id, cap: 1, include_upcoming: false },
    `pane-review-${binding.enrollment_id}`,
    backendSupports('review.queue')
  )
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [overrideOpen, setOverrideOpen] = useState(false)

  const revision = page.data ? page.data.revision : row ? row.revision : 0
  const check = useOpenCheck({
    enrollmentId: binding.enrollment_id,
    objectiveId,
    revision,
    enabled: Boolean(objectiveId) && backendSupports('check.open') && Boolean(page.data),
    implemented: backendWire.implemented
  })

  const section = page.data && page.data.section
  const runtime = page.data && page.data.runtime
  const bindingStatus = (runtime && runtime.binding_status) || binding.status

  const resume = useCallback(async () => {
    const outcome = await resumeBoundSession(binding)
    if (!outcome.ok) {
      host.notify({ kind: 'warning', message: outcome.message })
      return
    }
    setNotice('Focused the bound lesson chat.')
  }, [binding])

  const freshRun = useCallback(async () => {
    if (!objectiveId) return
    setBusy(true)
    setNotice(null)
    const response = await rpc(
      'lesson.begin',
      { enrollment_id: binding.enrollment_id, objective_id: objectiveId, mode: 'fresh' },
      { idempotencyKey: `cb-pane-run-${objectiveId}-${newOperationId('run')}` }
    )
    setBusy(false)
    if (!response.ok) {
      setNotice(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    const outcome = response.result
    armPendingBind({
      enrollmentId: binding.enrollment_id,
      objectiveId,
      objectiveTitle: section ? section.title : null,
      lessonRunId: outcome.lesson_run_id,
      profile
    })
    const started = startLessonChat(profile)
    setNotice(
      started
        ? 'A new lesson run is ready. Its chat connects when you send your first message.'
        : 'This Desktop build cannot open a new chat; start one from the sidebar.'
    )
    page.reload()
    library.reload()
  }, [objectiveId, binding, profile, page, library])

  const abandon = useCallback(async () => {
    if (!runtime || !runtime.binding_id) return
    const response = await rpc('binding.abandon', {
      binding_id: runtime.binding_id,
      reason: 'Abandoned from the Coursebook pane.'
    })
    if (!response.ok) {
      setNotice(`${response.error.code}: ${describeError(response.error)}`)
      return
    }
    setNotice('Binding abandoned. Start a new governed run when you are ready.')
    page.reload()
  }, [runtime, page])

  if (library.status === 'error' && !library.data) {
    return jsx(sdk.PanelEmpty, {
      icon: 'warning',
      title: 'Cannot read this lesson',
      description: library.error ? `${library.error.code}: ${describeError(library.error)}` : 'The course list could not be read.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: library.reload, children: 'Try again' })
    })
  }
  if (!row) {
    return jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'Bound, but not listed',
      description:
        'This chat is connected to a course the library did not return. Nothing is guessed: reopen Coursebook to check it.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: () => host.navigate(ROUTE_PATH), children: 'Open Coursebook' })
    })
  }

  return jsxs('div', {
    className: 'flex flex-col gap-2',
    children: [
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsx('div', { className: 'min-w-0 break-words text-xs font-medium text-(--ui-text-secondary)', children: row.title }),
          section ? jsx('div', { className: 'text-sm font-medium leading-snug', children: section.title }) : null,
          jsxs('div', {
            className: 'flex flex-wrap items-center gap-1.5',
            children: [
              section ? jsx(StateText, { state: section.state }) : null,
              bindingStatus !== 'active'
                ? jsx(sdk.Badge, { size: 'xs', variant: 'warn', children: `binding ${bindingStatus}` })
                : null
            ]
          })
        ]
      }),

      jsx(SnapshotLossNotice, { failures: binding.snapshot_failures }),

      bindingStatus !== 'active'
        ? jsxs('div', {
            className: 'flex flex-col gap-1 border-l border-(--ui-stroke-secondary) pl-3',
            children: [
              jsx('div', {
                className: 'text-xs leading-relaxed text-(--ui-text-secondary)',
                children:
                  'This chat is not part of a lesson yet. Open Coursebook and start a lesson; the first message in its new chat connects it.'
              }),
              jsx(sdk.Button, {
                variant: 'secondary',
                size: 'sm',
                disabled: busy,
                onClick: () => host.navigate(ROUTE_PATH),
                children: 'Open Coursebook'
              })
            ]
          })
        : null,

      notice ? jsx('div', { className: 'text-xs text-(--ui-text-secondary)', children: notice }) : null,

      jsx(CbLabel, { children: 'Current check' }),
      page.status === 'error'
        ? jsx('div', {
            className: 'text-xs text-(--ui-text-secondary)',
            children: page.error ? `${page.error.code}: ${describeError(page.error)}` : 'The lesson page could not be read.'
          })
        : check.status === 'error'
          ? jsx('div', {
              className: 'text-xs text-(--ui-text-secondary)',
              children: check.error ? `${check.error.code}: ${describeError(check.error)}` : 'No check could be opened.'
            })
          : check.status === 'loading' && !check.check
            ? jsx(sdk.Loader, { label: 'Opening the current check' })
            : jsx(AttemptControls, {
                enrollmentId: binding.enrollment_id,
                objectiveId,
                check: check.check,
                revision,
                implemented: backendWire.implemented,
                bindingState: bindingStatus,
                parentLed: Boolean(row && row.recipe === 'parent'),
                stimulusStatus: check.stimulusStatus,
                stimulusError: check.stimulusError,
                onRetryStimulus: check.reload,
                onCommitted: () => {
                  page.reload()
                  library.reload()
                  review.reload()
                }
              }),

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-1.5 border-t border-(--ui-stroke-tertiary) pt-2',
        children: [
          jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: resume, children: 'Open lesson chat' }),
          jsx(sdk.Button, {
            variant: 'text',
            size: 'sm',
            onClick: async () => {
              const sent = await continueLesson(binding)
              setNotice(sent)
            },
            children: 'Continue lesson'
          }),
          jsx(sdk.Button, { variant: 'text', size: 'sm', onClick: () => host.navigate(ROUTE_PATH), children: 'Full course' })
        ]
      }),

      jsxs('div', {
        className: 'flex flex-wrap items-center gap-2 text-xs text-(--ui-text-secondary)',
        children: [
          jsx('span', {
            children: review.data
              ? review.data.total_overdue > 0
                ? `${review.data.total_overdue} due for review`
                : 'Nothing due'
              : 'Review is unavailable right now'
          }),
          jsx('span', { children: '·' }),
          jsx('span', { children: `${Number((row.evidence_summary || {}).independent || 0)} independent` }),
          jsx('span', { children: '·' }),
          jsx('span', { children: `${(page.data && page.data.sources ? page.data.sources.length : 0)} sources` })
        ]
      })
    ]
  })
}

/**
 * "Continue lesson" is a real user turn, not automation: the chat keeps teaching, and the backend
 * gate decides whether anything is graded. If no mounted composer owns the bound chat, the action
 * reports that instead of pretending a message was sent.
 */
async function continueLesson(binding) {
  if (!binding || !binding.stored_session_id) return 'This lesson has no durable chat to continue yet.'
  if (binding.status !== 'active') return 'This lesson is not connected to its chat right now. Open it from the course page first.'
  if (typeof host.openSession === 'function') {
    try {
      await host.openSession(binding.stored_session_id, { profile: binding.profile || undefined })
    } catch (error) {
      return `Opening the lesson chat failed: ${describeError(error)}`
    }
  }
  const composer = host.composer
  if (composer && typeof composer.submit === 'function') {
    const sent = composer.submit(binding.stored_session_id, 'Continue the lesson.')
    if (sent) return 'Asked the lesson chat to continue.'
    return 'The lesson chat is not on screen, so nothing was sent. Open it and continue there.'
  }
  return 'This Desktop build cannot send a message; open the lesson chat and continue there.'
}
