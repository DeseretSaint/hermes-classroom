-- Coursebook schema v1.
-- Authoritative inventory: contracts/db.v1.json (cb.db). Every table, column, reference,
-- unique key and index below comes from that file; tests/test_kernel_schema.py introspects the
-- live database and fails if the two disagree.
--
-- Types are SQLite storage classes. NOT NULL follows the contract's `nullable: false`, defaults
-- follow `default`, foreign keys follow `ref`, single-column indexes follow `indexes`, and CHECK
-- lists are generated from the contract's `enum` / `vocabulary` values so an invalid state cannot
-- be written even by a buggy handler.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER NOT NULL PRIMARY KEY,
    checksum   TEXT    NOT NULL,
    applied_at TEXT    NOT NULL
);

-- Packs first: courses.pack_id references it.
CREATE TABLE packs (
    id            TEXT    NOT NULL PRIMARY KEY,
    pack_id       TEXT    NOT NULL,
    version       TEXT    NOT NULL,
    manifest_hash TEXT    NOT NULL,
    license_json  TEXT    NOT NULL DEFAULT '{}',
    derived_from  TEXT,
    source        TEXT    NOT NULL CHECK (source IN ('bundled', 'local', 'community')),
    installed_at  TEXT    NOT NULL,
    UNIQUE (pack_id, version)
);
CREATE INDEX idx_packs_pack_id ON packs (pack_id);

