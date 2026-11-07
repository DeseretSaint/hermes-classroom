-- 0008_syllabus_intake.sql — cb.db v8 (H-26 student syllabus import).
--
-- Additive only: no existing table, column, index or unique key is dropped or retyped, and there
-- is no backfill. A pre-v8 course keeps no `course_syllabi` row and behaves exactly as before.
--
-- The syllabus is read-only scope input. Courses, plans, objectives, enrollments, attempts and
-- evidence remain the only course engine, enrollment authority, plan hash and grading path. No
-- syllabus row writes `courses.pack_id`; no pack, library or export path reads these tables.

CREATE TABLE syllabus_series (
    id TEXT PRIMARY KEY,
    learner_label TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE syllabi (
    id TEXT PRIMARY KEY,
    series_id TEXT NOT NULL REFERENCES syllabus_series(id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    supersedes_id TEXT REFERENCES syllabi(id),
    content_sha256 TEXT NOT NULL,
    file_name TEXT,
    mime TEXT,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('text', 'markdown', 'pdf', 'docx', 'pasted')),
    state TEXT NOT NULL CHECK (state IN ('stored', 'parsing', 'parsed', 'failed')),
    created_at TEXT NOT NULL,
    superseded_at TEXT,
    deleted_at TEXT,
    UNIQUE (series_id, revision)
);

CREATE INDEX idx_syllabi_series ON syllabi(series_id);
CREATE INDEX idx_syllabi_sha ON syllabi(content_sha256);

CREATE TABLE syllabus_files (
    syllabus_id TEXT PRIMARY KEY REFERENCES syllabi(id),
    bytes BLOB NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    sha256 TEXT NOT NULL
);

CREATE TABLE syllabus_blocks (
    id TEXT PRIMARY KEY,
    syllabus_id TEXT NOT NULL REFERENCES syllabi(id),
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    label TEXT,
    page INTEGER,
    line_start INTEGER,
    line_end INTEGER,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    UNIQUE (syllabus_id, ordinal)
);

CREATE INDEX idx_syllabus_blocks_syllabus ON syllabus_blocks(syllabus_id);

CREATE TABLE syllabus_parse_runs (
    id TEXT PRIMARY KEY,
    syllabus_id TEXT NOT NULL REFERENCES syllabi(id),
    schema TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('parsed', 'needs_review', 'failed')),
    provider TEXT,
    model TEXT,
    validation_json TEXT NOT NULL DEFAULT '{}',
    coverage_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_syllabus_parse_runs_syllabus ON syllabus_parse_runs(syllabus_id);

CREATE TABLE syllabus_items (
    id TEXT PRIMARY KEY,
    syllabus_id TEXT NOT NULL REFERENCES syllabi(id),
    parse_run_id TEXT NOT NULL REFERENCES syllabus_parse_runs(id),
    kind TEXT NOT NULL CHECK (kind IN (
        'institution', 'course_code', 'course_title', 'term_label', 'term_start', 'term_end',
        'instructor', 'meeting_pattern', 'learning_outcome', 'week', 'reading', 'assessment', 'policy'
    )),
    ordinal INTEGER NOT NULL,
    week_ordinal INTEGER,
    title TEXT,
    value_json TEXT NOT NULL,
    value_state TEXT NOT NULL CHECK (value_state IN ('extracted', 'unknown', 'ambiguous')),
    anchors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_syllabus_items_syllabus_kind ON syllabus_items(syllabus_id, kind);
CREATE INDEX idx_syllabus_items_parse_run ON syllabus_items(parse_run_id);

CREATE TABLE course_syllabi (
    course_id TEXT PRIMARY KEY REFERENCES courses(id),
    syllabus_id TEXT NOT NULL REFERENCES syllabi(id),
    syllabus_revision INTEGER NOT NULL,
    alignment_revision INTEGER NOT NULL DEFAULT 0,
    reviewed_revision INTEGER,
    reviewed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_course_syllabi_syllabus ON course_syllabi(syllabus_id);

CREATE TABLE syllabus_alignments (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id),
    plan_id TEXT NOT NULL REFERENCES plans(id),
    syllabus_id TEXT NOT NULL REFERENCES syllabi(id),
    syllabus_revision INTEGER NOT NULL,
    item_id TEXT NOT NULL REFERENCES syllabus_items(id),
    target_kind TEXT NOT NULL CHECK (target_kind IN ('unit', 'objective', 'lesson')),
    target_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('aligned', 'partial', 'unmatched', 'conflict', 'unknown', 'stale')),
    reason_code TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    review_state TEXT NOT NULL CHECK (review_state IN ('pending', 'accepted', 'accepted_divergence', 'replan_requested')),
    stale INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (course_id, syllabus_revision, item_id, target_kind, target_id)
);

CREATE INDEX idx_syllabus_alignments_course ON syllabus_alignments(course_id, syllabus_revision);
CREATE INDEX idx_syllabus_alignments_item ON syllabus_alignments(item_id);
