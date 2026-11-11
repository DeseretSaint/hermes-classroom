/**
 * The three destinations, named, with a selected state a colour-blind learner can still read:
 * weight and a lamp underline, plus `aria-current="page"`. It replaces a segmented control whose
 * active state was a fill only.
 */
function CbDestinationNav({ value, onChange, onHome }) {
  return jsx('nav', {
    'data-cb-destination-nav': '',
    'aria-label': 'Coursebook sections',
    className: 'flex flex-wrap items-center gap-x-4',
    children: DESTINATIONS.map((item) => {
      const current = item.id === value
      return jsx(
        'button',
        {
          type: 'button',
          'data-cb-nav-item': item.id,
          'aria-current': current ? 'page' : undefined,
          onClick: () => {
            // GM-002: on the course home the Home destination is still current (it is a step
            // inside Home). Pressing it returns to the library instead of doing nothing.
            if (current) {
              if (item.id === 'home' && onHome) onHome()
              return
            }
            onChange(item.id)
          },
          style: {
            background: 'none',
            border: 'none',
            borderRadius: 0,
            padding: '0.35rem 0',
            cursor: current ? 'default' : 'pointer',
            fontFamily: CB_SANS,
            fontSize: CB_TYPE.meta,
            fontWeight: current ? 600 : 400,
            color: current ? 'var(--cb-ink)' : 'var(--cb-ink-soft)',
            borderBottom: current ? '2px solid var(--cb-lamp)' : '2px solid transparent',
            minHeight: '32px'
          },
          children: item.label
        },
        item.id
      )
    })
  })
}

/**
 * Lesson-context pane. Registered globally, but scoped: it reads the focused chat's stored id
 * and asks the backend for that exact binding. It never shows a lesson from another chat and
 * never guesses one from recency.
 */
/* ── GM-012 · the lesson-bound tutor rail ─────────────────────────────────────
 *
 * The right pane is a tutor, not a chat and not the authoring agent
 * (`docs/GAME-MODE-AND-TUTOR-RAIL-PLAN.md` §7). It is bound to the focused lesson chat's
 * `enrollment_id` / `objective_id` / `lesson_run_id`, it answers through `tutor.ask` with a
 * bounded lesson context, and it owns no tools. Three rules are load-bearing and visible here:
 *
 *   - one thread per lesson run: the thread is read from `tutor.history` for that run, never
 *     from "the newest chat";
 *   - a selection is deliberate: the reading column arms a quote into this rail, the learner
 *     still presses Ask, and nothing is sent by selecting, clicking or dragging;
 *   - practice is a mode of the rail, and only the learner's turns are graded
 *     (`coursebook/conversation.py` reads learner rows only; the rail labels which turns those
 *     are instead of implying the tutor's prose is marked).
 *
 * A failure is a named state, never an empty thread or a fabricated answer.
 */

const TUTOR_MODES = Object.freeze([
  { id: 'ask', label: 'Ask' },
  { id: 'practice', label: 'Practice' }
])
const TUTOR_ASK_PLACEHOLDER = 'Ask about this lesson…'
const TUTOR_MAX_QUOTE = 600
const TUTOR_SHEET_BREAKPOINT = 520
const TUTOR_HINT_QUESTION = 'Give me a hint for this check. Do not give the answer.'

/**
 * The selected excerpt is module state, not a callback chain.
 *
 * The route's reading column and the contributed pane are two React roots of the same module
 * instance, so a small broadcast store is the honest seam: the pill arms an excerpt, the pane
 * subscribes, and nothing about the lesson route is re-rendered by a chat.
 */
const tutorQuoteListeners = new Set()
let pendingTutorQuote = null
const tutorFocusListeners = new Set()
let tutorFocusTick = 0

function cbTutorQuoteText(value) {
  const text = String(value == null ? '' : value).replace(/\s+/g, ' ').trim()
  return text.length > TUTOR_MAX_QUOTE ? text.slice(0, TUTOR_MAX_QUOTE) : text
}

function armTutorQuote(quote) {
  const text = cbTutorQuoteText(quote && quote.text)
  if (!text) return null
  pendingTutorQuote = {
    text,
    blockId: (quote && quote.blockId) || null,
    courseId: (quote && quote.courseId) || null,
    objectiveId: (quote && quote.objectiveId) || null,
    source: (quote && quote.source) || 'selection',
    armedAt: Date.now()
  }
  tutorQuoteListeners.forEach((listener) => listener(pendingTutorQuote))
  revealCoursebookPane()
  return pendingTutorQuote
}

function clearTutorQuote() {
  pendingTutorQuote = null
  tutorQuoteListeners.forEach((listener) => listener(null))
}

function useTutorQuote() {
  const [quote, setQuote] = useState(pendingTutorQuote)
  useEffect(() => {
    const listener = (next) => setQuote(next)
    tutorQuoteListeners.add(listener)
    if (pendingTutorQuote) listener(pendingTutorQuote)
    return () => {
      tutorQuoteListeners.delete(listener)
    }
  }, [])
  return quote
}

function requestTutorFocus() {
  tutorFocusTick += 1
  tutorFocusListeners.forEach((listener) => listener(tutorFocusTick))
}

function useTutorFocusTick() {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const listener = (value) => setTick(value)
    tutorFocusListeners.add(listener)
    return () => {
      tutorFocusListeners.delete(listener)
    }
  }, [])
  return tick
}

/** The one shape `tutor.ask` accepts. No question means no request, whatever is selected. */
function tutorAskPayload({ courseId, enrollmentId, objectiveId, lessonRunId, question, quote, mode }) {
  const text = String(question == null ? '' : question).trim()
  if (!courseId || !enrollmentId || !objectiveId || !lessonRunId) return null
  if (!text) return null
  const selected = cbTutorQuoteText(quote && quote.text)
  return {
    course_id: courseId,
    enrollment_id: enrollmentId,
    objective_id: objectiveId,
    lesson_run_id: lessonRunId,
    question: text,
    block_id: selected && quote && quote.blockId ? quote.blockId : null,
    selected_text: selected || null,
    mode: mode === 'practice' ? 'practice' : 'ask'
  }
}

/** The served document by block id. Nothing outside this index can be cited. */
function cbTutorBlockIndex(page) {
  const blocks = (page && page.document && page.document.blocks) || []
  const index = {}
  for (const block of blocks) {
    if (block && block.id) index[block.id] = block
  }
  return index
}

/** Authored glossary entries only. A term without a gloss is not a glossary card. */
function cbTutorGlossary(page) {
  const document = page && page.document ? page.document : {}
  const raw = Array.isArray(document.glossary)
    ? document.glossary
    : Array.isArray(page && page.glossary)
      ? page.glossary
      : []
  const entries = []
  const seen = new Set()
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const term = String(item.term || '').trim()
    const gloss = String(item.gloss || '').trim()
    if (!term || !gloss) continue
    const key = term.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    entries.push({
      term,
      gloss,
      reading: item.reading ? String(item.reading) : null,
      pronunciation: item.pronunciation ? String(item.pronunciation) : null,
      blockId: item.block_id || null
    })
    if (entries.length >= 24) break
  }
  return entries
}

/** Only citations that resolve to a served block or source. A bad id is omitted, never invented. */
function cbTutorCitations(turn, blockIndex, sourceIndex) {
  const raw = (turn && Array.isArray(turn.citations) && turn.citations) || []
  const resolved = []
  const seen = new Set()
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const id = String(item.id || '').trim()
    if (!id) continue
    let kind = item.kind === 'source' ? 'source' : item.kind === 'block' ? 'block' : null
    if (!kind) kind = (blockIndex && blockIndex[id]) ? 'block' : (sourceIndex && sourceIndex[id]) ? 'source' : null
    if (kind === 'block' && !(blockIndex && blockIndex[id])) continue
    if (kind === 'source' && !(sourceIndex && sourceIndex[id])) continue
    if (!kind) continue
    const key = `${kind}:${id}`
    if (seen.has(key)) continue
    seen.add(key)
    const fallback = kind === 'block'
      ? (blockIndex[id].headline || blockIndex[id].role || id)
      : (sourceIndex[id].title || id)
    resolved.push({ kind, id, label: String(item.label || fallback) })
  }
  return resolved
}

/** History turns, normalized. A malformed row is omitted rather than printed as an answer. */
function cbTutorTurns(payload) {
  const raw = payload && Array.isArray(payload.turns) ? payload.turns : []
  const turns = []
  for (const turn of raw) {
    if (!turn || typeof turn !== 'object') continue
    if (turn.role !== 'learner' && turn.role !== 'tutor') continue
    const text = String(turn.text || '').trim()
    if (!text) continue
    turns.push({
      id: turn.id || null,
      ordinal: Number(turn.ordinal) || turns.length + 1,
      role: turn.role,
      text,
      block_id: turn.block_id || null,
      selected_text: turn.selected_text || null,
      citations: Array.isArray(turn.citations) ? turn.citations : [],
      state: turn.state || null
    })
  }
  return turns
}

/** The count the grader uses: learner rows only. Tutor prose is never counted, never graded. */
function cbTutorLearnerTurnCount(transcript) {
  return (Array.isArray(transcript) ? transcript : []).filter((turn) => turn && turn.speaker === 'learner').length
}

/** The rail is a side column on a wide surface and a bottom sheet on a phone-width one. */
function tutorRailLayout(width) {
  const value = Number(width)
  if (!Number.isFinite(value) || value <= 0) return 'sheet'
  return value < TUTOR_SHEET_BREAKPOINT ? 'sheet' : 'side'
}

function cbTutorPracticeDeclaration(check) {
  const practice = check && check.stimulus ? check.stimulus.practice : null
  return practice && typeof practice === 'object' ? practice : null
}

/** Hint copy: the policy label the backend declared, never a fabricated hint. */
function cbTutorHintAvailable(check) {
  const stimulus = check && check.stimulus ? check.stimulus : null
  if (!stimulus) return false
  const policy = stimulus.assistance_policy && typeof stimulus.assistance_policy === 'object'
    ? stimulus.assistance_policy
    : {}
  const hint = policy.hint
  if (hint === 'available') return true
  if (hint === 'after_attempt') return Number(check.attempt_count || 0) > 0
  return false
}

