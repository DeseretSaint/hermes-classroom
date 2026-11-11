// ══ H-27 — the student syllabus path: intake, parse review, anchors and alignment ══
//
// `docs/STUDENT-MODE.md` is the frozen design (H-25). This half renders exactly what the
// `syllabus.*` commands answer and nothing else:
//
//   intake     the host door reads bytes; the RPC carries bytes or pasted text and never a path;
//              when this Desktop build has no byte-reading door the screen says so and offers the
//              paste path, which the design makes first-class;
//   parse      every scalar is an item with a state and anchors. `unknown` renders as
//              "Not in your file" — a table cell is never filled from world knowledge;
//   alignment  one row per syllabus item with its state, one-line reason and the verbatim anchor;
//              conflict and stale block approval, and the learner's review is the gate;
//   course     the existing `course.create` → `enrollment.create` → plan job path, with the
//              syllabus fields the contract added. There is no second job engine and no percentage
//              invented for a job the backend reports by state only.
//
// The external class is the authority; Coursebook is a companion. That sentence is copy, not a
// badge, and `tests/test_desktop_syllabus_ui.py` refuses the marketing claims the design bans.

const SYLLABUS_LIMITS = Object.freeze({
  file_name: 255,
  text_bytes: 4 * 1024 * 1024,
  binary_bytes: 8 * 1024 * 1024,
  text_chars: 200000,
  pdf_pages: 60,
  docx_paragraphs: 2000,
  base64_chars: 11184812
})