CREATE TABLE courses (
    id          TEXT    NOT NULL PRIMARY KEY,
    title       TEXT    NOT NULL,
    recipe      TEXT    NOT NULL CHECK (recipe IN ('one_off', 'casual', 'committed', 'companion', 'parent')),
    goal        TEXT    NOT NULL,
    locale      TEXT,
    dials_json  TEXT    NOT NULL DEFAULT '{}',
    status      TEXT    NOT NULL CHECK (status IN ('draft', 'active', 'archived', 'deleted')),
    pack_id     TEXT REFERENCES packs (id),
    revision    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
CREATE INDEX idx_courses_status ON courses (status);
CREATE INDEX idx_courses_pack_id ON courses (pack_id);

CREATE TABLE plans (
    id            TEXT    NOT NULL PRIMARY KEY,
    course_id     TEXT    NOT NULL REFERENCES courses (id),
    version       INTEGER NOT NULL,
    state         TEXT    NOT NULL CHECK (state IN ('draft', 'approved', 'superseded')),
    plan_hash     TEXT,
    schedule_json TEXT    NOT NULL DEFAULT '{}',
    created_at    TEXT    NOT NULL,
    approved_at   TEXT,
    UNIQUE (course_id, version)
);
CREATE INDEX idx_plans_course_id ON plans (course_id);

CREATE TABLE objectives (
    id                    TEXT    NOT NULL PRIMARY KEY,
    plan_id               TEXT    NOT NULL REFERENCES plans (id),
    ordinal               INTEGER NOT NULL,
    title                 TEXT    NOT NULL,
    evidence_target       TEXT    NOT NULL CHECK (evidence_target IN ('recall', 'comprehension', 'production', 'discrimination', 'procedure', 'transfer')),
    evidence_criteria_json TEXT   NOT NULL DEFAULT '[]',
    state                 TEXT    NOT NULL CHECK (state IN ('not_started', 'introduced', 'independent_evidence', 'delayed_evidence', 'review_due', 'needs_review', 'overridden')),
    version               INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT    NOT NULL,
    UNIQUE (plan_id, ordinal)
);
CREATE INDEX idx_objectives_plan_id ON objectives (plan_id);
CREATE INDEX idx_objectives_state ON objectives (state);

CREATE TABLE enrollments (
    id            TEXT    NOT NULL PRIMARY KEY,
    course_id     TEXT    NOT NULL REFERENCES courses (id),
    learner_label TEXT,
    status        TEXT    NOT NULL CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    revision      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE INDEX idx_enrollments_course_id ON enrollments (course_id);
CREATE INDEX idx_enrollments_status ON enrollments (status);

CREATE TABLE checks (
    id             TEXT    NOT NULL PRIMARY KEY,
    objective_id   TEXT    NOT NULL REFERENCES objectives (id),
    version        INTEGER NOT NULL,
    evidence_target TEXT   NOT NULL CHECK (evidence_target IN ('recall', 'comprehension', 'production', 'discrimination', 'procedure', 'transfer')),
    stimulus_json  TEXT    NOT NULL,
    rubric_json    TEXT    NOT NULL,
    reference_json TEXT    NOT NULL,
    locale         TEXT,
    audit_state    TEXT    NOT NULL CHECK (audit_state IN ('pending', 'passed', 'failed')),
    state          TEXT    NOT NULL CHECK (state IN ('open', 'closed', 'superseded')),
    created_at     TEXT    NOT NULL,
    UNIQUE (objective_id, version)
);
CREATE INDEX idx_checks_objective_id ON checks (objective_id);
CREATE INDEX idx_checks_state ON checks (state);

CREATE TABLE attempts (
    id                     TEXT    NOT NULL PRIMARY KEY,
    enrollment_id          TEXT    NOT NULL REFERENCES enrollments (id),
    check_id               TEXT    NOT NULL REFERENCES checks (id),
    check_version          INTEGER NOT NULL,
    attempt_nonce          TEXT    NOT NULL,
    answer_kind            TEXT    NOT NULL CHECK (answer_kind IN ('text', 'selection')),
    answer_json            TEXT    NOT NULL,
    answer_hash            TEXT    NOT NULL,
    verdict                TEXT    CHECK (verdict IN ('pass', 'partial', 'not_yet', 'needs_retry', 'clarification')),
    evidence_class         TEXT    NOT NULL CHECK (evidence_class IN ('cold', 'hinted', 'answer_shown', 'self_reported', 'parent_reported', 'override')),
    criteria_json          TEXT    NOT NULL DEFAULT '[]',
    grading_provenance_json TEXT   NOT NULL DEFAULT '{}',
    state                  TEXT    NOT NULL CHECK (state IN ('pending', 'committed', 'failed')),
    created_at             TEXT    NOT NULL,
    committed_at           TEXT,
    UNIQUE (enrollment_id, check_id, attempt_nonce)
);
CREATE INDEX idx_attempts_enrollment_id ON attempts (enrollment_id);
CREATE INDEX idx_attempts_check_id ON attempts (check_id);
CREATE INDEX idx_attempts_state ON attempts (state);

CREATE TABLE transitions (
    id            TEXT    NOT NULL PRIMARY KEY,
    enrollment_id TEXT    NOT NULL REFERENCES enrollments (id),
    attempt_id    TEXT REFERENCES attempts (id),
    from_revision INTEGER NOT NULL,
    to_revision   INTEGER NOT NULL,
    next_action   TEXT    NOT NULL CHECK (next_action IN ('continue', 'retry_attempt', 'explain', 'select_alternative', 'review_objective', 'complete_objective', 'complete_course', 'await_override', 'retry_grading', 'rebind_session')),
    created_at    TEXT    NOT NULL,
    UNIQUE (enrollment_id, to_revision)
);
CREATE INDEX idx_transitions_enrollment_id ON transitions (enrollment_id);
CREATE INDEX idx_transitions_attempt_id ON transitions (attempt_id);

CREATE TABLE evidence (
    id             TEXT    NOT NULL PRIMARY KEY,
    enrollment_id  TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id   TEXT    NOT NULL REFERENCES objectives (id),
    attempt_id     TEXT REFERENCES attempts (id),
    layer          INTEGER NOT NULL CHECK (layer IN (1, 2, 3)),
    kind           TEXT    NOT NULL,
    evidence_class TEXT    NOT NULL CHECK (evidence_class IN ('cold', 'hinted', 'answer_shown', 'self_reported', 'parent_reported', 'override')),
    created_at     TEXT    NOT NULL
);
CREATE INDEX idx_evidence_enrollment_objective ON evidence (enrollment_id, objective_id);
CREATE INDEX idx_evidence_attempt_id ON evidence (attempt_id);
CREATE INDEX idx_evidence_layer ON evidence (layer);

CREATE TABLE bindings (
    id                 TEXT    NOT NULL PRIMARY KEY,
    enrollment_id      TEXT    NOT NULL REFERENCES enrollments (id),
    profile            TEXT    NOT NULL,
    connection_id      TEXT,
    runtime_session_id TEXT,
    stored_session_id  TEXT,
    cwd_fingerprint    TEXT,
    compression_tip    TEXT,
    status             TEXT    NOT NULL CHECK (status IN ('active', 'paused', 'detached', 'branched', 'completed', 'orphaned')),
    revision           INTEGER NOT NULL DEFAULT 0,
    updated_at         TEXT    NOT NULL
);
CREATE INDEX idx_bindings_enrollment_id ON bindings (enrollment_id);
CREATE INDEX idx_bindings_stored_session_id ON bindings (stored_session_id);
CREATE INDEX idx_bindings_runtime_session_id ON bindings (runtime_session_id);
CREATE INDEX idx_bindings_status ON bindings (status);

CREATE TABLE sources (
    id             TEXT    NOT NULL PRIMARY KEY,
    course_id      TEXT    NOT NULL REFERENCES courses (id),
    url            TEXT,
    title          TEXT    NOT NULL,
    source_type    TEXT    NOT NULL,
    published_at   TEXT,
    fetched_at     TEXT    NOT NULL,
    support_status TEXT    NOT NULL CHECK (support_status IN ('unassessed', 'model_assessed', 'conflicting', 'authoritative_documentation', 'stale', 'unreachable')),
    claim_count    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL
);
CREATE INDEX idx_sources_course_id ON sources (course_id);
CREATE INDEX idx_sources_support_status ON sources (support_status);

CREATE TABLE artifacts (
    id              TEXT    NOT NULL PRIMARY KEY,
    course_id       TEXT REFERENCES courses (id),
    kind            TEXT    NOT NULL CHECK (kind IN ('visual', 'audio', 'pdf', 'pack', 'export', 'other')),
    content_hash    TEXT    NOT NULL,
    path            TEXT    NOT NULL,
    bytes           INTEGER NOT NULL,
    mime            TEXT    NOT NULL,
    provenance_json TEXT    NOT NULL DEFAULT '{}',
    ref_count       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL,
    UNIQUE (content_hash, kind)
);
CREATE INDEX idx_artifacts_course_id ON artifacts (course_id);
CREATE INDEX idx_artifacts_kind ON artifacts (kind);

CREATE TABLE jobs (
    id               TEXT    NOT NULL PRIMARY KEY,
    kind             TEXT    NOT NULL CHECK (kind IN ('plan', 'research', 'media', 'export', 'import')),
    state            TEXT    NOT NULL CHECK (state IN ('queued', 'running', 'cancel_requested', 'cancelling', 'cancelled', 'completed', 'completed_late', 'failed', 'interrupted_requires_retry')),
    operation_id     TEXT,
    brief_json       TEXT    NOT NULL DEFAULT '{}',
    checkpoint_json  TEXT    NOT NULL DEFAULT '{}',
    attempt_id       TEXT,
    lease_owner      TEXT,
    lease_expires_at TEXT,
    progress_json    TEXT    NOT NULL DEFAULT '{}',
    error_json       TEXT    NOT NULL DEFAULT '{}',
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL
);
CREATE INDEX idx_jobs_state ON jobs (state);
CREATE INDEX idx_jobs_kind ON jobs (kind);
CREATE INDEX idx_jobs_operation_id ON jobs (operation_id);

CREATE TABLE usage_events (
    id             TEXT    NOT NULL PRIMARY KEY,
    operation_id   TEXT,
    enrollment_id  TEXT REFERENCES enrollments (id),
    provider       TEXT,
    model          TEXT,
    tokens_json    TEXT    NOT NULL DEFAULT '{}',
    duration_ms    INTEGER,
    artifact_count INTEGER NOT NULL DEFAULT 0,
    recorded_at    TEXT    NOT NULL
);
CREATE INDEX idx_usage_events_enrollment_id ON usage_events (enrollment_id);
CREATE INDEX idx_usage_events_operation_id ON usage_events (operation_id);

CREATE TABLE notebook_entries (
    id             TEXT    NOT NULL PRIMARY KEY,
    enrollment_id  TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id   TEXT    NOT NULL REFERENCES objectives (id),
    lesson_run_id  TEXT,
    kind           TEXT    NOT NULL CHECK (kind IN ('lesson_segment', 'artifact', 'source_passage', 'personal_note', 'quiz_moment')),
    excerpt        TEXT,
    note           TEXT,
    tags_json      TEXT    NOT NULL DEFAULT '[]',
    source_ref     TEXT,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL
);
CREATE INDEX idx_notebook_entries_enrollment_id ON notebook_entries (enrollment_id);
CREATE INDEX idx_notebook_entries_objective_id ON notebook_entries (objective_id);

CREATE TABLE idempotency_keys (
    key           TEXT NOT NULL PRIMARY KEY,
    payload_hash  TEXT NOT NULL,
    method        TEXT NOT NULL,
    operation_id  TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE INDEX idx_idempotency_keys_operation_id ON idempotency_keys (operation_id);
