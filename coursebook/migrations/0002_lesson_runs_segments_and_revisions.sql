-- Coursebook schema v2 (cb.db v2, commit 683201e).
-- Additive only: no v1 column is dropped or retyped. Impact is the contract's `migration_plan`:
--   * lesson_runs / lesson_segments become the durable textbook + lesson page record;
--   * bindings gain the run/objective they govern (NULL means "detached for section resume");
--   * notebook entries and packs gain their own revision fence;
--   * packs gain a lifecycle state so "removed" content never cascades into evidence.

CREATE TABLE lesson_runs (
    id             TEXT    NOT NULL PRIMARY KEY,
    enrollment_id  TEXT    NOT NULL REFERENCES enrollments (id),
    objective_id   TEXT    NOT NULL REFERENCES objectives (id),
    state          TEXT    NOT NULL CHECK (state IN ('active', 'paused', 'completed', 'abandoned')),
    revision       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    last_opened_at TEXT
);
CREATE INDEX idx_lesson_runs_enrollment_objective ON lesson_runs (enrollment_id, objective_id);
CREATE INDEX idx_lesson_runs_state ON lesson_runs (state);

CREATE TABLE lesson_segments (
    id            TEXT    NOT NULL PRIMARY KEY,
    lesson_run_id TEXT    NOT NULL REFERENCES lesson_runs (id),
    ordinal       INTEGER NOT NULL,
    kind          TEXT    NOT NULL CHECK (kind IN ('teaching', 'example', 'media', 'source_passage', 'check_prompt', 'feedback', 'summary')),
    text          TEXT,
    artifact_id   TEXT REFERENCES artifacts (id),
    source_id     TEXT REFERENCES sources (id),
    created_at    TEXT    NOT NULL,
    UNIQUE (lesson_run_id, ordinal)
);
CREATE INDEX idx_lesson_segments_lesson_run_id ON lesson_segments (lesson_run_id);

ALTER TABLE bindings ADD COLUMN lesson_run_id TEXT REFERENCES lesson_runs (id);
ALTER TABLE bindings ADD COLUMN objective_id TEXT REFERENCES objectives (id);

ALTER TABLE notebook_entries ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;

ALTER TABLE packs ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE packs ADD COLUMN state TEXT NOT NULL DEFAULT 'installed' CHECK (state IN ('installed', 'frozen', 'removed'));
CREATE INDEX idx_packs_state ON packs (state);