/** One tutor or learner turn in the rail's notebook margin. */
function TutorTurn({ turn, blockIndex, sourceIndex, onCitation }) {
  const learner = turn.role === 'learner'
  const citations = cbTutorCitations(turn, blockIndex, sourceIndex)
  const withheld = turn.state === 'answer_withheld'
  return jsxs('article', {
    'data-cb-tutor-turn': turn.role,
    'data-cb-tutor-turn-ordinal': String(turn.ordinal),
    'data-cb-tutor-graded': learner && !withheld ? 'true' : 'false',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
      paddingLeft: learner ? '0.55rem' : 0,
      borderLeft: learner ? '2px solid var(--cb-rule)' : 'none',
      minWidth: 0
    },
    children: [
      jsx('div', {
        style: {
          fontFamily: CB_SANS,
          fontSize: CB_TYPE.caption,
          fontWeight: 600,
          letterSpacing: '0.01em',
          color: 'var(--cb-ink-soft)'
        },
        children: learner ? 'You' : 'Tutor'
      }),
      learner && turn.selected_text
        ? jsx('div', {
            'data-cb-tutor-turn-quote': turn.block_id || '',
            style: {
              margin: 0,
              paddingLeft: '0.45rem',
              borderLeft: '2px solid var(--cb-accent)',
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.meta,
              lineHeight: 1.5,
              color: 'var(--cb-ink-soft)'
            },
            children: turn.selected_text
          })
        : null,
      learner
        ? jsx('p', {
            style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)', overflowWrap: 'anywhere' },
            children: turn.text
          })
        : jsx(ProseText, {
            style: { maxWidth: '100%', fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.6, color: 'var(--cb-ink)' },
            text: turn.text
          }),
      withheld
        ? jsx('span', {
            'data-cb-tutor-answer': 'withheld',
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
            children: 'The answer stays hidden while the check is open.'
          })
        : null,
      citations.length
        ? jsxs('div', {
            'data-cb-tutor-citations': String(citations.length),
            style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.3rem 0.6rem', paddingTop: '0.1rem' },
            children: [
              jsx('span', {
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' },
                children: citations.length === 1 ? 'Cited from' : 'Cited from'
              }),
              ...citations.map((citation) =>
                jsxs('button', {
                  type: 'button',
                  'data-cb-tutor-citation': citation.kind,
                  'data-cb-tutor-citation-target': citation.id,
                  'aria-label': `Go to ${citation.label}`,
                  onClick: () => onCitation && onCitation(citation),
                  style: {
                    display: 'inline-flex',
                    alignItems: 'center',
                    minHeight: '24px',
                    padding: '0.05rem 0.4rem',
                    border: '1px solid var(--cb-rule)',
                    borderRadius: '2px',
                    background: 'var(--cb-paper)',
                    color: 'var(--cb-ink)',
                    fontFamily: CB_SANS,
                    fontSize: CB_TYPE.caption,
                    fontWeight: 600,
                    lineHeight: 1.35,
                    textAlign: 'left',
                    cursor: 'pointer',
                    overflowWrap: 'anywhere'
                  },
                  children: citation.kind === 'source' ? `Source · ${citation.label}` : citation.label
                }, `${turn.ordinal}-${citation.kind}-${citation.id}`)
              )
            ]
          })
        : null
    ]
  }, turn.id || `${turn.role}-${turn.ordinal}`)
}

/** The authored glossary, as real buttons — no arbitrary prose is a target. */
function TutorGlossary({ entries, onAskTerm, onAddTermQuote }) {
  const [openTerm, setOpenTerm] = useState(null)
  if (!entries || entries.length === 0) return null
  const current = openTerm ? entries.find((entry) => entry.term === openTerm) : null
  return jsxs('section', {
    'data-cb-tutor-glossary': String(entries.length),
    'aria-label': 'Glossary',
    style: { display: 'flex', flexDirection: 'column', gap: '0.3rem' },
    children: [
      jsx('div', {
        style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, letterSpacing: '0.01em', color: 'var(--cb-ink-soft)' },
        children: 'Glossary'
      }),
      jsx('div', {
        style: { display: 'flex', flexWrap: 'wrap', gap: '0.25rem 0.55rem' },
        children: entries.map((entry) =>
          jsx('button', {
            type: 'button',
            'data-cb-tutor-term': entry.term,
            'aria-expanded': openTerm === entry.term ? 'true' : 'false',
            'aria-label': `Glossary: ${entry.term}`,
            onClick: () => setOpenTerm(openTerm === entry.term ? null : entry.term),
            style: {
              minHeight: '24px',
              padding: 0,
              border: 'none',
              background: 'transparent',
              color: 'var(--cb-ink)',
              fontFamily: CB_SERIF,
              fontSize: CB_TYPE.meta,
              lineHeight: 1.5,
              textDecoration: 'underline',
              textDecorationStyle: 'dotted',
              textDecorationColor: 'var(--cb-accent)',
              textUnderlineOffset: '3px',
              cursor: 'pointer'
            },
            children: entry.term
          }, `term-${entry.term}`)
        )
      }),
      current
        ? jsxs('div', {
            'data-cb-tutor-term-card': current.term,
            role: 'group',
            'aria-label': `${current.term} glossary entry`,
            style: {
              display: 'flex',
              flexDirection: 'column',
              gap: '0.2rem',
              padding: '0.45rem 0.55rem',
              border: '1px solid var(--cb-rule)',
              borderLeft: '2px solid var(--cb-lamp)',
              background: 'var(--cb-paper-raised)',
              borderRadius: 0
            },
            children: [
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '0.35rem' },
                children: [
                  jsx('span', { style: { fontFamily: CB_SERIF, fontSize: CB_TYPE.body, fontWeight: 600, color: 'var(--cb-ink)' }, children: current.term }),
                  current.reading
                    ? jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: current.reading })
                    : null,
                  current.pronunciation
                    ? jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: current.pronunciation })
                    : null
                ]
              }),
              jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' }, children: current.gloss }),
              jsxs('div', {
                style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem', paddingTop: '0.15rem' },
                children: [
                  jsx(CbAction, {
                    variant: 'tertiary',
                    'data-cb-tutor-term-ask': current.term,
                    onClick: () => (onAskTerm ? onAskTerm(current) : onAddTermQuote && onAddTermQuote(current)),
                    children: 'Ask more'
                  }),
                  onAddTermQuote
                    ? jsx(CbAction, {
                        variant: 'tertiary',
                        'data-cb-tutor-term-quote': current.term,
                        onClick: () => onAddTermQuote(current),
                        children: 'Use in a question'
                      })
                    : null
                ]
              })
            ]
          })
        : null
    ]
  })
}

/**
 * The rail itself. Presentational by design: the pane owns the reads and the writes, so every
 * state (loading, unavailable, provider failure, changed lesson, practice) can be rendered and
 * tested without a backend.
 */