/** The closed type list (§2.2). Anything else is refused; the UI does not offer it. */
const SYLLABUS_ACCEPT = Object.freeze([
  { ext: 'md', label: 'Markdown (.md)', format: 'markdown', mime: 'text/markdown', text: true },
  { ext: 'markdown', label: 'Markdown (.markdown)', format: 'markdown', mime: 'text/markdown', text: true },
  { ext: 'txt', label: 'Plain text (.txt)', format: 'text', mime: 'text/plain', text: true },
  { ext: 'pdf', label: 'PDF (.pdf)', format: 'pdf', mime: 'application/pdf', text: false },
  { ext: 'docx', label: 'Word document (.docx)', format: 'docx', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', text: false }
])

const SYLLABUS_MIME_HINTS = Object.freeze([
  'text/markdown',
  'text/plain',
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/octet-stream'
])

/**
 * The surface's copy, in one place so a test can read it without scraping JSX.
 *
 * Design §3.2 forbids "complete", "official" and "verified with your institution" as claims about
 * the parse; §4.6 forbids "official week 4 lesson", "your professor's lesson", "required by your
 * course", "counts toward your grade", "enrolled" and "accredited". "Not official course material"
 * is the required calm disclaimer and is written as a negation, never a promise.
 */
const SYLLABUS_COPY = Object.freeze({
  action: 'Use my college syllabus',
  actionDetail: 'You already have the syllabus. Coursebook builds a companion course around it.',
  entryTitle: 'Have a college syllabus?',
  entryBody:
    'Start a companion course from your own class. Your syllabus sets the scope; Coursebook authors its own lessons alongside it.',
  authority:
    'Your syllabus is the authority for what the class covers. Coursebook is a companion that supports it — it is not your class, your registrar, or a grade.',
  notOfficial: 'Not official course material. Coursebook writes its own lessons; your instructor’s document stays the authority.',
  parseSentence: 'Parsed from your file. Check each item against the page.',
  unknownValue: 'Not in your file',
  unknownWeight: 'Weight not in your file',
  unknownDue: 'Due date not in your file',
  ambiguousValue: 'Two readings in your file',
  acceptTypes: 'Markdown, plain text, PDF or Word (.docx). Up to 8 MB; 200,000 characters of text.',
  noFileDoor:
    'This Hermes Desktop build has no file door, so it cannot open a syllabus file here. Paste the text below — it is stored the same way and gets the same anchors.',
  noBackend:
    'This Coursebook backend does not have the syllabus import yet. Nothing here pretends to read your file until it does.',
  parseRunning: 'Reading your file. Extraction is local and runs in stages, so there is no percentage to show.',
  parseNeedsReview:
    'Some items could not be tied to a quote in your file. Check the ones marked below, or upload a cleaner copy.',
  storage: 'Your file stays on this profile. The parse and the alignment are sent to the model provider you have configured, and only after you acknowledge that.',
  alignmentGate: 'Review the mapping before a course is built. Conflict or stale items block approval.',
  researchMinutes: 'Research and authoring may take several minutes. The plan appears here when it is ready.',
  staleLead: 'Your syllabus changed. The earlier mapping was made against the previous version, so it is marked stale.',
  staleAction: 'Check the new version, then review the mapping again. Your approved plan and lessons are kept as they were.',
  startsCompanion: 'Create companion course',
  coversLine: (covered, total) => `This course covers ${covered} of ${total} syllabus weeks.`
})

const ALIGNMENT_STATE_COPY = Object.freeze({
  aligned: { label: 'Aligned', tone: 'ok', line: 'Coursebook covers what this item asks.' },
  partial: { label: 'Partly covered', tone: 'warn', line: 'This is covered, but less than the syllabus asks.' },
  unmatched: { label: 'Not covered', tone: 'warn', line: 'Nothing in this course plan maps to this item yet.' },
  conflict: { label: 'Conflicts', tone: 'bad', line: 'The course plan contradicts this item.' },
  unknown: { label: 'Not checked', tone: 'muted', line: 'This item has not been evaluated yet.' },
  stale: { label: 'Out of date', tone: 'bad', line: 'The syllabus or the plan changed after this was mapped.' }
})

const SYLLABUS_REASON_COPY = Object.freeze({
  week_ordinal: 'Matched on the week number in your syllabus.',
  title_tokens: 'Matched on the wording of the topic.',
  reading_match: 'Matched on the reading named in your syllabus.',
  assessment_match: 'Matched on the assessment name.',
  model: 'Suggested by the model; treat it as a hypothesis, not proof.',
  anchor_mismatch: 'The quote could not be found in your file, so this stays unknown.',
  no_target: 'No row in the course plan matched this item.',
  weak_title_tokens: 'The plan covers part of this item, not all of it.',
  scheduled_after_deadline: 'The plan reaches this topic after the week your syllabus gives it.',
  value_unknown: 'Your file does not state this item, so nothing was mapped to it.',
  week_mismatch: 'The plan places this topic in a different week.',
  deadline_passed: 'The plan schedules work after the date in your syllabus.',
  scope_exceeded: 'The plan claims more than this item asks for.',
  ignored_assessment: 'The plan claims coverage while ignoring this assessment.',
  revision_changed: 'The syllabus version changed after this mapping was made.',
  plan_superseded: 'The plan was replaced after this mapping was made.'
})

/** Format from the extension, never from a declared MIME (§2.1: magic bytes decide at the backend). */
function syllabusFormatFor(name) {
  const value = String(name || '')
  const dot = value.lastIndexOf('.')
  if (dot < 0 || dot === value.length - 1) return null
  const ext = value.slice(dot + 1).toLowerCase()
  const entry = SYLLABUS_ACCEPT.find((candidate) => candidate.ext === ext)
  return entry ? entry.format : null
}

function syllabusAcceptEntry(name) {
  const value = String(name || '')
  const dot = value.lastIndexOf('.')
  const ext = dot >= 0 ? value.slice(dot + 1).toLowerCase() : ''
  return SYLLABUS_ACCEPT.find((candidate) => candidate.ext === ext) || null
}

function base64FromUtf8(text) {
  const encoder = new TextEncoder()
  const bytes = encoder.encode(String(text))
  let binary = ''
  const step = 0x8000
  for (let index = 0; index < bytes.length; index += step) {
    binary += String.fromCharCode.apply(null, bytes.subarray(index, index + step))
  }
  return btoa(binary)
}

function utf8Bytes(text) {
  return new TextEncoder().encode(String(text)).length
}

/**
 * The `syllabus.intake.create` payload, or a typed refusal.
 *
 * Exactly one of `content_base64` / `pasted_text` (§2.1). Bounds are checked here, before a job
 * exists, so an oversized file is refused with the measured size instead of being uploaded to be
 * refused later. Nothing here is a sample: a caller that passes nothing gets a refusal.
 */
function syllabusIntakePayload(input = {}) {
  const fail = (code, message) => ({ ok: false, error: { code, message } })
  const pasted = typeof input.pastedText === 'string' ? input.pastedText : null
  const text = typeof input.text === 'string' ? input.text : null
  const dataUrl = typeof input.dataUrl === 'string' ? input.dataUrl : null
  const supplied = [pasted !== null, text !== null, dataUrl !== null].filter(Boolean).length
  if (supplied !== 1) {
    return fail('VALIDATION_FAILED', 'Send one file or one pasted syllabus, not several at once.')
  }

  const supersedes = input.supersedesSyllabusId ? String(input.supersedesSyllabusId) : null

  if (pasted !== null) {
    const chars = pasted.length
    if (chars === 0) return fail('VALIDATION_FAILED', 'The pasted syllabus is empty.')
    if (chars > SYLLABUS_LIMITS.text_chars) {
      return fail('SYLLABUS_REJECTED', `That text is ${chars.toLocaleString()} characters; the limit is ${SYLLABUS_LIMITS.text_chars.toLocaleString()}.`)
    }
    const payload = { pasted_text: pasted }
    if (supersedes) payload.supersedes_syllabus_id = supersedes
    return { ok: true, payload }
  }

  const fileName = String(input.fileName || '').trim()
  if (!fileName) return fail('VALIDATION_FAILED', 'The file has no name to show beside it.')
  if (fileName.length > SYLLABUS_LIMITS.file_name) {
    return fail('SYLLABUS_REJECTED', 'That file name is longer than the 255 characters the contract accepts.')
  }
  const entry = syllabusAcceptEntry(fileName)
  if (!entry) {
    return fail('SYLLABUS_REJECTED', 'Coursebook reads Markdown, plain text, PDF and Word (.docx) only. Nothing else is accepted.')
  }

  if (text !== null) {
    if (!entry.text) return fail('SYLLABUS_REJECTED', 'A PDF or Word file has to be read as bytes, not as text.')
    const chars = text.length
    const bytes = utf8Bytes(text)
    if (chars === 0) return fail('VALIDATION_FAILED', 'That file is empty.')
    if (chars > SYLLABUS_LIMITS.text_chars) {
      return fail('SYLLABUS_REJECTED', `That file is ${chars.toLocaleString()} characters; the limit is ${SYLLABUS_LIMITS.text_chars.toLocaleString()}.`)
    }
    if (bytes > SYLLABUS_LIMITS.text_bytes) {
      return fail('SYLLABUS_REJECTED', `That file is ${bytesLabel(bytes)}; the text limit is ${bytesLabel(SYLLABUS_LIMITS.text_bytes)}.`)
    }
    if (text.indexOf('\u0000') >= 0) return fail('SYLLABUS_REJECTED', 'That file is not plain UTF-8 text.')
    const payload = { content_base64: base64FromUtf8(text), file_name: fileName, mime_hint: entry.mime }
    if (supersedes) payload.supersedes_syllabus_id = supersedes
    return { ok: true, payload }
  }

  const match = /^data:([^;,]*)(?:;[^,]*)?;base64,(.*)$/s.exec(dataUrl)
  if (!match) return fail('VALIDATION_FAILED', 'The host returned a file in a form Coursebook cannot read. Paste the text instead.')
  const base64 = match[2] || ''
  if (base64.length > SYLLABUS_LIMITS.base64_chars) {
    return fail('SYLLABUS_REJECTED', `That file is larger than the 8 MB limit for PDF and Word.`)
  }
  const bytes = Math.floor((base64.length * 3) / 4)
  if (bytes > SYLLABUS_LIMITS.binary_bytes) {
    return fail('SYLLABUS_REJECTED', `That file is ${bytesLabel(bytes)}; the limit is ${bytesLabel(SYLLABUS_LIMITS.binary_bytes)}.`)
  }
  if (entry.text) return fail('SYLLABUS_REJECTED', 'A text document has to be read as text, not as bytes.')
  const declared = String(match[1] || '')
  const hint = SYLLABUS_MIME_HINTS.indexOf(declared) >= 0 ? declared : entry.mime
  const payload = { content_base64: base64, file_name: fileName, mime_hint: hint }
  if (supersedes) payload.supersedes_syllabus_id = supersedes
  return { ok: true, payload }
}

/** One anchor as a short human label: a page, a line range, or a named section. */
function syllabusAnchorLabel(anchor) {
  if (!anchor) return 'your file'
  const page = anchor.page
  if (page !== undefined && page !== null && String(page).length) return `p. ${page}`
  const start = anchor.line_start
  const end = anchor.line_end
  if (start !== undefined && start !== null && String(start).length) {
    if (end !== undefined && end !== null && String(end).length && end !== start) return `lines ${start}–${end}`
    return `line ${start}`
  }
  if (anchor.section) return String(anchor.section)
  if (anchor.label) return String(anchor.label)
  return 'your file'
}

/**
 * One parsed scalar as the review screen shows it.
 *
 * `unknown` never renders a value: the cell says the file does not state it. `ambiguous` shows
 * that the file supports two readings and lists them; it does not pick one. A state this module
 * does not know is treated as unknown, because guessing is the one thing this surface must not do.
 */
function syllabusItemView(item) {
  const state = item && typeof item.state === 'string' ? item.state : 'unknown'
  const anchors = (item && Array.isArray(item.anchors) ? item.anchors : []).filter(Boolean)
  const anchorLabels = anchors.map(syllabusAnchorLabel)
  if (state === 'extracted' && item.value !== null && item.value !== undefined && item.value !== '') {
    return {
      state: 'extracted',
      unknown: false,
      text: String(item.value),
      anchors,
      anchorLabels,
      derivation: item.derivation || 'explicit'
    }
  }
  if (state === 'ambiguous') {
    return {
      state: 'ambiguous',
      unknown: true,
      text: SYLLABUS_COPY.ambiguousValue,
      candidates: Array.isArray(item.candidates) ? item.candidates : [],
      anchors,
      anchorLabels,
      derivation: item.derivation || 'ambiguous'
    }
  }
  return {
    state: 'unknown',
    unknown: true,
    text: SYLLABUS_COPY.unknownValue,
    reason: item && item.reason ? String(item.reason) : null,
    anchors,
    anchorLabels,
    derivation: 'unknown'
  }
}

/** Weight and due date, each stated or explicitly unknown. No conversion, no arithmetic. */
function syllabusAssessmentRows(assessments) {
  return (Array.isArray(assessments) ? assessments : []).map((assessment) => {
    const rawTitle = assessment && assessment.title
    const title = syllabusItemView(
      rawTitle && typeof rawTitle === 'object'
        ? rawTitle
        : rawTitle
          ? { value: rawTitle, state: 'extracted', anchors: assessment.anchors }
          : { state: 'unknown' }
    )
    const weight = syllabusItemView((assessment && assessment.weight) || { state: 'unknown' })
    const unit = (assessment && assessment.weight_unit) || 'unknown'
    let weightText = weight.text
    if (!weight.unknown) {
      if (unit === 'percent') weightText = `${weight.text}%`
      else if (unit === 'points') weightText = `${weight.text} points`
    } else {
      weightText = SYLLABUS_COPY.unknownWeight
    }
    const due = syllabusItemView((assessment && assessment.due) || { state: 'unknown' })
    let dueText = due.text
    if (due.unknown) dueText = SYLLABUS_COPY.unknownDue
    else if (due.derivation === 'computed_from_term_start') dueText = `${due.text} (counted from your term start)`
    return {
      id: (assessment && assessment.id) || null,
      title: title.text,
      titleUnknown: title.unknown,
      kind: (assessment && assessment.kind) || 'unknown',
      due: dueText,
      dueUnknown: due.unknown,
      weight: weightText,
      weightUnknown: weight.unknown,
      weekOrdinal: assessment && assessment.week_ordinal !== undefined ? assessment.week_ordinal : null,
      anchors: (assessment && assessment.anchors) || [],
      anchorLabels: ((assessment && assessment.anchors) || []).map(syllabusAnchorLabel)
    }
  })
}

/**
 * The scope the parser proposes, with its reason. A syllabus with no term length proposes
 * nothing — the learner chooses, and the screen says why (§5).
 */
function syllabusScopeProposal(parsed) {
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const weeks = Array.isArray(document.weeks) ? document.weeks.length : 0
  const assessments = Array.isArray(document.assessments) ? document.assessments.length : 0
  if (weeks === 0) {
    return { proposal: null, reason: 'Your file does not list weeks, so Coursebook cannot propose a length. Choose one.', weeks, assessments }
  }
  if (weeks === 1) {
    return { proposal: 'single', reason: 'Your file covers one week, so one lesson is enough — you can choose a short course instead.', weeks, assessments }
  }
  if (weeks <= 7) {
    return { proposal: 'short', reason: `Your file lists ${weeks} weeks, so a short course fits.`, weeks, assessments }
  }
  return { proposal: 'full', reason: `Your file lists ${weeks} weeks and ${assessments} assessment${assessments === 1 ? '' : 's'}, so this is a long course; authoring runs unit by unit.`, weeks, assessments }
}

/**
 * One parsed item kind in the learner's words. The backend's `syllabus.get` serves a flat item
 * list; the review screen groups it, and the "what is missing" line never prints a raw kind.
 */
const SYLLABUS_KIND_COPY = Object.freeze({
  course_code: 'course code',
  course_title: 'course title',
  institution: 'institution',
  instructor: 'instructor',
  meeting_pattern: 'when the class meets',
  term_label: 'term name',
  term_start: 'term start',
  term_end: 'term end',
  week: 'week',
  reading: 'reading',
  assessment: 'assessment',
  learning_outcome: 'learning outcome',
  policy: 'study policy'
})

/**
 * `syllabus.get` → the review document.
 *
 * The wire carries a flat item list (`kind`, `title`, `value`, `state`, `anchors`, `week_ordinal`);
 * this groups it into the course facts, weeks, readings, assessments, outcomes and policies the
 * review renders. It composes nothing: an item the backend marks unknown stays unknown, a weight the
 * item list does not carry stays unknown, and a week's topic is only read off a title that the parse
 * wrote. Fixture documents (already in this shape) pass through unchanged.
 */
function syllabusParseView(view) {
  const source = view || {}
  if (source.document) return source
  const items = Array.isArray(source.items) ? source.items : []
  const blocks = Array.isArray(source.blocks) ? source.blocks : []
  const syllabus = source.syllabus || {}
  const run = source.parse_run || null
  const validation = (run && run.validation) || {}
  const item = (kind) => {
    const found = items.find((entry) => entry && entry.kind === kind)
    return found
      ? {
          value: found.value,
          state: found.state,
          anchors: Array.isArray(found.anchors) ? found.anchors : [],
          derivation: found.derivation || 'unknown',
          candidates: found.candidates,
          item_id: found.item_id
        }
      : { state: 'unknown', anchors: [], derivation: 'unknown' }
  }
  const weekItems = items.filter((entry) => entry && entry.kind === 'week')
  const weeks = weekItems.map((entry) => {
    const title = String(entry.title || '')
    const split = title.indexOf(':')
    const label = (split >= 0 ? title.slice(0, split) : title).trim()
    const topic = split >= 0 ? title.slice(split + 1).trim() : ''
    return {
      ordinal: { value: entry.value, state: entry.state, anchors: entry.anchors || [], derivation: entry.derivation || 'unknown' },
      weekOrdinal: entry.week_ordinal === undefined ? null : entry.week_ordinal,
      label: label ? { value: label, state: 'extracted', anchors: entry.anchors || [] } : { state: 'unknown', anchors: [] },
      topic: topic ? { value: topic, state: 'extracted', anchors: entry.anchors || [] } : { state: 'unknown', anchors: [] },
      anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
      readings: items.filter((candidate) => candidate.kind === 'reading' && candidate.week_ordinal === entry.week_ordinal),
      assessments: []
    }
  })
  // An assessment with no due date is stored twice: the title row and a `"<title> (due)"` row that
  // carries the unknown. The companion row is folded back into its title; it is never a second
  // assessment, and it never invents a date.
  const assessments = []
  for (const entry of items.filter((candidate) => candidate && candidate.kind === 'assessment')) {
    const title = String(entry.title || '')
    const due = /^(.*) \(due\)$/.exec(title)
    if (due) {
      const parent = assessments.find(
        (row) => row.baseTitle === due[1].trim() && row.week_ordinal === entry.week_ordinal
      )
      if (parent) {
        parent.due = {
          value: entry.value,
          state: entry.state,
          anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
          derivation: entry.derivation || 'unknown'
        }
        continue
      }
    }
    const row = {
      id: entry.item_id || null,
      baseTitle: title,
      title: {
        value: entry.value,
        state: entry.state,
        anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
        derivation: entry.derivation || 'unknown'
      },
      kind: 'assessment',
      due: { state: 'unknown', anchors: [], derivation: 'unknown' },
      weight: { state: 'unknown', anchors: [], derivation: 'unknown' },
      weight_unit: 'unknown',
      week_ordinal: entry.week_ordinal === undefined ? null : entry.week_ordinal,
      anchors: Array.isArray(entry.anchors) ? entry.anchors : []
    }
    assessments.push(row)
    const week = weeks.find((candidate) => candidate.weekOrdinal === entry.week_ordinal)
    if (week) week.assessments.push(row)
  }
  const listOf = (kind) =>
    items
      .filter((entry) => entry && entry.kind === kind)
      .map((entry) => ({
        value: entry.value,
        state: entry.state,
        anchors: Array.isArray(entry.anchors) ? entry.anchors : [],
        derivation: entry.derivation || 'unknown'
      }))
  const unknowns = []
  for (const entry of items) {
    if (!entry || entry.state !== 'unknown') continue
    const label = SYLLABUS_KIND_COPY[entry.kind] || 'item'
    const title = entry.title && !/ \(due\)$/.test(String(entry.title)) ? ` (${entry.title})` : ''
    unknowns.push(`${label}${title}`)
  }
  const warnings = []
  const mismatches = Number(validation.anchor_mismatches || 0)
  if (mismatches > 0) {
    warnings.push(
      `${mismatches} item${mismatches === 1 ? '' : 's'} could not be tied to a quote in your file. They are shown as not stated rather than guessed.`
    )
  }
  return {
    syllabus_id: syllabus.syllabus_id || null,
    revision: syllabus.revision === undefined ? null : syllabus.revision,
    content_sha256: syllabus.content_sha256 || null,
    parse_state: run ? (run.state === 'needs_review' ? 'needs_review' : 'parsed') : null,
    parse_run: run,
    warnings,
    blocks,
    coverage: source.coverage || {},
    unknowns: [...new Set(unknowns)],
    document: {
      schema: 'syllabus.parse.v1',
      course: { code: item('course_code'), title: item('course_title') },
      institution: item('institution'),
      instructor: item('instructor'),
      meeting_pattern: item('meeting_pattern'),
      term: { label: item('term_label'), start_date: item('term_start'), end_date: item('term_end') },
      weeks,
      assessments,
      learning_outcomes: listOf('learning_outcome'),
      policies: listOf('policy'),
      unknowns: [...new Set(unknowns)],
      coverage: source.coverage || {}
    }
  }
}

/** The course's own metadata, each field stated by the file or absent. Nothing is composed. */
function syllabusCourseFields(parsed) {
  const document = parsed && parsed.document ? parsed.document : parsed || {}
  const course = document.course || {}
  const code = syllabusItemView(course.code || { state: 'unknown' })
  const title = syllabusItemView(course.title || { state: 'unknown' })
  return {
    code: code.unknown ? null : code.text,
    title: title.unknown ? null : title.text,
    codeView: code,
    titleView: title,
    institution: syllabusItemView(document.institution ? document.institution : { state: 'unknown' })
  }
}

/**
 * `course.create` for a companion course (§6.2). The syllabus id and revision travel together or
 * not at all; `recipe` is always `companion` and `pack_id` is never sent, so the backend keeps
 * `courses.pack_id` NULL.
 */
function syllabusCoursePayload({ parsed, scope, goal, learnerLabel }) {
  const fields = syllabusCourseFields(parsed)
  const title = fields.title || fields.code || String(learnerLabel || '').trim() || 'Companion course'
  const payload = {
    title,
    recipe: 'companion',
    goal: String(goal || '').trim() || (fields.title ? `Support the class on ${fields.title}.` : 'Support the class described in my syllabus.'),
    dials: {},
    scope: scope || 'short'
  }
  if (parsed && parsed.syllabus_id) payload.syllabus_id = parsed.syllabus_id
  if (parsed && parsed.revision !== undefined) payload.syllabus_revision = parsed.revision
  return payload
}

/** The plan job brief: the existing brief plus the syllabus fields the contract added. */
function syllabusPlanBrief({ courseId, enrollmentId, goal, syllabusId, syllabusRevision, alignmentRevision, scope }) {
  const brief = { stage: 'plan', course_id: courseId, enrollment_id: enrollmentId, goal, recipe: 'companion', dials: {} }
  if (scope) brief.scope = scope
  if (syllabusId) brief.syllabus_id = syllabusId
  if (syllabusRevision !== undefined && syllabusRevision !== null) brief.syllabus_revision = syllabusRevision
  if (alignmentRevision !== undefined && alignmentRevision !== null) brief.alignment_revision = alignmentRevision
  return brief
}

/** `syllabus.align` between the draft plan and the parsed syllabus. */
function syllabusAlignPayload({ syllabusId, revision, courseId, planId }) {
  return { syllabus_id: syllabusId, revision: Number(revision) || 0, course_id: courseId, plan_id: planId }
}

/**
 * The alignment as the review screen shows it.
 *
 * One row per syllabus item. `aligned` and `partial` do not block; `conflict`, `stale`, and an
 * extracted item still awaiting evaluation (`unknown`) do. An item whose *value* is unknown never
 * blocks, because nothing was mapped, so nothing was invented (§4.2).
 */
function syllabusAlignmentView(alignment) {
  const source = alignment || {}
  const items = Array.isArray(source.items) ? source.items : []
  const rows = items.map((item) => {
    const state = typeof item.state === 'string' ? item.state : 'unknown'
    const copy = ALIGNMENT_STATE_COPY[state] || ALIGNMENT_STATE_COPY.unknown
    const valueState = item.value_state || item.valueState || (item.value === undefined || item.value === null ? 'unknown' : 'extracted')
    const anchors = Array.isArray(item.anchors) ? item.anchors : []
    const target = item.target || null
    const evidence = item.evidence && typeof item.evidence === 'object' ? item.evidence : {}
    const reasonCode = item.reason_code || item.reasonCode || null
    const reason =
      item.reason ||
      (reasonCode && SYLLABUS_REASON_COPY[reasonCode]) ||
      evidence.explanation ||
      copy.line
    const blocks = state === 'conflict' || state === 'stale' || (state === 'unknown' && valueState !== 'unknown')
    const actions = []
    if (state === 'partial') actions.push({ action: 'accept_partial', label: 'Accept what it covers' })
    if (state === 'unmatched') actions.push({ action: 'accept_unmatched', label: 'Accept not covered' })
    if (state === 'conflict') {
      actions.push({ action: 'accept_divergence', label: 'Accept this divergence' })
      actions.push({ action: 'request_replan', label: 'Replan to match my syllabus' })
    }
    return {
      itemId: item.item_id || item.itemId || null,
      kind: item.kind || 'item',
      title: item.title || item.value || (item.kind ? String(item.kind) : 'Syllabus item'),
      state,
      stateLabel: copy.label,
      tone: copy.tone,
      line: copy.line,
      reason,
      reasonCode,
      valueState,
      anchors,
      anchorLabels: anchors.map(syllabusAnchorLabel),
      target,
      targetLabel: target ? target.title || target.label || target.target_id || null : null,
      reviewState: item.review_state || 'pending',
      blocks,
      actions
    }
  })
  const counts = { aligned: 0, partial: 0, unmatched: 0, conflict: 0, unknown: 0, stale: 0 }
  if (source.counts && typeof source.counts === 'object') {
    for (const key of Object.keys(counts)) counts[key] = Number(source.counts[key] || 0)
  } else {
    rows.forEach((row) => {
      counts[row.state] = (counts[row.state] || 0) + 1
    })
  }
  const alignmentRevision = Number(source.alignment_revision) || 0
  const reviewedRevision = Number(source.reviewed_revision) || 0
  const stale = Boolean(source.stale) || rows.some((row) => row.state === 'stale')
  const blocking = rows.filter((row) => row.blocks)
  const awaitingReview = rows.filter((row) => row.state !== 'aligned' && row.state !== 'unknown' && row.reviewState === 'pending')
  return {
    rows,
    counts,
    stale,
    alignmentRevision,
    reviewedRevision,
    reviewComplete: alignmentRevision > 0 && reviewedRevision === alignmentRevision,
    blocking,
    awaitingReview,
    // The primary press IS the review call, so requiring reviewedRevision here made the only
    // control that records a review impossible to press. It is ready when the mapping is fresh,
    // unblocked and exists; the label flips to Approved once reviewedRevision catches up.
    approveReady: !stale && blocking.length === 0 && alignmentRevision > 0,
    approveBlockedReason: stale
      ? SYLLABUS_COPY.staleLead
      : blocking.length
        ? `${blocking.length} item${blocking.length === 1 ? '' : 's'} must be resolved before the plan can be approved.`
        : reviewedRevision !== alignmentRevision
          ? 'Review each item, then approve the mapping.'
          : null
  }
}

/** `syllabus.alignment.review`: the decisions, fenced to the revision the learner actually saw. */
function syllabusReviewPayload({ syllabusId, revision, courseId, alignmentRevision, decisions }) {
  const accepted = ['accept_partial', 'accept_unmatched', 'accept_divergence', 'request_replan']
  const rows = (Array.isArray(decisions) ? decisions : [])
    .filter((decision) => decision && decision.item_id && accepted.indexOf(decision.action) >= 0)
    .map((decision) => ({ item_id: decision.item_id, action: decision.action }))
  return {
    syllabus_id: syllabusId,
    revision: Number(revision) || 0,
    course_id: courseId,
    alignment_revision: Number(alignmentRevision) || 0,
    decisions: rows
  }
}

/** The revision notice. A new revision marks the old mapping stale; it never regenerates a plan. */
function syllabusStaleNotice({ revision, counts, planRevision }) {
  const pending = counts && typeof counts === 'object' ? Number(counts.conflict || 0) + Number(counts.stale || 0) : 0
  const lines = [SYLLABUS_COPY.staleLead]
  if (pending > 0) lines.push(`${pending} mapping${pending === 1 ? '' : 's'} need another look.`)
  if (planRevision !== undefined && planRevision !== null) {
    lines.push(`Your approved plan is still the one aligned to version ${planRevision} of your syllabus; it stays readable.`)
  }
  lines.push(SYLLABUS_COPY.staleAction)
  return { revision: Number(revision) || 0, pending, lines, action: 'Check the new version' }
}

/**
 * One companion course: `course.create` → `enrollment.create` → one plan job.
 *
 * The same shape as `startLearnerPlan`, with the syllabus binding and no second engine. A failed
 * plan job keeps the ids that already exist, and the same key retries the same job.
 */
async function startCompanionCourse({ call, key, parsed, scope, goal, learnerLabel }) {
  const course = await call('course.create', syllabusCoursePayload({ parsed, scope, goal, learnerLabel }), {
    idempotencyKey: key,
    expectedRevision: null
  })
  if (!course || !course.ok) return { ok: false, stage: 'course.create', error: (course && course.error) || null }
  const courseId = course.result.course_id
  const planId = course.result.plan_id || null

  const enrollment = await call(
    'enrollment.create',
    { course_id: courseId, learner_label: learnerLabel || course.result.title || 'Companion course' },
    { idempotencyKey: `${key}-enroll`, expectedRevision: null }
  )
  if (!enrollment || !enrollment.ok) {
    return { ok: false, stage: 'enrollment.create', error: (enrollment && enrollment.error) || null, courseId, planId }
  }
  const enrollmentId = enrollment.result.enrollment_id

  const job = await call(
    'jobs.create',
    {
      kind: 'plan',
      brief: syllabusPlanBrief({
        courseId,
        enrollmentId,
        goal,
        scope,
        syllabusId: parsed && parsed.syllabus_id,
        syllabusRevision: parsed && parsed.revision
      })
    },
    { idempotencyKey: `${key}-plan` }
  )
  if (!job || !job.ok) {
    return { ok: false, stage: 'jobs.create', error: (job && job.error) || null, courseId, planId, enrollmentId }
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

/** `syllabus.align` once a draft plan exists. Idempotent per (syllabus, revision, plan). */
async function queueSyllabusAlignment({ call, syllabusId, revision, courseId, planId }) {
  const response = await call(
    'syllabus.align',
    syllabusAlignPayload({ syllabusId, revision, courseId, planId }),
    { idempotencyKey: `cb-syllabus-align-${syllabusId}-${revision}-${planId}` }
  )
  if (!response || !response.ok) return { ok: false, error: (response && response.error) || null }
  return { ok: true, jobId: response.result.job_id, alignmentRevision: response.result.alignment_revision, state: response.result.state }
}