function TutorRail({
  state = 'ready',
  width = 0,
  courseTitle = '',
  sectionTitle = '',
  objectiveTitle = '',
  contextChip = '',
  turns = [],
  blockIndex = {},
  sourceIndex = {},
  glossary = [],
  checkOpen = false,
  hint = null,
  mode = 'ask',
  quote = null,
  draft = '',
  busy = false,
  notice = null,
  detached = false,
  practice = null,
  practiceAvailable = false,
  practiceSurface = null,
  practiceError = null,
  onModeChange,
  onDraftChange,
  onSend,
  onRemoveQuote,
  onCitation,
  onHint,
  onTermQuote,
  onRetry,
  onStartPractice,
  onEndPractice,
  onOpenSection,
  onOpenCoursebook
}) {
  const layout = tutorRailLayout(width)
  const sheet = layout === 'sheet'
  const declaration = practice && practice.declaration ? practice.declaration : null
  const transcript = practice && Array.isArray(practice.transcript) ? practice.transcript : []
  const practiceState = practice && practice.state ? practice.state : 'none'
  const modeOptions = TUTOR_MODES.filter((option) => option.id === 'ask' || practiceAvailable)
  const busyLabel = mode === 'practice' ? 'Sending…' : 'Thinking…'
  const line = sheet ? CB_TYPE.meta : CB_TYPE.caption
  const muted = { fontFamily: CB_SANS, fontSize: line, lineHeight: 1.5, color: 'var(--cb-ink-soft)' }

  const statusBanner = (label, action) =>
    jsxs('div', {
      role: 'status',
      'data-cb-tutor-notice': label,
      style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', padding: '0.45rem 0.55rem', border: '1px solid var(--cb-rule)', borderLeft: '2px solid var(--cb-coral)', background: 'var(--cb-paper-raised)', borderRadius: 0 },
      children: [
        jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink)' }, children: label }),
        action || null
      ]
    })

  let body
  if (state === 'no-lesson') {
    body = jsxs('div', {
      'data-cb-tutor-body': 'no-lesson',
      style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
      children: [
        jsx(sdk.EmptyState, {
          title: 'Open a lesson to ask the tutor.',
          description: 'The tutor answers about the section you are reading, with the lesson’s own words and sources.'
        }),
        jsx(CbAction, {
          variant: 'secondary',
          'data-cb-tutor-open-coursebook': '',
          onClick: onOpenCoursebook,
          children: 'Open Coursebook'
        })
      ]
    })
  } else if (state === 'loading') {
    body = jsxs('div', {
      'data-cb-tutor-body': 'loading',
      style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
      children: [
        jsx(sdk.Loader, { label: 'Reading this lesson…' }),
        jsx('span', { style: muted, children: 'The composer stays closed until the lesson context is here.' })
      ]
    })
  } else if (state === 'unavailable') {
    body = jsxs('div', {
      'data-cb-tutor-body': 'unavailable',
      style: { display: 'flex', flexDirection: 'column', gap: '0.45rem' },
      children: [
        statusBanner('The tutor is unavailable. The lesson is still readable.', null),
        onRetry
          ? jsx(CbAction, { variant: 'secondary', 'data-cb-tutor-retry': '', onClick: onRetry, children: 'Retry' })
          : null
      ]
    })
  } else if (state === 'provider-failure') {
    body = jsxs('div', {
      'data-cb-tutor-body': 'provider-failure',
      style: { display: 'flex', flexDirection: 'column', gap: '0.45rem' },
      children: [
        statusBanner('The tutor could not answer. Nothing was graded.', null),
        onRetry
          ? jsx(CbAction, { variant: 'secondary', 'data-cb-tutor-retry': '', onClick: onRetry, children: 'Retry' })
          : null
      ]
    })
  } else if (state === 'lesson-changed') {
    body = jsxs('div', {
      'data-cb-tutor-body': 'lesson-changed',
      style: { display: 'flex', flexDirection: 'column', gap: '0.45rem' },
      children: [
        statusBanner('This thread belongs to the previous section.', null),
        jsx('span', { style: muted, children: 'The lesson moved on. This thread is kept with the run it was written in.' }),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', gap: '0.4rem' },
          children: [
            onRetry ? jsx(CbAction, { variant: 'secondary', 'data-cb-tutor-read-old': '', onClick: onRetry, children: 'Read these turns' }) : null,
            onOpenSection ? jsx(CbAction, { variant: 'tertiary', onClick: onOpenSection, children: 'Open the section' }) : null
          ]
        })
      ]
    })
  } else {
    const thread = jsx('div', {
      'data-cb-tutor-thread': String(turns.length),
      role: 'log',
      'aria-live': 'polite',
      'aria-label': 'Tutor thread',
      style: { display: 'flex', flexDirection: 'column', gap: '0.7rem', minWidth: 0 },
      children: turns.length
        ? turns.map((turn) => jsx(TutorTurn, { turn, blockIndex, sourceIndex, onCitation }, turn.id || `${turn.role}-${turn.ordinal}`))
        : jsx('p', {
            style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink-soft)' },
            children: 'Ask about a word, a step or the check. The answer cites the lesson it came from.'
          })
    })
    const composer = jsxs('div', {
      'data-cb-tutor-composer': mode,
      style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', paddingTop: sheet ? '0.5rem' : '0.35rem', borderTop: '1px solid var(--cb-rule)' },
      children: [
        quote
          ? jsxs('div', {
              'data-cb-tutor-quote': quote.blockId || 'text',
              style: { display: 'flex', alignItems: 'flex-start', gap: '0.4rem', paddingLeft: '0.45rem', borderLeft: '2px solid var(--cb-accent)', minWidth: 0 },
              children: [
                jsx('span', {
                  'data-cb-tutor-quote-text': '',
                  style: { flex: '1 1 auto', minWidth: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.meta, lineHeight: 1.5, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
                  children: quote.text
                }),
                jsx('button', {
                  type: 'button',
                  'data-cb-tutor-quote-remove': '',
                  'aria-label': 'Remove the selected excerpt',
                  onClick: onRemoveQuote,
                  style: {
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '24px',
                    height: '24px',
                    flex: '0 0 auto',
                    padding: 0,
                    border: '1px solid var(--cb-rule)',
                    borderRadius: '2px',
                    background: 'var(--cb-paper)',
                    color: 'var(--cb-ink)',
                    cursor: 'pointer'
                  },
                  children: jsx(sdk.Codicon, { name: 'close', size: CB_ICON_UI })
                })
              ]
            })
          : null,
        jsx('label', {
          htmlFor: 'cb-tutor-input',
          style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink-soft)' },
          children: mode === 'practice' ? 'Your turn in the practice' : 'Your question'
        }),
        jsx(sdk.Textarea, {
          id: 'cb-tutor-input',
          'data-cb-tutor-input': '',
          'aria-describedby': 'cb-tutor-input-help',
          value: draft,
          rows: sheet ? 2 : 3,
          placeholder: mode === 'practice' ? 'Answer in the practice scene…' : TUTOR_ASK_PLACEHOLDER,
          onChange: (event) => onDraftChange && onDraftChange(event && event.target ? event.target.value : ''),
          onKeyDown: (event) => {
            if (!event || event.key !== 'Enter' || event.shiftKey) return
            event.preventDefault()
            if (!busy && String(draft || '').trim()) onSend && onSend()
          }
        }),
        jsx('p', {
          id: 'cb-tutor-input-help',
          style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
          children: mode === 'practice'
            ? 'Only your turns are graded. The tutor stays in the scene and never marks you.'
            : 'The tutor answers about this lesson only. Enter sends; Shift+Enter starts a new line.'
        }),
        jsxs('div', {
          style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.4rem' },
          children: [
            hint
              ? hint.used
                ? jsx('span', {
                    'data-cb-tutor-assist': 'hinted',
                    role: 'status',
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink-soft)' },
                    children: 'Hint recorded — this answer is marked hinted'
                  })
                : jsx(CbAction, {
                    variant: 'tertiary',
                    'data-cb-tutor-hint': hint.available ? 'available' : 'unavailable',
                    disabled: !hint.available || busy,
                    onClick: onHint,
                    children: 'Ask for a hint'
                  })
              : null,
            jsx(CbAction, {
              variant: 'primary',
              'data-cb-tutor-send': mode,
              disabled: Boolean(busy) || !String(draft || '').trim(),
              pending: Boolean(busy),
              onClick: onSend,
              children: busy ? busyLabel : mode === 'practice' ? 'Say it' : 'Ask'
            }),
            mode === 'practice' && practiceState === 'active'
              ? jsx(CbAction, {
                  variant: 'secondary',
                  'data-cb-tutor-practice-end': '',
                  disabled: Boolean(busy),
                  onClick: onEndPractice,
                  children: 'End practice'
                })
              : null
          ]
        })
      ]
    })

    let modeBody
    if (mode === 'practice') {
      if (!practiceAvailable) {
        modeBody = jsxs('div', {
          'data-cb-tutor-practice': 'unavailable',
          style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
          children: [
            jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' }, children: 'Practice is not available in this build. You can still ask about the lesson.' }),
            jsx(CbAction, { variant: 'secondary', 'data-cb-tutor-mode-back': '', onClick: () => onModeChange && onModeChange('ask'), children: 'Back to Ask' })
          ]
        })
      } else if (practiceError) {
        modeBody = jsxs('div', {
          'data-cb-tutor-practice': 'error',
          style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
          children: [
            statusBanner('Practice could not be read. Nothing was graded.', null),
            onRetry ? jsx(CbAction, { variant: 'secondary', onClick: onRetry, children: 'Retry' }) : null
          ]
        })
      } else if (practiceState === 'none') {
        modeBody = jsxs('div', {
          'data-cb-tutor-practice': 'ready',
          style: { display: 'flex', flexDirection: 'column', gap: '0.4rem' },
          children: [
            declaration && declaration.scenario
              ? jsx('p', { style: { margin: 0, fontFamily: CB_SERIF, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)' }, children: declaration.scenario })
              : null,
            declaration && (declaration.tutor_role || declaration.learner_role)
              ? jsx('p', {
                  style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.5, color: 'var(--cb-ink-soft)' },
                  children: `You are the ${declaration.learner_role || 'learner'}; the tutor is the ${declaration.tutor_role || 'other speaker'}.`
                })
              : null,
            jsx(CbAction, { variant: 'primary', 'data-cb-tutor-practice-start': '', disabled: Boolean(busy), onClick: onStartPractice, children: 'Start practice' }),
            jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' }, children: 'Only your turns are graded, after you end the practice.' })
          ]
        })
      } else {
        const graded = Boolean(practice && practice.verdict)
        modeBody = jsxs('div', {
          'data-cb-tutor-practice': practiceState,
          'data-cb-tutor-practice-graded': graded ? 'true' : 'false',
          style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
          children: [
            jsx('div', {
              'data-cb-tutor-practice-transcript': String(transcript.length),
              role: 'log',
              'aria-label': 'Practice transcript',
              style: { display: 'flex', flexDirection: 'column', gap: '0.5rem' },
              children: transcript.map((turn) =>
                jsxs('article', {
                  'data-cb-tutor-turn': turn.speaker === 'learner' ? 'learner' : 'tutor',
                  'data-cb-tutor-graded': turn.speaker === 'learner' ? 'true' : 'false',
                  style: { display: 'flex', flexDirection: 'column', gap: '0.15rem', paddingLeft: turn.speaker === 'learner' ? '0.55rem' : 0, borderLeft: turn.speaker === 'learner' ? '2px solid var(--cb-rule)' : 'none' },
                  children: [
                    jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, fontWeight: 600, color: 'var(--cb-ink-soft)' }, children: turn.speaker === 'learner' ? 'You · graded' : 'Tutor · not graded' }),
                    jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.meta, lineHeight: 1.55, color: 'var(--cb-ink)', overflowWrap: 'anywhere' }, children: turn.text })
                  ]
                }, `practice-${turn.ordinal}`)
              )
            }),
            practice && practice.remaining !== undefined
              ? jsx('p', { style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)' }, children: `${plural(Number(practice.remaining) || 0, 'turn', 'turns')} left before you can end.` })
              : null,
            graded
              ? jsxs('div', {
                  'data-cb-tutor-verdict': practice.verdict,
                  style: { display: 'flex', flexDirection: 'column', gap: '0.3rem', padding: '0.45rem 0.55rem', border: '1px solid var(--cb-rule)', borderLeft: '2px solid var(--cb-lamp)', background: 'var(--cb-paper-raised)', borderRadius: 0 },
                  children: [
                    jsx('span', { style: { fontFamily: CB_SANS, fontSize: CB_TYPE.meta, fontWeight: 600, color: 'var(--cb-ink)' }, children: practice.feedback || 'The practice was graded.' }),
                    jsx('span', { style: muted, children: 'Only your turns were read. Review grading has the stored result.' }),
                    jsx(CbAction, { variant: 'tertiary', 'data-cb-tutor-mode-back': '', onClick: () => onModeChange && onModeChange('ask'), children: 'Back to Ask' })
                  ]
                })
              : null
          ]
        })
      }
      body = practiceSurface
        ? jsx('div', {
            'data-cb-tutor-body': 'practice',
            'data-cb-tutor-practice-surface': practiceState,
            style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
            children: practiceSurface
          })
        : jsxs('div', {
            'data-cb-tutor-body': 'practice',
            style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
            children: [modeBody, practiceState === 'active' ? composer : null]
          })
    } else {
      body = jsxs('div', {
        'data-cb-tutor-body': 'ask',
        style: { display: 'flex', flexDirection: 'column', gap: '0.6rem' },
        children: [
          jsx(TutorGlossary, { entries: glossary, onTermQuote }),
          thread,
          notice ? jsx('div', { role: 'status', 'data-cb-tutor-notice': '', style: muted, children: notice }) : null,
          checkOpen
            ? jsx('p', {
                'data-cb-tutor-check-open': '',
                style: { margin: 0, fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                children: 'A check is open. The tutor helps you work it out; it does not show the answer or record a verdict.'
              })
            : null,
          composer
        ]
      })
    }
  }

  return jsxs('aside', {
    'data-cb-tutor-rail': layout,
    'data-cb-tutor-state': state,
    'data-cb-tutor-mode': mode,
    'aria-label': 'Lesson tutor',
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '0.55rem',
      minWidth: 0,
      width: '100%',
      ...(sheet
        ? { paddingTop: '0.6rem', borderTop: '1px solid var(--cb-rule)' }
        : { maxWidth: '24rem' })
    },
    children: [
      jsxs('header', {
        'data-cb-tutor-header': '',
        style: { display: 'flex', flexDirection: 'column', gap: '0.2rem', paddingBottom: '0.4rem', borderBottom: '1px solid var(--cb-rule)', minWidth: 0 },
        children: [
          jsxs('div', {
            style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.5rem', minWidth: 0 },
            children: [
              jsx('h2', {
                style: { margin: 0, fontFamily: CB_SERIF, fontSize: sheet ? CB_TYPE.lead : CB_TYPE.body, fontWeight: 600, lineHeight: 1.2, color: 'var(--cb-ink)' },
                children: 'Tutor'
              }),
              contextChip
                ? jsx('span', {
                    'data-cb-tutor-context': contextChip,
                    style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, color: 'var(--cb-ink-soft)', textAlign: 'right' },
                    children: contextChip
                  })
                : null
            ]
          }),
          jsx('div', {
            'data-cb-tutor-lesson': '',
            style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)', overflowWrap: 'anywhere' },
            children: [courseTitle, objectiveTitle || sectionTitle].filter(Boolean).join(' · ') || 'This lesson'
          }),
          detached
            ? jsx('div', {
                'data-cb-tutor-detached': '',
                role: 'status',
                style: { fontFamily: CB_SANS, fontSize: CB_TYPE.caption, lineHeight: 1.45, color: 'var(--cb-ink-soft)' },
                children: 'This lesson’s chat is disconnected. You can still ask about the section; the thread stays with its run.'
              })
            : null
        ]
      }),
      modeOptions.length > 1
        ? jsx(LearningTabs, {
            options: modeOptions,
            value: mode,
            onChange: (next) => onModeChange && onModeChange(next),
            phone: sheet,
            ariaLabel: 'Tutor mode'
          })
        : null,
      body
    ]
  })
}

/**
 * The selection pill: it appears only after a completed selection inside the lesson's reading
 * column, and pressing it arms a quote. It never sends, never opens a chat and never fires on a
 * single click or a drag that selected nothing.
 */
function TutorSelectionPill({ context }) {
  const [pill, setPill] = useState(null)
  const contextRef = useRef(context)
  contextRef.current = context
  useEffect(() => {
    if (typeof document === 'undefined' || typeof window === 'undefined') return undefined
    const read = () => {
      const selection = typeof window.getSelection === 'function' ? window.getSelection() : null
      if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
        setPill(null)
        return
      }
      const text = cbTutorQuoteText(selection.toString())
      if (text.length < 2) {
        setPill(null)
        return
      }
      const range = selection.getRangeAt(0)
      let node = range.commonAncestorContainer
      if (node && node.nodeType !== 1) node = node.parentElement
      const block = node && node.closest ? node.closest('[data-cb-block]') : null
      if (!block) {
        setPill(null)
        return
      }
      const rect = range.getBoundingClientRect()
      setPill({
        text,
        blockId: block.getAttribute('data-cb-block') || null,
        x: rect.left + rect.width / 2,
        y: rect.top
      })
    }
    const arm = () => {
      const current = contextRef.current || {}
      if (!pill) return
      armTutorQuote({
        text: pill.text,
        blockId: pill.blockId,
        courseId: current.courseId || null,
        objectiveId: current.objectiveId || null,
        source: 'selection'
      })
      requestTutorFocus()
      setPill(null)
    }
    const onPointerUp = () => window.setTimeout(read, 0)
    const onKeyUp = (event) => {
      if (event.key === 'Escape') {
        setPill(null)
        return
      }
      if (event.key === 'E' && (event.ctrlKey || event.metaKey) && event.shiftKey) {
        // Ctrl/Cmd+Shift+E opens the current selection as a quote without a pointer.
        read()
        return
      }
      if (event.shiftKey) read()
    }
    const onPointerDown = (event) => {
      const target = event && event.target
      if (target && target.closest && target.closest('[data-cb-tutor-pill]')) return
      setPill(null)
    }
    document.addEventListener('pointerup', onPointerUp)
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keyup', onKeyUp)
    return () => {
      document.removeEventListener('pointerup', onPointerUp)
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keyup', onKeyUp)
    }
  }, [pill])
  if (!pill) return null
  return jsx('button', {
    type: 'button',
    'data-cb-tutor-pill': pill.blockId || 'text',
    'aria-label': `Ask the tutor about “${pill.text.slice(0, 60)}”`,
    onMouseDown: (event) => event.preventDefault(),
    onClick: () => {
      const current = context || {}
      armTutorQuote({
        text: pill.text,
        blockId: pill.blockId,
        courseId: current.courseId || null,
        objectiveId: current.objectiveId || null,
        source: 'selection'
      })
      requestTutorFocus()
      setPill(null)
    },
    style: {
      position: 'fixed',
      zIndex: 60,
      left: `${Math.max(8, Math.round(pill.x))}px`,
      top: `${Math.max(8, Math.round(pill.y - 40))}px`,
      transform: 'translateX(-50%)',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.3rem',
      minHeight: '28px',
      padding: '0.2rem 0.6rem',
      border: '1px solid var(--cb-ink)',
      borderRadius: '2px',
      background: 'var(--cb-paper-raised)',
      color: 'var(--cb-ink)',
      fontFamily: CB_SANS,
      fontSize: CB_TYPE.caption,
      fontWeight: 600,
      cursor: 'pointer'
    },
    children: 'Ask tutor'
  })
}

/**
 * The pane's data half. One rail, one thread per lesson run, and one explicit write per press.
 */
function TutorRailPane({ binding }) {
  const profile = binding.profile || currentScope().profile
  const library = useRpcQuery(
    'library.list',
    { filter: 'all', limit: 100 },
    `tutor-library-${binding.enrollment_id}`,
    backendSupports('library.list')
  )
  const row =
    library.data && Array.isArray(library.data.items)
      ? library.data.items.find((item) => item.enrollment_id === binding.enrollment_id)
      : null
  const objectiveId = binding.objective_id || (row && row.evidence_summary ? row.evidence_summary.current_objective_id : null)
  const courseId = row ? row.course_id : null
  const runId = binding.lesson_run_id || null
  const page = useRpcQuery(
    'lesson.page',
    { enrollment_id: binding.enrollment_id, objective_id: objectiveId },
    `tutor-page-${binding.enrollment_id}-${objectiveId}`,
    backendSupports('lesson.page') && Boolean(objectiveId)
  )
  const history = useRpcQuery(
    'tutor.history',
    {
      course_id: courseId,
      enrollment_id: binding.enrollment_id,
      objective_id: objectiveId,
      lesson_run_id: runId
    },
    `tutor-history-${binding.enrollment_id}-${objectiveId}-${runId}`,
    backendSupports('tutor.history') && Boolean(courseId && objectiveId && runId)
  )
  const revision = page.data ? page.data.revision : row ? row.revision : 0
  const check = useOpenCheck({
    enrollmentId: binding.enrollment_id,
    objectiveId,
    revision,
    enabled: Boolean(objectiveId) && backendSupports('check.open') && Boolean(page.data),
    implemented: backendWire.implemented
  })
  const practiceRead = useRpcQuery(
    'practice.state',
    { enrollment_id: binding.enrollment_id, objective_id: objectiveId },
    `tutor-practice-${binding.enrollment_id}-${objectiveId}`,
    backendSupports('practice.state') && Boolean(objectiveId)
  )

  const quote = useTutorQuote()
  const focusTick = useTutorFocusTick()
  const [mode, setMode] = useState('ask')
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [failure, setFailure] = useState(null)
  const [localTurns, setLocalTurns] = useState([])
  const [fenced, setFenced] = useState(0)
  const [hintUsed, setHintUsed] = useState(false)
  const [width, setWidth] = useState(0)
  const rootRef = useRef(null)
  const endNonce = useRef(null)
  const autoPractice = useRef(false)

  // The pane is not the route: measure the rail itself, so a 460 px window and a 1049 px window
  // with a chat beside it both choose the sheet/side layout from the space the rail really has.
  useEffect(() => {
    if (typeof window === 'undefined' || typeof document === 'undefined') return undefined
    const node = rootRef.current
    if (!node) return undefined
    const read = () => {
      const rect = node.getBoundingClientRect()
      if (rect && rect.width > 0) setWidth(Math.round(rect.width))
    }
    read()
    let observer = null
    if (typeof ResizeObserver === 'function') {
      observer = new ResizeObserver(read)
      observer.observe(node)
    }
    return () => {
      if (observer) observer.disconnect()
    }
  }, [])

  const adoptRevision = useCallback((value) => {
    const next = Number(value)
    if (Number.isFinite(next) && next > 0) setFenced((current) => Math.max(current, next))
  }, [])
  useEffect(() => {
    adoptRevision(revision)
  }, [revision, adoptRevision])
  useEffect(() => {
    adoptRevision(history.data && history.data.revision)
  }, [history.data, adoptRevision])

  useEffect(() => {
    if (!focusTick) return
    if (typeof document === 'undefined') return
    const node = document.getElementById('cb-tutor-input')
    if (node && typeof node.focus === 'function') node.focus()
  }, [focusTick])

  useEffect(() => {
    // A history read replaces the optimistic turns it now contains; it never concatenates twice.
    if (history.status === 'ready') setLocalTurns([])
  }, [history.status, history.data])

  const blockIndex = cbTutorBlockIndex(page.data)
  const sourceIndex = {}
  for (const source of (page.data && page.data.sources) || []) {
    if (source && source.source_id) sourceIndex[source.source_id] = source
  }
  const glossary = cbTutorGlossary(page.data)
  const historyTurns = cbTutorTurns(history.data)
  const turns = historyTurns.concat(localTurns)
  const declaration = cbTutorPracticeDeclaration(check.check)
  const practiceSession = practiceRead.data && practiceRead.data.state !== 'none' ? practiceRead.data : null
  const practiceTranscript = (practiceSession && practiceSession.transcript) || (practiceRead.data && practiceRead.data.transcript) || []
  const practiceVerdict = practiceSession ? practiceSession.verdict : null
  const practiceFeedbackLine = practiceFeedback({
    verdict: practiceVerdict,
    criteria: (practiceSession && practiceSession.criteria) || [],
    learnerTurns: cbTutorLearnerTurnCount(practiceTranscript),
    targets: (declaration && declaration.targets) || []
  })

  const section = page.data && page.data.section
  const runtime = page.data && page.data.runtime
  const objectiveTitle = section ? section.title : (history.data && history.data.context ? history.data.context.objective_title : null)
  const contextChip = section && section.ordinal ? `Section ${section.ordinal}` : objectiveId ? 'This section' : ''
  const lessonChanged = Boolean(
    runtime && runtime.lesson_run_id && runId && String(runtime.lesson_run_id) !== String(runId)
  )
  const hintAvailable = Boolean(check.check) && cbTutorHintAvailable(check.check) && backendSupports('lesson.assist')
  const practiceAvailable = Boolean(
    declaration &&
    backendSupports('practice.state') &&
    backendSupports('practice.start') &&
    backendSupports('practice.end')
  )

  // The ask path needs a bound run: that is the only place `no-lesson` belongs.
  const askState =
    !objectiveId || !runId
      ? 'no-lesson'
      : lessonChanged && !localTurns.length
        ? 'lesson-changed'
        : library.status === 'error' && !library.data
          ? 'unavailable'
          : (library.status === 'loading' && !row) || (page.status === 'loading' && !page.data) || (history.status === 'loading' && !history.data)
            ? 'loading'
            : 'ready'
  const practiceState = practiceRead.status === 'loading' && !practiceRead.data ? 'loading' : 'ready'
  // Practice is keyed by (enrollment_id, objective_id) and needs no lesson run, so `no-lesson` is
  // an ask-path state only. A bound lesson with an open practice check still renders the practice
  // in the rail even when this chat carries no run id.
  const practiceHere = mode === 'practice' && practiceAvailable && Boolean(objectiveId)
  const railState =
    failure === 'provider'
      ? 'provider-failure'
      : failure === 'unavailable'
        ? 'unavailable'
        : practiceHere
          ? practiceState
          : askState

  const fence = Math.max(Number(fenced) || 0, Number(revision) || 0, Number(row && row.revision) || 0)

  /**
   * One explicit ask. The only callers are a press (Ask, Say it, or the Hint action); a selection,
   * a quote chip or a glossary card prepares this payload and never invokes it.
   */
  const performAsk = useCallback(
    async (payload) => {
      setBusy(true)
      setNotice(null)
      setFailure(null)
      const response = await rpc('tutor.ask', payload, {
        idempotencyKey: newOperationId(`tutor-${payload.mode}`),
        expectedRevision: fence
      })
      setBusy(false)
      if (!response.ok) {
        const code = response.error && response.error.code
        setFailure(code === 'HOST_UNAVAILABLE' ? 'unavailable' : 'provider')
        setNotice(response.error ? `${code || 'ERROR'}: ${describeError(response.error)}` : null)
        return false
      }
      adoptRevision(response.revision)
      const result = response.result || {}
      if (result.state === 'provider_failure') {
        setFailure('provider')
        return false
      }
      const learnerTurn = {
        id: `local-learner-${Date.now()}`,
        ordinal: turns.length + 1,
        role: 'learner',
        text: payload.question,
        block_id: payload.block_id,
        selected_text: payload.selected_text,
        citations: [],
        state: null
      }
      const tutorTurn = result.turn
        ? {
            ...result.turn,
            ordinal: turns.length + 2,
            state: result.state || null,
            citations: Array.isArray(result.citations) && result.citations.length ? result.citations : result.turn.citations
          }
        : null
      setLocalTurns((current) => (tutorTurn ? current.concat([learnerTurn, tutorTurn]) : current.concat([learnerTurn])))
      setDraft('')
      clearTutorQuote()
      if (result.state === 'answer_withheld') {
        setNotice('The answer stays hidden while the check is open. The hint path is the way forward.')
      }
      if (payload.mode === 'practice') practiceRead.reload()
      else history.reload()
      return true
    },
    [fence, adoptRevision, turns.length, practiceRead, history]
  )

  const send = useCallback(async () => {
    const payload = tutorAskPayload({
      courseId,
      enrollmentId: binding.enrollment_id,
      objectiveId,
      lessonRunId: runId,
      question: draft,
      quote,
      mode
    })
    if (!payload || busy) return
    if (quote && quote.blockId && !blockIndex[quote.blockId]) {
      setNotice('That excerpt belongs to another section. Select it again in this one.')
      return
    }
    await performAsk(payload)
  }, [courseId, binding.enrollment_id, objectiveId, runId, draft, quote, mode, busy, blockIndex, performAsk])

  const askHint = useCallback(async () => {
    if (!hintAvailable || busy || hintUsed) return
    setBusy(true)
    setNotice(null)
    const recorded = await rpc(
      'lesson.assist',
      { enrollment_id: binding.enrollment_id, objective_id: objectiveId, kind: 'hint_request' },
      { idempotencyKey: newOperationId('tutor-hint'), expectedRevision: fence }
    )
    if (!recorded.ok) {
      setBusy(false)
      setNotice(recorded.error ? `${recorded.error.code}: ${describeError(recorded.error)}` : 'The hint could not be recorded.')
      return
    }
    adoptRevision((recorded.result && recorded.result.revision) || recorded.revision)
    setHintUsed(true)
    const payload = tutorAskPayload({
      courseId,
      enrollmentId: binding.enrollment_id,
      objectiveId,
      lessonRunId: runId,
      question: TUTOR_HINT_QUESTION,
      quote: null,
      mode: 'ask'
    })
    if (!payload) {
      setBusy(false)
      return
    }
    setBusy(true)
    setNotice('Hint recorded. This answer is marked hinted; the check still owns the verdict.')
    await performAsk(payload)
  }, [
    hintAvailable,
    busy,
    hintUsed,
    binding.enrollment_id,
    objectiveId,
    courseId,
    runId,
    fence,
    adoptRevision,
    performAsk
  ])

  const startPractice = useCallback(async () => {
    if (!practiceAvailable || busy) return
    setBusy(true)
    setNotice(null)
    const response = await rpc(
      'practice.start',
      { enrollment_id: binding.enrollment_id, objective_id: objectiveId },
      { idempotencyKey: newOperationId('tutor-practice-start'), expectedRevision: fence }
    )
    setBusy(false)
    if (!response.ok) {
      setNotice(response.error ? `${response.error.code}: ${describeError(response.error)}` : 'The practice could not start.')
      return
    }
    adoptRevision((response.result && response.result.revision) || response.revision)
    endNonce.current = null
    practiceRead.reload()
  }, [practiceAvailable, busy, binding.enrollment_id, objectiveId, fence, adoptRevision, practiceRead])

  const endPractice = useCallback(async () => {
    if (busy) return
    const session = practiceRead.data
    const checkId = (session && session.check_id) || (check.check && check.check.check_id)
    const checkVersion = (session && session.check_version) || (check.check && check.check.check_version)
    if (!checkId || !checkVersion) {
      setNotice('The practice check could not be named, so nothing was graded.')
      return
    }
    if (!endNonce.current) endNonce.current = newOperationId('tutor-practice-end')
    setBusy(true)
    setNotice(null)
    const response = await rpc(
      'practice.end',
      {
        enrollment_id: binding.enrollment_id,
        check_id: checkId,
        check_version: Number(checkVersion),
        attempt_nonce: endNonce.current
      },
      { idempotencyKey: `tutor-end-${endNonce.current}`, expectedRevision: fence }
    )
    setBusy(false)
    if (!response.ok) {
      setNotice(practiceRefusalCopy(response.error) || (response.error ? describeError(response.error) : 'The practice could not be ended.'))
      return
    }
    adoptRevision(response.revision)
    endNonce.current = null
    practiceRead.reload()
    history.reload()
    page.reload()
    check.reload()
  }, [
    busy,
    practiceRead,
    check.check,
    binding.enrollment_id,
    fence,
    adoptRevision,
    history,
    page,
    check
  ])

  const openCitation = useCallback(
    (citation) => {
      if (!citation) return
      if (citation.kind === 'source') {
        requestIntent({ kind: 'lesson-block', row, objectiveId, blockId: null })
        return
      }
      requestIntent({ kind: 'lesson-block', row, objectiveId, blockId: citation.id })
    },
    [row, objectiveId]
  )

  const addTermQuote = useCallback(
    (entry) => {
      if (!entry) return
      armTutorQuote({
        text: entry.term,
        blockId: entry.blockId || null,
        courseId,
        objectiveId,
        source: 'glossary'
      })
      requestTutorFocus()
    },
    [courseId, objectiveId]
  )

  const retry = useCallback(() => {
    setFailure(null)
    setNotice(null)
    library.reload()
    page.reload()
    history.reload()
    practiceRead.reload()
    check.reload()
  }, [library, page, history, practiceRead, check])

  const modeChange = useCallback(
    (next) => {
      if (next !== 'ask' && next !== 'practice') return
      if (next === 'practice' && !practiceAvailable) return
      // A learner who has already chosen a mode owns the rail. Arming the auto-open guard here is
      // what keeps a practice check that lands after this click from moving them: the effect below
      // opens practice once, and only for a learner who has not chosen.
      autoPractice.current = true
      setMode(next)
      setFailure(null)
      setNotice(null)
    },
    [practiceAvailable]
  )

  // A conversation-practice check on a bound lesson that has no lesson run. The rail's Ask mode
  // needs a run to hold a thread, and the practice commands are keyed by (enrollment_id,
  // objective_id) and need none, so the practice is both reachable and the useful opening mode.
  const practiceCheck =
    check.check && cbTutorPracticeDeclaration(check.check) ? check.check : null
  const runBound = Boolean(runId)
  useEffect(() => {
    if (autoPractice.current) return
    if (runBound || !practiceCheck || !practiceAvailable || !objectiveId) return
    autoPractice.current = true
    setMode('practice')
  }, [runBound, practiceCheck, practiceAvailable, objectiveId])
  // With no run there is no rail thread to write practice turns into: the learner's turns are
  // written by the bound chat, so the pane shows the shipped PracticeSurface (the same surface the
  // lesson check has always used) instead of a second practice implementation.
  const practiceSurface =
    practiceCheck && !runBound
      ? jsx(PracticeSurface, {
          enrollmentId: binding.enrollment_id,
          objectiveId,
          check: practiceCheck,
          revision: fence,
          implemented: backendWire.implemented,
          bindingState: binding.status || 'active',
          onCommitted: retry
        })
      : null
  // Once the learner picks a mode, the rail never moves them again: the auto-open above fires once.
  const rail = jsx(TutorRail, {
    state: railState,
    width,
    courseTitle: (page.data && page.data.course && page.data.course.title) || (row && row.title) || '',
    sectionTitle: section ? section.title : '',
    objectiveTitle,
    contextChip,
    turns,
    blockIndex,
    sourceIndex,
    glossary,
    checkOpen: Boolean(check.check),
    hint: hintAvailable || hintUsed ? { available: hintAvailable && !hintUsed, used: hintUsed } : null,
    mode,
    quote,
    draft,
    busy,
    notice,
    detached: Boolean(binding.status && binding.status !== 'active'),
    practice:
      mode === 'practice'
        ? {
            declaration,
            state: practiceRead.status === 'error' ? 'none' : (practiceSession && practiceSession.state) || 'none',
            transcript: practiceSession ? practiceTranscript : [],
            remaining: practiceSession ? practiceSession.remaining : null,
            verdict: practiceVerdict,
            criteria: (practiceSession && practiceSession.criteria) || [],
            feedback: practiceFeedbackLine
          }
        : null,
    practiceAvailable,
    practiceSurface,
    practiceError: mode === 'practice' && practiceRead.status === 'error' ? practiceRead.error : null,
    onModeChange: modeChange,
    onDraftChange: setDraft,
    onSend: send,
    onRemoveQuote: clearTutorQuote,
    onCitation: openCitation,
    onHint: askHint,
    onTermQuote: addTermQuote,
    onRetry: retry,
    onStartPractice: startPractice,
    onEndPractice: endPractice,
    onOpenSection: () => requestIntent({ kind: 'lesson-block', row, objectiveId, blockId: null }),
    onOpenCoursebook: () => host.navigate(ROUTE_PATH)
  })

  return jsx('div', {
    ref: rootRef,
    'data-cb-tutor-pane': binding.enrollment_id,
    'data-cb-tutor-run': runId || '',
    'data-cb-tutor-objective': objectiveId || '',
    style: { display: 'flex', flexDirection: 'column', gap: '0.35rem', minWidth: 0 },
    children: rail
  })
}

function CoursebookPane() {
  const { state, storedId, reload } = useSessionBinding()
  // The pane is part of the same scoped surface as the route: same token table, same mode, and
  // the same H-147 appearance/motion settings the learner chose on Home.
  const [panePrefs] = useCbHomePrefs()
  const hostMode = useCbMode()
  const cbMode = cbAppliedMode(hostMode, panePrefs.appearance)
  const systemReduced = useCbReducedMedia()
  const cbMotion = panePrefs.reducedMotion === 'reduce' || systemReduced ? cbMotionFor('reduced') : cbMotionFor('full')
  useEffect(() => {
    publishCbMotion(cbMotion)
  }, [cbMotion.reduced])
  const scopeProfile = currentScope().profile
  const routingUnavailable = profileRouteState.status === 'unavailable'
  const [bindNote, setBindNote] = useState(null)
  const attemptedBind = useRef(null)
  // Which bundled learner skill this chat's next turn loads. Read from the backend's own rule
  // (`GET /sessions/skill` -> coursebook.lesson_skills), the same function the pre_llm_call hook
  // calls, so the note cannot describe a different skill than the turn loads.
  const [skillNote, setSkillNote] = useState(null)

  useEffect(() => {
    if (!storedId) {
      setSkillNote(null)
      return undefined
    }
    let cancelled = false
    rest(`/sessions/skill?session_id=${encodeURIComponent(storedId)}`)
      .then((answer) => {
        if (cancelled) return
        setSkillNote(answer && answer.skill ? answer : null)
      })
      .catch(() => {
        if (!cancelled) setSkillNote(null)
      })
    return () => {
      cancelled = true
    }
  }, [storedId, state.status, state.binding])

  useEffect(() => {
    // A run this Desktop opened is armed. Bind it to the focused chat once that chat has a
    // durable id and no binding of its own — by the exact stored id, never the runtime id and
    // never "the newest chat". One attempt per stored id; the seam decides legality.
    if (!storedId || attemptedBind.current === storedId) return undefined
    if (state.status !== 'ready' || state.binding) return undefined
    if (!pendingBindFor(scopeProfile)) return undefined
    let cancelled = false
    attemptedBind.current = storedId
    bindPendingChat(storedId, scopeProfile).then((response) => {
      if (cancelled || !response) return
      if (response.ok) {
        setBindNote('This lesson is bound to this chat.')
        reload()
      } else {
        setBindNote(`${response.code}: ${response.message || 'this chat could not be bound.'}`)
      }
    })
    return () => {
      cancelled = true
    }
  }, [storedId, state.status, state.binding, scopeProfile, reload])

  const openCoursebook = useCallback(() => {
    host.navigate(ROUTE_PATH)
  }, [])

  const resume = useCallback(async () => {
    const outcome = await resumeBoundSession(state.binding)
    if (!outcome.ok) {
      host.notify({ kind: 'warning', message: outcome.message })
      return
    }
  }, [state.binding])

  let body
  const armedRun = pendingBindFor(scopeProfile)
  if (armedRun && (state.status === 'no-session' || state.status === 'idle')) {
    // H-64: a fresh run this Desktop just started is armed to this exact chat. A blank "no durable
    // chat yet" panel here is where the old Start lesson dead end ended up; this state names the
    // run, the objective and the one action that turns this chat into a lesson.
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: armedRun.objectiveTitle ? `Lesson run ready: ${armedRun.objectiveTitle}` : 'Lesson run ready',
      description:
        'This chat belongs to that lesson. Send the first message and Coursebook connects it to the run; ' +
        'the section stays open beside it with the teaching, the sources and the check.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open the section' })
    })
  } else if (state.status === 'no-session' || state.status === 'idle') {
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'No lesson chat open',
      description:
        'A lesson runs in a chat. Open Coursebook, pick a course and start a run; the teaching stays beside the chat once it begins.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
    })
  } else if (state.status === 'loading') {
    body = jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this chat’s binding' }) })
  } else if (state.status === 'unavailable') {
    const code = state.error && state.error.code
    body =
      code === 'NOT_IMPLEMENTED'
        ? jsx(sdk.PanelEmpty, {
            icon: 'book',
            title: 'Lessons arrive with the learning kernel',
            description:
              'The backend is connected and answering, but this build has no kernel schema, so no ' +
              'session binding can exist yet. Nothing here is being guessed.',
            action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          })
        : jsx(sdk.PanelEmpty, {
            icon: 'warning',
            title: 'Cannot read this chat’s binding',
            description: code ? `${code}: ${describeError(state.error)}` : describeError(state.error),
            action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
          })
  } else if (state.binding && storedId && state.binding.stored_session_id && state.binding.stored_session_id !== storedId) {
    // a binding for a chat that is no longer on screen is never rendered as this chat's lesson
    body = jsx('div', { className: 'py-6', children: jsx(sdk.Loader, { label: 'Reading this chat’s binding' }) })
  } else if (!state.binding) {
    // GM-012: the rail is a tutor, not a chat probe. A chat with no lesson is not an error and is
    // never told it is "not a Coursebook lesson"; it points at the one door that starts one.
    body = jsx(sdk.PanelEmpty, {
      icon: 'book',
      title: 'Open a lesson to ask the tutor.',
      description:
        'The tutor answers about the section you are reading, with the lesson’s own words and sources. ' +
        'Open Coursebook, pick a section, and its chat brings the rail here.',
      action: jsx(sdk.Button, { variant: 'secondary', size: 'sm', onClick: openCoursebook, children: 'Open Coursebook' })
    })
  } else {
    body = jsx(TutorRailPane, { binding: state.binding })
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col px-3 py-2',
    'data-cb-stored-id': storedId || '',
    'data-cb-binding-id': (state.binding && state.binding.binding_id) || '',
    'data-cb-scope': cbMode,
    'data-cb-motion': cbMotion.preference,
    style: { ...cbScopeStyle(cbMode), ...cbHostVars(panePrefs.appearance) },
    children: [
      jsx(CbLabel, { children: 'Coursebook' }),
      routingUnavailable
        ? jsx('div', {
            className: 'pb-2 text-xs text-(--ui-text-secondary)',
            role: 'status',
            'data-cb-routing': 'unavailable',
            children:
              'Routing unavailable: Coursebook could not read this window’s profile routes, so ' +
              'requests go without a connection id. Reopen the pane or restart Desktop; on a ' +
              'single-connection install nothing is lost.'
          })
        : null,
      bindNote ? jsx('div', { className: 'pb-2 text-xs text-(--ui-text-secondary)', children: bindNote }) : null,
      skillNote
        ? jsx('div', {
            className: 'pb-2 text-xs text-(--ui-text-secondary)',
            'data-cb-skill': skillNote.skill,
            'data-cb-skill-reason': skillNote.reason || '',
            children:
              skillNote.reason === 'lesson_binding'
                ? `Tutor skill: ${skillNote.skill} — loads on this chat's next message.`
                : `Coach skill: ${skillNote.skill} — no live lesson run for this chat.`
          })
        : null,
      body
    ]
  })
}

/**
 * Reactive read of a host atom. The host's own `useValue` did not re-render this pane when the
 * focused chat changed (the pane stayed pinned to the binding of the chat it first mounted with,
 * so a bound lesson could outlive its chat), so subscribe directly and keep the value in local
 * state. Falls back to the host hook when the atom exposes no subscription.
 */
function useHostValue(atom) {
  const read = useCallback(() => (atom && typeof atom.get === 'function' ? atom.get() : atom), [atom])
  const [value, setValue] = useState(read)
  useEffect(() => {
    setValue(read())
    if (!atom) return undefined
    if (typeof atom.subscribe === 'function') return atom.subscribe((next) => setValue(next))
    if (typeof atom.listen === 'function') return atom.listen((next) => setValue(next))
    if (typeof sdk.useValue === 'function') return undefined
    return undefined
  }, [atom, read])
  return value
}

/**
 * The focused chat's binding, read by its STORED id only.
 *
 * Four honest states: no durable chat yet, loading, could-not-ask, and answered (bound or not).
 * `runtimeId` is returned for diagnostics; it is never sent to `binding.get`.
 */
function useSessionBinding() {
  const storedId = useHostValue(host.state.focusedStoredSessionId)
  const runtimeId = useHostValue(host.state.focusedSessionId)
  const [state, setState] = useState({ status: 'idle', binding: null, error: null })
  const [ticket, setTicket] = useState(0)
  const reload = useCallback(() => setTicket((value) => value + 1), [])

  useEffect(() => {
    if (!storedId) {
      setState({ status: 'no-session', binding: null, error: null })
      return undefined
    }
    let cancelled = false
    setState({ status: 'loading', binding: null, error: null })
    loadBinding({ storedSessionId: storedId })
      .then((response) => {
        if (cancelled) return
        if (response && response.ok) {
          setState({ status: 'ready', binding: response.result.binding, error: null })
        } else {
          setState({ status: 'unavailable', binding: null, error: (response && response.error) || null })
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: 'unavailable',
            binding: null,
            error: { code: 'HOST_UNAVAILABLE', message: describeError(error) }
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [storedId, ticket])

  return { storedId, runtimeId, state, reload }
}

function ContractList() {
  const [state, setState] = useState({ status: 'loading', contracts: [], error: null })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const response = await fetchSchema()
        if (cancelled) return
        if (response && response.ok) {
          setState({ status: 'ready', contracts: response.result.contracts, error: null })
        } else {
          setState({ status: 'unavailable', contracts: [], error: response && response.error })
        }
      } catch (error) {
        if (!cancelled) setState({ status: 'unavailable', contracts: [], error })
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (state.status === 'loading') return jsx(sdk.Loader, { label: 'Reading the contract inventory' })
  if (state.status === 'unavailable') {
    return jsx('div', {
      className: 'text-xs text-(--ui-text-secondary)',
      children: `Contract inventory unavailable. ${describeError(state.error)}`
    })
  }
  return jsx('div', {
    className: 'flex flex-col',
    children: state.contracts.map((entry) =>
      jsx(
        StatusRow,
        {
          label: entry.id,
          value: `v${entry.version}`,
          detail: `${entry.file} · ${String(entry.sha256).slice(7, 19)}…`
        },
        entry.id
      )
    )
  })
}

function SessionDiagnostics() {
  const runtimeId = useHostValue(host.state.focusedSessionId)
  const storedId = useHostValue(host.state.focusedStoredSessionId)
  const scope = currentScope()
  const implemented = backendWire.implemented ? Array.from(backendWire.implemented).sort() : null
  return jsxs('div', {
    className: 'flex flex-col',
    children: [
      jsx(StatusRow, {
        label: 'Runtime session id',
        value: runtimeId ? `${String(runtimeId).slice(0, 12)}…` : 'none',
        detail: 'Live gateway id. Valid for this turn only; never sent to binding.get.'
      }),
      jsx(StatusRow, {
        label: 'Stored session id',
        value: storedId ? `${String(storedId).slice(0, 12)}…` : 'none',
        detail: storedId
          ? 'Durable id used for bindings and for opening a lesson chat.'
          : 'A fresh chat has none until its first turn. Nothing falls back to the runtime id.'
      }),
      jsx(StatusRow, {
        label: 'Scope',
        value: scope.profile || 'unknown profile',
        detail: scope.connectionId ? `connection ${scope.connectionId}` : 'local source'
      }),
      jsx(StatusRow, {
        label: 'Wire contract',
        value: `cb.rpc v${backendWire.contractVersion}`,
        detail: implemented
          ? `${plural(implemented.length, 'implemented command', 'implemented commands')}: ${implemented.join(', ')}`
          : 'Backend method registry unavailable; commands are attempted, not assumed.'
      })
    ]
  })
}

function CoursebookSettings() {
  return jsxs('div', {
    className: 'flex flex-col gap-3',
    children: [
      jsx('div', {
        className: 'text-xs text-(--ui-text-secondary)',
        children:
          'Preferences appear here only when the code that reads them ships. The inventory below is ' +
          'read-only and shows the exact contracts this backend speaks.'
      }),
      jsx(CbLabel, { children: 'Session binding' }),
      jsx(SessionDiagnostics, {}),
      jsx(CbLabel, { children: 'Contracts' }),
      jsx(ContractList, {})
    ]
  })
}

// Named seam for tests/test_desktop_lesson_views.py and tests/test_desktop_field_quest.py. The
// block views, the section page and the quest projection are pure components/functions over a
// server-owned document, so a Node test can render them without a backend, a chat or a window.
export {
  TutorRail,
  TutorRailPane,
  TutorSelectionPill,
  TutorGlossary,
  TutorTurn,
  tutorAskPayload,
  cbTutorBlockIndex,
  cbTutorGlossary,
  cbTutorCitations,
  cbTutorTurns,
  cbTutorLearnerTurnCount,
  cbTutorPracticeDeclaration,
  cbTutorHintAvailable,
  cbTutorQuoteText,
  tutorRailLayout,
  armTutorQuote,
  clearTutorQuote,
  AttemptControls,
  TakeHomeStudio,
  TakeHomeShelf,
  TakeHomeSourcePanel,
  TakeHomeProof,
  TakeHomePackPanel,
  TakeThisWithYou,
  HomeworkSheetCard,
  HomeworkRecord,
  HomeworkRecordList,
  HomeworkStudio,
  CB_HOMEWORK_STATE_WORD,
  CB_HOMEWORK_KIND_WORD,
  CB_HOMEWORK_FORBIDDEN,
  GameHeader,
  GameJournal,
  CB_GAME_ACTION_WORD,
  CB_GAME_PROGRESS_NOTE,
  cbGameCourse,
  cbGameFeedbackVisible,
  cbGameSectionCards,
  cbHasJapanese,
  cbHomeworkIndexRows,
  cbHomeworkRefTaskId,
  cbHomeworkSourceRef,
  cbHomeworkExcerpt,
  cbHomeworkFilename,
  cbHomeworkSheetGuard,
  cbPrintHomeworkSheet,
  cbDownloadHomeworkSheet,
  StudioEntranceTabs,
  CB_STUDIO_ENTRANCES,
  CB_TAKEHOME_KINDS,
  cbTakeHomeSourceRows,
  cbTakeHomeProofPages,
  cbTakeHomePageOrder,
  cbTakeHomeKindWord,
  cbTakeHomeModeWord,
  AttemptVerdict,
  WorldStudio,
  CourseWorldHero,
  ModeSwitchDialog,
  ModeBadge,
  WorldPlate,
  useWorldRead,
  cbWorldPlate,
  cbWorldSectionPlates,
  cbWorldApproved,
  cbWorldMissingRoles,
  createModeCard,
  CB_WORLD_COPY,
  CB_WORLD_STATE_WORD,
  CB_GRAMMAR_NAME,
  StudioExportPanel,
  StudioFineTunePanel,
  StudioPlanView,
  StudioReviewDiff,
  fineTuneChip,
  fineTuneCriteriaText,
  fineTuneScopeLine,
  PracticeSurface,
  practiceFeedback,
  useOpenCheck,
  CbAction,
  CB_MOTION,
  CB_MOTION_BEATS,
  CB_MOTION_CEILING_MS,
  cbMotionFor,
  cbSettleFrame,
  useCbSettle,
  useCbSettled,
  BackendUnavailable,
  CB_HOME_PREF_DEFAULTS,
  CB_PRESENTATION_LABEL,
  CB_PRESENTATION_OPTIONS,
  CB_PRESENTATION_VIEW,
  CbSettingsSection,
  HomeDefaultsLine,
  HomeSettingsSheet,
  sanitizeCbHomePrefs,
  readCbHomePrefs,
  updateCbHomePrefs,
  resetCbHomePrefsSection,
  cbEffectiveMode,
  cbAppliedMode,
  cbHostVars,
  cbPlayCheckCue,
  CB_TOKENS,
  CB_TOKEN_NAMES,
  CB_TYPE,
  CB_TYPE_STEPS,
  COURSE_SCOPES,
  CREATE_RESULT_COPY,
  CB_USE_OPTIONS,
  scopeSectionBand,
  scopeFacts,
  CbShapeTrail,
  FieldDesk,
  deskEstimateState,
  CreateCourseFlow,
  createStartStep,
  suggestedTitle,
  effectiveDepth,
  SCOPE_MIN_DEPTH,
  LessonPlayer,
  PlayerVerdict,
  PlayerClose,
  EvidenceChip,
  evidenceChipView,
  EVIDENCE_CHIP_LABEL,
  EVIDENCE_CHIP_SENTENCE,
  choiceAnswer,
  playerSteps,
  playerCheckCount,
  playerConcept,
  FIRST_RUN_COPY,
  FirstRun,
  GOAL_EXAMPLES,
  GOAL_PLACEHOLDER,
  GoalGallery,
  LIBRARY_COPY,
  TITLE_PLACEHOLDER,
  EvidenceClassText,
  EvidenceView,
  EVIDENCE_TARGET_OPTIONS,
  RECIPE_COPY,
  courseToolsVisible,
  dialLabel,
  enrollmentStatusLabel,
  FieldRail,
  FieldDeskHome,
  CoursebookHome,
  HomeScene,
  CB_HOME_SCENE,
  cbShelfEdgeMask,
  HomeLibraryPanel,
  HomeCourseCard,
  readCoursePresentationMode,
  FieldNotesStrip,
  DeskFacts,
  FieldQuestView,
  LESSON_VIEWS,
  LEARNING_VIEWS,
  SELF_REPORTED_CONFIRM_COPY,
  SELF_REPORTED_EVIDENCE_COPY,
  StudioLanding,
  SYLLABUS_ACCEPT,
  SYLLABUS_COPY,
  SYLLABUS_LIMITS,
  SYLLABUS_MIME_HINTS,
  ALIGNMENT_STATE_COPY,
  SyllabusAlignmentReview,
  SyllabusAlignmentPanel,
  SyllabusAnchorPanel,
  SyllabusEntry,
  SyllabusIntakeFlow,
  SyllabusParseReview,
  SyllabusValue,
  queueSyllabusAlignment,
  startCompanionCourse,
  syllabusAlignmentView,
  syllabusAlignPayload,
  syllabusAnchorLabel,
  syllabusAssessmentRows,
  syllabusCourseFields,
  syllabusCoursePayload,
  syllabusFormatFor,
  syllabusIntakePayload,
  syllabusItemView,
  syllabusParseView,
  syllabusPlanGate,
  syllabusPlanBrief,
  syllabusReviewPayload,
  syllabusScopeProposal,
  syllabusStaleNotice,
  LearnerPlanView,
  LessonDocumentView,
  lessonReadiness,
  LessonReadinessPanel,
  lessonHeroPlan,
  MediaFrame,
  NotebookView,
  OBSERVATION_NOTE_MAX,
  OverviewView,
  ParentObservation,
  ParentObservationRecorded,
  ProvenanceInventoryRow,
  SourceExcerpt,
  SourceProvenanceCard,
  SourceProvenancePanel,
  SourcesView,
  sourceExcerptState,
  sourceSupportModel,
  sourceTypeLabel,
  TextbookView,
  PronunciationSeat,
  PronunciationStudio,
  QuestMission,
  SectionPage,
  SnapshotLossNotice,
  LessonPaneBody,
  WorkspaceShell,
  blockSaveExcerpt,
  buildDeskModel,
  hubSlots,
  hubSlotName,
  selectedHubSlot,
  SlotRail,
  cbCourseGoalLine,
  cbCourseMonogram,
  cbCoursePathCaption,
  cbCoursePathSegments,
  CheckpointPath,
  cbCheckStateWord,
  cbPathCurrentId,
  cbPathNextId,
  cbPathNodeKind,
  cbPathNodeSize,
  cbPathEvidenceCaption,
  cbSealStation,
  cbShelfFingerprint,
  cbShelfGroupKey,
  cbStableHash,
  cbCourseContour,
  CourseContour,
  cbNextStopSentence,
  StudyCompanion,
  CourseCover,
  PackShelfRow,
  PackShelfSplit,
  shelfFocusTarget,
  PackFacts,
  CoursePath,
  groupShelfRows,
  ShelfDisclosure,
  // H-196 — the Workshop's own surface, exported so the frame audit renders the shipped module.
  WORKSHOP_TABS,
  WORKSHOP_USER_CATEGORIES,
  WORKSHOP_BADGE,
  workshopBadge,
  workshopTone,
  workshopMetaLine,
  sanitizeWorkshopPrefs,
  useWorkshopCatalog,
  WorkshopCover,
  WorkshopBadge,
  WorkshopTrustNote,
  WorkshopMeta,
  WorkshopCard,
  WorkshopHero,
  WorkshopShelf,
  WorkshopDetail,
  WorkshopDiscoverV3,
  WorkshopDiscoverHead,
  WorkshopDiscoverFeature,
  WorkshopDiscoverCard,
  WorkshopDiscoverRow,
  WorkshopDiscoverGrid,
  WorkshopDiscoverSkeleton,
  WorkshopDiscoverNotice,
  cb3DiscoverColumns,
  cb3DiscoverFoxBox,
  cb3PackCover,
  cb3PackSections,
  cb3PackSubject,
  cb3PackTrustLabels,
  cb3DiscoverMeta,
  CB3_DISCOVER_COPY,
  CB3_TRUST_LABELS,
  WorkshopProvenance,
  WorkshopView,
  // UI-K4 — the Courses route, exported so the frame audit can photograph the shipped surface.
  CoursesView,
  workshopFactRows,
  cbLayoutFor,
  cbModeFromTheme,
  cbMotionPreference,
  cbScopeStyle,
  checklistAnswer,
  checklistItems,
  parentObservationKey,
  parentObservationPayload,
  nextObservationSubmission,
  recordParentObservation,
  deskEstimateLabel,
  learnerEvidenceTarget,
  objectiveProgress,
  progressStatement,
  lessonViewOptions,
  lessonViewChoices,
  mainlineObjective,
  notebookSourceRef,
  pronPercent,
  pronunciationAvailabilityCopy,
  questMissions,
  missionBriefLine,
  planJobBrief,
  plural,
  COURSE_PRIMARY_TABS,
  courseMoreTabs,
  primarySurfaceFor,
  planRejectView,
  PlanRejectPanel,
  PLAN_VALIDATION_LINES,
  PLAN_VALIDATION_SETTINGS_HINT,
  PLAN_VALIDATION_CONFIGURE_LINE,
  planValidationView,
  PlanValidationLine,
  planTimingCopy,
  startLearnerPlan,
  courseCreatePayload,
  questProgressLabel,
  readNotebookRef,
  stripExcerpt,
  courseExportRequest,
  courseExportRepair,
  COURSE_EXPORT_BLOCKED_COPY,
  COURSE_EXPORT_PRIVATE_ROWS,
  COURSE_EXPORT_REPAIR,
  // CP-020b — the Field Atlas v3 primitives and the component-lab sheet. Exported so the render
  // tests and scripts/cp-lab-shot.mjs can mount every primitive in every state without a backend.
  CbV3Scope,
  PillAction,
  ForestRail,
  ForestBand,
  PaperCard,
  CollectibleCard,
  CoverPlate3,
  ShelfPlank,
  StampNode,
  Medallion,
  FoxPose,
  DialogueBubble,
  ChallengeCard,
  EvidenceTray,
  CbV3LabSheet,
  CbV3LabSection,
  CbV3PaletteChip,
  CB3_POSES,
  CB3_DESTINATIONS,
  CB3_STAMP_STATES,
  CB3_MEDALS,
  CB3_LAB_COPY,
  cb3Contrast,
  cb3StepRendering,
  cb3FoxSource,
  cb3FoxPixels,
  cb3FoxSrcSet,
  cb3KitSource,
  cb3KitCoverFor,
  CB3_FOX_EXPORTS,
  // CP-040 — the merge seam. Every v3 component and helper the six wave cards (CP-021, CP-022,
  // CP-023, CP-024, CP-025a, CP-025b) declared is exported from the module that ships: a surface
  // may not be mounted on the route without also being renderable from `desktop/plugin.js`, and
  // the render suites import these names from the built module rather than a test-only copy.
  // Home (CP-022, 30-home.js)
  CB_HOME_V3_COPY,
  CB_HOME_V3_LIMIT,
  CB_HOME_TAG_MAX_AGE_MS,
  HomeV3Card,
  HomeV3Cover,
  homeCardFacts,
  homeCardWidth,
  homeContentWidth,
  homeCoverArtifactId,
  homeGutter,
  homeNewTagSlot,
  homeNumber,
  homeShelfColumns,
  homeShelfLayout,
  // Classroom (CP-023, 70-learning.js)
  ClassroomV3,
  ClassroomV3Surface,
  ClassroomCheckCard,
  ClassroomQuietLine,
  ClassroomScene,
  CB3_CLASSROOM_COPY,
  CB3_CLASSROOM_RUBY,
  CB3_DIALOGUE_LINE,
  CB3_JAPANESE,
  CB3_KANJI,
  classroomCopy,
  classroomEvidence,
  classroomLineFromPage,
  classroomRubySegments,
  classroomSceneFromWorld,
  classroomStepNodes,
  classroomVerdictSentence,
  modelRevision,
  // Course home (CP-024, 90-course.js)
  CourseHomeV3,
  CourseScene,
  CourseHomeAside,
  CourseRouteList,
  CourseRouteMapNode,
  CB3_COURSE_COPY,
  cb3CourseAnchorPoints,
  cb3CourseEvidenceLine,
  cb3CourseHeroPlate,
  cb3CourseNodes,
  cb3CoursePlateAnchors,
  cb3CourseRoutePlan,
  cb3CourseWorldPosture,
  // Discover (CP-021, 96-workshop.js)
  CB3_DISCOVER_BODY,
  CB3_DISCOVER_HEADING,
  cb3DiscoverOpenKey,
  // World Studio (CP-025b, 97-world.js)
  WorldStudioFrame
}

export default {
  id: PLUGIN_ID,
  name: 'Coursebook',
  defaultEnabled: true,

  register(ctx) {
    pluginContext = ctx

    // `host.profileRoutes()` is async in current Desktop builds (CB-021): resolve it once into a
    // cache instead of calling it from render, where a Promise is not an array. A failed read is
    // retried twice, then kept as a visible `unavailable` state rather than an empty route list.
    profileRouteState = { status: 'loading', error: null }
    loadProfileRoutes()

    // Read the mounted backend's wire version + method registry. Best-effort and non-blocking:
    // a backend that is off leaves the defaults in place, and the page renders "unavailable".
    loadBackendWire()

    ctx.register({
      id: 'page',
      area: AREAS.routes,
      data: { path: ROUTE_PATH },
      render: () => jsx(CoursebookPage, {})
    })

    ctx.register({
      id: 'nav',
      area: AREAS.sidebarNav,
      data: { path: ROUTE_PATH, label: ROUTE_TITLE, codicon: 'book' }
    })

    ctx.register({
      id: 'pane',
      area: AREAS.panes,
      title: 'coursebook',
      data: { placement: 'right', width: '340px' },
      render: () => jsx(CoursebookPane, {})
    })

    if (typeof AREAS.palette === 'string') {
      ctx.register({
        id: 'open',
        area: AREAS.palette,
        data: {
          id: 'coursebook.open',
          label: 'Open Coursebook',
          keywords: ['coursebook', 'course', 'lesson', 'learn'],
          run: () => host.navigate(ROUTE_PATH)
        }
      })
      ctx.register({
        id: 'studio',
        area: AREAS.palette,
        data: {
          id: 'coursebook.studio',
          label: 'Open Parent Studio',
          keywords: ['parent', 'studio', 'lesson pack', 'teach', 'author', 'brief'],
          run: () => requestIntent({ kind: 'studio' })
        }
      })
      ctx.register({
        id: 'takehome',
        area: AREAS.palette,
        data: {
          id: 'coursebook.takehome',
          label: 'Take-home from a lesson',
          keywords: ['take-home', 'takehome', 'print', 'pack', 'parent', 'worksheet', 'lesson plan'],
          run: () => requestIntent({ kind: 'studio-takehome' })
        }
      })
      ctx.register({
        id: 'studio-new',
        area: AREAS.palette,
        data: {
          id: 'coursebook.studio.new',
          label: 'Write a parent lesson brief',
          keywords: ['parent', 'brief', 'new lesson', 'author', 'prepare'],
          run: () => requestIntent({ kind: 'studio-new' })
        }
      })
      ctx.register({
        id: 'syllabus',
        area: AREAS.palette,
        data: {
          id: 'coursebook.syllabus',
          label: SYLLABUS_COPY.action,
          keywords: ['syllabus', 'college', 'class', 'student', 'import', 'companion'],
          run: () => requestIntent({ kind: 'syllabus' })
        }
      })
    }

    // Keybind: a rebindable default, never a synthetic KeyboardEvent.
    if (typeof AREAS.keybinds === 'string') {
      ctx.register({
        id: 'focus',
        area: AREAS.keybinds,
        data: {
          id: 'coursebook.focus',
          label: 'Open Coursebook',
          category: 'Coursebook',
          defaults: ['mod+shift+k'],
          run: () => host.navigate(ROUTE_PATH)
        }
      })
      // GM-012 §7.3: Ctrl/Cmd+J fronts the tutor rail and puts the caret in its composer. It is a
      // navigation key, never a send: the learner still writes and presses Ask.
      ctx.register({
        id: 'tutor',
        area: AREAS.keybinds,
        data: {
          id: 'coursebook.tutor',
          label: 'Open the lesson tutor',
          category: 'Coursebook',
          defaults: ['mod+j'],
          run: () => {
            revealCoursebookPane()
            requestTutorFocus()
          }
        }
      })
    }

    if (typeof ctx.registerSettingsPage === 'function') {
      ctx.registerSettingsPage({
        id: 'coursebook-settings',
        title: 'Coursebook',
        icon: 'book',
        render: () => jsx(CoursebookSettings, {})
      })
    }

    ctx.onDispose(() => {
      pluginContext = null
      intentListeners.clear()
      pendingIntent = null
    })
  }
}
